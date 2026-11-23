from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from models import Movie, Cast, MovieImage, Torrent
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
import ollama
from ai.ai_helpers import (
    is_movie_related,
    rewrite_query,
    generate_recommendation_reply,
)

movies_bp = Blueprint("movies", __name__, url_prefix="/movies")

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 50


def format_movie(movie, include_cast=False):
    images = None
    if movie.images:
        images = {
            "background_image": movie.images.background_image,
            "background_image_original": movie.images.background_image_original,
            "small_cover_image": movie.images.small_cover_image,
            "medium_cover_image": movie.images.medium_cover_image,
            "large_cover_image": movie.images.large_cover_image,
            "medium_screenshot_image1": movie.images.medium_screenshot_image1,
            "medium_screenshot_image2": movie.images.medium_screenshot_image2,
            "medium_screenshot_image3": movie.images.medium_screenshot_image3,
            "large_screenshot_image1": movie.images.large_screenshot_image1,
            "large_screenshot_image2": movie.images.large_screenshot_image2,
            "large_screenshot_image3": movie.images.large_screenshot_image3,
        }

    torrents = [
        {
            "id": t.id,
            "url": t.url,
            "hash": t.hash,
            "quality": t.quality,
            "type": t.type,
            "is_repack": t.is_repack,
            "video_codec": t.video_codec,
            "bit_depth": t.bit_depth,
            "audio_channels": t.audio_channels,
            "seeds": t.seeds,
            "peers": t.peers,
            "size": t.size,
            "size_bytes": t.size_bytes,
            "date_uploaded": t.date_uploaded,
            "date_uploaded_unix": t.date_uploaded_unix,
        }
        for t in movie.torrents
    ]

    data = {
        "id": movie.id,
        "yts_id": movie.yts_id,
        "imdb_code": movie.imdb_code,
        "title": movie.title,
        "title_english": movie.title_english,
        "slug": movie.slug,
        "year": movie.year,
        "rating": movie.rating,
        "runtime": movie.runtime,
        "genres": movie.genres,
        "description_full": movie.description_full,
        "yt_trailer_code": movie.yt_trailer_code,
        "language": movie.language,
        "mpa_rating": movie.mpa_rating,
        "date_uploaded": movie.date_uploaded,
        "date_uploaded_unix": movie.date_uploaded_unix,
        "is_fetched": movie.is_fetched,
        "images": images,
        "torrents": torrents,
    }

    if include_cast:
        data["cast"] = [
            {
                "id": c.id,
                "name": c.name,
                "character_name": c.character_name,
                "url_small_image": c.url_small_image,
                "imdb_code": c.imdb_code,
            }
            for c in movie.cast_members
        ]
    return data


class InvalidQueryParam(ValueError):
    pass


def _parse_int(name, default=None, minimum=None, maximum=None):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise InvalidQueryParam(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise InvalidQueryParam(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise InvalidQueryParam(f"{name} must be at most {maximum}")
    return value


def _like_pattern(value):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@movies_bp.route("/", methods=["GET"])
@jwt_required()
def show_movie():
    raw_id = request.args.get("id")
    if raw_id is not None and raw_id != "":
        try:
            movie_id = int(raw_id)
        except ValueError:
            return jsonify({"message": "id must be an integer"}), 400

        include = request.args.get("include")
        movie = Movie.query.get(movie_id)
        if movie is None:
            return jsonify({"message": "Movie not found"}), 404
        return jsonify(format_movie(movie, include_cast=include in ("cast", "actors")))

    try:
        page = _parse_int("page", default=1, minimum=1)
        per_page = _parse_int("per_page", default=DEFAULT_PER_PAGE, minimum=1)
        per_page = min(per_page, MAX_PER_PAGE)
        year = _parse_int("year")
        rating = _parse_int("rating", minimum=0, maximum=10)
    except InvalidQueryParam as e:
        return jsonify({"message": str(e)}), 400

    language = (request.args.get("language") or "").strip()
    quality = (request.args.get("quality") or "").strip()
    search = (request.args.get("q") or "").strip()
    if len(search) > 200:
        return jsonify({"message": "q must be at most 200 characters"}), 400

    include = request.args.get("include")
    include_cast = include in ("cast", "actors")

    query = Movie.query
    if year is not None:
        query = query.filter(Movie.year == year)
    if rating is not None:
        query = query.filter(Movie.rating >= rating, Movie.rating < rating + 1)
    if language:
        query = query.filter(Movie.language == language)
    if quality:
        query = query.filter(Movie.torrents.any(Torrent.quality == quality))
    if search:
        pattern = _like_pattern(search)
        query = query.filter(or_(
            Movie.title.ilike(pattern, escape="\\"),
            Movie.title_english.ilike(pattern, escape="\\"),
        ))

    load_options = [selectinload(Movie.images), selectinload(Movie.torrents)]
    if include_cast:
        load_options.append(selectinload(Movie.cast_members))

    pagination = (
        query.options(*load_options)
        .order_by(Movie.id.asc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "items": [format_movie(movie, include_cast=include_cast) for movie in pagination.items],
    })


@movies_bp.route("/recommendation", methods=["POST"])
@jwt_required()
def recommendation():
    data = request.get_json(silent=True) or {}
    user_message = data.get("user_message")
    if user_message:
        user_message = user_message.strip() or None
    movie_id = request.args.get("id", type=int)

    if movie_id is not None:
        movie = Movie.query.filter_by(id=movie_id).first()
        if movie is None:
            return jsonify({"message": "Movie not found"}), 404

        if movie.embedding is None:
            return jsonify({"message": "No recommendation found"}), 404

        recommendations = (
            Movie.query
            .filter(Movie.id != movie.id, Movie.embedding.isnot(None))
            .order_by(Movie.embedding.cosine_distance(movie.embedding))
            .limit(5)
            .all()
        )

        return jsonify([format_movie(m) for m in recommendations])

    elif user_message:
        if not is_movie_related(user_message):
            return jsonify({"message": "Sorry, I can only help you with movie recommendations"})

        rewrite_message = rewrite_query(user_message)

        try:
            response = ollama.embed(
                model="nomic-embed-text",
                input=rewrite_message
            )
            embedding = response["embeddings"][0]
        except Exception:
            return jsonify({"message": "Embedding service is currently unavailable. Please try again later."}), 503

        recommendations = (
            Movie.query
            .filter(Movie.embedding.isnot(None))
            .order_by(Movie.embedding.cosine_distance(embedding))
            .limit(5)
            .all()
        )

        movies = [format_movie(m) for m in recommendations]
        reply = generate_recommendation_reply(user_message, movies)

        return jsonify({
            "reply": reply,
            "movies": movies
        })

    return jsonify({"message": "Please enter message or movie_id"})