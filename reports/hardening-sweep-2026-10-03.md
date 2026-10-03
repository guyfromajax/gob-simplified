# Hardening sweep after the UX overhaul

**Date:** 2026-10-03
**Tree:** `develop` @ `feb86c507f84ba2bd80612d82aa2abb342c85cd6` (main checkout, read-only)
**Baseline:** audit commit `8625c30` (2026-09-29)
**Production:** `main` @ `27d9a0dde` (2026-09-23, "Merge branch 'develop'")
**Method:** git diff/log, route parser over `BackEnd/api/*.py` (output in `/tmp/gob-sweep`, not in the repo), handler reads, `scripts/ci/check_migration_gates.py`, `scripts/check_ui_tokens.py --no-write`. No pytest, no server, no DB.

## Summary

The app is in better shape than on 29 September. The fixes from that week (stats, memory, login, rate limits, CI) are still in the code, and the new shell did not undo them. The holes the plan already named are still open, and the new awards code adds a real chance of a slow or racy week close.

Top risks now:

1. Closing a week still trusts the score and game document the browser sends. A week can be saved from a partial game.
2. The actions that play and save a game still do not check who is calling. That was already true in production.
3. The new All-American / All-Conference code can scan a whole franchise's players twice on the first Office or Awards open after a week, and again inside the jump to week 35.

The plan's order still holds. Do the week-close guard first, then send the login token on the calls that still omit it, then require login on the server. Do the week-close guard before the next production promotion. Production is still the 23 September build, 420 commits behind.

---

## A. Delta since `8625c30`

`git rev-list --count 8625c30..HEAD` = **420 commits**.

Whole-tree `git diff --numstat` is dominated by deleted banner binaries and logs (`4054 files, +108372 / −663063`). Code-area totals (`git diff --numstat 8625c30..HEAD` on the paths below; binaries excluded by numstat):

| Area | Files | Added | Removed |
|---|---:|---:|---:|
| BackEnd/api | 7 | 1221 | 658 |
| BackEnd/utils | 27 | 3494 | 122 |
| BackEnd/persistence | 5 | 97 | 3 |
| BackEnd/engine | 1 | 4 | 1 |
| BackEnd/models | 1 | 0 | 352 |
| BackEnd/other | 2 | 23 | 2 |
| FrontEnd/static/js | 83 | 6611 | 3017 |
| FrontEnd/static/css | 38 | 3454 | 1928 |
| FrontEnd/static/other | 119 | 10592 | 29111 |
| FrontEnd/other | 7 | 0 | 816 |
| desktop | 6 | 228 | 41 |
| tests | 186 | 41656 | 1124 |
| scripts | 24 | 3185 | 82 |
| .github | 1 | 41 | 5 |
| _documentation_master | 28 | 3728 | 707 |

`franchise_routes.py` is now **20,991 lines** (`+830 / −379` since the audit). The Oct 2 note of "~580 lines" is stale; more landed after that snapshot. `api.py` is `+237 / −157`.

**New backend modules:** `all_american.py` (1,243), `season_preview.py` (489), `hidden_attrs.py` (130), `observability.py` (353), `request_limits.py` (126), `jwt_config.py` (47), `live_game_cache.py` (152). Grown, not new: `office_digest.py` (+91/−14), `trophy_log.py` (+122/−5), `career_data.py` (+63/−18), `auth.py` (+152/−40), `rate_limiter.py` (+88/−13).

**Deleted backend:** `BackEnd/api/training_routes.py`, `BackEnd/models/training_manager.py`. Engine change is a log-level edit in `skeleton_step_emitter.py` only.

**New routes** (decorator path diff vs `8625c30`): `GET /health/ready`, `GET /franchise/next-game`, `DELETE /franchise/current` (replaces `POST /franchise/delete-current`), `PATCH /franchise/archetype-reveal-seen`, `PATCH /franchise/archetype-evolution-seen`.

**Deleted routes:** `POST /api/run_training`, `POST /api/simulate`, `POST /franchise/save-result`, `POST /franchise/delete-current`, `GET /franchise/latest-training`, `GET /games`, `GET /debug/server-state`, `GET /franchise/debug-names`, `GET /sentry-debug`.

**New frontend modules** (7): `gobLeaveConfirm.js`, `gobToast.js`, `homeBase.js`, `milestoneModal.js`, `seasonPeak.js`, `trophyCase.js`, `views/viewLoader.js`. Shell files changed rather than added: `gobNav.js` +64/−10, `gobAdvance.js` +19/−6, `gobShell.js` +186/−45, `gobStore.js` +26/−2. `franchiseContext.js` has no diff since `8625c30` (last touch `50f85867e`).

**Tests added:** 26 new `tests/test_*.py`, 79 new `tests/e2e/*.spec.js` (plus helpers/fixtures). **CI:** `.github/workflows/test.yml` +41/−5 (ui-tokens + engine-equiv smoke). **Desktop:** icons, fonts, splash/error/pack; no persistence-safety work.

**Scripts added:** `scripts/sim_verify/` (equiv in-repo), `scripts/loadtest/`, `scripts/ops/check_auth_dupes.py`, `scripts/measure_play_cmd_training.py`.

---

## B. Route inventory

**178 routes** in `BackEnd/api/*.py` (17 page/HTML-ish, 161 JSON-ish). **90 mutating.** Oct 2's "176" is two behind this tree (the two archetype PATCH routes and `/health/ready` net of deletions; the parser is the count to use).

How a route was classified:

- **Auth** is `dependency` only when the decorator or signature contains `Depends(get_current_user)`, `get_current_user_optional`, `get_admin_user`, or `require_admin` (substring, so `require_admin_for_builder` counts). **Zero** routes do an in-handler token check without that dependency.
- **Ownership** `yes` means the handler body calls `verify_franchise_owned_by_user` / `verify_game_owned_by_user` / `verify_tournament_owned_by_user` / `_stamp_local_coach`, or a handler I read compares `user_id` (those are tagged in the appendix). `verify_game_owned_by_user` allows a single-mode game with no franchise and no tournament (`BackEnd/utils/ownership.py:102-103`).
- **Writes** means a write call in that handler, or a direct call to `_complete_week_process_user_game_block`, `_complete_week_finish_cpu_and_persist`, `_save_game_result`, `_run_franchise_training_impl`, `save_team_settings`, or `bump_browse_rev`. Writes buried in other helpers can show as `no`.
- **Trusts client doc** means the handler text contains `game_document` or `req.result`. Phase-a/phase-b trust the score by calling the shared block; the flag is `yes` on `complete-week` and `finish-season` only, because the string sits in the callee. Treat all three complete-week entry points as trusting the client (section C).
- **Callers** are exact path-string matches in `FrontEnd/static`, `scripts`, `tests`, `desktop` (`.js/.mjs/.html/.py`). A template that builds the URL will show 0. File-level "has getAuthHeaders" is not a per-call fact; per-call auth is stated only where the call site was read.

Router prefixes applied: `/api/auth`, `/api/admin`, `/api/email`, `/api/billing`, `/api/leaderboard`, `/api/community`.

### Mutating, no auth dependency (30)

Public account/email/billing/feedback routes are supposed to be open. The game/franchise/gameplan set the plan cares about is **21** (the Oct 2 list of 20, plus the two diagnostics, with `delete-completed-single` included in the 20-style count — recount below).

| Method | Path | file:line | Writes | Trusts client | Product callers |
|---|---|---|---|---|---|
| POST | `/api/simulate-quarter` | `api.py:3387` | yes | yes (`game_document` in body) | FE: `bootGame.js:2803` and `gameScene.js` send **no** Authorization (read) |
| POST | `/api/simulate-turn` | `api.py:5666` | yes | no | FE present |
| POST | `/api/set-playcall-override` | `api.py:6388` | no in handler | no | FE |
| POST | `/api/call-timeout` | `api.py:6507` | no in handler | no | FE |
| POST | `/api/save-man-defense-matchups` | `api.py:6664` | yes | no | FE |
| POST | `/api/autoset-lineup` | `api.py:7594` | via helper | no | FE |
| POST | `/api/init-game` | `api.py:7634` | yes | no | FE sends the token (`bootGame.js:2264-2266`). Server does not require it. Week-step guard still called at `api.py:7655-7661` |
| POST | `/api/games/delete-completed-single` | `api.py:8047` | yes (`games` delete) | no | `box-score.js`, `gameCompletionPopup.js`. No auth |
| POST | `/api/diagnostics/sim-quarter` | `api.py:8230` | disk if enabled | no | Returns `{}` unless `GOB_DIAGNOSTICS_ENABLED=1` (`api.py:8226-8237`) |
| POST | `/api/diagnostics/ft-fg-analysis` | `api.py:8391` | same gate | no | same |
| POST | `/franchise/complete-week` | `franchise_routes.py:9376` | yes | **yes** | box-score fallback |
| POST | `/franchise/complete-week/phase-a` | `franchise_routes.py:9485` | yes | **yes via shared block** | `finalizeGame.js:118-123` posts **without** auth headers |
| POST | `/franchise/complete-week/start-cpu-sims` | `franchise_routes.py:9591` | yes | no | FE client exists |
| POST | `/franchise/complete-week/phase-b` | `franchise_routes.py:9696` | yes | no (does not take the user score) | FE |
| POST | `/franchise/run-training` | `franchise_routes.py:17732` | yes via `_run_franchise_training_impl` | no | **no caller** in FrontEnd, scripts, tests, or desktop |
| POST | `/franchise/sim-rest-of-tournament` | `franchise_routes.py:19345` | yes | no | FE |
| POST | `/franchise/sim-championship` | `franchise_routes.py:19648` | yes | no | **only** `tests/test_browse_rev.py` |
| POST | `/franchise/finish-season` | `franchise_routes.py:20126` | yes | yes (flag) | FE. No `get_current_user`. Looks up franchise by id only (`:20138`) |
| PUT | `/api/gameplan` | `gameplan_routes.py:1873` | yes via `save_team_settings` | no | FE |
| POST | `/api/playbooks/preview-shot-weights` | `gameplan_routes.py:3182` | no | no | FE |
| POST | `/api/playbooks` | `gameplan_routes.py:3225` | yes | no | FE |

Also open by design: `POST /api/auth/{check-access-code,request-access-code,signup,login,reset-request,reset-password}`, `POST /api/billing/webhook` (0 in-repo callers; Stripe), `POST /api/email/unsubscribe` (0; email link), `POST /api/feedback`.

`POST /api/admin/reset-user-state` is `Depends(get_admin_user)` (`admin_routes.py:38-42`), not open.

### Read routes with no auth (franchise / game / gameplan)

HTML shells (`/franchise/command-center`, `/franchise/start`, `/animation`, team-builder page) are unauthenticated file responses. The data GETs that are still open:

`/franchise/standings` `:11707`, `/schedule` `:11814`, `/schedule/national` `:11826`, `/schedule/week` `:11832`, `/leaders` `:11905`, `/team-stats` `:12008`, `/player-detail` `:12119`, `/team-detail` `:12128`, `/team-traits` `:12137`, `/team-player-stats` `:12362` and `:12386`, `/player-stats` `:12420`, `/recruits` `:12429`, `/recruit/{recruit_id}` `:12447`, `/state` `:16533`, `/team-data` `:16568`, `/roster` `:16744`, `/scouting-report` `:17116`, `/training-points` `:17643`, `/training-report` `:18403`.

Plus `GET /api/gameplan` `:1471`, `GET /api/playbooks` `:1922`, `GET /roster/{team_identifier}` `api.py:7032`, `GET /player/{player_id}` `:8080`, `GET /teams/{team_id}/players` `:8182`, `GET /api/game/{id}/ft-lock` `:3220`, `.../playbook-settings` `:3267`, `.../lineup-for-matchups` `:6727`, `GET /api/plays` (no auth; builder POST is admin), `GET /api/fcp-skeletons`, `GET /api/hct-skeletons`, `GET /api/validate-pointer`.

`GET /api/game/{game_id}` and `GET .../resume-state` **do** take `get_current_user` and call `verify_game_owned_by_user` (`api.py:2279-2306`, `:3125-3133`).

These browse GETs **do** have auth and `verify_franchise_owned_by_user`: command-center/data `:10586`, league-news, recruiting-data, news, practice-squad/*, tournament brackets, recruiting-results, awards `:16306`, training-squad-reports, championship-moments/context, senior-tribute, next-game, coach-career. The shell's store sends the token on the browse list (section D). The server still accepts the unauthenticated standings/roster/state reads above.

### Routes added since `8625c30`

| Route | Auth | Ownership | Notes |
|---|---|---|---|
| `GET /health/ready` `_bootstrap.py:141` | none | n/a | readiness probe |
| `GET /franchise/next-game` `franchise_routes.py:5940` | yes | yes `verify_franchise_owned_by_user` `:5948` | read-only. **No frontend caller.** Only `tests/test_week_step_guard.py` |
| `DELETE /franchise/current` `:10122` | yes | yes, query by `user_id` `:10132` | replacement for the deleted POST |
| `PATCH /franchise/archetype-reveal-seen` `:18989` | yes | yes via `_stamp_local_coach` → `verify_franchise_owned_by_user` `:19016`; 404 unless local owner `:19017` | desktop-only stamp. FE: `momentQueue.js`, `archetypeReveal.js` |
| `PATCH /franchise/archetype-evolution-seen` `:19030` | yes | same helper | FE: `momentQueue.js` |

The Oct 2 awards/office/hidden-attrs work did **not** add routes. It was wired into existing handlers (`GET /franchise/awards`, command-center/data, finish-season, week-35 advance). Those existing awards/command-center handlers already had auth and ownership. The new code did not open a new unauthenticated route.

`GET /franchise/coach-career` `:10040` is older than this delta (not in the added set) and is auth + ownership. It is the desktop substitute for `/api/auth/me` (comment at `:10044`).

Full 178-row table: appendix.

---

## C. New backend risks (not on the DONE list)

DONE-list items were spot-checked, not re-audited. No regression found: season is in the matchup claim (`stat_updater.py:1849-1851`); `finish_season` clears `applied_matchups` (`franchise_routes.py:20607`) — `applied_games` is not in that `$set` (game ids are deleted at `:20593`, so this is leftover list growth, not the season-collision bug). Claim stale window is still 90s (`franchise_routes.py:6095-6110`). `CPU_SIM_RUNNING_STALE_SECONDS = 180` (`:207`, used `:6319`) is the per-matchup "running" row, not the claim reclaim window. Rate limit still keys on `X-Real-IP` (`rate_limiter.py:42-49`) with default `300/minute` (`:78`).

### Week-close (16a) — still exactly the hole in the plan

`_complete_week_process_user_game_block` uses `req.result` for the score and winner (`franchise_routes.py:7355-7357`, `:7440`, `:7453`). If `req.game_document` is present it is written as the snapshot (`:7496-7514`). `is_final` is logged (`:7502-7503`, `:7606`) and never used as a gate. All three entry points call this block: `complete_week` `:9428`, `complete_week_phase_a` `:9523`, and the combined path. Phase-b does not re-score the user game. The plan's placement (guard in the shared block, not only in `complete_week`) is still right.

### All-American / All-Conference (new)

| Sev | Where | Why |
|---|---|---|
| high | `all_american.py` `load_league` (scan of FTD then all FPD for the franchise, then `teams.find`) | First rebuild after a week reads the whole league in Python. Called from command-center (`franchise_routes.py` around the Office ensure) and `GET /franchise/awards` `:16316-16323` (`ensure_projection` then `_ensure_all_conference` — two scans). |
| high | same ensure functions, whole-`awards` `$set` | Two overlapping reads (Office and Awards, or two tabs) can each write the entire `awards` object and drop the other's keys. |
| high | week-35 callers (`sim-rest` `:19640-19644`, and the advance path that calls `_persist_week_35_awards_if_needed`) | Final awards run `compute_final` → `load_league` **inside** the week advance, not only on a later page view. |
| medium | `compute_final` vs week-26 snapshot | Finals use the frozen `aa_w26` snapshot only if some earlier read already wrote it. A scripted jump to week 35 that never opened Office/Awards can score `season_to_date` and skip the tournament bonus. Normal FCC play usually freezes earlier. **Unverified** how often harnesses hit this. |
| medium | `all_american.py` name/conference `except Exception` | A failed name load becomes empty maps and scoring continues. |
| low | `franchise_routes.py` Office preview / top-recruits `except` | Failures are logged and the page still returns. |

No new collection. Awards live on `franchises.awards`; the week-26 freeze is a field on franchise player docs. `bulk_write` is implemented on the SQLite collection. No new `import random` in these modules (tie-break is sha256). No new `from BackEnd.db import`.

### Other new/changed

| Sev | Where | Why |
|---|---|---|
| medium | `api.py:108` `except OperationFailure` in `lookup_team_doc_by_normalized_name` | Still catches every Mongo `OperationFailure`, not only a missing `$replaceAll`. Known small item. Still accurate. |
| low | `franchise_routes.py:9006-9007` | `random.randint(50, 90)` still fabricates a CPU score when a parallel sim throws. Pre-existing. Uses stdlib `random` (`franchise_routes.py:39`), not `sim_rng`. Not new, still in the week-advance path. |
| low | `_bootstrap.py` readiness dict | New module global for `/health/ready`. Not request-shared game state. |
| low | `HiddenAttrsJSONResponse` on the whole franchise router (`franchise_routes.py:166`) | Every franchise JSON body is copied and stripped. Correctness of the strip is the feature; cost is on large command-center payloads. |

**New env vars** (code reads; not all are required): `GOB_MAX_REQUEST_BYTES`, `GOB_ENFORCE_WEEK_STEPS` (`franchise_routes.py:5697` area), `GOB_CPU_SIM_CLAIM_STALE_SECONDS`, `RATE_LIMIT_WEEK_ADVANCE` / `RATE_LIMIT_CPU_SIMS` / `RATE_LIMIT_FINISH_SEASON` / `RATE_LIMIT_GENERAL`, `GOB_DIAGNOSTICS_ENABLED`, `GOB_DESKTOP_SENTRY`, `SENTRY_TRACES_SAMPLE_RATE`, `GOB_BUILD_ID`. Several of these are the DONE-list work.

**Dead routes, confirmed:** `POST /franchise/run-training` has zero path matches under FrontEnd, scripts, tests, desktop. The UI and harnesses use `/run-training/user` and `/run-training/cpu-train` (those two **do** have auth + ownership, `:17752` and `:17776`). `POST /franchise/sim-championship` matches only `tests/test_browse_rev.py`. `rg` of `scripts/` for those two path strings: no hits.

---

## D. Frontend after the overhaul

`rg -c 'fetch\(' FrontEnd/static --glob '*.js'` sums to **159** `fetch(` hits. That is the same ballpark as the audit's ~158–170, not a collapse. Under `FrontEnd/static/js` alone the count is lower (~86 call sites). There is still no single `apiFetch` that every call must use.

What the shell actually did:

- `API_CONFIG.getAuthHeaders` (`api-config.js:455`) and `fetchWithRateLimitRetry` (429 only) remain.
- `gobStore.js` installs once (`:15`, `:424`) and wraps `window.fetch` (`:426`).
- Browse **GETs** whose path starts with a `BROWSE_PREFIXES` entry (`gobStore.js:24-49`, includes standings, schedule, leaders, command-center/data, awards, gameplan, playbooks, roster, player) get the auth header inside `authHeaders` (`:273-279`) even if the caller forgot it.
- Franchise **writes** go through `mutate` (`:415-420`), which calls the original `fetch` and does **not** add the auth header.
- `simulate-quarter` is explicitly excluded from that write path (`:408`) and is not a browse GET, so the wrapper calls native `fetch` with whatever headers the caller passed (`:441`).
- `postPhaseA` sets only `Content-Type` (`finalizeGame.js:118-123`).
- `init-game` does send the token (`bootGame.js:2264-2266`).
- `play-next-game` is still used as a lookup by `playbook-report.js:303` (auth via `reportPostJson`) and by `gobAdvance.js:598`.
- `next_required_step`: **no matches** under `FrontEnd/static`. A 409 from the week-step guard has nothing to read it. Quarter-already-played 409s are handled in the game page; that is a different code.

**Stale snapshots.** `gob-store:<franchiseId>` in sessionStorage is dropped when a franchise write succeeds (`clearFranchiseFromWrite` `:394`) or when the etag generation (season / week / browse_rev / build) moves (`dropFranchise` also removes `fcc-shell:*`, `:198-200`). `gobAdvance.js` does not call `clearFranchise` itself; it relies on the patched fetch. FCC also reloads on bfcache (`gobNav.js` `pageshow` / `reloadIfStale` around `:380-408` and `:774-790`) and `franchise-command-center.js` `revalidateRestoredFcc`. Warm-paint can still show the old shell until the revalidate returns (comment in the FCC file). Office `gob-office-arrival` is an animation flag, not week data. Standings/roster view order keys are sort UI, and the data path is `GOBStore.revalidate`.

The Sep 30 "hard-refresh retest still pending" note is **not something this sweep re-ran**. The code for that bug class is in place. Whether a real browser still shows a stale locker room is **unverified**.

**bfcache:** handled on the shell (`gobNav.js`) and court (`bootGame.js` pageshow → `GOBNav.reloadIfStale`). Not re-tested in a browser.

**Duplicate modules.** `?v=` ES imports, now **6** (audit said 4): `bootGame.js:2`, `gameScene.js:1`, `animateGameTurns.js:5`, `AnimationRouter.js:15`, `AnimationEngine.js:313`, `animationPlayback.js:1962`. That chain still splits `gameSfx` / animation state. `authGuard` injects `gobStore.js` and the body also tags it; `__gobStoreInstalled` makes the second copy return. `gobNav.js` has no such guard; a second script tag would add listeners again.

**Listeners.** In-app views mount and stay mounted (`gobViews.js`). Several unmounts remove `gob-tab-shown`; `scoutingView.js` unmount is a no-op while a click listener was added. `gobSubtabs.js` document listeners have no remove. This is the shell-lifetime leak the audit warned about, now on the path the shell actually uses. Not measured at runtime.

**innerHTML / escapeHtml.** Named `escapeHtml` still exists in about 16 files plus `escapeHtmlLbt` in `mode-select.js:697` (same "about 17" as the audit). `homeBase.js:29` `esc()` is used for leaderboard names (`:251`, `:261`). `coaching-archetypes-leaderboard.html:106` escapes `r.username`. Mode-select team cards use `escapeHtmlLbt(team.name)` (`mode-select.js:769`). **V8 (unescaped usernames on the mode-select leaderboard) is fixed** on the current Home Base and archetype board. Custom team names in Office go through `gobTables.esc`. A full XSS pass of every `innerHTML` was not done.

**Phaser.** Still both: 3.60.0 in 5 modules (`bootGame.js`, `ballTween.js`, `createBallTrail.js`, `ballManager.js`, `animationTimeline.js`) and 3.70.0 in 6 (`ballAnimationSimple.js`, `passDetection.js`, `ShotAnimationSystem.js`, `fastBreak.js`, `turnAnimation.js`, `openingTip.js`).

| Old flag | Now |
|---|---|
| No shared client | Partial. Browse GETs only. |
| ~158 raw fetches | ~159 in `FrontEnd/static/**/*.js`. Not fixed. |
| FCC stale snapshot | Code paths exist to drop `fcc-shell` and reload bfcache. Browser retest unverified. |
| 17 `escapeHtml` | Still ~17. Not consolidated. |
| 4 `?v=` imports | **6.** Worse. |
| Two Phaser versions | Unchanged. |
| `playbook-report` POST lookup | Still `playbook-report.js:303`. |
| 409 / `next_required_step` | Still no frontend reader. |

---

## E. Desktop / offline

The new UX can run on the loopback build as written, for the franchise path:

- `BackEnd/loopback_app.py` overrides `get_current_user` to the local user (desktop agent read `:34-37`; not re-opened here — consistent with `local_identity.py` and with `api.py:604-608` omitting auth/billing/email/admin/community on the hosted-only include).
- `authGuard.js` skips login when the desktop profile is set.
- `franchiseContext.js` has a Session provider (`:9-16`).
- Trophy/career desktop path uses `save_meta` / `local_coach`, and `save_meta` is in `LOCAL_COLLECTIONS` (`sqlite.py:63`). It is **not** in `_COLLECTION_BINDINGS` (`sqlite.py:81-109`). Access is `db["save_meta"]`, which `__getitem__` serves from the local map (`sqlite.py:239`). That is not `RemoteUnavailable`. No new collection was added for All-American, season preview, hidden attrs, or the office digest.

**Gate** (`python scripts/ci/check_migration_gates.py`, exit 0):

```
Gate A: 0 imports in 0 files
Gate B: 133 lines in 43 files
NOTE: newsView.js count fell 3 → 2. Allowlist not tightened.
```

Oct 2 said 134/43. Live is 133/43. Allowlist still 134. Do not `--write-allowlist` without Jamie; the ratchet can be tightened later.

The four high-risk URL identity reads are still in the code (line numbers moved slightly since the Sep 29 table):

| Read | Now |
|---|---|
| `gobNav.js` `stripParam` → `commitParams(parsed.searchParams)` | ~`:624-630` |
| `gobAdvance.js` `queryId` from `location.search` only | ~`:166-171` |
| `officeHome.js` `teamHref` writes the viewed team into `team_id` | ~`:174-184` |
| `gobNav.js` `guardClosedFranchiseGame` reads `game_id` / `franchise_id` from the URL | ~`:803-808` |

### Lane 2 — not started

| Item | State |
|---|---|
| Save schema version + migrate-on-open | No `schema_version` under `BackEnd/persistence/` |
| Rolling backups | None in persistence or desktop |
| SQLite `busy_timeout` | `sqlite.py` connect has no `timeout=` / `PRAGMA busy_timeout` (connect near `:229`) |
| `finish_season` re-entrancy | One-shot `season_transition_token` (`franchise_routes.py:202`, consumed in `finish_season`). Not a phase journal or multi-collection transaction. V5 still open |
| `PYTHONHASHSEED=0` | `start.sh` only. No match under `desktop/` |
| Desktop crash reporting | `GOB_DESKTOP_SENTRY` opt-in in `observability.py`. Off unless set. No Electron `crashReporter` in `desktop/main.js` |
| SQLite CI | Not in `.github/workflows/test.yml`. Test job sets `GOB_DB_MODE: mongomock` only |
| Gate B high-risk reads | Still present (above) |
| Minimum spec | Still not measured. Audit `:341` still the latest word |

`check_ui_tokens.py --no-write` exit 0. New-design colour-law hits: 0. Legacy hits: 401. Not a gate failure.

---

## F. Tests and CI

**In CI** (`.github/workflows/test.yml`): `migration-gates`, `ui-tokens` (`--strict --no-write`), `engine-equiv` (`equiv --check --smoke`, 60 games, timeout 15 min), `test` (`pytest` on Python 3.11, `GOB_DB_MODE=mongomock`). Audit's "CI is Python 3.12" is **fixed** (workflow `:32` area and the test job both pin 3.11).

**Not in CI:** Playwright, SQLite/desktop mode, full 160-game equiv, nightly engine job. `railway.json` has no CI wait; "Wait for CI" is a Railway dashboard setting recorded in `lane1-progress-2026-09-29.md:54`. **Unverified** from this tree that the dashboard flag is still on. Netlify still does not wait (same doc `:119`).

**UX tests added since `8625c30`:** 26 Python modules (including `test_all_american.py`, `test_season_preview.py`, `test_hidden_attrs.py`, prep-module tests, `test_week_step_guard.py`, `test_desktop_shell_local.py`) and 79 Playwright specs. They do not run in CI.

**`tests/known_failures.py`:** 242 lines. 13 environment skips (5 node-loader, 6 screenshot ESM, 2 mongomock). **109** `XFAIL` entries (`strict=False`). Pytest was not run, so no XPASS claim. A static look did not show a missing test file for those node ids; that is not proof they pass.

**Flaky notes in commit subjects since `8625c30`** (`git log --oneline | rg flake`): court pre-game (`17ec90eae`), signing-orders CDN (`b89ed4c28` and follow-ups), `fcc-fresh-after-game` (`cf5988e63`), recruiting-tabs login redirect, FCC load-retry / player-stats staleness. These are e2e flakes, and e2e is not in CI, so they do not fail the GitHub jobs.

**Scratch / reports:** `git ls-files 'scratch_*.py'` = 7 (kept on purpose; do not delete). Working tree `git status` at start was clean, so the other `scratch_*.py` on disk are untracked/ignored. `git ls-files 'reports/**/*.png'` = **1913**. That is worse than the audit's "859 report files". Not a runtime risk. It is repo weight.

---

## Audit findings, current status

### §2 critical

| # | Status | Now |
|---|---|---|
| V1 season-less claim | **fixed** | `stat_updater.py:1849-1851`; `applied_matchups` cleared `franchise_routes.py:20607` |
| V2 unauthenticated lifecycle + client scores | **still present** | `save_result` is gone. `complete_week` `:9376`, `finish_season` `:20126`, phase-a `:9485` still take no user. Score from `req.result` `:7355` |
| V3 `/api/run_training` | **fixed** | `training_routes.py` deleted |
| V4 `ongoing_games` leak | **fixed** | `BackEnd/utils/live_game_cache.py` (not re-opened) |
| V5 `finish_season` re-entrancy | **still present** | Token is a single consume, not a journal. `:20144-20157` |
| V6 claim heartbeat | **fixed** | Refresh 30s, stale 90s `:6092-6110` |
| V7 two Phaser versions | **still present** | 5× 3.60, 6× 3.70 (section D) |
| V8 unescaped usernames | **fixed** | `homeBase.js:251` `esc(r.name)`; archetype board `escapeHtml(r.username)` |
| V9 desktop `PYTHONHASHSEED` | **still present** | absent under `desktop/` |

### §3 area findings (only where the status changed or the plan depends on it)

- **3.1 Engine.** Pipeline description not re-measured. Engine diff since the audit is `skeleton_step_emitter.py` +4/−1. Equiv **is** in CI as a 60-game smoke (`test.yml` engine-equiv job). The "equiv isn't in CI / aggregator lives in /tmp" line is **fixed** for the smoke (`scripts/sim_verify/`). Full 160 is still not in CI. Global `random` in outcome modules was not re-lined; no new use in the awards modules. Arm divergence: **still present** (no engine behaviour change). Fabricated `random.randint` scores: **still present** `:9006`.
- **3.2 Routes.** 185 → **178**. `franchise_routes.py` grew to 20,991. `api.py` is still inside the module `try`. **Worse** on file size, **better** on dead routes removed.
- **3.3 Persistence.** No new unregistered collection for the UX features. Save schema / backups / `busy_timeout`: **still absent**. Unique email/OTP indexes: DONE-list, `persistence/indexes.py` grew +45. Raw `db.` calls: not recounted; new awards code uses the store's `db`.
- **3.4 Security.** Unauthenticated mutating game/franchise routes: **still present** (21, section B). Debug routes and public `/docs`: **fixed** (`_bootstrap.py:27` sets `docs_url` None outside dev; deleted `/sentry-debug`, `/debug/server-state`, `/franchise/debug-names`). Auth weaknesses in the DONE list: still in force on a spot check (JWT helper, rate-limit key). Client-trusted `game_document` and scores: **still present**. `POST /api/community/debut` still takes client scores, but it is authenticated (`community_highlights_routes.py:37`). CSP: **still absent** (`netlify.toml` has `X-Frame-Options` only). JWT in localStorage: **still**.
- **3.5 Frontend.** Shared store: **partial fix**. `?v=` imports: **worse** (4 → 6). escapeHtml copies: **still**. Playwright not in CI: **still**. FCC stale class: **code fixed, retest unverified**.
- **3.6 CI.** Four jobs, Python 3.11, engine smoke. **Better.** Playwright and SQLite still absent. Railway wait-for-CI is a dashboard setting (documented 30 Sep), not in `railway.json`. Report PNG bloat: **worse** (1913 tracked). Root `CLAUDE.md` now exists: the "no CLAUDE.md" line is **fixed**.
- **3.7 Ops.** Backend Sentry PII: **fixed** (DONE). Frontend Sentry: **still** sends `email` and uses `user.email` as id (`sentryInit.js:44-49`), `tracesSampleRate: 0.1` hardcoded (`:63`), no `environment` / `release` / `beforeSend`. Desktop skips Sentry (`sentryInit.js:13-14`). `on_event` startup/shutdown: **still** `api.py:836` and `:850`. Admission control: **still absent**. simulate-quarter payload: **still** (21b not started). gzip: closed as "Railway already gzips" in the 30 Sep progress note; not re-measured.

### §5 risk register

| # | Status |
|---|---|
| 1 Stats claim | **fixed** |
| 2 Unauthenticated routes | **still** |
| 3 Client-trusted results | **still** |
| 4 Anonymous player-pool write | **fixed** (route deleted) |
| 5 `ongoing_games` leak | **fixed** |
| 6 Re-entrant `finish_season` | **still** |
| 7 No save versioning/backups | **still** |
| 8 No admission control | **still** |
| 9 CI doesn't gate deploys | **better** (Railway wait documented; Netlify still ungated; no Playwright/SQLite) |
| 10 IDOR + debug + spoofable limiter | **partial** — debug and limiter fixed; read IDOR **still** |
| 11 Engine RNG / arm split | **still** (unchanged) |
| 12 Observability | **partial** — backend Sentry fixed; frontend Sentry and desktop crashes **still** |
| 13 simulate-quarter size | **still** |
| 14 Unpinned deps | **fixed** |
| 15 Structural debt | **worse** (`franchise_routes.py` grew) |

---

## G. Verdict on the plan

### Planned items

| Item | Verdict |
|---|---|
| **16a week-close guard** | **Keep as written.** The shared block is still the right place (`_complete_week_process_user_game_block`). Phase-a is still the live path (`finalizeGame.js:118`). `is_final` is still log-only. Score still comes from `req.result`. Do this before promotion. |
| **15a token on every game/franchise call** | **Change the size, keep the item.** Browse GETs already get the header from `gobStore.js` when the shell is loaded. The hole is writes and the game loop: phase-a (`finalizeGame.js:118-123`), `simulate-quarter` (`bootGame.js:2803`), and any franchise write that forgot headers (`mutate` does not add them). One helper that the wrapper uses for every method, including writes, is the change. Not a 159-call rewrite. |
| **15b auth + ownership** | **Keep.** Server still does not require a user on the 21 mutating routes above, or on the open franchise reads. New UX routes were built **with** auth. Do not spend 15b re-doing awards/next-game/archetype stamps. Fold in `delete-completed-single`. Desktop keeps the loopback user override. |
| **16b server owns results** | **Keep, after 16a.** `req.game_document` is still `$set` onto the game (`:7498-7514`). Region reconcile still sits on `play-next-game` (`franchise_routes.py:5923-5931`), and the read-only twin does not reconcile (docstring `:5945-5947`). |
| **Enforce `GOB_ENFORCE_WEEK_STEPS`** | **Keep, blocked on the frontend.** Guard exists on `init-game` (`api.py:7655`). No `next_required_step` reader. `playbook-report.js:303` still POSTs `play-next-game`. Default remains report. Do not flip to enforce until those two moves land. |
| **18 Playwright smoke in CI** | **Keep.** 79 new specs, zero in `.github/workflows`. The Sep 30 mongomock-breaks-e2e lesson is unchanged. |
| **17 hygiene** | **Keep, and the `?v=` half got worse** (6 imports, was 4). escapeHtml still ~17. Phaser still two versions. V8 can come off this item. |
| **21b incremental turns** | **Keep.** No change in `simulate-quarter`'s response shape found in this sweep. |
| **Lane 2 (all eight)** | **Keep. None started**, except the existing one-shot season token and the opt-in `GOB_DESKTOP_SENTRY` flag, which are not the items. |
| **Lane 4 leftovers** | **Keep.** `on_event` still at `api.py:836`. No nightly equiv. No CSP. Frontend Sentry unchanged (`sentryInit.js:44-63`). Load-test phase 2, batch CPU saves, admission control, split Atlas: no code. |
| **Roster `OperationFailure` catch-all** | **Keep.** `api.py:108`. |
| **`delete-completed-single` unauthenticated** | **Keep inside 15b.** `api.py:8047`. |
| **Dead `run-training` and `sim-championship`** | **Keep, and they are safe to delete.** No script caller. `sim-championship` is only a browse-rev test. Do it as a small delete, not as part of 15b's auth pass. |

### New items the plan does not have

| Item | Sev | Size | Lane | Blocks |
|---|---|---|---|---|
| All-American `load_league` twice on first post-advance Office/Awards read, and `compute_final` inside the week-35 advance | high | M | 4 (perf) with a correctness tail | Week-35 advance latency; first Awards/Office paint; the `$set` race can drop one award set |
| Week-26 snapshot skipped when nothing opened Awards before week 35 | medium | S | same change | Tournament bonus on scripted/EOS advances. Confirm with one harness season before coding |
| `gobStore.mutate` does not attach auth (so 15a is not "the store already did it") | high | S | 3, part of 15a | Turning on 15b will 401 phase-a and simulate-quarter |
| Allowlist tighten for Gate B 133 vs 134 (`newsView.js` 3→2) | low | S | 2 | Nothing user-facing. Needs Jamie before `--write-allowlist` |
| `applied_games` not cleared in `finish_season` (only `applied_matchups`) | low | S | 1 leftover | Document growth, not the season-collision bug |

Not new, do not add: game design, colour law (token check is green on new surfaces), engine re-cut (engine barely moved).

### Next 10, in order

1. **16a week-close guard** — one function, stops a fake or partial score becoming the season result, and it is the only correctness fix that should ride the promotion.
2. **Delete `POST /franchise/run-training` and `POST /franchise/sim-championship`** — unauthenticated mutators with no product caller; shrinks 15b.
3. **15a, narrowed** — put the auth header on phase-a/b, complete-week, simulate-quarter/turn, timeout, and gameplan/playbook writes. Point `mutate` at that helper.
4. **All-American: one league load, no full scan inside week advance, awards updates that cannot clobber** — the new code can stall week 35 and the first Office open. Do it while 16a/15a are in review if a second person is free; do not put it after 15b.
5. **15b on the 21 mutating routes, then the open franchise reads** — this is the security grade. Desktop loopback override stays.
6. **Week-step enforce prerequisites** — `playbook-report.js` uses `GET /franchise/next-game`; the client reads `next_required_step`; then set `GOB_ENFORCE_WEEK_STEPS=enforce`.
7. **16b** — stop accepting `game_document`; move region reconcile to week advance.
8. **Playwright smoke in CI** — one path: login, advance, return to the office. The 79 specs are not a smoke suite; pick a handful.
9. **Frontend Sentry scrub + CSP** — before a wider beta, not before this promotion. Email is already sent today on production's frontend if that page is live; the overhaul did not make it worse.
10. **Lane 2 `PYTHONHASHSEED` + SQLite `busy_timeout`** — before any desktop beta build, not before the web promotion.

### Before the next production promotion

Production is `27d9a0dde` (23 Sep). `develop` is 420 commits ahead.

Fix **16a** in `develop` before that merge. The hole exists on production already; the new client still posts `game_document` and the score (`finalizeGame.js`), so the promotion should not ship another month of that write path without the guard.

Do **not** block the promotion on 15b. Those routes are already open on the September build. Blocking on them keeps testers on the old UI.

Do **not** flip `GOB_ENFORCE_WEEK_STEPS` to enforce in the same sitting. Nothing in the client reads `next_required_step`.

Confirm the FCC return in a real browser (hard refresh, play, locker room). The code looks fixed; this sweep did not click through it. That was the named promotion blocker on 30 Sep (`lane1-progress-2026-09-29.md:24`).

Tell testers that the first Office/Awards open after a week, and the week-35 advance, now do a full league read (`all_american.py`). If week 35 feels stuck, that is the first place to look. It is not a reason to hold the promotion by itself.

Railway "Wait for CI" is not in the repo. Check the dashboard flag is still on before the merge (documented 30 Sep, **unverified** here). Netlify will not wait.

---

## Appendix: all 178 routes

Ownership `yes (…)` rows were corrected after reading the handler. Other `yes`/`no` values are from the scanner described in section B. `writes=no` can still hide a helper write. Caller lists are truncated.

| method | path | file:line | auth | ownership | writes | trusts client doc | added | FE files | callers |
|---|---|---|---|---|---|---|---|---|---|
| GET | `/health` | _bootstrap.py:76 | none | no | no | no |  | 0 | scripts/ws2_loopback_season.py, scripts/verify_deploy.py, scripts/loadtest/ramp.py, tests/test_maintenance_mode.py +5 |
| GET | `/health/ready` | _bootstrap.py:141 | none | no | no | no | yes | 0 | tests/test_observability.py |
| POST | `/api/admin/reset-user-state` | admin_routes.py:38 | dependency | no | yes | no |  | 0 | tests/test_auth_hardening.py |
| POST | `/api/alpha-feedback` | alpha_feedback_routes.py:59 | dependency | no | yes | no |  | 3 | FrontEnd/static/alpha-feedback.html, FrontEnd/static/js/config/api-config.js, FrontEnd/static/js/shared/alphaFeedbackModal.js, tests/test_alpha_feedback_routes.py +2 |
| GET | `/app-config` | api.py:469 | none | no | no | no |  | 2 | FrontEnd/static/js/config/api-config.js, FrontEnd/static/js/shared/sentryInit.js, scripts/measure_nav_timing.js, scripts/loadtest/run.py +11 |
| GET | `/` | api.py:2133 | none | no | no | no |  | 327 | FrontEnd/static/tutorial-situation.js, FrontEnd/static/franchise-command-center.html, FrontEnd/static/team-builder.js, FrontEnd/static/tutorial-advanced-practice-squads.html +11 |
| GET | `/teams` | api.py:2143 | none | no | no | no |  | 8 | FrontEnd/static/team-roster-view.js, FrontEnd/static/franchise-command-center.js, FrontEnd/static/mode-select.js, FrontEnd/static/account.html +11 |
| GET | `/api/game/{game_id}` | api.py:2279 | dependency | yes | no | no |  | 0 | scripts/check_game_box_score.py, scripts/check_player_ids.py, scripts/check_tournament_games.py, scripts/check_game_document.py +8 |
| GET | `/api/game/{game_id}/resume-state` | api.py:3125 | dependency | yes | no | no |  | 0 | tests/test_hidden_attrs.py |
| GET | `/api/game/{game_id}/ft-lock` | api.py:3220 | none | no | no | no |  | 0 | — |
| GET | `/api/game/{game_id}/playbook-settings` | api.py:3267 | none | no | no | no |  | 0 | — |
| POST | `/api/simulate-quarter` | api.py:3387 | none | no | yes | yes |  | 4 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/phaser/bootGame.js, FrontEnd/static/js/phaser/gameScene.js, FrontEnd/static/js/phaser/utils/simTimelineAssembler.js +11 |
| POST | `/api/simulate-turn` | api.py:5666 | none | no | yes | no |  | 2 | FrontEnd/static/js/phaser/gameScene.js, FrontEnd/static/js/phaser/animation/AnimationEngine.js, scripts/ws2_loopback_season.py, scripts/loadtest/run.py +6 |
| POST | `/api/set-playcall-override` | api.py:6388 | none | no | no | no |  | 1 | FrontEnd/static/court.html |
| POST | `/api/call-timeout` | api.py:6507 | none | no | no | no |  | 1 | FrontEnd/static/js/phaser/utils/timeoutButtonManager.js, scripts/ws2_loopback_season.py, tests/test_hidden_attrs.py, tests/test_game_id_persistence.py |
| POST | `/api/save-man-defense-matchups` | api.py:6664 | none | no | yes | no |  | 1 | FrontEnd/static/js/phaser/utils/matchupsUiShared.js |
| GET | `/api/game/{game_id}/lineup-for-matchups` | api.py:6727 | none | no | no | no |  | 0 | tests/test_hidden_attrs.py |
| GET | `/roster/{team_identifier}` | api.py:7032 | none | no | no | no |  | 0 | tests/test_hidden_attrs.py |
| POST | `/api/autoset-lineup` | api.py:7594 | none | no | no | no |  | 3 | FrontEnd/static/set-lineup.js, FrontEnd/static/js/phaser/bootGame.js, FrontEnd/static/js/phaser/utils/autosetLineupApi.js, scripts/loadtest/run.py +3 |
| POST | `/api/init-game` | api.py:7634 | none | no | yes | no |  | 3 | FrontEnd/static/tutorial-pick-opponent.js, FrontEnd/static/set-lineup.js, FrontEnd/static/js/phaser/bootGame.js, scripts/measure_play_cmd_training.py +11 |
| POST | `/api/games/delete-completed-single` | api.py:8047 | none | no | yes | no |  | 2 | FrontEnd/static/box-score.js, FrontEnd/static/js/phaser/utils/gameCompletionPopup.js |
| GET | `/player/{player_id}` | api.py:8080 | none | no | no | no |  | 0 | tests/test_hidden_attrs.py |
| GET | `/teams/{team_id}/players` | api.py:8182 | none | no | no | no |  | 0 | tests/test_hidden_attrs.py |
| POST | `/api/diagnostics/sim-quarter` | api.py:8230 | none | no | no | no |  | 1 | FrontEnd/static/js/phaser/bootGame.js, tests/test_endpoint_hardening_heartbeat.py |
| POST | `/api/diagnostics/ft-fg-analysis` | api.py:8391 | none | no | no | no |  | 1 | FrontEnd/static/js/phaser/bootGame.js, tests/test_endpoint_hardening_heartbeat.py |
| GET | `/startup-error` | api.py:8733 | none | no | no | no |  | 0 | — |
| GET | `/api/auth/config` | auth_routes.py:325 | none | no | no | no |  | 0 | — |
| POST | `/api/auth/check-access-code` | auth_routes.py:521 | none | no | no | no |  | 1 | FrontEnd/static/signup.html, tests/test_alpha_access.py, tests/e2e/auth-pages-tokens.spec.js |
| POST | `/api/auth/request-access-code` | auth_routes.py:531 | none | no | no | no |  | 1 | FrontEnd/static/signup.html, tests/test_alpha_access.py, tests/test_alpha_access_email.py |
| POST | `/api/auth/signup` | auth_routes.py:630 | none | no | yes | no |  | 1 | FrontEnd/static/signup.html, tests/test_alpha_access.py, tests/test_observability.py, tests/test_auth_hardening.py |
| POST | `/api/auth/login` | auth_routes.py:752 | none | no | yes | no |  | 1 | FrontEnd/static/login.html, scripts/loadtest/cleanup.py, scripts/loadtest/seed.py, tests/test_observability.py +3 |
| POST | `/api/auth/set-username` | auth_routes.py:810 | dependency | no | yes | no |  | 1 | FrontEnd/static/js/shared/usernameModal.js |
| PATCH | `/api/auth/account-settings` | auth_routes.py:840 | dependency | no | yes | no |  | 0 | — |
| PATCH | `/api/auth/archetype-reveal-seen` | auth_routes.py:889 | dependency | no | no | no |  | 2 | FrontEnd/static/js/shared/momentQueue.js, FrontEnd/static/js/shared/archetypeReveal.js, tests/test_career_data.py, tests/e2e/polish-chrome-followups.spec.js |
| PATCH | `/api/auth/archetype-evolution-seen` | auth_routes.py:900 | dependency | no | no | no |  | 2 | FrontEnd/static/js/shared/archetypeEvolutionModal.js, FrontEnd/static/js/shared/momentQueue.js, tests/test_career_data.py, tests/e2e/polish-chrome-followups-2.spec.js |
| PATCH | `/api/auth/alpha-feedback-prompt-seen` | auth_routes.py:918 | dependency | no | yes | no |  | 1 | FrontEnd/static/js/shared/alphaFeedbackModal.js |
| PATCH | `/api/auth/tutorial-alert-dismiss` | auth_routes.py:958 | dependency | no | yes | no |  | 1 | FrontEnd/static/js/shared/gobTutorialAlerts.js |
| PATCH | `/api/auth/tutorial-alerts-enroll` | auth_routes.py:974 | dependency | no | yes | no |  | 1 | FrontEnd/static/js/shared/gobTutorialAlerts.js |
| PATCH | `/api/auth/tutorial-alerts-increment` | auth_routes.py:1001 | dependency | no | yes | no |  | 1 | FrontEnd/static/js/shared/gobTutorialAlerts.js |
| POST | `/api/auth/reset-request` | auth_routes.py:1035 | none | no | no | no |  | 1 | FrontEnd/static/reset-password.html, tests/test_auth_hardening.py, tests/e2e/auth-pages-tokens.spec.js |
| POST | `/api/auth/reset-password` | auth_routes.py:1062 | none | no | yes | no |  | 1 | FrontEnd/static/reset-password.html, tests/test_observability.py, tests/test_auth_hardening.py |
| GET | `/api/auth/me` | auth_routes.py:1108 | dependency | no | no | no |  | 12 | FrontEnd/static/tutorial-situation.js, FrontEnd/static/franchise-command-center.js, FrontEnd/static/mode-select.js, FrontEnd/static/game-plan.js +11 |
| GET | `/api/auth/leaderboard` | auth_routes.py:1219 | dependency | no | no | no |  | 1 | FrontEnd/static/mode-select.js, tests/test_home_base_server_followups.py, tests/e2e/home-base-online.spec.js, tests/e2e/season-peak-trophy-case.spec.js +4 |
| POST | `/api/auth/fte-complete` | auth_routes.py:1325 | dependency | no | yes | no |  | 0 | — |
| GET | `/api/auth/tutorial-opponents` | auth_routes.py:1358 | dependency | no | no | no |  | 1 | FrontEnd/static/tutorial-pick-opponent.js, tests/e2e/tutorials-fte-tokens.spec.js |
| POST | `/api/auth/tutorial-advance` | auth_routes.py:1414 | dependency | no | yes | no |  | 6 | FrontEnd/static/tutorial-situation.js, FrontEnd/static/game-plan.js, FrontEnd/static/tutorial-persona-intro.js, FrontEnd/static/tutorial-pick-opponent.js +7 |
| POST | `/api/auth/tutorial-complete` | auth_routes.py:1466 | dependency | no | yes | no |  | 1 | FrontEnd/static/js/phaser/utils/gameCompletionPopup.js |
| POST | `/api/auth/logout` | auth_routes.py:1490 | dependency | no | no | no |  | 1 | FrontEnd/static/js/config/api-config.js, tests/test_auth_hardening.py, tests/e2e/logout-auth-header.spec.js, tests/e2e/foundation-settings.spec.js |
| POST | `/api/billing/webhook` | billing_routes.py:41 | none | no | yes | no |  | 0 | — |
| GET | `/api/billing/status` | billing_routes.py:104 | dependency | no | no | no |  | 0 | tests/js/testApiConfigRouting.mjs |
| GET | `/api/community/highlights` | community_highlights_routes.py:18 | dependency | no | no | no |  | 0 | tests/js/testApiConfigRouting.mjs, tests/e2e/home-base-online.spec.js, tests/e2e/home-base-offline-guard.spec.js |
| GET | `/api/community/around-the-league` | community_highlights_routes.py:23 | dependency | no | no | no |  | 1 | FrontEnd/static/mode-select.js, tests/e2e/home-base-online.spec.js, tests/e2e/season-peak-trophy-case.spec.js, tests/e2e/home-base-offline-guard.spec.js +5 |
| POST | `/api/community/debut` | community_highlights_routes.py:37 | dependency | no | no | no |  | 1 | FrontEnd/static/js/phaser/utils/gameCompletionPopup.js |
| GET | `/api/email/unsubscribe` | email_routes.py:36 | none | no | no | no |  | 0 | — |
| POST | `/api/email/unsubscribe` | email_routes.py:45 | none | no | no | no |  | 0 | — |
| POST | `/api/feedback` | feedback_routes.py:37 | none | no | yes | no |  | 2 | FrontEnd/static/js/config/api-config.js, FrontEnd/static/js/shared/authBarInit.js, tests/test_feedback_routes.py, tests/js/testApiConfigRouting.mjs +1 |
| GET | `/court.html` | franchise_routes.py:3409 | none | no | no | no |  | 4 | FrontEnd/static/tutorial-situation.js, FrontEnd/static/mode-select.js, FrontEnd/static/game-plan.js, FrontEnd/static/set-lineup.js +11 |
| GET | `/franchise/start` | franchise_routes.py:3420 | none | no | no | no |  | 0 | tests/js/testApiConfigRouting.mjs |
| GET | `/franchise/select-team` | franchise_routes.py:3425 | none | no | no | no |  | 1 | FrontEnd/static/franchise-select-team.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py, scripts/measure_nav_timing.js +11 |
| POST | `/franchise/select-team` | franchise_routes.py:4710 | dependency | yes (creates for caller, :4721) | yes | no |  | 1 | FrontEnd/static/franchise-select-team.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py, scripts/measure_nav_timing.js +11 |
| GET | `/franchise/team-builder` | franchise_routes.py:4844 | none | no | no | no |  | 0 | tests/test_hidden_attrs.py |
| GET | `/franchise/team-builder/slot-roster` | franchise_routes.py:4849 | dependency | no | no | no |  | 1 | FrontEnd/static/js/team-builder/roster.js, tests/test_hidden_attrs.py, tests/e2e/team-builder-tokens.spec.js |
| GET | `/franchise/team-builder/league-context` | franchise_routes.py:4879 | dependency | no | no | no |  | 0 | tests/test_hidden_attrs.py, tests/test_team_builder_feature_flag.py |
| POST | `/franchise/team-builder/position-ratings` | franchise_routes.py:4967 | dependency | no | no | no |  | 1 | FrontEnd/static/js/team-builder/roster.js, tests/test_hidden_attrs.py, tests/e2e/team-builder-tokens.spec.js |
| GET | `/franchise/team-builder/drafts` | franchise_routes.py:5023 | dependency | yes (list by user_id, :5028) | no | no |  | 2 | FrontEnd/static/team-builder.js, FrontEnd/static/franchise-select-team.js, tests/test_hidden_attrs.py, tests/e2e/shared-chrome-tokens.spec.js +2 |
| POST | `/franchise/team-builder/drafts` | franchise_routes.py:5032 | dependency | yes (upsert by user_id, :5064) | no | no |  | 2 | FrontEnd/static/team-builder.js, FrontEnd/static/franchise-select-team.js, tests/test_hidden_attrs.py, tests/e2e/shared-chrome-tokens.spec.js +2 |
| DELETE | `/franchise/team-builder/drafts/{replaced_object_id}` | franchise_routes.py:5076 | dependency | no | no | no |  | 0 | tests/test_hidden_attrs.py |
| POST | `/franchise/team-builder/wizard-walk-ons` | franchise_routes.py:5096 | dependency | no | no | no |  | 2 | FrontEnd/static/team-builder.js, FrontEnd/static/js/team-builder/roster.js, tests/test_hidden_attrs.py, tests/e2e/team-builder-tokens.spec.js |
| POST | `/franchise/team-builder/portraits/assign` | franchise_routes.py:5172 | dependency | no | no | no |  | 1 | FrontEnd/static/js/team-builder/roster.js, tests/test_hidden_attrs.py, tests/e2e/team-builder-tokens.spec.js |
| POST | `/franchise/team-builder/portraits/reroll` | franchise_routes.py:5213 | dependency | no | no | no |  | 1 | FrontEnd/static/js/team-builder/roster.js, tests/test_hidden_attrs.py |
| POST | `/franchise/team-builder/portraits/pick` | franchise_routes.py:5256 | dependency | no | no | no |  | 1 | FrontEnd/static/js/team-builder/roster.js, tests/test_hidden_attrs.py |
| GET | `/franchise/team-builder/portraits/catalog` | franchise_routes.py:5307 | dependency | no | no | no |  | 1 | FrontEnd/static/js/team-builder/roster.js, tests/test_hidden_attrs.py, tests/e2e/team-builder-tokens.spec.js |
| POST | `/franchise/team-builder/apply` | franchise_routes.py:5321 | dependency | yes (creates for caller, :5345) | yes | no |  | 1 | FrontEnd/static/team-builder.js, tests/test_hidden_attrs.py, tests/test_browse_rev.py, tests/e2e/team-builder-tokens.spec.js |
| GET | `/franchise/command-center` | franchise_routes.py:5681 | none | no | no | no |  | 0 | tests/test_frontend_navigation.py |
| GET | `/animation` | franchise_routes.py:5686 | none | no | no | no |  | 0 | — |
| POST | `/franchise/play-next-game` | franchise_routes.py:5914 | dependency | yes | no | no |  | 2 | FrontEnd/static/playbook-report.js, FrontEnd/static/js/shared/gobAdvance.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py +11 |
| GET | `/franchise/next-game` | franchise_routes.py:5940 | dependency | yes | no | no | yes | 0 | tests/test_week_step_guard.py |
| POST | `/franchise/complete-week` | franchise_routes.py:9376 | none | no | yes | yes |  | 2 | FrontEnd/static/box-score.js, FrontEnd/static/js/phaser/finalizeGame.js, tests/test_tournament_id_sunset_franchise_contract.py, tests/test_browse_rev.py +6 |
| POST | `/franchise/complete-week/phase-a` | franchise_routes.py:9485 | none | no | yes | no |  | 1 | FrontEnd/static/js/phaser/finalizeGame.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py, scripts/loadtest/run.py +8 |
| POST | `/franchise/complete-week/start-cpu-sims` | franchise_routes.py:9591 | none | no | yes | no |  | 1 | FrontEnd/static/js/phaser/utils/franchiseStartCpuSimsClient.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py, scripts/loadtest/run.py +4 |
| POST | `/franchise/complete-week/phase-b` | franchise_routes.py:9696 | none | no | yes | no |  | 2 | FrontEnd/static/box-score.js, FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py +10 |
| GET | `/franchise/list` | franchise_routes.py:10023 | dependency | yes (query by user_id, :10029) | no | no |  | 1 | FrontEnd/static/mode-select.js, tests/test_browse_rev.py, tests/test_home_base_data.py, tests/e2e/home-base-online.spec.js +9 |
| GET | `/franchise/coach-career` | franchise_routes.py:10040 | dependency | yes | no | no |  | 3 | FrontEnd/static/mode-select.js, FrontEnd/static/js/shared/homeBase.js, FrontEnd/static/js/shared/trophyCase.js, tests/test_trophy_log.py +11 |
| GET | `/franchise/current` | franchise_routes.py:10094 | dependency | yes (query by user_id, :10101) | no | no |  | 1 | FrontEnd/static/alpha-feedback.html, tests/test_week_step_guard.py |
| DELETE | `/franchise/current` | franchise_routes.py:10122 | dependency | yes (query by user_id, :10132) | no | no | yes | 1 | FrontEnd/static/alpha-feedback.html, tests/test_week_step_guard.py |
| DELETE | `/franchise/{franchise_id}` | franchise_routes.py:10151 | dependency | yes (inline compare, :10174) | no | no |  | 0 | tests/test_endpoint_hardening_heartbeat.py |
| POST | `/franchise/player/development-focus` | franchise_routes.py:10190 | dependency | yes (inline compare, :10243) | yes | no |  | 2 | FrontEnd/static/js/shared/developmentFocus.js, FrontEnd/static/js/shared/views/playerView.js, tests/test_browse_rev.py, tests/test_development_focus_surfaces.py +9 |
| GET | `/franchise/command-center/data` | franchise_routes.py:10586 | dependency | yes | yes | no |  | 13 | FrontEnd/static/court.html, FrontEnd/static/franchise-tournament-brackets-render.js, FrontEnd/static/franchise-command-center.js, FrontEnd/static/mode-select.js +11 |
| GET | `/franchise/standings` | franchise_routes.py:11707 | none | no | no | no |  | 3 | FrontEnd/static/franchise-command-center.js, FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/standingsView.js, scripts/loadtest/run.py +11 |
| GET | `/franchise/schedule` | franchise_routes.py:11814 | none | no | no | no |  | 1 | FrontEnd/static/js/shared/gobStore.js, tests/test_tournament_id_sunset_franchise_contract.py, tests/test_franchise_game_scoping.py, tests/e2e/store-client.spec.js |
| GET | `/franchise/schedule/national` | franchise_routes.py:11826 | none | no | no | no |  | 0 | tests/e2e/shell-2.spec.js |
| GET | `/franchise/schedule/week` | franchise_routes.py:11832 | none | no | no | no |  | 2 | FrontEnd/static/js/shared/views/rankingsView.js, FrontEnd/static/js/shared/views/leagueScheduleView.js, tests/test_schedule_week.py, tests/e2e/schedule-views.spec.js +7 |
| GET | `/franchise/league-news` | franchise_routes.py:11843 | dependency | yes | no | no |  | 1 | FrontEnd/static/training.js, tests/e2e/prep-modules-gameplan.spec.js, tests/e2e/jamie-rulings-batch.spec.js, tests/e2e/prep-modules-playbooks.spec.js +11 |
| GET | `/franchise/leaders` | franchise_routes.py:11905 | none | no | no | no |  | 4 | FrontEnd/static/team-roster-view.js, FrontEnd/static/franchise-command-center.js, FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/leadersView.js +10 |
| GET | `/franchise/team-stats` | franchise_routes.py:12008 | none | no | no | no |  | 3 | FrontEnd/static/franchise-command-center.js, FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/teamStatsView.js, tests/test_hidden_attrs.py +9 |
| GET | `/franchise/player-detail` | franchise_routes.py:12119 | none | no | no | no |  | 2 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/playerView.js, tests/test_t3_detail.py, tests/e2e/nav-coverage-fix.spec.js +2 |
| GET | `/franchise/team-detail` | franchise_routes.py:12128 | none | no | no | no |  | 3 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/teamView.js, FrontEnd/static/js/shared/views/teamScheduleView.js, tests/test_t3_detail.py +11 |
| GET | `/franchise/team-traits` | franchise_routes.py:12137 | none | no | no | no |  | 0 | tests/test_week_step_guard.py |
| GET | `/franchise/team-player-stats/{team_id}` | franchise_routes.py:12362 | none | no | no | no |  | 0 | — |
| GET | `/franchise/team-player-stats` | franchise_routes.py:12386 | none | no | no | no |  | 2 | FrontEnd/static/team-roster-view.js, FrontEnd/static/js/shared/gobStore.js, tests/test_franchise_team_player_stats.py |
| GET | `/franchise/player-stats` | franchise_routes.py:12420 | none | no | no | no |  | 3 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/playerStatsView.js, FrontEnd/static/js/shared/views/teamView.js, tests/test_player_stats.py +4 |
| GET | `/franchise/recruits` | franchise_routes.py:12429 | none | no | no | no |  | 0 | scripts/ws2_loopback_season.py, tests/test_hidden_attrs.py, tests/test_fpd_frd_smoke.py |
| GET | `/recruit/{recruit_id}` | franchise_routes.py:12447 | none | no | no | no |  | 0 | — |
| GET | `/franchise/recruiting-data` | franchise_routes.py:15774 | dependency | yes | no | no |  | 2 | FrontEnd/static/recruiting-hub.js, FrontEnd/static/js/shared/gobStore.js, scripts/ws2_loopback_season.py, tests/test_hidden_attrs.py +11 |
| GET | `/franchise/news` | franchise_routes.py:15993 | dependency | yes | no | no |  | 2 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/newsView.js, tests/test_hidden_attrs.py, tests/test_all_american.py +11 |
| GET | `/franchise/practice-squad/standings` | franchise_routes.py:16042 | dependency | yes | no | no |  | 1 | FrontEnd/static/js/shared/views/practiceSquadView.js, tests/e2e/practice-squad-view.spec.js, tests/e2e/helpers/tablesLeagueFixtures.js |
| GET | `/franchise/practice-squad/schedule` | franchise_routes.py:16073 | dependency | yes | no | no |  | 1 | FrontEnd/static/js/shared/views/practiceSquadView.js, tests/e2e/practice-squad-view.spec.js, tests/e2e/helpers/tablesLeagueFixtures.js |
| GET | `/franchise/tournament/brackets` | franchise_routes.py:16124 | dependency | yes | no | no |  | 2 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/tournamentView.js, tests/test_tournament_browse.py, tests/e2e/tables-followups.spec.js +2 |
| GET | `/franchise/practice-squad/brackets` | franchise_routes.py:16152 | dependency | yes | no | no |  | 1 | FrontEnd/static/js/shared/views/practiceSquadView.js, tests/e2e/practice-squad-view.spec.js, tests/e2e/helpers/tablesLeagueFixtures.js |
| GET | `/franchise/practice-squad/team` | franchise_routes.py:16169 | dependency | yes | yes | no |  | 1 | FrontEnd/static/team-roster-view.js, tests/test_browse_rev.py, tests/e2e/practice-squad-view.spec.js |
| GET | `/franchise/recruiting-results` | franchise_routes.py:16294 | dependency | yes | no | no |  | 3 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/momentQueue.js, FrontEnd/static/js/shared/bigNewsModals.js, scripts/ws2_loopback_season.py +7 |
| GET | `/franchise/awards` | franchise_routes.py:16306 | dependency | yes | no | no |  | 2 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/awardsView.js, scripts/ws2_loopback_season.py, tests/test_all_american.py +4 |
| POST | `/franchise/recruiting-orders` | franchise_routes.py:16327 | dependency | yes | yes | no |  | 1 | FrontEnd/static/recruiting-hub.js, scripts/ws2_loopback_season.py, tests/test_observability.py, tests/test_browse_rev.py +2 |
| POST | `/franchise/run-week-35-recruiting` | franchise_routes.py:16454 | dependency | yes | yes | no |  | 1 | FrontEnd/static/recruiting-hub.js, scripts/ws2_loopback_season.py, tests/test_browse_rev.py, tests/e2e/signing-day.spec.js |
| GET | `/franchise/state` | franchise_routes.py:16533 | none | no | no | no |  | 3 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/rosterLoader.js, FrontEnd/static/js/phaser/finalizeGame.js, scripts/ws2_loopback_season.py +4 |
| GET | `/franchise/team-data` | franchise_routes.py:16568 | none | no | no | no |  | 4 | FrontEnd/static/franchise-command-center.js, FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/views/scoutingView.js, FrontEnd/static/js/shared/views/teamAttributesView.js +11 |
| GET | `/franchise/roster` | franchise_routes.py:16744 | none | no | no | no |  | 0 | tests/test_hidden_attrs.py, tests/test_fpd_frd_smoke.py, tests/e2e/desktop-first-paint-sweep.spec.js |
| POST | `/franchise/cut-players` | franchise_routes.py:16831 | dependency | yes | yes | no |  | 1 | FrontEnd/static/cut-players.js, scripts/loadtest/run.py, tests/test_browse_rev.py, tests/e2e/store-client.spec.js +2 |
| POST | `/franchise/cut-players-final` | franchise_routes.py:17061 | dependency | yes | yes | no |  | 0 | tests/test_browse_rev.py |
| GET | `/franchise/training-squad-reports` | franchise_routes.py:17098 | dependency | yes | no | no |  | 1 | FrontEnd/static/training-squad-report.js, tests/test_hidden_attrs.py, tests/e2e/tables-followups.spec.js, tests/e2e/hidden-attr-ch.spec.js +1 |
| GET | `/franchise/scouting-report` | franchise_routes.py:17116 | none | no | no | yes |  | 3 | FrontEnd/static/js/shared/gobStore.js, FrontEnd/static/js/shared/scoutingReport.js, FrontEnd/static/js/shared/views/scoutingView.js, tests/e2e/retire-prep-embed.spec.js +4 |
| GET | `/franchise/training-points` | franchise_routes.py:17643 | none | no | no | no |  | 1 | FrontEnd/static/training.js, scripts/measure_play_cmd_training.py, scripts/loadtest/run.py, tests/test_hidden_attrs.py +11 |
| POST | `/franchise/run-training` | franchise_routes.py:17732 | none | no | yes | no |  | 0 | — |
| POST | `/franchise/run-training/user` | franchise_routes.py:17752 | dependency | yes | yes | no |  | 1 | FrontEnd/static/training.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py, scripts/loadtest/run.py +6 |
| POST | `/franchise/run-training/cpu-train` | franchise_routes.py:17776 | dependency | yes | no | no |  | 1 | FrontEnd/static/training.js, scripts/measure_play_cmd_training.py, scripts/ws2_loopback_season.py, scripts/loadtest/run.py +5 |
| GET | `/franchise/training-report` | franchise_routes.py:18403 | none | no | no | no |  | 1 | FrontEnd/static/training-report.js, tests/e2e/prep-modules-report.spec.js, tests/e2e/shell-2.spec.js, tests/e2e/prep-modules-training.spec.js +9 |
| PATCH | `/franchise/region-bye-modal-seen` | franchise_routes.py:18904 | dependency | yes | yes | no |  | 2 | FrontEnd/static/js/shared/regionByeModal.js, FrontEnd/static/js/shared/momentQueue.js, tests/test_browse_rev.py |
| PATCH | `/franchise/conference-rs-region-modal-seen` | franchise_routes.py:18923 | dependency | yes | yes | no |  | 2 | FrontEnd/static/js/shared/momentQueue.js, FrontEnd/static/js/shared/conferenceRsRegionModal.js, tests/test_browse_rev.py |
| PATCH | `/franchise/bracket-reveal-modal-seen` | franchise_routes.py:18943 | dependency | yes | yes | no |  | 2 | FrontEnd/static/js/shared/momentQueue.js, FrontEnd/static/js/shared/bigNewsModals.js, tests/test_browse_rev.py |
| PATCH | `/franchise/elimination-seen` | franchise_routes.py:18970 | dependency | yes | yes | no |  | 1 | FrontEnd/static/js/shared/momentQueue.js, tests/e2e/polish-flow-bugs.spec.js |
| PATCH | `/franchise/archetype-reveal-seen` | franchise_routes.py:18989 | dependency | yes | no | no | yes | 2 | FrontEnd/static/js/shared/momentQueue.js, FrontEnd/static/js/shared/archetypeReveal.js, tests/e2e/polish-chrome-followups.spec.js |
| PATCH | `/franchise/archetype-evolution-seen` | franchise_routes.py:19030 | dependency | yes | no | no | yes | 1 | FrontEnd/static/js/shared/momentQueue.js, tests/e2e/polish-chrome-followups-2.spec.js |
| PATCH | `/franchise/season-review-seen` | franchise_routes.py:19056 | dependency | yes | yes | no |  | 1 | FrontEnd/static/js/shared/momentQueue.js, tests/e2e/season-peak-trophy-case.spec.js, tests/e2e/champ-moment-repeat.spec.js |
| PATCH | `/franchise/recruiting-results-modal-seen` | franchise_routes.py:19075 | dependency | yes | yes | no |  | 2 | FrontEnd/static/js/shared/momentQueue.js, FrontEnd/static/js/shared/bigNewsModals.js, tests/test_browse_rev.py |
| PATCH | `/franchise/recruiting-watchlist` | franchise_routes.py:19113 | dependency | yes | yes | no |  | 1 | FrontEnd/static/recruiting-hub.js, tests/test_browse_rev.py, tests/e2e/signing-day-hub.spec.js, tests/e2e/store-client.spec.js +3 |
| PATCH | `/franchise/recruit-visit-modal-seen` | franchise_routes.py:19172 | dependency | yes | yes | no |  | 1 | FrontEnd/static/js/shared/recruitVisitModal.js, tests/test_browse_rev.py |
| PATCH | `/franchise/invite-seed-modal-seen` | franchise_routes.py:19191 | dependency | yes | yes | no |  | 1 | FrontEnd/static/recruiting-hub.js, tests/test_browse_rev.py |
| PATCH | `/franchise/week-35-reveal-seen` | franchise_routes.py:19210 | dependency | yes | yes | no |  | 1 | FrontEnd/static/recruiting-hub.js, tests/test_browse_rev.py |
| PATCH | `/franchise/week-36-results-seen` | franchise_routes.py:19230 | dependency | yes | yes | no |  | 1 | FrontEnd/static/recruiting-hub.js, tests/test_browse_rev.py |
| PATCH | `/franchise/recruiting-wire-seen` | franchise_routes.py:19250 | dependency | yes | yes | no |  | 2 | FrontEnd/static/franchise-command-center.js, FrontEnd/static/js/shared/gobAdvance.js, tests/test_browse_rev.py, tests/e2e/store-client.spec.js |
| PATCH | `/franchise/walk-on-welcome-modal-seen` | franchise_routes.py:19274 | dependency | yes | yes | no |  | 2 | FrontEnd/static/js/shared/momentQueue.js, FrontEnd/static/js/shared/walkOnWelcomeModal.js, tests/test_browse_rev.py |
| GET | `/franchise/championship-moments/context` | franchise_routes.py:19297 | dependency | yes | no | no |  | 1 | FrontEnd/static/js/phaser/utils/gameCompletionPopup.js, scripts/loadtest/run.py |
| POST | `/franchise/championship-moments/dismiss` | franchise_routes.py:19325 | dependency | yes | no | no |  | 1 | FrontEnd/static/js/shared/championshipMoments.js, tests/test_browse_rev.py, tests/e2e/season-peak-trophy-case.spec.js, tests/e2e/champ-moment-repeat.spec.js +1 |
| POST | `/franchise/sim-rest-of-tournament` | franchise_routes.py:19345 | none | no | yes | no |  | 1 | FrontEnd/static/js/shared/gobAdvance.js, scripts/ws2_loopback_season.py, tests/test_browse_rev.py |
| POST | `/franchise/sim-championship` | franchise_routes.py:19648 | none | no | yes | no |  | 0 | tests/test_browse_rev.py |
| GET | `/franchise/senior-tribute` | franchise_routes.py:20105 | dependency | yes | no | no |  | 1 | FrontEnd/static/js/shared/gobAdvance.js |
| POST | `/franchise/finish-season` | franchise_routes.py:20126 | none | no | yes | yes |  | 1 | FrontEnd/static/js/shared/gobAdvance.js, scripts/ws2_loopback_season.py, tests/test_browse_rev.py, tests/test_auth_hardening.py +1 |
| GET | `/game-plan.html` | gameplan_routes.py:379 | none | no | no | no |  | 8 | FrontEnd/static/box-score.js, FrontEnd/static/franchise-command-center.js, FrontEnd/static/training.js, FrontEnd/static/set-lineup.js +11 |
| GET | `/playbooks.html` | gameplan_routes.py:384 | none | no | no | no |  | 3 | FrontEnd/static/playbook-report.js, FrontEnd/static/js/shared/gobShell.js, FrontEnd/static/js/shared/authGuard.js, tests/test_feedback_routes.py +3 |
| GET | `/playbook-report.html` | gameplan_routes.py:389 | none | no | no | no |  | 4 | FrontEnd/static/franchise-command-center.js, FrontEnd/static/playbooks.js, FrontEnd/static/js/shared/gobShell.js, FrontEnd/static/js/shared/authGuard.js +4 |
| GET | `/tutorial.html` | gameplan_routes.py:394 | none | no | no | no |  | 18 | FrontEnd/static/tutorial-advanced-practice-squads.html, FrontEnd/static/homepage-v3-source.html, FrontEnd/static/homepage.html, FrontEnd/static/tutorial-player-attributes.html +11 |
| GET | `/api/gameplan` | gameplan_routes.py:1471 | none | no | no | no |  | 8 | FrontEnd/static/franchise-command-center.js, FrontEnd/static/game-plan.js, FrontEnd/static/tutorial-pick-opponent.js, FrontEnd/static/set-lineup.js +11 |
| PUT | `/api/gameplan` | gameplan_routes.py:1873 | none | no | yes | no |  | 8 | FrontEnd/static/franchise-command-center.js, FrontEnd/static/game-plan.js, FrontEnd/static/tutorial-pick-opponent.js, FrontEnd/static/set-lineup.js +11 |
| GET | `/api/playbooks` | gameplan_routes.py:1922 | none | no | yes | no |  | 11 | FrontEnd/static/court.html, FrontEnd/static/training-playbooks.js, FrontEnd/static/franchise-command-center.js, FrontEnd/static/playbooks.js +11 |
| POST | `/api/playbooks/preview-shot-weights` | gameplan_routes.py:3182 | none | no | no | no |  | 1 | FrontEnd/static/playbooks.js, tests/e2e/prep-modules-playbooks.spec.js, tests/e2e/first-paint.spec.js, tests/e2e/hidden-attr-ch.spec.js +5 |
| POST | `/api/playbooks` | gameplan_routes.py:3225 | none | no | yes | no |  | 11 | FrontEnd/static/court.html, FrontEnd/static/training-playbooks.js, FrontEnd/static/franchise-command-center.js, FrontEnd/static/playbooks.js +11 |
| GET | `/api/leaderboard/by-team` | leaderboard_routes.py:38 | dependency | no | no | no |  | 1 | FrontEnd/static/mode-select.js, tests/e2e/home-base-offline-guard.spec.js |
| GET | `/api/leaderboard/by-archetype` | leaderboard_routes.py:134 | dependency | no | no | no |  | 1 | FrontEnd/static/coaching-archetypes-leaderboard.html, tests/e2e/community-tokens.spec.js, tests/e2e/first-paint.spec.js |
| GET | `/play-builder-v2.html` | play_routes.py:41 | none | no | no | no |  | 1 | FrontEnd/static/js/shared/adminGuard.js, tests/test_play_builder_redirect.py, tests/e2e/jamie-rulings-batch.spec.js |
| GET | `/play-builder.html` | play_routes.py:47 | none | no | no | no |  | 1 | FrontEnd/static/js/shared/adminGuard.js, tests/test_play_builder_redirect.py, tests/e2e/jamie-rulings-batch.spec.js |
| POST | `/api/plays` | play_routes.py:67 | dependency | no | yes | no |  | 3 | FrontEnd/static/plays-builder.html, FrontEnd/static/play-builder-v2.html, FrontEnd/static/js/config/api-config.js, scripts/fix_3_2_motion_skeleton.py +2 |
| GET | `/api/plays` | play_routes.py:142 | none | no | no | no |  | 3 | FrontEnd/static/plays-builder.html, FrontEnd/static/play-builder-v2.html, FrontEnd/static/js/config/api-config.js, scripts/fix_3_2_motion_skeleton.py +2 |
| GET | `/api/play/{play_name}` | play_routes.py:162 | none | no | no | no |  | 0 | — |
| GET | `/api/plays/{play_id}` | play_routes.py:195 | none | no | no | no |  | 0 | — |
| DELETE | `/api/plays/{play_id}` | play_routes.py:220 | dependency | no | yes | no |  | 0 | — |
| POST | `/player-image/ensure` | player_image_routes.py:153 | dependency | no | yes | no |  | 2 | FrontEnd/static/recruiting-hub.js, FrontEnd/static/js/config/api-config.js, tests/test_browse_rev.py, tests/js/testApiConfigRouting.mjs |
| POST | `/recruit-image/ensure` | player_image_routes.py:208 | dependency | no | no | no |  | 1 | FrontEnd/static/js/config/api-config.js |
| POST | `/player-image/warm-teams` | player_image_routes.py:361 | dependency | no | no | no |  | 1 | FrontEnd/static/set-lineup.js, scripts/loadtest/run.py, tests/test_browse_rev.py |
| GET | `/api/validate-pointer` | pointer_validation_routes.py:15 | none | no | no | no |  | 1 | FrontEnd/static/js/shared/pointerValidation.js, tests/e2e/game-start-sequence.spec.js |
| POST | `/franchise/press-conference/session` | press_conference_routes.py:190 | dependency | yes | yes | no |  | 1 | FrontEnd/static/js/phaser/utils/postGamePressConference.js |
| POST | `/franchise/press-conference/session/{session_id}/answer` | press_conference_routes.py:265 | dependency | yes (session user_id, :275) | yes | no |  | 0 | — |
| POST | `/franchise/press-conference/session/{session_id}/complete` | press_conference_routes.py:309 | dependency | yes (session user_id, :318) | yes | no |  | 0 | — |
| GET | `/fcp-skeletons.html` | skeleton_routes.py:46 | none | no | no | no |  | 1 | FrontEnd/static/js/shared/adminGuard.js |
| GET | `/hct-skeletons.html` | skeleton_routes.py:52 | none | no | no | no |  | 1 | FrontEnd/static/js/shared/adminGuard.js |
| POST | `/api/fcp-skeletons` | skeleton_routes.py:63 | dependency | no | yes | no |  | 2 | FrontEnd/static/fcp-skeletons.html, FrontEnd/static/js/config/api-config.js, tests/js/testApiConfigRouting.mjs |
| GET | `/api/fcp-skeletons` | skeleton_routes.py:110 | none | no | no | no |  | 2 | FrontEnd/static/fcp-skeletons.html, FrontEnd/static/js/config/api-config.js, tests/js/testApiConfigRouting.mjs |
| POST | `/api/hct-skeletons` | skeleton_routes.py:134 | dependency | no | yes | no |  | 2 | FrontEnd/static/hct-skeletons.html, FrontEnd/static/js/config/api-config.js, tests/js/testApiConfigRouting.mjs |
| GET | `/api/hct-skeletons` | skeleton_routes.py:181 | none | no | no | no |  | 2 | FrontEnd/static/hct-skeletons.html, FrontEnd/static/js/config/api-config.js, tests/js/testApiConfigRouting.mjs |


---

## Git status

**First command** (`git status --short` then `git rev-parse HEAD`), before any other work:

```
(no output — clean)

feb86c507f84ba2bd80612d82aa2abb342c85cd6
```

Branch: `develop`. HEAD subject: `Add tech-hardening docs (audit, progress, status) as dated snapshots` (2026-10-03 08:23:14 -0400).

**Last command** (`git status --short`), after this report was the only write:

```
?? reports/hardening-sweep-2026-10-03.md
```

HEAD unchanged: `feb86c507f84ba2bd80612d82aa2abb342c85cd6`.
