from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Alembic/Flask-Migrate can see them for autogeneration.
    from app import models  # noqa: F401

    from app.routes.games import games_bp
    app.register_blueprint(games_bp)

    return app
