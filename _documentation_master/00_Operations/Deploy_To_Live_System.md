# Deploy to Live System

This is the production deployment runbook for Netlify, Railway, and MongoDB Atlas.

## Operating rules

- `develop` deploys staging. `main` deploys production.
- Never merge into `main` until the exact `develop` commit has passed hosted CI and staging QA.
- All scheduled times are **Eastern Time (ET)** using the IANA zone `America/New_York`.
  This means EST (UTC−5) in winter and EDT (UTC−4) in summer; operators do not perform
  UTC or daylight-saving arithmetic.
- Railway application runtime receives production write authorization from Railway
  platform identity. Do **not** add persistent `GOB_DB_ACCESS` to Railway.
- Local production diagnostics and migrations still require process-only
  `GOB_DB_ACCESS=read|write`; see `Environment_Operations.md`.
- If any required check fails, keep maintenance enabled and fix forward or roll back.

## Choose the deployment path

### Standard deployment — no maintenance window

Use for low-risk changes that do not require users to stop writing:

1. Push `develop`; require hosted CI success and successful Netlify/Railway staging deploys.
2. Smoke test staging.
3. Merge `develop` into `main` and push.
4. Require hosted CI success for the production SHA and successful production deploys.
5. Run the post-deployment verification and manual smoke checks below.

### Maintenance deployment — advance warning and write freeze

Use for large releases, data migrations, or changes where mixed old/new clients are unsafe.
The workflow uses **three production pushes**:

1. warning banner;
2. application update with the maintenance page enabled;
3. reopening configuration.

The backend write freeze is controlled separately in Railway.

---

## Maintenance deployment checklist

### Preparation — before T−60 minutes ET

- [ ] All intended application changes are committed and pushed to `develop`.
- [ ] Hosted `Run Tests` is green for that exact `develop` SHA.
- [ ] Netlify and Railway staging deploys succeeded.
- [ ] Staging smoke testing is complete.
- [ ] The maintenance start is chosen and communicated in ET.
- [ ] If data will move, confirm a current Atlas Cloud Backup snapshot and prepare the
      separately reviewed migration, dry run, verification, and rollback procedure.
- [ ] Confirm the operator can access Netlify, Railway, GitHub Actions, and Atlas.

### Push 1 — T−60 minutes ET: warning banner

Checkout the current production branch:

```bash
git checkout main
git pull origin main
```

Edit only `FrontEnd/static/config/maintenance.json`:

```json
{
  "id": "maintenance-YYYY-MM-DD-1",
  "enabled": true,
  "starts_at_iso": "YYYY-MM-DDTHH:MM:SS",
  "starts_at_timezone": "America/New_York",
  "show_minutes_before": 60,
  "message": "Maintenance begins soon. Please finish your game to avoid losing progress.",
  "details_url": ""
}
```

`starts_at_iso` is New York wall-clock time with no `Z` or numeric offset. For example,
`2026-08-20T15:00:00` means 3:00 PM ET on August 20. The parser applies EST or EDT for
that date automatically.

Choose a real New York wall time. A nonexistent clock time during the spring DST jump
(for example, 2:30 AM on the transition date) is rejected rather than being interpreted
in the operator's or user's local timezone.

The `id` must be new so users who dismissed an earlier warning see this one. The banner
polls once per minute. It is intentionally suppressed on `court.html`, `set-lineup.html`,
and `game-plan.html` so an active game is not interrupted.

```bash
git add FrontEnd/static/config/maintenance.json
git commit -m "chore: schedule production maintenance warning"
git push origin main
```

After Netlify deploys, confirm the warning appears on a public page and FCC, and remains
absent from the three deferred gameplay pages.

### Push 2 — at the scheduled time ET: freeze writes and deploy the update

1. In the Railway **production** environment, set `MAINTENANCE_MODE=true`.
2. Wait for the Railway change to deploy. Confirm `/health` remains `200` and the Railway
   production logs identify `environment=production database=gob`.
3. Merge the tested staging branch without committing yet:

   ```bash
   git checkout main
   git pull origin main
   git merge --no-commit --no-ff develop
   ```

4. In `FrontEnd/static/_redirects`, enable the wildcard maintenance rule:

   ```text
   /*        /maintenance.html 200!
   ```

   Keep the preceding `/images`, `/css`, `/js`, and `/sounds` asset rules intact.

5. Commit the merge and push once:

   ```bash
   git add FrontEnd/static/_redirects
   git commit -m "deploy: release develop under maintenance"
   git push origin main
   ```

6. Confirm Netlify serves the maintenance page and wait for Railway production to finish.
7. Require hosted CI success for this exact SHA.
8. Verify the running backend while the maintenance page remains active:

   ```bash
   DEPLOY_SHA="$(git rev-parse HEAD)"
   ./.venv/bin/python scripts/verify_deploy.py \
     --health-url https://<production-backend>/health \
     --expect-commit "$DEPLOY_SHA" \
     --check-ci
   ```

The build check requires:

- the running commit matches `DEPLOY_SHA`;
- `PYTHONHASHSEED=0`;
- `environment=production`;
- `database=gob`;
- resolved database authorization is `write`.

Do not pass `--smoke-url` while the maintenance page is intentionally enabled; that check
correctly rejects a maintenance response.

### Data movement — only when explicitly required

Code-only deployments skip this section.

- Confirm Atlas backup first.
- Use only a reviewed script that goes through the shared database connection boundary.
- Compare content checksums, not only document counts.
- Run a read-only dry run before granting process-only write authorization.
- Keep Railway and Netlify maintenance active throughout the write and verification.
- Do not use a script reported by `scripts/check_env_safety.py` until it is migrated to the
  shared connection helper.

New code reading old reference data is the safer interim state. Do not publish new data
before the corresponding code is live unless that exact old-code/new-data combination was
explicitly verified.

### Push 3 — reopen production

Only proceed when the application deployment, hosted CI, and any data verification pass.

1. Set Railway production `MAINTENANCE_MODE=false` and wait for Railway to finish. The
   Netlify maintenance page still prevents normal entry while the backend reopens.
2. Comment the wildcard in `FrontEnd/static/_redirects`:

   ```text
   # /*        /maintenance.html 200!
   ```

3. Set `enabled` to `false` in `FrontEnd/static/config/maintenance.json`.
4. Commit and push the reopening configuration:

   ```bash
   git add FrontEnd/static/_redirects FrontEnd/static/config/maintenance.json
   git commit -m "chore: reopen production after maintenance"
   git push origin main
   ```

5. Wait for hosted CI, Netlify, and Railway to succeed for the final SHA.
6. Run final automated verification:

   ```bash
   FINAL_SHA="$(git rev-parse HEAD)"
   ./.venv/bin/python scripts/verify_deploy.py \
     --health-url https://<production-backend>/health \
     --expect-commit "$FINAL_SHA" \
     --check-ci \
     --smoke-url https://<production-frontend>/homepage.html \
     --smoke-url https://<production-frontend>/login.html
   ```

The public smoke checks require HTTP 2xx, nonempty content, and proof that Netlify is no
longer serving `<title>Maintenance</title>`.

7. Complete the manual authenticated checks:
   - homepage and login;
   - enter an existing franchise and load FCC;
   - open a game preview/set-lineup surface;
   - run one short gameplay action appropriate to the release;
   - confirm Railway logs show no new application or database errors.

Production is reopened only when every required check is green.

---

## Optional data and seeding verification

`scripts/verify_deploy.py` also supports reference-data checksums and a new-franchise seed
audit. These are required only when the release changes those surfaces.

Read-only production data verification must use the process-scoped production variables
described in `Environment_Operations.md` and the explicit `--db gob` target:

```bash
GOB_DB_ACCESS=read \
MONGO_URI="$PROD_MONGO_URI" \
MONGO_DB_NAME=gob \
ENVIRONMENT=production \
./.venv/bin/python scripts/verify_deploy.py \
  --db gob \
  --data \
  --snapshot <verified-snapshot-directory>
```

The seed audit requires an authenticated operator to create an unplayed week-1 throwaway
franchise. Deleting it is a production write and therefore requires a separately reviewed
process-level write invocation. Never embed authentication or production credentials in the
verification script.

## Failure and rollback rules

### Failure before reopening

- Leave `MAINTENANCE_MODE=true`.
- Leave the Netlify maintenance wildcard enabled.
- Preserve logs and identify whether Netlify, Railway, CI, code, or data failed.
- Fix forward or revert the failed application commit on `main`.
- Require the same exact-SHA verification before attempting to reopen.

### Failure after reopening

1. Set Railway production `MAINTENANCE_MODE=true` first to stop writes from open tabs.
2. Re-enable the Netlify maintenance wildcard and push.
3. Preserve logs and determine whether code rollback, data recovery, or both are required.
4. For data incidents, follow the Atlas restore procedure in `Environment_Operations.md`;
   never improvise broad compensating writes.

## Why the checks are mandatory

Production previously diverged from `develop` by 158 commits without an obvious surface
showing the running build. `/health` and `scripts/verify_deploy.py` exist to prove that the
tested commit, production environment, `gob` database, deterministic hash seed, and resolved
authorization are the combination actually running.

A UI-created franchise is seeded by deployed code. Local measurement code can then read that
persisted state, creating a silent deployed/local hybrid. Before any measurement season,
deploy first, provision locally, or explicitly normalize every field that changed—including
FPD `position_ratings`.
