# Real Time Clock System

## Purpose
Define how gameplay turns map to clock countdown behavior using four clock categories:
- `Skeleton`
- `CG` (Cover-Ground; user note said `CB`, treated here as CG)
- `non-CG`
- `No Impact`

## Clock Categories

### 1. Skeleton
Used for turn types with skeleton steps (`HCO`, `FCP`, `HCT`).

Clock calculation:
- **Bespoke per-step timing**: each step’s game seconds = time for the **last player in that step to reach his destination**. For each step, the backend considers all movers and applies the rate for that movement type (Open Floor, Challenged Open Floor, Drive, Compressed HCO, HCO shot, or fallback). Step duration = **max**(mover durations), or a minimum of 1 game second when no movement is computed. **Pass (ball in air)** time is added to the step when a pass event occurs. See **Movement rates** below for the full classification and formulas.
- Backend emits per-step timing contract:
  - `step_clock_seconds[]`
  - `resolution_step_index`
  - `executed_step_count`
- Turn elapsed: `time_elapsed = sum(step_clock_seconds)`
- Cap per turn: `min(sum_steps, 30)`
- HCO step-1 bring-up overhead:
  - Add movement-based overhead seconds to step 0 timing (setup-to-step1 bring-up), then apply cap.
  - Overhead uses **Open Floor (OF)** rate when inbound positions are available; otherwise fallback segment (step0→step1 ball-handler) at OF rate. See **Movement rates** below.

Execution:
- Backend computes authoritative `time_elapsed`
- Frontend animates each step using backend `step_clock_seconds[]` (not guessed durations)
- Frontend movement speed remains distance-based/consistent (not stretched to fill step)
- After a player reaches step destination, they hold until next step boundary
- Non-ball-handler overrun rule: if a move exceeds step budget, movement is clipped at boundary and continues next step from live position
- Ball-handler exception: if ball-handler move exceeds step budget, the step window extends until ball-handler movement completes
- Frontend countdown is presentation only, then syncs to backend `time_remaining` at turn end

### 2. CG (Cover-Ground)
Used for non-skeleton turns that travel significant court distance (`FAST_BREAK`).

Clock calculation (per movement segment):
- Fast Break movement uses **Challenged Open Floor (COF)** rate (18/18): `segment_seconds = sqrt(dx^2 + dy^2) / 18`. See **Movement rates** below.
- Turn elapsed = sum of all segment seconds (plus pass in-air where applicable). See **Movement rates** below.

Execution:
- Build movement segment timeline from start/end points
- Use segment time totals as turn `time_elapsed`
- Frontend countdown follows turn timeline and hard-syncs to backend at turn end

### 3. non-CG
Used for non-skeleton turns in compressed space with local action (`OPENING_TIP`, `OREB`).

Clock calculation (OREB):
- **Putback (PUTBACK_MAKE / PUTBACK_MISS):** `time_elapsed = 3` game seconds (collapse + attach: players to rebound spot, ball secured by rebounder).
- **Kickout (OREB_KICKOUT):** `time_elapsed = round(3 + pass_sec)` where `pass_sec` is distance-based from rebounder to PG (pass rate: 1 game sec per 36 grid spots). The 3 is the same collapse+attach phase.

Execution:
- Single-phase countdown for the turn
- Sync to backend authoritative clock/time_remaining after turn resolution

### 4. No Impact
Used for turn types that should not reduce game clock (`INBOUND_PASS`, `SIDE_INBOUND_PASS`, `FREE_THROW` per current plan).

Clock calculation:
- `time_elapsed = 0`

Execution:
- No countdown decrement during turn
- Clock display remains unchanged except for backend sync if response includes updated clock context
- Frontend realtime countdown is explicitly frozen during no-impact turns to prevent local drift
- Realtime clock start is deferred until first impact turn (non no-impact), preventing pre-turn drift on page load/resume flows

## Movement rates (game seconds vs grid distance)

Rates are defined as **grid units per game second** per axis (x / y). Segment formulas use the x rate for isotropic calculation: `segment_seconds = sqrt(dx^2 + dy^2) / x_rate`. **Step duration** = max over all movers in that step (time for last player to reach destination), or a minimum of 1 game second when no movement is computed. **Pass (ball in air)** time is additive to the step when a pass event occurs.

### Movement type classification

| ID | Type | Description | Rate (x / y) |
|----|------|-------------|--------------|
| **a)** | **Open Floor (OF)** | Unabated, unchallenged movement. | **20 / 15** |
| | | Examples: bring the ball up from BIP or SIP; bring-up when no inbound positions (e.g. DREB→HCO fallback). | |
| **b)** | **Challenged Open Floor (COF)** | Non-HCO skeleton steps with defensive pressure. | **16 / 12** |
| | | Examples: HCT and FCP skeleton steps (non-drive actions); all Fast Break movement. | |
| **c)** | **Drive / Attack to basket** | Any skeleton step (HCO, HCT, or FCP) with action **"drive"**. | **12 / 9** |
| **d)** | **Compressed HCO** | HCO skeleton steps that are neither drive nor shoot (cut, handle_ball, receive, pass as movement). | **12 / 9** |
| **e)** | **HCO shot attempts** | HCO step with shoot action. If there is player movement to the shot spot, use Compressed rate (16/12). If all players stationary, assign **1 game second** for the step. | **12 / 9** or **1 sec** |
| **f)** | **All other steps** | Any skeleton step not covered by (a)–(e). Open Floor is the fallback. | **20 / 15** |
| **g)** | **Pass (ball in air)** | Additive: 1 game second per 36 grid spots (Euclidean) from passer to receiver. Applied in addition to movement time for the step. | **36** (Euclidean) |

### Segment formulas

| Type | Rate | Formula |
|------|------|---------|
| **OF** | 20 / 15 | `segment_seconds = sqrt(dx^2 + dy^2) / 20` |
| **COF** | 16 / 12 | `segment_seconds = sqrt(dx^2 + dy^2) / 16` |
| **Drive** | 12 / 9 | `segment_seconds = sqrt(dx^2 + dy^2) / 12` |
| **Compressed HCO** | 12 / 9 | `segment_seconds = sqrt(dx^2 + dy^2) / 12` |
| **HCO shot (with movement)** | 16 / 12 | `segment_seconds = sqrt(dx^2 + dy^2) / 16`; stationary = 1 sec |
| **Fallback (other steps)** | 20 / 15 | `segment_seconds = sqrt(dx^2 + dy^2) / 20` |
| **Pass (ball in air)** | 36 (Euclidean) | `segment_seconds = sqrt(dx^2 + dy^2) / 36` — added to step duration when step contains a pass event. |

Pass is used in: HCO, HCT, FCP (skeleton steps with pass events); Fast Break (outlet pass); OREB Kickout (kickout pass from rebounder to PG).

## Turn Classification Matrix

1. `OPENING_TIP`: `non-CG`
2. `INBOUND_PASS` (BIP): `No Impact`
3. `SIDE_INBOUND_PASS` (SIP): `No Impact`
4. `HCO`: `Skeleton`
5. `OREB`: `non-CG`
6. `FREE_THROW`: `No Impact`
7. `FAST_BREAK`: `CG`
8. `FCP`: `Skeleton`
9. `HCT`: `Skeleton`

## System Rules
- Backend `time_elapsed`, `time_remaining`, and `clock` are authoritative.
- Frontend countdown is UX pacing only.
- No additional API calls for per-step/per-second updates.
- One turn response syncs the clock state (`time_remaining`/`clock`) at turn boundaries.
- Frontend must freeze realtime countdown when `time_elapsed = 0` (no-impact turns).
- For skeleton turns, frontend must consume backend `step_clock_seconds[]` so per-step animation time and elapsed clock time are aligned.

## Live clock end-of-turn snap
The frontend snaps the shot clock using the same pattern as the game clock: use turn’s explicit field when present (`shot_clock_remaining`), else use the contract end value **`shot_clock_end`**, else **`shot_clock_start`** (on every turn with a contract). When updating after a batch or at a turn boundary without a per-turn payload (e.g. summary update), the frontend uses the response’s top-level **`shot_clock_remaining`**. No extra backend fields; reset and shot-clock violation remain backend-only. The frontend does not implement reset or SIP→30 logic; it displays only values sent by the backend (turn or response). See `clock_sync_system.md` §9.

## Implementation Plan

### Phase 1: Backend Time Elapsed Derivation (SS&S Source of Truth)
Goal: compute `time_elapsed` on backend for every turn using the clock category rules.

1. Add a centralized clock-time resolver in backend turn resolution flow.
2. Route each turn through the resolver based on turn classification:
- `Skeleton`: per-step `random.randint(1,5)`, sum to resolution point, cap at `30`.
- `CG`: segment formula sum, round once at end, cap at `30`.
- `non-CG`: single `random.randint(1,5)`.
- `No Impact`: `0`.
3. Ensure CG uses round-at-end:
- `total_seconds = sum(segment_seconds)`
- `time_elapsed = min(30, round(total_seconds))`
4. Keep all existing clock decrement mechanics unchanged after `time_elapsed` is set:
- backend continues to update `time_remaining` and formatted `clock` as today.
5. Include derived `time_elapsed` in turn payload (already standard) for frontend use and debugging.
6. For skeleton turns, include per-step timing contract fields in payload:
- `step_clock_seconds[]`
- `resolution_step_index`
- `executed_step_count`

### Phase 2: Frontend Real-Time Countdown Module
Goal: add UX countdown that follows gameplay without changing backend authority.

1. Add `gameClock` module in frontend:
- initialize/start/pause/resume/stop/sync APIs.
2. Clock display cadence (temporary global setting):
- visible `1` game-second decrement every `700ms`.
3. Wire into gameplay scene lifecycle:
- initialize from authoritative backend time at scene start.
- pause/resume with gameplay pause conditions.
- stop/cleanup on scene teardown/navigation.
4. Use reason-based pause tokens so multiple pause causes do not conflict:
- `user_pause`: controlled by Pause/Resume button.
- `no_impact_turn`: applied during no-impact turns, removed on impact turns.
- Clock runs only when no pause tokens are active.
5. Keep existing scoreboard updates; add sync call at turn boundaries using backend `time_remaining`.

### Phase 3: Animation Synchronization
Goal: align visual countdown progression with movement/action progression.

1. Skeleton turns:
- use backend `step_clock_seconds[]` per executed step.
- apply `step_budget_ms = step_clock_seconds[i] * clock_second_ms` per step.
- animate movement at normal distance-based speed.
- hold remaining step time when movement finishes early.
- clip non-ball-handler movement at boundary if movement would exceed budget.
- extend step if ball-handler movement exceeds budget.
- keep backend turn-end sync as guardrail only (should be near no-op when aligned).
2. CG turns:
- use movement segments for animation timing and clock progression.
3. non-CG turns:
- treat as one phase for countdown progression.
4. No Impact turns:
- no decrement animation (clock remains static during turn).

### Phase 4: Validation and Tuning
Goal: ensure correctness, responsiveness, and stable UX.

1. Functional validation:
- each turn type produces expected `time_elapsed`.
- no-impact turns always produce `0`.
- CG rounding behaves as expected (example `2.24 -> 2`).
2. Integration validation:
- frontend countdown always re-syncs to backend on turn completion.
- timeout/foul-out/quarter transitions do not leak timers.
3. Performance validation:
- no additional API volume.
- no visible animation stutter attributable to countdown logic.
4. Tuning pass:
- keep temporary `700ms` cadence now.
- later split cadence by speed settings (`Normal`, `Fast`, `Super Fast`).

## Acceptance Criteria
- Every simulated turn has deterministic category-based `time_elapsed` logic applied on backend.
- `Skeleton` and `CG` turns never exceed `30` seconds elapsed.
- CG (Fast Break) calculation uses COF rate: `segment_seconds = sqrt(dx^2 + dy^2) / 18`; see Movement rates. Round-at-end and cap apply.
- `INBOUND_PASS`, `SIDE_INBOUND_PASS`, and `FREE_THROW` always return `time_elapsed = 0`.
- Frontend countdown runs continuously during active play, pauses correctly, and syncs at turn boundaries.
- No increase in backend/API call frequency.

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
- Frontend remains presentation clock; click capture prevents drift at timeout boundary.
- This reconciliation is surgical and only applies on timeout-click save path.

## Shot Clock Rules

Whenever the game clock is running, the shot clock runs, with one exception.

**Exception — shot attempt:** When a shot is attempted, the shot clock **stops** at that moment (in game time). The game clock keeps running for the rest of the turn. The shot clock **restarts** (resets to 30 and begins running) as follows:

- **Made shot, no shooting foul** → Next turn is BIP. Shot clock restarts when the receiver **receives the inbound pass** on that BIP turn.
- **Miss, offensive rebound** → Next turn is OREB (kickout, putback attempt, etc.). Shot clock restarts when the ball is **attached to the rebounder** on that OREB turn.
- **Miss, defensive rebound** → DREB occurs within the same shot-attempt turn. Shot clock restarts when the ball is **attached to the rebounding player** (at the DREB event) in that same turn.
- **Made or missed with shooting foul (free throws)** → After the final free throw: if the final FT is a **make**, shot clock restarts when the receiver receives the inbound on the following BIP turn; if the final FT is a **miss**, shot clock restarts when the ball is attached to the rebounder (on the rebound that follows).

### Backend: Shot clock derivation

The backend does **not** track shot clock independently. For each turn it derives shot clock end as follows:

1. **Current turn’s contract**
   - **Game clock:** `game_seconds_elapsed = clock_start - clock_end` (full turn). The game clock always uses this full elapsed value.
   - **Shot clock (non–shot-attempt turns):** `shot_clock_end = shot_clock_start - game_seconds_elapsed`, clamped to 0 (same as game clock delta).
   - **Shot clock (shot-attempt turns):** The shot clock **stops at the moment of the shot**. The backend computes `game_seconds_at_shot` = sum of `step_clock_seconds[0 .. resolution_step_index]` (capped by game/shot remaining). Then `shot_clock_end = shot_clock_start - game_seconds_at_shot`, clamped to 0. The rest of the turn does not reduce the shot clock further.
   - Shot-attempt turn = `result_type` in MAKE, MISS, BLOCK, or FOUL with free throws / `next_play_type` FREE_THROW. When `step_clock_seconds` and `resolution_step_index` are missing (e.g. some non-skeleton paths), the backend falls back to using full `game_seconds_elapsed` for that turn.
   - The **clock contract** attached to the turn uses this derived `shot_clock_end` so the frontend animates from `shot_clock_start` to `shot_clock_end` during the turn.

2. **Reset only affects the next turn**
   - Reset logic (make, miss with possession change, steal, dead ball, etc.) must **not** change the current turn’s `shot_clock_end`.
   - After the contract is attached, the backend sets `game_state["shot_clock_remaining"] = 30` (or min(30, time_remaining)) so that the **next** turn’s `shot_clock_start` is 30.
   - Order of operations: compute derived `shot_clock_end` → attach contract (so current turn shows start→end) → then, if reset, set game_state for next turn to 30.

3. **Shot clock at 0**
   - If the derived `shot_clock_end` would be 0 and the turn is in a clock-enforced state (HCO, FCP, HCT, FAST_BREAK), the backend triggers shot clock violation / forced shot logic instead of using that result.

### Shot clock reset instances

1. All shot attempts — reset at rim hold of make or miss; shot clock restarts when game clock restarts.
2. Offensive foul.
3. Defensive foul.
4. Steal.
5. Dead ball turnover.
6. Shot clock violation.

### Shot clock carryover between turns

1. FCP/HCT to HCO (with no foul or turnover in between).
2. Steal to HCO (with no foul or turnover in between).
3. OREB Kickout to HCO (with no foul or turnover in between).


**Shot Attempt or Shot Clock Violation**
When we reach the point of a potential Shot Clock Violation

chemistry = offense team's chemistry value (7-25)
discipline = offense team's discipline value (-10, 10)
intelligence = int(ball handler' IQ attribute / 4) (0-25)
*Note you don't need to use these exact variable names in the code, I'm just using them as placeholder in the documentation to commuicate intent

60 + chemistry + discipline + intelligence = violation_threshold
x = random.randint(1, 100)
if x > violation_threshold, violation = True, else shot attempt = True

if shot attempt, the ball handler shoots from his location at the point the turn ends
- add 100 to the shot threshold when calculating shot success

## Second Chance System (Motion only)

When a **Motion** HCO turn would hit shot clock 0, the offense gets one chance to “recalibrate” to an earlier step and take a normal shot instead of a violation or shot-at-1.

**When it runs:** Only for Motion plays. Only when the shot clock would reach 0 during the turn (same point as the violation/shot-at-1 decision). If the violation step index is &lt; 3, recalibration is skipped (no valid earlier step).

**Roll:**
- `recalibration_score = (chemistry × 5) + (discipline × 3)` (chemistry 7–25, discipline -10–10).
- `die_roll = random.randint(1, 100)`.
- If `die_roll < recalibration_score` → recalibrate; else → normal violation/shot-at-1 logic.

**Recalibration:** Pick a random step index in **[2, violation_step − 1]**. Resolve the motion shot from that step (same shot-type and execution logic as normal motion). Replace the turn’s skeleton with that shot sequence; game and shot clock elapse to the new shot. No new shot execution code—existing `resolve_motion_offense_shot` is called with a forced step index.

**Location:** `BackEnd/engine/phase_resolution.py` — shot clock block in `resolve_half_court_offense_logic`, and downstream motion shot block when `_motion_shot_recalibrated` is set. See `docs/To Do/_motion_play_decision.md` for the original spec.

