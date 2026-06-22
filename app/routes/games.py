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
    import os
    import sys
    from datetime import datetime
    
    # Add parent directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        from scripts.fetch_igdb_metadata import IGDBClient, GameMatcher
    except ImportError as e:
        return f'<span class="text-red-400 text-xs">⚠️ Import error: {str(e)}</span>'
    
    game = db.session.query(GameMaster).filter(
        GameMaster.game_id == game_id
    ).first()

    if not game:
        return '<span class="text-red-400 text-xs">Game not found</span>', 404

    # IMPORTANT: Do NOT use IGDBMetadataFetcher here — its __init__ calls
    # create_app() and pushes a second Flask app context, which breaks
    # inside an already-running request (causes a silent 500 that htmx
    # swallows). Use the low-level IGDBClient directly instead, reusing
    # the credentials from the CURRENT app's config/env.
    client_id = os.environ.get("IGDB_CLIENT_ID")
    client_secret = os.environ.get("IGDB_ACCESS_TOKEN")  # This is actually the Client Secret

    if not client_id or not client_secret:
        return '<span class="text-red-400 text-xs">⚠️ IGDB_CLIENT_ID / IGDB_ACCESS_TOKEN not set in environment</span>'

    try:
        igdb = IGDBClient(client_id, client_secret)
        matcher = GameMatcher()
    except Exception as e:
        return f'<span class="text-red-400 text-xs">⚠️ IGDB init error: {str(e)}</span>'

    # If no IGDB ID yet, search by title with fuzzy matching (like admin panel does)
    if not game.igdb_id:
        try:
            # Search with limit=5 to get multiple results for fuzzy matching
            results = igdb.search_games(game.title, limit=5)
            
            if not results:
                return f'<span class="text-yellow-400 text-xs">⚠️ No IGDB results found for: {game.title}</span>'
            
            # Use fuzzy matching to find best match (same as admin panel)
            best_match = matcher.find_best_match(game.title, results, threshold=0.7)
            
            if not best_match:
                return f'<span class="text-yellow-400 text-xs">⚠️ No close match in IGDB for: {game.title}<br><small>Tried: {", ".join([r.get("name", "?") for r in results[:3]])}</small></span>'
            
            game.igdb_id = best_match.get("id")
            if not game.igdb_id:
                return '<span class="text-yellow-400 text-xs">⚠️ No valid IGDB ID in search results</span>'
            
        except Exception as e:
            return f'<span class="text-red-400 text-xs">⚠️ Error searching IGDB: {str(e)}</span>'

    # Fetch details from IGDB by ID
    try:
        igdb_game = igdb.get_game_by_igdb_id(game.igdb_id)
        
        if not igdb_game:
            return f'<span class="text-yellow-400 text-xs">⚠️ Game ID {game.igdb_id} not found on IGDB</span>'

        # Update game with fresh data (same parsing as admin panel)
        if igdb_game.get("name"):
            game.title = igdb_game.get("name")
        
        # Cover art
        cover_data = igdb_game.get("cover")
        if cover_data:
            cover_id = cover_data.get("url") if isinstance(cover_data, dict) else cover_data
            if cover_id:
                # IGDB returns paths like: //images.igdb.com/igdb/image/upload/t_cover_big/co2tgb.jpg
                if isinstance(cover_id, str):
                    if cover_id.startswith("//"):
                        game.cover_url = f"https:{cover_id}".replace("t_thumb", "t_1080p").replace("t_cover_big", "t_1080p")
                    elif cover_id.startswith("http"):
                        game.cover_url = cover_id.replace("t_thumb", "t_1080p").replace("t_cover_big", "t_1080p")
                    else:
                        game.cover_url = f"https://images.igdb.com/igdb/image/upload/t_1080p/{cover_id}.jpg"

        # Ratings
        if igdb_game.get("rating") is not None:
            game.rating = float(igdb_game.get("rating"))
        if igdb_game.get("total_rating") is not None:
            game.total_rating = float(igdb_game.get("total_rating"))
        if igdb_game.get("total_rating_count") is not None:
            game.total_rating_count = int(igdb_game.get("total_rating_count"))

        # Release date (IGDB returns Unix timestamp)
        first_release = igdb_game.get("first_release_date")
        if first_release:
            try:
                game.first_release_date = datetime.fromtimestamp(int(first_release))
            except (ValueError, TypeError):
                pass

        # Summary
        if igdb_game.get("summary"):
            game.summary = igdb_game.get("summary")

        # Genres, themes, game modes
        genres = igdb_game.get("genres", [])
        if isinstance(genres, list):
            game.genres = ", ".join([g.get("name", "") for g in genres if isinstance(g, dict)])
        
        themes = igdb_game.get("themes", [])
        if isinstance(themes, list):
            game.themes = ", ".join([t.get("name", "") for t in themes if isinstance(t, dict)])
        
        game_modes = igdb_game.get("game_modes", [])
        if isinstance(game_modes, list):
            game.game_modes = ", ".join([m.get("name", "") for m in game_modes if isinstance(m, dict)])

        # Developers & Publishers (same logic as admin panel)
        developers_list = []
        publishers_list = []
        involved_companies = igdb_game.get("involved_companies", [])
        
        if isinstance(involved_companies, list):
            for ic in involved_companies:
                if not isinstance(ic, dict):
                    continue
                company = ic.get("company", {})
                company_name = company.get("name", "") if isinstance(company, dict) else ""
                if company_name:
                    if ic.get("developer"):
                        developers_list.append(company_name)
                    if ic.get("publisher"):
                        publishers_list.append(company_name)
        
        if developers_list:
            game.developers = ", ".join(list(dict.fromkeys(developers_list)))  # Remove duplicates
        if publishers_list:
            game.publishers = ", ".join(list(dict.fromkeys(publishers_list)))  # Remove duplicates

        db.session.commit()

        # Re-fetch the updated game and render modal
        game = db.session.query(GameMaster).filter(GameMaster.game_id == game_id).first()
        gfn = db.session.query(GfnGame).filter_by(game_id=game_id).first()
        
        return render_template(
            "_game_detail.html",
            game=game,
            is_on_gfn=gfn is not None,
            gfn_url=gfn.gfn_url if gfn else None,
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
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] refresh_igdb failed: {error_trace}")
        return f'<span class="text-red-400 text-xs">⚠️ Error: {str(e)}</span>'


@games_bp.route("/game/<int:game_id>/delete", methods=["POST"])
def delete_game(game_id):
    """Delete a game and all its ownership records."""
    game = db.session.query(GameMaster).filter(
        GameMaster.game_id == game_id
    ).first()

    if not game:
        return '<span class="text-red-400 text-xs">Game not found</span>', 404

    game_title = game.title

    try:
        # Delete from all owned_games_* tables
        db.session.execute(
            db.text("DELETE FROM owned_games_steam WHERE game_id = :gid"),
            {"gid": game_id}
        )
        db.session.execute(
            db.text("DELETE FROM owned_games_epic WHERE game_id = :gid"),
            {"gid": game_id}
        )
        db.session.execute(
            db.text("DELETE FROM owned_games_gog WHERE game_id = :gid"),
            {"gid": game_id}
        )
        db.session.execute(
            db.text("DELETE FROM owned_games_ea WHERE game_id = :gid"),
            {"gid": game_id}
        )
        db.session.execute(
            db.text("DELETE FROM owned_games_battlenet WHERE game_id = :gid"),
            {"gid": game_id}
        )
        db.session.execute(
            db.text("DELETE FROM owned_games_ubisoft WHERE game_id = :gid"),
            {"gid": game_id}
        )

        # Delete from gfn_games if exists
        db.session.execute(
            db.text("DELETE FROM gfn_games WHERE game_id = :gid"),
            {"gid": game_id}
        )

        # Delete from games_master
        db.session.delete(game)
        db.session.commit()

        # Return success message and close modal via htmx
        return '''
        <div class="p-8 text-center">
            <div class="text-5xl mb-4">🗑️</div>
            <p class="text-green-400 font-semibold mb-4">Game removed successfully!</p>
            <p class="text-gray-400 text-sm mb-6">''' + game_title + ''' has been deleted from your library.</p>
            <button 
                onclick="closeModal()"
                class="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition"
            >
                Close Modal
            </button>
        </div>
        '''

    except Exception as e:
        db.session.rollback()
        return f'<span class="text-red-400 text-xs">⚠️ Error deleting game: {str(e)}</span>', 500
