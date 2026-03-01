# Fast Break Miss: current_turn Mislabeled Bug

**Status:** Documented; verification via existing debug logs; fix not yet implemented.

**Related:** Turn_by_Turn_System, Fast_Break_System, Shot_System, Rebound_System. Debug logs: `🔍 [FB MISS]` in `phase_resolution.py` and `game_manager.py`.

---

## Summary

On a **Fast Break shot miss** (DREB or OREB), the turn we just ran is a **FAST_BREAK** turn, but the backend sends `current_turn = "HCO"` (or whatever the handler set as the *next* state) instead of `"FAST_BREAK"`. That can cause the frontend to mis-handle progression (e.g. DREB → HCO flow) or possession, and matches the “confusion on progressing to the next turn and/or flipping possession” seen on some FB misses.

---

## Expected Behavior (per docs)

- **current_turn** = the turn type we **just ran** (e.g. `"FAST_BREAK"` for a Fast Break shot attempt).
- **next_turn** = the turn type to run **next** (e.g. `"HCO"` after FB miss DREB, or `"OREB"` after FB miss OREB).
- On FB miss DREB: possession flips; frontend uses current (FB) turn for `runDefensiveReboundSetup()` and may key off `current_turn` to know it was a Fast Break miss.

---

## Root Cause

**File:** `BackEnd/models/turn_manager.py` — `run_micro_turn()`.

1. Near the **start** of the turn we set `state = self.game.game_state.get("offensive_state", "HCO")` (e.g. `"FAST_BREAK"`) and use it to **route** to the correct handler (e.g. `resolve_fast_break_logic()`).
2. The handler runs. For a FB **miss + DREB**, the shot handler sets `game_state["offensive_state"] = "HCO"` for the *next* turn.
3. When adding Bucket 1 (standard fields), we **re-read** state:
   - `state = self.game.game_state.get("offensive_state", "HCO")`  ← now `"HCO"`
   - `result["current_turn"] = state`
4. So we set **`result["current_turn"] = "HCO"`** even though the turn we **ran** was **FAST_BREAK**.

So `current_turn` is being set from the *next* offensive state (post-handler) instead of the state we used for routing (the turn we actually ran).

---

## Effect

- The emitted turn has `current_turn = "HCO"` for a turn that was actually a Fast Break (shot + miss).
- Any logic that uses `current_turn` to detect “this was a Fast Break miss” (e.g. frontend DREB→HCO flow, animations, or analytics) can mis-classify the turn and cause wrong progression or possession handling.

---

## Verification (before implementing fix)

Use the existing debug logs to confirm the hypothesis on a real FB miss:

- **phase_resolution:** `🔍 [FB MISS] phase_resolution: result_type=MISS outcome=... next_play_type=... possession_flips=...`
- **game_manager:** `🔍 [FB MISS] game_manager: outcome=... next_turn=... possession_flips=... (before flip logic)` and, when applicable, `🔍 [FB MISS] game_manager: processing DREB→HCO flip ...`

Then inspect the **serialized turn** sent to the frontend for that same turn: check whether `current_turn` is `"HCO"` instead of `"FAST_BREAK"`. If so, that confirms the bug.

---

## Proposed Fix (to implement after verification)

In `turn_manager.run_micro_turn()`:

- **Preserve** the routing state at the start of the turn (the `state` used to decide which handler to call — e.g. keep it in a variable like `routing_state` or `current_turn_type`).
- When adding Bucket 1 and setting `result["current_turn"]`, use that **preserved start-of-turn state**, not a fresh read of `game_state["offensive_state"]` after the handler.

That way, for a Fast Break turn we always set `result["current_turn"] = "FAST_BREAK"` regardless of the handler having set `offensive_state` to `"HCO"` (or anything else) for the next turn.

---

## References

- `docs/docs_1_systems/05_GP_Supporting_Systems/Turn_by_Turn_System.md`
- `docs/docs_1_systems/05_GP_Supporting_Systems/Fast_Break_System.md` (e.g. “Fast Break MISS → DREB Transition”)
- `BackEnd/models/turn_manager.py` — `run_micro_turn()` (routing ~464, Bucket 1 / current_turn ~759–762)
- `BackEnd/models/game_manager.py` — DREB→HCO / DREB→FB flip logic and `🔍 [FB MISS]` logs
