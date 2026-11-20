from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def _get_serial_status_label(lot, statuses):
    if lot.x_custom_status == 'under_repair':
        return 'Đang sửa chữa'
    return statuses.get(lot.x_custom_status, 'Không xác định')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_serial_count = fields.Integer(
        string='Số Serial',
        compute='_compute_serial_count',
    )

    def _compute_serial_count(self):
        counts = defaultdict(int)
        lots = self.env['stock.lot'].sudo().search([
            ('product_id', 'in', self.ids),
            ('company_id', 'in', [False] + self.env.companies.ids),
        ])
        for lot in lots:
            counts[lot.product_id.id] += 1
        for product in self:
            product.x_serial_count = (
                counts[product.id] if product.tracking == 'serial' else 0
            )

    def get_serial_picker_data(self):
        self.ensure_one()
        self.check_access('read')
        if self.tracking != 'serial':
            return []

        lots = self.env['stock.lot'].sudo().search([
            ('product_id', '=', self.id),
            ('company_id', 'in', [False] + self.env.companies.ids),
        ], order='name, id')
        quantities = defaultdict(float)
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', '=', self.id),
            ('lot_id', 'in', lots.ids),
            ('location_id.usage', '=', 'internal'),
            ('company_id', 'in', [False] + self.env.companies.ids),
        ])
        for quant in quants:
            quantities[quant.lot_id.id] += (
                quant.quantity - quant.reserved_quantity
            )

        statuses = dict(self.env['stock.lot']._fields['x_custom_status'].selection)
        lifecycle_statuses = dict(
            self.env['stock.lot']._fields['lifecycle_status'].selection
        )
        return [
            {
                'id': lot.id,
                'name': lot.name,
                'status': lot.x_custom_status,
                'status_label': _get_serial_status_label(lot, statuses),
                'lifecycle_status_label': lifecycle_statuses.get(
                    lot.lifecycle_status,
                    _('Không xác định'),
                ),
                'selectable': (
                    lot.x_custom_status == 'available'
                    and lot.lifecycle_status == 'available'
                    and quantities[lot.id] > 0
                ),
            }
            for lot in lots
        ]

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_serial_count = fields.Integer(
        string='Số Serial',
        compute='_compute_serial_count',
    )

    def _compute_serial_count(self):
        counts = defaultdict(int)
        lots = self.env['stock.lot'].sudo().search([
            ('product_id.product_tmpl_id', 'in', self.ids),
            ('company_id', 'in', [False] + self.env.companies.ids),
        ])
        for lot in lots:
            counts[lot.product_id.product_tmpl_id.id] += 1
        for template in self:
            template.x_serial_count = (
                counts[template.id] if template.tracking == 'serial' else 0
            )

    def get_serial_picker_data(self):
        self.ensure_one()
        self.check_access('read')
        if self.tracking != 'serial':
            return []

        variants = self.product_variant_ids
        lots = self.env['stock.lot'].sudo().search([
            ('product_id', 'in', variants.ids),
            ('company_id', 'in', [False] + self.env.companies.ids),
        ], order='name, id')
        quantities = defaultdict(float)
        quants = self.env['stock.quant'].sudo().search([
            ('product_id', 'in', variants.ids),
            ('lot_id', 'in', lots.ids),
            ('location_id.usage', '=', 'internal'),
            ('company_id', 'in', [False] + self.env.companies.ids),
        ])
        for quant in quants:
            quantities[quant.lot_id.id] += (
                quant.quantity - quant.reserved_quantity
            )

        statuses = dict(self.env['stock.lot']._fields['x_custom_status'].selection)
        lifecycle_statuses = dict(
            self.env['stock.lot']._fields['lifecycle_status'].selection
        )
        can_select_from_template = len(variants) == 1
        return [
            {
                'id': lot.id,
                'name': lot.name,
                'status': lot.x_custom_status,
                'status_label': _get_serial_status_label(lot, statuses),
                'selection_message': (
                    _('Chọn biến thể trước')
                    if not can_select_from_template
                    and lot.x_custom_status == 'available'
                    and lot.lifecycle_status == 'available'
                    else False
                ),
                'lifecycle_status_label': lifecycle_statuses.get(
                    lot.lifecycle_status,
                    _('Không xác định'),
                ),
                'selectable': (
                    can_select_from_template
                    and lot.x_custom_status == 'available'
                    and lot.lifecycle_status == 'available'
                    and quantities[lot.id] > 0
                ),
            }
            for lot in lots
        ]


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.constrains('product_id', 'x_selected_serial_lot_ids')
    def _check_selected_serial_lot_status(self):
        for line in self:
            lots = line.x_selected_serial_lot_ids
            if not lots:
                continue
            if line.product_id.tracking != 'serial':
                raise ValidationError(
                    _('Chỉ sản phẩm theo dõi Serial mới được gán Serial.')
                )
            if any(lot.product_id != line.product_id for lot in lots):
                raise ValidationError(
                    _('Serial đã chọn không thuộc sản phẩm trên dòng đơn hàng.')
                )
            unavailable_lots = lots.filtered(
                lambda lot: (
                    lot.x_custom_status != 'available'
                    or lot.lifecycle_status != 'available'
                )
            )
            if unavailable_lots:
                raise ValidationError(
                    _('Không thể chọn Serial đã bán hoặc đang sửa: %s')
                    % ', '.join(unavailable_lots.mapped('name'))
                )
