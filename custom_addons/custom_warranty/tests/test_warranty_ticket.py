from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWarrantyTicket(TransactionCase):

    def _create_product(self):
        template = self.env['product.template'].create({
            'name': 'Warranty Test Laptop',
            'is_storable': True,
            'tracking': 'serial',
            'warranty_period_days': 365,
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
        purchase_date = fields.Date.today() - timedelta(days=10)
        warranty_end = fields.Date.today() + timedelta(days=355)
        old_lot = self._create_lot(
            product,
            'EXCHANGE-OLD-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
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
        self.assertEqual(new_lot.x_purchase_date, purchase_date)
        self.assertEqual(new_lot.x_warranty_end_date, warranty_end)
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

    def test_return_moves_serial_back_to_internal_stock(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({'name': 'Return Customer'})
        lot = self._create_lot(
            product,
            'RETURN-001',
            x_customer_id=partner.id,
            x_custom_status='sold',
            x_purchase_date=fields.Date.today() - timedelta(days=5),
            x_warranty_end_date=fields.Date.today() + timedelta(days=360),
        )
        customer_location = self.env.ref('stock.stock_location_customers')
        internal_location = self.env.ref('stock.stock_location_stock')
        self.env['stock.quant']._update_available_quantity(
            product, customer_location, 1, lot_id=lot,
        )
        ticket = self.env['warranty.ticket'].create({
            'serial_id': lot.id,
            'ticket_type': 'return',
            'issue_category': 'user',
        })

        ticket.action_approve_return()

        self.assertEqual(ticket.state, 'done')
        self.assertTrue(ticket.return_move_ids)
        self.assertEqual(lot.x_custom_status, 'available')
        self.assertFalse(lot.x_customer_id)
        self.assertEqual(
            sum(self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('location_id', '=', internal_location.id),
            ]).mapped('quantity')),
            1,
        )
