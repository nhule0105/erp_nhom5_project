import os
import sys
import xmlrpc.client

sys.stdout.reconfigure(encoding='utf-8')

URL = os.environ.get('ODOO_URL', 'http://localhost:8069').rstrip('/')
DB = os.environ.get('ODOO_DB', 'erp_tramy')
USERNAME = os.environ.get('ODOO_USERNAME', 'admin')
PASSWORD = os.environ.get('ODOO_PASSWORD', '')


def connect():
    if not PASSWORD:
        raise RuntimeError('Set ODOO_PASSWORD to the Odoo admin user password.')

    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    version = common.version()
    print('Thông tin Odoo:', version.get('server_version'))

    uid = common.authenticate(DB, USERNAME, PASSWORD, {})
    if not uid:
        raise RuntimeError('Đăng nhập Odoo thất bại. Kiểm tra ODOO_DB / ODOO_USERNAME / ODOO_PASSWORD.')

    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
    print('Kết nối thành công. UID =', uid)
    return uid, models


def get_partner_count(models, uid):
    return models.execute_kw(
        DB,
        uid,
        PASSWORD,
        'res.partner',
        'search_count',
        [[]],
    )


def validate_sale_order_serials(models, uid, order_id, serial_numbers):
    order = models.execute_kw(
        DB,
        uid,
        PASSWORD,
        'sale.order',
        'read',
        [order_id],
        {'fields': ['name', 'state']},
    )

    if not order:
        raise RuntimeError('Sales Order không tồn tại.')

    if order[0].get('state') != 'sale':
        raise RuntimeError('Sales Order chưa được xác nhận.')

    return models.execute_kw(
        DB,
        uid,
        PASSWORD,
        'stock.lot',
        'validate_serial_number',
        [False, 1, serial_numbers],
    )


if __name__ == '__main__':
    try:
        uid, models = connect()
        print('Số đối tác hiện có:', get_partner_count(models, uid))
    except (OSError, RuntimeError, xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as exc:
        print('Lỗi kết nối Odoo:', exc)
        raise SystemExit(1) from exc
