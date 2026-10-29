from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    exchange_item_type = fields.Selection(
        [
            ('new_device', 'Thiết bị mới'),
            ('used_device', 'Thiết bị đã qua sử dụng'),
            ('accessory', 'Phụ kiện điện tử'),
        ],
        string='Nhóm chính sách đổi',
        help='Để trống để kế thừa nhóm chính sách từ danh mục cha.',
    )
    warranty_period_days = fields.Integer(
        string='Bảo hành mặc định (ngày)',
        default=0,
        help='Để 0 nếu từng sản phẩm tự cấu hình thời hạn.',
    )
    exchange_period_days = fields.Integer(
        string='Đổi hàng mặc định (ngày)',
        default=0,
        help='Thiết bị chính tối đa 30 ngày; phụ kiện tối đa 365 ngày. Để 0 để kế thừa hoặc dùng mặc định.',
    )

    def _get_exchange_item_type(self):
        self.ensure_one()
        category = self
        while category:
            if category.exchange_item_type:
                return category.exchange_item_type
            category = category.parent_id
        return 'new_device'

    @api.constrains('exchange_period_days', 'exchange_item_type', 'parent_id')
    def _check_category_exchange_policy(self):
        for category in self:
            limit = 365 if category._get_exchange_item_type() == 'accessory' else 30
            if category.exchange_period_days < 0 or category.exchange_period_days > limit:
                raise ValidationError(
                    _('Thời hạn đổi của danh mục phải nằm trong khoảng 0-%s ngày.') % limit
                )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    exchange_item_type = fields.Selection(
        [
            ('new_device', 'Thiết bị mới'),
            ('used_device', 'Thiết bị đã qua sử dụng'),
            ('accessory', 'Phụ kiện điện tử'),
        ],
        string='Nhóm chính sách đổi',
        help='Để trống để kế thừa chính sách từ danh mục.',
    )
    warranty_period_months = fields.Integer(
        string='Thời hạn bảo hành (tháng)',
        default=0,
        required=True,
        help='Số tháng bảo hành tính từ ngày giao hàng. Để 0 để dùng chính sách nhóm sản phẩm (hoặc mặc định 12 tháng).',
    )
    exchange_period_days = fields.Integer(
        string='Thời hạn đổi mới (ngày)',
        default=0,
        help='Để 0 để dùng chính sách mặc định của nhóm sản phẩm.',
    )

    @api.constrains(
        'warranty_period_months',
        'exchange_period_days',
        'exchange_item_type',
        'categ_id',
    )
    def _check_warranty_periods(self):
        for product in self:
            if product.warranty_period_months < 0 or product.exchange_period_days < 0:
                raise ValidationError(_('Thời hạn bảo hành và đổi mới không được âm.'))
            if product.exchange_period_days > product._get_exchange_period_limit():
                raise ValidationError(
                    _('Thời hạn đổi của sản phẩm vượt quá giới hạn %s ngày.')
                    % product._get_exchange_period_limit()
                )

    def _get_warranty_period_months(self):
        self.ensure_one()
        if self.warranty_period_months:
            return self.warranty_period_months
        category = self.categ_id
        while category:
            if category.warranty_period_days:
                return max(1, round(category.warranty_period_days / 30.4375))
            category = category.parent_id
        return 12

    def _get_exchange_period_days(self):
        self.ensure_one()
        if self.exchange_period_days:
            return min(self.exchange_period_days, self._get_exchange_period_limit())
        item_type = self._get_exchange_item_type()
        category = self.categ_id
        while category:
            if (
                category.exchange_period_days
                and category._get_exchange_item_type() == item_type
            ):
                return min(category.exchange_period_days, self._get_exchange_period_limit())
            category = category.parent_id
        return 0 if item_type == 'accessory' else 30

    def _get_exchange_item_type(self):
        self.ensure_one()
        if self.exchange_item_type:
            return self.exchange_item_type
        return self.categ_id._get_exchange_item_type()

    def _get_exchange_period_limit(self):
        self.ensure_one()
        return 365 if self._get_exchange_item_type() == 'accessory' else 30


class StockLot(models.Model):
    _inherit = 'stock.lot'

    _sql_constraints = [
        (
            'replacement_source_unique',
            'unique(x_replaced_from_lot_id)',
            'Một serial chỉ được dùng làm serial nguồn cho một lần đổi.',
        ),
    ]

    x_customer_id = fields.Many2one('res.partner', string='Khách hàng')
    x_custom_status = fields.Selection([
        ('available', 'Trong kho / Sẵn sàng bán'),
        ('sold', 'Đã bán'),
        ('under_repair', 'Đang bảo hành'),
        ('defective', 'Lỗi / Chờ xử lý')
    ], string='Trạng thái thiết bị', default='available')
    x_purchase_date = fields.Date(string='Ngày mua hàng')
    x_warranty_start_date = fields.Date(string='Ngày bắt đầu bảo hành')
    x_warranty_end_date = fields.Date(string='Ngày hết hạn bảo hành')
    x_sale_order_id = fields.Many2one('sale.order', string='Đơn bán')
    x_sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Dòng đơn bán',
        readonly=True,
        copy=False,
        index=True,
        ondelete='set null',
    )
    x_delivery_picking_id = fields.Many2one('stock.picking', string='Phiếu giao hàng')
    x_sale_date = fields.Date(string='Ngày giao hàng')
    source_warehouse_location = fields.Char(string='Vị trí kho nguồn')
    x_replaced_from_lot_id = fields.Many2one(
        'stock.lot',
        string='Đổi từ serial',
        readonly=True,
        copy=False,
        index=True,
        ondelete='restrict',
    )
    x_replacement_lot_ids = fields.One2many(
        'stock.lot',
        'x_replaced_from_lot_id',
        string='Serial thay thế',
        readonly=True,
    )
    warranty_ticket_ids = fields.One2many(
        'warranty.ticket',
        'serial_id',
        string='Phiếu hậu mãi theo serial',
        readonly=True,
    )
    replacement_ticket_ids = fields.One2many(
        'warranty.ticket',
        'new_serial_id',
        string='Phiếu đổi sang serial này',
        readonly=True,
    )

    def validate_serial_number(self, product_id=False, required_qty=0, serial_numbers=None):
        """Kiểm tra nghiệp vụ Serial Number trước khi xuất kho."""
        if serial_numbers is None:
            serial_numbers = []

        if not isinstance(serial_numbers, (list, tuple, set)):
            serial_numbers = [serial_numbers]

        serial_list = [str(item).strip() for item in serial_numbers if str(item).strip()]
        serial_list = list(dict.fromkeys(serial_list))

        if required_qty and len(serial_list) < int(required_qty):
            raise ValidationError(
                f'Không đủ S/N để xuất. Cần {required_qty}, đã nhận {len(serial_list)}.'
            )

        if not product_id:
            raise ValidationError('Thiếu sản phẩm để kiểm tra S/N.')

        for serial in serial_list:
            lot = self.search([('name', '=', serial), ('product_id', '=', product_id)])
            if not lot:
                raise ValidationError(f'S/N {serial} không tồn tại hoặc không thuộc sản phẩm yêu cầu.')

            qty_available = 0
            for quant in self.env['stock.quant'].search([
                ('lot_id', '=', lot.id),
                ('location_id.usage', '=', 'internal'),
            ]):
                qty_available += quant.quantity

            if qty_available <= 0:
                raise ValidationError(f'S/N {serial} không còn trong kho hoặc đã được xuất.')
        return True


class WarrantyTicket(models.Model):
    _name = 'warranty.ticket'
    _description = 'Phiếu Bảo hành, Sửa chữa và Đổi mới 1-1'
    _rec_name = 'ticket_code'
    _order = 'receive_date desc, id desc'

    ticket_code = fields.Char(
        string='Mã phiếu',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('warranty.ticket') or _('New'),
    )
    receive_date = fields.Date(string='Ngày tiếp nhận', default=fields.Date.context_today)
    completed_date = fields.Date(string='Ngày hoàn tất', readonly=True, copy=False)
    customer_phone = fields.Char(string='Số điện thoại khách hàng')
    serial_id = fields.Many2one(
        'stock.lot',
        string='S/N tiếp nhận',
        required=True,
        index=True,
        domain="[('x_custom_status', 'in', ['sold', 'under_repair'])]",
    )
    new_serial_id = fields.Many2one(
        'stock.lot',
        string='S/N đổi mới',
        copy=False,
        domain="[('x_custom_status', '=', 'available'), ('product_id', '=', product_id)]",
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Đơn bán',
        related='serial_id.x_sale_order_id',
        readonly=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Dòng đơn bán gốc',
        related='serial_id.x_sale_order_line_id',
        readonly=True,
    )
    delivery_picking_id = fields.Many2one(
        'stock.picking',
        string='Phiếu giao hàng',
        related='serial_id.x_delivery_picking_id',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Khách hàng',
        related='serial_id.x_customer_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm',
        related='serial_id.product_id',
        store=True,
        readonly=True,
    )
    purchase_date = fields.Date(
        string='Ngày mua',
        related='serial_id.x_purchase_date',
        readonly=True,
    )
    warranty_end_date = fields.Date(
        string='Hạn bảo hành',
        related='serial_id.x_warranty_end_date',
        readonly=True,
    )
    days_remaining = fields.Integer(
        string='Ngày bảo hành còn lại',
        compute='_compute_days_remaining',
    )
    warranty_status = fields.Selection(
        [
            ('valid', 'Còn hạn'),
            ('expired', 'Đã hết hạn'),
            ('unknown', 'Chưa có thông tin hạn'),
        ],
        string='Tình trạng bảo hành',
        compute='_compute_days_remaining',
    )
    issue_category = fields.Selection(
        [
            ('nsx', 'Lỗi nhà sản xuất'),
            ('user', 'Lỗi người dùng'),
            ('unknown', 'Chưa xác định'),
        ],
        string='Nguyên nhân',
        required=True,
        default='nsx',
    )
    ticket_type = fields.Selection(
        [
            ('repair', 'Sửa chữa / Bảo hành'),
            ('exchange', 'Đổi hàng 1-1'),
        ],
        string='Loại xử lý',
        required=True,
        default='repair',
    )
    warranty_decision = fields.Selection(
        [
            ('pending', 'Chờ xác minh'),
            ('free', 'Miễn phí'),
            ('paid', 'Tính phí'),
        ],
        string='Điều kiện bảo hành',
        default='pending',
        required=True,
    )
    appearance_ok = fields.Boolean(string='Ngoại quan đạt điều kiện đổi mới')
    no_liquid_damage = fields.Boolean(string='Không có dấu hiệu vào nước / chập cháy')
    security_cleared = fields.Boolean(string='Đã đăng xuất tài khoản và xóa mật khẩu')
    condition_notes = fields.Text(string='Tình trạng ngoại quan')
    fault_description = fields.Text(string='Mô tả lỗi kỹ thuật')
    repair_resolution = fields.Text(string='Kết quả xử lý')
    exchange_referral_reason = fields.Text(string='Lý do chuyển từ đổi sang sửa chữa')
    exchange_referral_date = fields.Date(
        string='Ngày chuyển sang sửa chữa',
        readonly=True,
        copy=False,
    )
    exchange_move_ids = fields.Many2many(
        'stock.move',
        'warranty_ticket_stock_move_rel',
        'ticket_id',
        'move_id',
        string='Giao dịch kho đổi mới',
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ('new', 'Mới tiếp nhận'),
            ('waiting_serial', 'Chờ serial thay thế'),
            ('fixing', 'Đang sửa'),
            ('waiting_parts', 'Chờ thay linh kiện'),
            ('done', 'Đã xong'),
        ],
        default='new',
        required=True,
        group_expand='_read_group_state',
        string='Trạng thái',
    )
    source_issue_description = fields.Text(string='Mô tả lỗi từ hệ thống nguồn')
    source_status = fields.Char(string='Trạng thái bảo hành nguồn')
    source_end_date = fields.Date(string='Ngày kết thúc từ hệ thống nguồn')

    @api.depends('warranty_end_date')
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for ticket in self:
            ticket.days_remaining = (
                max((ticket.warranty_end_date - today).days, 0)
                if ticket.warranty_end_date
                else 0
            )
            ticket.warranty_status = (
                'unknown' if not ticket.warranty_end_date
                else 'expired' if ticket.warranty_end_date < today
                else 'valid'
            )

    @api.model
    def _read_group_state(self, states, domain):
        return [key for key, _label in self._fields['state'].selection]

    @api.onchange('serial_id')
    def _onchange_serial_id(self):
        if self.serial_id:
            self.customer_phone = (
                self.serial_id.x_customer_id.phone or self.serial_id.x_customer_id.mobile or ''
            )

    @api.onchange('customer_phone')
    def _onchange_customer_phone(self):
        phone = (self.customer_phone or '').strip()
        if not phone:
            return
        partners = self.env['res.partner'].search([
            '|',
            ('phone', '=', phone),
            ('mobile', '=', phone),
        ])
        lots = self.env['stock.lot'].search([
            ('x_customer_id', 'in', partners.ids),
            ('x_custom_status', 'in', ['sold', 'under_repair']),
        ])
        if len(lots) == 1:
            self.serial_id = lots
        elif not lots:
            self.serial_id = False
            return {
                'warning': {
                    'title': _('Không tìm thấy thiết bị'),
                    'message': _('Không tìm thấy serial đang thuộc khách hàng với số điện thoại này.'),
                }
            }
        else:
            self.serial_id = False
            return {
                'warning': {
                    'title': _('Có nhiều thiết bị'),
                    'message': _('Khách hàng có nhiều thiết bị. Hãy chọn serial cần tiếp nhận.'),
                }
            }

    @api.constrains('serial_id', 'new_serial_id', 'ticket_type')
    def _check_serials(self):
        for ticket in self:
            if ticket.ticket_type not in ('repair', 'exchange'):
                raise ValidationError(_('Chỉ hỗ trợ sửa chữa/bảo hành hoặc đổi hàng 1-1.'))
            if ticket.serial_id and ticket.serial_id == ticket.new_serial_id:
                raise ValidationError(_('Serial cũ và serial đổi mới phải khác nhau.'))
            if ticket.new_serial_id and ticket.ticket_type != 'exchange':
                raise ValidationError(_('Chỉ phiếu đổi mới mới được chọn serial thay thế.'))

    @api.constrains('serial_id', 'state')
    def _check_open_ticket(self):
        for ticket in self.filtered(lambda record: record.state != 'done'):
            duplicate = self.search_count([
                ('id', '!=', ticket.id),
                ('serial_id', '=', ticket.serial_id.id),
                ('state', '!=', 'done'),
            ])
            if duplicate:
                raise ValidationError(_('Serial này đã có một phiếu hậu mãi chưa hoàn tất.'))

    def write(self, vals):
        target_state = vals.get('state')
        exchange_referral = (
            vals.get('ticket_type') == 'repair'
            and vals.get('new_serial_id') is False
            and target_state == 'new'
            and bool((vals.get('exchange_referral_reason') or '').strip())
            and vals.get('exchange_referral_date')
            == fields.Date.context_today(self)
            and all(
                ticket.ticket_type == 'exchange'
                and ticket.state in ('new', 'waiting_serial')
                for ticket in self
            )
        )
        if 'exchange_referral_date' in vals and not exchange_referral:
            raise UserError(_('Ngày chuyển chỉ được ghi cùng thao tác chuyển sang sửa chữa.'))
        if 'exchange_referral_reason' in vals:
            for ticket in self.filtered('exchange_referral_date'):
                if vals['exchange_referral_reason'] != ticket.exchange_referral_reason:
                    raise UserError(_('Không thể sửa lý do chuyển đổi sau khi đã ghi nhận.'))
        immutable_fields = {'serial_id', 'ticket_type'}
        if (
            immutable_fields.intersection(vals)
            and not exchange_referral
        ):
            for ticket in self.filtered(lambda record: record.state != 'new'):
                for field_name in immutable_fields.intersection(vals):
                    current_value = ticket[field_name]
                    if ticket._fields[field_name].type == 'many2one':
                        current_value = current_value.id
                    if vals[field_name] != current_value:
                        raise UserError(_('Không thể thay đổi serial hoặc loại xử lý sau khi bắt đầu xử lý phiếu.'))
        if 'new_serial_id' in vals:
            for ticket in self.filtered(
                lambda record: record.state not in ('new', 'waiting_serial')
            ):
                if vals['new_serial_id'] != ticket.new_serial_id.id:
                    raise UserError(_('Không thể đổi serial thay thế sau khi duyệt phiếu.'))
        if target_state:
            for ticket in self:
                if target_state == 'done' and ticket.ticket_type == 'exchange':
                    if not self.env.context.get('exchange_approval'):
                        raise UserError(_('Phiếu đổi mới chỉ được hoàn tất bằng thao tác duyệt đổi.'))
                elif target_state == 'done':
                    if ticket.state not in ('fixing', 'waiting_parts'):
                        raise UserError(_('Phiếu sửa chữa phải đang xử lý mới có thể hoàn tất.'))
                    if not vals.get('repair_resolution', ticket.repair_resolution):
                        raise ValidationError(_('Hãy ghi nhận kết quả sửa chữa trước khi hoàn tất phiếu.'))
                elif target_state == 'fixing':
                    if ticket.ticket_type != 'repair' or ticket.state not in ('new', 'waiting_parts'):
                        raise UserError(_('Trạng thái sửa chữa không hợp lệ.'))
                    if ticket.serial_id.x_custom_status not in ('sold', 'under_repair'):
                        raise ValidationError(_('Serial tiếp nhận phải đang được khách hàng sở hữu.'))
                elif target_state == 'waiting_parts':
                    if ticket.ticket_type != 'repair' or ticket.state != 'fixing':
                        raise UserError(_('Chỉ phiếu đang sửa mới được chuyển sang chờ linh kiện.'))
                elif target_state == 'waiting_serial':
                    if ticket.ticket_type != 'exchange' or ticket.state != 'new':
                        raise UserError(_('Chỉ phiếu đổi mới mới tiếp nhận mới được chờ serial thay thế.'))
                elif (
                    target_state == 'new'
                    and ticket.state != 'new'
                    and not exchange_referral
                ):
                    raise UserError(_('Không thể đưa phiếu đã xử lý về trạng thái mới tiếp nhận.'))

        result = super().write(vals)
        if target_state == 'fixing':
            self.filtered(lambda ticket: ticket.ticket_type == 'repair').mapped(
                'serial_id'
            ).write({'x_custom_status': 'under_repair'})
        elif target_state == 'done':
            self.filtered(lambda ticket: ticket.ticket_type == 'repair').mapped(
                'serial_id'
            ).write({'x_custom_status': 'sold'})
            if 'completed_date' not in vals:
                super(WarrantyTicket, self).write({
                    'completed_date': fields.Date.context_today(self),
                })
        return result
