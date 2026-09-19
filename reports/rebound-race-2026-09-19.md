# Stage 1b — the arm split, the OREB rise, and a race prototype

**Both flags stay OFF. Nothing flipped, no reference re-cut, nothing retuned.** Flag-off is **40/40 byte-identical to `equiv_v3_reference_bf7ed1181_crashmodela.json` on all four cells.**

## Q1 — the arm split: the window derivation is NOT the cause

**The brief's prime suspect is rejected, with numbers.** The derived post-shot window is **identical across arms**:

| | sim (`_is_full_simulation` True) | played (False only inside the four gated Animator methods) |
|---|---|---|
| derivations | 1,855 | 1,807 |
| **window mean** | **1.550 s** | **1.550 s** |
| window median | 1.570 | 1.598 |
| p10 / p90 | 1.156 / 1.857 | 1.156 / 1.857 |
| min / max | 0.907 / 2.376 | 0.907 / 2.420 |
| window `None` | 0 | 0 |
| `uses_shot_arc` present | **0.0%** | **0.0%** |
| `shot_variant` present | **0.0%** | **0.0%** |
| `result_type` present | **0.0%** | **0.0%** |
| `shot_spot` present | 100.0% | 100.0% |
| crashers prepared | off 3.59 / def 4.81 per shot | off 3.59 / def 4.78 per shot |

The derivation degrades **identically** on both arms — none of the three outcome fields is ever present at that point, on either arm, so both fall back to the same synthetic result. Pools match to two decimals. **There is no window bug and no derivation asymmetry.**

**What does differ is the starting positions**, which is a pre-existing arm difference that arrival now converts into a rebound outcome:

| | sim | played |
|---|---|---|
| start→destination distance (mean) | **13.89** | **12.76** |
| fully arrived | 84.9% | **87.3%** |
| **DEF mean distance to bounce, shot-moment** | **13.79** | **12.19** |
| OFF mean distance to bounce, shot-moment | 17.13 | 16.12 |

Played's players simply stand closer to the rim at the shot — its defenders are 1.60 units nearer the bounce and its crashers 1.13 units nearer their destinations. Under the legacy rule that difference was diluted across large distances; under arrival everything compresses toward the bounce, so the same difference becomes a larger *relative* one. **The arms diverge because arrival amplifies a starting-position difference that already existed, not because either arm derives the window differently.**

**No fix is proposed, because there is no bug to fix here.** The honest framing is that arrival makes the arms' pre-existing positional difference matter, and if that is unacceptable the question is why the two arms' shot-moment coordinates differ — which is the coord-parity workstream, not this one.

## Q2 — the OREB rise: pool-size asymmetry REJECTED, positional-edge collapse CONFIRMED

**The hypothesis as stated is wrong.** The defensive crash pool is *larger*, not smaller:

| | candidates at selection | of those, actually crashed |
|---|---|---|
| sim OFF | 4.59 | **3.59** |
| sim DEF | 4.81 | **4.81** |
| played OFF | 4.59 | **3.59** |
| played DEF | 4.78 | **4.78** |

The offense sends **fewer** crashers (the shooter is excluded from crashing but remains a candidate), and every defender crashes. Release and get-back exclusions do not leave the defense short-handed. So the offense does not win more boards by arriving in numbers.

**What actually happens is that arrival erases the defense's positional head start:**

| mean distance to the bounce | shot-moment | → arrival | change |
|---|---|---|---|
| sim OFF | 17.13 | 11.63 | −5.50 |
| sim DEF | 13.79 | 10.63 | −3.17 |
| **sim OFF-minus-DEF gap** | **+3.33** | **+1.00** | **−2.33** |
| played OFF | 16.12 | 10.82 | −5.30 |
| played DEF | 12.19 | 9.70 | −2.49 |
| **played OFF-minus-DEF gap** | **+3.93** | **+1.12** | **−2.81** |

Offensive players start much further from the bounce and therefore have much further to close; both sides converge on the same crash area, so the offense gains **2.33 units** on sim and **2.81** on played. `OREB_REBOUND_SCORE_DISCOUNT` (0.8) was the only remaining brake, and it was calibrated against a world where the defense also enjoyed a ~3.3–3.9 unit head start.

**This explains the arm split as well:** played's gap collapses by 2.81 against sim's 2.33, and played's OREB share rose further (+5.50 vs +3.06). One mechanism, both observations. **Reported, not adjusted** — the 0.8 discount is a balance number and tuning happens once, at the end.

## Q3 — the race constant, derived

`time_to_ball = distance(arrival → bounce) / _ag_grid_per_game_sec(player, "standard")`, scored through the same curve: `1 / (1 + time_to_ball / REBOUND_RACE_TIME_SCALE)`.

Measured over **6,555 candidate evaluations** (8 seeds per arm, `SEED_DEFENSES=1`, arrival on):

- league-average arrival distance **D̄ = 10.7069** grid units
- league-average time to ball **T̄ = 0.7752** game-seconds
- `REBOUND_RACE_TIME_SCALE = T̄ × REBOUND_DISTANCE_SCALE / D̄ = 0.7752 × 8.0 / 10.7069 = **0.5792**`

Verification: the distance term at D̄ is `1/(1 + 10.707/8.0) = 0.427651`; the race term at T̄ is `1/(1 + 0.775/0.5792) = 0.427651`. **Identical to six decimals** — the average player's discount is unchanged and only the spread between players moves. Implied mean travel rate D̄/T̄ = **13.81** grid units per game-second.

## Q4 — measurements: the race barely moves anything, and the reason is the rate curve

`SEED_DEFENSES=1`, n=40, arrival-only → arrival+race:

| | sim | played |
|---|---|---|
| winner-is-nearest | 22.4% → **22.3%** | 21.7% → **22.2%** |
| **winner mean AG** | 37.56 → **39.06** (field 43.88) | 36.21 → **36.91** (field 44.18) |
| winner had the highest AG | 16.0% → 17.2% | 14.8% → 14.1% |

**Win share by AG band** (candidate share in brackets):

| band | sim arrival → race | played arrival → race |
|---|---|---|
| AG < 40 *(45.8% of candidates)* | **64.3% → 61.6%** | 67.3% → 65.6% |
| AG 40–60 *(21.5%)* | 10.9% → 11.5% | 9.1% → 10.3% |
| AG > 60 *(32.7%)* | **24.8% → 26.9%** | 23.6% → 24.1% |

**Arrival fraction and fully-arrived, by band** (unchanged by the race, which only re-weights scoring): AG<40 0.964 / 87.4%, AG 40–60 0.953 / 81.9%, AG>60 0.963 / 83.3% on sim. The bands remain indistinguishable.

**Outcomes** — every movement is inside the CI and the two arms move in opposite directions:

| | sim arrival → race | played arrival → race |
|---|---|---|
| pts/team | 74.66 → 75.10 (+0.44) | 74.21 → 73.12 (−1.09) |
| OREB share | 29.41% → 31.20% (+1.79) | 31.56% → 28.76% (−2.80) |
| possessions | 41.05 → 40.65 (−0.40) | 39.83 → 41.95 (+2.12) |
| draws/game | 69,274 → 69,062 (−212) | 81,705 → 81,798 (+93) |
| arm gap | +0.45 ±4.04 → **+1.98 ±3.35** | |

`SEED_DEFENSES=0`: OREB share −0.08 (sim) / −0.23 (played), pts/team −1.29 / −0.47, arm gap −0.17 → −0.99.

**§8.1 coord-continuity corrections: 0 in every cell, both configurations, both arms.** Errors: 0 across 320 measured games.

**Gates:** independence **PASS** on both arms and both footings; FT-honour windowed 99.6–99.9%. **Flag-off 40/40 byte-identical on all four cells.**

### Why the race does so little — the finding of this pass

The race term *can* only ever be a small lever, because **`_ag_grid_per_game_sec` barely responds to AG**:

| AG | standard rate | time for 10 units |
|---|---|---|
| 10 | 12.88 | 0.776 s |
| 50 | 14.00 | 0.714 s |
| 90 | 15.12 | 0.661 s |

**A 9× difference in AG produces a 17% difference in rate**, and therefore at most a ~±7% difference in the scoring term after the calibration. That is far below the `randint(1, 6)`'s 6× swing, which is why the winner mean AG moves only +1.50 and the AG>60 win share only +2.1 points.

**And a caution about a number that looks dramatic but is not.** In the trace, the race changes the winner on **101 of 149 misses (68%)**. That is *churn among near-equals*, not a systematic shift: the dice already decide the winner about half the time, so a ±7% term change flips a great many coin-flips without moving who is actually favoured. The aggregate tables are the truth here, not the change rate.

**The lever is the rate curve, not the term.** If AG is meant to decide rebounds, `_ag_grid_per_game_sec`'s AG sensitivity is what needs to change — and that is a balance number, so it is reported and left alone.

One structural point worth noting alongside it: **AG<40 players are 45.8% of candidates but win 64.3% of boards.** The composite is RB-weighted and bigs are slow, so AG is pushing against the grain of the rest of the model.

## Q5 — the trace

**`reports/rebound-race-trace-2026-09-19.md`** — eight real misses, each with every candidate's arrival point, AG, **rate**, distance and time to ball, and the winner under each rule. Both winners come from the same miss with the sim RNG state saved and restored, so **the dice are identical in both columns**. The `rate` column is the story: across a field spanning AG 22–75 it varies only 13.22–14.70.

## Footing (rule 6e)

- **Branch `feature/animation-reward`**, prototype at `aa8921612`. Worker: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- Probes are read-only and never call `calculate_rebound_score` — that consumes the `randint(1,6)` dice and perturbed a run once already; the composite is recomputed from attributes instead.
- **A mid-pass machine restart wiped the scratchpad** (probes and one partial diagnostic). The source edits survived; the probes were recreated and every run below was re-executed from scratch on the settled tree.

## Not covered

- **Nothing flipped, nothing re-cut, nothing retuned.** `GOB_REBOUND_FROM_ARRIVAL` and `GOB_REBOUND_RACE` both remain default OFF.
- The composite, the team bonus, the 0.8 discounts, `REBOUND_DISTANCE_SCALE` and the `randint(1,6)`: untouched.
- `crash_destination.py`'s allowlisted signature and its two poisoned tests: untouched. Destinations still never read the bounce.
- **Not proposed:** a fix for the arm split, because the measurement shows no bug in the window derivation. The underlying cause is that the two arms' shot-moment coordinates differ, which belongs to the coord-parity work.
- **Not measured:** whether the OREB rise would come back into line if `OREB_REBOUND_SCORE_DISCOUNT` were re-derived against the new gap. That is a tuning question.
- **Not measured:** the FB-miss branch separately from HCO; both are in the aggregate.
