# B1-A timed spike — build animations for the sim arm's coordinate pipeline

**Flag `GOB_SIM_BUILD_ANIM_FOR_EMITTER`, default `"0"`. Nothing flipped, no reference re-cut, nothing retuned.** With the flag off the worker reproduces `equiv_v3_reference_ec4f5acfc_poslookup2.json` **40/40 on fingerprint and draws, all four cells** — the gate passed, so the numbers below are trustworthy. `develop` is merged in (`git rev-list --count HEAD..develop` = 0).

---

## Recommendation: adopt it. The timing cost is noise against the real bottleneck.

**Cost — engine sim CPU, three paired serial runs: +2.9%, +7.8%, +9.1%. Call it ~+7%.**

The budget unit in `Sim_Perf_Capstone.md` is a **63-game week against a 90 s target**, and the authoritative Railway numbers are `full_sim_block` **~20 s** (0.32 s/game, pooled) and `persist_loop` **~95 s** (1.5 s/game).

| | now | with B1-A |
|---|---|---|
| Railway `full_sim_block`, 63-game week | ~20 s | **~21.4 s** (+1.4 s) |
| Railway `persist_loop`, same week | ~95 s | ~95 s (untouched) |
| **week total** | **~115 s** | **~116.4 s** |

**+1.4 s on a week that is already ~115 s and is dominated 5:1 by persistence, not by the sim.** The 90 s target is missed today by ~25 s for reasons B1-A does not touch; this spike moves that number by 1.4 s. Locally at 8 workers the week runs in 34.6 s, so the headroom there is comfortable either way.

**What it buys:** the sim arm's shot logic stops running on a substitute coordinate frame. `_uess_sync_emitted_shot_coords` goes from failing **100%** of sim HCO shots to **2.2%** — the same rate as played (2.4%) — and the `ShotAttemptGeometry.source` distribution becomes **identical to played's**. On the structural measures the two arms converge almost exactly: draws/game from **−15.1% vs played to +1.6%**, FT awards from 2,120 to 2,291 against played's 2,290. Six of nine box-score measures move toward played.

**Caveats you should weigh, not dismissed:**
- It re-phases the sim RNG stream — **every sim game changes** (0/40 byte-equality on both footings). A full reference re-cut is mandatory.
- It makes `GOB_SIM_HCO_COORD_WRITE` and `GOB_SIM_CRASH_APPLY` dead on the HCO path, and **their three guard tests fail** with the flag on — correctly, because their subject no longer runs.
- Sim turn payloads grow **1.19×** in memory (30.2 → 35.8 MB/game), landing at 0.97× of played.
- The timing measurement is local and serial; **Railway is pooled with ~10× better DB latency**, so the +1.4 s above is an extrapolation from a ratio, not a Railway measurement.

---

## 1. Build — how "called from the emitter" is scoped

**An explicit keyword parameter, not call-stack inspection.**

`Animator.skeleton_to_animations(...)` gains `*, for_emitter=False`. The gate at `animator.py:1214` becomes:

```python
if self.game.game_state.get("_is_full_simulation", False):
    if not (for_emitter and sim_build_anim_for_emitter_enabled()):
        return []
```

`for_emitter=True` is passed at exactly **four** call sites — every one of them a member of the coordinate pipeline, i.e. its output feeds `apply_coords_from_animations_list` and/or `_uess_sync_emitted_shot_coords`:

| file:line | path |
|---|---|
| `phase_resolution.py:9561` | HCO **shot** — the build the file itself calls *"UESS single build … reuse it for coord-sync, resolve_shot, and (stamped below) the step emitter"* |
| `phase_resolution.py:9168` | HCO **non-shot** — feeds `apply_coords_from_animations_list` |
| `phase_resolution.py:8327` | **final turn** — feeds the final-turn coord sync |
| `skeleton_step_emitter.py:1614` | the emitter's own fallback build — this *is* the emitter |

**Deliberately NOT marked, so the FE animation packet stays unbuilt for sims:**

- `turn_manager.py:2267` and `:2282` — the `result["animations"]` FE payload writes, and `capture_halfcourt_animation`
- the three `capture_*` methods keep their own untouched `_is_full_simulation` gates
- `step_state.py:136` — a verification-only **second** draw on a deep copy; building it would add draws for no benefit
- the FCP/HCT legacy bodies (dead behind `USE_DYNAMIC_FCP` / `USE_DYNAMIC_HCT`)

The flag helper lives in `BackEnd/utils/lineup_position.py`, the existing leaf module, so nothing gains an import cycle.

## 2. Kill switch — the gate

| cell | arm | fingerprint | draws | errors |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=1` | played | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | played | **40/40** | **40/40** | 0 |

**PASSED.**

## 3. Timing

**Serial — one game per process, run one at a time, on an otherwise quiet box** (verified 0 stray sim processes before each run). `wall_s` is the worker's own measure of the four `simulate_quarter` calls, i.e. engine sim only, excluding import and seeding. The shell `time` figure is whole-process CPU including both.

| run | mean | CI95 | p50 | p90 |
|---|---|---|---|---|
| `SD=1` rep 1 OFF | 5.163 s | ±0.361 | 5.139 | 6.661 |
| `SD=1` rep 1 ON | 5.336 s | ±0.293 | 5.571 | 6.451 |
| `SD=1` rep 2 OFF | 4.846 s | ±0.325 | 5.124 | 6.086 |
| `SD=1` rep 2 ON | 5.267 s | ±0.289 | 5.408 | 6.309 |
| `SD=0` OFF | 4.147 s | ±0.285 | 3.888 | 5.460 |
| `SD=0` ON | 4.560 s | ±0.276 | 4.437 | 5.946 |

| | wall mean | wall p50 | wall p90 | **process CPU** |
|---|---|---|---|---|
| `SD=1` rep 1 | 1.033× | 1.084× | 0.968× | **1.029× (+2.9%)** |
| `SD=1` rep 2 | 1.087× | 1.055× | 1.037× | **1.078× (+7.8%)** |
| `SD=0` | 1.100× | 1.141× | 1.089× | **1.091× (+9.1%)** |

**Wall-clock CIs overlap in every pair — at n=40 the wall difference is not individually significant.** The three paired CPU-time ratios do not overlap zero and are the measure `Sim_Perf_Capstone.md` itself prefers ("immune to the machine contention that plagued wall-clock measurement"). **Take ~+7%, with a defensible range of +3% to +10%.**

The noise-free confirmation that real work was added:

| | flag OFF | flag ON | |
|---|---|---|---|
| **draws/game**, `SD=1` | 69,337 | **83,018** | **1.197×** |
| **draws/game**, `SD=0` | 55,096 | **62,834** | **1.140×** |

### How this compares to how Railway runs it — stated plainly

**It is measured differently.** These runs are serial, single-process, one game per process, on a local box with ~27 ms Atlas latency. Railway runs the week **pooled at 8 workers** with ~1–3 ms colocated Atlas. The +1.4 s week figure at the top is the ~+7% ratio applied to Railway's measured ~20 s `full_sim_block` — **a ratio extrapolation, not a Railway measurement.** The ratio should hold (it is CPU work, not DB wait), but the authoritative number needs a staging run.

**No multi-game/season path in this harness.** The equiv-v3 worker is one game per process by construction (rule 6e). The 63-game week figures are quoted from `Sim_Perf_Capstone.md`, not re-measured here.

## 4. Coverage

Sim arm, 40 games, `SEED_DEFENSES=1`:

| | flag OFF | **flag ON** | played (reference) |
|---|---|---|---|
| `build_skeleton_animation_steps` returned None | **4996/4996 (100.0%)** | **159/8534 (1.9%)** | 174/8447 (2.1%) |
| `_uess_sync_emitted_shot_coords` returned None | **3437/3437 (100.0%)** | **79/3662 (2.2%)** | 87/3614 (2.4%) |
| `[SHOT-NO-SCHEMA]` log lines | **93/game** | **5/game** | — |

**`ShotAttemptGeometry.source` — the frame shot logic actually consumes:**

| source | sim OFF | **sim ON** | played |
|---|---|---|---|
| `hco-emitter-shot-step` | **0** | **3,473** | 3,425 |
| `hco-stepstate-shot-step` | **3,364** | **0** | 0 |
| `hco-final-grid-shot-step` | 73 | 79 | 87 |

**The sim arm's distribution becomes played's.** This is the whole point of the spike.

## 5. What it buys — does sim move toward played?

`SEED_DEFENSES=1`, n=40. "→" means the sim–played gap narrowed.

| metric | sim OFF | **sim ON** | played | gap OFF | gap ON | |
|---|---|---|---|---|---|---|
| pts/team | 74.56 ±3.65 | 74.30 ±3.15 | 74.21 ±2.89 | 0.35 | **0.09** | → |
| possessions | 41.12 ±2.05 | 40.92 ±1.91 | 39.83 ±1.91 | 1.30 | **1.10** | → |
| **fouls** | 52.17 ±2.52 | 53.73 ±2.78 | 54.35 ±2.44 | 2.18 | **0.62** | → |
| FG% | 45.89 ±2.01 | 45.45 ±2.18 | 44.81 ±1.93 | 1.08 | **0.64** | → |
| **3PT attempt share** | 32.93% ±1.46 | **33.35% ±1.51** | 33.50% ±1.34 | 0.58 | **0.16** | → |
| FGA | 106.72 ±2.33 | 102.97 ±2.22 | 104.60 ±2.08 | 2.12 | **1.62** | → |
| OREB share | 29.61% ±1.73 | 29.34% ±1.48 | 31.56% ±1.89 | 1.95 | 2.22 | ← |
| OREB | 18.95 ±1.48 | 18.77 ±1.48 | 20.57 ±1.57 | 1.62 | 1.80 | ← |
| 3PT% | 31.58% ±2.90 | 34.31% ±3.60 | 32.09% ±2.79 | 0.50 | 2.22 | ← |

**Six of nine move toward played; three move away.** Every individual delta sits inside its own CI at n=40, so no single row is significant — the signal is the pattern plus the two structural measures below, which are not noisy:

| | sim OFF | **sim ON** | played | |
|---|---|---|---|---|
| **draws/game** | 69,337 (−15.1% vs played) | **83,018 (+1.6%)** | 81,705 | **converged** |
| **FT awards** (40 games) | 2,120 | **2,291** | 2,290 | **converged** |

**2PT/3PT reclassification, the direct measure the brief asked for:** 3PT attempt share rises **+0.42 pp** (32.93% → 33.35%), i.e. roughly **+0.44 three-point attempts per game reclassified upward**, landing **0.16 pp from played**. Direction: the sim arm now classifies *more* attempts as threes, which is what reading the emitter's interrupted (further-out) shooter coord does — exactly what commit `0050c5ebc` bought the played arm.

**Arm gap (sim − played), pts/team, paired per seed:**

| | flag OFF | flag ON |
|---|---|---|
| `SEED_DEFENSES=1` | +0.35 ±4.06 | **+0.09 ±3.26** |
| `SEED_DEFENSES=0` | +0.14 ±2.97 | +1.45 ±3.28 |

Mixed and well inside CI both ways — **pts/team arm gap is not a discriminating measure at n=40.** The draws and FT-award convergence are.

## 6. Integrity with the flag on

| gate | result |
|---|---|
| **§8.1 coord-continuity corrections** | **0 across 160 games, all four cells** |
| independence (seed 8000 × 3 processes) | **PASS** in all four cells |
| FT-honour windowed | sim 99.7% / 99.5%; played 99.7% / 99.7% |
| FT-honour strict | 95.8–96.2% |
| errors across 160 games | **0** |

**Byte-equality vs the current reference — the known cost, quantified:**

| cell | arm | fingerprint | draws |
|---|---|---|---|
| `SEED_DEFENSES=1` | **sim** | **0/40** | **0/40** |
| `SEED_DEFENSES=0` | **sim** | **0/40** | **0/40** |
| `SEED_DEFENSES=1` | played | **40/40** | **40/40** |
| `SEED_DEFENSES=0` | played | **40/40** | **40/40** |

**Every sim seed diverges; no played seed does.** That is the scoping working exactly as intended — the flag is sim-only by construction, and the played arm is untouched. How far: draws/game moves +19.7% / +14.0%, pts/team −0.26 / +1.31, both inside CI.

### Full suite

| | flag OFF (the committed default) | flag ON |
|---|---|---|
| failed | **0** | **3** |
| passed | 2813 | 2810 |
| skipped / xfailed | 20 / 112 | 20 / 112 |

**The committed state is 0 failed.** The three flag-on failures are:

```
tests/test_sim_crash_apply.py::test_guard_sim_overlay_players_reach_the_predicted_positions
tests/test_sim_crash_apply.py::test_guard_poison_flag_off_trips_the_threshold
tests/test_sim_hco_coord_write.py::test_guard_poison_shooter_only_trips_the_threshold
```

They fail with **`AssertionError: the guard measured too few overlay players to mean anything` — `assert 1 > 50` / `assert 0 > 50`.** These are the guards for `GOB_SIM_CRASH_APPLY` and `GOB_SIM_HCO_COORD_WRITE`: with B1-A on, the sim arm's HCO turns carry `animation_steps`, so `apply_sim_crash_destinations` returns 0 and `_write_sim_hco_placement_coords` never fires. **The guards have nothing to measure because their subject is dormant — they are detecting that correctly rather than silently passing.** Not a regression; it is the signal that B1-A retires both substitutes.

## 7. Risk

### What now exists on the sim arm that did not before

| | sim OFF | **sim ON** | played |
|---|---|---|---|
| turn payload, in-memory (`json.dumps` at end-of-turn) | 30.18 MB/game | **35.84 MB/game (1.19×)** | 37.12 MB/game |
| of which `animation_steps` | 8.71 MB | **14.79 MB** | 15.14 MB |
| HCO turns carrying `animation_steps` | 11/1243 | **1190/1221** | 1187/1218 |
| turns carrying `animations` | **10** | **932** | 1,569 |

- **`animation_steps` on sim HCO turns is new**, and it is the intended product. Sim payloads land at **0.97× of played**, so nothing exceeds what the played arm already carries.
- **`animations` now appears on ~932 turns/10 games**, from `phase_resolution.py:9594-9595` (`if animations: shot_result["animations"] = animations`) — a deliberate handoff so the emitter reuses the single build rather than redrawing. Still below played's 1,569.
- **Memory:** ~+5.7 MB per in-flight game. At 8 pooled workers that is ~+45 MB peak. Not measured under the pool.
- **Persistence:** `game_manager.to_dict()` includes `"turns": self.turns`, so anything on a turn result is reachable by a serializer. **I have not traced end-to-end which serializer the CPU-sim path uses**, so I cannot say whether these bytes reach Mongo for a simmed game — `build_game_summary` writes only `box_score`, not turns. **This is the one risk I would want closed before adoption**, and it is a read, not an experiment.
- **Nothing is written that a played game does not already write** — every field involved already exists on the played arm at equal or greater volume.

### What a full re-cut would involve

1. Flip the default to `"1"` in `sim_build_anim_for_emitter_enabled()`.
2. Kill-switch check: `=0` must still reproduce `equiv_v3_reference_ec4f5acfc_poslookup2.json` 40/40 on all four cells (verified today, would need re-verifying at the flip commit).
3. Cut `equiv_v3_reference_<sha>_b1a.json` — all four cells, both arms.
4. **Double re-baseline**: a second full worker run reproducing the new file 40/40.
5. Update `references/README.md`, moving `ec4f5acfc_poslookup2` to *Superseded* with `GOB_SIM_BUILD_ANIM_FOR_EMITTER=0` recorded as what reproduces it.
6. Decide what happens to `GOB_SIM_HCO_COORD_WRITE` and `GOB_SIM_CRASH_APPLY`: both become dead on the HCO path. Either retire them with their three guard tests, or keep them as the kill-switch partners of B1-A and re-scope the guards to run only with B1-A off.
7. Re-run the sim-arm portion of `reports/coord-parity-2026-09-20.md`'s scope table to confirm HCO coverage stays at played parity.
8. **Measure on Railway staging**, since the +1.4 s/week here is an extrapolation.

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A. Timing runs are **serial**; outcome and coverage runs are 8-parallel (parallelism does not affect determinism, only wall-clock, and no wall-clock number comes from a parallel run). Payload sizes are 10 games, not 40.

## Not covered

- **Default not flipped, reference not re-cut, nothing retuned.**
- **Not measured on Railway.** The +1.4 s/week is the local CPU ratio applied to a quoted Railway figure.
- **Not traced:** whether sim turn payloads reach Mongo, and at what size. Listed as the open risk above.
- **Not measured:** memory under the 8-worker pool.
- **Not attempted:** B1-B (a sim path inside `_uess_sync_emitted_shot_coords`), the fallback if the timing had been prohibitive. On these numbers it should not be needed.
