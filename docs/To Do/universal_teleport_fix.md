# Universal Teleport Fix (Pass Lifecycle Authority)

## Why this exists

We are seeing recurring ball teleports when a branch skips or short-circuits a pass animation, then a later phase force-attaches the ball to a new owner (usually shooter/receiver). This is a system-level consistency issue, not a one-off branch bug.

Goal: define one universal pass contract that all turn families follow so teleports cannot occur as a side effect of branch-local logic.

---

## Problem Pattern

Common failure chain:

1. Branch intends to animate a pass.
2. Pass helper exits early (missing id/target/sprite or silent skip).
3. Branch continues into shot/next phase anyway.
4. Ball is attached directly to downstream owner.
5. Viewer sees a teleport instead of pass flight.

This appears in different forms (Triangle RR feed, branch-specific lane passes, edge fallback paths), so patching each branch separately does not scale.

---

## Universal Fix Direction

### 1) Pass Contract (required vs intentional skip)

For every pass-capable phase, branch must declare one of:

- `pass_required = true`
- `pass_intentionally_skipped = true` with explicit reason

No silent fallback path.

### 2) Pass Lifecycle State Machine

Every required pass follows:

- `planned`
- `started`
- `in_flight`
- `received`
- `settled`

Lifecycle status is written to shared turn/scene state and telemetry.

### 3) Phase Gate Invariant

Before entering shot/resolve phase:

- If `pass_required`, lifecycle must be `received` (or `settled` if strict mode).
- If not satisfied, branch must not continue as if pass completed.

### 4) Single Attach Authority

Receiver ownership attach should come from pass lifecycle completion, not ad hoc branch-level attaches.

Only explicit `pass_intentionally_skipped` paths may attach directly, and must emit reasoned telemetry.

### 5) Explicit Fallback Policy (no silent returns)

If pass cannot run:

- Emit `pass_contract_violation` with cause (`missing_from`, `missing_to`, `missing_target`, `sprite_not_found`, etc.).
- Branch chooses one explicit outcome:
  - re-resolve valid pass endpoints, or
  - downgrade route to a no-pass branch/state.

---

## Implementation Strategy (Low-Risk Order)

1. Add shared pass contract validator and lifecycle fields.
2. Add phase gate checks before shot/resolve entry.
3. Add standardized telemetry for pass contract outcomes.
4. Migrate high-risk branches first (RR/Triangle/Fast Break custom branches).
5. Remove duplicated branch-level direct-attach logic after migration.

---

## Suggested Telemetry Events

- `pass_contract_planned`
- `pass_contract_started`
- `pass_contract_received`
- `pass_contract_settled`
- `pass_contract_intentional_skip`
- `pass_contract_violation`
- `pass_contract_phase_gate_blocked`

Payload minimum:

- `turn_id`, `turn_index`, `result_type`, `branch`
- `from_id`, `to_id`
- `required`, `intentionally_skipped`, `reason`
- `lifecycle_state`

---

## Acceptance Criteria

1. No shot/resolve phase begins with `pass_required=true` and lifecycle below `received`.
2. No silent pass skip paths remain in migrated branches.
3. Teleports attributable to skipped pass lifecycle are reduced to 0 in migrated branches.
4. Every intentional no-pass route is explicit and telemetry-backed.

---

## Notes for Future Thread

- This is intentionally universal and should be implemented as shared infrastructure, not another branch-local patch.
- Keep boundary guards as safety net; pass lifecycle should be primary authority.
