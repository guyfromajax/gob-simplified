# Position Rating Sanity Audit

> 🗄️ **SUPERSEDED (2026-08).** This is a dated staging snapshot from the **two-formula** era, when
> recruit-profile RT and player-profile RT were computed separately. The recalibration unified RT
> onto **one shared `compute_position_ratings` table for recruits and players, and RT no longer
> changes at signing** (see `Position_Ratings_System.md`). Section H's "Confirmed" recruit↔player
> RT **discontinuity** has therefore been ELIMINATED — do not action it as a live finding. The
> 300-recruit-pool and pre-−2-shift height numbers below are also historical. Retained as a record
> of the problem that motivated the unified table.

- Database: `gob-staging`
- Franchise: `6a67882a2b2eb443f8c7789f`
- Rostered players: **1,920** across **128** FTD documents
- Current franchise recruit pool: **300** FRD documents
- RT source: ratings recomputed in memory with the current `compute_position_ratings`; no stored values were changed.
- Argmax tie rule: stable `PG, SG, SF, PF, C` order. This only decides how exact top-rating ties are labeled.
- Percentiles: linear interpolation.
- Recruit delta convention: `player-profile RT - recruit-profile RT`.

## A. Argmax distribution

| Position | Count | % |
|---|---:|---:|
| PG | 454 | 23.65% |
| SG | 520 | 27.08% |
| SF | 295 | 15.36% |
| PF | 441 | 22.97% |
| C | 210 | 10.94% |

## B. Height by argmax position

| Position | N | Mean | Median | P10 | P90 |
|---|---:|---:|---:|---:|---:|
| PG | 454 | 70.31 | 70.00 | 67.00 | 74.00 |
| SG | 520 | 71.16 | 71.00 | 67.00 | 75.00 |
| SF | 295 | 71.08 | 71.00 | 67.00 | 75.00 |
| PF | 441 | 73.02 | 73.00 | 69.00 | 77.00 |
| C | 210 | 79.63 | 79.00 | 77.00 | 82.10 |

PF minus SF mean height: **1.94 in**; median difference: **2.00 in**.

## C. Undersized bigs

| Argmax | Height | Count | % of group | Group N |
|---|---:|---:|---:|---:|
| PF | < 78 in | 439 | 99.55% | 441 |
| PF | < 76 in | 334 | 75.74% | 441 |
| C | < 78 in | 23 | 10.95% | 210 |
| C | < 76 in | 0 | 0.00% | 210 |

## D. Height discrimination

| Measure | Value |
|---|---:|
| Pearson r: height vs PF RT (all players) | 0.5722 |
| Pearson r: height vs C RT (all players) | 0.7596 |
| PF weighted height contribution variance, heights 76–84 | 0.0000 |
| PF weighted height contribution range, heights 76–84 | 7.50–7.50 |
| Empirical height vs PF RT r, player heights 76–84 | 0.1355 |
| Players in empirical 76–84 subset | 396 |

The formula-level variance uses only PF's weighted height component while holding all other attributes constant.

## E. Tweener rate

| Rule | Count | % |
|---|---:|---:|
| rt_margin < 3 | 619 | 32.24% |
| rt_margin < 5 | 909 | 47.34% |

## F. RT distribution per position

| RT | P10 | P25 | P50 | P75 | P90 | Max |
|---|---:|---:|---:|---:|---:|---:|
| PG | 14.0 | 19.0 | 27.0 | 41.2 | 60.0 | 92.0 |
| SG | 14.0 | 20.0 | 28.0 | 50.0 | 68.0 | 90.0 |
| SF | 15.0 | 21.0 | 36.0 | 52.0 | 62.0 | 92.0 |
| PF | 13.0 | 19.0 | 31.0 | 53.0 | 67.0 | 91.0 |
| C | 8.0 | 12.0 | 21.0 | 40.0 | 61.0 | 100.0 |

Players with any RT ≥ 100: **1 (0.05%)**.

## G. RT by class year

| Class | N | Top1 P50 | Top1 P90 |
|---|---:|---:|---:|
| FR | 479 | 24.0 | 73.0 |
| SO | 364 | 50.0 | 76.0 |
| JR | 456 | 54.0 | 79.0 |
| SR | 621 | 54.0 | 80.0 |

## H. Recruit/player formula discontinuity

| Position | Delta P10 | Delta P50 | Delta P90 | Abs delta P50 | Abs delta P90 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| PG | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SG | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SF | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| PF | -3.0 | -1.0 | 1.0 | 1.0 | 3.0 | -8.0 | 4.0 |
| C | -14.1 | -7.0 | -3.0 | 7.0 | 15.0 | -23.0 | 20.0 |

Recruits whose argmax changes between profiles: **47/300 (15.67%)**.

## I. Short-big compensation

| Measure | Count | % |
|---|---:|---:|
| All recruits under 71 in | 135 | 45.00% |
| Under-71 recruits with recruit-profile argmax PF/C | 34 | 25.19% |

## Hypothesis verdicts

### H1 — **Inconclusive (mixed result)**

PF is 441/1,920 (**22.97%**) of argmax labels versus a 20% balance reference. PF-argmax players average **73.02 in** versus **71.08 in** for SF, a **1.94 in** difference. The PF and SF P10–P90 ranges overlap from **69.00 to 75.00 in**. PF is modestly over the balance reference and the ranges overlap, but no threshold was supplied for whether a 1.94-inch mean difference is meaningful, so the compound hypothesis cannot be classified as confirmed or refuted without imposing one.

### H2 — **Confirmed**

`_pf_height_to_rating` returns **75.0** at every integer height from 76 through 84. With PF's 0.10 height weight, every one contributes **7.5 RT points**, with variance **0.0000**.

### H3 — **Confirmed**

PF median absolute profile change is **1.0 RT** (P90 **3.0**); C is **7.0 RT** (P90 **15.0**). **300/300** recruits have a nonzero PF or C change, and **47** change argmax position.

These profile comparisons are counterfactual computations on identical recruit attributes and height; they measure formula discontinuity only, with no development. Code tracing also found that season rollover currently copies the recruit's stored recruit-profile ratings into the new FPD player record; therefore the formula discontinuity is real when the player profile is next recomputed, but the persisted value is not switched at the exact signing write.

## Anything else that looked wrong

- Exact top-RT ties: 154/1,920 (8.02%); their argmax label depends on the documented stable tie rule.
- Stored player-profile RT dictionaries differing from fresh computation: 1,794/1,920.
- Stored recruit-profile RT dictionaries differing from fresh computation: 163/300.
- Players without a resolvable team_id: 0/1,920.
- Every audited player, recruit, and short-big weight vector sums to 1.0.
- No database writes, migrations, or stored RT recomputations were performed.
