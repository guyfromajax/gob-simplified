# Local Development Setup

**Goal:** Run GOB locally for fast iteration (1-2 second reloads) instead of waiting 4-8 minutes for Railway deploys.

---

## Quick Start

### 1. Set up environment variables

Create `.env.local` in the project root:

```bash
# Copy your MongoDB connection string here
MONGO_URI=mongodb+srv://your-username:your-password@your-cluster.mongodb.net/gob?retryWrites=true&w=majority
```

**Where to get your MongoDB URI:**
- MongoDB Atlas → Connect → Drivers → Copy connection string
- Replace `<password>` with your actual password
- You can use the **same Atlas database** as Railway (recommended for simplicity)

**Optional: Local MongoDB**
If you want to run MongoDB locally:
```bash
# Install MongoDB: brew install mongodb-community (macOS)
# Start: brew services start mongodb-community
# Then use:
MONGO_URI=mongodb://localhost:27017/gob
```

### 2. Install dependencies

Make sure you're in the virtual environment:

```bash
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows
```

Install requirements (if not already installed):

```bash
pip install -r requirements.txt
```

### 3. Start the dev server

**Single command:**

```bash
python dev.py
```

You'll see:
```
🚀 Starting GOB local dev server...
📍 Backend: http://localhost:8000
📍 Frontend: http://localhost:8000/static/court.html
🔄 Hot reload: ENABLED
```

### 4. Access the app

Open your browser:
- **Game court:** `http://localhost:8000/static/court.html`
- **Homepage:** `http://localhost:8000/static/homepage.html`
- **Play builder:** `http://localhost:8000/static/play-builder-v2.html`
- **Skeleton builders:** `http://localhost:8000/static/fcp-skeletons.html`

**Backend API:** `http://localhost:8000/docs` (FastAPI auto-generated docs)

---

## How It Works

### Environment Loading

**Local development:**
1. `BackEnd/db.py` checks if `.env.local` exists
2. If yes → loads `.env.local` (your local config)
3. If no → loads `.env` or Railway system env vars

**Railway deployment:**
- `.env.local` doesn't exist on Railway
- Uses Railway environment variables (set in dashboard)
- No code changes needed!

### Hot Reload

When you save a Python file in `BackEnd/`:
- Uvicorn detects the change (~100ms)
- Reloads the app (~1-2 seconds)
- No need to restart manually!

**What triggers reload:**
- ✅ Python files (`.py`) in `BackEnd/`
- ❌ Frontend files (HTML/JS) - just refresh browser
- ❌ `.env.local` changes - must restart `dev.py`

### Frontend Changes

**No build step needed!** Frontend is static HTML/JS/Phaser.

When you change frontend files:
- Just **refresh the browser** (Cmd+R or Ctrl+R)
- Changes appear instantly
- No server restart needed

---

## Local vs Railway

| Aspect | Local Dev | Railway |
|--------|-----------|---------|
| **Start command** | `python dev.py` | Auto-starts via `BackEnd/run.py` |
| **Port** | `8000` | Railway assigns dynamically |
| **MongoDB** | `.env.local` → Your choice | Railway env vars → Atlas |
| **Hot reload** | ✅ Yes (~1-2s) | ❌ No (4-8min deploys) |
| **Environment** | `.env.local` file | Railway dashboard variables |
| **Use case** | Fast iteration | Staging/prod |

---

## Common Tasks

### Run local dev server
```bash
python dev.py
```

### Stop dev server
Press `Ctrl+C` in terminal

### Change MongoDB connection
Edit `.env.local` and restart `dev.py`

### Test Railway deployment locally
```bash
# Temporarily rename .env.local to test Railway behavior
mv .env.local .env.local.bak
python dev.py  # Will use .env (Railway config)
mv .env.local.bak .env.local  # Restore
```

### View backend logs
Logs appear in terminal where you ran `dev.py`

### View frontend logs
Open browser DevTools → Console tab

---

## Troubleshooting

### "Module not found" errors
```bash
# Make sure you're in the venv
source venv/bin/activate
pip install -r requirements.txt
```

### "Connection refused" or MongoDB errors
- Check `.env.local` has correct `MONGO_URI`
- Test connection: Can you connect via MongoDB Compass?
- If using local MongoDB, check it's running: `brew services list`

### Hot reload not working
- Make sure you're saving files in `BackEnd/` directory
- Frontend changes just need browser refresh (no reload needed)
- `.env.local` changes require manual restart

### Port 8000 already in use
```bash
# Find what's using port 8000
lsof -i :8000
# Kill it, or change port in dev.py to 8001
```

---

## Files Reference

### Local Dev Files
- `dev.py` - Dev server script (hot reload enabled)
- `.env.local` - Your local environment config (gitignored)
- `.env.railway.example` - Template showing Railway env vars

### Backend Entry Points
- `BackEnd/run.py` - Production entry (no hot reload, used by Railway)
- `BackEnd/api/api.py` - FastAPI app definition
- `BackEnd/db.py` - Database connection (env-aware)

### Environment Priority
1. `.env.local` (local dev) - highest priority
2. `.env` (fallback)
3. System env vars (Railway sets these)

---

## Next Steps

After confirming local dev works:
1. Make code changes locally
2. Test immediately (1-2s reload)
3. When ready, `git push` to deploy to Railway
4. Railway auto-deploys on push (4-8min)
5. Test on Railway staging URL

**You now have fast local iteration + stable Railway deployment!** 🎯

