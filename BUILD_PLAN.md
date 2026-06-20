# Game Library Project — Complete Build Plan

## Executive Summary

You're building a personal game inventory system that:
1. **Aggregates** games you own across Steam, Epic, GOG into a single view
2. **Enriches** that data with IGDB metadata (cover art, genres, release date)
3. **Marks** which games are playable on GeForce Now (with direct launch links)
4. **Stores** everything in Postgres using a modular schema that scales to new platforms
5. **Serves** it via Flask + htmx on a gamer-themed UI
6. **Deploys** as a Docker container for personal use or eventual monetization

---

## Architecture Decisions & Rationale

### Database: Postgres + Flask-SQLAlchemy

**Why Postgres?**
- Multi-arch Docker support (amd64 AND ARM — future-proof for any hardware)
- No licensing restrictions (unlike SQL Server Express)
- Cleaner driver story (`psycopg2-binary` vs MS ODBC + `pyodbc`)
- Rock-solid migration tooling (Alembic)

**Why separate platform tables?**
Each storefront has fundamentally different data:
- Steam: numeric appid, playtime_minutes, last_played
- Epic: namespace + item_id (both strings), no playtime data available
- GOG: product_id, different metadata

Putting them in separate tables keeps queries clean and performance predictable.

**Why a unified view?**
The view (`vw_owned_games_unified`) UNIONs all platforms into one queryable shape.
- Flask routes query one source, not three
- Adding platform #4 means extend the view's SQL, not rewrite the app

### Backend: Flask + htmx

**Why Flask over FastAPI?**
- You asked for Flask explicitly
- Flask + Jinja2 templates + htmx is a proven, lightweight pattern
- Simpler to deploy (one Python process, no separate API/frontend split)
- Perfect for personal projects that might become production SaaS

**Why htmx?**
- Zero JavaScript to maintain for core filtering/view-toggling
- Server sends back partial HTML fragments, htmx swaps them in-place
- All business logic (filtering, sorting) lives in Python — easier to maintain

### Data Flow

```
[Your Steam Library] → SteamSync (Python API client)
[Your Epic Library]  → EpicSync (legendary CLI wrapper)
[Your GOG Library]   → GogSync (unofficial endpoint)
                        ↓
                  Matcher (fuzzy match vs IGDB)
                        ↓
              [Postgres: owned_games_steam/epic/gog]
                        ↓
          [Postgres: vw_owned_games_unified (VIEW)]
                        ↓
              Flask routes → Jinja2 templates
                        ↓
           [Browser: Grid/List + htmx filtering]
                        ↓
      [GFN deeplinks: button click → cloud streaming]
```

---

## Schema Design (Already Built ✅)

### Tables

**`platforms`** — Seed with Steam, Epic, GOG; add new rows for platform #4+
- `platform_id (PK)`, `name (UNIQUE)`

**`accounts`** — Your usernames per platform (supports multiples)
- `account_id (PK)`, `platform_id (FK)`, `username (UNIQUE per platform)`, `display_name`

**`games_master`** — Canonical game list (IGDB as source of truth)
- `game_id (PK)`, `igdb_id (UNIQUE)`, `title`, `slug`, `cover_url`, `first_release_date`, `genres`
- Indexed on `title` for fuzzy-matching performance

**`owned_games_steam`** — Your Steam library
- `account_id (FK)`, `game_id (FK→games_master)`, `steam_appid (UNIQUE per account)`, `playtime_minutes`, `last_played`

**`owned_games_epic`** — Your Epic library
- `account_id (FK)`, `game_id (FK→games_master)`, `epic_namespace`, `epic_item_id (UNIQUE per account)`

**`owned_games_gog`** — Your GOG library
- `account_id (FK)`, `game_id (FK→games_master)`, `gog_product_id (UNIQUE per account)`

**`gfn_games`** — GeForce Now catalog
- `game_id (FK→games_master, UNIQUE)`, `available_on_steam`, `available_on_epic`, `available_on_gog`, `gfn_deeplink_url`

**`vw_owned_games_unified` (VIEW)** — Your unified library
Queries all platform tables with UNION ALL:
```
SELECT game_id, title, platform_name, account_username, platform_specific_id,
       playtime_minutes, is_on_gfn, gfn_deeplink_url
FROM (
  SELECT ... FROM owned_games_steam
  UNION ALL
  SELECT ... FROM owned_games_epic
  UNION ALL
  SELECT ... FROM owned_games_gog
)
```

### Why This Design

| Question | Answer |
|----------|--------|
| Why separate tables per platform? | Data shapes are genuinely different; allows indexing/constraints specific to each storefront |
| Why nullable `game_id`? | A game can be ingested before the IGDB matcher links it to games_master |
| Why a view instead of app-side UNIONs? | Database handles it once; faster for repeated queries; cleaner SQL |
| How do I add platform #4? | (1) Create `owned_games_xbox` table, (2) Add UNION block to view, (3) Done — no Flask code changes |

---

## Build Phases (In Order)

### Phase 1️⃣: Flask App + Templates (Your Next Task)

**Deliverable:** A working web app showing all games in grid or list view, with filter buttons

**Tasks:**
1. Create `docker-compose.yml` ← **Already done, in `/mnt/user-data/outputs/gamelibrary/`**
2. Create `base.html` (Jinja2, imports htmx + Tailwind CSS)
3. Create `games_grid.html` (CSS grid of game cards)
4. Create `games_list.html` (table of games)
5. Implement `/games` route in Flask:
   - Reads query params: `view` (grid|list), `filter_platform`, `filter_account`, `search_title`, etc.
   - Queries `vw_owned_games_unified` with SQLAlchemy ORM
   - Returns HTML fragment for the game container
6. Implement `/` route: render base.html + initial games

**Styling:** 
- Dark background (gamer theme)
- Glassmorphism cards (frosted glass effect, platform-colored borders)
- Neon accents (cyan, magenta, green for different sections)
- Platform badges (Steam blue, Epic black, GOG gold)
- Smooth htmx swaps (fade-in on filter change)

**Example htmx markup:**
```html
<button hx-get="/games?view=grid" hx-target="#games" hx-push-url="true">
  Grid View
</button>
<input type="search" name="search_title" 
       hx-get="/games" hx-target="#games" 
       hx-trigger="keyup changed delay:300ms"
       placeholder="Search games...">
<div id="games"><!-- Initial games load here --></div>
```

**What you'll see when it's done:**
- http://localhost:5000 loads with all games from DB
- Click "Grid View" → cards rearrange (htmx swap)
- Type in search box → filters live (htmx refetch with params)
- Dropdown by platform → re-filters

### Phase 2️⃣: Steam Ingestion (Most Important)

**Why steam first?** It's fully automatable — no unofficial APIs, no broken endpoints.

**Deliverable:** A background job that pulls your Steam library and populates `owned_games_steam`

**Tasks:**
1. Get your Steam API key: https://steamcommunity.com/dev/apikey
2. Find your SteamID: https://steamid.io/ (64-bit version)
3. Write `ingestion/steam.py`:
   ```python
   class SteamSync:
       def __init__(self, api_key, steam_id):
           self.api = SteamClient(api_key, steam_id)
       
       def fetch_owned_games(self):
           # Call Steam API → returns list of (appid, title, playtime_minutes)
           
       def upsert_to_db(self, games):
           # INSERT OR UPDATE owned_games_steam
   ```
4. Write `matching/matcher.py` — fuzzy match game titles to IGDB
   - For each Steam game, search IGDB by title
   - Find best match (use `fuzz.token_set_ratio` from `rapidfuzz` library)
   - Update `owned_games_steam.game_id` with the match
5. Flask route `/sync/steam` (admin-only, triggers a sync)
6. Optional: APScheduler to run nightly

**What you'll see when it's done:**
- Run `/sync/steam` → fetches your library, matches to IGDB, populates DB
- All your Steam games appear in the web UI
- Click one → shows playtime, last played, cover art from IGDB

### Phase 3️⃣: Epic & GOG Ingestion (Trickier)

**Why harder?** Epic/GOG don't have official third-party APIs.

**For Epic:**
- Use the open-source `legendary` CLI (unofficial, but battle-tested)
- Wrapper script in Python that calls `legendary list-games --json`
- Ingests output into `owned_games_epic`

**For GOG:**
- Two options:
  1. Use the unofficial GOG Galaxy embed (fragile, may break)
  2. Manual CSV import: export your GOG library, upload CSV, parse + ingest
- Second option is safer for a production app

**Fallback:** Manual add/edit UI in Flask so you can add games by hand if sync fails

### Phase 4️⃣: GeForce Now Integration

**Deliverable:** A flag on each game showing "Playable on GFN?" + a launch button

**Tasks:**
1. Get NVIDIA's GFN game list (they publish it periodically):
   - Option A: Scrape from their website
   - Option B: Manual maintenance (simpler, more reliable)
2. Seed `gfn_games` table with (game_title, is_on_gfn, deeplink_url)
3. Match GFN games to `games_master` by fuzzy title match
4. UI: add button "Launch on GeForce Now" → opens GFN deeplink in new tab

**Example deeplink:** `https://play.geforcenow.com/launch/hades` → boots Hades via streaming

### Phase 5️⃣: UI Polish + Gamer Theme

**Deliverable:** A visually cohesive, gamer-aesthetic interface

**Design Tokens:**
- **Background:** #0a0e27 (very dark blue, easier on eyes than pure black)
- **Accent 1 (Steam):** #1b2838 (Steam's dark blue) + #00a0df (bright cyan)
- **Accent 2 (Epic):** #000000 + #252f3f (Epic purple)
- **Accent 3 (GOG):** #2d2d2d + #c5a000 (gold)
- **GFN highlight:** #00d98e (neon green)

**Components:**
- Glassmorphism cards: `backdrop-filter: blur(10px)`, semi-transparent white background
- Platform badges: chip-style with platform color + icon
- Grid: CSS Grid, responsive (auto-fit, minmax(250px, 1fr))
- List: table with row hover effect
- Filters: floating bar, sticky at top (htmx-powered)

**Nice-to-haves:**
- Parallax scroll on cover art
- Hover animations (card lifts, cover blurs slightly)
- Loading spinners during htmx swaps
- Dark mode toggle (just CSS vars)

### Phase 6️⃣: Containerize + Deploy

**Deliverable:** Running on your server

**Tasks:**
1. Test locally: `docker-compose up`
2. Create `.env` with production DATABASE_URL (your server's Postgres)
3. Build image: `docker build -t thejijogeorge/game-library:latest .`
4. Push to Docker Hub: `docker push thejijogeorge/game-library:latest`
5. On your server:
   ```bash
   docker pull thejijogeorge/game-library:latest
   docker-compose up -d
   ```
6. Verify: `http://server-ip:5000`

---

## File Structure (Ready to Go)

```
gamelibrary/
├── Dockerfile                          # ✅ Built
├── docker-compose.yml                  # ✅ Built
├── .env.example                        # ✅ Built
├── .gitignore                          # ✅ Built
├── requirements.txt                    # ✅ Built
├── config.py                           # ✅ Built (env-driven)
├── wsgi.py                             # ✅ Built (gunicorn entry point)
├── README.md                           # ✅ Built (you're reading its sibling)
│
├── app/
│   ├── __init__.py                     # ✅ Flask factory
│   ├── models.py                       # ✅ All 9 SQLAlchemy models
│   │
│   ├── routes/
│   │   ├── __init__.py                 # ✅
│   │   └── games.py                    # 🚧 Phase 1: Add /games, / routes
│   │
│   ├── ingestion/
│   │   ├── __init__.py                 # ✅
│   │   ├── steam.py                    # 🚧 Phase 2: SteamSync class
│   │   ├── epic.py                     # 🚧 Phase 3: EpicSync class
│   │   └── gog.py                      # 🚧 Phase 3: GogSync class
│   │
│   ├── matching/
│   │   ├── __init__.py                 # ✅
│   │   └── matcher.py                  # 🚧 Phase 2: IGDB matching
│   │
│   ├── templates/
│   │   ├── base.html                   # 🚧 Phase 1: Jinja2 + htmx + Tailwind
│   │   ├── games_grid.html             # 🚧 Phase 1: CSS grid layout
│   │   ├── games_list.html             # 🚧 Phase 1: table layout
│   │   ├── _filters.html               # 🚧 Phase 1: htmx filter partial
│   │   └── _game_card.html             # 🚧 Phase 1: game card partial
│   │
│   └── static/
│       ├── css/
│       │   └── style.css               # 🚧 Phase 5: gamer theme
│       └── js/
│           └── (htmx is in base.html CDN, no custom JS needed)
│
└── migrations/
    ├── env.py                          # ✅ Alembic config
    └── versions/
        ├── 2d802ec2e524_initial_schema.py              # ✅ Tables
        └── 72f65884cab5_unified_owned_games_view.py    # ✅ View
```

---

## Modularity for Future Platform #4

When you want to add, say, Xbox Game Pass, do this:

1. **Add to models.py:**
   ```python
   class OwnedGameXbox(db.Model):
       __tablename__ = "owned_games_xbox"
       id = db.Column(db.Integer, primary_key=True)
       account_id = db.Column(db.Integer, db.ForeignKey("accounts.account_id"))
       game_id = db.Column(db.Integer, db.ForeignKey("games_master.game_id"), nullable=True)
       xbox_product_id = db.Column(db.String(100), unique=True)
       # ... etc
   ```

2. **Create migration:**
   ```bash
   flask db migrate -m "add xbox platform"
   ```

3. **Update view in a new migration:**
   - Add UNION ALL block to `vw_owned_games_unified`

4. **Add sync class:**
   ```python
   # ingestion/xbox.py
   class XboxSync:
       def fetch_owned_games(self): ...
       def upsert_to_db(self, games): ...
   ```

5. **Wire into Flask:**
   ```python
   # routes/sync.py
   @app.route("/sync/xbox", methods=["POST"])
   def sync_xbox():
       sync = XboxSync(...)
       sync.upsert_to_db(sync.fetch_owned_games())
       return "OK"
   ```

**That's it.** The view queries work unchanged. The /games route works unchanged. Filtering works unchanged.

---

## Production Readiness Checklist

- ✅ **Database:** Postgres 16, schema tested against live instance
- ✅ **Config:** Environment-driven, no secrets in code
- ✅ **Migrations:** Alembic versioned, tested, reversible
- ✅ **Containerization:** Dockerfile + docker-compose, healthchecks
- ✅ **Serving:** Gunicorn (not Flask dev server)
- ✅ **Modularity:** Each platform is isolated, adding new ones is straightforward
- 🚧 **UI:** Gamer theme, htmx-powered, responsive
- 🚧 **Sync jobs:** Nightly Steam/Epic/GOG pulls (optional APScheduler)
- 🚧 **Error handling:** Graceful failures if APIs are down
- 🚧 **Logging:** Track syncs, matches, misses

---

## Key Technologies & Why

| Tech | Purpose | Why |
|------|---------|-----|
| PostgreSQL 16 | Database | Multi-arch, no licensing, great migrations |
| Flask 3.1 | Web framework | Lightweight, templating native, htmx-friendly |
| SQLAlchemy 3.1 | ORM | Type-safe queries, automatic migrations |
| Alembic | Schema versioning | Production migrations, reversible |
| htmx 2.0 | Client-side interactivity | Zero JavaScript, server-side logic only |
| Tailwind CSS | Styling | Utility-first, gamer theme easy to customize |
| Docker & Compose | Containerization | Reproducible deployments, same image everywhere |
| Gunicorn | WSGI server | Production-grade, handles concurrency |

---

## Estimated Time Per Phase

| Phase | Tasks | Est. Hours | Notes |
|-------|-------|-----------|-------|
| 1 | Flask routes + templates | 4–6 | CSS + htmx learning curve, but straightforward |
| 2 | Steam sync + IGDB matcher | 6–8 | Most complex part; API integration + fuzzy matching |
| 3 | Epic/GOG + manual import | 4–6 | Simpler if using manual CSV; legendary CLI adds complexity |
| 4 | GFN integration | 2–3 | Mostly data entry + linking |
| 5 | UI polish | 3–5 | Design iteration, animations |
| 6 | Deploy + test | 2–3 | Documentation, on-server testing |
| **Total** | | **21–31 hours** | Spread over several weeks; can be done part-time |

---

## Questions Before You Start Phase 1?

- **"Should I use Tailwind CSS?"** → Recommended for speed; custom CSS works too
- **"Do I need TypeScript?"** → No; htmx + server-side rendering means minimal client logic
- **"How do I auth the `/sync/*` routes?"** → Simple decorator: require a secret key in the request
- **"Can I add game reviews/ratings?"** → Yes; add columns to `games_master` and extend the UI
- **"What if IGDB matching fails?"** → Gracefully skip, keep the game in DB, flag for manual review

---

**Next:** Choose Phase 1 tasks and start building the web interface. Let me know what you want to tackle first!
