# Game Library — Server Deployment Guide

A personal game aggregator that pulls games from Steam, Epic Games, and GOG with GeForce NOW streaming integration. Deploy to your own server with Docker.

## 📋 Prerequisites

- **Docker & Docker Compose** installed on your server
- **IGDB API credentials** (Twitch Client ID & Secret) — [Get them free](https://dev.twitch.tv/console/apps)
- **Game library Excel file** (from local export)
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
3. Click **"Fetch Missing Covers"** under "🖼️ Cover Art"
4. Click **"Populate GFN URLs"** under "☁️ GeForce NOW"

All tasks run in the background — status updates appear in real-time! 🎮

---

## 📊 Features

### **Core**
- ✅ Multi-platform game aggregator — Steam, Epic Games, GOG
- ✅ Beautiful cover art — High-resolution (t_1080p) from IGDB
- ✅ Real-time filtering — Search, filter by platform/account
- ✅ Grid & list views — Choose your preferred layout
- ✅ Responsive design — Works on mobile & desktop
- ✅ Dark gamer theme — Glassmorphism UI with neon accents

### **Admin Panel (⚙️)**
- ✅ Upload Excel via browser — No more manual CLI imports
- ✅ One-click cover art fetch — Pulls covers from IGDB automatically
- ✅ GFN URL population — Sets launch URLs for all GFN-available games
- ✅ GFN UUID assignment — Search any game and paste its real GFN deep link UUID

### **GeForce NOW Integration (☁️)**
- ✅ Launch on GFN buttons — Every GFN-available game has a launch button
- ✅ Direct deep links — Games with assigned UUIDs launch directly into GFN
- ✅ Fallback support — Games without UUIDs open the GFN web app

---

## ⚙️ Admin Panel Guide

Click the **⚙️ Admin** button in the header to open the management panel.

### **📤 Import Games**

Upload your game library Excel file (`.xlsx`) directly from the browser. The import script runs in the background and shows progress in real-time.

### **🖼️ Cover Art**

Click "Fetch Missing Covers" to pull high-res game covers from IGDB for any games without cover art. Requires IGDB credentials in `.env`.

### **☁️ GeForce NOW URLs**

Click "Populate GFN URLs" to set launch URLs for all games in the GFN catalog. Games get a fallback URL to the GFN web app by default.

### **🎯 Assign GFN Deep Links**

For direct game launching on GeForce NOW:

1. Go to [play.geforcenow.com](https://play.geforcenow.com)
2. Find a game and click it
3. Copy the `game-id` UUID from the browser URL bar
   ```
   Example URL: https://play.geforcenow.com/games?game-id=81810b31-1b34-4921-8ab3-c6c3485fe4ce
   Copy this:    81810b31-1b34-4921-8ab3-c6c3485fe4ce
   ```
4. In the admin panel, search for the game under "Assign GFN Deep Link"
5. Paste the UUID and click **Save**

The game's "Launch on GFN" button will now open it directly in GeForce NOW! 🚀

---

## 📁 Project Structure

```
my_gamelibrary/
├── docker-compose.yml          ← Rename from docker-compose.deploy.yml
├── .env                        ← Your credentials & secrets
├── app/
│   ├── __init__.py             ← App factory with admin blueprint
│   ├── models.py               ← Database models (GfnGame has gfn_game_id + gfn_url)
│   ├── routes/
│   │   ├── games.py            ← Game display & filtering routes
│   │   └── admin.py            ← Admin panel routes (upload, covers, GFN)
│   ├── templates/
│   │   ├── index.html          ← Main page with admin panel
│   │   ├── _games_grid.html    ← Grid view partial
│   │   └── _games_list.html    ← List view partial
│   └── static/css/style.css    ← Gamer theme
├── scripts/
│   ├── import_games_from_excel.py    ← Import from Excel
│   ├── fetch_igdb_metadata.py        ← Fetch covers from IGDB
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

Nuke and restart:
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
docker build -t thejijogeorge/gamelibrary-web:latest -t thejijogeorge/gamelibrary-web:2.0.0 .

# Push to Docker Hub
docker push thejijogeorge/gamelibrary-web:latest
docker push thejijogeorge/gamelibrary-web:2.0.0
```

---

## 📝 Version History

| Version | Features |
|---------|----------|
| **2.0.0** | Admin panel, Excel upload via UI, cover art button, GFN UUID assignment, GFN launch buttons |
| **1.0.0** | Initial release — game import, IGDB covers, grid/list view, htmx filtering |

---

## 🎮 Have Fun!

Your game library is now running! Access it at:

```
http://your-server-ip:5000
```

Click ⚙️ Admin to manage your library right from the browser! ☁️✨

---

**Made with ❤️ for gamers who want control over their libraries**
