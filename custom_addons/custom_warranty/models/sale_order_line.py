from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_product_tracking = fields.Selection(
        related='product_id.tracking',
        readonly=True,
    )
    x_serial_numbers = fields.Text(
        string='S/N đã quét',
        help='Nhập từng Serial Number trên một dòng.'
    )
    x_serial_number_ids = fields.Many2many(
        'stock.lot',
        string='Serial Number',
        copy=False,
    )

    def validate_serial_numbers_for_order_line(self):
        """Return the validated serials selected for this order line."""
        self.ensure_one()

        if not self.product_id or self.product_id.tracking != 'serial':
            return self.env['stock.lot']

        quantity = self.product_uom_qty or 0
        if quantity <= 0:
            return self.env['stock.lot']

        if float_compare(
            quantity,
            round(quantity),
            precision_digits=6,
        ):
            raise ValidationError('Sản phẩm theo dõi bằng serial phải có số lượng nguyên.')

        required_qty = int(round(quantity))
        lots = self.x_serial_number_ids

        if self.x_serial_numbers and not lots:
            serial_list = [
                serial.strip()
                for serial in self.x_serial_numbers.splitlines()
                if serial.strip()
            ]
            if len(serial_list) != len(set(serial_list)):
                raise ValidationError('Có S/N bị trùng trong danh sách quét.')
            lots = self.env['stock.lot'].search([
                ('name', 'in', serial_list),
                ('product_id', '=', self.product_id.id),
            ])
            if set(lots.mapped('name')) != set(serial_list):
                raise ValidationError(
                    'Có S/N không tồn tại hoặc không thuộc sản phẩm cần bán.'
                )
            self.x_serial_number_ids = [(6, 0, lots.ids)]

        if len(lots) != required_qty:
            raise ValidationError(
                f'Cần chọn đúng {required_qty} Serial Number cho sản phẩm này; '
                f'hiện đã chọn {len(lots)}.'
            )

        if any(lot.product_id != self.product_id for lot in lots):
            raise ValidationError('Serial Number được chọn không thuộc sản phẩm cần bán.')

        for lot in lots:
            if lot.x_custom_status != 'available':
                raise ValidationError(
                    f'S/N {lot.name} không còn ở trạng thái sẵn sàng bán.'
                )

            quants = self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('location_id.usage', '=', 'internal'),
            ])
            available_quantity = sum(quants.mapped('quantity')) - sum(
                quants.mapped('reserved_quantity')
            )
            if available_quantity <= 0:
                raise ValidationError(f'S/N {lot.name} không còn trong kho hoặc không khả dụng để xuất.')

        return lots

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered('x_serial_numbers'):
            record.validate_serial_numbers_for_order_line()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'x_serial_numbers' in vals and vals.get('x_serial_numbers'):
            for rec in self:
                rec.validate_serial_numbers_for_order_line()
        return result
