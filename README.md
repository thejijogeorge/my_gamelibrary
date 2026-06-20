# Game Library Project — Database & Schema Ready ✅

## What's built and tested

### 1. **Postgres Schema** (verified against live Postgres 16)
- ✅ `platforms` — Steam, Epic, GOG (and ready for platform #4+)
- ✅ `accounts` — multiple usernames per platform
- ✅ `games_master` — canonical game list (IGDB ID, title, cover, genres, release date)
- ✅ `owned_games_steam` — Steam-specific game ownership with playtime tracking
- ✅ `owned_games_epic` — Epic-specific game ownership
- ✅ `owned_games_gog` — GOG-specific game ownership
- ✅ `gfn_games` — GeForce Now availability + deeplink URLs
- ✅ `vw_owned_games_unified` — A SQL view that UNIONs all platform tables into one query-friendly shape

**Why this design:**
- Each platform table is isolated (they have genuinely different identifiers: Steam = appid integer, Epic = namespace + item_id, GOG = product_id)
- The unified view lets Flask query one source instead of writing complex UNIONs
- Adding platform #4 means: write a new table (e.g., `owned_games_xbox`), add it to the view definition, done — no Flask code changes

### 2. **Flask App Structure**

```
gamelibrary/
├── Dockerfile                          # Production-ready (gunicorn)
├── docker-compose.yml                  # ❌ Not yet created — see "Next Steps"
├── requirements.txt                    # All deps pinned
├── config.py                           # Environment-driven config (DATABASE_URL, etc.)
├── wsgi.py                             # App entry point
├── app/
│   ├── __init__.py                     # Flask app factory (create_app)
│   ├── models.py                       # All 9 SQLAlchemy models
│   ├── routes/
│   │   ├── __init__.py
│   │   └── games.py                    # ❌ Placeholder — full htmx endpoints go here
│   ├── ingestion/                      # ❌ Empty — Steam/Epic/GOG sync modules go here
│   │   └── __init__.py
│   └── matching/                       # ❌ Empty — IGDB fuzzy-matching logic goes here
│       └── __init__.py
├── migrations/                         # Alembic migrations (tested against Postgres)
│   ├── env.py
│   ├── versions/
│   │   ├── 2d802ec2e524_initial_schema.py       # Creates all 7 tables
│   │   └── 72f65884cab5_unified_owned_games_view.py  # Creates vw_owned_games_unified
└── templates/                          # ❌ Empty — Jinja2 + htmx templates go here
    └── (base.html, games_grid.html, games_list.html, _filters.html, _game_card.html)
```

### 3. **Key Design Principles**

**Modularity for new platforms:**
- Each platform inherits the same pattern (platform table → account rows → owned_games_* rows)
- The unified view's SQL is straightforward to extend (just add a UNION ALL block)
- Flask routes read from the view, so they never need updating

**Normalized schema:**
- games_master is the source of truth for game metadata (title, cover, IGDB ID)
- Owned games link to games_master.game_id, not storing redundant data
- One account_id uniquely identifies a user on a specific platform
- Unique constraints prevent duplicate entries (e.g., can't own the same game twice on Steam under one account)

**Production-ready config:**
- All secrets/connection strings come from environment variables (`.env` file, not code)
- DATABASE_URL format: `postgresql://user:pass@host:5432/dbname`
- Same image works locally, in docker-compose, and in cloud (just swap the env)

---

## Next Steps (in order)

### Phase 1️⃣: Flask App + Templates (ready to build)
- [ ] Create `docker-compose.yml` with `db` (Postgres) and `web` (Flask) services
- [ ] Write base.html (Jinja2 template with htmx script tag + CSS)
- [ ] Write games_grid.html and games_list.html (the two view modes)
- [ ] Build `/games` route in `routes/games.py` to fetch from `vw_owned_games_unified`
- [ ] Wire up htmx buttons for grid/list toggle and per-column filtering
- [ ] Add `.env.example` with `DATABASE_URL`, `SECRET_KEY`, etc.

### Phase 2️⃣: Steam Ingestion (most important — it's fully automatable)
- [ ] `ingestion/steam.py` — SteamSync class
  - Fetch user's library via Steam API (needs SteamID + API key)
  - Extract appid, title, playtime_minutes, last_played
  - Upsert into `owned_games_steam`
- [ ] `matching/matcher.py` — fuzzy match Steam titles against IGDB
  - For each steam appid, search IGDB by title
  - Update owned_games_steam.game_id once matched
  - Flag any unmatched (manual review needed)

### Phase 3️⃣: Epic/GOG Ingestion (less automatable — manual fallback)
- [ ] `ingestion/epic.py` — Use `legendary` CLI (reverse-engineered, unofficial but works)
- [ ] `ingestion/gog.py` — Use unofficial GOG endpoint or manual CSV import
- [ ] Manual add/edit routes in Flask for when APIs fail or are missing

### Phase 4️⃣: GeForce Now Integration
- [ ] Seed `gfn_games` table from NVIDIA's published list (can do manually or write scraper)
- [ ] Map each GFN game to games_master.game_id
- [ ] Populate the `available_on_steam/epic/gog` flags
- [ ] Front-end: add "Launch via GFN" button when `is_on_gfn = true`

### Phase 5️⃣: UI Polish + Gamer Theme
- [ ] Glassmorphism/neon CSS (dark background, frosted glass cards, platform-colored badges)
- [ ] Responsive grid → list toggle (htmx + Tailwind)
- [ ] Per-column filters (account, platform, genre, etc.)
- [ ] Add/edit modal for manual game entries
- [ ] Icons for platforms (Steam logo, Epic logo, etc.)

### Phase 6️⃣: Containerize + Deploy
- [ ] Test `docker-compose up` locally
- [ ] Write production `.env` for your server's Postgres
- [ ] Push to Docker Hub as `thejijogeorge/game-library:latest`
- [ ] Deploy to your server (docker pull + docker-compose up)

---

## Running Locally (right now)

1. **Prerequisites:** Docker + docker-compose (or Postgres 16 + Python 3.12+)

2. **Without Docker (local dev):**
   ```bash
   # Create a .env file
   export DATABASE_URL="postgresql://gameapp:gameapp@localhost:5432/gamelibrary"
   export FLASK_APP=wsgi.py
   export FLASK_DEBUG=1

   pip install -r requirements.txt
   flask db upgrade          # Apply migrations (assumes Postgres is running)
   flask run                 # Visit http://localhost:5000
   ```

3. **With Docker (coming next):**
   ```bash
   docker-compose up
   # Postgres starts, migrations run automatically, Flask starts
   # Visit http://localhost:5000
   ```

---

## Migration Notes

The schema comes with two migrations (in `/migrations/versions/`):

- **2d802ec2e524_initial_schema.py** — Creates all 7 tables with foreign keys, unique constraints, indexes
- **72f65884cab5_unified_owned_games_view.py** — Creates the `vw_owned_games_unified` view

To roll back:
```bash
flask db downgrade  # Reverses to before migration 1
flask db upgrade    # Re-applies both
```

---

## Key Files to Reference

| File | Purpose |
|------|---------|
| `models.py` | All SQLAlchemy table definitions — add new columns here when schema changes |
| `config.py` | Environment-based config — update for deployment |
| `wsgi.py` | Entry point — gunicorn calls this in production |
| `migrations/versions/*.py` | Schema change history — version control these! |

---

## Questions?

- **"How do I add a new platform?"** → Create `owned_games_newplatform` table in models.py, run `flask db migrate`, add a UNION block to `vw_owned_games_unified` migration
- **"Where's the IGDB matcher?"** → In `/matching/` (empty for now, Phase 2️⃣)
- **"How do I deploy this?"** → Push the `gamelibrary/` folder to your server, update `.env`, run `docker-compose up -d`
- **"Can I switch databases later?"** → Yes — as long as you use SQLAlchemy ORM, just change `DATABASE_URL` in `.env` to point to a different Postgres (or another compatible dialect like MySQL, though Postgres is the validated target)

---

**Status:** Database schema is production-ready. Flask skeleton is in place. Ready for Phase 1️⃣ (UI + Flask routes).

