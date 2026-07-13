# Shot Classification → UESS Single-Coord-Source Fix (Option C)

**Scope:** Make 2PT/3PT classification read the **same terminal shoot coord the FE renders**, for all skeleton-shot turn types (HCO, Final Turn, FCP, HCT). Supersedes the "prefer explicit coords / named-spot" framing in Phase 1/3 of [three_pointer_classification.md](../three_pointer_classification.md).

> **STATUS (2026-07-05): ~98% variant SHIPPED, exact Option C DEFERRED.** HCO / Final Turn / FCP now classify from the emitter's terminal shoot coord via an RNG-neutral throwaway pre-pass (`_uess_terminal_shoot_coord`), cutting misclassification from ~25% → ~2-3% (regression-clean). The **exact 0%** version (§4d pin) was deferred because the pre-pass can't perfectly reproduce the late render context (see §"Reality check" below); true parity needs pinning the coord into the emitter core. Residual gap documented in `UESS_System.md` §12.1.
>
> **Reality check (measured during build):** the scope's premise — "emitter is deterministic from `(skeleton, animations)`, so an early pre-pass == the late render" — does **not** hold: live context (backfill / entry orchestrator / prior-turn seam) differs between the pre-resolve call and the turn_manager emit, so the pre-pass coord degenerates toward the animator row-end value (~98% class-correct, not coord-identical). Exact 0% therefore requires the §4d pin, not just the pre-pass.

---

## 1. Problem (empirically measured)

Classification reads `roles["shot_spot"]`, set pre-emit from the skeleton **named spot** (or explicit coords). The FE renders the shooter at the emitter's **terminal shoot-step coord**, which is computed by a step-sequential positional pass and diverges from the named spot / animator row end.

Probe: 60 clean HCO shots (mock sim), comparing `classify(shot_spot)` vs `classify(render coord)`:

| Candidate coord for classification | Residual misclassification vs render |
|---|---|
| `shot_spot` (today) | **15/60 (25%)** |
| `shooter.coords` after `apply_coords` (row end) | 1/60 (~1.7%) |
| **Emitted shoot-step coord (Option C)** | **0/60 (exact)** |

Root cause: **two coord pipelines.** Classification uses a pre-emit named/row coord; the FE uses the emitter's positional-pass terminal coord. `apply_coords`/`shooter.coords` is *not* the render truth — it matches the emitted coord in only ~42% of shots (only ~25% flip the arc, hence the 1.7% residual). The only exact source is the emitter's terminal step coord.

**Broader implication:** backend `shooter.coords` already desyncs from the rendered shooter position in ~58% of shots. Classification is the visible symptom; the emitter is the true single coord source. Fixing this closes a real UESS §1/§8 gap, not just the 3PT bug.

## 2. Why the emitted coord is the authority

- Shooter is the **gate** on the shot step → `_build_step_end_coords_with_interrupts` gives it the full `destination` ([skeleton_step_emitter.py:1687](../../../BackEnd/engine/skeleton_step_emitter.py#L1687), [:784](../../../BackEnd/engine/skeleton_step_emitter.py#L784)).
- The terminal coord is produced by the **positional loop** (`for i in range(num_steps)`, [:1498-1865](../../../BackEnd/engine/skeleton_step_emitter.py#L1498)) — **outcome-independent** (only the final step's `next` pointer branches on result_type).
- The **outcome-dependent** work (micro-movements + post-shot sub-steps) runs *after*, at [:1996-2001](../../../BackEnd/engine/skeleton_step_emitter.py#L1996), and appends sub-steps rather than mutating the shoot-step coord (probe: `shoot.start == shoot.end == render`, static).
- The emitter is **deterministic** given `skeleton + animations`, and that single build already exists before `resolve_shot` (HCO single-build reuse, [phase_resolution.py:7268](../../../BackEnd/engine/phase_resolution.py#L7268), stamped to `shot_result["animations"]`).

∴ The terminal shoot coord can be computed once, pre-resolve, from the shared build — and the later emitter reproduces the identical coord.

## 3. The single-source contract

> The shooter's terminal shoot coord is computed **once** from `(skeleton, animations)` and is the sole input to: (a) 2PT/3PT classification, (b) `shooter.coords` / `roles["shot_spot"]`, (c) the FE-rendered shoot step. No named-spot lookup on the dynamic path.

## 4. Implementation

### 4a. Extract the terminal-coord resolver (new)
Factor the shoot-step slice of the positional pass into a reusable, outcome-independent function:

```
resolve_terminal_shoot_coord(game, skeleton, animations, roles, off_lineup, def_lineup) -> {x, y} | None
```

- Runs the same start-coord accumulation + gate/`_build_step_end_coords_with_interrupts` logic the emitter uses, returning `end.coords[shooter_id]` for the final (shoot) step.
- Reuses existing helpers (`_shooter_pos_in_step`, `_build_step_end_coords_with_interrupts`, archetype rates) — no reimplementation of geometry.
- Display-oriented output (same frame the emitter emits) → **no away re-mirror** (matches the explicit-coords branch).
- Returns None if it can't resolve (missing build / no shoot step) → callers fall back to today's `set_shooter_coords_from_skeleton_last_step`.

### 4b. Rewrite `set_shooter_coords_from_skeleton_last_step` priority
New ladder (replaces named-spot-first for location-only steps):

| Priority | Source |
|---|---|
| 1 | Explicit shoot-step `coords` (freelance/attack-drive) — unchanged |
| 2 | **`resolve_terminal_shoot_coord(...)`** ← the fix |
| 3 | `HCO_STRING_SPOTS[location]` named spot — true last-resort only |

Stamp both `shooter.coords` and `roles["shot_spot"]` from the resolved coord. Delete the "so block spot uses shot location" comments (unfounded — §6).

### 4c. Wire the 4 call sites
Pass the in-scope build to the resolver. All four already build + `apply_coords` immediately before the call:

| Turn | Resolver | Build var |
|---|---|---|
| HCO | [phase_resolution.py:7275](../../../BackEnd/engine/phase_resolution.py#L7275) | `animations` |
| Final Turn | [:6200](../../../BackEnd/engine/phase_resolution.py#L6200) | `final_turn_animations` (guarded — skip priority 2 if None) |
| FCP | [:7851](../../../BackEnd/engine/phase_resolution.py#L7851) | `animations` |
| HCT | [:9960](../../../BackEnd/engine/phase_resolution.py#L9960) | `animations` |

One chokepoint fix → all four turn types.

### 4d. Guarantee emitter parity
The emitter is deterministic from the same `(skeleton, animations)`, so it already reproduces the resolved coord. Add a **debug assertion** (behind a flag) that `resolve_terminal_shoot_coord(...) == emitted shoot-step end.coords[shooter]` to lock the contract and catch future drift.

## 5. Caveats / boundaries
- **Dunk / at-rim micro is outcome-dependent** (`resolve_dunk_micro_stamp` reads MAKE/MISS/BLOCK) — rim finishes stay forced-2. For jump-shot micros that displace the shooter, classify from **`micro_release_coord`** (post-footwork), planned before shot math so emit and scoring share one pinned destination.
- **Forced-value paths unchanged:** OREB putback (forced-2), FT (forced-1), Steal/RR/CR rim (forced-2). Option C only governs arc-classified jump shots.
- **Motion synthetic shoot step** often omits the shooter from the animator destinations → resolver must use the carried-forward start coord (same as emitter's `dest is None` branch, [:778](../../../BackEnd/engine/skeleton_step_emitter.py#L778)).

## 6. Open items to confirm during build
1. **Block-reconciliation:** trace shows no consumer needs the *named* spot over a coord (only classification + result-stamp + FB geometry read `shot_spot`). Confirm before deleting the comment premise.
2. **Positional-pass factoring:** the start-coord accumulation currently lives inside the emitter's main loop; confirm it can be sliced into `resolve_terminal_shoot_coord` without duplicating the loop (ideal: emitter calls the same helper for step N-1).

## 7. Verification
- Re-run the probe (`scratchpad/probe2.py` logic): expect **0/60** `classify(shot_spot) != render`.
- Parity assertion (4d) green across a full-sim batch for all 4 turn types.
- Regression: existing shot/classification tests + the flaky-seeded suites still pass.

## 8. Tests (extends Phase 7)
- Dish-to-corner, shooter rendered inside arc → **2** (the Turn 42 regression).
- Step-back from key → 3; step-in from wing → 2.
- Named-spot fallback still classifies when no build coord (priority 3).
- Home/away parity (`x_away = 100 − x_home`).
- One case per turn type (HCO / Final Turn / FCP / HCT).
- Parity: `resolve_terminal_shoot_coord == emitted shoot-step coord`.

## 9. Ripple
Corrects ~25% of HCO arc calls → **3PT rate will drop** (corner dishes 3→2). Correct, but lands before FG%/3PT% tuning ([project_shot_system_tuning]). Don't tune around current (buggy) numbers.

## 10. Risk & sequencing
- **Risk: medium.** Additive priority ladder + one new resolver; the real risk is factoring the positional pass faithfully (mitigated by the 4d parity assertion).
- **Sequence:** (1) build `resolve_terminal_shoot_coord` + parity assertion on HCO; (2) verify 0/60; (3) rewrite the chokepoint + wire 4 sites; (4) tests; (5) full-sim parity batch; (6) remove diagnostics.
- **Interim option:** priority-2 = `shooter.coords` (apply_coords) ships in one line at ~98% if a fast mitigation is needed before the resolver lands. Not exact; not a substitute for C.

## Tunable Constants
| Constant | Location | Effect |
|---|---|---|
| `UESS_SEAM_TELEPORT_GRID_EPSILON` | skeleton_step_emitter.py | teleport-detection threshold (unrelated, listed for the emitter knob set) |
| arc boundary table | shot_geometry.py `is_three_point_shot_from_coords` | the 3PT line; classification is only as correct as the coord fed in — this fix fixes the coord, not the line |
