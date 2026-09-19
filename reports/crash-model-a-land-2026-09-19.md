# Crash Model A — Stage 2: landed at tightness 0.7

**Lead: the mismatch closed on the x axis in every band, the y axis stayed flat as Stage 1 predicted, and the live euclidean medians came in *worse* than predicted in the short bands for a reason worth knowing.**

Live, `SEED_DEFENSES=1`, n=40, sim arm — crasher destination vs the bounce that shot actually produced:

| band | n | **x median** | **y median** | **euclidean median** | Stage 1 predicted |
|---|---|---|---|---|---|
| 0–10 rim | 2,689 | 4.0 → **3.0** | 4.0 → 4.0 | 7.3 → **6.3** | 4.0 |
| 10–18 short | 5,118 | 4.0 → **2.0** | 5.0 → 4.0 | 7.6 → **6.1** | 4.0 |
| 18–26 mid | 7,354 | 6.0 → **3.0** | 5.0 → 5.0 | 8.9 → **7.3** | **7.3** |
| 26–40 long | 2,629 | 8.0 → **4.0** | 5.0 → 6.0 | 10.8 → **8.5** | 9.8 |

Played agrees within a tenth on every cell (x 4.5→2.5, 4.0→2.0, 6.0→3.0, 7.0→4.0; euclidean 7.6→6.3, 7.3→6.3, 9.1→7.2, 10.8→8.2).

**The x error stops growing with shot distance** — before it ran 4.0 → 8.0 across the bands, now 3.0 → 4.0. That was the stated target and it is met. **The y axis is unchanged**, exactly as Stage 1 said it would be: today's y box was already centred on the rim's y=25 and only mis-scaled, so there was no location error to fix.

**Why the short bands missed the prediction (6.3 against 4.0), and the mid band hit it exactly.** Stage 1 sampled the *distance model* on both sides — crasher and ball. Live, the ball's side is frequently **not** the distance model. `bounce_spot` is overridden by `block_spot_used` and by the fast-break path, which bypass `calculate_bounce_spot` entirely. Measured: in the rim band the live bounce reaches **p90 18.2 and max 23.8** units from the rim, against a model band that cannot exceed **8**; in the short band, max **64.8**. Across all bands, **3.0% of bounces land more than 30 units from the rim** — distances the distance model cannot generate for a short shot. Model A samples only the distribution it is allowed to know about, so it cannot match a bounce that was never drawn from it. **That is the model behaving correctly under a prediction that was too clean**, not a shortfall in the model.

**The 40+ deep band does not appear** — fewer than 100 live samples at n=40, so it is omitted rather than reported thin.

## Footing (rule 6e)

- **Branch `feature/animation-reward`.** Tightness `5fdb6001e`, flag flip `bf7ed1181`, reference `2354f8966`.
- equiv-v3 worker, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- **Flag-off integrity: 40/40 identical to `equiv_v3_reference_d91679bef_foulweight.json` on all four cells**, 0 probe errors across 320 measured games + 12 gate games.
- Probe: `s2/probe.py` (session scratchpad, uncommitted) — a delegating RNG proxy plus counters; forwards every attribute so draw order is untouched.

## 2. Draws — call-neutral, not draw-neutral, and the brief's expectation was not achievable

| arm | | crashers/game | **randint CALLS / crasher** | underlying draws / crasher | total draws/game |
|---|---|---|---|---|---|
| sim | before | 732.4 | **2.000** | 3.443 | 69,528 |
| sim | after | 728.5 | **2.000** | 3.198 | 69,230 |
| played | before | 713.9 | **2.000** | 3.468 | 80,885 |
| played | after | 701.9 | **2.000** | 3.225 | 81,805 |

**The design property holds exactly: two `randint` calls per crasher, before and after, measured live.** But the raw draw counter moves, and the brief's "must be unchanged" was not reachable by any model of this shape. The reason is `randint` itself: it rejection-samples via `_randbelow`, so the number of underlying `getrandbits` calls depends on the **width of the range**. Measured directly:

| range | values | draws per call |
|---|---|---|
| `randint(85, 92)` legacy x | 8 | 1.997 |
| `randint(20, 30)` legacy y | 11 | 1.455 |
| `randint(2, 4)` Model A x, rim | 3 | 1.332 |
| `randint(8, 21)` Model A x, deep | 14 | 1.142 |
| `randint(-10, 10)` Model A y, deep | 21 | 1.524 |

Legacy pair: **3.454**. Model A's shot-dependent pairs: **3.20** on average. **Nothing else changed** — the per-crasher call count is identical and the difference is fully accounted for by range width. I corrected the docstring that claimed draw-neutrality rather than leaving the wrong claim in the code.

## 3. UESS 8.1 coord-continuity guard — stayed at zero

| arm | | guard calls/game | **corrections over 40 games** |
|---|---|---|---|
| sim | before | 192.3 | **0** |
| sim | after | 190.1 | **0** |
| played | before | 184.4 | **0** |
| played | after | 188.2 | **0** |

**Zero in every cell**, against ~190 live invocations a game. Crashers are now sent further and more variably than before and the guard still has nothing to correct.

## 4. Outcome table

**`SEED_DEFENSES=1` (production), n=40:**

| metric | sim before | sim after | Δ | played before | played after | Δ |
|---|---|---|---|---|---|---|
| **pts/team** | 71.83 ±3.25 | 70.29 ±3.24 | −1.54 | 73.21 ±2.39 | 70.28 ±3.37 | −2.94 |
| OREB | 16.75 ±1.20 | 17.27 ±1.20 | +0.52 | 14.50 ±1.26 | 17.27 ±1.34 | **+2.77** |
| **OREB share** | **26.34% ±1.60** | **26.35% ±1.60** | **+0.00** | 23.28% ±1.82 | 26.06% ±1.67 | **+2.77** |
| second-chance pts | 7.90 ±1.24 | 7.67 ±1.16 | −0.23 | 6.15 ±1.04 | 5.65 ±0.75 | −0.50 |
| over-the-back in play | 60.40 ±2.80 | 62.60 ±2.24 | +2.20 | 59.05 ±2.25 | 62.52 ±2.19 | +3.48 |
| over-the-back fouls | 1.90 ±0.36 | 1.62 ±0.35 | −0.27 | 1.95 ±0.41 | 2.08 ±0.37 | +0.13 |
| FG% | 44.62 ±2.16 | 44.08 ±1.94 | −0.55 | 44.96 ±1.77 | 42.72 ±2.25 | −2.24 |
| possessions | 44.15 ±2.29 | 44.15 ±1.83 | 0.00 | 44.55 ±1.97 | 44.55 ±1.74 | 0.00 |
| draws | 69,528 ±1,012 | 69,230 ±1,059 | −298 | 80,885 ±769 | 81,805 ±1,040 | +921 |
| **arm gap** | **−1.39 ±3.46** | **+0.01 ±3.67** | | | | |

**`SEED_DEFENSES=0`:** sim pts +0.88, played −0.70; OREB share sim +0.28, played −1.79; over-the-back essentially flat; arm gap −1.43 → +0.15. Nothing outside CI except played's OREB share.

**Over-the-back rose on both arms (+2.20 sim, +3.48 played)** — expected and stated up front, since it reads rendered positions and crashers now spread out.

## 5. The rebounder check — sim confirms the prediction, played does not

**On sim the prediction holds exactly: OREB share 26.34% → 26.35%, a change of +0.00.** `select_rebounder_by_score` runs at `:2483`, before crash authoring at `:2550`, so moving the destinations cannot move the selection — and it did not.

**On played it moved +2.77 (23.28% → 26.06%), which is outside the CI and which the brief says to chase.** What I established:

- It is not a systematic bias: on `SEED_DEFENSES=0` played moved the **other way** (−1.79).
- The played arm's *before* value (23.28%) was the outlier — sim sat at 26.34% before and both arms land at ~26.1–26.4% after. The flag brought played into line with sim rather than pushing it somewhere new.
- **There are rebound paths that filter candidates by proximity to the bounce, reading `player.coords`:** `_filter_lineup_by_max_x_delta_from_bounce` (free-throw rebounds, `shared.py:2142`, `ft_step_emitter.py:971`), `NEAR_BOUNCE_REBOUND_ATTEMPTOR_DISTANCE` (`shared.py:1399`, `:1905`) and `FAST_BREAK_REBOUND_GEO_DISTANCE` (`shot_manager.py:2387`, `:2406`). Crash destinations are written onto `player.coords` by the crash applier, so these filters see different candidate sets once destinations move.

**That is a mechanism, not a confirmed cause.** I did not isolate it to the +2.77, and I am not claiming it explains the whole move. It is exactly the class of thing the brief warned about — something downstream reading crash positions — and it is now named and located rather than left as "unknown". Given sim is flat and played is not, the next question is why those proximity filters bite on one arm and not the other; that needs its own pass.

## Byte-equality and gates

**Both arms moved; byte-equality does not hold — 0/40 on all four cells.** Placement changed. Expected, not attempted.

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes) | **PASS** — both arms, both footings |
| FT-honour windowed | sim 99.8% / 99.6%; played 99.8% / 99.7% |
| FT-honour strict | 95.5–97.0% |
| errors, 320 measured + 12 gate games | **0** |
| **`GOB_CRASH_SHOT_AWARE=0` escape hatch** | **40/40 reproduces the previous reference on all four cells** |
| crash-destination guard tests | **14 passed, 1 skipped** |

## References

| file | status |
|---|---|
| **`equiv_v3_reference_bf7ed1181_crashmodela.json`** | **the reference from now on, for both arms.** Crash model on at tightness 0.7. |
| `equiv_v3_reference_d91679bef_foulweight.json` | **superseded** — but exactly what `GOB_CRASH_SHOT_AWARE=0` reproduces, verified 40/40. |
| `equiv_v3_reference_1fd08c080_zonesink.json` and earlier | superseded, as previously recorded. |

## Not covered

- `select_rebounder_by_score`, the `randint(1, 6)`, the selection order and `uses_shot_arc`: untouched. **The reorder is the next workstream.**
- `crash_destination.py`'s allowlisted signature and the two poisoned tests: unchanged.
- Branch 3 (never fires), get-back and release destinations, the zone work, the foul system, the crash-apply flags, `animator.py:1213`, R1, R2: untouched. **No balance number changed and nothing was retuned.**
- **Not resolved:** the +2.77 OREB-share move on played. Mechanism candidates named and located; not isolated.
- **Not resolved:** why the 40+ deep band is too thin to report at n=40, and whether it behaves like the long band.
- **Not investigated:** the 3.0% of bounces beyond 30 units from the rim (block spots and the fast-break path). They are the reason Model A cannot close the short-band gap further, and whether *they* are correct is a separate question.
