PRODUCT_NAME_REPAIRS = {
    'MASTER-BAG': ('Ba l?? laptop', 'Ba lô laptop'),
    'MASTER-MAT': ('L??t chu???t', 'Lót chuột'),
    'MASTER-MOU': ('Chu???t t???ng k??m', 'Chuột tặng kèm'),
}


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    Product = env['product.product'].with_context(lang='en_US')
    for default_code, (damaged_name, corrected_name) in PRODUCT_NAME_REPAIRS.items():
        products = Product.search([('default_code', '=', default_code)])
        for product in products:
            template = product.product_tmpl_id.with_context(lang='en_US')
            if template.name == damaged_name:
                template.write({'name': corrected_name})
