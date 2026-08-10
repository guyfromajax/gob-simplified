## CPU Team Lineup & Rotation System ✅ **SHIPPED** (August 2026)

Describes what is IN THE CODE, not what was designed. Where a mechanism was designed,
measured and rejected, that is stated as such.

---

## ⚠️ READ FIRST — the metric defect

**A rebuild-timeline metric produced a star-minutes figure that was 40% of the game when the
true value is 69%. Anyone re-measuring rotation must not repeat it.**

The defect: minutes were reconstructed by bucketing lineup-rebuild events by
`(game_id, team_name)`, where `team_name` came from a wrapper on `build_lineup_from_mongo`
holding the value in a module-level context dict. **Not every call to the selector routes
through that wrapper**, so the context frequently held a *stale* team name — merging two
teams' rebuilds into one bucket. Consequences:

| figure | wrong (timeline) | correct (per-turn) |
|---|---|---|
| best-rated player, % of game | 40.5% | **69.0%** |
| most-used player, % of game | 88% | 70.3% |
| distinct players logging minutes | ~14 (from a **12**-man roster) | **6.69 above 8%** |

The impossible ~14-from-12 was the tell; the 40.5% went unchallenged for several rounds of
analysis and drove a false conclusion ("star minutes are immovable, the fatigue economy must
be wrong"). Two independent measurements disagreed — a probe said the star was on the floor
for 52% of *rebuilds* while the timeline said 40.5% of *minutes* — and the discrepancy was
rationalised instead of investigated.

**Correct method: measure per TURN from the live lineup.** Sample
`team.lineup` at every turn append and weight by that turn's `time_elapsed`. This needs no
team attribution at all, because you read the lineup off the TeamManager you are already
holding. See `/tmp` harness `minutes_diag.py` pattern: replace `gm.turns` with a list
subclass whose `append()` snapshots both lineups.

---

## 1. Selection — exact max-weight assignment

`solve_best_assignment(players, positions, *, required_ids, preference_fn, effective_weight)`
in `BackEnd/utils/db_utils.py`.

Seats the EXACT best five by maximum-weight assignment, solved with a **DP over position
bitmasks** — `2^len(positions)` states x pool size, microseconds at five slots and a twelve-man
pool. It replaced a greedy position-by-position fill over a randomly shuffled order.

**The DP is LAYERED** (`layers[L][mask][k]`), and this is load-bearing: a flat parent table
can reconstruct a path through a predecessor state produced by a LATER player, which
**silently seats the same player twice**. That bug occurred and was caught by a
brute-force-comparison unit check. Any rewrite must keep the layering or re-prove
duplicate-freedom.

**Two selectors share it:**

| function | used for |
|---|---|
| `build_unified_autoset_lineup_from_eligible` | full rebuild — quarter break, timeout, foul-out |
| `fill_unified_lineup_gaps` | partial fill, holding seated slots fixed (the foul-out path) |

**The Autoset endpoint inherits it automatically.** `autoset_lineup_player_ids_from_payload`
(the lineup-UI "Autoset" button) calls `build_unified_autoset_lineup_from_eligible` directly,
so it received the exact solve with no separate change.

### Constraints the solve respects

- **Eligibility and the waterfall are UPSTREAM** in `build_lineup_from_mongo` and unchanged.
  The solver optimises over the eligible pool it is handed, never the whole roster.
- **`force_include_ids` is a HARD CONSTRAINT INSIDE the optimisation** — the best five
  *containing* the locked FT shooter. The old code pre-seated him and greedily filled around,
  which is not the same thing. Tracked as a second DP dimension (`k` = required seated).
- **Blowout (`prefer_lowest_rt`) inverts SELECTION, not seating**: take the five lowest-RT
  eligible players, then seat those five optimally. Resting starters is the intent; fielding
  them in nonsense positions was not. Forced players are retained.
- **Random tie-break among equal optima**: the pool is shuffled up front and the DP improves
  on strict `>`, so equally-optimal assignments are chosen at random. Variation at zero rating
  cost — unlike the old random fill order, which bought variation by giving up rating.

### What was removed

The **team-chemistry random candidate pool** (`_team_chemistry_pool_sizes`) previously sized a
random pick for the last fill slot. Measured cost: **4.39 rating points per rebuild**, with no
measurable benefit. `team_chemistry` is still accepted by both selectors and ignored — callers
pass it positionally. The helper survives only for legacy callers.

---

## 2. The objective weight `w`

```
score = w * static_rating + (1 - w) * effective_rating
```

**`LINEUP_EFFECTIVE_WEIGHT_DEFAULT = 0.25`** (adopted August 2026).

- **static** = `position_ratings[pos]`, paper talent, fatigue-blind.
- **effective** = `_player_effective_slot_rating` — the position rating **RECOMPUTED** from
  NG-rescaled attributes. Only `MALLEABLE_ATTRS` rescale with energy, so an IQ-heavy player
  degrades more slowly than `rating * NG` would imply. That is why it recomputes rather than
  scales. Cached per player per NG value; `w = 1.0` skips the recompute entirely.

At `w = 1.0` the solver optimises paper talent and can seat a tired star over a fresh backup
who is better *right now*. Lowering `w` makes rotation **emergent**: a starter tires, his
effective rating falls below a fresh backup's, the next rebuild seats the backup, he recovers
on the bench and returns. No separate hysteresis or floor mechanism is required.

**Effective-talent gap by w** (a bench player materially better at that slot than the starter
in it; 16 games per value):

| w | any | >5 | >10 |
|---|---|---|---|
| 1.00 | 51.8% | 33.4% | 20.8% |
| 0.50 | 30.3% | 9.9% | 2.1% |
| **0.25** | **16.7%** | **2.1%** | **0.7%** |
| 0.00 | 1.0% | 0.7% | 0.5% |

0.25 removes essentially all of it while keeping a quarter of the objective on paper talent,
so a genuinely better player still wins a close call — and the parameter keeps headroom.

**`w` IS THE INTENDED ARCHETYPE HOOK, via `starter_bench_gap`.** A team with a wide
starter-bench gap should be more reluctant to go to its bench (higher `w`); a deep team can
afford pure responsiveness (lower `w`). Not wired yet.

**What `w` is NOT for.** It cannot deliver "ride your stars" — that is the eligibility gate,
not the objective. See §4.

---

## 3. `preference_fn` — the deliberate-deviation seam

`preference_fn(player, position) -> float`, added to a candidate's score. **Currently always
`None`.** The principle: **optimal is the BASELINE, and any deviation must MEAN something** —
a vision preference, resting a star in a decided game, developing a freshman. The pre-fix
behaviour deviated via `random.shuffle`, which meant nothing.

**`position_fill_order` is its first intended consumer.** The parameter is still accepted by
`build_unified_autoset_lineup_from_eligible` and is now **unused** — fill order cannot affect
an exact assignment. It is NOT dead code, and the distinction matters:

> Shot-weight ordering optimises a **genuinely different objective** — seat scorers where the
> playbook shoots most — which can CONFLICT with max-sum-of-position-ratings. A team may
> rationally field a slightly lower-rated five to get its shooters into high-attempt spots.
> That tension is exactly what `preference_fn` exists to express.

Related: `compute_team_fill_order` returns `None` in `mode="single"` (playbook_settings is
never populated) but works in franchise. Across 60 franchise teams it returns **one distinct
order** (`SF, SG, C, PF, PG`) because they share a default playbook — see the ticket in
`projects/bugs.md`.

---

## 4. NG eligibility gate — as it actually is

**A single threshold, not a pair.**

| | value |
|---|---|
| standard | `NG >= 0.80` |
| final 4:00 of Q4 and all OT | `NG >= 0.64` |
| waterfall relaxation | drop 0.20 per step to 0, then relax foul limits |

Implemented in `is_player_eligible_for_lineup` / `_waterfall_eligibility`. Fouled out
(F >= 5) is always ineligible.

**A pull/return hysteresis pair was implemented, swept, head-to-head'd and REJECTED.** It
reduced churn 20-33% and lengthened stints 41%, but cost ~1 point per game and did not move
star minutes at all. It was **stripped rather than left as inert plumbing**. Full results in
`projects/bugs.md`. Do not re-attempt by searching for a better threshold pair; the case for
revisiting is a change to the **fatigue economy**, not a better gate.

The gate — not the objective — is what governs how much a star plays, because it decides
whether he is in the eligible pool at all. The selector seats him **100% of the times he is
eligible**.

---

## 5. Measured baselines (single mode, 12-man rosters, 32 team-games)

Re-measure against these before claiming a regression.

| metric | value |
|---|---|
| assignment optimality | **100.0%** of rebuilds (was 19.1% under greedy) |
| visible failure — bench player better at that slot | **0.0%** at every threshold (was 47.1% any / 24.5% >10) |
| best-rated player, share of game | **69.0%** (median 68.8, range 52.7-86.2) = **27.6 of 40 minutes** |
| star leads his team in minutes | **72%** of team-games; top-3 in **97%** |
| most-used player, share of game | 70.3% |
| players above 8% of team minutes | **6.69** |
| effective-talent gap >10 (at w=0.25) | **0.7%** of rebuilds |
| minutes ~ rating (partial, ND held) | **+0.340** |
| minutes ~ ND (partial, rating held) | **+0.311** |
| rating ~ ND collinearity | +0.782 |

**Minutes track talent slightly more strongly than durability** once their 0.78 collinearity
is partialled out. Raw correlations (+0.686 rating, +0.677 ND) are too close to separate and
should not be quoted alone.

---

## 6. Tunable Constants

| constant | location | value | effect |
|---|---|---|---|
| `LINEUP_EFFECTIVE_WEIGHT_DEFAULT` | `db_utils.py` | **0.25** | objective blend; 1.0 = paper talent, 0.0 = pure right-now. Archetype hook via `starter_bench_gap` |
| NG standard threshold | `is_player_eligible_for_lineup` | **0.80** | eligibility floor; governs star minutes and rotation depth |
| NG late-game threshold | `is_player_eligible_for_lineup` | **0.64** | final 4:00 of Q4 and OT |
| NG waterfall step | `_waterfall_eligibility` | **0.20** | relaxation per step when <5 eligible |
| `DEFAULT_FOUL_LIMITS_BY_QUARTER` | `db_utils.py` | `{1:1, 2:2, 3:3, 4:3}` | per-quarter foul ceiling; not applied late Q4/OT |
| `_ND_DECAY_TIERS` | `models/player.py` | ~0.01-0.02 / possession | on-floor fatigue, ND-dependent |
| bench recovery | `phase_resolution.py` | 20% none / 70% +0.01 / 10% +0.02 | ~0.009 / possession |
| `_team_chemistry_pool_sizes` | `db_utils.py` | `[1,1,1,1,2]` / `[1,1,1,1,3]` | **NO LONGER USED by the selectors** — legacy callers only |
| `BLOWOUT_*` margins | `db_utils.py` | Q3 50, Q4 35/25/20 | when `prefer_lowest_rt` engages |

**The decay:recovery ratio (~1.7:1) sets rotation depth and star minutes.** It is the real
lever on both, and it is NOT in the selector. Changing it moves pace, foul trouble and the
EOG bands too.

---

## 7. Open items

- **Rotation is ~7 deep (6.69 above 8% of minutes) against a real 8-9.** Whether that is a
  defect or a design choice is unsettled; it follows from the fatigue economy, not the selector.
- **Everything here was measured in `mode="single"` with 12-man rosters, CPU vs CPU.**
  Franchise dresses 12 from a 15-man roster and may distribute minutes differently. Metrics
  1-5 are properties of the algorithm and should hold; the minutes distribution should be
  re-measured in franchise before being treated as league-wide.
- **`position_fill_order` is inert** pending the `preference_fn` work, and its franchise
  values are identical across teams.
- **Fatigue economy unexamined.** The case for opening it rested on the void 40.5% figure.
  With the corrected 27.6-of-40, the argument is much weaker.
