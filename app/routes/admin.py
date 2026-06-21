"""
Admin routes — upload Excel, fetch covers, manage GFN game IDs.
"""

import os
import subprocess
import threading
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, render_template, current_app
from app import db
from app.models import GfnGame, GameMaster

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# In-memory task tracker (simple; resets on restart)
_tasks = {}


def _run_script_background(task_id, script_args, app):
    """Run a Python script in background and track status."""
    _tasks[task_id]["status"] = "running"
    _tasks[task_id]["started_at"] = datetime.utcnow().isoformat()

    try:
        result = subprocess.run(
            ["python"] + script_args,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
            cwd="/app",
        )
        _tasks[task_id]["output"] = result.stdout[-3000:] if result.stdout else ""
        _tasks[task_id]["errors"] = result.stderr[-1000:] if result.stderr else ""

        if result.returncode == 0:
            _tasks[task_id]["status"] = "completed"
        else:
            _tasks[task_id]["status"] = "failed"

    except subprocess.TimeoutExpired:
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
        return _render_status("running", "Still working...", task_id=task_id)
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
