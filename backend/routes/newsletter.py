"""Newsletter subscription endpoint."""

from flask import Blueprint, jsonify, request
from mysql.connector import IntegrityError

from db import cursor
from utils.validators import ValidationError, validate_email


newsletter_bp = Blueprint("newsletter", __name__, url_prefix="/api/newsletter")


@newsletter_bp.post("")
def subscribe():
    data = request.get_json(silent=False)
    if not isinstance(data, dict):
        raise ValidationError("A JSON object is required.")
    email = validate_email(data.get("email"))
    try:
        with cursor() as (connection, db_cursor):
            db_cursor.execute("INSERT INTO newsletter (email) VALUES (%s)", (email,))
            connection.commit()
        return jsonify({"message": "Subscription received.", "subscribed": True}), 201
    except IntegrityError as error:
        if error.errno == 1062:
            return jsonify({"message": "Already subscribed.", "subscribed": True}), 200
        raise
