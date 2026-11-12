import base64
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
            'exchange_item_type': 'new_device',
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

    def _create_repair_ticket(self, product, name, **lot_values):
        partner = self.env['res.partner'].create({
            'name': 'Warranty Policy Customer ' + name,
        })
        lot = self._create_lot(
            product,
            name,
            x_customer_id=partner.id,
            x_custom_status='sold',
            **lot_values,
        )
        return self.env['warranty.ticket'].create({
            'serial_id': lot.id,
            'ticket_type': 'repair',
            'fault_description': 'Mô tả lỗi kiểm thử.',
        })

    def _submit_for_approval(self, ticket):
        ticket.action_submit_for_approval()

    def _confirm_free_decision(self, ticket):
        ticket.write({
            'issue_category': 'nsx',
            'warranty_decision': 'free',
            'warranty_decision_reason': 'Còn hạn và xác định lỗi nhà sản xuất.',
        })
        with self.assertRaises(UserError):
            ticket.action_confirm_warranty_decision()
        self._submit_for_approval(ticket)
        self.assertEqual(ticket.approval_status, 'pending')
        ticket.action_confirm_warranty_decision()

    def test_warranty_decision_free_for_valid_manufacturer_fault(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-FREE-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )

        self.assertEqual(ticket.warranty_decision, 'pending')
        ticket.write({
            'issue_category': 'nsx',
            'warranty_decision': 'free',
            'warranty_decision_reason': 'Còn hạn và xác định lỗi nhà sản xuất.',
        })
        self._submit_for_approval(ticket)
        ticket.action_confirm_warranty_decision()

        self.assertEqual(ticket.warranty_decision, 'free')
        self.assertEqual(ticket.warranty_decision_user_id, self.env.user)
        self.assertTrue(ticket.warranty_decision_date)

    def test_warranty_decision_generates_reason_from_selected_policy(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-AUTO-REASON-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )
        ticket.write({
            'issue_category': 'nsx',
            'warranty_decision': 'free',
        })

        self._submit_for_approval(ticket)
        ticket.action_confirm_warranty_decision()

        self.assertIn('Lỗi nhà sản xuất', ticket.warranty_decision_reason)
        self.assertIn('Còn hạn', ticket.warranty_decision_reason)
        self.assertEqual(ticket.warranty_decision_user_id, self.env.user)

    def test_repair_can_start_with_selected_fault_symptom(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(product, 'REPAIR-CHECKBOX-FAULT-001')
        ticket.write({
            'fault_description': False,
            'symptom_power': True,
        })

        ticket.action_start_repair()

        self.assertEqual(ticket.state, 'fixing')
        self.assertEqual(ticket.fault_summary, 'Không lên nguồn')

    def test_intake_summary_distinguishes_unchecked_from_checked_items(self):
        ticket = self.env['warranty.ticket'].new()

        self.assertEqual(ticket.intake_checklist_summary, 'Chưa xác nhận mục nào.')

        ticket.screen_ok = True
        self.assertIn('Đạt: Màn hình bình thường.', ticket.intake_checklist_summary)
        self.assertIn('chưa được xác nhận', ticket.intake_checklist_summary)

    def test_warranty_decision_paid_for_valid_user_fault(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-PAID-USER-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )

        ticket.write({
            'issue_category': 'user',
            'warranty_decision': 'paid',
            'warranty_decision_reason': 'Còn hạn nhưng lỗi do người dùng.',
        })
        self._submit_for_approval(ticket)
        ticket.action_confirm_warranty_decision()

        self.assertEqual(ticket.warranty_decision, 'paid')

    def test_warranty_decision_paid_for_expired_warranty(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-PAID-EXPIRED-001',
            x_warranty_end_date=fields.Date.today() - timedelta(days=1),
        )

        ticket.write({
            'issue_category': 'nsx',
            'warranty_decision': 'paid',
            'warranty_decision_reason': 'Đã hết hạn bảo hành.',
        })
        self._submit_for_approval(ticket)
        ticket.action_confirm_warranty_decision()

        self.assertEqual(ticket.warranty_status, 'expired')
        self.assertEqual(ticket.warranty_decision, 'paid')

    def test_warranty_decision_waits_for_unknown_cause(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-UNKNOWN-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )

        with self.assertRaises(ValidationError):
            ticket.write({
                'warranty_decision': 'free',
                'warranty_decision_reason': 'Chưa đủ kết quả kiểm tra.',
            })

        self.assertEqual(ticket.warranty_decision, 'pending')
        self.assertFalse(ticket.warranty_decision_user_id)

    def test_regular_stock_user_cannot_confirm_warranty_decision(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-ACCESS-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )
        ticket.write({
            'issue_category': 'nsx',
            'warranty_decision': 'free',
            'warranty_decision_reason': 'Còn hạn và xác định lỗi nhà sản xuất.',
        })
        self._submit_for_approval(ticket)
        stock_user = self.env['res.users'].create({
            'name': 'Warranty Decision Stock User',
            'login': 'warranty-decision-stock-user',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
            ])],
        })

        with self.assertRaises(AccessError):
            ticket.with_user(stock_user).action_confirm_warranty_decision()

        self.assertFalse(ticket.warranty_decision_user_id)

    def test_decision_audit_cannot_be_written_directly_or_changed(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-AUDIT-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )
        self._confirm_free_decision(ticket)

        with self.assertRaises(UserError):
            ticket.write({'warranty_decision_reason': 'Sửa lại lịch sử'})
        with self.assertRaises(UserError):
            ticket.write({'warranty_decision_user_id': self.env.user.id})
        with self.assertRaises(UserError):
            ticket.write({'approval_status': 'approved'})
        with self.assertRaises(UserError):
            ticket.write({'issue_category': 'user'})
        with self.assertRaises(UserError):
            ticket.action_confirm_warranty_decision()

    def test_submitted_approval_locks_decision_inputs(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-APPROVAL-LOCK-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )
        ticket.write({
            'issue_category': 'nsx',
            'warranty_decision': 'free',
        })
        self._submit_for_approval(ticket)

        with self.assertRaises(UserError):
            ticket.write({'issue_category': 'user'})

    def test_staff_cannot_complete_exchange_by_spoofing_context(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Exchange State Permission Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-STATE-PERMISSION-OLD-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=10),
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'ticket_type': 'exchange',
        })
        stock_user = self.env['res.users'].create({
            'name': 'Warranty State Stock User',
            'login': 'warranty-state-stock-user',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('stock.group_stock_user').id,
            ])],
        })

        with self.assertRaises(UserError):
            ticket.with_user(stock_user).with_context(exchange_approval=True).write({
                'state': 'done',
            })

        self.assertEqual(ticket.state, 'new')

    def test_repair_cannot_be_completed_without_confirmed_decision(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'POLICY-COMPLETE-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )
        ticket.action_start_repair()
        ticket.repair_resolution = 'Đã sửa và kiểm tra đạt.'

        with self.assertRaises(ValidationError):
            ticket.action_complete_repair()

        self.assertNotEqual(ticket.state, 'done')

    def test_intake_checklist_attachments_assignment_and_sla(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(
            product,
            'INTAKE-CHECKLIST-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )
        attachment = self.env['ir.attachment'].create({
            'name': 'intake-device.jpg',
            'datas': base64.b64encode(b'fake-image-for-test'),
            'mimetype': 'image/jpeg',
        })
        ticket.write({
            'screen_condition': 'Màn hình không nứt, có một điểm sáng.',
            'keyboard_condition': 'Đủ phím, một phím bị kẹt.',
            'battery_charger_condition': 'Có sạc, pin còn nhận.',
            'accessories_condition': 'Thiếu túi chống sốc.',
            'intake_notes': 'Đã kiểm tra ngoại quan cùng khách.',
            'inspection_attachment_ids': [(4, attachment.id)],
            'technician_id': self.env.user.id,
            'promised_return_date': fields.Date.today() - timedelta(days=1),
        })
        self._confirm_free_decision(ticket)

        self.assertEqual(ticket.technician_id, self.env.user)
        self.assertTrue(ticket.technician_assigned_date)
        self.assertIn(attachment, ticket.inspection_attachment_ids)
        self.assertTrue(ticket.is_overdue)

        ticket.action_start_repair()
        self.assertTrue(ticket.repair_start_datetime)
        ticket.repair_resolution = 'Đã sửa và kiểm tra đạt.'
        ticket.action_complete_repair()
        self.assertTrue(ticket.repair_completed_datetime)
        self.assertGreaterEqual(ticket.processing_duration_hours, 0)
        self.assertFalse(ticket.is_overdue)

    def test_sla_defaults_and_allows_adjustment(self):
        product = self._create_product()
        ticket = self._create_repair_ticket(product, 'SLA-DEFAULT-001')

        self.assertEqual(ticket.sla_days, 3)
        self.assertEqual(
            ticket.promised_return_date,
            ticket.receive_date + timedelta(days=3),
        )

        adjusted_date = ticket.receive_date + timedelta(days=7)
        ticket.promised_return_date = adjusted_date
        self.assertEqual(ticket.promised_return_date, adjusted_date)

    def test_new_ticket_form_shows_sla_date_and_unchecked_checklists(self):
        receive_date = fields.Date.today()
        ticket_model = self.env['warranty.ticket']
        new_ticket = ticket_model.new()
        ticket = ticket_model.new({
            'receive_date': receive_date,
            'sla_days': 3,
        })

        self.assertEqual(
            new_ticket.promised_return_date,
            fields.Date.today() + timedelta(days=3),
        )
        ticket._onchange_sla_deadline()

        self.assertEqual(ticket.promised_return_date, receive_date + timedelta(days=3))
        for field_name in (
            'symptom_power',
            'symptom_charging',
            'symptom_display',
            'symptom_keyboard',
            'symptom_battery',
            'symptom_overheating',
            'symptom_network',
            'symptom_physical_damage',
            'symptom_other',
            'screen_ok',
            'keyboard_ok',
            'battery_charger_ok',
            'accessories_complete',
            'appearance_ok',
            'no_liquid_damage',
            'security_cleared',
        ):
            self.assertFalse(ticket[field_name], field_name)

    def test_sla_cron_marks_overdue_and_ignores_completed(self):
        product = self._create_product()
        overdue_ticket = self._create_repair_ticket(product, 'SLA-CRON-OVERDUE-001')
        completed_ticket = self._create_repair_ticket(
            product,
            'SLA-CRON-DONE-001',
            x_warranty_end_date=fields.Date.today() + timedelta(days=30),
        )
        self._confirm_free_decision(completed_ticket)
        overdue_ticket.promised_return_date = fields.Date.today() - timedelta(days=1)
        completed_ticket.promised_return_date = fields.Date.today() - timedelta(days=1)
        completed_ticket.action_start_repair()
        completed_ticket.repair_resolution = 'Đã hoàn tất sửa chữa.'
        completed_ticket.action_complete_repair()

        self.env['warranty.ticket']._cron_update_sla_overdue()

        self.assertTrue(overdue_ticket.is_overdue)
        self.assertFalse(completed_ticket.is_overdue)

    def test_exchange_ticket_is_not_overdue_by_repair_return_date(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Exchange SLA Customer'})
        lot = self._create_lot(
            product,
            'EXCHANGE-SLA-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=5),
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': lot.id,
            'ticket_type': 'exchange',
            'promised_return_date': fields.Date.today() - timedelta(days=1),
        })

        self.assertFalse(ticket.is_overdue)

        ticket.ticket_type = 'repair'

        self.assertTrue(ticket.is_overdue)

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
        self.assertIn(ticket, lot.warranty_ticket_ids)
        self.assertIn(ticket, ticket.serial_history_ids)
        self._confirm_free_decision(ticket)
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
        warranty_start = purchase_date
        warranty_end = fields.Date.today() + timedelta(days=355)
        old_lot = self._create_lot(
            product,
            'EXCHANGE-OLD-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_sale_order_id=sale_order.id,
            x_sale_order_line_id=sale_order_line.id,
            x_purchase_date=purchase_date,
            x_warranty_start_date=warranty_start,
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
            'fault_description': 'Lỗi nhà sản xuất cần kiểm tra.',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        with self.assertRaises(UserError):
            ticket.action_approve_exchange()
        self._submit_for_approval(ticket)
        ticket.action_approve_exchange()

        self.assertEqual(ticket.state, 'done')
        self.assertEqual(ticket.approval_status, 'approved')
        self.assertEqual(ticket.approval_user_id, self.env.user)
        self.assertTrue(ticket.approval_date)
        self.assertEqual(old_lot.x_custom_status, 'defective')
        self.assertEqual(new_lot.x_custom_status, 'sold')
        if 'lifecycle_status' in self.env['stock.lot']._fields:
            self.assertEqual(old_lot.lifecycle_status, 'defective')
            self.assertEqual(new_lot.lifecycle_status, 'issued')
        self.assertEqual(new_lot.x_customer_id, partner)
        self.assertEqual(new_lot.x_sale_order_line_id, sale_order_line)
        self.assertEqual(new_lot.x_purchase_date, purchase_date)
        self.assertEqual(new_lot.x_warranty_start_date, warranty_start)
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
        internal_locations = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
        ])
        internal_quants = quant_model.search([
            ('product_id', '=', product.id),
            ('lot_id', 'in', [old_lot.id, new_lot.id]),
            ('location_id', 'in', internal_locations.ids),
            ('quantity', '>', 0),
        ])
        self.assertFalse(internal_quants)
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
            'fault_description': 'Lỗi nhà sản xuất cần kiểm tra.',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        with self.assertRaises(ValidationError):
            ticket.action_submit_for_approval()

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
            'fault_description': 'Lỗi nhà sản xuất cần kiểm tra.',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        ticket.action_wait_for_exchange_serial()

        self.assertEqual(ticket.state, 'waiting_serial')
        with self.assertRaises(ValidationError):
            self._submit_for_approval(ticket)
        new_lot = self._create_lot(
            product,
            'EXCHANGE-WAIT-NEW-001',
            x_custom_status='available',
        )
        quant_model._update_available_quantity(product, internal_location, 1, lot_id=new_lot)
        ticket.write({'new_serial_id': new_lot.id})
        self._submit_for_approval(ticket)
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
            'fault_description': 'Máy lỗi nhà sản xuất sau thời hạn đổi.',
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
            'fault_description': 'Lỗi nhà sản xuất cần kiểm tra.',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        self._submit_for_approval(ticket)
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
                    self._submit_for_approval(ticket)
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
        with self.assertRaises(ValidationError):
            self.env['product.category'].create({
                'name': 'Unclassified Exchange Policy Category',
                'exchange_period_days': 20,
            })

        unconfigured_accessory = self.env['product.template'].create({
            'name': 'Warranty Test Accessory Without Policy',
            'is_storable': True,
            'tracking': 'serial',
            'exchange_item_type': 'accessory',
            'warranty_period_months': 12,
        })
        self.assertEqual(unconfigured_accessory._get_exchange_period_days(), 0)

        device_template = self.env['product.template'].create({
            'name': 'Warranty Test New Device',
            'is_storable': True,
            'tracking': 'serial',
            'exchange_item_type': 'new_device',
            'warranty_period_months': 12,
        })
        self.assertEqual(device_template._get_exchange_period_days(), 30)
        with self.assertRaises(ValidationError):
            device_template.write({'exchange_period_days': 31})

        used_device_template = self.env['product.template'].create({
            'name': 'Warranty Test Used Device',
            'is_storable': True,
            'tracking': 'serial',
            'exchange_item_type': 'used_device',
            'warranty_period_months': 12,
        })
        self.assertEqual(used_device_template._get_exchange_period_days(), 30)

        unclassified_template = self.env['product.template'].create({
            'name': 'Unclassified Product',
            'is_storable': True,
            'tracking': 'serial',
            'warranty_period_months': 12,
        })
        self.assertFalse(unclassified_template._get_exchange_item_type())
        self.assertEqual(unclassified_template._get_exchange_period_days(), 0)

    def test_category_reclassification_cannot_invalidate_child_policy(self):
        category = self.env['product.category'].create({
            'name': 'Accessory Policy Parent',
            'exchange_item_type': 'accessory',
        })
        self.env['product.category'].create({
            'name': 'Accessory Policy Child',
            'parent_id': category.id,
            'exchange_period_days': 365,
        })

        with self.assertRaises(ValidationError):
            category.write({'exchange_item_type': 'new_device'})

        product_category = self.env['product.category'].create({
            'name': 'Product Policy Parent',
            'exchange_item_type': 'accessory',
        })
        child_category = self.env['product.category'].create({
            'name': 'Product Policy Child',
            'parent_id': product_category.id,
        })
        self.env['product.template'].create({
            'name': 'Inherited Accessory Policy Product',
            'categ_id': child_category.id,
            'exchange_period_days': 365,
        })

        with self.assertRaises(ValidationError):
            product_category.write({'exchange_item_type': 'new_device'})

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
            'fault_description': 'Thiết bị hỏng do người dùng.',
        })

        with self.assertRaises(ValidationError):
            ticket.action_wait_for_exchange_serial()

        self.assertEqual(ticket.state, 'new')

    def test_exchange_requires_fault_description_and_full_intake_checklist(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Incomplete Intake Customer'})
        old_lot = self._create_lot(
            product,
            'EXCHANGE-INCOMPLETE-INTAKE-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=10),
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': old_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
        })

        with self.assertRaises(ValidationError):
            ticket.action_wait_for_exchange_serial()

        ticket.symptom_power = True
        with self.assertRaises(ValidationError):
            ticket.action_wait_for_exchange_serial()

        ticket.write({
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })
        ticket.action_wait_for_exchange_serial()
        self.assertEqual(ticket.state, 'waiting_serial')


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
            'fault_description': 'Lỗi nhà sản xuất cần kiểm tra.',
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
            'fault_description': 'Lỗi nhà sản xuất cần kiểm tra.',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })
        self._submit_for_approval(first_ticket)
        first_ticket.action_approve_exchange()
        quant_model._update_available_quantity(product, internal_location, 1, lot_id=third_lot)
        second_ticket = self.env['warranty.ticket'].create({
            'serial_id': second_lot.id,
            'new_serial_id': third_lot.id,
            'ticket_type': 'exchange',
            'issue_category': 'nsx',
            'fault_description': 'Lỗi nhà sản xuất cần kiểm tra.',
            'appearance_ok': True,
            'no_liquid_damage': True,
            'security_cleared': True,
        })

        self._submit_for_approval(second_ticket)
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

    def test_warranty_receipt_report_and_security_groups_are_loaded(self):
        report = self.env.ref('custom_warranty.action_warranty_receipt_report')
        self.assertEqual(report.model, 'warranty.ticket')
        self.assertEqual(report.report_type, 'qweb-pdf')
        self.assertTrue(self.env.ref('custom_warranty.group_warranty_technician'))
        self.assertTrue(self.env.ref('custom_warranty.group_warranty_manager'))
        ticket = self._create_repair_ticket(
            self._create_product(),
            'RECEIPT-RENDER-001',
        )
        ticket.symptom_power = True
        html, _content_type = report._render_qweb_html(report.report_name, ticket.ids)
        rendered_html = html.decode() if isinstance(html, bytes) else str(html)

        self.assertIn('BIÊN NHẬN TIẾP NHẬN THIẾT BỊ HẬU MÃI', rendered_html)
        self.assertIn('font-family: "DejaVu Sans", sans-serif !important', rendered_html)
        self.assertNotIn('Your logo', rendered_html)
        self.assertNotIn('My Company (San Francisco)', rendered_html)
        self.assertIn('class="topage"', rendered_html)
        self.assertIn('signature-space', rendered_html)
        self.assertIn('signature-hint', rendered_html)
        self.assertIn('<em>(Ký và ghi rõ họ tên)</em>', rendered_html)
        self.assertIn('Không lên nguồn', rendered_html)
