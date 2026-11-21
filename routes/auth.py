from flask import jsonify, request, Blueprint
from models import Auth, bcrypt, db, ActiveToken
from flask_jwt_extended import get_jti, jwt_required, get_jwt, get_jwt_identity, decode_token
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    try:
        user = Auth.query.filter_by(email=email).first()

        if user is None:
            new_user = Auth(
                name=name,
                email=email,
                password=bcrypt.generate_password_hash(password).decode("utf-8")
            )

            db.session.add(new_user)
            db.session.commit()

            return jsonify({"message": "Signup successful"}), 201
        return jsonify({"message": "try another email"}), 409
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Unable to complete signup"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    try:
        user = Auth.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            access_token = create_access_token(identity=str(user.id))
            refresh_token = create_refresh_token(identity=str(user.id))
            token_id = get_jti(access_token)

            active_token = ActiveToken(user_id=user.id, jti=token_id)

            db.session.add(active_token)
            db.session.commit()

            return jsonify({
                "message": "login successful",
                "access_token": access_token,
                "refresh_token": refresh_token
            }), 200

        return jsonify({"message": "incorrect login"}), 401
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Unable to complete login"}), 500

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    try:
        current_user_id = get_jwt_identity()

        # 1. Get old access token from header and delete it
        old_access_token = request.headers.get("X-Access-Token")

        if old_access_token:
            old_access_token = old_access_token.replace("Bearer ", "").strip()
            try:
                decoded = decode_token(old_access_token, allow_expired=True)
                old_jti = decoded.get("jti")
                if old_jti:
                    old_token = ActiveToken.find_active(old_jti)
                    if old_token and old_token.user_id == int(current_user_id):
                        db.session.delete(old_token)
            except Exception:
                pass

        # 2. Create new access token
        new_access_token = create_access_token(
            identity=current_user_id
        )

        # 3. Save new token to database
        new_jti = get_jti(new_access_token)
        new_token = ActiveToken(user_id=int(current_user_id), jti=new_jti)
        db.session.add(new_token)

        db.session.commit()

        return jsonify({
            "access_token": new_access_token
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Unable to refresh token"}), 401



@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    try:
        jti = get_jwt()["jti"]

        token = ActiveToken.find_active(jti)
        if token:
            db.session.delete(token)
            db.session.commit()

        return jsonify({"message": "Logout successful"}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Unable to logout"}), 500


@auth_bp.route("/forget", methods=["POST"])
def forget():
    data = request.get_json(silent=True) or {}

    email = data.get("email")
    current_password = data.get("current_password")
    password = data.get("password")

    if not email or not current_password or not password:
        return jsonify({"message": "Email, current password and new password are required"}), 400

    try:
        user = Auth.query.filter_by(email=email).first()

        if user is None:
            return jsonify({"message": "email user not found"}), 409

        if not bcrypt.check_password_hash(user.password, current_password):
            return jsonify({"message": "incorrect current password"}), 401

        user.password = bcrypt.generate_password_hash(password).decode("utf-8")
        ActiveToken.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        return jsonify({"message": "Password updated successfully"}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Unable to reset password"}), 500
