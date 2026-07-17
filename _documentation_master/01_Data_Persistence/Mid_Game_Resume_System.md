# Mid-Game Resume System

## Purpose

The Mid-Game Resume System lets a user refresh `court.html`, close the browser, or return later during an unfinished franchise game and resume from the latest stable game anchor.

The system intentionally resumes from a **stable stoppage anchor**, not from an arbitrary mid-animation or mid-possession frame. This keeps game state coherent even if the browser closes, the frontend cache disappears, or the backend process no longer has the game in memory.

## Current Status

**Simplified MGR v1 is the active target contract.**

Supported return paths:

- Browser refresh on `court.html`
- Browser close / later return through Mode Select
- Mode Select franchise card routing back to an active game
- Timeout / foul-out anchors
- Quarter-break resume through Set Lineup
- Live quarter-to-quarter transitions through Set Lineup without triggering the resume modal

Active implementation direction:

- `game.resume_anchor` is the durable source of truth for mid-game resume.
- No active `resume_anchor` means no Mid Game Resume behavior.
- Active `resume_anchor` means the user should see the MGR modal and, after accepting it, route through Set Lineup.
- Quarter-break anchors are created immediately when a non-final quarter completes.
- Quarter-break anchors are also created on the `/api/simulate-turn` early-return quarter-complete path so stale timeout/foul-out anchors do not survive a duplicate/preloaded `0:00` request.
- Timeout and foul-out anchors are created when their modal state is saved, before the user enters Set Lineup.
- Refresh and browser-close return both use the same anchor rule: backend resume state decides whether MGR exists.
- Accepting the MGR modal always routes through Set Lineup.
- Set Lineup return from MGR is the only path that should send both `resume_from_anchor=true` and `consume_resume_anchor=true`.
- `consume_resume_anchor=true` means restore from the saved anchor on this request; it does **not** delete the durable anchor.
- The durable anchor remains available until a newer timeout, foul-out, or non-final quarter-break anchor overwrites it, or until the game becomes final.
- When the first restored turn is `SIDE_INBOUND`, court playback skips only the SIP setup/walk-in phase because the resume anchor already hydrates player sprites at the SIP setup spots. The inbound pass phase still plays. This skip is scoped to accepted MGR Set Lineup returns and is not applied to normal live Set Lineup returns.
- Normal live quarter breaks must send `quarter_break_from=play_quarter` to Set Lineup and preserve it when returning to `court.html`; this marker tells the court boot code not to read the durable resume anchor or show the mid-game resume modal.
- If `quarter_break_from` is dropped on a side hop, `lineup_checkpoint=true` (without cold-resume flags) is the documented live-entry fallback so an in-session Set Lineup return never shows Resume Game merely because a durable stoppage anchor exists.
- `quarter_break_from=play_quarter|sim_quarter` and `lineup_checkpoint=true` are one-load court-entry markers. After the first successful `/api/simulate-quarter` call starts that live quarter, `gameScene.js` removes them from the URL. If they survive into later mid-quarter refreshes, the court falsely classifies the page as a live quarter entry, skips `/resume-state`, and paints dirty current-document scores/stats instead of the saved stoppage anchor.
- Live quarter entries are authoritative. If stale resume flags survive into a live quarter URL, `bootGame.js` strips them and `loadGameStats.js` ignores them.
- Resume-anchor writes must resolve and update the existing game document id before writing. Do not upsert a string `_id` first and then retry `ObjectId`; that can create duplicate game documents with different anchors.
- Mode Select resume card clock text is display-only. If a quarter-break anchor has already advanced the period but still reports `0:00`, Mode Select displays `8:00` in the resume card so the capsule reads as the next quarter start. This does not mutate the backend clock, URL clock, or court resume logic.

The simplified v1 intentionally does **not** support arbitrary mid-quarter recovery before the first stable anchor. If the user refreshes or closes the browser before any timeout, foul-out, or non-final quarter-break anchor exists, MGR is unavailable and normal non-MGR flow applies.

Primary files:

- Backend resume anchor save/load: `BackEnd/api/api.py`
- Backend Mode Select active-game lookup: `BackEnd/api/franchise_routes.py`
- Court resume modal and URL hydration: `FrontEnd/static/js/phaser/bootGame.js`
- Court resume request flagging: `FrontEnd/static/js/phaser/gameScene.js`
- Lineup return URL preservation: `FrontEnd/static/set-lineup.js`
- Mode Select active-game card and routing: `FrontEnd/static/mode-select.js`
- Mode Select resume card markup: `FrontEnd/static/mode-select.html`

Historical plan:

- `_documentation_master/projects/court_persistence_plan.md`

That project plan explains the original Option A + B-lite design. This document is the current system reference.

## Simplified MGR v1 Contract

This section is the active work plan.

### Product Rule

> MGR only resumes from explicit stable stoppage anchors.

The supported anchors are:

- timeout modal
- player foul-out modal
- non-final quarter break

No anchor means no MGR. The system should not try to preserve or reconstruct arbitrary mid-quarter refresh state.

### User Flow

When a valid anchor exists:

1. Browser refresh or browser close/return detects the active anchor through backend resume state.
2. Court shows the `Game In Progress` modal.
3. Gameplay does not start behind the modal.
4. User presses `Resume Game`.
5. User is routed to Set Lineup.
6. User and computer lineups are established on Set Lineup.
7. Set Lineup returns to `court.html` with `resume_from_anchor=true`, `consume_resume_anchor=true`, and `quarter_break_from=mid_game_resume`.
8. Backend restores from `game.resume_anchor.snapshot`.
9. Backend preserves the durable anchor after successful restore so later mid-quarter refreshes roll back to the same latest stoppage.
10. If the first restored turn is SIP, the court skips the redundant SIP setup/walk-in animation and plays the inbound pass from the already-hydrated setup spots.
11. Gameplay continues from the restored anchor using the Set Lineup selections.

When no valid anchor exists:

- Mode Select does not show active-game resume.
- Court does not show the MGR modal.
- Court does not route to Set Lineup for MGR.
- Backend does not restore or consume an anchor.
- Normal non-MGR game flow applies.

### Implementation Checklist

- [x] Disable pre-anchor Q1 fresh-game reset behavior.
- [x] Ensure Mode Select only exposes resume when backend `active_game_resume` exists and reports `status=stoppage_anchor`.
- [x] Ensure court only shows the MGR modal when `/api/game/{game_id}/resume-state` returns `status=stoppage_anchor`.
- [x] Ensure accepting the MGR modal always routes to Set Lineup.
- [x] Ensure Set Lineup return from MGR is the only path that sends `consume_resume_anchor=true`.
- [x] Ensure backend clears `resume_anchor` only when the game becomes final.
- [x] Ensure live timeout/foul-out returns do not convert the URL into `resume_from_anchor=true`.
- [x] Ensure computer lineup rebuilds only happen at explicit lineup checkpoints, full sim/CPU sim paths, or other non-court-refresh contexts.
- [x] Ensure no code path calls `/api/init-game` for a game with an active resume anchor.

### Sunset / Disabled Behaviors

These behaviors are being removed from the active v1 contract because they increased state complexity and second-order bug risk:

- Pre-anchor Q1 refresh fresh-game replacement.
- Direct timeout auto-start as an MGR cold/refresh resume path.
- URL-only proof that a resume exists.
- `resume_from_anchor=true` before the user accepts the MGR modal.
- Hidden computer lineup rebuild while staying on `court.html` after refresh.
- Attempting to make arbitrary mid-quarter refresh look like a coherent exact restore.

### Reduced Test Matrix

Required before treating the simplified feature as stable:

| Scenario | Expected result |
|---|---|
| Refresh before first anchor | No MGR modal; no hidden lineup mutation; normal non-MGR flow |
| Browser close before first anchor | Mode Select has no resume card; routes normally |
| Timeout anchor then refresh | MGR modal -> Set Lineup -> restore from durable anchor |
| Timeout anchor then browser close/return | Mode Select resume card -> court MGR modal -> Set Lineup -> restore from durable anchor |
| Foul-out anchor then refresh | MGR modal -> Set Lineup -> restore from durable anchor |
| Non-final quarter break anchor then refresh | MGR modal -> Set Lineup -> restore from durable anchor |
| Live Q1 -> Q2 transition without leaving | No MGR modal; normal Set Lineup quarter flow |
| Set Lineup return from MGR | No second MGR modal; backend restores from anchor and preserves it |
| Final game | Anchor cleared; no MGR resume |

## Core Principle

The user-facing resume target is the latest **stable stoppage anchor**.

That means the resume system does not try to restore:

- the exact animation frame
- a partially played micro-turn
- arbitrary live state after every completed turn
- frontend SFX or announcement cursor state

Instead, it restores from the last coherent point where the game had a known restart state:

- when a non-final quarter ends
- when `/api/simulate-turn` is called after a non-final quarter has already reached `0:00`
- when a timeout modal is created
- when a player foul-out modal is created

This may lose some turns if the user closes the browser mid-flow, but it avoids returning them to a random-looking state with missing sprites, incorrect clock setup, or mismatched UI controls.

## URL Flag Semantics

Resume URL flags have distinct meanings and must not be used interchangeably:

- `active_resume=true`: Mode Select found a durable resume anchor and is routing the user to `court.html` to decide whether to resume. This means **resume available**, not restore consumed.
- `resume_from_anchor=true`: the court or Set Lineup flow is actively restoring from the saved anchor.
- `consume_resume_anchor=true`: the next backend restore request should restore from the anchor. It does not clear the durable anchor.
- `resume_from_timeout=true`: the next gameplay turn should use timeout/foul-out restart semantics, usually SIP or free throw.
- `quarter_break_from=mid_game_resume`: cold resume has routed through Set Lineup and is returning to court.

Mode Select should set `active_resume=true`, but it should not set `resume_from_anchor=true`. The latter is only added after the user accepts the court resume modal or after Set Lineup returns from a cold resume flow.

`bootGame.js` is intentionally defensive: if an older URL contains both `active_resume=true` and `resume_from_anchor=true`, `active_resume` wins and the page must still probe `/api/game/{game_id}/resume-state`, hide Play Quarter controls, and show the resume modal.

Set Lineup returns from a cold resume with both `resume_from_anchor=true` and `consume_resume_anchor=true`. That combination is not modal state. It means the user already accepted resume, adjusted lineups, and the next gameplay request should restore from the anchor. Court boot must not show the `Game In Progress` modal again for this URL shape, or it creates a modal -> Set Lineup -> modal loop.

Live timeout/foul-out returns must not convert the URL to `resume_from_anchor=true` after gameplay starts. A normal live timeout return can set `resume_from_timeout=true` for the immediate restart turn, then normalize that flag back to `false` for future refreshes. Future refreshes should discover the durable anchor by calling `/api/game/{game_id}/resume-state`, not by relying on a stale URL restore flag.

Live timeout/foul-out returns must also not probe or publish `/resume-state` during the immediate court reload. The durable anchor exists for future browser refresh/close recovery, but `resume_from_timeout=true` means the user is already in the normal in-session timeout flow. If `loadGameStats.js` publishes that anchor into `window.__GOB_MGR_RESUME_STATE__`, `bootGame.js` can falsely show the MGR modal and route the user back through Set Lineup again.

Backend anchor clearing is intentionally narrow:

- clear `resume_anchor` when the game becomes final
- do not clear `resume_anchor` merely because `resume_from_anchor=true`
- do not clear `resume_anchor` merely because `consume_resume_anchor=true`

This prevents normal continued play after a timeout/foul-out or quarter-break resume from destroying the last stable rollback point before a newer stoppage anchor exists.

## Pre-Anchor Q1 Refresh Contract

Before the first stable anchor exists, the game has no durable mid-game resume target. Earlier versions attempted to make Q1 refresh safe by detecting a dirty pre-anchor game document, suppressing partial stats, and creating a fresh initialized game id before gameplay restarted.

That clean restart behavior is active for browser refresh only. It is intentionally separate from MGR.

This applies when the user refreshes `court.html` during Q1 before any of these have occurred:

- timeout modal
- player foul-out modal
- non-final quarter break

Simplified v1 expected behavior:

- Browser close / later return through Mode Select does not show a mid-game resume card.
- Browser refresh does not show the MGR modal.
- Browser refresh must not paint dirty gameplay scores, player stats, team stats, or playbook stats from the abandoned game document.
- Browser refresh shows the normal Play Quarter / Sim Game modal with clean pre-game chrome.
- When the user presses Play Quarter, Sim Quarter, or Sim Full Game, the frontend calls the normal `/api/init-game` path and replaces the URL `game_id` with the newly initialized game document before simulation starts.
- The abandoned dirty game document is not used for gameplay after the clean restart.
- Team strategy, playbook, FTD, scouting, and baseline player setup come from the normal backend init pipeline, not from copying stale fields out of the abandoned dirty game document.

Product rule:

> Pre-anchor Q1 refresh abandons live gameplay progress, but preserves setup and baseline initialization.

Critical hierarchy:

> Resume anchor existence disables pre-anchor reset. Do not add or rely on a separate "disable pre-anchor reset" flag.

The pre-anchor Q1 refresh path is allowed only when all of these are true:

- the URL is Q1
- the URL is not a live quarter entry (`quarter_break_from=play_quarter` / `sim_quarter`)
- the URL has no resume-flow flags:
  - `active_resume=true`
  - `resume_from_anchor=true`
  - `consume_resume_anchor=true`
  - `resume_from_timeout=true`
  - `quarter_break_from=mid_game_resume`
- the normal game document is dirty
- the game has no active backend resume anchor

Once the first timeout, player foul-out, or non-final quarter-break anchor is written, the game is no longer pre-anchor. From that moment, any dirty Q1 state must be resolved through the resume anchor on the existing game document, not by creating a fresh game id.

### Preserve

The system preserves setup identity by sending the same matchup/mode context into `/api/init-game`:

- matchup identity
- `mode`
- `franchise_id`
- `tournament_id`
- `week`
- `home`
- `away`
- `home_id`
- `away_id`
- `home_team_id`
- `away_team_id`
- `my_team`
- `team_id`
- `user_team_side`

The fresh game document then rebuilds these through the official init process:

- game plan / strategy settings
- playbook settings
- team attributes
- scouting data
- FTD baselines
- team record/display metadata
- initialized roster identity data
- `game_stats_initialized=true`

### Reset

The system discards gameplay data created after opening tip and before the refresh by not reusing the abandoned game document for simulation:

- `score`
- `home_team.score`
- `away_team.score`
- `quarter` back to `1`
- `clock` / `time_remaining` back to Q1 start: `8:00` / `480`
- `shot_clock_remaining` back to `30`
- `turns`
- animation payloads
- last turn payloads
- play-by-play state
- `box_score`
- `teams[*].box_score`
- `teams[*].team_game_stats`
- player `stats.game`
- player fouls
- team fouls
- timeouts consumed during abandoned gameplay
- `team_timeouts`
- `computer_timeouts`
- points by quarter
- possession / offense / defense live state
- `offensive_state`
- `current_playcall`
- `defense_playcall`
- `start_box_score`
- `team_scoreboard_meta`
- `timeout_*` fields
- `pending_computer_timeout`
- `timeout_called`
- foul-out pending or foul-out lock fields
- `_prev_offense_positions_for_hco`
- `motion_attack_shot_tracker`
- `no_defender_shots` and related diagnostic counters
- `last_*` live trackers
- `free_throws*`
- `one_and_one`
- `shooter`
- `flss_*` pending state
- `resume_anchor`
- all resume URL flags once normalized

### Player Baseline Rule

Player baseline initialization must be preserved, while gameplay mutations must be reset.

The persisted summary currently stores player runtime attributes as:

```json
{
  "EM": 0,
  "CH": 0,
  "MO": 0,
  "NG": 1.0
}
```

Contract:

- preserve baseline initialized `EM`
- preserve baseline initialized `CH`
- preserve baseline initialized `MO` only if it is still the pregame baseline value
- preserve baseline initialized `NG` only if it is still the pregame baseline value
- reset gameplay-mutated `MO`
- reset gameplay-mutated `NG`
- reset live `x` / `y` coordinates to lineup/default starting locations
- reset player game stats and fouls

Because `MO` and `NG` can be mutated during gameplay, the deprecated pre-anchor Q1 refresh path did **not** try to surgically clean the dirty game document.

Deprecated implementation behavior:

- `initializeGameStats()` previously detected dirty Q1 game documents and armed `window.__GOB_PRE_ANCHOR_Q1_REFRESH__`.
- `bootGame.js` previously used that flag to call `/api/init-game`, replace the URL `game_id`, and restart from a fresh initialized game document.
- This path is disabled in simplified MGR v1. `initializeGameStats()` clears any stale pre-anchor reset flag, and `ensureFreshGameForPreAnchorQ1Refresh()` is intentionally inert.

Current simplified behavior:

- If no durable `game.resume_anchor` exists, the MGR system does not intervene.
- A dirty pre-anchor Q1 refresh may show the current game document state, but it must not create a replacement game document.
- Once the first timeout, foul-out, or non-final quarter break creates an anchor, refresh/close recovery uses the normal MGR path: modal -> Set Lineup -> restore from durable anchor.

## Resume Anchor

Resume anchors are stored on the existing `games` document in a nested `resume_anchor` object.

The anchor is built in `BackEnd/api/api.py` by `_build_resume_anchor(...)`.

Writes use `resolve_game_write_id(...)`, which first calls `find_game_doc(...)` and then updates the id form already used by the saved game document. This prevents split-brain persistence where timeout anchors are written to a string-id duplicate while quarter-break anchors are written to the ObjectId document.

Shape:

```json
{
  "version": 1,
  "anchor_type": "quarter_break | timeout | foul_out",
  "saved_at": "2026-06-25T15:00:00Z",
  "game_id": "...",
  "quarter": 1,
  "clock": "7:54",
  "time_remaining": 474,
  "shot_clock_remaining": 30,
  "resume_from_timeout": true,
  "timeout_next_play_type": "SIDE_INBOUND",
  "timeout_trace_id": "...",
  "home_lineup": {
    "PG": "...",
    "SG": "...",
    "SF": "...",
    "PF": "...",
    "C": "..."
  },
  "away_lineup": {
    "PG": "...",
    "SG": "...",
    "SF": "...",
    "PF": "...",
    "C": "..."
  },
  "snapshot": {
    "...": "compact summarized game state"
  }
}
```

The `snapshot` is a compact game document produced from `summarize_game_state(gm, exclude_animations=True)`. It removes nested `resume_anchor` before saving, so anchors do not recursively contain older anchors.

## When Anchors Are Saved

### Quarter-break anchor

The backend creates a `quarter_break` anchor immediately when a non-final quarter ends.

Behavior:

- The anchor is created before or alongside the end-of-quarter / locker-room modal.
- The anchor captures the completed-quarter scoreboard, stats, clock, lineups, and restart context.
- The anchor is not created when the game is final, including final overtime.
- If the user closes the browser on the EOQ modal or before submitting the next lineup, Mode Select should offer resume from this quarter-break anchor.

Location:

- `BackEnd/api/api.py`
- save path: `/api/simulate-turn` quarter-complete save
- early-return save path: `/api/simulate-turn` when the saved game is already at `0:00` and no terminal free throw is pending
- log markers:
  - `[RESUME-ANCHOR-SAVE] phase=quarter_complete type=quarter_break`
  - `[RESUME-ANCHOR-SAVE] phase=quarter_complete_early_return type=quarter_break`

Reason:

- Quarter end is a natural exit point.
- The user should not lose progress through the completed quarter.
- The early-return save prevents stale timeout/foul-out anchors from surviving when a duplicate/preloaded turn request discovers that the quarter is already complete.

### Timeout anchor

The backend creates a `timeout` anchor when the timeout modal state is saved, before the user enters Set Lineup.

Behavior:

- The anchor includes `timeout_next_play_type`.
- The anchor includes timeout trace metadata and any SIP / FT restart fields.
- If the next play is a free throw, the designated free-throw shooter lock state must be preserved.
- Cold resume from this anchor routes to Set Lineup before gameplay.
- Returning from Set Lineup uses the preserved restart metadata to generate the first live turn.

Location:

- `BackEnd/api/api.py`
- save path: timeout modal save through `handle_timeout_save_and_response(...)`
- log marker: `[RESUME-ANCHOR-SAVE] phase=timeout_modal type=timeout`

### Foul-out anchor

The backend creates a `foul_out` anchor when the foul-out timeout modal state is saved, before the user enters Set Lineup.

Behavior:

- The anchor preserves the post-foul-out restart state.
- If the restart is a free throw, FT shooter lock state must be preserved.
- If the lineup required an exhausted/emergency player rule, the resulting context must be preserved.
- Cold resume from this anchor routes to Set Lineup before gameplay so the user can submit a legal replacement lineup.

Location:

- `BackEnd/api/api.py`
- save path: foul-out modal save through `handle_timeout_save_and_response(...)`
- discriminator: timeout save metadata has `timeout_reason: "FOUL_OUT"`
- log marker: `[RESUME-ANCHOR-SAVE] phase=timeout_modal type=foul_out`

### Legacy direct pre-sim anchor compatibility

There is still a guarded compatibility path in `/api/simulate-quarter` that can write a pre-sim anchor only when all are true:

- `resume_from_timeout=true`
- `resume_from_anchor=true`
- `consume_resume_anchor=false`

This is not the normal anchor creation path. Normal cold resume through Set Lineup returns with both `resume_from_anchor=true` and `consume_resume_anchor=true`, so it restores from the existing anchor while preserving the durable rollback point.

### Final game cleanup

When the game is final, the backend unsets `resume_anchor` so completed games do not show as resumable.

Location:

- `BackEnd/api/api.py`
- save update includes `"$unset": {"resume_anchor": ""}` when `is_final` is true.

## Resume-State Endpoint

Court pages check the lightweight resume-state endpoint before deciding whether to show start controls or a resume modal.

Endpoint:

```http
GET /api/game/{game_id}/resume-state
```

Location:

- `BackEnd/api/api.py`
- function: `get_game_resume_state(...)`

If the saved game has a `resume_anchor` and is not final, the endpoint returns a forced `stoppage_anchor` status based on the anchor snapshot.

Important response fields:

```json
{
  "game_id": "...",
  "status": "stoppage_anchor",
  "has_cached_game": true,
  "quarter": 1,
  "clock": "7:54",
  "time_remaining": 474,
  "home_team_id": "...",
  "away_team_id": "...",
  "home_team_name": "Morristown",
  "away_team_name": "Appalachia",
  "home_score": 3,
  "away_score": 2,
  "resume_from_timeout": true,
  "timeout_next_play_type": "SIDE_INBOUND",
  "timeout_trace_id": "...",
  "home_lineup": {},
  "away_lineup": {}
}
```

Status values used by the broader endpoint:

- `stoppage_anchor`: saved anchor exists and should drive resume.
- `timeout_resume`: timeout state exists without a dedicated anchor.
- `quarter_break`: game is between quarters.
- `active_mid_quarter`: game is active but no clean anchor is available.
- `pregame`: game exists but has not started.
- `final`: game is complete.
- `missing`: no usable game document exists.

For user-facing resume, `stoppage_anchor` is the important status.

## Browser Refresh Flow

Refresh starts on `court.html` with an existing `game_id`.

Flow:

1. `court.html` loads with a `game_id`.
2. `loadGameStats.js` checks `/api/game/{game_id}/resume-state` before normal game-doc hydration unless this is:
   - a live quarter transition (`quarter_break_from=play_quarter|sim_quarter`), or
   - an accepted Set Lineup restore return (`consume_resume_anchor=true`).
3. If the endpoint returns `stoppage_anchor`, `loadGameStats.js` publishes that anchor to `window.__GOB_MGR_RESUME_STATE__` and paints court stats from the anchor, not from the latest arbitrary game document.
4. `bootGame.js` consumes the published anchor state before making its own fallback `/resume-state` request.
5. If an active anchor exists, the page hides the normal Play Quarter / Sim controls.
6. The page shows a `Game In Progress` modal.
7. User presses `Resume Game`.
8. `applyResumeStateToUrl(resumeState)` updates the current court URL with:
   - `quarter`
   - `period`
   - `clock`
   - `resume_from_timeout`
   - `resume_from_anchor=true`
   - lineup player IDs from the anchor
9. `redirectResumeAnchorToSetLineup(resumeState)` routes all supported anchor types through Set Lineup.
10. The Set Lineup URL must preserve `resume_from_anchor=true`.
11. When the user submits Set Lineup, `set-lineup.js` must send both:
   - `resume_from_anchor=true`
   - `consume_resume_anchor=true`
12. `gameScene.js` includes both flags in the `/api/simulate-quarter` payload.
13. Backend restores the saved anchor snapshot first, then preserves the durable anchor after the successful save.

Key frontend function:

- `FrontEnd/static/js/phaser/bootGame.js`
- `applyResumeStateToUrl(resumeState)`
- `applyResumeStateToCourtChrome(resumeState)`

Key backend behavior:

- `BackEnd/api/api.py`
- when `body.resume_from_anchor` is true, the backend loads `game.resume_anchor.snapshot`, drops stale in-memory game state, and resumes from the anchor.

## Court UI Hydration

During an active mid-game resume, the visible court UI must use the saved stoppage anchor as its source of truth before the user presses `Resume Game`.

This matters because the normal game document can be ahead of the resume anchor. Example: the latest saved game document may contain several turns after the last stoppage, while the resume anchor intentionally points back to the last timeout, player foul-out, or quarter-break lineup return. Showing the normal game document behind the modal makes the court appear to have the wrong score, clock, fouls, or stat panels.

Rules:

- If `court.html` has a `game_id` and is not a live quarter transition or an accepted Set Lineup restore return, `loadGameStats.js` first calls `/api/game/{game_id}/resume-state`.
- If that endpoint returns `status: "stoppage_anchor"`, the returned anchor payload paints:
  - scoreboard scores
  - game clock
  - quarter label
  - shot clock when available
  - timeout/foul header state
  - player stat panels
  - team stat panels
- Only page loads without a valid backend anchor should prefer `/api/game/{game_id}` for initial court stats.
- `loadGameStats.js` publishes a valid anchor to `window.__GOB_MGR_RESUME_STATE__` so `bootGame.js` can use the same decision instead of running a separate, potentially divergent UI mode decision.
- `bootGame.js` also applies the compact anchor score/clock values through `applyResumeStateToCourtChrome(resumeState)` so the modal chrome cannot show stale values while the full stat panels hydrate.

Backend support:

- `/api/game/{game_id}/resume-state` returns a game-state-shaped anchor payload, not just a modal summary.
- The payload includes the anchor `score`, `teams`, `home_team`, `away_team`, `box_score`, `team_totals`, `team_stats`, `team_scoreboard_meta`, `fouls`, `timeouts`, `clock`, and `shot_clock_remaining`.
- Name-keyed score and box-score entries are included for compatibility with the existing court renderer.

## Browser Close / Later Return Flow

Cold return starts from Mode Select, not from an existing `court.html` tab.

Flow:

1. Mode Select loads the user's franchise command-center data.
2. Backend includes `active_game_resume` when the user's current scheduled game has a saved active anchor.
3. Mode Select renders the normal franchise card plus a visible `Game In Progress` resume card.
4. The franchise entry button changes to `Resume Game`.
5. Clicking franchise entry routes to `court.html` with:
   - `active_resume=true`
   - `resume_from_anchor=true`
   - `resume_from_timeout` from the saved anchor
   - canonical team ObjectIds
   - game ID, week, quarter, period, and clock
6. `bootGame.js` sees `active_resume=true` and shows the `Game In Progress` modal.
7. The game does **not** auto-start while this modal is visible.
8. User presses `Resume Game`.
9. `bootGame.js` applies the anchor URL state and routes to Set Lineup.
10. Set Lineup returns to `court.html` with both `resume_from_anchor=true` and `consume_resume_anchor=true`.
11. The backend restores from `resume_anchor.snapshot`, simulates from that anchor, saves the restored state, and preserves the durable anchor.

Key frontend files:

- `FrontEnd/static/mode-select.js`
- `FrontEnd/static/mode-select.html`
- `FrontEnd/static/js/phaser/bootGame.js`

Key backend file:

- `BackEnd/api/franchise_routes.py`

## Mode Select Active-Game Lookup

Mode Select active-game routing is handled by `_find_active_user_game_resume(...)` in `BackEnd/api/franchise_routes.py`.

Mode Select renders active-game resume details in `FrontEnd/static/mode-select.js`. Its clock label can normalize a `0:00` quarter-break anchor to `8:00` for display only, because the backend may advance the quarter before the persisted clock text has caught up. Do not use this display formatter as game-state authority.

It determines the user's current scheduled game from the franchise schedule, then scans incomplete game documents with a `resume_anchor`.

Important implementation detail:

Some saved game documents identify teams with slugs or names such as:

- `APPALACHIA`
- `MORRISTOWN`

The franchise schedule identifies teams with ObjectIds.

The lookup therefore matches teams using normalized identifier tokens:

- canonical ObjectId
- `name`
- `team_id`
- `slug`
- space/underscore variants
- case-insensitive comparisons

The payload returned to the frontend uses canonical scheduled ObjectIds for `home_team_id` and `away_team_id`, even if the saved game document internally used team slugs. This keeps the `court.html` URL compatible with the rest of the franchise game boot path.

Diagnostic logs:

- `[MODE-RESUME-LOOKUP] start`
- `[MODE-RESUME-LOOKUP] anchored_scan`
- `[MODE-RESUME-LOOKUP] fallback_exact_query`
- `[MODE-RESUME-LOOKUP] no_match`
- `[MODE-RESUME-RETURN]`

## Resume Modal Behavior

The court resume modal is intentionally blocking.

Simplified v1 rules:

- If `active_resume=true`, show the modal and wait for user input.
- Do not auto-start the game behind the modal.
- On `Resume Game`, route through Set Lineup.
- Set Lineup return sends `resume_from_anchor=true` and `consume_resume_anchor=true`.
- Do not use direct timeout auto-start as a cold/refresh MGR resume path.

This distinction matters:

- Browser refresh with an active anchor must show the modal.
- Browser close / return from Mode Select must pause at the modal so the user understands they are entering an active game.

Deprecated direct-timeout guard in `FrontEnd/static/js/phaser/bootGame.js`:

```javascript
if (resumeFromTimeout && !activeResume && gameId && homeTeam && awayTeam) {
  handleButtonClick(true);
}
```

Simplified v1 should remove or bypass this guard for MGR cold/refresh resume. Timeout-specific live gameplay may still use timeout restart semantics, but MGR recovery should always go through modal -> Set Lineup -> restore from durable anchor.

## Court Boot Classifier

Shared authority: `FrontEnd/static/js/phaser/utils/courtEntryResolver.js`.

Both `bootGame.js` and `loadGameStats.js` must call `classifyCourtBootMode` / `shouldProbeResumeStateForBoot` from that module. Do not re-implement live vs MGR probe rules locally — divergent guards caused live quarter-break returns to show Resume Game when a durable `quarter_break` anchor existed.

Boot modes:

- `live_quarter_entry`:
  - `quarter_break_from=play_quarter` or `quarter_break_from=sim_quarter`, **or**
  - `lineup_checkpoint=true` without cold-resume flags (`active_resume` / `resume_from_anchor` / `consume_resume_anchor`) and without `quarter_break_from=mid_game_resume`
- `anchor_restore_entry`: `resume_from_anchor=true` or `consume_resume_anchor=true`
- `cold_resume_entry`: `active_resume=true`
- `timeout_direct_entry`: `resume_from_timeout=true` (deprecated for MGR cold/refresh resume)
- `normal_entry`: no resume-specific intent

Rules:

- Cold / restore / timeout flags are classified **before** the `lineup_checkpoint` live fallback (MGR Set Lineup returns also set `lineup_checkpoint=true`).
- Explicit `quarter_break_from=play_quarter|sim_quarter` still wins first for live entry.
- `live_quarter_entry` always wins over stale resume flags once classified.
- `live_quarter_entry` strips `active_resume`, `resume_from_anchor`, `consume_resume_anchor`, and `anchor_type` from the URL and forces `resume_from_timeout=false`.
- `live_quarter_entry` and `timeout_direct_entry` must **not** probe or publish `/resume-state` for the Resume Game modal. A durable stoppage anchor may exist for cold recovery; that must not imply modal on an in-session return.
- `consume_resume_anchor=true` must not probe for the modal (accepted cold resume returning from Set Lineup).
- `cold_resume_entry` and refresh/`normal_entry` may probe `/api/game/:game_id/resume-state` for the resume modal.
- `anchor_restore_entry` restores from the anchor through `/api/simulate-quarter` and leaves the durable anchor available for later rollback until replaced or final.
- `timeout_direct_entry` should not be used for MGR cold/refresh resume in simplified v1.

`loadGameStats.js` hydrates before Phaser starts. It must use the same resolver so it does not publish `window.__GOB_MGR_RESUME_STATE__` on live quarter / live timeout / accepted-consume returns (that publication alone can make `bootGame.js` show Resume Game).

`TimeoutNavigationHelper.buildGameNavigationParams` preserves MGR/live court-entry flags across hops (`quarter_break_from`, `lineup_checkpoint`, `resume_from_anchor`, `consume_resume_anchor`, `active_resume`, `anchor_type`, `timeout_next_play_type`) so Game Plan / Box Score / Set Lineup side paths cannot drop live markers and false-trigger MGR.

## Lineup Checkpoint Contract

`lineup_checkpoint=true` is the explicit signal that the user has just exited `set-lineup.html`.

Only requests with this flag may perform checkpoint lineup work such as rebuilding the computer team's lineup from energy/foul restrictions and autosetting computer strategy. Plain `court.html` refreshes must not rebuild the computer lineup, because the user never left the court and existing sprites still represent the active lineup.

Court-entry role (MGR):

- On a live Set Lineup → court return, `lineup_checkpoint=true` (without cold-resume flags) classifies as `live_quarter_entry` even if `quarter_break_from=play_quarter|sim_quarter` was dropped on a side hop.
- Like `quarter_break_from=play_quarter|sim_quarter`, it is a **one-load** marker: after the first successful `/api/simulate-quarter` for that entry, `gameScene.js` removes `lineup_checkpoint` from the URL so a mid-quarter refresh can still probe `/resume-state` for true cold MGR.

Current wiring:

- `FrontEnd/static/set-lineup.js` adds `lineup_checkpoint=true` to court navigation after the user submits a lineup.
- `FrontEnd/static/js/shared/timeoutNavigationHelper.js` preserves `lineup_checkpoint` (and other MGR/live flags) across Set Lineup / Game Plan / Box Score hops.
- `FrontEnd/static/js/phaser/gameScene.js` forwards the flag in `/api/simulate-quarter`, then clears it from the URL after a successful quarter start.
- `BackEnd/api/api.py` accepts `lineup_checkpoint`.
- `BackEnd/main.py::simulate_quarter()` rebuilds the computer lineup only when `lineup_checkpoint=true` or when the request is a full-sim path (`turn_by_turn_mode=false`).

This keeps the MGR flow consistent:

- refresh/close with an anchor: modal -> Set Lineup -> `lineup_checkpoint=true` + consume flags -> restore from durable anchor (`anchor_restore_entry`, not live)
- live quarter break: Set Lineup -> `lineup_checkpoint=true` (+ preferably `quarter_break_from=play_quarter`) -> Play Quarter controls, no Resume Game modal
- refresh without leaving court and without a Set Lineup submit: no hidden lineup mutation
- full sim: computer lineup automation remains allowed

## URL Flags

### `resume_from_anchor=true`

Tells the backend to restore from `game.resume_anchor.snapshot` instead of using the latest arbitrary game document or in-memory game object.

Used by:

- `bootGame.js`
- `gameScene.js`
- `/api/simulate-quarter`

Lifecycle rule:

- `resume_from_anchor=true` is a one-shot restore flag.
- If a resume anchor routes through Set Lineup, this flag must survive both hops:
  - `court.html` resume modal to `set-lineup.html`
  - `set-lineup.html` return to `court.html`
- Do not replace `resume_from_anchor=true` with only `consume_resume_anchor=true`; consume is only meaningful when paired with an anchor restore request.
- After the first successful `/api/simulate-quarter` response from that anchor, `gameScene.js` removes `resume_from_anchor` and `active_resume` from the browser URL and sets `resume_from_timeout=false`.
- On the same successful backend save, `/api/simulate-quarter` preserves `game.resume_anchor`.
- The next stable stoppage overwrites the durable anchor, which prevents an older anchor such as `Q1 2:36` from remaining the latest rollback point after the user later reaches a newer timeout, foul-out, or quarter break.

### `consume_resume_anchor=true`

Tells the backend that this request is the Set Lineup return for an accepted anchor-backed restore. It does not clear `game.resume_anchor`.

Lifecycle rule:

- `consume_resume_anchor=true` is paired with `resume_from_anchor=true` on Set Lineup returns from cold resume.
- It is not a substitute for `resume_from_anchor=true`.
- The backend restore order is: load anchor snapshot, simulate/save from that snapshot, preserve `resume_anchor`.

### `resume_from_timeout=true`

Preserves the existing timeout/foul-out restart path when the anchor's next play is a timeout-style restart.

This flag does not by itself mean "show a modal." It means the backend should resume through the timeout restart logic if appropriate.

### `active_resume=true`

Frontend-only UX flag used when entering from Mode Select into an active unfinished game.

It means:

- show the `Game In Progress` modal
- block auto-start
- clear the flag when the user presses `Resume Game`

### `quarter_break_from=play_quarter`

Frontend live-quarter guard used for normal in-game Q1→Q2, Q2→Q3, and Q3→Q4 transitions.

It means:

- the user is already in the game flow
- the transition is a live quarter break, not a cold browser-return resume
- `bootGame.js` must not check `/resume-state` to show the mid-game resume modal on this load

Lifecycle rule:

- Every non-final live quarter-complete path in `gameScene.js` must add `quarter_break_from=play_quarter` when sending the user to `set-lineup.html`.
- `set-lineup.js` must preserve the marker when returning to `court.html`.
- Do not set `resume_from_anchor=true`, `consume_resume_anchor=true`, or `active_resume=true` for normal live quarter transitions.
- Missing this marker causes `court.html` to treat the next quarter as a possible cold resume and can incorrectly show the `Game In Progress` modal from the durable anchor.

## Backend Load Path

When `/api/simulate-quarter` receives `resume_from_anchor=true`:

1. It finds the saved game document.
2. It reads `resume_anchor.snapshot`.
3. It sets `timeout_saved_state` to the anchor snapshot.
4. It updates the request quarter from the snapshot.
5. It sets `resume_from_timeout` if the snapshot includes a timeout next play.
6. It drops any stale `ongoing_games` cache entry for that game.
7. If a saved game document is loaded later in the function, the saved document is replaced with the anchor snapshot before constructing the `GameManager`.
8. After a successful save, the `resume_anchor` remains on the game document until replaced by a newer stoppage anchor or cleared at final.

Relevant logs:

- `[RESUME-ANCHOR-LOAD]`
- `[RESUME-ANCHOR-RESTORE]`
- `[RESUME-ANCHOR-CONSUME]`
- `[TIMEOUT TRACE] simulate-quarter loaded-timeout`

## Frontend Court Load Guard

`bootGame.js` keeps the normal pre-game controls hidden while resume state is checked.

If an anchor exists:

- normal Play Game / Sim Full Game controls stay hidden
- `Game In Progress` modal appears
- resume button is enabled only when `status === "stoppage_anchor"`

If no anchor exists:

- normal game-start or quarter-start controls show as before.

## Player Sprite Coordinate Hydration

Backend resume snapshots persist active player court positions as `player.x` and `player.y` in `simData.players`.

Frontend sprite creation uses `player.startingCoords`.

Therefore, `gameScene.js` must bridge these fields before calling `loadPhaserPlayers(...)`:

```javascript
player.startingCoords = { x: Number(player.x), y: Number(player.y) }
```

This matters most on cold browser return from Mode Select. The resume request can produce a valid restart turn, such as `SIDE_INBOUND`, while player rows only carry saved `x/y` positions. If the frontend does not hydrate `startingCoords`, `createPhaserPlayer(...)` falls back to `{ x: 50, y: 25 }`, which stacks all player sprites at center court.

The correct contract is:

- backend owns authoritative player coordinates
- backend sends those coordinates as `x/y` in `simData.players`
- frontend copies `x/y` into `startingCoords` before sprite creation
- frontend remains renderer-only; it does not calculate new gameplay coordinates

## Expected User Experience

### Refresh During Active Game

Expected:

- user returns to the latest saved stoppage anchor
- normal start buttons are not shown for an active game
- game resumes after pressing `Resume Game` if the modal is shown
- score, clock, lineups, possession context, and next play come from the anchor

### Close Browser During Active Game, Return Later

Expected:

- user lands on Mode Select
- franchise card shows active-game resume state
- entering franchise routes to `court.html`, not FCC
- court shows `Game In Progress`
- game does not start until the user presses `Resume Game`

### Completed Game

Expected:

- `resume_anchor` is removed
- Mode Select does not show active-game resume
- franchise entry routes normally

## Known Tradeoffs

The system prioritizes coherent resume over exact resume.

If a user plays several possessions after the last saved anchor and then closes the browser, they may resume from the earlier anchor rather than the last visible possession. This is intentional for now.

Reasons:

- exact mid-turn restore would require frontend playback state persistence
- arbitrary DB checkpoints can produce inconsistent court setup
- stable anchors reduce risk of missing sprites, wrong buttons, or mismatched clock/possession state

## Diagnostic Logging

Backend:

- `[RESUME-ANCHOR-SAVE] phase=timeout_modal type=timeout|foul_out`
- `[RESUME-ANCHOR-SAVE] phase=quarter_complete type=quarter_break`
- `[RESUME-ANCHOR-SAVE] phase=quarter_complete_early_return type=quarter_break`
- `[RESUME-ANCHOR-SAVE] phase=pre_sim` for guarded legacy direct-anchor compatibility only
- `[RESUME-ANCHOR-READ]`
- `[RESUME-ANCHOR-LOAD]`
- `[RESUME-ANCHOR-RESTORE]`
- `[RESUME-ANCHOR-CONSUME]`
- `[MODE-RESUME-LOOKUP]`
- `[MODE-RESUME-RETURN]`

Frontend:

- `[RESUME-ANCHOR-CLIENT] applied anchor URL state`
- `[RESUME-ANCHOR-CLIENT] simulate-quarter payload from anchor`
- `[RESUME-ANCHOR-CLIENT] converted timeout-return URL for future refreshes`
- `[MODE-RESUME-CLIENT] render franchise card`
- `[MODE-RESUME-CLIENT] route resume`

These logs are intentionally verbose while the feature is being stabilized. Once the feature is fully settled in production, reduce non-error logs from warning to debug/info or remove them.

## Testing Checklist

### Browser refresh

1. Start a franchise game.
2. Reach a timeout, foul-out, or quarter-break lineup return.
3. Resume play.
4. Let the game advance.
5. Refresh `court.html`.
6. Confirm the game returns to the latest saved anchor.
7. Confirm the game does not reset to opening tip.
8. Confirm lineups and score come from the anchor.

### Browser close / cold return

1. Start a franchise game.
2. Reach a saved anchor.
3. Resume play.
4. Close the browser tab or browser.
5. Return to the site.
6. Confirm Mode Select shows the active-game resume state.
7. Click the franchise card.
8. Confirm `court.html` shows `Game In Progress`.
9. Confirm game does not start behind the modal.
10. Press `Resume Game`.
11. Confirm game starts from the anchor.

### Completion cleanup

1. Finish a franchise game.
2. Confirm the saved game document no longer has `resume_anchor`.
3. Confirm Mode Select routes to FCC normally.

## Future Improvements

Potential future work:

- Move stabilized diagnostic logs to debug level.
- Add automated tests for `_find_active_user_game_resume(...)` identifier matching.
- Add API tests for `/api/game/{game_id}/resume-state`.
- Add a user-facing timestamp on the Mode Select resume card.
- Add an explicit abandon/forfeit flow as a separate feature if needed.
- Consider exact completed-turn resume only if the UX need outweighs the added persistence complexity.

## Related: Franchise CPU Sim Resume

Mid Game Resume owns the user's active game resume path. It does not own computer-game simulation for the rest of the franchise week.

Computer games are covered by the adjacent Franchise CPU Sim Resume work stream:

- project plan: `_documentation_master/projects/franchise_cpu_sim_resume_plan.md`
- backend entry points:
  - `POST /franchise/complete-week/start-cpu-sims`
  - `POST /franchise/complete-week/phase-b`
  - `_complete_week_finish_cpu_and_persist`
- durable state:
  - `franchises.cpu_sim_jobs.{week}`

Contract:

- completed CPU games are retained
- completed `franchise.results.{week}` rows are retained
- missing/stale/failed CPU matchups are resumable
- phase B remains the final authority for week advancement
- Mid Game Resume can restore the user game independently while CPU sims continue or are resumed later

As of 2026-06-29, backend durable CPU sim job state and frontend recovery surfaces are implemented:

- `GET /franchise/command-center/data` exposes `cpu_sim_resume`.
- Mode Select shows a “Finishing Computer Games” card only when the user has no active game resume and phase B still needs to finish.
- FCC is the recovery surface. It keeps the page-load overlay visible, resumes phase B, reloads authoritative command-center data, then renders.
- If phase B cannot finish, FCC keeps the main CTA pointed at `Finish Computer Games` instead of exposing normal week actions.


## Current SS&S Contract

The formal resume contract is:

1. One source of truth: game.resume_anchor is the only source for mid-game resume.
2. One lifecycle: create anchors at stable stoppages, route cold resume through Set Lineup, restore from the latest anchor, preserve it until the next anchor or final.
3. One API: court and Mode Select both read resume eligibility/state from the same backend contract.
4. One frontend mode: if active resume exists, court boots into resume_pending, hydrates all UI from anchor, blocks sim until button press.
5. One backend behavior: `consume_resume_anchor=true` restores from the anchor but does not clear it; only final game cleanup clears it.
6. One v1 scope: no anchor means no MGR behavior.
7. Tests for flows: browser refresh, browser close/return, timeout anchor, foul-out anchor, quarter-break anchor, Q1 to Q2 transition, and no stale-anchor reuse.

## Deferred Future Hardening: Central Court Entry Resolver

**Partial progress (live false-MGR fix):** `courtEntryResolver.js` is now the shared classifier for `bootGame.js` + `loadGameStats.js` probe/modal eligibility, including `lineup_checkpoint` as a live-entry fallback. `TimeoutNavigationHelper` preserves MGR/live URL flags across hops. Full enum / Mode Select / Set Lineup adoption and the Phase 5–6 test matrix below remain future work.

The remaining fragility is modules that still infer resume state independently:

- `mode-select.js`
- `set-lineup.js` (flag emission; court consumers are shared)
- `gameScene.js`

A future hardening pass should finish centralizing court-entry classification so UI behavior, URL handling, backend restore flags, and pre-anchor reset rules are derived from the same state everywhere.

### Goal

Create one court-entry decision layer that answers:

> Given the current URL and backend resume state, what kind of court entry is this?

All frontend modules should consume that resolved state instead of independently interpreting URL flags.

### Target State Enum

The resolver should return one of these states:

| State | Meaning | Primary UI behavior |
|---|---|---|
| `new_game_entry` | No game id or clean new game start | Show Play Quarter / Sim Full Game controls |
| `pre_anchor_dirty_q1` | Q1 game has partial gameplay but no resume anchor | Suppress dirty stats; next play/sim creates a fresh game id |
| `anchor_available` | Backend has `resume_anchor.status=stoppage_anchor`; user has not accepted resume | Show `Game In Progress` modal; block gameplay |
| `anchor_lineup_entry` | Cold resume accepted and routed to Set Lineup | Show Set Lineup from anchor snapshot |
| `anchor_restore_entry` | Set Lineup returned and backend should restore from anchor | Simulate from anchor; consume anchor after successful restore |
| `live_quarter_entry` | Normal quarter-to-quarter transition without browser exit | Do not show resume modal; show normal quarter controls |
| `timeout_direct_entry` | Live timeout/foul-out return that should start directly | Hide Play Quarter controls; auto-start only for valid live return |
| `final_game` | Game complete | No resume; route normally |
| `invalid_resume_state` | URL claims resume but backend has no valid anchor | Fail visibly or route to safe recovery; never silently init a fresh game |

### Authority Rules

1. Backend resume state outranks URL flags.
2. `game.resume_anchor.status=stoppage_anchor` means the game is not pre-anchor.
3. `active_resume=true` means resume is available; it does not mean restore should run.
4. `resume_from_anchor=true` means restore is being requested.
5. `consume_resume_anchor=true` means the backend should restore from the anchor for this request; it must not clear the durable anchor.
6. `quarter_break_from=play_quarter|sim_quarter` means normal live quarter entry and should suppress the resume modal.
7. Fresh game-id creation is allowed only in `pre_anchor_dirty_q1`.

### Resolver Inputs

The resolver should accept:

- current URL params
- current `game_id`
- backend `/api/game/{game_id}/resume-state` response, when available
- optionally the normal `/api/game/{game_id}` response for dirty pre-anchor detection

The resolver should not directly mutate URL, DOM, or backend state. It should be pure enough to unit test.

### Resolver Output

The resolver should return:

- `state`
- `game_id`
- `quarter`
- `period`
- `clock`
- `home_score`
- `away_score`
- `anchor_type`
- `resume_from_timeout`
- `next_play_type`
- `should_show_resume_modal`
- `should_show_pregame_controls`
- `should_route_to_set_lineup`
- `should_autostart`
- `should_create_fresh_pre_anchor_game`
- `should_consume_anchor`
- `reason`

### Migration Plan

#### Phase 1: Descriptive Resolver, No Behavior Change

- Add shared resolver module, likely under `FrontEnd/static/js/phaser/utils/`.
- Wire `bootGame.js` to call it and log the resolved state.
- Do not change existing behavior in this phase.
- Compare resolver output against current behavior in logs.

Search logs:

- `[MGR-ENTRY-RESOLVER]`

#### Phase 2: Court Boot Adopts Resolver

- Replace `bootGame.js` local boot classification with resolver output.
- Use resolver output to decide:
  - resume modal visibility
  - pre-game button visibility
  - whether gameplay can auto-start
  - whether to route through Set Lineup

#### Phase 3: Stats Hydration Adopts Resolver

- Replace `loadGameStats.js` local resume/pre-anchor inference.
- Use resolver output to decide:
  - anchor snapshot hydration
  - normal game-doc hydration
  - dirty pre-anchor suppression

#### Phase 4: Set Lineup Return Adopts Resolver Semantics

- Ensure `set-lineup.js` emits only documented flags:
  - cold resume return: `resume_from_anchor=true`, `consume_resume_anchor=true`, `quarter_break_from=mid_game_resume`
  - live quarter return: `quarter_break_from=play_quarter|sim_quarter`, `resume_from_timeout=false`
  - live timeout/foul-out return: `resume_from_timeout=true`

#### Phase 5: Backend Contract Tests

- Add tests for:
  - `/api/game/{game_id}/resume-state`
  - anchor creation at timeout modal
  - anchor creation at foul-out modal
  - anchor creation at non-final quarter complete
  - anchor clearing only after final game completion
  - no active resume after final game

#### Phase 6: Frontend State Matrix Tests

Unit test the resolver for:

- fresh Q1 game
- dirty Q1 before first anchor
- dirty Q1 with anchor
- Mode Select cold return with active anchor
- browser refresh on court with active anchor
- normal Q1 to Q2 live transition
- timeout Set Lineup return
- foul-out Set Lineup return
- Set Lineup return from cold resume
- durable anchor preserved after restore
- final game
- stale URL with conflicting flags

### Anti-Regression Rules

- Do not introduce a new durable frontend resume flag.
- Do not create another source of truth outside `game.resume_anchor`.
- Do not let URL flags alone prove a resume exists.
- Do not let dirty Q1 detection create a fresh game if backend resume-state says an anchor exists.
- Do not auto-start gameplay while the `Game In Progress` modal is visible.
- Do not show Play Quarter / Sim Full Game controls in `anchor_available`.
- Do not show the resume modal in `live_quarter_entry`.

### Success Criteria

The hardening pass is complete when:

- one resolver owns court-entry classification
- all listed frontend modules consume resolver output or documented backend state
- every state in the matrix has automated coverage
- browser refresh and browser close/return behave identically when a resume anchor exists
- Q1 pre-anchor refresh remains isolated to games with no anchor
- normal quarter transitions never trigger the resume modal
- no code path can call `/api/init-game` for a game with an active resume anchor
