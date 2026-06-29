# Franchise CPU Sim Resume Plan

## Purpose

Make franchise computer-game simulation resumable and idempotent across browser refresh, browser close, tab crashes, and backend request interruption.

This plan covers CPU games that run in parallel with or after the user's franchise game:

- early overlap path: `POST /franchise/complete-week/start-cpu-sims`
- end-of-game phase B path: `POST /franchise/complete-week/phase-b`
- shared backend worker: `_complete_week_finish_cpu_and_persist`

The system should retain completed CPU game results, resume missing games, and never restart the whole slate unless an explicit repair tool requests that.

## Current Behavior

### Early CPU sims

When the user starts or sims their franchise game, `bootGame.js` calls:

```text
getOrStartFranchiseStartCpuSims({ franchise_id, week })
```

That client calls:

```text
POST /franchise/complete-week/start-cpu-sims
```

The backend simulates non-user games and persists partial `franchise.results.{week}` without advancing the franchise week.

### End-of-game phase B

When the user's franchise game ends:

1. `finalizeGame.js` calls `POST /franchise/complete-week/phase-a`.
2. Phase A saves the user game result and marks `post_game_status.phase_a_user_week`.
3. `gameCompletionPopup.js` starts or reuses `POST /franchise/complete-week/phase-b`.
4. Phase B merges existing week results, simulates missing CPU games, and advances the franchise week only if the full slate is complete.

### Existing backend idempotency

The backend already has useful protections:

- existing CPU game documents are skipped
- existing `franchise.results.{week}` rows are reused
- result rows are deduped by unordered matchup key
- `start-cpu-sims` re-reads fresh DB state before persisting so it does not clobber a concurrent phase-A user result
- phase B can fill missing CPU games later
- phase B returns idempotent success when the franchise week has already advanced past the requested week

## Current Gap

Frontend single-flight state is tab-local only:

- `franchiseStartCpuSimsClient.js` stores in-flight/completed state in memory.
- `franchisePhaseBClient.js` stores in-flight state in memory.
- Those maps disappear on browser refresh, browser close, crash, or device switch.

There is no durable CPU sim job state that tells the UI:

- CPU sims are pending
- CPU sims are running
- some matchups are complete
- some matchups failed
- phase A is complete but phase B still needs to finish
- the week can safely advance / has already advanced

As a result, the backend is mostly retry-safe, but the product flow is not yet fully observable or resumable across sessions.

## Product Contract

If the user refreshes or closes the browser before all computer games have simmed:

- keep completed CPU games
- keep persisted game documents
- keep completed `franchise.results.{week}` rows
- keep EOS bracket cells that already have winners
- resume only missing, stale-running, or failed matchups when the user returns
- never delete completed CPU games as part of normal resume
- never duplicate completed results for the same matchup
- only advance the franchise week after every scheduled matchup for that week has a canonical result

## Durable Job Model

Store CPU sim progress on the franchise document.

Recommended path:

```text
franchises.cpu_sim_jobs.{week}
```

Example shape:

```json
{
  "week": 4,
  "status": "pending | running | partial | complete | failed | finalized",
  "phase": "start_cpu_sims | phase_b",
  "started_at": "2026-06-29T12:00:00Z",
  "updated_at": "2026-06-29T12:01:15Z",
  "completed_at": null,
  "finalized_at": null,
  "expected_matchups": 64,
  "completed_matchups": 23,
  "failed_matchups": 1,
  "running_owner": "optional-worker-id-or-request-id",
  "running_started_at": "2026-06-29T12:00:00Z",
  "last_error": null,
  "matchups": {
    "awayId|homeId": {
      "away_id": "...",
      "home_id": "...",
      "status": "pending | running | complete | failed",
      "simulation_engine": "distant | cpu_full",
      "game_id": "...",
      "away_score": 67,
      "home_score": 73,
      "started_at": "2026-06-29T12:00:00Z",
      "completed_at": "2026-06-29T12:00:03Z",
      "attempts": 1,
      "last_error": null
    }
  }
}
```

Use a stable unordered matchup key internally where needed. The display key above is illustrative only; implementation should use the same matchup identity concept as `_week_result_matchup_key`.

## Status Lifecycle

### Job-level status

| Status | Meaning |
|---|---|
| `pending` | Job initialized, no active worker. |
| `running` | Worker is actively simming one or more matchups. |
| `partial` | Some matchups complete, some still pending/failed. |
| `complete` | All CPU matchups have results, but week may not be finalized yet. |
| `failed` | Job cannot currently continue without retry or user-visible recovery. |
| `finalized` | Week has advanced; job is historical. |

### Matchup-level status

| Status | Return behavior |
|---|---|
| `pending` | Sim this matchup. |
| `running` | If fresh, do not duplicate; if stale, reclaim and retry. |
| `complete` | Keep result and skip. |
| `failed` | Retry or surface recoverable error. |

### Stale running rule

If a job or matchup is `running` but `updated_at` is older than a configured timeout, treat it as retryable.

Suggested first pass:

```text
CPU_SIM_RUNNING_STALE_SECONDS = 180
```

This avoids permanent stuck state after a backend process dies mid-request.

## Backend Plan

### 1. Add job helpers

Create small helper functions in or near `BackEnd/api/franchise_routes.py`:

- build expected CPU matchups for a franchise week
- initialize or load `cpu_sim_jobs.{week}`
- mark job running
- mark matchup running
- mark matchup complete
- mark matchup failed
- mark job complete / partial / failed / finalized
- compute completed count from canonical persisted results
- reconcile job state from `franchise.results.{week}` and `games`

The reconcile helper is important because `results.{week}` and `games` are the actual outcome truth. The job object is orchestration state, not the scoring authority.

### 2. Wire `start-cpu-sims`

Before `_complete_week_finish_cpu_and_persist(..., persist_cpu_results_only=True)` runs:

1. initialize/load `cpu_sim_jobs.{week}`
2. reconcile completed matchups from persisted results/games
3. mark job `running`
4. run only incomplete matchups
5. mark each completed matchup as complete as soon as its result is persisted
6. mark failed matchups with error details
7. mark job `complete` if all non-user CPU matchups are complete, else `partial` or `failed`

`start-cpu-sims` must not advance the franchise week.

### 3. Wire phase B

At the start of `POST /franchise/complete-week/phase-b`:

1. confirm phase A is complete
2. load/reconcile `cpu_sim_jobs.{week}`
3. if CPU job has missing/failed/stale matchups, resume them
4. call the existing week-finalization path only after all scheduled matchups are complete
5. mark `cpu_sim_jobs.{week}.status = finalized` after week advance succeeds

Phase B remains the final authority for week closure.

### 4. Preserve existing idempotency

Keep these current behaviors:

- skip existing game docs
- skip existing result rows
- dedupe by matchup key
- merge fresh DB state before writing partial CPU results
- phase B self-heal / EOS bracket sync logic

The new job state must sit on top of this behavior, not replace it.

## Frontend Plan

### 1. Add status read

Expose CPU sim job state through one of:

- existing FCC data response
- existing mode-select current-franchise response
- new endpoint: `GET /franchise/week-sim-status?franchise_id=...&week=...`

The frontend needs enough information to choose:

- no work needed
- CPU sims are running
- CPU sims failed and can retry
- phase A done but phase B incomplete
- week finalized

### 2. Mode Select behavior

When a user returns after closing the browser:

- If no active/incomplete franchise week job exists, show normal mode select behavior.
- If phase A is not done and Mid Game Resume has an active user game, show the existing resume card.
- If phase A is done and phase B is incomplete, show a “Finishing Computer Games” resume/continue card.
- Pressing it should resume phase B or route to an appropriate waiting surface.

### 3. FCC behavior

On FCC load:

- If current week has incomplete CPU sim job state, block week-advance actions.
- Show a clear loading/retry state rather than stale FCC data.
- If phase A is done and phase B incomplete, offer or auto-start phase B.
- When phase B finishes, refresh FCC data.

### 4. EOG popup behavior

Keep current behavior:

- EOG starts phase B in the background.
- Go To Locker Room waits for phase B.

Add durable fallback:

- if the tab is closed during phase B, returning through Mode Select/FCC can detect and resume phase B.

## Expected User Scenarios

### Browser close during early CPU sims, before user game ends

Expected:

- completed CPU games remain saved
- user game resume is governed by Mid Game Resume
- when user game eventually reaches EOG, phase B fills any remaining CPU games and finalizes week

### Browser close after user game ends, while phase B is running

Expected:

- phase A user result remains saved
- completed CPU games remain saved
- Mode Select or FCC detects phase B incomplete
- user sees a “Finishing Computer Games” state
- phase B resumes missing games
- week advances after all results exist

### Backend request fails mid CPU slate

Expected:

- completed matchups remain complete
- failed/running-stale matchups become retryable
- retry resumes missing work only
- duplicate result rows are deduped

### User returns after phase B already completed

Expected:

- no retry
- no duplicate CPU sims
- franchise week is already advanced
- UI routes normally to FCC for the new week

## Implementation Status

### Implemented 2026-06-29

Backend phases 1–2 are implemented in `BackEnd/api/franchise_routes.py`:

- durable `franchises.cpu_sim_jobs.{week}` job state
- per-matchup status rows
- reconciliation from persisted `franchise.results.{week}`
- completed-matchup skip/retention
- stale `running` rows reclaimed as `pending`
- job writes from both `start-cpu-sims` and phase B
- finalized marker after successful week advancement
- response payload summaries under `cpu_sim_job`

Still pending:

- optional dedicated status endpoint
- automated regression tests around partial CPU sim recovery
- deeper UI retry/error treatment beyond the main FCC CTA

## Implementation Phases

### Phase 1: Durable status only

- Add backend job schema helpers.
- Write job status from `start-cpu-sims` and phase B.
- Add logs.
- No major UI changes yet.

Status: implemented 2026-06-29.

### Phase 2: Resume/retry backend

- Reconcile job state from persisted results/games.
- Treat stale `running` as retryable.
- Ensure `start-cpu-sims` and phase B run only incomplete matchups.
- Add tests for partial results.

Status: backend implementation complete 2026-06-29; automated tests still pending.

### Phase 3: Frontend recovery

- Add status endpoint or include status in existing payloads.
- Mode Select shows incomplete CPU sim state.
- FCC blocks/recovers incomplete phase B.
- EOG flow remains unchanged except it benefits from durable state.

Status: implemented 2026-06-29 through existing command-center data.

Implementation notes:

- `GET /franchise/command-center/data` now includes `cpu_sim_resume`.
- Mode Select uses `cpu_sim_resume` after active-game resume priority:
  - active user game resume still routes to `court.html`
  - phase-A-complete / phase-B-incomplete CPU jobs show “Finishing Computer Games”
  - pressing the card routes to FCC with CPU recovery intent
- FCC is the recovery surface:
  - if `cpu_sim_resume.phase_b_required` is true, FCC keeps the page-load overlay visible
  - FCC calls `POST /franchise/complete-week/phase-b`
  - FCC reloads command-center data after phase B succeeds
  - if recovery still needs work or fails, the primary FCC CTA becomes `Finish Computer Games`

### Phase 4: Documentation + hardening

- Promote this work plan into a permanent system doc if needed.
- Cross-link from:
  - `Press_Conference_System.md`
  - `Tournament_Execution_System.md`
  - `Mid_Game_Resume_System.md`
  - `Distant_Game_Sim_System.md`
- Add repair/admin notes if a job remains failed after retries.

## Testing Plan

### Backend tests

- `start-cpu-sims` with no existing results creates job and partial results.
- Re-running `start-cpu-sims` skips completed matchups.
- Phase A landing during `start-cpu-sims` is preserved by merge.
- Phase B after partial `start-cpu-sims` only runs missing matchups.
- Phase B is idempotent after week advance.
- Stale running matchup is retried.
- Failed matchup is retried.
- EOS bracket cells are not clobbered by job writes.

### Manual QA

- Start franchise game, close browser before CPU sims finish, return and complete user game.
- Finish user game, close browser during “Simming Computer Games”, return through Mode Select.
- Trigger phase B twice from same tab; confirm single-flight still works.
- Trigger phase B after tab close; confirm durable resume works.
- Confirm no duplicate rows in `franchise.results.{week}`.
- Confirm week advances only after full slate is complete.

## Open Implementation Notes

- Job state should not become the source of truth for game results. `games` and `franchise.results.{week}` remain authoritative.
- Avoid nuking completed games. Repair tools may delete/rebuild corrupted data, but normal resume must retain completed results.
- The first implementation can track job/matchup state coarsely; exact per-matchup timing can be expanded later if useful.
- Keep phase B as the final closure path. Early `start-cpu-sims` is an optimization, not the authority for advancing the week.
