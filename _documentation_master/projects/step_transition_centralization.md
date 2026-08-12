# Step Transition Centralization

**Status:** Proposed work plan; implementation not started  
**Created:** July 24, 2026  
**Last reviewed against code:** August 2, 2026
**Scope:** Backend gameplay turn transitions and their frontend contract  
**Canonical turn vocabulary:** [`../06_Gameplay_Systems/Turn_by_Turn_System.md`](../06_Gameplay_Systems/Turn_by_Turn_System.md)

**Related systems:**

- [`../06_Gameplay_Systems/Possession_Mgmt_System.md`](../06_Gameplay_Systems/Possession_Mgmt_System.md)
- [`../06_Gameplay_Systems/Rebound_System.md`](../06_Gameplay_Systems/Rebound_System.md)
- [`../05_UESS_System/UESS_System.md`](../05_UESS_System/UESS_System.md)
- [`Sim_Perf_Capstone.md`](Sim_Perf_Capstone.md)

---

## 1. Objective

Create one contract that moves the game from a resolved outcome to the next
turn, without rewriting or retuning basketball resolution.

Today, outcome handlers generally transition correctly, but they collectively
coordinate several downstream responsibilities:

- set `game_state["offensive_state"]`;
- publish `next_play_type` and `next_turn`;
- flip possession at the correct point;
- create DREB, OREB, BIP, SIP, free-throw, and timeout turns;
- preserve the completed turn's offense identity for animation;
- prepare pressure or HCO entry state;
- suppress extra turns at the end of a period.

The target is a pure transition planner followed by one transition execution
boundary. Migration must be incremental and preserve existing runtime behavior.

---

## 2. Verified Current State

### What already works

- `GameManager._append_turn()` is the universal append and coordinate-sync
  funnel. Centralization must continue to use it.
- `GameManager.switch_possession()` is the possession-swap primitive.
- Backend `offense_team_id` is authoritative for the frontend.
- Frontend `handleTurnTransition()` consumes backend possession rather than
  independently calculating gameplay routing.
- Existing inbound, rebound, free-throw, timeout, and pressure builders can be
  reused by a centralized executor.

### What remains fragmented

Three overlapping representations remain:

1. `game_state["offensive_state"]` controls the next backend route.
2. `result["next_play_type"]` publishes the handler-selected route.
3. `result["next_turn"]` is normalized later by
   `GameManager.determine_next_turn()`.

`determine_next_turn()` is not the transition authority: for most gameplay
results it accepts a handler's existing `next_play_type`. It does not itself
apply `offensive_state`, flip possession, or coordinate synthetic turns.

Transition writes and repair logic remain distributed across outcome handlers,
`TurnManager`, `GameManager`, rebound loops, Fast Break and pressure paths,
free-throw handling, and EOQ utilities.

### Registry status

`BackEnd/utils/transition_registry.py` is descriptive and non-authoritative. It
does not yet match the canonical runtime model:

- discrete `DREB` and `TIMEOUT` are absent;
- inbound enum names differ from canonical turn names;
- events are free-form strings rather than stable codes;
- production routing does not consult the registry;
- event-validation warnings are disabled and source context can be incomplete.

Do not make the registry authoritative until it is rebuilt from verified
runtime behavior and parity-tested.

### Immediate `offensive_state` guardrail

Before the full planner/executor migration, add a small defense-in-depth check
for the current handler-owned contract. `offensive_state` is the canonical next
resolver (`HCO`, `HCT`, `FCP`, `FAST_BREAK`, or `FREE_THROW`);
`next_play_type` remains informational. `OREB`, `DREB`, and inbound turns are
coordinated through their existing synthetic-turn and `pending_*` payloads, not
by adding new `offensive_state` values.

The guard must detect whether a handler explicitly published its next routing
state, not merely whether the value changed—a valid HCO → HCO transition can
write the same value. Start with a diagnostic assertion/log in test or debug
profiles, then cover every legitimate same-state and `pending_*` exception
before considering production enforcement.

This guardrail addresses two May 2026 After-Steal incidents where MAKE-no-foul
and MISS-no-foul exits left `offensive_state="FAST_BREAK"`, producing a repeating
BIP/FB route. The resolver fixes shipped, but the informal contract remains easy
for a new exit path to violate. Existing `transition_validator.py` does not close
this gap: it validates the resulting state when enough context exists, does not
prove the handler wrote it, and its invalid-transition warning in `GameManager`
is currently disabled.

Do not introduce the full `TransitionPlan` merely to obtain this guardrail. It
is a bounded precursor to the phased centralization below.

---

## 3. Target Architecture

```text
Outcome resolver
    -> normalized basketball facts
Transition planner
    -> immutable TransitionPlan
Transition executor
    -> state mutation and synthetic-turn instructions
GameManager._append_turn()
    -> universal append and coordinate sync
```

### Outcome resolvers

Existing resolvers continue to decide basketball facts: outcome, rebound type,
foul and free-throw awards, pressure choice, timeout request, and terminal-clock
facts. They should eventually stop coordinating the full downstream route.

### Transition planner

The planner converts normalized facts into a plan. It must:

- be pure and deterministic;
- perform no RNG draws, database access, or animation construction;
- mutate neither the result nor game state;
- use bounded field checks suitable for the simulation hot path;
- support tests and temporary shadow-parity comparison.

### Transition executor

The executor is the eventual sole authority for:

- `offensive_state`, `next_play_type`, and `next_turn`;
- possession changes and flip timing;
- synthetic-turn selection and sequencing;
- pressure/HCO-entry preparation;
- terminal-period suppression.

It delegates animation payload construction to existing turn-specific builders.
All resulting turns continue through `_append_turn()`.

---

## 4. Proposed Contract

The exact type remains an implementation decision. The conceptual
`TransitionPlan` needs only routing data:

| Field | Purpose |
|---|---|
| `source_turn` | Canonical turn type that produced the outcome |
| `event_code` | Stable normalized event/reason code |
| `next_offensive_state` | State consumed by the next micro turn |
| `next_play_type` | Public route placed on the completed source turn |
| `next_turn` | Public next-row type |
| `possession_change` | Whether possession changes |
| `flip_timing` | None, before/after a synthetic turn, or already applied |
| `synthetic_turns` | Ordered DREB/OREB/BIP/SIP/FT/TIMEOUT instructions |
| `pressure_setup` | None, HCO, FCP, or HCT |
| `hco_entry_mode` | Inbound, DREB outlet, FB bring-up, or another existing mode |
| `terminal_period` | Whether this transition terminates the period |
| `suppress_inbound` | Prevent an inbound while FT/timeout/EOQ state is pending |
| `preserve_source_offense_id` | Preserve the completed turn's animation identity |

Do not place player objects, lineups, animation structures, or database
documents in the plan.

Before implementation, define stable event codes for at least:

- made field goal;
- miss/block with OREB or DREB;
- putback make/miss and OREB kickout;
- final FT make or miss with OREB/DREB;
- shooting foul/and-one and non-shooting defensive foul;
- offensive foul/charge and dead-ball turnover;
- steal, pressure break, and FB defensive stop;
- timeout/foul-out interruption;
- terminal EOQ and FLSS continuation.

Use the canonical turn types in `Turn_by_Turn_System.md`; do not introduce a
second vocabulary in this project.

---

## 5. Required Invariants

1. Existing behavior is the initial reference, including documented legacy
   exceptions.
2. Migrate one transition family at a time; no big-bang replacement.
3. Do not change basketball probabilities, clock policy, or RNG draw order.
4. Planner and executor perform no database access or animation builds.
5. Backend remains authoritative; frontend continues to consume
   `offense_team_id` and turn payloads.
6. A possession flip must not rewrite the completed source turn's offense
   identity.
7. Possession changes exactly once per transition sequence.
8. DREB, OREB, BIP, SIP, FT, and TIMEOUT remain real turns routed through
   `_append_turn()`.
9. Do not collapse discrete DREB/OREB/inbound rows to reduce turn count.
10. Pending free throws prevent premature BIP synthesis.
11. Pressure selection remains a resolver decision; the planner only routes the
    selected setup.
12. EOQ and FLSS migrate last, after ordinary transition families prove parity.

---

## 6. Migration Plan

### Phase 0 — Freeze current behavior

Build a reviewed transition matrix containing:

- source turn and normalized event;
- possession change and exact flip timing;
- synthetic-turn sequence;
- resulting `offensive_state`, `next_play_type`, and `next_turn`;
- pressure/HCO-entry mode;
- FT, timeout, rebound-loop, and EOQ exceptions.

Cover HCO, FCP, HCT, Fast Break, OREB/DREB, FT, BIP/SIP, timeout/foul-out
resume, and EOQ/FLSS. Compare runtime code, existing tests, the registry,
`Turn_by_Turn_System.md`, and `Possession_Mgmt_System.md`. Mark disagreements;
do not silently reinterpret current behavior.

**Done when:** every live transition mutation maps to a matrix row or is
identified as dead/debug code.

### Phase 1 — Repair the descriptive registry

- Adopt canonical turn names.
- Add DREB and TIMEOUT.
- Replace descriptive event strings with stable event codes.
- Represent possession change and synthetic-turn requirements explicitly.
- Validate from the actual source-turn payload rather than inferred stale
  previous state.
- Keep the registry non-authoritative.

**Done when:** registry completeness tests pass, the registry agrees with the
matrix, and simulation output is unchanged.

### Phase 2 — Add a planner in shadow mode

- Define the immutable plan type and normalized inputs.
- Calculate a shadow plan at one post-resolution boundary without applying it.
- Compare it with actual backend state, public route fields, possession, and
  appended synthetic turns.
- Keep runtime diagnostics gated off for bulk simulations.

**Done when:** representative seeded games and focused scenarios have no
unexplained shadow mismatches or meaningful performance regression.

### Phase 3 — Migrate simple transitions

Suggested order:

1. Opening tip -> HCO.
2. BIP -> HCO/FCP/HCT.
3. SIP -> HCO.
4. Ordinary made FG -> BIP.
5. Dead-ball turnover/charge -> SIP.
6. Timeout resume -> SIP/BIP/FT.

For each family, make planner/executor output authoritative, prove exact parity,
then remove the migrated handler's duplicate transition writes.

### Phase 4 — Migrate fouls and free throws

Cover shooting fouls, and-one, bonus/one-and-one, non-shooting fouls,
offensive fouls, final FT make/miss, and foul-out timeout/resume.

Protect these invariants:

- no BIP before pending free throws;
- final made FT flips before BIP;
- final missed FT respects OREB/DREB;
- timeout/foul-out resume retains shooter and remaining attempts.

### Phase 5 — Migrate pressure and Fast Break

Cover BIP pressure setup, FCP/HCT breaks, pressure steals/dead balls/shots,
Fast Break outcomes and defensive stops, steal-initiated Fast Break, and all
migrated FB families.

Protect these invariants:

- FB defensive stop does not flip possession;
- steal/DREB paths flip exactly once;
- HCO bring-up is prepared without duplicate setup animation.

### Phase 6 — Migrate rebound sequences

Cover miss/block -> OREB/DREB, OREB kickout/putback/chains, discrete DREB from
all shot families, DREB -> HCO/FB, DREB OTB fouls, and HCO outlet/handoff.

The executor must support ordered sequences rather than only one next-state
string:

```text
SHOT MISS
  -> append shot
  -> append DREB capture
  -> flip possession once
  -> arm HCO entry
```

The source miss/block retains its offense identity, DREB uses post-shot
coordinates, OREB-loop promotion cannot double flip, and the last batched
foul/dead-ball result controls SIP synthesis.

### Phase 7 — Migrate EOQ and FLSS

Migrate final shot/rebound behavior, FLSS, BIP runoff, `RUN_OUT_CLOCK`,
terminal inbound suppression, and quarter-complete payloads.

The final playable turn must animate before quarter completion. Do not create a
BIP/SIP after a terminal event or introduce an additional clock draw.

### Phase 8 — Retire duplicate authority

- Remove obsolete transition writes and repair blocks after parity proves them
  unnecessary.
- Retire or repurpose `determine_next_turn()`.
- Make planner output the only authority for route fields and possession-change
  instructions.
- Add a test/static guard against new direct transition assignments outside the
  planner/executor and explicitly approved boot/resume seams.
- Update canonical system documentation.

**Done when:** every resolver returns normalized facts that the planner can
route, and migrated handlers no longer coordinate transition state.

---

## 7. Verification

### Matrix tests

For every transition row, assert:

- backend state and both public route fields;
- possession change and flip timing;
- ordered synthetic turns;
- preservation of source offense identity;
- terminal-period handling;
- pressure/HCO-entry mode.

### Sequence tests

At minimum:

- make -> BIP -> HCO/FCP/HCT;
- dead ball/charge -> SIP -> HCO;
- foul -> FT sequence -> BIP;
- final FT miss -> OREB/DREB;
- miss -> OREB -> kickout;
- miss -> OREB -> putback miss -> DREB -> HCO;
- miss/block -> DREB -> HCO/FB;
- steal -> HCO/FB;
- FB defensive stop -> HCO without a flip;
- DREB OTB foul -> SIP/FT;
- timeout and foul-out resume;
- final make/miss/DREB at EOQ.

Run home/away and user/CPU variants where possession identity or geometry may
differ.

### Determinism and performance

- Use seeded exact-diff tests and `PYTHONHASHSEED=0` for behavior-preserving
  migrations.
- Stop and locate any changed RNG draw site; distributional similarity is not
  sufficient for this refactor.
- Follow `Sim_Perf_Capstone.md`: no DB calls, eager debug reports, animation
  builds, or full-lineup scans in the planner/executor.
- Profile repeated full-sim runs before and after each material phase.
- Verify frontend possession events fire once and final turns animate before
  quarter completion.

---

## 8. Decisions Required Before Coding

1. Frozen dataclass, typed dictionary, or another immutable plan type.
2. Whether the registry drives the planner or both are generated from shared
   canonical definitions.
3. The single planning boundary: after `run_micro_turn()`, inside a new
   `GameManager` coordinator, or split between fact normalization and sequence
   planning.
4. Whether shadow comparison exists only in tests or temporarily in interactive
   runtime behind a diagnostic gate.
5. The first production transition family after shadow parity.

**Start with:** agree on normalized event codes, the minimal plan fields, and
the Phase 0 matrix format before adding runtime code.
