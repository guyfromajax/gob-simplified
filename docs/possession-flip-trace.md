# Possession flip trace: Offensive Foul, Charge, Dead Ball

This document traces **when** we flip possession and when we treat the defense as the new offense for the three result types that lead to a side inbound (SIP): **Offensive foul (not charge)**, **Charge**, and **Dead ball turnover**.

## Summary

**All three are handled the same way in the backend:** possession is flipped **after** the result turn is appended and **before** the SIDE_INBOUND turn is created. The **result** turn always keeps `offense_team_id` = team that had the ball (old offense). The **new offense** appears only on the next turn (SIDE_INBOUND). The frontend is designed to set `scene.offenseTeamId` from each turn’s `offense_team_id` at **turn start** (prepareTurnForAnimation), so the “defense becomes new offense” moment is when the **SIP turn** starts, not during the Dead Ball / FOUL / CHARGE turn.

---

## 1. Where each result type is produced

| Result type | Where produced | possession_flips | offense_team_id on result |
|------------|----------------|-------------------|---------------------------|
| **Offensive foul (FOUL, no FT)** | `BackEnd/engine/phase_resolution.py` → `resolve_non_shooting_foul()` | `True` when `foul_team == off_team` (line 383) | `game.offense_team.team_id` (line 403) |
| **Charge** | `BackEnd/models/shot_manager.py` (attack shot charge check) | `True` (line 608) | `off_team.team_id` (line 614) |
| **Dead ball** | `BackEnd/engine/phase_resolution.py` → `resolve_turnover_logic(..., turnover_type="DEAD BALL")` | `True` (line 1745) | `game.offense_team.team_id` (line 1744) |

In all three cases the result is built with:

- `offense_team_id` = team that had the ball (old offense)
- `possession_flips` = `True`

No possession flip happens inside these producers; they only set the flag.

---

## 2. Backend: when we flip and when we “declare” new offense

**File:** `BackEnd/models/game_manager.py` → `simulate_macro_turn()`

### Order of operations

1. **Result is created**  
   `result = self.turn_manager.run_micro_turn()` (or equivalent path that returns FOUL / CHARGE / DEAD BALL).  
   At this point `result["offense_team_id"]` = current `game.offense_team.team_id` (old offense), and `result["possession_flips"]` = `True`.

2. **Result is appended**  
   `result["next_turn"] = self.determine_next_turn(result)` then `self._append_turn(result)`.  
   So the **result turn** is in `gm.turns` with `offense_team_id` = old offense. We do **not** update `result["offense_team_id"]` after this.

3. **DREB → HCO / Fast Break**  
   Blocks at ~585 and ~596 only run when `next_play_type` is `HCO` or `FAST_BREAK`. For FOUL/CHARGE/DEAD BALL, `determine_next_turn` yields `SIDE_INBOUND`, so these blocks are **skipped**.

4. **SIP block (lines 608–694)**  
   Condition:

   ```python
   if (
       (result.get("result_type") == "FOUL" and self.game_state.get("free_throws_remaining", 0) == 0)
       or result.get("result_type") == "DEAD BALL"
       or result.get("result_type") == "CHARGE"
   ):
   ```

   - If `result.get("possession_flips")`:
     - `self.switch_possession()` → `offense_team` and `defense_team` are swapped; `game_state["offense_team"]` is updated.
     - `result["possession_flips"] = False` (so frontend doesn’t double-flip).
   - We do **not** set `result["offense_team_id"] = self.offense_team.team_id` here (unlike the DREB→HCO block, which does update `result["offense_team_id"]` after the flip).
   - `inbound_payload = self.turn_manager.setup_side_inbound()` → uses **current** `self.offense_team` (now the new offense), so the SIP turn gets `offense_team_id` = new offense.
   - `self._append_turn(inbound_payload)` → SIP turn is appended.

So:

- **When we flip:** In the same macro turn, **after** appending the result turn and **before** creating the SIDE_INBOUND turn (inside the SIP block).
- **When we “declare” defense as new offense:**  
  - In **game state**: at the moment we call `switch_possession()` (defense becomes `gm.offense_team`).  
  - In **turn data**: the **result** turn is never updated; it keeps `offense_team_id` = old offense. The **SIDE_INBOUND** turn carries `offense_team_id` = new offense.

So for **all three** (offensive foul, charge, dead ball):

- Flip and “new offense” in game state happen in the **same** place and at the **same** time relative to the result turn (after result append, before SIP create/append).
- The “defense is the new offense” is visible to the frontend **only** on the **next** turn (SIDE_INBOUND), not on the result turn.

---

## 3. Frontend: when we set “offense” from turn data

**Files:**  
`FrontEnd/static/js/phaser/animation/turnPreparation.js`  
`FrontEnd/static/js/phaser/utils/offenseTeamIdResolver.js`  
`FrontEnd/static/js/phaser/gameScene.js`

- **Before each turn animates:** `prepareTurnForAnimation()` sets `scene.offenseTeamId = turn.offense_team_id` when it differs (lines 47–50). So for a **Dead Ball** turn we set offense to that turn’s `offense_team_id` (old offense); for the **SIDE_INBOUND** turn we set it to that turn’s `offense_team_id` (new offense).
- **After each turn:** `handleTurnTransition()` / finalize use `turnData.offense_team_id` again; no separate “flip” logic—just assignment from the **current** turn.
- **Batch (e.g. [Dead Ball, SIDE_INBOUND]):** The frontend iterates over each sub-turn and calls `prepareTurnForAnimation` per sub-turn. So during the Dead Ball sub-turn we use Dead Ball’s `offense_team_id` (old); when we start the SIDE_INBOUND sub-turn we set `scene.offenseTeamId` to SIP’s `offense_team_id` (new). The “defense becomes new offense” moment on the frontend is therefore **at the start of the SIDE_INBOUND turn**, not during the Dead Ball (or FOUL/CHARGE) turn.

`gameScene.js` uses `turnData.offense_team` for “who has offense next” (e.g. clipboard/countdown); that value comes from the API’s `gm.offense_team.name` **after** the macro turn (so it’s already the new offense). That’s used for UI/state after the batch, not for per-step animation; per-step offense is driven by the **current** turn’s `offense_team_id` in prepareTurnForAnimation and the resolver.

---

## 4. Conclusion

- **Backend:** For offensive foul (no FT), charge, and dead ball we flip possession in **one place** (the SIP block in `game_manager.simulate_macro_turn()`), **after** appending the result turn and **before** creating/appending the SIDE_INBOUND turn. We do **not** set the result turn’s `offense_team_id` to the new offense; only the SIP turn has the new offense.
- **Frontend:** We set “who is on offense” from the **current** turn’s `offense_team_id` at **turn start** (prepareTurnForAnimation). So we only treat defense as the new offense when we **start** the SIDE_INBOUND turn, not during the Dead Ball / FOUL / CHARGE turn.

So **all three result types are aligned:** we do **not** flip or declare "defense is new offense" **during** the result turn; we do it when we **start** the next (SIP) turn. If there is an HCO defender/ball desync, it is not explained by a difference in **when** we flip or set new offense for dead ball vs offensive foul/charge; the next place to look would be **how** offense/defense/ball are used during the **SIP** turn (e.g. HCO steps) or resolver/fallbacks (e.g. `possession_team_id` vs `offense_team_id`).

---

## 5. End-to-end differences between the three turn types

Tracing from backend result creation through `determine_next_turn`, SIP block, and frontend handling shows these **concrete differences** (only these affect behavior; everything else is shared).

### 5.1 Backend: `next_play_type` / `next_turn` (CHARGE vs FOUL / DEAD BALL)

| Result type   | Who sets next | Value on result turn |
|---------------|---------------|----------------------|
| **CHARGE**    | `shot_manager.py` (line 612) | `next_play_type`: **"SIP"** |
| **FOUL** (no FT) | Not set on result; `determine_next_turn()` (game_manager) | `next_turn`: **"SIDE_INBOUND"** |
| **DEAD BALL** | Not set on result (non-STEAL branch); `determine_next_turn()` | `next_turn`: **"SIDE_INBOUND"** |

- **Flow:** In `determine_next_turn()`, `if result.get("next_play_type"): return result["next_play_type"]` runs first (game_manager ~951). So CHARGE returns **"SIP"**; FOUL and DEAD BALL never set `next_play_type` on the result, so they fall through to the `result_type` checks and get **"SIDE_INBOUND"**.
- **Effect:** The **result** turn (the one that just happened) has `next_turn: "SIP"` for CHARGE and `next_turn: "SIDE_INBOUND"` for FOUL and DEAD BALL. The **following** turn is always `result_type: "SIDE_INBOUND"` in all three cases. So naming is inconsistent only for CHARGE (`"SIP"` vs `"SIDE_INBOUND"`). Any frontend logic that branches on `previousTurn.next_turn === "SIDE_INBOUND"` (e.g. timeout eligibility, transition type) would be **true** for FOUL/DEAD BALL but **false** for CHARGE.

**Recommendation:** In `shot_manager.py`, set `next_play_type` (and thus `next_turn`) to **"SIDE_INBOUND"** for CHARGE instead of `"SIP"`, so all three SIP-bound result types have the same `next_turn` and the same frontend branching behavior.

### 5.2 Backend: payload shape (no behavioral difference for possession)

- **FOUL:** Has `foul_player_id`, `foul_team`, `foul_count`, `fouled_out`, optional `foul_out_player`; no `victim_id`/`stealer_id`.
- **CHARGE:** Has `foul_player_id`, `foul_team`, `shooter`, `shooter_id`, `shooter_pos`; no `foul_count`/`fouled_out`/`foul_out_player` in the same shape as FOUL; no `victim_id`.
- **DEAD BALL:** Has `victim_id`, `victim_name`; optionally `stealer_id`/`stealer_name` for STEAL branch only; no `foul_team`/`foul_player_id`.

Possession and flip logic do not depend on these; they only affect announcements and foul-out handling.

### 5.3 Frontend: announcements

- **CHARGE:** End-of-turn announcement is **"CHARGE!"** with defense team and foul player (announcements.js ~364–386).
- **FOUL:** **"OFFENSIVE FOUL!"** or **"DEFENSIVE FOUL!"** depending on `foul_team`, with foul player (announcements.js ~389–434).
- **DEAD BALL:** Treated with other turnovers; random text like "Travel!" / "Double Dribble!" (announcements.js ~470–471, 499–500).

Purely presentational.

### 5.4 Frontend: animation / step behavior

- **turnAnimation.js (~2350–2352):** `isChargeOrBlockingFoul = turnData.result_type === 'CHARGE' || (turnData.result_type === 'FOUL' && ... blocking foul)`. For these, we **skip** animating a shot attempt and keep the ball on the ball handler. DEAD BALL is **not** in this group, but DEAD BALL turns typically have no "shoot" action anyway, so no practical difference for possession or HCO.

### 5.5 Frontend: routing and handlers

- **AnimationEngine.js:** All three are in the handlers map: `FOUL`, `CHARGE`, `DEAD BALL` / `DEAD BALL` (space) all use `handleDefault`. No routing difference.
- **animateGameTurns.js:** The **next** turn is routed by `turn.result_type === "SIDE_INBOUND"`; the **result** turn (CHARGE/FOUL/DEAD BALL) is not branched by result_type for routing. No difference.

### 5.6 Summary of behavioral differences

- The only **behavioral** difference that can affect logic (e.g. transition type or eligibility) is **CHARGE** having `next_turn: "SIP"` instead of **"SIDE_INBOUND"**. Unifying CHARGE to use `next_play_type: "SIDE_INBOUND"` (and thus `next_turn: "SIDE_INBOUND"`) would make all three identical for possession, next-turn type, and any frontend that keys off `next_turn` or `next_play_type`.
- Possession flip timing, `offense_team_id` on the result turn, and when the frontend sets `scene.offenseTeamId` are the **same** for all three.
