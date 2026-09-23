# Sweeping the AG movement spread — audit and counterfactual

**The shortfall does not bite where the design note assumed: it is concentrated in
`standard`, and `burst` and `drift` never occur for defenders at all.** Of 645,163 moving
defender placements, `cruise` is 49.4% but ends short only 14.1% of the time, while `standard`
is 41.2% and ends short **55.7%** of the time with a mean shortfall of 27.4 grid units. Burst,
drift, shot_motion and compressed_hco account for **zero** defender placements. So "wide on
burst and sprint, narrow on drift and cruise" is the wrong mapping — it would widen two
archetypes that never run and leave untouched the one that decides almost every shortfall.

**Fast and slow become visibly different at about s = 0.50 (±50%), and the cost is small.**
The p10→p90 endpoint gap on `standard` goes **0.66 → 3.49 grid units** (today → s=0.50), which
the eye can see on 41% of placements — but only **2.4% of placements change proximity band** and
**1.1% cross the 11 gate**. Even the extreme s=0.75 moves only 4.0% of placements across a band.
Widening buys visual variety cheaply; it does not move the contest much.

**LATE is not redundant, but it is no longer required for complaint #2.** The spread fixes the
*between-player* problem Jamie actually described — "defenders all move identically regardless
of who they are". LATE fixes a different one: *within-player, between-step* variation, a
defender beaten on timing rather than on speed. On the evidence I would ship the spread first
and hold LATE.

Reference used: **`equiv_v3_reference_1f4af0ede_loosesag_nogate.json`**. develop has not moved
(`0a5af30ca` is HEAD and added only markdown); the reference was confirmed **160/160** at
`c33e4879b` and the census probe here reproduces it exactly — fingerprint `b8c4ce02536e2a6d`
and **74,529 draws** at seed 8000, unchanged. Nothing built, no flag, no constant changed.

---

## 0. A correction to my own census

Two numbers in `reports/movement-variance-census-2026-09-24.md` need adjusting, both because
that census hit the **module-level import trap**: it patched `animation_step_helpers
.stamp_tween_durations`, but every caller does `from … import stamp_tween_durations`, so the
patch reached only the minority of call sites that go through the module attribute.

| | census said | complete data | effect |
|---|---|---|---|
| steps per game | 2,573 | **2,785** | census saw 92.4% of steps |
| moving defender placements per game | 7,864 | **8,065** | same shortfall rate, wider base |
| **ends short** | **31.8%** | **31.9%** | unchanged — the conclusion holds |

The headline conclusion is unaffected: **31.9%** of moving defender placements still end short.
Fixed here by rebinding the name in all seventeen modules that hold it.

One further correction, to a number I estimated rather than measured. The census said the
fastest and slowest defender differ by "roughly 1.2 grid units"; that was arithmetic
(rate difference × median T), not a measurement. **Measured, the p10→p90 endpoint gap today is
0.35 units overall** — 0.66 on `standard`, 0.26 on `sprint`, 0.11 on `cruise` — because on most
placements *both* defenders reach the target and the gap is exactly zero. The real starting
point is three times smaller than I reported.

## 1. Where the shortfall actually bites

n=40 seeds 8000-8039, both arms, SD=1. 1,105,185 defender-step slots (all five defenders every
step), of which **645,163 (58.4%) demand movement**. Rates at today's s=0.10.

| archetype | moving | share | ends short | mean shortfall | p90 | mean T | mean distance |
|---|---|---|---|---|---|---|---|
| **cruise** | 318,513 | 49.4% | 14.1% | 3.90 | 8.60 | 1.32 | 7.0 |
| **standard** | 266,123 | 41.2% | **55.7%** | **27.39** | 56.40 | 1.31 | **28.1** |
| **sprint** | 57,303 | 8.9% | 22.4% | 8.32 | 20.47 | 1.21 | 14.6 |
| other (unnamed) | 3,224 | 0.5% | 0.0% | 0.00 | 0.00 | 0.68 | 0.3 |
| **burst / drift / shot_motion / compressed_hco** | **0** | **0.0%** | — | — | — | — | — |

By context:

| context | moving | share | ends short |
|---|---|---|---|
| **HCO** | 470,179 | **72.9%** | **27.6%** |
| non-HCO | 174,984 | 27.1% | 43.5% |

### Answer

**The proposed mapping is wrong, and the data says so unambiguously.** Widening `burst` and
`sprint` while narrowing `drift` and `cruise` would:

- change **nothing at all** on burst and drift — defenders are never assigned either;
- touch 8.9% of placements via sprint;
- deliberately narrow `cruise`, which is half of all placements;
- leave `standard` — 41% of placements, 56% of all shortfalls, and essentially all of the
  shortfall *mass* — at today's near-flat band.

There is also a structural squeeze worth naming. On `cruise` the defender is asked for 7.0 units
in 1.32 s with ~18 units of budget: he arrives whatever his AG, so the endpoint cannot express
speed. On `standard` he is asked for 28.1 units against the same ~18: he falls short whatever
his AG, and speed changes only *how far* short. The band where AG decides arrive-versus-not is
narrow, which is exactly why today's gap measures 0.35 units rather than the 1.2 I estimated.

The design note's instinct — differentiate on short explosive movement — is realistic but has no
purchase on the **endpoint**, because short movements already complete. Where it already lives
is the **tween duration**: `stamp_tween_durations` writes `min(dist/rate, T)`, so a quick
defender on a cruise step already arrives early and idles. That is the "first-step quickness"
channel, and it is orthogonal to this sweep.

## 2–4. The sweeps

Midpoint-preserving band: `scale(AG) = (1 − s) + (AG/100) × 2s`, so AG=50 is 1.0 at every `s`
and the average player never changes. Counterfactual only: each placement's own start, target,
archetype, AG and T, recomputed through the shipped `_interrupted_coord` arithmetic. Nothing
simulated, no RNG. p10/p90 AG are the **real league** values (24 / 73).

Sweep B mapping, derived from §1 rather than assumed — sensitivity proportional to how often
that archetype's endpoint is actually rate-determined (end-short rate 55.7 / 22.4 / 14.1):
`standard 1.00, sprint 0.40, cruise 0.25`, and the sweep scales the whole map.

| variant | ends short | mean shortfall | p90 | **p10→p90 gap: standard / sprint / cruise** | band moves | crosses 11 |
|---|---|---|---|---|---|---|
| **A s=0.10 (today)** | 31.9% | 21.08 | 53.41 | **0.66** / 0.26 / 0.11 | — | — |
| A s=0.25 | 32.7% | 21.05 | 53.50 | 1.68 / 0.72 / 0.28 | 0.92% | 0.40% |
| **A s=0.50** | 35.1% | 20.59 | 53.31 | **3.49** / 1.69 / 0.62 | **2.44%** | 1.14% |
| A s=0.75 | 38.3% | 20.10 | 52.95 | 5.42 / 3.04 / 1.08 | 4.01% | 2.06% |
| B arch ×0.25 | 31.8% | 21.47 | 53.80 | 1.68 / 0.26 / 0.07 | 0.71% | 0.29% |
| **B arch ×0.50** | 32.8% | 21.59 | 54.08 | **3.49** / 0.56 / 0.14 | **1.67%** | 0.72% |
| B arch ×0.75 | 33.8% | 21.92 | 54.50 | 5.42 / 0.88 / 0.21 | 2.67% | 1.25% |
| B arch ×1.00 | 34.2% | 21.76 | 54.36 | 5.42 / 1.25 / 0.28 | 2.80% | 1.33% |

"Band moves" = the placement's endpoint changes which proximity band it sits in relative to the
ball handler (≤3 full contest / 3–9 graded ramp / 9–11 floor 0.15 / >11 nothing). "Crosses 11" =
it moves in or out of contest range entirely.

**On the within-step spread:** I measured the maximum pairwise distance between the five
defenders' endpoints, and it is ~83 units in *every* variant (83.20 today → 82.60 at s=0.75).
That metric is dominated by formation geometry — the five defenders are spread across the court
regardless of how fast they run — so it cannot discriminate between these variants and I have
not used it. The p10→p90 same-step gap is the discriminating number.

### At AG 144 (the league maximum, above the 100 the formula assumes)

| s | scale @144 | standard | sprint | burst |
|---|---|---|---|---|
| 0.10 (today) | 1.188 | 16.63 | 21.38 | 38.02 |
| 0.25 | 1.470 | 20.58 | 26.46 | 47.04 |
| 0.50 | 1.940 | 27.16 | 34.92 | **60.00 — clamped** |
| 0.75 | 2.410 | 33.74 | 43.38 | **60.00 — clamped** |

The `[0.5, 60]` clamp does catch the top end, but only on `burst`, and it starts biting at
s=0.50. **No defender is affected** — burst is never assigned to one — but burst is the FB
outlet archetype for the offence, so a shared-function change at s≥0.50 would silently flatten
the top of the offensive fast break. That is one more reason not to touch the shared function
(§5). Nothing at the bottom end clamps: the worst case is AG=10 at s=0.75, giving
`standard × 0.40 = 5.6`, well above the 0.5 floor.

### Where does it become visible?

Two different answers, and they should not be conflated:

- **Visible to the eye — yes, at s≈0.50.** The p10→p90 gap on `standard` reaches **3.49 grid
  units** (≈3.5 ft), on 41% of placements. At s=0.25 it is 1.68, which is about one defender's
  stance and marginal. At s=0.75 it is 5.42, clearly visible but also the point where the
  shortfall rate climbs to 38.3%.
- **Visible in the contest — barely, at any value.** Even s=0.75 moves only **4.01%** of
  placements across a proximity band and **2.06%** across the 11 gate. Half of graded shots have
  the defender inside 3 units where the factor is pinned at 1.0, so movement there does nothing.

**So the honest framing is that this is a cosmetic-tier change with a real visual payoff.** That
is a feature, not a disappointment: Jamie asked for variety, not for a rebalance.

**On the drive corridor:** the same 11.0 threshold is crossed by 1.14% of placements at s=0.50
and 2.06% at s=0.75. I have **not** re-derived the drive-end guardian count (0 / 1 / 2+) under
each variant, and I will not pretend to: that count is the product of a whole chain of steps,
and this is a single-step counterfactual with no re-simulation. What I can say is that today's
distribution is 2.06% / 11.10% / **86.84%** — drive ends are almost always crowded, so a
1–2% per-placement crossing rate has very little room to turn a guarded rim into an open one.
Measuring it properly needs outcome runs, which this brief correctly defers.

## 5. The pacing trap — confirmed, quantified, and avoidable

Player rate feeds `natural_t` ([transition_bridge.py:285](BackEnd/utils/transition_bridge.py#L285)),
which feeds the gate ([:296-327](BackEnd/utils/transition_bridge.py#L296-L327)), which sets `t`
([:328](BackEnd/utils/transition_bridge.py#L328)). Widening the **shared** function therefore
changes how long steps take. Quantified over the defender AG actually in play (mean 45.1):

| s | mean step T vs today | game length |
|---|---|---|
| 0.25 | ×1.0283 | **+2.8%** |
| 0.50 | ×1.1121 | **+11.2%** |
| 0.75 | ×1.2801 | **+28.0%** |

The inflation is one-sided because `1/x` is convex: slowing a below-average player costs more
seconds than speeding an above-average one saves, and the league mean AG (44) sits below the
curve's 50 anchor. Mean step T today is 1.076 game-seconds, and this scales the **74.6%** of
steps that are `player_reaches_position`-gated; ball-gated and fixed-duration steps are immune.

**A +11% pacing change at the very setting that first looks good is not acceptable collateral.**

**The alternative is clean by construction.** Applying the widened band *only* to the defender
endpoint, inside the `final_end_coords` loop at
[transition_bridge.py:335-344](BackEnd/utils/transition_bridge.py#L335-L344), runs strictly
after `t` is frozen at :328 and after `natural_t`/`rates` have already been consumed by the gate
at :296-327. The widened rate therefore **cannot** reach `natural_t`, cannot reach
`_offense_arrival_times`, and cannot change T — not by discipline, but because the values it
would need to influence are already fixed. Offence is untouched because the loop can branch on
lineup membership.

**I would build the endpoint-only version.** The shared-function version is a pacing change
wearing a movement-variety costume.

One subtlety that must ship with it: `stamp_tween_durations`
([:420](BackEnd/utils/transition_bridge.py#L420)) recomputes the rate independently to write
each player's tween duration. If the endpoint uses a widened rate and the tween uses the narrow
one, the rendered motion stops matching the distance actually covered. **Both must read the same
rate**, so the build touches two functions, not one.

## 6. What this means for LATE

**Complementary, not redundant — and no longer the first thing to build.**

- The **spread** is a fixed per-player property: the same defender is always the fast one. That
  is precisely Jamie's complaint #2 — *"defenders all move identically regardless of who they
  are"*. The sweep addresses it head-on and, at s=0.50, visibly.
- **LATE** is a per-step property: any defender, fast or slow, can be caught a beat behind. It
  produces *within-player* variation the spread cannot, because a fixed multiplier is by
  definition never surprising.

There is also a coverage argument in LATE's favour. The spread is powerless exactly where the
census showed the most headroom: on `cruise` — half of all placements — the defender has ~18
units of budget for a 7.0-unit demand, so no realistic multiplier stops him arriving, and the
p10→p90 gap only reaches 0.62 even at s=0.50. A lag, by contrast, eats the budget directly and
**can** make a cruise-step defender late. If Jamie later wants variety on the short, tidy
half-court movements rather than on long recoveries, LATE is the only one of the two that
reaches them.

Recommendation: **ship the spread, keep LATE parked but not cancelled**, and revisit it only if
the eye test says the short movements still look uniform.

## 7. Pricing the build — described, not written

Flag `GOB_DEFENDER_AG_SPREAD`, default `"0"`. A single named constant beside the existing rate
constants — `DEFENDER_AG_SPREAD = 0.50` for the global form, or a small archetype map if Jamie
prefers sweep B — read by name at call time so a retune moves it. It lands in exactly two
places: the `final_end_coords` loop at
[transition_bridge.py:335-344](BackEnd/utils/transition_bridge.py#L335-L344), where the
defender's endpoint is computed (the branch condition `natural_t[pid] > t` has to be re-evaluated
at the widened rate, and `_interrupted_coord` then takes that rate), and
[`stamp_tween_durations`](BackEnd/utils/animation_step_helpers.py#L1193-L1226), so the tween
matches the distance actually covered. It must **not** go into `ag_to_grid_per_game_sec`, for the
reason in §5. Kill switch: `s = 0.10` reproduces today exactly, since that is the current
formula rewritten — `(1−0.10) + (AG/100)×0.20` is `0.90 + (AG/100)×0.2` identically, so the
rollback is byte-identical rather than merely equivalent. **A reference re-cut would be
needed** — this fires on every defender placement in every scheme at every posture, changing
~3% of placements' endpoints at s=0.25 and more above, so every seed will move in all four
cells. **Small build**: one rate expression, two call sites, no new state, no RNG, no ordering
hazard once it sits after :328. The work is the eye test and the outcome run, not the diff.

---

## Tunable Constants

Reported, not changed.

| constant | value today | effect | what the sweep says |
|---|---|---|---|
| AG band `s` in `ag_to_grid_per_game_sec` | **0.10** (`0.90 + AG/100 × 0.2`) | player speed multiplier | p10→p90 endpoint gap 0.66 on standard; 3.49 at s=0.50 |
| `STANDARD_GRID_PER_GAME_SEC` | 14 | curve anchor at AG=50 | midpoint preserved at every `s`, so the average player never moves |
| archetype bases | standard 14 / cruise 13 / sprint 18 / drift 8 / burst 32 | movement kind | **defenders only ever get cruise, standard, sprint** |
| rate clamp | `[0.5, 60]` | safety rails | catches burst at AG 144 from s=0.50; no defender ever clamps |
| `CONTEST_EUCLIDEAN_RADIUS` | 11 | hard contest gate | crossed by 1.14% of placements at s=0.50 |
| `PROXIMITY_CONTEST_NEAR_DIST` / `_OPEN_DIST` | 3.0 / 9.0 | grading ramp | 2.44% of placements change band at s=0.50 |
| `HCO_CUTOFF_PATH_CORRIDOR` | 11.0 | drive help corridor | drive ends carry 2+ guardians 86.8% of the time |

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed−8000)`, n=40 seeds 8000-8039, **both arms**, **`SEED_DEFENSES=1`** (catalogue
seeded with the six real defenses). All shipped flags at their current defaults. 80 games,
1,105,185 defender-step slots captured, 0 census errors.

The census wraps `stamp_tween_durations` — rebound in all seventeen modules that import the name
by value, which is the trap the previous census fell into — plus five emitter entry points for
the HCO/non-HCO context. Every wrapper calls the original **first** and reads only arguments and
return values. Proved, not asserted: the instrumented run reproduces the reference fingerprint
**and** draw count exactly (`b8c4ce02536e2a6d` / 74,529 at seed 8000).

Every sweep number is a counterfactual recomputed offline from each placement's own start,
target, archetype, AG and T through the shipped `_interrupted_coord` arithmetic. Nothing was
simulated at any variant, so no number here propagates across steps — single-step only, stated
wherever it matters.

**Nothing built. No flag. No constant changed.**
