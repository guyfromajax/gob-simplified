# Deploy To Live System

- **Branch rules:** `develop` = staging (Netlify + Railway). `main` = production. Don’t push to `main` until staging is verified on `develop`.

---

## Standard Deploy (No Maintenance)

1. Make changes on `develop`, push, confirm staging deploys (Netlify + Railway if backend changed).
2. Smoke test staging.
3. Merge `develop` into `main`, push `main`.
4. Confirm production deploys, then smoke test production (homepage, auth, a quick gameplay check).

---

## Maintenance Deploy (Update to Live with Warning)

**High-level:**

1. **T–60 min:** Push the warning banner live (steps below). No Railway change. Users see a dismissible red banner; it does not show on court/set-lineup/game-plan so it won’t disrupt active games.
2. **Right before the real deploy:** Turn on the maintenance page (Netlify) and block writes (Railway): uncomment the wildcard in `FrontEnd/static/_redirects` and push `main`; set Railway production `MAINTENANCE_MODE=true`.
3. **Push the update to main** (merge your branch into `main`, push).
4. **After deploys are done:** Set Railway `MAINTENANCE_MODE=false`; comment `_redirects` back and set `maintenance.json` `enabled: false`; push `main`. Users then see the live app with the new code.

---

### Step 1 — T–60 min: Push the warning banner only

Do **not** merge your feature branch yet. Deploy only the banner config.

1. Checkout `main` and pull latest (stash or commit any other work first):

   ```bash
   git checkout main
   git pull origin main
   ```

2. Edit **only** `FrontEnd/static/config/maintenance.json`:

   - Set `"enabled": true`.
   - Set `"id"` to a **new** value (e.g. `maintenance-2026-02-17`). Changing the id ensures returning users who dismissed a previous banner will see this one.
   - Set `"starts_at_iso"` to the **exact UTC time** when you plan to start the real maintenance (when you’ll turn on the maintenance page and set Railway `MAINTENANCE_MODE=true`). The banner will appear **60 minutes before** that time (or immediately if that time is less than 60 minutes away).
   - Optionally keep or edit `"message"` and leave `"details_url": ""` unless you have a link.

   Example (replace the date/time with your planned maintenance start in UTC):

   ```json
   {
     "id": "maintenance-2026-02-17",
     "enabled": true,
     "starts_at_iso": "2026-02-17T20:00:00Z",
     "show_minutes_before": 60,
     "message": "Maintenance begins soon. Please finish your game to avoid losing progress.",
     "details_url": ""
   }
   ```

3. Commit and push only that file:

   ```bash
   git add FrontEnd/static/config/maintenance.json
   git commit -m "chore: enable 60-min maintenance warning banner"
   git push origin main
   ```

4. After Netlify deploys, check production (e.g. mode-select or homepage). The red banner should appear there; it will not appear on court/set-lineup/game-plan.

---

### Step 2 — Right before the real deploy: Maintenance on

- **Netlify (maintenance page):** On `main`, in `FrontEnd/static/_redirects`, uncomment the wildcard so all routes serve the maintenance page:
  - Change `# /*        /maintenance.html 200!` → `/*        /maintenance.html 200!`  
  - (The `200!` is required so the redirect overrides existing HTML.)  
  Commit and push `main`.
- **Railway:** Set production env `MAINTENANCE_MODE=true` so the API returns 503 on writes (POST/PUT/PATCH/DELETE).

---

### Step 3 — Push the update

Merge your branch (e.g. `develop`) into `main` and push. Wait for Netlify and Railway production deploys to finish.

---

### Step 4 — Reopen after maintenance

1. **Railway:** Set production `MAINTENANCE_MODE=false`.
2. **Netlify:** In `FrontEnd/static/_redirects`, comment the wildcard line back (`# /* ...`), and in `FrontEnd/static/config/maintenance.json` set `"enabled": false`. Commit and push `main`.

Users will now see the live site with the new code.

---

**Reference:** Banner dismissal is stored in browser localStorage by `id`; changing `id` in the config makes the banner show again for returning users.
