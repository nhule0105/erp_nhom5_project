from datetime import timedelta

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

    warranty_ticket_ids = fields.One2many(
        'warranty.ticket',
        'serial_id',
        string='Lịch sử bảo hành',
        readonly=True,
    )
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

    sla_days = fields.Integer(
        string='Số ngày SLA',
        default=3,
        required=True,
        help='Thời hạn xử lý mặc định tính từ ngày tiếp nhận.',
    )
    ticket_code = fields.Char(
        string='Mã phiếu',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('warranty.ticket') or _('New'),
    )
    receive_date = fields.Date(string='Ngày tiếp nhận', default=fields.Date.context_today)
    completed_date = fields.Date(string='Ngày hoàn tất', readonly=True, copy=False)
    promised_return_date = fields.Date(
        string='Ngày hẹn trả thiết bị',
        help='Mặc định là ngày tiếp nhận cộng số ngày SLA; có thể điều chỉnh.',
    )
    repair_start_datetime = fields.Datetime(
        string='Bắt đầu sửa chữa',
        readonly=True,
        copy=False,
    )
    repair_completed_datetime = fields.Datetime(
        string='Hoàn thành sửa chữa',
        readonly=True,
        copy=False,
    )
    processing_duration_hours = fields.Float(
        string='Tổng thời gian xử lý (giờ)',
        compute='_compute_processing_duration',
        store=True,
        readonly=True,
    )
    is_overdue = fields.Boolean(
        string='Quá hạn trả',
        compute='_compute_processing_duration',
        store=True,
        readonly=True,
    )
    customer_phone = fields.Char(string='Số điện thoại khách hàng')
    serial_id = fields.Many2one(
        'stock.lot',
        string='S/N tiếp nhận',
        required=True,
        index=True,
        domain="[('x_custom_status', 'in', ['sold', 'under_repair'])]",
    )
    serial_history_ids = fields.One2many(
        'warranty.ticket',
        related='serial_id.warranty_ticket_ids',
        string='Lịch sử bảo hành của serial',
        readonly=True,
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
        default='unknown',
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
    warranty_decision_reason = fields.Text(
        string='Lý do quyết định bảo hành',
        copy=False,
    )
    warranty_decision_user_id = fields.Many2one(
        'res.users',
        string='Người xác nhận quyết định',
        readonly=True,
        copy=False,
    )
    warranty_decision_date = fields.Datetime(
        string='Thời điểm xác nhận quyết định',
        readonly=True,
        copy=False,
    )
    technician_id = fields.Many2one(
        'res.users',
        string='Kỹ thuật viên phụ trách',
        domain=[('share', '=', False)],
        copy=False,
    )
    technician_assigned_date = fields.Datetime(
        string='Thời điểm phân công',
        readonly=True,
        copy=False,
    )
    appearance_ok = fields.Boolean(string='Ngoại quan đạt điều kiện đổi mới')
    no_liquid_damage = fields.Boolean(string='Không có dấu hiệu vào nước / chập cháy')
    security_cleared = fields.Boolean(string='Đã đăng xuất tài khoản và xóa mật khẩu')
    condition_notes = fields.Text(string='Tình trạng ngoại quan')
    screen_condition = fields.Text(string='Tình trạng màn hình')
    keyboard_condition = fields.Text(string='Tình trạng bàn phím')
    battery_charger_condition = fields.Text(string='Tình trạng pin và sạc')
    accessories_condition = fields.Text(string='Phụ kiện đi kèm')
    intake_notes = fields.Text(string='Ghi chú nhân viên tiếp nhận')
    inspection_attachment_ids = fields.Many2many(
        'ir.attachment',
        'warranty_ticket_attachment_rel',
        'ticket_id',
        'attachment_id',
        string='Ảnh tình trạng khi nhận',
        copy=True,
    )
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            receive_date = fields.Date.to_date(
                vals.get('receive_date') or fields.Date.context_today(self)
            )
            if not vals.get('promised_return_date'):
                sla_days = vals.get('sla_days', 3)
                vals['promised_return_date'] = fields.Date.to_string(
                    receive_date + timedelta(days=sla_days)
                )
        return super().create(vals_list)

    @api.model
    def _cron_update_sla_overdue(self):
        tickets = self.search([
            ('state', '!=', 'done'),
            ('promised_return_date', '!=', False),
        ])
        tickets._compute_processing_duration()
        self.env['warranty.ticket'].flush_model(['is_overdue'])

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

    @api.depends(
        'repair_start_datetime',
        'repair_completed_datetime',
        'promised_return_date',
        'state',
    )
    def _compute_processing_duration(self):
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        for ticket in self:
            if ticket.repair_start_datetime:
                end = ticket.repair_completed_datetime or now
                ticket.processing_duration_hours = max(
                    (end - ticket.repair_start_datetime).total_seconds() / 3600,
                    0,
                )
            else:
                ticket.processing_duration_hours = 0
            ticket.is_overdue = bool(
                ticket.promised_return_date
                and ticket.state != 'done'
                and ticket.promised_return_date < today
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

    def _get_warranty_decision_policy(self):
        self.ensure_one()
        if self.issue_category == 'unknown':
            return 'pending'
        if self.warranty_status == 'unknown':
            return 'pending'
        if self.warranty_status == 'expired':
            return 'paid'
        return 'free' if self.issue_category == 'nsx' else 'paid'

    def action_confirm_warranty_decision(self):
        for ticket in self:
            if ticket.ticket_type != 'repair':
                raise UserError(
                    _('Chỉ phiếu sửa chữa/bảo hành mới có quyết định miễn phí hoặc tính phí.')
                )
            if ticket.warranty_decision not in ('free', 'paid'):
                raise ValidationError(
                    _('Chưa thể xác nhận: hãy chọn Miễn phí hoặc Tính phí sau khi kiểm tra.')
                )
            expected_decision = ticket._get_warranty_decision_policy()
            if expected_decision == 'pending':
                raise ValidationError(
                    _('Chưa đủ thông tin để quyết định. Hãy xác định nguyên nhân và hạn bảo hành.')
                )
            if ticket.warranty_decision != expected_decision:
                raise ValidationError(
                    _('Quyết định không phù hợp: tình trạng hiện tại phải là "%s".')
                    % dict(self._fields['warranty_decision'].selection).get(expected_decision)
                )
            if not (ticket.warranty_decision_reason or '').strip():
                raise ValidationError(_('Phải ghi rõ lý do trước khi xác nhận quyết định.'))
            ticket.with_context(warranty_decision_confirmation=True).write({
                'warranty_decision_user_id': self.env.user.id,
                'warranty_decision_date': fields.Datetime.now(),
            })

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
        if 'technician_id' in vals:
            vals = dict(vals)
            vals['technician_assigned_date'] = (
                fields.Datetime.now() if vals['technician_id'] else False
            )
        if 'warranty_decision' in vals:
            for ticket in self:
                if (
                    ticket.warranty_decision != 'pending'
                    and vals['warranty_decision'] != ticket.warranty_decision
                ):
                    raise UserError(_('Không thể thay đổi quyết định đã xác nhận.'))
                if (
                    vals['warranty_decision'] != 'pending'
                    and vals.get('issue_category', ticket.issue_category) == 'unknown'
                ):
                    raise ValidationError(
                        _('Chưa thể chọn miễn phí hoặc tính phí khi chưa xác định nguyên nhân.')
                    )
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

    def _check_manager(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(_('Chỉ quản lý kho mới được duyệt đổi mới 1-1.'))

    def _get_lot_location(self, lot, usage, available=False):
        quants = self.env['stock.quant'].search([
            ('lot_id', '=', lot.id),
            ('location_id.usage', '=', usage),
            ('quantity', '>', 0),
        ], order='id')
        for quant in quants:
            quantity = quant.available_quantity if available else quant.quantity
            if float_compare(
                quantity,
                1.0,
                precision_rounding=lot.product_id.uom_id.rounding,
            ) >= 0:
                return quant.location_id
        return self.env['stock.location']

    def _create_exchange_moves(self, old_sn, new_sn):
        if self.exchange_move_ids or self.return_move_ids:
            raise UserError(_('Phiếu đổi trả này đã có giao dịch kho; không được tạo trùng.'))
        customer_location = self.env.ref('stock.stock_location_customers')
        loss_location = self.env['stock.location'].search([
            ('usage', '=', 'inventory'),
            ('scrap_location', '=', False),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not loss_location:
            raise UserError(_('Không tìm thấy vị trí điều chỉnh tồn kho cho công ty hiện tại.'))
        new_source = self._get_lot_location(new_sn, 'internal', available=True)
        old_source = self._get_lot_location(old_sn, 'customer', available=True)
        if not old_source:
            raise ValidationError(
                _('Không tìm thấy serial cũ trong vị trí kho Khách hàng; không thể thu hồi tồn kho.')
            )
        if not new_source:
            raise ValidationError(
                _('Serial thay thế không có sẵn trong kho nội bộ. Hãy chuyển phiếu sang sửa chữa hoặc bổ sung hàng.')
            )
        if old_sn.product_id != new_sn.product_id:
            raise ValidationError(_('Serial đổi mới phải thuộc cùng sản phẩm với serial lỗi.'))

        moves = self.env['stock.move']
        for lot, source, destination in (
            (old_sn, old_source, loss_location),
            (new_sn, new_source, customer_location),
        ):
            move = self.env['stock.move'].create({
                'name': _('Đổi trả 1-1: %s') % self.ticket_code,
                'product_id': lot.product_id.id,
                'product_uom_qty': 1,
                'product_uom': lot.product_id.uom_id.id,
                'location_id': source.id,
                'location_dest_id': destination.id,
                'company_id': self.env.company.id,
            })
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': lot.product_id.id,
                'product_uom_id': lot.product_id.uom_id.id,
                'location_id': source.id,
                'location_dest_id': destination.id,
                'lot_id': lot.id,
                'quantity': 1,
                'picked': True,
            })
            moves |= move
        moves._action_done()
        if any(move.state != 'done' for move in moves):
            raise UserError(_('Không thể hoàn tất dịch chuyển serial trong kho.'))
        return moves

    def _create_return_move(self, old_sn):
        if self.return_move_ids or self.exchange_move_ids:
            raise UserError(_('Phiếu trả hàng này đã có giao dịch kho; không được tạo trùng.'))
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        customer_location = self.env.ref('stock.stock_location_customers')
        if not warehouse or not warehouse.lot_stock_id:
            raise UserError(_('Không tìm thấy kho nội bộ để nhập lại sản phẩm trả.'))
        source = self._get_lot_location(old_sn, 'customer', available=True)
        if not source:
            raise ValidationError(_('Không tìm thấy serial trả hàng tại vị trí Khách hàng.'))
        move = self.env['stock.move'].create({
            'name': _('Trả hàng: %s') % self.ticket_code,
            'product_id': old_sn.product_id.id,
            'product_uom_qty': 1,
            'product_uom': old_sn.product_id.uom_id.id,
            'location_id': source.id,
            'location_dest_id': warehouse.lot_stock_id.id,
            'company_id': self.env.company.id,
        })
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'product_id': old_sn.product_id.id,
            'product_uom_id': old_sn.product_id.uom_id.id,
            'location_id': source.id,
            'location_dest_id': warehouse.lot_stock_id.id,
            'lot_id': old_sn.id,
            'quantity': 1,
            'picked': True,
        })
        move._action_done()
        if move.state != 'done':
            raise UserError(_('Không thể hoàn tất nhập kho sản phẩm trả.'))
        return move

    def action_start_repair(self):
        for ticket in self:
            if ticket.serial_id.x_custom_status not in ('sold', 'under_repair'):
                raise ValidationError(_('Serial tiếp nhận phải đang được khách hàng sở hữu.'))
            ticket.state = 'fixing'

    def action_waiting_parts(self):
        for ticket in self:
            ticket.state = 'waiting_parts'

    def action_resume_repair(self):
        for ticket in self:
            ticket.state = 'fixing'

    def action_complete_repair(self):
        for ticket in self:
            if not ticket.repair_resolution:
                raise ValidationError(_('Hãy ghi nhận kết quả sửa chữa trước khi hoàn tất phiếu.'))
            ticket.write({
                'state': 'done',
                'completed_date': fields.Date.context_today(ticket),
            })

    def action_approve_exchange(self):
        self._check_manager()
        for ticket in self:
            old_sn = ticket.serial_id
            new_sn = ticket.new_serial_id
            if ticket.ticket_type != 'exchange':
                raise UserError(_('Chỉ phiếu có loại xử lý Đổi mới 1-1 mới được duyệt đổi.'))
            if ticket.state != 'new':
                raise UserError(_('Chỉ phiếu mới tiếp nhận mới được duyệt đổi mới 1-1.'))
            if not old_sn or not new_sn:
                raise ValidationError(_('Phải chọn đầy đủ serial cũ và serial thay thế.'))
            if old_sn.x_custom_status != 'sold':
                raise ValidationError(_('Serial cũ chưa được bán ra hoặc đang được xử lý.'))
            if new_sn.x_custom_status != 'available':
                raise ValidationError(_('Serial thay thế không còn sẵn sàng trong kho.'))
            if not old_sn.x_customer_id:
                raise ValidationError(_('Serial cũ chưa được liên kết với khách hàng.'))
            if not old_sn.x_purchase_date:
                raise ValidationError(_('Serial cũ chưa có ngày bán để kiểm tra thời hạn đổi mới.'))
            if ticket.issue_category != 'nsx':
                raise ValidationError(_('Chỉ tiếp nhận đổi mới 1-1 cho lỗi nhà sản xuất.'))
            if not ticket.appearance_ok or not ticket.no_liquid_damage or not ticket.security_cleared:
                raise ValidationError(
                    _('Chưa đạt kiểm tra ngoại quan, dấu hiệu vào nước/chập cháy hoặc bảo mật thiết bị.')
                )
            exchange_days = old_sn.product_id.product_tmpl_id._get_exchange_period_days()
            days_since_purchase = (
                fields.Date.context_today(ticket) - old_sn.x_purchase_date
            ).days
            if days_since_purchase < 0 or days_since_purchase > exchange_days:
                raise ValidationError(
                    _('Đã quá thời hạn đổi mới %s ngày. Hãy chuyển thiết bị sang luồng sửa chữa.')
                    % exchange_days
                )

            exchange_moves = ticket._create_exchange_moves(old_sn, new_sn)
            old_sn.write({'x_custom_status': 'defective'})
            new_sn.write({
                'x_custom_status': 'sold',
                'x_customer_id': old_sn.x_customer_id.id,
                'x_purchase_date': old_sn.x_purchase_date,
                'x_warranty_end_date': old_sn.x_warranty_end_date,
                'x_sale_order_id': old_sn.x_sale_order_id.id,
                'x_delivery_picking_id': old_sn.x_delivery_picking_id.id,
                'x_sale_date': old_sn.x_sale_date,
            })
            ticket.with_context(exchange_approval=True).write({
                'exchange_move_ids': [(6, 0, exchange_moves.ids)],
                'state': 'done',
                'completed_date': fields.Date.context_today(ticket),
            })

    def action_approve_return(self):
        self._check_manager()
        for ticket in self:
            if ticket.ticket_type != 'return':
                raise UserError(_('Chỉ phiếu có loại xử lý Trả hàng mới được duyệt.'))
            if ticket.state != 'new':
                raise UserError(_('Chỉ phiếu mới tiếp nhận mới được duyệt trả hàng.'))
            old_sn = ticket.serial_id
            if not old_sn or old_sn.x_custom_status != 'sold':
                raise ValidationError(_('Serial trả hàng phải đang thuộc khách hàng.'))
            if not old_sn.x_customer_id or not old_sn.x_purchase_date:
                raise ValidationError(_('Serial trả hàng chưa đủ thông tin khách hàng/ngày giao.'))
            if ticket.issue_category == 'unknown':
                raise ValidationError(_('Cần xác định nguyên nhân trước khi duyệt trả hàng.'))
            return_move = ticket._create_return_move(old_sn)
            old_sn.write({
                'x_custom_status': 'available',
                'x_customer_id': False,
            })
            ticket.with_context(return_approval=True).write({
                'return_move_ids': [(6, 0, return_move.ids)],
                'state': 'done',
                'completed_date': fields.Date.context_today(ticket),
            }            )
