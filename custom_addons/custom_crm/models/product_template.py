from odoo import fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    lifecycle_status = fields.Selection(
        [
            ('available', 'Sẵn sàng'),
            ('issued', 'Đã xuất'),
            ('defective', 'Lỗi chờ xử lý'),
        ],
        string='Trạng thái vòng đời S/N',
        default='available',
        required=True,
        index=True,
        help='Trạng thái của S/N trong luồng hàng hóa của cửa hàng.',
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    lifecycle_product_type = fields.Selection(
        [
            ('laptop', 'Laptop'),
            ('mouse', 'Chuột'),
            ('backpack', 'Balo'),
        ],
        string='Loại hàng nhập',
        help='Dùng để phân loại thành phần khi gộp Combo.',
    )
    brand = fields.Char(
        string='Thương hiệu',
        help='Thương hiệu của sản phẩm.',
    )
    cpu = fields.Char(
        string='CPU',
        help='Bộ xử lý, áp dụng chủ yếu cho laptop.',
    )
    ram = fields.Char(
        string='RAM',
        help='Dung lượng và loại RAM, áp dụng chủ yếu cho laptop.',
    )
    storage = fields.Char(
        string='Ổ cứng',
        help='Dung lượng và loại ổ cứng, áp dụng chủ yếu cho laptop.',
    )
    gpu = fields.Char(
        string='Card màn hình',
        help='Thông tin card màn hình, áp dụng chủ yếu cho laptop.',
    )
    mouse_connection = fields.Selection(
        [
            ('wired', 'Có dây'),
            ('wireless', 'Không dây'),
            ('bluetooth', 'Bluetooth'),
        ],
        string='Kết nối chuột',
    )
    mouse_dpi = fields.Char(string='DPI chuột')
    mouse_buttons = fields.Integer(string='Số nút chuột')
    mouse_color = fields.Char(string='Màu sắc chuột')
    backpack_material = fields.Char(string='Chất liệu balo')
    backpack_size = fields.Char(string='Kích thước balo')
    backpack_capacity = fields.Char(string='Sức chứa balo')
    backpack_color = fields.Char(string='Màu sắc balo')
