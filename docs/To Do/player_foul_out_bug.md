# Player foul-out bug (persistent)

## Summary

In **some (not all)** instances when a player fouls out, the standard foul-out flow does **not** run:

- **No** foul-out popup is shown.
- The user is **not** taken to the lineup screen.
- The fouled-out player’s **sprite appears “dead”** on screen and does not animate.

So the game can end up in a state where the UI never enters the normal “player fouled out” progression (popup → lineup screen), even though a player has fouled out.

## Previous hypothesis

It was previously assumed this was a **frontend-only** issue: the backend still simulates as if both teams have a legal lineup, and the problem was thought to be purely animation/UI (e.g. not handling a foul-out event correctly in the frontend).

**Current uncertainty:** It’s not clear that the cause is only on the frontend; the bug has proven persistent and may involve backend event ordering, event type, or a missing/duplicate foul-out signal.

## What we need to achieve

When a player fouls out:

1. The foul-out popup is shown.
2. The user is taken to the lineup screen to replace the fouled-out player.
3. The fouled-out player’s sprite does not remain “dead” or stuck on screen.

## Notes for future debugging

- Bug is **intermittent** (some instances, not all).
- Document any fix attempts and findings in this file so we don’t re-explain from scratch each time.
- Check both:
  - **Backend:** When/how foul-out is detected, what event(s) are emitted, and whether a timeout/foul-out flow is always triggered so the frontend receives a clear signal.
  - **Frontend:** How foul-out (and related timeout) events are handled, and whether the animation/UI path for foul-out is ever skipped or overridden.

---

## End-to-end trace (foul-out path)

### Backend

1. **Foul-out detection**  
   Several places call `check_and_handle_foul_out()` (phase_resolution): shot_manager (block/recon foul, blocking foul, regular foul, shooting foul, blocking from `_blocking_foul_out_info`), and game_manager’s end-of-turn check.

2. **Result shape when someone fouls out**  
   The **foul turn** gets `fouled_out: true`, `foul_out_player: { player_id, name, photo, team }`, and often `foul_out_context` in `game_state`.  
   `_append_turn(turn_result)` is the single funnel: it appends the turn, then calls `_check_lineups_for_foul_out(turn_result)` (which can add `fouled_out` / `foul_out_player` if the turn didn’t have it), then if `turn_result.get("fouled_out")` it calls `_handle_foul_out_timeout(turn_result)`.

3. **Foul-out timeout turn**  
   `_handle_foul_out_timeout`:
   - Reads `foul_out_player` from the result (dict with `player_id`, etc.).
   - Resolves the **Player** instance by `player_id` from `team.get_all_players()` or `team.lineup`; if not found, `foul_out_player` (the object passed to timeout) stays **None**.
   - Calls `call_timeout(timeout_reason="FOUL_OUT", foul_out_player=..., foul_out_context=...)`, which calls `turn_manager.setup_timeout_turn(...)`.
   - `setup_timeout_turn` only adds `payload["foul_out_player"]` when `foul_out_player` is truthy. So if the lookup fails, the **timeout turn is still created and appended** but has **no `foul_out_player`** in the payload.

4. **What the client gets**  
   One `simulate_macro_turn()` can append two turns: the foul turn and the timeout turn. The API returns `new_turns = gm.turns[turns_before:]`. If there are 2+ turns, the response is a single object: `result_type: "BATCH", batch_turns: [foul_turn, timeout_turn]`. So the frontend always receives both in one response when both exist.

### Frontend

1. **Two ways foul-out UI can trigger**
   - **gameScene** `updateScoreboard` (used as `onUpdate`): for each turn it receives, it checks `(turn.result_type === 'TIMEOUT' && turn.timeout_reason === 'FOUL_OUT' && turn.foul_out_player)` or `(turn.fouled_out && turn.foul_out_player)`. If true and no popup already, it shows the foul-out popup.
   - **AnimationEngine** `handleTimeout`: when the animated turn has `result_type === 'TIMEOUT'`, it runs `handleTimeout`. If `timeout_reason === 'FOUL_OUT' && turnData.foul_out_player`, it shows the foul-out popup and returns; otherwise it falls through to the “computer timeout” path (navigate to lineup with “Team calls timeout” style).

2. **BATCH handling**  
   For a BATCH, the frontend loops over `batch_turns` and calls `animateGameTurns` with `turns: [subTurn]` for each. So it animates the foul sub-turn, then the timeout sub-turn. After each sub-turn, `finalizeTurnAfterAnimation` runs and calls `onUpdate(subTurn)` (so updateScoreboard runs with that sub-turn). The TIMEOUT sub-turn is routed to `handleTimeout`. So in the “happy” path, either the timeout sub-turn’s `onUpdate` or `handleTimeout` should show the popup and lead to lineup.

3. **Critical frontend condition**  
   In AnimationEngine: `if (turnData.timeout_reason === 'FOUL_OUT' && turnData.foul_out_player)`. If the timeout turn has **no `foul_out_player`** (e.g. backend lookup failed), this branch is skipped and the code falls through to the **computer timeout** path (navigate + “Team calls timeout”). So: no foul-out popup, but navigation might still happen unless that path also fails in this scenario.

---

## Working vs broken: hypotheses

These are candidate causes for “no popup, no lineup, dead sprite” (to confirm with logs or a reproducible case):

1. **Backend: timeout turn has no `foul_out_player`**  
   In `_handle_foul_out_timeout`, the fouled-out player is looked up by `player_id` from the result dict. If the ID is missing, wrong type, or not in `get_all_players()` / lineup, `foul_out_player` stays None and the timeout payload is sent without `foul_out_player`. Frontend then skips the foul-out popup and uses the computer-timeout path. If that path also doesn’t navigate (e.g. missing `game_id` or other state), user gets no popup and no lineup. **Check:** When the bug happens, does the TIMEOUT turn in the response include `foul_out_player`?

2. **Frontend: first sub-turn (foul) never finishes**  
   If the foul sub-turn’s animation throws, hangs, or never completes, the loop may never process the second sub-turn (timeout). Then `handleTimeout` never runs and `onUpdate` may never be called with the timeout turn. Result: no popup, no lineup, and the fouled-out player’s sprite can stay in whatever state the foul animation left it in (“dead” or stuck). **Check:** When the bug happens, does the console show the “Timeout subTurn detected inside BATCH” log? If not, the timeout sub-turn may not be reached.

3. **Frontend: TIMEOUT not routed for the timeout sub-turn**  
   If the timeout sub-turn is not passed to the animation router as `result_type: 'TIMEOUT'` (e.g. BATCH flattened differently or second item missing), the TIMEOUT handler would not run. **Check:** When the bug happens, does the router receive a turn with `result_type === 'TIMEOUT'` for the second item in the batch?

4. **Ordering / duplicate handling**  
   If the foul turn is sometimes processed in a way that triggers navigation or a different flow before the timeout turn is processed, or if the popup is suppressed by a duplicate check (e.g. “popup already exists”) in a case where the first trigger was wrong or empty, the intended foul-out flow could be skipped. **Check:** In the failing case, is `updateScoreboard` called with the timeout sub-turn, and does that call see `turn.foul_out_player`?

**Suggested next step:** Reproduce the bug (or capture it when it happens) and verify: (a) backend response for that request: does the BATCH contain two turns and does the second have `result_type: "TIMEOUT"`, `timeout_reason: "FOUL_OUT"`, and `foul_out_player`? (b) frontend: for that batch, is the second sub-turn animated and does the TIMEOUT handler run? (c) if the timeout turn has no `foul_out_player`, add backend logging in `_handle_foul_out_timeout` when the player lookup fails so we can confirm that path.

---

## Fix attempts / findings

*(Add dated notes here as we try fixes.)*

- **2025-02-02:** Added end-to-end trace (backend + frontend) and “Working vs broken” hypotheses. No code change yet; next step is to confirm which hypothesis matches the failing case (logs or repro).
