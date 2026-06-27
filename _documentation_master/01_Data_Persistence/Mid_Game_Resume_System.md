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

Current implementation details:

- `game.resume_anchor` is the durable source of truth for mid-game resume.
- Quarter-break anchors are created immediately when a non-final quarter completes.
- Quarter-break anchors are also created on the `/api/simulate-turn` early-return quarter-complete path so stale timeout/foul-out anchors do not survive a duplicate/preloaded `0:00` request.
- Timeout and foul-out anchors are created when their modal state is saved, before the user enters Set Lineup.
- Cold resume routes every supported anchor type through Set Lineup before gameplay.
- Set Lineup returns from cold resume must send both `resume_from_anchor=true` and `consume_resume_anchor=true`.

Primary files:

- Backend resume anchor save/load: `BackEnd/api/api.py`
- Backend Mode Select active-game lookup: `BackEnd/api/franchise_routes.py`
- Court resume modal and URL hydration: `FrontEnd/static/js/phaser/bootGame.js`
- Court resume request flagging: `FrontEnd/static/js/phaser/gameScene.js`
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

## Resume Anchor

Resume anchors are stored on the existing `games` document in a nested `resume_anchor` object.

The anchor is built in `BackEnd/api/api.py` by `_build_resume_anchor(...)`.

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


## Current SS&S Contract

The formal resume contract is:

1. One source of truth: game.resume_anchor is the only source for mid-game resume.
2. One lifecycle: create anchors at stable stoppages, route cold resume through Set Lineup, restore once, then consume.
3. One API: court and Mode Select both read resume eligibility/state from the same backend contract.
4. One frontend mode: if active resume exists, court boots into resume_pending, hydrates all UI from anchor, blocks sim until button press.
5. One backend behavior: resume_from_anchor=true restores once, simulates, then clears the anchor.
6. Tests for flows: browser refresh, browser close/return, timeout anchor, foul-out anchor, quarter-break anchor, Q1 to Q2 transition, and no stale-anchor reuse.
