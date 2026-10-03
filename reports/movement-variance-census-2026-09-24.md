# Defender movement variance and the AG curve — census

**Defender speed already matters, and more than expected: 31.8% of off-ball defender
placements end SHORT of their target today**, because the defender's own rate cannot cover
the distance inside the step's duration. This is not a structural gap — the mechanism exists,
is wired to AG, and fires on roughly one placement in three.

**But the variance it produces is tiny, because the AG curve is nearly flat.** Across the real
league a 90th-percentile defender is **1.103×** the speed of a 10th-percentile one; across the
whole 0–100 range the spread is only 1.222×. The archetype a step assigns (drift 8 → burst 32,
a 4× range) matters about forty times more than which player is running.

**LATE is a small build mechanically and a large one in consequence.** The endpoint primitive
already exists (`_interrupted_coord`), the shortfall already carries automatically because each
step starts from the previous step's end coords, and the cost is negligible. The risk is that
it stacks on a mechanism that is already biting: the median defender has only **0.25 game-
seconds of slack**, so almost any lag lands immediately.

Reference used: **`equiv_v3_reference_1f4af0ede_loosesag_nogate.json`**, re-confirmed
**160/160** on fingerprint AND draws at the merged tree (`c33e4879b`; develop was 1 commit
ahead and merged first, zero files changed). Every probe below is read-only and verified
RNG-neutral against that reference. Nothing built, no flag, no constant changed.

---

## 1. Go / no-go: does off-ball defender speed matter today?

### Are defenders ever in the gate set?

Yes, on **3.6%** of steps. n=205,853 steps (n=40 seeds × both arms, SD=1):

| who sets step T | steps | share |
|---|---|---|
| offense | 161,704 | **78.6%** |
| nobody (fixed duration / ball-gated) | 36,494 | 17.7% |
| **defense** | **7,333** | **3.6%** |
| unresolved id | 322 | 0.2% |

By `advance_trigger.condition`: `player_reaches_position` 74.6%, `ball_reaches_player` 17.1%,
`fixed_duration` 7.3%, `offense_players_reach_position` 1.0%. A defender becomes the gate when
`gate_player_ids` is unset — then `build_walk_up_step` gates on the slowest of *everyone*
([transition_bridge.py:325-327](BackEnd/utils/transition_bridge.py#L325-L327)) — and the
slowest happens to be a defender.

### For non-gate defenders, is the end coord simply the target?

**No.** [transition_bridge.py:341-344](BackEnd/utils/transition_bridge.py#L341-L344):

```python
if player_rate > 0 and pid in natural_t and natural_t[pid] > t:
    final_end_coords[pid] = _interrupted_coord(sc, target, player_rate, t)
else:
    final_end_coords[pid] = dict(target)
```

Measured over **629,126 defender placements**:

| | defence | offence |
|---|---|---|
| ends **exactly** on target | 429,183 — **68.2%** | 349,463 — 70.6% |
| ends **short** | 200,139 — **31.8%** | 145,712 — 29.4% |
| `natural_t > T` (rate-limited) | 200,139 — **31.8%** | not measured |

For defenders the two lines are the *same* population to within 0 placements: the shortfall
**is** the rate limit. (The offence "short" column is a different phenomenon — some builders
use `destination` as a multi-step target rather than this step's endpoint — and I did not
compute `natural_t` for offensive players, so that row is blank rather than zero.)

So a 90-AG and a 40-AG defender do **not** both arrive on time. The 40-AG defender falls short
on about a third of his placements. What is missing is not the mechanism; it is spread.

### What does the FE actually do between start and end?

**Per-player linear tweens over backend-stamped per-player durations — not one lerp over T.**

[animation_step_helpers.py:1193-1226](BackEnd/utils/animation_step_helpers.py#L1193-L1226)
stamps `tween_durations[pid] = min(distance / rate, step_t)`, with `rate` from
`_ag_grid_per_game_sec`. [animationPlayback.js:1237-1244](FrontEnd/static/js/phaser/animation/animationPlayback.js#L1237-L1244)
consumes it verbatim — *"Spawn one linear tween per player… Players who finish before step T
sit idle at their end coord until the wall-clock timer below fires — produces the natural
'settle and wait' feel rather than stretching every player's tween across the gating player's
duration."* The tween itself is
[startSchemaPlayerTween](FrontEnd/static/js/phaser/animation/animationPlayback.js#L984-L1010),
a Phaser tween to the end pixel over that duration.

**The `min(..., step_t)` cap is the important detail.** It clips the *slow* direction: a
defender who would need longer than T has his tween compressed to exactly T. **32.2% of
defender tweens are capped this way.** So on screen, being slow does not look like moving
slowly — it looks like *stopping short*. Only the fast direction is visible as speed, as an
early arrival followed by an idle.

### Answer

**Off-ball defender AG affects placement today, materially — on 31.8% of placements it decides
where the defender ends up, and on 100% of placements it decides how long his tween runs.**
Complaint #2 is therefore a **magnitude** problem, not a structural one. That reframes the
build: LATE is not adding a missing mechanism, it is widening one that already exists and
already bites.

## 2. The AG curve as it actually is

[shared.py:723-745](BackEnd/utils/shared.py#L723-L745):

```python
rate = STANDARD_GRID_PER_GAME_SEC * (0.90 + (ag / 100.0) * 0.2)   # clamped [0.5, 60]
```

| AG | 0 | 20 | 40 | 50 | 60 | 80 | 100 |
|---|---|---|---|---|---|---|---|
| grid/game-sec | 12.60 | 13.16 | 13.72 | **14.00** | 14.28 | 14.84 | 15.40 |

**Full-range ratio AG100 / AG0 = 1.2222.** Over the range actually present:

| population | n | p10 | p50 | p90 | max | rate p10 → p90 | **p90/p10 ratio** |
|---|---|---|---|---|---|---|---|
| **real league** (`gob-staging`, players with an AG) | 1,536 | 24 | 39 | 73 | 144 | 13.27 → 14.64 | **1.1034** |
| equiv-v3 fixture roster | 48 | 12 | 42 | 80 | 98 | 12.94 → 14.84 | 1.1472 |

Real-league p99/p1 is 1.1884; min→max (AG 10 → 144, the latter above the nominal 100 the
docstring allows for) is 1.2913. **The ratio is near 1.0: a typical fast defender is ~10%
quicker than a typical slow one.** Measured in-game defender rate across 629,126 placements:
mean 13.72, p50 13.40, p90 15.00 — a band 1.6 grid/game-sec wide.

**The archetype dwarfs the player.** `_ag_grid_per_game_sec` multiplies the AG scale by an
archetype base: drift 8, cruise 13, shot_motion 14, standard 14, sprint 18, **burst 32**. That
is a 4× range against AG's 1.1×, so which archetype a step assigns is worth roughly forty times
more than who is running.

**Call sites** (`_ag_grid_per_game_sec`), all of which a steeper curve would move:
`transition_bridge` (both `natural_t` — which feeds the gate — and `_offense_arrival_times`),
`animation_step_helpers.stamp_tween_durations`, `reset_step_helper`,
`after_steal_fast_break_step_emitter`, `dynamic_hct`, `final_turn_pacing`, `ft_step_emitter`,
`quick_foul`, `skeleton_step_emitter`. **Steepening is not isolated:** `natural_t` feeds step T,
so a steeper curve changes *how long steps take*, not just who falls behind. That is a bigger
blast radius than a lag applied after T is fixed. Reported, not changed.

## 3. Variance that exists today

n=40 seeds 8000-8039, both arms, SD=1. 205,853 steps, 629,126 defender placements
(**3.06 defenders per step**), 0 census errors.

| distribution | mean | p50 | p90 |
|---|---|---|---|
| defender distance per step | 9.75 | 7.00 | 19.00 |
| offence distance per step | 13.96 | 10.00 | 33.50 |
| **spread across the defenders within one step** | **7.73** | **5.50** | **16.00** |
| step T (game-seconds) | 1.12 | 0.75 | 2.50 |
| defender rate (grid/game-sec) | 13.72 | 13.40 | 15.00 |
| **slack: T − natural_t** | **0.12** | **0.25** | 1.75 |

**Step duration is short.** 11.2% of steps have T ≤ 0.25 s, **42.6% ≤ 0.5 s**, 66.9% ≤ 1.0 s.
Combined with a median slack of 0.25 game-seconds, **a lag of a quarter-second would leave the
median defender short on the median step.** That is the single most important number here for
sizing LATE: there is very little headroom to spend.

By scheme and posture — essentially identical, so the machinery is scheme-blind:

| cell | placements | ends short | `natural_t > T` | mean defender AG |
|---|---|---|---|---|
| zone | 319,671 | 32.0% | 32.0% | 45.2 |
| man | 309,455 | 31.5% | 31.6% | 44.9 |
| posture loose (separate run) | 628,900 | 32.2% | 32.2% | — |

Posture `loose` matches base man on every movement metric (T p50 0.75, slack p50 0.25, gate
offence 78.4% / defence 3.6%). **Posture changes where defenders are sent, not how they move.**

## 4. The 11-unit cliff — how lumpy would lateness be?

**There are two thresholds, not one**, and the brief's framing conflates them:

| band | what happens |
|---|---|
| ≤ 3.0 (`PROXIMITY_CONTEST_NEAR_DIST`) | factor **1.0**, full contest |
| 3.0 → 9.0 (`PROXIMITY_CONTEST_OPEN_DIST`) | linear ramp 1.0 → 0.15 |
| 9.0 → 11 | **flat at the floor, 0.15** (`PROXIMITY_CONTEST_OPEN_FLOOR`) |
| > 11 (`CONTEST_EUCLIDEAN_RADIUS`) | `has_contest = False` — contributes nothing |

**So the cliff at 11 is 0.15 → 0, not 1.0 → 0.** It is a small step off a low ledge, not a
coin-flip. [shot_manager.py:236-252](BackEnd/models/shot_manager.py#L236-L252),
[:1146-1149](BackEnd/models/shot_manager.py#L1146-L1149).

Distribution of primary-defender → shot-spot distance:

| view | ≤3 | 3–9 | 9–10 | 10–11 | 11–12 | >12 |
|---|---|---|---|---|---|---|
| **graded shots only** (n=7,460) | 50.0% | 46.2% | 1.3% | 1.6% | — | — |
| **every resolution call** (n=27,564) | 23.8% | 32.9% | 3.4% | 3.7% | 4.0% | 31.9% |

- Of shots that actually receive a graded contest, only **2.4% sit within 1 unit inside the 11
  gate**, and the contest mass sitting in the whole 9–11 floor band is **0.5%**.
- Counting every resolution call, including defenders already beyond the gate, **9.62% fall
  within ±1 unit of 11** and 35.9% are beyond it entirely.

(The two rows have different denominators: `_proximity_contest_factor` is only reached when the
defender is already inside 11, so it cannot see the outside population; the second row hooks
`_shot_defender_xy`, which is called on every resolution — roughly 345/game against ~104 FGA,
so it counts repeat evaluations of the same shot. Neither is a clean per-shot rate and I have
not treated either as one.)

**Verdict: a small lag degrades smoothly, it does not coin-flip.** Half of graded shots have
the defender inside 3 units where the factor is pinned at 1.0 and small movement does nothing;
the 9–11 band where the cliff lives is flat at 0.15 and holds 2.9% of graded shots.

**The drive corridor** (`HCO_CUTOFF_PATH_CORRIDOR` 11.0) and the drive-end guardian count, same
footing:

| | |
|---|---|
| tier-A blow-bys reaching the cutoff resolver | 12.2 / game |
| demoted by a help cutoff | 8.9 / game (73.5%) |
| drive end with **0** defenders within 11 | **2.06%** |
| drive end with **1** defender within 11 | 11.10% |
| drive end with **2+** defenders within 11 | **86.84%** |

The drive end is almost always crowded, so a lag that pushes one defender out of 11 changes the
guardian count from 2+ to 1 far more often than it creates an unguarded rim.

## 5. CPU baseline

Sim arm, n=40 seeds 8000-8039, SD=1. CI = 1.96 × SEM.

| | ms / game | calls / game | µs / call | % of sim wall |
|---|---|---|---|---|
| `get_defender_coords` | 140.4 ±3.4 | 31,576 ±806 | 4.45 | 2.73% |
| `assign_zone_defender_coords` | 370.3 ±18.7 | 19,500 ±854 | 18.99 | 7.19% |
| **placement total** (the two above) | **510.7 ±19.4** | — | — | **10.27% ±0.68** |
| `stamp_tween_durations` | 117.7 ±1.8 | 2,588 ±20 | 45.48 | 2.28% |
| `_apply_defender_posture` *(nested inside `get_defender_coords`; not added)* | 22.5 ±2.0 | 6,240 ±247 | 3.60 | 0.44% |

Instrumented sim wall 5.15 s ±0.32 per game. **The timing wrappers cost +0.09 s ±0.04 paired
(1.7%)**, so every figure above is an upper bound. This replaces the "+11% CPU" figure that was
n=8 noise; it is the number a later build should be compared against.

**Pricing a per-step-per-defender computation:** **2,573 steps/game**, **7,864 defender
placements/game**, **3.06 defenders/step**. A cheap arithmetic op at ~1 µs per defender per step
costs ≈ **7.9 ms/game ≈ 0.15% of sim wall** — negligible against the 510 ms already spent on
placement. Cost is not a reason to avoid this build.

## 6. Pricing LATE — described, not written

**Where the lag goes, and the ordering constraint.** In
[`build_walk_up_step`](BackEnd/utils/transition_bridge.py#L226), inside the `final_end_coords`
loop at [:335-344](BackEnd/utils/transition_bridge.py#L335-L344). The constraint is exact and
satisfiable in one place: `natural_t` is built at :271-286, the gate selects `slowest_t` from it
at :296-327, and `t` is frozen at :328 — *all before* the :335 loop runs. **A lag applied inside
that loop cannot reach `natural_t` and therefore cannot stretch T.** The trap the brief names —
the offence waiting for the slow defender — is avoided by construction, provided the lag is
never added to `natural_t` and never consulted by `_offense_arrival_times`.

**The endpoint.** `endpoint = start + rate × max(0, T − lag)`, clamped at the target with no
overshoot, is exactly what
[`_interrupted_coord(start, target, rate, t)`](BackEnd/utils/transition_bridge.py#L111-L124)
already computes — it takes `max_traversal = rate * t` and returns the target when
`dist <= max_traversal`. The change is to pass `max(0.0, t - lag)` in place of `t`, for
defenders, and to take that branch unconditionally rather than only when `natural_t > t`.
Computable exactly where proposed; no new geometry.

**How the shortfall carries — it already does.** The emitter chains steps by
`start_coords = last_end["coords"]`
([skeleton_step_emitter.py:1127-1128](BackEnd/engine/skeleton_step_emitter.py#L1127-L1128),
[:1338-1339](BackEnd/engine/skeleton_step_emitter.py#L1338-L1339)). The next step therefore
starts from where the defender actually ended, not from where he was supposed to be, so a
defender left behind is genuinely behind until he catches up. **No new state is needed**, and
this sits correctly with the placement freeze: the one authoritative row per step is the *end*
row, which already carries the shortfall.

**Per-turn profile.** Possible with the current plumbing. Posture is already resolved once per
turn into `game_state["_hco_defense_posture"]`
([phase_resolution.py:5070-5091](BackEnd/engine/phase_resolution.py#L5070-L5091)); a per-player
lag profile keyed by `player_id` can live beside it, resolved in the same per-turn roll and read
per step as a dict lookup. Attributes do not change within a turn, so this is correct as well as
cheap — ~7,864 dict lookups per game, well under the 0.15% ceiling priced above.

**RNG.** If the lag is deterministic from attributes, **zero draws**. If it is jittered, the
honest shape is **one draw per defender per turn — 5 per turn — taken when the profile is
resolved**, not per step. Drawn there it is clairvoyance-safe by construction (the profile
exists before the step and its outcome do) and freeze-compatible (the frozen row is computed
downstream). Per-step draws would be the wrong choice: they would multiply draw count by ~2,573
steps and put an RNG read inside the placement path the freeze exists to make single-valued.

**Flag and kill switch.** `GOB_DEFENDER_LATE`, default `"0"`; with it off the lag is 0.0 and
`_interrupted_coord(..., t)` is called exactly as today, so the rollback is byte-identical.
**A reference re-cut would be needed — yes, certainly.** This fires in every scheme at every
posture and on every step, so every seed will move in all four cells.

**Is it small or large?** **Mechanically small; consequentially large.** The primitive exists,
the carry is free, the ordering constraint is satisfied by placing the change in one loop, the
RNG shape is clean, and the CPU cost is ~0.15%. I would expect the diff to be tens of lines. But
it lands on a mechanism that **already** leaves defenders short 31.8% of the time with a median
slack of 0.25 game-seconds — so even a small lag will bite immediately and often, and 42.6% of
steps are under half a second. The work is not writing it; the work is choosing the lag scale
and measuring what it does to the shot contest and the drive, both of which sit close enough to
their thresholds to move. Budget for the tuning pass, not the patch.

---

## Tunable Constants

Reported, not changed.

| constant | value | effect | what the census says |
|---|---|---|---|
| `ag_to_grid_per_game_sec` slope | `0.90 + AG/100 × 0.2` | the whole AG curve | near-flat: 1.103× across the real league's p10→p90 |
| `STANDARD_GRID_PER_GAME_SEC` | 14 | curve anchor at AG=50 | every archetype scales off it |
| archetype bases | drift 8 / cruise 13 / shot_motion 14 / standard 14 / sprint 18 / burst 32 | per-step speed class | 4× range — dominates AG by ~40× |
| `CONTEST_EUCLIDEAN_RADIUS` | 11 | hard in/out gate on the shot contest | 2.4% of graded shots sit within 1 unit inside it |
| `PROXIMITY_CONTEST_NEAR_DIST` / `_OPEN_DIST` / `_OPEN_FLOOR` | 3.0 / 9.0 / 0.15 | grades the contest | the cliff at 11 is 0.15 → 0, not 1.0 → 0 |
| `HCO_CUTOFF_PATH_CORRIDOR` | 11.0 | drive help corridor | drive end has 2+ guardians 86.8% of the time |
| step `min_t_game_sec` floor | per-builder | lower bound on T | 11.2% of steps land at T ≤ 0.25 s |

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed−8000)`, n=40 seeds 8000-8039, **both arms**, **`SEED_DEFENSES=1`** (catalogue
seeded with the six real defenses), CI = 1.96 × SEM. sim arm = `_is_full_simulation` True
throughout; played arm = False only inside the four gated Animator methods at Pattern A. Posture
runs use `EQUIV_MAN_POSTURE` (the playbook path). All shipped flags at their current defaults
(`GOB_MAN_LOOSE_SAG_AXIS`, `GOB_HCO_CUTOFF_NO_GATE`, `GOB_BOXOUT_CONTEST`, `GOB_MAN_HELP_SHADE`,
`GOB_ZONE_HELP_SHADE`, `GOB_ZONE_SINK_ESCAPE`, `GOB_PLACEMENT_FREEZE` all ON).

Every probe wraps its target, calls the original **first**, and reads only arguments and return
values. Proved, not asserted: the census run reproduces the reference fingerprint **and** draw
count exactly (`b8c4ce02536e2a6d` / 74,529 at seed 8000), and the full 160-cell reproduction
passed before any probe was installed. The league AG figures are a read-only `find` against
`gob-staging` with a projection — no writes.

400 games: 160 reference re-confirmation + 160 census (base man and loose, both arms) + 80
CPU/shot-tail pass. **0 errors.**

**Nothing built. No flag. No constant changed.**
