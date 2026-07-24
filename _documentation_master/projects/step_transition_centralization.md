# Step Transition Centralization

**Status:** Proposed work plan; implementation not started  
**Created:** July 24, 2026  
**Scope:** Backend gameplay turn transitions and their frontend contract  
**Primary context:** [`../06_Gameplay_Systems/Turn_by_Turn_System.md`](../06_Gameplay_Systems/Turn_by_Turn_System.md)  
**Related systems:**

- [`../06_Gameplay_Systems/Possession_Mgmt_System.md`](../06_Gameplay_Systems/Possession_Mgmt_System.md)
- [`../05_UESS_System/UESS_System.md`](../05_UESS_System/UESS_System.md)
- [`../06_Gameplay_Systems/Rebound_System.md`](../06_Gameplay_Systems/Rebound_System.md)
- [`Sim_Perf_Capstone.md`](Sim_Perf_Capstone.md)
- [`Unified_Animation_System.md`](Unified_Animation_System.md)

---

## 1. Purpose

Centralize the contract that moves the game from one turn to the next without
rewriting the basketball resolution systems.

The current engine generally transitions correctly, but transition authority is
distributed across outcome handlers, `TurnManager`, `GameManager`, rebound and
Fast Break integrations, free-throw handling, EOQ utilities, and several
post-resolution repair blocks. New gameplay features can resolve their immediate
outcome correctly while omitting one of the downstream requirements:

- update the backend routing state;
- publish the matching `next_play_type` / `next_turn`;
- flip possession at the correct moment;
- synthesize a DREB, OREB, BIP, SIP, FT, or timeout turn;
- preserve the offense identity of the turn that just animated;
- prepare HCO entry/handoff state;
- terminate a quarter without creating an extra inbound;
- maintain UESS ball and coordinate ownership.

The objective is a single transition-planning contract and a single transition
execution boundary, introduced incrementally while preserving today's working
behavior.

---

## 2. Audit Summary

### 2.1 Existing strengths

- `GameManager._append_turn()` is a successful universal funnel for appending
  turns, stamping common state, checking foul-outs, and syncing coordinates.
- `GameManager.switch_possession()` is the single primitive that swaps offense
  and defense.
- Backend `offense_team_id` is the frontend's possession authority.
- Frontend `handleTurnTransition()` assigns the backend-provided offense rather
  than independently calculating possession.
- The engine already has a transition registry, validator, and event detector
  that can be modernized rather than starting from nothing.

### 2.2 Fragmentation found

A static audit found:

- 111 assignments to `game_state["offensive_state"]`;
- 54 direct subscript assignments to `result["next_play_type"]`, plus many
  result-dictionary constructions;
- six active `switch_possession()` calls within `simulate_macro_turn()`;
- transition writes spread across `phase_resolution.py`, `shot_manager.py`,
  `turn_manager.py`, `game_manager.py`, pressure-shot modules, Fast Break
  integrations, rebound handling, and EOQ handling.

Three overlapping representations currently exist:

1. `game_state["offensive_state"]` — actual backend routing authority;
2. `result["next_play_type"]` — public/informational route;
3. `result["next_turn"]` — post-resolution normalization.

`TurnManager.run_micro_turn()` explicitly treats handlers as the source of truth
for `offensive_state`, while `GameManager.determine_next_turn()` is described as
centralized SS&S. In practice, `determine_next_turn()` normally accepts the
handler's `next_play_type`, does not apply `offensive_state`, does not execute a
possession change, and only runs for the main result and batched OREB results.

### 2.3 Existing registry drift

`BackEnd/utils/transition_registry.py` and its validator are not production
authorities and no longer match the canonical turn model:

- discrete `DREB` is omitted and still described as embedded;
- `TIMEOUT` is omitted;
- inbound enum names differ from canonical backend names;
- production routing does not consult the registry;
- warning output is disabled;
- validation often lacks enough source-state information and passes;
- possession flags may already be cleared before validation runs.

The registry should not be made authoritative until it is rebuilt from current
runtime behavior and verified against all special paths.

---

## 3. Architectural Target

Use four explicit layers:

```text
Outcome resolver
    |
    | basketball facts only
    v
Transition planner
    |
    | immutable TransitionPlan
    v
Transition executor
    |
    | state mutation + synthetic transition turns
    v
Universal append funnel
```

### 3.1 Outcome resolver

Existing gameplay resolvers continue to decide basketball facts:

- make, miss, block;
- rebound winner and type;
- foul classification and awarded free throws;
- steal, dead ball, charge, defensive stop;
- pressure choice;
- timeout request;
- final-turn and EOQ facts.

Resolvers should eventually stop coordinating the full downstream transition.

### 3.2 Transition planner

A pure, deterministic function converts the source turn plus game-state facts
into a transition plan. It must:

- perform no database access;
- perform no RNG draws;
- perform no animation build;
- mutate neither the result nor game state;
- use bounded O(1) field checks;
- be callable in tests and temporary shadow-parity mode.

### 3.3 Transition executor

The executor applies one plan and is the sole eventual authority for:

- setting `game_state["offensive_state"]`;
- publishing `next_play_type` and `next_turn`;
- calling `switch_possession()`;
- clearing/consuming `possession_flips`;
- deciding which synthetic transition turn is required;
- preparing HCO-entry state;
- respecting terminal quarter boundaries.

It may delegate construction of turn-specific animation payloads to the
existing BIP, SIP, DREB, OREB, FT, and timeout builders. Centralization does not
mean one function should contain every turn's animation details.

### 3.4 Append funnel

All produced turns continue through `GameManager._append_turn()`. Transition
centralization must not create a competing append path or duplicate coordinate
sync.

---

## 4. Proposed TransitionPlan Contract

The exact implementation type will be aligned before coding. Conceptually, the
plan should include:

| Field | Purpose |
|---|---|
| `source_turn` | Canonical turn type that produced the outcome |
| `source_result` | Canonical outcome/event classification |
| `next_offensive_state` | State consumed by the next `run_micro_turn()` |
| `next_play_type` | Public route placed on the source turn |
| `next_turn` | Public next-row type; normally identical to `next_play_type` |
| `possession_change` | Whether team possession changes |
| `flip_timing` | Before synthetic turn, after current turn, already applied, or none |
| `synthetic_turn` | None, DREB, OREB, BIP, SIP, FREE_THROW, or TIMEOUT |
| `pressure_setup` | None, HCO, FCP, or HCT |
| `hco_entry_mode` | None, inbound setup, DREB outlet, FB bring-up, or other canonical mode |
| `terminal_period` | Whether the turn terminates the quarter/period |
| `suppress_inbound` | Prevent BIP/SIP synthesis at EOQ or while FT/timeout is pending |
| `preserve_source_offense_id` | Keep the just-completed turn's offense identity for animation |
| `reason` | Stable event/reason code for tests and debugging |

Avoid placing player objects, full lineups, animation structures, or database
documents in the plan.

---

## 5. Canonical Turn and Event Vocabulary

Before implementation, align one canonical enum/value set with the live engine.

### 5.1 Canonical turn types

- `OPENING_TIP`
- `HCO`
- `FCP`
- `HCT`
- `FAST_BREAK`
- `OREB`
- `DREB`
- `BASELINE_INBOUND`
- `SIDE_INBOUND`
- `FREE_THROW`
- `TIMEOUT`

Terminal outcomes such as `FINAL_HOLD` and `RUN_OUT_CLOCK` are result/event
types, not routable next turns.

### 5.2 Canonical transition events

Use stable event codes rather than free-form descriptive strings. At minimum:

- made field goal;
- missed/blocked field goal with OREB;
- missed/blocked field goal with DREB;
- putback make/miss;
- final FT make;
- final FT miss with OREB/DREB;
- shooting foul / and-one;
- non-shooting defensive foul;
- offensive foul / charge;
- dead-ball turnover;
- steal;
- Fast Break defensive stop;
- pressure break;
- timeout;
- foul-out interruption;
- terminal EOQ;
- FLSS continuation.

The event vocabulary must capture facts needed for planning without duplicating
shot, foul, rebound, or pressure resolution.

---

## 6. Migration Principles

1. **Parity first.** Existing runtime behavior is the initial reference even
   where the architecture is awkward.
2. **No big-bang replacement.** Migrate one transition family at a time.
3. **No basketball retuning.** Transition consolidation must not alter outcome
   probabilities, shot selection, foul rates, rebound selection, or clock
   consumption.
4. **No RNG topology changes.** Planning and execution must not draw RNG or
   reorder existing resolver draws.
5. **No database access in the loop.** Follow `Sim_Perf_Capstone.md`.
6. **No extra animation builds.** Reuse existing turn builders and UESS payloads.
7. **Backend remains authoritative.** Frontend continues to consume
   `offense_team_id` and turn payloads; it does not calculate gameplay routing.
8. **Preserve source-turn identity.** A possession flip must not rewrite the
   offense identity used to animate the turn that just completed.
9. **Synthetic turns remain real turns.** DREB, OREB, BIP, SIP, FT, and timeout
   rows continue through `_append_turn()`.
10. **EOQ is last.** Terminal clock and FLSS paths migrate only after ordinary
    transitions have proven parity.

---

## 7. Phased Work Plan

## Phase 0 — Freeze and inventory current behavior

**Goal:** Establish a trustworthy current-state transition matrix before moving
authority.

Tasks:

1. Enumerate every live transition by:
   - source turn;
   - result/event;
   - rebound/foul/pressure context;
   - possession change;
   - synthetic turn;
   - resulting `offensive_state`;
   - published `next_play_type` / `next_turn`;
   - quarter/timeout/FT exceptions.
2. Include separate rows for:
   - ordinary HCO;
   - FCP and HCT;
   - every migrated Fast Break family;
   - OREB chains;
   - discrete DREB;
   - free throws;
   - BIP/SIP;
   - timeout and foul-out resume;
   - EOQ/FLSS.
3. Compare the matrix with:
   - `Turn_by_Turn_System.md`;
   - `Possession_Mgmt_System.md`;
   - transition registry;
   - current tests.
4. Mark documentation or registry entries that are stale; do not silently
   reinterpret runtime behavior.

**Deliverable:** Reviewed canonical transition matrix and vocabulary.

**Exit criteria:** Every live transition mutation in the audit maps to a matrix
row or is identified as dead/debug code.

---

## Phase 1 — Rebuild the registry as a descriptive contract

**Goal:** Make the registry accurately describe the current engine without
changing runtime routing.

Tasks:

1. Replace the stale turn enum with the canonical turn set.
2. Add discrete DREB and TIMEOUT transitions.
3. Replace descriptive string matching with stable event codes.
4. Represent possession change and synthetic-turn requirements explicitly.
5. Update validation so source turn comes from the actual turn payload rather
   than inferred stale `_previous_offensive_state`.
6. Keep the registry non-authoritative during this phase.

**Verification:**

- Registry completeness tests.
- No duplicate transition keys.
- Every canonical turn has defined outgoing/terminal behavior.
- Existing simulation output remains byte-identical.

**Exit criteria:** Registry and matrix agree, with no production behavior change.

---

## Phase 2 — Introduce a pure planner in shadow mode

**Goal:** Calculate the proposed plan alongside existing logic and compare it
without applying it.

Tasks:

1. Define the immutable `TransitionPlan` contract.
2. Implement a pure planner from normalized turn facts.
3. At one post-resolution boundary, calculate the shadow plan.
4. Compare it with:
   - actual `offensive_state`;
   - actual `next_play_type` / `next_turn`;
   - actual possession state;
   - appended synthetic turn, if any.
5. Keep shadow comparison:
   - test-first;
   - gated off in bulk simulations if runtime diagnostics are retained;
   - free of eager report building and database writes.
6. Resolve mismatches by correcting the matrix/planner or documenting a genuine
   legacy exception. Do not mutate live behavior in shadow mode.

**Verification:**

- Focused transition matrix tests.
- Seeded full-game and multi-game parity.
- Profile one game to prove no meaningful hot-path regression.

**Exit criteria:** Zero unexplained shadow mismatches across representative
games and all targeted unit scenarios.

---

## Phase 3 — Centralize simple, low-risk transitions

**Goal:** Make the planner/executor authoritative for transitions with minimal
rebound or clock complexity.

Suggested order:

1. Opening tip → HCO.
2. BIP → HCO/FCP/HCT.
3. SIP → HCO.
4. Ordinary made FG → BIP.
5. Ordinary dead-ball turnover / charge → SIP.
6. Timeout resume to SIP/BIP/FT.

Tasks per family:

1. Route through the planner.
2. Execute state/public-route/flip/synthetic-turn actions once.
3. Remove migrated handler writes only after parity.
4. Preserve existing builders and animation payloads.

**Verification:**

- Seeded exact-diff because no RNG draws should change.
- Home/away and user/CPU modes.
- Turn-by-turn and full simulation.
- Timeout and foul-out interruption coverage.

**Exit criteria:** Migrated handlers no longer write their own transition state.

---

## Phase 4 — Centralize foul and free-throw transitions

**Goal:** Unify routes into and out of FT/SIP/BIP while preserving foul
resolution.

Coverage:

- shooting fouls;
- and-one;
- bonus and one-and-one;
- non-shooting defensive fouls;
- offensive fouls and charges;
- blocking fouls;
- final FT make/miss;
- foul-out timeout and resume.

Special invariants:

- No BIP before pending free throws.
- Final made FT flips before BIP.
- Final missed FT respects OREB/DREB.
- Timeout/foul-out resumes retain shooter and remaining attempts.

**Exit criteria:** FT state and public routing are produced from one plan, with
no handler-specific route repair.

---

## Phase 5 — Centralize pressure and Fast Break transitions

**Goal:** Consolidate FCP/HCT/FB routing after ordinary possession transitions
are stable.

Coverage:

- BIP pressure setup;
- FCP/HCT break to HCO;
- pressure steals and dead balls;
- pressure shots and fouls;
- Fast Break make/miss/block;
- Fast Break defensive stop → HCO;
- steal-initiated Fast Break;
- migrated RR, Triangle, Covert Release, and After-Steal families.

Special invariants:

- Pressure selection remains a basketball decision made before planning.
- FB defensive stop does not flip possession.
- Steal/DREB paths flip exactly once.
- HCO bring-up state is prepared without embedding duplicate setup animation.

**Exit criteria:** Fast Break integrations return normalized outcome facts and
do not independently coordinate route fields.

---

## Phase 6 — Centralize OREB/DREB and batched transitions

**Goal:** Move the most structurally complex ordinary transitions after the
planner/executor has proven itself.

Coverage:

- miss/block → OREB;
- OREB kickout;
- putback make/miss;
- consecutive OREBs;
- OREB miss → discrete DREB;
- HCO/FCP/HCT/FB/FT miss → discrete DREB;
- DREB → HCO/FB;
- DREB OTB foul;
- HCO outlet/handoff preparation.

Design requirement:

The executor must support a transition sequence, not just a single next-state
string. Example:

```text
SHOT MISS
  -> append shot
  -> append DREB capture
  -> flip possession once
  -> arm HCO entry
```

Do not collapse the discrete DREB row into the shot or HCO turn.

Special invariants:

- Source MISS/BLOCK keeps its original offense identity.
- DREB capture uses post-shot coordinates.
- Possession flips exactly once.
- OREB-loop DREB does not double flip.
- Last batched foul/dead-ball outcome controls SIP synthesis.
- Outlet/handoff is authored once.

**Exit criteria:** Main-turn and OREB-loop DREB promotion use one transition
sequence planner/executor path.

---

## Phase 7 — Centralize EOQ and FLSS transitions

**Goal:** Migrate terminal clock behavior last.

Coverage:

- final shot make/miss/block;
- terminal OREB/DREB;
- FLSS after DREB/inbound;
- BIP runoff;
- `FINAL_HOLD`;
- `RUN_OUT_CLOCK`;
- no-inbound terminal suppression;
- quarter-complete payload behavior.

Special invariants:

- The final playable turn is emitted and animated before quarter completion.
- No BIP/SIP is synthesized after a terminal period event.
- Terminal DREB remains visible when required.
- No extra clock draw/runoff is introduced.

**Exit criteria:** EOQ utilities provide event facts or planner inputs but no
longer independently rewrite overlapping route fields.

---

## Phase 8 — Retire duplicate authority and harden enforcement

**Goal:** Complete the SS&S migration.

Tasks:

1. Remove obsolete transition assignments from migrated handlers.
2. Retire or repurpose `determine_next_turn()`.
3. Make planner output the only authority for:
   - `offensive_state`;
   - `next_play_type`;
   - `next_turn`;
   - possession change instructions.
4. Add a test/static guard preventing new direct transition-state assignments
   outside the planner/executor and explicitly approved boot/resume seams.
5. Update all canonical documentation.
6. Remove stale transition repair blocks only after parity proves them
   unnecessary.

**Exit criteria:** A new gameplay resolver cannot complete without returning
normalized facts that the planner can route.

---

## 8. Verification Strategy

### 8.1 Transition matrix tests

For every matrix row, assert:

- next backend state;
- public `next_play_type`;
- public `next_turn`;
- possession change;
- flip timing;
- synthetic turn;
- source-turn offense identity;
- terminal handling;
- HCO-entry mode.

### 8.2 Sequence integration tests

At minimum:

- make → BIP → HCO;
- make → BIP → FCP/HCT;
- dead ball / charge → SIP → HCO;
- shooting foul → FT sequence → BIP;
- final FT miss → OREB/DREB;
- miss → OREB → kickout;
- miss → OREB → putback miss → DREB → HCO;
- miss/block → DREB → HCO/FB;
- steal → HCO/FB;
- FB defensive stop → HCO without flip;
- DREB OTB foul → SIP/FT;
- timeout and foul-out resume;
- final make/miss/DREB at EOQ.

Run home/away variants where geometry or possession identity differs.

### 8.3 Determinism

Transition centralization must not change RNG draw count.

- Use `PYTHONHASHSEED=0`.
- Use seeded exact-diff for behavior-preserving migrations.
- If a migration unexpectedly changes draws, stop and identify the draw-site
  difference; do not accept distributional similarity for an intended
  no-basketball-change refactor.

### 8.4 Performance

Per `Sim_Perf_Capstone.md`:

- no DB calls in planner/executor;
- no eager debug report construction;
- no extra animation or defender-grid builds;
- no full-lineup scans in the planner;
- diagnostics gated off for full/CPU/PS simulation;
- profile one full-sim game before and after each material phase;
- timing claims use repeated/median runs.

### 8.5 Frontend

Verify that:

- frontend continues to read `offense_team_id`;
- possession-change events fire once;
- DREB/BIP/SIP/FT schema and legacy playback routes remain unchanged;
- final turns animate before quarter completion;
- no frontend gameplay route calculation is introduced.

---

## 9. Risk Register

| Risk | Mitigation |
|---|---|
| Big-bang transition regression | Shadow mode and family-by-family migration |
| Double possession flip | Plan carries explicit flip timing; executor applies once |
| Source turn animated with new offense | Preserve source `offense_team_id`; flip affects following turn |
| DREB/OREB sequence collapse | Support transition sequences and keep synthetic rows |
| FT followed by erroneous BIP | Pending-FT invariant in planner |
| EOQ creates extra inbound | Terminal/suppress-inbound plan fields; EOQ migrates last |
| Pressure choice lost | Resolver supplies chosen pressure; planner only routes it |
| RNG drift | Planner/executor draw no RNG; seeded exact-diff |
| Sim slowdown | O(1) pure planning, no DB/animation work, profile each phase |
| Registry becomes a second authority | Registry and planner share one canonical definition before runtime cutover |
| Documentation drift | Update canonical docs at each migrated phase |

---

## 10. Non-Goals

- Do not retune basketball outcome probabilities.
- Do not redesign shots, fouls, rebounds, steals, pressure, or Fast Break
  resolution.
- Do not combine discrete DREB/OREB/inbound rows merely to reduce turn count.
- Do not move gameplay routing to the frontend.
- Do not redesign UESS or animation schemas.
- Do not change quarter duration, shot-clock policy, or EOQ strategy.
- Do not add transition persistence inside the simulation loop.
- Do not add default-on bulk-simulation diagnostics.

---

## 11. Decisions to Align Before Implementation

1. Whether `TransitionPlan` should be a frozen dataclass, typed dictionary, or
   another immutable structure.
2. Whether the canonical registry should directly drive the planner or remain
   a validation representation generated from the same definitions.
3. Where the single planning boundary belongs:
   - immediately after `run_micro_turn()`;
   - inside a new `GameManager` transition coordinator;
   - or split between outcome normalization and macro-sequence planning.
4. Whether shadow comparison should exist only in tests or temporarily in
   interactive runtime behind a diagnostics gate.
5. Which low-risk family should be the first production migration after shadow
   parity.

**Recommended starting alignment:** agree on the normalized event vocabulary,
the `TransitionPlan` fields, and the exact Phase 0 transition-matrix format
before writing runtime code.
