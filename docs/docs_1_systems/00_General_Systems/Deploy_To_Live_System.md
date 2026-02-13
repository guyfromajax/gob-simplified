# Deploy To Live System

This is the simple workflow to deploy safely and predictably.

## Branch Rules

- `develop` = staging (Netlify staging + Railway staging)
- `main` = production/live (Netlify production + Railway production)
- Do not deploy to `main` until staging is verified on `develop`.

## Standard Deploy (No Maintenance)

1. Make changes on `develop`.
2. Push `develop` and confirm deploys complete:
   - Netlify staging deploy is successful.
   - Railway staging deploy is successful (if backend changed).
3. Test staging:
   - Smoke test the exact screens you touched.
   - Verify no obvious regressions (login, mode-select, scrimmage start, etc.).
4. Promote to production:
   - Merge `develop` into `main`.
   - Push `main`.
5. Confirm production deploys complete:
   - Netlify production deploy is successful.
   - Railway production deploy is successful (if backend changed).
6. Smoke test production (quick check):
   - Homepage loads.
   - Auth + mode-select works.
   - A basic gameplay action works (or at least API health).

## Maintenance Deploy (Banner + Full Maintenance + Backend Protection)

These three toggles are separate. You can enable them independently.

### A) Warning Banner (Frontend Only, Does Not Block The Site)

Config file:
- `FrontEnd/static/config/maintenance.json`

How it behaves:
- If `"enabled": false`, banner is off.
- If `"enabled": true` and `"starts_at_iso"` is set, banner appears starting `show_minutes_before` minutes before the start time.
- If `"enabled": true` and `"starts_at_iso"` is blank, banner shows immediately.
- Users can dismiss it; changing `"id"` forces it to reappear.

Steps:
1. On `main`, update `FrontEnd/static/config/maintenance.json`:
   - Set `"enabled": true`
   - Set a new `"id"` (unique per maintenance event)
   - Set `"starts_at_iso"` (UTC) and keep `"show_minutes_before": 60`
   - Update `"message"` if needed
2. Commit + push `main` (Netlify production deploy).
3. Verify banner appears on production.

### B) Full Maintenance Screen (Frontend Blocks All Routes)

Redirect file:
- `FrontEnd/static/_redirects`

Rule to toggle:
- OFF (normal site): `# /*        /maintenance.html 200!`
- ON (maintenance): `/*        /maintenance.html 200!`

Steps:
1. At maintenance start time, on `main`, uncomment the wildcard line:
   - Change `# /*        /maintenance.html 200!` to `/*        /maintenance.html 200!`
2. Commit + push `main` (Netlify production deploy).
3. Verify production routes all show the maintenance page:
   - `/`
   - `/homepage.html`
   - `/mode-select.html`
   - A random URL like `/anything`

### C) Backend Protection (Blocks Writes)

Railway env var:
- `MAINTENANCE_MODE`

Values:
- `false` = normal
- `true` = block mutations with `503` (POST/PUT/PATCH/DELETE)

Steps:
1. At maintenance start time, set Railway production `MAINTENANCE_MODE=true`.
2. Verify:
   - `GET /health` returns `200`
   - `POST /api/simulate-quarter` returns `503`
   - `POST /api/simulate-turn` returns `503`

## Reopen After Maintenance

1. Railway production:
   - Set `MAINTENANCE_MODE=false`
2. Netlify production:
   - Comment the wildcard line again in `FrontEnd/static/_redirects` and push `main`
3. Frontend banner:
   - Set `FrontEnd/static/config/maintenance.json` `"enabled": false` and push `main`

## Gotchas (Read This Once)

- A push to `main` always triggers a new production deploy. Keep “toggle-only” commits small and intentional.
- For full maintenance mode to override existing `.html` files, the wildcard must be `200!` (the `!` matters).
- The banner dismissal is stored in browser `localStorage` and is not tied to a user account.

