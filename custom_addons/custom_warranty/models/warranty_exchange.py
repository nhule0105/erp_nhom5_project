from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


class WarrantyTicketExchange(models.Model):
    _inherit = 'warranty.ticket'

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
        if self.exchange_move_ids:
            raise UserError(_('Phiếu đổi mới này đã có giao dịch kho; không được tạo trùng.'))
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
                _('Serial thay thế không có sẵn trong kho nội bộ. Hãy chuyển phiếu sang chờ serial thay thế.')
            )
        if old_sn.product_id != new_sn.product_id:
            raise ValidationError(_('Serial đổi mới phải thuộc cùng sản phẩm với serial lỗi.'))

        moves = self.env['stock.move']
        for lot, source, destination in (
            (old_sn, old_source, loss_location),
            (new_sn, new_source, customer_location),
        ):
            move = self.env['stock.move'].create({
                'name': _('Đổi mới 1-1: %s') % self.ticket_code,
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

    def _validate_exchange_policy(self):
        self.ensure_one()
        old_sn = self.serial_id
        if self.ticket_type != 'exchange':
            raise UserError(_('Chỉ phiếu có loại xử lý Đổi mới 1-1 mới được duyệt đổi.'))
        if not old_sn or old_sn.x_custom_status != 'sold':
            raise ValidationError(_('Serial cũ phải đang thuộc khách hàng và chưa được xử lý.'))
        if not old_sn.x_customer_id:
            raise ValidationError(_('Serial cũ chưa được liên kết với khách hàng.'))
        if not old_sn.x_purchase_date:
            raise ValidationError(_('Serial cũ chưa có ngày mua để kiểm tra thời hạn đổi mới.'))
        if self.issue_category != 'nsx':
            raise ValidationError(
                _('Không áp dụng đổi 1-1 cho lỗi người dùng hoặc nguyên nhân chưa xác định.')
            )
        if not self.appearance_ok or not self.no_liquid_damage or not self.security_cleared:
            raise ValidationError(
                _('Chưa đạt kiểm tra ngoại quan, dấu hiệu vào nước/chập cháy hoặc bảo mật thiết bị.')
            )

        product = old_sn.product_id.product_tmpl_id
        exchange_days = product._get_exchange_period_days()
        if not exchange_days:
            raise ValidationError(
                _('Chưa cấu hình thời hạn đổi cho phụ kiện này; hãy kiểm tra chính sách sản phẩm.')
            )
        days_since_purchase = (
            fields.Date.context_today(self) - old_sn.x_purchase_date
        ).days
        if days_since_purchase < 0 or days_since_purchase > exchange_days:
            raise ValidationError(
                _('Đã quá thời hạn đổi mới %s ngày. Hãy chuyển thiết bị sang luồng sửa chữa.')
                % exchange_days
            )

    def action_wait_for_exchange_serial(self):
        for ticket in self:
            if ticket.state != 'new':
                raise UserError(_('Chỉ phiếu đổi mới mới tiếp nhận mới được chuyển sang chờ serial.'))
            ticket._validate_exchange_policy()
            ticket.state = 'waiting_serial'

    def action_refer_exchange_to_repair(self):
        for ticket in self:
            if ticket.ticket_type != 'exchange' or ticket.state not in ('new', 'waiting_serial'):
                raise UserError(
                    _('Chỉ phiếu đổi mới chưa duyệt mới có thể chuyển sang sửa chữa/bảo hành.')
                )
            reason = (ticket.exchange_referral_reason or '').strip()
            if not reason:
                raise ValidationError(_('Hãy ghi rõ lý do chuyển phiếu sang sửa chữa/bảo hành.'))
            ticket.write({
                'ticket_type': 'repair',
                'new_serial_id': False,
                'state': 'new',
                'exchange_referral_reason': reason,
                'exchange_referral_date': fields.Date.context_today(ticket),
            })

    def action_approve_exchange(self):
        self._check_manager()
        for ticket in self:
            old_sn = ticket.serial_id
            new_sn = ticket.new_serial_id
            if ticket.state not in ('new', 'waiting_serial'):
                raise UserError(_('Chỉ phiếu mới hoặc đang chờ serial mới được duyệt đổi.'))
            ticket._validate_exchange_policy()
            if not old_sn or not new_sn:
                raise ValidationError(_('Phải chọn đầy đủ serial cũ và serial thay thế.'))
            if new_sn.x_custom_status != 'available':
                raise ValidationError(_('Serial thay thế không còn sẵn sàng trong kho.'))

            exchange_moves = ticket._create_exchange_moves(old_sn, new_sn)
            old_sn.write({'x_custom_status': 'defective'})
            new_sn.write({
                'x_custom_status': 'sold',
                'x_customer_id': old_sn.x_customer_id.id,
                'x_purchase_date': old_sn.x_purchase_date,
                'x_warranty_end_date': old_sn.x_warranty_end_date,
                'x_sale_order_id': old_sn.x_sale_order_id.id,
                'x_sale_order_line_id': old_sn.x_sale_order_line_id.id,
                'x_delivery_picking_id': old_sn.x_delivery_picking_id.id,
                'x_sale_date': old_sn.x_sale_date,
                'x_replaced_from_lot_id': old_sn.id,
            })
            ticket.with_context(exchange_approval=True).write({
                'exchange_move_ids': [(6, 0, exchange_moves.ids)],
                'state': 'done',
                'completed_date': fields.Date.context_today(ticket),
            })
