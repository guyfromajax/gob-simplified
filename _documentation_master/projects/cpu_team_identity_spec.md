# CPU Team Identity — Design Spec

*Draft for review. Everything in §1–§3 is settled and measured. §4–§7 are proposals
that need your eye, particularly the slider distributions.*

---

## 1. Model

A team holds a **vision** — one offensive, one defensive, chosen independently — set at
training camp and re-evaluated every five weeks. The vision drives four surfaces:
playbooks, game plans, training, and lineup/rotation.

Vision is **chosen**, not derived. The roster determines which visions are *plausible*;
the choice picks among them. A team then grows into its vision through training, and the
cost of abandoning one is emergent — player attributes rebuild slowly, and team
attributes decay under the EOG "use it or lose it" mechanic.

```
roster signals  →  fit scores  →  vision pair  →  four surfaces
                                       ↑                ↓
                                       └──── training ───┘
```

---

## 2. Signals

Eight signals, all computed over the **projected starting five**, using `anchor_<attr>`
with `<attr>` fallback.

> ⚠️ "Projected starting five" here means `team_identity.projected_starting_five` — a **greedy**
> fill, and now a DIFFERENT five from the one the UI displays. The display surfaces moved to
> the exact max-weight assignment in August 2026 (`06_Gameplay_Systems/CPU_Team_Rotation_System.md`
> §6); this one deliberately did not, because the frozen constants in §3 were calibrated
> against the greedy five. Re-pointing it requires re-deriving them. Ticketed in `bugs.md`.

| Signal | Definition | Notes |
|---|---|---|
| `fuel` | `min ND` | weakest-link: one gassed defender kills a press |
| `athleticism` | `p20 (AG+ST)` | p20 not min — min was 91% guards |
| `intelligence` | `min IQ` | |
| `tempo_tilt` | `ΣOD − ΣSC` | confound-free by construction |
| `scoring_tilt` | `ΣSH − ΣSC`, orthogonalized on `tempo_tilt` | |
| `inside_peak` | `best SC + 0.3 × second SC` | **not** orthogonalized on tempo |
| `attack_peak` | `best (SC+AG) + 0.3 × second`, orthogonalized on `inside_peak` | |
| `breadth` | outside concentration, negated | low concentration = many shooters |
| `multiple_signal` | `min(athleticism_z, intelligence_z)`, then standardized | |

`fuel`, `athleticism`, `intelligence`, `inside_peak`, `attack_peak` are residualized on
`starter_strength` (OLS residual) before standardizing. The tilts and breadth are not —
they're confound-free already.

### Frozen scale constants

Each signal is centered and scaled by constants fixed at pool calibration. **Not** a
live z-score — a league that trains up drifts away from the fixed scale, which is how
macro trends show.

| Signal | mean | sd |
|---|---|---|
| `fuel` | 33.1641 | 4.9118 |
| `athleticism` | 84.0266 | 10.6469 |
| `intelligence` | 29.0469 | 4.8520 |
| `tempo_tilt` | −7.1016 | 35.6489 |
| `scoring_tilt` | 9.0547 | 37.0003 |
| `inside_peak` | 99.1000 | 16.4100 |
| `attack_peak` | 193.8289 | 20.8603 |
| `breadth` | −0.3085 | 0.0427 |
| `multiple_signal` | −0.5232 | 0.8253 |

`multiple_signal`'s constants are downstream of `athleticism` and `intelligence` —
changing either forces re-derivation.

---

## 3. Fit function

### Offensive weights

| Vision | fuel | tempo_tilt | scoring_tilt | inside_peak | attack_peak | breadth | cost |
|---|---|---|---|---|---|---|---|
| Run and Gun | +2.0 | −1.0 | 0 | 0 | 0 | +0.5 | 2 |
| Spread | 0 | 0 | +2.0 | −0.5 | 0 | +1.5 | 0 |
| Inside-Out | 0 | 0 | −1.0 | +2.0 | 0 | −1.0 | 0 |
| Attack | +0.5 | −0.5 | 0 | 0 | +2.0 | +0.5 | 1 |
| Motion | flat **+0.60** | | | | | | 1 |

### Defensive weights

| Vision | fuel | athleticism | intelligence | tempo_tilt | multiple | cost |
|---|---|---|---|---|---|---|
| Full-Court Press | +2.0 | +1.5 | 0 | +1.0 | 0 | 2 |
| Man Lockdown | +0.5 | +2.0 | 0 | 0 | 0 | 1 |
| Zone | −0.5 | 0 | +2.0 | 0 | 0 | 0 |
| Multiple | 0 | 0 | 0 | 0 | +2.0 | 1 |
| Contain | flat **−0.50** | | | | | 0 |

Zone's negative fuel weight is deliberate — it's the right answer for a team that
*can't* run, not a penalty.

### Selection

```
1. score all ten visions
2. enumerate pairs; discard any where off_cost + def_cost > fuel_capacity
3. softmax over surviving pairs at T = 0.5, sample one
```

**Fuel capacity by tercile of residualized `fuel`: high 4, mid 2, low 1.**

The high tercile is 4 rather than 3 so that Run and Gun + Full-Court Press is reachable
— it's the intended reward for a high-stamina roster. Lands ~17 teams (13%).

> **Press prevalence is tuned via fuel capacity, not via the Full-Court Press weights.**
> The filter moves FCP by more than any scoring weight does. If 13% is too common,
> narrow the capacity-4 band to the top quintile rather than changing costs.

Softmax `T = 0.5` puts the top pair at ~64% and gives teams an effective choice among
3–4 pairs. Usable range is 0.3–1.0; below 0.15 it's deterministic, above 2.0 it stops
expressing preferences.

---

## 4. Surface: strategy sliders

**Two different scales.**

*Standard nine* — `offense`, `inside`, `attack`, `outside`, `tempo`, `alterations`,
`defense`, `aggression`, `rebounding`. Default 2, skew symmetrically.

*Special three* — `hc_trap`, `fc_press`, `fast_breaks`. 1 is normal, 3 is an identity
team, 4 is exceptional. Most of the league lives at 0–1.

Each vision specifies **weight vectors over [0,1,2,3,4]**, drawn per game. This reuses
the existing `_strategy_roll_trap_press()` mechanism — same call site, vision-specific
table instead of the league-wide `[34,40,20,5,1]`.

The distribution's *width* is a personality dial: narrow means a rigid system coach,
wide means an adaptive one.

### Offensive visions

| Vision | Slider | Weights `[0,1,2,3,4]` |
|---|---|---|
| **Run and Gun** | `fast_breaks` | `[0, 5, 20, 60, 15]` |
| | `tempo` | `[0, 0, 15, 60, 25]` |
| | `offense` (motion lean) | `[0, 10, 30, 45, 15]` |
| **Spread** | `outside` | `[0, 0, 20, 55, 25]` |
| | `inside` | `[15, 45, 35, 5, 0]` |
| | `offense` (motion lean) | `[0, 5, 25, 50, 20]` |
| **Inside-Out** | `inside` | `[0, 0, 15, 60, 25]` |
| | `outside` | `[5, 30, 50, 15, 0]` |
| | `offense` (set lean) | `[15, 45, 35, 5, 0]` |
| | `tempo` | `[10, 35, 45, 10, 0]` |
| **Attack** | `attack` | `[0, 0, 15, 60, 25]` |
| | `alterations` | `[0, 10, 35, 45, 10]` |
| **Motion** | all | `[5, 20, 50, 20, 5]` — centered, no lean |

### Defensive visions

| Vision | Slider | Weights `[0,1,2,3,4]` |
|---|---|---|
| **Full-Court Press** | `fc_press` | `[0, 5, 15, 65, 15]` |
| | `hc_trap` | `[0, 10, 25, 55, 10]` |
| | `aggression` | `[0, 0, 20, 55, 25]` |
| **Man Lockdown** | `defense` (man lean) | `[20, 55, 25, 0, 0]` |
| | `aggression` | `[0, 10, 45, 40, 5]` |
| | `hc_trap` | `[20, 50, 25, 5, 0]` |
| **Zone** | `defense` (zone lean) | `[0, 0, 25, 55, 20]` |
| | `aggression` | `[10, 40, 45, 5, 0]` |
| | `hc_trap` / `fc_press` | `[45, 45, 10, 0, 0]` |
| **Multiple** | `defense` | `[10, 25, 30, 25, 10]` — genuinely spread |
| | `aggression` | `[0, 15, 50, 30, 5]` |
| **Contain** | `defense` | `[10, 30, 40, 20, 0]` |
| | `aggression` | `[25, 50, 25, 0, 0]` |
| | `hc_trap` / `fc_press` | `[60, 35, 5, 0, 0]` |

> **Assumption to confirm:** I've read `offense` as motion↔set and `defense` as man↔zone,
> with higher = more motion / more zone. If either is inverted, flip those rows.

Sliders a vision doesn't name are drawn from the neutral `[5, 20, 50, 20, 5]`.

### Mid-game adjustment (deferred)

When CPU mid-game adjustment lands, movement should be **bounded to ±1 within the
vision's support**, driven by game state — not a fresh draw. A pressing team trailing
late pushes to 4; up twenty it eases to 2. Never to 0, because that isn't who they are.

---

## 5. Surface: playbooks

Two things per vision: **which play families** and **how concentrated**.

Concentration is set from the `breadth` signal, in three bands. Low breadth → few plays,
funneled to the focal scorer. High breadth → many plays, distributed.

| Vision | Play families | Concentration |
|---|---|---|
| Run and Gun | fast breaks weighted, motion base | medium |
| Spread | outside sets, motion | **low** (many plays) |
| Inside-Out | post family — Base, Movement, Flash, etc. | **high** personnel, **low** play conc. |
| Attack | drives, iso, pick-and-roll | medium-high |
| Motion | motion base, balanced sets | medium |

**Inside-Out is the important case.** Concentrated personnel, diverse *plays* — feed one
post scorer through five different actions. That's how a star-driven team reaches the
EOG `offensive_efficiency` reward tier instead of paying a permanent scouting tax.

**The concentration caps must be lifted.** `_set_play_percentages` currently tops out
around 45%, and `_random_capped_three(max_pct=50)` caps motion shares, so no CPU team can
exceed ~25% top-play share. That ceiling has to rise for Inside-Out and Attack to be
expressible at all.

Defensive visions also carry play sets — Full-Court Press should hold 3–4 press variants,
since the EOG concentration penalty applies to press plays too.

---

## 6. Surface: training

**Split by half.** Player development stays on the frozen reference substrate
(`_CPU_REFERENCE_BASE`, quality ~1.0, guarded by `test_cpu_reference_training.py`).
Archetype drives only the **team-attribute drills**.

Changing the player-development half would break the coaching-quality normalization and
drift the league off the RT ladder. That's not what this system is for.

| Vision | Team drill emphasis |
|---|---|
| Run and Gun | FB offense install, conditioning |
| Spread | team offense install |
| Inside-Out | team offense install |
| Attack | team offense install, scrimmages |
| Motion | balanced |
| Full-Court Press | P/T install, conditioning |
| Man Lockdown | team defense install |
| Zone | team defense install, film study |
| Multiple | team defense install (split) |
| Contain | team defense install, breaks |

**This is where forced specialization lives.** 24 points across 20 categories means
emphasis is a real sacrifice, and the EOG bands are calibrated against exactly that.

**And this is what closes the growth loop.** A team that pours points into conditioning
raises its `fuel` signal, and at the next five-week review, up-tempo visions score higher
for it. Vision → training → signals → vision.

---

## 7. Surface: lineups and rotation

### Starting five

Established at training camp, **persisted**, and used as the starting lineup every game.
This is new state — today the five is re-derived from eligibility at each rebuild.

> **The frontend also needs handling.** Browser bulk sims call `/api/autoset-lineup` for
> both teams on every quarter after the first, so a designated five currently survives
> only one quarter. The override has to reach that path, not just the backend selector.

### Rotation size

Driven by **depth**, not vision — with one vision override.

| Capable backups (RT ≥ pool bar) | Rotation |
|---|---|
| 0–2 | ~8 players |
| 3–4 | ~9 |
| 5–6 | ~10–11 |

Full-Court Press forces a minimum of 9 regardless — you can't press forty minutes off
seven men. That's the vision's cost showing up on a third surface.

> The `RT ≥ 50` bar is **not portable** — a pool migration moved the bench median by 5
> points and emptied the deep band entirely. Either re-derive it per pool
> (`bench median + 3`) or, better, express backup quality as a **within-team**
> comparison — how many bench players are within X of the starter they'd replace. That's
> a difference, and differences travel.

### Substitution policy

**Mechanical floor, universal:** never field a player whose *current effective rating* is
below his actual replacement's. Effective rating recomputes the position rating from
NG-rescaled attributes — not `rating × NG`, since only malleable attributes rescale and
an IQ-heavy player degrades more slowly.

**Archetype margin above the floor:** subbing exactly at crossover is myopic — it leaves
the starter at 0.67 needing a long rest. The margin is set by `starter_bench_gap`:

| Gap | Behavior |
|---|---|
| < 13 | sub early and freely, the drop-off is small |
| 13–19 | normal |
| > 19 | ride the starters, the bench is a real downgrade |

> ### ⛔ SUPERSEDED 2026-08-12 — the mechanism below was tried and REJECTED
>
> **Original proposal, struck:** *"Replace the single `NG ≥ 0.8` gate with a pull/return
> pair — pull at the margin, return higher. One threshold means a player bounces at the
> boundary; hysteresis makes a substitution buy a real rest."*
>
> **That exact mechanism was implemented, swept and stripped** before this spec was written.
> See `projects/bugs.md` § "MEASURED AND REJECTED: NG pull/return hysteresis pair" and
> `06_Gameplay_Systems/CPU_Team_Rotation_System.md` §4:
>
> | pair | record vs control | mean margin |
> |---|---|---|
> | 0.75/0.85 | 14-18 | **−1.81** |
> | 0.70/0.90 | 15-17 | **−1.66** |
> | 0.65/0.90 | 16-16 | −0.56 |
>
> It cut churn 20–33% and lengthened stints 41%, but **cost ~1 point per game and did not
> move star minutes at all**. The sweep covered pull 0.60–0.80 against return 0.80–0.95 and
> was monotonic throughout. **Do not revisit by searching for a better threshold pair.**
>
> **Why it fails, and why that does not condemn the archetype idea:** holding a tired player
> past PULL is *by construction* fielding someone worse than the best available alternative.
> The gate governs **eligibility** — it cannot express "this tired starter is still better
> than his backup," which is exactly what a large `starter_bench_gap` means.
>
> **Use the objective weight `w` instead.** `db_utils.py` already blends
> `score = w · static_rating + (1 − w) · effective_rating`, already implements the
> NG-rescaled `_player_effective_slot_rating` this section describes, and its own comment
> names this seam: *"This single weight is the intended home for archetype influence (via
> starter_bench_gap)."* It is currently a global constant
> (`LINEUP_EFFECTIVE_WEIGHT_DEFAULT = 0.25`, adopted in `c2570c5aa`) and has never been
> varied per team.
>
> `w` changes **who the selector considers better**, rather than holding anyone past a gate —
> so it can express the gap table above without paying the hysteresis cost:
>
> | `starter_bench_gap` | behaviour wanted | `w` |
> |---|---|---|
> | < 13 | sub early and freely | **low** — responsive, rotation emergent |
> | 13–19 | normal | 0.25 (today's global constant) |
> | > 19 | ride the starters | **high** — fatigue-blind, paper talent wins |
>
> **The mechanical floor above this box is NOT superseded** — it was never tested. It is a
> different rule from hysteresis, and `_player_effective_slot_rating` already computes what
> it needs.
>
> Open before building: whether `w` is plumbed per-call or read from the module constant at
> the selection site, and what a `w` sweep does to margin (0.25 was adopted after an
> evaluation whose scope is not yet established here).

### User teams

The effective-talent floor applies to the user too — automatically in sim, and as a
**warning** in turn-by-turn. Crossover is the right trigger precisely because it's rare:
it fires only when something is objectively wrong, rather than nagging.

---

## 8. Re-evaluation

Every five weeks. Switching requires something **compelling** — two inputs:

```
results     are we failing?           1-9 switches even if fit is fine
fit gap     is another vision better?  covers both roster drift and a bad initial pick
```

**The switch threshold rises with the week.** A week-5 change costs five weeks of
training; a week-20 change is nearly pointless with six weeks left. A rising bar kills
late switches without a special rule, and it captures the sunk cost directly.

That also collapses commitment and hysteresis into one thing: commitment is *how long
you've been building this*, and it raises the bar for abandoning it.

**Penalties are emergent, not designed.** Player attributes don't transfer, and the team
attributes built under the old identity decay once unused. No extra machinery needed.

---

## 9. Implementation notes

**Tunable Constants — document as one coupled block:**

- fit weights (both tables)
- frozen scale constants (means and sds)
- flat constants (Motion +0.60, Contain −0.50)
- fuel costs and capacity terciles
- softmax temperature
- slider weight vectors

All are calibrated against the pool the signals were measured from. A pool migration
should **break a regression test**, not drift the league quietly — same pattern as
`_CPU_REFERENCE_BASE` and `test_cpu_reference_training.py`.

**Dead code to remove:** the `cum_nd > 350` branch in `team_manager.py:704-726` matches
zero of 128 teams, and `endurance_d > 600` / `intelligence > 300` are nested inside it, so
all of it is unreachable. This is what the vision system replaces.

**Freeze `autoset_strategy_settings` at roster level** — today it re-derives sliders from
`cum()` over the new five after every lineup rebuild, so identity shifts four times a
game as players tire.

**Validation:** the vision assignment can't be validated distributionally — different
aggregation forms produce near-identical population splits while disagreeing about a
third of the teams. Validation is downstream: do press-identity teams actually press
effectively, and do outside-identity teams shoot better than the league?

---

## Open items

1. **Slider semantics** — confirm `offense` is motion↔set and `defense` is man↔zone,
   and which direction is which.
2. **Slider weight vectors** — §4 is my proposal, not measured. Most likely to need
   your instincts.
3. **Playbook concentration caps** — the specific values to raise them to.
4. **Backup-quality bar** — per-pool re-derivation vs the within-team reformulation.
5. **Vision persistence** — where it lives, and whether users get one too.

---

## Measured effect of the identity slice (August 2026)

### ⚠️ READ FIRST — measurements MUST pin `PYTHONHASHSEED`

`PYTHONHASHSEED` reaches simulation behaviour (see `projects/bugs.md`). Each process gets a
random hash seed, so **two runs of the SAME configuration produce different games.** Measured
run-to-run spread on a single arm, 96 team-games: FCP foul-outs/team-game **0.81 vs 1.19** —
as large as any effect being tested.

**Any arm-vs-arm comparison run in separate unpinned processes is invalid.** Run every arm
with `PYTHONHASHSEED` pinned to the same value, and repeat across at least two values so
between-world spread is visible. Verified: with `PYTHONHASHSEED=0`, two runs of the same arm
are bit-identical across every metric.

This defect voided two earlier rounds of conclusions on this project. Do not skip it.

### Identity OFF vs ON — the valid comparison

Mean of two pinned hash worlds (`PYTHONHASHSEED` 0 and 1), 96 team-games each, identical sim
seeds, team aggregates summed from player stat containers (`PTS`/`FGA`/`FTA`/`TO`/`OREB`) —
never from parsing turn `result_type` strings.

| metric | identity OFF | identity ON | Δ | |
|---|---|---|---|---|
| **points / team-game** | **67.91** | **70.92** | **+3.02** | **+4.4%** |
| possessions / team-game | 70.01 | 71.92 | +1.92 | +2.7% |
| PPP | 0.970 | 0.986 | +0.016 | +1.7% |
| FG% | 39.92 | 40.94 | +1.02pp | +2.6% |
| 3PT% | 30.59 | 30.34 | −0.26pp | −0.8% |
| fouls / team-game | 19.28 | 20.98 | +1.70 | +8.8% |
| FTA / team-game | 20.09 | 21.73 | +1.63 | +8.1% |
| turnovers / team-game | 11.07 | 11.84 | +0.77 | +6.9% |
| foul-outs / team-game | 0.59 | 0.72 | +0.13 | +22.0% |

**Identity raises scoring by ~3 points/team-game, and it is BOTH pace and efficiency** —
possessions +2.7% and PPP +1.7%, roughly evenly split. Both hash worlds agree on direction and
magnitude (+3.07 and +2.96), so this one is solid.

### Corrections to earlier numbers on this project

| claim | status |
|---|---|
| "identity raises scoring +12.2% (63.2 → 70.9)" | **overstated.** 16-game sample, and the OFF arm was miscounted by turn-string parsing. True effect **+4.4%**. |
| "identity does NOT raise scoring (69.52 → 69.11)" | **also wrong.** 96 team-games but each arm ran in its own UNPINNED process, so it compared two different hash worlds. |
| "foul-outs +42.9% with identity" | **noise.** 32 team-games, ~65 events, Poisson error ±11.6. Controlled value is **+22%**. |
| "damping FCP aggression cuts FCP foul-outs 1.308 → 0.808" | **does not survive.** Cross-world artifact; see the lever table below. |

Two methodology rules follow, both learned the expensive way:

1. **Never parse turn `result_type` strings for team aggregates.** A turnover filter matched
   `"DEAD_BALL_TURNOVER"` but not `"DEAD BALL"` — the largest turnover category — which
   inverted a pace-vs-efficiency headline. Use the player stat containers.
2. **Never compare arms across unpinned processes, and never tune against foul-out counts at
   small n.**

### What identity changes: foul concentration by vision

Identity ON, mean of both hash worlds:

| defensive vision | team-games | foul-outs / tg | fouls / tg |
|---|---|---|---|
| Multiple | 18 | 1.111 | 24.00 |
| **Full-Court Press** | 52 | **1.000** | **24.46** |
| Man Lockdown | 46 | 0.739 | 19.30 |
| Zone | 46 | 0.434 | 19.30 |
| Contain | 30 | 0.433 | 18.30 |

Press teams commit clearly the most fouls (24.46 vs 18–19 for the passive visions) and
disqualify players ~2.3× as often as Zone/Contain. Note **Multiple edges FCP on foul-outs on
only 18 team-games** — too thin to rank against it.

The league-wide foul-out rate is already 0.59/tg with identity OFF, against a real-basketball
~0.2–0.4. **That is a pre-existing calibration issue identity did not cause**, and it is the
larger number; tracked separately.

### The scoring guardrail

Identity's +3 points is a move toward realism from a cold baseline (67.9 → 70.9 against a
college norm of ~70–72), not inflation. The guardrail for any damping or self-regulation work
is therefore: **league points/team-game must not fall back toward the identity-OFF baseline of
67.9. Staying within ~1 point of 70.9 is the pass condition.**

### Lever comparison — foul trouble

Mean of both hash worlds; single-arm between-world spread in brackets.

| arm | points/tg | foul-outs/tg | FCP foul-outs/tg | FCP fouls/tg |
|---|---|---|---|---|
| identity ON (baseline) | 70.92 | 0.72 | 1.000 [0.81 / 1.19] | 24.46 |
| tighter foul limits `{1:1,2:2,3:2,4:3}` | 70.72 | 0.68 | 1.097 [0.89 / 1.31] | 25.06 |
| FCP aggression damp (3.05 → 2.50) | 71.04 | 0.73 | 0.981 [0.92 / 1.04] | 23.50 |
| **self-regulation override** | **70.37** | **0.69** | 1.096 [1.19 / 1.00] | **23.52** |

**No lever moves foul-outs detectably at this sample size.** The between-world spread on a
single arm (0.81 → 1.19) exceeds every between-arm difference. Do not read a foul-out ranking
off this table; it would need far more hash worlds to resolve.

What IS consistent across both worlds: **damping and self-regulation each cut FCP fouls
committed by ~1 per team-game (24.46 → 23.5)** while tighter limits raise them.

### Self-regulation: the behavioural result

This is the deliverable that did land, and it replicates across both worlds.

| FCP slider | identity base when in trouble | effective when in trouble | effective when clear |
|---|---|---|---|
| `aggression` | 2.86 | **2.56** | 2.86 |
| `hc_trap` | 2.69 | **2.16** | 2.91 |
| `fc_press` | 2.84 | **2.25** | 2.70 |

A press team in foul or fatigue trouble now visibly plays differently from the same team when
clear, and reverts when the trouble passes. Scoring holds (70.37 vs 70.92 baseline, inside the
0.7–1.5 between-world spread). Desperation suppression fires on ~10% of calls; the override
moves at least one slider on ~19% of all calls and ~69% of FCP rebuilds.

**Open concern:** 69% of FCP rebuilds register as in-trouble, which is more than the 51%
calibration predicted (the absolute-4 floor added cases). Worth checking whether the identity
is being damped too much of the time.
