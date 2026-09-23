# A posture-dependent sag axis for man off-ball help — counterfactual

**Yes, Loose can be made more rim-protective than Base, and the crossover is early:
`BASKET_PULL` 0.15.** Blending the sag target toward the rim takes the weak-side helper from
12.05 (today's Loose, *worse* than Base) to 10.55 at 0.15, 10.02 at 0.20 and 9.53 at 0.25,
against Base's 10.67.

**The strong side does not pay for it — it gains.** Measured against today's Loose, the
strong-side gap to his man moves only +0.19 at 0.15 and +0.49 at 0.25, while his distance to
the rim falls 14.85 → 13.46 → 12.59. The same amount of "off his man" is simply pointed at
the basket instead of at the ball, and ball-crowding collapses with it: placements sitting
inside the shot-contest radius of the ball drop from **52.4% to 29.0% (0.15) / 25.8% (0.25)**,
against Base's 22.5%.

**Build the axis, not the `HELP_SAG` tune.** Lowering `HELP_SAG` at Loose cannot produce the
ordering at all: its best weak-side result across the whole sweep is **−0.12** against Base
(at 0.35) — a tie inside the measurement's own resolution — and the strong side stays pinned
at ~14.9 from the rim at *every* value. That is arithmetic, not luck: at `HELP_SAG` 0.30,
Loose **is** Base. The tune can remove Loose's penalty; only the axis can give Loose a job.

Reference in use: **`equiv_v3_reference_09f1b0ca9_boxout.json`** (current, cut at the box-out
flip). Nothing was built, flagged, changed or committed except this report and two PNGs.

---

## 1. What was priced

```
sag_target = ball + BASKET_PULL[posture] × (rim − ball)
```

`BASKET_PULL` 0.0 reproduces today exactly. The shipped man help shade stays **ON** in every
variant — this is a second, independent term, not a replacement for it. Deny is untouched (it
returns before the help branch) and so is the inside-man lock.

**Method.** Pure arithmetic on each step's own man/ball/rim, recomputed from the shipped
formula in `_apply_defender_posture` with `HELP_SAG_JITTER` pinned to **0 in every variant
including the baseline**, so nothing is de-phased. Nothing is simulated. The sim RNG state is
captured before the recompute and asserted identical after it — printed as
`RNG state unchanged: OK` on every run below.

**Validation that the recompute is the shipped behaviour:** at `BASKET_PULL` 0.00 it returns
weak-side defender→rim **10.69** at normal and **12.05** at loose (sim arm), against the
**10.71** and **12.03** measured live in `reports/man-help-shade-2026-09-22.md` §3.

Footing: equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders
2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed−8000)`, **`SEED_DEFENSES=1`** (catalogue seeded with the six real defenses),
n=40 seeds 8000-8039, **both arms**, posture set through `EQUIV_MAN_POSTURE` (the playbook
path). 283,510 base and 273,053 loose placements pooled across the two arms. **The two arms
agree to ±0.05 on every number below**, so the tables are the pooled figures.

## 2. The `BASKET_PULL` sweep

Base (normal, today): weak rim **10.67**, strong rim **14.91**, strong gap **6.64**, inside
the contest radius **22.5%**.

| `BASKET_PULL` | weak rim | vs Base | strong rim | strong gap | middle rim | in contest radius |
|---|---|---|---|---|---|---|
| **0.00** (today) | 12.05 | +1.38 | 14.85 | 9.28 | 11.35 | **52.4%** |
| 0.05 | 11.41 | +0.74 | 14.40 | 9.40 | 10.90 | 45.0% |
| 0.10 | 11.05 | +0.37 | 13.91 | 9.37 | 10.60 | 41.1% |
| **0.15** | **10.55** | **−0.12** | 13.46 | 9.47 | 10.16 | 29.0% |
| 0.20 | 10.02 | −0.65 | 12.97 | 9.55 | 9.86 | 27.4% |
| **0.25** | **9.53** | **−1.14** | 12.59 | 9.77 | 9.36 | 25.8% |
| 0.30 | 9.17 | −1.50 | 12.02 | 9.88 | 9.11 | 23.5% |
| 0.40 | 8.32 | −2.36 | 11.09 | 10.42 | 8.34 | 22.1% |
| 0.50 | 7.38 | −3.29 | 10.24 | 10.83 | 7.68 | 20.1% |
| 0.75 | 5.57 | −5.10 | 7.91 | 12.52 | 5.98 | 17.0% |
| 1.00 | 4.36 | −6.31 | 6.15 | 14.15 | 4.33 | 13.1% |

Full detail (p50/p90, distance to ball, rim-ward vs ball-ward decomposition, anchor-floor
rate) for the five briefed values, sim arm:

| variant | side | defender→rim m/p50/p90 | gap to man m/p50/p90 | dist to ball m/p50/p90 | rim-ward | ball-ward |
|---|---|---|---|---|---|---|
| BASE normal | strong | 14.85 / 15.60 / 19.20 | 6.63 / 6.10 / 10.20 | 12.15 / 12.00 / 18.00 | 5.28 | 5.11 |
| | middle | 12.65 / 13.00 / 17.10 | 10.00 / 11.00 / 13.50 | 13.64 / 14.10 / 16.80 | 9.38 | 7.62 |
| | weak | 10.69 / 10.20 / 16.20 | 13.48 / 13.90 / 18.00 | 18.84 / 18.80 / 21.30 | 12.46 | 11.43 |
| loose 0.00 | strong | 14.82 / 15.60 / 19.90 | 9.26 / 9.10 / 14.60 | 9.67 / 10.00 / 17.00 | 6.15 | **8.02** |
| | middle | 11.38 / 12.50 / 17.00 | 13.51 / 13.20 / 20.00 | 11.07 / 11.70 / 13.60 | 11.98 | 11.06 |
| | weak | 12.05 / 12.80 / 15.30 | 19.21 / 20.20 / 26.10 | 13.63 / 13.00 / 16.10 | 16.82 | **17.54** |
| loose 0.25 | strong | 12.57 / 13.30 / 17.10 | 9.74 / 9.20 / 14.30 | 11.48 / 12.40 / 18.20 | **8.14** | 7.17 |
| | middle | 9.39 / 10.20 / 13.30 | 14.36 / 16.10 / 19.00 | 12.53 / 13.50 / 15.70 | 13.51 | 10.90 |
| | weak | 9.51 / 10.00 / 12.60 | 18.63 / 19.70 / 24.00 | 16.11 / 16.40 / 18.60 | **17.22** | 15.81 |
| loose 0.50 | strong | 10.23 / 10.60 / 13.40 | 10.82 / 10.80 / 16.10 | 13.68 / 14.60 / 20.00 | 10.16 | 6.06 |
| | middle | 7.71 / 8.10 / 10.80 | 15.22 / 18.00 / 18.70 | 14.19 / 15.60 / 17.80 | 14.81 | 10.52 |
| | weak | 7.37 / 8.00 / 10.30 | 18.13 / 19.20 / 22.00 | 18.55 / 18.40 / 21.30 | 17.36 | 13.96 |
| loose 0.75 | strong | 7.90 / 8.50 / 10.00 | 12.53 / 13.50 / 17.30 | 15.96 / 17.10 / 23.10 | 12.25 | 5.02 |
| | weak | 5.56 / 6.00 / 8.50 | 18.02 / 18.20 / 20.60 | 20.89 / 20.50 / 24.00 | 17.60 | 12.32 |
| loose 1.00 | strong | 6.15 / 6.70 / 8.60 | 14.16 / 15.00 / 18.40 | 17.88 / 18.60 / 25.50 | 14.01 | 4.16 |
| | weak | 4.34 / 4.50 / 6.30 | 18.43 / 18.00 / 21.60 | 23.40 / 22.80 / 27.00 | 18.15 | 10.82 |

**The decomposition is the whole story.** At today's Loose the strong-side helper's movement
is *more ball-ward than rim-ward* (8.02 vs 6.15) and the weak-side helper's likewise (17.54 vs
16.82). At `BASKET_PULL` 0.25 both invert (7.17 vs 8.14; 15.81 vs 17.22). The magnitude of
the sag barely changes — its **direction** does. That is exactly the diagnosis in the brief.

**`HELP_ANCHOR_FLOOR` is unaffected**: it binds on 26.6% of loose placements at *every*
`BASKET_PULL` value, and 25.8% at base. The blend moves the target, not the anchor weights,
so the floor neither tightens nor loosens.

**Blast radius on the shot contest.** Placements crossing the `CONTEST_EUCLIDEAN_RADIUS` (11)
boundary relative to today, i.e. off-ball helpers who become — or stop being — candidate
contest defenders:

| `BASKET_PULL` | 0.25 | 0.50 | 0.75 | 1.00 |
|---|---|---|---|---|
| crossings vs 0.00 | **26.6%** | 32.5% | 35.7% | 39.5% |

A quarter of loose placements change contest-candidate status at 0.25. That is large, and it
is why **outcomes must be measured before this ships** — geometry alone cannot predict what it
does to the scoreboard. (Caveat: this is distance to the ball at that step, which is the
likely but not certain shot spot.)

## 3. The honest alternative — just lower `HELP_SAG`

Axis untouched, `BASKET_PULL` 0.00 throughout, pooled both arms:

| `HELP_SAG` at loose | weak rim | vs Base | strong rim | strong gap | in contest radius |
|---|---|---|---|---|---|
| **0.55** (today) | 12.05 | +1.38 | 14.85 | 9.28 | 52.4% |
| 0.50 | 11.53 | +0.86 | 14.75 | 8.84 | 43.9% |
| 0.45 | 11.05 | +0.37 | 14.69 | 8.21 | 29.5% |
| 0.40 | 10.83 | +0.16 | 14.85 | 7.72 | 33.5% |
| **0.35** | **10.56** | **−0.12** | 14.92 | 7.09 | 25.1% |
| 0.30 | 10.66 | −0.01 | 14.89 | 6.63 | 22.3% |
| 0.25 | 11.03 | +0.36 | 14.99 | 6.12 | 19.3% |
| 0.20 | 11.21 | +0.53 | 15.04 | 5.57 | 18.5% |

(The contest column is lumpy — 0.45 reads lower than 0.40 — because placements are rounded to
integer grid and the 11.0 threshold catches them unevenly. The rim and gap columns are smooth.)

**The tune has a floor it cannot pass, and the reason is arithmetic.** `HELP_SAG` at 0.30 *is*
Base's sag, so Loose at 0.30 is Base — weak rim 10.66 against Base's 10.67. Going lower keeps
the defender nearer his man and therefore **further** from the rim (11.21 at 0.20). The best
value in the sweep beats Base by 0.12, which is one grid unit's rounding.

And it buys **nothing on the strong side at any value**: strong rim reads 14.69–15.04 across
the entire sweep against Base's 14.91. Lowering the sag walks the helper back toward his man
along the same line; it never points him at the basket. The shade cannot make up the
difference because it is a fixed fraction of man→rim and does not scale with posture.

**At equal weak-side benefit the axis is strictly better.** `HELP_SAG` 0.35 and `BASKET_PULL`
0.15 both give −0.12 on the weak side. The axis additionally brings the strong side 1.45
closer to the rim (13.46 vs 14.92) and cuts ball-crowding to 29.0% (vs 25.1%). And only the
axis can go further: −0.65 at 0.20, −1.14 at 0.25, with the tune already exhausted.

### Which I would build

**The axis, at `BASKET_PULL[loose]` ≈ 0.20–0.25**, and I would pick **0.25**.

- 0.15 is the crossover but its margin (−0.12) is inside the measurement's own 0.1-unit
  bucket. It would be shipping a tie and calling it a win.
- 0.25 gives a real margin (−1.14 weak-side, a rim distance of 9.53 against Base's 10.67),
  inverts the rim-ward/ball-ward decomposition on both sides, and brings ball-crowding
  (25.8%) essentially back to Base's 22.5% — which is the specific pathology behind Loose's
  +2.06 points and +1.79 fouls in `reports/man-posture-fixture-2026-09-22.md` §4: today's
  Loose parks **52.4%** of off-ball helpers inside the contest radius of the ball, guarding
  neither their man nor the rim.
- 0.50 and above turn Loose into a zone — the strong-side helper ends up 10.24 from the rim
  with his man 10.83 away, and by 1.00 everyone is standing in the restricted area. Those
  values are in the table for shape, not as candidates.

The constant is Jamie's single tuning pass; 0.20 is equally defensible and I have priced both.

## 4. Pictures

- [loose-sag-axis-000-2026-09-23.png](reports/loose-sag-axis-000-2026-09-23.png) — `BASKET_PULL` 0.00 (today)
- [loose-sag-axis-025-2026-09-23.png](reports/loose-sag-axis-025-2026-09-23.png) — `BASKET_PULL` 0.25

The same four steps in both, same seeds, same axes; every placement recomputed with the jitter
pinned to 0 so only `BASKET_PULL` differs. Away-offense steps mirrored to attack the same
basket. Drawn from the steps with at least one man off the strong side (376 of 498) — a
central ball produces no weak side and therefore no change, which is about a quarter of all
placements and would have made the two figures identical.

Mean defender→rim per panel, 0.00 → 0.25: seed 8009 **16.9 → 13.7**, seed 8004 **13.9 → 11.1**,
seed 8003 **13.6 → 11.3**, seed 8005 **15.1 → 11.7**. In seed 8009 the far-side man's defender
goes from 24.2 off him to 23.0 while dropping into the lane; the man beside the ball tightens
from 7.0 to 8.7 without leaving the perimeter.

## 5. Pricing the build

One function, one constant, one flag. `_apply_defender_posture` in
[shared_defense.py](BackEnd/utils/shared_defense.py#L2150) — the normal/loose HELP branch only
— gains two lines computing `tx, ty` from a new `HELP_BASKET_PULL = {"normal": 0.0, "loose":
0.25}` declared beside `HELP_SAG`, read by name at call time so it is reused rather than
copied; the existing `hx, hy` then use `tx, ty` in place of `bx, by`. Deny and the inside-man
lock already return before that branch, so neither needs touching, and the man help shade is
left exactly as shipped. Flag `GOB_MAN_LOOSE_SAG_AXIS`, default `"0"`, via a
`loose_sag_axis_enabled()` helper alongside `man_help_shade_enabled()`; with it off the pull
is 0.0 for every posture, which is byte-identical to today. Guard tests would mirror
`tests/test_man_help_shade_flags.py`: default off, kill switch, `HELP_BASKET_PULL` reused not
copied, **normal unchanged at any pull value**, deny and the inside-man lock untouched, and no
clamp. **It would not need a reference re-cut** — and that is the one non-obvious thing about
this build. The equiv-v3 reference footing runs the unset posture, which resolves to base
`man` and therefore posture `normal`, where `BASKET_PULL` is 0.0; so
`equiv_v3_reference_09f1b0ca9_boxout.json` would reproduce 160/160 **whether the flag is on or
off**, and the reference cannot see this change at all. The acceptance evidence has to come
from the posture-parameterised fixture (`EQUIV_MAN_POSTURE=loose`) instead, with its own
loose-footing baseline cut at flip time, and outcomes at n=120 seed-paired — which, given that
26.6% of loose placements cross the shot-contest radius, is the part that actually decides
whether it ships.

---

## Tunable Constants

Reported, not changed. Nothing here is built.

| constant | value today | role | what this counterfactual says |
|---|---|---|---|
| `HELP_SAG` | normal 0.30 / loose 0.55 | fraction of the way from the man toward the sag target | the magnitude; lowering it cannot make Loose rim-protective (floor at ≈ Base) |
| **`HELP_BASKET_PULL`** (proposed) | — | blends the sag target from the ball toward the rim | crossover at **0.15**; recommended **0.25**; ≥0.50 turns Loose into a zone |
| `HELP_BASKET_SHADE` | 0.20 | the rim-ward term, scaled by ball side since 2026-09-22 | kept ON in every variant; independent of the axis |
| `HELP_ANCHOR_FLOOR` | 0.30 | min follow in the basket-aligned axis | bind rate 26.6% at **every** pull value — the blend does not press on it |
| `HELP_SAG_JITTER` | 0.10 | ±0–10% on the sag | pinned to 0 in every variant, baseline included |
| `POSTURE_DENY_DISTANCE` | 2.0 | off-ball deny | out of scope; deny returns before this branch |
| `CONTEST_EUCLIDEAN_RADIUS` | 11 | shot-contest proximity gate | 26.6% of loose placements cross it at pull 0.25 |

**Not built. Not flagged. Nothing committed to behaviour.**
