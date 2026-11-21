from groq import (
    Groq,
    RateLimitError,
    AuthenticationError,
    PermissionDeniedError,
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    APIError,
)
import os
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


class AIServiceError(Exception):
    pass


class AIRateLimitError(AIServiceError):
    pass


class AIAuthError(AIServiceError):
    pass


def _handle_groq_error(e):
    if isinstance(e, RateLimitError):
        raise AIRateLimitError("AI service rate limit reached. Please try again later.") from e
    if isinstance(e, (AuthenticationError, PermissionDeniedError)):
        raise AIAuthError("AI service authentication failed. Please check API configuration.") from e
    if isinstance(e, (APIConnectionError, APITimeoutError, APIStatusError, APIError)):
        raise AIServiceError("AI service is currently unavailable. Please try again later.") from e
    raise AIServiceError("AI service is currently unavailable. Please try again later.") from e


def is_movie_related(message):
    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": "You are a movie assistant. You only answer YES or NO. If the user message is related to movies, reply YES. If not, reply NO."
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )
        answer = (response.choices[0].message.content or "").strip().upper()
        return answer == "YES"
    except Exception as e:
        _handle_groq_error(e)


def rewrite_query(message):
    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": "You are a movie search assistant. Rewrite the user message into a short and clear movie search query. Return only the rewritten query, nothing else."
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )
        return (response.choices[0].message.content or "").strip() or message
    except Exception:
        return message


def generate_recommendation_reply(user_message, movies):
    movies_text = ""
    for movie in movies:
        description = movie.get("description_full") or movie.get("description") or ""
        movies_text += f"- {movie.get('title', '')}: {description}\n"

    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful movie recommendation assistant. Based on the movies provided, write a short and friendly reply to the user. Keep it under 3 sentences. No tables, no bullet points, just plain text."
                },
                {
                    "role": "user",
                    "content": f"User said: {user_message}\n\nAvailable movies:\n{movies_text}"
                }
            ]
        )
        return (response.choices[0].message.content or "").strip() or "Here are some movie recommendations based on your request."
    except Exception:
        return "Here are some movie recommendations based on your request."