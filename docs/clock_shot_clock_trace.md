# Shot Clock vs Game Clock — Trace and Root Cause

## Summary

**Root cause:** The backend attaches the **clock contract** (`clock_start`, `clock_end`, `shot_clock_start`, `shot_clock_end`) to every turn that goes through `update_clock_and_possession` or a direct `_attach_clock_contract` call. It does **not** consistently attach the **display/snap fields** (`clock`, `time_remaining`, `shot_clock_remaining`) to the turn dict. The frontend uses those display fields for the **end-of-turn snap** in `updateScoreboard`. So the shot clock often has nothing to snap to.

**Why game clock works more often:** `result["clock"]` and `result["shot_clock_remaining"]` are only set in one place: `run_micro_turn` (turn_manager.py lines 1105–1106). So only turns that go through that function get them. Many “normal” turns (e.g. HCO) go through `run_micro_turn`, so they get `clock` and the game clock snap works. The same line sets `shot_clock_remaining`, but any turn that **does not** go through `run_micro_turn` (e.g. some inbounds, opening tip from main, OREB from game_manager, or any path that builds a result and only calls `_attach_clock_contract`) never gets `shot_clock_remaining` (or `clock` / `time_remaining`) on the result. The API then returns `response_data.turn = latest_turn` without those keys; the frontend only ever sees `turn`, so when it calls `updateScoreboard(turn)`, `turn.shot_clock_remaining` is missing and the shot clock doesn’t snap.

---

## 1. Backend: Who sets the clock contract?

- **`_attach_clock_contract`** (turn_manager.py ~128–159) always sets on `result`:
  - `clock_start`, `clock_end`, `shot_clock_start`, `shot_clock_end`, `shot_clock_reset`, `real_time_elapsed_ms`
- It does **not** set: `clock`, `time_remaining`, `shot_clock_remaining`.

So every turn that gets the contract has start/end and duration for interpolation, but not the “current” values used for the final snap.

---

## 2. Backend: Who sets the display/snap fields?

- **`run_micro_turn`** (turn_manager.py ~1105–1106) is the only place that sets:
  - `result["clock"] = self.game.game_state["clock"]`
  - `result["shot_clock_remaining"] = self.game.game_state.get("shot_clock_remaining", 30)`
- So only turns that go through `run_micro_turn` get these. Any turn built elsewhere (e.g. opening tip, quarter start inbounds, OREB built in game_manager, or any path that only calls `_attach_clock_contract`) never gets `clock` or `shot_clock_remaining` on the turn dict.

---

## 3. Backend: Which turns go through which path?

- **Normal sim turns (HCO, etc.):** Handlers run inside the main turn loop; step 4 calls `update_clock_and_possession(result)`, which updates `game_state` and then calls `_attach_clock_contract(result, ...)`. So they get the contract. Whether they get `clock` / `shot_clock_remaining` depends on whether the handler that built `result` was `run_micro_turn` (which does set them) or something else (which often doesn’t).
- **OREB:** game_manager.py calls `update_clock_and_possession(oreb_turn)` for the OREB turn, so OREB gets the contract. The OREB result is built in game_manager/turn_manager; it does not go through `run_micro_turn`’s final block, so it does not get `clock` / `shot_clock_remaining`.
- **main.py / game_manager.py** (e.g. opening tip, quarter start inbounds): They build a turn dict and call `_attach_clock_contract` **directly**. So they get the contract but never get `clock` / `time_remaining` / `shot_clock_remaining` on the result.

So: **contract is widespread; display/snap fields are not.**

---

## 4. API response shape

- api.py (e.g. ~4298–4302) returns:
  - `response_data["turn"] = latest_turn`  (the turn dict)
  - `response_data["time_remaining"] = gm.game_state["time_remaining"]`
  - `response_data["shot_clock_remaining"] = gm.game_state.get("shot_clock_remaining", ...)`
  - `response_data["clock"] = gm.game_state.get("clock", "8:00")`
- So the **top-level** response has current clock and shot clock, but the **turn** object is `latest_turn` exactly as returned by the backend (with or without `clock` / `time_remaining` / `shot_clock_remaining`).

---

## 5. Frontend: How the turn is used

- **AnimationRouter** uses the **turn** for interpolation: `clock_start`, `clock_end`, `shot_clock_start`, `shot_clock_end`, `real_time_elapsed_ms`. So interpolation works whenever the contract is present (and we fixed the “shot clock only” and camelCase cases).
- **updateScoreboard** is called as `onUpdate(turn)` from `finalizeTurnAfterAnimation` (turnPreparation.js ~303). So it receives **only the turn object**, not the full API response.
- **updateScoreboard** (gameScene.js ~1452–1505):
  - **Game clock:** Uses `turn.time_remaining` (number) or `turn.clock` / `turn.game_clock` (parsed string). If the handler set `result["clock"]` (e.g. via `run_micro_turn`), the game clock snap works.
  - **Shot clock:** Uses only `turn.shot_clock_remaining`. If that key is missing, it only updates when `shouldResetShotClockOnTurn(turn)` is true (then sets 30). So for most turns without `shot_clock_remaining` on the turn, the shot clock never gets the correct end-of-turn snap.

So the **game clock** often works because many turns go through `run_micro_turn` and get `clock` (and possibly `time_remaining`). The **shot clock** fails whenever the turn dict doesn’t have `shot_clock_remaining`, which is the case for any turn that didn’t go through `run_micro_turn`’s final block.

---

## 6. Conclusion and recommended fix

- **Contract:** Attached consistently for every turn that goes through `update_clock_and_possession` or a direct `_attach_clock_contract` call. So start/end and interpolation are fine when the frontend uses the turn’s contract.
- **Snap:** Depends on `turn.clock`, `turn.time_remaining`, and `turn.shot_clock_remaining`. Those are only set in `run_micro_turn`, so many turns never get them and the shot clock (and sometimes game clock) doesn’t snap correctly.

**Recommended fix (backend):** In `_attach_clock_contract`, after setting the existing contract fields, set the display/snap fields from the same `game_state` that is already used for `clock_end` / `shot_clock_end`:

- `result["clock"] = game_state.get("clock")`
- `result["time_remaining"] = int(game_state.get("time_remaining", 0))`
- `result["shot_clock_remaining"] = int(game_state.get("shot_clock_remaining", 30))`

Then every turn that gets the clock contract (all paths: update_clock_and_possession, main.py, game_manager.py) also gets the values the frontend needs for the end-of-turn snap. No change to API shape or frontend needed for the snap; the frontend already reads these from the turn.

**Optional frontend hardening:** In `updateScoreboard`, if `turn.shot_clock_remaining` is missing, fall back to `turn.shot_clock_end` (same value semantically). Same idea for game clock: if `turn.time_remaining` and `turn.clock` are missing, use `turn.clock_end` (and optionally format as "M:SS") so the snap still works even if the backend is ever inconsistent.
