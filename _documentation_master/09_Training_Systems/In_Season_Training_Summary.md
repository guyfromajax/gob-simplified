# In-Season Training — Impact of Drill Points on Player Attributes

*Net RT change per attribute, per week, in-season (weeks 2–26). Current constants (2026-08-14): `IN_SEASON_GAIN_SCALE` 0.28; class-gain FR 100 / SO 91 / JR 95 / SR 100; year decay FR −2..0, SO/JR/SR −1..0. Fit = the `TRAINING_GAIN_PERCENTAGES` value (0.25–1.0).*

**The model is two gates:** *points* decide how hard you fight decay; *position fit* decides whether you can win. Points alone can't save a badly-fit attribute. **0 points always declines** (year decay + raw −2..−1 neglect drag), floor-clamped at the bottom.

## Net RT / attr / week, by fit × points

### Freshman — decay −1.0/wk, class 100%

| fit | 1 pt | 2 pt | 3 pt | 4 pt | 5 pt |
|---|--:|--:|--:|--:|--:|
| 1.0 | +0.26 | +0.40 | +0.54 | +0.82 | +0.96 |
| 0.7 | −0.12 | −0.02 | +0.08 | +0.27 | +0.37 |
| 0.5 | −0.37 | −0.30 | −0.23 | −0.09 | −0.02 |
| 0.4 | −0.50 | −0.44 | −0.38 | −0.27 | −0.22 |
| 0.25 | −0.68 | −0.65 | −0.61 | −0.54 | −0.51 |

### Sophomore — decay −0.5/wk, class 91%

| fit | 1 pt | 2 pt | 3 pt | 4 pt | 5 pt |
|---|--:|--:|--:|--:|--:|
| 1.0 | +0.39 | +0.52 | +0.65 | +0.90 | +1.03 |
| 0.7 | +0.12 | +0.21 | +0.30 | +0.48 | +0.57 |
| 0.5 | −0.05 | +0.01 | +0.07 | +0.20 | +0.26 |
| 0.4 | −0.14 | −0.09 | −0.04 | +0.06 | +0.11 |
| 0.25 | −0.28 | −0.25 | −0.21 | −0.15 | −0.12 |

### Junior — decay −0.5/wk, class 95%

| fit | 1 pt | 2 pt | 3 pt | 4 pt | 5 pt |
|---|--:|--:|--:|--:|--:|
| 1.0 | +0.30 | +0.43 | +0.56 | +0.83 | +0.96 |
| 0.7 | +0.06 | +0.15 | +0.24 | +0.43 | +0.52 |
| 0.5 | −0.10 | −0.03 | +0.03 | +0.17 | +0.23 |
| 0.4 | −0.18 | −0.13 | −0.07 | +0.03 | +0.09 |
| 0.25 | −0.30 | −0.27 | −0.23 | −0.17 | −0.13 |

### Senior — decay −0.5/wk, class 100%

| fit | 1 pt | 2 pt | 3 pt | 4 pt | 5 pt |
|---|--:|--:|--:|--:|--:|
| 1.0 | +0.20 | +0.34 | +0.48 | +0.76 | +0.90 |
| 0.7 | −0.01 | +0.09 | +0.19 | +0.38 | +0.48 |
| 0.5 | −0.15 | −0.08 | −0.01 | +0.13 | +0.20 |
| 0.4 | −0.22 | −0.16 | −0.11 | 0.00 | +0.06 |
| 0.25 | −0.32 | −0.29 | −0.26 | −0.18 | −0.15 |

## Minimum fit to prevent decay (net ≥ 0)

| Points | FR | SO | JR | SR |
|---|--:|--:|--:|--:|
| 1 pt | 0.79 | 0.56 | 0.63 | 0.71 |
| 2 pt | 0.71 | 0.49 | 0.54 | 0.60 |
| 3 pt | 0.65 | 0.44 | 0.47 | 0.51 |
| 4 pt | 0.55 | 0.36 | 0.38 | 0.40 |
| 5 pt | 0.51 | 0.33 | 0.34 | 0.36 |

*Read: at/above the listed fit → holds or grows; below it → still declines.*

## Three rules that fall out

1. **0 points always declines** — regardless of fit (floor-clamped at the bottom).
2. **On-position is forgiving; freshmen are harsh** — a well-fit attr holds at 1 pt, but a freshman needs ~0.8 fit even at 1 pt (double decay).
3. **Below ~0.5 fit, points barely help** — a badly-off-position attr (0.25) declines at *every* point level, even 5; the best you buy is slowing the bleed.

*Method: net = E[raw roll incl. year-max bump] × 0.28 × fit × class − decay EV. Modeled averages; matches measured week-2/3 output.*
