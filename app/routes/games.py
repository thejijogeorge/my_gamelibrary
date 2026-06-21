"""
Games routes — display owned games with filtering, sorting, status.
"""

from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import GameMaster

games_bp = Blueprint("games", __name__)

VALID_SORTS = {
    "title": "title",
    "rating": "total_rating DESC NULLS LAST",
    "release": "first_release_date DESC NULLS LAST",
    "status": "status",
}


def get_filter_params():
    """Extract filter parameters from request."""
    return {
        "view": request.args.get("view", "grid"),
        "search": request.args.get("search", "").strip(),
        "platform": request.args.get("platform", "").strip(),
        "account": request.args.get("account", "").strip(),
        "gfn_only": request.args.get("gfn_only", "").lower() == "true",
        "status": request.args.get("status", "").strip(),
        "sort": request.args.get("sort", "title").strip(),
    }


@games_bp.route("/")
def index():
    """Home page."""
    platforms = db.session.execute(
        db.text("SELECT DISTINCT platform_name FROM vw_owned_games_unified ORDER BY platform_name")
    ).fetchall()
    accounts = db.session.execute(
        db.text("SELECT DISTINCT account_username FROM vw_owned_games_unified ORDER BY account_username")
    ).fetchall()

    platforms = [p[0] for p in platforms] if platforms else []
    accounts = [a[0] for a in accounts] if accounts else []

    params = get_filter_params()

    return render_template(
        "index.html",
        view=params["view"],
        search=params["search"],
        platform_filter=params["platform"],
        account_filter=params["account"],
        gfn_only=params["gfn_only"],
        status_filter=params["status"],
        sort=params["sort"],
        platforms=platforms,
        accounts=accounts,
    )


@games_bp.route("/games")
def get_games():
    """Filtered games — returns HTML partial for htmx."""
    params = get_filter_params()

    # Build parameterised filters
    conditions = ["1=1"]
    bind_params = {}

    if params["search"]:
        conditions.append("title ILIKE :search")
        bind_params["search"] = f"%{params['search']}%"

    if params["platform"]:
        conditions.append("platform_name = :platform")
        bind_params["platform"] = params["platform"]

    if params["account"]:
        conditions.append("account_username = :account")
        bind_params["account"] = params["account"]

    if params["gfn_only"]:
        conditions.append("is_on_gfn = true")

    if params["status"]:
        conditions.append("status = :status")
        bind_params["status"] = params["status"]

    where_clause = " AND ".join(conditions)
    order = VALID_SORTS.get(params["sort"], "title")

    query_str = f"""
        SELECT
            game_id, title, cover_url, platform_name,
            account_username, platform_specific_id,
            playtime_minutes, last_played, is_on_gfn,
            gfn_deeplink_url, total_rating, status
        FROM vw_owned_games_unified
        WHERE {where_clause}
        ORDER BY {order}, title
        LIMIT 500
    """

    games = db.session.execute(db.text(query_str), bind_params).fetchall()

    games_list = [
        {
            "game_id": g[0],
            "title": g[1],
            "cover_url": g[2],
            "platform_name": g[3],
            "account_username": g[4],
            "platform_specific_id": g[5],
            "playtime_minutes": g[6],
            "last_played": g[7],
            "is_on_gfn": g[8],
            "gfn_deeplink_url": g[9],
            "total_rating": g[10],
            "status": g[11] or "Not Started",
        }
        for g in games
    ]

    if params["view"] == "list":
        return render_template("_games_list.html", games=games_list)
    return render_template("_games_grid.html", games=games_list)


@games_bp.route("/api/stats")
def api_stats():
    """Library statistics."""
    stats = {
        "total_games": db.session.execute(
            db.text("SELECT COUNT(*) FROM vw_owned_games_unified")
        ).scalar(),
        "gfn_available": db.session.execute(
            db.text("SELECT COUNT(*) FROM vw_owned_games_unified WHERE is_on_gfn = true")
        ).scalar(),
        "total_platforms": db.session.execute(
            db.text("SELECT COUNT(DISTINCT platform_name) FROM vw_owned_games_unified")
        ).scalar(),
    }
    return jsonify(stats)


@games_bp.route("/game/<int:game_id>")
def game_detail(game_id):
    """Game detail modal partial."""
    game = db.session.query(GameMaster).filter(
        GameMaster.game_id == game_id
    ).first()

    if not game:
        return '<div class="p-6 text-center text-gray-400">Game not found.</div>'

    gfn_result = db.session.execute(
        db.text("SELECT gfn_url FROM gfn_games WHERE game_id = :gid"),
        {"gid": game_id},
    ).fetchone()
    is_on_gfn = gfn_result is not None
    gfn_url = gfn_result[0] if gfn_result else None

    platforms = db.session.execute(
        db.text("""
            SELECT DISTINCT platform_name, account_username
            FROM vw_owned_games_unified
            WHERE game_id = :gid
        """),
        {"gid": game_id},
    ).fetchall()

    return render_template(
        "_game_detail.html",
        game=game,
        is_on_gfn=is_on_gfn,
        gfn_url=gfn_url,
        platforms=platforms,
    )


@games_bp.route("/game/<int:game_id>/status", methods=["POST"])
def update_status(game_id):
    """Update game status (htmx)."""
    new_status = request.form.get("status", "Not Started")

    if new_status not in ("Not Started", "Started", "Completed"):
        return '<span class="text-red-400 text-xs">Invalid status</span>', 400

    game = db.session.query(GameMaster).filter(
        GameMaster.game_id == game_id
    ).first()

    if not game:
        return '<span class="text-red-400 text-xs">Game not found</span>', 404

    game.status = new_status
    db.session.commit()

    colors = {
        "Not Started": "gray",
        "Started": "yellow",
        "Completed": "green",
    }
    c = colors.get(new_status, "gray")

    return f'<span class="px-3 py-1 rounded-full text-xs font-bold bg-{c}-500/20 text-{c}-400 border border-{c}-500/30">{new_status}</span>'
