"""Create ten completed, clearly marked S1 sales workflow examples."""

from odoo.exceptions import UserError
from odoo.tools import float_compare


def seed_sales_s1(env):
    admin = env.ref('base.user_admin')
    company = admin.company_id
    warehouse = env['stock.warehouse'].with_user(admin).search(
        [('company_id', '=', company.id)],
        limit=1,
    )
    products = env['product.product'].with_user(admin).search(
        [('default_code', '=', 'XPS15')],
        limit=2,
    )
    if not warehouse or len(products) != 1:
        raise UserError('Cần đúng một sản phẩm XPS15 và một kho công ty.')

    product = products
    if product.tracking != 'serial' or not product.is_storable:
        raise UserError('Sản phẩm XPS15 phải được lưu kho và theo dõi bằng serial.')
    warranty_months = product.product_tmpl_id.warranty_period_months
    if warranty_months < 0:
        raise UserError('Thời hạn bảo hành trên XPS15 không hợp lệ.')

    SaleOrder = env['sale.order'].with_user(admin)
    Partner = env['res.partner'].with_user(admin)
    Lot = env['stock.lot'].with_user(admin)
    Picking = env['stock.picking'].with_user(admin)
    Move = env['stock.move'].with_user(admin)
    MoveLine = env['stock.move.line'].with_user(admin)
    demo_order_count = 10
    prefix = 'DEMO-S1-SALES-'
    origins = [f'{prefix}{number:02d}' for number in range(1, demo_order_count + 1)]
    customer_emails = [
        f'demo.sales.s1.{number:02d}@example.test'
        for number in range(1, demo_order_count + 1)
    ]
    existing_orders = SaleOrder.search([('origin', 'in', origins)])
    if existing_orders:
        outgoing_by_order = {
            order.id: order.picking_ids.filtered(
                lambda picking: picking.picking_type_code == 'outgoing'
            )
            for order in existing_orders
        }
        if len(existing_orders) != len(origins) or any(
            order.origin not in origins
            or order.create_uid != admin
            or order.invoice_ids
            or order.state not in ('sale', 'done')
            or len(outgoing_by_order[order.id]) != 1
            or outgoing_by_order[order.id].state != 'done'
            for order in existing_orders
        ):
            raise UserError(
                'Bộ demo S1 đã tồn tại nhưng chưa hoàn tất hoặc có phát sinh '
                'ngoài dự kiến; không tự sửa giao dịch.'
            )
        for order in existing_orders:
            picking = outgoing_by_order[order.id]
            delivered_lots = picking.move_ids.move_line_ids.filtered(
                lambda line: line.quantity > 0
            ).lot_id
            if (
                len(delivered_lots) != 1
                or delivered_lots.x_custom_status != 'sold'
                or delivered_lots.x_customer_id != order.partner_id
                or delivered_lots.x_sale_order_id != order
                or not delivered_lots.x_sale_date
                or not delivered_lots.x_warranty_end_date
            ):
                raise UserError(
                    f'Đơn demo {order.name} thiếu lịch sử serial/bảo hành; '
                    'không tự sửa giao dịch.'
                )
        return existing_orders

    open_moves = env['stock.move'].with_user(admin).search([
        ('product_id', '=', product.id),
        ('state', 'in', ('confirmed', 'waiting', 'partially_available', 'assigned')),
        ('picking_id.picking_type_code', '=', 'outgoing'),
        ('location_id', 'child_of', warehouse.lot_stock_id.id),
    ])
    pending_quantity = sum(
        move.product_uom._compute_quantity(
            move.product_uom_qty,
            product.uom_id,
        )
        for move in open_moves
    )
    if float_compare(
        pending_quantity,
        round(pending_quantity),
        precision_digits=6,
    ):
        raise UserError(
            'Có đơn giao XPS15 đang chờ với số lượng serial không nguyên; '
            'không thể tạo dữ liệu demo an toàn.'
        )
    serial_count = demo_order_count + int(round(pending_quantity))
    serial_names = [
        f'DEMO-S1-XPS15-{number:03d}'
        for number in range(1, serial_count + 1)
    ]
    collision = Partner.search([
        ('email', 'in', customer_emails + ['demo.sales.s1.vendor@example.test']),
    ], limit=1)
    existing_lots = Lot.search([
        ('product_id', '=', product.id),
        ('name', 'in', serial_names),
    ])
    if collision or existing_lots:
        raise UserError(
            'Email hoặc serial thuộc bộ demo S1 đã được sử dụng; '
            'không ghi đè dữ liệu hiện có.'
        )

    customers = Partner.create([
        {
            'name': f'DEMO S1 Customer {number:02d}',
            'ref': f'DEMO-S1-KH{number:03d}',
            'email': email,
            'customer_rank': 1,
            'company_type': 'person',
        }
        for number, email in enumerate(customer_emails, start=1)
    ])
    vendor = Partner.create({
        'name': 'DEMO S1 Laptop Vendor',
        'email': 'demo.sales.s1.vendor@example.test',
        'supplier_rank': 1,
        'company_type': 'company',
    })
    lots = Lot.create([
        {
            'name': serial_name,
            'product_id': product.id,
            'company_id': company.id,
            'x_custom_status': 'available',
        }
        for serial_name in serial_names
    ])

    receipt_type = env['stock.picking.type'].with_user(admin).search([
        ('code', '=', 'incoming'),
        ('warehouse_id', '=', warehouse.id),
    ], limit=1)
    if not receipt_type:
        raise UserError('Không tìm thấy loại phiếu nhập kho của kho bán hàng.')
    receipt = Picking.create({
        'picking_type_id': receipt_type.id,
        'partner_id': vendor.id,
        'location_id': receipt_type.default_location_src_id.id,
        'location_dest_id': warehouse.lot_stock_id.id,
        'origin': 'DEMO-S1-RECEIPT',
        'company_id': company.id,
    })
    receipt_move = Move.create({
        'name': product.display_name,
        'product_id': product.id,
        'product_uom': product.uom_id.id,
        'product_uom_qty': len(lots),
        'picking_id': receipt.id,
        'picking_type_id': receipt_type.id,
        'location_id': receipt.location_id.id,
        'location_dest_id': receipt.location_dest_id.id,
        'company_id': company.id,
    })
    receipt.action_confirm()
    MoveLine.create([
        {
            'picking_id': receipt.id,
            'move_id': receipt_move.id,
            'company_id': company.id,
            'product_id': product.id,
            'product_uom_id': product.uom_id.id,
            'location_id': receipt.location_id.id,
            'location_dest_id': receipt.location_dest_id.id,
            'lot_id': lot.id,
            'quantity': 1,
            'picked': True,
        }
        for lot in lots
    ])
    result = receipt.button_validate()
    if isinstance(result, dict):
        raise UserError(
            'Phiếu nhập demo cần hoàn tất thêm bước: '
            f'{result.get("res_model", "xác nhận phiếu")}.'
        )
    available_quantity = product.with_context(
        location=warehouse.lot_stock_id.id,
        allowed_company_ids=[company.id],
    ).free_qty
    if float_compare(
        available_quantity,
        demo_order_count,
        precision_rounding=product.uom_id.rounding,
    ) < 0:
        raise UserError(
            f'Sau khi nhập kho chỉ còn {available_quantity:g} XPS15 khả dụng '
            f'cho {demo_order_count} đơn demo.'
        )

    orders = SaleOrder
    delivered_lot_ids = set()
    for number, customer in enumerate(customers, start=1):
        order = SaleOrder.create({
            'partner_id': customer.id,
            'origin': origins[number - 1],
            'company_id': company.id,
            'warehouse_id': warehouse.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        order.action_confirm()
        outgoing = order.picking_ids.filtered(
            lambda picking: picking.picking_type_code == 'outgoing'
        )
        if len(outgoing) != 1:
            raise UserError(f'Đơn {order.name} không tạo đúng một phiếu giao.')
        picking = outgoing
        picking.action_assign()
        move_lines = picking.move_ids.move_line_ids.filtered(
            lambda line: line.quantity > 0
        )
        if (
            len(move_lines) != 1
            or not move_lines.lot_id
            or move_lines.lot_id not in lots
            or move_lines.lot_id.id in delivered_lot_ids
        ):
            raise UserError(
                f'Đơn {order.name} chưa được gán đúng một serial demo khả dụng.'
            )
        delivered_lot_ids.add(move_lines.lot_id.id)
        result = picking.button_validate()
        if isinstance(result, dict):
            raise UserError(
                f'Phiếu giao {picking.name} cần hoàn tất thêm bước: '
                f'{result.get("res_model", "xác nhận phiếu")}.'
            )
        lot = move_lines.lot_id
        if (
            picking.state != 'done'
            or lot.x_custom_status != 'sold'
            or lot.x_customer_id != customer
            or lot.x_sale_order_id != order
            or not lot.x_sale_date
            or not lot.x_warranty_end_date
        ):
            raise UserError(
                f'Đơn {order.name} chưa ghi nhận đủ lịch sử bán và bảo hành.'
            )
        orders |= order

    if (
        len(orders) != demo_order_count
        or len(delivered_lot_ids) != demo_order_count
    ):
        raise UserError('Bộ demo S1 cần đúng 10 đơn và 10 serial riêng biệt.')
    env.cr.flush()
    return orders


demo_orders = seed_sales_s1(env)
env.cr.commit()
print('DEMO S1 SALES WORKFLOW')
for demo_order in demo_orders.sorted('origin'):
    print(
        demo_order.origin,
        demo_order.name,
        demo_order.partner_id.display_name,
        demo_order.state,
        ', '.join(demo_order.picking_ids.mapped('name')),
    )
