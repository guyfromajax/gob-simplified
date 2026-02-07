# Foul-out fix: FCP/HCT not triggering popup and processing

## Bug

When a player reaches their fifth foul during an **FCP or HCT** foul (pressure defense), the expected behavior does not occur:

- The **player foul-out popup** is not shown.
- The foul-out **timeout/sub flow** is not run.
- The fouled-out player’s **sprite stays on the court** (no further animation) while the other nine players continue to animate for multiple turns.

## Root cause

**Backend state is correct.**  
`check_and_handle_foul_out()` is called in all foul paths (HCO, FCP, HCT, shooting fouls). It correctly:

- Adds the player to `game_state["ineligible_players"]`
- Removes them from `foul_team.lineup` and replaces via `_ensure_complete_lineup`

**FCP and HCT do not surface foul-out on the turn result.**  
In `phase_resolution.py`, the FCP and HCT foul branches:

- Call `check_and_handle_foul_out(foul_player, game_state, def_team)` (or `off_team` for O_FOUL) but **discard the return value** (no `foul_out_info = ...`).
- Build a `result` dict that **never includes** `fouled_out`, `foul_out_player`, or `foul_count`.

So:

1. **game_manager** (around 383–384) only creates the foul-out timeout turn when `result.get("fouled_out")` is truthy. For FCP/HCT fouls it never is, so no timeout turn is created.
2. The **frontend** only shows the foul-out popup when it receives a turn with `turn.fouled_out && turn.foul_out_player` (gameScene.js) and only gets the timeout/sub flow when the backend sends that timeout turn.
3. The client never gets the foul-out signal or the timeout, so the popup never runs and the fouled-out player’s sprite is never removed/refreshed → it appears as a “dead” stationary sprite.

## Where to fix

**FCP** (`phase_resolution.py`):

- ~4825 (D_FOUL): capture `foul_out_info = check_and_handle_foul_out(...)`.
- ~4860 (O_FOUL): same.
- When building the FCP `result` (~4995–5018): add `fouled_out`, `foul_count`, and (when `fouled_out`) `foul_out_player` from `foul_out_info`, and set `game_state["foul_out_context"]` when applicable (same pattern as `resolve_non_shooting_foul`).

**HCT** (`phase_resolution.py`):

- ~5952 (D_FOUL): capture `foul_out_info = check_and_handle_foul_out(...)`.
- ~5986 (O_FOUL): same.
- When building the HCT `result` (~6113–6134): add the same foul-out fields and context as above.

**Reference implementation:**  
`resolve_non_shooting_foul()` in the same file (~345–437): it captures `foul_out_info`, attaches it to the result, and sets `game_state["foul_out_context"]` when the player fouled out. FCP/HCT should mirror that for their returned `result` and context.

## Files

- `BackEnd/engine/phase_resolution.py` — FCP/HCT foul handling and result construction.
- `BackEnd/models/game_manager.py` — uses `result.get("fouled_out")` to create timeout turn (~383–384).
- `FrontEnd/static/js/phaser/gameScene.js` — shows popup when `turn.fouled_out && turn.foul_out_player` (~1272–1289).
