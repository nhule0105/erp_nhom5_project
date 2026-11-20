import secrets
import string

from odoo import _, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare


class StockLot(models.Model):
    _inherit = 'stock.lot'

    lifecycle_status = fields.Selection(
        [
            ('available', 'Sẵn sàng'),
            ('issued', 'Đã xuất'),
            ('defective', 'Lỗi chờ xử lý'),
        ],
        string='Trạng thái vòng đời S/N',
        default='available',
        required=True,
        index=True,
        help='Trạng thái của S/N trong luồng hàng hóa của cửa hàng.',
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _compute_nbr_moves(self):
        """Reconcile displayed received quantity with current stock history.

        Some initial/manual/chat stock entries create inventory directly and do
        not have an incoming move line.  Treat that quantity as received stock
        so the displayed balance is always: received - delivered = on hand.
        """
        self.nbr_moves_in = 0
        self.nbr_moves_out = 0
        if not self:
            return

        quantities = {
            template.id: {'incoming': 0.0, 'outgoing': 0.0}
            for template in self
        }
        for picking_code in ('outgoing',):
            grouped_moves = self.env['stock.move.line']._read_group(
                [
                    ('product_id.product_tmpl_id', 'in', self.ids),
                    ('state', '=', 'done'),
                    ('picking_code', '=', picking_code),
                ],
                ['product_id', 'product_uom_id'],
                ['quantity:sum'],
            )
            for product, uom, quantity in grouped_moves:
                template_id = product.product_tmpl_id.id
                quantities[template_id][picking_code] += uom._compute_quantity(
                    quantity,
                    product.uom_id,
                )

        for template in self:
            outgoing = round(quantities[template.id]['outgoing'])
            template.nbr_moves_out = outgoing
            template.nbr_moves_in = round(template.qty_available + outgoing)

    lifecycle_product_type = fields.Selection(
        [
            ('laptop', 'Laptop'),
            ('mouse', 'Chuột'),
            ('backpack', 'Balo'),
        ],
        string='Loại hàng nhập',
        help='Dùng để phân loại thành phần khi gộp Combo.',
    )
    brand = fields.Char(
        string='Thương hiệu',
        help='Thương hiệu của sản phẩm.',
    )
    cpu = fields.Char(
        string='CPU',
        help='Bộ xử lý, áp dụng chủ yếu cho laptop.',
    )
    ram = fields.Char(
        string='RAM',
        help='Dung lượng và loại RAM, áp dụng chủ yếu cho laptop.',
    )
    storage = fields.Char(
        string='Ổ cứng',
        help='Dung lượng và loại ổ cứng, áp dụng chủ yếu cho laptop.',
    )
    gpu = fields.Char(
        string='Card màn hình',
        help='Thông tin card màn hình, áp dụng chủ yếu cho laptop.',
    )
    mouse_connection = fields.Selection(
        [
            ('wired', 'Có dây'),
            ('wireless', 'Không dây'),
            ('bluetooth', 'Bluetooth'),
        ],
        string='Kết nối chuột',
    )
    mouse_dpi = fields.Char(string='DPI chuột')
    mouse_buttons = fields.Integer(string='Số nút chuột')
    mouse_color = fields.Char(string='Màu sắc chuột')
    backpack_material = fields.Char(string='Chất liệu balo')
    backpack_size = fields.Char(string='Kích thước balo')
    backpack_capacity = fields.Char(string='Sức chứa balo')
    backpack_color = fields.Char(string='Màu sắc balo')

    def action_open_product_lot(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'stock.action_product_production_lot_form'
        )
        allowed_companies = self._context.get('allowed_company_ids') or self.env.companies.ids
        lot_ids = self.env['stock.quant'].search([
            ('product_id.product_tmpl_id', '=', self.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
            ('company_id', 'in', allowed_companies),
        ]).mapped('lot_id').ids
        action['domain'] = [('id', 'in', lot_ids)]
        action['context'] = {
            'default_product_tmpl_id': self.id,
            'search_default_group_by_location': True,
        }
        if self.product_variant_count == 1:
            action['context']['default_product_id'] = self.product_variant_id.id
        return action

    def action_convert_untracked_serial_stock(self):
        self.ensure_one()
        product = self.product_variant_id
        if product.tracking != 'serial':
            raise UserError(
                _('Sản phẩm phải được đặt Theo số sê-ri duy nhất trước khi điều chỉnh.')
            )

        Quant = self.env['stock.quant'].sudo()
        Lot = self.env['stock.lot'].sudo()
        locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        quants = Quant.search([
            ('product_id', '=', product.id),
            ('location_id', 'in', locations.ids),
            ('lot_id', '=', False),
            ('quantity', '>', 0),
        ])
        converted = self._convert_untracked_quants(product, quants, Lot, Quant)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn tất tạo Serial'),
                'message': _('Đã tạo %s Serial cho %s.') % (
                    converted,
                    self.display_name,
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_convert_selected_untracked_serial_stock(self):
        Quant = self.env['stock.quant'].sudo()
        Lot = self.env['stock.lot'].sudo()
        locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        total = 0
        for template in self.filtered(
            lambda record: record.product_variant_id.tracking == 'serial'
        ):
            product = template.product_variant_id
            quants = Quant.search([
                ('product_id', '=', product.id),
                ('location_id', 'in', locations.ids),
                ('lot_id', '=', False),
                ('quantity', '>', 0),
            ])
            total += template._convert_untracked_quants(product, quants, Lot, Quant)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Hoàn tất tạo Serial'),
                'message': _('Đã tạo %s Serial cho các sản phẩm được chọn.') % total,
                'type': 'success',
                'sticky': False,
            },
        }

    def _convert_untracked_quants(self, product, quants, lot_model, quant_model):
        converted = 0
        for quant in quants:
            if float_compare(
                quant.quantity,
                round(quant.quantity),
                precision_rounding=product.uom_id.rounding,
            ):
                raise ValidationError(
                    _('Tồn kho của %s phải là số nguyên.') % product.display_name
                )
            for _index in range(int(round(quant.quantity))):
                lot = lot_model.create({
                    'name': self._next_serial(product, lot_model),
                    'product_id': product.id,
                    'company_id': quant.company_id.id,
                    'x_custom_status': 'available',
                })
                quant_model.with_context(inventory_mode=True).create({
                    'product_id': product.id,
                    'location_id': quant.location_id.id,
                    'lot_id': lot.id,
                    'inventory_quantity': 1.0,
                    'inventory_quantity_set': True,
                }).action_apply_inventory()
                converted += 1
            quant.with_context(inventory_mode=True).write({'inventory_quantity': 0.0})
            quant.action_apply_inventory()
        return converted

    def _next_serial(self, product, lot_model):
        alphabet = string.ascii_uppercase + string.digits
        while True:
            name = ''.join(secrets.choice(alphabet) for _index in range(8))
            if not lot_model.search_count([
                ('name', '=', name),
                ('product_id', '=', product.id),
            ]):
                return name


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _compute_nbr_moves(self):
        """Show moved quantities instead of the number of move lines.

        The standard Odoo fields are displayed as In/Out on the product form.
        Out is the completed delivered quantity. In also includes stock entered
        through opening/manual/chat inventory adjustments, which may not have an
        incoming move line, so the displayed balance remains consistent.
        """
        self.nbr_moves_in = 0
        self.nbr_moves_out = 0
        if not self:
            return

        quantities = {
            product.id: {'incoming': 0.0, 'outgoing': 0.0}
            for product in self
        }
        for picking_code in ('outgoing',):
            grouped_moves = self.env['stock.move.line']._read_group(
                [
                    ('product_id', 'in', self.ids),
                    ('state', '=', 'done'),
                    ('picking_code', '=', picking_code),
                ],
                ['product_id', 'product_uom_id'],
                ['quantity:sum'],
            )
            for product, uom, quantity in grouped_moves:
                quantities[product.id][picking_code] += uom._compute_quantity(
                    quantity,
                    product.uom_id,
                )

        for product in self:
            outgoing = round(quantities[product.id]['outgoing'])
            product.nbr_moves_out = outgoing
            product.nbr_moves_in = round(product.qty_available + outgoing)

    def _get_available_lot_domain(self, product_domain):
        """Restrict product lot lists to serials currently in internal stock."""
        return product_domain + [
            ('quant_ids.location_id.usage', '=', 'internal'),
            ('quant_ids.quantity', '>', 0),
        ]

    def action_open_product_lot(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'stock.action_product_production_lot_form'
        )
        allowed_companies = self._context.get('allowed_company_ids') or self.env.companies.ids
        lot_ids = self.env['stock.quant'].search([
            ('product_id', '=', self.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
            ('company_id', 'in', allowed_companies),
        ]).mapped('lot_id').ids
        action['domain'] = [('id', 'in', lot_ids)]
        action['context'] = {
            'default_product_id': self.id,
            'set_product_readonly': True,
            'search_default_group_by_location': True,
        }
        return action

    def action_convert_untracked_serial_stock(self):
        self.ensure_one()
        return self.product_tmpl_id.action_convert_untracked_serial_stock()
