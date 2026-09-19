# Rebound from arrival — Stage 1: built, measured, stopped

**Two results run against what the brief expected, and both matter more than the ones that went to plan.**

**1. The winner-is-nearest rate FELL, it did not rise.** Sim **31.7% → 23.9%**, played **32.9% → 23.8%** (`SEED_DEFENSES=1`, n=40, ~2,600 selections per cell). The brief predicted a substantial rise and flagged ~100% as the failure mode. Neither happened, and the reason is the second result.

**2. The AG test moves in the right direction but barely, because almost every crasher arrives.** Mean AG of the winner rises **34.85 → 36.71** on sim (+1.86) and 35.83 → 35.98 on played (+0.15); the winner held the highest AG in the field on **12.1% → 15.6%** (sim) and 12.0% → 14.7% (played). Directionally right, small. The cause is measurable and is the headline finding of this pass:

| AG band | mean share of the way covered | **fully arrived** | n |
|---|---|---|---|
| AG < 40 | 95.0% | **85.8%** | 8,270 |
| AG 40–60 | 94.3% | **81.1%** | 3,746 |
| AG > 60 | 95.1% | **82.2%** | 5,716 |

**The three bands are indistinguishable, and 82–87% of crashers reach their destination outright.** The post-shot window is ~1.6 s and the standard rate is ~14 grid units per game-second, so a crasher has ~22 units of reach — while crash destinations sit only ~5–15 units from where he already stood. Nearly everyone gets there, so AG has almost nothing to bite on, and arrival compresses the whole field into a narrow distance band near the bounce. That is also why winner-is-nearest fell: **when everybody arrives, the distance term discriminates less than it did from shot-moment positions, so the dice and the composite matter more, not less.**

**The reorder itself works exactly as designed** — the mechanism is sound, the plumbing is correct, and crash destinations are no longer cosmetic (OREB share moves +3.06 on sim against +0.00 when Model A landed). **The lever that is missing is not the model; it is the time budget.** Making AG matter means a shorter window, longer crash distances, or a rate that separates the bands — a tuning question, and one for Jamie's single tuning pass, not for me.

## Footing (rule 6e)

- **Branch `feature/animation-reward`.** develop merged (`ddb7acf74`), which includes `c689db170`. Build at `2ce07a75a`.
- **Post-merge worker check, as the brief required, done before anything was measured:** the ws1/mongo-adapter migration is engine-neutral — the worker runs clean and reproduces `equiv_v3_reference_bf7ed1181_crashmodela.json` **8/8 on all four cells**.
- equiv-v3 worker, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- **Flag-off integrity: 40/40 identical to the reference on all four cells**, 0 probe errors across 320 measured + 12 gate games.

**Two process notes, both reported rather than buried.**

- A stale zero-byte `index.lock` (≈10 h old, no git process running) in this worktree's git dir blocked the merge. I removed it. It is recreated by git on the next operation.
- **My first measurement run was invalid and was discarded.** `shot_manager` imports `select_rebounder_by_score` at module level, so patching `shared` never reached the wired call sites — every "selection" the probe saw was the unwired putback path. Caught because all 257 traced calls reported `arrival_coords=None` with the flag on. Probe fixed to patch both references, run discarded and repeated. Separately, an earlier probe cut called `calculate_rebound_score` to snapshot the composite — **that consumes Jamie's `randint(1,6)` dice** and perturbed the run; caught by the flag-off reference check, and replaced with a pure recomputation of the composite from attributes.

## What was built

`GOB_REBOUND_FROM_ARRIVAL`, **default OFF**.

- **`BackEnd/utils/rebound_arrival.py`** — travel along the line toward the destination at `_ag_grid_per_game_sec(player, "standard")`, capped by the post-shot window. `arrival_point`, `arrival_coords`, `travel_fraction`.
- **`select_rebounder_by_score(..., arrival_coords=...)`** — an override threaded into `_rebound_entries`, used for the distance term only. **It is not a mutation:** `player.coords` is untouched, so nothing else in the turn sees a moved player.
- **`ShotManager._prepare_crash_arrival`** — authors both pools' destinations before selection, in the same order the later authoring loops walk, cached by player id so those loops reuse them rather than drawing again.

**The clairvoyance guard is deliberately not extended, and the reason is written into both modules.** `crash_destination` may not see the bounce because that would change *where* a player aims. Arrival may use the outcome-dependent window because a ball that rattles really does give crashers longer — it moves them further along a line already chosen. Selection may read the bounce because it *is* the resolution of the rebound. `crash_destination.py`'s allowlisted signature and its two poisoned tests are untouched.

### `uses_shot_arc`: derived at the new point, not moved — and why

`uses_shot_arc` is set from `select_and_stamp_shot_micro` at `:2742`, after selection. **Moving it earlier means moving that call earlier, which would re-phase shot micro-movement as well** — a far larger change than this pass. So the window is derived at the new point from what is known there (result type, bounce, any variant already stamped) with `uses_shot_arc` absent. Observed windows are ~0.98–1.62 s. **This is an approximation and is recorded as one in the code**, not assumed away; quantifying its error against the true post-selection window is left open below.

### The exclusion order

`canonicalize_post_shot_overlays` is unaffected **by construction**: the authoring loops still populate `offense_rebounder_coords` / `defense_rebounder_coords` with identical membership logic — the only change is that the values come from the cache instead of a fresh draw. The shooter, get-back and release exclusions run exactly where they did.

### The three proximity filters — what each reads, and what I chose

| filter | reads today | after this pass | why |
|---|---|---|---|
| `FAST_BREAK_REBOUND_GEO_DISTANCE` via `max_distance_from_bounce` | `entry["distance"]` inside `select_rebounder_by_score` | **follows arrival automatically** | it filters on the same distance the scoring uses, so it stays consistent with selection for free. This is the consistent answer the brief asked for |
| `NEAR_BOUNCE_REBOUND_ATTEMPTOR_DISTANCE` (`shared.py:1399` → `:1905`) | live `player.coords` | **left alone** | this is the putback / second-rebound path, which runs *after* the crash coords have been applied — so it already reads post-crash positions. It is not a shot-moment reader |
| `_filter_lineup_by_max_x_delta_from_bounce` (FT rebounds) | live `player.coords` | **left alone** | free throws have no crash, so arrival is undefined there |

## The trace

**`reports/rebound-arrival-trace-2026-09-19.md`** — fifteen real misses, each with every candidate's shot-moment position (lower-case), destination and arrival (upper-case), the bounce, both winners, and the score breakdown. Both winners are computed on the **same** miss: the counterfactual runs with the sim RNG state saved and restored, so the dice are identical in both columns and **any change of winner comes from position alone**. Away-attacking shots are mirrored into the home frame.

Across the 4 traced games, **the winner differs from the legacy rule on 142 of 190 wired selections (75%)**.

## Measurements

**Draws, crash calls, continuity guard** (`SEED_DEFENSES=1`):

| arm | | draws/game | authored destinations/game | randint per authored | **§8.1 corrections** |
|---|---|---|---|---|---|
| sim | before | 69,230 | 728.5 | 2.000 | **0** |
| sim | after | 69,274 | 721.1 | 2.000 | **0** |
| played | before | 81,805 | 701.9 | 2.000 | **0** |
| played | after | 81,705 | 702.9 | 2.000 | **0** |

**Draws are essentially unchanged** (+44 sim, −100 played) even though the stream re-phases — selection's draws now follow the crash draws instead of preceding them, but neither side's count changed. Crash authoring stays at exactly **2.000 randint calls per destination**. **The §8.1 guard stays at zero in every cell.**

**Outcomes, `SEED_DEFENSES=1`:**

| metric | sim before | sim after | Δ | played before | played after | Δ |
|---|---|---|---|---|---|---|
| **pts/team** | 70.29 ±3.24 | 74.66 ±3.62 | **+4.38** | 70.28 ±3.37 | 74.21 ±2.89 | **+3.94** |
| OREB | 17.27 ±1.20 | 18.77 ±1.53 | +1.50 | 17.27 ±1.34 | 20.57 ±1.57 | **+3.30** |
| **OREB share** | 26.35% ±1.60 | **29.41% ±1.78** | **+3.06** | 26.06% ±1.67 | **31.56% ±1.89** | **+5.50** |
| second-chance pts | 7.67 ±1.16 | 7.28 ±1.18 | −0.40 | 5.65 ±0.75 | 9.28 ±1.40 | **+3.62** |
| over-the-back in play | 62.60 ±2.24 | 59.52 ±2.84 | −3.08 | 62.52 ±2.19 | 60.98 ±2.74 | −1.55 |
| over-the-back fouls | 1.62 ±0.35 | 1.82 ±0.43 | +0.20 | 2.08 ±0.37 | 2.45 ±0.50 | +0.38 |
| FG% | 44.08 ±1.94 | 46.00 ±2.00 | +1.93 | 42.72 ±2.25 | 44.81 ±1.93 | +2.09 |
| **possessions** | 44.15 ±1.83 | **41.05 ±2.06** | **−3.10** | 44.55 ±1.74 | **39.83 ±1.91** | **−4.72** |
| **arm gap** | **+0.01 ±3.67** | **+0.45 ±4.04** | | | | |

`SEED_DEFENSES=0` moves the same way: OREB share +4.39 (sim) / +7.29 (played), possessions −1.05 / −4.10, pts/team roughly flat.

**OREB share is up substantially and the move is resolved** — outside the CI on both arms and both footings. That is the intended direction (crash position now decides rebounds) but the **magnitude is large**, and it comes with possessions down ~3–5 a game. Both are tuning surface, and per the brief nothing was retuned.

**Gates:** independence **PASS** on both arms and both footings; FT-honour windowed 99.7–99.8%; **0 errors**. Byte-equality does not hold (0/40 on all four cells) — expected, the stream re-phases by design.

## Stop

Stage 1 ends here. **The flag was not flipped and no reference was re-cut.** Jamie reads the trace first.

The question I would want answered alongside the trace: **is "almost everyone arrives" the right physical picture?** If a crasher should sometimes be visibly beaten to the spot, the window or the distances need to change, and that decision shapes whether this model delivers Jamie's stated goal. As it stands the reorder makes *position* matter — the 75% winner-change rate and the +3.06 OREB share prove that — but it does not yet make **AG** matter.

## Not covered

- `select_rebounder_by_score`'s composite, the team bonus, the 0.8 discounts, `REBOUND_DISTANCE_SCALE` and the `randint(1, 6)`: untouched. ST's role in positioning is a later pass.
- `crash_destination.py`, tightness 0.7, the zone work, the foul system, the crash-apply flags, `animator.py:1213`, R1, R2: untouched. **No balance number changed.**
- Branches 1 (MAKE) and 2 (shooting foul) are untouched beyond sharing `_crash_coords`; they select no rebounder. Branch 3 never fires.
- **Not quantified:** the error in the derived window from omitting `uses_shot_arc`. It affects how far a crasher gets, never where he aimed, but it is unmeasured.
- **Not explained:** why OREB share rises as much as it does. The mechanism is presumably that the offensive crash pool arrives in numbers near the bounce while release and get-back players are excluded from the defensive pool, but I did not verify the pool-size asymmetry.
- **Not measured:** the FB-miss branch separately from HCO. Both were wired and both are in the aggregate.
