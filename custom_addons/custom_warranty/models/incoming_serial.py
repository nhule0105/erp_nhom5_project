import secrets
import string

from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _generate_incoming_serial_name(self, product, company):
        alphabet = string.ascii_uppercase + string.digits
        while True:
            name = ''.join(secrets.choice(alphabet) for _ in range(8))
            if not self.env['stock.lot'].search_count([
                ('name', '=', name),
                ('product_id', '=', product.id),
                ('company_id', 'in', [False, company.id]),
            ]):
                return name

    def _prepare_incoming_serial_lines(self):
        Lot = self.env['stock.lot']
        MoveLine = self.env['stock.move.line']
        for picking in self.filtered(lambda record: record.picking_type_code == 'incoming'):
            for move in picking.move_ids.filtered(
                lambda record: record.product_id.tracking == 'serial'
                and record.state not in ('done', 'cancel')
            ):
                required_quantity = move.product_uom._compute_quantity(
                    move.product_uom_qty,
                    move.product_id.uom_id,
                )
                if float_compare(
                    required_quantity,
                    round(required_quantity),
                    precision_digits=6,
                ):
                    raise ValidationError(
                        f'Số lượng nhập của {move.product_id.display_name} phải là '
                        'số nguyên khi theo dõi bằng Serial Number.'
                    )

                existing_lines = move.move_line_ids.filtered(
                    lambda line: line.lot_id or line.lot_name
                )
                blank_lines = move.move_line_ids.filtered(
                    lambda line: line.quantity > 0
                    and not line.lot_id
                    and not line.lot_name
                )
                existing_quantity = sum(
                    existing_lines.mapped('quantity_product_uom')
                )
                total_line_quantity = existing_quantity + sum(
                    blank_lines.mapped('quantity_product_uom')
                )
                if float_compare(
                    total_line_quantity,
                    required_quantity,
                    precision_digits=6,
                ) > 0:
                    raise ValidationError(
                        f'Phiếu nhập {picking.name} có nhiều Serial hơn số lượng '
                        f'của {move.product_id.display_name}.'
                    )

                missing_quantity = int(round(required_quantity - existing_quantity))
                if missing_quantity <= 0:
                    continue

                serial_lines = []
                for _index in range(missing_quantity):
                    lot = Lot.create({
                        'name': self._generate_incoming_serial_name(
                            move.product_id,
                            picking.company_id,
                        ),
                        'product_id': move.product_id.id,
                        'company_id': picking.company_id.id,
                        'x_custom_status': 'available',
                    })
                    if blank_lines:
                        line = blank_lines[0]
                        blank_lines -= line
                        line.write({'lot_id': lot.id, 'quantity': 1.0})
                    else:
                        serial_line = {
                            'picking_id': picking.id,
                            'move_id': move.id,
                            'company_id': picking.company_id.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'lot_id': lot.id,
                            'quantity': 1.0,
                        }
                        serial_lines.append(serial_line)
                if serial_lines:
                    MoveLine.create(serial_lines)

                generated_quantity = missing_quantity
                if float_compare(
                    existing_quantity + generated_quantity,
                    required_quantity,
                    precision_digits=6,
                ) != 0:
                    raise ValidationError(
                        f'Không tạo đủ Serial cho {move.product_id.display_name}: '
                        f'cần {required_quantity:g}, đã có '
                        f'{existing_quantity + generated_quantity:g}.'
                    )

    def button_validate(self):
        self._prepare_incoming_serial_lines()
        return super().button_validate()

    def action_confirm(self):
        result = super().action_confirm()
        self._prepare_incoming_serial_lines()
        return result

    def _action_done(self):
        result = super()._action_done()
        for picking in self.filtered(
            lambda record: record.picking_type_code == 'incoming'
        ):
            receipt_date = fields.Date.to_date(
                picking.date_done or fields.Date.context_today(picking)
            )
            for lot in picking.move_ids.move_line_ids.filtered(
                lambda line: line.quantity > 0 and line.lot_id
            ).lot_id:
                lot.write({
                    'x_custom_status': 'available',
                    'x_purchase_date': receipt_date,
                    'x_warranty_start_date': False,
                    'x_warranty_end_date': False,
                })
        return result
