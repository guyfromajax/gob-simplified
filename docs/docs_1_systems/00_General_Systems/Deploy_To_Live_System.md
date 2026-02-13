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

### 60‑minute early warning (recommended)

To show the warning **60 minutes before** maintenance **without** pushing your feature/fix to production:

1. **Do not merge** your feature branch into `main` yet.
2. On `main`, update **only** `FrontEnd/static/config/maintenance.json`:
   - Set `"enabled": true`
   - Set a new `"id"` (unique per maintenance event)
   - Set `"starts_at_iso"` (UTC) to the planned maintenance start time
   - Keep `"show_minutes_before": 60` and update `"message"` if needed
3. Commit and push **only this file** to `main` (Netlify production deploy).
4. Confirm the banner appears on production for non–game pages. Users in an active game (court / set-lineup / game-plan) do not see the banner until they leave those screens, so they are not interrupted mid-session.
5. At the planned maintenance time, proceed with the full maintenance steps (B and C below) and merge your code when you are ready.

**Step-by-step (copy-paste):**

1. **Checkout `main` and pull latest** (do this from a clean state; stash or commit any other work first):
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Edit only the banner config.** Open `FrontEnd/static/config/maintenance.json` and set something like (replace the `id` and `starts_at_iso` with your maintenance time in UTC):
   ```json
   {
     "id": "maintenance-2025-02-15",
     "enabled": true,
     "starts_at_iso": "2025-02-15T20:00:00Z",
     "show_minutes_before": 60,
     "message": "Maintenance begins soon. Please finish your game to avoid losing progress.",
     "details_url": ""
   }
   ```
   - `starts_at_iso`: when maintenance actually starts (UTC). The banner will appear 60 minutes before this.
   - `id`: change this for each maintenance event so returning users see the banner again (dismissal is per `id`).

3. **Commit and push only that file to `main`:**
   ```bash
   git add FrontEnd/static/config/maintenance.json
   git commit -m "chore: enable 60-min maintenance warning banner"
   git push origin main
   ```

4. **Wait for Netlify** to finish the production deploy, then open production (e.g. mode-select or homepage). You should see the red banner. It will not appear on court/set-lineup/game-plan.

5. **When it’s time for the real maintenance**, do the full maintenance flow (B and C below) and merge your code to `main` when you’re ready.

### A) Warning Banner (Frontend Only, Does Not Block The Site)

Config file:
- `FrontEnd/static/config/maintenance.json`

How it behaves:
- If `"enabled": false`, banner is off.
- If `"enabled": true` and `"starts_at_iso"` is set, banner appears starting `show_minutes_before` minutes before the start time.
- If `"enabled": true` and `"starts_at_iso"` is blank, banner shows immediately.
- Users can dismiss it; changing `"id"` forces it to reappear.
- The banner is **non-blocking** (small top-right notice, not a full-screen overlay). It is **not shown** on game/court, set-lineup, or game-plan pages so users in an active game are not interrupted; they see it after leaving those screens.

Steps (when enabling the banner as part of your deploy):
1. On `main`, update `FrontEnd/static/config/maintenance.json`:
   - Set `"enabled": true`
   - Set a new `"id"` (unique per maintenance event)
   - Set `"starts_at_iso"` (UTC) and keep `"show_minutes_before": 60`
   - Update `"message"` if needed
2. Commit + push `main` (Netlify production deploy).
3. Verify banner appears on production (e.g. on mode-select or homepage; it will not appear on court/set-lineup/game-plan).

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

