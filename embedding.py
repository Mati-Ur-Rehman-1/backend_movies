import ollama
from concurrent.futures import ThreadPoolExecutor, as_completed
from app import app
from models import db, Movie

BATCH_SIZE = 10  # movies per batch
MAX_WORKERS =4  # parallel threads


def process_movie(movie_data):
    movie_id, title, description = movie_data

    description = (description or "").strip()
    if not description:
        return movie_id, None, f"Skipping: {title} (empty description)"

    try:
        response = ollama.embed(
            model="nomic-embed-text",
            input=description
        )
        embeddings = response.get("embeddings") or []
        if not embeddings:
            return movie_id, None, f"Skipping: {title} (empty embedding)"

        return movie_id, embeddings[0], f"OK: {title}"

    except Exception as e:
        return movie_id, None, f"Failed: {title} ({e})"


def save_batch(results):
    with app.app_context():
        for movie_id, embedding, message in results:
            if embedding is not None:
                try:
                    movie = db.session.get(Movie, movie_id)
                    if movie:
                        movie.embedding = embedding
                        db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Save failed for id={movie_id}: {e}")


with app.app_context():
    try:
        movies = Movie.query.filter(
            Movie.description_full.isnot(None),
            Movie.embedding.is_(None)
        ).with_entities(Movie.id, Movie.title, Movie.description_full).all()
    except Exception as e:
        print(f"Failed to load movies: {e}")
        raise

    total = len(movies)
    print(f"Movies to process: {total}")

    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_movie, m): m for m in movies}

        batch_results = []

        for future in as_completed(futures):
            result = future.result()
            movie_id, embedding, message = result
            print(f"{completed + 1}/{total} - {message}")
            batch_results.append(result)
            completed += 1

            if len(batch_results) >= BATCH_SIZE:
                save_batch(batch_results)
                batch_results = []

        if batch_results:
            save_batch(batch_results)

    print("Embedding generation completed!")