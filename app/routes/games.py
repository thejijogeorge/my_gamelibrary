from flask import Blueprint

games_bp = Blueprint("games", __name__)


@games_bp.route("/")
def index():
    return "Game library — UI coming in the next phase."
