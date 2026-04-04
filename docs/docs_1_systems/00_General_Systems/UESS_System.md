# Universal End-State Sync (UESS) System

## Purpose

Define the canonical runtime contract that keeps backend movement/decision logic, game-clock expiration, and frontend sprite/ball animation fully synchronized.

This file is the system-level source of truth for UESS cards.
Implementation sequencing and migration notes remain in `docs/To Do/Unified_Animation.md`.

## UESS Launch Status Board

Status key:

- `launch_ready`: approved for prototype launch in current scope.
- `proceed_with_polish`: functionally stable; non-blocking polish remains.
- `in_progress`: implemented or partially implemented, but not yet locked for launch.

Current status (as of 2026-03-26; consolidated prototype passes: `contractErrors=0`, `clockReconRows>=30`):

- `clock_authority_contract`: `launch_ready`
  - notes: launch decision recorded; polish backlog remains non-blocking.
- `ownership_pass_lifecycle_contract`: `proceed_with_polish`
  - notes: backend/API coverage is strong; runtime observability ergonomics remain polish.
- `inbound_unit_completion_contract` (`sip`/`bip`): `proceed_with_polish`
  - notes: contract wiring is in place; telemetry tap reliability is tracked as tooling polish.
- `hco_core_units` (`lead_in`, `step_movement`, `step_pass`, `resolution`, `out`): `proceed_with_polish`
  - notes: strict-path coverage is broad; known edge-case hard-overrun remains tracked in backlog.
- `pressure_units` (`fcp`/`hct` step + resolution + out): `proceed_with_polish`
  - notes: parity wiring validated in consolidated warn-mode pass; keep runtime sampling in normal dev flow.
- `fast_break_phase_contract`: `proceed_with_polish`
  - notes: Wave 2 trigger-lock runtime parity is wired (`fb.lead_in/*`, `fb.phase/*`, `fb.out.to_*`); keep branch-level polish/backlog tracking.
- `oreb_phase_contract`: `proceed_with_polish`
  - notes: decision/action contracts are active with mode gating; keep branch-behavior cleanup in polish backlog.
- `free_throw_phase_contract`: `proceed_with_polish`
  - notes: attempt + sequence-control contracts are active; continue monitoring multi-FT edge flows.
- `timeout_phase_contract`: `proceed_with_polish`
  - notes: pause/resume barrier contracts are active; maintain popup/navigation UX polish items separately.
- `opening_tip_phase_contract`: `proceed_with_polish`
  - notes: jump/control/transition contracts are active; keep lightweight runtime sampling in standard QA.

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
- Clock authority rollout default is `warn` for local development; use `observe` only when explicitly gathering baseline telemetry.

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
- Resets to `30` and starts on all BIP/SIP receive events.
- Resets to `30` and starts when rebounder controls ball after missed FG or missed FT.
- Explicitly allowed state: game clock running while shot clock is stopped during shot flight before rebound control.

End-of-quarter basket validity:

- Basket counts if shot detaches before game clock reaches zero.
- Basket does not count if shot detaches at the exact period-zero boundary (`shot_detach_timestamp == period_zero_timestamp`).
- Backend shot selection policy should bias release to occur before period-zero whenever a legal pre-buzzer attempt is intended.

Made-basket dead-ball window shot clock policy:

- On made basket, shot clock resets to `30` during dead-ball window and remains stopped until inbound receive.

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
- Frontend does not use clock-contract elapsed fallback when `clock_event_ledger` is missing; it emits `clock_contract_missing_ledger` and enforces by mode (`observe|warn|throw`).
- For `BATCH` turn wrappers, backend mirrors the first sub-turn clock contract fields at wrapper level to keep top-level turn shape complete while sub-turns remain authoritative for sequencing.
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
- `window.UESS_CLOCK_ELAPSED_AUTHORITY = "legacy" | "ledger"` (default backend: `ledger`)
- Frontend propagates `window.UESS_CLOCK_ELAPSED_AUTHORITY` to backend on each `/api/simulate-turn` request via `uess_clock_elapsed_authority`, and backend applies it to `game_state.uess_clock_elapsed_authority` when valid.
- `window.UESS_CLOCK_RECON_TOLERANCE_SECONDS = <number>`
- Frontend propagates `window.UESS_CLOCK_RECON_TOLERANCE_SECONDS` to backend on each `/api/simulate-turn` request via `uess_clock_recon_tolerance_seconds`, and backend applies it to `game_state.uess_clock_recon_tolerance_seconds` when valid/non-negative.
- Backend ownership contract mode: `game_state.uess_ownership_contract_mode = "off" | "observe" | "warn"` (default: `warn`).
- Frontend can override ownership mode per turn via `window.UESS_OWNERSHIP_CONTRACT_MODE`, propagated as `uess_ownership_contract_mode` on `/api/simulate-turn`.
- Turn payload exposes both `uess_ownership_contract_mode` (top-level) and `uess_ownership_contract.mode` (contract-level) for parity/debug clarity.
- Runtime ownership debug mirrors/helpers:
  - `window.__OWNERSHIP_CONTRACT_LAST__`, `window.__OWNERSHIP_CONTRACT_BUFFER__`
  - `window.__OWNERSHIP_CONTRACT_SUMMARY_LAST__`, `window.__OWNERSHIP_CONTRACT_SUMMARY_BUFFER__`
  - `showOwnershipContractConfig()`, `getOwnershipContractSummaryLatest(n)`, `clearOwnershipContractBuffers()`
  - `window.UESS_OWNERSHIP_SUMMARY_EVERY` controls summary cadence (default `10` rows).
- `window.UESS_CLOCK_RECON_SUMMARY_EVERY = <int>` (default: `10`)
- `window.UESS_CLOCK_RECON_WARN_MIN_ROWS = <int>` (default: `40`)
- `window.UESS_CLOCK_RECON_WARN_OUT_OF_TOLERANCE_RATE_MAX = <float>` (default: `0.02`)
- `window.UESS_CLOCK_RECON_WARN_AVG_ABS_DELTA_SECONDS_MAX = <float>` (default: `0.25`)
- `window.UESS_CLOCK_RECON_WARN_MAX_ABS_DELTA_SECONDS_MAX = <float>` (default: `1.0`)
- `window.UESS_OWNERSHIP_SUMMARY_EVERY = <int>` (default: `10`)
- `window.UESS_OWNERSHIP_WARN_MIN_ROWS = <int>` (default: `40`)
- `window.UESS_OWNERSHIP_WARN_INVALID_APPLICABLE_RATE_MAX = <float>` (default: `0.02`)
- `window.UESS_OWNERSHIP_WARN_MISSING_CONTRACT_ROWS_MAX = <int>` (default: `0`)
- `window.UESS_INBOUND_CONTRACT_MODE = "off" | "observe" | "warn" | "throw"` (default: `warn`)
- `window.UESS_INBOUND_SETUP_MAX_GAME_SECONDS = <number>` (default: `4`)
- `window.UESS_INBOUND_PASS_MAX_GAME_SECONDS = <number>` (default: `2`)
- Optional per-family overrides:
  - `window.UESS_SIDE_INBOUND_SETUP_MAX_GAME_SECONDS`
  - `window.UESS_SIDE_INBOUND_PASS_MAX_GAME_SECONDS`
  - `window.UESS_BASELINE_INBOUND_SETUP_MAX_GAME_SECONDS`
  - `window.UESS_BASELINE_INBOUND_PASS_MAX_GAME_SECONDS`
- `window.UESS_PRESSURE_STEP_CONTRACT_MODE = "off" | "warn" | "throw"` (default: `warn`)
- Optional pressure-step tunables:
  - `window.UESS_PRESSURE_STEP_MOVEMENT_TOLERANCE_PX`
  - `window.UESS_PRESSURE_STEP_MOVEMENT_MAX_GAME_SECONDS`
  - `window.UESS_PRESSURE_STEP_CLOCK_JITTER_ABS_SECONDS`
  - `window.UESS_PRESSURE_STEP_CLOCK_JITTER_RATIO`
  - `window.UESS_PRESSURE_STEP_PASS_CLOCK_JITTER_ABS_SECONDS`
  - `window.UESS_PRESSURE_STEP_PASS_CLOCK_JITTER_RATIO`
- `window.UESS_OREB_CONTRACT_MODE = "off" | "observe" | "warn" | "throw"` (default: `observe`)
- `window.UESS_OREB_DECISION_MAX_GAME_SECONDS = <number>` (default: `2`)
- `window.UESS_OREB_ACTION_MAX_GAME_SECONDS = <number>` (default: `3`)
- `window.UESS_FT_CONTRACT_MODE = "off" | "observe" | "warn" | "throw"` (default: `observe`)
- `window.UESS_FT_ATTEMPT_MAX_GAME_SECONDS = <number>` (default: `3`)
- `window.UESS_FT_SEQUENCE_MAX_GAME_SECONDS = <number>` (default: `2`)
- `window.UESS_TIMEOUT_CONTRACT_MODE = "off" | "observe" | "warn" | "throw"` (default: `warn`)
- `window.UESS_TIMEOUT_PAUSE_BARRIER_MAX_GAME_SECONDS = <number>` (default: `1`)
- `window.UESS_TIMEOUT_RESUME_PREP_MAX_GAME_SECONDS = <number>` (default: `6`)
- `window.UESS_TIP_CONTRACT_MODE = "off" | "observe" | "warn" | "throw"` (default: `observe`)
- `window.UESS_TIP_JUMP_MAX_GAME_SECONDS = <number>` (default: `2`)
- `window.UESS_TIP_CONTROL_MAX_GAME_SECONDS = <number>` (default: `2`)
- `window.UESS_FB_CONTRACT_MODE = "off" | "observe" | "warn" | "throw"` (default: `observe`)
- `window.UESS_FB_LEAD_IN_MAX_GAME_SECONDS = <number>` (default: `4`)
- `window.UESS_FB_PHASE_MAX_GAME_SECONDS = <number>` (default: `6`)
- `window.UESS_FB_OUT_MAX_GAME_SECONDS = <number>` (default: `2`)

Debug helpers currently installed in local runtime:

- `showClockReconConfig()`
- `getClockReconSummaryLatest(n = 5)`
- `clearClockReconBuffers()`

Mode semantics:

- `observe`: emit reconciliation telemetry only (frontend + backend; no enforcement).
- `warn`: emit telemetry and log warning on reconciliation failure (frontend + backend).
- `throw`: emit telemetry and hard-fail turn processing on reconciliation failure (frontend + backend).
- `off`: disable frontend clock reconciliation telemetry/enforcement; backend still emits reconciliation payload fields but skips warn/throw enforcement.

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

1. `rows >= UESS_CLOCK_RECON_WARN_MIN_ROWS` (default `40`)
2. `outOfToleranceRate <= UESS_CLOCK_RECON_WARN_OUT_OF_TOLERANCE_RATE_MAX` (default `0.02`)
3. `averageAbsDeltaSeconds <= UESS_CLOCK_RECON_WARN_AVG_ABS_DELTA_SECONDS_MAX` (default `0.25`)
4. `maxAbsDeltaSeconds <= UESS_CLOCK_RECON_WARN_MAX_ABS_DELTA_SECONDS_MAX` (default `1.0`)

Runtime summary payloads include:

- `thresholds`
- `hasEnoughRows`
- `meetsWarnPromotionGate`

If `meetsWarnPromotionGate` is false, runtime emits `clock_contract_reconciliation_threshold_breach`.

## Ownership Observe -> Warn Promotion Gate

Promotion from ownership `observe` to `warn` requires all of the following on ownership summaries:

1. `rows >= UESS_OWNERSHIP_WARN_MIN_ROWS` (default `40`)
2. `invalidApplicableRate <= UESS_OWNERSHIP_WARN_INVALID_APPLICABLE_RATE_MAX` (default `0.02`)
3. `missingContractRows <= UESS_OWNERSHIP_WARN_MISSING_CONTRACT_ROWS_MAX` (default `0`)

Runtime ownership summary payloads include:

- `thresholds`
- `hasEnoughRows`
- `meetsWarnPromotionGate`

If `meetsWarnPromotionGate` is false, runtime emits `ownership_contract_threshold_breach`.

## Inbound Unit-Completion Contract (SIP/BIP Families)

Runtime now enforces unit-completion semantics for inbound families:

- `sip.lead_in.entry` (`SIDE_INBOUND`)
- `sip.phase.setup_positions` (`SIDE_INBOUND`)
- `sip.phase.pass` (`SIDE_INBOUND`)
- `sip.out.to_*` (`SIDE_INBOUND`)
- `bip.lead_in.entry` (`BASELINE_INBOUND`)
- `bip.phase.setup_positions` (`BASELINE_INBOUND`)
- `bip.phase.pass` (`BASELINE_INBOUND`)
- `bip.out.to_*` (`BASELINE_INBOUND`)

Contract telemetry branch: `inbound_unit_contract`.

At minimum, runtime emits:

- `unit_completion_contract_validated`
- `unit_completion_contract_violation`
- `inbound_contract_owner_missing`
- `inbound_contract_owner_invalid`
- `inbound_contract_pass_in_flight`
- `inbound_contract_clock_overrun`

## Pressure Skeleton Step Contract (FCP/HCT Families)

Runtime now applies unit-completion step validation to pressure skeleton families:

- `fcp.step[n].movement` and `fcp.step[n].pass`
- `hct.step[n].movement` and `hct.step[n].pass`
- `fcp.resolution` / `hct.resolution`
- `fcp.out.to_*` / `hct.out.to_*`

Telemetry is emitted under pressure branch/event labels:

- `branchKind: "pressure_step_movement"`
- `pressure_step_movement_*` and `pressure_step_pass_*` event families
- shared completion contract events (`unit_completion_contract_validated`, `unit_completion_contract_violation`)

## OREB Phase Contract (Lead-In + Decision + Action + Out)

Runtime now emits/enforces unit-completion contracts for OREB branch phases in `ShotAnimationSystem` and `animateGameTurns`:

- `oreb.lead_in.from_miss`
- `oreb.phase.hold`
- `oreb.phase.decision`
- `oreb.phase.kickout_pass`
- `oreb.phase.putback_attempt`
- `oreb.phase.putback_rebound_resolution`
- `oreb.out.to_*`

Telemetry branch: `oreb_phase_contract`, including:

- `unit_completion_contract_validated`
- `unit_completion_contract_violation`
- `oreb_phase_clock_overrun`
- `oreb_phase_putback_failed`

## Free Throw Phase Contract

Runtime now emits/enforces unit-completion contracts for FT phases in `FreeThrowAnimationSystem`:

- `ft.lead_in.entry`
- `ft.phase.attempt[n]`
- `ft.phase.sequence_control`
- `ft.out.to_*`

Telemetry branch: `ft_phase_contract`, including:

- `unit_completion_contract_validated`
- `unit_completion_contract_violation`
- `ft_phase_clock_overrun`

## Timeout Phase Contract

Runtime now emits/enforces unit-completion contracts for timeout handling in `AnimationEngine`:

- `timeout.phase.pause_barrier`
- `timeout.phase.resume_prepare`
- `timeout.out.to_next`

Telemetry branch: `timeout_phase_contract`, including:

- `unit_completion_contract_validated`
- `unit_completion_contract_violation`
- `timeout_phase_clock_overrun`

## Opening Tip Phase Contract

Runtime now emits/enforces unit-completion contracts for opening tip handling in `AnimationEngine`:

- `tip.phase.jump`
- `tip.phase.control`
- `tip.out.to_hco`

Telemetry branch: `tip_phase_contract`, including:

- `unit_completion_contract_validated`
- `unit_completion_contract_violation`
- `tip_phase_clock_overrun`

## Fast Break Phase Contract

Runtime now emits/enforces unit-completion contracts for Fast Break orchestration in `fastBreak.js`:

- `fb.lead_in.from_hco_steal`
- `fb.lead_in.from_dreb_release`
- `fb.phase.entry_burst`
- `fb.phase.outlet`
- `fb.phase.shot_attempt`
- `fb.phase.defensive_stop`
- `fb.phase.rebound_resolution`
- `fb.out.to_*`

Telemetry includes:

- `unit_completion_contract_validated`
- `unit_completion_contract_violation`
- `fb_phase_clock_overrun`

## Clock Sync Launch Status

- **Status:** Launch-ready for prototype usage.
- **Decision date:** 2026-03-26.
- **Go/No-go:** **GO** for clock-sync scope with follow-on polish.
- **Scope covered by this decision:**
  - Event-ledger-based FE/BE elapsed parity and tolerance enforcement.
  - Mode propagation (`observe|warn|throw|off`) and reconciliation telemetry rollups.
  - Ledger-authority elapsed default (`ledger`) and continuity guard across turn boundaries.
- **Known polish backlog (non-blocking):**
  - Intermittent transition presentation polish on select rebound-derived HCO sequences.
  - Debug helper ergonomics/initialization reliability in fresh browser sessions.
  - Remaining warning cleanup and logging severity normalization tracked in implementation backlog.

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

---

## Temporary Implementation Plan: Universal Clock Authority

Temporary note: this section is an implementation work plan, not permanent system documentation. Remove it once rollout is complete and the contract is fully enforced.

### Goal

Implement one universal event-driven clock authority across all turn families so backend `turn.time_elapsed` and frontend animated elapsed derive from the same live-clock semantics.

### Locked Rollout Decisions

- Keep `turn.time_elapsed` as the public field name.
- Emit `clock_event_ledger` on every turn for now.
- Game clock stops on made basket.
- Game clock continues during missed-shot flight unless a later explicit dead-ball event stops it.
- Fouls during shot flight stop the game clock immediately.
- BIP/SIP setup is clock-dead until inbound receive.
- Timeout resume requires a fresh explicit restart event; there is no implicit clock restart.

### Work Plan

1. Lock backend clock event production for every turn family.
   - Ensure every turn result emits `clock_event_ledger`.
   - Ensure event rows use the canonical schema:
     - `event_id`
     - `turn_id`
     - `event_type`
     - `reason`
     - `game_clock_before`
     - `game_clock_after`
     - `shot_clock_before`
     - `shot_clock_after`
     - `timestamp_game_seconds`
   - Ensure minimum event coverage exists on every turn:
     - `game_clock_start` when live-ball clock actually begins
     - `game_clock_stop` when live-ball clock actually stops
     - `shot_clock_start` when possession clock actually begins
     - `shot_clock_stop` when possession clock actually stops
     - `shot_clock_reset` when policy resets the possession clock
     - `period_end`, `basket_counted`, `possession_committed` where applicable

2. Replace legacy backend `time_elapsed` derivation with ledger-derived elapsed.
   - Compute backend elapsed by summing live game-clock intervals from `game_clock_start` / `game_clock_stop` semantics.
   - Do not let branch-local phase timing heuristics override ledger-derived elapsed.
   - Preserve current output field name: `turn.time_elapsed`.

3. Encode universal turn-family rules into ledger production.
   - BIP/SIP:
     - game clock stopped during setup
     - game clock starts on inbound receive
     - shot clock resets to `30` and starts on inbound receive
   - HCO / OREB / FAST_BREAK / FCP / HCT shot attempts:
     - shot clock stops on shot detach
     - game clock continues during shot flight unless an explicit stop event occurs
   - Made basket:
     - game clock stops on made basket
     - shot clock resets to `30` during dead-ball window and remains stopped until inbound receive
   - Missed FG / missed FT:
     - shot clock resets to `30` and starts when rebounder controls the ball
   - Fouls:
     - game clock stops immediately, including foul during shot flight
   - Timeout:
     - game clock stops immediately on timeout
     - resume path does not restart clock until the next explicit restart event
   - Opening tip:
     - game clock starts when a player first controls the tip

4. Keep precedence deterministic everywhere.
   - Apply the existing precedence rules consistently in backend ledger generation:
     1. `period_end`
     2. `foul | dead_ball | timeout`
     3. `shot_detach`
     4. `rebound_controlled`
     5. `inbound_received`
     6. `basket_counted`
   - If precedence overrides a branch-local expectation, emit telemetry for that override.

5. Make frontend derive elapsed from the same ledger semantics.
   - Frontend reads `clock_event_ledger` from every turn.
   - Frontend derives elapsed from ledger rows rather than inferring from branch timing.
   - Frontend reconciliation compares:
     - backend ledger-derived elapsed
     - frontend ledger-derived elapsed
     - legacy public field `turn.time_elapsed`

6. Run rollout in `observe` mode first.
   - Default `window.UESS_CLOCK_AUTHORITY_MODE = "warn"`.
   - Emit reconciliation telemetry on every turn.
   - Track:
     - pass/fail counts
     - average absolute delta
     - max absolute delta
     - out-of-tolerance rate
     - result-type / turn-family clustering of failures

7. Validate full-family coverage and remove hidden legacy assumptions.
   - Verify every turn family emits ledger rows:
     - `HCO`
     - `HCT`
     - `FCP`
     - `FAST_BREAK`
     - `OREB`
     - `FREE_THROW`
     - `SIDE_INBOUND`
     - `BASELINE_INBOUND`
     - `OPENING_TIP`
     - `TIMEOUT`
   - Identify any family still depending on:
     - implicit restart timing
     - timeout-only elapsed assumptions
     - branch-local clock mutation that is not represented in the ledger

8. Promote only after observe metrics pass the gate.
   - Promote `observe -> warn` only when:
     - `rows >= UESS_CLOCK_RECON_WARN_MIN_ROWS`
     - `outOfToleranceRate <= UESS_CLOCK_RECON_WARN_OUT_OF_TOLERANCE_RATE_MAX`
     - `averageAbsDeltaSeconds <= UESS_CLOCK_RECON_WARN_AVG_ABS_DELTA_SECONDS_MAX`
     - `maxAbsDeltaSeconds <= UESS_CLOCK_RECON_WARN_MAX_ABS_DELTA_SECONDS_MAX`
   - Promote `warn -> throw` only after repeated stable runs with no unresolved contract exceptions.

### Current Execution Order

1. Confirm and complete backend `clock_event_ledger` coverage on every turn family.
2. Confirm backend `turn.time_elapsed` is ledger-derived everywhere, not partially heuristic.
3. Confirm frontend reconciliation is reading the ledger everywhere and not silently falling back.
4. Run observe-mode validation across representative live scenarios:
   - made basket
   - missed shot + rebound
   - foul during shot flight
   - BIP
   - SIP
   - timeout
   - opening tip
   - HCO -> OREB
   - HCO -> FAST_BREAK
   - FAST_BREAK -> HCO
5. Fix any reconciliation drift or missing-event families.
6. Promote to `warn` only after the observe gate passes.

### Targeted Clock Hardening Test Command

Run the current backend clock-authority hardening suites in one command:

`bash scripts/run_uess_hardening_tests.sh`

### Definition of Done

- Every turn emits valid `clock_event_ledger`.
- Backend `turn.time_elapsed` is universally ledger-derived.
- Frontend derives elapsed from the same ledger semantics.
- BIP/SIP, shot-flight, made-basket, rebound-control, foul, timeout, and tipoff rules behave as locked above.
- Observe-mode reconciliation passes promotion thresholds.
- No remaining turn family depends on undocumented implicit clock behavior.
