"""Server-priced cart quote endpoint."""

from decimal import Decimal

from flask import Blueprint, jsonify, request

from db import cursor
from utils.validators import PACK_PRICES, ValidationError, validate_items


cart_bp = Blueprint("cart", __name__, url_prefix="/api/cart")


@cart_bp.post("/quote")
def quote_cart():
    data = request.get_json(silent=False)
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")
    items = validate_items(data.get("items"))
    quoted_items = []
    subtotal = Decimal("0.00")
    with cursor() as (_, db_cursor):
        for item in items:
            db_cursor.execute(
                "SELECT id, name, stock, price_250, price_500, price_1kg "
                "FROM products WHERE id = %s AND is_active = TRUE",
                (item["product_id"],),
            )
            product = db_cursor.fetchone()
            if not product:
                raise ValidationError(f"Product {item['product_id']} is unavailable.")
            if item["qty"] > product["stock"]:
                raise ValidationError(f"Only {product['stock']} of {product['name']} are in stock.")
            price = product[PACK_PRICES[item["size"]]]
            line_total = price * item["qty"]
            subtotal += line_total
            quoted_items.append({
                "product_id": product["id"],
                "name": product["name"],
                "size": item["size"],
                "qty": item["qty"],
                "unit_price": float(price),
                "line_total": float(line_total),
            })
    delivery_fee = Decimal("0.00") if subtotal >= Decimal("999.00") else Decimal("60.00")
    return jsonify({
        "items": quoted_items,
        "subtotal": float(subtotal),
        "delivery_fee": float(delivery_fee),
        "total": float(subtotal + delivery_fee),
    })
