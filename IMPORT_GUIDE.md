# Game Library Import Guide

This guide walks you through importing your game library from the Excel file into Postgres.

---

## **Step 1: Prepare Your Files**

1. **Copy your Excel file** into the `gamelibrary` folder:
   ```
   cp ~/Downloads/Epic_Games_Library_Final.xlsx gamelibrary/
   ```

2. **Create the scripts directory** (if it doesn't exist):
   ```powershell
   # On Windows PowerShell
   mkdir -p gamelibrary/scripts
   ```

---

## **Step 2: Start Docker Containers**

```powershell
cd gamelibrary
docker-compose up
```

Wait for the output to show:
```
db_1   | ... is ready to accept connections
web_1  | INFO in app: Running on http://0.0.0.0:5000
```

---

## **Step 3: Run the Import Script**

**In a new PowerShell/terminal window**, run:

```powershell
# Import your Excel file into the database
docker exec gamelibrary-web python scripts/import_games_from_excel.py Epic_Games_Library_Final.xlsx
```

You'll see output like:
```
[INFO] Starting game library import...
[INFO] Step 1: Setting up platforms and accounts
[INFO] Created platform: Steam
[INFO] Created platform: Epic
[INFO] Created platform: GOG
[INFO] Created account: Steam/jijo_george_max
[INFO] Created account: Epic/Geekstradamus01
...
================================================================================
IMPORT SUMMARY
================================================================================
✅ Games created in games_master: 839
✅ Platforms created: 3
✅ Accounts created: 4
✅ Steam games imported: 409
✅ Epic games imported: 335
✅ GOG games imported: 94
✅ GeForce NOW games linked: 2187
================================================================================
```

---

## **Step 4: Verify the Data**

Connect to the database and check:

```powershell
# Access Postgres command line
docker exec -it gamelibrary-db psql -U gameapp -d gamelibrary
```

Then run these queries:

```sql
-- Check platforms
SELECT * FROM platforms;

-- Check accounts
SELECT p.name, a.username FROM accounts a JOIN platforms p ON a.platform_id = p.platform_id;

-- Count games by platform
SELECT 
    p.name, 
    COUNT(*) as game_count
FROM (
    SELECT account_id FROM owned_games_steam
    UNION ALL SELECT account_id FROM owned_games_epic
    UNION ALL SELECT account_id FROM owned_games_gog
) owned
JOIN accounts a ON a.account_id = owned.account_id
JOIN platforms p ON p.platform_id = a.platform_id
GROUP BY p.name;

-- Check unified view
SELECT COUNT(*) FROM vw_owned_games_unified;

-- See sample data
SELECT title, platform_name, account_username, is_on_gfn 
FROM vw_owned_games_unified 
LIMIT 10;
```

Exit Postgres:
```sql
\q
```

---

## **Step 5: Build Phase 1 UI**

Once data is imported, I'll create the Flask routes and templates so you can see your games at http://localhost:5000

---

## **Important Notes**

### ⚠️ **About Steam/Epic/GOG IDs**

The import script currently uses **game titles as temporary IDs** for Steam (steam_appid), Epic (epic_item_id), and GOG (gog_product_id). 

This works for now, but for **full functionality**, you'll need to:

1. **For Steam:** Get actual appids by implementing Steam API integration (Phase 2)
2. **For Epic:** Get actual item IDs (requires Epic API)
3. **For GOG:** Get actual product IDs (requires GOG API)

For now, the UI will work fine with titles as IDs — it just means you can't launch directly from Steam/Epic/GOG URLs yet (but GFN links will work).

### ✅ **What's Working Now**

- ✅ All games imported into `games_master`
- ✅ Platforms and accounts set up
- ✅ Games linked to accounts
- ✅ GeForce NOW games marked with store availability
- ✅ Unified view shows all your games

### 🚧 **What Needs Phase 2**

- 🚧 Match game titles to IGDB for cover art, genres, release dates
- 🚧 Get actual Steam appids from Steam API
- 🚧 Get actual Epic item IDs and namespaces
- 🚧 Get actual GOG product IDs

---

## **Troubleshooting**

### **Script not found**
```
Error: No such file or directory
```
Make sure:
1. The script is at `gamelibrary/scripts/import_games_from_excel.py`
2. You're running from the `gamelibrary` folder
3. Docker container is running (`docker-compose up`)

### **Excel file not found**
```
Error: File not found: Epic_Games_Library_Final.xlsx
```
Copy the Excel file to the `gamelibrary` folder first:
```powershell
cp ~/Downloads/Epic_Games_Library_Final.xlsx gamelibrary/
```

### **Connection to database failed**
```
Error: could not translate host name "db" to address
```
Make sure:
1. Docker container is running: `docker-compose up`
2. Wait 5-10 seconds for Postgres to start

### **Re-import issues**
If you want to reimport (delete all data and start fresh):
```powershell
docker-compose down -v   # Deletes the database volume
docker-compose up        # Recreates fresh database
# Then run import script again
```

---

## **Next Steps**

Once data is imported, reply with "Data imported!" and I'll:

1. ✅ Build **Phase 1 UI** — Flask routes + Jinja2 templates to display your games
2. ✅ Create grid/list toggle with htmx filtering
3. ✅ Add gamer theme CSS (dark, glassmorphism, neon accents)
4. ✅ Test everything works locally

Then you'll see your games beautifully displayed at http://localhost:5000!

---

## **Questions?**

If anything fails, share:
1. The error message
2. Your command (what you ran)
3. The output (paste last 20 lines)

I can troubleshoot from there.
