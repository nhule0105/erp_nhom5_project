from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_customer_code = fields.Char(
        related='partner_id.ref',
        string='Mã khách hàng',
        readonly=True,
        store=True,
    )
    serial_lot_ids = fields.Many2many(
        'stock.lot',
        string='Serial đã giao',
        compute='_compute_serial_lot_ids',
    )
    x_promotional_combo_id = fields.Many2one(
        'custom.crm.combo',
        string='Combo khuyến mãi',
        compute='_compute_promotional_combo',
    )
    x_promotional_gift_product_ids = fields.Many2many(
        'product.product',
        string='Quà tặng theo combo',
        compute='_compute_promotional_combo',
    )
    x_promotional_combo_message = fields.Char(
        string='Thông tin khuyến mãi',
        compute='_compute_promotional_combo',
    )

    def _apply_promotional_combo(self):
        SaleLine = self.env['sale.order.line']
        for order in self:
            if order.state not in ('draft', 'sent'):
                continue
            combo = order._get_matching_promotional_combo()
            if not combo:
                continue
            existing_gifts = order.order_line.filtered(
                lambda line: line.is_combo_gift
            ).mapped('product_id')
            for product in combo.component_product_ids - existing_gifts:
                SaleLine.create({
                    'order_id': order.id,
                    'product_id': product.id,
                    'name': 'Quà tặng combo: %s' % combo.name,
                    'product_uom_qty': 1,
                    'product_uom': product.uom_id.id,
                    'price_unit': 0,
                    'is_combo_gift': True,
                    'x_combo_rule_id': combo.id,
                })

    def _get_matching_promotional_combo(self):
        self.ensure_one()
        combos = self.env['custom.crm.combo'].search([
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
        ], order='min_order_total desc, id desc')
        return combos.filtered(
            lambda rule: rule.matches_order_total(self.amount_total)
        )[:1]

    @api.depends('amount_total', 'company_id')
    def _compute_promotional_combo(self):
        for order in self:
            combo = order._get_matching_promotional_combo()
            order.x_promotional_combo_id = combo
            order.x_promotional_gift_product_ids = combo.component_product_ids
            order.x_promotional_combo_message = (
                'Quà tặng được thêm vào đơn khi xác nhận.'
                if combo
                else 'Không có combo áp dụng cho tổng tiền hiện tại.'
            )

    def action_confirm(self):
        for order in self:
            if order.state not in ('draft', 'sent'):
                continue
            order._apply_promotional_combo()
            order._check_sale_stock_availability()
        result = super().action_confirm()
        self.mapped('picking_ids')._auto_assign_delivery_serials()
        return result

    def _check_sale_stock_availability(self):
        self.ensure_one()
        warehouse = self.warehouse_id
        location = warehouse.lot_stock_id
        if not location:
            raise ValidationError('Không tìm thấy vị trí kho xuất của đơn hàng.')

        quantities_by_product = {}
        for line in self.order_line.filtered(
            lambda item: not item.display_type
            and item.product_id
            and item.product_id.is_storable
        ):
            product = line.product_id
            quantity = line.product_uom._compute_quantity(
                line.product_uom_qty,
                product.uom_id,
            )
            quantities_by_product[product] = (
                quantities_by_product.get(product, 0.0) + quantity
            )

        for product, required_quantity in quantities_by_product.items():
            if product.tracking == 'serial':
                product.product_tmpl_id.action_convert_untracked_serial_stock()

            available_quantity = product.with_context(
                location=location.id,
                allowed_company_ids=[self.company_id.id],
            ).free_qty
            if float_compare(
                available_quantity,
                required_quantity,
                precision_digits=6,
            ) < 0:
                raise ValidationError(
                    f'Không đủ tồn kho cho {product.display_name}. '
                    f'Cần {required_quantity:g}, còn khả dụng {available_quantity:g}.'
                )

            if product.tracking != 'serial':
                continue

            if float_compare(
                required_quantity,
                round(required_quantity),
                precision_digits=6,
            ):
                raise ValidationError(
                    f'Số lượng {product.display_name} phải là số nguyên vì sản phẩm '
                    'được theo dõi bằng Serial Number.'
                )

            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', 'child_of', location.id),
                ('location_id.usage', '=', 'internal'),
                ('company_id', 'in', [False, self.company_id.id]),
                ('lot_id', '!=', False),
            ])
            free_quantity_by_lot = {}
            lots_by_id = {}
            for quant in quants:
                lot_id = quant.lot_id.id
                free_quantity_by_lot[lot_id] = (
                    free_quantity_by_lot.get(lot_id, 0.0)
                    + quant.quantity
                    - quant.reserved_quantity
                )
                lots_by_id[lot_id] = quant.lot_id
            available_lots = self.env['stock.lot'].browse([
                lot_id
                for lot_id, free_quantity in free_quantity_by_lot.items()
                if free_quantity > 0
                and lots_by_id[lot_id].x_custom_status == 'available'
                and lots_by_id[lot_id].lifecycle_status == 'available'
            ])
            required_serials = int(round(required_quantity))
            if len(available_lots) < required_serials:
                raise ValidationError(
                    f'{product.display_name} cần {required_serials} Serial Number '
                    f'khả dụng nhưng trong kho chỉ còn {len(available_lots)}.'
                )

    @api.depends(
        'picking_ids.state',
        'picking_ids.picking_type_code',
        'picking_ids.move_ids.move_line_ids.lot_id',
        'picking_ids.move_ids.move_line_ids.quantity',
    )
    def _compute_serial_lot_ids(self):
        for order in self:
            order.serial_lot_ids = order.picking_ids.filtered(
                lambda picking: picking.picking_type_code == 'outgoing'
                and picking.state != 'cancel'
            ).move_ids.move_line_ids.lot_id


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _auto_assign_delivery_serials(self):
        for picking in self.filtered(
            lambda record: record.picking_type_code == 'outgoing'
            and record.sale_id
        ):
            for move in picking.move_ids.filtered(
                lambda item: item.product_id.tracking == 'serial'
                and item.state not in ('done', 'cancel')
            ):
                required_quantity = move.product_uom._compute_quantity(
                    move.product_uom_qty,
                    move.product_id.uom_id,
                )
                assigned_lines = move.move_line_ids.filtered(
                    lambda line: line.quantity > 0 and line.lot_id
                )
                assigned_quantity = sum(
                    assigned_lines.mapped('quantity_product_uom')
                )
                missing_quantity = int(round(
                    required_quantity - assigned_quantity
                ))
                if missing_quantity <= 0:
                    continue

                used_lot_ids = set(assigned_lines.mapped('lot_id').ids)
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('location_id', 'child_of', move.location_id.id),
                    ('location_id.usage', '=', 'internal'),
                    ('company_id', 'in', [False, picking.company_id.id]),
                    ('lot_id', '!=', False),
                ])
                available_lots = []
                for quant in quants:
                    if quant.lot_id.id in used_lot_ids:
                        continue
                    if quant.lot_id.x_custom_status != 'available':
                        continue
                    if quant.quantity - quant.reserved_quantity > 0:
                        available_lots.append(quant.lot_id)
                        used_lot_ids.add(quant.lot_id.id)

                if len(available_lots) < missing_quantity:
                    raise ValidationError(
                        f'Không đủ S/N khả dụng để giao {move.product_id.display_name}. '
                        f'Cần thêm {missing_quantity}, chỉ còn '
                        f'{len(available_lots)}.'
                    )

                empty_lines = list(move.move_line_ids.filtered(
                    lambda line: line.quantity > 0 and not line.lot_id
                ))
                for lot in available_lots[:missing_quantity]:
                    if empty_lines:
                        line = empty_lines.pop(0)
                        remaining_quantity = line.quantity - 1.0
                        line.write({
                            'lot_id': lot.id,
                            'quantity': 1.0,
                        })
                        if remaining_quantity > 0:
                            remainder = self.env['stock.move.line'].create({
                                'picking_id': picking.id,
                                'move_id': move.id,
                                'company_id': picking.company_id.id,
                                'product_id': move.product_id.id,
                                'product_uom_id': move.product_uom.id,
                                'location_id': move.location_id.id,
                                'location_dest_id': move.location_dest_id.id,
                                'quantity': remaining_quantity,
                            })
                            empty_lines.append(remainder)
                    else:
                        self.env['stock.move.line'].create({
                            'picking_id': picking.id,
                            'move_id': move.id,
                            'company_id': picking.company_id.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'lot_id': lot.id,
                            'quantity': 1.0,
                        })

    def _validate_sale_delivery_serials(self):
        for picking in self.filtered(
            lambda record: record.picking_type_code == 'outgoing'
            and record.sale_id
        ):
            seen_lot_ids = set()
            for move in picking.move_ids.filtered(
                lambda item: item.product_id.tracking == 'serial'
            ):
                product = move.product_id
                required_quantity = move.product_uom._compute_quantity(
                    move.product_uom_qty,
                    product.uom_id,
                )
                done_lines = move.move_line_ids.filtered(
                    lambda line: line.quantity > 0
                )
                done_quantity = sum(
                    done_lines.mapped('quantity_product_uom')
                )
                if float_compare(
                    done_quantity,
                    required_quantity,
                    precision_digits=6,
                ) != 0:
                    raise ValidationError(
                        f'Phiếu giao cần đủ {required_quantity:g} sản phẩm '
                        f'{product.display_name}; hiện đã quét {done_quantity:g}.'
                    )

                for line in done_lines:
                    lot = line.lot_id
                    if not lot:
                        raise ValidationError(
                            f'Vui lòng quét S/N cho {product.display_name}.'
                        )
                    if lot.product_id != product:
                        raise ValidationError(
                            f'S/N {lot.name} không thuộc sản phẩm {product.display_name}.'
                        )
                    if float_compare(
                        line.quantity_product_uom,
                        1.0,
                        precision_digits=6,
                    ) != 0:
                        raise ValidationError(
                            f'Mỗi S/N của {product.display_name} phải tương ứng '
                            'với đúng một sản phẩm.'
                        )
                    if lot.id in seen_lot_ids:
                        raise ValidationError(
                            f'S/N {lot.name} bị quét trùng trong phiếu giao.'
                        )
                    seen_lot_ids.add(lot.id)

                    if (
                        lot.x_custom_status != 'available'
                        or lot.lifecycle_status != 'available'
                    ):
                        raise ValidationError(
                            f'S/N {lot.name} không còn khả dụng hoặc đã được bán.'
                        )
                    source_quants = self.env['stock.quant'].search([
                        ('lot_id', '=', lot.id),
                        ('location_id', 'child_of', move.location_id.id),
                        ('location_id.usage', '=', 'internal'),
                    ])
                    source_quantity = sum(source_quants.mapped('quantity'))
                    if float_compare(
                        source_quantity,
                        line.quantity_product_uom,
                        precision_digits=6,
                    ) < 0:
                        raise ValidationError(
                            f'S/N {lot.name} không còn trong kho xuất.'
                        )

    def button_validate(self):
        self._auto_assign_delivery_serials()
        self._validate_sale_delivery_serials()
        return super().button_validate()

    def _action_done(self):
        self._auto_assign_delivery_serials()
        self._validate_sale_delivery_serials()
        result = super()._action_done()
        for picking in self.filtered(
            lambda record: record.picking_type_code == 'outgoing'
            and record.sale_id
        ):
            delivery_date = fields.Date.to_date(
                picking.date_done or fields.Date.context_today(picking)
            )
            for move_line in picking.move_ids.filtered(
                lambda move: move.product_id.tracking == 'serial'
            ).move_line_ids.filtered(lambda line: line.quantity > 0):
                serial = move_line.lot_id
                if not serial:
                    continue
                warranty_months = serial.product_id.product_tmpl_id._get_warranty_period_months()
                serial.write({
                    'x_customer_id': picking.sale_id.partner_id.id or picking.partner_id.id,
                    'x_custom_status': 'sold',
                    'x_purchase_date': delivery_date,
                    'x_sale_order_line_id': move_line.move_id.sale_line_id.id,
                    'x_delivery_picking_id': picking.id,
                    'x_sale_order_id': picking.sale_id.id,
                    'x_sale_date': delivery_date,
                    'x_warranty_start_date': delivery_date,
                    'x_warranty_end_date': fields.Date.add(
                        delivery_date,
                        months=warranty_months,
                    ),
                })
        return result


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_custom_sale_order_ids = fields.One2many(
        'sale.order',
        'partner_id',
        string='Lịch sử mua hàng',
        domain=[('state', 'in', ['sale', 'done'])],
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        customer_search = (
            self.env.context.get('res_partner_search_mode') == 'customer'
        )
        for vals in vals_list:
            rank = vals.get(
                'customer_rank',
                self.env.context.get('default_customer_rank', 0),
            )
            if (
                not vals.get('ref')
                and not vals.get('parent_id')
                and (rank or customer_search)
            ):
                vals['ref'] = sequence.next_by_code(
                    'custom.sales.customer.v2'
                )
                if not vals['ref']:
                    raise ValidationError(
                        'Không tìm thấy chuỗi tự sinh mã khách hàng.'
                    )
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if vals.get('customer_rank'):
            customers_without_code = self.filtered(
                lambda partner: not partner.ref and not partner.parent_id
            )
            for partner in customers_without_code:
                code = self.env['ir.sequence'].next_by_code(
                    'custom.sales.customer.v2'
                )
                if not code:
                    raise ValidationError(
                        'Không tìm thấy chuỗi tự sinh mã khách hàng.'
                    )
                partner.write({'ref': code})
        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_combo_gift = fields.Boolean(
        string='Quà tặng combo',
        default=False,
        copy=False,
    )
    combo_parent_line_id = fields.Many2one(
        'sale.order.line',
        string='Thuộc Combo',
        copy=False,
        readonly=True,
        ondelete='cascade',
    )
    combo_component_line_ids = fields.One2many(
        'sale.order.line',
        'combo_parent_line_id',
        string='Thành phần Combo',
        copy=False,
    )
    combo_serial_lot_ids = fields.Many2many(
        'stock.lot',
        'sale_order_line_combo_serial_rel',
        'sale_line_id',
        'lot_id',
        string='Serial dự kiến của Combo',
        copy=False,
        domain="[('product_id', '=', product_id), ('product_qty', '>', 0), "
        "('x_custom_status', '=', 'available'), ('lifecycle_status', '=', 'available')]",
        help='Chọn Serial ở báo giá nếu đã biết; nếu chưa, nhân viên chọn trên phiếu giao.',
    )
    x_selected_product_details = fields.Text(
        string='Thông tin sản phẩm',
        compute='_compute_selected_product_details',
    )
    x_available_serial_lot_ids = fields.Many2many(
        'stock.lot',
        string='Serial sản phẩm/combo',
        compute='_compute_selected_product_details',
        help='Giữ tương thích với giao diện đã lưu; danh sách Serial không còn '
        'hiển thị trên đơn bán.',
    )
    x_available_stock_qty = fields.Float(
        string='Còn khả dụng',
        compute='_compute_selected_product_details',
        digits='Product Unit of Measure',
        help='Số lượng còn khả dụng trong kho của đơn. Với sản phẩm theo dõi Serial, '
        'chỉ tính các Serial còn hàng và chưa bị giữ chỗ.',
    )

    @api.depends(
        'product_id',
        'order_id.warehouse_id',
        'product_uom_qty',
        'product_id.stock_quant_ids.location_id',
        'product_id.stock_quant_ids.quantity',
        'product_id.stock_quant_ids.reserved_quantity',
        'product_id.stock_quant_ids.lot_id.x_custom_status',
        'product_id.stock_quant_ids.lot_id.lifecycle_status',
        'product_id.product_tmpl_id.brand',
        'product_id.product_tmpl_id.lifecycle_product_type',
        'product_id.product_tmpl_id.cpu',
        'product_id.product_tmpl_id.ram',
        'product_id.product_tmpl_id.storage',
        'product_id.product_tmpl_id.gpu',
        'product_id.product_tmpl_id.mouse_connection',
        'product_id.product_tmpl_id.mouse_dpi',
        'product_id.product_tmpl_id.mouse_buttons',
        'product_id.product_tmpl_id.mouse_color',
        'product_id.product_tmpl_id.backpack_material',
        'product_id.product_tmpl_id.backpack_size',
        'product_id.product_tmpl_id.backpack_capacity',
        'product_id.product_tmpl_id.backpack_color',
    )
    def _compute_selected_product_details(self):
        for line in self:
            product = line.product_id
            if not product:
                line.x_selected_product_details = False
                line.x_available_serial_lot_ids = False
                line.x_available_stock_qty = 0.0
                continue

            line.x_available_serial_lot_ids = False
            template = product.product_tmpl_id
            details = line._get_product_detail_lines(template)
            line.x_available_stock_qty = line._get_available_stock_quantity(
                product
            )
            if product.tracking in ('lot', 'serial') and not line.x_available_stock_qty:
                details.append('Chưa có Serial khả dụng trong kho.')
            elif product.tracking == 'none':
                details.append('Sản phẩm không theo dõi Serial Number.')

            line.x_selected_product_details = '\n'.join(details)

    def _get_available_stock_quantity(self, product):
        self.ensure_one()
        warehouse = self.order_id.warehouse_id
        if not warehouse or not warehouse.lot_stock_id:
            return 0.0
        if product.tracking == 'serial':
            return float(len(self._get_available_product_serials(product)))
        return max(
            product.with_context(
                location=warehouse.lot_stock_id.id,
                allowed_company_ids=[self.order_id.company_id.id],
            ).free_qty,
            0.0,
        )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            {
                **vals,
                **({'price_unit': 0.0} if vals.get('is_combo_gift') else {}),
            }
            for vals in vals_list
        ]
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('is_combo_gift'):
            vals['price_unit'] = 0.0
        return super().write(vals)

    @api.onchange('is_combo_gift')
    def _onchange_is_combo_gift(self):
        for line in self:
            if line.is_combo_gift:
                line.price_unit = 0.0

    @staticmethod
    def _get_product_detail_lines(template):
        product_type_labels = {
            'laptop': 'Laptop',
            'mouse': 'Chuột',
            'backpack': 'Ba lô',
        }
        details = []
        product_type = template.lifecycle_product_type
        if product_type:
            details.append(
                'Loại: %s' % product_type_labels.get(product_type, product_type)
            )
        if template.brand:
            details.append('Thương hiệu: %s' % template.brand)

        for label, value in (
            ('CPU', template.cpu),
            ('RAM', template.ram),
            ('Ổ cứng', template.storage),
            ('Card màn hình', template.gpu),
            ('DPI chuột', template.mouse_dpi),
            ('Số nút chuột', template.mouse_buttons),
            ('Màu sắc chuột', template.mouse_color),
            ('Chất liệu ba lô', template.backpack_material),
            ('Kích thước ba lô', template.backpack_size),
            ('Sức chứa ba lô', template.backpack_capacity),
            ('Màu sắc ba lô', template.backpack_color),
        ):
            if value:
                details.append('%s: %s' % (label, value))

        if template.mouse_connection:
            connection_labels = {
                'wired': 'Có dây',
                'wireless': 'Không dây',
                'bluetooth': 'Bluetooth',
            }
            details.append(
                'Kết nối chuột: %s'
                % connection_labels.get(
                    template.mouse_connection,
                    template.mouse_connection,
                )
            )
        return details

    def _get_available_product_serials(self, product):
        self.ensure_one()
        warehouse = self.order_id.warehouse_id
        if not warehouse or not warehouse.lot_stock_id:
            return self.env['stock.lot']

        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', 'child_of', warehouse.lot_stock_id.id),
            ('location_id.usage', '=', 'internal'),
            ('company_id', 'in', [False, self.order_id.company_id.id]),
            ('lot_id', '!=', False),
        ])
        available_quantity_by_lot = {}
        lots_by_id = {}
        for quant in quants:
            lot = quant.lot_id
            if (
                lot.x_custom_status != 'available'
                or lot.lifecycle_status != 'available'
            ):
                continue
            free_quantity = quant.quantity - quant.reserved_quantity
            available_quantity_by_lot[lot.id] = (
                available_quantity_by_lot.get(lot.id, 0.0) + free_quantity
            )
            lots_by_id[lot.id] = lot

        return self.env['stock.lot'].browse(
            sorted(
                (
                    lot_id
                    for lot_id, quantity in available_quantity_by_lot.items()
                    if quantity > 0
                ),
                key=lambda lot_id: lots_by_id[lot_id].name,
            )
        )
