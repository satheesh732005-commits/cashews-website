"""Registration, login, and current-user profile endpoints."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from db import cursor
from utils.validators import (
    ValidationError,
    required_text,
    validate_email,
    validate_mobile,
    validate_password,
    validate_pincode,
    validate_state,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def json_body():
    body = request.get_json(silent=False)
    if not isinstance(body, dict):
        raise ValidationError("A JSON object is required.")
    return body


def public_user(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "mobile": row["mobile"],
        "email": row["email"],
        "address": row["address"],
        "city": row["city"],
        "pincode": row["pincode"],
        "state": row["state"],
        "is_admin": bool(row.get("is_admin", False)),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def user_response(row, status=200):
    claims = {"is_admin": bool(row.get("is_admin", False))}
    token = create_access_token(identity=str(row["id"]), additional_claims=claims)
    return jsonify({"token": token, "user": public_user(row)}), status


@auth_bp.post("/register")
def register():
    data = json_body()
    name = required_text(data, "name", "Name", minimum=3, maximum=120)
    mobile = validate_mobile(data.get("mobile"))
    email = validate_email(data.get("email"))
    password = validate_password(data.get("password"))
    address = required_text(data, "address", "Address", minimum=5, maximum=255)
    city = required_text(data, "city", "City", minimum=2, maximum=120)
    pincode = validate_pincode(data.get("pincode"))
    state = validate_state(data.get("state"))
    password_hash = generate_password_hash(password, method="scrypt")

    try:
        with cursor() as (connection, db_cursor):
            db_cursor.execute(
                """
                INSERT INTO users (name, mobile, email, password_hash, address, city,
                                   pincode, state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (name, mobile, email, password_hash, address, city, pincode, state),
            )
            user_id = db_cursor.lastrowid
            connection.commit()
            db_cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = db_cursor.fetchone()
            return user_response(row, 201)
    except IntegrityError as error:
        if error.errno == 1062:
            return jsonify({"error": "An account with that mobile or email already exists."}), 409
        raise


@auth_bp.post("/login")
def login():
    data = json_body()
    identity = data.get("identity") or data.get("email") or data.get("mobile")
    if not isinstance(identity, str) or not identity.strip():
        raise ValidationError("Enter your email address or mobile number.")
    identity = identity.strip().lower()
    if "@" in identity:
        identity = validate_email(identity)
        lookup = "email"
    else:
        identity = validate_mobile(identity)
        lookup = "mobile"
    password = data.get("password")
    if not isinstance(password, str) or not password:
        raise ValidationError("Password is required.")

    with cursor() as (_, db_cursor):
        db_cursor.execute(
            f"SELECT * FROM users WHERE {lookup} = %s LIMIT 1",
            (identity,),
        )
        row = db_cursor.fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email/mobile or password."}), 401
    return user_response(row)


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    with cursor() as (_, db_cursor):
        db_cursor.execute(
            "SELECT id, name, mobile, email, address, city, pincode, state, is_admin, created_at "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        row = db_cursor.fetchone()
    if not row:
        return jsonify({"error": "Account not found."}), 404
    return jsonify({"user": public_user(row)})
