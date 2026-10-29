from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProductCombo(models.Model):
    _name = 'custom.crm.combo'
    _description = 'Combo sản phẩm cửa hàng'
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Tên combo',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'custom.crm.combo'
        ) or 'New',
        index=True,
    )
    combo_tier = fields.Selection(
        [
            ('under_13m', 'Dưới 13 triệu'),
            ('13m_to_15m', 'Từ 13 triệu đến dưới 15 triệu'),
            ('over_15m', 'Từ 15 triệu trở lên'),
        ],
        string='Mức hóa đơn',
        required=True,
        default='under_13m',
    )
    min_order_total = fields.Monetary(
        string='Tổng hóa đơn từ',
        currency_field='currency_id',
        required=True,
        default=0,
    )
    max_order_total = fields.Monetary(
        string='Tổng hóa đơn dưới',
        currency_field='currency_id',
        help='Để trống nếu không giới hạn trên.',
    )
    gift_value_limit = fields.Monetary(
        string='Giá trị quà tặng tối đa',
        currency_field='currency_id',
        required=True,
        default=0,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    component_product_ids = fields.Many2many(
        'product.product',
        'custom_crm_combo_product_rel',
        'combo_id',
        'product_id',
        string='Sản phẩm phụ kiện tặng',
        domain="[('is_storable', '=', True)]",
    )
    available_combo_count = fields.Integer(
        string='Số combo hiện có',
        compute='_compute_available_combo_inventory',
        help='Số combo có thể ghép từ tồn kho khả dụng hiện tại.',
    )
    component_serial_summary = fields.Text(
        string='Serial phụ kiện khả dụng',
        compute='_compute_available_combo_inventory',
        help='Danh sách Serial không trùng của từng phụ kiện trong kho.',
    )
    active = fields.Boolean(default=True)
    laptop_lot_id = fields.Many2one(
        'stock.lot',
        string='S/N Laptop',
        required=False,
        domain="[('lifecycle_status', '=', 'available')]",
    )
    mouse_lot_id = fields.Many2one(
        'stock.lot',
        string='S/N Chuột',
        required=False,
        domain="[('lifecycle_status', '=', 'available')]",
    )
    backpack_lot_id = fields.Many2one(
        'stock.lot',
        string='S/N Balo',
        domain="[('lifecycle_status', '=', 'available')]",
    )
    laptop_warranty_months = fields.Integer(
        string='Bảo hành Laptop (tháng)',
        default=12,
        required=True,
    )
    mouse_warranty_months = fields.Integer(
        string='Bảo hành Chuột (tháng)',
        default=3,
        required=True,
    )
    backpack_warranty_months = fields.Integer(
        string='Bảo hành Balo (tháng)',
        default=0,
        required=True,
    )
    state = fields.Selection(
        [
            ('available', 'Sẵn sàng'),
            ('issued', 'Đã xuất'),
            ('defective', 'Lỗi chờ xử lý'),
        ],
        string='Trạng thái Combo',
        default='available',
        required=True,
        index=True,
    )
    combo_product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm Combo',
        readonly=True,
        copy=False,
    )
    assembled_date = fields.Date(
        string='Ngày gộp Combo',
        default=fields.Date.context_today,
        required=True,
    )
    note = fields.Text(string='Ghi chú nhập kho')

    _sql_constraints = [
        ('combo_name_unique', 'unique(name)', 'Mã Combo phải là duy nhất.'),
    ]

    @api.constrains('laptop_lot_id', 'mouse_lot_id', 'backpack_lot_id')
    def _check_distinct_lots(self):
        for combo in self:
            lots = combo.laptop_lot_id | combo.mouse_lot_id | combo.backpack_lot_id
            if len(lots) != sum(bool(lot) for lot in (
                combo.laptop_lot_id,
                combo.mouse_lot_id,
                combo.backpack_lot_id,
            )):
                raise ValidationError('Mỗi S/N chỉ được sử dụng một lần trong Combo.')

    @api.constrains(
        'laptop_warranty_months',
        'mouse_warranty_months',
        'backpack_warranty_months',
    )
    def _check_warranty_months(self):
        for combo in self:
            if any(months < 0 for months in (
                combo.laptop_warranty_months,
                combo.mouse_warranty_months,
                combo.backpack_warranty_months,
            )):
                raise ValidationError('Thời hạn bảo hành không được âm.')

    @api.constrains('min_order_total', 'max_order_total', 'gift_value_limit')
    def _check_promotion_values(self):
        for combo in self:
            if combo.min_order_total < 0 or combo.gift_value_limit < 0:
                raise ValidationError('Giá trị combo không được âm.')
            if combo.max_order_total and combo.max_order_total <= combo.min_order_total:
                raise ValidationError(
                    'Mức hóa đơn tối đa phải lớn hơn mức hóa đơn tối thiểu.'
                )

    @api.constrains('component_product_ids')
    def _check_component_products(self):
        for combo in self:
            if len(combo.component_product_ids) > 4:
                raise ValidationError('Một combo không được quá 4 phụ kiện.')
            if any(not product.is_storable for product in combo.component_product_ids):
                raise ValidationError('Sản phẩm trong combo phải là hàng hóa lưu kho.')

    def _get_available_component_inventory(self, product):
        """Return unique available Serial names or the available quantity."""
        self.ensure_one()
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id.usage', '=', 'internal'),
            ('company_id', 'in', [False, self.company_id.id]),
        ])
        if product.tracking != 'serial':
            quantity = sum(
                quant.quantity - quant.reserved_quantity
                for quant in quants
            )
            return max(0, int(quantity)), []

        lots_by_name = {}
        for quant in quants:
            lot = quant.lot_id
            if not lot or quant.quantity - quant.reserved_quantity <= 0:
                continue
            if lot.lifecycle_status != 'available' or lot.x_custom_status != 'available':
                continue
            lots_by_name.setdefault(lot.name, lot)
        serials = sorted(lots_by_name)
        return len(serials), serials

    @api.depends('component_product_ids')
    def _compute_available_combo_inventory(self):
        for combo in self:
            if not combo.component_product_ids:
                combo.available_combo_count = 0
                combo.component_serial_summary = False
                continue

            component_counts = []
            summary_lines = []
            for product in combo.component_product_ids.sorted('display_name'):
                count, serials = combo._get_available_component_inventory(product)
                component_counts.append(count)
                if product.tracking == 'serial':
                    serial_text = ', '.join(serials) or 'Không có Serial khả dụng'
                    summary_lines.append(
                        '%s (%s): %s'
                        % (product.display_name, count, serial_text)
                    )
                else:
                    summary_lines.append(
                        '%s (tồn khả dụng: %s)' % (product.display_name, count)
                    )

            combo.available_combo_count = min(component_counts)
            combo.component_serial_summary = '\n'.join(summary_lines)

    def matches_order_total(self, amount_total):
        self.ensure_one()
        return (
            amount_total >= self.min_order_total
            and (
                not self.max_order_total
                or amount_total < self.max_order_total
            )
        )

    def _get_component_lots(self):
        self.ensure_one()
        return (
            self.laptop_lot_id,
            self.mouse_lot_id,
            self.backpack_lot_id,
        )

    def _validate_component_types(self):
        expected_types = (
            ('laptop_lot_id', 'laptop', 'Laptop'),
            ('mouse_lot_id', 'mouse', 'Chuột'),
            ('backpack_lot_id', 'backpack', 'Balo'),
        )
        for combo in self:
            for field_name, expected_type, label in expected_types:
                lot = combo[field_name]
                if lot and lot.product_id.product_tmpl_id.lifecycle_product_type != expected_type:
                    raise ValidationError(
                        'S/N %s phải thuộc sản phẩm loại %s.'
                        % (lot.name, label)
                    )
                if lot and lot.lifecycle_status != 'available':
                    raise ValidationError(
                        'S/N %s không ở trạng thái Sẵn sàng.' % lot.name
                    )

    def _set_warranty_dates(self):
        warranty_months = (
            ('laptop_lot_id', self.laptop_warranty_months),
            ('mouse_lot_id', self.mouse_warranty_months),
            ('backpack_lot_id', self.backpack_warranty_months),
        )
        for field_name, months in warranty_months:
            lot = self[field_name]
            if lot:
                lot.write({
                    'x_purchase_date': self.assembled_date,
                    'x_warranty_end_date': self.assembled_date + relativedelta(
                        months=months
                    ),
                })

    def action_create_combo(self):
        for combo in self:
            if combo.state != 'available':
                raise UserError('Chỉ có thể gộp Combo khi Combo đang ở trạng thái Sẵn sàng.')
            if combo.combo_product_id:
                raise UserError('Combo này đã được tạo thành sản phẩm.')
            combo._validate_component_types()
            product_template = self.env['product.template'].create({
                'name': combo.name,
                'type': 'consu',
            })
            combo.combo_product_id = product_template.product_variant_id
            combo._set_warranty_dates()
        return True

    def action_unbundle_combo(self):
        for combo in self:
            if combo.state == 'issued':
                raise UserError('Không thể tách Combo đã xuất.')
            combo._set_component_lifecycle('available')
            combo._set_warranty_dates()
            if combo.combo_product_id:
                combo.combo_product_id.product_tmpl_id.unlink()
            combo.combo_product_id = False
        return True

    def action_mark_issued(self):
        self._validate_component_types()
        self.write({'state': 'issued'})
        self._set_component_lifecycle('issued')

    def action_mark_defective(self):
        self.write({'state': 'defective'})
        self._set_component_lifecycle('defective')

    def action_mark_available(self):
        self.write({'state': 'available'})
        self._set_component_lifecycle('available')

    def _set_component_lifecycle(self, status):
        for combo in self:
            lots = combo.laptop_lot_id | combo.mouse_lot_id | combo.backpack_lot_id
            lots.write({'lifecycle_status': status})


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_combo_rule_id = fields.Many2one(
        'custom.crm.combo',
        string='Rule combo khuyến mại',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
