"""
Games routes — display owned games with filtering, sorting, status.
"""

from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models import GameMaster, GfnGame

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


@games_bp.route("/game/<int:game_id>/gfn-toggle", methods=["POST"])
def toggle_gfn(game_id):
    """Enable or disable GeForce NOW availability for a game (htmx)."""
    enable = request.form.get("enabled") == "true"

    game = db.session.query(GameMaster).filter(
        GameMaster.game_id == game_id
    ).first()

    if not game:
        return '<span class="text-red-400 text-xs">Game not found</span>', 404

    gfn = db.session.query(GfnGame).filter(GfnGame.game_id == game_id).first()

    if enable:
        if not gfn:
            gfn = GfnGame(
                game_id=game_id,
                gfn_url="https://play.geforcenow.com/mall/#/layout/games",
            )
            db.session.add(gfn)
        is_on_gfn = True
        gfn_url = gfn.gfn_url
    else:
        if gfn:
            db.session.delete(gfn)
        is_on_gfn = False
        gfn_url = None

    db.session.commit()

    return render_template(
        "_gfn_toggle.html",
        game=game,
        is_on_gfn=is_on_gfn,
        gfn_url=gfn_url,
    )


@games_bp.route("/game/<int:game_id>/refresh-igdb", methods=["POST"])
def refresh_igdb(game_id):
    """Refresh a single game's IGDB details (manual update from modal)."""
    from scripts.fetch_igdb_metadata import IGDBMetadataFetcher
    from datetime import datetime
    
    game = db.session.query(GameMaster).filter(
        GameMaster.game_id == game_id
    ).first()

    if not game:
        return '<span class="text-red-400 text-xs">Game not found</span>', 404

    # If no IGDB ID yet, search by title first
    if not game.igdb_id:
        try:
            fetcher = IGDBMetadataFetcher()
            results = fetcher.search_games(game.title, limit=1)
            if results:
                game.igdb_id = results[0]["id"]
            else:
                return '<span class="text-yellow-400 text-xs">⚠️ No IGDB match found for: ' + game.title + '</span>'
        except Exception as e:
            return f'<span class="text-red-400 text-xs">⚠️ Error searching IGDB: {str(e)}</span>'

    # Fetch details from IGDB by ID
    try:
        fetcher = IGDBMetadataFetcher()
        igdb_game = fetcher.get_game_by_igdb_id(game.igdb_id)
        
        if not igdb_game:
            return '<span class="text-yellow-400 text-xs">⚠️ Game not found on IGDB</span>'

        # Update game with fresh data
        game.title = igdb_game.get("name", game.title)
        
        # Cover art
        if igdb_game.get("cover"):
            cover_id = igdb_game["cover"].get("url", "").split("/")[-1].split(".")[0]
            if cover_id:
                game.cover_url = f"https://images.igdb.com/igdb/image/upload/t_1080p/{cover_id}.jpg"

        # Ratings
        game.rating = igdb_game.get("rating")
        game.total_rating = igdb_game.get("total_rating")
        game.total_rating_count = igdb_game.get("total_rating_count")

        # Release date
        first_release = igdb_game.get("first_release_date")
        if first_release:
            game.first_release_date = datetime.fromtimestamp(first_release)

        # Summary
        game.summary = igdb_game.get("summary")

        # Genres, themes, game modes
        if igdb_game.get("genres"):
            game.genres = ", ".join([g.get("name", "") for g in igdb_game["genres"]])
        if igdb_game.get("themes"):
            game.themes = ", ".join([t.get("name", "") for t in igdb_game["themes"]])
        if igdb_game.get("game_modes"):
            game.game_modes = ", ".join([m.get("name", "") for m in igdb_game["game_modes"]])

        # Developers & Publishers
        devs, pubs = [], []
        for ic in igdb_game.get("involved_companies", []):
            name = ic.get("company", {}).get("name", "")
            if ic.get("developer"):
                devs.append(name)
            if ic.get("publisher"):
                pubs.append(name)
        if devs:
            game.developers = ", ".join(devs)
        if pubs:
            game.publishers = ", ".join(pubs)

        db.session.commit()

        return render_template(
            "_game_detail.html",
            game=game,
            is_on_gfn=db.session.query(GfnGame).filter_by(game_id=game_id).first() is not None,
            gfn_url=db.session.query(GfnGame).filter_by(game_id=game_id).first().gfn_url 
                    if db.session.query(GfnGame).filter_by(game_id=game_id).first() else None,
            platforms=db.session.execute(
                db.text("""
                    SELECT DISTINCT platform_name, account_username
                    FROM vw_owned_games_unified
                    WHERE game_id = :gid
                """),
                {"gid": game_id},
            ).fetchall(),
            refresh_success=True
        )

    except Exception as e:
        return f'<span class="text-red-400 text-xs">⚠️ Error: {str(e)}</span>'
