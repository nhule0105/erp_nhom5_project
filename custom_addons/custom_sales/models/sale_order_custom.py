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

    def action_confirm(self):
        for order in self:
            if order.state not in ('draft', 'sent'):
                continue
            order._check_sale_stock_availability()
        return super().action_confirm()

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
    )
    def _compute_serial_lot_ids(self):
        for order in self:
            order.serial_lot_ids = order.picking_ids.filtered(
                lambda picking: picking.state == 'done'
                and picking.picking_type_code == 'outgoing'
            ).move_ids.move_line_ids.lot_id


class StockPicking(models.Model):
    _inherit = 'stock.picking'

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

                    if lot.x_custom_status != 'available':
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
        self._validate_sale_delivery_serials()
        return super().button_validate()

    def _action_done(self):
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
                warranty_months = (
                    serial.product_id.product_tmpl_id._get_warranty_period_months()
                )
                serial.write({
                    'x_customer_id': picking.sale_id.partner_id.id or picking.partner_id.id,
                    'x_custom_status': 'sold',
                    'x_purchase_date': delivery_date,
                    'x_delivery_picking_id': picking.id,
                    'x_sale_order_id': picking.sale_id.id,
                    'x_sale_date': delivery_date,
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
