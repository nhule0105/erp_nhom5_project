from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_serial_number_ids = fields.Many2many(
        'stock.lot',
        string='Serial nguồn nhập',
        help='Liên kết serial trong dữ liệu lịch sử đã nhập; không dùng để chọn serial giao hàng.',
        copy=False,
    )
