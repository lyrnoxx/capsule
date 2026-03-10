import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY environment variable is required. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'logger.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Umami analytics (optional – set in .env to activate)
    ANALYTICS_DOMAIN = os.environ.get("ANALYTICS_DOMAIN", "")
    ANALYTICS_ID = os.environ.get("ANALYTICS_ID", "")
