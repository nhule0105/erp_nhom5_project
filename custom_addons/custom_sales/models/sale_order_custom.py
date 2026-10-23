from datetime import timedelta

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    serial_lot_ids = fields.Many2many(
        'stock.lot',
        string='Serial đã giao',
        compute='_compute_serial_lot_ids',
    )

    @api.depends(
        'picking_ids.state',
        'picking_ids.picking_type_code',
        'picking_ids.move_ids.move_line_ids.lot_id',
    )
    def _compute_serial_lot_ids(self):
        for order in self:
            order.serial_lot_ids = order.picking_ids.filtered(
                lambda picking: picking.state == 'done'
                and picking.picking_type_code == 'outgoing'
            ).move_ids.move_line_ids.lot_id


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        result = super()._action_done()
        purchase_date = fields.Date.context_today(self)
        for picking in self.filtered(
            lambda record: record.picking_type_code == 'outgoing'
            and record.sale_id
        ):
            serials = picking.move_ids.move_line_ids.lot_id
            for serial in serials:
                warranty_days = serial.product_id.product_tmpl_id.warranty_period_days
                serial.write({
                    'x_customer_id': picking.partner_id.id,
                    'x_custom_status': 'sold',
                    'x_purchase_date': purchase_date,
                    'x_warranty_end_date': purchase_date + timedelta(days=warranty_days),
                })
        return result
