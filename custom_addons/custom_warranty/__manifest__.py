{
    'name': 'Custom Warranty - Đổi trả 1-1',
    'version': '1.0',
    'summary': 'Quản lý phiếu bảo hành và thuật toán đổi trả 1-1 cho thiết bị',
    'author': 'Nhóm 5',
    'depends': ['stock'], # Kế thừa ứng dụng Kho vận
    'data': [
        'security/ir.model.access.csv',
        'views/warranty_views.xml',
        'views/warranty_menus.xml',
    ],
    'installable': True,
    'application': True,
}