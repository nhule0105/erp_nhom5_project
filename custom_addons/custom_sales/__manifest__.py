{
    'name': 'Tự động hóa Bán hàng & Serial Number',
    'version': '18.0.1.0.0',
    'summary': 'Ghi nhận serial và chủ sở hữu khi hoàn tất giao hàng',
    'author': 'Nhóm 5',
    'depends': ['sale_management', 'stock', 'custom_warranty'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
}
