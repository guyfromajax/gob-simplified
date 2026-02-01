# Environment Variables

**Status:** Alpha launch (Step 5.3)  
**Purpose:** Single reference for all environment variables used by GOB.

---

## Required (Backend – Railway / Local)

| Variable | Purpose | Example (never commit real values) | Where to set |
|----------|---------|-----------------------------------|--------------|
| `MONGO_URI` | MongoDB Atlas connection string | `mongodb+srv://user:pass@cluster.mongodb.net/gob` | Railway dashboard, `.env` (local) |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens. **Must be unique per environment.** | `your-32-plus-char-random-secret` | Railway dashboard, `.env` (local). **Required in production** – app fails to start if missing. |
| `IS_ALPHA` | If `true`, signup requires valid OTP | `true` or `false` | Railway, `.env` |
| `PORT` | HTTP port (Railway sets automatically) | `8000` | Railway (auto), optional locally |

---

## Database Separation (Staging vs Production)

| Variable | Purpose | Staging | Production |
|----------|---------|---------|------------|
| `MONGO_URI` | Connection string | Same cluster OK; may include `gob-staging` in path | Same cluster OK; typically `gob` in path |
| `MONGO_DB_NAME` | Overrides DB name from URI | `gob-staging` | `gob` (or omit to use URI path) |

**Rule:** Staging and production must use different database names. Use `MONGO_DB_NAME` or different `MONGO_URI` paths.

---

## Optional (Backend)

| Variable | Purpose | Default |
|----------|---------|---------|
| `JWT_EXPIRATION_HOURS` | JWT token lifetime | `24` |
| `CORS_ORIGINS` | Comma-separated allowed origins | (see api.py) |
| `SENTRY_DSN` | Backend error tracking | (none) |
| `SENTRY_DSN_FRONTEND` | Exposed to frontend for Sentry | (none) |
| `ENVIRONMENT` / `ENV` / `RAILWAY_ENVIRONMENT` | Environment label | `development` |
| `FRANCHISE_NAMES_FILE` | Path to franchise names config | (none) |
| `FRANCHISE_START_WEEK` | Override start week | (none) |
| `DISABLE_DEBUG` | Set to `1`/`true`/`yes` to disable debug | (enabled) |
| `DEBUG_SERIALIZATION` | Enable player serialization debug | (none) |
| `API_URL` | Used by some scripts | `http://localhost:8000` |

---

## Frontend (Netlify / Static)

No env vars in frontend code. API base URL is derived from `window.location.hostname` in `api-config.js`. Sentry DSN comes from backend `/app-config`.

---

## Local Development

1. Copy `.env.railway.example` to `.env` or `.env.local`
2. Set real values locally only; never commit `.env` or `.env.local`
3. `.env.local` overrides `.env` if present (see `BackEnd/db.py`)

---

## Verification Checklist (Staging vs Production)

Before alpha launch, confirm:

- [ ] `JWT_SECRET_KEY` is set and **different** for staging and production
- [ ] Staging uses `MONGO_DB_NAME=gob-staging` (or `gob-staging` in `MONGO_URI` path)
- [ ] Production uses `gob` database (or `MONGO_DB_NAME=gob`)
- [ ] No real secrets in git history (run `git log -p -S "mongodb+srv"` or use gitleaks)
- [ ] `.env`, `.env.local`, `.env.railway` are in `.gitignore` (they are)
