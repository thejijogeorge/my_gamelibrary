"""
Admin routes — upload Excel, fetch covers, manage GFN game IDs.
"""

import os
import subprocess
import threading
import uuid
import json
from datetime import datetime
from html import escape as html_escape

from flask import Blueprint, request, jsonify, render_template, current_app
from app import db
from app.models import (
    GfnGame, GameMaster, Platform, Account,
    OwnedGameSteam, OwnedGameEpic, OwnedGameGog,
    OwnedGameEA, OwnedGameBattlenet, OwnedGameUbisoft,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Canonical storefront list — keep in sync with Platform seed data and
# the ownership-table mapping in _add_ownership() below.
STOREFRONTS = ["Steam", "Epic", "GOG", "EA", "Battle.net", "Ubisoft"]

# In-memory task tracker (simple; resets on restart)
_tasks = {}


def _run_script_background(task_id, script_args, app):
    """Run a Python script in background and stream output in real-time."""
    _tasks[task_id]["status"] = "running"
    _tasks[task_id]["started_at"] = datetime.utcnow().isoformat()
    _tasks[task_id]["recent_lines"] = []
    _tasks[task_id]["output"] = ""
    _tasks[task_id]["errors"] = ""

    try:
        process = subprocess.Popen(
            ["python", "-u"] + script_args,  # -u for unbuffered output
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/app",
        )

        all_output = []

        # Read stdout line by line in real-time
        for line in process.stdout:
            line = line.rstrip()
            if line:
                all_output.append(line)
                # Keep last 5 meaningful lines for live status
                recent = _tasks[task_id]["recent_lines"]
                recent.append(line)
                if len(recent) > 5:
                    recent.pop(0)

        # Wait for process to finish
        process.wait(timeout=600)

        # Capture any remaining stderr
        stderr_output = process.stderr.read() if process.stderr else ""

        _tasks[task_id]["output"] = "\n".join(all_output[-50:])
        _tasks[task_id]["errors"] = stderr_output[-1000:] if stderr_output else ""

        if process.returncode == 0:
            _tasks[task_id]["status"] = "completed"
        else:
            _tasks[task_id]["status"] = "failed"

    except subprocess.TimeoutExpired:
        process.kill()
        _tasks[task_id]["status"] = "timeout"
        _tasks[task_id]["errors"] = "Script exceeded 10 minute timeout."
    except Exception as e:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["errors"] = str(e)

    _tasks[task_id]["finished_at"] = datetime.utcnow().isoformat()


# ── Upload Excel ─────────────────────────────────────────────

@admin_bp.route("/upload", methods=["POST"])
def upload_excel():
    """Upload Excel file and import games."""
    if "file" not in request.files:
        return _render_status("error", "No file selected.")

    file = request.files["file"]
    if file.filename == "":
        return _render_status("error", "No file selected.")

    if not file.filename.endswith((".xlsx", ".xls")):
        return _render_status("error", "Please upload an .xlsx or .xls file.")

    # Save uploaded file
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    safe_name = f"upload_{uuid.uuid4().hex[:8]}_{file.filename}"
    filepath = os.path.join(upload_dir, safe_name)
    file.save(filepath)

    # Start import in background
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {"type": "import", "status": "starting", "filename": file.filename}

    thread = threading.Thread(
        target=_run_script_background,
        args=(task_id, ["scripts/import_games_from_excel.py", filepath], current_app._get_current_object()),
        daemon=True,
    )
    thread.start()

    return _render_status(
        "running",
        f"Importing games from <strong>{file.filename}</strong>...",
        task_id=task_id,
    )


# ── Fetch Covers ─────────────────────────────────────────────

@admin_bp.route("/fetch-covers", methods=["POST"])
def fetch_covers():
    """Trigger IGDB cover art fetch."""
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {"type": "covers", "status": "starting"}

    thread = threading.Thread(
        target=_run_script_background,
        args=(task_id, ["scripts/fetch_igdb_metadata.py"], current_app._get_current_object()),
        daemon=True,
    )
    thread.start()

    return _render_status(
        "running",
        "Fetching cover art from IGDB...",
        task_id=task_id,
    )


# ── Deduplicate Games ────────────────────────────────────────

@admin_bp.route("/deduplicate", methods=["POST"])
def deduplicate():
    """Remove duplicate games (same game + storefront + gamer ID)."""
    total_deleted = 0

    # Deduplicate each owned_games table
    for table, id_col in [
        ("owned_games_steam", "steam_appid"),
        ("owned_games_epic", "epic_item_id"),
        ("owned_games_gog", "gog_product_id"),
    ]:
        result = db.session.execute(db.text(f"""
            DELETE FROM {table}
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM {table}
                GROUP BY account_id, game_id
            )
        """))
        deleted = result.rowcount
        total_deleted += deleted

    db.session.commit()

    if total_deleted > 0:
        return _render_status("completed", f"✅ Removed <strong>{total_deleted}</strong> duplicate entries.")
    else:
        return _render_status("completed", "✅ No duplicates found — library is clean!")


# ── Populate GFN URLs ────────────────────────────────────────

@admin_bp.route("/fetch-details", methods=["POST"])
def fetch_details():
    """Fetch game details (summary, rating, themes) for games that already have covers."""
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {"type": "details", "status": "starting"}

    thread = threading.Thread(
        target=_run_script_background,
        args=(task_id, ["scripts/fetch_igdb_metadata.py", "--details"], current_app._get_current_object()),
        daemon=True,
    )
    thread.start()

    return _render_status(
        "running",
        "Fetching game details (summary, ratings, themes) from IGDB...",
        task_id=task_id,
    )


@admin_bp.route("/populate-gfn", methods=["POST"])
def populate_gfn():
    """Populate GFN launch URLs for all GFN games."""
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {"type": "gfn_populate", "status": "starting"}

    thread = threading.Thread(
        target=_run_script_background,
        args=(task_id, ["scripts/populate_gfn_game_ids.py"], current_app._get_current_object()),
        daemon=True,
    )
    thread.start()

    return _render_status(
        "running",
        "Populating GFN launch URLs...",
        task_id=task_id,
    )


# ── Task Status ──────────────────────────────────────────────

@admin_bp.route("/task-status/<task_id>")
def task_status(task_id):
    """Poll task status (used by htmx)."""
    task = _tasks.get(task_id)
    if not task:
        return _render_status("error", "Task not found.")

    if task["status"] == "running":
        recent = task.get("recent_lines", [])
        if recent:
            # Show the last few lines of output as live progress
            progress_html = "<br>".join(
                f'<span class="text-cyan-300">{line}</span>' 
                for line in recent[-3:]
            )
            return _render_status("running", progress_html, task_id=task_id)
        else:
            return _render_status("running", "Starting...", task_id=task_id)
    elif task["status"] == "completed":
        # Extract last few meaningful lines from output
        output = task.get("output", "")
        summary = _extract_summary(output)
        return _render_status("completed", summary)
    elif task["status"] == "failed":
        error_msg = task.get("errors", "Unknown error")
        output = task.get("output", "")
        return _render_status("error", f"{_extract_summary(output)}<br><pre class='text-xs mt-2 text-red-300'>{error_msg[:500]}</pre>")
    elif task["status"] == "timeout":
        return _render_status("error", "Task timed out after 10 minutes.")
    else:
        return _render_status("running", "Starting...", task_id=task_id)


# ── Update GFN ID for a game ─────────────────────────────────

@admin_bp.route("/update-gfn-id", methods=["POST"])
def update_gfn_id():
    """Set or update a GFN game UUID for a specific game."""
    game_id = request.form.get("game_id")
    gfn_uuid = request.form.get("gfn_uuid", "").strip()

    if not game_id:
        return _render_status("error", "No game selected.")

    # Validate UUID format (basic check)
    if gfn_uuid and (len(gfn_uuid) != 36 or gfn_uuid.count("-") != 4):
        return _render_status("error", "Invalid UUID format. Expected: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

    try:
        game_id = int(game_id)
    except ValueError:
        return _render_status("error", "Invalid game ID.")

    # Find or create GFN entry
    gfn_game = db.session.query(GfnGame).filter(GfnGame.game_id == game_id).first()

    if not gfn_game:
        # Create new GFN entry
        gfn_game = GfnGame(game_id=game_id)
        db.session.add(gfn_game)

    if gfn_uuid:
        gfn_game.gfn_url = f"https://play.geforcenow.com/games?game-id={gfn_uuid}"
    else:
        # Clear the UUID - set fallback
        gfn_game.gfn_url = "https://play.geforcenow.com/mall/#/layout/games"

    db.session.commit()

    game = db.session.query(GameMaster).filter(GameMaster.game_id == game_id).first()
    title = game.title if game else f"Game #{game_id}"

    if gfn_uuid:
        return _render_status("completed", f"✅ <strong>{title}</strong> — GFN deep link set!")
    else:
        return _render_status("completed", f"✅ <strong>{title}</strong> — GFN link cleared, using fallback.")


# ── Search games for GFN assignment ──────────────────────────

@admin_bp.route("/search-games")
def search_games():
    """Search games for GFN ID assignment (htmx partial)."""
    q = request.args.get("q", "").strip()

    if len(q) < 2:
        return '<p class="text-gray-500 text-sm py-2">Type at least 2 characters...</p>'

    results = db.session.execute(
        db.text("""
            SELECT DISTINCT gm.game_id, gm.title, gm.cover_url,
                   gfn.gfn_url,
                   CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn
            FROM games_master gm
            LEFT JOIN gfn_games gfn ON gm.game_id = gfn.game_id
            WHERE gm.title ILIKE :q
            ORDER BY gm.title
            LIMIT 15
        """),
        {"q": f"%{q}%"},
    ).fetchall()

    if not results:
        return '<p class="text-gray-500 text-sm py-2">No games found.</p>'

    html = ""
    for r in results:
        game_id, title, cover_url, gfn_url, is_on_gfn = r

        # Extract existing UUID from URL if present
        current_uuid = ""
        if gfn_url and "game-id=" in gfn_url:
            current_uuid = gfn_url.split("game-id=")[-1].split("&")[0]

        gfn_badge = '<span class="text-green-400 text-xs">☁️ On GFN</span>' if is_on_gfn else '<span class="text-gray-600 text-xs">Not on GFN</span>'

        html += f"""
        <div class="flex items-center gap-3 p-3 rounded-lg bg-gray-800/50 border border-cyan-500/10 hover:border-cyan-500/30 transition">
            <div class="w-8 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-700">
                {'<img src="' + cover_url + '" class="w-full h-full object-cover" />' if cover_url else '<div class="w-full h-full flex items-center justify-center text-xs">🎮</div>'}
            </div>
            <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-white truncate">{title}</p>
                <p class="text-xs">{gfn_badge}</p>
            </div>
            <div class="flex items-center gap-2">
                <input
                    type="text"
                    name="gfn_uuid"
                    value="{current_uuid}"
                    placeholder="Paste GFN UUID..."
                    class="w-64 px-3 py-1.5 text-xs rounded bg-gray-900 border border-cyan-500/20 text-white placeholder-gray-600 focus:border-cyan-400 focus:outline-none"
                    id="uuid-{game_id}"
                />
                <button
                    hx-post="/admin/update-gfn-id"
                    hx-vals='{{"game_id": "{game_id}"}}'
                    hx-include="#uuid-{game_id}"
                    hx-target="#gfn-status"
                    class="px-3 py-1.5 text-xs font-semibold rounded bg-green-600 hover:bg-green-500 text-white transition whitespace-nowrap"
                >
                    Save
                </button>
            </div>
        </div>
        """

    return html


# ── Add Game Manually ───────────────────────────────────────

# Maps a storefront display name to (OwnedGame model class, its
# storefront-specific id column name). Used by both the gamer-ID
# checkbox loader and the actual insert logic, so the two can never
# drift out of sync with each other.
_STOREFRONT_TABLE_MAP = {
    "Steam": (OwnedGameSteam, "steam_appid"),
    "Epic": (OwnedGameEpic, "epic_item_id"),
    "GOG": (OwnedGameGog, "gog_product_id"),
    "EA": (OwnedGameEA, "ea_game_id"),
    "Battle.net": (OwnedGameBattlenet, "battlenet_game_id"),
    "Ubisoft": (OwnedGameUbisoft, "ubisoft_game_id"),
}


@admin_bp.route("/add-game-form")
def add_game_form():
    """Render the 'Add Game' form (htmx partial, loaded into the admin panel)."""
    return render_template("_add_game_form.html", storefronts=STOREFRONTS)


@admin_bp.route("/igdb-search")
def igdb_search():
    """
    Live IGDB search for the Add Game form's name field.
    Distinct from /admin/search-games, which searches the LOCAL database
    (used for GFN UUID assignment) — this one hits the IGDB API directly
    so the user can pick the canonical title/cover for a game they don't
    own yet.
    """
    # Reads "title" (not "q") because htmx's default GET serialization
    # uses the triggering input's own name="title" attribute — there's
    # no js: eval extension loaded in this project, so we match the
    # field's real name rather than trying to rename it via hx-vals.
    q = request.args.get("title", "").strip()

    if len(q) < 2:
        return '<p class="text-gray-500 text-sm py-2">Type at least 2 characters...</p>'

    # IGDB credentials are read from the environment directly everywhere
    # else in this app (see games.py's refresh_igdb) — Config never loads
    # them into Flask's app.config, so match that convention here too.
    client_id = os.environ.get("IGDB_CLIENT_ID")
    client_secret = os.environ.get("IGDB_ACCESS_TOKEN")

    if not client_id or not client_secret:
        return '<p class="text-red-400 text-xs py-2">⚠️ IGDB credentials not configured.</p>'

    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from scripts.fetch_igdb_metadata import IGDBClient
        igdb = IGDBClient(client_id, client_secret)
        results = igdb.search_games(q, limit=8)
    except Exception as e:
        return f'<p class="text-red-400 text-xs py-2">⚠️ IGDB search error: {str(e)}</p>'

    if not results:
        return '<p class="text-gray-500 text-sm py-2">No IGDB matches. You can still type the name manually below.</p>'

    html = ""
    for r in results:
        igdb_id = r.get("id", "")
        name = r.get("name") or ""
        year = ""
        if r.get("first_release_date"):
            try:
                year = datetime.utcfromtimestamp(int(r["first_release_date"])).year
            except (ValueError, TypeError):
                year = ""

        cover_url = ""
        cover = r.get("cover")
        if isinstance(cover, dict) and cover.get("url"):
            raw = cover["url"]
            if raw.startswith("//"):
                raw = "https:" + raw
            cover_url = raw.replace("t_thumb", "t_cover_big")

        # Two different escaping contexts here: json.dumps() for values
        # embedded inside the inline onclick="..." JS call (so titles
        # with apostrophes — "Assassin's Creed" — don't break out of the
        # JS string and throw a syntax error on click), and html_escape()
        # separately for the human-readable text actually shown on the
        # button.
        name_js = json.dumps(name)
        name_html = html_escape(name)
        year_html = f" ({year})" if year else ""

        # Inline onclick sets the hidden form fields directly.
        # No dependency on any external function or <script> block -
        # the JS runs entirely inside the onclick attribute, which is
        # immune to whatever syntax errors affect the main script block.
        onclick_js = (
            f"document.getElementById('add-game-title-hidden').value={name_js};"
            f"document.getElementById('add-game-igdb-hidden').value='{igdb_id}';"
            f"document.getElementById('igdb-search-input').value={name_js};"
            f"document.getElementById('igdb-results').innerHTML='';"
        )

        html += f"""
        <button
            type="button"
            onclick="{html_escape(onclick_js)}"
            class="w-full flex items-center gap-3 p-2 rounded-lg bg-gray-800/50 border border-cyan-500/10 hover:border-cyan-400/50 hover:bg-gray-800 transition text-left"
        >
            <div class="w-8 h-11 flex-shrink-0 rounded overflow-hidden bg-gray-700">
                {'<img src="' + cover_url + '" class="w-full h-full object-cover" />' if cover_url else '<div class="w-full h-full flex items-center justify-center text-xs">🎮</div>'}
            </div>
            <span class="text-sm text-white truncate">{name_html}{year_html}</span>
        </button>
        """

    return html


@admin_bp.route("/add-game-step2", methods=["POST"])
def add_game_step2():
    """
    Step 2 of the Add Game wizard: receive game name + storefronts
    from step 1, render the gamer ID pickers for each selected
    storefront. All server-rendered - no client-side JS needed.
    """
    title = request.form.get("title", "").strip()
    igdb_id = request.form.get("igdb_id", "").strip()
    selected_storefronts = request.form.getlist("storefronts")

    if not title:
        return _render_status("error", "Game name is required. Go back and enter a name.")

    if not selected_storefronts:
        return _render_status("error", "Select at least one storefront. Go back and check one.")

    # Filter to valid storefronts only
    selected_storefronts = [s for s in selected_storefronts if s in STOREFRONTS]

    if not selected_storefronts:
        return _render_status("error", "No valid storefronts selected.")

    # Fetch existing accounts for each selected storefront
    accounts_by_storefront = {}
    for storefront in selected_storefronts:
        platform = db.session.query(Platform).filter_by(name=storefront).first()
        if platform:
            accounts = db.session.execute(
                db.text("SELECT username FROM accounts WHERE platform_id = :pid ORDER BY username"),
                {"pid": platform.platform_id},
            ).fetchall()
            accounts_by_storefront[storefront] = [a[0] for a in accounts]
        else:
            accounts_by_storefront[storefront] = []

    return render_template(
        "_add_game_step2.html",
        title=title,
        igdb_id=igdb_id,
        selected_storefronts=selected_storefronts,
        accounts_by_storefront=accounts_by_storefront,
    )


@admin_bp.route("/add-game", methods=["POST"])
def add_game():
    """
    Create a game (optionally enriched from IGDB) and link it to every
    selected (storefront, gamer ID) combination in one go — covering the
    "same game on multiple storefronts" and "same storefront, two
    accounts" cases in a single submission.
    """
    title = request.form.get("title", "").strip()
    igdb_id = request.form.get("igdb_id", "").strip()

    if not title:
        return _render_status("error", "Game name is required.")

    # Collect selected storefronts and, for each, the gamer IDs checked
    # (existing) plus any free-text "new gamer ID" field filled in.
    # Field naming convention (set by _add_game_form.html /
    # _gamer_id_picker.html):
    #   storefronts            -> list of checked storefront names
    #   gamer_id__<safe_name>  -> list of checked existing usernames for that storefront
    #   new_gamer_id__<safe_name> -> free-text new username for that storefront
    selected_storefronts = request.form.getlist("storefronts")

    if not selected_storefronts:
        return _render_status("error", "Select at least one storefront.")

    # Build the full (storefront, username) pair list, deduplicated.
    pairs = []
    for storefront in selected_storefronts:
        if storefront not in _STOREFRONT_TABLE_MAP:
            continue
        safe_name = storefront.replace(".", "_").replace(" ", "_")

        usernames = set(request.form.getlist(f"gamer_id__{safe_name}"))

        new_username = request.form.get(f"new_gamer_id__{safe_name}", "").strip()
        if new_username:
            usernames.add(new_username)

        for username in usernames:
            pairs.append((storefront, username))

    if not pairs:
        return _render_status(
            "error",
            "Select at least one existing gamer ID or enter a new one for each chosen storefront."
        )

    try:
        # 1. Get or create the canonical game row.
        normalised = title.lower().strip()
        game = db.session.query(GameMaster).filter(
            db.func.lower(GameMaster.title) == normalised
        ).first()

        if not game:
            game = GameMaster(title=title, status="Not Started")
            if igdb_id:
                try:
                    game.igdb_id = int(igdb_id)
                except ValueError:
                    pass
            db.session.add(game)
            db.session.flush()  # get game.game_id without a full commit yet
        elif igdb_id and not game.igdb_id:
            # Existing game with no IGDB link yet — attach it now.
            try:
                game.igdb_id = int(igdb_id)
            except ValueError:
                pass

        # 2. For each (storefront, username) pair: get-or-create the
        #    Platform + Account, then insert an ownership row if one
        #    doesn't already exist for that account+game.
        created_count = 0
        skipped_count = 0

        for storefront, username in pairs:
            platform = db.session.query(Platform).filter_by(name=storefront).first()
            if not platform:
                platform = Platform(name=storefront)
                db.session.add(platform)
                db.session.flush()

            account = db.session.query(Account).filter_by(
                platform_id=platform.platform_id, username=username
            ).first()
            if not account:
                account = Account(
                    platform_id=platform.platform_id,
                    username=username,
                    display_name=username,
                )
                db.session.add(account)
                db.session.flush()

            model_cls, id_column = _STOREFRONT_TABLE_MAP[storefront]

            existing = db.session.query(model_cls).filter_by(
                account_id=account.account_id, game_id=game.game_id
            ).first()

            if existing:
                skipped_count += 1
                continue

            kwargs = {
                "account_id": account.account_id,
                "game_id": game.game_id,
            }
            if model_cls is OwnedGameSteam:
                # steam_appid is an Integer column (unlike every other
                # storefront's id column, which is a String) — match
                # import_games_from_excel.py's exact convention here.
                kwargs[id_column] = game.game_id
                kwargs["playtime_minutes"] = 0
            else:
                kwargs[id_column] = str(game.game_id)

            db.session.add(model_cls(**kwargs))
            created_count += 1

        db.session.commit()

        pairs_summary = ", ".join(f"{s}/{u}" for s, u in pairs)
        summary = f"Linked to {created_count} account(s): {pairs_summary}."
        if skipped_count:
            summary += f" ({skipped_count} already existed.)"

        return render_template(
            "_add_game_success.html",
            title=title,
            summary=summary,
        )

    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"[ERROR] add_game failed: {traceback.format_exc()}")
        return _render_status("error", f"Failed to add game: {str(e)}")


# ── Helpers ──────────────────────────────────────────────────

def _extract_summary(output: str) -> str:
    """Extract meaningful summary lines from script output."""
    if not output:
        return "Task completed."

    lines = output.strip().split("\n")
    summary_lines = []
    for line in lines[-15:]:
        line = line.strip()
        if line and ("✅" in line or "❌" in line or "⚠️" in line or "SUMMARY" in line
                     or "Total" in line or "Matched" in line or "imported" in line
                     or "Updated" in line or "processed" in line or "games now" in line):
            summary_lines.append(line)

    if summary_lines:
        return "<br>".join(summary_lines[-6:])
    elif lines:
        return "<br>".join(lines[-3:])
    return "Task completed."


def _render_status(status: str, message: str, task_id: str = None) -> str:
    """Render a status HTML fragment for htmx responses."""
    if status == "running":
        color = "cyan"
        icon = '<div class="spinner inline-block w-4 h-4 mr-2"></div>'
        poll = f' hx-get="/admin/task-status/{task_id}" hx-trigger="every 2s" hx-swap="outerHTML"' if task_id else ""
    elif status == "completed":
        color = "green"
        icon = "✅ "
        poll = ""
    elif status == "error":
        color = "red"
        icon = "❌ "
        poll = ""
    else:
        color = "gray"
        icon = ""
        poll = ""

    return f"""
    <div class="p-3 rounded-lg border border-{color}-500/30 bg-{color}-500/10 text-sm text-{color}-300"{poll}>
        {icon}{message}
    </div>
    """
