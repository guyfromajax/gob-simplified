# Court Persistence Plan

## Purpose

Clean up `court.html` refresh / close / re-entry behavior so an active game resumes from the latest stable stoppage anchor instead of an arbitrary mid-turn or mid-animation state.

Target user experience:

- If the user refreshes or closes/reopens `court.html` mid-game, they return to the latest stable stoppage anchor.
- The page should not show `Play Game` / `Sim Full Game` when the saved game is already active mid-quarter.
- If the user logs back in later and enters the same franchise, the app should route them back to the active game instead of letting them bypass it into the FCC.
- Resume anchors are saved after the user returns from the set-lineup screen at quarter breaks, timeouts, and player foul-outs.
- Quarter breaks and timeout/foul-out resumes keep their existing distinct behavior.

## Current Failure Mode

Observed behavior:

- Team scores and player stats can appear preserved after refresh.
- The game clock can reset to `8:00`.
- The pre-game / quarter-start button container appears.
- Pressing `Play Game` can trigger an opening-tip style flow while previous score/state remains.

Likely cause:

- `court.html` reloads from URL/default defaults.
- `bootGame.js` shows the pre-game button container unless `resume_from_timeout=true`.
- Pressing `Play Game` calls the quarter-start path through `/api/simulate-quarter`.
- `/api/simulate-quarter` is quarter-oriented, not a “resume latest live turn” endpoint.
- Turn-by-turn game state is persisted periodically, not after every completed turn, so DB state may lag the in-memory `ongoing_games` state.

## Scope

This plan intentionally targets **latest stable stoppage resume**, not mid-animation or arbitrary completed-turn resume.

Stable stoppage anchors:

- Quarter break after the user returns from set-lineup for the next quarter.
- Timeout after the user returns from set-lineup.
- Player foul-out after the user returns from set-lineup.

The anchor is captured after lineup return because that is the first point where lineups, strategy settings, possession, clock, score, and the next restart turn are all coherent.

Out of scope for this phase:

- Restoring the exact current animation frame.
- Restoring elapsed milliseconds within an animation step.
- Replaying pending SFX/announcement cursor state.

Those would require persisting frontend playback state and are a larger system.

## Option A: Active Game Resume Guard

### Goal

Prevent active mid-quarter games from dropping into the quarter-start UI.

### Backend

Add or extend an endpoint that returns a lightweight resume classification for a game:

`GET /api/game/{game_id}/resume-state`

Suggested response shape:

```json
{
  "game_id": "...",
  "status": "stoppage_anchor",
  "quarter": 2,
  "clock": "4:23",
  "time_remaining": 263,
  "shot_clock_remaining": 18,
  "offensive_state": "HCO",
  "next_play_type": "SIDE_INBOUND",
  "resume_from_timeout": false,
  "is_final": false,
  "has_cached_game": true,
  "source": "cache"
}
```

Status values:

- `pregame`: game exists but gameplay has not started.
- `active_mid_quarter`: game is in progress, but should resume from the latest saved stoppage anchor rather than the current arbitrary live state.
- `stoppage_anchor`: a saved lineup-return anchor exists and should be used for resume.
- `timeout_resume`: timeout/foul-out state exists; existing timeout resume flow should run.
- `quarter_break`: quarter completed; show quarter-start buttons.
- `final`: game completed; route to completion / box score behavior.
- `missing`: game not found or not owned by user.

Classification rules:

- Use `games` document plus `ongoing_games` cache when available.
- Prefer cache for live active state if cache exists.
- Use DB fallback when cache is missing.
- Treat `timeout_next_play_type` / `timeout_offense_team_id` / pending FT timeout fields as timeout resume state.
- Treat `time_remaining <= 0` and non-final as quarter break.
- Treat `quarter == 0` or no meaningful gameplay state as pregame.
- Treat `time_remaining > 0` and game not final as active mid-quarter only for live-state classification; user-facing resume should still resolve to the latest saved stoppage anchor.

### Frontend

On `court.html` load:

1. If URL has `game_id`, call `/api/game/{game_id}/resume-state` before revealing the pre-game button container.
2. If status is `stoppage_anchor` or an active game with an available anchor:
   - Hide `Play Game`, `Sim Full Game`, and other quarter-start controls.
   - Show a blocking `Game In Progress` resume modal.
   - Resume from the saved anchor and let the normal restart-turn path create the next BIP/SIP/FT/tip state.
   - Do not hydrate a random mid-possession snapshot.
3. If status is `timeout_resume`:
   - Preserve existing `resume_from_timeout=true` behavior.
4. If status is `quarter_break`:
   - Show the normal quarter-start button container.
5. If status is `pregame`:
   - Show normal start controls.
6. If status is `final`:
   - Route to final/completion behavior or box score.

### Franchise Entry Routing

When the user enters a franchise experience from Mode Select or any franchise entry CTA:

1. Check whether that franchise has an active incomplete user-played game.
2. If no active game exists:
   - Route normally to the FCC.
3. If an active incomplete game exists:
   - Route to `court.html?game_id=...`.
   - Do not route directly to the FCC.
4. If the game is completed or the franchise is between games:
   - Route normally to the FCC.

This preserves franchise state integrity: a live game must be resumed or completed before the user can continue normal franchise management.

Recommended post-login UX:

- Do not auto-drop the user directly into court immediately after login.
- Land them on the normal post-login surface, then show a prominent `Resume Game` card/button if an active game exists.
- If they choose to enter the franchise with an active game, route them to the court resume flow.

## Resume Modal

### Goal

When `court.html` detects an active incomplete game, present clear context before resuming.

### Trigger

Show the resume modal when `/api/game/{game_id}/resume-state` returns:

- `stoppage_anchor`
- or an active incomplete game that has a saved stoppage anchor.

Do not show the resume modal for:

- `pregame`
- `quarter_break`
- `final`
- existing `timeout_resume` flows that already route through lineup/timeout behavior.

### Content

Suggested copy:

- Title: `Game In Progress`
- Body: `{Away Team} vs {Home Team}, resume from the last stoppage`
- Score line: `{Away Team} {away_score} - {Home Team} {home_score}`
- Primary button: `Resume Game`

Optional secondary detail:

- Current possession / next play type if useful and already available from resume state.

No destructive or alternate action should be added in this phase. Abandon/forfeit is a separate feature and should not be bundled into persistence.

### Behavior

1. `court.html` starts in a neutral loading state.
2. Pre-game controls stay hidden while resume-state resolves.
3. If the game is active, render the resume modal.
4. Pressing `Resume Game` hydrates the court from the saved stoppage anchor and continues from the restart turn.
5. If the user refreshes again before pressing `Resume Game`, the same modal can appear again.

### Visual Design

Use the existing gameplay modal language from `court.html`, especially the quarter-start functional modal:

- full-court dark backdrop
- compact centered modal box
- dark translucent surface
- subtle light border
- rounded corners
- top orange accent bar
- `Bebas Neue` title treatment
- muted `Inter` body copy
- existing primary button style

Implementation should reuse or extend the existing `.pre-game-container`, `.pre-game-backdrop`, `.pre-game-modal-box`, `.pre-game-modal-accent`, `.pre-game-modal-title`, `.pre-game-modal-subtitle`, and `.pre-game-modal-actions` patterns where practical.

Do not invent a new modal design system. This is a gameplay modal and should visually match other mid-game court overlays.

## Option B-Lite: Stoppage Anchor Persistence

### Goal

Make DB fallback good enough that a refresh can resume from the latest lineup-return stoppage anchor, even if the server cache is gone.

### Backend

Current turn-by-turn save behavior:

- `/api/simulate-turn` persists periodically, currently every 25 turns or at quarter completion, plus special timeout/foul-out paths.

Proposed change:

- Do not use arbitrary per-turn checkpoints as the user-facing resume target.
- Persist a dedicated `resume_anchor` after lineup return for quarter breaks, timeouts, and player foul-outs.
- The anchor should be based on `summarize_game_state(gm, exclude_animations=True)` so the DB record remains compact.
- The anchor should preserve the restart context needed to recreate the next turn: quarter-start BIP/tip, timeout SIP/BIP, or FT.
- Existing timeout/foul-out save state remains useful, but the user-facing resume target should be the post-lineup-return anchor.

Potential implementation choices:

1. **Anchor field on game doc:** add `resume_anchor` as a nested snapshot inside the existing game document.
2. **Anchor metadata only:** mark the existing game document as a resume anchor when the save happens after lineup return.
3. **Separate collection:** store anchors in a small `game_resume_anchors` collection keyed by `game_id`.

Recommended first implementation:

- Use an anchor field on the existing game document.
- Save/update it only after lineup return.
- Have `/api/game/{game_id}/resume-state` classify active games from this anchor rather than from arbitrary latest game state.

### Checkpoint Contents

Anchor snapshot must preserve:

- `quarter`
- `clock`
- `time_remaining`
- `shot_clock_remaining`
- `score`
- `offensive_state`
- current offense / defense team identity
- `next_play_type` / timeout state / free throw state
- player game stats
- player `NG`, `EM`, `MO`, foul count
- player coords
- team fouls
- timeouts
- lineups
- playbook and strategy settings in the game document
- timeout/foul-out next-play state when applicable
- quarter-start possession state when applicable

`summarize_game_state()` already captures much of this, but implementation should audit the fields above before relying on it for refresh resume.

## Resume Flow

Preferred runtime flow after this work:

1. User refreshes `court.html?game_id=...`.
2. Frontend shows load overlay immediately.
3. Frontend calls `/api/game/{game_id}/resume-state`.
4. Backend classifies game status from cache or DB.
5. If active mid-quarter and a stoppage anchor exists:
   - Frontend shows the `Game In Progress` resume modal.
   - On `Resume Game`, frontend resumes from the saved anchor.
   - Frontend calls the existing quarter/timeout restart path with anchor-backed parameters instead of arbitrary live-state hydration.
6. If active mid-quarter and no stoppage anchor exists:
   - Treat as a pre-anchor game and fall back to the safest existing behavior.
   - This should be rare after the feature is deployed because the first anchor is created after the first lineup return.

## Implementation Status

Current implementation adds:

- `GET /api/game/{game_id}/resume-state` for lightweight active-game classification.
- `resume_anchor` metadata on the game document, written after `/api/simulate-quarter` runs from a lineup-return entry.
- Quarter-complete DB saves in `/api/simulate-turn`; arbitrary per-turn saves are not used as the resume target.
- FCC command-center payload field `active_game_resume` for the user's current scheduled active game.
- Mode Select resume card inside the existing active franchise card.
- Mode Select active-game routing to `court.html` instead of direct FCC entry.
- Court resume modal using the existing pre-game modal visual language.
- Direct `court.html` refresh detection for active games with `game_id`.
- `GameScene` resumes through the normal `/api/simulate-quarter` restart path; it does not hydrate arbitrary DB snapshots directly.

Current limitation:

- The first usable anchor is created only after the first lineup-return `/api/simulate-quarter` call.
- If a game predates this feature and has no `resume_anchor`, the system cannot create a clean stoppage resume point retroactively.

Next implementation step:

- Prototype-test the three anchor cases:
  - quarter break return
  - timeout return
  - player foul-out return
- Confirm refresh and next-day re-entry both land on the last stoppage and generate the correct restart turn.

## Open Design Questions

1. Should active mid-quarter refresh auto-run the next turn immediately, or show a “Resume Game” button?
   - Decision: show a `Game In Progress` modal with a `Resume Game` button. This confirms context and avoids surprising the user after refresh or later re-entry.

2. Should we use DB or cache as source of truth when both exist?
   - Recommendation: cache first for live state, DB fallback. After each turn save, cache and DB should match closely.

3. Should every turn be persisted?
   - Recommendation: yes for this phase, for user-played games. Reassess if DB write latency becomes visible.

4. Should exact mid-animation resume be supported later?
   - Recommendation: no for now. Latest completed turn/checkpoint is the pragmatic product line.

## Testing Plan

Manual tests:

1. Start a new Q1 game, play past opening tip, refresh.
   - Expected: no Play/Sim buttons; restore overlay appears; next turn resumes from current state.

2. Refresh after score changes.
   - Expected: score, clock, quarter, fouls, player stats, and possession state match latest checkpoint.

3. Refresh during a timeout/foul-out lineup flow.
   - Expected: existing timeout resume behavior remains intact.

4. Refresh at quarter break.
   - Expected: quarter-start controls appear, not auto-resume.

5. Refresh after final game.
   - Expected: final/completion behavior, not active resume.

6. Kill backend cache if feasible, then refresh with only DB state.
   - Expected: resume from latest persisted checkpoint, not opening tip.

7. Close browser during active game, reopen later, log in, and enter the same franchise.
   - Expected: franchise entry routes to `court.html?game_id=...`, not FCC.

8. Land on `court.html` with an active incomplete game.
   - Expected: `Game In Progress` modal appears; `Play Quarter` / `Sim Full Game` buttons remain hidden.

9. Click `Resume Game`.
   - Expected: modal closes, court hydrates from checkpoint, and gameplay resumes from the latest completed backend state.

Automated tests:

- Unit-test backend resume classification.
- Integration-test `/api/game/{game_id}/resume-state` for:
  - pregame
  - active mid-quarter
  - timeout resume
  - quarter break
  - final
- Frontend test for pre-game container visibility based on resume-state status.

## Rollout Plan

1. Implement backend resume-state endpoint.
2. Add frontend load guard that hides controls until resume-state resolves.
3. Add active-mid-quarter resume path.
4. Increase checkpoint save frequency for user-played turn-by-turn games.
5. Test refresh/close/reopen across active play, timeout, quarter break, and final.
6. Update data persistence documentation after behavior is verified.
