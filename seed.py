"""Create the MySQL schema and seed products/admin without resetting existing inventory."""

from __future__ import annotations

import os
import re
import sys
import json
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DB_NAME = os.getenv("SANTHI_DB_NAME", os.getenv("DB_NAME", "santhi_cashew"))
DB_CONFIG = {
    "host": os.getenv("SANTHI_DB_HOST", os.getenv("DB_HOST", "127.0.0.1")),
    "port": int(os.getenv("SANTHI_DB_PORT", os.getenv("DB_PORT", "3306"))),
    "user": os.getenv("SANTHI_DB_USER", os.getenv("DB_USER", "root")),
    "password": os.getenv("SANTHI_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
    "charset": "utf8mb4",
    "use_unicode": True,
}
PRODUCTS = [
    {
        "id": 1, "name": "Whole Cashew W320", "category": "Raw", "grade": "W320",
        "description": "A versatile, whole cashew with a naturally creamy bite. Carefully selected and packed fresh in Panruti.",
        "ingredients": "Whole cashew nuts.", "best_for": "Everyday snacking, cooking and baking.",
        "stock": 120, "rating": 4.8, "reviews": 128,
        "prices": {"250 g": (250, 229), "500 g": (500, 445), "1 kg": (1000, 870)},
        "image_url": "/images/cashew-bowl.png",
    },
    {
        "id": 2, "name": "Premium Jumbo W180", "category": "Raw", "grade": "W180",
        "description": "Our show-stopping jumbo whole cashews: rich, smooth and beautifully substantial.",
        "ingredients": "Whole premium cashew nuts.", "best_for": "Celebrations, gifting and a truly special snack.",
        "stock": 40, "rating": 4.9, "reviews": 86,
        "prices": {"250 g": (250, 299), "500 g": (500, 580), "1 kg": (1000, 1140)},
        "image_url": "/images/cashew-bowl.png",
    },
    {
        "id": 3, "name": "Roasted Salted", "category": "Roasted", "grade": "W240",
        "description": "Golden-roasted W240 cashews with a delicate, savoury touch of salt.",
        "ingredients": "Cashew nuts, salt.", "best_for": "A savoury snack to share (or keep all to yourself).",
        "stock": 8, "rating": 4.7, "reviews": 64,
        "prices": {"250 g": (250, 269), "500 g": (500, 520), "1 kg": (1000, 1020)},
        "image_url": "/images/cashew-bowl.png",
    },
    {
        "id": 4, "name": "Pepper Masala", "category": "Flavoured", "grade": "W320",
        "description": "Crunchy W320 cashews coated in a lively pepper masala seasoning.",
        "ingredients": "Cashew nuts, pepper masala seasoning.", "best_for": "Tea-time snacks and spice-loving gatherings.",
        "stock": 60, "rating": 4.6, "reviews": 52,
        "prices": {"250 g": (250, 279), "500 g": (500, 540), "1 kg": (1000, 1060)},
        "image_url": "/images/cashew-bowl.png",
    },
    {
        "id": 5, "name": "Cashew Pieces", "category": "Raw", "grade": "Broken",
        "description": "Tasty, carefully sorted cashew pieces: the clever pantry staple for your favourite recipes.",
        "ingredients": "Cashew nut pieces.", "best_for": "Sweets, curries, baking and everyday cooking.",
        "stock": 200, "rating": 4.7, "reviews": 73,
        "prices": {"250 g": (250, 179), "500 g": (500, 340), "1 kg": (1000, 660)},
        "image_url": "/images/cashew-bowl.png",
    },
    {
        "id": 6, "name": "Festive Gift Box", "category": "Gift", "grade": "W240",
        "description": "A considered cashew gift for sharing something special.",
        "ingredients": "Cashew nuts. Contents may vary by seasonal selection.",
        "best_for": "Festive gifting and thoughtful celebrations.",
        "stock": 0, "rating": 4.8, "reviews": 34,
        "prices": {"250 g": (250, 399), "500 g": (500, 749), "1 kg": (1000, 1399)},
        "image_url": "/images/cashew-bowl.png",
    },
]
NUTRITION = {
    "energy_kcal": 553,
    "protein_g": 18,
    "fat_g": 44,
    "carbohydrates_g": 30,
    "fibre_g": 3.3,
}


def table_columns(cursor, table: str) -> dict[str, dict]:
    cursor.execute(
        """SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
        (DB_NAME, table),
    )
    return {
        name: {"type": column_type, "nullable": nullable == "YES"}
        for name, column_type, nullable in cursor.fetchall()
    }


def add_columns(cursor, table: str, columns: dict[str, str]) -> None:
    existing = table_columns(cursor, table)
    for name, definition in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {definition}")


def migrate_existing_tables(connection) -> None:
    cursor = connection.cursor()
    add_columns(cursor, "users", {"role": "VARCHAR(20) NOT NULL DEFAULT 'customer'"})
    user_columns = table_columns(cursor, "users")
    if "mobile" in user_columns and not user_columns["mobile"]["nullable"]:
        cursor.execute("ALTER TABLE users MODIFY mobile CHAR(10) NULL")

    add_columns(cursor, "products", {
        "category": "VARCHAR(40) NOT NULL DEFAULT ''",
        "grade": "VARCHAR(20) NOT NULL DEFAULT ''",
        "description": "TEXT NULL",
        "ingredients": "VARCHAR(500) NOT NULL DEFAULT ''",
        "best_for": "VARCHAR(500) NOT NULL DEFAULT ''",
        "nutrition_json": "JSON NULL",
        "shelf_life": "VARCHAR(120) NOT NULL DEFAULT '6 months from packing'",
        "storage_instructions": "VARCHAR(255) NOT NULL DEFAULT 'Airtight container, cool and dry place'",
        "packaging": "VARCHAR(120) NOT NULL DEFAULT 'Vacuum-sealed pouch'",
        "allergen": "VARCHAR(120) NOT NULL DEFAULT 'Contains tree nuts'",
        "origin": "VARCHAR(160) NOT NULL DEFAULT 'Panruti, Tamil Nadu'",
        "image_url": "VARCHAR(500) NOT NULL DEFAULT '/images/cashew-bowl.png'",
        "rating": "DECIMAL(2,1) NOT NULL DEFAULT 4.8",
        "review_count": "INT UNSIGNED NOT NULL DEFAULT 0",
        "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
        "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    })
    add_columns(cursor, "orders", {
        "placed_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "payment_method": "VARCHAR(16) NOT NULL DEFAULT 'COD'",
        "payment_status": "VARCHAR(40) NOT NULL DEFAULT 'Pay on delivery'",
        "status": "VARCHAR(32) NOT NULL DEFAULT 'Placed'",
        "cancelled": "BOOLEAN NOT NULL DEFAULT FALSE",
        "address": "JSON NULL",
        "subtotal": "INT UNSIGNED NOT NULL DEFAULT 0",
        "delivery": "INT UNSIGNED NOT NULL DEFAULT 0",
        "total": "INT UNSIGNED NOT NULL DEFAULT 0",
        "razorpay_order_id": "VARCHAR(64) NULL",
        "razorpay_payment_id": "VARCHAR(64) NULL",
        "refund_status": "VARCHAR(40) NULL",
    })
    order_columns = table_columns(cursor, "orders")
    if order_columns["payment_method"]["type"].lower().startswith("enum("):
        cursor.execute("ALTER TABLE orders MODIFY payment_method VARCHAR(16) NOT NULL")
    if not order_columns["status"]["type"].lower().startswith("varchar"):
        cursor.execute("ALTER TABLE orders MODIFY status VARCHAR(32) NOT NULL DEFAULT 'Placed'")
        cursor.execute(
            """UPDATE orders SET status = CASE status
               WHEN '0' THEN 'Placed' WHEN '1' THEN 'Packed' WHEN '2' THEN 'Shipped'
               WHEN '3' THEN 'Out for delivery' WHEN '4' THEN 'Delivered'
               WHEN '5' THEN 'Cancelled' ELSE 'Placed' END"""
        )
        cursor.execute("UPDATE orders SET cancelled = TRUE WHERE status = 'Cancelled'")
    cursor.execute("UPDATE orders SET payment_method = 'CARD' WHERE UPPER(payment_method) = 'CARD'")
    cursor.execute(
        """UPDATE orders SET payment_status = 'Refund pending'
           WHERE cancelled = TRUE AND payment_status = 'Paid (demo)' AND refund_status IS NULL"""
    )
    cursor.execute(
        """UPDATE orders SET refund_status = 'Refund pending'
           WHERE cancelled = TRUE AND payment_status = 'Refund pending' AND refund_status IS NULL"""
    )
    cursor.execute(
        """UPDATE orders SET status = 'Cancelled', cancelled = TRUE
           WHERE status = '5'"""
    )
    cursor.execute(
        """INSERT INTO order_history (order_number, status, note)
           SELECT o.order_number, o.status, 'Imported from existing order data.'
           FROM orders o LEFT JOIN order_history h ON h.order_number = o.order_number
           WHERE h.id IS NULL"""
    )

    item_columns = table_columns(cursor, "order_items")
    if "pack_size" in item_columns and "varchar(12)" not in item_columns["pack_size"]["type"].lower():
        cursor.execute("ALTER TABLE order_items MODIFY pack_size VARCHAR(12) NOT NULL")
    connection.commit()
    cursor.close()


def ensure_database() -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]+", DB_NAME):
        raise RuntimeError("DB_NAME may contain only letters, numbers, and underscores.")
    connection = mysql.connector.connect(**DB_CONFIG)
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE `{DB_NAME}`")
        statements = (ROOT / "schema.sql").read_text(encoding="utf-8").split(";")
        for statement in statements:
            if statement.strip():
                cursor.execute(statement)
        connection.commit()
        cursor.close()
        migrate_existing_tables(connection)
    finally:
        connection.close()


def seed_products(connection) -> None:
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] != 0:
        cursor.close()
        return
    for product in PRODUCTS:
        cursor.execute(
            """INSERT INTO products
               (id, name, category, grade, description, ingredients, best_for, nutrition_json,
                shelf_life, storage_instructions, packaging, allergen, origin, image_url,
                rating, review_count, stock, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
               ON DUPLICATE KEY UPDATE
                 name = VALUES(name), category = VALUES(category), grade = VALUES(grade),
                 description = VALUES(description), ingredients = VALUES(ingredients),
                 best_for = VALUES(best_for), nutrition_json = VALUES(nutrition_json),
                 shelf_life = VALUES(shelf_life), storage_instructions = VALUES(storage_instructions),
                 packaging = VALUES(packaging), allergen = VALUES(allergen),
                 origin = VALUES(origin), image_url = VALUES(image_url),
                 rating = VALUES(rating), review_count = VALUES(review_count), is_active = TRUE""",
            (
                product["id"], product["name"], product["category"], product["grade"],
                product["description"], product["ingredients"], product["best_for"],
                json.dumps(NUTRITION), "6 months from packing",
                "Airtight container, cool and dry place", "Vacuum-sealed pouch",
                "Contains tree nuts", "Panruti, Tamil Nadu", product["image_url"],
                product["rating"], product["reviews"], product["stock"],
            ),
        )
        for size, (weight, price) in product["prices"].items():
            cursor.execute(
                """INSERT INTO product_sizes (product_id, size, weight_grams, price)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE weight_grams = VALUES(weight_grams), price = VALUES(price)""",
                (product["id"], size, weight, price),
            )
    connection.commit()
    cursor.close()


def seed_admin(connection) -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    if len(password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise RuntimeError("ADMIN_EMAIL must be a valid email address.")

    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, role FROM users WHERE email = %s", (email,))
    existing = cursor.fetchone()
    if existing:
        if existing["role"] != "admin":
            raise RuntimeError(
                "ADMIN_EMAIL already belongs to a customer account; choose a different unused admin email."
            )
        cursor.close()
        return
    cursor.execute(
        """INSERT INTO users
           (full_name, mobile, email, password_hash, address, city, pincode, state, role)
           VALUES (%s, NULL, %s, %s, '', '', '', '', 'admin')""",
        ("Santhi Cashew Admin", email, generate_password_hash(password)),
    )
    connection.commit()
    cursor.close()


def seed() -> None:
    ensure_database()
    connection = mysql.connector.connect(database=DB_NAME, **DB_CONFIG)
    try:
        seed_products(connection)
        seed_admin(connection)
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        seed()
        print(f"MySQL schema and catalog are ready in '{DB_NAME}'. Existing stock, users, and orders were preserved.")
    except mysql.connector.Error as error:
        print(f"MySQL setup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    except RuntimeError as error:
        print(f"Setup configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
