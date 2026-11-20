{
    'name': 'Quản lý Bán hàng Laptop',
    'version': '18.0.2.10.0',
    'summary': 'Quản lý đơn bán Laptop và lịch sử mua hàng',
    'author': 'Nhóm 5',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'stock', 'custom_warranty', 'custom_crm'],
    'data': [
        'security/ir.model.access.csv',
        'data/customer_sequence.xml',
        'reports/report_invoice.xml',
        'reports/report_saleorder.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_sales/static/src/js/product_serial_picker.js',
            'custom_sales/static/src/xml/product_serial_picker.xml',
            'custom_sales/static/src/scss/product_serial_picker.scss',
        ],
    },
    'installable': True,
    'application': True,
}
