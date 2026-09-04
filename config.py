import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "smart-recipe-ai-dev-secret-key-change-me")
    DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    # Fallback chain tried in order if the primary model name is retired/unavailable.
    GEMINI_MODEL_FALLBACKS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-2.5-flash"]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
