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

    def test_customer_code_is_generated_and_vietnamese_name_is_preserved(self):
        first_customer = self.env['res.partner'].create({
            'name': 'Nguyễn Vĩnh Thị Trà My',
            'customer_rank': 1,
        })
        second_customer = self.env['res.partner'].create({
            'name': 'Trần Thị Bình',
            'customer_rank': 1,
        })

        self.assertEqual(first_customer.name, 'Nguyễn Vĩnh Thị Trà My')
        self.assertRegex(first_customer.ref, r'^KH\d{5}$')
        self.assertRegex(second_customer.ref, r'^KH\d{5}$')
        self.assertEqual(
            int(second_customer.ref[2:]),
            int(first_customer.ref[2:]) + 1,
        )

    def test_salesperson_can_create_edit_and_delete_combo_rules(self):
        salesperson = self.env['res.users'].with_context(
            no_reset_password=True
        ).create({
            'name': 'Sales Combo Manager',
            'login': 'sales-combo-manager',
            'groups_id': [fields.Command.set([
                self.env.ref('base.group_user').id,
                self.env.ref('sales_team.group_sale_salesman').id,
            ])],
        })
        combo_model = self.env['custom.crm.combo'].with_user(salesperson)

        combo = combo_model.create({'name': 'Salesperson Test Combo'})
        combo.write({'min_order_total': 1_000_000})
        self.assertEqual(combo.min_order_total, 1_000_000)
        combo.unlink()
        self.assertFalse(combo.exists())

    def test_selected_product_shows_details_and_available_stock(self):
        product = self._create_product(tracking='serial')
        product.product_tmpl_id.write({
            'lifecycle_product_type': 'laptop',
            'brand': 'Test Brand',
            'cpu': 'Test CPU',
            'ram': '16 GB',
        })
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        available_lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-DETAILS-AVAILABLE',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_custom_status': 'available',
            'lifecycle_status': 'available',
        })
        unavailable_lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-DETAILS-SOLD',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_custom_status': 'sold',
            'lifecycle_status': 'issued',
        })
        self.env['stock.quant']._update_available_quantity(
            product,
            warehouse.lot_stock_id,
            1,
            lot_id=available_lot,
        )
        self.env['stock.quant']._update_available_quantity(
            product,
            warehouse.lot_stock_id,
            1,
            lot_id=unavailable_lot,
        )

        order = self._create_order(product)
        line = order.order_line
        self.assertIn('Thương hiệu: Test Brand', line.x_selected_product_details)
        self.assertIn('CPU: Test CPU', line.x_selected_product_details)
        self.assertEqual(line.x_available_stock_qty, 1)
        self.assertFalse(line.x_available_serial_lot_ids)
        self.assertEqual(available_lot.x_custom_status, 'available')

        self.env['stock.quant']._update_reserved_quantity(
            product,
            warehouse.lot_stock_id,
            1,
            lot_id=available_lot,
        )
        self.assertEqual(line.x_available_stock_qty, 0)
        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_confirmation_applies_the_matching_combo_gift_once(self):
        sold_product = self._create_product()
        gift_product = self._create_product()
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        self.env['stock.quant']._update_available_quantity(
            sold_product,
            warehouse.lot_stock_id,
            1,
        )
        self.env['stock.quant']._update_available_quantity(
            gift_product,
            warehouse.lot_stock_id,
            1,
        )
        combo = self.env['custom.crm.combo'].create({
            'name': 'Sales Custom Test Gift Combo',
            'combo_tier': '13m_to_15m',
            'min_order_total': 13_000_000,
            'max_order_total': 15_000_000,
            'gift_value_limit': 2_000_000,
            'component_product_ids': [fields.Command.set([gift_product.id])],
        })
        order = self._create_order(sold_product)
        order.order_line.write({
            'price_unit': 13_500_000,
            'tax_id': [fields.Command.clear()],
        })

        self.assertEqual(order.x_promotional_combo_id, combo)
        self.assertEqual(order.x_promotional_gift_product_ids, gift_product)
        self.assertIn('được thêm vào đơn', order.x_promotional_combo_message)

        order.action_confirm()

        gifts = order.order_line.filtered('is_combo_gift')
        self.assertEqual(len(gifts), 1)
        self.assertEqual(gifts.product_id, gift_product)
        self.assertEqual(gifts.price_unit, 0)
        self.assertIn(combo.name, gifts.name)

    def test_promotional_combo_display_updates_with_order_total(self):
        product = self._create_product()
        gift_product = self._create_product()
        self.env['custom.crm.combo'].search([
            ('company_id', '=', self.env.company.id),
        ]).write({'active': False})
        combo = self.env['custom.crm.combo'].create({
            'name': 'Sales Custom Display Combo',
            'min_order_total': 1_000_000,
            'max_order_total': 2_000_000,
            'component_product_ids': [fields.Command.set([gift_product.id])],
        })
        order = self._create_order(product)
        line = order.order_line
        line.write({
            'price_unit': 1_500_000,
            'tax_id': [fields.Command.clear()],
        })

        self.assertEqual(order.x_promotional_combo_id, combo)
        self.assertEqual(order.x_promotional_gift_product_ids, gift_product)

        line.write({'price_unit': 500_000})

        self.assertFalse(order.x_promotional_combo_id)
        self.assertFalse(order.x_promotional_gift_product_ids)
        self.assertIn('Không có combo', order.x_promotional_combo_message)

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
        if isinstance(result, dict):
            wizard = self.env[result['res_model']].with_context(
                result['context']
            ).create({})
            result = wizard.process()
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
