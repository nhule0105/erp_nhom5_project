import secrets
import string

from odoo import _, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_convert_untracked_serial_stock(self):
        self.ensure_one()
        product = self.product_variant_id
        if product.tracking != 'serial':
            raise UserError(
                _('Sản phẩm phải được đặt Theo số sê-ri duy nhất trước khi điều chỉnh.')
            )

        Quant = self.env['stock.quant'].sudo()
        Lot = self.env['stock.lot'].sudo()
        internal_locations = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
        ])
        untracked_quants = Quant.search([
            ('product_id', '=', product.id),
            ('location_id', 'in', internal_locations.ids),
            ('lot_id', '=', False),
            ('quantity', '>', 0),
        ])
        if not untracked_quants:
            return True

        total_quantity = sum(untracked_quants.mapped('quantity'))
        if float_compare(
            total_quantity,
            round(total_quantity),
            precision_rounding=product.uom_id.rounding,
        ):
            raise ValidationError(
                _('Tồn kho chưa gắn số sê-ri phải là số nguyên: %s.')
                % total_quantity
            )

        converted = self._convert_untracked_serial_quants(product, untracked_quants, Lot, Quant)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn tất điều chỉnh Serial'),
                'message': _(
                    'Đã tạo %s Serial cho %s. Tổng tồn kho không thay đổi.'
                ) % (converted, self.display_name),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_convert_selected_untracked_serial_stock(self):
        converted = 0
        products = self.filtered(
            lambda template: template.product_variant_id.tracking == 'serial'
        )
        Quant = self.env['stock.quant'].sudo()
        Lot = self.env['stock.lot'].sudo()
        internal_locations = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
        ])
        for template in products:
            product = template.product_variant_id
            untracked_quants = Quant.search([
                ('product_id', '=', product.id),
                ('location_id', 'in', internal_locations.ids),
                ('lot_id', '=', False),
                ('quantity', '>', 0),
            ])
            if not untracked_quants:
                continue
            total_quantity = sum(untracked_quants.mapped('quantity'))
            if float_compare(
                total_quantity,
                round(total_quantity),
                precision_rounding=product.uom_id.rounding,
            ):
                raise ValidationError(
                    _('Tồn kho chưa gắn số sê-ri của %s phải là số nguyên: %s.')
                    % (template.display_name, total_quantity)
                )
            converted += template._convert_untracked_serial_quants(
                product,
                untracked_quants,
                Lot,
                Quant,
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn tất tạo Serial'),
                'message': _('Đã tạo %s Serial cho các sản phẩm được chọn.') % converted,
                'type': 'success',
                'sticky': False,
            },
        }

    def _convert_untracked_serial_quants(self, product, untracked_quants, lot_model, quant_model):
        converted = 0
        for quant in untracked_quants:
            quantity = int(round(quant.quantity))
            for _index in range(quantity):
                lot = lot_model.create({
                    'name': self._generate_conversion_serial(product, lot_model),
                    'product_id': product.id,
                    'company_id': quant.company_id.id,
                    'x_custom_status': 'available',
                })
                quant_model.with_context(inventory_mode=True).create({
                    'product_id': product.id,
                    'location_id': quant.location_id.id,
                    'lot_id': lot.id,
                    'quantity': 0.0,
                    'inventory_quantity': 1.0,
                    'inventory_quantity_set': True,
                    'company_id': quant.company_id.id,
                }).action_apply_inventory()
                converted += 1

            quant.with_context(inventory_mode=True).write({
                'inventory_quantity': 0.0,
            })
            quant.action_apply_inventory()
        return converted

    @staticmethod
    def _generate_conversion_serial(product, lot_model):
        alphabet = string.ascii_uppercase + string.digits
        while True:
            name = ''.join(secrets.choice(alphabet) for _index in range(8))
            if not lot_model.search_count([
                ('name', '=', name),
                ('product_id', '=', product.id),
                ('company_id', 'in', [False, lot_model.env.company.id]),
            ]):
                return name
