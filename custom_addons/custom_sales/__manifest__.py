{
    'name': 'Quản lý Bán hàng Laptop',
    'version': '18.0.1.1.0',
    'summary': 'Quản lý đơn bán Laptop, chọn Serial Number và lịch sử mua hàng',
    'author': 'Nhóm 5',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'stock', 'custom_warranty'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
}
