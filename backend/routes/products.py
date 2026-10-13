"""Public product catalogue endpoints."""

from flask import Blueprint, jsonify, request

from db import cursor
from utils.validators import ValidationError, validate_nonnegative_decimal


products_bp = Blueprint("products", __name__, url_prefix="/api/products")
SORT_COLUMNS = {"lo": "price_250 ASC, name ASC", "hi": "price_250 DESC, name ASC", "az": "name ASC"}
VALID_CATEGORIES = {"Raw", "Roasted", "Flavoured", "Gift"}


def serialize_product(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "grade": row["grade"],
        "description": row["description"],
        "ingredients": row["ingredients"],
        "best_for": row["best_for"],
        "p": [
            {"size": "250 g", "price": float(row["price_250"])},
            {"size": "500 g", "price": float(row["price_500"])},
            {"size": "1 kg", "price": float(row["price_1kg"])},
        ],
        "stock": row["stock"],
        "rating": float(row["rating"]),
        "review_count": row["review_count"],
        "image_url": row["image_url"],
    }


@products_bp.get("")
def list_products():
    clauses = ["is_active = TRUE"]
    values = []
    category = request.args.get("category", "").strip()
    grade = request.args.get("grade", "").strip()
    query = request.args.get("q", "").strip()
    if category:
        if category not in VALID_CATEGORIES:
            raise ValidationError("Unknown product category.")
        clauses.append("category = %s")
        values.append(category)
    if grade:
        clauses.append("grade = %s")
        values.append(grade)
    if query:
        clauses.append("(name LIKE %s OR description LIKE %s OR grade LIKE %s)")
        pattern = f"%{query[:100]}%"
        values.extend([pattern, pattern, pattern])
    min_price = None
    max_price = None
    if "min_price" in request.args and request.args["min_price"]:
        min_price = validate_nonnegative_decimal(request.args["min_price"], "Minimum price")
        clauses.append("price_250 >= %s")
        values.append(min_price)
    if "max_price" in request.args and request.args["max_price"]:
        max_price = validate_nonnegative_decimal(request.args["max_price"], "Maximum price")
        clauses.append("price_250 <= %s")
        values.append(max_price)
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValidationError("Minimum price cannot exceed maximum price.")
    sort = request.args.get("sort", "")
    if sort and sort not in SORT_COLUMNS:
        raise ValidationError("Sort must be lo, hi, or az.")
    order_by = SORT_COLUMNS.get(sort, "id ASC")

    with cursor() as (_, db_cursor):
        db_cursor.execute(
            f"SELECT id, name, category, grade, description, ingredients, best_for, "
            f"price_250, price_500, price_1kg, stock, rating, review_count, image_url "
            f"FROM products WHERE {' AND '.join(clauses)} ORDER BY {order_by}",
            tuple(values),
        )
        rows = db_cursor.fetchall()
    return jsonify([serialize_product(row) for row in rows])


@products_bp.get("/<int:product_id>")
def get_product(product_id):
    with cursor() as (_, db_cursor):
        db_cursor.execute(
            "SELECT id, name, category, grade, description, ingredients, best_for, "
            "price_250, price_500, price_1kg, stock, rating, review_count, image_url "
            "FROM products WHERE id = %s AND is_active = TRUE",
            (product_id,),
        )
        row = db_cursor.fetchone()
    if not row:
        return jsonify({"error": "Product not found."}), 404
    return jsonify(serialize_product(row))
