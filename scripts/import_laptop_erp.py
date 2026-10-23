import argparse
import getpass
import sys
import xmlrpc.client
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor


SOURCE_HOST = "127.0.0.1"
SOURCE_PORT = 5432
SOURCE_DB = "laptop_erp"
SOURCE_USER = "postgres"
ODOO_URL = "http://localhost:8069"
ODOO_DB = "erp_tramy"

TABLE_COLUMNS = {
    "laptop_customers": {"id", "name", "phone", "address"},
    "laptop_products": {
        "id", "name", "brand", "category", "cpu", "ram", "storage", "gpu", "price"
    },
    "laptop_orders": {"id", "customer_id", "total_amount", "order_date"},
    "laptop_order_items": {"id", "order_id", "serial_id", "price"},
    "laptop_serials": {"id", "product_id", "serial_number", "status"},
    "laptop_warranties": {
        "id", "serial_id", "customer_id", "issue_description",
        "status", "start_date", "end_date"
    },
}

SERIAL_STATUS_MAP = {
    "in_stock": "available",
    "sold": "sold",
    "in_warranty": "sold",
}
WARRANTY_STATUS_MAP = {
    "received": "new",
    "repairing": "fixing",
    "done": "done",
    "completed": "done",
}


class Odoo:
    def __init__(self, username, password):
        self.db = ODOO_DB
        self.password = password
        self.common = xmlrpc.client.ServerProxy(
            f"{ODOO_URL}/xmlrpc/2/common",
            allow_none=True,
        )
        version = self.common.version()
        self.uid = self.common.authenticate(self.db, username, password, {})
        if not self.uid:
            raise RuntimeError(
                f"Cannot authenticate to Odoo database {self.db!r} as {username!r}."
            )
        self.models = xmlrpc.client.ServerProxy(
            f"{ODOO_URL}/xmlrpc/2/object",
            allow_none=True,
        )
        self.version = version.get("server_version", "unknown")

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            model,
            method,
            args or [],
            kwargs or {},
        )

    def fields(self, model):
        return self.call(model, "fields_get", [], {
            "attributes": ["type", "required", "selection", "relation"]
        })

    def find(self, model, domain, fields=None):
        ids = self.call(model, "search", [domain], {"limit": 2})
        if len(ids) > 1:
            raise RuntimeError(f"Multiple matching records in {model}: {domain!r}")
        if not ids:
            return None
        if fields:
            return self.call(model, "read", [ids], {"fields": fields})[0]
        return {"id": ids[0]}


def source_rows(password):
    connection = psycopg2.connect(
        host=SOURCE_HOST,
        port=SOURCE_PORT,
        dbname=SOURCE_DB,
        user=SOURCE_USER,
        password=password,
        connect_timeout=10,
    )
    try:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                """,
                (list(TABLE_COLUMNS),),
            )
            columns = defaultdict(set)
            for row in cursor.fetchall():
                columns[row["table_name"]].add(row["column_name"])

            for table, required in TABLE_COLUMNS.items():
                missing = sorted(required - columns[table])
                if missing:
                    raise RuntimeError(
                        f"Source table {table!r} is missing required columns: "
                        + ", ".join(missing)
                    )

            result = {}
            for table in TABLE_COLUMNS:
                cursor.execute(f"SELECT * FROM public.{table} ORDER BY id")
                result[table] = [dict(row) for row in cursor.fetchall()]
            connection.rollback()
            return result, columns
    finally:
        connection.close()


def normalize(value):
    if isinstance(value, datetime):
        return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def source_key(kind, source_id):
    return f"LAPTOP-ERP-{kind}-{source_id}"


def validate_source(data):
    customers = {row["id"]: row for row in data["laptop_customers"]}
    products = {row["id"]: row for row in data["laptop_products"]}
    orders = {row["id"]: row for row in data["laptop_orders"]}
    serials = {row["id"]: row for row in data["laptop_serials"]}
    warranties = data["laptop_warranties"]

    if len(customers) != len(data["laptop_customers"]):
        raise RuntimeError("Duplicate customer IDs in source.")
    if len(products) != len(data["laptop_products"]):
        raise RuntimeError("Duplicate product IDs in source.")
    if len(orders) != len(data["laptop_orders"]):
        raise RuntimeError("Duplicate order IDs in source.")
    if len(serials) != len(data["laptop_serials"]):
        raise RuntimeError("Duplicate serial IDs in source.")

    for row in data["laptop_customers"]:
        if not row["name"] or not row["phone"]:
            raise RuntimeError(f"Customer {row['id']} has no required name or phone.")
    for row in data["laptop_products"]:
        if not row["name"] or row["price"] is None:
            raise RuntimeError(f"Product {row['id']} has no name or price.")
    for row in data["laptop_serials"]:
        if row["product_id"] not in products:
            raise RuntimeError(f"Serial {row['id']} references a missing product.")
        status = str(row["status"] or "").strip().lower()
        if status not in SERIAL_STATUS_MAP:
            raise RuntimeError(
                f"Unsupported serial status {row['status']!r} on source serial {row['id']}."
            )
    for row in data["laptop_orders"]:
        if row["customer_id"] not in customers:
            raise RuntimeError(
                f"Order {row['id']} has no source customer; Odoo requires a customer."
            )

    items_by_order = defaultdict(list)
    customer_by_serial = {}
    for row in data["laptop_order_items"]:
        if row["order_id"] not in orders or row["serial_id"] not in serials:
            raise RuntimeError(f"Order item {row['id']} has a broken order/serial relation.")
        items_by_order[row["order_id"]].append(row)
        customer_id = orders[row["order_id"]]["customer_id"]
        prior_customer = customer_by_serial.setdefault(row["serial_id"], customer_id)
        if prior_customer != customer_id:
            raise RuntimeError(
                f"Source serial {row['serial_id']} is linked to orders for different customers."
            )

    for warranty in warranties:
        if warranty["serial_id"] not in serials:
            raise RuntimeError(
                f"Warranty {warranty['id']} has no source serial; Odoo requires one."
            )
        if warranty["customer_id"] not in customers:
            raise RuntimeError(
                f"Warranty {warranty['id']} has no source customer."
            )
        sale_customer = customer_by_serial.get(warranty["serial_id"])
        if sale_customer and sale_customer != warranty["customer_id"]:
            raise RuntimeError(
                f"Warranty {warranty['id']} customer does not match the source sale customer."
            )
        status = str(warranty["status"] or "").strip().lower()
        if status not in WARRANTY_STATUS_MAP:
            raise RuntimeError(
                f"Unsupported warranty status {warranty['status']!r} "
                f"on source warranty {warranty['id']}."
            )

    return customers, products, orders, items_by_order, serials


def check_target(odoo, apply):
    required = {
        "res.partner": {"name", "phone", "street", "ref"},
        "product.template": {
            "name", "default_code", "list_price", "is_storable",
            "tracking", "description_sale",
        },
        "product.product": {"product_tmpl_id", "uom_id"},
        "sale.order": {"partner_id", "client_order_ref", "date_order", "order_line", "state"},
        "sale.order.line": {
            "order_id", "product_id", "product_uom", "product_uom_qty",
            "price_unit", "name", "x_serial_number_ids",
        },
        "stock.lot": {
            "name", "product_id", "ref", "x_customer_id", "x_custom_status",
            "x_sale_order_id", "x_sale_date", "source_warehouse_location",
        },
        "stock.quant": {"product_id", "location_id", "lot_id", "inventory_quantity"},
        "stock.warehouse": {"lot_stock_id", "company_id"},
        "warranty.ticket": {
            "ticket_code", "serial_id", "receive_date", "state",
            "source_issue_description", "source_status", "source_end_date",
        },
    }
    fields = {model: odoo.fields(model) for model in required}
    for model, names in required.items():
        missing = sorted(names - fields[model].keys())
        if missing:
            raise RuntimeError(
                f"Odoo model {model} lacks fields: {', '.join(missing)}. "
                "Upgrade the custom_warranty module before importing."
            )

    if "serial" not in [key for key, _label in fields["product.template"]["tracking"]["selection"]]:
        raise RuntimeError("Odoo product tracking does not support serial tracking.")
    serial_states = {
        key for key, _label in fields["stock.lot"]["x_custom_status"]["selection"]
    }
    if not set(SERIAL_STATUS_MAP.values()).issubset(serial_states):
        raise RuntimeError("Odoo serial-status selection does not support source mapping.")
    warranty_states = {
        key for key, _label in fields["warranty.ticket"]["state"]["selection"]
    }
    if not set(WARRANTY_STATUS_MAP.values()).issubset(warranty_states):
        raise RuntimeError("Odoo warranty states do not support source mapping.")

    if apply:
        user = odoo.call(
            "res.users", "read", [[odoo.uid]], {"fields": ["company_id"]}
        )[0]
        company_id = user["company_id"][0]
        warehouses = odoo.call(
            "stock.warehouse",
            "search_read",
            [[("company_id", "=", company_id)]],
            {"fields": ["lot_stock_id", "company_id"], "limit": 1},
        )
        if not warehouses or not warehouses[0]["lot_stock_id"]:
            raise RuntimeError("No stock location is configured for the Odoo company.")
        return fields, warehouses[0]["lot_stock_id"][0]
    return fields, None


def preflight_target_collisions(odoo, data):
    checks = (
        ("res.partner", "ref", "CUST", data["laptop_customers"]),
        ("product.template", "default_code", "PROD", data["laptop_products"]),
        ("stock.lot", "ref", "SERIAL", data["laptop_serials"]),
        ("sale.order", "client_order_ref", "ORDER", data["laptop_orders"]),
        ("warranty.ticket", "ticket_code", "WARRANTY", data["laptop_warranties"]),
    )
    for model, field, kind, rows in checks:
        for row in rows:
            value = source_key(kind, row["id"])
            odoo.find(model, [(field, "=", value)])

    for row in data["laptop_serials"]:
        existing = odoo.call(
            "stock.lot",
            "search_read",
            [[("name", "=", row["serial_number"])]],
            {"fields": ["ref", "product_id"], "limit": 10},
        )
        expected_ref = source_key("SERIAL", row["id"])
        if any(record["ref"] != expected_ref for record in existing):
            raise RuntimeError(
                f"Serial number {row['serial_number']!r} already exists in Odoo; "
                "review it before importing to avoid a duplicate."
            )
        if str(row["status"] or "").strip().lower() == "in_stock":
            existing_lot = odoo.find("stock.lot", [("ref", "=", expected_ref)])
            if existing_lot:
                quants = odoo.call(
                    "stock.quant",
                    "search_read",
                    [[("lot_id", "=", existing_lot["id"]),
                      ("location_id.usage", "=", "internal")]],
                    {"fields": ["quantity"], "limit": 100},
                )
                quantity = sum(float(quant["quantity"]) for quant in quants)
                if abs(quantity) > 0.000001 and abs(quantity - 1.0) > 0.000001:
                    raise RuntimeError(
                        f"Serial {row['serial_number']} already has Odoo on-hand "
                        f"quantity {quantity}; refusing to adjust existing stock."
                    )

    serial_customer_ids = {}
    order_customers = {
        order["id"]: order["customer_id"]
        for order in data["laptop_orders"]
    }
    serials_by_id = {
        serial["id"]: serial for serial in data["laptop_serials"]
    }
    for item in data["laptop_order_items"]:
        serial_customer_ids[item["serial_id"]] = order_customers[item["order_id"]]
    for warranty in data["laptop_warranties"]:
        serial_customer_ids.setdefault(
            warranty["serial_id"], warranty["customer_id"]
        )

    for serial_id, customer_id in serial_customer_ids.items():
        expected_ref = source_key("SERIAL", serial_id)
        lot = odoo.find("stock.lot", [("ref", "=", expected_ref)], ["x_customer_id"])
        if lot and lot["x_customer_id"]:
            expected_customer = odoo.find(
                "res.partner",
                [("ref", "=", source_key("CUST", customer_id))],
            )
            if not expected_customer or lot["x_customer_id"][0] != expected_customer["id"]:
                raise RuntimeError(
                    f"Existing Odoo serial {expected_ref} is linked to a different customer."
                )


def upsert(odoo, model, key_field, key, values):
    existing = odoo.find(model, [(key_field, "=", key)])
    if existing:
        odoo.call(model, "write", [[existing["id"]], values])
        return existing["id"], False
    return odoo.call(model, "create", [values]), True


def apply_import(odoo, data, warehouse_location_id):
    customers, products, orders, items_by_order, serials = validate_source(data)
    stats = defaultdict(lambda: [0, 0])
    partner_ids = {}
    template_ids = {}
    product_ids = {}
    lot_ids = {}
    order_ids = {}

    for source_id, row in customers.items():
        key = source_key("CUST", source_id)
        partner_id, created = upsert(odoo, "res.partner", "ref", key, {
            "name": row["name"],
            "phone": row["phone"],
            "street": row["address"] or False,
            "ref": key,
        })
        partner_ids[source_id] = partner_id
        stats["customers"][int(created)] += 1

    for source_id, row in products.items():
        key = source_key("PROD", source_id)
        specs = [
            ("Brand", row.get("brand")),
            ("Category", row.get("category")),
            ("CPU", row.get("cpu")),
            ("RAM", row.get("ram")),
            ("Storage", row.get("storage")),
            ("GPU", row.get("gpu")),
        ]
        description = "\n".join(
            f"{label}: {value}" for label, value in specs if value
        )
        template_id, created = upsert(odoo, "product.template", "default_code", key, {
            "name": row["name"],
            "default_code": key,
            "list_price": float(row["price"]),
            "is_storable": True,
            "tracking": "serial",
            "description_sale": description,
        })
        template_ids[source_id] = template_id
        variant = odoo.call(
            "product.template", "read", [[template_id]], {"fields": ["product_variant_id"]}
        )[0]["product_variant_id"]
        if not variant:
            raise RuntimeError(f"Odoo product {key} has no product variant.")
        product_ids[source_id] = variant[0]
        stats["products"][int(created)] += 1

    for source_id, row in serials.items():
        product = products[row["product_id"]]
        product_id = product_ids[row["product_id"]]
        source_status = str(row["status"] or "").strip().lower()
        location = row.get("warehouse_location") if "warehouse_location" in row else None
        values = {
            "name": row["serial_number"],
            "product_id": product_id,
            "ref": source_key("SERIAL", source_id),
            "x_custom_status": SERIAL_STATUS_MAP[source_status],
            "source_warehouse_location": location or False,
        }
        lot_id, created = upsert(odoo, "stock.lot", "ref", values["ref"], values)
        lot_ids[source_id] = lot_id
        stats["serials"][int(created)] += 1

    for source_id, row in orders.items():
        key = source_key("ORDER", source_id)
        values = {
            "partner_id": partner_ids[row["customer_id"]],
            "client_order_ref": key,
        }
        if row["order_date"]:
            values["date_order"] = normalize(row["order_date"])
        existing = odoo.find("sale.order", [("client_order_ref", "=", key)], ["state"])
        if existing and existing["state"] != "draft":
            raise RuntimeError(
                f"Imported order {key} is no longer a draft; refusing to overwrite it."
            )
        order_id, created = upsert(
            odoo, "sale.order", "client_order_ref", key, values
        )
        order_ids[source_id] = order_id
        stats["orders"][int(created)] += 1

        for item in items_by_order.get(source_id, []):
            lot_id = lot_ids[item["serial_id"]]
            serial = serials[item["serial_id"]]
            product_id = product_ids[serial["product_id"]]
            line_domain = [
                ("order_id", "=", order_id),
                ("x_serial_number_ids", "in", [lot_id]),
            ]
            line = odoo.find(
                "sale.order.line", line_domain, ["id", "state"]
            )
            if line:
                if line["state"] != "draft":
                    raise RuntimeError(
                        f"Order line for source item {item['id']} is not a draft."
                    )
                odoo.call("sale.order.line", "write", [[line["id"]], {
                    "price_unit": float(item["price"] or 0),
                }])
                stats["order lines"][0] += 1
            else:
                product_data = odoo.call(
                    "product.product",
                    "read",
                    [[product_id]],
                    {"fields": ["uom_id", "display_name"]},
                )[0]
                odoo.call("sale.order.line", "create", [{
                    "order_id": order_id,
                    "product_id": product_id,
                    "name": product_data["display_name"],
                    "product_uom": product_data["uom_id"][0],
                    "product_uom_qty": 1,
                    "price_unit": float(item["price"] or 0),
                    "x_serial_number_ids": [(6, 0, [lot_id])],
                }])
                stats["order lines"][1] += 1

            order_date = row.get("order_date")
            lot_values = {
                "x_customer_id": partner_ids[row["customer_id"]],
                "x_sale_order_id": order_id,
            }
            if order_date:
                lot_values["x_sale_date"] = normalize(order_date)[:10]
            odoo.call("stock.lot", "write", [[lot_id], lot_values])

    for row in data["laptop_warranties"]:
        status = str(row["status"] or "").strip().lower()
        key = source_key("WARRANTY", row["id"])
        values = {
            "ticket_code": key,
            "serial_id": lot_ids[row["serial_id"]],
            "state": WARRANTY_STATUS_MAP[status],
            "source_status": row["status"] or False,
            "source_issue_description": row["issue_description"] or False,
            "source_end_date": normalize(row["end_date"]) if row["end_date"] else False,
        }
        lot = odoo.call(
            "stock.lot",
            "read",
            [[lot_ids[row["serial_id"]]]],
            {"fields": ["x_customer_id"]},
        )[0]
        if not lot["x_customer_id"]:
            odoo.call(
                "stock.lot",
                "write",
                [[lot_ids[row["serial_id"]]], {
                    "x_customer_id": partner_ids[row["customer_id"]]
                }],
            )
        if row["start_date"]:
            values["receive_date"] = normalize(row["start_date"])
        _ticket_id, created = upsert(
            odoo, "warranty.ticket", "ticket_code", key, values
        )
        stats["warranties"][int(created)] += 1

    in_stock_lots = [
        (row, lot_ids[row["id"]], product_ids[row["product_id"]])
        for row in serials.values()
        if str(row["status"] or "").strip().lower() == "in_stock"
    ]
    for row, lot_id, product_id in in_stock_lots:
        quants = odoo.call(
            "stock.quant",
            "search_read",
            [[("lot_id", "=", lot_id), ("location_id.usage", "=", "internal")]],
            {"fields": ["quantity"], "limit": 100},
        )
        quantity = sum(float(quant["quantity"]) for quant in quants)
        if abs(quantity - 1.0) < 0.000001:
            stats["stock quantities"][0] += 1
            continue
        if abs(quantity) > 0.000001:
            raise RuntimeError(
                f"Serial {row['serial_number']} already has Odoo on-hand quantity "
                f"{quantity}; refusing to adjust existing stock."
            )
        quant_id = odoo.call("stock.quant", "create", [{
            "product_id": product_id,
            "location_id": warehouse_location_id,
            "lot_id": lot_id,
            "inventory_quantity": 1,
        }])
        odoo.call("stock.quant", "action_apply_inventory", [[quant_id]])
        stats["stock quantities"][1] += 1

    print("\nImport complete:")
    for label in (
        "customers", "products", "serials", "orders", "order lines",
        "warranties", "stock quantities",
    ):
        created, updated = stats[label][1], stats[label][0]
        print(f"  {label}: created {created}, existing/updated {updated}")
    print("  Sales orders remain quotations (draft); no delivery was marked done.")


def main():
    parser = argparse.ArgumentParser(
        description="Import laptop_erp records into Odoo through the Odoo ORM API."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the validated source data to Odoo. Without this flag, run a dry-run.",
    )
    args = parser.parse_args()

    username = input("Odoo login (same as the Odoo website): ").strip()
    if not username:
        raise RuntimeError("Odoo login is required.")
    odoo_password = getpass.getpass(f"Odoo password for {username}@{ODOO_DB}: ")
    odoo = Odoo(username, odoo_password)
    print(f"Connected to Odoo {odoo.version}, database {ODOO_DB}.")

    source_password = getpass.getpass(
        f"PostgreSQL password for {SOURCE_USER}@{SOURCE_HOST}:{SOURCE_PORT}/{SOURCE_DB}: "
    )
    data, columns = source_rows(source_password)
    validate_source(data)

    source_counts = {table: len(rows) for table, rows in data.items()}
    print("\nSource records:")
    for table, count in source_counts.items():
        print(f"  {table}: {count}")
    print("Status mapping:")
    print("  serial: in_stock -> available; sold/in_warranty -> sold")
    print("  warranty: received -> new; repairing -> fixing; done/completed -> done")
    if "warehouse_location" not in columns["laptop_serials"]:
        print("  Note: source serial warehouse location column not found; it will not be mapped.")

    check_target(odoo, args.apply)
    preflight_target_collisions(odoo, data)
    print("\nValidation passed: relationships and target models are compatible.")
    if not args.apply:
        print("Dry-run only. No source or Odoo data was changed.")
        print("Review the mapping, then run again with --apply to import.")
        return

    _fields, warehouse_location_id = check_target(odoo, True)
    apply_import(odoo, data, warehouse_location_id)


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        psycopg2.Error,
        RuntimeError,
        xmlrpc.client.Error,
        KeyError,
        ValueError,
    ) as exc:
        print(f"Import stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
