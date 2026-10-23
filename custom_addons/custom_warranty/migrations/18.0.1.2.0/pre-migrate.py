def migrate(cr, version):
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'product_template'
           AND column_name = 'warranty_period_days'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        ALTER TABLE product_template
        ADD COLUMN IF NOT EXISTS warranty_period_months integer
    """)
    cr.execute("""
        UPDATE product_template
           SET warranty_period_months = ROUND(
               COALESCE(warranty_period_days, 365)::numeric / 30.4375
           )::integer
    """)
