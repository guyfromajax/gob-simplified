# Environment Variables

**Status:** Environment streamlining Tasks 1–10 (2026-08-11)
**Purpose:** Single reference for all environment variables used by GOB.

---

## Required (Backend – Railway / Local)

| Variable | Purpose | Example (never commit real values) | Where to set |
|----------|---------|-----------------------------------|--------------|
| `ENVIRONMENT` | Canonical runtime identity | `development`, `test`, `staging`, `production` | Railway dashboard or `.env.local` |
| `MONGO_URI` | MongoDB Atlas connection string including the database path | `mongodb+srv://user:pass@host/gob-staging` | Railway dashboard or `.env.local` |
| `MONGO_DB_NAME` | Explicit database identity; must match URI and environment | `gob-staging` | Railway dashboard or `.env.local` |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens. **Must be unique per environment.** | `your-32-plus-char-random-secret` | Railway dashboard or `.env.local`. **Required in production** – app fails to start if missing. |
| `IS_ALPHA` | If `true`, signup requires valid OTP | `true` or `false` | Railway or `.env.local` |
| `PORT` | HTTP port (Railway sets automatically) | `8000` | Railway (auto), optional locally |

---

## Database Separation (Staging vs Production)

| Variable | Purpose | Staging | Production |
|----------|---------|---------|------------|
| `MONGO_URI` | Connection string | Same cluster OK; may include `gob-staging` in path | Same cluster OK; typically `gob` in path |
| `MONGO_DB_NAME` | Required explicit database name | `gob-staging` | `gob` |

**Rule:** `MONGO_DB_NAME` and the `MONGO_URI` path must agree. `development`/`staging` require `gob-staging`; `production` requires `gob`. Mismatch fails before a collection is opened.

---

## Optional (Backend)

| Variable | Purpose | Default |
|----------|---------|---------|
| `JWT_EXPIRATION_HOURS` | JWT token lifetime | `24` |
| `CORS_ORIGINS` | Comma-separated allowed origins | (see api.py) |
| `SENTRY_DSN` | Backend error tracking | (none) |
| `SENTRY_DSN_FRONTEND` | Exposed to frontend for Sentry | (none) |
| `RAILWAY_ENVIRONMENT` | Railway-owned metadata; application identity remains `ENVIRONMENT` | (platform supplied) |
| `FRANCHISE_NAMES_FILE` | Path to franchise names config | (none) |
| `FRANCHISE_START_WEEK` | Override start week | (none) |
| `DISABLE_DEBUG` | Set to `1`/`true`/`yes` to disable debug | (enabled) |
| `DEBUG_SERIALIZATION` | Enable player serialization debug | (none) |
| `API_URL` | Used by some scripts | `http://localhost:8000` |

---

## Feature Flags (Backend)

Dynamic HCO motion and set plays are permanent; their former flags are retired. Defense retains one active fallback kill switch.

| Variable | Purpose | Default | Docs |
|----------|---------|---------|------|
| `GOB_DYNAMIC_HCO_DEFENSE` | Kill switch for dynamic HCO defense; enabled by default | on | [Dynamic_HCO_System.md](06_Gameplay_Systems/Dynamic_HCO_System.md) |

**Rollback:** set the variable to `0` (or remove it) and redeploy/restart the service — instantly reverts that turn type to the legacy path. No code change.

---

## Frontend (Netlify / Static)

No env vars in frontend code. API base URL is derived from `window.location.hostname` in `api-config.js`. Sentry DSN comes from backend `/app-config`.

---

## Local Development

1. Copy `.env.example` to `.env.local` for local staging development. Railway environments use Railway variables directly; do not create a production env file in the repository.
2. Set real values locally only; never commit `.env` or `.env.local`
3. Set `ENVIRONMENT=development`, `MONGO_DB_NAME=gob-staging`, and a URI whose path is `/gob-staging`.
4. Local startup fails if `.env.local` is missing. It never loads `.env` and never silently selects mongomock.
5. Tests explicitly set `GOB_DB_MODE=mongomock`, `ENVIRONMENT=test`, and `MONGO_DB_NAME=gob-test`.

---

## Verification Checklist (Staging vs Production)

Before alpha launch, confirm:

- [ ] `JWT_SECRET_KEY` is set and **different** for staging and production
- [ ] Staging uses `MONGO_DB_NAME=gob-staging` and `/gob-staging` in the URI
- [ ] Production uses `MONGO_DB_NAME=gob` and `/gob` in the URI
- [ ] No real secrets in git history (run `git log -p -S "mongodb+srv"` or use gitleaks)
- [ ] `.env`, `.env.local`, `.env.railway` are in `.gitignore` (they are)

## Operations

For copy-safe commands covering local setup, Railway, tests, staging/production
maintenance, Atlas backups, external R2 credentials, rotation, and incident response,
see [Environment_Operations.md](00_Operations/Environment_Operations.md).
