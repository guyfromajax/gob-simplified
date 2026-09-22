# Sim HCO coord staleness: scope and fix

Written for: Jamie and the sessions tuning against sim results. Fix committed as `4f856721a` on `feature/animation-reward`. This report is untracked.

**Short answer.** The sim arm now writes all ten players' coords from the placement build it already runs, at the two points where played writes them. Staleness at the shot, measured against that placement, goes from 26 (defense) / 34 (offense) grid units to **0.00**. Played's residual against the same placement is 1.31, which is interruption. Played is byte-identical 40/40. The cost is about 20 ms per game (0.4%), and the paired wall-clock change is not resolvable from noise.

## Footing (rule 6e)

Unless a line says otherwise:
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, game id `0xE0000+(seed-8000)`, `ALIGN_RNG=0`.
- **Played arm:** `ARM=played`, `_is_full_simulation` False only inside the four gated Animator methods.
- **Sim arm:** `ARM=sim`, `_is_full_simulation` True.
- **SEED_DEFENSES** is stated on every table.
- **Samples:** Part 1 probes use seeds 8000–8015 (n=16) at `5d44194c1`. Verification uses seeds 8000–8039 (n=40) on the fix tree.
- **Probe integrity:** every probe's game rows match the `d9a4f1517` reference (64/64 in each Part 1 probe, 160/160 in the S6 probe).
- **Probes** live in the session scratchpad (`st/stale_probe.py`, `st/emu_probe.py`, `fix/s6_probe.py`) and are not committed.

---

## Part 1: Scope

### S1: Coverage

**`compute_defender_grid` runs on every HCO turn on both arms:** sim 2,018/2,018 HCO turns, played 1,862/1,862 (`SEED_DEFENSES=1`). Poison: one extra call per HCO turn adds exactly the HCO-turn count on every seed. Sim 538/542/513/525 vs 397/410/389/393 unpoisoned, a difference of 141/132/124/132 = HCO turns. Played likewise (126/115/118/114).

Call sites that fire (per game):

| site | `SEED_DEFENSES=1` played / sim | `SEED_DEFENSES=0` played / sim |
|---|---|---|
| `phase_resolution.py:6353` `_stamp_contest_defender_grid`, reached from the pre-walk stamp `:7161`, walk-time `:7892` and coverage pass `:6405` | 258.9 / 282.1 | 279.2 / 299.6 |
| `phase_resolution.py:5758` subtle-beat two-step mini build | 99.4 / 106.2 | 98.7 / 98.6 |
| `phase_resolution.py:4859` freeze fallback (missing shot-step stamp) | 2.2 / 2.1 | 0 / 0 |
| `step_state.py:97` | **0 / 0**: runs only when `_is_full_simulation` is never set (`played_full`); unreachable on these arms | 0 / 0 |

The write points, though, don't always have a build of *their own* skeleton:
- **Shot path (`:9409`):** a build identical in every placement input exists on 79.6 of 96.1 per game on sim (82.8%, `SEED_DEFENSES=1`) and 93.2% on `SEED_DEFENSES=0`. The rest differ only in `_defender_reads` / `_attack_drive` written after the last build.
- **Stopper path (`:9019`):** 0%. `apply_stopper_system_to_skeleton` truncates and appends a stopper step after every build.

So the fix reads the **placement stamp on the skeleton itself**, which survives truncation and deepcopies. It takes the last step with a complete defense + offense stamp. Coverage at the write points (sim, n=16):

| | shot path: stamp step used | stopper path: stamp step used | no candidate |
|---|---|---|---|
| `SEED_DEFENSES=1` | final step 94.0, 1 back 1.8, 2 back 0.2 | 1 back 13.1, 2 back 3.4, 3 back 0.7, 4 back 0.2 | **0** |
| `SEED_DEFENSES=0` | final step 101.7 | 1 back 11.1, 2 back 4.2, 3 back 0.4, 4 back 0.9 | **0** |

Stopper turns have no build of the stopper step itself; the other source is the stop step's stamp from the same build family, no new computation.

### S2: What the build contains

**The offense rows are in the build: 5.00 offense and 5.00 defense rows per build** (all 360.6 / 390.4 builds per game). `defender_grid_from_animations` drops the offense.

It also **cannot be reused for offense.** An offensive player's `movement` gains an entry only on steps where he has a `pos_action` (`defender_placement.py` offense loop), so `movement[i]` is not step `i`. Each entry carries its step's `timestamp`, so the fix maps step `i` to the player's last entry at or before that timestamp. That is the new `offense_grid_from_animations`. Indexing by position left offense incomplete at the final step and pushed the candidate 1–4 steps back on most shot turns; the timestamp carry-forward fixed that.

### S3: Which build

- **Sim's contest reads that same stamp.** On sim, `_freeze_hco_shot_attempt_geometry` fills the shot geometry from `_step_state["defense"]` at the shot step. Where a build matched the final skeleton, its defender row-ends equal that stamp **6,200/6,200** (max diff 0.00, sim, `SEED_DEFENSES=1`).
- **So the coords and the contest come from one computation.** The fix writes from the stamp itself, so sim's coords and sim's contest are identical by construction.
- **No third draw.** Offense extraction and the write are pure. Grid extractions per game are unchanged with the flag on or off (284 vs 286, `SEED_DEFENSES=1`), so no build was added.
- **Sim draws do still change** once coords move, because consumers downstream branch on them (see S6).

### S4: Intended vs actual

Emulated before writing code: probe-side stamping plus the same step search. The table gives the distance from the positions the fix would write to the coords played's consumers read (the residual sim would carry against played), and to sim's coords today (the staleness removed). Grid units, n=16.

| path | class | `D=1` residual vs played | `D=1` sim staleness removed | `D=0` residual vs played | `D=0` staleness removed |
|---|---|---|---|---|---|
| shot | defense | mean **1.27**, p90 4.33 | 26.45 | 1.07 | 26.70 |
| shot | offense (incl. shooter) | mean **0.01** | 27.17 | 0.00 | 27.32 |
| stopper | defense | mean **4.13**, p90 10.30 | 26.34 | 2.78 | 26.12 |
| stopper | offense | mean **1.70**, p90 7.07 | 34.65 | 2.28 | 34.05 |

- **Shot path:** the residual is played's interruption (placement has none).
- **Stopper path:** the residual is larger because the write uses the stop step while played renders the appended stopper step.
- **Shooter:** today's shooter-only fallback already reads 0.00 against the placement, so nothing changes for him.

### S5: Wall-clock

Measured on the fix (below), with the flag toggling before/after on the same tree. Flag off is byte-identical to `d9a4f1517` 40/40 on both arms and both footings.

### S6: Blast radius

Measured on the fix tree, n=40, sim arm with the flag off (= before) vs on. The played column is the reference at `_is_full_simulation` False.

| per game | sim before `D=1` | sim after `D=1` | played `D=1` | sim before `D=0` | sim after `D=0` | played `D=0` |
|---|---|---|---|---|---|---|
| HCO rebound selections | 51.8 | 50.6 | — | 52.3 | 52.7 | — |
| **OREB share of HCO misses** | **30.3%** | **24.7%** | **24.8%** | **32.4%** | **25.6%** | **22.9%** |
| OREB | 15.6 | 12.5 | 11.2 | 17.0 | 13.5 | 10.9 |
| DREB share | 69.7% | 75.3% | 75.2% | 67.6% | 74.4% | 77.1% |
| second-chance pts (both teams) | 28.7 | 21.9 | 18.6 | 29.1 | 19.9 | 16.3 |
| second-chance pts per HCO OREB | 1.85 | 1.77 | 1.66 | 1.71 | 1.48 | 1.51 |
| over-the-back calls | 67.2 | 66.4 | 60.1 | 67.9 | 71.0 | 64.3 |
| **over-the-back in play (≤ 4 units, rolls drawn)** | **15.1** | **25.9** | **39.0** | 14.8 | 29.0 | 42.2 |
| over-the-back fouls called | 0.70 | 0.95 | 2.12 | 0.40 | 1.20 | 2.02 |
| putback-defender calls | 13.9 | 11.4 | 10.3 | 13.9 | 12.2 | 10.3 |

- **Static counterfactual (Part 1, same dice replayed, turns where a matching build existed):**
  - Sim: rebounder picks change on 21.9/game (50.1%, `SEED_DEFENSES=1`) and 24.9/game (51.0%, `SEED_DEFENSES=0`); side flips 11.1 / 13.4.
  - Played control, same replay: 2.4/game (6.4%). So on those turns sim would select the same way as played about 94% of the time.
- **Over-the-back is still below played.** Played's post-shot crash sub-steps move players toward the rim before the DREB/OREB turn reads them; sim doesn't apply crash destinations. That was left alone per instruction.

**Everything else reading `player.coords` on sim during an HCO turn or the turn after** (read census, calls per game, `SEED_DEFENSES=1`):
- End-of-turn coord sync and `build_final_coords` (next-turn seeds): 2,079 each.
- Position-snapshot ledger: 1,134 during / 427 after.
- Shot micro-movement snapshots: 826 / 173.
- Rebound distance: 467 during / 72 after.
- Rim-runner FB `_player_x/_y`: 418 / 250.
- EOQ debug: 225.
- DREB turn build: 213.
- Over-the-back: 176.
- `resolve_shot`: 126.
- Rim-runner emitter: 124.
- Getback selection (`_matchup_spot_at_shot`, `_player_xy`): 110 / 90.
- Covert-release emitter: 110.
- `get_in_play_defenders`: 108.
- After-steal drive integration: 95 / 33.
- `add_player_movement`: 119.
- `covert_release._player_x`: 55.
- Steal FB routing: 54 / 21.
- Lineup helpers, `_ids_near`, `summarize_game_state`, `resolve_offensive_rebound` (43), bounce-spot lineup filter (39), putback defender (32), baseline inbound setup (30), free throw (21), DREB outlet receiver target (18), `_maybe_stamp_hco_setup` (16).

All of these now read placement coords after an HCO possession.

**These are corrections, but they move tuned numbers:** OREB rate, second-chance points, over-the-back roll counts and FB start positions.

---

## Part 2: Fix

- **`defender_placement.offense_grid_from_animations`:** per-step offense positions from the existing animations, by timestamp.
- **`Animator.compute_placement_grids`:** `compute_defender_grid`'s single build, returning `(defense, offense)`. `compute_defender_grid` delegates to it and returns the defense grid unchanged.
- **`_stamp_contest_defender_grid`:** also stamps `_step_state["offense"]`.
- **`_write_sim_hco_placement_coords`** (`phase_resolution.py`):
  - Only when `_is_full_simulation` is set and `GOB_SIM_HCO_COORD_WRITE` is on (default on).
  - Writes all ten players from the last fully stamped step.
  - Called where played calls `apply_coords_from_animations_list`: the HCO stopper path (`else` branch, `if animations:`) and the HCO shot path (`if not animations:`), before `_uess_sync_emitted_shot_coords` / `set_shooter_coords_from_skeleton_last_step`, which are unchanged.
- **Full-sim animation skip** (`animator.py:1213`): untouched. No animations are built on sim.
- **Logging (26b):**
  - `[SIM HCO COORDS] <path>: wrote N players from step i of n (k back); moved [(pos, distance)…]` at INFO on every write.
  - `⚠️ [SIM HCO COORDS] … no step with a complete placement stamp … only the shooter's coords update` at WARNING. It fired **0** times per game in all 80 sim runs.
- **Test `tests/test_sim_hco_coord_write.py`** (8 tests):
  - All ten written from the stamp, with the 26b log line.
  - Stopper uses the stop step.
  - No write on played or with the flag off.
  - Missing-stamp warning.
  - Offense carry-forward.
  - **Guard** on a real simulated quarter (mongomock, real catalogues): mean defender staleness at the shot < 2.0 units, measured **0.0**.
  - **Poison:** flag off = shooter-only must trip the same threshold, measured **35.0**.
- **Suite:** the full suite on the fix tree fails exactly the same 130 tests as at `5d44194c1` (same ids, full runs on both), with 8 more passing (2,563 vs 2,555). The six that appeared fix-only in a subset run fail the same way in a full HEAD run and pass in isolation: order-dependent `caplog` tests, pre-existing.

## Verification (n=40)

| | `SEED_DEFENSES=1` | `SEED_DEFENSES=0` |
|---|---|---|
| **staleness at the shot vs placement, sim before → after:** defense | 26.17 → **0.00** | 26.89 → **0.00** |
|   offense (non-shooter) | 34.06 → **0.00** | 34.13 → **0.00** |
|   shooter | 0.00 → 0.00 | 0.00 → 0.00 |
|   played defense / offense / shooter | 1.31 / 0.00 / 0.00 | 1.12 / 0.00 / 0.00 |
| **played arm vs `d9a4f1517`** | **40/40 byte-identical**, 0 errors | **40/40 byte-identical**, 0 errors |
| sim flag off vs `d9a4f1517` | 40/40 byte-identical | 40/40 byte-identical |
| sim pts/team before → after | 85.10 ±2.77 → 82.74 ±3.23 | 83.39 ±3.02 → 84.69 ±3.63 |
|   paired Δ | −2.36 ±3.53, not resolved | +1.30 ±4.00, not resolved |
| sim possessions before → after | 46.85 ±2.23 → 48.30 ±2.65 (Δ +1.45 ±2.74) | 47.17 ±2.10 → 50.30 ±2.21 (**Δ +3.12 ±2.73, resolved**) |
| sim draws before → after | 76,669 → 76,863 (Δ +194 ±1,199) | 60,582 → 62,249 (**Δ +1,667 ±828, resolved**) |
| arm gap sim − played, pts/team | +13.75 ±3.17 → +11.39 ±3.46 | +8.41 ±3.13 → +9.71 ±4.05 |
| independence, sim after, seed 8000 × 3 processes | identical (95.0 / 510 / 75,196), matches n=40 cell | identical (72.5 / 430 / 58,120), matches n=40 cell |
| FT-honour, sim after (windowed) | 2,420/2,427 = 99.7% | 2,954/2,968 = 99.5% |
| wall-clock per game, sim before → after (6-way parallel) | 5.02 s → 5.18 s, paired Δ +0.16 ±0.47, not resolved | 4.74 s → 4.81 s, paired Δ +0.08 ±0.39, not resolved |
| added work, timed in-process | offense extraction 17.3 ms + writer 2.8 ms per game | 17.6 ms + 2.7 ms per game |

- **Staleness reference:** the placement stamp on the final skeleton step, the position a consumer would ideally read. After the fix it is 0.00 by construction; the guard's poison shows the same measure reads 35.0 with shooter-only.
- **Residual against played's coords:** can't be paired across arms after turn 1. Part 1's emulation gives 1.27 defense / 0.01 offense on the shot path and 4.13 / 1.70 on the stopper path (`SEED_DEFENSES=1`).
- **Cost of the added work:** offense extraction runs on every stamp, flag on or off. With the flag off the writer costs 0.5 ms/game, just the env check. The total is about 20 ms on a ~5 s game (≈0.4%): no new placement build, a small pure extraction.

## Not covered

- **Final Turn shot** (`phase_resolution.py:8183`, `resolve_final_turn_shot_logic`) takes the same `skeleton_to_animations` → `[]` path on sim and still updates only the shooter.
- **Crash destinations** are not applied on sim (why over-the-back in-play is still 25.9 vs played's 39.0).
- **Rebound selection, the 1–6 dice roll in `calculate_rebound_score`, and crash destinations:** unchanged, per instruction.
- **No baseline re-cut.**

**Is sim reading the same coords as played, and what does it cost?** Sim now reads the same placement played renders from, with no staleness against it, which leaves only played's interruption (≈1.3 units on shots, ≈4 on stoppers) and the unapplied crash positions. It costs about 20 ms per game and no new placement build or draw, and played is untouched.
