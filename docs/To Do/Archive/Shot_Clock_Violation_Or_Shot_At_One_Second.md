# Shot Clock Violation vs Shot at 1 Second — To Do

**Status:** Planned (not yet implemented)  
**Location:** Backend; decision point is where we currently detect “shot clock would hit 0” (e.g. HCO path in `phase_resolution.py`, before applying the stopper for `SHOT_CLOCK_VIOLATION`).

---

## Goal

When a turn would hit the **shot clock violation threshold** (cumulative game seconds ≥ shot clock remaining during the turn), support two outcomes instead of always violating:

1. **Shot clock violation** — Current behavior: truncate at the violation step, announce violation, process as dead-ball turnover (0 seconds on shot clock).
2. **Shot attempt at 1 second** — Run a shot attempt timed so the shot occurs with **1 second remaining** on the shot clock (not 0).

---

## Current Behavior

- We compute per-step timing for the full skeleton and find the first step `i` where cumulative game seconds ≥ `shot_remaining`.
- We always override to `SHOT_CLOCK_VIOLATION`, set `shot_clock_violation_step_index = i`, and run the stopper path (truncated skeleton + violation announcement + turnover logic).

---

## Proposed Addition

At the same decision point (when we detect “would hit 0”):

- **Branch:** Choose between:
  - **A)** Shot clock violation (0 remaining) — keep current behavior.
  - **B)** Shot at 1 second — do *not* override to violation; instead run a shot attempt with timing such that the shot happens when the shot clock has 1 second left.

**Shot-at-1 path (B):**

- **Timing:** Movement phase = `shot_remaining - 1` game seconds; shot phase = 1 game second. Total turn = `shot_remaining` game seconds; shot clock ends at **1** (not 0).
- **Play:** Use existing shot resolution (make/miss/block/foul). Feed a truncated skeleton (steps only up to the point where cumulative = `shot_remaining - 1`) and treat the next moment as the shot step. Roles (shooter, defender, etc.) come from that truncated skeleton / intended shot step so backend and frontend have a clear “who shot, from where.”

**Choice rule:** To be defined (e.g. 50/50, or violation-only under certain conditions, or shot-at-1 only when a valid shot step exists). Document the chosen rule in this file when decided.

---

## Implementation Notes

- Single branch point: where we currently set `result = "SHOT_CLOCK_VIOLATION"` and `game_state["shot_clock_violation_step_index"]`.
- Violation path (A): no change.
- Shot-at-1 path (B): skip violation override; set timing/truncation so `shot_clock_end = 1` and run normal shot resolution with the truncated skeleton and shot step.
- Game clock and shot clock math should stay consistent (same formulas, different `shot_clock_end` for path B).

---

## References

- Shot clock violation logic: `BackEnd/engine/phase_resolution.py` (HCO shot-clock check before `apply_stopper_system_to_skeleton`).
- Stopper system: `apply_stopper_system_to_skeleton`, `SHOT_CLOCK_VIOLATION` handling.
- Real_Time_Clock_System.md — shot clock rules and derivation.
