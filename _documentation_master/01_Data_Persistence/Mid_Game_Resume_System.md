# Mid-Game Resume System

## Purpose

The Mid-Game Resume System lets a user refresh `court.html`, close the browser, or return later during an unfinished franchise game and resume from the latest stable game anchor.

The system intentionally resumes from a **stable stoppage anchor**, not from an arbitrary mid-animation or mid-possession frame. This keeps game state coherent even if the browser closes, the frontend cache disappears, or the backend process no longer has the game in memory.

## Current Status

**Implemented for franchise court resume; active stabilization ongoing.**

Supported return paths:

- Browser refresh on `court.html`
- Browser close / later return through Mode Select
- Mode Select franchise card routing back to an active game
- Timeout / foul-out style restart flows where the next turn is already known
- Quarter-break resume through Set Lineup
- Live quarter-to-quarter transitions through Set Lineup without triggering the resume modal

Current implementation details:

- `game.resume_anchor` is the durable source of truth for mid-game resume.
- `bootGame.js` classifies every court load into one boot mode before deciding whether to read resume state, show the resume modal, auto-start, or treat the page as normal live gameplay.
- Quarter-break anchors are created immediately when a non-final quarter completes.
- Quarter-break anchors are also created on the `/api/simulate-turn` early-return quarter-complete path so stale timeout/foul-out anchors do not survive a duplicate/preloaded `0:00` request.
- Timeout and foul-out anchors are created when their modal state is saved, before the user enters Set Lineup.
- Cold resume routes every supported anchor type through Set Lineup before gameplay.
- Set Lineup returns from cold resume must send both `resume_from_anchor=true` and `consume_resume_anchor=true`.
- Normal live quarter breaks must send `quarter_break_from=play_quarter` to Set Lineup and preserve it when returning to `court.html`; this marker tells the court boot code not to read the durable resume anchor or show the mid-game resume modal.
- Live quarter entries are authoritative. If stale resume flags survive into a live quarter URL, `bootGame.js` strips them and `loadGameStats.js` ignores them.
- Resume-anchor writes must resolve and update the existing game document id before writing. Do not upsert a string `_id` first and then retry `ObjectId`; that can create duplicate game documents with different anchors.

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
- `consume_resume_anchor=true`: the next backend restore request should consume/clear the anchor after successful restore.
- `resume_from_timeout=true`: the next gameplay turn should use timeout/foul-out restart semantics, usually SIP or free throw.
- `quarter_break_from=mid_game_resume`: cold resume has routed through Set Lineup and is returning to court.

Mode Select should set `active_resume=true`, but it should not set `resume_from_anchor=true`. The latter is only added after the user accepts the court resume modal or after Set Lineup returns from a cold resume flow.

`bootGame.js` is intentionally defensive: if an older URL contains both `active_resume=true` and `resume_from_anchor=true`, `active_resume` wins and the page must still probe `/api/game/{game_id}/resume-state`, hide Play Quarter controls, and show the resume modal.

Set Lineup returns from a cold resume with both `resume_from_anchor=true` and `consume_resume_anchor=true`. That combination is not modal state. It means the user already accepted resume, adjusted lineups, and the next gameplay request should restore/consume the anchor. Court boot must not show the `Game In Progress` modal again for this URL shape, or it creates a modal -> Set Lineup -> modal loop.

Live timeout/foul-out returns must not convert the URL to `resume_from_anchor=true` after gameplay starts. A normal live timeout return can set `resume_from_timeout=true` for the immediate restart turn, then normalize that flag back to `false` for future refreshes. Future refreshes should discover the durable anchor by calling `/api/game/{game_id}/resume-state`, not by relying on a stale URL restore flag.

Backend anchor clearing is explicit:

- clear `resume_anchor` when `consume_resume_anchor=true`
- clear `resume_anchor` when the game becomes final
- do not clear `resume_anchor` merely because `resume_from_anchor=true`

This prevents normal continued play after a timeout/foul-out from destroying the last stable resume anchor.

## Pre-Anchor Q1 Refresh Contract

Before the first stable anchor exists, the game has no durable mid-game resume target.

This applies when the user refreshes `court.html` during Q1 before any of these have occurred:

- timeout modal
- player foul-out modal
- non-final quarter break

Expected behavior:

- Browser close / later return through Mode Select does not show a mid-game resume card.
- Browser refresh may show the normal Play Quarter / Sim Full Game controls.
- The refreshed court must not display partial scores, partial player stats, partial team stats, or stale clock values from the abandoned pre-anchor gameplay.
- The next Play Quarter / Sim Full Game action must not continue from the dirty partial gameplay state.

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

The system should preserve setup data that existed before gameplay began:

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
- selected user lineup from URL params
- selected computer lineup if already encoded in URL params
- game plan / strategy settings
- playbook settings
- team attributes
- scouting data
- FTD baselines
- team record/display metadata such as rank, wins, losses, colors, logos, and profile fields when present
- initialized roster identity data such as player id, name, jersey, height, photo, and team colors
- `game_stats_initialized=true`

### Reset

The system should discard gameplay data created after opening tip and before the refresh:

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

Because `MO` and `NG` can be mutated during gameplay, the implemented pre-anchor Q1 refresh path does **not** try to surgically clean the dirty game document.

Implemented behavior:

1. `initializeGameStats()` detects dirty Q1 game documents only when there are no resume-flow URL flags and no active backend resume anchor.
2. When dirty pre-anchor Q1 state is detected, the court suppresses accumulated stat hydration and paints clean pregame chrome:
   - score `0-0`
   - `Q1`
   - `8:00`
   - shot clock `30`
   - no partial player or team stats
3. The court sets `window.__GOB_PRE_ANCHOR_Q1_REFRESH__ = true`.
4. Before Play Quarter, Sim Quarter, or Sim Full Game starts, `bootGame.js` re-checks:
   - no resume-flow URL flags are present
   - the armed game id still matches the current URL game id
   - `/api/game/{game_id}/resume-state` does not report `status=stoppage_anchor`
5. Only if those checks still pass, `bootGame.js` calls `/api/init-game` with the preserved setup payload.
6. The response `game_id` replaces the dirty URL `game_id`.
7. Gameplay starts from the fresh initialized game document.

This intentionally abandons the dirty pre-anchor game document instead of mutating it in place. Once the first stable anchor exists, this fresh-game replacement path is no longer used; the Mid Game Resume System resumes from anchors on the existing game document.

The abandoned pre-anchor document may remain in the database until normal cleanup handles it. It is no longer referenced by the active browser URL after the fresh replacement is created.

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

This is not the normal anchor creation path. Normal cold resume through Set Lineup returns with both `resume_from_anchor=true` and `consume_resume_anchor=true`, so it restores the existing anchor and then clears it.

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

1. `bootGame.js` loads.
2. `initGame()` calls `/api/game/{game_id}/resume-state` if a game is present and either:
   - `active_resume=true`, or
   - the URL is not already a direct timeout resume.
3. If the endpoint returns `stoppage_anchor`, the page hides the normal pre-game controls.
4. The page shows a `Game In Progress` modal.
5. User presses `Resume Game`.
6. `applyResumeStateToUrl(resumeState)` updates the current court URL with:
   - `quarter`
   - `period`
   - `clock`
   - `resume_from_timeout`
   - `resume_from_anchor=true`
   - lineup player IDs from the anchor
7. `redirectResumeAnchorToSetLineup(resumeState)` routes all supported anchor types through Set Lineup.
8. The Set Lineup URL must preserve `resume_from_anchor=true`.
9. When the user submits Set Lineup, `set-lineup.js` must send both:
   - `resume_from_anchor=true`
   - `consume_resume_anchor=true`
10. `gameScene.js` includes both flags in the `/api/simulate-quarter` payload.
11. Backend restores the saved anchor snapshot first, then clears the anchor after the successful save.

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

- If `active_resume=true` or `resume_from_anchor=true`, `loadGameStats.js` first calls `/api/game/{game_id}/resume-state`.
- If that endpoint returns `status: "stoppage_anchor"`, the returned anchor payload paints:
  - scoreboard scores
  - game clock
  - quarter label
  - shot clock when available
  - timeout/foul header state
  - player stat panels
  - team stat panels
- Only non-resume page loads should prefer `/api/game/{game_id}` for initial court stats.
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
11. The backend restores from `resume_anchor.snapshot`, simulates from that anchor, saves the restored state, then clears the anchor.

Key frontend files:

- `FrontEnd/static/mode-select.js`
- `FrontEnd/static/mode-select.html`
- `FrontEnd/static/js/phaser/bootGame.js`

Key backend file:

- `BackEnd/api/franchise_routes.py`

## Mode Select Active-Game Lookup

Mode Select active-game routing is handled by `_find_active_user_game_resume(...)` in `BackEnd/api/franchise_routes.py`.

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

Rules:

- If `active_resume=true`, show the modal and wait for user input.
- Do not auto-start the game behind the modal.
- On `Resume Game`, remove the modal and start the game.
- Direct timeout resumes without `active_resume=true` can still auto-start.

This distinction matters:

- Browser refresh may resume directly after the URL has already been normalized.
- Browser close / return from Mode Select must pause at the modal so the user understands they are entering an active game.

The guard lives in `FrontEnd/static/js/phaser/bootGame.js`:

```javascript
if (resumeFromTimeout && !activeResume && gameId && homeTeam && awayTeam) {
  handleButtonClick(true);
}
```

## Court Boot Classifier

`FrontEnd/static/js/phaser/bootGame.js` owns the frontend boot-mode decision. This classifier is the single frontend authority for whether `court.html` is entering live gameplay, restoring an anchor, or showing the `Game In Progress` modal.

Boot modes:

- `live_quarter_entry`: `quarter_break_from=play_quarter` or `quarter_break_from=sim_quarter`
- `anchor_restore_entry`: `resume_from_anchor=true` or `consume_resume_anchor=true`
- `cold_resume_entry`: `active_resume=true`
- `timeout_direct_entry`: `resume_from_timeout=true`
- `normal_entry`: no resume-specific intent

Rules:

- `live_quarter_entry` always wins over stale resume flags.
- `live_quarter_entry` strips `active_resume`, `resume_from_anchor`, `consume_resume_anchor`, and `anchor_type` from the URL and forces `resume_from_timeout=false`.
- Only `cold_resume_entry` or `normal_entry` may probe `/api/game/:game_id/resume-state` for the resume modal.
- `anchor_restore_entry` restores from the anchor through `/api/simulate-quarter` and then consumes it.
- `timeout_direct_entry` may auto-start because it is already an in-game timeout/foul-out restart, not a cold browser return.

`FrontEnd/static/js/phaser/utils/loadGameStats.js` must apply the same live-quarter guard when deciding whether to hydrate from `/resume-state`. This matters because court stats hydrate before `bootGame.js` starts Phaser.

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
- Do not replace `resume_from_anchor=true` with only `consume_resume_anchor=true`; that clears the saved anchor without restoring it and can reload newer non-anchor score/stats.
- After the first successful `/api/simulate-quarter` response from that anchor, `gameScene.js` removes `resume_from_anchor` and `active_resume` from the browser URL and sets `resume_from_timeout=false`.
- On the same successful backend save, `/api/simulate-quarter` unsets `game.resume_anchor`.
- This prevents a stale anchor, for example `Q1 2:36`, from being restored again after the user later reaches the next quarter break or lineup return.

### `consume_resume_anchor=true`

Tells the backend to clear `game.resume_anchor` after the anchor-backed restore succeeds.

Lifecycle rule:

- `consume_resume_anchor=true` is paired with `resume_from_anchor=true` on Set Lineup returns from cold resume.
- It is not a substitute for `resume_from_anchor=true`.
- The backend restore order is: load anchor snapshot, simulate/save from that snapshot, then unset `resume_anchor`.

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
8. After a successful save, the consumed `resume_anchor` is removed from the game document.

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
2. One lifecycle: create anchors at stable stoppages, route cold resume through Set Lineup, restore once, then consume.
3. One API: court and Mode Select both read resume eligibility/state from the same backend contract.
4. One frontend mode: if active resume exists, court boots into resume_pending, hydrates all UI from anchor, blocks sim until button press.
5. One backend behavior: resume_from_anchor=true restores once, simulates, then clears the anchor.
6. Tests for flows: browser refresh, browser close/return, timeout anchor, foul-out anchor, quarter-break anchor, Q1 to Q2 transition, and no stale-anchor reuse.

## System Hardening Plan: Central Court Entry Resolver

The current implementation has been stabilized incrementally, but several frontend modules still infer resume state independently:

- `mode-select.js`
- `bootGame.js`
- `loadGameStats.js`
- `set-lineup.js`
- `gameScene.js`

That distributed inference is the main fragility risk. A future hardening pass should centralize court-entry classification into one resolver so UI behavior, URL handling, backend restore flags, and pre-anchor reset rules are derived from the same state.

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
5. `consume_resume_anchor=true` means the backend may clear the anchor after successful restore.
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
  - anchor clearing only after successful restore/consume
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
- consumed anchor after restore
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
