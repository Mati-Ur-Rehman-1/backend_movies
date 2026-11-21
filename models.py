from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from pgvector.sqlalchemy import Vector

db = SQLAlchemy()
bcrypt = Bcrypt()


# ─── Auth ───────────────────────────────────────────────

class Auth(db.Model):
    __tablename__ = "auth"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))


class ActiveToken(db.Model):
    __tablename__ = "active_tokens"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("auth.id"), nullable=False)
    jti = db.Column(db.String(255), unique=True, nullable=False)

    @staticmethod
    def find_active(jti):
        return ActiveToken.query.filter_by(jti=jti).first()

    @staticmethod
    def is_active(jti):
        return ActiveToken.find_active(jti) is not None


class Profile(db.Model):
    __tablename__ = "profile"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("auth.id"), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    image = db.Column(db.String(500))
    location = db.Column(db.String(255))


# ─── Movies ─────────────────────────────────────────────

class Movie(db.Model):
    __tablename__ = "movies_movie"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    yts_id = db.Column(db.Integer, unique=True, nullable=False)
    imdb_code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    title_english = db.Column(db.String(255), nullable=True)
    slug = db.Column(db.String(255), nullable=True)
    year = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float, default=0.0)
    runtime = db.Column(db.Integer, nullable=True)
    genres = db.Column(db.ARRAY(db.String), nullable=True)
    description_full = db.Column(db.Text, nullable=True)
    yt_trailer_code = db.Column(db.String(50), nullable=True)
    language = db.Column(db.String(10), default='en')
    mpa_rating = db.Column(db.String(20), nullable=True)
    date_uploaded = db.Column(db.String(100), nullable=True)
    date_uploaded_unix = db.Column(db.BigInteger, nullable=True)
    is_fetched = db.Column(db.Boolean, default=False)
    embedding = db.Column(Vector(768), nullable=True)

    images = db.relationship("MovieImage", backref="movie", uselist=False)
    torrents = db.relationship("Torrent", backref="movie")
    cast_members = db.relationship("Cast", backref="movie")


class Cast(db.Model):
    __tablename__ = "movies_cast"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies_movie.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    character_name = db.Column(db.String(255), nullable=False)
    url_small_image = db.Column(db.String(500), nullable=True)
    imdb_code = db.Column(db.String(20), nullable=True)


class MovieImage(db.Model):
    __tablename__ = "movies_movieimage"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies_movie.id"), unique=True, nullable=False)
    background_image = db.Column(db.String(500), nullable=False)
    background_image_original = db.Column(db.String(500), nullable=False)
    small_cover_image = db.Column(db.String(500), nullable=False)
    medium_cover_image = db.Column(db.String(500), nullable=False)
    large_cover_image = db.Column(db.String(500), nullable=False)
    medium_screenshot_image1 = db.Column(db.String(500), nullable=True)
    medium_screenshot_image2 = db.Column(db.String(500), nullable=True)
    medium_screenshot_image3 = db.Column(db.String(500), nullable=True)
    large_screenshot_image1 = db.Column(db.String(500), nullable=True)
    large_screenshot_image2 = db.Column(db.String(500), nullable=True)
    large_screenshot_image3 = db.Column(db.String(500), nullable=True)


class Torrent(db.Model):
    __tablename__ = "movies_torrent"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies_movie.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    hash = db.Column(db.String(100), nullable=False)
    quality = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    is_repack = db.Column(db.String(5), default="0")
    video_codec = db.Column(db.String(20), nullable=False)
    bit_depth = db.Column(db.String(5), nullable=True)
    audio_channels = db.Column(db.String(10), nullable=True)
    seeds = db.Column(db.Integer, default=0)
    peers = db.Column(db.Integer, default=0)
    size = db.Column(db.String(50), nullable=False)
    size_bytes = db.Column(db.BigInteger, nullable=False)
    date_uploaded = db.Column(db.String(100), nullable=False)
    date_uploaded_unix = db.Column(db.BigInteger, nullable=False)