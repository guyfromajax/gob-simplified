# Universal End-State Sync (UESS) System

## Purpose

Define the canonical runtime contract that keeps backend movement/decision logic, game-clock expiration, and frontend sprite/ball animation fully synchronized.

This file is the system-level source of truth for UESS cards.
Implementation sequencing and migration notes remain in `docs/To Do/Unified_Animation.md`.

## UESS Contract Fields (Universal)

Every execution unit must define:

- `authority`
- `clock`
- `completion`
- `failure_policy`
- `ownership`

The schema is universal; field values are unit-specific.

## Runtime Policy Hierarchy

When policies overlap, resolve in this order:

1. Explicit clock events + precedence rules (gameplay authority)
2. Unit completion contracts (`advance_trigger`, `visual_settle_trigger`)
3. Unit transition budgets (guardrails and diagnostics)

This prevents conflict between gameplay clock semantics and per-unit timing budgets.

## Local Dev Strictness Policy

- Unit-completion contracts default to `throw` for UESS-target units.
- Strict-path degraded fallback is disallowed unless explicitly documented by unit.
- Unit budget overrun policy in local dev: hard-fail.
- Ownership commit timing for pass actions: `pass receipt`.
- Turn-boundary elapsed guard source for runtime checks: `min(wall_elapsed_ms, real_time_elapsed_ms + guard_slack_ms)`.
- Clock authority rollout defaults to observe mode until explicitly promoted.

## HCO Turn Elapsed Authority (Observe Rollout)

- **Runtime flag:** `window.UESS_HCO_ELAPSED_AUTHORITY`
  - `observe` (default): compute and emit telemetry only.
  - `off`: disable HCO elapsed authority telemetry.
- **Observed units:** `lead_in`, `step_movement`, `step_pass`, `resolution`, `transition_out`.
- **Elapsed source:** contract-bounded turn elapsed (`min(wall_elapsed_ms, real_time_elapsed_ms + guard_slack_ms)`), sampled at unit boundaries.
- **Telemetry event:** `hco_uess_elapsed_observe`
  - `hco_uess_elapsed_game_seconds`
  - `hco_uess_elapsed_ms`
  - `hco_uess_elapsed_unit_breakdown_game_seconds`
  - `hco_uess_elapsed_unit_breakdown_ms`
- **Current local implementation note:** unit-boundary capture is wired for `lead_in`, `step_movement`, `step_pass`, `resolution`, and `transition_out`.

## Clock Authority Contract (Parallel to Unit Completion)

### Objective

Define one universal event-driven clock authority that keeps backend and frontend synchronized across all turn types and transition boundaries.

### Core Principle

- Unit completion controls animation progression.
- Clock authority controls game/shot clock start-stop-reset semantics.
- `turn.time_elapsed` is derived from the clock event ledger (not independently tuned).
- Transition boundaries do not implicitly pause clocks.

### Canonical Clock Ledger Schema

Each turn/transition emits an ordered ledger row with:

- `event_id`
- `turn_id`
- `event_type`
- `reason`
- `game_clock_before`
- `game_clock_after`
- `shot_clock_before`
- `shot_clock_after`
- `timestamp_game_seconds`

Minimum event types:

- `game_clock_start`
- `game_clock_stop`
- `shot_clock_start`
- `shot_clock_stop`
- `shot_clock_reset`
- `period_end`
- `basket_counted`
- `possession_committed`

### Current Gameplay Policy (Locked)

Game clock:

- Stops immediately on foul (including foul during shot in flight).
- Stops immediately on dead-ball turnover.
- Stops immediately on timeout.
- Stops immediately at quarter end.
- Stops on made basket.
- Does not run during timeout turns, free throw turns, BIP/SIP setup turns, or opening tip setup.
- Starts when:
  - inbound receiver receives BIP/SIP pass,
  - a player controls opening tip,
  - rebounder controls rebound after missed free throw.

Shot clock:

- Stops when a shot detaches from the shooter sprite.
- Stops at shot clock zero.
- Stops immediately on dead-ball turnover or foul.
- Resets to `35` and starts on all BIP/SIP receive events.
- Resets to `35` and starts when rebounder controls ball after missed FG or missed FT.
- Explicitly allowed state: game clock running while shot clock is stopped during shot flight before rebound control.

End-of-quarter basket validity:

- Basket counts if shot detaches before game clock reaches zero.
- Basket does not count if shot detaches at the exact period-zero boundary (`shot_detach_timestamp == period_zero_timestamp`).
- Backend shot selection policy should bias release to occur before period-zero whenever a legal pre-buzzer attempt is intended.

Made-basket dead-ball window shot clock policy:

- On made basket, shot clock resets to `35` during dead-ball window and remains stopped until inbound receive.

### Event Precedence (Deterministic)

When multiple events share the same frame boundary, apply in this order:

1. `period_end`
2. `foul | dead_ball | timeout`
3. `shot_detach`
4. `rebound_controlled`
5. `inbound_received`
6. `basket_counted`

If policy and event order conflict, precedence wins and telemetry must capture the override.

### Backend/Frontend Reconciliation

- Backend computes `turn.time_elapsed` by summing live game-clock intervals from ledger events.
- Frontend derives elapsed from the same ledger semantics while animating.
- At turn close validate:
  - `abs(fe_derived_elapsed - be_time_elapsed) <= tolerance`
  - game clock parity
  - shot clock parity
- Default tolerance targets:
  - `observe`: `<= 0.10s`
  - `warn`: `<= 0.05s`
  - `throw`: `<= 0.02s`

### Transition Continuity Requirement

Clock evaluation must continue through turn transitions; only explicit stop events pause clocks.

Required continuity examples:

- `HCO -> OREB`
- `HCO -> FAST_BREAK`
- `HCO -> HCO` (possession change)
- `FAST_BREAK -> OREB`
- `FAST_BREAK -> HCO` (possession change)

### Rollout Flags

- `window.UESS_CLOCK_AUTHORITY_MODE = "observe" | "warn" | "throw" | "off"`
- Frontend propagates `window.UESS_CLOCK_AUTHORITY_MODE` to backend on each `/api/simulate-turn` request via `uess_clock_authority_mode`, and backend applies it to `game_state.uess_clock_authority_mode` when valid.
- `window.UESS_CLOCK_RECON_TOLERANCE_SECONDS = <number>`
- `window.UESS_CLOCK_RECON_SUMMARY_EVERY = <int>` (default: `10`)
- `window.UESS_CLOCK_RECON_WARN_MIN_ROWS = <int>` (default: `50`)
- `window.UESS_CLOCK_RECON_WARN_OUT_OF_TOLERANCE_RATE_MAX = <float>` (default: `0.02`)
- `window.UESS_CLOCK_RECON_WARN_AVG_ABS_DELTA_SECONDS_MAX = <float>` (default: `0.25`)
- `window.UESS_CLOCK_RECON_WARN_MAX_ABS_DELTA_SECONDS_MAX = <float>` (default: `1.0`)

Debug helpers currently installed in local runtime:

- `showClockReconConfig()`
- `getClockReconSummaryLatest(n = 5)`
- `clearClockReconBuffers()`

Mode semantics:

- `observe`: emit reconciliation telemetry only.
- `warn`: emit telemetry + runtime `console.warn` on reconciliation failure.
- `throw`: emit telemetry + hard-fail turn processing on reconciliation failure.
- `off`: disable frontend clock reconciliation telemetry/enforcement.

### Required Clock Telemetry

Emit at minimum:

- `clock_contract_event_applied`
- `clock_contract_precedence_override`
- `clock_contract_reconciliation_pass`
- `clock_contract_reconciliation_fail`
- `clock_contract_reconciliation_summary`
- `clock_contract_reconciliation_threshold_breach`

Each payload includes:

- `turn_id`
- `event_type`
- `reason`
- `game_clock_before`
- `game_clock_after`
- `shot_clock_before`
- `shot_clock_after`
- `be_elapsed`
- `fe_elapsed`
- `delta_seconds`

## Observe -> Warn Promotion Gate

Promotion from `observe` to `warn` requires all of the following on reconciliation summaries:

1. `rows >= UESS_CLOCK_RECON_WARN_MIN_ROWS` (default `50`)
2. `outOfToleranceRate <= UESS_CLOCK_RECON_WARN_OUT_OF_TOLERANCE_RATE_MAX` (default `0.02`)
3. `averageAbsDeltaSeconds <= UESS_CLOCK_RECON_WARN_AVG_ABS_DELTA_SECONDS_MAX` (default `0.25`)
4. `maxAbsDeltaSeconds <= UESS_CLOCK_RECON_WARN_MAX_ABS_DELTA_SECONDS_MAX` (default `1.0`)

Runtime summary payloads include:

- `thresholds`
- `hasEnoughRows`
- `meetsWarnPromotionGate`

If `meetsWarnPromotionGate` is false, runtime emits `clock_contract_reconciliation_threshold_breach`.

## Locked UESS Card: `hco.lead_in.from_dreb_outlet`

### 1) Authority

- **Primary movement authority (receiver):**
  - `dreb_outlet_pass.receiver_target { x, y }`
- **Identity authority:**
  - `dreb_outlet_pass.passer_id`
  - `dreb_outlet_pass.receiver_id`
- **Transition orientation authority:**
  - Backend receiver target orientation must match frontend transition basket convention:
    - home offense -> `HOME_RIM`
    - away offense -> `AWAY_RIM`
- **Strict-path fallback:**
  - Not allowed.
  - Missing/invalid required contract fields are contract violations.

### 2) Clock

- **Clock anchor:** transition budget
- **Clock coupling rule:** this unit must consume only its declared transition budget window.
- **Overrun handling (local dev):** hard-fail.

### 3) Completion

- **Execution mode:** `dynamic_event`
- **Advance trigger:** outlet pass received
- **Visual settle trigger:** outlet movement + pass settled
- **Ordering rule:** movement settle precedes pass execution for this unit.

### 4) Failure Policy

- **Default local strict mode:** `throw`
- **Contract violations:** fail-fast in local dev (no silent degrade in strict path).
- **Telemetry requirement:** emit explicit violation event with reason code.

### 5) Ownership

- **Owner authority at end:** outlet receiver
- **Commit timing:** on pass receipt (not pass release)

## UESS Acceptance Gates (`hco.lead_in.from_dreb_outlet`)

A unit can be marked UESS-complete only when all are true:

1. Required `dreb_outlet_pass` fields present and valid (`passer_id`, `receiver_id`, `receiver_target`).
2. Receiver target orientation matches transition basket convention.
3. Advance occurs on pass receipt; ownership commits on pass receipt.
4. No strict-path degraded fallback.
5. Clock overrun produces hard failure in local dev.
6. Backend/FE handoff positions remain within declared tolerance band.

## Locked UESS Card: `hco.step[n].movement`

### 1) Authority

- **Primary movement authority:**
  - step-level backend movement contract from `turn.animations` targets for required movers in step `n`
- **Fallback policy:**
  - degraded fallback is not valid in strict mode for required movers
  - missing required mover target is a contract violation
- **Scope note:**
  - this card governs skeleton-step offensive mover settle, not branch resolution and not the pass receipt contract itself

### 2) Clock

- **Clock anchor:** `step_clock_seconds[n]`
- **Clock coupling rule:** required mover settle must complete within the declared step budget window
- **Local runtime guardrails:**
  - `window.HCO_STEP_MOVEMENT_STRICT_CONTRACT = "throw" | "warn" | "off"`
  - `window.UESS_HCO_STEP_MOVEMENT_TOLERANCE_PX`
  - `window.UESS_HCO_STEP_MOVEMENT_MAX_GAME_SECONDS`
- **Overrun handling (local dev default):** hard-fail when strict mode resolves to `throw`

### 3) Completion

- **Execution mode:** `skeleton`
- **Advance trigger:** required movers reach step-n targets
- **Visual settle trigger:** required step-n tweens complete
- **Completion semantics:** final offensive mover settle is mandatory unless a unit-specific exception is explicitly documented
- **Telemetry contract:** emit validation success/failure through unit-completion telemetry and HCO step telemetry channels

### 4) Failure Policy

- **Default rollout:** `warn -> throw`
- **Strict-path rule:** no timeout-only completion for required mover settle
- **Violation classes currently enforced locally:**
  - tolerance breach
  - clock soft overrun / hard overrun
  - missing required movers or missing settle targets
  - unit-completion contract violation

### 5) Ownership

- **Owner authority at end:** per-step owner contract
- **Note:** this unit validates mover settle only; pass-step ownership commits are validated by `hco.step[n].pass`

## UESS Acceptance Gates (`hco.step[n].movement`)

A unit can be marked UESS-complete only when all are true:

1. Required movers are resolved from the step contract with no silent role drops.
2. All required movers finish within declared tolerance of backend targets.
3. Completion is driven by mover-settle semantics, not timeout-only fallback.
4. Step elapsed remains within declared budget and strict-mode guardrails.
5. Unit-completion validation emits clean telemetry with no strict-path degraded fallback.
6. End-of-step ownership context remains compatible with downstream pass/resolution units.

## Reuse Pattern for Other Units

- Reuse the same five-field contract structure and lifecycle.
- Define new unit-specific values only.
- Do not copy basketball-branch heuristics from this card unless they are explicitly declared as that unit's authority.

## Card Formatting Rule

At the end of every unit card, include:

- **Plain-English advance trigger:** `<one sentence>`

For `hco.lead_in.from_dreb_outlet`:

- **Plain-English advance trigger:** This unit advances when the outlet receiver receives the outlet pass.
