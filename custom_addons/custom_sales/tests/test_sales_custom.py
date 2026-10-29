from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSalesCustom(TransactionCase):

    def _create_product(self, tracking='none', warranty_months=12):
        template = self.env['product.template'].create({
            'name': 'Sales Custom Test Laptop',
            'is_storable': True,
            'tracking': tracking,
            'warranty_period_months': warranty_months,
        })
        return template.product_variant_id

    def _create_order(self, product, quantity=1):
        partner = self.env['res.partner'].create({
            'name': 'Sales Custom Test Customer',
            'customer_rank': 1,
        })
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': quantity,
            })],
        })

    def test_confirmation_rejects_insufficient_stock(self):
        product = self._create_product()
        order = self._create_order(product)

        with self.assertRaises(ValidationError):
            order.action_confirm()

        self.assertEqual(order.state, 'draft')

    def test_delivery_records_serial_owner_sale_and_month_warranty(self):
        product = self._create_product(tracking='serial', warranty_months=12)
        order = self._create_order(product)
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-TEST-001',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_custom_status': 'available',
        })
        self.env['stock.quant']._update_available_quantity(
            product,
            warehouse.lot_stock_id,
            1,
            lot_id=lot,
        )

        order.action_confirm()
        picking = order.picking_ids.filtered(
            lambda record: record.picking_type_code == 'outgoing'
        )
        picking.action_assign()
        move = picking.move_ids.filtered(lambda record: record.product_id == product)
        move_line = move.move_line_ids[:1]
        if not move_line:
            move_line = self.env['stock.move.line'].create({
                'picking_id': picking.id,
                'move_id': move.id,
                'company_id': order.company_id.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
                'lot_id': lot.id,
                'quantity': 1,
                'picked': True,
            })
        else:
            move_line.write({
                'lot_id': lot.id,
                'quantity': 1,
                'picked': True,
            })

        result = picking.button_validate()
        self.assertFalse(isinstance(result, dict), 'The test delivery needs a wizard.')

        sale_date = fields.Date.context_today(self.env.user)
        self.assertEqual(lot.x_custom_status, 'sold')
        self.assertEqual(lot.x_customer_id, order.partner_id)
        self.assertEqual(lot.x_sale_order_id, order)
        self.assertEqual(lot.x_sale_order_line_id, move.sale_line_id)
        self.assertEqual(lot.x_sale_date, sale_date)
        self.assertEqual(lot.x_warranty_end_date, fields.Date.add(sale_date, months=12))
        self.assertIn(lot, order.serial_lot_ids)
        self.assertIn(lot, move.sale_line_id.x_delivered_serial_ids)

    def test_promotional_gift_line_keeps_combo_rule_link(self):
        laptop = self._create_product()
        gift = self._create_product(tracking='serial')
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        self.env['stock.quant']._update_available_quantity(
            laptop,
            warehouse.lot_stock_id,
            1,
        )
        self.env['stock.quant']._update_available_quantity(
            gift,
            warehouse.lot_stock_id,
            1,
            lot_id=self.env['stock.lot'].create({
                'name': 'SALES-CUSTOM-TEST-COMBO-GIFT-001',
                'product_id': gift.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'available',
            }),
        )
        gift_lot = self.env['stock.lot'].search([
            ('name', '=', 'SALES-CUSTOM-TEST-COMBO-GIFT-001'),
        ])
        combo = self.env['custom.crm.combo'].create({
            'name': 'Sales Custom Test Combo',
            'min_order_total': 0,
            'gift_value_limit': 0,
            'component_product_ids': [(6, 0, [gift.id])],
        })
        order = self._create_order(laptop)

        order.action_confirm()

        gift_line = order.order_line.filtered(
            lambda line: line.is_combo_gift and line.product_id == gift
        )
        self.assertEqual(len(gift_line), 1)
        self.assertEqual(gift_line.x_combo_rule_id, combo)

        picking = order.picking_ids.filtered(
            lambda record: record.picking_type_code == 'outgoing'
        )
        picking.action_assign()
        gift_move = picking.move_ids.filtered(
            lambda move: move.product_id == gift
        )
        gift_move_line = gift_move.move_line_ids[:1]
        if not gift_move_line:
            gift_move_line = self.env['stock.move.line'].create({
                'picking_id': picking.id,
                'move_id': gift_move.id,
                'company_id': order.company_id.id,
                'product_id': gift.id,
                'product_uom_id': gift.uom_id.id,
                'location_id': gift_move.location_id.id,
                'location_dest_id': gift_move.location_dest_id.id,
                'lot_id': gift_lot.id,
                'quantity': 1,
                'picked': True,
            })
        else:
            gift_move_line.write({
                'lot_id': gift_lot.id,
                'quantity': 1,
                'picked': True,
            })
        for move in picking.move_ids.filtered(
            lambda record: record.product_id != gift
        ):
            move_line = move.move_line_ids[:1]
            if not move_line:
                self.env['stock.move.line'].create({
                    'picking_id': picking.id,
                    'move_id': move.id,
                    'company_id': order.company_id.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'quantity': move.product_uom_qty,
                    'picked': True,
                })
            else:
                move_line.write({
                    'quantity': move.product_uom_qty,
                    'picked': True,
                })
        result = picking.button_validate()

        self.assertFalse(isinstance(result, dict), 'The test delivery needs a wizard.')
        self.assertEqual(gift_lot.x_sale_order_line_id, gift_line)

    def test_serial_quantity_must_be_a_whole_number(self):
        product = self._create_product(tracking='serial')
        order = self._create_order(product, quantity=1.5)
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        for index in range(2):
            lot = self.env['stock.lot'].create({
                'name': f'SALES-CUSTOM-TEST-FRACTIONAL-{index}',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'available',
            })
            self.env['stock.quant']._update_available_quantity(
                product,
                warehouse.lot_stock_id,
                1,
                lot_id=lot,
            )

        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_delivery_rejects_missing_serial(self):
        product = self._create_product(tracking='serial')
        order = self._create_order(product)
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-TEST-MISSING-SERIAL',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_custom_status': 'available',
        })
        self.env['stock.quant']._update_available_quantity(
            product,
            warehouse.lot_stock_id,
            1,
            lot_id=lot,
        )

        order.action_confirm()
        picking = order.picking_ids.filtered(
            lambda record: record.picking_type_code == 'outgoing'
        )
        picking.action_assign()
        move = picking.move_ids.filtered(lambda record: record.product_id == product)
        move_line = move.move_line_ids[:1]
        if not move_line:
            move_line = self.env['stock.move.line'].create({
                'picking_id': picking.id,
                'move_id': move.id,
                'company_id': order.company_id.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
                'quantity': 1,
                'picked': True,
            })
        else:
            move_line.write({
                'lot_id': False,
                'quantity': 1,
                'picked': True,
            })

        with self.assertRaises(ValidationError):
            picking._validate_sale_delivery_serials()
