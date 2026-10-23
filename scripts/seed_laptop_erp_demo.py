import argparse
import getpass
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg2


SOURCE_HOST = "127.0.0.1"
SOURCE_PORT = 5432
SOURCE_DB = "laptop_erp"
SOURCE_USER = "postgres"
DEMO_PREFIX = "DEMO-ERP-20261023"

CUSTOMER_NAMES = [
    "An Nguyen",
    "Bao Tran",
    "Chi Le",
    "Dung Pham",
    "Giang Vo",
    "Hanh Bui",
    "Khanh Do",
    "Linh Ho",
    "Minh Vu",
    "Nhi Dang",
]

PRODUCT_SPECS = [
    ("Orion 14 A1", "DemoTech", "Intel Core i5", "16 GB", "512 GB SSD", "Integrated"),
    ("Orion 15 A2", "DemoTech", "Intel Core i7", "16 GB", "1 TB SSD", "Integrated"),
    ("Nova 14 B1", "DemoTech", "AMD Ryzen 5", "16 GB", "512 GB SSD", "Integrated"),
    ("Nova 16 B2", "DemoTech", "AMD Ryzen 7", "32 GB", "1 TB SSD", "RTX 4050"),
    ("Atlas 14 C1", "DemoTech", "Intel Core Ultra 5", "16 GB", "512 GB SSD", "Integrated"),
    ("Atlas 16 C2", "DemoTech", "Intel Core Ultra 7", "32 GB", "1 TB SSD", "RTX 4060"),
    ("Pixel 14 D1", "DemoTech", "Intel Core i5", "8 GB", "512 GB SSD", "Integrated"),
    ("Pixel 15 D2", "DemoTech", "AMD Ryzen 5", "16 GB", "1 TB SSD", "Integrated"),
    ("Summit 14 E1", "DemoTech", "Intel Core i7", "32 GB", "1 TB SSD", "RTX 4050"),
    ("Summit 16 E2", "DemoTech", "AMD Ryzen 9", "32 GB", "2 TB SSD", "RTX 4070"),
]

PRODUCT_PRICES = [
    18990000, 24990000, 19990000, 32990000, 22990000,
    38990000, 16990000, 21990000, 35990000, 45990000,
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Add clearly marked, linked demo rows to source laptop_erp."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Insert demo records. Without this option, only validate and preview.",
    )
    parser.add_argument(
        "--backup-file",
        type=Path,
        help="Verified custom-format pg_dump backup required with --apply.",
    )
    return parser.parse_args()


def validate_backup(path):
    if not path or not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(
            "A non-empty laptop_erp backup file is required before applying."
        )
    candidates = [
        Path(r"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe"),
        Path(r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe"),
    ]
    restore = next((item for item in candidates if item.is_file()), None)
    if restore is None:
        raise RuntimeError("pg_restore.exe not found; cannot validate the backup.")
    result = subprocess.run(
        [str(restore), "--list", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"Backup validation failed: {message}")
    print(f"Verified backup archive: {path} ({path.stat().st_size} bytes)")


def get_schema(cursor):
    cursor.execute(
        """
        SELECT table_name, column_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
        """,
        ([
            "laptop_customers",
            "laptop_products",
            "laptop_orders",
            "laptop_order_items",
            "laptop_serials",
            "laptop_warranties",
        ],),
    )
    schema = {}
    for table, column, nullable, default in cursor.fetchall():
        schema.setdefault(table, {})[column] = {
            "nullable": nullable == "YES",
            "default": default,
        }
    expected = {
        "laptop_customers": {"id", "name", "phone", "address"},
        "laptop_products": {
            "id", "name", "brand", "category", "cpu", "ram",
            "storage", "gpu", "price",
        },
        "laptop_orders": {"id", "customer_id", "total_amount", "order_date"},
        "laptop_order_items": {"id", "order_id", "serial_id", "price"},
        "laptop_serials": {"id", "product_id", "serial_number", "status"},
        "laptop_warranties": {
            "id", "serial_id", "customer_id", "issue_description",
            "status", "start_date", "end_date",
        },
    }
    for table, required in expected.items():
        missing = sorted(required - schema.get(table, {}).keys())
        if missing:
            raise RuntimeError(
                f"Unexpected source schema: {table} is missing "
                + ", ".join(missing)
            )
        if schema[table]["id"]["default"] is None:
            raise RuntimeError(
                f"{table}.id has no default sequence; refusing to guess IDs."
            )
    return schema


def ensure_no_existing_demo(cursor):
    checks = {
        "customers": (
            "SELECT count(*) FROM public.laptop_customers WHERE name LIKE %s "
            "OR phone LIKE %s"
        ),
        "products": (
            "SELECT count(*) FROM public.laptop_products WHERE name LIKE %s"
        ),
        "serials": (
            "SELECT count(*) FROM public.laptop_serials WHERE serial_number LIKE %s"
        ),
    }
    marker = f"{DEMO_PREFIX}-%"
    found = {}
    for label, query in checks.items():
        cursor.execute(query, (marker, marker) if label == "customers" else (marker,))
        found[label] = cursor.fetchone()[0]
    if any(found.values()):
        raise RuntimeError(
            "Demo rows with this marker already exist in laptop_erp: "
            + ", ".join(f"{key}={value}" for key, value in found.items())
            + ". Refusing to duplicate them."
        )


def insert_row(cursor, table, values):
    columns = list(values)
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    cursor.execute(
        f'INSERT INTO public."{table}" ({quoted_columns}) '
        f"VALUES ({placeholders}) RETURNING id",
        [values[column] for column in columns],
    )
    return cursor.fetchone()[0]


def add_demo_data(connection, schema):
    today = date.today()
    now = datetime.now().replace(microsecond=0)
    with connection.cursor() as cursor:
        ensure_no_existing_demo(cursor)
        customer_ids = []
        product_ids = []
        serial_ids = []
        order_ids = []
        warranty_ids = []

        for index, name in enumerate(CUSTOMER_NAMES, start=1):
            marker = f"{DEMO_PREFIX}-C{index:02d}"
            customer_ids.append(insert_row(cursor, "laptop_customers", {
                "name": f"{marker} {name}",
                "phone": marker,
                "address": f"{index} Demo Street, Sample District",
            }))

        for index, spec in enumerate(PRODUCT_SPECS, start=1):
            name, brand, cpu, ram, storage, gpu = spec
            marker = f"{DEMO_PREFIX}-P{index:02d}"
            product_ids.append(insert_row(cursor, "laptop_products", {
                "name": f"{marker} {name}",
                "brand": brand,
                "category": "Laptop",
                "cpu": cpu,
                "ram": ram,
                "storage": storage,
                "gpu": gpu,
                "price": PRODUCT_PRICES[index - 1],
            }))

        serial_rows = []
        for index in range(1, 21):
            product_index = (index - 1) % len(product_ids)
            status = "in_warranty" if index in {1, 4, 7, 10, 13} else (
                "sold" if index <= 15 else "in_stock"
            )
            values = {
                "product_id": product_ids[product_index],
                "serial_number": f"{DEMO_PREFIX}-SN{index:03d}",
                "status": status,
            }
            if "warehouse_location" in schema["laptop_serials"]:
                values["warehouse_location"] = (
                    f"Demo Warehouse / Rack {(index - 1) // 5 + 1}"
                    if status == "in_stock"
                    else None
                )
            serial_id = insert_row(cursor, "laptop_serials", values)
            serial_ids.append(serial_id)
            serial_rows.append({
                "id": serial_id,
                "product_id": product_ids[product_index],
                "status": status,
                "source_index": index,
            })

        warranty_serial_indexes = {1, 4, 7, 10, 13}
        for customer_index in range(10):
            item_indexes = (
                [customer_index * 2, customer_index * 2 + 1]
                if customer_index < 5
                else [customer_index + 5]
            )
            order_total = sum(
                PRODUCT_PRICES[
                    (serial_rows[item_index]["source_index"] - 1) % 10
                ]
                for item_index in item_indexes
            )
            order_date = now - timedelta(days=customer_index * 3)
            order_id = insert_row(cursor, "laptop_orders", {
                "customer_id": customer_ids[customer_index],
                "total_amount": order_total,
                "order_date": order_date,
            })
            order_ids.append(order_id)
            for item_index in item_indexes:
                serial_row = serial_rows[item_index]
                product_index = (serial_row["source_index"] - 1) % 10
                insert_row(cursor, "laptop_order_items", {
                    "order_id": order_id,
                    "serial_id": serial_row["id"],
                    "price": PRODUCT_PRICES[product_index],
                })

                if serial_row["source_index"] in warranty_serial_indexes:
                    warranty_index = serial_row["source_index"]
                    warranty_status = (
                        "repairing" if warranty_index == 1
                        else "received" if warranty_index == 4
                        else "done" if warranty_index == 7
                        else "repairing" if warranty_index == 10
                        else "received"
                    )
                    start_date = today - timedelta(days=20 + warranty_index)
                    insert_row(cursor, "laptop_warranties", {
                        "serial_id": serial_row["id"],
                        "customer_id": customer_ids[customer_index],
                        "issue_description": (
                            f"{DEMO_PREFIX}: sample warranty case "
                            f"for serial {serial_row['source_index']:03d}"
                        ),
                        "status": warranty_status,
                        "start_date": start_date,
                        "end_date": start_date + timedelta(days=365),
                    })
                    warranty_ids.append(warranty_index)

    return {
        "customers": len(customer_ids),
        "products": len(product_ids),
        "serials": len(serial_ids),
        "orders": len(order_ids),
        "order items": 15,
        "warranties": len(warranty_ids),
    }


def main():
    args = parse_args()
    if args.apply:
        validate_backup(args.backup_file)
    elif args.backup_file:
        validate_backup(args.backup_file)

    password = getpass.getpass(
        f"PostgreSQL password for {SOURCE_USER}@{SOURCE_HOST}:{SOURCE_PORT}/{SOURCE_DB}: "
    )
    connection = psycopg2.connect(
        host=SOURCE_HOST,
        port=SOURCE_PORT,
        dbname=SOURCE_DB,
        user=SOURCE_USER,
        password=password,
        connect_timeout=10,
    )
    try:
        connection.set_session(readonly=not args.apply, autocommit=False)
        with connection.cursor() as cursor:
            schema = get_schema(cursor)
            ensure_no_existing_demo(cursor)
        if args.apply:
            counts = add_demo_data(connection, schema)
        else:
            connection.rollback()
            counts = {
                "customers": 10,
                "products": 10,
                "serials": 20,
                "orders": 10,
                "order items": 15,
                "warranties": 5,
            }
        if args.apply:
            confirmation = input(
                "Type ADD DEMO DATA to commit 10 customers, 10 products, "
                "20 serials, 10 orders, 15 order lines, and 5 warranties: "
            )
            if confirmation != "ADD DEMO DATA":
                connection.rollback()
                print("Cancelled. No source records were committed.")
                return
            connection.commit()
            print("\nDemo data committed to source laptop_erp:")
        else:
            connection.rollback()
            print("\nDry run only; no source data changed. Planned rows:")
        for table, count in counts.items():
            print(f"  {table}: {count}")
        print(
            f"All demo rows are marked with {DEMO_PREFIX}; "
            "the existing rows were not updated."
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except (OSError, psycopg2.Error, RuntimeError, ValueError) as exc:
        print(f"Demo-data generation stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
