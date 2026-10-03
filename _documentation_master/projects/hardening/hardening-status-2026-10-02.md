# Tech hardening: status and restart plan

**Date:** 2026-10-02 (morning); updated 2026-10-03 with the week-close guard (item 16a)
**Reviewed:** `develop` @ `6ef3d58df` (Oct 2); week-close code re-read at `1d71666f4` (Oct 3)
**Companions:** `codebase/codebase-audit-2026-09-29.md` (audit + lanes), `codebase/lane1-progress-2026-09-29.md` (detail up to Sep 30, promotion checklist)

## Where we stand

- **`develop` is healthy for hardening to resume.**
  - Up to Oct 2 morning the backend had barely moved since Sep 30.
  - **On Oct 2 a lot of backend landed with the polish work:** All-American / All-Conference (`BackEnd/utils/all_american.py`, ~1.2k lines), season preview, hidden attrs, office digest, trophy log, and ~580 lines changed in `franchise_routes.py`. Re-run the route inventory before starting 15b.
  - Migration gates pass (Gate B was 134 lines in 43 files on Oct 2).
  - CI has four jobs: `test`, `migration-gates`, `ui-tokens`, `engine-equiv`.
- **UX agents:** Chapter 8 coding is complete; they are on Jamie's walk-through polish.
- **Production is still on the Sep 23 build**, 10 days and several hundred commits behind. Every extra day makes the eventual promotion bigger and riskier.
- **Lanes:**
  - Lane 1: done.
  - Lane 4: mostly done (auth hardening, graceful deploy, pinning, observability, engine check in CI, load-test Phase 1).
  - Lane 3: **not started; now unblocked.**
  - Lane 2 (desktop safety): **not started.**

## Lane 3: the main remaining risk (security grade is still F until this lands)

Route inventory on `develop` (Oct 2): 176 routes, 88 mutating.

**Mutating game/franchise routes with no auth dependency (20):**
- `api.py`:
  - `simulate-quarter`
  - `simulate-turn`
  - `set-playcall-override`
  - `call-timeout`
  - `save-man-defense-matchups`
  - `autoset-lineup`
  - `init-game`
  - `games/delete-completed-single`
- `franchise_routes.py`:
  - `complete-week`
  - `complete-week/phase-a`
  - `complete-week/start-cpu-sims`
  - `complete-week/phase-b`
  - `run-training`
  - `sim-rest-of-tournament`
  - `sim-championship`
  - `finish-season`
- `gameplan_routes.py`:
  - `PUT /api/gameplan`
  - `POST /api/playbooks`
  - `POST /api/playbooks/preview-shot-weights`
- Plus the two diagnostics POSTs, which are gated off by env.

Some of these may check auth inside the handler (simulate-quarter was reported to), so verify per handler.

**Read routes with no auth dependency (~30):** most `GET /franchise/*` (command-center, state, roster, recruits, standings, schedule, leaders, player/team detail, training-report, scouting-report…), `GET /api/gameplan`, `GET /api/playbooks`, `GET /roster/{team}`, and `GET /api/game/{id}/*`.

**Frontend side:** 158 raw `fetch(` calls; 53 files use `getAuthHeaders`. A shared client exists only in pieces (`API_CONFIG.getAuthHeaders`, `fetchWithRateLimitRetry`, `logout`).

### Recommended order
1. **16a: week-close guard** (below). Small, backend-only, closes a real data-integrity hole. Owner: the backend/hardening agent. Run it first.
2. **15a: frontend sends the token everywhere.** One shared fetch helper; move every game/franchise call onto it. Mechanical, no behaviour change.
3. **15b: server requires auth + ownership** on every route above (a router-level dependency + an "is this your franchise/game" check), with real-auth ownership tests. Desktop keeps its local-user override.
4. **16b: server owns results, the rest.** Stop accepting the client-posted `game_document`; move the region reconcile to week-advance.
5. **Enforce week steps:** set-lineup/game page handle the 409; `playbook-report.js` moves to `GET /franchise/next-game`; then `GOB_ENFORCE_WEEK_STEPS=enforce`.
6. **18: Playwright smoke in CI.**
7. **17: hygiene:** one `escapeHtml`, drop `?v=` from ES imports, one Phaser version.
8. **21b: incremental turns in simulate-quarter.**

### 16a: week-close guard (added Oct 3; Jamie's task, assigned to the hardening lane)

**Problem (verified in code at `1d71666f4`):** closing a week trusts the caller.
- The score in `CompleteWeekRequest.result` is written as the final result.
- `is_final` on the game document is only logged, never checked.
- `scripts/ws2_loopback_season.py` played one quarter and then closed the week, storing first-quarter scores (e.g. 20-14) as finals.

**Where the hole actually is:**
- The harness and the live app close a week with **`POST /franchise/complete-week/phase-a` then `/phase-b`** (`finalizeGame.js`; `finish_open_week` in the harness). The single `POST /franchise/complete-week` is only a fallback (`box-score.js`).
- All three entry points share `_complete_week_process_user_game_block` (`franchise_routes.py` ~7338). **The guard belongs there**; a guard only in `complete_week()` misses the real path.

**Requirements for the brief:**
1. Refuse to process the user's game unless the **stored** game document is final. Load it before any request data is applied, and never trust `req.game_document`, which the caller supplies and could mark `is_final: true`.
2. Scope the check to the game being closed (`req.game_id`). Don't block on "any non-final game this week", because abandoned/duplicate in-progress docs would lock players out. Define and test the no-`game_id` legacy lookup; if several docs match, a final one wins.
3. Score: when the stored game is final, use the stored final score for the results row, winner and EOG; ignore the caller's score; log a WARNING when they differ; don't reject on mismatch. Check the team1/team2 ↔ away/home mapping.
4. Refusal uses the existing `_phase_a_conflict(code, message)` 409 shape (new code, e.g. `game_not_final`) so the app shows it, plus a log line (franchise, week, game_id, stored quarter).
5. Weeks with no user game (bye, eliminated) must still close: name the route the app really uses and test it. Online and offline (SQLite) both.
6. Harnesses: `ws2_loopback_season.py`, `scripts/loadtest/run.py`, `scripts/measure_play_cmd_training.py`, `scripts/season_advance_harness.py`. Either play the game to final or use a test-only bypass that can't be reached in production; state the run-time effect.
7. No changes to sim logic, `stat_updater.finalize_game`, `cpu_week_pool` or `sim_rng`. Out of scope: auth on these routes (15b) and removing `game_document` from the request (16b).
8. Gates: migration gates, full pytest on Python 3.11, the week-close tests under SQLite, and the `engine-equiv` smoke unchanged (no re-cut).

**What it doesn't fix:** the routes still need no login, and the client-supplied `game_document` is still accepted for everything else. Those are 15b and 16b.

## New or still-open issues found in the Oct 2 review

1. **`POST /api/games/delete-completed-single`:** unauthenticated delete. Anyone with a game id can delete a completed single-mode game. Limited blast radius, but fold it into 15b.
2. **Probably dead, unauthenticated, mutating:**
   - `POST /franchise/run-training`: no frontend caller; the UI uses `/run-training/user` + `/cpu-train`. Check the season harness before deleting.
   - `POST /franchise/sim-championship`: no caller found.

   Verify and delete (same pattern as Sep 30).
3. **Roster name-lookup fallback catches every `OperationFailure`** (`api.py lookup_team_doc_by_normalized_name`), not just mongomock's missing `$replaceAll`. A real Mongo error would silently take the slow path. Gate it on `USING_MONGOMOCK`, or log when it fires on real Mongo.
4. **No Content-Security-Policy** on Netlify (`netlify.toml` has X-Frame-Options and HSTS only). The JWT lives in localStorage and third-party scripts load (GTM, Sentry CDN), so a CSP matters before beta.
5. **Frontend Sentry is unchanged:** it still sends the user's email as the id, has no environment/release, no scrubbing, and a hard-coded 0.1 trace rate.
6. **Handoffs still open:**
   - `playbook-report.js:303` still uses the POST `play-next-game` as a lookup
   - no frontend handling of the 409 / `next_required_step`
   - the Playbooks e2e baseline file still isn't committed
   - two Phaser versions (3.60 ×5 modules, 3.70 ×6)
   - 17 `escapeHtml` definitions
   - 4 ES imports with `?v=`
7. **No Playwright in CI and no nightly full engine run.** The Sep 30 mongomock break killed the e2e server and CI didn't see it.
8. **The promotion gap** (above). The FCC stale-return real-browser retest is still the stated blocker; confirm it.

## Lane 2: desktop safety (not started; required before the desktop beta)

- Save schema version + migrate-on-open
- Rolling save backups; SQLite `busy_timeout`
- `finish_season` re-entrancy (phase journal / transaction)
- `PYTHONHASHSEED=0` in the Electron launcher (only `start.sh` sets it today)
- Desktop crash reporting (opt-in)
- SQLite leg in CI
- The 4 High-risk URL-identity reads from the Gate B table
- Minimum-spec measurement

## Lane 4 leftovers

- Load-test Phase 2 (needs a quiet window; shared Atlas cluster) → batch CPU-result saves → admission control → widen the pool
- Separate the staging and production Atlas clusters
- A nightly full engine check
- The `on_event` → lifespan migration
- Jamie setup: uptime monitor, Sentry alert rules, Atlas tier/backup status
