from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class StockLocation(models.Model):
    _inherit = 'stock.location'

    warranty_repair_location = fields.Boolean(
        string='Vị trí sửa chữa bảo hành',
        copy=False,
        default=False,
        index=True,
    )
    warranty_defective_location = fields.Boolean(
        string='Vị trí cách ly hàng lỗi bảo hành',
        copy=False,
        default=False,
        index=True,
    )


class WarrantyTicketRepair(models.Model):
    _inherit = 'warranty.ticket'

    def _get_internal_warranty_location(self, marker_field, location_name):
        self.ensure_one()
        company = self.sale_order_id.company_id or self.serial_id.company_id or self.env.company
        warehouse = self.sale_order_id.warehouse_id
        if not warehouse or warehouse.company_id != company:
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)],
                order='sequence, id',
                limit=1,
            )
        if not warehouse or not warehouse.lot_stock_id:
            raise UserError(_('Không tìm thấy kho nội bộ để tiếp nhận thiết bị sửa chữa.'))

        location_model = self.env['stock.location'].sudo()
        location = location_model.search([
            ('location_id', '=', warehouse.lot_stock_id.id),
            ('company_id', '=', company.id),
            ('usage', '=', 'internal'),
            (marker_field, '=', True),
        ], limit=1)
        if not location:
            location = location_model.create({
                'name': location_name,
                'location_id': warehouse.lot_stock_id.id,
                'company_id': company.id,
                'usage': 'internal',
                marker_field: True,
            })
        return location

    def _get_repair_stock_location(self):
        return self._get_internal_warranty_location(
            'warranty_repair_location',
            _('Khu vực sửa chữa bảo hành'),
        )

    def _create_repair_stock_move(self, source, destination, operation):
        self.ensure_one()
        lot = self.serial_id
        company = self.sale_order_id.company_id or lot.company_id or self.env.company
        quants = self.env['stock.quant'].search([
            ('lot_id', '=', lot.id),
            ('location_id', '=', source.id),
            ('quantity', '>', 0),
        ])
        available_quantity = sum(quants.mapped('available_quantity'))
        if float_compare(
            available_quantity,
            1.0,
            precision_rounding=lot.product_id.uom_id.rounding,
        ) < 0:
            raise ValidationError(
                _('Không tìm thấy Serial ở vị trí nguồn hoặc Serial đã được đặt chỗ.')
            )

        move = self.env['stock.move'].create({
            'name': _('%(operation)s - %(ticket)s') % {
                'operation': operation,
                'ticket': self.ticket_code,
            },
            'origin': self.ticket_code,
            'partner_id': self.partner_id.id,
            'product_id': lot.product_id.id,
            'product_uom_qty': 1,
            'product_uom': lot.product_id.uom_id.id,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'company_id': company.id,
        })
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'company_id': company.id,
            'product_id': lot.product_id.id,
            'product_uom_id': lot.product_id.uom_id.id,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'lot_id': lot.id,
            'quantity': 1,
            'picked': True,
        })
        move._action_done()
        if move.state != 'done':
            raise UserError(_('Không thể hoàn tất giao dịch kho sửa chữa.'))
        return move

    def _has_repair_intake_move(self, repair_location):
        self.ensure_one()
        customer_location = self.env.ref('stock.stock_location_customers')
        return any(
            move.state == 'done'
            and move.location_id == customer_location
            and move.location_dest_id == repair_location
            and self.serial_id in move.move_line_ids.lot_id
            for move in self.repair_move_ids
        )

    def _receive_repair_device(self):
        self.ensure_one()
        repair_location = self._get_repair_stock_location()
        if self._has_repair_intake_move(repair_location):
            return
        if not self.partner_id:
            raise ValidationError(_('Serial chưa được liên kết với khách hàng.'))
        customer_location = self.env.ref('stock.stock_location_customers')
        move = self._create_repair_stock_move(
            customer_location,
            repair_location,
            _('Tiếp nhận sửa chữa'),
        )
        self.write({'repair_move_ids': [(4, move.id)]})
        self.serial_id.write({'x_custom_status': 'under_repair'})

    def action_receive_repair_device(self):
        for ticket in self:
            if ticket.ticket_type != 'repair' or ticket.state != 'new':
                raise UserError(
                    _('Chỉ phiếu sửa chữa mới tiếp nhận mới được ghi nhận máy vào kho sửa chữa.')
                )
            if ticket._has_repair_intake_move(ticket._get_repair_stock_location()):
                raise UserError(_('Serial này đã được tiếp nhận vào kho sửa chữa.'))
            ticket._receive_repair_device()

    def action_start_repair(self):
        for ticket in self:
            if ticket.ticket_type != 'repair' or ticket.state not in ('new', 'waiting_parts'):
                raise UserError(_('Trạng thái phiếu không cho phép bắt đầu hoặc tiếp tục sửa chữa.'))
            if ticket.serial_id.x_custom_status not in ('sold', 'under_repair'):
                raise ValidationError(_('Serial tiếp nhận phải đang được khách hàng sở hữu.'))
            if not ticket._has_fault_report():
                raise ValidationError(
                    _('Hãy chọn biểu hiện lỗi hoặc nhập mô tả lỗi trước khi bắt đầu sửa chữa.')
                )
            ticket._receive_repair_device()
            ticket.with_context(repair_action='start').write({
                'state': 'fixing',
                'repair_start_datetime': (
                    ticket.repair_start_datetime or fields.Datetime.now()
                ),
            })

    def action_waiting_parts(self):
        for ticket in self:
            if ticket.ticket_type != 'repair' or ticket.state != 'fixing':
                raise UserError(_('Chỉ phiếu đang sửa mới được chuyển sang chờ linh kiện.'))
            ticket.with_context(repair_action='waiting_parts').write({
                'state': 'waiting_parts',
            })

    def action_resume_repair(self):
        for ticket in self:
            if ticket.ticket_type != 'repair' or ticket.state != 'waiting_parts':
                raise UserError(_('Chỉ phiếu chờ linh kiện mới được tiếp tục sửa.'))
            ticket.with_context(repair_action='resume').write({
                'state': 'fixing',
            })

    def action_complete_repair(self):
        for ticket in self:
            if ticket.ticket_type != 'repair' or ticket.state != 'fixing':
                raise UserError(
                    _('Phiếu phải đang sửa mới có thể hoàn tất. '
                      'Hãy chọn Tiếp tục sửa sau khi linh kiện đã về.')
                )
            if not ticket.repair_resolution:
                raise ValidationError(_('Hãy ghi nhận kết quả sửa chữa trước khi hoàn tất phiếu.'))
            if (
                ticket.warranty_decision not in ('free', 'paid')
                or not ticket.warranty_decision_user_id
            ):
                raise ValidationError(
                    _('Chủ cửa hàng phải xác nhận miễn phí/tính phí trước khi hoàn tất sửa chữa.')
                )
            ticket._receive_repair_device()
            repair_location = ticket._get_repair_stock_location()
            customer_location = ticket.env.ref('stock.stock_location_customers')
            if any(
                move.state == 'done'
                and move.location_id == repair_location
                and move.location_dest_id == customer_location
                and ticket.serial_id in move.move_line_ids.lot_id
                for move in ticket.repair_move_ids
            ):
                raise UserError(_('Serial này đã được chuyển trả cho khách hàng.'))
            return_move = ticket._create_repair_stock_move(
                repair_location,
                customer_location,
                _('Trả máy sau sửa chữa'),
            )
            ticket.write({'repair_move_ids': [(4, return_move.id)]})
            ticket.with_context(repair_action='complete').write({
                'state': 'done',
                'completed_date': fields.Date.context_today(ticket),
                'repair_completed_datetime': fields.Datetime.now(),
            })
