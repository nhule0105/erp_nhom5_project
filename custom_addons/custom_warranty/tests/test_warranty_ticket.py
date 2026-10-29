from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWarrantyTicket(TransactionCase):

    def _create_product(self):
        template = self.env['product.template'].create({
            'name': 'Warranty Test Laptop',
            'is_storable': True,
            'tracking': 'serial',
            'warranty_period_months': 12,
            'exchange_period_days': 30,
        })
        return template.product_variant_id

    def _create_lot(self, product, name, **values):
        return self.env['stock.lot'].create({
            'name': name,
            'product_id': product.id,
            **values,
        })

    def test_repair_workflow_updates_serial_status(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({
            'name': 'Warranty Customer',
            'phone': '0900000000',
        })
        lot = self._create_lot(
            product,
            'REPAIR-TEST-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=10),
            x_warranty_end_date=fields.Date.today() + timedelta(days=355),
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': lot.id,
            'ticket_type': 'repair',
            'fault_description': 'Không khởi động',
        })

        self.assertEqual(ticket.partner_id, partner)
        self.assertEqual(ticket.days_remaining, 355)
        self.assertEqual(ticket.warranty_status, 'valid')
        phone_lookup = self.env['warranty.ticket'].new({'customer_phone': partner.phone})
        phone_lookup._onchange_customer_phone()
        self.assertEqual(phone_lookup.serial_id, lot)
        ticket.action_start_repair()
        self.assertEqual(ticket.state, 'fixing')
        self.assertEqual(lot.x_custom_status, 'under_repair')
        ticket.action_waiting_parts()
        self.assertEqual(ticket.state, 'waiting_parts')
        ticket.action_resume_repair()
        ticket.repair_resolution = 'Thay linh kiện và kiểm tra đạt.'
        ticket.action_complete_repair()
        self.assertEqual(ticket.state, 'done')
        self.assertEqual(lot.x_custom_status, 'sold')
        self.assertTrue(ticket.completed_date)

    def test_exchange_moves_lots_and_preserves_warranty(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Exchange Customer'})
        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
            })],
        })
        sale_order_line = sale_order.order_line
        purchase_date = fields.Date.today() - timedelta(days=10)
        warranty_end = fields.Date.today() + timedelta(days=355)
        old_lot = self._create_lot(
            product,
            'EXCHANGE-OLD-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_sale_order_id=sale_order.id,
            x_sale_order_line_id=sale_order_line.id,
            x_purchase_date=purchase_date,
            x_warranty_end_date=warranty_end,
        )
        new_lot = self._create_lot(product, 'EXCHANGE-NEW-001', x_custom_status='available')
        customer_location = self.env.ref('stock.stock_location_customers')
        internal_location = self.env.ref('stock.stock_location_stock')
        loss_location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('scrap_location', '=', False),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        quant_model = self.env['stock.quant']
        quant_model._update_available_quantity(product, customer_location, 1, lot_id=old_lot)
        quant_model._update_available_quantity(product, internal_location, 1, lot_id=new_lot)
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'new_serial_id': new_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        ticket.action_approve_exchange()

        self.assertEqual(ticket.state, 'done')
        self.assertEqual(old_lot.x_custom_status, 'defective')
        self.assertEqual(new_lot.x_custom_status, 'sold')
        self.assertEqual(new_lot.x_customer_id, partner)
        self.assertEqual(new_lot.x_sale_order_line_id, sale_order_line)
        self.assertEqual(new_lot.x_purchase_date, purchase_date)
        self.assertEqual(new_lot.x_warranty_end_date, warranty_end)
        self.assertEqual(new_lot.x_replaced_from_lot_id, old_lot)
        self.assertEqual(old_lot.x_replacement_lot_ids, new_lot)
        self.assertEqual(old_lot.warranty_ticket_ids, ticket)
        self.assertEqual(new_lot.replacement_ticket_ids, ticket)
        follow_up_ticket = self.env['warranty.ticket'].create({
            'serial_id': new_lot.id,
            'ticket_type': 'repair',
            'fault_description': 'Lỗi phát sinh sau khi đổi máy',
        })
        self.assertEqual(follow_up_ticket.partner_id, partner)
        self.assertEqual(follow_up_ticket.sale_order_line_id, sale_order_line)
        self.assertEqual(follow_up_ticket.warranty_end_date, warranty_end)
        old_move = self.env['stock.move'].search([
            ('move_line_ids.lot_id', '=', old_lot.id),
            ('state', '=', 'done'),
        ], limit=1)
        new_move = self.env['stock.move'].search([
            ('move_line_ids.lot_id', '=', new_lot.id),
            ('state', '=', 'done'),
        ], limit=1)
        self.assertTrue(old_move)
        self.assertEqual(old_move.location_id, customer_location)
        self.assertEqual(old_move.location_dest_id, loss_location)
        self.assertTrue(new_move)
        self.assertEqual(new_move.location_id, internal_location)
        self.assertEqual(new_move.location_dest_id, customer_location)
        old_loss_quants = quant_model.search([
            ('product_id', '=', product.id),
            ('lot_id', '=', old_lot.id),
            ('location_id', '=', loss_location.id),
        ])
        new_customer_quants = quant_model.search([
            ('product_id', '=', product.id),
            ('lot_id', '=', new_lot.id),
            ('location_id', '=', customer_location.id),
        ])
        self.assertEqual(sum(old_loss_quants.mapped('quantity')), 1)
        self.assertEqual(sum(new_customer_quants.mapped('quantity')), 1)
        self.assertEqual(ticket.exchange_move_ids, old_move | new_move)
        move_count = self.env['stock.move'].search_count([
            ('move_line_ids.lot_id', 'in', [old_lot.id, new_lot.id]),
        ])
        with self.assertRaises(UserError):
            ticket.action_approve_exchange()
        self.assertEqual(
            self.env['stock.move'].search_count([
                ('move_line_ids.lot_id', 'in', [old_lot.id, new_lot.id]),
            ]),
            move_count,
        )

    def test_exchange_rejects_expired_exchange_window(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Expired Exchange Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-EXPIRED-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=31),
            x_warranty_end_date=fields.Date.today() + timedelta(days=334),
        )
        new_lot = self._create_lot(product, 'EXCHANGE-EXPIRED-002', x_custom_status='available')
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'new_serial_id': new_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        with self.assertRaises(ValidationError):
            ticket.action_approve_exchange()

        self.assertEqual(ticket.state, 'new')
        self.assertEqual(old_lot.x_custom_status, 'sold')
        self.assertEqual(new_lot.x_custom_status, 'available')

    def test_exchange_waits_for_replacement_serial_then_completes(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Waiting Exchange Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-WAIT-OLD-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=10),
            x_warranty_end_date=fields.Date.today() + timedelta(days=355),
        )
        customer_location = self.env.ref('stock.stock_location_customers')
        internal_location = self.env.ref('stock.stock_location_stock')
        quant_model = self.env['stock.quant']
        quant_model._update_available_quantity(product, customer_location, 1, lot_id=old_lot)
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        ticket.action_wait_for_exchange_serial()

        self.assertEqual(ticket.state, 'waiting_serial')
        new_lot = self._create_lot(
            product,
            'EXCHANGE-WAIT-NEW-001',
            x_custom_status='available',
        )
        quant_model._update_available_quantity(product, internal_location, 1, lot_id=new_lot)
        ticket.write({'new_serial_id': new_lot.id})
        ticket.action_approve_exchange()

        self.assertEqual(ticket.state, 'done')
        self.assertEqual(old_lot.x_custom_status, 'defective')
        self.assertEqual(new_lot.x_custom_status, 'sold')
        self.assertEqual(new_lot.x_replaced_from_lot_id, old_lot)

    def test_exchange_can_be_referred_to_repair_with_audited_reason(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Exchange Referral Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-REFERRAL-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=40),
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'exchange_referral_reason': 'Đã quá hạn đổi; tiếp nhận sửa chữa theo chính sách bảo hành.',
        })

        ticket.action_refer_exchange_to_repair()

        self.assertEqual(ticket.ticket_type, 'repair')
        self.assertEqual(ticket.state, 'new')
        self.assertFalse(ticket.new_serial_id)
        self.assertEqual(ticket.exchange_referral_date, fields.Date.today())
        self.assertEqual(
            ticket.exchange_referral_reason,
            'Đã quá hạn đổi; tiếp nhận sửa chữa theo chính sách bảo hành.',
        )
        with self.assertRaises(UserError):
            ticket.write({'exchange_referral_reason': 'Thay đổi lịch sử'})
        ticket.action_start_repair()
        self.assertEqual(ticket.state, 'fixing')

    def test_exchange_referral_requires_a_reason(self):
        product = self._create_product()
        lot = self._create_lot(
            product,
            'EXCHANGE-REFERRAL-NO-REASON-001',
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=40),
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': lot.id,
            'ticket_type': 'exchange',
        })

        with self.assertRaises(ValidationError):
            ticket.action_refer_exchange_to_repair()

        self.assertEqual(ticket.ticket_type, 'exchange')
        self.assertEqual(ticket.state, 'new')

    def test_exchange_rolls_back_both_moves_when_second_step_fails(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Rollback Exchange Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-ROLLBACK-OLD-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=10),
            x_warranty_end_date=fields.Date.today() + timedelta(days=355),
        )
        new_lot = self._create_lot(product, 'EXCHANGE-ROLLBACK-NEW-001', x_custom_status='available')
        customer_location = self.env.ref('stock.stock_location_customers')
        internal_location = self.env.ref('stock.stock_location_stock')
        loss_location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('scrap_location', '=', False),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        quant_model = self.env['stock.quant']
        quant_model._update_available_quantity(product, customer_location, 1, lot_id=old_lot)
        quant_model._update_available_quantity(product, internal_location, 1, lot_id=new_lot)
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'new_serial_id': new_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        stock_move_model = type(self.env['stock.move'])
        original_action_done = stock_move_model._action_done

        def fail_after_recovering_old_serial(moves):
            old_move = moves.filtered(
                lambda move: old_lot in move.move_line_ids.lot_id
            )
            original_action_done(old_move)
            raise UserError('Simulated failure between the two exchange movements.')

        with self.assertRaises(UserError):
            with self.env.cr.savepoint():
                with patch.object(
                    stock_move_model,
                    '_action_done',
                    fail_after_recovering_old_serial,
                ):
                    ticket.action_approve_exchange()

        self.assertEqual(ticket.state, 'new')
        self.assertFalse(ticket.exchange_move_ids)
        self.assertEqual(old_lot.x_custom_status, 'sold')
        self.assertEqual(new_lot.x_custom_status, 'available')
        self.assertEqual(
            quant_model._get_available_quantity(product, customer_location, lot_id=old_lot),
            1,
        )
        self.assertEqual(
            quant_model._get_available_quantity(product, internal_location, lot_id=new_lot),
            1,
        )
        self.assertEqual(
            self.env['stock.move'].search_count([
                ('move_line_ids.lot_id', 'in', [old_lot.id, new_lot.id]),
                ('location_dest_id', '=', loss_location.id),
            ]),
            0,
        )

    def test_exchange_policy_uses_category_limits_and_accessory_window(self):
        category = self.env['product.category'].create({
            'name': 'Warranty Test Accessories',
            'exchange_item_type': 'accessory',
            'exchange_period_days': 365,
        })
        template = self.env['product.template'].create({
            'name': 'Warranty Test Accessory',
            'is_storable': True,
            'tracking': 'serial',
            'categ_id': category.id,
            'warranty_period_months': 12,
        })

        self.assertEqual(template._get_exchange_item_type(), 'accessory')
        self.assertEqual(template._get_exchange_period_days(), 365)
        with self.assertRaises(ValidationError):
            template.write({'exchange_period_days': 366})

        device_template = self.env['product.template'].create({
            'name': 'Warranty Test New Device',
            'is_storable': True,
            'tracking': 'serial',
            'warranty_period_months': 12,
        })
        self.assertEqual(device_template._get_exchange_period_days(), 30)
        with self.assertRaises(ValidationError):
            device_template.write({'exchange_period_days': 31})

    def test_exchange_policy_rejects_user_damage(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'User Damage Exchange Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-USER-DAMAGE-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=10),
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'user',
        })

        with self.assertRaises(ValidationError):
            ticket.action_wait_for_exchange_serial()

        self.assertEqual(ticket.state, 'new')

    def test_regular_stock_user_cannot_approve_exchange(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Permission Exchange Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-PERMISSION-OLD-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=10),
        )
        new_lot = self._create_lot(
            product,
            'EXCHANGE-PERMISSION-NEW-001',
            x_custom_status='available',
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'new_serial_id': new_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })
        stock_user = self.env['res.users'].create({
            'name': 'Warranty Stock User',
            'login': 'warranty-stock-user',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
            ])],
        })

        with self.assertRaises(AccessError):
            ticket.with_user(stock_user).action_approve_exchange()

        self.assertEqual(ticket.state, 'new')
        self.assertFalse(ticket.exchange_move_ids)

    def test_exchange_history_links_multiple_replacements(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Serial History Customer'})
        purchase_date = fields.Date.today() - timedelta(days=5)
        warranty_end = fields.Date.today() + timedelta(days=360)
        first_lot = self._create_lot(
            product,
            'EXCHANGE-HISTORY-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=purchase_date,
            x_warranty_end_date=warranty_end,
        )
        second_lot = self._create_lot(product, 'EXCHANGE-HISTORY-002', x_custom_status='available')
        third_lot = self._create_lot(product, 'EXCHANGE-HISTORY-003', x_custom_status='available')
        customer_location = self.env.ref('stock.stock_location_customers')
        internal_location = self.env.ref('stock.stock_location_stock')
        quant_model = self.env['stock.quant']
        quant_model._update_available_quantity(product, customer_location, 1, lot_id=first_lot)
        quant_model._update_available_quantity(product, internal_location, 1, lot_id=second_lot)
        first_ticket = self.env['warranty.ticket'].create({
            'serial_id': first_lot.id,
            'new_serial_id': second_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })
        first_ticket.action_approve_exchange()
        quant_model._update_available_quantity(product, internal_location, 1, lot_id=third_lot)
        second_ticket = self.env['warranty.ticket'].create({
            'serial_id': second_lot.id,
            'new_serial_id': third_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        second_ticket.action_approve_exchange()

        self.assertEqual(second_lot.x_replaced_from_lot_id, first_lot)
        self.assertEqual(second_lot.x_replacement_lot_ids, third_lot)
        self.assertEqual(third_lot.x_replaced_from_lot_id, second_lot)
        self.assertEqual(first_lot.x_replacement_lot_ids, second_lot)
        self.assertIn(first_ticket, first_lot.warranty_ticket_ids)
        self.assertIn(second_ticket, second_lot.warranty_ticket_ids)
        self.assertIn(second_ticket, third_lot.replacement_ticket_ids)

    def test_refund_return_type_is_not_supported(self):
        product = self._create_product()
        lot = self._create_lot(
            product,
            'RETURN-TYPE-REJECTED-001',
            x_custom_status='sold',
        )
        with self.assertRaises(ValueError):
            self.env['warranty.ticket'].create({
                'serial_id': lot.id,
                'ticket_type': 'return',
            })

    def test_operations_report_includes_repair_and_exchange_tickets(self):
        action = self.env.ref(
            'custom_warranty.action_warranty_operations_report'
        )
        self.assertEqual(action.res_model, 'warranty.ticket')
        self.assertFalse(action.domain)
        self.assertTrue(self.env.ref(
            'custom_warranty.view_warranty_operations_graph'
        ))
        self.assertTrue(self.env.ref(
            'custom_warranty.view_warranty_operations_pivot'
        ))
