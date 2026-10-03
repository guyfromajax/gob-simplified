# What actually creates the exact-coincidence stacks — read-only audit

Branch `feature/animation-reward`, HEAD `2073a5704`. **READ-ONLY**: nothing was fixed, no flag
added, no constant changed. All instrumentation lives in `scratch_coincidence_origin.py` and a
scratch cell. All three screen flags and `GOB_COLLISION_SEPARATION` stayed **OFF** for every
number except the Q6 targeting run, which is marked.

**Rule 6e footing** (every number): worker `scratch_equiv3_fbdedupe.py`, Lancaster vs
Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game
per process, `SEED_DEFENSES=1`, `GOB_DEFENDER_AG_SPREAD` unset (ON), n=40 seeds 8000–8039, both
arms. `ovcensus.py` was reused unmodified; the new probe **chains after** it, so the baseline and
the attribution come from the same run.

## Baseline reproduced first

| | expected | measured |
|---|---|---|
| steps | ~222,188 | **222,188** |
| pairs | ~10,040,944 | **10,040,944** |
| total exact coincidence | ~28,377 | **28,377** |
| O-C/O-PF | ~3,501 | **3,501** |
| probe errors | — | **0** |

Exact, and stable across a second full re-run after the probe was extended.

### Correction: two different "exact" definitions, and my own prior report mixed them

`ovcensus.py` computes coincidence **two ways**:

- `PAIRS["exact|*"]` — float-identical, `d < 1e-9` → **28,377**
- `ROLEPAIR` — **same rounded cell** → **36,468**

`reports/spatial-screens-phase2-measurements.md` used the first for its "total" row and the
second for its per-pair rows, so its total and its pair rows were not on the same definition.
Every conclusion in that report was drawn from within-run comparisons on a consistent
definition, so **none of its deltas change** — but the two columns were never comparable to each
other. **Same-cell (36,468) is the right definition** for "two sprites on one cell" and is used
throughout below.

---

## Q1 — Attribution by placement path

Per-write tracing is not tractable (`end_coords` is a plain dict built at ~45 call sites). But
both coinciding players are always in the **same dict at the same step**, so what differs is the
branch inside that call. That is recoverable from the emitter's own inputs — `start["coords"]`,
`start["destination"]`, `end_coords` — with no guessing. **All rows below are TRACED** from those
inputs; none is inferred.

### Provenance of each coincident player-slot (n=72,936)

| class | n | share |
|---|---|---|
| at_destination | 31,510 | **43.2%** |
| stationary_at_destination | 24,824 | **34.0%** |
| no_destination | 8,618 | 11.8% |
| interrupted | 7,984 | 10.9% |

**77.2% of coinciding players are exactly where the emitter told them to be.** This is not a
movement or interruption bug. The destinations themselves collide.

### Creation vs persistence — the distinction that matters

36,468 coincident pair-steps are only **23,762 distinct events**: 34.8% of pair-steps are the
same pair still sitting there from the previous step. For O-C/O-PF it is worse — 3,501
pair-steps are just **1,543 runs (55.9% persistence)**.

So the table that answers "what *creates* a stack" is restricted to the first step of each run.

### (builder, class_a, class_b) at run creation — all pairs, n=23,762

| builder | classes | n | share | cum |
|---|---|---|---|---|
| `skeleton_step_emitter:build_skeleton_animation_steps` | at_dest + at_dest | 5,482 | 23.1% | 23.1% |
| `skeleton_step_emitter:build_skeleton_animation_steps` | at_dest + stationary | 3,418 | 14.4% | 37.5% |
| `dynamic_hct_step_emitter:_build_loop_step` | at_dest + at_dest | 3,130 | 13.2% | 50.6% |
| `skeleton_step_emitter:build_skeleton_animation_steps` | stationary + at_dest | 2,881 | 12.1% | 62.8% |
| `transition_bridge:build_walk_up_step` | interrupted + interrupted | 926 | 3.9% | 66.6% |
| `transition_bridge:build_walk_up_step` | at_dest + at_dest | 868 | 3.7% | 70.3% |
| `transition_bridge:_build_handoff_converge_substep` | interrupted + interrupted | 572 | 2.4% | 72.7% |
| `transition_bridge:build_pass_step` | interrupted + interrupted | 503 | 2.1% | 74.8% |
| `skeleton_step_emitter:build_skeleton_animation_steps` | interrupted + at_dest | 472 | 2.0% | 76.8% |
| `transition_bridge:build_walk_up_step` | interrupted + at_dest | 359 | 1.5% | 78.3% |
| `after_steal_fast_break_step_emitter:_build_meet_drive_step` | at_dest + at_dest | 352 | 1.5% | 79.8% |
| `oreb_step_emitter:_build_putback_shoot_step` | no_dest + no_dest | 261 | 1.1% | 80.9% |
| `skeleton_step_emitter:_scramble_leg` | at_dest + at_dest | 250 | 1.1% | 82.0% |

### Same table, O-C/O-PF only, n=1,543

| builder | classes | n | share | cum |
|---|---|---|---|---|
| `skeleton_step_emitter:build_skeleton_animation_steps` | **stationary (C) + at_dest (PF)** | 1,075 | **69.7%** | 69.7% |
| `skeleton_step_emitter:build_skeleton_animation_steps` | at_dest + at_dest | 190 | 12.3% | 82.0% |
| `transition_bridge:build_walk_up_step` | interrupted + interrupted | 69 | 4.5% | 86.5% |
| `skeleton_step_emitter:build_skeleton_animation_steps` | at_dest + stationary | 54 | 3.5% | 90.0% |
| `transition_bridge:_build_kickout_positioning_substep` | at_dest + at_dest | 31 | 2.0% | 92.0% |
| `transition_bridge:build_walk_up_step` | interrupted + at_dest | 27 | 1.7% | 93.7% |
| `dynamic_hct_step_emitter:_build_loop_step` | at_dest + at_dest | 15 | 1.0% | 94.7% |

**The O-C/O-PF stack is one shape: the C is parked at his destination and the PF arrives on top
of him.** 69.7% of creations, all in the skeleton emitter.

---

## Q2 — Where, and is it the same few cells

Yes, overwhelmingly.

| cell | n | share | cum | named spot |
|---|---|---|---|---|
| 86,32 | 2,742 | 9.3% | 9.3% | **upper lowPost** |
| 14,32 | 2,580 | 8.8% | 18.1% | **upper lowPost** (away) |
| 86,19 | 1,392 | 4.7% | 22.9% | lower lowPost |
| 14,19 | 1,267 | 4.3% | 27.2% | lower lowPost (away) |
| 36,25 | 1,094 | 3.7% | 30.9% | key (away) |
| 25,49 | 838 | 2.9% | 33.8% | — unnamed — |
| 29,35 | 696 | 2.4% | 36.1% | upper highPost (offset, away) |
| 64,25 | 659 | 2.2% | 38.4% | key |
| 70,34 | 637 | 2.2% | 40.5% | — unnamed — |
| 80,25 | 590 | 2.0% | 42.5% | midLane |
| 20,25 | 525 | 1.8% | 44.3% | midLane (away) |
| 10,25 | 524 | 1.8% | 46.1% | hct_inbound_pg |
| 90,25 | 445 | 1.5% | 47.6% | hct_inbound_pg (away) |
| 81,43 | 431 | 1.5% | 49.1% | upper midCorner |
| 73,10 | 390 | 1.3% | 50.4% | lower wing |
| 19,43 | 349 | 1.2% | 51.6% | upper midCorner (away) |
| 81,27 | 338 | 1.2% | 52.8% | — unnamed — |
| 73,40 | 319 | 1.1% | 53.9% | upper wing |
| 19,27 | 283 | 1.0% | 54.8% | — unnamed — |
| 27,10 | 279 | 1.0% | 55.8% | lower wing (away) |

**20 cells carry 55.8%** of all coincidence. **51.9% sit on a named playbook spot**; 48.1% do not.

### O-C/O-PF is concentrated far harder than the rest

| cell | n | share | cum | spot |
|---|---|---|---|---|
| 86,32 | 1,331 | 38.0% | 38.0% | **upper lowPost** |
| 14,32 | 1,257 | 35.9% | **73.9%** | **upper lowPost** (away) |
| 36,25 | 207 | 5.9% | 79.8% | key (away) |
| 64,25 | 60 | 1.7% | 81.5% | key |

**73.9% of the entire O-C/O-PF stack is one named spot, `upper lowPost`**, and **93.6%** of it is
on a named spot at all (vs 51.9% overall). Both bigs live in the same post.

---

## Q3 — At rest or in transit, and for how long

| | all | O-C/O-PF |
|---|---|---|
| both static | 33.8% | **55.8%** |
| one moving | 24.1% | 32.9% |
| both moving | 42.1% | 11.3% |

| run length | all runs | O-C/O-PF |
|---|---|---|
| 1 step | 72.8% | 53.7% |
| 2 | 13.8% | 5.8% |
| 3–5 | 11.8% | **36.4%** |
| 6+ | 1.6% | 4.1% |
| mean | 1.53 | **2.27** |
| max | 9 | 8 |

**13.90%** of all steps contain at least one coincidence somewhere on the floor.

This is the part that decides whether it *looks* broken, and it is the worst news for O-C/O-PF:
the two bigs are **stationary** more than half the time and stay stacked for a **mean 2.27
consecutive steps, up to 8**. A stack that persists while both players stand still is exactly
the one a viewer notices.

---

## Q4 — Counterfactuals

Each changes the trajectory, so counts are normalised per 1,000 steps. Baseline 164.13/1k total,
15.76/1k O-C/O-PF. **All of these are throwaway scratch probes; nothing landed.**

| # | counterfactual | steps | total/1k | Δ | O-C/O-PF /1k | Δ |
|---|---|---|---|---|---|---|
| — | baseline | 222,188 | 164.13 | — | 15.76 | — |
| A | PF off `upper lowPost`, MongoDB source | 220,776 | 165.59 | **+0.9%** | 14.32 | **−9.1%** |
| B | `OFFSET_SPOTS` displacement ×2 | 219,383 | 162.82 | **−0.8%** | 16.63 | **+5.6%** |
| C | de-collide every authored co-location, MongoDB source | 220,626 | 157.21 | **−4.2%** | 15.51 | **−1.6%** |
| D | PF off `upper lowPost`, **both** sources | 220,776 | 165.59 | +0.9% | 14.32 | −9.1% |
| E | de-collide every authored co-location, **both** sources | 220,776 | 165.59 | +0.9% | 14.32 | −9.1% |

**All five are disproven as the cause.**

- **A — DISPROVEN.** Removing the PF from the spot that carries 73.9% of the stack removes 9% of
  it. After the change the stack is *still* 73.3% on `upper lowPost`.
- **B — DISPROVEN, and slightly counter-productive.** The existing anti-overlap nudge being "too
  small" is not the explanation.
- **C — DISPROVEN.** Removing **every** authored same-step co-location in the play catalogue
  removes 4.2% of total coincidence.
- **D/E — no effect beyond A.** Byte-identical fingerprint, draws and step count to A (seed 8000:
  fp `9ac2395d333aa5c8`, draws 77,340, 2,876 steps in all three). Patching the hardcoded
  `BackEnd/playcall_skeletons/*` fallback scenes changes **nothing**.

### Static evidence behind A/C/D/E (TRACED)

The harness seeds `play_skeletons_export.json` — 7 plays, 51 authored steps, and **only the
`successful` lean is authored**; `mid_play_change`, `contested` and `broken` are all empty and
fall back to `successful` (`phase_resolution.get_skeleton_by_lean`). In it:

- C is authored to `upper lowPost` in **19 of 51** steps, PF in **8**, SG in 4, SF in 1.
- C and PF are authored to the **same** spot in the same step **once**.

One authored collision cannot produce 2,588 runtime coincidences. The stack is built by
**occupancy plus persistence**, not by an authored collision.

### An unresolved contradiction — reported, not explained away

A second probe wrapping `phase_resolution.get_hco_skeleton` attributes **37.5% of calls and
40.7% of executed skeleton steps to the hardcoded fallback scenes**, and counts 375 executed
`PF → upper lowPost` pos_actions from that path in 4 games. That cannot be squared with D/E
being byte-identical to A.

Both measurements are reproducible; I could not determine which is misleading within this
audit's budget, and I am not going to guess. Candidate explanations I did **not** verify: the
fallback attribution heuristic (`_get_skeleton_from_team_plays` returning falsy) may mis-label
Mongo-sourced skeletons, or the fallback scenes may be copied before the patch point. **This
deserves its own look** — if 40% of executed skeletons really do come from six hardcoded files,
that is a significant fact about the engine regardless of coincidence.

---

## Q5 — The floor, and whether this is even the problem

### The structural floor — this is the finding that reframes everything

Taking each role's **own observed cell distribution** from the real run and asking how often two
roles would land on the same cell if they were placed **independently**:

| | pair-steps | per 1k steps |
|---|---|---|
| independence floor | **22,853** | 102.86 |
| observed | **36,468** | 164.13 |
| **ratio** | **1.60×** | |

| pair | observed | floor | ratio |
|---|---|---|---|
| **O-C / O-PF** | 3,501 | **2,702** | **1.30×** |
| O-PF / O-SF | 2,241 | 1,713 | 1.31× |
| O-SG / O-C | 2,209 | 2,060 | 1.07× |
| O-PG / O-SF | 1,938 | 2,747 | **0.71×** |
| O-SG / O-SF | 644 | 1,369 | **0.47×** |
| O-SG / O-PG | 943 | 2,147 | **0.44×** |

(Marginals are capped at the top 400 cells per role per game, which makes the floor a slight
**under**-estimate — so the true ratios are *lower* than shown.)

**The headline stack is 1.30× its own structural floor.** Two bigs both live in the post; on a
100×50 integer grid with ten players, they land on the same cell 2,702 times **by chance alone**.
The entire "excess" of the O-C/O-PF stack is ~800 pair-steps — **2.2% of total coincidence**.

Several pairs sit *below* the floor (guards at 0.44–0.71×), i.e. the engine already actively
keeps them apart. Nothing is systematically herding players together.

### Exact-cell is the wrong metric for the visible problem

Sprites are ~5.25 grid units wide, so two players 1–2 cells apart still overlap on screen.

| separation | pairs | share of all pairs | vs exact |
|---|---|---|---|
| exact (float-identical) | 28,377 | 0.283% | 1× |
| within 1.0 grid | 50,603 | 0.504% | 1.8× |
| within 2.0 grid | 156,232 | 1.556% | 5.5× |
| **within 5.25 (sprite width)** | **1,040,690** | **10.364%** | **36.7×** |

**Stated plainly: exact coincidence is 2.7% of the visible overlap problem.** 74.2% of steps
contain at least one sub-3.0-grid overlap (25.8% are clean), which matches the original audit's
74.78%. Eliminating *every* exact coincidence in the game would leave ~97% of the visual overlap
untouched, and eliminating the whole O-C/O-PF *excess* would address roughly **0.08%** of it.

**Near-coincidence is the right metric. Exact-cell coincidence was never the problem.**

---

## Q6 — The relocation

With `GOB_SCREEN_TARGETING=1` (the only run here with a flag on), O-PF/O-SF goes
**10.09 → 11.73 per 1k steps, +16.3%**, reproducing Phase 2's +16.1%.

**Where the extra ones appear** (per 1k steps):

| cell | base | targeting | Δ | spot |
|---|---|---|---|---|
| **14,19** | 3.11 | 4.53 | **+1.41** | **lower lowPost** (away) |
| 86,19 | 3.55 | 3.71 | +0.16 | lower lowPost |
| 20,19 | 0.02 | 0.09 | +0.08 | lower midPost (away) |
| 19,7 | 0.21 | 0.28 | +0.07 | lower midCorner (away) |

**86% of the entire increase is one cell** — `lower lowPost` in the away orientation.

**By path**, the increase is concentrated in one class:

| builder | classes | base | targeting | Δ |
|---|---|---|---|---|
| `build_skeleton_animation_steps` | **at_dest + at_dest** | 0.77 | 1.81 | **+1.04** |
| `build_skeleton_animation_steps` | at_dest + stationary | 4.15 | 4.59 | +0.44 |

63% of the rise is **both players arriving at their destinations** on the same cell — not drift,
not interruption.

**TRACED:** the rise is one cell, one builder, one provenance class, and targeting is the only
variable. **INFERRED (not verified):** the mechanism is that Stage A moves a screener onto the
receiver's defender, and in the post that defender stands essentially on `lower lowPost` — the
named spot the other big is already authored to, so retargeting lands the screener on an
occupied offensive spot. Confirming it needs the retarget-target cell distribution cross-tabbed
against defender positions, which I did not run. Phase 2's "no mechanism" is now narrowed to one
cell and one path, but **not closed**.

---

## Two latent oddities found on the way (reported, not fixed)

1. **Players in `end_coords` who are on neither lineup.** 96 of 36,468 coincidences (0.3%)
   involve a role the probe resolves as `?`. Small, but it means the emitter is stamping
   coordinates for a player id that is in neither the offensive nor the defensive lineup.
2. **Steps containing more than ten players.** The per-step overlap histogram has non-zero
   entries at **11, 13 and 17 players** (10 steps total). Ten players is the maximum a step
   should contain. Likely the same root cause as (1), probably mid-substitution.

---

## Bottom line

**No single cause. Mostly structural.**

1. **Not the screen script.** Already falsified in Phase 2 (−0.3%); this audit adds why —
   O-C/O-PF is only 13.3% of screens.
2. **Not authored co-location.** Removing every same-step shared location from the play
   catalogue removes **4.2%** of coincidence. Removing the PF from the spot carrying 73.9% of
   the headline stack removes **9%** of it.
3. **Not a movement or fallback bug.** 77.2% of coinciding players are exactly where the emitter
   told them to go.
4. **It is occupancy plus persistence.** Two bigs both live in the post; the C parks on
   `upper lowPost`, the PF arrives, and they stay there a mean 2.27 steps. That is 69.7% of the
   headline stack in one sentence.
5. **And it is 1.30× what pure chance would give**, on a metric that captures 2.7% of the
   visible overlap.

### What would be worth building

**Nothing aimed at exact coincidence.** The metric is not the problem; the arithmetic above caps
any possible win at a fraction of a percent of what a viewer sees.

If the visible overlap is worth fixing, the only intervention the evidence supports is a
**general near-coincidence separation at render or stamp time, applied to all ten players** —
i.e. Collision Phase 1 (`GOB_COLLISION_SEPARATION`) extended from defender-defender to every
pair, evaluated on the **within-2.0-grid** metric (156,232 pairs) rather than exact cells
(28,377). That is the metric that moves what people actually see.

Two things to settle first, both already flagged above: the **skeleton-source contradiction**
(is 40% of execution really coming from six hardcoded files?), and Phase 1's own open item —
its 49% residual overlap with untuned caps.

## Tunable Constants

None. This audit changed no constant, added no flag, and landed no code. The constants it
*measured against* are `OFFSET_SPOTS` / `HCO_STRING_SPOTS` (`BackEnd/constants/__init__.py`),
left untouched.
