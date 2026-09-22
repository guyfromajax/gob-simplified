# Zone sink Stage B — landed, measured, re-baselined

**Lead answer, in the order asked.**

**1. The rung-share prediction holds.** Stage A put on the record that the empty rung share should not move at all, because the sink changes *where* an empty-zone defender stands, not *whether* the branch fires — and that if it moved, the wiring was wrong. It did not move: sim **17.97% → 17.92% → 17.75%**, played **18.08% → 17.93% → 18.47%**, every step well inside a ±0.44–0.53 CI, across both arms and both measurement steps. No rung moved by more than its own interval. The wiring is right.

**2. The §8.1 coord-continuity guard fired zero times.** Not "low" — **0 corrections in 240 measured games**, on both arms, at both steps, against ~186–195 guard invocations per game. The sink introduced no discontinuity anywhere the guard can see.

**3. The outcome.** Both arms moved on the production footing and byte-equality does not hold (0/40 at both steps, both arms) — expected and stated up front. Sim pts/team drifts up across the two steps (73.95 → 74.95 → 75.66), played is flat (70.79 → 71.71 → 71.56), arm gap +3.16 → +3.24 → +4.10, all with overlapping intervals and none resolved at n=40. The two controls both held exactly: `SEED_DEFENSES=0` is **byte-identical 40/40 on both arms at both steps**, and `GOB_ZONE_SINK=0` reproduces the rings reference **40/40 on all four cells**. IQ rolls landed at **290.2/game (sim) and 304.9 (played) — exactly 5.00 per zone possession**, against the ~282 predicted.

## Footing (rule 6e)

- **Tree:** `feature/animation-reward`. Baseline and step 1 at `cd2a08c3e`/`3af6b50b7`; step 2 and the gates at `1fd08c080`.
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` (production) and `=0` (control).
- **Sim arm:** `_is_full_simulation` **True** throughout the quarter loop. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- **480 measured games** (3 conditions × 160) plus 12 gate games. **0 errors** in every cell.
- Probe: `sb/probe.py` (session scratchpad, uncommitted) — pure counters plus deterministic geometry.

**One process note, reported rather than buried.** My first step-1 run was started and then I edited `shared_defense.py` and `defender_placement.py` while it was still in flight. Because each game is a fresh process, games launched after the edit would have picked up the new code. Per the standing rule I **discarded that run entirely and re-ran step 1 from scratch on a settled tree** (`git status` clean of tracked modifications before launch). Every number below comes from the re-run.

## What landed — five commits

| commit | what |
|---|---|
| `e2d42945a` | the `shape` preset + the continuous ball-centrality term (still inert, flag OFF) |
| `cd2a08c3e` | **step 1** — `GOB_ZONE_SINK` default ON |
| `3af6b50b7` | the IQ per-possession roll, default OFF |
| `1fd08c080` | **step 2** — `GOB_ZONE_SINK_IQ` default ON |
| `3b4d2b2f5` | both references re-cut |

**The preset**, built as one preset and not a per-defender switch:

| | value | from |
|---|---|---|
| `ball_strong` | 0.25 | `balanced` |
| `basket_strong` | 0.15 | `balanced` |
| `ball_weak` | 0.05 | `rim_heavy` |
| `basket_weak` | 0.75 | `rim_heavy` |
| reach p/s/i | 8 / 7 / 5 | `rim_heavy` |

The other four presets remain selectable via `GOB_ZONE_SINK_WEIGHTS`.

**The middle band is a ramp, not a step.** `ball_centrality(y)` is 0 at y=18, rises linearly to 1 at y=23, is flat through y=28, and falls linearly back to 0 at y=33. Verified continuous: sweeping y in 0.1 increments, the **largest single step in the output is 0.0200**, exactly the ramp slope — there is no edge anywhere. It composes with the existing term (`strongness += (1 − strongness) × centrality`) rather than replacing it, so off-centre geometry still shows through a partial ramp.

**Side comes from the anchor — confirmed, no fix needed.** `sink_position` computes `strongness` from `abs(ball[1] − anchor[1])`. It never reads the defender's live position, and it could not sensibly do so: the live position is this function's own output, so reading it would make the model self-referential and path-dependent across steps. The Stage A code already had this right.

## 1. Rung shares — the prediction check

`SEED_DEFENSES=1`, n=40. baseline = sink off → step 1 = sink on, IQ neutral → step 2 = + IQ.

**sim arm** (defender-steps/game 11,376 → 11,244 → 11,500):

| rung | baseline | step 1 | step 2 | Δ step 1 | Δ step 2 |
|---|---|---|---|---|---|
| 0 overlap | 38.69% ±0.72 | 38.86% ±0.69 | 39.23% ±0.69 | +0.18 | +0.54 |
| a bh in zone | 15.66% ±0.23 | 15.54% ±0.25 | 15.81% ±0.24 | −0.12 | +0.15 |
| b deep | 0.00% | 0.00% | 0.00% | 0.00 | 0.00 |
| c one player | 22.27% ±0.64 | 22.27% ±0.67 | 21.60% ±0.66 | −0.00 | −0.67 |
| d many | 5.41% ±0.22 | 5.42% ±0.28 | 5.62% ±0.26 | +0.00 | +0.20 |
| **e empty** | **17.97% ±0.49** | **17.92% ±0.53** | **17.75% ±0.48** | **−0.06** | **−0.22** |

**played arm** (11,322 → 11,556 → 11,396):

| rung | baseline | step 1 | step 2 | Δ step 1 | Δ step 2 |
|---|---|---|---|---|---|
| 0 overlap | 38.63% ±0.73 | 38.78% ±0.71 | 38.00% ±0.78 | +0.15 | −0.62 |
| a bh in zone | 15.72% ±0.23 | 15.79% ±0.26 | 15.80% ±0.27 | +0.06 | +0.08 |
| b deep | 0.00% | 0.00% | 0.00% | 0.00 | 0.00 |
| c one player | 22.08% ±0.64 | 21.96% ±0.64 | 22.22% ±0.67 | −0.12 | +0.14 |
| d many | 5.49% ±0.24 | 5.54% ±0.30 | 5.50% ±0.27 | +0.05 | +0.00 |
| **e empty** | **18.08% ±0.44** | **17.93% ±0.46** | **18.47% ±0.47** | **−0.14** | **+0.40** |

**The empty rung is unmoved on both arms at both steps**, and so is every other rung — nothing exceeds its own CI. That is the falsifiable prediction from Stage A, and it passed. The `b_deep` rung remains exactly zero across all 480 games, as it has in every pass since it was first measured.

## 2. The §8.1 coord-continuity guard

`SEED_DEFENSES=1`, n=40 per cell:

| arm | condition | guard invocations/game | **corrections/game** | total over 40 games |
|---|---|---|---|---|
| sim | baseline (sink off) | 194.1 | **0.000** | **0** |
| sim | step 1 (sink on) | 194.9 | **0.000** | **0** |
| sim | step 2 (+ IQ) | 194.2 | **0.000** | **0** |
| played | baseline | 186.2 | **0.000** | **0** |
| played | step 1 | 187.4 | **0.000** | **0** |
| played | step 2 | 186.8 | **0.000** | **0** |

**Zero, in every cell.** The guard is genuinely live and genuinely exercised — it ran ~190 times a game and reported nine distinct emitter contexts in a single-game breakdown (`dreb`, `oreb`, `dynamic_hct`, `dynamic_fcp`, `fb_drive`, `fb_outlet_pass`, `covert_release`, `after_steal`, `rim_runner/triangle`) — it simply never had anything to correct. Emitters whose contexts did not appear (`ft`, `hct`, `triangle`) did not fire in the sampled game rather than being unmonitored.

This is the result the design predicted: the sink returns a position clamped inside a fixed polygon from a fixed anchor, and it is recomputed identically per step, so consecutive steps cannot disagree about where a defender was.

## 3. Outcome table

**`SEED_DEFENSES=1` (production), n=40** — baseline → step 1 → step 2:

| metric | sim baseline | sim step 1 | sim step 2 | played baseline | played step 1 | played step 2 |
|---|---|---|---|---|---|---|
| **pts/team** | 73.95 ±2.96 | 74.95 ±3.14 | **75.66 ±3.40** | 70.79 ±3.74 | 71.71 ±3.03 | **71.56 ±2.60** |
| FG% | 45.77 ±1.93 | 45.29 ±2.03 | 46.53 ±1.93 | 43.55 ±2.55 | 44.25 ±2.15 | 43.96 ±1.84 |
| **3P%** | 31.13 ±2.81 | 31.57 ±2.77 | 32.01 ±3.37 | 31.52 ±3.42 | 31.13 ±3.52 | 32.68 ±2.39 |
| 3PTA | 34.73 ±1.55 | 36.25 ±1.70 | 34.70 ±1.22 | 34.48 ±1.55 | 34.58 ±1.88 | 35.35 ±1.80 |
| blocks | 10.05 ±0.87 | 9.88 ±1.14 | 10.10 ±1.01 | 10.93 ±1.11 | 10.03 ±1.02 | 11.03 ±1.39 |
| steals | 17.48 ±1.30 | 17.50 ±1.15 | 16.30 ±1.21 | 16.93 ±1.16 | 16.88 ±1.03 | 16.73 ±1.36 |
| OREB | 18.57 ±1.45 | 16.50 ±1.48 | 16.45 ±1.21 | 16.05 ±1.48 | 17.02 ±1.56 | 16.10 ±1.47 |
| OREB share | 28.60% ±1.76 | 25.53% ±1.90 | 26.34% ±1.45 | 24.87% ±1.81 | 26.15% ±1.90 | 25.16% ±1.99 |
| second-chance pts | 7.60 ±1.19 | 6.88 ±1.09 | 8.00 ±1.29 | 6.00 ±0.84 | 6.58 ±1.05 | 6.47 ±1.31 |
| over-the-back in play | 61.50 ±2.68 | 61.35 ±2.42 | 59.52 ±2.54 | 61.48 ±3.04 | 61.77 ±2.94 | 60.35 ±2.39 |
| over-the-back fouls | 2.27 ±0.56 | 1.65 ±0.41 | 2.00 ±0.42 | 1.75 ±0.41 | 2.02 ±0.52 | 2.00 ±0.45 |
| possessions | 42.52 ±1.94 | 44.05 ±1.84 | 42.67 ±1.88 | 44.40 ±2.11 | 43.90 ±2.13 | 43.90 ±1.95 |
| Final Turn shots | 5.80 ±0.44 | 6.25 ±0.50 | 5.85 ±0.47 | 3.17 ±0.17 | 3.12 ±0.13 | 3.10 ±0.12 |
| `:8747` fires | 2.50 ±0.53 | 2.85 ±0.47 | 1.95 ±0.36 | 2.17 ±0.42 | 2.42 ±0.52 | 2.40 ±0.46 |
| draws | 70,476 ±992 | 69,451 ±1,032 | 70,464 ±1,107 | 81,899 ±1,118 | 81,561 ±908 | 81,711 ±747 |
| errors | 0 | 0 | 0 | 0 | 0 | 0 |
| **arm gap** | **+3.16 ±3.45** | **+3.24 ±3.41** | **+4.10 ±4.25** | | | |

**`SEED_DEFENSES=0` (control): every metric identical to three decimal places at every step, and every seed byte-identical — 40/40 on both arms at both steps.** Zone code is never reached with no catalogue, so nothing leaked into the man path.

**Reading this honestly.** Not one metric moved outside its confidence interval, on either arm, at either step. The largest movements are sim pts/team +1.71 across both steps (CI ±3.4) and sim OREB share −2.26 (CI ±1.8, the closest to resolving). The sink is doing what it was designed to do — moving five defenders on ~18% of zone defender-steps — and at n=40 that does not resolve into a measurable outcome change. **Whether it looks right is the eye test, not this table.**

One thing I would not over-read but will name: **3P% rose on both arms at step 2** (sim 31.13 → 32.01, played 31.52 → 32.68). That is the opposite direction from the ring repair, which lowered 3P% on both arms. If both are real, the sink's rim-hungry weak side is giving back some of the perimeter coverage the ring repair gained. Neither is resolved; both are worth watching together rather than separately.

## Defender stacking

Exactly co-located defender pairs, per game, `SEED_DEFENSES=1`:

| arm | baseline | step 1 | step 2 |
|---|---|---|---|
| sim | 324.2 ±23.5 | 287.7 ±19.5 | 307.0 ±19.5 |
| played | 438.8 ±31.5 | 424.5 ±29.4 | 419.7 ±29.0 |

As a share of zone placement steps: sim 6.63% → 6.01% → 6.26%, played 6.30% → 6.04% → 5.99%.

**It falls, but far less than the static sweep implied and not outside the CI.** Stage A measured 8 co-located pairs under current behaviour against 1–2 under the presets across 15 hand-picked cases, and I predicted a clear live drop. What actually happens is a ~5–10% relative reduction that does not resolve at n=40. The static sweep over-stated it because it sampled five canonical ball positions with all five zones empty simultaneously; in real possessions the empty branch fires for one or two defenders at a time, so there are fewer opportunities for two *sink-placed* defenders to collide in the first place. **My Stage A prediction was directionally right and materially over-confident**, and the honest reading is that stacking is not a reason to prefer the sink.

## IQ rolls

| arm | rolls/game | zone possessions/game | rolls per possession | step 1 (must be 0) |
|---|---|---|---|---|
| sim | **290.2 ±10.8** | 58.0 | **5.00** | 0.0 |
| played | **304.9 ±9.9** | 61.0 | **5.00** | 0.0 |

**Exactly five per possession — one per defender — against the ~282/game predicted in Stage A.** Confirmed per-possession, not per-step: per-step rolling would have been ~11,200/game, and the roll is cached against a possession key of (quarter, clock, both team ids) so the several placement builds a turn makes reuse one roll each. Step 1 draws zero, which is what makes the two steps attributable.

**A real bug caught on the way, worth recording.** The first cut rolled whenever `GOB_ZONE_SINK_IQ` was on, regardless of whether the sink was on — so with the sink off the rolls burned draws for a value nothing consumed, moving the fingerprint (`c92c889c…` vs `16d70a85…`) and spending 2,777 extra draws on seed 8000. The roll is now gated on **both** flags. Verified after the fix: with the sink off, both IQ settings give fp `16d70a857a11c905` / 69,231 draws, identical.

## Byte-equality and the gates

**Both arms moved and byte-equality does not hold — 0/40 at both steps on both arms, on `SEED_DEFENSES=1`.** Placement is shared code. Expected, not a regression signal, and not something I attempted to preserve.

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes) | **PASS** — both arms, both footings, identical fp/draws/points/turns |
| FT-honour windowed | sim 99.5% (`=1`) / 99.7% (`=0`); played 99.4% / 99.8% |
| FT-honour strict | 95.8–96.7% |
| **`SEED_DEFENSES=0` control** | **40/40 byte-identical, both arms, both steps** |
| **`GOB_ZONE_SINK=0` escape hatch** | **40/40 reproduces the rings reference on all four cells** |
| errors, 480 games | **0** |

## References

| file | status |
|---|---|
| `equiv_v3_reference_1fd08c080_zonesink.json` | **the reference from now on, for BOTH arms.** Sink on (`shape`), IQ on. |
| `equiv_v3_reference_c1958f8f6_rings.json` | **superseded** — but still exactly what `GOB_ZONE_SINK=0` reproduces, verified 40/40 on all four cells. |
| `equiv_v3_reference_29e6a6792_merged.json` | pre-ring merged tree; unchanged, still separable. |
| `equiv_v3_sim_reference_9910cd6fd.json`, `d9a4f1517` | superseded two passes ago. |

## Not covered

- Rungs 0/a/c/d and the overlap pass: **untouched, and deliberately not pre-empted** — the overlap rung is the next workstream and is being scoped separately. I have avoided drawing conclusions about it here beyond reporting its share.
- `_point_in_zone` / `_point_in_polygon`, the zone spot lists, the crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1, R2 and every balance number: untouched.
- The two sliver zones and the `ZONE_23_UPPER_SHIFT` PG/PF anchor collision: both reported in Stage A, both spot-list questions, both out of scope here and **still open**.
- **A known limit in the IQ wiring, documented in code rather than papered over:** the resolution-side callers of `assign_all_zone_defenders` in `phase_resolution.py` do not pass through `position_zone_defenders`, so one running before a possession's first placement build sees error 0.0 while the render sees the rolled value. Three of the four discard coordinates entirely and keep only the guard map, so the exposure is the legacy fallback at `phase_resolution.py:5485`. Not measured.
- Second-chance points still uses my own definition (points on the turn during or immediately following an offensive rebound) and **remains not comparable** to the 18.40 figure in the flags-on report.
