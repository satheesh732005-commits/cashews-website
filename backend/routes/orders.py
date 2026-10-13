"""Order creation, history, tracking, and cancellation endpoints."""

import secrets
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from mysql.connector import IntegrityError

from db import cursor
from utils.validators import (
    PACK_PRICES,
    UPI_PATTERN,
    ValidationError,
    required_text,
    validate_items,
    validate_mobile,
    validate_pincode,
    validate_state,
)


orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")
PAYMENT_METHODS = {"COD", "UPI", "CARD", "Card"}
ORDER_STAGES = ["Placed", "Packed", "Shipped", "Out for delivery", "Delivered"]


def json_body():
    body = request.get_json(silent=False)
    if not isinstance(body, dict):
        raise ValidationError("A JSON object is required.")
    return body


def shipping_details(data):
    source = data.get("shipping") or data.get("customer") or data
    if not isinstance(source, dict):
        raise ValidationError("Shipping details must be an object.")
    return {
        "name": required_text(source, "name", "Shipping name", minimum=3, maximum=120),
        "mobile": validate_mobile(source.get("mobile")),
        "address": required_text(source, "address", "Address", minimum=5, maximum=255),
        "city": required_text(source, "city", "City", minimum=2, maximum=120),
        "pincode": validate_pincode(source.get("pincode")),
        "state": validate_state(source.get("state")),
    }


def order_payload(order, items, history):
    return {
        "id": order["id"],
        "order_code": order["order_code"],
        "user_id": order["user_id"],
        "subtotal": float(order["subtotal"]),
        "delivery_fee": float(order["delivery_fee"]),
        "total": float(order["total"]),
        "payment_method": order["payment_method"],
        "payment_status": order["payment_status"],
        "status": order["status"],
        "shipping": {
            "name": order["ship_name"],
            "mobile": order["ship_mobile"],
            "address": order["ship_address"],
            "city": order["ship_city"],
            "pincode": order["ship_pincode"],
            "state": order["ship_state"],
        },
        "created_at": order["created_at"].isoformat() if order["created_at"] else None,
        "items": items,
        "status_history": [
            {"status": row["status"], "changed_at": row["changed_at"].isoformat()}
            for row in history
        ],
    }


def load_order(db_cursor, order_code, user_id=None, lock=False):
    sql = "SELECT * FROM orders WHERE order_code = %s"
    params = [order_code]
    if user_id is not None:
        sql += " AND user_id = %s"
        params.append(user_id)
    if lock:
        sql += " FOR UPDATE"
    db_cursor.execute(sql, tuple(params))
    return db_cursor.fetchone()


def load_order_details(db_cursor, order):
    db_cursor.execute(
        "SELECT oi.product_id, p.name, oi.size, oi.quantity AS qty, oi.unit_price "
        "FROM order_items oi JOIN products p ON p.id = oi.product_id "
        "WHERE oi.order_id = %s ORDER BY oi.id",
        (order["id"],),
    )
    items = [
        {**row, "unit_price": float(row["unit_price"])}
        for row in db_cursor.fetchall()
    ]
    db_cursor.execute(
        "SELECT status, changed_at FROM order_status_history "
        "WHERE order_id = %s ORDER BY id",
        (order["id"],),
    )
    return items, db_cursor.fetchall()


@orders_bp.post("")
@jwt_required()
def create_order():
    data = json_body()
    items = validate_items(data.get("items"))
    shipping = shipping_details(data.get("shipping") or data.get("customer") or data)
    payment_method = data.get("payment_method")
    if not isinstance(payment_method, str) or payment_method not in PAYMENT_METHODS:
        raise ValidationError("Payment method must be COD, UPI, or Card.")
    payment_method = "Card" if payment_method == "CARD" else payment_method
    if payment_method == "UPI":
        upi_id = data.get("upi_id")
        if not isinstance(upi_id, str) or not UPI_PATTERN.fullmatch(upi_id.strip()):
            raise ValidationError("Enter a valid UPI ID.")
    user_id = int(get_jwt_identity())

    with cursor() as (connection, db_cursor):
        connection.start_transaction()
        priced_items = []
        subtotal = Decimal("0.00")
        for item in sorted(items, key=lambda line: (line["product_id"], line["size"])):
            db_cursor.execute(
                "SELECT id, name, stock, price_250, price_500, price_1kg "
                "FROM products WHERE id = %s AND is_active = TRUE FOR UPDATE",
                (item["product_id"],),
            )
            product = db_cursor.fetchone()
            if not product:
                raise ValidationError(f"Product {item['product_id']} is unavailable.")
            if item["qty"] > product["stock"]:
                raise ValidationError(f"Only {product['stock']} of {product['name']} are in stock.")
            unit_price = product[PACK_PRICES[item["size"]]]
            subtotal += unit_price * item["qty"]
            priced_items.append({
                **item,
                "name": product["name"],
                "unit_price": unit_price,
            })
        delivery_fee = Decimal("0.00") if subtotal >= Decimal("999.00") else Decimal("60.00")
        total = subtotal + delivery_fee
        payment_status = "Pay on delivery" if payment_method == "COD" else "Paid"

        for _ in range(5):
            order_code = f"SC{secrets.randbelow(10_000_000):07d}"
            try:
                db_cursor.execute(
                    """
                    INSERT INTO orders
                      (order_code, user_id, subtotal, delivery_fee, total,
                       payment_method, payment_status, status, ship_name, ship_mobile,
                       ship_address, ship_city, ship_pincode, ship_state)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Placed', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_code, user_id, subtotal, delivery_fee, total,
                        payment_method, payment_status, shipping["name"],
                        shipping["mobile"], shipping["address"], shipping["city"],
                        shipping["pincode"], shipping["state"],
                    ),
                )
                break
            except IntegrityError as error:
                if error.errno != 1062:
                    raise
        else:
            raise RuntimeError("Unable to allocate a unique order code.")

        order_id = db_cursor.lastrowid
        db_cursor.execute(
            "INSERT INTO order_status_history (order_id, status) VALUES (%s, 'Placed')",
            (order_id,),
        )
        for item in priced_items:
            db_cursor.execute(
                "INSERT INTO order_items (order_id, product_id, size, quantity, unit_price) "
                "VALUES (%s, %s, %s, %s, %s)",
                (order_id, item["product_id"], item["size"], item["qty"], item["unit_price"]),
            )
            db_cursor.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s",
                (item["qty"], item["product_id"]),
            )
        connection.commit()
        db_cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = db_cursor.fetchone()
        order_items, history = load_order_details(db_cursor, order)
        return jsonify({"order": order_payload(order, order_items, history)}), 201


@orders_bp.get("")
@jwt_required()
def list_orders():
    user_id = int(get_jwt_identity())
    with cursor() as (_, db_cursor):
        db_cursor.execute(
            "SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        rows = db_cursor.fetchall()
        result = []
        for order in rows:
            items, history = load_order_details(db_cursor, order)
            result.append(order_payload(order, items, history))
    return jsonify(result)


@orders_bp.get("/<string:order_code>")
@jwt_required()
def get_order(order_code):
    user_id = int(get_jwt_identity())
    with cursor() as (_, db_cursor):
        order = load_order(db_cursor, order_code, user_id=user_id)
        if not order:
            return jsonify({"error": "Order not found."}), 404
        items, history = load_order_details(db_cursor, order)
    return jsonify({"order": order_payload(order, items, history)})


@orders_bp.put("/<string:order_code>/cancel")
@jwt_required()
def cancel_order(order_code):
    user_id = int(get_jwt_identity())
    with cursor() as (connection, db_cursor):
        connection.start_transaction()
        order = load_order(db_cursor, order_code, user_id=user_id, lock=True)
        if not order:
            return jsonify({"error": "Order not found."}), 404
        if order["status"] not in {"Placed", "Packed"}:
            return jsonify({"error": "Only orders that are Placed or Packed can be cancelled."}), 409
        db_cursor.execute(
            "SELECT product_id, quantity FROM order_items WHERE order_id = %s",
            (order["id"],),
        )
        for item in db_cursor.fetchall():
            db_cursor.execute(
                "UPDATE products SET stock = stock + %s WHERE id = %s",
                (item["quantity"], item["product_id"]),
            )
        payment_status = "Refund initiated" if order["payment_status"] == "Paid" else order["payment_status"]
        db_cursor.execute(
            "UPDATE orders SET status = 'Cancelled', payment_status = %s WHERE id = %s",
            (payment_status, order["id"]),
        )
        db_cursor.execute(
            "INSERT INTO order_status_history (order_id, status) VALUES (%s, 'Cancelled')",
            (order["id"],),
        )
        connection.commit()
        db_cursor.execute("SELECT * FROM orders WHERE id = %s", (order["id"],))
        updated = db_cursor.fetchone()
        items, history = load_order_details(db_cursor, updated)
    return jsonify({"order": order_payload(updated, items, history)})


@orders_bp.put("/<string:order_code>/status")
@jwt_required(optional=True)
def update_order_status(order_code):
    claims = get_jwt()
    is_admin = bool(claims.get("is_admin"))
    admin_key = request.headers.get("ADMIN_KEY", "")
    configured_admin_key = current_app.config["ADMIN_KEY"]
    key_matches = bool(configured_admin_key) and secrets.compare_digest(admin_key, configured_admin_key)
    if not is_admin and not key_matches:
        return jsonify({"error": "Administrator access is required."}), 403
    data = json_body()
    next_status = data.get("status")
    if next_status not in ORDER_STAGES:
        raise ValidationError("Status must be a valid order tracking stage.")

    with cursor() as (connection, db_cursor):
        connection.start_transaction()
        order = load_order(db_cursor, order_code, lock=True)
        if not order:
            return jsonify({"error": "Order not found."}), 404
        if order["status"] == "Cancelled":
            return jsonify({"error": "Cancelled orders cannot be advanced."}), 409
        current_index = ORDER_STAGES.index(order["status"])
        if current_index >= len(ORDER_STAGES) - 1 or ORDER_STAGES[current_index + 1] != next_status:
            return jsonify({"error": "Order status must move to the next tracking stage."}), 409
        payment_status = "Paid" if next_status == "Delivered" and order["payment_method"] == "COD" else order["payment_status"]
        db_cursor.execute(
            "UPDATE orders SET status = %s, payment_status = %s WHERE id = %s",
            (next_status, payment_status, order["id"]),
        )
        db_cursor.execute(
            "INSERT INTO order_status_history (order_id, status) VALUES (%s, %s)",
            (order["id"], next_status),
        )
        connection.commit()
        db_cursor.execute("SELECT * FROM orders WHERE id = %s", (order["id"],))
        updated = db_cursor.fetchone()
        items, history = load_order_details(db_cursor, updated)
    return jsonify({"order": order_payload(updated, items, history)})
