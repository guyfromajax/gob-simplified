# Clock Sync System

## 1. OVERVIEW

**Problem:** Frontend and backend had independent clocks, causing drift between displayed time and authoritative game state.

**Solution:** Backend-authoritative clock contract on every turn. The backend attaches `clock_start`, `clock_end`, `shot_clock_*`, and `real_time_elapsed_ms` to each turn result; the frontend uses these as the single source of truth for display and interpolation.

**Implementation phases:**
- **Phase 1:** Backend attaches all clock contract fields (including `real_time_elapsed_ms`) in `_attach_clock_contract` (TurnManager).
- **Phase 2:** Frontend consumes `real_time_elapsed_ms` to interpolate the game clock from `clock_start` to `clock_end` over the actual animation duration (no local countdown).

## 2. ARCHITECTURE

- **Backend** computes all clock values: `time_remaining`, `shot_clock_remaining`, and per-turn `time_elapsed` and `real_time_elapsed_ms`.
- **Frontend** is a dumb display: it shows the clock based on contract fields and interpolates over `real_time_elapsed_ms` when Phase 2 is active.
- **Bridge constant:** 350 ms real time = 1 game second. This aligns backend movement (157.5 px per game second) with frontend animation (450 px/s) so the clock countdown rate matches the on-screen action.

## 3. CLOCK CONTRACT FIELDS

Attached to every turn that receives a clock contract (all normal and bypass turns).

| Field | Type | Description | Applies to |
|-------|------|-------------|------------|
| `clock_start` | int | Game clock (seconds) at turn start | All turns with contract |
| `clock_end` | int | Game clock (seconds) at turn end | All turns with contract |
| `shot_clock_start` | int | Shot clock at turn start | All turns with contract |
| `shot_clock_end` | int | Shot clock at turn end | All turns with contract |
| `shot_clock_reset` | bool | True if shot clock was reset this turn | All turns with contract |
| `clock_contract_source` | str | Where the contract was attached (e.g. `update_clock_and_possession`, `timeout`, `opening_tip`) | All turns with contract |
| `real_time_elapsed_ms` | int | Total wall clock ms for this turn’s animation (used for clock interpolation) | All turns with contract |

## 4. TURN TIME ELAPSED

### game_time_elapsed (time_elapsed)

- **What it is:** Game seconds consumed by the turn (deducted from game clock). Stored on the turn result as `time_elapsed`.
- **How it’s computed:** Depends on turn type (skeleton steps, fast-break segments, OREB, opening tip, etc.); ledger-derived per UESS. See `_documentation_master/00_General_Systems/UESS_System.md` (§5 clock authority) for elapsed-time derivation, and `_documentation_master/05_GP_Supporting_Systems/Shot_Clock_System.md` for shot-clock policy. Not modified by the clock sync system.

### real_time_elapsed_ms

- **Formula:** `real_time_elapsed_ms = (game_time_elapsed * 350) + fixed_phases_ms`
- **Included:** Movement time (game seconds × 350 ms) plus fixed animation phases during which the clock runs (pass delays, steal, outlet, shot, rim hold on misses, etc.).
- **Excluded (clock paused):**
  - Any phase whose name contains `"announcement"`.
  - Rim hold on **makes** (only rim hold on **misses** counts).
  - OPENING_TIP `initial_hold` (clock not started yet).

**Fixed phases table (verified against animation config):**

| Turn type | Condition | Fixed phases (ms) | Notes |
|-----------|-----------|-------------------|--------|
| Shot (half-court) | Make | 150 | pass_delay only |
| Shot (half-court) | Miss/block | 1150 | pass_delay + rim_hold |
| Shot (fast break) | Make | 1050 | pass + outlet_move + shot |
| Shot (fast break) | Miss/block | 2050 | pass + outlet_move + shot + rim_hold |
| DEFENSIVE_STOP | Fast break | 1000 | defensive_stop_hold |
| DEFENSIVE_STOP | Non fast break | 0 | — |
| PUTBACK_MAKE | — | 800 | rebound_move + attach_delay |
| PUTBACK_MISS | — | 1800 | rebound_move + attach_delay + rim_hold |
| OREB_KICKOUT | — | 800 | rebound_move + attach_delay |
| FOUL | — | 0 | — |
| OPENING_TIP | — | 400 | apex_delay + pass_delay (initial_hold excluded) |
| FINAL_HOLD | — | 1800 | holdClockOutMs (final turn shot) |
| FREE_THROW, SIDE_INBOUND, BASELINE_INBOUND, TIMEOUT | — | 0 | Zero-elapsed; no interpolation |

*Shot outcomes use `result_type` MAKE / MISS / BLOCK; half-court vs fast break is determined by `fast_break` on the result. Defensive stops use `result_type == "DEFENSIVE_STOP"`.*

## 5. FRONTEND CLOCK INTERPOLATION (Phase 2)

When a turn is played:

- `gameSecondsToCount = turn.clock_start - turn.clock_end`
- `durationMs = turn.real_time_elapsed_ms`

If `durationMs > 0` and `gameSecondsToCount > 0`:

- `ratePerMs = gameSecondsToCount / durationMs` (game seconds per real ms).
- Count down the displayed clock at this rate.
- Clamp: never below `clock_end`, never above `clock_start`.
- When the animation completes, snap the display to `clock_end`.

**Zero-elapsed turns** (`real_time_elapsed_ms === 0` or `clock_start === clock_end`): do not run countdown; leave the clock display unchanged.

## 6. BYPASS TURNS

Bypass turns are those where the clock contract is attached outside the main `update_clock_and_possession` path (e.g. in `game_manager.py` or `main.py`). They still go through `_attach_clock_contract`, so they receive the same fields, including `real_time_elapsed_ms`.

| Bypass type | Where contract is attached | clock_start vs clock_end |
|-------------|----------------------------|---------------------------|
| TIMEOUT | game_manager (timeout turn) | Equal (no time elapsed) |
| SIDE_INBOUND (SIP) | main.py (SIP turn) | Equal |
| BASELINE_INBOUND (BIP) | main.py (BIP inbound turns) | Equal |
| OPENING_TIP | main.py (opening tip turn) | May differ (fixed 400 ms) |
| FOUL (non-shooting, etc.) | game_manager (foul result) | Depends on foul path |

For TIMEOUT, SIP, BIP: `time_elapsed` is 0 and `real_time_elapsed_ms` is 0; no clock interpolation.

## 7. OPTION B UPGRADE PATH

**What Option B is:** Full end-to-end precision where every fixed phase (including those currently excluded for balance) is reflected in `real_time_elapsed_ms` or in a future extension (e.g. game_time_elapsed contribution).

**Why deferred:** Including certain phases (e.g. announcement holds, make rim holds) in the clock run would change effective game pacing and was deferred to preserve game balance.

**How to upgrade:** In `TurnManager._compute_real_time_elapsed_ms`, search for comments starting with `OPTION_B`. Each marks a site where additional time could be added (or logic switched) for full precision; uncomment or adjust those sites per product decision.

## 8. SPEED CONSTANTS REFERENCE

- **Backend:** 157.5 pixels = 1 game second (movement).
- **Frontend:** 450 px/s (animation speed).
- **Bridge:** 350 ms real time = 1 game second (clock interpolation).
- **Fast break (anisotropic):** `sqrt((dx/20)^2 + (dy/10)^2)` game seconds per segment.
- **Sprint multiplier (1.5x):** Present in config; currently unused.

## 9. END-OF-TURN SNAP (SHOT CLOCK)

The frontend uses the same pattern for shot clock as for game clock. In `updateScoreboard`, the shot clock snap uses `turn.shot_clock_remaining` when present, and falls back to **`turn.shot_clock_end`** (contract field on every turn) when missing. That way every turn gets a correct snap without the backend adding extra display fields. Reset and shot-clock violation remain backend-only; `shot_clock_end` already reflects the post-reset value because it is read from `game_state` after `update_clock_and_possession` applies the reset.

## 10. KNOWN ISSUES / FUTURE WORK

- **Shot clock violation:** Trigger depends on backend `shot_clock_remaining` reaching zero before reset; a log check is recommended to confirm behavior.
- **Quarter start:** Clock initialization at quarter start should be verified for continuity with the first turn’s clock contract (e.g. clock_start matches expected value after quarter break).
