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

- **2025-02-02 (solution summary):** Offensive-foul possession fix in `call_timeout()` (timeout_offense_team_id = defense_team when foul_type == OFFENSIVE). FREE_THROW resume: persist/restore shooter + FT state for 5th-foul-on-shooting-foul (miss and AND-1). Full solution summary and edge-case notes added to this doc; Timeout_System.md and timeout_data_&_state_persistence.md updated with cross-references.
- **2025-02 (later):** Defensive fix: timeout turn gets `foul_out_player` from result when Player lookup fails (game_manager). Frontend: FOUL_OUT branch in handleTimeout always runs when `timeout_reason === 'FOUL_OUT'`; warn when `foul_out_player` missing and return. Backend: ObjectId fallback for foul-out save; logs upgraded to WARNING. Persistence: doc often has no `timeout_next_play_type` on return; foul-out save may not run or match. FOUL_OUT_TEST_MODE env var added for testing.

- **2025-02-02:** Added end-to-end trace (backend + frontend) and “Working vs broken” hypotheses. No code change yet; next step is to confirm which hypothesis matches the failing case (logs or repro).

- **2025-02-02 (data loss on return to court):** Confirmed from logs: foul-out save to DB was correct (Q4, scores 72–90, `timeout_next_play_type=SIP`). On "return to court" the frontend sent **quarter=1** in the simulate_quarter request instead of 4. Backend saw `body.quarter=1` vs `saved_quarter=4` → treated as quarter mismatch → cleared timeout state and did **not** treat as timeout resume → `should_restore_stats` False (new Q1) → score/stats not restored. **Backend safeguard (surgical fix):** In `restore_timeout_resume_state` (api.py), when `timeout_next_play_type` exists and **saved_quarter > body.quarter** (e.g. requested 1, saved 4), treat as "frontend sent wrong quarter on return to court" → set `body.quarter = saved_quarter`, `body.resume_from_timeout = True`, force DB reload; do **not** clear timeout state. Existing behavior unchanged when `saved_quarter == body.quarter` or `saved_quarter < body.quarter`.

- **2025-02-02 (quarter carry-over – to address later):** **Rule:** Quarter should never end with a carry-over; every new quarter must start clean. **Current bug:** If the final play of a quarter results in free throws (e.g. shooting foul at buzzer), we can persist `timeout_next_play_type=FREE_THROW` and 0:00 for the *next* quarter, so the next quarter does not start clean. **Intended behavior:** Run the free-throw turn(s) from that final play as part of finishing the quarter, then enter the quarter-break scenario and save a clean state (no pending FTs for next quarter). **Symptom patch in place:** We only restore timeout state when client sends `resume_from_timeout=true`, so "Play Quarter" after "Sim quarter" no longer restores that bad state and causes instant EOG. The underlying fix is to never persist a carry-over: resolve FTs before marking the quarter complete.

---

## System review: step back and fix coherently

The foul-out flow has broken in **multiple ways** and piecemeal fixes have been unstable. Recommended approach: **treat foul-out as one system**, define a clear contract, then fix backend and frontend to that contract in order.

### Known failure modes (observed)

| Symptom | Likely cause |
|--------|---------------|
| No foul-out popup | Backend sends TIMEOUT turn without `foul_out_player`, or frontend never receives/processes timeout sub-turn (BATCH order, animation hang). |
| User not taken to lineup | Same as above; or navigation runs but with wrong/missing params; or popup shows but button doesn't navigate. |
| Dead / stuck sprite | Foul turn applies red tint (negativeActionEffects); if foul-out flow never runs, tint or animation state is never cleared; or sprite left in "fouled" pose when next turn never runs. |
| Persistence reset (score, clock, stats, NG) | Foul-out save to DB never runs (e.g. `game_id` missing, update matched 0), or runs but doc is overwritten later; on return, `restore_timeout_resume_state` finds no `timeout_next_play_type` and treats as quarter start. **Or:** frontend sends wrong quarter (e.g. `quarter=1`) on "return to court" while game is in Q4 → backend treats as new Q1 and does not restore → scores/stats zeroed (see below). |

### Touchpoints (single checklist)

**Backend:** Detection (phase_resolution, shot_manager, game_manager) → result has `fouled_out` + `foul_out_player`. Funnel: `_append_turn` → `_check_lineups_for_foul_out` → `_handle_foul_out_timeout`. Timeout turn: `call_timeout(FOUL_OUT)` → `setup_timeout_turn`; payload must include `foul_out_player` (from Player or result dict). game_state: `timeout_next_play_type`, `timeout_offense_team_id` set then saved via `summarize_game_state` + `update_one`; save must match game doc. API returns BATCH with `[foul_turn, timeout_turn]`; timeout turn must have `result_type: "TIMEOUT"`, `timeout_reason: "FOUL_OUT"`, `foul_out_player`.

**Frontend:** BATCH handling: animateGameTurns loops over `batch_turns`; each sub-turn animated then `onUpdate` and router (handleTimeout for TIMEOUT). If foul animation hangs, timeout sub-turn may never run. Popup: updateScoreboard and handleTimeout both require `foul_out_player` for foul-out popup; if missing, handleTimeout falls through to computer timeout. Navigation: foulOutPopup builds URL via TimeoutNavigationHelper. Sprite: negativeActionEffects applies red tint on foul; if foul-out flow never completes, no clear-tint step → sprite can look "dead".

### Proposed contract

1. **Backend:** Every foul-out returns BATCH of two turns; second turn is TIMEOUT with `timeout_reason: "FOUL_OUT"` and **always** has `foul_out_player` (from result dict if Player lookup fails). Backend **always** persists timeout state in the same request and uses _id that matches on read.
2. **Frontend:** For BATCH whose second turn is TIMEOUT with `timeout_reason === 'FOUL_OUT'`, **always** show foul-out popup (use placeholder if `foul_out_player` missing) and navigate; never fall through to computer timeout. Ensure timeout sub-turn is always processed (don't swallow if foul sub-turn fails).
3. **Persistence:** One save path for foul-out (same _id format as load); one load path on return to court.
4. **Sprite:** When foul-out popup is shown, clear fouled-out player's tint / set consistent "out" state so sprite doesn't stay "dead".

### Recommended fix order

1. **Backend:** Ensure `_handle_foul_out_timeout` always attaches `foul_out_player` to timeout turn; ensure save always runs and matches game doc; optionally unify with user/computer timeout save path.
2. **Frontend:** In handleTimeout, if `timeout_reason === 'FOUL_OUT'` always show popup (placeholder if no player) and navigate; never fall through to computer timeout. Ensure BATCH always processes timeout sub-turn even if foul sub-turn errors.
3. **Persistence:** Single save/load path; defensive _id retry and logging.
4. **Sprite:** On foul-out popup (or when applying foul-out from turn), clear red tint for fouled-out player's sprite.

---

## Solution summary (2025-02)

**What was fixed (concise):**

| Scenario | Fix |
|----------|-----|
| **5th foul on shooting foul (miss or AND-1)** | Backend sets `foul_out_context` with `next_play_type="FREE_THROW"` and `shooter`; persist `timeout_free_throws_remaining`, `timeout_shooter_id`, etc. in `summarize_game_state`; restore in `apply_timeout_resume_state_to_gm` so first `simulate_turn` runs `resolve_free_throw()`. |
| **5th foul on offensive foul (charge or HCO o-foul)** | `timeout_offense_team_id` was saved *before* the possession flip, so the fouling team was restored as offense. Fix: in `call_timeout()`, when `timeout_reason == "FOUL_OUT"` and `foul_out_context.foul_type == "OFFENSIVE"`, set `timeout_offense_team_id = self.defense_team.team_id` (the team that receives the ball). |

**Code locations:**
- **Offensive-foul possession:** `BackEnd/models/game_manager.py` → `call_timeout()` (branch before DREB⇒HCO check).
- **FREE_THROW resume persist:** `BackEnd/utils/shared.py` → `summarize_game_state()` (when `timeout_next_play_type == "FREE_THROW"`).
- **FREE_THROW resume restore:** `BackEnd/api/api.py` → `apply_timeout_resume_state_to_gm()` (restore `offensive_state`, `shooter`, `free_throws_remaining` from saved doc).
- **Shooting-foul foul-out (miss + d_foul):** `BackEnd/models/shot_manager.py` (miss + d_foul block sets `foul_out_context` and result `fouled_out` like AND-1).

**Edge cases / what to watch:**
- **Offensive foul:** Only `foul_type == "OFFENSIVE"` in `foul_out_context` triggers the possession fix; charge and HCO o-foul both set that.
- **FREE_THROW resume:** Shooter is resolved by `timeout_shooter_id` from both teams’ rosters; if lineup was rebuilt and shooter is no longer in roster, log warns and FT turn could fail.
- **Blocking foul on made shot + 5th foul:** Path may set `foul_out_context` in a different place; confirm if ever used and that `foul_type` / `next_play_type` are correct.
- **Persistence:** Foul-out save uses same `game_id` as load; ObjectId retry exists for string vs ObjectId mismatch. If save matches 0 docs, timeout state is not persisted and return-to-court can reset.

**Cross-references:** Timeout flow → `docs/docs_1_systems/05_GP_Supporting_Systems/Timeout_System.md`. Persistence → `docs/docs_1_systems/03_Data_Persistence/timeout_data_&_state_persistence.md`.
