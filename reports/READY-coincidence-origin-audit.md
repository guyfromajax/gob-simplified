# READY — coincidence origin audit: no single cause, mostly structural, and the METRIC was wrong

Report: `reports/coincidence-origin-audit.md`. Branch `feature/animation-reward`, HEAD
`2073a5704`. Verified against the audit brief by Claude. **Read-only confirmed** — nothing fixed,
no flag added, no constant changed, all instrumentation in `scratch_coincidence_origin.py`.
`ovcensus.py` reused unmodified with the new probe CHAINED AFTER it, so baseline and attribution
come from the same run.

## Baseline reproduced exactly, first

222,188 steps / 10,040,944 pairs / 28,377 total / O-C/O-PF 3,501 / 0 probe errors — every figure
exact, and stable across a second full re-run.

## A definition error in my own prior relay, corrected

`ovcensus.py` computes coincidence TWO ways: float-identical (`d < 1e-9`) = **28,377**, and
same-rounded-cell = **36,468**. `spatial-screens-phase2-measurements.md` used the first for its
total row and the second for its per-pair rows — the two columns were never comparable to each
other. Every delta in that report was a within-run comparison on a consistent definition, so
**no conclusion changes**, but the mixed presentation was wrong. **Same-cell (36,468) is the
right definition** and is used throughout this audit.

## THE FINDING THAT REFRAMES EVERYTHING — exact coincidence was never the problem

Sprites are ~5.25 grid units wide, so two players 1-2 cells apart still overlap on screen:

| separation | pairs | share of all pairs | vs exact |
|---|---|---|---|
| exact | 28,377 | 0.283% | 1x |
| within 1.0 grid | 50,603 | 0.504% | 1.8x |
| within 2.0 grid | 156,232 | 1.556% | 5.5x |
| **within 5.25 (sprite width)** | **1,040,690** | **10.364%** | **36.7x** |

**Exact coincidence is 2.7% of the visible overlap problem.** 74.2% of steps contain at least one
sub-3.0-grid overlap. Eliminating EVERY exact coincidence in the game would leave ~97% of the
visual overlap untouched, and eliminating the whole O-C/O-PF excess would address roughly
**0.08%** of it.

## And the stack is 1.30x pure chance

Independence floor computed from each role's OWN observed cell distribution:

| | pair-steps | ratio |
|---|---|---|
| independence floor | 22,853 | — |
| observed | 36,468 | **1.60x** |
| **O-C/O-PF observed vs its floor** | 3,501 vs 2,702 | **1.30x** |

The entire O-C/O-PF "excess" is ~800 pair-steps = **2.2% of total coincidence**. And several
guard pairs sit BELOW their floor (0.44-0.71x) — the engine already actively keeps them apart.
Nothing is herding players together. (Marginals capped at top 400 cells per role, which makes the
floor an UNDER-estimate, so true ratios are even lower.)

## ALL FIVE COUNTERFACTUALS DISPROVEN

| counterfactual | total delta | O-C/O-PF delta |
|---|---|---|
| A: PF off `upper lowPost` | +0.9% | **-9.1%** |
| B: `OFFSET_SPOTS` displacement x2 | -0.8% | **+5.6%** (worse) |
| C: de-collide EVERY authored co-location | **-4.2%** | -1.6% |
| D/E: same, both skeleton sources | +0.9% | -9.1% |

Removing the PF from the spot that carries **73.9%** of the stack removes only **9%** of it — and
afterwards the stack is still 73.3% on that spot. Removing every authored same-step co-location
in the play catalogue removes 4.2%. The static evidence: C and PF are authored to the same spot
in the same step **once** across 51 authored steps. One authored collision cannot produce 2,588
runtime coincidences.

## What it actually is

- **77.2% of coinciding players are exactly where the emitter told them to be** (43.2%
  at_destination, 34.0% stationary_at_destination). Not a movement or interruption bug — the
  DESTINATIONS collide.
- **Creation vs persistence:** 36,468 pair-steps are only 23,762 distinct events. For O-C/O-PF,
  3,501 pair-steps are **1,543 runs (55.9% persistence)**.
- **One shape, 69.7% of the headline stack:** the C is parked at his destination on
  `upper lowPost` and the PF arrives on top of him. **73.9% of the entire O-C/O-PF stack is that
  one named spot.**
- **And it is the visible kind:** both bigs static 55.8% of the time, mean run **2.27 consecutive
  steps, max 8**. 13.90% of all steps contain a coincidence somewhere.

## Q6 relocation — narrowed, honestly not closed

86% of the +16.3% O-PF/O-SF rise is ONE cell (`lower lowPost`, away), 63% is
at_dest+at_dest in `build_skeleton_animation_steps`. Marked **TRACED**. The mechanism —
retargeting lands the screener on an occupied offensive spot — is marked **INFERRED, not
verified**, with the exact cross-tab that would confirm it named and explicitly not run.

## AN UNRESOLVED CONTRADICTION THE AGENT REFUSED TO EXPLAIN AWAY — worth its own task

A second probe attributes **37.5% of calls and 40.7% of executed skeleton steps to the six
hardcoded fallback scenes**, and counts 375 executed `PF -> upper lowPost` pos_actions from that
path. That cannot be squared with counterfactuals D/E being byte-identical to A. Both
measurements are reproducible; the agent could not determine which is misleading and declined to
guess, naming two unverified candidate explanations.

**If 40% of executed skeletons really do come from six hardcoded files, that is a significant
fact about the engine regardless of coincidence.** This is the most valuable loose thread in the
report.

Also: the harness seeds only the `successful` lean — `mid_play_change`, `contested` and `broken`
are all empty and fall back to `successful`.

## Two latent oddities, reported not fixed

1. **Players in `end_coords` on NEITHER lineup** — 96 of 36,468 (0.3%). The emitter is stamping
   coordinates for a player id in neither the offensive nor defensive lineup.
2. **Steps containing MORE THAN TEN players** — non-zero entries at 11, 13 and 17 (10 steps).
   Ten is the maximum a step should contain. Probably the same root cause, likely mid-substitution.

## Bottom line and recommendation

**No single cause. Mostly structural.** Not the screen script, not authored co-location, not a
movement bug. It is occupancy plus persistence — two bigs both live in the post — at 1.30x
chance, on a metric that captures 2.7% of what a viewer sees.

**Build nothing aimed at exact coincidence.** The arithmetic caps any possible win at a fraction
of a percent of the visible problem.

The only intervention the evidence supports: **extend Collision Phase 1
(`GOB_COLLISION_SEPARATION`) from defender-defender to ALL TEN players, and evaluate it on the
within-2.0-grid metric (156,232 pairs) rather than exact cells (28,377).** Phase 1 was the right
shape all along; it was scoped too narrowly and judged on the wrong metric.

Settle first: the skeleton-source contradiction, and Phase 1's own 49% residual with untuned caps.

No merge by Claude. Jamie merges.
