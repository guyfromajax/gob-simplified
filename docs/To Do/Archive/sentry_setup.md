# Sentry Error Tracking Setup

Backend and frontend Sentry integration is implemented. You need to create Sentry projects and add the DSNs.

---

## 1. Create a Sentry account (if needed)

1. Go to [sentry.io](https://sentry.io) and sign up (free tier).
2. Create an organization (e.g. "Geeked Out Basketball").

---

## 2. Backend project (Python/FastAPI)

1. In Sentry: **Projects** → **Create project**.
2. Select **FastAPI**.
3. Name it (e.g. "gob-backend").
4. Copy the **DSN** (looks like `https://xxx@xxx.ingest.sentry.io/xxx`).
5. Add to **Railway** (both staging and production):
   - **Variables** → **Add variable**
   - Name: `SENTRY_DSN`
   - Value: your backend DSN

---

## 3. Frontend project (JavaScript)

1. In Sentry: **Projects** → **Create project**.
2. Select **JavaScript** (or **Browser**).
3. Name it (e.g. "gob-frontend").
4. Copy the **DSN**.
5. Add to **Railway** (production backend — this is served via `/app-config`):
   - **Variables** → **Add variable**
   - Name: `SENTRY_DSN_FRONTEND`
   - Value: your frontend DSN

> **Why backend?** The frontend gets the DSN from `/app-config` so it’s not hardcoded. The production backend must have `SENTRY_DSN_FRONTEND` set for the frontend to load Sentry.

---

## 4. Verify

**Backend:** After deploy, trigger an error (e.g. visit a non-existent endpoint that returns 500, or add a test route that raises). Check Sentry for the event.

**Frontend:** After deploy, open the browser console and run:
```javascript
throw new Error("Test Sentry frontend");
```
Check Sentry for the event.

---

## Environment variables summary

| Variable              | Where        | Purpose                          |
|-----------------------|-------------|-----------------------------------|
| `SENTRY_DSN`          | Railway     | Backend Python error tracking     |
| `SENTRY_DSN_FRONTEND` | Railway     | Frontend JS error tracking (served via app-config) |

If either DSN is not set, that part of Sentry is disabled (no errors, no extra cost).
