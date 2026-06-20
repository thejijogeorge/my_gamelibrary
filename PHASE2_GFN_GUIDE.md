# Phase 2: GeForce NOW Integration Guide

Enable one-click game launching on GeForce NOW from your game library!

## 🎯 What This Does

When you click "Launch on GFN" in the app, users are taken directly to:
```
https://geforcenow.com/{game-id}
```

This opens the game in GeForce NOW (requires active NVIDIA account).

---

## 🚀 Quick Setup (5 Minutes)

### **Step 1: Populate GFN Game IDs**

Run the matching script:

```bash
sudo docker compose exec web python scripts/populate_gfn_game_ids.py
```

Output will show:
```
[INFO] Found 847 games without GFN IDs
[INFO] GFN database has 45 games

[INFO] [1/847] Matching: Elden Ring
[INFO]   ✅ Matched! GFN ID: 5e99f1b6-6db5-404e-bd80-f9d5c86b64d5
[INFO] [2/847] Matching: Baldur's Gate 3
[INFO]   ✅ Matched! GFN ID: 7f1c2a3d-4e5f-6789-abcd-ef1234567890
[INFO] [3/847] Matching: Some Niche Game
[INFO]   ⚠️  No match found (not in GFN catalog or different title)

================================================================================
GFN GAME ID POPULATION SUMMARY
================================================================================
Total GFN games checked: 847
✅ Matched & updated: 42
⚠️  Not in GFN catalog: 805
================================================================================
```

### **Step 2: Refresh Browser**

```
http://your-server:5000
```

Games with GFN support now have **"Launch on GFN"** buttons! 🚀

### **Step 3: Test a Launch**

Click any "Launch on GFN" button → Opens GeForce NOW in browser

---

## 📚 How to Add More Games

The community database is in: `data/gfn_game_ids.json`

### **Add Your Games**

Edit the file and add entries:

```json
{
  "Elden Ring": "5e99f1b6-6db5-404e-bd80-f9d5c86b64d5",
  "Baldur's Gate 3": "7f1c2a3d-4e5f-6789-abcd-ef1234567890",
  "YOUR NEW GAME": "new-gfn-uuid-here",
  "ANOTHER GAME": "another-uuid-here"
}
```

### **How to Find GFN Game IDs**

**Option A: Desktop Shortcut Method (Windows)**
1. Open GeForce NOW app on Windows
2. Right-click a game → "Create shortcut"
3. Open shortcut properties → Copy target URL
4. Extract the UUID from: `nvidia://deeplink?game-id=YOUR-UUID-HERE`

**Option B: GeForce NOW Web**
1. Go to https://play.geforcenow.com
2. Open a game's page
3. Check the browser's network tab → look for `game-id` parameter

**Option C: Community Contributions**
- Share your game IDs with other users
- Get them from gaming community forums

### **After Adding Games**

Run the script again:

```bash
sudo docker compose exec web python scripts/populate_gfn_game_ids.py
```

It will match the new games automatically! ✅

---

## 🔍 Matching Algorithm

The script uses **fuzzy string matching** (70% similarity threshold):

```
"Cyberpunk 2077" → matches → "Cyberpunk 2077" ✅
"Baldurs Gate 3" → matches → "Baldur's Gate 3" ✅
"The Witcher 3 Wild Hunt" → matches → "The Witcher 3" ✅
"Random Indie Game XYZ" → NO MATCH ❌
```

If a game doesn't match, it might have a different title in GFN.

---

## 📊 Workflow

```
Your Game Library
    ↓
[Import games from Excel]
    ↓
[Fetch covers from IGDB]
    ↓
data/gfn_game_ids.json (community DB)
    ↓
[Run populate_gfn_game_ids.py]
    ↓
Database updated with GFN IDs
    ↓
Browser shows "Launch on GFN" buttons
    ↓
Click button → opens GeForce NOW
```

---

## 🛠️ Database Schema

**gfn_games table now has:**

```sql
CREATE TABLE gfn_games (
    id INTEGER PRIMARY KEY,
    game_id INTEGER UNIQUE NOT NULL,
    available_on_steam BOOLEAN,
    available_on_epic BOOLEAN,
    available_on_gog BOOLEAN,
    gfn_deeplink_url TEXT,
    gfn_game_id VARCHAR(36),          ← NEW
    gfn_url VARCHAR(255),              ← NEW
    added_at TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games_master(game_id)
);
```

---

## 🎮 Testing Launch Links

### **From Command Line:**

```bash
# Check a game has GFN ID
sudo docker compose exec db psql -U gameapp -d gamelibrary \
  -c "SELECT title, gfn_game_id, gfn_url FROM gfn_games LIMIT 5;"
```

### **From Web UI:**

1. Open app: `http://your-server:5000`
2. Look for games with "☁️ GFN" badge
3. Click "Launch on GFN" button
4. Should open: `https://geforcenow.com/{game-id}`

---

## ⚙️ Configuration

### **Change Matching Threshold**

Edit `scripts/populate_gfn_game_ids.py` line ~150:

```python
gfn_id = self.matcher.find_gfn_id(game, self.gfn_mapping, threshold=0.75)  # Stricter
```

- `0.9` = Very strict (only exact-ish matches)
- `0.7` = Default (recommended)
- `0.5` = Loose (risky, might misidentify)

### **Check Current GFN Coverage**

```bash
sudo docker compose exec db psql -U gameapp -d gamelibrary \
  -c "SELECT COUNT(*) as with_gfn FROM gfn_games WHERE gfn_game_id IS NOT NULL;"
```

---

## 📝 Contributing to Community Database

Share new game IDs with others:

1. Find the GFN UUID for a game
2. Add to `data/gfn_game_ids.json`
3. Format: `"Game Title": "uuid-here"`
4. Submit for community use!

---

## 🚨 Troubleshooting

### **"Launch on GFN" button missing**

- Game doesn't have a GFN ID in database
- Run: `sudo docker compose exec web python scripts/populate_gfn_game_ids.py`
- Add the game to `data/gfn_game_ids.json` manually

### **Button shows but click does nothing**

- Browser JavaScript issue
- Try different browser or clear cache
- Check browser console for errors: `F12 → Console`

### **Wrong game launches**

- Fuzzy matching mistake
- Edit `data/gfn_game_ids.json` and fix the mapping
- Re-run the script

---

## 🔗 Deep Linking Details

**Web Browser Method (What We Use):**
```
https://geforcenow.com/{game-id}
```
- ✅ Works in any browser
- ✅ No app installation needed
- ✅ Seamless redirect

**Native Desktop Method (Alternative):**
```
nvidia://deeplink?game-id={game-id}
```
- Requires GeForce NOW app installed
- Opens app directly

We're using the web method for universal compatibility. ✅

---

## 📈 Phase 2 Complete!

Your game library now has full GeForce NOW integration:

- ✅ Fuzzy-matched game IDs
- ✅ One-click cloud gaming
- ✅ Community-maintained database
- ✅ Easy to extend

**Next Phase (Phase 3):** Steam/Epic/GOG API integration for real-time game data! 🚀

---

**Questions?** Check the main README.md for general troubleshooting!
