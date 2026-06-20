import os


class Config:
    """Base config. Reads everything from environment variables so the
    same image works locally, in docker-compose, and in any future
    production deployment (just swap DATABASE_URL)."""

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://gameapp:gameapp@localhost:5432/gamelibrary",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
