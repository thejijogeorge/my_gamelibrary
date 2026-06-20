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
- `Epic_Games_Library Final.xlsx` (your game export)

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

### **Step 4: Import Your Games**

```bash
sudo docker compose exec web python scripts/import_games_from_excel.py "Epic_Games_Library Final.xlsx"
```

You should see:
```
✅ Steam games imported: 408
✅ Epic games imported: 333
✅ GOG games imported: 93
```

### **Step 5: Fetch Cover Art**

```bash
sudo docker compose exec web python scripts/fetch_igdb_metadata.py
```

Sits back and watch it fetch beautiful game covers! ☕

### **Step 6: Access Your Library**

Open browser:
```
http://your-server-ip:5000
```

You should see your games with covers, filters, and GFN streaming buttons! 🎮

---

## 📁 Project Structure

```
my_gamelibrary/
├── docker-compose.yml          ← Rename from docker-compose.deploy.yml
├── .env                        ← Your credentials & secrets
├── Epic_Games_Library Final.xlsx ← Your game library
├── app/
│   ├── routes/
│   ├── templates/
│   ├── static/css/
│   └── models.py
├── scripts/
│   ├── import_games_from_excel.py
│   ├── fetch_igdb_metadata.py
│   ├── clear_cover_urls.py
│   └── deduplicate_games.py
├── migrations/                 ← Database schema
├── Dockerfile
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

### **Clear Blurry Covers & Re-fetch**
```bash
sudo docker compose exec web python scripts/clear_cover_urls.py
sudo docker compose exec web python scripts/fetch_igdb_metadata.py
```

### **Remove Duplicate Games**
```bash
sudo docker compose exec -it web python scripts/deduplicate_games.py
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

### **Database stuck or corrupted**

Nuke and restart:
```bash
sudo docker compose down -v
sudo docker compose up -d
# Re-import games
sudo docker compose exec web python scripts/import_games_from_excel.py "Epic_Games_Library Final.xlsx"
```

### **Performance issues**

Increase Docker memory:
```yaml
# docker-compose.yml
services:
  web:
    mem_limit: 2g
  db:
    mem_limit: 1g
```

---

## 📊 Features

✅ **Multi-platform game aggregator** — Steam, Epic Games, GOG  
✅ **Beautiful cover art** — High-resolution (t_1080p) from IGDB  
✅ **Real-time filtering** — Search, filter by platform/account  
✅ **GeForce NOW integration** — One-click cloud gaming launch  
✅ **Grid & list views** — Choose your preferred layout  
✅ **Responsive design** — Works on mobile & desktop  
✅ **Dark gamer theme** — Beautiful glassmorphism UI  

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

## 📝 Next Steps

- Customize the UI theme in `app/static/css/style.css`
- Add more platforms by modifying `app/models.py` and import scripts
- Set up Nginx reverse proxy for production HTTPS
- Configure automatic daily backups

---

## 💬 Support

For issues or questions, check:
- Docker logs: `sudo docker compose logs web`
- Database status: `sudo docker compose ps`
- Game count: `sudo docker compose exec db psql -U gameapp -d gamelibrary -c "SELECT COUNT(*) FROM vw_owned_games_unified;"`

---

## 📄 Files Explained

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Container orchestration — defines web & database services |
| `.env` | Environment variables — IGDB credentials, secrets |
| `Dockerfile` | Web app container definition |
| `app/routes/games.py` | Flask routes for filtering & displaying games |
| `app/templates/` | HTML templates for UI |
| `scripts/import_games_from_excel.py` | Import games from Excel file |
| `scripts/fetch_igdb_metadata.py` | Fetch game covers & metadata from IGDB |
| `migrations/` | Database schema & updates |

---

## 🎮 Have Fun!

Your game library is now running! Access it at:

```
http://your-server-ip:5000
```

Enjoy organizing and launching your games! ☁️✨

---

**Made with ❤️ for gamers who want control over their libraries**
