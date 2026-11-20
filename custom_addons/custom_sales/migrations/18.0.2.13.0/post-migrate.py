def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    SaleOrder = env['sale.order']
    sequences = env['ir.sequence'].search([('code', '=', 'sale.order')])
    for sequence in sequences:
        sequence.write({'prefix': 'S', 'padding': 5})
        SaleOrder._synchronize_existing_code_sequence(
            sequence,
            'sale_order',
            'name',
            r'([0-9]+)$',
            sequence.company_id.id,
        )

    sequences = env['ir.sequence'].search([
        ('code', '=', 'custom.sales.customer.v2'),
    ])
    for sequence in sequences:
        sequence.write({'prefix': 'KH', 'padding': 5})
        SaleOrder._synchronize_existing_code_sequence(
            sequence,
            'res_partner',
            'ref',
            r'^KH([0-9]+)$',
        )
