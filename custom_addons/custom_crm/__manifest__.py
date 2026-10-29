{
    'name': 'Danh mục Sản phẩm CRM',
    'version': '18.0.1.6.0',
    'summary': 'Quản lý danh mục laptop, phụ kiện và Serial Number',
    'author': 'Nhóm 5',
    'license': 'LGPL-3',
    'depends': ['stock', 'custom_warranty'],
    'data': [
        'data/product_categories.xml',
        'data/combo_sequence.xml',
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/product_combo_views.xml',
    ],
    'installable': True,
    'application': True,
}
