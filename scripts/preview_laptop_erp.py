import getpass
import sys
import xmlrpc.client

import psycopg2


SOURCE_HOST = "127.0.0.1"
SOURCE_PORT = 5432
SOURCE_DB = "laptop_erp"
SOURCE_USER = "postgres"
ODOO_URL = "http://localhost:8069"
ODOO_DB = "erp_tramy"
ODOO_USER = input("Odoo login (same as the Odoo web login): ").strip()

TABLES = (
    "laptop_customers",
    "laptop_products",
    "laptop_orders",
    "laptop_order_items",
    "laptop_serials",
    "laptop_warranties",
)

COUNT_QUERIES = {
    "laptop_customers": "SELECT count(*) FROM public.laptop_customers",
    "laptop_products": "SELECT count(*) FROM public.laptop_products",
    "laptop_orders": "SELECT count(*) FROM public.laptop_orders",
    "laptop_order_items": "SELECT count(*) FROM public.laptop_order_items",
    "laptop_serials": "SELECT count(*) FROM public.laptop_serials",
    "laptop_warranties": "SELECT count(*) FROM public.laptop_warranties",
}

ORPHAN_QUERIES = {
    "orders without customer": """
        SELECT count(*)
        FROM public.laptop_orders o
        LEFT JOIN public.laptop_customers c ON c.id = o.customer_id
        WHERE o.customer_id IS NOT NULL AND c.id IS NULL
    """,
    "order items without order": """
        SELECT count(*)
        FROM public.laptop_order_items i
        LEFT JOIN public.laptop_orders o ON o.id = i.order_id
        WHERE i.order_id IS NOT NULL AND o.id IS NULL
    """,
    "order items without serial": """
        SELECT count(*)
        FROM public.laptop_order_items i
        LEFT JOIN public.laptop_serials s ON s.id = i.serial_id
        WHERE i.serial_id IS NOT NULL AND s.id IS NULL
    """,
    "serials without product": """
        SELECT count(*)
        FROM public.laptop_serials s
        LEFT JOIN public.laptop_products p ON p.id = s.product_id
        WHERE s.product_id IS NOT NULL AND p.id IS NULL
    """,
    "warranties without serial": """
        SELECT count(*)
        FROM public.laptop_warranties w
        LEFT JOIN public.laptop_serials s ON s.id = w.serial_id
        WHERE w.serial_id IS NOT NULL AND s.id IS NULL
    """,
    "warranties without customer": """
        SELECT count(*)
        FROM public.laptop_warranties w
        LEFT JOIN public.laptop_customers c ON c.id = w.customer_id
        WHERE w.customer_id IS NOT NULL AND c.id IS NULL
    """,
}


def main():
    if not ODOO_USER:
        raise RuntimeError("Enter the Odoo login you use on the Odoo website.")

    odoo_password = getpass.getpass(
        f"Odoo password for {ODOO_USER}@{ODOO_DB}: "
    )

    print("\nChecking Odoo connection...")
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    version = common.version()
    uid = common.authenticate(ODOO_DB, ODOO_USER, odoo_password, {})
    if not uid:
        raise RuntimeError(
            f"Odoo authentication failed for database {ODOO_DB!r}. "
            "Check the database name, login, and password."
        )

    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    partner_count = models.execute_kw(
        ODOO_DB, uid, odoo_password, "res.partner", "search_count", [[]]
    )
    product_count = models.execute_kw(
        ODOO_DB, uid, odoo_password, "product.template", "search_count", [[]]
    )
    print(f"Odoo {version.get('server_version')} / {ODOO_DB}: connected")
    print(f"Existing Odoo contacts: {partner_count}")
    print(f"Existing Odoo products: {product_count}")

    source_password = getpass.getpass(
        f"PostgreSQL password for {SOURCE_USER}@{SOURCE_HOST}:{SOURCE_PORT}/{SOURCE_DB}: "
    )
    print(f"\nChecking source PostgreSQL {SOURCE_HOST}:{SOURCE_PORT}/{SOURCE_DB}...")
    with psycopg2.connect(
        host=SOURCE_HOST,
        port=SOURCE_PORT,
        dbname=SOURCE_DB,
        user=SOURCE_USER,
        password=source_password,
        connect_timeout=10,
    ) as connection:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor() as cursor:
            for table in TABLES:
                cursor.execute(COUNT_QUERIES[table])
                print(f"{table}: {cursor.fetchone()[0]} rows")

            for table, status_column in (
                ("laptop_serials", "status"),
                ("laptop_warranties", "status"),
                ("laptop_products", "category"),
            ):
                cursor.execute(
                    f"""
                    SELECT COALESCE({status_column}::text, '<NULL>'), count(*)
                    FROM public.{table}
                    GROUP BY {status_column}
                    ORDER BY 1
                    """
                )
                print(f"\n{table}.{status_column} values:")
                for value, count in cursor.fetchall():
                    print(f"  {value}: {count}")

            print("\nRelationship checks (orphan rows):")
            for label, query in ORPHAN_QUERIES.items():
                cursor.execute(query)
                print(f"  {label}: {cursor.fetchone()[0]}")

            connection.rollback()

    print("\nPreview complete. No source or Odoo data was changed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, psycopg2.Error, RuntimeError, xmlrpc.client.Error) as exc:
        print(f"Preview failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
