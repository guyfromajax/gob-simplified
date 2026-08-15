# Team & Player Attribute Tuning — measured season

**Latest run: 2026-08-15, PRODUCTION (`gob`).** Full 26-week regular season plus postseason,
played through the UI — not simmed.

**Franchise** `6a8073d78294292a794bec4c` · user team **HA Rushmore** (26-0 regular season, 33-0
including postseason) · 128 teams · 1,524 players · AutoTrain run every week.

⚠️ **This is the first PROD dataset here.** Earlier entries in this file were staging sims. Read
via the read-only guard (`GOB_DB_ACCESS=read`, `PRODUCTION 'gob' opened READ-ONLY`).

---

## Team attributes — core 8

Range `(-20, 20)`, buckets of 8. 128 teams × 8 attributes = 1,024 slots.

| attribute | −20~−12 | −12~−4 | −4~4 | 4~12 | 12~20 | mean | @−20 | @+20 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `offensive_efficiency` | 19 | 2 | 4 | 8 | **95** | +11.4 | 16 | **45** |
| `defensive_efficiency` | 20 | 17 | 5 | 5 | **81** | +8.7 | 8 | **55** |
| `fb_efficiency` | **59** | 26 | 11 | 5 | 27 | −5.9 | 26 | 13 |
| `fb_opp_modifier` | 0 | 3 | 17 | 39 | **69** | +11.7 | **0** | 19 |
| `pt_efficiency` | **43** | 11 | 21 | 15 | 38 | −0.8 | 29 | 17 |
| `pt_opp_modifier` | 0 | 4 | 18 | 42 | **64** | +11.2 | **0** | 15 |
| `discipline` | 23 | 5 | 7 | 11 | **82** | +9.2 | 11 | **55** |
| `fight` | 33 | 19 | 15 | 20 | 41 | +0.9 | 11 | 14 |
| **TOTAL** | | | | | | | **101** | **233** |

**334 of 1,024 slots railed (33%) — 233 at the CEILING against 101 at the floor.** The league
drifts upward. The reactive pair (`fb_opp_modifier`, `pt_opp_modifier`) remain the healthiest:
**zero teams at the floor**, 15–19 rails each.

## `shot_threshold` — no rails, but the strongest non-talent predictor of winning

Range `-10–190` (MID 90), mean **59.5**, median 56.0, **actual spread 10 → 124**.

| tier | teams | share | |
|---|--:|--:|---|
| −10 – 30 | 8 | 6% | `███` |
| **30 – 70** | **90** | **70%** | `███████████████████████████████████` |
| 70 – 110 | 25 | 20% | `██████████` |
| 110 – 150 | 5 | 4% | `██` |
| 150 – 190 | 0 | 0% | |

Floor 0 · ceiling 0. ✅ The scrimmages baseline is holding — no rails in either direction.

⚠️ **`corr(shot_threshold, wins) = −0.495`** — second only to talent. And the league uses just
**57% of the 200-point range** (10–124), so *narrowing the scale would not help*: it would
compress the same 114-point competitive gap into fewer points and make each point hurt more.
**The issue is that EOG rewards the already-good, not that the range is wide.**

## `rebound_modifier` — U-shaped, hollow middle

Mean **0.52**, median 0.55. Floor 28 · ceiling 35.

| tier | teams | share | |
|---|--:|--:|---|
| 0.0 – 0.2 | **51** | 40% | `████████████████████` |
| 0.2 – 0.4 | 5 | 4% | `██` |
| 0.4 – 0.6 | 11 | 9% | `████` |
| 0.6 – 0.8 | 7 | 5% | `███` |
| 0.8 – 1.0 | **54** | 42% | `█████████████████████` |

**82% in the two extreme tiers, 18% across the middle three.** Being *average* at rebounding is
nearly impossible. Training drift is fixed; EOG step size is not — ±0.10 in one game against
+0.0125 per week of training.

## `team_chemistry` — one-way ramp

Mean **19.7**, median 22.5. Floor 3 · ceiling **37**.

| tier | teams | share | |
|---|--:|--:|---|
| 7 – 10 | 10 | 8% | `████` |
| 10 – 13 | 14 | 11% | `█████` |
| 13 – 16 | 11 | 9% | `████` |
| 16 – 19 | 9 | 7% | `████` |
| 19 – 22 | 15 | 12% | `██████` |
| **22 – 25** | **69** | **54%** | `███████████████████████████` |

---

## Player attributes — by attribute

Raw attribute points, **not RT**. Every `TOTAL` row is the sum of 12 attribute deltas.

| attr | TC (wk 1) | wks 2–26 | % up | TC + season | % up |
|---|--:|--:|--:|--:|--:|
| **ND** | +1.68 | **+6.21** | 94% | **+7.89** | 97% |
| **IQ** | +1.81 | +4.51 | 88% | **+6.32** | 95% |
| **FT** | +1.73 | +4.41 | 89% | **+6.14** | 95% |
| SC | +1.07 | −1.54 | 34% | −0.47 | 42% |
| RB | +1.19 | −1.53 | 40% | −0.34 | 43% |
| SH | +1.09 | −2.01 | 28% | −0.93 | 33% |
| ST | +1.06 | −2.33 | 32% | −1.28 | 36% |
| OD | +1.07 | −2.42 | 30% | −1.35 | 39% |
| ID | +1.07 | −3.10 | 28% | −2.03 | 34% |
| PS | +0.97 | −3.14 | 28% | −2.17 | 33% |
| BH | +0.97 | −3.29 | 29% | −2.31 | 32% |
| AG | +1.00 | −3.33 | 27% | −2.33 | 34% |
| **TOTAL** | **+14.71** | **−7.57** | 35% | **+7.15** | **60%** |

## Player attributes — by class year

| year | n | camp (wk 1) | in-season | **total** |
|---|--:|--:|--:|--:|
| freshman | 81 | +24.21 | **−43.79** | **−19.57** |
| sophomore | 285 | +16.29 | +16.67 | **+32.96** |
| junior | 527 | +14.73 | −1.34 | +13.39 |
| senior | 631 | +12.77 | **−19.07** | **−6.30** |

**Two of four class years finish net negative.** Freshmen lose nearly double what camp gave them.
The universals (`ND`/`IQ`/`FT`) gain 88–94% of the time; the nine skills fall for 60–73% of
players. Fit dominates — this is unchanged from the staging measurement and confirms it on prod.

---

## Findings from this season

### AutoTrain is NOT overpowered — winning is

The user's allocation is **identical to the CPU's**: all team drills at 1, `scrimmages: 1`,
general at 1, with `shot_threshold +3` from training in week 26 — same direction and magnitude as
CPU teams.

| | HA Rushmore | CPU mean | CPU best | pctile |
|---|--:|--:|--:|--:|
| player attrs / player | 563.8 | 508.0 | 608.9 | **94%** |
| top-8 position rating | 68.8 | 64.4 | 76.8 | 86% |
| **`shot_threshold`** | **10** | **59.5** | 10 *(user)* | **best in league** |
| `offensive_efficiency` | −10 | +11.4 | +20 | **15%** |

94th percentile on talent — strong, **not** the strongest — and *below average* on offensive
efficiency. **The `shot_threshold` gap is the whole advantage, and winning caused it**: EOG pays
`−6…−2` for shooting above 37%, so 26 straight blowouts took the reward band nearly every game.
Win big → threshold drops → shoot better → win bigger.

**Confirmation it is not the user:** `Couer d'Alene` also went **26-0** with the same Run and Gun
/ Full-Court Press identity and `shot_threshold` 49, without AutoTrain.

### Losing teams: talent, not identity

**`corr(talent, wins) = +0.750`** — dominates everything. Bottom 12 average ~462 total
attributes, top 12 ~558.

Identity is a real but second-order effect:

| defensive vision | n | mean wins | | offensive vision | n | mean wins |
|---|--:|--:|---|---|--:|--:|
| Multiple | 17 | **16.2** | | Attack | 17 | **14.8** |
| Man Lockdown | 17 | 14.7 | | Run and Gun | 28 | 14.3 |
| Full-Court Press | 38 | 13.6 | | Motion | 16 | 12.6 |
| Zone | 40 | 11.8 | | Spread | 31 | 12.4 |
| **Contain** | 16 | **9.3** | | Inside-Out | 36 | 11.8 |

⚠️ **`Contain` costs ~7 wins against `Multiple`** — the clearest identity signal in the data and
the one worth investigating. The bottom 12 skew `Zone` (5/12) and `Inside-Out` (5/12), both
below-average visions, but their talent deficit is the larger factor.

### Drift: a CEILING problem on team attributes, a FLOOR problem on player skills

* **Team:** 233 ceiling rails vs 101 floor. `offensive_efficiency`, `defensive_efficiency` and
  `discipline` each have 45–55 teams pinned at +20; `team_chemistry` has 37 at its ceiling.
* **Player:** the opposite — nine of twelve attributes decline for most players, and only the
  three fit-1.00 universals reliably grow.

---

## Method

Team attributes are point-in-time snapshots of `ftd.team_attributes`. Player attributes are
summed from `ftd.training_reports[week].player_changes`. Read-only against production; the write
guard was verified engaged (`ProdWriteBlocked`) before any query ran.

## Related

* [`team_attribute_testing.md`](./team_attribute_testing.md) — earlier staging franchises, same rail methodology
* [`cpu_identity_design.md`](./cpu_identity_design.md) — the allocation system
* [`../09_Training_Systems/In_Season_Training_Summary.md`](../09_Training_Systems/In_Season_Training_Summary.md) — the fit model these numbers test
* [`../06_Gameplay_Systems/End_Of_Game_System.md`](../06_Gameplay_Systems/End_Of_Game_System.md) — the EOG bands
