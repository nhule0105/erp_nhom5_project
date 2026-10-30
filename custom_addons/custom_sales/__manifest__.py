{
    'name': 'Quản lý Bán hàng Laptop',
    'version': '18.0.2.6.0',
    'summary': 'Quản lý đơn bán Laptop và lịch sử mua hàng',
    'author': 'Nhóm 5',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'stock', 'custom_warranty', 'custom_crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/customer_sequence.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
}
