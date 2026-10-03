# Franchise flow integrity: 2026-09-30

Branch `fix/flow-integrity` (worktree `../gob-flow`), backend only. No `FrontEnd/` file is touched. Python 3.11.16 venv built from `requirements-dev.txt`.

## Part 1: week-step guard (default: report)

### Where the guard runs: `POST /api/init-game`, franchise mode (`api.py:7658`)

| Candidate | Always hit? | Notes |
|---|---|---|
| `POST /franchise/play-next-game` | **No** | It is only a matchup lookup. set-lineup can be reached without it (lineup URL, `scripts/loadtest`, `ws2_loopback_season` call init-game directly). It also has a lookup-only caller, `playbook-report.js:303`, which resolves the opponent's name. A guard here would report false positives from that page, and in enforce mode it would break the page. |
| `POST /api/init-game` | **Yes** | It is the only thing that creates a franchise game doc: `simulate-quarter` refuses Q1 without an init-game doc (`api.py:4516`). The game is started from set-lineup on load, from PLAY GAME, and from bootGame's pre-anchor Q1 refresh. Resumes (timeout, mid-game reload, the FCC's active-game resume) never call it. |
| `POST /api/simulate-quarter` | Yes, but later | The game doc already exists by then. |

The check runs before init-game's first write (the community-engagement consume) and before `GameManager`. It runs only when `mode == "franchise"` and a `franchise_id` is present. Tutorial, single and scrimmage games are never checked.

### Rules: `pending_week_step(franchise_doc)` (`franchise_routes.py:5710`)

The checks mirror the FCC Advance ladder (`gobAdvance.js:193`) and use the same server fields the FCC reads. The step names reuse the ladder's `data-mode` values. They are checked in this order, and the first one pending is returned:

| # | Step | Pending when | Server source |
|---|---|---|---|
| 1 | `finish-cpu-sims` | This week's phase A is done but the CPU slate isn't finalized (`phase_b_required`) | `_cpu_sim_job_public_summary` (`franchise_routes.py:6540`), which the FCC also uses (`:10846`). Ladder: `gobAdvance.js:216` |
| 2 | `cut-players` | Camp week (`CAMP_WEEKS=1`), training complete, roster over 12 | `_week_1_cut_requirement` (`:13809`), the FCC's `cut_state` (`:10832`). Ladder: `gobAdvance.js:241` |
| 3 | `recruit-invites` | Weeks 20–26 and `recruiting_board_saved_week != week` | `INVITE_FIRST_WEEK/LAST_WEEK` (`:4405`), `RECRUITING_BOARD_SAVED_WEEK_FIELD` (`:4122`), which feeds `recruiting_wire.board_saved_week` (`:4526`). Ladder: `gobAdvance.js:239` |
| 4 | `training` | Week ≤ `LAST_TRAINING_WEEK` (26) and the week isn't fully trained (user and CPU) | `_postseason_training_disabled_for_week` (`:216`), `franchise_training_fully_complete_for_week`, the FCC's `training_completed` (`:10548`). Ladder: `gobAdvance.js:284` |

- **EOS weeks 27–34** have no invite or training step. Their games pass unless step 1 applies, which is correct there too.
- **Weeks 35–36** have no games.
- **Cost:** one projected `franchises.find_one` (7 fields), plus one FTD read in week 1 only. There's no teams scan and no games query.
- **Guard failures:** if the guard itself throws, it logs and lets the game start.

### Modes: `GOB_ENFORCE_WEEK_STEPS`

| Value | Behaviour |
|---|---|
| unset / `report` / anything unknown | Logs a WARNING `[WEEK-STEP-GUARD] violation franchise_id=… week=… pending_step=… context=init_game mode=report` and sends a Sentry `capture_message` ("User game started with a week step pending", level warning; tags `franchise_id`, `week`, `pending_step`, `gob.area=week_step_guard`, `gob.week_step_mode`). The game then starts. Same default on desktop: there is no loopback special case. Desktop Sentry stays off unless `GOB_DESKTOP_SENTRY=1`. |
| `enforce` | Same log and Sentry message, then **409** with `{"detail": "Week 25 step 'recruit-invites' must be completed before this week's game.", "next_required_step": "recruit-invites"}`. Nothing is created or modified (no game doc, no CE consume; the test asserts zero Mongo writes). |
| `off` | No check. |

### Before Jamie flips `GOB_ENFORCE_WEEK_STEPS=enforce`

1. **Handle the 409 on set-lineup.** `set-lineup.js` (init on load at `:898`, `:2449`, `:2798`) and `bootGame.js:2264` should handle 409 by returning to the FCC (`GOBNav.exitFlow`, which reloads fresh) and routing to `next_required_step`. Today a 409 is a generic init error.
2. **Move the opponent lookup off the POST.** `playbook-report.js:303` should switch to `GET /franchise/next-game`. After that, play-next-game has only game-start callers, and it could carry the same guard for earlier feedback (at the Advance click rather than on set-lineup).
3. **Watch the report-mode signal first.** Watch `gob.area=week_step_guard` in Sentry for a few days of staging play. The only expected hits are genuine stale-page starts.
4. **Know the in-flight edge.** A game started in report mode with a step pending, then refreshed pre-Q1 after the flip, would get a 409 on bootGame's Q1 refresh (that refresh re-runs init-game). This is rare, and it goes away with item 1.

### Proof that report mode still starts the game

- **Test:** `test_report_mode_logs_the_violation_and_still_starts_the_game`. Week 25, invites pending: 200 with a game doc, one WARNING line with franchise/week/step/mode, and one Sentry message with those tags.
- **Manual run:** real app, in-process, on mongomock. Not staging: staging writes weren't authorized for this task. select-team needs the full 128-team league, so the week-25 franchise was inserted directly and the real `play-next-game` → `init-game` calls were driven against it:
  ```
  franchise week 25 board_saved_week 24 training done for week 25
  play-next-game 200 {'home': 'Bentley-Truman', 'away': 'Lancaster', 'week': 25}
  [WEEK-STEP-GUARD] violation franchise_id=6abd55c3c18e3f0f70588706 week=25 pending_step=recruit-invites context=init_game mode=report
  init-game 200 game_id 6abd55c447368d3901fdbcc8 game doc exists: True
  ```

## Part 2: play-next-game side effect

### Callers of `POST /franchise/play-next-game`

| Caller | Purpose |
|---|---|
| `FrontEnd/static/js/shared/gobAdvance.js:586` | Starts the game (FCC Advance, recruiting-page Advance, training report). |
| `FrontEnd/static/playbook-report.js:303` | **Lookup only** (opponent name). Should move to the GET. |
| `scripts/ws2_loopback_season.py:234, :502` | Season walker; starts games. |
| `scripts/loadtest/run.py:393` | Load test; starts games. |
| `tests/test_tournament_id_sunset_franchise_contract.py:57` | Route-exists contract. |
| e2e mocks (`office-frontend`, `prep-scouting`, `retire-prep-embed`, `navigation-fixes-3`, `fcc-fresh-after-game`, `desktop-play-flow`, `season-advance`) | Mocked or asserted-absent. No live call. |
| `franchise-command-center.js:2425` | Comment only: Scouting already stopped calling it. |
| `desktop/` | None. |

### `GET /franchise/next-game` (`franchise_routes.py:5932`)

- **Behaviour:** owner-only (`get_current_user` + `verify_franchise_owned_by_user`). Same response shape as the POST, including `eos_meta` in EOS weeks. It never reconciles or writes.
- **Shared lookup:** the lookup is one function, `_lookup_user_next_game` (`:5830`), shared with the POST. So the two can't drift, and the test asserts `GET == POST` byte for byte.
- **Region-week caveat:** in a region week with a half-built bracket that nothing has reconciled yet, the GET can 404 where the POST would first repair the bracket. The command-center load normally reconciles first.
- **Tests:** a Mongo write spy on every collection asserts zero writes, both in the regular season and in a half-built region-week bracket.

### `_maybe_reconcile_region_for_eos` is now idempotent

- **Old behaviour:** it was **not** idempotent. `reconcile_region_tournaments_with_canonical` marked a fully-unplayed region "changed" whenever its slots were incomplete. But the canonical bracket itself carries placeholder slots (`R1_0`/`R1_1` finals, empty regions), so it rewrote an identical blob on every call. That meant every `play-next-game`, and every `command-center/data` load (`franchise_routes.py:~11000`), in weeks 30–31 wrote `region_tournaments` and folded `browse_rev`. That also defeated the FCC's browse ETag in those weeks.
- **Fix** (`franchise_tournament.py:378, :389`): a replacement counts as a change only when it differs from what is saved.
- **Tests:**
  - two direct calls: 1 write, then 0
  - two POSTs: 1 `franchises.update_one`, then 0, with `browse_rev` unchanged
  - the same pair of tests fails without the fix
- **Side effect:** `browse.region_tournaments_stale()` is now accurate (no frontend reads that field).
- **Unchanged:** the POST behaviour is otherwise the same for its callers. It still reconciles before the lookup.
- **Incidental:** the POST no longer constructs `FranchiseManager(db)`. That loaded every team plus a ScheduleManager and RecruitManager, and only `week`/`schedule` were used. Reads only, no behaviour change.

### Moving reconcile to week-advance (later Lane 3 step)

1. **Where brackets are built today.** They are built once at week-advance, in `_eos_calendar_advance_update_fields` (`franchise_routes.py:~7967`, when week 29 completes). The reconcile exists because that build could leave TBD slots (conference champions or RS#1 not yet resolvable).
2. **The step.** Run `reconcile_region_tournaments_with_canonical` right after `initialize_region_tournaments` in that same `$set`. Also run it after each conference-final result lands (the complete-week / phase-b / sim-rest-of-tournament writers).
3. **Then remove the read-path reconciles.** Once the bracket is always canonical when week 30 starts, remove the reconcile from `play_next_game` and from `command_center_data`, which turns them into pure reads. Keep the complete-week call as the last line of defence. It is now a no-op when nothing changed.
4. **Prove it.** Run a season-walker run (`ws2_loopback_season`) through weeks 29→31 with zero `[EOS-REGION-RECONCILE] context=play_next_game|fcc persisted=True` lines.

## Part 3: dead routes deleted

| Route | Callers found (FrontEnd, desktop, tests, scripts, BackEnd, string-built URLs, handler names) | Removed |
|---|---|---|
| `POST /franchise/save-result` | No caller. Two references only: `/tournament/save-result` in a sunset contract test (a different route), and `"save_result"` in `tests/test_home_base_data.py`'s `PLAY_ROUTES`. That is a registry asserting each stamped route carries `@marks_last_played`. It checks the decorator and never calls the handler, so I removed the entry. **Judgement call, flagged:** if Jamie counts registry entries as callers, restore both. | Handler plus `FranchiseResultRequest` (its only user). The helpers it called (`_finalize_team_attributes_for_game`, `_normalize_team_id_to_string`, the archetype helpers) all have other callers and stay. It also read `req.week`, which the model never had. |
| `POST /franchise/delete-current` | None | The POST decorator only. The handler also serves `DELETE /franchise/current`, which is not on this list and stays. It has no caller either: `alpha-feedback.html:302` is a GET of `/franchise/current`. Flagged for a later sweep. |
| `GET /franchise/team-traits` | **Caller found: `tests/test_resource_page_scoping.py:138`**, which calls `franchise_routes.team_traits(...)` directly to test region scoping. No FrontEnd, desktop or scripts caller (the `team-traits.html` hits are the redirect-stub page). | **Not deleted**, per the brief. It is back byte-identical to develop. My first grep was truncated (`head -20`) and missed this; the full suite caught it. Delete the route and that test together if Jamie agrees. |
| `GET /franchise/latest-training` | None | Handler. `latest_training` the field stays (many readers). |

- **Not touched:** `GET /startup-error` and `POST /api/billing/webhook`.
- **Docs:** `SECURITY_BASELINE.md` endpoint list is updated (save-result and latest-training removed, `GET /franchise/next-game` added), and so is `Box_Score_System.md` (save-result was described as live).
- **Stale mentions left:** `Games_Collection.md`, `Player_EM_Overview.md`, `End_Of_Game_System.md` still mention save-result as a legacy path. Not edited.
- **Test:** `test_dead_franchise_routes_are_gone` (covers the three deleted routes, and that `DELETE /franchise/current` stays).

### Unauthenticated-route count

I couldn't find the audit document with the original number, so I measured it by walking every mounted route's dependency tree for `get_current_user` / `require_admin_for_builder`. Hosted build, mongomock.

| | Routes (method+path) | Auth required | Optional auth | **No auth** |
|---|---|---|---|---|
| develop | 180 | 89 | 1 | **90** |
| this branch | 178 | 89 | 1 | **88** |

- **Removed no-auth routes:** `POST /franchise/save-result` (a client-trusted-score route: it took the winner from the request body) and `GET /franchise/latest-training`. `GET /franchise/team-traits` stays (it has a test caller), so it is still one of the 88.
- **Auth-required count:** `POST /franchise/delete-current` was authenticated. It is replaced in the count by the new authenticated `GET /franchise/next-game`, so auth-required stays at 89.
- **Still no-auth:** `POST /api/init-game` is one of the 88. The guard reads the franchise it names but adds no auth, and making it authenticated is out of scope here.

## Files

- `BackEnd/api/franchise_routes.py`: guard (mode / rules / report / 409), `_lookup_user_next_game`, `GET /franchise/next-game`, 3 route removals (save-result, delete-current POST alias, latest-training).
- `tests/test_home_base_data.py`: `save_result` dropped from `PLAY_ROUTES`.
- `BackEnd/api/api.py`: guard call in `init_game`.
- `BackEnd/tournament/franchise_tournament.py`: reconcile only reports real changes.
- `tests/test_week_step_guard.py` (new, 21 tests). Its write spy also patches collection instances. `tests/test_conference_rs_region_modal.py:65` monkeypatches `db.franchises.update_one` on the instance, and on undo that leaves the original bound method as an instance attribute. A class-level spy then sees nothing, which made two of my tests fail only in the full run. It's test-only with no product impact, but anyone spying on writes should know.
- `_documentation_master/SECURITY_BASELINE.md`, `_documentation_master/06_Gameplay_Systems/Box_Score_System.md`.

## Tests

- **`tests/test_week_step_guard.py`:** 21 passed, including in the full-suite order.
  - With `api.py` and `franchise_tournament.py` reverted to develop, 4 fail: report mode, enforce mode, and both idempotency tests.
  - The GET and route-gone tests can't run on develop because the routes differ.
- **Gates:** `scripts/ci/check_migration_gates.py` passed.
- **Full suite:** Python 3.11.16, default config.
  - The first run had 4 failures: `team_traits` still had a test caller, `save_result` was in the `PLAY_ROUTES` registry, and the write-spy shadowing broke two of my tests (all described above).
  - After the fixes: the three affected modules pass in the polluting order, and the full suite re-ran green.
  - XPASS: `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`. Same backend harness entry as on develop, not from this change. `known_failures.py` not edited.

Migration gates: passed (Gate A 0, Gate B 138 lines / 46 files).
Full suite: 4246 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed.
