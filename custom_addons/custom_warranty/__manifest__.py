{
    'name': 'Quản lý Bảo hành & Đổi trả',
    'version': '18.0.1.0.0',
    'summary': 'Tiếp nhận sửa chữa, theo dõi bảo hành và xử lý đổi máy 1-1',
    'author': 'Nhóm 5',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'stock'],
    'data': [
        'data/warranty_sequence.xml',
        'security/ir.model.access.csv',
        'views/warranty_views.xml',
        'views/warranty_menus.xml',
    ],
    'demo': [
        'demo/warranty_demo.xml',
    ],
    'installable': True,
    'application': True,
}