# `COLLISION_OVERLAP_TOLERANCE` — the measured surface

Measurement, not tuning. **No default was changed and no value is recommended** — this exists to
give Jamie the surface for his single tuning pass.

Branch `feature/animation-reward`. New: `GOB_COLLISION_TOLERANCE`, a call-time override that
**resolves to `COLLISION_OVERLAP_TOLERANCE = 0.5` exactly when absent**, so production is inert.
The constant itself is untouched.

**Rule 6e footing**: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2
/ traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process,
`SEED_DEFENSES=1`, `GOB_DEFENDER_AG_SPREAD` unset (ON), all three screen flags OFF,
`GOB_STRICT_EXCEPTIONS=1`. Sweep configuration: `GOB_COLLISION_SEPARATION=1` +
`GOB_COLLISION_SEPARATION_ALL=1`, **`PIN_OFFENCE_AT_AUTHORED_LOCATION = False`**.

## Gates — both passed

| | result |
|---|---|
| all collision flags off, override absent | **240/240** fp AND draws, 480/480 checks, 0 mismatches |
| seed 8000 played SD=1 | fp `0c3389cd41d0bbef`, draws `75363` ✓ |
| flags ON, override **absent** vs flags ON at **0.5** | **80/80 byte-identical** on fp AND draws |
| suite | **3,651 passed** / 20 skipped / 110 xfailed / **0 failed** |

---

# LEAD: the displacement cap binds before tolerance stops mattering — and sprite-width overlap is barely movable by this constant at all

Two things dominate everything below.

**1. `COLLISION_MAX_DISPLACEMENT = 2.0` becomes the limiter, not the tolerance.** The share of
pushes that hit the cap goes **9.4% → 21.5% → 32.4% → 44.1%** across the four points, and from
0.85 upward the **p90 push is exactly 2.0** — i.e. the top decile of every push is the cap, not
the geometry. Above ~0.7 Jamie is tuning a constant whose effect is increasingly clipped by a
different constant.

**2. Full sprite clearance still does not clear the sprites.** within-5.25 moves 10.3645% →
**9.2142%** at tolerance 1.00 — **−11.1%**, against −29% for the much finer within-2.0 band at
0.5. Even targeting the entire combined sprite width, 9 of every 10 sprite-width overlaps
survive, because most of them are pairs the capped relaxation cannot resolve at all (residual
73.01% at 1.00).

---

## The surface — n=40 seeds 8000–8039, both arms, SD=1

| tolerance | threshold (median pair) | (1) within 5.25 | (2) steps w/ any sub-3.0 | (3) within 2.0 | within 1.0 | (4) residual | (5) cap-bound pushes | (6) p50/p90/max | (7) divergence | (8) OOB | shooter violations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *flags off* | — | 10.3645% | 74.21% | 1.5559% | 0.5040% | — | — | — | 0.0221% | 0 | 0 |
| **0.50** | 2.62 | 10.2399% | **73.17%** | 1.0144% | 0.2747% | 58.49% | **9.4%** (66,702/708,237) | 0.6 / 1.4 / 2.0 | 0.0250% | **0** | **0** |
| **0.70** | 3.67 | 10.0685% | **54.27%** | 1.0153% | 0.2958% | 61.12% | **21.5%** (335,658/1,559,504) | 0.6 / 1.8 / 2.0 | 0.0241% | **0** | **0** |
| **0.85** | 4.46 | 9.8704% | **54.20%** | 1.0048% | 0.2913% | 65.22% | **32.4%** (771,189/2,381,045) | 0.9 / **2.0** / 2.0 | 0.0265% | **0** | **0** |
| **1.00** | 5.25 | **9.2142%** | **54.67%** | 1.0448% | 0.3042% | **73.01%** | **44.1%** (1,365,101/3,093,312) | 1.2 / **2.0** / 2.0 | 0.0191% | **0** | **0** |

Pair metrics are shares of all measured pairs, so the ~1% trajectory drift between states is
normalised out.

### (2) has a cliff at 0.70, and it is mechanical

Steps containing any sub-3.0 overlap collapse **74.21% → 54.27%** between 0.5 and 0.7, then go
flat (54.20%, 54.67%). That is not a tuning sweet spot — it is the threshold crossing the metric:

```
median player radius 2.6241 grid, so r_a + r_b = 5.2482
  tol 0.50 -> threshold 2.624   BELOW 3.0
  tol 0.70 -> threshold 3.674   ABOVE 3.0
  tol 0.85 -> threshold 4.461   ABOVE 3.0
  tol 1.00 -> threshold 5.248   ABOVE 3.0
```

At 0.5 the pass separates pairs to 2.62 and *leaves them inside 3.0 by construction*; at 0.7 it
pushes them past 3.0. Everything above 0.7 is already clearing the bar, so the metric cannot
improve further — the residual 54% is the population the capped relaxation never resolves.
**Reading the 0.5→0.7 step as "the fix" would be reading the metric's own definition.**

### (3) within-2.0 is flat across the whole sweep

1.0144% → 1.0153% → 1.0048% → 1.0448%. It saturates at 0.5 because the 2.0 band already sits
below even the lowest threshold, so raising tolerance adds nothing there. What is left is
residual, not tolerance.

### (4) residual rises monotonically: 58.49% → 61.12% → 65.22% → **73.01%**

At 1.00, nearly three quarters of overlapping pairs are accepted rather than separated. Caps
**not tuned**, per the brief.

### (7) divergence has no trend

0.0250% → 0.0241% → 0.0265% → **0.0191%**, against a 0.0221% flags-off baseline. Non-monotonic,
and the highest tolerance gives the *lowest* figure — below baseline. At ~150–180 events in
~670,000 checks this is noise at this sample size, not a signal. **I am not claiming tolerance
improves or worsens divergence.** The Phase-1-extended finding stands separately: the extension
raises divergence relative to flags-off, and this sweep does not explain it.

### (8) Out of bounds: zero at every point, including 1.00

No separated coordinate landed outside the 100 × 50 court at any tolerance, and none was created
by the pass. Worth being precise about **why**, because it is not a safety net: `separate_defenders`
has **no court clamp at all** (unlike `screen_targeting`, which clamps explicitly). What keeps it
inside is `COLLISION_MAX_DISPLACEMENT = 2.0` plus the fact that players rarely start within 2.0
of an edge. **If Jamie raises the displacement cap, this measurement no longer holds** — it was
taken at cap 2.0 only.

### Item 22 — valid at every point

`SHOOTER VIOLATIONS = 0` at all four tolerances (80 games each). The shooter stays exempt at
every step, so no point in this sweep is invalidated.

---

## Outcomes — n=120 seeds 8000–8119, played, SD=1, seed-paired

CI = 1.96 × SEM **of the per-seed difference** vs flags-off. `*` = CI excludes zero.

**The 0.5 figures in `collision-phase1-extended.md` are NOT reused**: those were measured with
the authored-location pin **ON**, and this sweep runs pin **OFF**. Comparing them would conflate
two changes, so 0.5 was re-run pin-off for a like-for-like baseline.

| metric | baseline | 0.50 | 0.70 | 0.85 | 1.00 |
|---|---|---|---|---|---|
| points/team | 73.37 | +0.47 ± 1.76 | +1.12 ± 1.83 | **+1.95 ± 1.94\*** | **+3.24 ± 1.93\*** |
| FG% | 40.58 | +0.59 ± 1.16 | +1.20 ± 1.28 | **+1.90 ± 1.25\*** | **+2.66 ± 1.14\*** |
| 3PA share% | 35.82 | +0.78 ± 1.03 | +0.53 ± 1.30 | +0.49 ± 1.12 | −0.05 ± 1.20 |
| 3PT% | 33.23 | −0.41 ± 1.97 | +0.76 ± 2.01 | +1.38 ± 2.09 | **+2.52 ± 2.21\*** |
| fouls | 31.70 | −0.51 ± 1.25 | −0.34 ± 1.29 | −0.44 ± 1.34 | −0.79 ± 1.28 |
| OREB | 14.76 | **−1.11 ± 0.82\*** | −0.57 ± 0.97 | **−1.50 ± 0.88\*** | **−1.32 ± 0.94\*** |
| DREB | 43.09 | +0.33 ± 1.24 | −0.64 ± 1.26 | **−2.20 ± 1.28\*** | **−2.09 ± 1.26\*** |
| blocks | 10.06 | −0.48 ± 0.69 | −0.29 ± 0.68 | −0.57 ± 0.72 | **−0.83 ± 0.72\*** |
| steals | 16.55 | −0.46 ± 0.94 | +0.38 ± 0.96 | **+1.08 ± 1.05\*** | +0.34 ± 1.00 |
| possessions | 39.70 | +0.29 ± 1.26 | −0.99 ± 1.29 | **−2.18 ± 1.25\*** | **−2.02 ± 1.23\*** |

| tolerance | metrics whose CI excludes zero |
|---|---|
| 0.50 | **1** (OREB) |
| 0.70 | **0** |
| 0.85 | **6** (points, FG%, OREB, DREB, steals, possessions) |
| 1.00 | **7** (points, FG%, 3PT%, OREB, DREB, blocks, possessions) |

The cost is not gradual — it is a step between 0.70 and 0.85. At 0.85 and above the sim changes
materially and coherently: the offence shoots better and scores more (**FG% +1.9 to +2.7**,
points **+2.0 to +3.2**) while rebounds and possessions fall. Nothing was retuned in response.

---

## Bottom line

**At what tolerance does sprite-width overlap actually move? It doesn't — not meaningfully, at
any value this constant can take.** within-5.25 goes 10.36% → 9.21% at full clearance, −11.1%,
and that is the ceiling: tolerance 1.00 already targets the entire combined sprite width, so
there is nothing above it. The remaining overlap is residual the capped relaxation does not
resolve (73.01% at 1.00), not tolerance the constant failed to ask for.

**The one metric that moves a lot — steps with any sub-3.0 overlap, 74.21% → 54.27% — moves
because the threshold crosses 3.0 between 0.5 and 0.7**, and then goes flat. It is the metric's
own boundary, not a property of the game.

**And the cap binds before any of this settles**: 44.1% of pushes are clipped at 1.00, with p90 =
2.0 from 0.85 upward. Past ~0.7, `COLLISION_MAX_DISPLACEMENT` is doing more of the deciding than
`COLLISION_OVERLAP_TOLERANCE` is. **If the visible overlap is the goal, the cap is at least as
much the constant to look at as the tolerance** — and no measurement of raising the cap exists,
including the out-of-bounds check above, which was taken at cap 2.0 only.

What it costs, plainly: residual 58% → 73%, cap-binding 9% → 44%, and the outcome surface going
from 1 significant metric at 0.50 and 0 at 0.70 to 6 at 0.85 and 7 at 1.00. Divergence shows no
trend. Out-of-bounds is zero throughout, at this cap.

**No value recommended. Jamie picks.**

## Tunable Constants

| Constant | Value | Effect |
|---|---|---|
| `COLLISION_OVERLAP_TOLERANCE` | **0.5 (unchanged)** | Fraction of combined sprite width tolerated. Surface measured above. |
| `GOB_COLLISION_TOLERANCE` | *unset* | Measurement override only. Absent/empty/unparseable/non-positive → the constant. Inert in production. |
| `COLLISION_MAX_DISPLACEMENT` | 2.0 | Per-player, per-step push cap. **Binds 9.4%–44.1% of pushes across the sweep; unmeasured above 2.0.** |
| `COLLISION_MAX_PASSES` | 3 | Relaxation passes. Drives the residual that caps every metric here. |
| `PIN_OFFENCE_AT_AUTHORED_LOCATION` | True (shipped) | Set **False** for this whole sweep, per the Phase-1-extended recommendation. |

Nothing was tuned. No default changed.
