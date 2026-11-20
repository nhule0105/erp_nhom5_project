from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    category_model = env['product.category']
    product_model = env['product.template']
    product_categories = {
        'laptop': env.ref('custom_crm.product_category_laptop'),
        'mouse': env.ref('custom_crm.product_category_mouse'),
        'backpack': env.ref('custom_crm.product_category_backpack'),
    }
    category_ids = {
        product_type: set(category_model.search([
            ('id', 'child_of', category.id),
        ]).ids)
        for product_type, category in product_categories.items()
    }

    products = product_model.search([
        ('active', '=', True),
        ('is_storable', '=', True),
        ('lifecycle_product_type', '=', False),
    ])
    for product in products:
        for product_type, ids in category_ids.items():
            if product.categ_id.id in ids:
                product.lifecycle_product_type = product_type
                break
