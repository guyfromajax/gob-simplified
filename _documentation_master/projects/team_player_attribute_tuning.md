# Team & Player Attribute Tuning — measured season

**Latest run completed 2026-08-15.** Full 26-week regular season, simmed in-process via
`scripts/eog_measurement_season.py`.

**Franchise** `6a7faae1e124f3d78f7d63f0` · user team **South Lancaster** · 128 teams ·
1,524 players · 26 weeks on one unchanged configuration.

**Configuration under test** — everything shipped 2026-08-14:

| change | effect |
|---|---|
| `scrimmages` universal baseline of 1 | was Attack-vision only; 80% of teams ran 0 |
| rebound applied ONCE, un-halved, bands re-cut | was two rolls/week with a phantom penalty |
| EOG rebound bands narrowed | max single-game swing 0.14 → 0.10 |
| reactive baseline mean 1.43 → 1.00 + tendency tiers | `fb_opp_modifier` / `pt_opp_modifier` |
| rotating lift on the **nine skills only** | universal:skill ratio 0.97x → 0.72x |

---

## Team attributes — core 8

Range `(-20, 20)`, buckets of 8. 128 teams × 8 attributes = 1,024 slots.

| attribute | −20~−12 | −12~−4 | −4~4 | 4~12 | 12~20 | mean | railed |
|---|--:|--:|--:|--:|--:|--:|--:|
| `offensive_efficiency` | 14 | 2 | 10 | 8 | **94** | +11.9 | 63 |
| `defensive_efficiency` | 27 | 21 | 9 | 10 | **61** | +4.5 | 44 |
| `fb_efficiency` | **61** | 27 | 13 | 1 | 26 | −6.7 | 36 |
| `fb_opp_modifier` | 0 | 0 | 20 | 41 | **67** | +11.4 | 15 |
| `pt_efficiency` | 35 | 18 | 23 | 11 | 41 | +0.1 | 45 |
| `pt_opp_modifier` | 0 | 9 | 31 | 35 | **53** | +8.6 | 10 |
| `discipline` | 18 | 9 | 7 | 10 | **84** | +9.7 | 65 |
| `fight` | 27 | 22 | 12 | 18 | **49** | +2.3 | 34 |

### Rails split by direction

| attribute | mean | at **−20** | at **+20** | total |
|---|--:|--:|--:|--:|
| `discipline` | +9.7 | 8 | **57** | 65 |
| `offensive_efficiency` | +11.9 | 12 | **51** | 63 |
| `pt_efficiency` | +0.1 | **25** | 20 | 45 |
| `defensive_efficiency` | +4.5 | 8 | **36** | 44 |
| `fb_efficiency` | −6.7 | **25** | 11 | 36 |
| `fight` | +2.3 | 12 | 22 | 34 |
| `fb_opp_modifier` | +11.4 | **0** | 15 | 15 |
| `pt_opp_modifier` | +8.6 | **0** | 10 | 10 |
| **TOTAL** | | **90** | **222** | **312** |

**312 of 1,024 slots railed (30%), and 71% of those are at the CEILING.** The league drifts
upward, it does not merely spread. Accepted as intended — teams should have distinct identities
after 26 games.

**The reactive pair are the healthiest in the table**: `fb_opp_modifier` and `pt_opp_modifier`
have **zero teams at the floor** and only 10–15 rails each. That is the tendency-tier design
producing a real distribution rather than a converged one.

**Genuinely bipolar**: `pt_efficiency` (25 down / 20 up) and `fb_efficiency` (25 down / 11 up) —
press and fast-break teams build them while everyone else lets them rot. Identity working.

---

## `rebound_modifier` — U-shaped, hollow middle

Range `0.0–1.0`, mean **0.54**, median 0.60.

| tier | teams | share | |
|---|--:|--:|---|
| 0.0 – 0.2 | **46** | 36% | `██████████████████████` |
| 0.2 – 0.4 | 7 | 5% | `███` |
| 0.4 – 0.6 | 11 | 9% | `█████` |
| 0.6 – 0.8 | 7 | 5% | `███` |
| 0.8 – 1.0 | **57** | 45% | `███████████████████████████` |

Floor 32 · ceiling 34.

⚠️ **81% of teams sit in the two extreme tiers; 19% occupy the middle three.** The mean of 0.54
is two crowds cancelling, not a league centred on 0.5 — being *average* at rebounding is nearly
impossible. The training fix removed the drift but not EOG's step size: **±0.10 in a single
game against training's +0.0125 per week**, so one rebounding run still crosses the range.

---

## `shot_threshold` — tight, single-peaked, ZERO rails

Range `-10–190` (MID 90, init 85–95), mean **57.7**, median 54.5.

| tier | teams | share | |
|---|--:|--:|---|
| −10 – 30 | 3 | 2% | `█` |
| **30 – 70** | **98** | **77%** | `██████████████████████████████████████████████` |
| 70 – 110 | 24 | 19% | `███████████` |
| 110 – 150 | 3 | 2% | `█` |
| 150 – 190 | 0 | 0% | |

Floor 0 · ceiling 0.

✅ **The scrimmages fix worked.** Prior season: mean +135.8, 23 rails, 104 of 128 teams in the
top bucket, and the tier containing the init range EMPTY. Now zero rails in either direction and
a genuine centre — **the only attribute in the system with no rails at all**.

⚠️ Two residual issues, opposite to the rebounding problem: **77% of teams sit in one tier** (so
shooting barely differentiates), and the league settled **~32 below MID**, meaning everyone
shoots better than the scale's centre assumes.

---

## `team_chemistry` — a one-way ramp

Range `7–25` (init 8–11), mean **19.7**, median 21.0.

| tier | teams | share | |
|---|--:|--:|---|
| 7 – 10 | 8 | 6% | `████` |
| 10 – 13 | 10 | 8% | `█████` |
| 13 – 16 | 14 | 11% | `███████` |
| 16 – 19 | 15 | 12% | `███████` |
| 19 – 22 | 19 | 15% | `█████████` |
| **22 – 25** | **62** | **48%** | `█████████████████████████████` |

Floor 6 · ceiling 38.

Monotonically increasing into the top tier. Every tier is populated — healthier than the other
two — but it is a one-way climb from an 8–11 init rather than a spread.

---

## Player attributes — by attribute

Raw attribute points, **not RT**. Every `TOTAL` row is the sum of 12 attribute deltas.

| attr | TC (wk 1) | wks 2–26 | % up | TC + season | % up |
|---|--:|--:|--:|--:|--:|
| **ND** | +1.69 | **+5.45** | 92% | **+7.14** | 97% |
| **IQ** | +1.78 | +4.05 | 87% | **+5.83** | 94% |
| **FT** | +1.75 | +3.95 | 86% | **+5.70** | 94% |
| SC | +1.07 | −1.69 | 34% | −0.62 | 43% |
| RB | +1.15 | −1.57 | 39% | −0.42 | 42% |
| SH | +1.12 | −2.10 | 26% | −0.98 | 32% |
| ST | +1.06 | −2.20 | 32% | −1.14 | 37% |
| OD | +1.08 | −2.45 | 30% | −1.37 | 39% |
| ID | +1.06 | −2.96 | 29% | −1.90 | 34% |
| AG | +1.02 | −3.24 | 26% | −2.22 | 35% |
| PS | +0.99 | −3.24 | 26% | −2.25 | 31% |
| BH | +1.02 | −3.27 | 27% | −2.25 | 32% |
| **TOTAL** | **+14.78** | **−9.27** | 32% | **+5.51** | **58%** |

## Player attributes — by class year

| year | n | camp (wk 1) | in-season | **total** |
|---|--:|--:|--:|--:|
| freshman | 89 | +24.19 | **−46.52** | **−22.33** |
| sophomore | 276 | +16.41 | +14.93 | **+31.34** |
| junior | 527 | +14.84 | −2.33 | +12.51 |
| senior | 632 | +12.68 | **−20.38** | **−7.70** |

### ⚠️ This is materially worse than the previous configuration

| | previous | **this run** |
|---|--:|--:|
| in-season total | −4.59 (12 wks) | **−9.27** (25 wks) |
| season total | +19.53 | **+5.51** |
| players net up | 79% | **58%** |
| freshman total | −8.54 | **−22.33** |
| senior total | +5.52 | **−7.70** |

**Two of four class years now finish net negative.** Freshmen lose all of camp and more; seniors
flipped from +5.5 to −7.7.

**The cause is the deliberate tilt.** Removing `ND`/`IQ`/`FT` from the rotating lift moved points
onto skills at fit ~0.56, where they buy far less than the same points at fit 1.00. The ratio hit
its 0.72x target — but universals still gained (`ND +5.45`) while skills fell *further* than
before. **Fit dominates: the allocation change could not overcome it and made the league poorer
in the attempt.**

Holding all twelve needs 2 points each = 24 = the entire budget with nothing for team drills. The
remaining lever is the in-season economy — `IN_SEASON_GAIN_SCALE` (0.28), the year decay ranges,
and `TRAINING_GAIN_PERCENTAGES` — which belongs to the player-development system.

---

## Method

Team attributes are point-in-time snapshots of `ftd.team_attributes`. Player attributes are
summed from `ftd.training_reports[week].player_changes`. Read-only; no sim or dry run, so none of
the measurement caveats that apply to dry-run A/Bs apply here.

## Related

* [`team_attribute_testing.md`](./team_attribute_testing.md) — earlier franchises, same rail methodology
* [`cpu_identity_training_design.md`](./cpu_identity_training_design.md) — the allocation system
* [`../09_Training_Systems/In_Season_Training_Summary.md`](../09_Training_Systems/In_Season_Training_Summary.md) — the fit model these numbers test
* [`../06_Gameplay_Systems/End_Of_Game_System.md`](../06_Gameplay_Systems/End_Of_Game_System.md) — the EOG bands
