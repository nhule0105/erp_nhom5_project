from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date

class StockLot(models.Model):
    _inherit = 'stock.lot'

    x_customer_id = fields.Many2one('res.partner', string='Khách hàng')
    x_custom_status = fields.Selection([
        ('available', 'Sẵn sàng bán'),
        ('sold', 'Đã bán'),
        ('defective', 'Lỗi / Chờ xử lý')
    ], string='Trạng thái thiết bị', default='available')
    x_purchase_date = fields.Date(string='Ngày mua hàng')
    x_warranty_end_date = fields.Date(string='Ngày hết hạn bảo hành')


class WarrantyTicket(models.Model):
    _name = 'warranty.ticket'
    _description = 'Phiếu Hậu mãi và Đổi trả'
    _rec_name = 'ticket_code'

    ticket_code = fields.Char(string='Mã phiếu', required=True, default=lambda self: 'NEW')
    receive_date = fields.Date(string='Ngày tiếp nhận', default=fields.Date.context_today)
    
    serial_id = fields.Many2one('stock.lot', string='S/N Máy cũ (Lỗi)', required=True)
    new_serial_id = fields.Many2one('stock.lot', string='S/N Máy mới (Đổi 1-1)')

    issue_category = fields.Selection([('nsx', 'Lỗi NSX'), ('user', 'Lỗi Người dùng')], string='Nguyên nhân')
    ticket_type = fields.Selection([('repair', 'Sửa chữa'), ('exchange', 'Đổi trả 1-1')], string='Loại xử lý')
    state = fields.Selection([('new', 'Mới tiếp nhận'), ('fixing', 'Đang xử lý'), ('done', 'Hoàn tất')], default='new', string='Trạng thái')

    # ==============================================================
    # THUẬT TOÁN ĐỔI TRẢ 1-1 (TỪ PSEUDOCODE)
    # ==============================================================
    def action_approve_exchange(self):
        for ticket in self:
            old_sn = ticket.serial_id
            new_sn = ticket.new_serial_id
            
            # PHẦN 1: VALIDATION
            if not old_sn or not new_sn:
                raise ValidationError("Lỗi: Phải chọn đầy đủ S/N cũ và S/N xuất đổi!")

            if old_sn.x_custom_status != 'sold':
                raise ValidationError("Lỗi: S/N cũ chưa được bán ra.")

            if new_sn.x_custom_status != 'available':
                raise ValidationError("Lỗi: S/N xuất đổi không có sẵn trong kho.")

            # Kiểm tra quy tắc Bao test 30 ngày
            if old_sn.x_purchase_date:
                days_used = (fields.Date.today() - old_sn.x_purchase_date).days
                if days_used > 30:
                    raise ValidationError("Lỗi: Sản phẩm đã vượt quá 30 ngày đổi mới. Vui lòng chuyển sang luồng Nhận bảo hành sửa chữa.")

            # PHẦN 2: THỰC THI GIAO DỊCH ATOMIC (Cấn trừ hiện vật & Bảo lưu)
            # 2.1 Thu hồi máy cũ vào kho lỗi
            old_sn.write({
                'x_custom_status': 'defective'
            })
            
            # 2.2 Xuất máy mới và 2.3 Bảo lưu quyền lợi
            new_sn.write({
                'x_custom_status': 'sold',
                'x_customer_id': old_sn.x_customer_id.id,
                'x_warranty_end_date': old_sn.x_warranty_end_date # Map đè ngày bảo hành
            })

            # Chốt trạng thái phiếu
            ticket.write({'state': 'done'})