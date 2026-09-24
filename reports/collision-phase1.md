# Collision Phase 1 — defender-defender partial-overlap separation

**`GOB_COLLISION_SEPARATION`, default OFF.** Flag-off is byte-identical: **240/240** on both
references, fingerprint AND draws, with seed 8000 played SD=1 at
**fp `0c3389cd41d0bbef`, draws `75363`**.

Flag on, the headline numbers against the audit's flat-3.0 baselines:

| | flat-3.0 baseline | Phase 1 |
|---|---|---|
| defender placements moved | 25.32% | **12.76%** |
| separated pairs that were deliberate coverage | 28.6% | **9.18%** — and **0** were pushed off it |
| screen-vs-game divergence | 0.0221% | **0.0207%** (did not rise) |
| offensive coordinates moved | — | **0** |

**Nothing cleared in outcomes at n=120.** The one number that is not flattering: **49.14% of
overlapping pairs are still inside threshold after the capped relaxation** — that is the
designed trade, reported in full below rather than tuned away.

---

## Footing (Rule 6e)

| | |
|---|---|
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process |
| **Defenses catalogue** | **`SEED_DEFENSES=1` — production footing, seeded.** The main reference also covers `SEED_DEFENSES=0`. |
| Spread flag | `GOB_DEFENDER_AG_SPREAD` unset = ON, the shipped default |
| Flag-on runs | `GOB_STRICT_EXCEPTIONS=1` |
| Flag-off gate | n=40 seeds 8000–8039, both arms, SD=1 **and** SD=0 (160) + loose SD=1 (80) = **240** |
| Flag-on measurement | n=40 seeds 8000–8039, both arms, SD=1 (80 games, 1,104,380 defender placements) |
| Outcomes | n=120 seeds 8000–8119, played, SD=1, seed-paired, CI = 1.96 × SEM |

---

## 1. Files changed

| file | change |
|---|---|
| `BackEnd/utils/collision_separation.py` | **new** — the whole pass |
| `BackEnd/engine/defender_placement.py` | **+27 / −1** — one hook in `build_all_animations` before the return |
| `tests/test_collision_separation_flags.py` | **new** — 15 guards |

That is the entire engine footprint: one new module and one call site.

---

## 2. The threshold

Derived from height, mirroring `createHeadshotMarkerV2.js`:

```
headRadiusForHeight(h) = clamp(25.5, 39, 30 + (h - 72) * 0.75)   px
radius_grid            = headRadiusForHeight(h) / 12.29           (1229 canvas px / 100 grid)
threshold(a, b)        = COLLISION_OVERLAP_TOLERANCE * (r_a + r_b)
```

`COLLISION_OVERLAP_TOLERANCE = 0.5` is a **named constant**, not inlined and **not tuned**.

| player | radius (grid) | width (grid) | pair threshold |
|---|---|---|---|
| 5'6" (66") — short clamp | 2.075 | **4.150** | 2.075 |
| **75" — league median** | 2.624 | **5.248** | **2.624** |
| 6'4" (76") | 2.685 | 5.370 | 2.685 |
| 7'0" (84") — tall clamp | 3.173 | **6.347** | 3.173 |
| height unknown | 2.319 | 4.638 | 2.319 |

The widths reproduce the brief's 4.15 / 5.25 / 6.35 exactly — but as **output**, not input. A
test asserts the clamp behaviour so the four numbers cannot be hardcoded back in.

---

## 3. Where it runs, and how I confirmed it is before the freeze stamp

**One hook**, in `defender_placement.build_all_animations`, immediately before its return.

All four placement paths — FCP, HCT, zone (`position_zone_defenders`), and man
(`position_standard_defenders`) — build their defenders with the **defender as the outer loop
and the step as the inner one**. I verified this by walking each function's loop nesting: there
is no point inside any of them where "every defender at step *i*" exists. It exists exactly once,
here, after the per-defender movement lists are assembled. That is why one hook covers both the
paths the brief named **and** the two it did not.

### Confirmed, not asserted

`_stamp_contest_defender_grid` → `Animator.compute_placement_grids` → `_build_all_animations`
(**the hook**) → `defender_grid_from_animations` → the stamp writes. So separation completes
*inside* the stamp's own build, before the grid is read from it.

Proved by instrumenting the grid read and comparing every cell against the post-separation
animation coords it was built from:

```
grid cells built from the separated animations : 10245
cells where the grid DISAGREES with them       :     0
stamped defender cells                         :  9990
```

**Zero disagreement.** The frozen row carries the post-separation coordinate; nothing writes to
a frozen row afterwards. Measurement (e) is the independent cross-check — a pass writing after
the stamp would show up there as a divergence spike, and it did not.

> **A false alarm worth recording.** My first ordering probe logged `freeze_stamp` at function
> *entry* and reported "1 read before any separation". That was an artefact of where I logged:
> separation happens *inside* the stamp call, so entry necessarily precedes it. The direct
> cell-by-cell comparison above is what actually settles it.

---

## 4. The exempt set

A defender is **PINNED** — never moved — when he is within `pinned_coverage_distance()` of the
man he is assigned to. That resolves at call time to
`max(POSTURE_DENY_DISTANCE 2.0, ONBALL_POSTURE_DIST["tight"] 2.5) = 2.5`, read from
`shared_defense` so a retune moves with it.

- **Both pinned** → the pair is skipped entirely; the overlap is accepted.
- **One pinned** → the partner absorbs the **whole** separation. (The pair midpoint is
  deliberately *not* preserved here — that is the point of the exemption.)
- **Neither pinned** → each moves `(threshold − d) / 2`, midpoint preserved.

Assignment comes from `get_matchups_for_defending_team`, defaulting to position-on-position.

---

## 5. Determinism

| guarantee | how |
|---|---|
| iteration order | `sorted(coords)` — never dict or set order. A test shuffles the input 25 ways and asserts an identical result. |
| pass cap | `COLLISION_MAX_PASSES = 3`, then residual is **accepted**, not iterated away |
| displacement cap | `COLLISION_MAX_DISPLACEMENT = 2.0` grid units per defender per step, summed across passes — under half a sprite width |
| **zero RNG** | no draw anywhere. Exact coincidence breaks on player id (lower id to −x), not a coin flip. A test asserts both `random` and `sim_rng` states are unchanged. |

---

## 6. Flag OFF — the gate

```
equiv_v3_reference_f600628a4_agspread.json
  SD=1 sim 40/40 · SD=1 played 40/40 · SD=0 sim 40/40 · SD=0 played 40/40   TOTAL 160/160
equiv_v3_loose_baseline_f600628a4_agspread.json
  LOOSE SD=1 sim 40/40 · LOOSE SD=1 played 40/40                             TOTAL  80/80
```

**240/240**, fingerprint AND draws. Seed 8000 played SD=1 = **fp `0c3389cd41d0bbef`,
draws `75363`** — the post-flip reference, not the superseded one.

Sanity check in the other direction: all 40 flag-ON cells **differ** from the reference. Byte-
identity with the flag on would have meant the pass never fired.

---

## 7. Flag ON — measurements

n=80 games (40 seeds × both arms), SD=1, `GOB_COLLISION_SEPARATION=1`, `GOB_STRICT_EXCEPTIONS=1`.

### (a) Placements moved, and how far

| | |
|---|---|
| defender placements | 1,104,380 |
| **moved** | **140,923 = 12.76%** *(flat-3.0 baseline 25.32%)* |
| push mean | 0.629 grid |
| push median | 0.542 |
| push p90 | 1.312 |
| push max | 2.000 — the cap, exactly |

**Half the footprint of the naive rule**, and the typical push is about half a cell.

### (b) Deliberate coverage work — the exemption working

| | |
|---|---|
| overlapping pairs | 78,901 |
| separated | 78,152 |
| **involving a pinned defender** | **7,244 = 9.18%** *(baseline 28.6%)* |
| — both pinned, skipped entirely | 749 |
| — one pinned, partner absorbed the push | 6,495 |
| pinned defenders seen | 55,192 |
| **defenders pushed OFF deliberate coverage** | **0** |

The baseline number fell from 28.6% to 9.18%, and the stronger statement is the last row: a
pinned defender is never moved, so deny and tight work is not disturbed at all. The residual
9.18% is pairs that *touch* a pinned defender, where only the unpinned partner moves.

### (c) Residual overlap — the honest number

| | |
|---|---|
| pairs still inside threshold after 3 passes | **38,769 = 49.14% of overlapping pairs** |

**About half of overlapping pairs are not fully resolved.** This is the designed trade — bounded
passes and a 2.0 displacement cap in exchange for determinism and no oscillation — and three
things drive it: a pinned partner must be cleared by one defender alone, both-pinned pairs are
skipped by design, and a multi-defender pileup cannot be undone inside the cap. Those pairs are
*reduced*, not resolved. If Jamie wants that number lower, the levers are
`COLLISION_MAX_PASSES` and `COLLISION_MAX_DISPLACEMENT` — **neither touched here**.

### (d) Openness-floor crossings

The consumers that actually read separation. Measured as the distance from a moved defender to
the **nearest** offensive player, before vs after:

| floor | crossed INTO (< floor) | crossed OUT (≥ floor) | net |
|---|---|---|---|
| `BACKDOOR_OPENNESS_MIN` 3.0 | 7,990 | 4,755 | **+3,235 closed** |
| `STEP_IN_OPENNESS_MIN` 5.0 | 1,974 | 3,459 | **+1,485 opened** |

Real but small against 1.1M placements (~1.2% and ~0.5%). The two floors move in **opposite**
directions, which is what you would expect from a pass that is not systematically pushing
defenders toward or away from the ball — it pushes them off each other. *(The 11-unit contest
gate is not an exposed consumer of separation and is not reported as one.)*

### (e) Screen-vs-game divergence — same metric and code as Stage 2 (`bcensus.py`)

| | checked | over tolerance | share | worst |
|---|---|---|---|---|
| flag OFF | 666,385 | 147 | **0.0221%** | 16.84 grid |
| flag ON | 666,364 | 138 | **0.0207%** | 16.76 grid |

**It did not rise.** The flag-off figure reproduces the established baseline exactly, which also
validates the harness. This is the independent confirmation that the pass writes *before* the
freeze stamp — writing after it would have shown here.

### (f) Offensive coordinates moved — **0**

Proved by measurement, not by inspection. The probe snapshots **every** player's coordinates
before and after each call, including offence, and counts any that changed:

```
OFFENSIVE COORDINATES MOVED: 0        (across all 80 games)
```

Structurally, the applier only ever writes entries whose `playerId` is on the defending lineup;
offensive entries are read (to locate each defender's man) and never written. A test asserts the
same thing on a fixture where an offensive pair is overlapping and must stay that way.

---

## 8. Outcomes — n=120, played, SD=1, seed-paired

| metric | OFF | ON | delta | 95% CI | CI excludes 0 |
|---|---|---|---|---|---|
| points per team | 73.367 | 73.279 | −0.087 | 1.710 | no |
| FG% | 40.584 | 40.476 | −0.109 | 1.099 | no |
| fouls | 31.700 | 30.975 | −0.725 | 1.109 | no |
| offensive rebounds | 14.758 | 14.333 | −0.425 | 0.914 | no |
| defensive rebounds | 43.092 | 42.658 | −0.433 | 1.219 | no |
| total rebounds | 57.850 | 56.992 | −0.858 | 1.339 | no |
| blocks | 10.058 | 9.833 | −0.225 | 0.668 | no |
| steals | 16.550 | 16.358 | −0.192 | 0.973 | no |
| possessions | 39.700 | 39.217 | −0.483 | 1.265 | no |

**Nothing clears.** Full suite: **3,587 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** — the 3,572 baseline plus the 15 new guards, with no existing test edited.

Every delta is negative but small and well inside its CI — consistent with a
pass that nudges defenders apart without changing what the defence achieves. Nothing retuned.

---

## 9. Anything that did not behave as expected

1. **The residual is high — 49.14%.** I expected the capped relaxation to leave a tail, not half.
   The cap is doing more work than anticipated because a pinned partner forces one defender to
   cover the entire gap alone. Reported, not tuned.
2. **The two openness floors move in opposite directions** (backdoor net closes, step-in net
   opens). I had assumed any systematic effect would push the same way on both.
3. **My first ordering probe raised a false alarm** (§3) by logging the stamp at entry. The
   direct grid-vs-animation comparison is the real proof.
4. **A `ls`-based progress counter appeared to go backwards twice** during the runs (178 → 171).
   Both times it was a read racing a write; no cell was lost, none was zero-byte, and the final
   counts were complete.
5. **One thing the brief predicted that did not appear:** no path needed a second hook. The
   defender-outer/step-inner loop shape is uniform across all four placement functions, so the
   "51% placed outside `_apply_defender_posture`" split in the audit does not fragment the hook —
   it is all reachable from the same assembled animations.
6. **Not fixed, by design:** this does not touch the O-C/O-PF screen stack (3,367 coincidences).
   Separating offence would only mask the screen script sending the screener to the receiver's own
   named `location` on 90.5% of screens. That is Phase 2.
