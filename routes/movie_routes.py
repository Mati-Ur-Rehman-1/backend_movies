from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from models import Movie, Cast, MovieImage, Torrent
import ollama
from ai.ai_helpers import (
    is_movie_related,
    rewrite_query,
    generate_recommendation_reply,
)

movies_bp = Blueprint("movies", __name__, url_prefix="/movies")

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


@movies_bp.route("/", methods=["GET"])
@jwt_required()
def show_movie():
    movie_id = request.args.get("id", type=int)
    include = request.args.get("include")
    limit = request.args.get("limit", default=20, type=int)
    include_cast = include in ("cast", "actors")


    if movie_id:
        movie = Movie.query.get(movie_id)
        if movie is None:
            return jsonify({"message": "Movie not found"}), 404
        return jsonify(format_movie(movie, include_cast=include_cast))

    movies = Movie.query.limit(limit).all()
    return jsonify([format_movie(m, include_cast=include_cast) for m in movies])


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