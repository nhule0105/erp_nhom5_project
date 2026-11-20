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

    def test_customer_code_increments_by_one_after_existing_code(self):
        existing_customer = self.env['res.partner'].create({
            'name': 'Existing customer',
            'ref': 'KH00011',
            'customer_rank': 1,
        })

        sequence = self.env['ir.sequence'].search([
            ('code', '=', 'custom.sales.customer.v2'),
        ], limit=1)
        sequence.write({'number_increment': 1})
        new_customer = self.env['res.partner'].create({
            'name': 'New customer',
            'customer_rank': 1,
        })

        self.assertEqual(existing_customer.ref, 'KH00011')
        self.assertEqual(new_customer.ref, 'KH00012')

    def test_sale_order_number_increments_by_one_after_existing_code(self):
        product = self._create_product()
        partner = self.env['res.partner'].create({
            'name': 'Sequence test customer',
            'customer_rank': 1,
        })
        existing_order = self.env['sale.order'].create({
            'name': 'S00014',
            'partner_id': partner.id,
        })
        new_order = self._create_order(product)

        self.assertEqual(existing_order.name, 'S00014')
        self.assertEqual(new_order.name, 'S00015')

    def test_customer_code_skips_codes_used_by_archived_customers(self):
        sequence = self.env['ir.sequence'].search([
            ('code', '=', 'custom.sales.customer.v2'),
        ], limit=1)
        sequence.next_by_code('custom.sales.customer.v2')
        first_reserved_code = sequence.next_by_code(
            'custom.sales.customer.v2'
        )
        second_reserved_code = sequence.next_by_code(
            'custom.sales.customer.v2'
        )
        self.env['res.partner'].create([
            {
                'name': 'Archived customer code reservation',
                'ref': code,
                'active': False,
            }
            for code in (first_reserved_code, second_reserved_code)
        ])
        self.env.cr.execute(
            'ALTER SEQUENCE "ir_sequence_%03d" RESTART WITH %s'
            % (sequence.id, int(first_reserved_code[2:]))
        )

        generated_code = self.env['res.partner']._next_customer_code()

        self.assertEqual(
            int(generated_code[2:]),
            int(second_reserved_code[2:]) + 1,
        )

    def test_invoice_report_repairs_damaged_accessory_names(self):
        repaired_names = {
            'MASTER-BAG': 'Ba lô laptop',
            'MASTER-MAT': 'Lót chuột',
            'MASTER-MOU': 'Chuột tặng kèm',
        }
        for default_code, product_name in repaired_names.items():
            product = self._create_product()
            product.default_code = default_code
            invoice_line = self.env['account.move.line'].new({
                'name': f'[{default_code}] Tên bị lỗi',
                'product_id': product.id,
            })

            self.assertEqual(
                invoice_line._get_invoice_report_name(),
                f'[{default_code}] {product_name}',
            )

    def test_quotation_report_repairs_product_names_and_labels_combo_gifts(self):
        product = self._create_product()
        product.default_code = 'MASTER-BAG'
        combo = self.env['custom.crm.combo'].create({
            'name': 'Quotation Test Combo',
        })
        line = self.env['sale.order.line'].new({
            'product_id': product.id,
            'name': '[MASTER-BAG] Ba l?? laptop',
            'is_combo_gift': True,
            'x_combo_rule_id': combo.id,
        })

        self.assertEqual(
            line._get_quote_report_name(),
            '[MASTER-BAG] Ba lô laptop\nQuà tặng kèm: Quotation Test Combo',
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

    def test_device_in_warranty_repair_location_cannot_be_sold(self):
        product = self._create_product(tracking='serial')
        customer = self.env['res.partner'].create({
            'name': 'Customer With Device Under Repair',
            'customer_rank': 1,
        })
        lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-UNDER-REPAIR-001',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_customer_id': customer.id,
            'x_custom_status': 'sold',
            'lifecycle_status': 'issued',
        })
        customer_location = self.env.ref('stock.stock_location_customers')
        self.env['stock.quant']._update_available_quantity(
            product,
            customer_location,
            1,
            lot_id=lot,
        )
        repair_ticket = self.env['warranty.ticket'].create({
            'serial_id': lot.id,
            'ticket_type': 'repair',
            'fault_description': 'Không lên nguồn.',
        })
        repair_ticket.action_receive_repair_device()

        order = self._create_order(product)
        self.assertNotIn(
            lot,
            order.order_line._get_available_product_serials(product),
        )

        with self.assertRaises(ValidationError):
            order.action_confirm()
        self.assertEqual(lot.x_custom_status, 'under_repair')
        self.assertEqual(lot.lifecycle_status, 'issued')

    def test_defective_exchange_return_in_quarantine_cannot_be_sold(self):
        product = self._create_product(tracking='serial')
        customer = self.env['res.partner'].create({
            'name': 'Customer With Defective Exchange Device',
            'customer_rank': 1,
        })
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        defective_location = self.env['stock.location'].create({
            'name': 'Warranty Defective Quarantine',
            'location_id': warehouse.lot_stock_id.id,
            'company_id': self.env.company.id,
            'usage': 'internal',
            'warranty_defective_location': True,
        })
        lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-DEFECTIVE-001',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_customer_id': customer.id,
            'x_custom_status': 'defective',
            'lifecycle_status': 'defective',
        })
        self.env['stock.quant']._update_available_quantity(
            product,
            defective_location,
            1,
            lot_id=lot,
        )
        order = self._create_order(product)
        self.assertNotIn(
            lot,
            order.order_line._get_available_product_serials(product),
        )

        with self.assertRaises(ValidationError):
            order.action_confirm()

        self.assertEqual(lot.x_custom_status, 'defective')
        self.assertEqual(lot.lifecycle_status, 'defective')
        self.assertEqual(
            sum(self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('location_id', '=', defective_location.id),
            ]).mapped('quantity')),
            1,
        )

    def test_serial_picker_disables_sold_and_repair_serials(self):
        product = self._create_product(tracking='serial')
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        serials = {
            'available': self.env['stock.lot'].create({
                'name': 'SERIAL-PICKER-AVAILABLE',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'available',
                'lifecycle_status': 'available',
            }),
            'sold': self.env['stock.lot'].create({
                'name': 'SERIAL-PICKER-SOLD',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'sold',
                'lifecycle_status': 'issued',
            }),
            'under_repair': self.env['stock.lot'].create({
                'name': 'SERIAL-PICKER-REPAIR',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'under_repair',
                'lifecycle_status': 'issued',
            }),
        }
        for lot in serials.values():
            self.env['stock.quant']._update_available_quantity(
                product,
                warehouse.lot_stock_id,
                1,
                lot_id=lot,
            )

        picker_data = {
            item['id']: item for item in product.get_serial_picker_data()
        }
        self.assertEqual(product.x_serial_count, 3)
        self.assertEqual(product.product_tmpl_id.x_serial_count, 3)
        self.assertTrue(picker_data[serials['available'].id]['selectable'])
        self.assertFalse(picker_data[serials['sold'].id]['selectable'])
        self.assertFalse(picker_data[serials['under_repair'].id]['selectable'])

        order = self._create_order(product)
        for key in ('sold', 'under_repair'):
            with self.assertRaises(ValidationError):
                order.order_line.write({
                    'x_selected_serial_lot_ids': [
                        (6, 0, [serials[key].id]),
                    ],
                })

    def test_confirmation_randomly_assigns_only_available_serials(self):
        product = self._create_product(tracking='serial')
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        serials = {
            'available': self.env['stock.lot'].create({
                'name': 'SERIAL-AUTO-AVAILABLE',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'available',
                'lifecycle_status': 'available',
            }),
            'sold': self.env['stock.lot'].create({
                'name': 'SERIAL-AUTO-SOLD',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'sold',
                'lifecycle_status': 'issued',
            }),
            'under_repair': self.env['stock.lot'].create({
                'name': 'SERIAL-AUTO-REPAIR',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'under_repair',
                'lifecycle_status': 'issued',
            }),
            'issued': self.env['stock.lot'].create({
                'name': 'SERIAL-AUTO-ISSUED',
                'product_id': product.id,
                'company_id': self.env.company.id,
                'x_custom_status': 'available',
                'lifecycle_status': 'issued',
            }),
        }
        for lot in serials.values():
            self.env['stock.quant']._update_available_quantity(
                product,
                warehouse.lot_stock_id,
                1,
                lot_id=lot,
            )

        order = self._create_order(product)
        self.assertFalse(order.order_line.x_selected_serial_lot_ids)
        order.action_confirm()

        picking = order.picking_ids.filtered(
            lambda record: record.picking_type_code == 'outgoing'
        )
        assigned_serials = picking.move_ids.move_line_ids.filtered(
            lambda line: line.quantity > 0
        ).mapped('lot_id')
        self.assertEqual(assigned_serials, serials['available'])

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

    def test_exchange_submission_rejects_defective_lifecycle_replacement(self):
        product = self._create_product(tracking='serial')
        product.product_tmpl_id.write({
            'exchange_item_type': 'new_device',
            'exchange_period_days': 30,
        })
        customer = self.env['res.partner'].create({
            'name': 'Customer With Defective Replacement',
            'customer_rank': 1,
        })
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)],
            limit=1,
        )
        old_lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-EXCHANGE-STATUS-OLD',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_customer_id': customer.id,
            'x_custom_status': 'sold',
            'x_purchase_date': fields.Date.today(),
        })
        new_lot = self.env['stock.lot'].create({
            'name': 'SALES-CUSTOM-EXCHANGE-STATUS-NEW',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'x_custom_status': 'available',
            'lifecycle_status': 'defective',
        })
        self.env['stock.quant']._update_available_quantity(
            product,
            self.env.ref('stock.stock_location_customers'),
            1,
            lot_id=old_lot,
        )
        self.env['stock.quant']._update_available_quantity(
            product,
            warehouse.lot_stock_id,
            1,
            lot_id=new_lot,
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

        with self.assertRaises(ValidationError):
            ticket.action_submit_for_approval()

        self.assertEqual(ticket.approval_status, 'none')
        self.assertFalse(ticket.exchange_move_ids)
        self.assertEqual(new_lot.lifecycle_status, 'defective')
