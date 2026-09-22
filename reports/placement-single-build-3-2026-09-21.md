# Stage 3 — delete the redundant builds, on top of 2a

**The three numbers the joint flip turns on:**

| | |
|---|---|
| **CPU, 2a+3 vs OFF** | **placement cost −13.3 % ± 4.3 pp — RESOLVED** (0.993 → 0.860 s/game), **32.5 fewer builds/game**. **Total sim wall is NOT resolvable**: +1.08 % ± 11 %. Placement is ~19.5 % of wall, so the saving is worth **≈ 2.6 % of a sim**, and the wall measurement cannot see it because flag-on games are different games. |
| **freeze-miss** | **2.20 per game** (sim SD=1) — **did not rise** from 2a's 2.25. Acceptance test passes. |
| **what n=120 resolved** | **Nothing except draws.** Interceptions +0.225 ± 0.521, pts/team −0.592 ± 2.134, FG% −0.346 ± 1.177, possessions +0.092 ± 1.477. To resolve a +0.40/game interception shift you would need **n ≈ 204**. |

**I must correct my own 2a report.** It claimed 2a cost **+11 % CPU**. Measured properly — three
configs interleaved per seed, run sequentially, n=20 — **2a is CPU-neutral: −0.63 % ± 8.7 pp on wall,
+1.6 % ± 5.4 pp on placement, neither resolved.** The +11 % was n=8 non-interleaved noise and should
not be carried forward.

Both flags default `"0"`. **Not flipped, not re-cut, not merged.** `GOB_BOXOUT_CONTEST` still `"0"`,
nothing retuned, `crash_destination.py` untouched.

---

## 1. The gate

| configuration | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| **both flags OFF** — fp / draws | **40/40** | **40/40** | **40/40** | **40/40** |
| **`SINGLE_BUILD=1`, `FREEZE=0`** — fp / draws | **40/40** | **40/40** | **40/40** | **40/40** |

Both with **freeze-miss 0 and builds-skipped 0**. The dependency is not merely documented — with the
freeze off, Stage 3 skipped **zero** builds across 160 games.

**How the dependency is enforced:** by conjunction, in one place —
`placement_freeze.single_build_enabled()` returns `enabled() and os.environ.get(FLAG_SINGLE_BUILD) == "1"`.
With write-once off every build's result is still consumed, so nothing is discardable and skipping one
would change what a consumer reads. There is no second place to get this wrong.

## 2. Part A — the inventory, before changing anything

### 2.1 A build is whole-skeleton and SEQUENTIAL

`position_standard_defenders` seeds step N from step N−1 (`defender_placement.py:1219`):

```python
_prior = def_movement[-1]["coords"]
_man_prev = off_coords_list[step_idx - 1] if step_idx >= 1 else off_coords
…
"x": int(round(float(_prior["x"]) + (float(def_coords["x"]) - float(_prior["x"])) * _frac)),
```

**A partial build would be wrong**, so a build can only be skipped **whole**. Per the brief I did not
invent one. *(Worth recording for a later stage: a partial build is not impossible in principle — the
frozen row at step N−1 could supply `_prior` — but it would also need the offense track rebuilt, and
it is a design, not a tweak.)*

### 2.2 How often is a whole build discardable

sim arm, freeze on, n=40 games per footing. Line numbers are post-2a (`:7286`→`:7322`,
`:6530`→`:6566`, `:8017`→`:8053`):

| call site | calls/game | **fully covered** | steps already covered |
|---|---|---|---|
| **pre-walk (`:7322`)** | 149.0 | **21.3 %** | 20.5 % |
| coverage (`:6566`) | 75.4 | **0.0 %** | 66.8 % |
| freelance (`:8053`) | 40.7 | **0.0 %** | 76.1 % |
| **all sites, SD=1** | 265.1 | **12.0 %** | — |
| **all sites, SD=0** | 280.3 | **6.1 %** | — |

**Every skippable build is at the pre-walk site.** The coverage and freelance stamps are *never* fully
covered, because by the time they run the skeleton has grown — which is exactly why the coverage pass
is load-bearing and must keep running.

**This is much less than my scope report estimated.** That report assumed collapsing 2.14 stamps to 1
(≈27 % of placement builds, ≈5.4 % of wall). The real figure is **6.3 % of builds**, because most
stamps still have new steps to cover.

### 2.3 The emit's build is NOT fully discarded — out of scope

Under 2a, `apply_frozen_grid_to_animations` overwrites `movement[i]["coords"]` **only**. The same build
also produces the `action` tags (`guard_ball` / `guard_offball` / overrides) and timestamps the render
needs, and `_step_state` stores **coords only**. So the emit's defender build is not discardable, and
per the brief's rule it stays.

### 2.4 Other builds

| build | status under the freeze |
|---|---|
| `step_state.py` `compute_defender_grid` fallback | already short-circuited in 2a |
| `:4928` shot-contest fallback | fires only on a freeze-miss (~2/game) — not worth gating |
| `:5880` `_hco_post_subtle_defender_row` | **needed** (2a Part A) |

### 2.5 Is the skipped work *provably* discarded? — verified, not assumed

Run under 2a (build still happens), comparing what the build **would** have written against what is
already stored, on exactly the calls Stage 3 skips. n=20, sim SD=1:

| on skippable calls | identical | note |
|---|---|---|
| the build's **offense** row vs the stored row | **22,285 / 22,285 = 100.000 %** (max delta 0.00) | the refresh is a byte-for-byte no-op |
| the build's **defense** row vs the stored row | 13,865 / 22,285 = 62.2 % (max delta 26.31) | differs 37.8 % of the time — **and write-once discards all of it** |

So every write the build would have made is either **blocked** (defense) or a **no-op** (offense).
The result is discarded in full. *(The zone `guard` map was not separately compared; skipping leaves
the stored guard in place, which makes it consistent with the frozen defence rather than mixed across
two builds.)*

## 3. What was built

| file | change |
|---|---|
| `placement_freeze.py` | `FLAG_SINGLE_BUILD`, `single_build_enabled()` (the conjunction), `stamp_build_is_discardable()`, `note_stamp_build()` + `builds_total`/`builds_skippable`/`builds_skipped` |
| `phase_resolution.py` `_stamp_contest_defender_grid` | early return before `compute_placement_grids` when the build is discardable and the flag is on |
| `phase_resolution.py:7729` (separate commit) | the `:7683` write is now a **merge**, not a wholesale replace |

**The skip predicate demands BOTH a defender row and an offense row on every step.** Defence alone
would let a post-subtle beat (pre-seeded with `defense`, no `offense`) qualify, and skipping there
would strip the offense row the SIM arm's coord write scans for at `:5030`.

**Realised == ceiling**, so nothing available is being left on the table:

| | stamp calls/game | skippable | **actually skipped** |
|---|---|---|---|
| sim SD=1 | 266.7 | 11.5 % | **11.5 %** |
| sim SD=0 | 279.8 | 5.9 % | **5.9 %** |
| played SD=1 | 259.1 | 12.3 % | **12.3 %** |
| played SD=0 | 277.9 | 5.8 % | **5.8 %** |

### The `:7683` merge

2a flagged it as the one writer that could clobber a row: it assigned `beat["_step_state"]` outright,
discarding `offense` and `guard` with it. It now merges, and under the freeze an existing `defense`
wins. **Behaviour-neutral, as predicted** — all three configurations produced byte-identical
fingerprints and draw counts before and after. It closes a path, it does not change an outcome.

## 4. CPU — the headline (brief item 1)

`GOB_SIM_PROFILE=1`, sim SD=1 (**the production footing** — placement is ~20 % of wall there vs 2 % at
SD=0), seeds 8000–8019, **the three configs interleaved per seed and run sequentially** so machine
drift and contention hit all three equally.

| config | wall / game | placement self | builds / game | ms per build |
|---|---|---|---|---|
| OFF | 5.088 ± 0.431 s | 0.993 ± 0.034 s (19.51 %) | 514.0 ± 9.1 | 1.932 ± 0.061 |
| 2a | 5.055 ± 0.427 s | 1.008 ± 0.038 s (19.95 %) | 509.8 ± 10.1 | 1.980 ± 0.076 |
| **2a+3** | 5.142 ± 0.488 s | **0.860 ± 0.032 s (16.73 %)** | **481.4 ± 9.0** | 1.789 ± 0.073 |

| paired | wall | placement cost | builds |
|---|---|---|---|
| OFF → 2a | −0.63 % (within CI) | +1.6 % ± 5.4 (within CI) | −4.2 ± 10.7 (within CI) |
| 2a → 2a+3 | +1.72 % (within CI) | **−14.7 % ± 5.2 — RESOLVED** | **−28.3 ± 10.2 — RESOLVED** |
| **OFF → 2a+3** | **+1.08 % ± 11 % (within CI)** | **−13.3 % ± 4.3 — RESOLVED** | **−32.5 ± 13.7 — RESOLVED** |

**Read the placement column, not the wall column.** Total wall cannot resolve a 2–3 % effect here
because the configs play *different games* once outcomes diverge — different turn counts, different
work. Placement cost is attributable and it drops **13.3 %**, which at a 19.5 % share is **≈2.6 % of a
sim**. Against the 63-game week and B1-A's ~7 %, this recovers roughly a third of B1-A.

**And it corrects 2a.** 2a is CPU-neutral on both measures. My 2a report's "+11 %" came from n=8
runs that were not interleaved; it was noise and I have said so above rather than leaving it standing.

## 5. Freeze-miss (brief item 2) — must not rise

| cell | 2a (prior pass) | **2a+3** | by consumer | by reason |
|---|---|---|---|---|
| sim SD=1 | 2.25 /game | **2.20 /game** (88) | shot-contest 78, `_hco_step_def_xy` 10 | `stamped_empty` 83, `appended` 5 |
| sim SD=0 | 0.33 | **0.38** (15) | `_hco_step_def_xy` 15 | `appended` 15 |
| played SD=1 | 2.40 | **1.85** (74) | shot-contest 68, `_hco_step_def_xy` 6 | `stamped_empty` 69, `appended` 5 |
| played SD=0 | 0.40 | **0.28** (11) | `_hco_step_def_xy` 11 | `appended` 11 |

**It did not rise.** The one cell that moved up (sim SD=0, 0.33 → 0.38) is 2 occurrences across 40
games. As in 2a, ~89 % of the residual is the shot-contest selection reaching a step whose stamp
produced an **empty** row — a pre-existing gap, surfaced rather than created.

## 6. The draw-level invariant (brief item 3)

Stage 3 **removes** draws, so the 2a invariant does not carry over and I am not restating it.

**What does NOT hold:** any identical-draw prefix. Seed 8000, OFF vs 2a+3 — the break is immediate:

| | |
|---|---|
| first stamp call whose draw cost differs | **index 1** (OFF 152 draws, 2a+3 **0** — the skip) |
| first turn with a cumulative draw delta | turn **1** |
| first turn with a different `result_type` | turn 2 |

**What does hold, and is verified:**

> **Every build that still runs costs exactly what it would have** — the call before the first skip is
> 172 draws in both configs — **and the only draws removed belong to builds whose entire written
> output is discarded**, which §2.5 establishes directly rather than by inference.

Whole-game draws fall **−4,676 ± 1,157 /game (−5.6 %, RESOLVED)** at sim SD=1.

## 7. Part C — the same-moment gate, replacing my mis-specified one

The old gate compared the **shoot step's** coords to the **last stamped step's** row: two different
moments, so it could never read 0 however perfect the freeze. I specified it and carried it forward;
it is retired.

**The correct gate:** for one step object, the row a consumer reads (`step["_step_state"]["defense"]`)
against the coords the **emit renders for that same step**. Same step, same moment.

| config | pairs | **identical** | mean | max |
|---|---|---|---|---|
| OFF | 277,050 | 69.282 % | 0.7203 | 29.61 |
| **2a** | 276,445 | **100.000 %** | **0.0000** | **0.00** |
| **2a+3** | 280,045 | **100.000 %** | **0.0000** | **0.00** |

**It reads 0 by construction, and it does.** Contest and render are the same value because there is
one value, not because two draws were made to agree.

## 8. Outcomes (brief item 4)

### n=40, both arms, both footings, paired per-seed

Everything is within CI except: `draws/game` in three cells and `turns/game` (−10.70 ± 8.95),
`FGA/game` (+2.80 ± 1.74) and `fouls` (−2.88 ± 2.00) at **played SD=1**.

`draws` is mechanical (§6), not an outcome. The three played-SD=1 crossings are **marginal, and there
are ~40 metric×cell comparisons here** — a handful of boundary crossings is what chance produces. I am
not treating them as findings, and I did not run n=120 on the played arm, so they stay unresolved.
Sim SD=1 at n=40: interceptions +0.55 ± 0.88, pts/team −1.39 ± 3.96, FG% −0.61 ± 1.94 — all within CI.

### n=120, sim arm, SD=1, seed-paired (seeds 8000–8119)

| metric | OFF | 2a+3 | paired Δ | |
|---|---|---|---|---|
| **interceptions** | 3.52 ± 0.36 | 3.75 ± 0.36 | **+0.225 ± 0.521** | within CI |
| pts/team | 74.31 ± 1.91 | 73.72 ± 1.72 | −0.592 ± 2.134 | within CI |
| FG% | 40.50 ± 1.16 | 40.15 ± 1.07 | −0.346 ± 1.177 | within CI |
| possessions | 40.44 ± 1.15 | 40.53 ± 1.21 | +0.092 ± 1.477 | within CI |
| draws/game | 82,538 ± 544 | 77,980 ± 427 | −4,558 ± 661 | **RESOLVED** |

**n=120 resolves nothing but draws — say it plainly.** The interception paired SD is **2.915**, so the
n=120 half-width is ±0.521 and any true shift below that is invisible. **Resolving a +0.40/game shift
at 95 % needs n ≈ 204 seeds.** That is the number to budget if the interception question must be
settled rather than bounded.

What n=40 and n=120 together *do* establish: nothing large or unexpected happens.

## 9. Gates

| | OFF | 2a+3 |
|---|---|---|
| **§8.1 coord-continuity corrections** | **0** (179.6 guard calls/game) | **0** (182.2) |
| errors | 0 | 0 |
| **suite** | **2850 passed, 20 skipped, 112 xfailed, 0 failed, 0 XPASS** | **identical** |

## 10. Footing

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`.
Gate + outcomes: n=40 seeds 8000–8039, **both arms × both `SEED_DEFENSES`**, three configs = 480 games.
n=120: seeds 8000–8119, sim SD=1, two configs = 240 games. CPU: n=20 interleaved × 3 = 60 games.
Part C: n=40 × 3 = 120 games. **0 errors throughout.**

**Catalogue state per table**: SD=1 seeds the six real defenses; **SD=0 leaves it empty and every zone
call plays man**, which is why the skip rate halves (12 % → 6 %) and the freeze-miss rate falls 7× at
SD=0. **SD=1 is the footing that decides.**

## 11. What I did not do

- **Did not flip either flag, re-cut, or merge.**
- **Did not touch seam B** (the drive reconstruction) — out of scope by the brief; it still needs its
  own design.
- **Did not build a partial build** (§2.1), per the brief, though I have recorded why one is possible.
- **Did not run n=120 on the played arm**, so played SD=1's three marginal n=40 crossings stay open.
- **Did not gate the `:4928` fallback build** — ~2 calls/game.
- **Did not separately verify the zone `guard` map** on skipped calls (§2.5).

## 12. Tunable constants

**Nothing was retuned.**

| flag | where | default | effect |
|---|---|---|---|
| `GOB_PLACEMENT_FREEZE` | `placement_freeze.py:33` | **`"0"`** | Stage 2a |
| `GOB_PLACEMENT_SINGLE_BUILD` | `placement_freeze.py:34` | **`"0"`** | Stage 3; **inert unless the freeze is on** |
| `GOB_BOXOUT_CONTEST` | `utils/boxout_contest.py` | `"0"` | untouched |
| `GOB_SIM_PROFILE` | `sim_profiler.py:32` | unset | `=1` reproduces §4 |
