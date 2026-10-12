"""Flask and MySQL API for the Santhi Cashew storefront."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from pathlib import Path

import jwt
import mysql.connector
import requests
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory
from flask_cors import CORS
from mysql.connector import Error as MySQLError
from mysql.connector.pooling import MySQLConnectionPool
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000
app.config["JSON_SORT_KEYS"] = False
app.config["JWT_SECRET"] = os.getenv("JWT_SECRET", "")
app.config["CLIENT_ORIGIN"] = os.getenv("CLIENT_ORIGIN", "http://127.0.0.1:5000")
app.config["RAZORPAY_KEY_ID"] = os.getenv("RAZORPAY_KEY_ID", "")
app.config["RAZORPAY_KEY_SECRET"] = os.getenv("RAZORPAY_KEY_SECRET", "")
app.config["ADMIN_EMAIL"] = os.getenv("ADMIN_EMAIL", "").strip().lower()

if len(app.config["JWT_SECRET"]) < 32:
    raise RuntimeError("JWT_SECRET must be set in .env and contain at least 32 characters.")

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": list({
                app.config["CLIENT_ORIGIN"],
                "http://127.0.0.1:5500",
                "http://localhost:5500",
            })
        }
    },
    allow_headers=["Authorization", "Content-Type"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
logging.getLogger("werkzeug").setLevel(logging.INFO)

DB_CONFIG = {
    "host": os.getenv("SANTHI_DB_HOST", os.getenv("DB_HOST", "127.0.0.1")),
    "port": int(os.getenv("SANTHI_DB_PORT", os.getenv("DB_PORT", "3306"))),
    "user": os.getenv("SANTHI_DB_USER", os.getenv("DB_USER", "root")),
    "password": os.getenv("SANTHI_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
    "database": os.getenv("SANTHI_DB_NAME", os.getenv("DB_NAME", "santhi_cashew")),
    "charset": "utf8mb4",
    "use_unicode": True,
    "autocommit": False,
}
connection_pool = MySQLConnectionPool(
    pool_name="santhi_cashew_pool",
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    pool_reset_session=True,
    **DB_CONFIG,
)

STATES = {
    "Andhra Pradesh", "Karnataka", "Kerala", "Maharashtra",
    "Puducherry", "Tamil Nadu", "Telangana", "Other",
}
ORDER_STAGES = ("Placed", "Packed", "Shipped", "Out for delivery", "Delivered")
PRODUCT_SELECT = """SELECT id, name, category, grade, description, ingredients, best_for,
    nutrition_json, shelf_life, storage_instructions, packaging, allergen, origin, image_url,
    rating, review_count, stock, is_active FROM products"""


class APIError(Exception):
    def __init__(self, status: int, message: str, errors: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.errors = errors or {}


def database():
    connection = getattr(g, "db_connection", None)
    if connection is None or not connection.is_connected():
        connection = connection_pool.get_connection()
        g.db_connection = connection
    return connection


@app.teardown_appcontext
def release_database(_error):
    connection = g.pop("db_connection", None)
    if connection is not None and connection.is_connected():
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def api_error(message: str, status: int, errors: dict | None = None):
    return jsonify({"message": message, "errors": errors or {}}), status


@app.errorhandler(APIError)
def handle_api_error(error: APIError):
    return api_error(error.message, error.status, error.errors)


@app.errorhandler(404)
def handle_not_found(_error):
    if request.path.startswith("/api/"):
        return api_error("API endpoint not found.", 404)
    return api_error("Page not found.", 404)


@app.errorhandler(405)
def handle_method_not_allowed(_error):
    return api_error("Method not allowed.", 405)


@app.errorhandler(413)
def handle_payload_too_large(_error):
    return api_error("Request is too large.", 413)


@app.errorhandler(500)
def handle_internal_error(error):
    app.logger.error("Unhandled API error: %s", error)
    return api_error("An unexpected server error occurred.", 500)


def get_json_object() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise APIError(400, "Request body must be a JSON object.")
    return payload


def issue_token(user: dict, remember: bool = False) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=30 if remember else 7)
    return jwt.encode(
        {
            "sub": str(user["id"]),
            "role": user["role"],
            "iat": now,
            "exp": expires,
        },
        app.config["JWT_SECRET"],
        algorithm="HS256",
    )


def password_matches(password: str, encoded: str) -> bool:
    if encoded.startswith(("pbkdf2:", "scrypt:")):
        try:
            return check_password_hash(encoded, password)
        except (TypeError, ValueError):
            return False
    try:
        rounds_text, salt_hex, digest_hex = encoded.split("$", 2)
        rounds = int(rounds_text)
        if rounds < 1 or rounds > 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), rounds
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def current_user() -> dict:
    if hasattr(g, "current_user"):
        return g.current_user
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise APIError(401, "Authentication is required.")
    try:
        claims = jwt.decode(token, app.config["JWT_SECRET"], algorithms=["HS256"])
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise APIError(401, "Your session is invalid or has expired.") from None
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT id, full_name, mobile, email, address, city, pincode, state, role
               FROM users WHERE id = %s""",
            (user_id,),
        )
        user = cursor.fetchone()
        database().commit()
    finally:
        cursor.close()
    if user is None:
        raise APIError(401, "Your account could not be found.")
    g.current_user = user
    return user


def login_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        current_user()
        return function(*args, **kwargs)
    return wrapped


def admin_required(function):
    @wraps(function)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user()["role"] != "admin":
            raise APIError(403, "Administrator access is required.")
        return function(*args, **kwargs)
    return wrapped


def validate_registration(payload: dict) -> tuple[dict, dict]:
    fields = {
        "name": payload.get("name", ""),
        "mobile": payload.get("mobile", ""),
        "email": payload.get("email", ""),
        "password": payload.get("password", ""),
        "confirmPassword": payload.get("confirmPassword", ""),
        "address": payload.get("address", ""),
        "city": payload.get("city", ""),
        "pincode": payload.get("pincode", ""),
        "state": payload.get("state", ""),
    }
    errors = {}
    for key, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            errors[key] = "This field is required."
    name = fields["name"].strip() if isinstance(fields["name"], str) else ""
    mobile = fields["mobile"].strip() if isinstance(fields["mobile"], str) else ""
    email = fields["email"].strip().lower() if isinstance(fields["email"], str) else ""
    password = fields["password"] if isinstance(fields["password"], str) else ""
    confirm = fields["confirmPassword"] if isinstance(fields["confirmPassword"], str) else ""
    pincode = fields["pincode"].strip() if isinstance(fields["pincode"], str) else ""
    state = fields["state"].strip() if isinstance(fields["state"], str) else ""
    if name and len(name) < 3:
        errors["name"] = "Enter at least 3 characters."
    if mobile and not re.fullmatch(r"[6-9]\d{9}", mobile):
        errors["mobile"] = "Enter a 10-digit mobile starting with 6–9."
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        errors["email"] = "Enter a valid email address."
    if password and len(password) < 8:
        errors["password"] = "Use at least 8 characters."
    if password and len(password) > 128:
        errors["password"] = "Use no more than 128 characters."
    if password and confirm != password:
        errors["confirmPassword"] = "Passwords do not match."
    if pincode and not re.fullmatch(r"\d{6}", pincode):
        errors["pincode"] = "Enter a 6-digit pincode."
    if state and state not in STATES:
        errors["state"] = "Choose a valid state."
    for key in ("address", "city"):
        if isinstance(fields[key], str) and len(fields[key].strip()) > (500 if key == "address" else 120):
            errors[key] = "This field is too long."
    if payload.get("termsAccepted") is not True:
        errors["termsAccepted"] = "Agree to the terms to create an account."
    clean = {
        "name": name,
        "mobile": mobile,
        "email": email,
        "password": password,
        "address": fields["address"].strip() if isinstance(fields["address"], str) else "",
        "city": fields["city"].strip() if isinstance(fields["city"], str) else "",
        "pincode": pincode,
        "state": state,
    }
    return clean, errors


def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime,)):
        return value.replace(tzinfo=timezone.utc).isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def normalize_product(row: dict, sizes: list[dict]) -> dict:
    nutrition = row["nutrition_json"]
    if isinstance(nutrition, str):
        nutrition = json.loads(nutrition)
    elif isinstance(nutrition, bytes):
        nutrition = json.loads(nutrition.decode("utf-8"))
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "grade": row["grade"],
        "description": row["description"],
        "ingredients": row["ingredients"],
        "best": row["best_for"],
        "nutrition": nutrition,
        "shelfLife": row["shelf_life"],
        "storage": row["storage_instructions"],
        "packaging": row["packaging"],
        "allergen": row["allergen"],
        "origin": row["origin"],
        "image": row["image_url"],
        "rating": json_value(row["rating"]),
        "reviews": row["review_count"],
        "stock": row["stock"],
        "active": bool(row["is_active"]),
        "prices": {size["size"]: size["price"] for size in sizes},
    }


def product_sizes(cursor, product_ids: list[int]) -> dict[int, list[dict]]:
    if not product_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(product_ids))
    cursor.execute(
        f"""SELECT product_id, size, weight_grams, price FROM product_sizes
            WHERE product_id IN ({placeholders}) ORDER BY weight_grams""",
        tuple(product_ids),
    )
    grouped = {product_id: [] for product_id in product_ids}
    for row in cursor.fetchall():
        grouped[row["product_id"]].append(row)
    return grouped


def product_response(cursor, rows: list[dict]) -> list[dict]:
    grouped = product_sizes(cursor, [row["id"] for row in rows])
    return [normalize_product(row, grouped[row["id"]]) for row in rows]


def read_order_items(cursor, order_number: str) -> list[dict]:
    cursor.execute(
        """SELECT oi.product_id AS id, p.name, oi.pack_size AS size, oi.quantity AS qty,
                  oi.unit_price AS unitPrice
           FROM order_items oi JOIN products p ON p.id = oi.product_id
           WHERE oi.order_number = %s ORDER BY oi.id""",
        (order_number,),
    )
    return cursor.fetchall()


def serialize_order(cursor, row: dict) -> dict:
    address = row["address"]
    if isinstance(address, str):
        address = json.loads(address)
    if isinstance(address, bytes):
        address = json.loads(address.decode("utf-8"))
    status_index = ORDER_STAGES.index(row["status"]) if row["status"] in ORDER_STAGES else 4
    return {
        "number": row["order_number"],
        "date": json_value(row["placed_at"]),
        "payment": row["payment_method"],
        "paymentStatus": row["payment_status"],
        "status": status_index,
        "statusLabel": row["status"],
        "cancelled": bool(row["cancelled"]),
        "refundStatus": row.get("refund_status"),
        "subtotal": row["subtotal"],
        "delivery": row["delivery"],
        "total": row["total"],
        "address": address,
        "items": read_order_items(cursor, row["order_number"]),
    }


def add_history(cursor, order_number: str, status: str, note: str, changed_by: int | None):
    cursor.execute(
        """INSERT INTO order_history (order_number, status, note, changed_by)
           VALUES (%s, %s, %s, %s)""",
        (order_number, status, note[:500], changed_by),
    )


def status_history(cursor, order_number: str) -> list[dict]:
    cursor.execute(
        """SELECT status, note, created_at FROM order_history
           WHERE order_number = %s ORDER BY created_at, id""",
        (order_number,),
    )
    return [
        {"status": row["status"], "note": row["note"], "date": json_value(row["created_at"])}
        for row in cursor.fetchall()
    ]


@app.get("/")
def storefront():
    return send_from_directory(ROOT, "index.html")


@app.get("/images/<path:filename>")
def product_image(filename):
    return send_from_directory(ROOT / "static" / "images", filename, max_age=3600)


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/auth/register")
def register():
    payload = get_json_object()
    clean, errors = validate_registration(payload)
    if errors:
        return api_error("Please correct the highlighted fields.", 400, errors)
    connection = database()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """INSERT INTO users
               (full_name, mobile, email, password_hash, address, city, pincode, state, role)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'customer')""",
            (
                clean["name"], clean["mobile"], clean["email"],
                generate_password_hash(clean["password"]),
                clean["address"], clean["city"], clean["pincode"], clean["state"],
            ),
        )
        connection.commit()
        user = {
            "id": cursor.lastrowid, "name": clean["name"], "mobile": clean["mobile"],
            "email": clean["email"], "address": clean["address"], "city": clean["city"],
            "pincode": clean["pincode"], "state": clean["state"], "role": "customer",
        }
        return jsonify({
            "message": "Account created successfully.",
            "user": {key: value for key, value in user.items() if key != "role"},
            "token": issue_token(user),
        }), 201
    except MySQLError as error:
        connection.rollback()
        if error.errno == 1062:
            field = "email" if "email" in str(error).lower() else "mobile"
            return api_error("An account already exists with those details.", 409, {field: "Already registered."})
        raise
    finally:
        cursor.close()


@app.post("/api/auth/login")
def login():
    payload = get_json_object()
    identity = payload.get("identity", payload.get("email", payload.get("mobile", "")))
    password = payload.get("password")
    errors = {}
    if not isinstance(identity, str) or not identity.strip():
        errors["identity"] = "Enter your email or mobile."
    if not isinstance(password, str) or not password:
        errors["password"] = "Enter your password."
    if errors:
        return api_error("Please correct the highlighted fields.", 400, errors)
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT id, full_name, mobile, email, password_hash, address, city, pincode,
                      state, role FROM users WHERE email = %s OR mobile = %s LIMIT 1""",
            (identity.strip().lower(), identity.strip()),
        )
        row = cursor.fetchone()
        if row is None or not password_matches(password, row["password_hash"]):
            return api_error("Email/mobile or password is incorrect.", 401, {"identity": "Check your login details."})
        if "$" in row["password_hash"] and not row["password_hash"].startswith(("pbkdf2:", "scrypt:")):
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (generate_password_hash(password), row["id"]),
            )
            database().commit()
        user = {
            "id": row["id"], "name": row["full_name"], "mobile": row["mobile"],
            "email": row["email"], "address": row["address"], "city": row["city"],
            "pincode": row["pincode"], "state": row["state"], "role": row["role"],
        }
        return jsonify({
            "message": "Login successful.",
            "user": {key: value for key, value in user.items() if key != "role"},
            "token": issue_token(user, payload.get("remember") is True),
        })
    finally:
        cursor.close()


@app.get("/api/auth/me")
@login_required
def me():
    user = current_user()
    return jsonify({
        "user": {
            "id": user["id"], "name": user["full_name"], "mobile": user["mobile"],
            "email": user["email"], "address": user["address"], "city": user["city"],
            "pincode": user["pincode"], "state": user["state"], "role": user["role"],
        }
    })


@app.get("/api/products")
def list_products():
    category = request.args.get("category", "").strip()
    grade = request.args.get("grade", "").strip()
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "featured")
    sort_sql = {
        "featured": "p.id ASC",
        "price_asc": "(SELECT MIN(ps.price) FROM product_sizes ps WHERE ps.product_id = p.id) ASC, p.id ASC",
        "price_desc": "(SELECT MIN(ps.price) FROM product_sizes ps WHERE ps.product_id = p.id) DESC, p.id ASC",
        "name_asc": "p.name ASC",
    }
    if sort not in sort_sql:
        raise APIError(400, "Unsupported sort option.", {"sort": "Choose featured, price_asc, price_desc, or name_asc."})
    conditions = ["p.is_active = TRUE"]
    values = []
    if category and category.lower() != "all":
        conditions.append("LOWER(p.category) = LOWER(%s)")
        values.append(category)
    if grade:
        conditions.append("LOWER(p.grade) = LOWER(%s)")
        values.append(grade)
    if query:
        conditions.append("(p.name LIKE %s OR p.category LIKE %s OR p.grade LIKE %s)")
        search = f"%{query[:100]}%"
        values.extend((search, search, search))
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(
            f"{PRODUCT_SELECT} p WHERE {' AND '.join(conditions)} ORDER BY {sort_sql[sort]}",
            tuple(values),
        )
        return jsonify({"products": product_response(cursor, cursor.fetchall())})
    finally:
        cursor.close()


@app.get("/api/products/<int:product_id>")
def get_product(product_id: int):
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(f"{PRODUCT_SELECT} WHERE id = %s AND is_active = TRUE", (product_id,))
        row = cursor.fetchone()
        if row is None:
            raise APIError(404, "Product not found.")
        return jsonify({"product": product_response(cursor, [row])[0]})
    finally:
        cursor.close()


def validated_order_address(payload: dict) -> dict:
    address = payload.get("address")
    if not isinstance(address, dict):
        raise APIError(400, "Delivery address is required.", {"address": "Complete the delivery form."})
    errors = {}
    for key in ("name", "mobile", "address", "city", "pincode", "state"):
        value = address.get(key)
        if not isinstance(value, str) or not value.strip():
            errors[key] = "This field is required."
    for key, limit in (("name", 160), ("address", 500), ("city", 120)):
        value = address.get(key)
        if isinstance(value, str) and len(value.strip()) > limit:
            errors[key] = "This field is too long."
    if isinstance(address.get("name"), str) and len(address["name"].strip()) < 3:
        errors["name"] = "Enter at least 3 characters."
    if isinstance(address.get("mobile"), str) and not re.fullmatch(r"[6-9]\d{9}", address["mobile"].strip()):
        errors["mobile"] = "Enter a valid 10-digit mobile number."
    if isinstance(address.get("pincode"), str) and not re.fullmatch(r"\d{6}", address["pincode"].strip()):
        errors["pincode"] = "Enter a 6-digit pincode."
    if isinstance(address.get("state"), str) and address["state"].strip() not in STATES:
        errors["state"] = "Choose a valid state."
    if errors:
        raise APIError(400, "Please correct the delivery details.", errors)
    return {key: address[key].strip() for key in ("name", "mobile", "address", "city", "pincode", "state")}


def razorpay_enabled() -> bool:
    return bool(app.config["RAZORPAY_KEY_ID"] and app.config["RAZORPAY_KEY_SECRET"])


def create_razorpay_order(order_number: str, amount_rupees: int) -> dict:
    if not razorpay_enabled():
        raise APIError(503, "Online payments are not configured. Choose cash on delivery.")
    try:
        response = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]),
            json={"amount": amount_rupees * 100, "currency": "INR", "receipt": order_number},
            timeout=(5, 20),
        )
        if response.status_code not in (200, 201):
            app.logger.error("Razorpay order creation failed with HTTP %s.", response.status_code)
            raise APIError(502, "The payment provider could not start checkout.")
        result = response.json()
        if not isinstance(result, dict) or not result.get("id"):
            raise APIError(502, "The payment provider returned an invalid checkout response.")
        return result
    except requests.RequestException:
        raise APIError(502, "The payment provider could not be reached. Please try again.") from None
    except ValueError:
        raise APIError(502, "The payment provider returned an invalid response.") from None


@app.post("/api/orders")
@login_required
def create_order():
    payload = get_json_object()
    user = current_user()
    payment_method = payload.get("payment")
    if not isinstance(payment_method, str) or payment_method.upper() not in {"COD", "UPI", "CARD"}:
        raise APIError(400, "Choose COD, UPI, or CARD.", {"payment": "Unsupported payment method."})
    payment_method = payment_method.upper()
    if payment_method == "UPI" and not re.fullmatch(r"[\w.-]+@[\w.-]+", str(payload.get("upiId", ""))):
        raise APIError(400, "Enter a valid UPI ID.", {"upiId": "Use the name@bank format."})
    address = validated_order_address(payload)
    items = payload.get("items")
    if not isinstance(items, list) or not items or len(items) > 30:
        raise APIError(400, "Your cart is empty or has too many items.", {"items": "Check your cart."})

    quantities = {}
    allowed_sizes = {"250 g", "500 g", "1 kg"}
    for item in items:
        if not isinstance(item, dict):
            raise APIError(400, "Cart item is invalid.", {"items": "Check your cart."})
        product_id, size, quantity = item.get("id"), item.get("size"), item.get("qty")
        if (not isinstance(product_id, int) or isinstance(product_id, bool)
                or size not in allowed_sizes or not isinstance(quantity, int)
                or isinstance(quantity, bool) or quantity < 1 or quantity > 200):
            raise APIError(400, "Cart item is invalid.", {"items": "Choose a valid product, pack size, and quantity."})
        quantities[(product_id, size)] = quantities.get((product_id, size), 0) + quantity

    connection = database()
    cursor = connection.cursor(dictionary=True)
    order_number = f"SC{uuid.uuid4().hex[:16].upper()}"
    razorpay_order = None
    try:
        connection.start_transaction()
        priced_items = []
        subtotal = 0
        product_totals = {}
        for (product_id, size), quantity in quantities.items():
            cursor.execute(
                """SELECT p.name, p.stock, p.is_active, ps.price
                   FROM products p JOIN product_sizes ps ON ps.product_id = p.id
                   WHERE p.id = %s AND ps.size = %s FOR UPDATE""",
                (product_id, size),
            )
            row = cursor.fetchone()
            if row is None or not row["is_active"]:
                raise APIError(400, "A product in your cart is no longer available.", {"items": "Refresh your cart."})
            product_totals[product_id] = product_totals.get(product_id, 0) + quantity
            unit_price = int(row["price"])
            subtotal += unit_price * quantity
            priced_items.append({
                "id": product_id, "name": row["name"], "size": size,
                "qty": quantity, "unitPrice": unit_price,
            })
        for product_id, quantity in product_totals.items():
            cursor.execute(
                """UPDATE products SET stock = stock - %s
                   WHERE id = %s AND is_active = TRUE AND stock >= %s""",
                (quantity, product_id, quantity),
            )
            if cursor.rowcount != 1:
                raise APIError(409, "A cart item no longer has enough stock. Refresh and try again.")

        delivery = 0 if subtotal >= 999 else 60
        total = subtotal + delivery
        if payment_method in {"UPI", "CARD"}:
            razorpay_order = create_razorpay_order(order_number, total)
        payment_status = "Pay on delivery" if payment_method == "COD" else "Payment pending"
        cursor.execute(
            """INSERT INTO orders
               (order_number, user_id, payment_method, payment_status, status, address,
                subtotal, delivery, total, razorpay_order_id)
               VALUES (%s, %s, %s, %s, 'Placed', %s, %s, %s, %s, %s)""",
            (
                order_number, user["id"], payment_method, payment_status,
                json.dumps(address), subtotal, delivery, total,
                razorpay_order["id"] if razorpay_order else None,
            ),
        )
        for item in priced_items:
            cursor.execute(
                """INSERT INTO order_items
                   (order_number, product_id, pack_size, quantity, unit_price)
                   VALUES (%s, %s, %s, %s, %s)""",
                (order_number, item["id"], item["size"], item["qty"], item["unitPrice"]),
            )
        add_history(cursor, order_number, "Placed", "Order placed.", user["id"])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    result = {"message": "Order placed.", "number": order_number, "paymentStatus": payment_status}
    if razorpay_order:
        result["razorpay"] = {
            "key": app.config["RAZORPAY_KEY_ID"],
            "orderId": razorpay_order["id"],
            "amount": razorpay_order["amount"],
            "currency": razorpay_order.get("currency", "INR"),
            "name": "Santhi Cashew",
            "description": f"Order {order_number}",
            "prefill": {"name": address["name"], "email": user["email"], "contact": address["mobile"]},
            "notes": {"order_number": order_number},
        }
    return jsonify(result), 201


@app.get("/api/orders")
@login_required
def list_orders():
    user = current_user()
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT order_number, placed_at, payment_method, payment_status, status, cancelled,
                      refund_status, address, subtotal, delivery, total
               FROM orders WHERE user_id = %s ORDER BY placed_at DESC""",
            (user["id"],),
        )
        orders = [serialize_order(cursor, row) for row in cursor.fetchall()]
        return jsonify({"orders": orders})
    finally:
        cursor.close()


@app.get("/api/orders/<order_number>")
@login_required
def get_order(order_number: str):
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT order_number, placed_at, payment_method, payment_status, status, cancelled,
                      refund_status, address, subtotal, delivery, total
               FROM orders WHERE order_number = %s AND user_id = %s""",
            (order_number, current_user()["id"]),
        )
        row = cursor.fetchone()
        if row is None:
            raise APIError(404, "Order not found.")
        result = serialize_order(cursor, row)
        result["history"] = status_history(cursor, order_number)
        return jsonify({"order": result})
    finally:
        cursor.close()


@app.patch("/api/orders/<order_number>/cancel")
@login_required
def cancel_order(order_number: str):
    user = current_user()
    connection = database()
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        cursor.execute(
            """SELECT payment_method, payment_status, status, cancelled FROM orders
               WHERE order_number = %s AND user_id = %s FOR UPDATE""",
            (order_number, user["id"]),
        )
        order = cursor.fetchone()
        if order is None:
            raise APIError(404, "Order not found.")
        if order["cancelled"] or order["status"] == "Cancelled":
            raise APIError(409, "This order has already been cancelled.")
        if order["status"] not in ("Placed", "Packed"):
            raise APIError(409, "Orders can only be cancelled while Placed or Packed.")
        cursor.execute(
            "SELECT product_id, quantity FROM order_items WHERE order_number = %s",
            (order_number,),
        )
        for item in cursor.fetchall():
            cursor.execute(
                "UPDATE products SET stock = stock + %s WHERE id = %s",
                (item["quantity"], item["product_id"]),
            )
        paid = order["payment_status"] in {"Paid", "Paid (demo)", "Paid (cash)"}
        new_payment_status = "Refund pending" if paid else order["payment_status"]
        cursor.execute(
            """UPDATE orders SET status = 'Cancelled', cancelled = TRUE,
               payment_status = %s, refund_status = %s WHERE order_number = %s""",
            (new_payment_status, "Refund pending" if paid else None, order_number),
        )
        add_history(
            cursor, order_number, "Cancelled",
            "Customer cancelled the order." + (" Refund pending." if paid else ""),
            user["id"],
        )
        connection.commit()
        return jsonify({
            "message": "Order cancelled successfully.",
            "paymentStatus": new_payment_status,
            "refundStatus": "Refund pending" if paid else None,
        })
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


@app.post("/api/payments/verify")
@login_required
def verify_payment():
    payload = get_json_object()
    razorpay_order_id = payload.get("razorpay_order_id")
    razorpay_payment_id = payload.get("razorpay_payment_id")
    signature = payload.get("razorpay_signature")
    if not all(isinstance(value, str) and value for value in
               (razorpay_order_id, razorpay_payment_id, signature)):
        raise APIError(400, "Payment verification details are incomplete.")
    secret = app.config["RAZORPAY_KEY_SECRET"]
    if not secret:
        raise APIError(503, "Online payment verification is not configured.")
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise APIError(400, "Payment signature verification failed.")
    user = current_user()
    connection = database()
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        cursor.execute(
            """SELECT order_number, status, payment_status FROM orders
               WHERE razorpay_order_id = %s AND user_id = %s FOR UPDATE""",
            (razorpay_order_id, user["id"]),
        )
        order = cursor.fetchone()
        if order is None:
            raise APIError(404, "Payment order not found.")
        if order["payment_status"] == "Paid":
            raise APIError(409, "This order has already been paid.")
        cursor.execute(
            """UPDATE orders SET payment_status = 'Paid', razorpay_payment_id = %s
               WHERE order_number = %s""",
            (razorpay_payment_id, order["order_number"]),
        )
        add_history(cursor, order["order_number"], order["status"], "Payment verified.", user["id"])
        connection.commit()
        return jsonify({"message": "Payment verified.", "orderNumber": order["order_number"], "paymentStatus": "Paid"})
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


@app.get("/api/admin/orders")
@admin_required
def admin_orders():
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT order_number, placed_at, payment_method, payment_status, status, cancelled,
                      refund_status, address, subtotal, delivery, total
               FROM orders ORDER BY placed_at DESC"""
        )
        return jsonify({"orders": [serialize_order(cursor, row) for row in cursor.fetchall()]})
    finally:
        cursor.close()


@app.patch("/api/admin/orders/<order_number>/status")
@admin_required
def admin_update_order_status(order_number: str):
    payload = get_json_object()
    next_status = payload.get("status")
    user = current_user()
    connection = database()
    cursor = connection.cursor(dictionary=True)
    try:
        connection.start_transaction()
        cursor.execute(
            """SELECT payment_method, payment_status, status, cancelled FROM orders
               WHERE order_number = %s FOR UPDATE""",
            (order_number,),
        )
        order = cursor.fetchone()
        if order is None:
            raise APIError(404, "Order not found.")
        if order["cancelled"] or order["status"] == "Cancelled":
            raise APIError(409, "This order has already been cancelled.")
        if next_status == "Cancelled":
            if order["status"] not in ("Placed", "Packed"):
                raise APIError(409, "An order can only be cancelled before it is Shipped.")
            cursor.execute(
                "SELECT product_id, quantity FROM order_items WHERE order_number = %s",
                (order_number,),
            )
            for item in cursor.fetchall():
                cursor.execute(
                    "UPDATE products SET stock = stock + %s WHERE id = %s",
                    (item["quantity"], item["product_id"]),
                )
            paid = order["payment_status"] in {"Paid", "Paid (demo)", "Paid (cash)"}
            payment_status = "Refund pending" if paid else order["payment_status"]
            refund_status = "Refund pending" if paid else None
            cursor.execute(
                """UPDATE orders SET status = 'Cancelled', cancelled = TRUE,
                   payment_status = %s, refund_status = %s WHERE order_number = %s""",
                (payment_status, refund_status, order_number),
            )
            add_history(cursor, order_number, "Cancelled", "Administrator cancelled the order.", user["id"])
        else:
            if order["status"] not in ORDER_STAGES[:-1]:
                raise APIError(409, "This order cannot move to another stage.")
            current_index = ORDER_STAGES.index(order["status"])
            if current_index + 1 >= len(ORDER_STAGES) or next_status != ORDER_STAGES[current_index + 1]:
                raise APIError(400, "Order status must advance exactly one stage.")
            payment_status = "Paid (cash)" if next_status == "Delivered" and order["payment_method"] == "COD" else order["payment_status"]
            cursor.execute(
                "UPDATE orders SET status = %s, payment_status = %s WHERE order_number = %s",
                (next_status, payment_status, order_number),
            )
            add_history(cursor, order_number, next_status, "Order status updated by administrator.", user["id"])
        connection.commit()
        return jsonify({"message": "Order status updated.", "status": next_status})
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def validate_product_payload(payload: dict, creating: bool) -> dict:
    errors = {}
    for key in ("name", "category", "grade", "description", "ingredients", "bestFor"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors[key] = "This field is required."
    stock = payload.get("stock", 0)
    if not isinstance(stock, int) or isinstance(stock, bool) or stock < 0:
        errors["stock"] = "Stock must be a non-negative whole number."
    prices = payload.get("prices")
    if not isinstance(prices, dict) or set(prices) != {"250 g", "500 g", "1 kg"}:
        errors["prices"] = "Provide prices for 250 g, 500 g, and 1 kg."
    elif any(not isinstance(price, int) or isinstance(price, bool) or price <= 0 for price in prices.values()):
        errors["prices"] = "Prices must be positive whole rupee values."
    if errors:
        raise APIError(400, "Please correct the product details.", errors)
    return {
        "name": payload["name"].strip(),
        "category": payload["category"].strip(),
        "grade": payload["grade"].strip(),
        "description": payload["description"].strip(),
        "ingredients": payload["ingredients"].strip(),
        "best_for": payload["bestFor"].strip(),
        "nutrition": payload.get("nutrition") or {
            "energy_kcal": 553, "protein_g": 18, "fat_g": 44, "carbohydrates_g": 30, "fibre_g": 3.3,
        },
        "shelf_life": payload.get("shelfLife", "6 months from packing"),
        "storage_instructions": payload.get("storage", "Airtight container, cool and dry place"),
        "packaging": payload.get("packaging", "Vacuum-sealed pouch"),
        "allergen": payload.get("allergen", "Contains tree nuts"),
        "origin": payload.get("origin", "Panruti, Tamil Nadu"),
        "image_url": payload.get("image", "/images/cashew-bowl.png"),
        "rating": payload.get("rating", 4.8),
        "review_count": payload.get("reviews", 0),
        "stock": stock,
        "prices": prices,
        "active": payload.get("active", True),
    }


def save_product(product: dict, product_id: int | None = None) -> int:
    columns = (
        "name", "category", "grade", "description", "ingredients", "best_for",
        "nutrition_json", "shelf_life", "storage_instructions", "packaging", "allergen",
        "origin", "image_url", "rating", "review_count", "stock", "is_active",
    )
    values = (
        product["name"], product["category"], product["grade"], product["description"],
        product["ingredients"], product["best_for"], json.dumps(product["nutrition"]),
        product["shelf_life"], product["storage_instructions"], product["packaging"],
        product["allergen"], product["origin"], product["image_url"], product["rating"],
        product["review_count"], product["stock"], bool(product["active"]),
    )
    connection = database()
    cursor = connection.cursor()
    try:
        if product_id is None:
            placeholders = ", ".join(["%s"] * len(columns))
            cursor.execute("SELECT id FROM products ORDER BY id DESC LIMIT 1 FOR UPDATE")
            last_product = cursor.fetchone()
            product_id = (last_product[0] if last_product else 0) + 1
            cursor.execute(
                f"INSERT INTO products (id, {', '.join(columns)}) VALUES (%s, {placeholders})",
                (product_id, *values),
            )
        else:
            cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
            if cursor.fetchone() is None:
                raise APIError(404, "Product not found.")
            updates = ", ".join(f"{column} = %s" for column in columns)
            cursor.execute(f"UPDATE products SET {updates} WHERE id = %s", (*values, product_id))
        for size, weight in (("250 g", 250), ("500 g", 500), ("1 kg", 1000)):
            cursor.execute(
                """INSERT INTO product_sizes (product_id, size, weight_grams, price)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE weight_grams = VALUES(weight_grams), price = VALUES(price)""",
                (product_id, size, weight, product["prices"][size]),
            )
        connection.commit()
        return product_id
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


@app.get("/api/admin/products")
@admin_required
def admin_products():
    cursor = database().cursor(dictionary=True)
    try:
        cursor.execute(f"{PRODUCT_SELECT} ORDER BY id")
        return jsonify({"products": product_response(cursor, cursor.fetchall())})
    finally:
        cursor.close()


@app.post("/api/admin/products")
@admin_required
def admin_create_product():
    product = validate_product_payload(get_json_object(), creating=True)
    product_id = save_product(product)
    return jsonify({"message": "Product created.", "id": product_id}), 201


@app.put("/api/admin/products/<int:product_id>")
@admin_required
def admin_replace_product(product_id: int):
    product = validate_product_payload(get_json_object(), creating=False)
    save_product(product, product_id)
    return jsonify({"message": "Product updated.", "id": product_id})


@app.delete("/api/admin/products/<int:product_id>")
@admin_required
def admin_hide_product(product_id: int):
    cursor = database().cursor()
    try:
        cursor.execute("SELECT id FROM products WHERE id = %s", (product_id,))
        if cursor.fetchone() is None:
            raise APIError(404, "Product not found.")
        cursor.execute("UPDATE products SET is_active = FALSE WHERE id = %s", (product_id,))
        database().commit()
        return jsonify({"message": "Product hidden."})
    except Exception:
        database().rollback()
        raise
    finally:
        cursor.close()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=False,
    )
