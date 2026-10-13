"""Flask application factory and API error handling."""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from werkzeug.exceptions import HTTPException

from config import Config
from routes.auth import auth_bp
from routes.cart import cart_bp
from routes.newsletter import newsletter_bp
from routes.orders import orders_bp
from routes.products import products_bp
from utils.validators import ValidationError


jwt = JWTManager()


def create_app():
    if not Config.JWT_SECRET_KEY or Config.JWT_SECRET_KEY == "replace-with-a-long-random-secret":
        raise RuntimeError("Set a private JWT_SECRET_KEY in backend/.env before starting the API.")
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(
        app,
        resources={r"/api/*": {"origins": ["http://127.0.0.1:5500", "http://localhost:5500"]}},
        allow_headers=["Content-Type", "Authorization", "ADMIN_KEY"],
        methods=["GET", "POST", "PUT", "OPTIONS"],
    )
    jwt.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(newsletter_bp)

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({"error": error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request error.")
        return jsonify({"error": "An unexpected server error occurred."}), 500

    @jwt.unauthorized_loader
    def handle_missing_token(_reason):
        return jsonify({"error": "Authorization token is required."}), 401

    @jwt.invalid_token_loader
    def handle_invalid_token(_reason):
        return jsonify({"error": "Authorization token is invalid."}), 401

    @jwt.expired_token_loader
    def handle_expired_token(_jwt_header, _jwt_payload):
        return jsonify({"error": "Authorization token has expired."}), 401

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
