# Game Library — Server Deployment Guide

A personal game aggregator that pulls games from Steam, Epic Games, and GOG with GeForce NOW streaming integration, game status tracking, and sorting/filtering options. Deploy to your own server with Docker.

## 📋 Prerequisites

- **Docker & Docker Compose** installed on your server
- **IGDB API credentials** (Twitch Client ID & Secret) — [Get them free](https://dev.twitch.tv/console/apps)
- **Game library Excel file** (in the format specified below)
- Server with at least **2GB RAM** and **5GB storage**

---

## 🚀 Quick Start (5 Minutes)

### **Step 1: Prepare Your Files**

```bash
mkdir -p ~/my_gamelibrary
cd ~/my_gamelibrary
```

Copy these files to the directory:
- `docker-compose.deploy.yml` → rename to `docker-compose.yml`
- `.env.example` → rename to `.env` and fill in credentials

### **Step 2: Configure Environment**

Edit `.env` with your IGDB credentials:

```bash
nano .env
```

Add:
```
IGDB_CLIENT_ID=your_twitch_client_id
IGDB_ACCESS_TOKEN=your_twitch_client_secret
FLASK_ENV=production
SECRET_KEY=generate-a-random-secret-key-here
```

### **Step 3: Start Docker Containers**

```bash
sudo docker compose up -d
```

Wait for all services to be healthy:
```bash
sudo docker compose ps
```

Both containers should show `Up` status. ✅

### **Step 4: Import Games & Fetch Covers (via Web UI)**

Open your browser:
```
http://your-server-ip:5000
```

1. Click the **⚙️ Admin** button in the top-right
2. **Upload your Excel file** under "📤 Import Games"
3. Click **"Fetch Missing Covers"** under "🖼️ Cover Art & Details"
4. Click **"Fetch Game Details"** to get summaries, ratings, themes, etc.
5. Click **"Populate GFN URLs"** under "☁️ GeForce NOW"

All tasks run in the background — status updates appear in real-time! 🎮

---

## 📊 Features

### **Core**
- ✅ Multi-platform game aggregator — **7 storefronts**: Steam, Epic Games, GOG, EA, Battle.net, Ubisoft
- ✅ Beautiful cover art — High-resolution (t_1080p) from IGDB
- ✅ Real-time filtering — Search, filter by platform/account/status
- ✅ Grid & list views — Choose your preferred layout
- ✅ Responsive design — Works on mobile & desktop
- ✅ Dark gamer theme — Glassmorphism UI with neon accents

### **Game Tracking**
- ✅ **Status tracking** — Track games as: Not Started, Started, Completed
- ✅ **Status filter** — Show only games by status (great for backlog management!)
- ✅ **Quick status change** — Click Info → dropdown to update instantly from the modal
- ✅ **Status badges** — Visual indicators on every game card

### **Admin Panel (⚙️)**
- ✅ Upload Excel via browser — Simple 3-column format, no more manual CLI imports
- ✅ One-click cover art fetch — Pulls covers from IGDB automatically
- ✅ Fetch game details — Summaries, ratings (0-100), themes, game modes, developers/publishers
- ✅ GFN URL population — Sets launch URLs for all GFN-available games
- ✅ GFN toggle per game — Enable/disable GeForce NOW availability directly in the Info modal
- ✅ Remove duplicates — Cleans up duplicate game+storefront+gamerID combinations

### **Sorting & Filtering**
- ✅ **Filter by**: Platform, Account, Status, GFN availability
- ✅ **Search**: Real-time game name search
- ✅ **Sort by**: 
  - Name (A-Z)
  - Rating (High to Low)
  - Release Date (Newest)
  - Status

### **GeForce NOW Integration (☁️)**
- ✅ Enable/disable GFN per game in the modal
- ✅ Launch on GFN buttons — Every GFN-enabled game has a launch button
- ✅ Direct deep links — Games with assigned UUIDs launch directly into GFN
- ✅ Fallback support — Games without UUIDs open the GFN web app
- ✅ GFN-only filter — Show only games available on GeForce NOW

---

## 📥 Game Import Format

Your Excel file should have **3 columns** in the first sheet:

| Game Name | Storefront | Gamer ID |
|-----------|-----------|----------|
| Baldur's Gate 3 | Steam | jijo_george_max |
| Cyberpunk 2077 | Epic | Geekstradamus01 |
| The Witcher 3 | GOG | jijo_george |
| Elden Ring | Steam | jijo_george_max |
| Starfield | EA | myeaaccount |
| Overwatch 2 | Battle.net | MyBattleTag |
| Assassin's Creed | Ubisoft | myubisoftname |

### **Column Details:**

- **Game Name**: Exact game title (used to match against IGDB)
- **Storefront**: One of:
  - `Steam`
  - `Epic` / `Epic Games` / `Epic Games Store`
  - `GOG` / `GOG.com`
  - `EA` / `EA Play` / `Origin`
  - `Battle.net` / `Battlenet` / `Blizzard`
  - `Ubisoft` / `Ubisoft Connect` / `Uplay`
- **Gamer ID**: Your account username on that storefront

### **Example Excel Setup:**

```
Row 1:  Game Name | Storefront | Gamer ID
Row 2:  Hades | Steam | mysteamname
Row 3:  Fortnite | Epic | myepicusername
Row 4:  Baldur's Gate 3 | GOG | mygogusername
```

**Optional**: Include a "GeForce NOW Catalog" sheet with columns `No.`, `Title`, `Publisher`, `Available Store(s)` for GFN catalog data (same format as before).

### **Import Safety:**

- **Re-importing is safe** — existing games are detected and skipped
- **No duplicates** — same game+storefront+gamerID won't be added twice
- **Automatic deduplication** — use the "Remove Duplicates" button to clean up

---

## 🎮 Admin Panel Guide

Click the **⚙️ Admin** button in the header to open the management panel.

### **📤 Import Games**

Upload your 3-column Excel file directly from the browser. The import script runs in the background with **live progress updates**:

```
[123/500] Importing: Baldur's Gate 3 (Steam/myaccount)
  ✅ Added
[124/500] Importing: Cyberpunk 2077 (Epic/myaccount)
  ✅ Added
```

### **🖼️ Cover Art & Details**

Two buttons for different scenarios:

- **"Fetch Missing Covers"** — Games with NO IGDB data → searches by title, gets covers + all metadata
- **"Fetch Game Details"** — Games that already have covers → fills in summary, ratings, themes, etc.

Both support **live progress** so you know what's being processed.

### **☁️ GeForce NOW URLs**

Click "Populate GFN URLs" to set launch URLs for all games in the GFN catalog. Games get a fallback URL to the GFN web app by default.

Click **"Remove Duplicates"** to clean up any duplicate game+storefront+gamerID combinations.

### **🎯 Enable/Disable GFN Per Game**

In the game's **Info modal** (click the Info button):

```
GeForce NOW:  [toggle switch]  Enabled/Disabled    [☁️ Launch]
```

- **Toggle ON** → game appears in GFN-only filter, shows launch button
- **Toggle OFF** → game removed from GFN listings

Great for marking games as GFN-playable without using the admin bulk tools!

---

## 🔄 Game Status Tracking

Every game has a **Status** field: **Not Started**, **Started**, or **Completed**.

### **Set Status:**

1. Click **Info** on any game
2. Use the **Status** dropdown to select:
   - **⏸️ Not Started** — Haven't played yet (default for new imports)
   - **🎮 Started** — Currently playing
   - **✅ Completed** — Finished

### **Filter by Status:**

Use the **Status** filter in the main filter bar to show only games in a specific state. Perfect for:
- Viewing your **backlog** (Not Started)
- Seeing what you're **actively playing** (Started)
- Celebrating **finished games** (Completed)

### **Status Badges:**

Games display status badges on their cards:
- **Gray** — Not Started
- **Yellow** — Started
- **Green** — Completed

---

## 🔀 Sorting Options

Click the **"Sort By"** dropdown to organize your library:

| Option | Behavior |
|--------|----------|
| **Name (A-Z)** | Alphabetical order |
| **Rating (High-Low)** | Games sorted by IGDB user ratings (100 = highest) |
| **Release Date (Newest)** | Most recent releases first |
| **Status** | Groups by status (Not Started → Started → Completed) |

---

## 📁 Project Structure

```
my_gamelibrary/
├── docker-compose.yml          ← Rename from docker-compose.deploy.yml
├── .env                        ← Your credentials & secrets
├── app/
│   ├── __init__.py             ← App factory with admin blueprint
│   ├── models.py               ← Database models (includes status column)
│   ├── routes/
│   │   ├── games.py            ← Game display, filtering, sorting, status update
│   │   └── admin.py            ← Admin panel routes (upload, covers, GFN toggle, dedup)
│   ├── templates/
│   │   ├── index.html          ← Main page with admin panel & filters
│   │   ├── _games_grid.html    ← Grid view partial
│   │   ├── _games_list.html    ← List view partial
│   │   ├── _game_detail.html   ← Game info modal with status & GFN toggle
│   │   └── _gfn_toggle.html    ← GFN enable/disable switch
│   └── static/css/style.css    ← Gamer theme
├── scripts/
│   ├── import_games_from_excel.py    ← Import from simplified Excel
│   ├── fetch_igdb_metadata.py        ← Fetch covers & details from IGDB
│   ├── populate_gfn_game_ids.py      ← Set GFN launch URLs
│   ├── deduplicate_games.py          ← Remove duplicate entries
│   └── clear_cover_urls.py           ← Clear covers for re-fetch
├── data/
│   └── gfn_game_ids.json             ← Community GFN UUID database
├── migrations/                        ← Database schema & updates
├── Dockerfile
├── config.py
├── wsgi.py
└── requirements.txt
```

---

## 🔧 Common Commands

### **View Logs**
```bash
sudo docker compose logs -f web
```

### **Access Database**
```bash
sudo docker compose exec db psql -U gameapp -d gamelibrary
```

### **Check Game Count**
```bash
sudo docker compose exec db psql -U gameapp -d gamelibrary \
  -c "SELECT COUNT(*) FROM vw_owned_games_unified;"
```

### **Check Games by Status**
```bash
sudo docker compose exec db psql -U gameapp -d gamelibrary \
  -c "SELECT status, COUNT(*) FROM games_master GROUP BY status;"
```

### **Remove Duplicate Games**
```bash
sudo docker compose exec web python scripts/deduplicate_games.py --yes
```

### **Clear & Re-fetch Covers**
```bash
sudo docker compose exec web python scripts/clear_cover_urls.py
sudo docker compose exec web python scripts/fetch_igdb_metadata.py
```

### **Stop the App**
```bash
sudo docker compose down
```

### **Stop & Delete All Data**
```bash
sudo docker compose down -v
```

---

## 🔐 Security Notes

### **Before Production:**

1. **Change SECRET_KEY** in `.env`:
   ```bash
   openssl rand -hex 32
   ```

2. **Change database password** in `.env` and `docker-compose.yml`:
   ```
   POSTGRES_PASSWORD=your-strong-password
   ```

3. **Use HTTPS** (recommended):
   - Set up Nginx reverse proxy with SSL
   - Run Gunicorn on localhost only, proxy through Nginx

4. **Restrict access** to port 5000:
   ```bash
   sudo ufw allow 5000/tcp  # Or restrict to specific IPs
   ```

5. **Regular backups**:
   ```bash
   sudo docker compose exec db pg_dump -U gameapp gamelibrary > backup.sql
   ```

---

## 🐛 Troubleshooting

### **"Internal Server Error"**

Check logs:
```bash
sudo docker compose logs web
```

Common causes:
- Database migrations didn't run: `sudo docker compose exec web flask db upgrade`
- Missing `.env` variables: Verify all IGDB credentials are set
- Database connection failed: Ensure `db` container is healthy

### **"Authorization Failure" from IGDB**

Your IGDB credentials are wrong or expired:
1. Go to https://dev.twitch.tv/console/apps
2. Re-copy Client ID and Secret
3. Update `.env`
4. Restart: `sudo docker compose restart web`

### **"No results found" for games**

This is normal for niche/indie games. IGDB doesn't have everything. Popular AAA games should have covers.

### **Admin panel tasks stuck on "running"**

Tasks have a 10-minute timeout. If stuck:
1. Check logs: `sudo docker compose logs web`
2. Restart: `sudo docker compose restart web`

### **Database stuck or corrupted**

Nuke and restart (you'll lose all data):
```bash
sudo docker compose down -v
sudo docker compose up -d
```

Then re-import via the Admin panel.

---

## 🔄 Update Process

When new versions are released:

```bash
# Pull latest image
sudo docker compose pull

# Restart with new image
sudo docker compose up -d

# Migrations run automatically
# Your game data is preserved!
```

---

## 🏗️ Build & Push (For Developers)

```bash
# Build with dual tags
docker build -t thejijogeorge/gamelibrary-web:latest -t thejijogeorge/gamelibrary-web:2.2.0 .

# Push to Docker Hub
docker push thejijogeorge/gamelibrary-web:latest
docker push thejijogeorge/gamelibrary-web:2.2.0
```

---

## 📝 Version History

| Version | Features |
|---------|----------|
| **2.3.0** | Added EA, Battle.net, and Ubisoft storefronts (7 total platforms) |
| **2.2.0** | Status tracking (Not Started/Started/Completed), GFN toggle per game, sort options (Name/Rating/Release/Status), simplified 3-column Excel import |
| **2.1.0** | Game info modal with details (summary, rating, genres, themes, devs), game detail fetching |
| **2.0.0** | Admin panel, Excel upload via UI, cover art button, GFN UUID assignment, GFN launch buttons |
| **1.0.0** | Initial release — game import, IGDB covers, grid/list view, htmx filtering |

---

## 🎮 Have Fun!

Your game library is now running! Access it at:

```
http://your-server-ip:5000
```

Track your gaming progress, filter by status, sort by rating, and launch games on GeForce NOW — all from one beautiful dashboard! ☁️✨

---

**Made with ❤️ for gamers who want control over their libraries**
