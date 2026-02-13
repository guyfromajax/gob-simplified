# Maintenance Mode + Warning Banner (Netlify JSON Config)

## Goals
- 60-minute pre-maintenance warning banner (dismissible).
- During maintenance/deploys: show a universal maintenance screen (image) instead of the app.
- Keep this low-risk: toggles should be simple and avoid backend dependency.

This design assumes:
- Frontend is served by Netlify from `FrontEnd/static/`.
- Backend API is served by Railway.

---

## Part A: Warning Banner (Does Not Block Gameplay)

### 1) Add a remote config file (served by Netlify)
Create:
- `FrontEnd/static/config/maintenance.json`

Example contents:
```json
{
  "id": "2026-02-13-maint-1",
  "enabled": true,
  "starts_at_iso": "2026-02-13T21:00:00Z",
  "show_minutes_before": 60,
  "message": "Maintenance begins in about 60 minutes. Please finish your game to avoid losing progress.",
  "details_url": ""
}
```

Notes:
- `id` is important: changing it forces the banner to re-appear even if a user dismissed the previous one.
- `starts_at_iso` + `show_minutes_before` allows the banner to appear automatically when you’re within the time window.
- If you want a manual override, just set `enabled=true` and omit `starts_at_iso` (banner shows immediately).

### 2) Add a shared banner script
Create:
- `FrontEnd/static/js/shared/maintenanceBanner.js`

Responsibilities:
- Fetch `/config/maintenance.json` (add a cache-busting query param).
- Decide whether to show:
  - If `enabled !== true`: do nothing.
  - If `starts_at_iso` is present: show only when now is within `show_minutes_before` minutes of `starts_at_iso`.
- Render a bright red fixed-position banner top-right with a close `X`.
- Persist dismiss in `localStorage` keyed by config `id`:
  - Example key: `maintenance_banner_dismissed_id`
  - If stored `id` matches current config `id`, keep it hidden.

Recommended UI behavior:
- `position: fixed`
- `z-index` higher than game UI (e.g. 99999)
- Avoid covering the top nav:
  - If `document.body.classList.contains('has-auth-bar')`, use a larger `top` offset (auth bar height).

Polling:
- Fetch once on page load.
- Then poll every 60 seconds so you can flip the JSON and have it take effect without a hard refresh.

### 3) Load the banner script on all pages
Simplest and most universal in this codebase:
- Update `FrontEnd/static/js/shared/authGuard.js` so it **always** injects `maintenanceBanner.js` before returning.

Why:
- `authGuard.js` is already included in the `<head>` of essentially every page (including `court.html` and `set-lineup.html`).
- If you only attach this to the auth bar script, gameplay pages won’t see it (auth bar is suppressed there).

Implementation detail:
- Even for public pages where `authGuard.js` returns early, we still want the banner.

---

## Part B: Full Maintenance Mode (Universal Maintenance Screen)

### 1) Add a maintenance page
Create:
- `FrontEnd/static/maintenance.html`

Content:
- Show `static/images/maintenance-image.png`.
- Include a short message like “We’ll be back soon. Please refresh in a few minutes.”
- No auth requirements, no API calls.

### 2) Add a Netlify redirect to serve `maintenance.html` for all routes
Netlify uses `FrontEnd/static/_redirects`.

Add a maintenance block (order matters):
```txt
# Maintenance mode (ENABLE by uncommenting the wildcard rule)
/images/*   /images/:splat   200
/css/*      /css/:splat      200
/js/*       /js/:splat       200
/sounds/*   /sounds/:splat   200

# ENABLE THIS DURING MAINTENANCE:
# /*        /maintenance.html 200
```

How it works:
- Asset allowlist rules prevent the wildcard from breaking images/CSS/JS needed to render `maintenance.html`.
- When maintenance is on, every route returns `maintenance.html`.

Operational toggle:
- You flip maintenance by commenting/uncommenting the wildcard redirect line, then deploying.

---

## Part C: Backend Safety (Optional But Recommended)

Even if Netlify is serving `maintenance.html`, users with an already-open game tab may still hit the API.

Add a Railway env var:
- `MAINTENANCE_MODE=true|false`

Backend behavior when `true`:
- For write/mutation endpoints (simulate turn/quarter, save game, complete-week, etc.), return:
  - `503 Service Unavailable`
  - Optionally include `Retry-After: 60`
- Keep `/health` allowed.

This prevents half-finished requests and “site can’t be reached” mid-timeout/sim flows.

---

## Testing Checklist (Before Reopening)

### Deploy Preview (Frontend)
1. Create a deploy preview with:
  - `maintenance.json` added
  - `maintenanceBanner.js` added and loaded
2. Verify the banner shows and can be dismissed.
3. Verify it reappears when you change `maintenance.json` `id`.

### Maintenance Screen
1. In a deploy preview, enable the wildcard rule in `_redirects`.
2. Verify any route (mode-select, FCC/TCC, roster, court) renders `maintenance.html`.
3. Verify the image loads (allowlist rules working).

### Backend Maintenance Mode
1. In Railway staging, set `MAINTENANCE_MODE=true`.
2. Attempt:
  - `/api/simulate-quarter`
  - `/api/simulate-turn`
3. Confirm requests fail fast with 503 and UI doesn’t corrupt state.

---

## Recommended Operational Runbook

1. 60 minutes before:
  - Set `maintenance.json.enabled=true` with `starts_at_iso` and deploy frontend.
2. At maintenance start:
  - Deploy the “maintenance redirect” change on Netlify (wildcard rule enabled).
  - Set Railway `MAINTENANCE_MODE=true`.
3. Deploy new code:
  - Ship backend changes to Railway.
  - Ship frontend changes to Netlify (separate deploy/preview first if needed).
4. Reopen:
  - Set Railway `MAINTENANCE_MODE=false`.
  - Remove/disable the wildcard maintenance redirect and deploy.
  - Set `maintenance.json.enabled=false` (or bump `id` and update message to “Maintenance complete”) and deploy.

