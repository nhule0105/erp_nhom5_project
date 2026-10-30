from odoo import _, fields, models
from odoo.exceptions import ValidationError


class WarrantyTicketRepair(models.Model):
    _inherit = 'warranty.ticket'

    def action_start_repair(self):
        for ticket in self:
            if ticket.serial_id.x_custom_status not in ('sold', 'under_repair'):
                raise ValidationError(_('Serial tiếp nhận phải đang được khách hàng sở hữu.'))
            ticket.state = 'fixing'
            if not ticket.repair_start_datetime:
                ticket.repair_start_datetime = fields.Datetime.now()

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
                'repair_completed_datetime': fields.Datetime.now(),
            })
