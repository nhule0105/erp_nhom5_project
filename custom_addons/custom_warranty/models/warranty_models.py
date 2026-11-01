from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    exchange_item_type = fields.Selection(
        [
            ('new_device', 'Thiết bị mới'),
            ('used_device', 'Thiết bị đã qua sử dụng'),
            ('accessory', 'Phụ kiện điện tử'),
        ],
        string='Nhóm chính sách đổi',
        help='Phải chọn nhóm nếu danh mục có chính sách thời hạn đổi.',
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
        return False

    @api.constrains(
        'exchange_period_days',
        'exchange_item_type',
        'parent_id',
        'warranty_period_days',
    )
    def _check_category_exchange_policy(self):
        categories = self.search([('id', 'child_of', self.ids)])
        for category in categories:
            if category.warranty_period_days < 0:
                raise ValidationError(_('Thời hạn bảo hành của danh mục không được âm.'))
            item_type = category._get_exchange_item_type()
            if category.exchange_period_days and not item_type:
                raise ValidationError(
                    _('Hãy chọn nhóm chính sách đổi trước khi cấu hình thời hạn cho danh mục.')
                )
            limit = 365 if item_type == 'accessory' else 30
            if category.exchange_period_days < 0 or category.exchange_period_days > limit:
                raise ValidationError(
                    _('Thời hạn đổi của danh mục phải nằm trong khoảng 0-%s ngày.') % limit
                )
        products = self.env['product.template'].search([
            ('categ_id', 'child_of', self.ids),
        ])
        for product in products:
            if product.exchange_period_days > product._get_exchange_period_limit():
                raise ValidationError(
                    _('Thời hạn đổi của sản phẩm vượt quá giới hạn theo danh mục.')
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
        help='Để trống để kế thừa từ danh mục; sản phẩm chưa phân nhóm không đủ điều kiện đổi.',
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
            limit = product._get_exchange_period_limit()
            if product.exchange_period_days > limit:
                raise ValidationError(
                    _('Thời hạn đổi của sản phẩm vượt quá giới hạn %s ngày.')
                    % limit
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
            if not self._get_exchange_item_type():
                return 0
            return self.exchange_period_days
        item_type = self._get_exchange_item_type()
        if not item_type:
            return 0
        category = self.categ_id
        while category:
            if (
                category.exchange_period_days
                and item_type
                and category._get_exchange_item_type() == item_type
            ):
                return category.exchange_period_days
            category = category.parent_id
        return 30 if item_type in ('new_device', 'used_device') else 0

    def _get_exchange_item_type(self):
        self.ensure_one()
        if self.exchange_item_type:
            return self.exchange_item_type
        return self.categ_id._get_exchange_item_type()

    def _get_exchange_period_limit(self):
        self.ensure_one()
        item_type = self._get_exchange_item_type()
        if item_type == 'accessory':
            return 365
        if item_type in ('new_device', 'used_device'):
            return 30
        return 0


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
        help='Số ngày lịch mặc định để xử lý; có thể điều chỉnh theo chính sách cửa hàng.',
    )
    ticket_code = fields.Char(
        string='Mã phiếu',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('warranty.ticket') or _('New'),
    )
    receive_date = fields.Date(
        string='Ngày tiếp nhận',
        default=fields.Date.context_today,
        required=True,
    )
    completed_date = fields.Date(string='Ngày hoàn tất', readonly=True, copy=False)
    promised_return_date = fields.Date(
        string='Ngày hẹn trả thiết bị',
        default=lambda self: fields.Date.context_today(self) + timedelta(days=3),
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
    approval_status = fields.Selection(
        [
            ('none', 'Chưa gửi duyệt'),
            ('pending', 'Chờ chủ cửa hàng duyệt'),
            ('approved', 'Đã được duyệt'),
        ],
        string='Trạng thái duyệt',
        default='none',
        required=True,
        copy=False,
    )
    approval_user_id = fields.Many2one(
        'res.users',
        string='Người duyệt',
        readonly=True,
        copy=False,
    )
    approval_date = fields.Datetime(
        string='Thời điểm duyệt',
        readonly=True,
        copy=False,
    )
    warranty_decision_reason = fields.Text(
        string='Lý do quyết định bảo hành',
        copy=False,
        help='Có thể để trống; hệ thống sẽ ghi căn cứ tự động từ nguyên nhân và tình trạng bảo hành.',
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
    screen_ok = fields.Boolean(string='Màn hình bình thường')
    keyboard_ok = fields.Boolean(string='Bàn phím hoạt động bình thường')
    battery_charger_ok = fields.Boolean(string='Pin và sạc bình thường')
    accessories_complete = fields.Boolean(string='Đủ phụ kiện đi kèm')
    symptom_power = fields.Boolean(string='Không lên nguồn')
    symptom_charging = fields.Boolean(string='Lỗi sạc')
    symptom_display = fields.Boolean(string='Lỗi màn hình')
    symptom_keyboard = fields.Boolean(string='Lỗi bàn phím')
    symptom_battery = fields.Boolean(string='Lỗi pin')
    symptom_overheating = fields.Boolean(string='Nóng bất thường')
    symptom_network = fields.Boolean(string='Lỗi kết nối mạng')
    symptom_physical_damage = fields.Boolean(string='Nứt/vỡ hoặc móp méo')
    symptom_other = fields.Boolean(string='Lỗi khác')
    fault_summary = fields.Char(
        string='Lỗi ghi nhận',
        compute='_compute_fault_summary',
    )
    intake_checklist_summary = fields.Char(
        string='Checklist tiếp nhận',
        compute='_compute_intake_checklist_summary',
    )
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

    @api.depends(
        'fault_description',
        'symptom_power',
        'symptom_charging',
        'symptom_display',
        'symptom_keyboard',
        'symptom_battery',
        'symptom_overheating',
        'symptom_network',
        'symptom_physical_damage',
        'symptom_other',
    )
    def _compute_fault_summary(self):
        symptom_fields = (
            'symptom_power',
            'symptom_charging',
            'symptom_display',
            'symptom_keyboard',
            'symptom_battery',
            'symptom_overheating',
            'symptom_network',
            'symptom_physical_damage',
            'symptom_other',
        )
        for ticket in self:
            symptoms = [
                ticket._fields[field_name].string
                for field_name in symptom_fields
                if ticket[field_name]
            ]
            description = (ticket.fault_description or '').strip()
            ticket.fault_summary = ', '.join(symptoms + ([description] if description else []))

    def _has_fault_report(self):
        self.ensure_one()
        return bool(
            (self.fault_description or '').strip()
            or any(self[field_name] for field_name in (
                'symptom_power',
                'symptom_charging',
                'symptom_display',
                'symptom_keyboard',
                'symptom_battery',
                'symptom_overheating',
                'symptom_network',
                'symptom_physical_damage',
                'symptom_other',
            ))
        )

    @api.depends(
        'appearance_ok',
        'no_liquid_damage',
        'security_cleared',
        'screen_ok',
        'keyboard_ok',
        'battery_charger_ok',
        'accessories_complete',
    )
    def _compute_intake_checklist_summary(self):
        checklist_fields = (
            'screen_ok',
            'keyboard_ok',
            'battery_charger_ok',
            'accessories_complete',
            'appearance_ok',
            'no_liquid_damage',
            'security_cleared',
        )
        for ticket in self:
            checked = [
                ticket._fields[field_name].string
                for field_name in checklist_fields
                if ticket[field_name]
            ]
            ticket.intake_checklist_summary = (
                _('Đạt: %s. Các mục chưa đánh dấu chưa được xác nhận.') % ', '.join(checked)
                if checked
                else _('Chưa xác nhận mục nào.')
            )
    source_issue_description = fields.Text(string='Mô tả lỗi từ hệ thống nguồn')
    source_status = fields.Char(string='Trạng thái bảo hành nguồn')
    source_end_date = fields.Date(string='Ngày kết thúc từ hệ thống nguồn')

    @api.model_create_multi
    def create(self, vals_list):
        protected_fields = {
            'approval_status',
            'approval_user_id',
            'approval_date',
            'warranty_decision_user_id',
            'warranty_decision_date',
        }
        for vals in vals_list:
            if protected_fields.intersection(vals):
                raise UserError(_('Thông tin xác nhận chỉ được ghi bởi thao tác xác nhận quyết định.'))
            if vals.get('sla_days', 3) < 0:
                raise ValidationError(_('Số ngày SLA không được âm.'))
            receive_date = fields.Date.to_date(
                vals.get('receive_date') or fields.Date.context_today(self)
            )
            if not vals.get('promised_return_date'):
                sla_days = vals.get('sla_days', 3)
                vals['promised_return_date'] = fields.Date.to_string(
                    receive_date + timedelta(days=sla_days)
                )
        return super().create(vals_list)

    @api.constrains('sla_days')
    def _check_sla_days(self):
        if any(ticket.sla_days < 0 for ticket in self):
            raise ValidationError(_('Số ngày SLA không được âm.'))

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

    @api.onchange('receive_date', 'sla_days')
    def _onchange_sla_deadline(self):
        for ticket in self:
            ticket.promised_return_date = (
                ticket.receive_date + timedelta(days=ticket.sla_days)
                if ticket.receive_date and ticket.sla_days >= 0
                else False
            )

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

    def action_submit_for_approval(self):
        for ticket in self:
            if ticket.approval_status != 'none':
                raise UserError(_('Phiếu này đã được gửi duyệt hoặc đã được duyệt.'))
            if ticket.state == 'done':
                raise UserError(_('Không thể gửi duyệt phiếu đã hoàn tất.'))
            if ticket.ticket_type == 'repair':
                expected_decision = ticket._get_warranty_decision_policy()
                if expected_decision == 'pending':
                    raise ValidationError(
                        _('Chưa đủ thông tin để gửi duyệt. Hãy xác định nguyên nhân và hạn bảo hành.')
                    )
                if ticket.warranty_decision != expected_decision:
                    raise ValidationError(
                        _('Đề xuất phải là "%s" theo nguyên nhân và thời hạn bảo hành.')
                        % dict(self._fields['warranty_decision'].selection).get(expected_decision)
                    )
            elif ticket.ticket_type == 'exchange':
                if ticket.state not in ('new', 'waiting_serial'):
                    raise UserError(_('Chỉ phiếu đổi mới chưa hoàn tất mới được gửi duyệt.'))
                ticket._validate_exchange_policy()
                if not ticket.new_serial_id:
                    raise ValidationError(
                        _('Hãy chọn serial thay thế còn sẵn sàng trong kho trước khi gửi duyệt.')
                    )
                if ticket.new_serial_id.x_custom_status != 'available':
                    raise ValidationError(_('Serial thay thế không còn sẵn sàng trong kho.'))
                if ticket.new_serial_id.product_id != ticket.serial_id.product_id:
                    raise ValidationError(_('Serial thay thế phải thuộc cùng sản phẩm với serial lỗi.'))
            else:
                raise ValidationError(_('Loại phiếu này không hỗ trợ gửi duyệt.'))
            ticket._set_approval_status('pending')

    def _set_approval_status(self, status):
        self.ensure_one()
        values = {'approval_status': status}
        if status == 'approved':
            values.update({
                'approval_user_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })
        else:
            values.update({
                'approval_user_id': False,
                'approval_date': False,
            })
        super(WarrantyTicket, self).write(values)

    def action_confirm_warranty_decision(self):
        self._check_warranty_decision_manager()
        for ticket in self:
            if ticket.ticket_type != 'repair':
                raise UserError(
                    _('Chỉ phiếu sửa chữa/bảo hành mới có quyết định miễn phí hoặc tính phí.')
                )
            if ticket.warranty_decision_user_id:
                raise UserError(_('Quyết định bảo hành của phiếu này đã được xác nhận.'))
            if ticket.approval_status != 'pending':
                raise UserError(_('Nhân viên cần gửi đề xuất bảo hành để chủ cửa hàng duyệt.'))
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
            cause = dict(self._fields['issue_category'].selection).get(ticket.issue_category)
            warranty_status = dict(self._fields['warranty_status'].selection).get(
                ticket.warranty_status
            )
            reason = (ticket.warranty_decision_reason or '').strip() or _(
                'Căn cứ: %(cause)s; tình trạng bảo hành: %(status)s.'
            ) % {
                'cause': cause,
                'status': warranty_status,
            }
            super(WarrantyTicket, ticket).write({
                'warranty_decision_reason': reason,
                'warranty_decision_user_id': self.env.user.id,
                'warranty_decision_date': fields.Datetime.now(),
                'approval_status': 'approved',
                'approval_user_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

    def _check_warranty_decision_manager(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(_('Chỉ chủ cửa hàng/quản lý kho được xác nhận quyết định bảo hành.'))

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
        protected_audit_fields = {
            'approval_status',
            'approval_user_id',
            'approval_date',
            'warranty_decision_user_id',
            'warranty_decision_date',
        }
        if protected_audit_fields.intersection(vals):
            raise UserError(_('Không thể tự sửa trạng thái hoặc thông tin duyệt phiếu.'))
        approval_sensitive_fields = {
            'issue_category',
            'new_serial_id',
            'fault_description',
            'symptom_power',
            'symptom_charging',
            'symptom_display',
            'symptom_keyboard',
            'symptom_battery',
            'symptom_overheating',
            'symptom_network',
            'symptom_physical_damage',
            'symptom_other',
            'appearance_ok',
            'no_liquid_damage',
            'security_cleared',
            'warranty_decision',
            'warranty_decision_reason',
        }
        for ticket in self.filtered(lambda record: record.approval_status == 'pending'):
            if approval_sensitive_fields.intersection(vals):
                raise UserError(
                    _('Không thể sửa nội dung đã gửi duyệt; hãy trao đổi với chủ cửa hàng.')
                )
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
        decision_context_fields = {
            'warranty_decision',
            'warranty_decision_reason',
            'issue_category',
            'serial_id',
        }
        for ticket in self.filtered('warranty_decision_user_id'):
            for field_name in decision_context_fields.intersection(vals):
                value = vals[field_name]
                current_value = ticket[field_name]
                if ticket._fields[field_name].type == 'many2one':
                    current_value = current_value.id
                if value != current_value:
                    raise UserError(
                        _('Không thể thay đổi nguyên nhân, serial hoặc quyết định sau khi đã xác nhận.')
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
            for ticket in self.filtered(
                lambda record: record.state != 'new' or record.approval_status == 'pending'
            ):
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
                    if (
                        not self.env.context.get('exchange_approval')
                        or not self.env.user.has_group('stock.group_stock_manager')
                        or ticket.approval_status != 'pending'
                    ):
                        raise UserError(_('Phiếu đổi mới chỉ được hoàn tất bằng thao tác duyệt đổi.'))
                    move_ids = set(ticket.exchange_move_ids.ids)
                    for command in vals.get('exchange_move_ids', []):
                        if command[0] == 6:
                            move_ids = set(command[2])
                        elif command[0] == 4:
                            move_ids.add(command[1])
                        elif command[0] in (2, 3):
                            move_ids.discard(command[1])
                        elif command[0] == 5:
                            move_ids.clear()
                    moves = self.env['stock.move'].browse(list(move_ids))
                    if not moves or any(move.state != 'done' for move in moves):
                        raise ValidationError(
                            _('Chỉ được hoàn tất phiếu đổi sau khi giao dịch kho đã hoàn thành.')
                        )
                elif target_state == 'done':
                    if ticket.state not in ('fixing', 'waiting_parts'):
                        raise UserError(_('Phiếu sửa chữa phải đang xử lý mới có thể hoàn tất.'))
                    if not vals.get('repair_resolution', ticket.repair_resolution):
                        raise ValidationError(_('Hãy ghi nhận kết quả sửa chữa trước khi hoàn tất phiếu.'))
                    if (
                        ticket.warranty_decision not in ('free', 'paid')
                        or not ticket.warranty_decision_user_id
                    ):
                        raise ValidationError(
                            _('Chủ cửa hàng phải xác nhận miễn phí/tính phí trước khi hoàn tất sửa chữa.')
                        )
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

    def unlink(self):
        if any(
            ticket.state != 'new'
            or ticket.exchange_move_ids
            or ticket.warranty_decision_user_id
            for ticket in self
        ):
            raise UserError(_('Không thể xóa phiếu đã bắt đầu xử lý hoặc có lịch sử nghiệp vụ.'))
        return super().unlink()
