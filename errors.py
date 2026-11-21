from flask import jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from ai.ai_helpers import AIRateLimitError, AIAuthError, AIServiceError
from models import db


def register_error_handlers(app):
    @app.errorhandler(AIRateLimitError)
    def handle_ai_rate_limit(e):
        return jsonify({"message": "AI service rate limit reached. Please try again later."}), 429

    @app.errorhandler(AIAuthError)
    def handle_ai_auth_error(e):
        return jsonify({"message": "AI service authentication failed. Please check API configuration."}), 503

    @app.errorhandler(AIServiceError)
    def handle_ai_service_error(e):
        return jsonify({"message": "AI service is currently unavailable. Please try again later."}), 503

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        db.session.rollback()
        return jsonify({"message": "A database error occurred. Please try again later."}), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        if isinstance(e, HTTPException):
            return e
        db.session.rollback()
        return jsonify({"message": "An unexpected error occurred. Please try again later."}), 500
