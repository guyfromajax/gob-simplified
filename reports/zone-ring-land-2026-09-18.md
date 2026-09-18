# Stage 2 — the zone rings, landed and re-baselined

**Lead answer, three parts.**

**What develop did on its own.** The merge was clean — no conflicts, and **no semantic conflict with `GOB_SIM_CRASH_CLOCK`** (develop's new code *gates* entry choreography on `time_remaining` and only reads the clock; the crash flag *adds* post-shot window time — different phases, no double count). On its own develop moved the arm gap from **+3.61 ±3.88 to +0.79 ±3.08**, with sim 74.96 → 73.86 and played 71.35 → 73.08. Most of the arm gap this workstream has been chasing was closed by develop's Final Turn pacing work, not by anything here.

**What the rings did to the rung shares — and this is the honest headline: not what any of us predicted.** The empty-zone rate did **not** fall in any way the data can resolve (sim 18.38% → 17.97%, −0.41, CI ±0.39/±0.49), and the overlap rung did **not** grow — it *fell* slightly (39.32% → 38.69%, −0.63). Stage 1 predicted double-covered area would roughly double, and it did, but **area is not occupancy**: the region the repair added is mostly floor that offensive players rarely stand on. Exactly **one** per-defender move is resolvable outside the combined CI — the **1-3-1 centre, 32.19% → 29.19% empty (−3.00)** — and that is precisely the defender whose rings were repaired in commit 1 *and* replaced in commit 2. The effect is real, causal and local; it is just small.

**The outcome.** On the production footing both arms moved and neither is byte-comparable to its old reference — expected, stated up front, and not a regression signal. Sim pts/team is flat (73.86 → 73.95), played drifts down (73.08 → 70.79, within CI), arm gap +0.79 → +3.16 ±3.45. The cleanest result in the whole pass is the control: on `SEED_DEFENSES=0` **every seed is byte-identical, 40/40 on both arms**, because with no catalogue the rings are never read.

## Footing (rule 6e)

- **Tree:** `feature/animation-reward`. Merged tree (the new "before") `29e6a6792`; final tree `60ac43b1d`.
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, both `SEED_DEFENSES=1` (production) and `=0` (control).
- **Sim arm:** `_is_full_simulation` **True** throughout the quarter loop. **Played arm:** `_is_full_simulation` **False only inside the four gated Animator methods** at Pattern A.
- **Flags:** `GOB_SIM_HCO_COORD_WRITE`, `GOB_SIM_CRASH_APPLY`, `GOB_SIM_CRASH_CLOCK` all at their shipped defaults (on).
- **Volume:** 480 measured games (3 × 160) plus 36 gate games. **0 errors** in every pass.
- Probe: `zl/probe.py` (session scratchpad, uncommitted) — pure counters plus a re-evaluation of deterministic geometry; touches no RNG.

## Step 0 — the merge

The branch was **9 behind develop**, not 5. Merged with `git merge develop`, **no conflicts**.

**The semantic check the brief asked for, done explicitly.** develop landed `final_turn_pacing.py`, `eoq_clock_progression.py` changes and 154 lines in `turn_manager.py`. The question was whether it now also adds post-shot time, which would double-count against `GOB_SIM_CRASH_CLOCK`.

It does not. `final_turn_pacing.py` only **reads** `time_remaining` — it is a preflight budget (`can_fit_final_shot_dest_and_pass`, the FLSS pending/override path) that decides *whether a Final Shot choreography fits* and routes to FLSS when it does not. `eoq_clock_progression.py`'s changes are to when FLSS is armed and overridden. Neither mutates the clock after a shot. `_maybe_add_sim_post_shot_clock` and its call site in the `anim_steps is None` branch of `_emit_hco_animation_steps` survived the merge intact. **No stop was needed.**

### What develop's changes did on their own

`SEED_DEFENSES=1`, n=40, at `29e6a6792`:

| | sim | played |
|---|---|---|
| pts/team | 74.96 → **73.86 ±2.88** | 71.35 → **73.08 ±2.59** |
| possessions | 43.75 → **43.25 ±2.13** | — → **42.00 ±1.88** |
| draws | 69,190 → **69,564 ±931** | — → **80,639 ±995** |
| Final Turn shots | — | **5.95 ±0.46** (sim) vs **3.23 ±0.13** (played) |
| **arm gap** | **+3.61 ±3.88 → +0.79 ±3.08** | |

On `SEED_DEFENSES=0` the gap sits at **−0.23 ±3.28**. Independence PASS on both arms and both footings; FT-honour windowed 99.9%.

**Worth flagging on its own:** sim takes **5.95** Final Turn shots a game against played's **3.23**, a near-2× asymmetry that develop's pacing work did not close and that nothing in this pass touches.

**One housekeeping note.** Two untracked `READY--` handoff notes in `reports/` had newer local content than develop's tracked copies (both replaced by "Superseded — ignore, see `READY--zone-16-of-55-shapes-broken.md`"). The merge would have refused to overwrite them, so I backed both up to the session scratchpad (`ready_backup/`) and let the merge bring develop's tracked versions in. Nothing was lost, but **the two files in the tree are now develop's older text** — if the local "superseded" pointers mattered, they are in the backup.

## The ring work — four commits

| commit | what |
|---|---|
| `3ace4a84f` | re-cut both references at the merged tree (the new "before") |
| `5c4a2a645` | **commit 1** — the 14 repaired rings |
| `a431a5014` | **commit 2** — Option B for the two 1-3-1 corner-shift centres |
| `b288e4346` | **commit 3** — `basketSpot` into the 2-3 centre |
| `c1958f8f6` | the geometry guard test |
| `60ac43b1d` | re-cut both references at the final tree |

**Every spot was inserted at its position in the boundary walk, never appended** — appending is what created the original self-intersections. Verified after every commit over all 55 definitions:

| after | self-intersecting | degenerate (<3 distinct) | duplicate vertices |
|---|---|---|---|
| merged tree (before) | 14 | 2 | 3 |
| **commit 1** | **0** | 2 | **0** |
| **commit 2** | **0** | **0** | **0** |
| **commit 3** | **0** | **0** | **0** |

**Commit 1** — `set(before) == set(after)` asserted programmatically for **all 14** before anything was written; the assertion is in the apply script and would have aborted the write. Three rings were de-duplicated as part of their own repair, which is the only place the brief allows it: `ZONE_32_LOWER_SHIFT["PF"]` 11→9, `ZONE_32_UPPER_SHIFT["C"]` 11→9, `ZONE_131_NORMAL["C"]` 13→11. One trailing comment on `ZONE_23_UPPER_SHIFT["PG"]` was stripped by the rewrite and restored by hand — it describes the spot set, which did not change.

**Commit 2** — Option B, ordered as a boundary walk rather than in the order the option was written:

| | ring order | area | self-int | of the 4 uncovered spots |
|---|---|---|---|---|
| lower | `lower bird`, `lower corner`, `lower midBaseline`, `basketSpot`, `lower lowPost` | 0.0 → **38.1** | no | **4 of 4 covered** |
| upper | `upper bird`, `upper lowPost`, `basketSpot`, `upper midBaseline`, `upper corner` | 0.0 → **37.2** | no | **4 of 4 covered** |

**Commit 3** — `basketSpot` inserted after `upper lowPost` in the 2-3 centre's walk. **Applied to all three variants** (`ZONE_23_NORMAL`, `ZONE_23_LOWER_SHIFT`, `ZONE_23_UPPER_SHIFT`) — the C list was character-identical in all three and the rim gap was present in all three, so there was no reason to split them. Area **82.8 → 87.9** in each, and `basketSpot` now tests inside. **The 2-3 rim gap is closed.**

**Coverage at the final tree:** nine of the eleven tables now cover **every** real half-court spot. The two that do not are `ZONE_131_LOWER_SHIFT` and `ZONE_131_UPPER_SHIFT`, each still leaving the weak-side `bird` uncovered — pre-existing, present before this pass, and out of scope. Double-covered area landed where Stage 1 said it would: `ZONE_23_LOWER_SHIFT` 40.0 → 88.0, `ZONE_23_UPPER_SHIFT` 35.2 → 80.0, `ZONE_131_NORMAL` 33.5 → 64.0, the two 3-2 corner shifts 69 → 100.5, the two 1-3-1 corner shifts 53.2 → 53.5 and 59.8 → 60.0.

## Rung shares — did the empty rate fall and did overlap grow?

**Stated plainly: no and no, on the evidence.** `SEED_DEFENSES=1`, n=40, merged-tree before → final:

| rung | sim before | sim final | Δ | played before | played final | Δ |
|---|---|---|---|---|---|---|
| **0** overlap | 39.32% ±0.80 | 38.69% ±0.72 | **−0.63** | 39.23% ±0.56 | 38.63% ±0.73 | **−0.60** |
| **a** bh in zone | 15.38% ±0.23 | 15.66% ±0.23 | +0.28 | 15.26% ±0.26 | 15.72% ±0.23 | +0.46 |
| **b** deep | 0.00% | 0.00% | 0.00 | 0.00% | 0.00% | 0.00 |
| **c** one player | 21.66% ±0.64 | 22.27% ±0.64 | +0.61 | 21.69% ±0.60 | 22.08% ±0.64 | +0.39 |
| **d** many players | 5.25% ±0.28 | 5.41% ±0.22 | +0.16 | 5.62% ±0.28 | 5.49% ±0.24 | −0.13 |
| **e** **empty** | 18.38% ±0.46 | **17.97% ±0.49** | **−0.41** | 18.19% ±0.47 | **18.08% ±0.44** | **−0.11** |
| defender-steps/game | 11,204 ±379 | 11,376 | | 11,292 ±456 | 11,322 | |

Every move is inside the confidence interval. The `b_deep` rung remains **exactly zero** across all 480 games — still dead code.

**By shell (sim, before → final):**

| shell | empty | overlap |
|---|---|---|
| 2-3 | 16.17% → 16.34% (+0.17) | 45.38% → 44.00% (−1.38) |
| 3-2 | 12.63% → 13.43% (+0.80) | 33.08% → 31.21% (−1.87) |
| 1-3-1 | 26.06% → **24.30% (−1.76)** | 39.85% → 41.07% (+1.22) |

**By defender (sim), with the resolvability test applied:**

| shell\|pos | before | after commit 1 | final | Δ | resolvable? |
|---|---|---|---|---|---|
| **1-3-1 C** | 32.19% ±1.31 | 31.10% | **29.19% ±1.59** | **−3.00** | **RESOLVED** |
| 1-3-1 PF | 49.11% ±2.01 | 46.35% | 46.20% ±1.57 | −2.91 | within CI |
| 1-3-1 SF | 22.74% ±1.68 | 20.63% | 21.33% ±1.54 | −1.41 | within CI |
| 1-3-1 SG | 19.63% ±1.45 | 18.66% | 18.66% ±1.33 | −0.97 | within CI |
| 1-3-1 PG | 6.63% ±0.96 | 6.67% | 6.10% ±1.03 | −0.54 | within CI |
| 2-3 C | 46.95% ±1.75 | 49.04% | 47.96% ±2.18 | +1.01 | within CI |
| 2-3 SF | 15.45% ±1.15 | 15.51% | 14.86% ±1.16 | −0.58 | within CI |
| 2-3 PF | 8.40% ±0.97 | 9.18% | 8.70% ±1.14 | +0.29 | within CI |
| 2-3 SG | 7.51% ±1.06 | 7.40% | 7.77% ±0.99 | +0.25 | within CI |
| 2-3 PG | 2.53% ±0.67 | 2.34% | 2.44% ±0.70 | −0.09 | within CI |
| 3-2 SF | 21.47% ±1.59 | 23.60% | 23.40% ±1.69 | +1.92 | within CI |
| 3-2 C | 10.31% ±1.24 | 12.35% | 12.12% ±1.24 | +1.82 | within CI |
| 3-2 PF | 6.42% ±0.87 | 7.47% | 7.24% ±0.85 | +0.82 | within CI |
| 3-2 PG | 17.13% ±1.16 | 17.56% | 17.51% ±0.88 | +0.38 | within CI |
| 3-2 SG | 7.83% ±0.75 | 6.92% | 6.90% ±0.83 | −0.93 | within CI |

**The one resolvable move is the 1-3-1 centre**, and it is the right one: his `NORMAL`, `LOWER_SHIFT` and `UPPER_SHIFT` rings were all repaired in commit 1, and both `CORNER_SHIFT` rings were replaced outright in commit 2 (from a zone that could never match anyone to a 38-unit baseline zone). Roughly a third of the drop arrived with commit 1 and two thirds with commits 2–3, which is what you would expect if Option B is doing the work.

**Why the aggregate barely moved — the explanation, not an excuse.** Two reasons, both checkable in the tables above:

1. **The defenders driving the empty rate were never broken.** The two worst offenders are the 2-3 centre (47%) and the 1-3-1 power forward (49%). `ZONE_23_*["C"]` was not among the 14 — it was a sound ring — and `ZONE_131_*["PF"]` was not either. Commit 3 added one spot to the 2-3 centre; nothing in this pass reshaped either zone. They sit empty because they own the lane and the lane is often vacant, which is a **design** property of the shell, not a geometry defect.
2. **Area is not occupancy.** The repair added real floor — `ZONE_23_NORMAL["SF"]` went 55.2 → 92.3 — but mostly along baselines and into notch fills where offensive players seldom stand. Double-covered area more than doubled in four tables while the overlap *rung* fell 0.6 points.

**On `_resolve_overlap_assignments`:** the brief asked me to say so if the overlap rung grew materially. **It did not** — it fell slightly on both arms. So this pass produces **no new argument** for auditing it. The standing argument from the previous report is unchanged and unaffected: it is still the single largest rung at ~38.7% of all zone defender-steps and it has still never been looked at.

**The `random.choice` at `phase_resolution.py:8747`:** **2.23 ±0.40 → 2.50 ±0.53** fires per game on sim (played 2.38 → 2.17). Within CI, and on `SEED_DEFENSES=0` it is 0.00 by construction. Small, but its *phase* is what breaks byte-equality, not its count.

## Outcome table

**`SEED_DEFENSES=1` (production), n=40, merged-tree before → final:**

| metric | sim before | sim final | played before | played final |
|---|---|---|---|---|
| **pts/team** | 73.86 ±2.88 | **73.95 ±2.96** | 73.08 ±2.59 | **70.79 ±3.74** |
| FG% | 45.71 ±1.97 | 45.77 ±1.93 | 45.48 ±2.26 | 43.55 ±2.55 |
| 3P% | 34.10 ±2.32 | 31.13 ±2.81 | 36.15 ±3.42 | 31.52 ±3.42 |
| blocks | 9.45 ±0.89 | 10.05 ±0.87 | 9.68 ±0.99 | 10.93 ±1.11 |
| steals | 16.98 ±1.18 | 17.48 ±1.30 | 17.40 ±1.18 | 16.93 ±1.16 |
| OREB | 16.30 ±1.23 | 18.57 ±1.45 | 16.55 ±1.43 | 16.05 ±1.48 |
| OREB share | 26.00% ±1.76 | 28.60% ±1.76 | 26.43% ±1.87 | 24.87% ±1.81 |
| second-chance pts | 7.08 ±1.24 | 7.60 ±1.19 | 7.00 ±1.16 | 6.00 ±0.84 |
| over-the-back in play | 60.15 ±2.50 | 61.50 ±2.68 | 59.58 ±2.62 | 61.48 ±3.04 |
| over-the-back fouls | 1.70 ±0.41 | 2.27 ±0.56 | 2.12 ±0.43 | 1.75 ±0.41 |
| possessions | 43.25 ±2.13 | 42.52 ±1.94 | 42.00 ±1.88 | 44.40 ±2.11 |
| Final Turn shots | 5.95 ±0.46 | 5.80 ±0.44 | 3.23 ±0.13 | 3.17 ±0.17 |
| `:8747` fires | 2.23 ±0.40 | 2.50 ±0.53 | 2.38 ±0.54 | 2.17 ±0.42 |
| draws | 69,564 ±931 | 70,476 ±992 | 80,639 ±995 | 81,899 ±1,118 |
| errors | 0 | 0 | 0 | 0 |
| **arm gap** | **+0.79 ±3.08** | → | **+3.16 ±3.45** | |

**`SEED_DEFENSES=0` (control): every single metric is unchanged, and every seed is byte-identical — 40/40 on both arms.** With no catalogue, `is_zone_defense` does not resolve, every zone call is substituted with man placement, and the rings are never read. This is the strongest evidence in the pass that the change is data-only and zone-only: if a ring edit had leaked into the man path, this column would have moved.

**Reading the production column honestly.** Every individual movement above has overlapping confidence intervals, so nothing here is resolved at n=40. Two patterns are worth naming rather than burying:

- **3P% fell on both arms** (sim −2.97, played −4.63). Same direction, both arms, which is what a genuine placement effect would look like — more perimeter zones now actually contain the shooter, so more threes are contested. It is **not resolved** (the CIs are ±2.8–3.4) but it is the movement I would watch first on the eye test.
- **The two arms moved in opposite directions on the glass** — sim OREB share up 2.6 points, played down 1.6. I have no mechanism for that and would not read anything into it at this n.

**On second-chance points:** I could not reproduce the definition behind the 18.40 figure in `reports/flags-on-2026-09-17.md`, so this column uses my own — *points scored on the turn during or immediately following an offensive rebound* — measured identically before and after. It is valid as a delta and **is not comparable to that earlier number**. The per-turn score delta it is built on also under-counts total points by roughly 8% (free throws land outside the micro-turn boundary), so treat the absolute value as indicative only.

## Byte-equality: expected to break, and it did

**Played moved. This is not a regression signal and it cannot be validated by exact diff.** Placement is shared code — `position_zone_defenders` runs on both arms — and the `random.choice` at `phase_resolution.py:8747` re-phases the stream whenever the number of defenders credited with the ball handler changes. On `SEED_DEFENSES=1`, **0 of 40** seeds match their merged-tree fingerprint on either arm. That was the predicted outcome and no attempt was made to preserve equality.

The gates that must still pass, did:

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes) | **PASS** — sim and played, both footings, identical fingerprint/draws/points/turns |
| FT-honour, windowed | sim 99.7% (`=1`) / 99.7% (`=0`); played 99.6% / 99.8% |
| FT-honour, strict | 96.1–96.7% |
| errors, 480 games | **0** |
| `SEED_DEFENSES=0` byte-equality | **40/40 both arms** |

## References

| file | status |
|---|---|
| `equiv_v3_reference_c1958f8f6_rings.json` | **the reference from now on, for BOTH arms.** Per-seed rows 8000–8039, both footings, aggregates and gate results. |
| `equiv_v3_reference_29e6a6792_merged.json` | the merged-tree "before" — develop merged, rings untouched. Kept so develop's contribution stays separable from the rings'. |
| `equiv_v3_sim_reference_9910cd6fd.json` | **superseded.** |
| `d9a4f1517` (played) | **superseded.** The played arm no longer reproduces it. |
| `equiv_v3_sim_reference_4f856721a.json` | **now unreachable.** `GOB_SIM_CRASH_APPLY=0 GOB_SIM_CRASH_CLOCK=0` still disables the crash work, but **placement changed underneath the escape hatch**, so the flags-off path no longer reproduces the pre-workstream sim arm. The escape hatch still works as a *flag* switch; it is no longer a *time machine*. |

## The guard

`tests/test_zone_ring_geometry.py` — 55 parametrised cases, one per zone definition, asserting ≥3 distinct vertices, no duplicate consecutive vertices, and no self-intersection. **56 tests pass** against the repaired data.

**Poisoned twice, because a guard nobody has seen fail is not a guard.** The in-file poison test asserts the guard *raises* on each of the three shapes that actually shipped. Separately, run against the whole **pre-repair** table set at `3ace4a84f`, it fails on **exactly 16 of 55** — the same 16 the Stage 1 inventory found, by the same three categories:

```
 14 self-intersecting   e.g. ZONE_23_NORMAL['SF']: edge pairs (1,5) and (1,6) cross
  1 duplicate vertex    ZONE_131_NORMAL['C']: basketSpot repeated at index 12
  2 single-spot         ZONE_131_{LOWER,UPPER}_CORNER_SHIFT['C']: 1 distinct vertex
```

## Not covered

- `assign_zone_defender_coords` and its ladder, including the empty-zone branch, were **not touched**. This pass fixed the cause; the fallback is still a separate decision, and with the empty rate essentially unmoved, that decision is now more load-bearing than it looked at the end of Stage 1.
- `_point_in_zone` / `_point_in_polygon` untouched. The ray-cast is correct.
- The 13 sound-but-dented rings: inventoried in Stage 1, left alone.
- The crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1 (Final Turn), R2 (stopper) and every balance number: untouched.
- The weak-side `bird` gap in the two 1-3-1 **wing** shifts remains. Pre-existing, out of scope, and it needs a spot-set decision like the corner shifts did.
- **Not explained:** why sim takes 5.95 Final Turn shots a game to played's 3.17. Pre-existing and unaffected by this pass, but it is a near-2× arm asymmetry sitting in plain sight.

## Stop

**Nothing further should be built on this until Jamie eye-verifies a zone game.** The numbers clear every gate and the geometry is provably sound for the first time, but the distributional evidence is thin by design — one resolvable rung move and no resolved outcome change. The eye test is the gate here, not the table.
