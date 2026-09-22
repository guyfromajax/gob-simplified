# Sim crash-destination parity

Written for: Jamie and the sessions tuning sim results. Three commits on `feature/animation-reward` over `f28f52475`: `5febb76ad` (writer), `0bf1b57ba` (clock flag), `43cc59158` (tests). Both flags default **OFF**.

**Short answer.** The over-the-back in-play gap **closed**: sim goes from 25.85 to **39.58** per game against played's 38.98 (`SEED_DEFENSES=1`), and fouls called from 0.95 to **2.12** against played's 2.12. The writer takes **0 `sim_rng` draws** and about **6 ms/game**. Played is byte-identical 40/40 on both footings with both flags on. **No fresh sim reference is owed** — nothing defaults on.

## Footing (rule 6e)

- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`.
- **Played arm:** `ARM=played`, `_is_full_simulation` False only inside the four gated Animator methods at Pattern A.
- **Sim arm:** `ARM=sim`, `_is_full_simulation` True throughout.
- **Seeds 8000–8039 (n=40), both `SEED_DEFENSES=1` and `=0`, CI = 1.96 × SEM.**
- **References:** sim `equiv_v3_sim_reference_4f856721a.json`; played `d9a4f1517`.
- **Probe integrity:** verification 40/40 per cell; blast-radius probe (flags off) 80/80; accuracy probe 80/80; all match their references.
- **Probes:** session scratchpad (`cr/pre_probe.py`, `cr/s6b.py`), uncommitted.

## What was built

**`5febb76ad` — the writer** (`BackEnd/utils/shared.py`):
- `sim_post_shot_window_seconds(turn_result, away_offense, shot_spot)` derives the live-ball window from the turn result alone: ball flight (`_variant_flight_end` + arc-aware rate) + RATTLE hops + the make settle + the miss/block bounce.
- `apply_sim_crash_destinations(game, turn_result, positions)` advances each overlay player with **one** `_interpolate_step_end` toward his destination at his `_OVERLAY_ARCHETYPES` rate over that window, writing into the `positions` map `sync_lineup_coords_from_turn` is about to assign.
- Called from `sync_lineup_coords_from_turn` **after** `canonicalize_post_shot_overlays`, so the shooter / get-back / release exclusions are the existing ones (not reimplemented).
- Gated: full simulation, `GOB_SIM_CRASH_APPLY` on, and the turn produced **no schema steps and no legacy `animations`**.
- **All five authoring branches are covered**, because the gate is on the turn's rendered output rather than on the branch: MAKE (`:2057`/`:2076`), shooting foul on a miss (`:2160`/`:2172`), defensive foul on a miss (`:2264`/`:2279`), fast-break miss (`:2444`/`:2454`), HCO miss (`:2550`/`:2565`). A test asserts the writer fires for each.
  - In practice the HCO family is what it fills: fast-break, HCT and FCP turns emit schema steps **on both arms** and already carry these positions (sim: 12 of 110 such turns/game emit; the other 98 are the HCO family).
- **Why both `animation_steps` and `animations` are checked:** the equiv-v3 played arm has `_is_full_simulation` true outside the four gated methods, and on ~3 HCO turns/game its emitter returns None. A gate on the flag alone fired there and moved played (61.0 → 67.5 on seed 8000). Played keeps `animations` on those turns and sim never has it (0 of 110), so the two-way check restores byte-identity.

**`0bf1b57ba` — the clock flag** (`BackEnd/models/turn_manager.py`): `_maybe_add_sim_post_shot_clock` adds the same derived window to a sim HCO shot turn's `time_elapsed`, at the point played realigns its own clock, same gate, `GOB_SIM_CRASH_CLOCK`, independent of the writer. The duration **is** derivable without a build, so this was built rather than skipped.

**`43cc59158` — tests** (23 pass): the arithmetic, one per authoring branch, the skips (played / flag off / already-rendered), `sim_post_shot_window_seconds` on a non-shot turn, an assertion that the writer touches no `sim_rng` method, and the simulated-quarter guard with its poison.

## Position accuracy (played arm, where both the prediction and the true answer exist)

| `SEED_DEFENSES=1`, n=32,326 overlay players | mean | p50 | p90 | max |
|---|---|---|---|---|
| **writer's arithmetic vs played's actual** | **2.17** | 0.00 | 6.52 | 77.5 |
| **POISON (writer off — today's sim)** | **13.31** | 12.08 | 23.02 | 86.1 |
| offense rebounders | 2.80 | 0.00 | 6.63 | 66.4 |
| defense rebounders | 1.47 | 0.00 | 5.65 | 77.5 |
| get-back | 4.11 | 1.73 | 8.69 | 28.6 |
| release | 3.89 | 0.00 | 9.24 | 30.6 |
| by result: MISS | **0.81** | 0.00 | 1.94 | 58.7 |
| by result: MAKE | 3.66 | 1.80 | 8.95 | 77.5 |
| by result: BLOCK | 3.08 | 2.47 | 6.68 | 11.5 |

`SEED_DEFENSES=0` matches: 1.98 prediction / 13.20 poison; MISS 0.64, MAKE 3.33, BLOCK 3.08.

**Why this is 2.17 and not B2's 0.05.** B2 fed the emulation **played's emitted step durations**, which exist only on the played arm. The shipped writer must derive the window on sim, and the derived window is not the emitted one: derived/emitted ≈ **0.80 on HCO MISS** (1.84 s vs 2.28 s), **0.57 on MAKE** (0.93 vs 1.55), **1.62 on BLOCK** (1.21 vs 0.76). The differences are played's shoot-step duration (an emitter construct: gate travel plus floors, ~0.4 s) and the clock-pinned beats (the make hold freezes players, so including or excluding it changes the total). MISS — the case rebounding depends on — lands at 0.81. The guard in the test suite measures the writer against its own arithmetic (0.0 with the flag, 13.17 with it off), so it catches a writer that stops working; this table is the separate question of how close the arithmetic is to played.

## Verification

| | `SEED_DEFENSES=1` | `SEED_DEFENSES=0` |
|---|---|---|
| **played, both flags ON, vs `d9a4f1517`** | **40/40 byte-identical**, 0 errors | **40/40 byte-identical**, 0 errors |
| sim, both flags OFF, vs the `4f856721a` reference | 40/40 byte-identical | 40/40 byte-identical |
| independence, APPLY on (seed 8000 × 3) | identical, matches the n=40 cell | identical, matches the n=40 cell |
| independence, APPLY+CLOCK (seed 8000 × 3) | identical, matches the n=40 cell | identical, matches the n=40 cell |
| FT-honour, all four cells | 99.5–99.9% | 99.5–99.6% |
| errors, all four cells | 0 | 0 |

Four arms, n=40:

| `SEED_DEFENSES=1` | pts/team | possessions | draws (Δ vs off/off) | wall (Δ) | arm gap (sim − played) |
|---|---|---|---|---|---|
| APPLY 0 / CLOCK 0 | 82.74 ±3.23 | 48.30 | 76,863 (—) | 5.25 s | +11.39 ±3.46 |
| **APPLY 1 / CLOCK 0** | 83.99 ±3.53 | 47.88 | 76,728 (−136 ±1,460) | 5.32 s (+0.07 ±0.48) | +12.64 ±3.59 |
| APPLY 0 / CLOCK 1 | 73.15 ±3.14 | 44.15 | 68,933 (−7,931 ±1,078) | 4.43 s (−0.82 ±0.46) | +1.80 ±3.10 |
| APPLY 1 / CLOCK 1 | 74.96 ±3.01 | 43.75 | 69,190 (−7,673 ±1,208) | 4.48 s (−0.77 ±0.46) | +3.61 ±3.88 |

| `SEED_DEFENSES=0` | pts/team | possessions | draws (Δ) | wall (Δ) | arm gap |
|---|---|---|---|---|---|
| APPLY 0 / CLOCK 0 | 84.69 ±3.63 | 50.30 | 62,249 (—) | 4.89 s | +9.71 ±4.05 |
| **APPLY 1 / CLOCK 0** | 82.92 ±4.61 | 49.85 | 61,267 (−981 ±971) | 4.90 s (+0.00 ±0.53) | +7.95 ±4.18 |
| APPLY 0 / CLOCK 1 | 78.55 ±3.68 | 45.55 | 56,187 (−6,062 ±773) | 4.70 s (−0.19 ±0.46) | +3.58 ±3.80 |
| APPLY 1 / CLOCK 1 | 72.79 ±3.73 | 45.27 | 55,167 (−7,081 ±744) | 4.20 s (−0.69 ±0.44) | −2.19 ±3.73 |

- **Draws:** the writer itself takes **0** `sim_rng` draws (counted in-process, 0 across all 80 sim games with APPLY on, and asserted by a test). Total game draws move because the new positions change downstream behaviour — −136 ±1,460 (not resolved) seeded, −981 ±971 unseeded.
- **Wall-clock:** APPLY +0.07 ±0.48 s seeded, +0.00 ±0.53 unseeded — not resolved. In-process, the added work is **8.3 ms/game** against a 2.3 ms baseline for the same instrumentation with the flags off, so **≈6 ms/game net**.

## Blast radius (sim before → after, played alongside)

| per game, `SEED_DEFENSES=1` | sim off/off | sim APPLY | sim APPLY+CLOCK | played |
|---|---|---|---|---|
| **over-the-back IN PLAY (≤4 units)** | **25.85 ±1.90** | **39.58 ±1.66** | 36.05 ±1.70 | **38.98 ±2.04** |
| **over-the-back fouls called** | 0.95 ±0.33 | **2.12 ±0.37** | 1.60 ±0.41 | **2.12 ±0.42** |
| over-the-back calls | 66.38 | 67.97 | 61.60 | 60.10 |
| OREB share of HCO misses | 24.71% | 25.73% | 25.57% | 24.75% |
| OREB | 12.45 | 12.95 | 11.72 | 11.20 |
| DREB share | 75.29% | 74.27% | 74.43% | 75.25% |
| second-chance points (both teams) | 21.85 | 21.50 | 18.40 | 18.60 |
| putback-defender calls | 11.38 | 11.82 | 10.70 | 10.25 |
| rebounder selections | 50.58 | 50.77 | 46.08 | 45.05 |
| possessions | 48.30 | 47.88 | 43.75 | 42.65 |
| pts/team | 82.74 | 83.99 | 74.96 | 71.35 |
| players moved by the writer | 0 | 839.5 | 757.8 |  |

| per game, `SEED_DEFENSES=0` | sim off/off | sim APPLY | sim APPLY+CLOCK | played |
|---|---|---|---|---|
| **over-the-back IN PLAY (≤4 units)** | **28.98 ±1.73** | **40.25 ±2.51** | 37.17 ±2.32 | **42.17 ±2.48** |
| over-the-back fouls called | 1.20 | 1.48 | 1.80 | 2.02 |
| OREB share | 25.62% | 24.65% | 24.36% | 22.94% |
| second-chance points | 19.93 | 19.50 | 16.38 | 16.32 |
| putback-defender calls | 12.22 | 10.80 | 10.18 | 10.25 |
| possessions | 50.30 | 49.85 | 45.27 | 46.62 |
| pts/team | 84.69 | 82.92 | 72.79 | 74.97 |

**Did the over-the-back in-play gap close? Yes.** Seeded: 25.85 → 39.58 against played's 38.98, and fouls called land exactly on played's 2.12. Unseeded: 28.98 → 40.25 against 42.17, most of the way. Rebounding stays where it was (OREB share 24.71% → 25.73%, played 24.75%), which is expected: selection still reads pre-crash positions by design.

**The clock flag is a separate, much larger lever.** It closes the arm gap (+11.39 → +1.80 seeded, +9.71 → +3.58 unseeded) by removing ~4 possessions/game, and it pulls second-chance points and rebounder selections onto played's values. It also moves points per team by ~9.6, so it is a balance decision, not a parity one.

**Final Turn shots:** not reported per cell. The worker rows don't carry them and the flags don't touch `resolve_final_turn_shot_logic`; at `4f856721a` they were sim 3.77 vs played 2.48 seeded.

## Not covered

- **Fast-break start positions** as a distinct metric: not quantified. FB turns emit on both arms, so their own crash overlays were already applied; what changes for them is the coords they inherit from the preceding HCO turn.
- **Selection from crash arrival positions:** not attempted. `select_rebounder_by_score` still runs at `:2483` reading pre-crash coords, as instructed.
- **Crash destination values, the `randint(1,6)`, `uses_shot_arc`, selection order, `_team_rebound_bonus`:** untouched.
- **R1 (Final Turn) and R2 (stopper):** still open; this pass doesn't change them. The sim Final Turn shot still updates only the shooter, so its crash maps are applied by this writer only if that turn carries no rendered output (it does not — it has `animations`).
- **`animator.py:1213`, the played arm:** untouched.
- **Fresh sim reference:** **not owed.** Both flags default OFF and the flags-off arm is byte-identical to `4f856721a`. One becomes owed the moment either default flips — and with APPLY the sim reference moves by roughly −136 (seeded) / −981 (unseeded) draws and +1.25 / −1.76 pts/team.
- **Untracked files not created by this session:** `reports/READY--TEST-can-you-see-this-in-cursor.md`, `reports/READY--sim-coord-fix-landed-3-calls-for-you.md`.
