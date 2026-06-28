# Shot Clock System

> **Scope note.** Game-clock elapsed-time derivation, movement rates, and animation timing are owned by **UESS** — see [`UESS_System.md`](../00_General_Systems/UESS_System.md) §3.4 (archetype rates), §5 (clock authority / ledger-derived `time_elapsed`), and §9.3–§9.4 (AG curve, `tickMs` wall-clock). The legacy "clock categories" model and per-movement pace constants (Open Floor / COF / Drive / Compressed HCO) that previously lived here were retired in the May 2026 Movement Rate Refactor (`projects/Z-Completed/Movement_Rate_Refactor.md`).
>
> **This doc covers shot-clock policy only** — rules the backend applies on top of the UESS clock contract: running/stop behavior, reset triggers, derivation of `shot_clock_end`, the shot-clock-violation decision, the Motion second-chance recalibration, and timeout-click reconciliation.

---

## Shot Clock Rules

Whenever the game clock is running, the shot clock runs, with one exception.

**Exception — shot attempt:** When a shot is attempted, the shot clock **stops** at that moment (in game time). The game clock keeps running for the rest of the turn.

Shot clock reset triggers (authoritative policy):

- **Possession change** (except timeout turns).
- **Non-shooting defensive foul** where next turn is `SIDE_INBOUND`/`SIP` and possession does not change (defensive aliases accepted: `DEFENSIVE`, `DEFENSE`, `D_FOUL` from `foul_type`/`foul_team`).
- **OREB possession renewal** event — **except after a blocked shot** (see below).

Inbound receive by itself does **not** reset shot clock.

**Blocked shot → OREB does NOT reset.** A `BLOCK` stops the shot clock at the moment of the block; if the offense rebounds it (OREB), the ensuing possession — putback **or** kickout→HCO — continues from the **remaining** shot-clock time (pure carryover, no floor). Mirrors real-rule behavior for a block that doesn't reset. Normal `MISS`/`FREE_THROW` → OREB still reset.

### Shot clock reset instances

1. Possession change (except `TIMEOUT`).
2. Non-shooting defensive foul with next turn `SIDE_INBOUND`/`SIP`, no possession change.
3. OREB possession renewal — **only when the shot was `MISS` or `FREE_THROW`; a `BLOCK` → OREB carries the remaining clock over (no reset).**

### Shot clock carryover between turns

1. FCP/HCT to HCO (with no foul or turnover in between).
2. Steal to HCO (with no foul or turnover in between).
3. OREB Kickout to HCO (with no foul or turnover in between).

---

## Backend: shot clock derivation

The backend does **not** track shot clock independently. For each turn it derives shot clock end as follows (`turn_manager.py`):

1. **Current turn's contract**
   - **Game clock:** `game_seconds_elapsed = clock_start - clock_end` (full turn). The game clock always uses this full elapsed value.
   - **Shot clock (non–shot-attempt turns):** `shot_clock_end = shot_clock_start - game_seconds_elapsed`, clamped to 0 (same as game clock delta).
   - **Shot clock (shot-attempt turns):** The shot clock **stops at the moment of the shot**. The backend computes `game_seconds_at_shot` = sum of `step_clock_seconds[0 .. resolution_step_index]` (capped by game/shot remaining). Then `shot_clock_end = shot_clock_start - game_seconds_at_shot`, clamped to 0. The rest of the turn does not reduce the shot clock further.
   - Shot-attempt turn = `result_type` in MAKE, MISS, BLOCK, or FOUL with free throws / `next_play_type` FREE_THROW. When `step_clock_seconds` and `resolution_step_index` are missing (e.g. some non-skeleton paths), the backend falls back to using full `game_seconds_elapsed` for that turn.
   - The **clock contract** attached to the turn uses this derived `shot_clock_end` so the frontend animates from `shot_clock_start` to `shot_clock_end` during the turn.

2. **Reset only affects the next turn**
   - Reset logic must **not** change the current turn's `shot_clock_end`.
   - After the contract is attached, the backend sets `game_state["shot_clock_remaining"] = 30` (or `min(30, time_remaining)`) so that the **next** turn's `shot_clock_start` is 30.
   - Order of operations: compute derived `shot_clock_end` → attach contract (so current turn shows start→end) → then, if reset, set game_state for next turn to 30.

3. **Shot clock at 0**
   - If the derived `shot_clock_end` would be 0 and the turn is in a clock-enforced state (HCO, FCP, HCT, FAST_BREAK), the backend triggers shot-clock-violation / forced-shot logic instead of using that result (see below).

### Live clock end-of-turn snap (frontend)

The frontend snaps the shot clock using the same pattern as the game clock: use the turn's explicit field when present (`shot_clock_remaining`), else the contract end value **`shot_clock_end`**, else **`shot_clock_start`** (on every turn with a contract). When updating after a batch or at a turn boundary without a per-turn payload (e.g. summary update), the frontend uses the response's top-level **`shot_clock_remaining`**. No extra backend fields; reset and shot-clock-violation logic remain backend-only. The frontend does not implement reset policy; it displays only values sent by the backend (turn or response). See `clock_sync_system.md` §9.

---

## Shot clock violation vs forced shot attempt

When a clock-enforced turn would hit shot clock 0, the backend decides between a violation and a forced shot attempt (`phase_resolution.py` ~L4605):

```
chemistry    = offense team's chemistry value (7–25)
discipline   = offense team's discipline value (−10 to 10)
intelligence = int(ball handler's IQ attribute / 4)   (0–25)

violation_threshold = 60 + chemistry + discipline + intelligence
x = random.randint(1, 100)
if x > violation_threshold: violation = True
else:                       shot attempt = True
```

If a shot attempt results, the ball handler shoots from his location at the point the turn ends, with **+100 added to the shot threshold** when calculating shot success.

> Variable names above are illustrative (intent only); the code does not require these exact names.

**Coverage:** this violation-vs-forced-shot logic is **not universal** — it applies to the clock-enforced states `HCO`, `FCP`, `HCT`, `FAST_BREAK` (a turn-start check when `shot_clock_remaining <= 0`, plus the HCO mid-skeleton check above). `OREB`/putback is handled separately (below).

### OREB shot clock → dead-ball turnover

The OREB possession needs enough **carried** shot clock (no reset after a block — see § Shot clock reset instances) to reach a shot. Checked once at the top of the OREB turn (`resolve_offensive_rebound_turn`):

- If the carried `shot_clock_remaining` `<= ~2s` (the pre-shot window — too little to reach the putback shot, or to run the block→HCO reset into a shot), the possession is **killed as a clean dead-ball / `SHOT_CLOCK` turnover** — *always a turnover, never the HCO 50/50 forced-shot path*. Covers both the entry case (already ≤0) and the clock expiring mid-progression before the next shot. Applies to **both** the miss→OREB→putback path and the block→OREB→HCO path (the gate fires before the HCO handoff).
- **OREB credit:** the offensive rebound is credited only if `shot_clock_remaining > 0` at the start of the OREB turn. The board is recorded upstream (on the block/miss turn); if the clock had already expired (`== 0`), it is uncredited (`record_stat("OREB", -1)`).

---

## Second Chance System (Motion only)

When a **Motion** HCO turn would hit shot clock 0, the offense gets one chance to "recalibrate" to an earlier step and take a normal shot instead of a violation or shot-at-1.

**When it runs:** Only for Motion plays. Only when the shot clock would reach 0 during the turn (same point as the violation / shot-at-1 decision). If the violation step index is < 3, recalibration is skipped (no valid earlier step).

**Roll** (`phase_resolution.py` ~L4588):
- `recalibration_score = (chemistry × 5) + (discipline × 3)` (chemistry 7–25, discipline −10 to 10).
- `die_roll = random.randint(1, 100)`.
- If `die_roll < recalibration_score` → recalibrate; else → normal violation / shot-at-1 logic.

**Recalibration:** Pick a random step index in **[2, violation_step − 1]**. Resolve the motion shot from that step (same shot-type and execution logic as normal motion). Replace the turn's skeleton with that shot sequence; game and shot clock elapse to the new shot. No new shot-execution code — existing `resolve_motion_offense_shot` is called with a forced step index.

**Location:** `BackEnd/engine/phase_resolution.py` — shot clock block in `resolve_half_court_offense_logic`, and downstream motion-shot block when `_motion_shot_recalibrated` (game_state) is set/consumed.

---

## Post-Make BIP Clock Run-Through Rule

- After made field goals (`MAKE`, `PUTBACK_MAKE`), the following `BASELINE_INBOUND` turn may consume game-clock time when quarter `time_remaining > 60`.
- At `time_remaining <= 60`, BIP stays clock-dead.
- This does not change timeout / free-throw stoppage rules.

(`FREE_THROW` and `SIDE_INBOUND_PASS` are always clock-dead; `INBOUND_PASS`/BIP is clock-dead by default with the post-make exception above.)

---

## Timeout Click Clock Reconciliation (February 2026)

### Problem
During live countdown, a timeout click can happen between backend turn boundaries. In that gap, backend `game_state.time_remaining` may still be slightly higher than the user-visible clock on `court.html`. If timeout save uses backend-only time, lineup can show the expected value while return-to-court resumes from an earlier (higher) time.

### Rule
At timeout click, backend reconciles clocks using:
- `effective_game_time = min(backend_time_remaining, displayed_time_remaining)`
- `effective_shot_clock = min(backend_shot_clock_remaining, displayed_shot_clock_remaining, effective_game_time)`

Both are clamped to `>= 0`.

### Execution Flow
1. Frontend sends timeout click payload with:
   - `displayed_clock`
   - `displayed_time_remaining`
   - `displayed_shot_clock_remaining`
   - `timeout_trace_id`
2. `/api/call-timeout` applies the min-reconciliation before `gm.call_timeout(...)`.
3. Timeout snapshot persisted to DB uses reconciled values.
4. Resume (`/api/simulate-quarter?resume_from_timeout=true`) restores from that saved snapshot.

### Notes
- Backend remains source of truth for persisted state.
- Frontend remains presentation clock; click capture prevents drift at the timeout boundary.
- This reconciliation is surgical and only applies on the timeout-click save path.

---

## Key files

- `BackEnd/models/turn_manager.py` — shot-clock derivation (`shot_clock_end`, `game_seconds_at_shot`), contract attach, reset-for-next-turn.
- `BackEnd/engine/phase_resolution.py` — shot-clock-0 handling in `resolve_half_court_offense_logic`: violation vs forced shot (`violation_threshold`), Motion second-chance recalibration (`recalibration_score`, `_motion_shot_recalibrated`); dynamic HCO/set-play walks may stamp `_hco_shot_clock_est` for finer at-attempt tier diagnostics.
- `BackEnd/utils/shot_split_tracker.py` — end-of-game **HCO shot-clock tier** report (`hco_shot_tier_counts`): every HCO FGA via `record_shot_split` / `ShotManager._record_shot_diagnostics`. At-attempt clock: dynamic `_hco_shot_clock_est` when stamped, else `shot_clock_remaining − elapsed_to_shot_step` (same detach math as `turn_manager._shot_detach_elapsed_seconds`). Grep `END-OF-GAME SHOT DIAGNOSTICS`.
- `BackEnd/api/api.py` — `/api/call-timeout` min-reconciliation; `/api/simulate-quarter?resume_from_timeout=true` restore.
- Frontend clock display / snap: `FrontEnd/static/js/phaser/utils/gameClock.js`, `court.html`; see `clock_sync_system.md` §9.

> For everything about how a turn's elapsed game-clock time is computed (per-step `step_clock_seconds[]`, archetype/AG movement rates, ledger authority, wall-clock `tickMs`), see `UESS_System.md`.
