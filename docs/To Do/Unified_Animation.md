# Unified Animation System Blueprint

**Status:** Draft working spec (March 2026)
**Objective**
1. **Clock-coupled execution:** Animation phases consume game-clock budget according to defined turn/phase timing rules.
2. **Backend-usable spatial truth:** Backend logic can rely on player/ball locations produced by the same turn timeline used for animation.
3. **Continuous positional continuity:** Player and ball positions are well-defined at each step/phase boundary and across turn boundaries.
4. **Physically plausible movement:** Movement speed respects AG plus configured speed ranges; no branch can bypass this and create unrealistic "Superman" movement.
5. **Standardized animation payload contract:** Every turn emits a consistent animation data shape for frontend consumption (including required endpoints/events).
6. **Explicit completion semantics per turn type:** Each turn type declares `execution_mode`, `advance_trigger`, `visual_settle_trigger`, and `failure_policy`.
7. **Perfect end-state sync across runtime layers:** Backend movement/decision authority, game-clock expiration, and frontend sprite/ball animation must resolve from one coherent contract per unit, with no conflicting timing or position authorities.
  - In this context, "semantics" means what event counts as completion (name + contract meaning), and what state transition that completion authorizes.
  - Turn declares a completion contract, and each step/phase (execution unit) declares a local completion contract, with turn completion derived from the final unit’s completion + transition-out contract.

**Shared Definitions**
- `execution_mode`: `skeleton` units complete on deterministic step geometry (final offensive mover settled unless explicitly shot-terminating); `dynamic_event` units complete on declared event receipt.
- `advance_trigger`: The authoritative event that allows turn logic to progress to the next turn.
- `visual_settle_trigger`: The event that marks the animation phase as visually complete for the current turn.
- `failure_policy`: The branch-specific rule for contract/timing failures (`degrade`, `warn`, or `throw`) and what recovery behavior is allowed.

**Non-Negotiable Runtime Invariants**
- Backend and frontend must maintain a valid position for the ball and all 10 active players at every execution-unit boundary.
- No execution unit may complete without resolved ball-owner authority.
- No silent teleport: position deltas above tolerance must emit contract-failure telemetry.
- Movement must respect AG-based speed and configured locomotion limits on all paths.
- Transition handoffs must preserve spatial continuity within declared tolerance bands.
- Completion semantics are event-authorized; timeout-only completion is not valid for strict units.
- Any fallback must be explicit, counted, thresholded, and branch-scoped.
- On invariant violation, apply the declared unit `failure_policy` (`degrade`, `warn`, or `throw`).

## Current State Snapshot (Today)

- **Objective status:** Objectives are locked and now explicitly require perfect end-state sync between backend movement logic, clock expiration, and frontend animation execution.
- **Transition source of truth:** `docs/GP_Core_Docs/GP_TRANSITION_SYSTEM.md` is canonical for turn-to-turn routing and possession transitions.
- **UESS system source of truth:** `docs/docs_1_systems/00_General_Systems/UESS_System.md` holds locked UESS contract cards and cross-layer sync policy.
- **Execution semantics source of truth:** `6.4 Canonical Execution-Unit Matrices (Draft v0)` defines intra-turn units and completion semantics for all canonical turn families.
- **Architecture status:** Universal movement/clock intent is defined; implementation remains hybrid in several branches.
- **Authority model status:** Current hybrid authority (backend contract + frontend heuristic fallback) is temporary migration mode, not target architecture.
- **Critical stabilization status:** `DREB -> outlet -> HCO` lead-in slice is in progress (functionally stabilized; full end-state sync closure pending).
- **Known risk themes:** mixed authority (backend contract vs frontend fallback), timeout-based completion fallbacks, and boundary handoff inconsistencies.
- **Intentional constraint:** migration remains incremental and contract-first; no broad rewrite.
- **Target authority end-state:** backend contract is the single primary authority for movement/ownership/transition semantics; frontend fallback is explicit degraded mode only and retired from strict units as contract coverage reaches thresholds.

### Current Local Implementation Snapshot (April 2026)

- `dreb_outlet_pass.receiver_target` is now emitted by backend shot/rebound flow as the unit-specific receiver movement authority for `hco.lead_in.from_dreb_outlet`.
- HCO skeleton-step runtime enforcement has landed locally for `hco.step[n].movement` and `hco.step[n].pass`:
  - shared completion validator: `FrontEnd/static/js/phaser/animation/unitCompletionContract.js`
  - strictness runtime flag: `window.HCO_STEP_MOVEMENT_STRICT_CONTRACT = "throw" | "warn" | "off"`
  - movement tolerance override: `window.UESS_HCO_STEP_MOVEMENT_TOLERANCE_PX`
  - step budget override: `window.UESS_HCO_STEP_MOVEMENT_MAX_GAME_SECONDS`
- HCO elapsed observe telemetry is wired at unit boundaries (`lead_in`, `step_movement`, `step_pass`, `resolution`, `transition_out`) and emits `hco_uess_elapsed_observe`.
- Clock-authority observe rollout is implemented end-to-end:
  - frontend request propagation via `uess_clock_authority_mode`
  - backend `clock_event_ledger` generation + observe reconciliation payload
  - frontend parity telemetry + summary thresholds + local debug buffers/helpers
- Fast Break entry announcements are enabled by default again, with runtime override support via `window.ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS`.
- Rim Runner fast-break outcomes now attach decision metadata (`Good Decision` / `Bad Decision`) for announcement/UI presentation.

## Next Implementation Slice (Locked)

- **Slice ID:** `hco.step[n].movement`
- **Why this slice:** first skeleton-mode unit after DREB lead-in completion; validates deterministic mover-completion semantics under clock-coupled step execution.
- **Contract target:**
  - `execution_mode`: skeleton
  - `advance_trigger`: required movers reach step-n targets
  - `visual_settle_trigger`: required step-n tweens complete
  - `failure_policy`: warn -> throw
  - `movement_authority`: step-level backend movement contract (`turn.animations` step targets)
  - `clock_anchor`: `step_clock_seconds[n]`
  - `owner_authority_at_end`: per-step owner contract
- **Definition of done:**
  - Required movers resolve from step contract (no silent role drops)
  - Step completion uses mover-settle contract (not timeout-only completion)
  - AG-based duration/speed limits are respected on all movers
  - Passes Acceptance Gates + Spatial-Truth Validation for this slice

**Implementation status:** local runtime contract checks and telemetry are landed for step movement/pass validation; remaining work is acceptance-gate cleanup, live validation, and promotion from provisional strict rollout to trusted slice completion.

**Active stabilization slice:** `hco.lead_in.from_dreb_outlet` -> **in progress** (deterministic + prototype validation passed; full end-state sync criteria still open).

## Reviewer Reading Order (External)

1. **Objective + Shared Definitions** (top of this document).
2. **6.4 Canonical Execution-Unit Matrices (Draft v0)** for execution semantics.
3. **`docs/GP_Core_Docs/GP_TRANSITION_SYSTEM.md`** for transition registry/routing context.

Optional supporting context:
- **7 / 7.1** Acceptance + Spatial-Truth Gates
- **9+** Turn-type audit baseline sections

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

None at this time. Product/architecture decisions are currently locked; remaining items are implementation/calibration tasks.

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
- Requirement: fallback usage must be logged, measurable, thresholded, and explicitly treated as degraded mode (not co-equal authority).
- Retirement rule: strict units graduate to backend-only authority once baseline telemetry confirms contract completeness and fallback rates meet approved thresholds.

### Layer B: Kinematics Authority

- One speed resolver for all player locomotion (`playerMovementDuration.js`).
- Turn type may apply legal context multipliers/scalars only through shared APIs.
- No direct fixed-duration locomotion outside approved exceptions.

### Layer C: Orchestration Authority

- One policy for pause/freeze/cancel/resume by phase type.
- One policy for turn transitions (no visual yank on first frame of next turn).
- Shared-phase movement should preserve player-relative spacing and avoid forced rail endpoints.

### Layer D: Universal Animation Payload Contract

- Every turn returns the same top-level animation envelope, regardless of turn family.
- Required envelope fields:
  - `animations[]` (always present; may be empty only when explicitly valid by turn type)
  - `events[]` (optional but standardized event schema when present)
  - `roles{}` (optional but standardized role keys when present)
  - `completion_contract{}` (required per turn type; defines completion semantics)
- `completion_contract{}` required fields:
  - `execution_mode` (`skeleton` | `dynamic_event`)
  - `advance_trigger`
  - `visual_settle_trigger`
  - `failure_policy`
  - `clock_anchor`
  - `max_wait_game_seconds`
- Branch-specific additions are allowed, but only as additive fields under this universal envelope.
- Current strict DREB outlet contract shape:
  - `dreb_outlet_pass{ passer_id, receiver_id, receiver_target{x,y}, required, contract_source }`
  - `receiver_target` is unit-specific movement authority for `hco.lead_in.from_dreb_outlet` (do not substitute generic shot-turn `animations[].end` as primary authority).

---

## 6) Migration Strategy (incremental)

### 6.1 How Incremental Work Becomes Universal

The implementation sequence is intentionally branch-by-branch, but the architecture pattern is the same each time:

1. **Authority first**
   - Prefer backend endpoints (`turn.animations[].end`) for destination resolution.
   - Allow frontend heuristics only as fallback.
2. **Telemetry attached**
   - Emit required-role count, fallback count/rate, and transition diagnostics.
3. **Strict guardrails**
   - Start with `warn` while stabilizing, then move local dev defaults to `throw`.
4. **Roll forward**
   - Add the next turn-family without changing the contract model.

This is an additive migration, not per-branch one-offs. Each slice removes unique logic and increases shared behavior under one movement contract.

**Current rollout map (completed -> next):**
- Fast Break family (RR + generic FB shot/stop) -> Phase 1 contract/telemetry framework completed; branch hardening and threshold calibration in progress
- DREB -> outlet -> HCO setup path -> stabilizing (in progress; completion-contract hardening active)
- HCO shot/rebound family (non-FB) -> next
- SIDE_INBOUND / BASELINE_INBOUND / OREB / pressure flows -> follow

**Exit condition for "universal":**
- No active locomotion path bypasses backend-first destination authority without explicit documented invariant.
- All major turn families emit contract telemetry and run strict-mode clean in local throw mode.

### 6.2 Turn Completion Matrix (required before implementation passes)

For each canonical turn type, explicitly lock:
- `execution_mode` (`skeleton` | `dynamic_event`)
- `advance_trigger`
- `visual_settle_trigger`
- `failure_policy` (`degrade`, `warn`, `throw`)
- `clock_anchor` (which moment consumes turn clock budget)
- `owner_authority_at_end` (who sets final ball ownership state)

`clock_anchor` legend (v0):
- `transition budget`: turn-boundary handoff window between `from_turn` and `to_turn` (no hidden extra hold).
- `inbound turn budget`: clock allocation for inbound setup + inbound pass completion.
- `FB phase budget` / `OREB phase budget`: clock allocation for named phases inside those turn families.
- `step_clock_seconds[n]`: backend-provided per-step clock budget for skeleton turns (`HCO`/`FCP`/`HCT`).
- `remaining turn budget`: post-step budget consumed by terminal resolution (shot/foul/turnover/rebound outcome).
- `tip phase budget`: opening-tip jump/control allocation.
- `timeout contract budget`: non-gameplay pause/resume control window for timeout barrier semantics.
- `resume setup budget`: timeout-exit setup allocation before next gameplay turn resumes.

Minimum matrix rows:
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

No turn family moves to "completed" without a locked matrix row and passing validation against that row.

### 6.3 Fixed-Duration Deprecation Milestones

- **Milestone A (now):** Inventory and tag all fixed-duration movement/pass paths (`keep`, `replace`, `invariant`).
- **Milestone B:** Remove fixed-duration locomotion in `HCO/HCT/FCP/SIP/BIP` unless explicitly listed as invariant.
- **Milestone C:** Remove timeout/polling-based completion fallbacks where deterministic lifecycle signals exist.
- **Milestone D:** Enforce static guardrails so new fixed-duration locomotion cannot be introduced outside allowlist.

### 6.4 Canonical Execution-Unit Matrices (Draft v0)

Transition graph source of truth: `docs/GP_Core_Docs/GP_TRANSITION_SYSTEM.md` (Complete Transition Registry).
This section defines intra-turn execution units and completion semantics for each turn family.

#### HCO

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `hco.lead_in.from_dreb_outlet` | lead_in_phase | prior turn ends with DREB and next is HCO/HCT/FCP | dynamic_event | outlet pass received | outlet movement + pass settled | throw | transition budget | outlet receiver |
| `hco.lead_in.from_sip_or_bip` | lead_in_phase | prior turn is SIP/BIP into HCO | dynamic_event | inbound pass received | inbound setup + pass settled | warn -> throw | inbound turn budget | inbound receiver / BH |
| `hco.step[n].movement` | skeleton_step | each HCO skeleton step | skeleton | required movers reach step-n targets | required step-n tweens complete | warn/throw | `step_clock_seconds[n]` | per-step owner contract |
| `hco.step[n].pass` | skeleton_step | step-n includes pass action | skeleton | pass received | ball flight + receiver settle | throw | same step budget | pass receiver |
| `hco.resolution` | branch_phase | shot/foul/turnover/dead-ball point | dynamic_event | result committed | resolution visuals settled | throw | remaining turn budget | result-dependent |
| `hco.out.to_*` | transition_out_phase | any HCO exit route | dynamic_event | route committed (`next_play_type`) | end-of-turn visuals settled | throw | boundary handoff | route-specific owner |

#### FAST_BREAK

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `fb.lead_in.from_hco_steal` | lead_in_phase | HCO steal routes to FAST_BREAK | dynamic_event | FB route committed + entry owner resolved | steal handoff visuals settled | throw | transition budget | stealer / entry BH |
| `fb.lead_in.from_dreb_release` | lead_in_phase | DREB routes to FAST_BREAK | dynamic_event | DREB committed + FB route committed | rebound secure + release setup settled | throw | transition budget | rebounder / outlet passer |
| `fb.phase.entry_burst` | branch_phase | initial FB acceleration and spacing | dynamic_event | required movers reach burst targets | burst tweens settled | warn -> throw | FB phase budget | entry BH |
| `fb.phase.outlet` | branch_phase | outlet subphase exists | dynamic_event | outlet pass received | passer/receiver movement + pass settled | throw | FB phase budget | outlet receiver |
| `fb.phase.defensive_stop` | branch_phase | stop branch selected | dynamic_event | stop result committed | stop visuals settled | throw | FB phase budget | stopped BH or defender context |
| `fb.phase.shot_attempt` | branch_phase | shot branch selected | dynamic_event | shot release/result committed | shot visuals settled | throw | FB phase budget | result-dependent |
| `fb.phase.rebound_resolution` | branch_phase | FB miss/block rebound path | dynamic_event | rebound outcome committed | rebound attach + settle complete | throw | FB phase budget | rebounder |
| `fb.out.to_*` | transition_out_phase | any FB exit route | dynamic_event | route committed | final FB settle complete | throw | boundary handoff | route-specific owner |

#### OREB

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `oreb.lead_in.from_miss` | lead_in_phase | HCO/FB miss routes to OREB | dynamic_event | OREB committed | rebound secure + attach settled | throw | transition budget | OREB rebounder |
| `oreb.phase.hold` | branch_phase | short stabilization before decision | dynamic_event | hold boundary reached | no active attach/tween conflicts | warn -> throw | OREB phase budget | rebounder |
| `oreb.phase.decision` | branch_phase | choose kickout vs putback | dynamic_event | decision event committed | decision prep visuals settled | throw | OREB phase budget | rebounder |
| `oreb.phase.kickout_pass` | branch_phase | kickout branch pass | dynamic_event | pass received | ball flight + receiver settle | throw | OREB phase budget | kickout receiver |
| `oreb.phase.putback_attempt` | branch_phase | putback branch | dynamic_event | shot release/result committed | putback visuals settled | throw | OREB phase budget | result-dependent |
| `oreb.phase.putback_rebound_resolution` | branch_phase | putback miss/block rebound path | dynamic_event | rebound outcome committed | rebound settle complete | throw | OREB phase budget | rebounder |
| `oreb.out.to_*` | transition_out_phase | any OREB exit route | dynamic_event | route committed | OREB final settle complete | throw | boundary handoff | route-specific owner |

#### SIDE_INBOUND (SIP)

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `sip.lead_in.entry` | lead_in_phase | route enters SIP | dynamic_event | SIP route committed + inbounder resolved | setup settled | throw | transition budget | SIP inbounder |
| `sip.phase.setup_positions` | branch_phase | place inbound actors | dynamic_event | required setup movers reached targets | setup tweens settled | warn -> throw | SIP phase budget | inbounder |
| `sip.phase.pass` | branch_phase | inbound pass executes | dynamic_event | pass received | ball flight + receiver settle | throw | SIP phase budget | SIP receiver |
| `sip.out.to_*` | transition_out_phase | SIP exits to HCO/FCP/HCT | dynamic_event | route committed | SIP final settle complete | throw | boundary handoff | route-specific owner |

#### BASELINE_INBOUND (BIP)

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `bip.lead_in.entry` | lead_in_phase | route enters BIP after make | dynamic_event | BIP route committed + inbounder resolved | baseline setup settled | throw | transition budget | BIP inbounder |
| `bip.phase.setup_positions` | branch_phase | half-court reset to inbound geometry | dynamic_event | required setup movers reached targets | setup tweens settled | warn -> throw | BIP phase budget | inbounder |
| `bip.phase.pass` | branch_phase | inbound pass executes | dynamic_event | pass received | ball flight + receiver settle | throw | BIP phase budget | BIP receiver |
| `bip.out.to_*` | transition_out_phase | BIP exits to HCO/FCP/HCT | dynamic_event | route committed | BIP final settle complete | throw | boundary handoff | route-specific owner |

#### FREE_THROW

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `ft.lead_in.entry` | lead_in_phase | route enters FT | dynamic_event | FT route committed + shooter resolved | lane setup settled | throw | transition budget | FT shooter |
| `ft.phase.attempt[n]` | branch_phase | each FT attempt | dynamic_event | shot release/result committed | ball/rim/announcement settled | throw | FT attempt budget | result-dependent |
| `ft.phase.sequence_control` | branch_phase | multi-shot context | dynamic_event | remaining-attempt decision committed | sequence state settled | warn | FT sequence budget | FT shooter |
| `ft.out.to_*` | transition_out_phase | FT exits to FT/BIP/OREB/HCO/FB/SIP | dynamic_event | route committed | FT final settle complete | throw | boundary handoff | route-specific owner |

#### FCP

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `fcp.lead_in.entry` | lead_in_phase | route enters FCP | dynamic_event | FCP route committed + pressure setup owner resolved | pressure setup settled | throw | transition budget | FCP entry BH |
| `fcp.step[n].skeleton` | skeleton_step | each FCP skeleton step | skeleton | step-n contract event committed | step-n tweens settled | warn -> throw | `step_clock_seconds[n]` | per-step owner contract |
| `fcp.step[n].pass` | skeleton_step | pass on step-n | skeleton | pass received | pass settle complete | throw | same step budget | pass receiver |
| `fcp.resolution` | branch_phase | foul/turnover/shot result | dynamic_event | result committed | resolution visuals settled | throw | remaining turn budget | result-dependent |
| `fcp.out.to_*` | transition_out_phase | any FCP exit route | dynamic_event | route committed | FCP boundary settle complete | throw | boundary handoff | route-specific owner |

#### HCT

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `hct.lead_in.entry` | lead_in_phase | route enters HCT | dynamic_event | HCT route committed + trap setup owner resolved | trap setup settled | throw | transition budget | HCT entry BH |
| `hct.step[n].skeleton` | skeleton_step | each HCT skeleton step | skeleton | step-n contract event committed | step-n tweens settled | warn -> throw | `step_clock_seconds[n]` | per-step owner contract |
| `hct.step[n].pass` | skeleton_step | pass on step-n | skeleton | pass received | pass settle complete | throw | same step budget | pass receiver |
| `hct.resolution` | branch_phase | foul/turnover/shot result | dynamic_event | result committed | resolution visuals settled | throw | remaining turn budget | result-dependent |
| `hct.out.to_*` | transition_out_phase | any HCT exit route | dynamic_event | route committed | HCT boundary settle complete | throw | boundary handoff | route-specific owner |

#### OPENING_TIP

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `tip.phase.jump` | branch_phase | tipoff launch and contest | dynamic_event | tip outcome committed | jump visuals settled | throw | tip phase budget | tip winner |
| `tip.phase.control` | branch_phase | first control to handler | dynamic_event | possession control committed | control pass/attach settled | throw | tip phase budget | initial ball handler |
| `tip.out.to_hco` | transition_out_phase | standard tip completion | dynamic_event | HCO route committed | tip boundary settle complete | throw | boundary handoff | HCO entry BH |

#### TIMEOUT

| unit_id | unit_type | when it applies | execution_mode | advance_trigger | visual_settle_trigger | failure_policy | clock_anchor | owner_authority_at_end |
|---|---|---|---|---|---|---|---|---|
| `timeout.phase.pause_barrier` | branch_phase | timeout initiated | dynamic_event | timeout state committed | active tweens/flows paused to barrier | throw | timeout contract budget | unchanged |
| `timeout.phase.resume_prepare` | branch_phase | timeout ending | dynamic_event | resume route/context committed | resume setup settled | warn -> throw | resume setup budget | unchanged |
| `timeout.out.to_next` | transition_out_phase | return to pending route | dynamic_event | pending route committed | timeout exit settle complete | throw | boundary handoff | next-turn contract owner |

### 6.5 Advance Trigger Lock Pass (Wave 1)

Purpose: lock trigger semantics against concrete runtime checks, then isolate remaining gaps as targeted follow-ups (no broad rewrites).

Lock criteria:

1. Trigger wording is explicit and unambiguous in Section 6.4.
2. Runtime check exists for both `advance_trigger` and `visual_settle_trigger` (or documented as pending).
3. Failure policy mode is wired (`off/observe/warn/throw` or `warn/throw` as defined by family rollout).
4. Any uncovered units are explicitly listed in "Pending lock" (not implicit).

Wave 1 lock status (current):

- **LOCKED (runtime-wired):**
  - `hco.lead_in.from_dreb_outlet`
  - `hco.lead_in.from_sip_or_bip`
  - `hco.step[n].movement`
  - `hco.step[n].pass`
  - `hco.resolution`
  - `hco.out.to_*`
  - `sip.phase.setup_positions`
  - `sip.phase.pass`
  - `sip.lead_in.entry`
  - `sip.out.to_*`
  - `bip.lead_in.entry`
  - `bip.phase.setup_positions`
  - `bip.phase.pass`
  - `bip.out.to_*`
  - `fcp.step[n].movement` + `fcp.step[n].pass`
  - `fcp.resolution` + `fcp.out.to_*`
  - `hct.step[n].movement` + `hct.step[n].pass`
  - `hct.resolution` + `hct.out.to_*`
  - `oreb.phase.decision`
  - `oreb.phase.kickout_pass`
  - `oreb.phase.putback_attempt`
  - `oreb.lead_in.from_miss`
  - `oreb.phase.hold`
  - `oreb.phase.putback_rebound_resolution`
  - `oreb.out.to_*`
  - `ft.lead_in.entry`
  - `ft.phase.attempt[n]`
  - `ft.phase.sequence_control`
  - `ft.out.to_*`
  - `timeout.phase.pause_barrier`
  - `timeout.phase.resume_prepare`
  - `timeout.out.to_next`
  - `tip.phase.jump`
  - `tip.phase.control`
  - `tip.out.to_hco`
  - FAST_BREAK family trigger-lock runtime parity:
    - `fb.lead_in.from_hco_steal`
    - `fb.lead_in.from_dreb_release`
    - `fb.phase.entry_burst`
    - `fb.phase.outlet`
    - `fb.phase.shot_attempt`
    - `fb.phase.defensive_stop`
    - `fb.phase.rebound_resolution`
    - `fb.out.to_*`

- **PENDING LOCK (defined in matrix, runtime parity still to finish):**
  - none

Wave 1 completion note:

- Trigger semantics are now locked for the runtime-wired units above.
- No remaining Wave 1 trigger-lock rows are pending; follow-up work is now polish/tuning rather than missing unit wiring.

### 6.6 Destination-First Invariant Pass (New Baseline)

Purpose: eliminate hidden pauses by making continuous movement-to-destination the default runtime behavior.

Policy:

1. Required movers must progress toward their unit destination continuously unless an allowed interrupt is active.
2. Allowed interrupts are explicit per unit (`pass_in_flight`, `shot_release_or_flight`, `rebound_secure`, `timeout_pause_barrier`, `dead_ball_or_whistle_stop`, `period_end`).
3. Any hold must be declared in the unit contract (`hold_reason`, `hold_budget_ms`, affected movers).
4. Undeclared waits/timeouts are treated as contract violations.

Execution order (forward-only):

1. Apply to all newly modified units immediately (no exceptions).
2. Retrofit highest-risk boundaries first:
   - `hco.lead_in.from_dreb_outlet`
   - `oreb.*` putback/kickout boundaries
   - batch/sub-turn transition boundaries
3. Add runtime acceptance checks:
   - destination availability at unit start
   - continuous-progress watchdog while no interrupt is active
   - undeclared-hold violation emission
   - unit-budget overrun enforcement by mode

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
6. Turn clock movement aligns with declared `clock_anchor` per turn type (no early/late logical advancement).
7. Every turn type passes its locked `advance_trigger` + `visual_settle_trigger` contract without timeout-only recovery.
8. Backend `Player.coords` and frontend end-of-turn sprite/ball positions stay within tolerance at turn boundary handoff.

### 7.1 Backend Spatial-Truth Validation Gates

- For every sampled turn family, capture:
  - backend end-of-turn coords
  - frontend end-of-turn coords
  - delta (`grid`, `px`)
- Balanced provisional tolerance bands (v0; calibrate after baseline audit):
  - **Strict (inbound/outlet phases):** pass if `deltaPx <= 12`; fail if `> 12`
  - **Moderate (skeleton step + controlled branch phases):** pass if `deltaPx <= 18`; fail if `> 18`
  - **Transition-heavy phases (FB/OREB handoffs):** pass if `deltaPx <= 24`; fail if `> 24`
  - **Absolute fail-safe cap (all families):** fail if `deltaPx > 30` regardless of phase family
- These v0 values are intentionally balanced defaults and must be confirmed/recalibrated from sampled telemetry before CI hard-fail enforcement.
- If tolerance is exceeded:
  - emit telemetry event
  - mark branch run as contract-invalid in dev/CI
  - block completion status for that turn family until corrected

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


Decision lock is complete. Before additional code changes, execute:

1. Run the Fast Break baseline telemetry audit (Section 11.D) and populate the capture table.
2. Confirm or recalibrate provisional Phase 1 fallback thresholds using audit results.
3. Validate `fb_transition_snap` detection with the v0 rule (`deltaPx > 12`) and record outcomes.
4. Start the locked next slice (`hco.step[n].movement`) and validate against Acceptance Gates.

### 8.1 Unit-by-Unit Cadence Loop (Execution Standard)

Apply this loop for every execution unit in Section 6.4:

1. **Select one unit** (single `unit_id` scope only).
2. **Implement unit contract** (`execution_mode`, `advance_trigger`, `visual_settle_trigger`, `failure_policy`, `clock_anchor`, `owner_authority_at_end`).
3. **Run deterministic validation** (lint/tests/contract assertions/telemetry checks for that unit).
4. **Run prototype validation** (visual motion realism + ownership continuity + handoff behavior).
5. **Mark unit status** (`complete` or `needs_patch`) with notes.
6. **Patch once if needed**, then re-run steps 3-5.
7. **Promote and proceed** to the next unit only after unit is marked `complete`.

Checkpoint cadence:
- **Turn checkpoint:** after all units in a turn family are complete, run turn-level regression.
- **Handoff checkpoint:** after coupled families (e.g., `FAST_BREAK -> HCO`) are complete, run boundary/handoff regression.


---

## 9) Turn-Type Sections (audit baseline)

> **Legacy/audit context note:** This section is retained as migration context and may include point-in-time observations. When conflicts exist, prioritize the Objective, Current State Snapshot, Section 6.4 matrices, and Acceptance Gates.

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

Rationale: start with the highest branch complexity + fixed-duration density, then converge pressure/inbound/rebound flows onto shared movement authority, and leave stable/special-case turns for last validation. Dependency note: FastBreak -> HCO handoff closure is coupled to HCO contract hardening and should be treated as a shared milestone, not independent serial work.

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

> **Legacy/audit context note:** This checklist remains useful for Fast Break migration, but completion semantics and universal contract decisions are now governed by Section 6.4 and Section 7 gates.

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

- **Status:** Phase 1 values below are provisional defaults and must be calibrated after baseline audit (Section D) before enforcing hard fail in CI.

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

Snap detection rule (v0, provisional):
- Count a transition snap event when `deltaPx > 12`.
- Treat `deltaPx <= 12` as acceptable micro-adjustment (not a snap event).

**Aggregation counters per turn (for threshold checks):**
- `fbFallbackCount`
- `fbRequiredRoleCount`
- `fbFallbackRate` = `fbFallbackCount / fbRequiredRoleCount`
- `fbClampCount`
- `fbSnapCount`

---

### D) Baseline Audit Capture Table (first pass)

Populate this table for sampled turns before Phase 2 tuning:

- **Owner:** animation workstream lead (current implementer for this stream).
- **Timing:** must be completed and reviewed before any Phase 2 tuning starts.
- **Minimum sample:** run at least 5 simulated games or capture at least 25 Fast Break turns (whichever is greater).
- **Review checkpoint:** after table population, confirm/adjust Phase 1 thresholds and record approved values.

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
4. Controlled fallback thresholds are calibrated from baseline audit and approved.

---

## Cleanup List (Active)

- [ ] **HCO/FCP/HCT player classification warning** (`owner`: animation workstream lead, `phase`: HCO hardening follow-up, `priority`: P1): investigate and eliminate `Expected 5 offensive and 5 defensive players` warnings (seen around OREB/putback and mixed transition contexts); ensure classification input set is stable before strict unit checks.
- [ ] **Clock continuity warning** (`owner`: animation workstream lead + game clock owner, `phase`: HCO/OREB boundary stabilization, `priority`: P1): investigate `Ignoring non-monotonic clock update` scoreboard warnings; confirm whether this is display-order only or indicates real turn clock handoff inconsistency.
- [ ] **SIDE_INBOUND fallback dependency** (`owner`: inbound/transition owner, `phase`: SIP/BIP/HCO pass authority cleanup, `priority`: P2): reduce/remove reliance on `Using fallback hardcoded SF→PG pass` by sourcing inbound pass roles from authoritative payload wherever available.
- [ ] **Debug log severity cleanup** (`owner`: frontend animation owner, `phase`: telemetry/log hygiene, `priority`: P3): convert non-actionable diagnostic `console.warn` lines (e.g., frontend steal entry/setup traces) to debug-level logs to keep runtime warning signal high.

## Known HCO Turn Issues

- [ ] **HCO resolution hard overrun with invalid elapsed clock** (`severity`: Critical, `priority`: P0): observed throw `"[HCO resolution contract] clock overrun ... elapsedGameSeconds=649.00"` on `DEAD BALL` path. This indicates timer baseline/state contamination (not normal jitter). **Mitigation applied (Option A):** turn-boundary guards now use contract-capped elapsed (`min(wall_elapsed_ms, real_time_elapsed_ms + guard_slack_ms)`); validate in live runs before closing.
- [ ] **HCO step-pass hard overrun with invalid elapsed clock in BATCH/DEAD BALL sub-turns** (`severity`: Critical, `priority`: P0): observed throw `"[HCO step pass contract] clock overrun ... elapsedGameSeconds=405.78"` at `step=6` on `DEAD BALL` batch sub-turn processing. Magnitude indicates elapsed baseline contamination/leak (not jitter). Track as separate from resolution-path overrun; likely same timer-source class but distinct enforcement site (`step pass` guard).
- [ ] **DREB->HCO strict contract degradation still triggered in mixed OREB/putback flows** (`severity`: High, `priority`: P1): observed `missing_outlet_receiver_animation_end` followed by synthetic pass fallback (`Using synthetic passInfo for non-strict branch`), indicating incomplete backend endpoint coverage on some rebound-derived transitions.
- [ ] **HCO/FCP/HCT player classification mismatch in OREB/putback contexts** (`severity`: High, `priority`: P1): repeated warning `Expected 5 offensive and 5 defensive players`; likely destabilizes ownership/step gating on adjacent turns.
- [ ] **Clock continuity drift around putback/inbound boundaries** (`severity`: High, `priority`: P1): repeated `Ignoring non-monotonic clock update` warnings; may be display-order only, but currently treated as timing-integrity risk until proven otherwise.
- [ ] **SIDE_INBOUND fallback pass authority still active** (`severity`: Medium, `priority`: P2): `Using fallback hardcoded SF→PG pass` persists; increases variance in SIP->HCO entry behavior and should be retired.
- [ ] **Ownership attach gating noise during possession flips** (`severity`: Medium, `priority`: P2): frequent `BallControllerAdapter: Skipping attach due to possessionFlipInProgress`; likely expected in some windows but should be reviewed against teleport/ownership-snap incidents.
