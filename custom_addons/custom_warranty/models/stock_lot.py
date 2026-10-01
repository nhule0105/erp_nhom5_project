from odoo import models, fields

class StockLot(models.Model):
    _inherit = 'stock.lot'

    # Khai báo thêm các trường Custom để phục vụ đồ án
    x_warranty_end_date = fields.Date(string="Hạn bảo hành")
    
    x_custom_status = fields.Selection([
        ('sold', 'Đã bán'),
        ('defective', 'Hàng lỗi')
    ], string="Trạng thái S/N", default='sold')
    
    x_customer_id = fields.Many2one('res.partner', string="Khách hàng sở hữu")