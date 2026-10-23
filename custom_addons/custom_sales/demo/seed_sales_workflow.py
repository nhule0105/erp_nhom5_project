"""Run by piping this file into ``odoo shell`` to seed the sales workflow."""

from odoo.exceptions import UserError
from odoo.tools import float_compare


def seed_sales_workflow(env):
    admin = env.ref('base.user_admin')
    company = admin.company_id
    warehouse = env['stock.warehouse'].with_user(admin).search(
        [('company_id', '=', company.id)],
        limit=1,
    )
    product = env['product.product'].with_user(admin).search(
        [('default_code', '=', 'XPS15')],
        limit=1,
    )
    if not warehouse or not product or product.tracking != 'serial':
        raise UserError(
            'Cần có kho và sản phẩm Laptop XPS15 được theo dõi bằng Serial Number.'
        )

    SaleOrder = env['sale.order'].with_user(admin)
    Partner = env['res.partner'].with_user(admin)
    Lot = env['stock.lot'].with_user(admin)
    Picking = env['stock.picking'].with_user(admin)
    Move = env['stock.move'].with_user(admin)
    MoveLine = env['stock.move.line'].with_user(admin)
    Quant = env['stock.quant'].with_user(admin)

    origins = [
        f'DEMO-SALES-WORKFLOW-{number:02d}'
        for number in range(1, 6)
    ]
    existing_orders = SaleOrder.search([('origin', 'in', origins)])
    customer_emails = [
        f'demo.sales.{number:02d}@example.test'
        for number in range(1, 6)
    ]
    existing_orders_by_origin = {
        order.origin: order for order in existing_orders
    }
    if existing_orders and (
        len(existing_orders) != 5
        or any(
            order.create_uid != admin
            or order.invoice_ids
            or order.state not in ('sale', 'done')
            or not order.picking_ids.filtered(
                lambda picking: picking.picking_type_code == 'outgoing'
            )
            or any(
                picking.state != 'done'
                for picking in order.picking_ids.filtered(
                    lambda picking: picking.picking_type_code == 'outgoing'
                )
            )
            for order in existing_orders
        )
    ):
        raise UserError(
            'Dữ liệu demo cũ chưa hoàn tất hoặc có phát sinh ngoài demo; '
            'không tự xóa giao dịch bán/giao hàng.'
        )
    reusing_completed_orders = bool(existing_orders)

    target_order_names = [
        f'S{number:05d}' for number in range(1, 6)
    ]
    legacy_orders = SaleOrder.search([
        ('name', 'in', target_order_names),
        ('origin', 'not in', origins),
    ])
    for order in legacy_orders:
        if order.invoice_ids or order.picking_ids:
            raise UserError(
                f'Không thể đổi mã {order.name}: đơn có hóa đơn hoặc phiếu kho.'
            )
        legacy_name = f'OLD-{order.name}'
        if SaleOrder.search([('name', '=', legacy_name)], limit=1):
            raise UserError(
                f'Mã lưu trữ {legacy_name} đã tồn tại; không tự ghi đè.'
            )
        order.write({'name': legacy_name})

    customers = []
    for number, email in enumerate(customer_emails, start=1):
        customer_code = f'KH{number:03d}'
        partner = Partner.search([('email', '=', email)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': f'Customer {customer_code}',
                'ref': customer_code,
                'email': email,
                'customer_rank': 1,
                'company_type': 'person',
            })
        else:
            non_demo_orders = partner.sale_order_ids - existing_orders
            if non_demo_orders:
                raise UserError(
                    f'Khách {partner.display_name} đang được đơn khác sử dụng.'
                )
            partner.write({
                'name': f'Customer {customer_code}',
                'ref': customer_code,
                'customer_rank': 1,
                'company_type': 'person',
            })
        customers.append(partner)

    lot_names = [f'DXPS15-{number:03d}' for number in range(1, 6)]
    lots = Lot.search([
        ('product_id', '=', product.id),
        ('name', 'in', lot_names),
    ])
    lots_by_name = {lot.name: lot for lot in lots}
    for lot_name in lot_names:
        if lot_name not in lots_by_name:
            lots_by_name[lot_name] = Lot.create({
                'name': lot_name,
                'product_id': product.id,
                'company_id': company.id,
                'x_custom_status': 'available',
            })
    lots = Lot.browse([
        lots_by_name[lot_name].id for lot_name in lot_names
    ])
    if reusing_completed_orders:
        demo_order_ids = set(existing_orders.ids)
        if any(
            lot.x_custom_status != 'sold'
            or lot.x_sale_order_id.id not in demo_order_ids
            for lot in lots
        ):
            raise UserError(
                'Serial demo đã giao không khớp với 5 đơn demo; '
                'không sửa lịch sử tồn kho.'
            )
    elif any(lot.x_custom_status != 'available' for lot in lots):
        raise UserError('Serial demo phải đang ở trạng thái Trong kho.')

    stock_location = warehouse.lot_stock_id
    lots_to_receive = Lot
    if not reusing_completed_orders:
        for lot in lots:
            internal_quants = Quant.search([
                ('lot_id', '=', lot.id),
                ('location_id', 'child_of', stock_location.id),
                ('location_id.usage', '=', 'internal'),
            ])
            on_hand_quantity = sum(internal_quants.mapped('quantity'))
            if float_compare(
                on_hand_quantity,
                1.0,
                precision_rounding=product.uom_id.rounding,
            ) < 0:
                if on_hand_quantity > 0:
                    raise UserError(
                        f'S/N {lot.name} có tồn kho không nguyên; cần xử lý tồn kho '
                        'trước khi tạo dữ liệu mẫu.'
                    )
                lots_to_receive |= lot

    if lots_to_receive:
        receipt_type = env['stock.picking.type'].with_user(admin).search([
            ('code', '=', 'incoming'),
            ('warehouse_id', '=', warehouse.id),
        ], limit=1)
        vendor = Partner.search(
            [('email', '=', 'demo.laptop.vendor@example.test')],
            limit=1,
        )
        if not vendor:
            vendor = Partner.create({
                'name': 'Demo Laptop Vendor',
                'email': 'demo.laptop.vendor@example.test',
                'supplier_rank': 1,
                'company_type': 'company',
            })
        elif vendor.name != 'Demo Laptop Vendor':
            vendor.write({'name': 'Demo Laptop Vendor'})
        if not receipt_type:
            raise UserError('Không tìm thấy loại phiếu nhập kho của kho bán hàng.')

        receipt = Picking.create({
            'picking_type_id': receipt_type.id,
            'partner_id': vendor.id,
            'location_id': receipt_type.default_location_src_id.id,
            'location_dest_id': stock_location.id,
            'origin': 'DEMO-SALES-WORKFLOW-RECEIPT',
            'company_id': company.id,
        })
        move = Move.create({
            'name': product.display_name,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': len(lots_to_receive),
            'picking_id': receipt.id,
            'picking_type_id': receipt_type.id,
            'location_id': receipt.location_id.id,
            'location_dest_id': stock_location.id,
            'company_id': company.id,
        })
        receipt.action_confirm()
        for lot in lots_to_receive:
            MoveLine.create({
                'picking_id': receipt.id,
                'move_id': move.id,
                'company_id': company.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': receipt.location_id.id,
                'location_dest_id': stock_location.id,
                'lot_id': lot.id,
                'quantity': 1,
                'picked': True,
            })
        result = receipt.button_validate()
        if isinstance(result, dict):
            raise UserError(
                'Phiếu nhập demo cần hoàn tất thêm bước: '
                f'{result.get("res_model", "xác nhận phiếu")}.'
            )

    orders = SaleOrder
    for number, partner in enumerate(customers, start=1):
        origin = origins[number - 1]
        order = existing_orders_by_origin.get(origin)
        if not order:
            order = SaleOrder.create({
                'partner_id': partner.id,
                'origin': origin,
                'company_id': company.id,
                'warehouse_id': warehouse.id,
                'order_line': [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 1,
                })],
            })
            order.action_confirm()
            outgoing_pickings = order.picking_ids.filtered(
                lambda picking: picking.picking_type_code == 'outgoing'
            )
            if len(outgoing_pickings) != 1:
                raise UserError(
                    f'Đơn {order.name} không tạo đúng một phiếu giao hàng.'
                )
            picking = outgoing_pickings
            picking.action_assign()
            result = picking.button_validate()
            if isinstance(result, dict):
                raise UserError(
                    f'Phiếu giao {picking.name} cần hoàn tất thêm bước: '
                    f'{result.get("res_model", "xác nhận phiếu")}.'
                )
        else:
            order.write({
                'name': target_order_names[number - 1],
                'partner_id': partner.id,
            })
            for picking in order.picking_ids.filtered(
                lambda record: record.picking_type_code == 'outgoing'
            ):
                picking.write({'partner_id': partner.id})
                picking.move_ids.move_line_ids.lot_id.write({
                    'x_customer_id': partner.id,
                })
        if order.name != target_order_names[number - 1]:
            order.write({'name': target_order_names[number - 1]})
        orders |= order

    sequence = env['ir.sequence'].with_user(admin).search(
        [('code', '=', 'sale.order'), ('company_id', '=', company.id)],
        limit=1,
    ) or env['ir.sequence'].with_user(admin).search(
        [('code', '=', 'sale.order'), ('company_id', '=', False)],
        limit=1,
    )
    if (
        sequence
        and sequence.implementation == 'standard'
        and not reusing_completed_orders
    ):
        sequence_name = f'ir_sequence_{sequence.id:03d}'
        env.cr.execute('SELECT to_regclass(%s)', [sequence_name])
        if env.cr.fetchone()[0]:
            env.cr.execute(
                'SELECT setval(%s, 5, true)',
                [sequence_name],
            )

    env.cr.flush()
    for records in (orders, orders.partner_id, orders.picking_ids):
        for record in records:
            if record.create_uid != admin:
                raise UserError(
                    f'Bản ghi {record.display_name} không được tạo bởi Administrator.'
                )
    return orders


demo_orders = seed_sales_workflow(env)
env.cr.commit()
print('DEMO SALES WORKFLOW')
for demo_order in demo_orders.sorted('origin'):
    print(
        demo_order.name,
        demo_order.partner_id.display_name,
        demo_order.state,
        demo_order.amount_total,
        demo_order.create_uid.display_name,
        ', '.join(demo_order.picking_ids.mapped('name')),
    )
