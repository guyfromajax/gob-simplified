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

---

# MEASURED — a full simulated season

Everything above is a **model**. This section is what a season actually produced, and it is the
first end-to-end check of that model against real output.

**Franchise `6a7f1acc7d319324cd3259ab`** — 128 CPU teams, **1,523 players**, weeks 1–26 on one
unchanged configuration (identity-driven allocation, two modes, 1-skill focus emphasis, 16
rotating coaching focuses). Read from `ftd.training_reports[week].player_changes`.

⚠️ **UNITS: raw attribute points, NOT RT.** These are the per-attribute deltas the training
engine records, summed across weeks. RT is a *derived*, non-linear function of attributes and a
player's position, so an RT change cannot be inferred from these numbers — a player who gains
+13 `ND` and loses −3 across several skills may move RT up, down, or not at all. Every `TOTAL`
row is the **sum of 12 attribute deltas**, not a rating.

## Per attribute — camp vs in-season vs the whole year

| attr | TC (wk 1) | wks 2–26 | % up | TC + season | % up |
|---|--:|--:|--:|--:|--:|
| **ND** | +2.15 | **+13.18** | 100% | **+15.33** | 100% |
| **IQ** | +2.30 | **+11.73** | 100% | **+14.03** | 100% |
| **FT** | +1.80 | +6.86 | 97% | **+8.66** | 99% |
| SC | +1.02 | −2.29 | 29% | −1.27 | 37% |
| RB | +1.10 | −2.42 | 37% | −1.32 | 40% |
| SH | +1.04 | −2.60 | 24% | −1.56 | 30% |
| ST | +1.03 | −2.95 | 29% | −1.92 | 34% |
| OD | +1.01 | −2.98 | 27% | −1.96 | 33% |
| PS | +0.98 | −3.46 | 26% | −2.48 | 32% |
| BH | +1.01 | −3.52 | 27% | −2.51 | 32% |
| AG | +0.94 | −3.57 | 24% | −2.63 | 32% |
| ID | +0.98 | −3.82 | 25% | −2.84 | 30% |
| **TOTAL** | **+15.36** | **+4.17** | 57% | **+19.53** | **79%** |

Camp is clean: **0 of 18,276 attribute-slots ≤ 0** — every player gained on every attribute,
as expected with decay switched off.

### What it confirms

**The fit table is the whole story, and the model called it.** `ND`/`IQ`/`FT` are fit **1.00**
for every position; the nine skills average **0.56**. The minimum-fit table above says a 1-point
allocation needs 0.56–0.79 fit to hold — so the universals clear it comfortably and the skills
sit right at or below the line. Measured: universals **97–100%** of players up, skills
**24–37%**.

**Camp does not cover the season's skill losses.** Camp gives each skill about **+1**; the
season takes **2–4** back. Every skill finishes the year net negative.

**The headline `79% up` is carried by three attributes.** On the nine actual basketball skills,
only 30–40% of players end the year better than they started. The shape of a season is: everyone
gets fitter, smarter and a better free-throw shooter, while roughly two-thirds get slightly worse
at every skill.

**Camp barely differentiates skills** — all nine land between +0.94 and +1.10. Even with decay
off and the scale at 0.70, camp lifts everything roughly equally rather than shaping a player.

## By class year

| year | n | camp (wk 1) | in-season | season total |
|---|--:|--:|--:|--:|
| freshman | 87 | +24.08 | **−32.61** | **−8.54** |
| sophomore | 298 | +16.97 | +27.71 | **+44.68** |
| junior | 514 | +15.34 | +11.36 | +26.70 |
| senior | 624 | +13.39 | −7.86 | +5.52 |

**Freshmen finish the season worse than they started.** They gain the most at camp (+24.08) and
then lose more than all of it. Their decay is `randint(−2, 0)` — double every other class — while
their class-gain multiplier is already 100%, so there is no headroom left to compensate. Of the
four levers (points, fit, class gain, decay), decay is the only one still available to them.

Sophomores are the clear winners at **+44.68**; the curve then falls monotonically through junior
and senior. Note the cohort sizes are uneven (87 freshmen against 624 seniors), so the freshman
figure rests on the smallest sample here.

## Open design questions this raises

1. **Should skills erode league-wide in-season?** It follows directly from 12 floors at 1 point.
   Holding all twelve would need 3 points each = 36 against a 24-point budget, so something must
   give: train fewer attributes, raise `IN_SEASON_GAIN_SCALE`, or accept erosion and let camp
   rebuild.
2. **Is a net-negative freshman year intended?** Measured across 25 weeks, not one — a recruiting
   class that peaks at camp and ends underwater may or may not be the arc you want.

Both sit with the player-development system rather than CPU identity: the levers are the
in-season scale, the decay ranges, and `TRAINING_GAIN_PERCENTAGES`.
