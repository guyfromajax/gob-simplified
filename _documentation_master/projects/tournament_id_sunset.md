# `tournament_id` Sunset

**Status:** Phases 0–3 completed; stop before Phase 4
**Created:** July 24, 2026  
**Scope:** Retire the legacy standalone Tournament Mode and its
`tournament_id` compatibility surface without disrupting Franchise tournament
weeks  
**Important:** This plan does not authorize deletion of production tournament
documents or other persisted user data.

---

## 1. Executive Summary

`tournament_id` is not 100% dormant and is not safe to delete as an isolated
variable.

The old standalone Tournament Mode is no longer exposed through the intended
mode-selection flow, but its implementation remains live and reachable. The
backend still mounts its router, its API endpoints still read and write
tournament documents, direct frontend pages can still start and resume the
mode, and shared gameplay screens still branch on `mode === "tournament"` and
propagate `tournament_id`.

The safe approach is to retire the complete standalone Tournament Mode
compatibility surface in deliberate stages. Active Franchise tournament weeks
must remain supported. They are a separate system whose authority is
`franchise_id`, franchise week state, `tournament_schedule`, and
`tournament_context`; they do not require the legacy standalone
`tournament_id`.

---

## 2. Audit Conclusion

### 2.1 What is obsolete

The sunset target is the original standalone Tournament Mode:

- tournament selection and creation outside Franchise;
- standalone tournament documents and bracket progression;
- tournament-specific game launch and resume flows;
- standalone tournament result persistence;
- standalone tournament roster, scouting, training, and team-data routes;
- shared-page branches whose only purpose is `mode === "tournament"`;
- the `tournament_id` field used to connect games and requests to that mode.

### 2.2 What remains active

The legacy system remains executable in the current codebase:

- `BackEnd/api/api.py` imports and mounts `tournament_router`;
- `BackEnd/api/tournament_routes.py` exposes creation, current-state, deletion,
  round simulation, result saving, team data, scouting, roster, training, and
  remaining-game operations;
- tournament selection and tournament management frontend assets can still
  initiate and operate the mode;
- gameplay, court entry, finalization, game-plan, playbook, roster, training,
  timeout, and navigation code still propagate or branch on `tournament_id`;
- game loading and simulation code still loads and persists tournament-linked
  records;
- ownership, pointer validation, and retention logic still recognize
  tournament documents and tournament-linked games.

Therefore, removal of only the request field or only the backend model would
break reachable paths and leave a partially retired feature.

### 2.3 What must not be removed

Franchise tournament weeks are active product behavior and are outside the
sunset target. Preserve:

- `franchise_id`;
- the Franchise season week and schedule;
- `tournament_schedule`;
- `tournament_context`;
- Franchise tournament bracket/state;
- Franchise CPU simulation and persistence;
- Franchise tournament UI and navigation;
- any generic use of the word “tournament” that refers to a Franchise
  tournament week rather than the legacy standalone mode.

The removal criterion is semantic, not a global text replacement.

---

## 3. Why an Isolated Variable Deletion Is Unsafe

`tournament_id` currently acts as more than a dormant schema field. Depending
on the path, it is used as:

- request context;
- URL/query context;
- a game-document relationship;
- the lookup key for a standalone tournament document;
- a persistence destination for results and state;
- an ownership and access-control input;
- a navigation and page-mode discriminator;
- a retention signal preventing linked games from being removed;
- a compatibility branch in shared Franchise-adjacent endpoints.

Deleting the name without retiring those behaviors would create failures such
as:

- requests accepted by the frontend but rejected by backend models;
- completed games that cannot save their result;
- old direct URLs that enter a broken partial mode;
- ownership checks against missing context;
- incorrect cleanup or retention of tournament-linked games;
- shared screens selecting the wrong data source;
- confusion between a legacy standalone tournament and an active Franchise
  tournament week.

---

## 4. Required Product Decision Before Implementation

Confirm whether existing standalone Tournament Mode saves must remain playable.

If they do not need to remain playable, implementation may intentionally retire
the endpoints and redirect or reject old direct links. Persisted data should
still be left intact unless a separate data-retention decision explicitly
authorizes archival or deletion.

If old saves must remain playable, `tournament_id` cannot be fully sunset yet.
The appropriate result would instead be to rename and isolate the legacy
surface, clearly marking it as compatibility code.

This is the only material product decision required before beginning the
retirement.

---

## 5. Phase 0 Execution Record

**Completed:** July 24, 2026

The product decision is resolved: existing standalone Tournament Mode saves do
not need to remain playable. This authorizes intentional retirement of their
entry points and APIs in later phases. It does not authorize deletion of their
persisted data.

Phase 0 made no runtime changes.

### 5.1 Current reference baseline

The inventory commands found:

- 222 backend `tournament_id` references across 15 Python runtime files;
- 138 frontend `tournament_id` references across 26 JavaScript/HTML files;
- 44 test references across 14 Python test files.

Counts are a removal baseline, not a global replacement target. Some test and
documentation references should remain temporarily to prove that the legacy
surface is retired intentionally.

### 5.2 Backend executable inventory

| Category | Files | Retirement responsibility |
|---|---|---|
| Standalone API and manager | `BackEnd/api/tournament_routes.py`, `BackEnd/tournament/tournament_manager.py`, `BackEnd/tournament/bracket_logic.py` | Remove after entry is closed and no caller remains |
| Application/game lifecycle | `BackEnd/api/api.py`, `BackEnd/models/turn_manager.py`, `BackEnd/models/team_manager.py` | Remove standalone game initialization, loading, mode propagation, and persistence branches |
| Game plan/playbooks/settings | `BackEnd/api/gameplan_routes.py`, `BackEnd/utils/team_settings_manager.py`, `BackEnd/utils/team_id_resolver.py`, `BackEnd/utils/payload_builder.py` | Remove standalone context selection and request fields while retaining Franchise selection |
| Results and statistics | `BackEnd/utils/stat_updater.py` | Remove standalone tournament aggregation, idempotency, leader recomputation, and finalize behavior |
| Training | `BackEnd/models/training_manager.py`, `BackEnd/api/franchise_routes.py` | Remove standalone training compatibility; preserve Franchise training and EOS behavior |
| Ownership and pointers | `BackEnd/utils/ownership.py`, `BackEnd/utils/pointer_validation.py`, `BackEnd/api/pointer_validation_routes.py` | Remove the legacy document relationship after its callers are gone |
| Operations and cleanup | `BackEnd/api/admin_routes.py` | Remove legacy cascade/retention assumptions only after runtime references are gone |

The router is actively mounted by `BackEnd/api/api.py`; it is not dead code.

### 5.3 Mounted standalone endpoint baseline

`BackEnd/api/tournament_routes.py` currently exposes:

| Method | Route |
|---|---|
| GET | `/tournament/team-stats` |
| GET | `/tournament/leaders` |
| GET | `/tournament/current` |
| POST / DELETE | `/tournament/delete-current`, `/tournament/current` |
| POST | `/tournament/start`, `/start-tournament` |
| POST | `/tournament/simulate-round`, `/simulate-tournament-round` |
| POST | `/tournament/save-result` |
| GET | `/tournament/command-center/data` |
| GET | `/tournament/state` |
| GET | `/tournament/team-data` |
| GET | `/tournament/scouting-report` |
| GET | `/tournament/roster` |
| POST | `/tournament/sim-remaining` |
| POST | `/tournament/run-training` |

The duplicate non-namespaced routes are backward-compatibility aliases and
belong to the same sunset.

### 5.4 Frontend executable inventory

| Category | Files |
|---|---|
| Standalone entry and management | `tournament-select.html`, `tournament-select.js`, `tournament-select.css`, `tournament.html`, `tournament.js`, `tournament.css` |
| Court boot, gameplay, and finalization | `court.html`, `court (1).html`, `js/phaser/bootGame.js`, `js/phaser/gameScene.js`, `js/phaser/finalizeGame.js`, `js/phaser/animation/AnimationEngine.js` |
| Gameplay utilities | `js/phaser/utils/foulOutPopup.js`, `gameCompletionPopup.js`, `timeoutButtonManager.js` |
| Lineup, game plan, and playbooks | `set-lineup.js`, `game-plan.js`, `playbooks.js`, `playbook-report.js` |
| Team and result views | `team-roster-view.js`, `player-detail.js`, `box-score.js` |
| Training | `training.js`, `training-report.js` |
| Shared context/navigation | `js/shared/pointerValidation.js`, `stateTelemetry.js`, `errorHandler.js`, `timeoutNavigationHelper.js` |
| Legacy query propagation | `recruiting-invites.html`, `recruiting-orders.html`, `recruiting-results.html` |

Each shared file must be traced by branch. The file itself is not necessarily a
sunset target; only its standalone `mode === "tournament"` and
`tournament_id` behavior is.

The normal mode-selection page does not currently expose standalone Tournament
Mode. The legacy entry remains directly reachable at `tournament-select.html`;
its JavaScript posts to `/tournament/start`, stores `activeTournament`, and
navigates to `tournament.html`. This is the Phase 1 entry boundary.

### 5.5 Storage and operational contract inventory

The legacy relationship currently touches:

- the `tournaments` collection and standalone tournament `_id`;
- `games.tournament_id`;
- game summaries carrying `tournament_id`;
- tournament documents containing results, applied-game/idempotency state,
  players, leaders, game plans, playbooks, settings, and bracket progress;
- training-session documents that can carry `tournament_id`;
- game and document ownership checks;
- pointer validation;
- game-retention protection for any game with `tournament_id`;
- admin and user tournament deletion cascades.

No index or historical-data removal is authorized in Phase 0. Index inventory
must be rechecked immediately before Phase 5 because deployment configuration
may differ from source-declared indexes.

### 5.6 Active Franchise tournament contract

The surviving system is explicitly based on:

- `franchise_id`;
- Franchise weeks 27–34;
- `eos_tournament_active`;
- `conference_tournaments`;
- `region_tournaments`;
- `national_tournament`;
- game-document `eos_meta`;
- schedule response `tournament_schedule`;
- schedule-row `tournament_context`.

The active Franchise surfaces are concentrated in:

- `BackEnd/api/franchise_routes.py`;
- `BackEnd/tournament/franchise_tournament.py`;
- `FrontEnd/static/franchise-command-center.js`;
- `FrontEnd/static/franchise-tournament-brackets-render.js`;
- `FrontEnd/static/schedule.html`;
- the EOS progression, bracket, schedule, and completion regression tests.

The literal word “tournament” in these files is not evidence of legacy mode and
must not be removed.

### 5.7 Regression baseline added

`tests/test_tournament_id_sunset_franchise_contract.py` now protects three
boundaries:

1. Franchise play and complete-week request models are keyed by
   `franchise_id`, not `tournament_id`.
2. Active play-next, complete-week phase A/B, and schedule routes remain on the
   Franchise router.
3. Franchise EOS schedule rows derive from week/bracket metadata and expose
   `tournament_context` without a legacy `tournament_id`.

Focused result:

```text
3 passed
```

Combined with the existing Franchise EOS bracket-invariant and week-26
transition suites:

```text
28 passed
```

The test ran with `PYTHONHASHSEED=0` against a forced local `mongomock`
database named `tournament_sunset_test`. The repository safety guard correctly
refused an earlier attempt that inherited the blocked `gob-staging` database
name; no production or staging database writes occurred.

### 5.8 Phase 0 checkpoint

Phase 0 is complete when reviewed against this record:

- product treatment of old saves is decided;
- executable legacy surfaces are classified;
- active Franchise tournament authority is documented;
- storage, ownership, validation, and retention relationships are identified;
- Franchise boundary tests pass;
- runtime behavior remains unchanged.

The next implementation boundary is Phase 1: close standalone entry points and
stop creation of new standalone tournaments while temporarily retaining old
read paths.

---

## 6. Phase 1 Execution Record

**Completed:** July 24, 2026

Phase 1 prevents all supported entry into standalone Tournament Mode and
prevents creation of new standalone tournament documents. It deliberately
retains existing read/state/result compatibility code for Phase 2 and later
removal.

### 6.1 Frontend entry closure

Netlify now issues forced temporary redirects:

```text
/tournament-select.html -> /mode-select.html (302)
/tournament.html        -> /mode-select.html (302)
```

Both source HTML files are also minimal redirect-only fallbacks using
`window.location.replace()` plus a meta refresh. This covers local development,
backend static serving, and any environment that does not apply Netlify
redirect rules.

The fallback pages no longer load:

- `tournament-select.js`;
- `tournament.js`;
- tournament styles or gameplay dependencies;
- authentication, analytics, or command-center boot code.

The legacy JavaScript and styles remain in the repository for the later shared
caller audit and deletion phases, but ordinary page navigation cannot execute
them.

### 6.2 Creation closure

Both authenticated creation aliases now return `410 Gone`:

```text
POST /tournament/start
POST /start-tournament
```

The response explains that standalone Tournament Mode is retired and directs
the user toward Mode Select or Franchise tournament weeks.

Authentication remains the outer boundary. An unauthenticated request still
returns `401` rather than exposing endpoint behavior.

The retired creation handler performs no:

- team or player lookup;
- player-stat reset;
- tournament document insert;
- profiling run;
- game creation;
- database mutation.

The old `_do_start_tournament()` implementation remains temporarily in source
as unreachable compatibility code. It will be deleted with the standalone
router implementation in Phase 2 rather than mixing code deletion into this
boundary phase.

### 6.3 Intentionally retained in Phase 1

Phase 1 does not:

- unmount `tournament_router`;
- remove current/state/result/simulation/read APIs;
- delete tournament documents or tournament-linked games;
- remove shared `tournament_id` request fields;
- change ownership, pointer validation, or retention logic;
- change any active Franchise tournament-week route or data structure.

This keeps the next removal boundary explicit and makes Phase 1 reversible
without a data migration.

### 6.4 Phase 1 regression coverage

Tests now assert:

- both creation aliases return `410`;
- creation writes no tournament document;
- the retired start path does not reset player statistics;
- unauthenticated creation remains `401`;
- both standalone HTML pages are redirect-only and cannot load legacy boot
  scripts;
- active Franchise play, completion, schedule, and EOS contracts remain keyed
  by `franchise_id`.

Focused Phase 1 and security result:

```text
12 passed
```

Combined with the existing Franchise EOS bracket-invariant and week-26
transition suites:

```text
37 passed
```

Tests ran with `PYTHONHASHSEED=0` against the isolated
`tournament_sunset_test` `mongomock` database. No staging or production data was
read, changed, or deleted.

### 6.5 Phase 1 checkpoint

Phase 1 is complete:

- no normal UI exposes standalone Tournament Mode;
- old direct page URLs redirect to Mode Select;
- neither creation alias can create a tournament;
- authentication behavior is preserved;
- old read paths and persisted data remain intact;
- Franchise tournament weeks are unchanged.

The next boundary is Phase 2: unmount and remove the standalone backend router,
then identify and remove direct callers that become dead with it.

---

## 7. Phase 2A Execution Record

**Completed:** July 24, 2026

Phase 2A unmounts the standalone Tournament Mode router without deleting its
module or shared helper functions.

### 7.1 Application route change

`BackEnd/api/api.py` no longer:

- imports `router as tournament_router`;
- calls `app.include_router(tournament_router)`.

As a result, the application route table no longer contains any of the
standalone `/tournament/*` endpoints or the two backward-compatible aliases:

```text
/start-tournament
/simulate-tournament-round
```

Because the application mounts static files at the root, unmatched GET
requests normally return `404`, while unmatched POST requests may return `405`.
The authoritative assertion is that none of the legacy paths exists in the
FastAPI route table.

### 7.2 Code intentionally retained

`BackEnd/api/tournament_routes.py` remains in the repository and remains
importable. Shared compatibility code still imports
`get_user_team_from_tournament()` from it in:

- `BackEnd/api/api.py`;
- `BackEnd/api/gameplan_routes.py`;
- `BackEnd/api/franchise_routes.py`;
- `BackEnd/utils/team_settings_manager.py`;
- `BackEnd/utils/team_id_resolver.py`.

Removing that module now would break application startup and shared code paths.
Separating the unmount from helper extraction/deletion is the risk boundary
that defines Phase 2A.

The Tournament Manager, standalone endpoint functions, request models, and old
creation implementation are now unreachable through the application, but are
left intact for the Phase 2B dependency cleanup.

### 7.3 Behavior after Phase 2A

- standalone frontend pages still redirect to Mode Select;
- no standalone API route can be invoked;
- no new standalone tournament can be created;
- old standalone saves are no longer playable, as explicitly approved;
- old tournament documents and tournament-linked games remain stored;
- no ownership, pointer, retention, or shared request contract has been
  removed;
- active Franchise tournament routes remain mounted.

The Phase 1 `410` and unauthenticated `401` behavior is now historical: once the
router is unmounted, the request cannot reach either the endpoint handler or
its authentication dependency.

### 7.4 Phase 2A regression coverage

Tests now assert:

- the complete legacy endpoint set is absent from the application route table;
- active Franchise play-next, complete-week phase A/B, and schedule routes
  remain present;
- requests to the retired start path are unavailable and cannot reset player
  statistics or create tournament documents;
- both redirect-only frontend fallbacks remain closed;
- shared application imports and startup still succeed.

Focused route, mutation, and security result:

```text
12 passed
```

The full checkpoint also includes the Franchise EOS bracket-invariant and
week-26 transition suites:

```text
37 passed
```

All verification uses `PYTHONHASHSEED=0` and the isolated
`tournament_sunset_test` `mongomock` database.

### 7.5 Phase 2A checkpoint

Phase 2A is complete. The next step is a discussion checkpoint before Phase 2B.

Phase 2B is not a no-risk deletion. It requires extracting or replacing shared
helpers, removing endpoint-only implementation, and updating legacy tests
without changing active Franchise or normal game behavior.

---

## 8. Phase 2B Execution Record

**Completed:** 18 September 2026  
**Commit:** `80b12bf03`

Phase 2B extracts the one shared helper that kept `tournament_routes.py`
importable, then deletes the standalone router, manager, and standalone-only
bracket wrapper.

### 8.1 Helper decision

`get_user_team_from_tournament()` had remaining callers in:

- `BackEnd/api/api.py` (2)
- `BackEnd/api/franchise_routes.py` (2)
- `BackEnd/api/gameplan_routes.py` (module import + several uses)
- `BackEnd/utils/team_id_resolver.py`
- `BackEnd/utils/team_settings_manager.py`

Every call site is a leftover `mode == "tournament"` compatibility branch.
Those branches are Phase 4 work and were left intact. The helper therefore had
to move, not disappear, or application import of `gameplan_routes` would fail.

It now lives in `BackEnd/utils/team_id_resolver.py` (already the team-id
resolution boundary; no new `BackEnd.db` import file). Franchise tournament
weeks continue to use `get_user_team_from_franchise`.

### 8.2 Deleted standalone implementation

Verified no remaining production caller, then deleted:

- `BackEnd/api/tournament_routes.py`
- `BackEnd/tournament/tournament_manager.py`
- `BackEnd/tournament/bracket_logic.py`

Franchise code uses `bracket_engine` and `franchise_tournament`, not
`bracket_logic`.

Also removed the leftover `GET /tournament/active` handler from `api.py`. It
was not on `tournament_router` but it created standalone tournament documents
via `TournamentManager` and was the last production manager caller.

### 8.3 Tests belonging solely to the router

Removed:

- `tests/test_tournament_state_scores.py`
- `tests/test_tournament_sim_remaining.py`
- `tests/test_tournament_save_results.py`
- `tests/test_tournament_leaders_endpoint.py`
- `tests/test_tournament_full_bracket_progression.py`
- `tests/test_tournament_bracket_update.py`
- `tests/test_tournament_active_returns_progress.py`
- `tests/test_simulate_round_results.py`
- `tests/test_tournament_manager.py`
- `tests/test_tournament_progression.py`
- `test_tournament_create_tournament_teams_use_seed_based_attributes` in
  `tests/test_mode_init_system.py`

`TeamManager.init_team_attributes(mode="tournament")` tests remain; that is
engine init, not the retired router. Phase 4 can drop them.

Sunset contract tests now also assert `/tournament/active` is unmounted and
that the three deleted modules fail to import.

### 8.4 Intentionally retained

- shared backend `mode == "tournament"` branches (Phase 4)
- frontend `tournament_id` / `mode === "tournament"` branches (Phase 3, still
  live at this commit)
- storage, ownership, retention (Phase 5)
- Franchise tournament weeks, `bracket_engine`, `franchise_tournament*`
- historical standalone documents (no data deletion)

The three deleted modules each imported `BackEnd.db`. Gate A therefore fell
from the original freeze of 120 statements / 64 files to 117 / 61. The
allowlist in `scripts/ci/migration_gates_allowlist.json` was tightened in this
same commit so those three slots cannot be refilled.

### 8.5 Behavior after Phase 2B

- application startup still succeeds (181 routes)
- no standalone tournament route remains mounted, including `/tournament/active`
- the three deleted modules raise `ModuleNotFoundError`
- shared Phase 4 leftover branches still import the moved helper
- active Franchise tournament routes remain mounted
- no persisted standalone documents were deleted

### 8.6 Phase 2B regression coverage

Isolated mongomock `tournament_sunset_test`, `PYTHONHASHSEED=0`. Same four
files as the Phase 2A 37-test checkpoint, plus the new “modules are gone”
assertion:

- `tests/test_tournament_id_sunset_franchise_contract.py`
- `tests/test_franchise_eos_bracket_invariant.py`
- `tests/test_week26_completion_regression.py`
- `tests/test_eos_region_week30_meta.py`

```text
38 passed, 1 skipped
```

The skip is `test_week26_completion_integration_no_delete` in
`tests/test_week26_completion_regression.py`. It is skipped when `MONGO_URI`
is unset (`@pytest.mark.skipif` since `dff5f515c3`, March 2026). The same skip
is on `develop`; this change did not introduce it.

### 8.7 Phase 2B checkpoint

Phase 2B is complete. The standalone router, manager, and unused
`bracket_logic` wrapper are gone. Gate A’s floor is 117 / 61.

The next boundary is Phase 3: remove shared frontend `tournament_id` and
`mode === "tournament"` branches without touching Franchise tournament weeks.

---

## 9. Phase 3 Execution Record

**Completed:** 18 September 2026  
**Commit:** `1ebf785db`

Phase 3 removes standalone Tournament Mode from shared frontend screens. The
surviving contract distinguishes normal vs Franchise. Leftover
`mode=tournament` / `tournament_id` values are ignored so they cannot skip
Franchise complete-week.

### 9.1 Frontend `tournament_id` file count

| When | Files under `FrontEnd/static` |
|---|---|
| Before Phase 3 | 23 |
| After Phase 3 | 0 |

Removed, by branch rather than by file name:

- `mode === "tournament"` feature branches and their dead sides
- `tournament_id` reads from URL, localStorage, and sessionStorage
- `tournament_id` on request payloads and constructed query strings

Court pages still neutralize a stale `mode=tournament` URL value so it cannot
win over `franchise_id`. That is a guard, not a standalone mode branch.

A follow-up `rg` of `FrontEnd/static` for `tournament_id` returns no matches.

### 9.2 Deleted legacy-only assets

- `tournament-select.html`, `tournament-select.js`, `tournament-select.css`
- `tournament.html`, `tournament.js`, `tournament.css`

Netlify / `_redirects` still send `/tournament.html` and
`/tournament-select.html` to Mode Select. Leftover stylesheet links on
set-lineup, brackets, practice-squad-bracket, and the unused
`FrontEnd/roster.html` were dropped; those pages do not use the TCC classes.

### 9.3 Intentionally retained

- shared backend `mode == "tournament"` branches (Phase 4)
- storage, ownership, retention (Phase 5)
- dead-implementation sweep beyond the six legacy assets (Phase 6)
- repository guard (Phase 7)
- Franchise tournament weeks and their files: `franchise-command-center.js`,
  `franchise-tournament-brackets-render.js`, `schedule.html`,
  `franchise_routes.py`, `franchise_tournament.py`
- historical standalone documents (no data deletion)

Phases 4–7 are not started.

### 9.4 Behavior after Phase 3

- application startup still succeeds (181 routes)
- shared screens no longer send or require `tournament_id`
- old standalone page URLs still redirect to Mode Select
- Franchise locker-room, schedule, and EOS routes still key on `franchise_id`
- Phase 3 is frontend-only: no engine-loop or RNG-order change; draw count is
  unchanged and no refstats rebaseline

### 9.5 Gate B drop reconciliation

Gate B counts lines matching `URLSearchParams`, `location.search`, or
`.searchParams`. It does not count `.get('tournament_id')` calls.

On `develop` there were 30 `.get('tournament_id')` / equivalent URL reads
across the 23 files (the ~29 call-site figure). Most of those sat on a line
that already constructed `URLSearchParams` for `franchise_id` / `game_id`.
Removing the `.get('tournament_id')` therefore does not drop the Gate B line.

The 313 → 294 drop (19 lines) is exactly:

| Change | Gate B lines |
|---|---|
| Delete `tournament.js` | −15 (file had 15 URL-state lines) |
| `box-score.js` | 10 → 9 (−1) |
| `finalizeGame.js` | 3 → 1 (−2) |
| `gameCompletionPopup.js` | 7 → 6 (−1) |

Allowlist: 313 lines / 79 files → 294 / 78. `tournament.js` is off the list.

Gate A remains 117 / 61 (tightened in Phase 2B; Phase 3 did not add or restore
`BackEnd.db` imports).

### 9.6 Franchise tournament-week verification (section 11.1)

These checks were run against isolated mongomock `tournament_sunset_test` with
`PYTHONHASHSEED=0`. “Exercised” means a test invoked the path. “Inferred”
means code was read and not executed.

| 11.1 check | Status | Evidence |
|---|---|---|
| Franchise reaches a tournament week | Exercised | `test_week26_builds_update_fields_week_27_and_16_conference_tournaments` sets week 27 and `conference_tournaments`; `test_eos_init_uses_bracket_engine` builds the EOS bracket |
| Tournament schedule and context load | Exercised | `test_franchise_eos_schedule_uses_week_and_bracket_metadata_without_legacy_id`; HTTP `GET /franchise/schedule` in `test_franchise_game_scoping.py` |
| User game launches | Partial | `PlayGameRequest` is `{franchise_id}` only and `POST /franchise/play-next-game` remains mounted. No full EOS play-next HTTP create was run |
| User game resumes | Exercised | `test_resume_anchor_franchise_identity.py` — merge keeps `franchise_id` |
| CPU games simulate | Exercised | `test_complete_week_saves_and_simulates`; `test_start_cpu_then_phase_a_phase_b_advances_week`; `test_franchise_eos_sim_policy.py` |
| User and CPU results persist | Exercised | same complete-week / phase-A-B tests plus `_save_user_eos_bracket_result` in `test_franchise_eos_sim_policy.py` |
| Bracket advances | Exercised | `test_eos_save_advance_round1_to_2`; `test_eos_save_advance_to_final_and_champion`; `test_eos_advance_conference_when_four_r1_winners_and_round2_empty` |
| Next Franchise week selected | Exercised | complete-week advances `week`; week-26 payload writes `week = 27` |
| Roster / scouting / game-plan / playbook / training use Franchise data | Exercised | `test_franchise_team_player_stats.py`; `test_scouting_usage_unlocks.py` (tournament weeks unlock without training); `test_gameplan_game_doc_precedence.py` (4 passed); `test_playbooks_game_doc_precedence.py` unit cases plus HTTP GET with `mode=franchise&franchise_id`; `test_training_report_franchise_roster.py` |
| Refresh / direct-navigation preserve `franchise_id` | Inferred | no browser session. `franchise-command-center.js` still builds court / lineup / roster URLs with `franchise_id` and was not edited |
| No surviving request requires `tournament_id` | Exercised (frontend) | `FrontEnd/static` has zero `tournament_id` matches. Backend request models still accept the field on leftover Phase 4 branches |

One extra playbooks HTTP assertion
(`test_get_playbooks_franchise_with_game_id_returns_game_doc_slot_assignments`)
failed on this branch and fails identically on `develop`. It is a pre-existing
FTD/game-doc merge issue, not introduced by Phases 2B or 3.

No browser walkthrough of a live Franchise tournament week was performed.

### 9.7 Phase 3 regression coverage

Original four-file checkpoint, same as Phase 2B:

```text
38 passed, 1 skipped
```

The skip is again `test_week26_completion_integration_no_delete` (needs
`MONGO_URI`; present on `develop` before this work).

Wider Franchise / EOS / data-source suite run for section 11.1:

```text
104 passed, 1 failed, 1 skipped
```

The one failure is the pre-existing playbooks game-doc slot assertion above.

### 9.8 Phase 3 checkpoint

Phase 3 is complete. Shared frontend no longer carries a standalone tournament
branch. Gate B’s floor is 294 / 78. Frontend `tournament_id` file count is 0.

The next boundary is Phase 4: remove shared backend `tournament_id` request
fields and `mode == "tournament"` branches. Phases 4–7 are not started.

---

## 10. Proposed Retirement Sequence

### Phase 0 — Freeze and inventory

Before changing behavior:

1. Record every executable `tournament_id` reference in backend and frontend
   code.
2. Classify each reference as:
   - legacy standalone Tournament Mode;
   - active Franchise tournament week;
   - shared generic code;
   - documentation, test, fixture, or migration only.
3. Inventory direct routes, pages, request models, stored fields, indexes,
   ownership checks, pointer checks, and retention policies.
4. Establish tests for active Franchise tournament-week launch, game play,
   CPU-week completion, result persistence, bracket advancement, training, and
   resume behavior.
5. Capture current standalone route behavior so its intentional retirement is
   distinguishable from accidental breakage.

No database cleanup is part of this phase.

### Phase 1 — Close standalone entry points

Retire user entry into the old mode before removing its internal data contract:

- remove or redirect the standalone tournament selection page;
- remove or redirect tournament management pages;
- remove legacy navigation links and launch actions;
- stop creating new standalone tournament documents;
- return an intentional, documented response for old direct URLs;
- ensure active Franchise tournament-week links continue to use
  `franchise_id`.

Closing entry points first prevents new legacy sessions from being created
while deeper compatibility paths are removed.

### Phase 2 — Retire the standalone backend router

After entry points are closed:

- unmount `tournament_router` from the application;
- remove standalone create/current/delete/state endpoints;
- remove round simulation and “sim remaining” endpoints;
- remove standalone save-result behavior;
- remove standalone team-data, scouting, roster, and training endpoints;
- remove the standalone Tournament Manager and its helpers once no caller
  remains;
- remove imports, request/response models, and tests belonging solely to that
  router.

Do not remove Franchise routes or Franchise tournament-week helpers merely
because they contain tournament terminology.

### Phase 3 — Remove shared frontend compatibility branches

Trace each shared screen from its entry context and remove only the standalone
mode branch:

- game launch and boot context;
- court/gameplay state;
- game finalization;
- game-plan and playbook loading/saving;
- roster and team-data fetches;
- training and training-report fetches;
- timeout/navigation/resume behavior;
- any local-storage, session-storage, or URL propagation;
- request payloads and query strings carrying `tournament_id`.

The surviving shared contract should distinguish normal and Franchise contexts
without a legacy standalone tournament branch.

### Phase 4 — Remove shared backend compatibility branches

Remove standalone-mode behavior from shared APIs and engine entry points:

- request models that accept `tournament_id`;
- `mode == "tournament"` branches;
- tournament-document loads during game creation and simulation;
- tournament-specific result and state persistence;
- tournament-specific roster, team-data, game-plan, playbook, scouting, and
  training lookups;
- propagation into managers and game state;
- response fields emitted only for the old mode.

Keep game-engine basketball behavior mode-agnostic wherever possible. This
sunset should simplify context selection, not alter turn resolution, RNG, or
simulation results for surviving modes.

### Phase 5 — Retire storage relationships and operational protections

Once no runtime caller depends on the relationship:

- stop writing `tournament_id` to new game documents;
- remove it from shared serializers and projections;
- remove standalone tournament pointer and ownership validation;
- update retention logic that protects games solely because they have a
  standalone `tournament_id`;
- assess obsolete indexes and schema documentation;
- decide separately whether historical fields remain tolerated on old
  documents.

Historical data should be ignored safely before any decision to migrate,
archive, or delete it.

### Phase 6 — Remove dead implementation and tests

After runtime removal is verified:

- delete legacy-only frontend assets and backend modules;
- remove fixtures and tests whose only purpose was the standalone mode;
- rewrite shared tests around the surviving normal and Franchise contracts;
- remove stale comments and documentation that imply Tournament Mode is still
  available;
- retain historical release notes where useful, clearly marking the feature as
  sunset.

### Phase 7 — Repository guard

Add a narrowly scoped guard that fails when new executable legacy references
are introduced.

The guard should check runtime source for:

- `tournament_id`;
- `mode === "tournament"`;
- `mode == "tournament"`;
- legacy standalone route paths and page names.

Allow explicit exceptions for migrations, archived documentation, or historical
fixtures only when each exception is documented. Do not require the literal
word “tournament” to disappear because Franchise tournament weeks remain
active.

---

## 11. Verification Plan

### 11.1 Franchise tournament-week regressions

Verify at minimum:

- a Franchise reaches a tournament week;
- the tournament schedule and context load;
- the user game launches and resumes;
- CPU games simulate;
- the user result and CPU results persist;
- the bracket advances correctly;
- the next Franchise week is selected correctly;
- roster, scouting, game-plan, playbook, and training screens use the Franchise
  data source;
- refresh and direct-navigation flows preserve `franchise_id`;
- no surviving request requires `tournament_id`.

### 11.2 Normal-mode regressions

Verify:

- a normal game can be created, played, resumed, and finalized;
- shared roster, playbook, game-plan, training, and navigation paths do not
  expect a tournament identifier;
- game retention and cleanup still apply their intended normal-mode policies.

### 11.3 Intentional legacy behavior

Verify:

- old standalone tournament entry URLs redirect or return the agreed sunset
  response;
- standalone APIs are unavailable after router retirement;
- old tournament-linked records do not crash generic game/history queries;
- no new standalone tournament or tournament-linked game document can be
  created;
- no persisted records are deleted by the code-removal deployment.

### 11.4 Performance and determinism

This is primarily a context and persistence cleanup, but it touches simulation
entry points. Follow `Sim_Perf_Capstone.md`:

- add no database calls inside game-engine loops;
- do not change RNG draw order;
- use seeded exact-diff verification for non-drawing changes;
- run measurements with `PYTHONHASHSEED=0`;
- compare representative full-sim timing before and after;
- do not edit source while a measurement run is in flight.

The sunset should be performance-neutral or a small improvement.

---

## 12. Acceptance Criteria

The sunset is complete only when:

1. No user-accessible flow can create or enter standalone Tournament Mode.
2. The standalone tournament router and manager are no longer mounted or
   called.
3. No executable frontend request sends `tournament_id`.
4. No executable shared backend request model or runtime branch requires
   `tournament_id`.
5. New game documents no longer store `tournament_id`.
6. Ownership, pointer, and retention logic no longer depends on the legacy
   relationship.
7. Active Franchise tournament weeks pass end-to-end regression coverage.
8. Normal game flows pass end-to-end regression coverage.
9. Historical records containing the field are tolerated without runtime
   failure.
10. A repository guard prevents accidental reintroduction of the legacy mode.
11. No production data has been deleted without a separate, explicit data
    retirement plan and authorization.

---

## 13. Non-Goals

This project does not:

- remove or redesign Franchise tournament weeks;
- rename all tournament-related concepts;
- rewrite bracket logic that is active within Franchise;
- change basketball simulation behavior;
- alter shot, block, possession, transition, or animation systems;
- delete historical database records;
- bundle unrelated persistence or performance refactors into the sunset.

---

## 14. Recommended First Implementation Slice

After the old-save policy is confirmed, begin with a reversible boundary slice:

1. add Franchise tournament-week regression coverage;
2. remove or redirect standalone frontend entry points;
3. stop creation of new standalone tournaments;
4. leave existing read paths temporarily intact;
5. verify normal and Franchise flows in staging.

This establishes that the active product no longer enters the legacy system
before shared contracts and stored relationships are removed. The remaining
phases can then proceed in small, testable changes rather than one high-risk
global deletion.
