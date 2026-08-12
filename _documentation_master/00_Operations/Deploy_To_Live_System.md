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
   - Set `"starts_at_iso"` to the **planned maintenance start** (when you’ll turn on the maintenance page and set Railway `MAINTENANCE_MODE=true`). The banner appears **60 minutes before** that instant (or immediately if that time is less than 60 minutes away).
   - **Recommended (US Eastern / Philadelphia):** use a **naive** local time string with **no** `Z` and **no** `±hh:mm` offset, e.g. `"2026-02-17T15:00:00"`. That is interpreted as **wall clock in `America/New_York`** (Eastern Standard or Eastern Daylight, depending on the date). Optional `"starts_at_timezone"` overrides the IANA zone if you need something other than New York (rare).
   - **Alternate (absolute / UTC):** you may still pass a full ISO instant with `Z` or an explicit offset (e.g. `"2026-02-17T20:00:00Z"`). In that case `starts_at_timezone` is ignored for parsing.
   - Optionally keep or edit `"message"` and leave `"details_url": ""` unless you have a link.

   Example — maintenance starts **3:00 PM US Eastern** on 17 Feb 2026 (no UTC math required):

   ```json
   {
     "id": "maintenance-2026-02-17",
     "enabled": true,
     "starts_at_iso": "2026-02-17T15:00:00",
     "show_minutes_before": 60,
     "message": "Maintenance begins soon. Please finish your game to avoid losing progress.",
     "details_url": ""
   }
   ```

   Example — same instant expressed explicitly in UTC (optional):

   ```json
   "starts_at_iso": "2026-02-17T20:00:00Z"
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

**Reference:**

- Banner dismissal is stored in browser localStorage by `id`; changing `id` in the config makes the banner show again for returning users.
- Time math is implemented in `FrontEnd/static/js/shared/maintenanceBanner.js`: naive `starts_at_iso` values use **IANA `America/New_York`** (US Eastern, including EST and EDT), not the viewer’s browser local zone and not “UTC only.”


---

## Post-deploy verification — `scripts/verify_deploy.py`

**Nothing else on a deploy proves it took.** Production silently diverged from `develop` by
**158 commits** once, and no surface exposed the running build. `/health` now reports
`commit`, `hash_seed` and `db_access`.

```bash
scripts/verify_deploy.py --health-url https://<prod>/health   # A: build
GOB_DB_ACCESS=read scripts/verify_deploy.py --data            # B: data (prod MONGO_URI)
scripts/verify_deploy.py --franchise-id <id> --delete         # C: seeding
```

| check | asserts |
|---|---|
| **A. BUILD** | `/health` commit matches what shipped; `PYTHONHASHSEED=0` live; `GOB_DB_ACCESS=write` set |
| **B. DATA** | copied collections match the shipped staging snapshot by **CONTENT checksum ignoring `_id`** — counts are not enough (`recruit_sets` matched on count while differing by 150 recruits) |
| **C. SEEDING** | a throwaway **week-1, unplayed** franchise gets identity persisted, sliders varying, and the current init values — then deletes it and its FTD/FPD/FRD rows |

C takes a franchise id rather than creating one: creation needs an authenticated session and
the script deliberately does not embed auth. **The franchise must be unplayed** — training moves
the seeded values on the first week.

The check was **negative-controlled**: run against prod before a deploy, B correctly FAILS.

## Deploys that also move DATA

Some deploys need reference collections copied staging → prod. **Back them up first** — the
code half has a git rollback, the data half has nothing, and `gob.players_backup` is a stale
snapshot whose `attributes` differ from live on 1440/1536 documents.

**ORDERING IS BACKUP → MERGE → COPY, not copy → merge.** New code reading old data is a
known-good combination (two full measurement seasons ran on exactly that). **Old code reading
NEW data is untested.**

Before copying, **checksum content rather than comparing counts**, and note that documents can
be identical except for `_id` — the skeleton collections hash differently across databases
while every coordinate matches, so copying them would churn prod for no benefit. **Heuristic:
same byte size + different hash usually means metadata; a real content change moves the size.**

## ⚠️ The prod/local divergence trap

**A franchise created through the UI is seeded by the DEPLOYED backend and then measured by
LOCAL code.** Everything set at creation comes from prod; everything computed during a run comes
from local. **Anything changed since the last deploy seeds wrong, silently, and looks like data
rather than an error.**

Caught once on `rebound_modifier` (deployed 0.2 vs local 0.5) only because someone was looking
for it. The worst instance found: **100% of FPD players carried pre-recalibration
`position_ratings`, median delta 24, max 55** — baked in at creation and never recomputed for
franchise mode.

Before any measurement season, do ONE of:
1. **Deploy first**, so seeded and measured code agree (cleanest).
2. **Normalise after creation** — overwrite everything local would seed differently, including
   recomputing FPD `position_ratings`.
3. **Provision locally** rather than through the UI.
