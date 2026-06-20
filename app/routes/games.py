"""
Games routes — display owned games with filtering.
"""

from flask import Blueprint, render_template, request, jsonify
from app import db

games_bp = Blueprint("games", __name__)


def get_filter_params():
    """Extract filter parameters from request."""
    return {
        "view": request.args.get("view", "grid"),  # grid or list
        "search": request.args.get("search", "").strip(),
        "platform": request.args.get("platform", "").strip(),
        "account": request.args.get("account", "").strip(),
        "gfn_only": request.args.get("gfn_only", "").lower() == "true",
    }


@games_bp.route("/")
def index():
    """Home page — display all games."""
    # Get filter options for dropdowns
    platforms = db.session.execute(
        db.text("SELECT DISTINCT platform_name FROM vw_owned_games_unified ORDER BY platform_name")
    ).fetchall()
    
    accounts = db.session.execute(
        db.text("SELECT DISTINCT account_username FROM vw_owned_games_unified ORDER BY account_username")
    ).fetchall()
    
    # Flatten tuples to lists
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
        platforms=platforms,
        accounts=accounts,
    )


@games_bp.route("/games")
def get_games():
    """
    API endpoint to fetch filtered games.
    Returns HTML partial for grid/list view (used by htmx).
    """
    params = get_filter_params()
    
    # Build filtered query
    filters = ["1=1"]
    
    if params["search"]:
        filters.append(f"title ILIKE '%{params['search']}%'")
    
    if params["platform"]:
        filters.append(f"platform_name = '{params['platform']}'")
    
    if params["account"]:
        filters.append(f"account_username = '{params['account']}'")
    
    if params["gfn_only"]:
        filters.append("is_on_gfn = true")
    
    where_clause = " AND ".join(filters)
    
    query_str = f"""
        SELECT 
            game_id,
            title,
            cover_url,
            platform_name,
            account_username,
            platform_specific_id,
            playtime_minutes,
            last_played,
            is_on_gfn,
            gfn_deeplink_url
        FROM vw_owned_games_unified
        WHERE {where_clause}
        ORDER BY title
        LIMIT 500
    """
    
    games = db.session.execute(db.text(query_str)).fetchall()
    
    # Convert to list of dicts
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
        }
        for g in games
    ]
    
    # Return HTML partial based on view type
    if params["view"] == "list":
        return render_template("_games_list.html", games=games_list)
    else:  # grid
        return render_template("_games_grid.html", games=games_list)


@games_bp.route("/api/stats")
def api_stats():
    """Return library statistics."""
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
