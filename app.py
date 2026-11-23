from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flasgger import Swagger

from config import Config, HOST, SWAGGER_CONFIG, SWAGGER_TEMPLATE
from errors import register_error_handlers
from models import ActiveToken, bcrypt, db
from routes.auth import auth_bp
from routes.movie_routes import movies_bp
from routes.profile import profile_bp


app = Flask(__name__)
CORS(
    app,
    origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174"
    ],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.config.from_object(Config)
app.json.sort_keys = False

bcrypt.init_app(app)
db.init_app(app)

with app.app_context():
    db.create_all()

jwt = JWTManager(app)


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    if jwt_payload.get("type") != "access":
        return False
    return not ActiveToken.is_active(jwt_payload.get("jti"))


app.register_blueprint(movies_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)

Swagger(app, config=SWAGGER_CONFIG, template_file=SWAGGER_TEMPLATE)
register_error_handlers(app)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(host=HOST)
