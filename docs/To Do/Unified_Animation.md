# Unified Animation System Blueprint

**Status:** Draft working spec (March 2026)
**Purpose:** Define one coherent animation model across all turn types so movement logic is organic, clock-tethered, AG-scaled, and not dependent on siloed per-feature patches. Also ensure frontend animation state stays spatially synchronized with backend gameplay logic so future geography/location-aware decisioning can use player positions without desyncing the visual clock tick. This system is mandatory and authoritative for all player locomotion and animation orchestration paths in the game engine, with exceptions allowed only as explicitly documented invariants.

---

## 0) Reviewer Brief (for external consultation)

### Objective of This Review

Validate whether this plan can deliver a truly universal animation system (not siloed turn-by-turn patchwork) while preserving game-clock sync and backend/frontend spatial consistency.

### Non-Negotiable Outcomes

1. No mass x-clamp pileups (`x=4` / `x=97`) unless explicitly intended by design.
2. No Superman-like long traversals in a single phase from hidden fallback rules.
3. No visible backward snap at phase/turn handoff (especially FastBreak -> HCO).
4. Backend gameplay geography and frontend sprite geography must stay synchronized enough to support location-aware logic.
5. Universal movement authority must apply across all turn types, with documented invariants only.

### Known Bug Exemplars (current)

- **RR Fast Break hold-up (No Pass):** non-BH drift can over-travel to x-clamp due to shared-phase duration floor + speed-based stride.
- **Residual "jetting" instances:** still occur where fixed-duration systems and universal AG-duration systems coexist.
- **Occasional transition whiplash:** visible repositioning during FastBreak -> HalfCourt handoffs in some paths.

### Evidence Pointers (high-signal files)

- Router/handler authority: `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
- Universal speed math: `FrontEnd/static/js/phaser/utils/playerMovementSpeed.js`, `playerMovementDuration.js`
- Fast break branch complexity: `FrontEnd/static/js/phaser/animation/fastBreak.js`
- Shared/default turn animation: `FrontEnd/static/js/phaser/animation/turnAnimation.js`
- Pass system fixed durations: `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js`
- Ball duration fallbacks: `FrontEnd/static/js/phaser/animation/ballTween.js`

### Decisions Already Made (do not re-litigate unless evidence demands)

- Keep AG-scaled movement as the universal base model.
- Keep game clock baseline (`350ms real = 1 game second`) as pacing reference.
- Prefer backend movement endpoints when available; fallback only when contract data is missing.
- Universal scope is mandatory across the engine; siloed behavior should only survive as explicit invariants.

### Open Product/Architecture Questions Requiring Decision

1. Should announcement freeze be global by class/type, or remain path-specific?
2. Which turn types require backend endpoint authority immediately (phase 1 contract)?
3. Which timing constants remain invariants vs temporary migration fallbacks?
4. What is the acceptable fallback threshold before a turn is considered contract-invalid?

---

## 1) Product Intent (authoritative)

1. Player movement should be tethered to game pacing and look human.
2. Movement speed should vary by player AG.
3. Turn type should shape movement intent (who moves, where, and why), not bypass core movement rules.
4. Avoid hardcoded spots/minimums except where explicitly required as invariants or temporary fallbacks.
5. No branch should create mass rail/clamp artifacts (x=4/97 pileups) or Superman-like traversals.

---

## 2) Current System Snapshot

### What is already unified

- Universal player speed/duration math:
  - `FrontEnd/static/js/phaser/utils/playerMovementSpeed.js`
  - `FrontEnd/static/js/phaser/utils/playerMovementDuration.js`
- Core formula:
  - `speedPxPerSec = (400 + AG) * (BH ? 0.95 : 1.0) * (window.__GAME_SPEED / 450)`
  - `durationMs = distancePx / speedPxPerSec * 1000` (min 50 ms)
- Game pacing reference:
  - `350ms real time = 1 game second` (clock baseline)

### What is still hybrid / fragmented

- Fast break orchestration includes bespoke branch logic and fallback target generation.
- Some paths use backend endpoints (`turn.animations[].end`), others derive local random/heuristic targets.
- Announcement freeze behavior is path-specific, not a global movement policy.
- Some shared-phase floors and per-branch drift rules can force over-travel into hard clamps.

---

## 3) Key Constants In Play Today

### Frontend fast-break movement ranges (`fastBreakConstants.js`)

- BH move: `x +5..10`, `y ±3`
- Stopper offset: `1..3`
- Shot defender: `x offset 1`, `y ±2`
- Rebounder defensive stop: `x 40..60`, `y ±6`
- Rebounder shot attempt: `y ±10` around rim
- Outlet passer move: `x +7`
- Defensive stop y gate: `±6`
- Steal entry: `x +5..10`, `y ±4`, clamp y `3..47`
- Steal HCO setup (BH): `x 3..7`, `y ±3`, clamp y `3..47`

### Backend adds additional ranges (`fast_break_constants.py`)

- FB shot spot: `x distance 2..6 from rim`, `y ±6`
- DREB outlet defensive stop y range: `±8`
- Steal HCO setup for other players: `x 15..30`, `y ±6`, clamp y `4..46`

---

## 4) Root Problems to Solve

1. Universal speed exists, but universal movement policy does not.
2. Shared-duration + speed-based drift in some branches can over-travel and clamp.
3. Mixed destination authority (backend vs frontend fallback) causes inconsistent outcomes.
4. Transition handoffs (e.g. FastBreak -> HCO) can produce visible backward repositioning.

---

## 5) Unified Architecture Target

### Layer A: Movement Authority

- Primary: backend-provided per-player endpoint (`turn.animations[]` / explicit role coords).
- Secondary (fallback): deterministic frontend policy only when authority data is missing.
- Requirement: fallback usage must be logged and measurable.

### Layer B: Kinematics Authority

- One speed resolver for all player locomotion (`playerMovementDuration.js`).
- Turn type may apply legal context multipliers/scalars only through shared APIs.
- No direct fixed-duration locomotion outside approved exceptions.

### Layer C: Orchestration Authority

- One policy for pause/freeze/cancel/resume by phase type.
- One policy for turn transitions (no visual yank on first frame of next turn).
- Shared-phase movement should preserve player-relative spacing and avoid forced rail endpoints.

---

## 6) Migration Strategy (incremental)

### Phase 1 - Contract and visibility

- Define required movement authority fields per turn type.
- Add debug visibility for fallback usage and clamp-as-destination events.

### Phase 2 - Fast break unification

- Continue migrating FB branch helpers to prefer backend endpoints.
- Reduce branch-local random target generation in shot/stop/settle paths.

### Phase 3 - Global policy enforcement

- Route all locomotion through shared planner/executor interfaces.
- Enforce lint/guardrails against direct ad-hoc player tweening.

### Phase 4 - Cleanup

- Decommission legacy hardcoded spots/minimums that are no longer needed.
- Keep only explicit invariants with rationale.

---

## 7) Acceptance Gates (engine-wide)

1. No mass x-clamp destination artifacts in any supported branch.
2. No Superman-like long traversals in a single phase unless explicitly intended by design.
3. No visible backward snap immediately after phase/turn transition.
4. Consistent movement authority resolution (backend first; fallback logged).
5. AG-based speed differentials remain visible but physically plausible.

---

## 8) Immediate Next Work Session Inputs

### Decision Lock (Approved)

1. **Fallback Threshold Policy (Layer A):** **Controlled**
   - Fallbacks are allowed only up to defined per-turn thresholds; beyond threshold, treat as contract invalid in dev/CI gates.

2. **Announcement Freeze Policy (Layer C):** **Class-based**
   - Freeze applies by announcement class (not all announcements globally, and not ad-hoc per path).

3. **Guardrail Enforcement (Phase 3):** **Runtime + Static + Review**
   - Runtime warnings for bypassed movement authority.
   - Static lint/checks for disallowed direct tween patterns outside allowlist.
   - PR checklist requiring movement-authority and duration-authority compliance.

4. **FastBreak -> HCO Handoff Contract:** **Hybrid temporary (C)**
   - Frontend smoothing allowed short-term.
   - Backend handoff contract is required by milestone date (no permanent FE-only patch).

5. **Phase 3 Roadmap Protection:** **Release gate**
   - Phase 3 is mandatory for completion; no “done” status without active/passing guardrails.


Before additional code changes, decide:

1. Which turn types must require backend endpoint authority now (starting set).
2. Which constants are true invariants vs temporary fallback knobs.
3. Whether to codify a global announcement movement policy (freeze or no freeze by class).

Then apply one scoped implementation pass and validate against Acceptance Gates.


---

## 9) Turn-Type Sections (audit baseline)

### Priority Execution Queue

1. Fast Break
2. SIDE_INBOUND (SIP)
3. BASELINE_INBOUND (BIP)
4. OREB
5. FCP
6. HCT
7. Free Throw
8. HCO
9. Opening Tip
10. Timeout

Rationale: start with the highest branch complexity + fixed-duration density, then converge pressure/inbound/rebound flows onto shared movement authority, and leave stable/special-case turns for last validation.

### HCO

**Adherence status:** Medium-High

- **What aligns well**
  - Primarily backend `turn.animations` driven through `playTurnAnimation()` / `animateStep()`.
  - Player movement duration generally resolves via universal `getPlayerDuration()`.
- **Red flags**
  - Hardcoded durations still exist in helper paths (for passes / ball phases).
  - Some inbound/rebound-adjacent setup uses branch-specific random spot logic.
- **Gaps to close**
  - Remove fixed locomotion durations from helper subpaths.
  - Ensure destination authority is backend-first in every HCO-adjacent subflow.

### FCP

**Adherence status:** Medium

- **What aligns well**
  - Shares core HCO/default animation machinery.
  - Pressure setup state is explicit (`next_defensive_setup`, pressure flags).
- **Red flags**
  - Pressure setup + inbound sequencing introduces extra bespoke orchestration.
  - Inbound/pass components still rely on fixed duration fallbacks.
- **Gaps to close**
  - Unify pressure inbound pass timing with universal duration contracts.
  - Reduce branch-local handoff logic between BIP -> pressure turns.

### HCT

**Adherence status:** Medium

- **What aligns well**
  - Uses same core routing philosophy as FCP/HCO.
- **Red flags**
  - Same inbound/pass fixed-duration dependency pattern as FCP.
  - Multiple branch-specific transition checks increase desync risk.
- **Gaps to close**
  - Reuse one shared pass/inbound timing policy for all pressure entries.
  - Collapse duplicated pressure transition logic.

### Fast Break

**Adherence status:** Low

- **What aligns well**
  - Uses universal player duration in many locomotion calls.
  - Some shot-phase helpers now prefer backend animation endpoints.
- **Red flags**
  - Hybrid authority remains (backend endpoints + frontend fallback geometry).
  - Shared-phase minimum + speed-based drift can over-travel and hit x clamps.
  - Extensive branch-local random/heuristic target generation.
- **Gaps to close**
  - Make backend endpoint authority mandatory for required roles by branch.
  - Replace drift overshoot pattern with deterministic non-rail policy.
  - Standardize transition-to-HCO handoff to avoid backward snaps.

### OREB

**Adherence status:** Low-Medium

- **What aligns well**
  - Routes through dedicated OREB handlers and rebound setup helpers.
- **Red flags**
  - OREB flow split across multiple modules (`animateGameTurns`, `turnAnimation`, shot/rebound helpers).
  - Fixed-time behavior still present (`oreb_hold_seconds * 350`, kickout pass duration constants).
- **Gaps to close**
  - Consolidate OREB orchestration into one authority path.
  - Convert hardcoded pass/hold timing to contract-driven or universal policies.

### Opening Tip

**Adherence status:** Medium-High

- **What aligns well**
  - Player jumps/converges use `getPlayerDuration()` and backend animation coords.
- **Red flags**
  - Still a bespoke scripted sequence with dedicated ball timing assumptions.
- **Gaps to close**
  - Keep as special-case turn, but formalize which timings are invariants vs fallbacks.

### BASELINE_INBOUND (BIP)

**Adherence status:** Medium

- **What aligns well**
  - Player setup uses backend animation endpoints + distance-based durations.
  - Explicit wait for inbound pass completion before next turn.
- **Red flags**
  - Inbound pass execution path still relies on `PassAnimationSystem` fixed durations.
  - Safety timeout-based completion (`2s` fallback) indicates orchestration fragility.
- **Gaps to close**
  - Replace fixed inbound pass timings with contract-driven duration inputs.
  - Remove polling/timeout fallback by using deterministic pass lifecycle signals.

### SIDE_INBOUND (SIP)

**Adherence status:** Low-Medium

- **What aligns well**
  - Has a dedicated pass handler path.
- **Red flags**
  - `PassAnimationSystem` is duration-constant heavy (300/400/500/600ms profiles).
  - Receiver repositioning often uses fixed-duration tweens.
- **Gaps to close**
  - Migrate SIP to universal duration authority for receiver/player motion.
  - Keep pass profile semantics, but derive durations from distance/contract where possible.

### Free Throw

**Adherence status:** Medium

- **What aligns well**
  - Uses backend animation coordinates for lane setup and shooter positions.
  - Supports sequence context and outcome-specific flow.
- **Red flags**
  - Free throw systems retain fallback fixed durations (`setupDuration`, `shotDuration`).
  - Legacy and newer free throw paths coexist.
- **Gaps to close**
  - Choose one canonical FT animation path.
  - Move fallback timing onto explicit contract fields or shared policy.

### Timeout

**Adherence status:** High (for non-locomotion turn)

- **What aligns well**
  - Explicit global pause flow (`pauseAll`) and timeout popup integration.
- **Red flags**
  - Global pause semantics can mask lingering animation lifecycle issues in other turns.
- **Gaps to close**
  - Keep timeout behavior simple; use it as a strict state barrier, not a cleanup crutch.


---

## 10) Universality Assessment

### Short Answer

Yes — a truly universal animation system is achievable in this engine. The current architecture does **not** require siloed per-turn animation logic as a permanent state.

### What Can Be Fully Universal

1. **Kinematics** (speed/duration/displacement math)
   - One player locomotion resolver for all turn types.
   - One ball-flight duration policy for all pass/shot travel where applicable.
2. **Movement authority resolution**
   - Backend endpoint authority first, deterministic fallback second, with explicit logging.
3. **Orchestration policy**
   - One phase policy for freeze/pause/cancel/resume and one transition handoff policy.
4. **Validation and observability**
   - One set of acceptance gates and debug telemetry across all turns.

### What Should Remain Turn-Specific (but not siloed)

Turn-specific behavior is still valid where it encodes **basketball semantics**, for example:

- Opening tip jump/converge choreography
- Free throw lane/no-lane setup semantics
- Timeout pause and popup flow
- Inbound-specific pass semantics (BIP/SIP)

These should be implemented as **data/config and role semantics**, while still using the same universal movement/orchestration core.

### Why It Feels Siloed Today

- Mixed authority sources (backend endpoints vs frontend heuristic/random targets)
- Legacy systems with fixed durations coexisting beside universal AG-duration logic
- Branch-local orchestration fallback patterns (timeouts, polling guards, bespoke drifts)

This is a migration state, not a hard engine constraint.

### Final Position

- **Universal core:** feasible and recommended.
- **Siloed logic:** should be reduced to explicit, documented invariants only.
- **Target model:** shared movement engine + turn-type role semantics (not turn-type animation engines).


---

## 11) Fast Break Phase 1 Contract Checklist

Use this as the first implementation gate before additional Fast Break behavior tuning.

### A) Required Movement Authority Fields (by branch)

For each role listed below, the turn must provide either:
- `turn.animations[playerId].end` (preferred), or
- explicit role coordinates field(s) defined by contract.

If neither exists, the move is fallback-driven and must be counted.

#### Branch: RR hold-up / no lane pass (`rim_runner_hco_settle`, `rim_runner_no_lane_pass`)

Required roles:
- Ball handler (outlet receiver / passer role resolution)
- Rim runner
- Get-back defenders
- Primary defender / stopper (when present)

Required authority data:
- BH settle endpoint
- Non-BH drift/settle endpoints (or explicit deterministic policy contract)

#### Branch: RR outlet denied (`rim_runner_outlet_failed`)

Required roles:
- Outlet passer
- Outlet receiver
- Outlet defender
- Other moving players in denied beat

Required authority data:
- Outlet defender destination
- Receiver cut destination
- Other-player post-denial movement destinations (or deterministic contract)

#### Branch: RR lane pass -> shot (`MAKE`/`MISS`/`BLOCK`)

Required roles:
- Shooter
- Defender(s): primary + stopper/trail if present
- Get-back defenders
- Rebounders

Required authority data:
- `shot_spot`
- `defender_spot` (or role-level endpoints in `animations`)
- Get-back/rebounder endpoints

#### Branch: RR interception (`STEAL`) / bat OOB (`DEAD BALL`)

Required roles:
- Victim / stealer / rim runner / involved defenders
- Any helper movers participating in transition/handoff

Required authority data:
- Interception lane/touch endpoints
- OOB interaction endpoints and reset destinations

#### Branch: Generic fast break shot / stop

Required roles:
- Ball handler
- Primary defender
- Supporting movers (get-back/rebounders)

Required authority data:
- Shot/stop endpoints for all participating movers

---

### B) Fallback Thresholds (Decision Lock: Controlled)

Define and enforce per-turn thresholds in dev/CI:

- **Phase 1 (baseline + migration):**
  - Fast Break total fallback rate target: `< 15%`
  - Hard fail threshold: `>= 25%`
- **Phase 2+ (steady-state target):**
  - Fast Break total fallback rate target: `< 5%`
  - Hard fail threshold: `>= 10%`
- Clamp-as-destination events target: `0` for non-invariant branches
- FastBreak -> HCO snap events target: `0`

Fallback event definition (count as fallback):
- Player destination generated from FE random/heuristic policy because required authority endpoint was missing.

---

### C) Telemetry Requirements (Phase 1 visibility)

Log per Fast Break turn:
- branch kind
- required roles present/missing
- fallback count and player IDs
- clamp destination count and player IDs
- transition snap flag

Suggested event keys:
- `fb_contract_missing_endpoint`
- `fb_fallback_used`
- `fb_clamp_destination`
- `fb_transition_snap`

#### Telemetry Payload Schema (v1)

Use a shared payload envelope for all four events, then event-specific fields.

**Shared envelope fields (all events):**
- `event`: string (one of the four keys)
- `turnIndex`: number
- `turnId`: string | number | null
- `resultType`: string
- `branchKind`: string (e.g., `rr_hold_up`, `rr_outlet_denied`, `rr_lane_shot`, `rr_interception`, `rr_bat_oob`, `generic_fb_shot_stop`)
- `offenseTeamId`: string | number | null
- `gameClock`: string | null (e.g., `"3:42"`)
- `quarter`: number | null
- `timestampMs`: number (Date.now)

**1) `fb_contract_missing_endpoint`**
- `playerId`: string | number
- `role`: string (e.g., `ball_handler`, `rim_runner`, `getback_defender`, `stopper`, `rebounder`, `outlet_receiver`, `outlet_defender`)
- `requiredEndpointType`: string (`animations_end` | `role_coord`)
- `availableAuthority`: object
  - `hasAnimations`: boolean
  - `hasPlayerAnimation`: boolean
  - `hasAnimEnd`: boolean
  - `hasRoleCoord`: boolean
- `reason`: string

**2) `fb_fallback_used`**
- `playerId`: string | number
- `role`: string
- `fallbackPolicy`: string (e.g., `random_band`, `heuristic_lane`, `ag_horizontal_drift`)
- `missingAuthority`: array of strings
- `target`: `{ x: number, y: number }`
- `source`: `{ x: number, y: number }`

**3) `fb_clamp_destination`**
- `playerId`: string | number
- `role`: string
- `sourceX`: number
- `proposedEndX`: number
- `clampedEndX`: number
- `clampEdge`: string (`min_x` | `max_x`)
- `phaseDurationMs`: number | null
- `speedPxPerSec`: number | null

**4) `fb_transition_snap`**
- `playerId`: string | number
- `role`: string
- `fromTurnType`: string (`FAST_BREAK`)
- `toTurnType`: string (usually `HCO`)
- `preTransition`: `{ x: number, y: number }`
- `postTransition`: `{ x: number, y: number }`
- `deltaPx`: number
- `deltaGridApprox`: `{ x: number, y: number }`

**Aggregation counters per turn (for threshold checks):**
- `fbFallbackCount`
- `fbRequiredRoleCount`
- `fbFallbackRate` = `fbFallbackCount / fbRequiredRoleCount`
- `fbClampCount`
- `fbSnapCount`

---

### D) Baseline Audit Capture Table (first pass)

Populate this table for sampled turns before Phase 2 tuning:

| Branch | Sample Count | Endpoint Completeness % | Fallback Rate % | Clamp Events | Snap Events | Notes |
|---|---:|---:|---:|---:|---:|---|
| RR hold-up / no pass |  |  |  |  |  |  |
| RR outlet denied |  |  |  |  |  |  |
| RR lane pass -> shot |  |  |  |  |  |  |
| RR interception |  |  |  |  |  |  |
| RR bat OOB |  |  |  |  |  |  |
| Generic FB shot/stop |  |  |  |  |  |  |

---

### E) Exit Criteria for Phase 1 (Fast Break)

Phase 1 is complete only when:
1. Required authority fields are defined for every Fast Break branch.
2. Telemetry is emitting for missing endpoints/fallbacks/clamps/snaps.
3. Baseline table is populated with real sample data.
4. Controlled fallback thresholds are explicitly filled and approved.
