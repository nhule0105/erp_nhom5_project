from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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
