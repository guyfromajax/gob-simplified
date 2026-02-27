# Final Turn Implementation Plan

Step-by-step implementation for **Final Turn Execution** (end of quarter / end of game). Reference: [Situational_Logic_System.md](../docs_1_systems/05_GP_Supporting_Systems/Situational_Logic_System.md) — Final Turn Execution section.

**Scope:** Q4 and OT use the same Final Turn logic. Trigger: first possession with `time_remaining <= 30` seconds that is not OREB or Fast Break.

---

## Phase 1: Backend — Trigger and routing

1. **Detect Final Turn eligibility**
   - At the start of a turn (before state routing), if `quarter >= 4` and `time_remaining <= 30` and the current turn is not OREB and not Fast Break, mark this turn as eligible for Final Turn.
   - Ensure we only trigger once per quarter/OT (e.g. set a `final_turn_triggered_this_period` or equivalent so the *first* team to have possession with ≤ 30s gets it).

2. **Q4 branch: decide Final Turn subtype**
   - If Final Turn eligible and we're in Q4 or OT, evaluate Slow It Down, Quick Shot, and Force Foul (existing situational_logic).
   - **Slow It Down + Force Foul false:** Produce a **FINAL_HOLD** turn (no shot, time_elapsed = time_remaining, no fouls/turnovers). Quarter ends after this turn.
   - **Slow It Down + Force Foul true:** Execute Force Foul (existing logic); no new Final Turn type.
   - **Quick Shot:** Route to normal Quick Shot turn (no Final Turn alignment or play execution).
   - **None of the above (normal):** Use the same final-shot play execution as Qs 1–3 (trailing or tied only; verify in time-band logic).

3. **Qs 1–3 (and Q4 “normal” final shot): route into Final Turn play**
   - Once we've determined this is a Final Turn shot attempt (not FINAL_HOLD, not Quick Shot, not Force Foul), we need to produce a turn that uses Final Turn State alignment and play execution instead of normal HCO.

---

## Phase 2: Backend — Final Turn State (alignment)

4. **Constants / spots**
   - Confirm all Final Turn spot names exist in `HCO_STRING_SPOTS`: deep upper wing, deep lower wing, upper/lower corner, upper/lower midCorner, key, midWing, wing, midCorner, corner, deep wing, deep baseline. Add any missing entries if needed.
   - Optionally add a `FINAL_TURN_OFFENSE_SPOTS` or similar for clarity (or derive from HCO_STRING_SPOTS by name).

5. **Offense starting alignment**
   - Ball handler: 60% PG, 30% SG, 10% SF (random). If SF is ball handler, swap his placement logic with SG so ball handler is always at deep upper wing or deep lower wing.
   - PG: deep lower wing or deep upper wing (random).
   - SG: the other of deep lower wing / deep upper wing (so PG and SG occupy the two deep wings).
   - SF and PF: each randomly assigned to one of upper corner, lower corner, upper midCorner, lower midCorner; enforce one upper and one lower.
   - C: key.
   - Build an `oDestinations` (or equivalent) keyed by position for this alignment; use home-side coords and flip for away offense.

6. **Defense starting alignment**
   - Choose 2-3 zone or 3-2 zone at random (50/50).
   - Use existing zone logic from `shared_defense.py` (e.g. `ZONE_23_NORMAL`, `ZONE_32_NORMAL`) to get defender positions for “ball at key” or neutral state, or define a minimal “starting” zone set for Final Turn so all five defenders have a spot. Reuse `get_defender_coords` or the same pattern used in HCO for zone.
   - Produce `dDestinations` for the defense.

7. **Attach alignment to the turn**
   - Final Turn shot attempts should include a skeleton or step list that reflects: (1) starting positions from the alignment above, (2) play execution steps (ball handler and shooter movement, pass if needed, other 3 or 4 players to opposite half), (3) shot attempt at 3–5 seconds “remaining” (conceptually). The backend can emit a minimal skeleton (e.g. step 0 = alignment, step 1 = movement + pass, step 2 = shot) and set `time_elapsed = time_remaining` for the turn.

---

## Phase 3: Backend — Play execution (shooter choice and shot)

8. **Shot type and shooter selection**
   - Shot type: 50% outside, 50% Attack (random).
   - **Outside:** Rank all five players by SH (tie-break random). Weighted random: #1 50%, #2 30%, #3 20%, #4 9%, #5 1%.
   - **Attack:** Rank all five by (SC + AG) (tie-break random). Same weights: 50%, 30%, 20%, 9%, 1%.
   - Set `ball_handler` (already set by alignment) and `shooter` on the turn. Ensure roles are consistent with the skeleton (shooter moves to wing, ball handler either dribbles to wing or passes from deep key).

9. **Shot attempt and result**
   - Run standard shot attempt logic (make/miss, shooting foul, charge, blocking foul). Use `time_elapsed = time_remaining` for the turn.
   - **Blocking foul on Final Turn attack shot:** Special case — always award exactly 2 free throws (no and-1, no 3 FTs for three-point attempt). All other game situations keep current blocking-foul behavior (non-shooting defensive foul → SIP or bonus FTs).
   - After the shot (or FTs if shooting foul), quarter ends (and game ends if it’s the final period).

10. **FINAL_HOLD turn**
    - Result type: `FINAL_HOLD`. `time_elapsed = time_remaining`. No shot, no fouls, no turnovers. Quarter ends after this turn. Frontend will need to recognize this and animate “hold until 0” (and possibly advance to Quarter Break).

---

## Phase 4: Frontend — Final Turn detection and routing

11. **Detect Final Turn and FINAL_HOLD**
    - When the current turn has a Final Turn flag (or equivalent) or `result_type === "FINAL_HOLD"`, route to Final Turn handlers instead of normal HCO.
    - FINAL_HOLD: play starting alignment (optional), then run clock out (no shot animation), then trigger quarter/game end.

12. **Final Turn shot attempt: alignment animation**
    - Use `oDestinations` and `dDestinations` from the turn to place offense and defense in Final Turn State (same as other inbounds/setups: tween players to spots). Ensure home/away flip for away offense using existing coord flip.

---

## Phase 5: Frontend — Play execution animation

13. **Ball handler and shooter movement**
    - Shooter moves to wing on his vertical half (upper spot → upper wing, lower spot → lower wing; C → random upper or lower wing). If shooter is ball handler, he dribbles to that wing; otherwise, he moves to his wing, then ball handler passes (from same half or via deep key if opposite half).
    - Implement “same half” vs “opposite half” rule: if ball handler and shooter are on opposite vertical halves, ball handler goes to deep key then passes to shooter.

14. **Other 3 or 4 players**
    - The 3 or 4 players who are not ball handler and not shooter move to the opposite vertical half. Each picks one of: midWing, wing, midCorner, corner, deep wing, deep baseline; no two players same spot. Animate these movements in parallel (or in one step) with the ball handler/shooter actions where appropriate.

15. **Shot attempt**
    - With “3–5 seconds remaining” (for now, a fixed delay or step), trigger the shot attempt. Reuse Motion offense outside/attack shot animation (same as current HCO outside/attack). Then run standard shot result (make/miss, foul) and quarter end.

16. **Blocking foul: 2 FTs only**
    - When the result is a blocking foul on a Final Turn attack shot, frontend should show exactly 2 free throws (no and-1, no three-shot foul). Backend will have already produced the correct FT count; frontend just needs to not override it.

---

## Phase 6: Quarter / game end and edge cases ✅ Implemented

17. **Quarter end after Final Turn**
    - After a Final Turn shot attempt (or FINAL_HOLD), ensure the game advances to Quarter Break (and, if applicable, to OT or end of game). Reuse existing quarter-end and game-end logic; ensure it triggers after the Final Turn result is applied.
    - *Implemented:* Phase 3 sets `time_elapsed = time_remaining` so the clock reaches 0. API computes `quarter_complete` when `time_remaining <= 0` and no pending FTs; frontend advances to Quarter Break / game end when `quarter_complete` is true. Comments added in `api.py` and `gameScene.js`.

18. **OREB and Fast Break**
    - No code change to OREB/Fast Break execution. The *next* turn after an OREB or Fast Break (when time is still ≤ 30 and quarter ≥ 4) is the one that is evaluated for Final Turn. So the trigger check runs at the start of each turn; if the turn is OREB or Fast Break, we do not treat it as Final Turn.
    - *Implemented:* Trigger requires `state in ("HCO", "HCT", "FCP")`; OREB and Fast Break use other states, so they are excluded. Comment added in `turn_manager.py`.

19. **Force Foul edge case (Q4)**
    - If we ever reach “Slow It Down + Force Foul true” at Final Turn time, execute the Force Foul (existing logic). No special Final Turn alignment for that possession.
    - *Implemented:* `elif slow and force_foul: result = self._execute_final_turn_force_foul()`. Comment added in `turn_manager.py`.

---

## Implementation order (suggested)

| Order | Step | Phase |
|-------|------|--------|
| 1 | Trigger detection and “first possession ≤ 30s” per period | 1 |
| 2 | Q4 branch: FINAL_HOLD vs Quick Shot vs Force Foul vs normal final shot | 1 |
| 3 | Constants: confirm/add Final Turn spots in HCO_STRING_SPOTS | 2 |
| 4 | Offense starting alignment (ball handler, PG, SG, SF, PF, C) | 2 |
| 5 | Defense starting alignment (2-3 or 3-2 zone) | 2 |
| 6 | Attach alignment to turn (skeleton / oDestinations / dDestinations) | 2 |
| 7 | Shot type and shooter selection (SH vs SC+AG, weights) | 3 |
| 8 | Shot attempt + blocking foul = 2 FTs only for Final Turn attack | 3 |
| 9 | FINAL_HOLD result type and quarter end | 3 |
| 10 | Frontend: detect Final Turn and FINAL_HOLD, route to handlers | 4 |
| 11 | Frontend: alignment animation (Final Turn State) | 4 |
| 12 | Frontend: ball handler + shooter movement and pass | 5 |
| 13 | Frontend: other 3 or 4 players to opposite half | 5 |
| 14 | Frontend: shot attempt animation and quarter end | 5 |
| 15 | Quarter/game end and OREB/FB/Force Foul edge cases | 6 |

---

## Reference

- **Doc:** `docs/docs_1_systems/05_GP_Supporting_Systems/Situational_Logic_System.md` (Final Turn Execution).
- **Constants:** `BackEnd/constants/__init__.py` (HCO_STRING_SPOTS, SITUATIONAL_*).
- **Zone defense:** `BackEnd/utils/shared_defense.py` (ZONE_23_*, ZONE_32_*, get_defender_coords).
- **Situational:** `BackEnd/utils/situational_logic.py` (is_slow_it_down, is_quick_shot, should_force_foul).
- **Attributes:** SH, SC, AG on player/lineup objects.
