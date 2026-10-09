from odoo import models, fields, api  # type: ignore[reportMissingImports]

# ==============================================================
# 1. KẾ THỪA BẢNG STOCK.LOT (Quản lý Serial Number)
# ==============================================================
class StockLot(models.Model):
    _inherit = 'stock.lot'

    # Bổ sung các trường Custom phục vụ thuật toán đổi trả
    x_customer_id = fields.Many2one(
        'res.partner', 
        string='Khách hàng sở hữu',
        help='Khách hàng đang nắm giữ thiết bị này'
    )
    x_custom_status = fields.Selection([
        ('available', 'Sẵn sàng bán'),
        ('sold', 'Đã bán'),
        ('defective', 'Lỗi / Chờ xử lý')
    ], string='Trạng thái thiết bị', default='available')
    
    x_purchase_date = fields.Date(
        string='Ngày mua hàng', 
        help='Dùng để tính mốc 30 ngày bao test'
    )
    x_warranty_end_date = fields.Date(
        string='Ngày hết hạn bảo hành'
    )


# ==============================================================
# 2. TẠO MỚI BẢNG WARRANTY.TICKET (Phiếu Bảo hành & Đổi trả)
# ==============================================================
class WarrantyTicket(models.Model):
    _name = 'warranty.ticket'
    _description = 'Phiếu Hậu mãi và Đổi trả'
    _rec_name = 'ticket_code' # Hiển thị mã phiếu làm tên chính

    ticket_code = fields.Char(
        string='Mã phiếu', 
        required=True, 
        copy=False, 
        readonly=True, 
        default='Mới'
    )
    receive_date = fields.Date(
        string='Ngày tiếp nhận', 
        default=fields.Date.context_today
    )
    
    # Liên kết với bảng stock.lot (Máy cũ mang đến và Máy mới xuất đổi)
    serial_id = fields.Many2one(
        'stock.lot', 
        string='S/N Máy cũ (Lỗi)', 
        required=True
    )
    new_serial_id = fields.Many2one(
        'stock.lot', 
        string='S/N Máy mới (Đổi 1-1)'
    )

    issue_category = fields.Selection([
        ('nsx', 'Lỗi Nhà sản xuất'),
        ('user', 'Lỗi Người dùng (Rơi, vỡ, nước...)')
    ], string='Phân loại nguyên nhân')
    
    ticket_type = fields.Selection([
        ('repair', 'Sửa chữa dịch vụ'),
        ('exchange', 'Đổi trả 1-1')
    ], string='Loại nghiệp vụ xử lý')

    # Trạng thái Kanban phục vụ kéo thả (User Task)
    state = fields.Selection([
        ('new', 'Mới tiếp nhận'),
        ('fixing', 'Đang xử lý / Đang sửa'),
        ('done', 'Hoàn tất')
    ], string='Trạng thái', default='new')