{
    'name': 'Quản lý Bảo hành, Sửa chữa & Đổi mới 1-1',
    'version': '18.0.1.14.0',
    'summary': 'Tiếp nhận sửa chữa, theo dõi bảo hành và xử lý đổi máy 1-1',
    'author': 'Nhóm 5',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'stock'],
    'data': [
        'data/warranty_sequence.xml',
        'data/warranty_cron.xml',
        'security/warranty_security.xml',
        'security/ir.model.access.csv',
        'views/warranty_views.xml',
        'views/warranty_report_views.xml',
        'reports/warranty_receipt_report.xml',
        'views/warranty_menus.xml',
    ],
    'demo': [
        'demo/warranty_demo.xml',
    ],
    'installable': True,
    'application': True,
}