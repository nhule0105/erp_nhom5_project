from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    warranty_period_days = fields.Integer(
        string='Thời hạn bảo hành (ngày)',
        default=365,
        required=True,
        help='Số ngày bảo hành tính từ ngày giao hàng. Có thể đặt 30 ngày cho hàng cũ.',
    )
    exchange_period_days = fields.Integer(
        string='Thời hạn đổi mới (ngày)',
        default=30,
        required=True,
        help='Số ngày tối đa để xét đổi mới 1-1 cho sản phẩm này.',
    )

    @api.constrains('warranty_period_days', 'exchange_period_days')
    def _check_warranty_periods(self):
        for product in self:
            if product.warranty_period_days < 0 or product.exchange_period_days < 0:
                raise ValidationError(_('Thời hạn bảo hành và đổi mới không được âm.'))


class StockLot(models.Model):
    _inherit = 'stock.lot'

    x_customer_id = fields.Many2one('res.partner', string='Khách hàng')
    x_custom_status = fields.Selection([
        ('available', 'Sẵn sàng bán'),
        ('sold', 'Đã bán'),
        ('under_repair', 'Đang bảo hành'),
        ('defective', 'Lỗi / Chờ xử lý')
    ], string='Trạng thái thiết bị', default='available')
    x_purchase_date = fields.Date(string='Ngày mua hàng')
    x_warranty_end_date = fields.Date(string='Ngày hết hạn bảo hành')


class WarrantyTicket(models.Model):
    _name = 'warranty.ticket'
    _description = 'Phiếu Bảo hành và Đổi trả'
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
        [('nsx', 'Lỗi nhà sản xuất'), ('user', 'Lỗi người dùng')],
        string='Nguyên nhân',
        required=True,
        default='nsx',
    )
    ticket_type = fields.Selection(
        [('repair', 'Sửa chữa / Bảo hành'), ('exchange', 'Đổi mới 1-1')],
        string='Loại xử lý',
        required=True,
        default='repair',
    )
    appearance_ok = fields.Boolean(string='Ngoại quan đạt điều kiện đổi mới')
    no_liquid_damage = fields.Boolean(string='Không có dấu hiệu vào nước / chập cháy')
    security_cleared = fields.Boolean(string='Đã đăng xuất tài khoản và xóa mật khẩu')
    condition_notes = fields.Text(string='Tình trạng ngoại quan')
    fault_description = fields.Text(string='Mô tả lỗi kỹ thuật')
    repair_resolution = fields.Text(string='Kết quả xử lý')
    state = fields.Selection(
        [
            ('new', 'Mới tiếp nhận'),
            ('fixing', 'Đang sửa'),
            ('waiting_parts', 'Chờ thay linh kiện'),
            ('done', 'Đã xong'),
        ],
        default='new',
        required=True,
        group_expand='_read_group_state',
        string='Trạng thái',
    )

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
                raise ValidationError(_('Serial này đã có một phiếu bảo hành hoặc đổi trả chưa hoàn tất.'))

    def write(self, vals):
        target_state = vals.get('state')
        immutable_fields = {'serial_id', 'new_serial_id', 'ticket_type'}
        if immutable_fields.intersection(vals):
            for ticket in self.filtered(lambda record: record.state != 'new'):
                for field_name in immutable_fields.intersection(vals):
                    current_value = ticket[field_name]
                    if ticket._fields[field_name].type == 'many2one':
                        current_value = current_value.id
                    if vals[field_name] != current_value:
                        raise UserError(_('Không thể thay đổi serial hoặc loại xử lý sau khi bắt đầu xử lý phiếu.'))
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
                elif target_state == 'new' and ticket.state != 'new':
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
            exchange_days = old_sn.product_id.product_tmpl_id.exchange_period_days
            days_since_purchase = (
                fields.Date.context_today(ticket) - old_sn.x_purchase_date
            ).days
            if days_since_purchase < 0 or days_since_purchase > exchange_days:
                raise ValidationError(
                    _('Đã quá thời hạn đổi mới %s ngày. Hãy chuyển thiết bị sang luồng sửa chữa.')
                    % exchange_days
                )

            ticket._create_exchange_moves(old_sn, new_sn)
            old_sn.write({'x_custom_status': 'defective'})
            new_sn.write({
                'x_custom_status': 'sold',
                'x_customer_id': old_sn.x_customer_id.id,
                'x_purchase_date': old_sn.x_purchase_date,
                'x_warranty_end_date': old_sn.x_warranty_end_date,
            })
            ticket.with_context(exchange_approval=True).write({
                'state': 'done',
                'completed_date': fields.Date.context_today(ticket),
            })