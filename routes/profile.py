from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
import os
import uuid
from werkzeug.utils import secure_filename

from models import db, Auth, Profile
from flask import current_app

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.route("/", methods=["GET", "POST"])
@jwt_required()
def profile():

    user_id = get_jwt_identity()

    # Find user in database
    try:
        user = Auth.query.get(int(user_id))
    except (TypeError, ValueError):
        return jsonify({"message": "Unauthorized"}), 401

    if not user:
        return jsonify({
            "message": "User not found"
        }), 404

    user_profile = Profile.query.filter_by(user_id=user.id).first()

    if request.method == "GET":

        return jsonify({
            "message": "Profile fetched successfully",
            "profile": {
                "name": user.name,
                "email": user.email,
                "phone": user_profile.phone if user_profile else None,
                "image": f"uploads/{user_profile.image}" if user_profile and user_profile.image else None,
                "location": user_profile.location if user_profile else None
            }
        }), 200

    # POST: Create or update profile
    if request.method == "POST":
        try:
            data = request.form

            name = data.get("name")
            email = data.get("email")
            phone = data.get("phone")
            location = data.get("location")
            image = request.files.get("image")

            # Create profile if it doesn't exist
            if not user_profile:
                user_profile = Profile(user_id=user.id)
                db.session.add(user_profile)

            # Update Auth table
            if name is not None:
                user.name = name
            if email is not None:
                user.email = email

            # Update profile
            if phone is not None:
                user_profile.phone = phone

            if location is not None:
                user_profile.location = location

            if image and image.filename:
                upload_folder = current_app.config.get("UPLOAD_FOLDER")
                if not upload_folder:
                    return jsonify({"message": "Upload folder is not configured"}), 500
                os.makedirs(upload_folder, exist_ok=True)
                filename = secure_filename(image.filename)
                extension = os.path.splitext(filename)[1].lower()
                if extension not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                    return jsonify({"message": "Unsupported image type"}), 400
                filename = f"{uuid.uuid4().hex}{extension}"
                image.save(os.path.join(upload_folder, filename))
                user_profile.image = filename

            db.session.commit()

            return jsonify({
                "message": "Profile updated successfully",
                "profile": {
                    "name": user.name,
                    "email": user.email,
                    "phone": user_profile.phone,
                    "image": f"uploads/{user_profile.image}" if user_profile.image else None,
                    "location": user_profile.location
                }
            }), 200
        except IntegrityError:
            db.session.rollback()
            return jsonify({"message": "Email is already in use"}), 409
        except Exception:
            db.session.rollback()
            return jsonify({"message": "Unable to update profile"}), 500


