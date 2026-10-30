from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    combo_category = env.ref(
        'custom_crm.product_category_combo',
        raise_if_not_found=False,
    )
    if not combo_category:
        return

    combos = env['custom.crm.combo'].search([
        ('combo_product_id', '!=', False),
    ])
    sale_lines = env['sale.order.line']
    for combo in combos:
        product = combo.combo_product_id
        if product.type != 'service' or product.categ_id != combo_category:
            continue

        used_in_sales = sale_lines.search_count([
            ('product_id', '=', product.id),
        ])
        combo.combo_product_id = False
        if not used_in_sales:
            product.product_tmpl_id.active = False
