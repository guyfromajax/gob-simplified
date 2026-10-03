# Technical work progress (Lane 1 + Lane 4) and desktop follow-ups

**Last updated:** 2026-09-30 end of day
**Companion to:** `codebase/codebase-audit-2026-09-29.md` §6

## Where things stand (end of Sep 30)

**The backend-only hardening lane is essentially caught up.** What remains is waiting on:
- Jamie's quick setup items and the FCC retest (below)
- the load-test Phase 2 window
- **Lane 3**, after the UX overhaul lands: auth/ownership on the remaining routes, server-owned results/flow + enforce mode, escaping/fetch client, Playwright in CI
- **Lane 2**, folded into the desktop build: save versioning, finish_season safety, backups, crash reporting, the SQLite CI leg, min spec

## Production promotion checklist (do these in the same sitting)

1. Check that `develop` CI is green for the commit you're promoting: all four jobs (`test`, `migration-gates`, `ui-tokens`, `engine-equiv`).
2. Pick a quiet time: few testers online, nobody mid-week-advance.
3. **Railway production → backend service → Variables:** add these, in the same sitting as the promotion (adding a variable redeploys immediately):
   - `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=180`, which goes with the graceful-deploy code
   - `SENTRY_TRACES_SAMPLE_RATE=0.03` (optional), so simulate-turn traces don't burn the Sentry free quota
   - leave `GOB_ENFORCE_WEEK_STEPS` unset (= report) until the enforce prerequisites (handoff 8) are done
4. Confirm `JWT_SECRET_KEY` is set (it is, checked Sep 30) and `ENVIRONMENT=production`.
5. Optional: re-run the auth dupes check against production (clean Sep 30).
6. **Confirm the FCC stale-return fix works in a real browser first:** the hard-refresh retest (⌘⇧R on the FCC → play → Go To Locker Room → correct fresh state).
7. Merge `develop` → `main` and push. Production waits for CI, then deploys.
8. Afterwards:
   - log in on production and advance a week (a weeks-20–26 week if possible, returning to the FCC after the game)
   - check Online
   - switch the uptime monitor to `/health/ready`
   - **tell testers to hard-refresh once**

What goes live with the first promotion after Sep 23:
- the stats-claim fix
- the memory-leak fix
- the endpoint lockdown + heartbeat
- auth hardening + the rate limiter
- graceful deploy
- pinned dependencies (FastAPI 0.142 / Starlette 1.7)
- observability
- the FCC stale-return fix
- the week-step guard (report mode)
- the idempotent region reconcile
- the 1 MiB request cap + 422s no longer echoing input
- 6 dead/unauthenticated routes removed

## Done Sep 29–30 (all merged to develop; staging week verified unless noted)

- **Lane 1 (closed):**
  - the stats-claim fix
  - `ongoing_games` eviction (+ the py3.11 hotfix)
  - endpoint hardening + heartbeat
  - CLAUDE.md + repo hygiene
  - green migration gates
  - Railway "Wait for CI" on staging + production

  Decision: no GitHub status-check protection on `main` (promotion merge commits have no checks; "Wait for CI" covers it).
- **Item 19, auth hardening + rate limiter** (`7c619be`).
  - A spoofed-IP curl check gave 10×401 then 429.
  - `RATE_LIMIT_*` env vars.
  - Report: `reports/auth-hardening-2026-09-30.md`.
- **Graceful deploy.**
  - Claim stale window 300 s → 90 s; the shutdown hook releases only this process's claims; uvicorn `--timeout-graceful-shutdown 150`; staging drain 180 s.
  - Still lost on deploy: in-memory live games (per-turn persistence is a PvP/ghost-live prerequisite).
- **Item 24, pinned dependencies.**
  - `requirements.in` → pip-compile (3.11) → `requirements.txt`; `requirements-dev.txt` for CI; mongomock is dev-only.
  - Framework jump verified (`on_event` hooks + the graceful flag).
- **Item 22, observability.**
  - Sentry: no PII, a fail-closed scrubber, release = SHA, environment from `ENVIRONMENT`.
  - Tags; `[HCO ENTRY BUG]` demoted; `SENTRY_TRACES_SAMPLE_RATE`; `GET /health/ready`.
  - `ENVIRONMENT` also drives the DB guard + static serving (staging = `staging`).
- **FCC stale return (UX agent).**
  - Cause: the sessionStorage shell copy set the Advance before real data; a failed first read left it live; gobStore ran twice.
  - Fix: Advance disabled until server data; first-read retries; bfcache revalidation. **Real-browser retest pending.**
- **Flow integrity.**
  - Week-step guard on `POST /api/init-game`: `GOB_ENFORCE_WEEK_STEPS` report (default everywhere) | enforce | off. It mirrors the FCC Advance ladder.
  - New read-only `GET /franchise/next-game`; the region reconcile is idempotent.
  - Deleted save-result, delete-current, latest-training.
  - Report: `reports/flow-integrity-2026-09-30.md`.
- **Item 21a, gzip: closed, no change.** Railway's edge already gzips every response, including 30–40 MB simulate-quarter POSTs (~7×). App-level gzip would add 100–200 ms CPU per big response on the single process for no client gain. The real fix is incremental turns in simulate-quarter (frontend + backend → Lane 3). Report: `reports/gzip-2026-09-30.md`.
- **Security batch 2.**
  - Request body cap of 1 MiB (`GOB_MAX_REQUEST_BYTES`). The largest real body is a ~130 KB phase-a game doc; 413 carries CORS.
  - 422s keep only loc/msg/type (no input echo).
  - Deleted `GET /games` (anyone's game docs) and `POST /api/simulate` + `/simulate` (unauthenticated full sim that wrote to `games`).
  - **Note for college/pro:** roster/league uploads may need a larger cap or a per-route limit.
  - Report: `reports/security-batch-2-2026-09-30.md`.
- **Item 23, engine regression check in CI.**
  - Tooling in `scripts/sim_verify/`: worker, a rebuilt aggregator, and the `equiv` entry point. `scratch_equiv3_fbdedupe.py` is a thin wrapper.
  - Pointers `CURRENT_REFERENCE` (`equiv_v3_reference_f600628a4_agspread.json`) and `CURRENT_LOOSE_BASELINE`.
  - Develop matched exactly: 160/160 and 80/80 byte-identical.
  - **CI job `engine-equiv`:** a 60-game smoke (14 coverage-selected seeds × 4 cells + 4 loose games), ~3.5 min, running in parallel with `test`.
  - **Re-cut:** `python -m scripts.sim_verify.equiv --recut --reason … --slug …` (runs twice, refuses in CI or with a dirty tree; needs Jamie's approval).
  - **Limit:** rare-path changes can slip the smoke (a test nudge moved 5/160 full, 1/60 smoke), so engine work must still run the full local check.
  - Report: `reports/equiv-in-ci-2026-09-30.md`.
- **Item 25, load test:** Phase 1 done and merged; **Phase 2 postponed** until Jamie picks a window.
  - Staging = production hardware (32 vCPU / 32 GB, 1 replica, pool on, 8 workers).
  - The week advance swings ~2.5× by time of day (~50 s vs ~125 s).
  - start-cpu-sims ≈ 50 s: ~34 s pool, ~14 s serial saves, ~1.5 s setup.
  - Phase 2 go-message decisions:
    - replace the 120 s stop rule with "3× the endpoint's N=1 p95, or >300 s"
    - re-baseline N=1 at the start and end
    - rate-limit overrides during the run (report §6), removed after
  - Report: `reports/load-test-2026-09-30.md`.

## Jamie to-do

- the FCC hard-refresh retest (blocks promotion)
- an uptime monitor (UptimeRobot / Better Stack) on staging `/health/ready` + production `/health`
- Sentry alert rules (production: new issue, regression, spike, >50/hour; staging: daily digest)
- recording the Atlas tier + backup status
- a local Python 3.11 venv from `requirements-dev.txt`
- telling engine/animation agents that intentional outcome changes now turn CI red until a re-cut is approved
- picking the load-test Phase 2 window
- the staging test league is compromised (week 26 skipped invites/training), so use a fresh franchise for clean season testing

## Infra facts

- `gob` and `gob-staging` share **MVP-Cluster (Atlas project gob-mvp)**.
- Railway staging = project "resplendent-mercy"; production = "motivated-liberation". Both are 32 vCPU / 32 GB.
- The frontend on Netlify deploys without waiting for CI.
- **Running production scripts:** `read -s PROD_MONGO_URI`, then `GOB_DB_ACCESS=read MONGO_URI="$PROD_MONGO_URI" MONGO_DB_NAME=gob ENVIRONMENT=production .venv/bin/python <script> --db gob`, then `unset PROD_MONGO_URI`. Worktrees need `.env.local` copied from gob-simplified for staging scripts.

## Open handoffs to UX/frontend agents

1. ~~Logout bearer~~, ~~429 retry on week routes~~ (done).
2. **Playbooks baseline:** commit `reports/prep-modules-playbooks/before-metrics.json`.
3. **Game Plan `game_id`:** `game-plan.js` `init()` never reads `options.game_id`.
4. **Frontend Sentry (`js/shared/sentryInit.js`), before beta:**
   - it sends the email as the id
   - no environment/release (use `/app-config`)
   - no scrubbing (reset-token URLs)
   - hard-coded 0.1 tracing
   - no SRI
5. **Training screen UX:** Submit is silently disabled until points + focus are set (Jamie handling).
6. ~~FCC stale return~~: fixed; the retest is pending.
7. **FCC "Couldn't load your season — Retry" state:** queued (`fix/fcc-load-retry`).
8. **Before `GOB_ENFORCE_WEEK_STEPS=enforce`:**
   - set-lineup/the game page must handle the 409
   - `playbook-report.js` should move to `GET /franchise/next-game`
   - watch the staging week-step warnings for a few days
9. **Roster name lookup on mongomock** (`fix/roster-name-lookup-mongomock`, UX audit agent): the fallback should trigger only on mongomock (`USING_MONGOMOCK`) or log when it fires on real Mongo, not catch all `OperationFailure`s silently.

## Backlog (backend, not blocked)

- **A nightly full engine check:** a scheduled CI job running all 160 games on develop, to catch rare-path drift the smoke misses.
- **The `on_event` → lifespan migration** (deprecated in the pinned FastAPI); keep the graceful-deploy shutdown identical.
- **Load test Phase 2** → **batch CPU-result saves** (~14 s → ~2 s per week) → **item 20, admission control** → widen the pool.
- **Separate the staging and production Atlas clusters** (before the January beta).
- **Test hygiene:** `tests/test_conference_rs_region_modal.py:65` leaves a patch that hides class-level write spies.

## Lane 3 (after UX lands)

- **Item 15:** auth + ownership on the remaining routes, incl. init-game, simulate-quarter, simulate-turn, phase-a (called without a token today).
- **Item 16:** server-owned results / flow, incl. `GOB_ENFORCE_WEEK_STEPS=enforce` and moving the region reconcile to week-advance (after week 29).
- **Item 17:** escaping + a shared fetch client + duplicate-module fix.
- **Item 18:** Playwright smoke in CI. Today a mongomock break killed the full Playwright server and CI didn't notice.
- **Item 21b:** incremental turns in simulate-quarter (the real payload fix).

## Gate B re-baseline (Sep 29)

144 URL-read lines in 50 FrontEnd files were frozen, not fixed, because the UX agents are editing those files (136 in 44 by end of Sep 30 as cleanup removed files). Classification: 67 UI state, 41 not a read, 36 franchise identity (4 High desktop risk, 29 Low, 3 None). Full table: `reports/migration-gates-rebaseline-2026-09-29.md`.

## Desktop-lane follow-ups (add to Lane 2)

Fix these when the UX overhaul is done with those files, before the desktop beta:

1. **`gobNav.js:625` `stripParam()`** passes the whole URL query to `FranchiseContext.commitParams`. On desktop this wipes session-only identity. Called from `recruiting-hub.js`.
2. **`gobAdvance.js:158` `queryId()`** reads `franchise_id`/`team_id` from the URL only.
3. **`officeHome.js:173` `teamHref()`** sets `team_id` to the *viewed* team when the URL has none.
4. **`gobNav.js:796` `guardClosedFranchiseGame()`** reads `game_id` from the URL only.
5. *(Check)* **`leagueScheduleView.js:57`** writes the browse `week` into the URL.
6. *(Minor)* The Game Plan and Playbooks redirect stubs decide from the URL while their modules decide from FranchiseContext.

Also noted: `schedule_browse.py` still makes raw `db.teams`/`db.games`/`db.franchises` calls through `_store.db` (part of the adapter-bypass pile, audit §3.3).
