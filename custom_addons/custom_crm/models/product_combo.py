from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductCombo(models.Model):
    _name = 'custom.crm.combo'
    _description = 'Combo sản phẩm cửa hàng'
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Mã Combo',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'custom.crm.combo'
        ) or 'New',
        index=True,
    )
    laptop_lot_id = fields.Many2one(
        'stock.lot',
        string='S/N Laptop',
        required=True,
        domain="[('lifecycle_status', '=', 'available')]",
    )
    mouse_lot_id = fields.Many2one(
        'stock.lot',
        string='S/N Chuột',
        required=True,
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

    def action_mark_issued(self):
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
