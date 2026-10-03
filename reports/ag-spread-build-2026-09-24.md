# The defender AG spread at s = 0.50, built behind a flag

**The built spread landed exactly on the priced numbers.** Measured from the runs' own
endpoints: placements ending short **31.73% → 35.17%** against a prediction of 35.1%, and the
p10-AG vs p90-AG endpoint gap on the same step **0.66 → 3.49** on `standard`, **0.26 → 1.69** on
`sprint`, **0.11 → 0.62** on `cruise` — the three predictions were 3.49, 1.69 and 0.62.

**Step duration is genuinely unchanged: mean T moves +0.32%**, against the **+11.2%** the same
band costs when applied to the shared rate function. The pacing trap is avoided by construction,
and the ordering that guarantees it is now pinned by a test rather than by convention.

**Nothing moved on the scoreboard.** At n=120 seed-paired, not one of eleven metrics clears its
CI — points −0.38 ±1.25, FG% −0.19 ±0.84, paint share −0.10 ±0.71. Cosmetic-tier, exactly as
the sweep predicted.

> **⚠️ DO NOT FLIP THIS YET.** The brief specified two call sites for the endpoint. There are
> **eighteen**, across five modules. I wired ten (~76% of the interrupt mass); the rest are in
> `dynamic_hct.py` and `fcp_offball_attack.py`. With the flag ON that leaves the rendered motion
> disagreeing with the simulated endpoint on **7.8%** of defender movements, against 0.03%
> today. Details and cost in §6. The flag ships **OFF** and the OFF path is byte-identical, so
> nothing is at risk — but it is not ready for a flip.

Reference used: **`equiv_v3_reference_1f4af0ede_loosesag_nogate.json`**. develop has not moved.
A second agent's deny-jitter work is on `feature/deny-jitter` in its own worktree and was not
touched.

---

## 1. What was built

Commits `0ebac3824` (wrapper + spread), `92a5c2aa4` (tests), `33d2e5171` (the additional call
sites).

```python
DEFENDER_AG_SPREAD = 0.50
scale(AG) = (1 - s) + (AG / 100) * 2s          # midpoint fixed at AG=50
```

`defender_movement_rate(player, archetype, is_defender)` in
[animation_step_helpers.py](BackEnd/utils/animation_step_helpers.py) is the single source of
truth. Flag off, or any offensive player, and it returns `_ag_grid_per_game_sec` **itself** —
not a re-derivation — so there is no second implementation to drift.

**Proved, not asserted:**

| property | evidence |
|---|---|
| `s = 0.10` is byte-identical to the shipped formula | equal on **1,015 / 1,015** comparisons (7 archetypes × AG 0-144) |
| AG=50 unchanged at every `s` | checked at s = 0.10 / 0.25 / 0.50 / 0.75 / 1.00 |
| offence untouched at every `s` | same sweep, `is_defender=False` |
| the spread is absent from the shared rate functions | source assertion on `_ag_grid_per_game_sec` and `ag_to_grid_per_game_sec` |
| T is frozen before the spread is applied | source-ordering assertion: `rates` → `t = max(...)` → `defender_movement_rate` |
| no new RNG | `sim_rng.getstate()` unchanged across 21 calls |

Rates at s=0.50 on `standard`: AG 24 → 10.36, AG 39 → 12.46, **AG 50 → 14.00 (unchanged)**,
AG 73 → 17.22, AG 144 → 27.16. League p90/p10 rate ratio **1.103 → 1.662**.

Untouched: archetype bases (8 / 13 / 14 / 18 / 32), `STANDARD_GRID_PER_GAME_SEC` 14, the
`[0.5, 60]` clamp — applied to the standard-equivalent rate and then scaled by archetype, which
is exactly what the shipped pair does and is *why* s=0.10 agrees byte-for-byte. Nothing retuned.
Every other flag keeps its default.

## 2. Acceptance

| check | result |
|---|---|
| reference with the flag **OFF**, all four cells | **160/160** on fingerprint AND draws |
| reference with the flag **ON** | **39/160** unchanged, 121 seeds differ — **not re-cut** |
| draws added by the build | **none** |

The ON row is reported, not acted on. On the 39 seeds whose fingerprint is unchanged, the **draw
count is also unchanged** — which is the evidence that the build adds no RNG: where gameplay
does not diverge, the draw stream is identical. Where it does diverge, draw counts move because
different contests are rolled, not because new draws were introduced.

That 39 of 160 seeds resolve identically despite thousands of moved defender positions is itself
informative: the fingerprint hashes result types, next-turn transitions and score, not
positions. A quarter of games can have every defender in a different place and still play out
the same way.

## 3. Geometry — measured against what was priced

n=40 seeds 8000-8039, both arms, SD=1. Measured from each run's own stamped endpoints.

| | flag OFF | flag ON | predicted ON |
|---|---|---|---|
| moving placements ending short | 31.73% | **35.17%** | 35.1% |
| mean shortfall (grid) | 21.20 | 21.24 | — |
| p90 shortfall | 53.47 | 53.73 | — |

**p10-AG vs p90-AG endpoint gap, same step, same archetype:**

| archetype | OFF | ON | predicted |
|---|---|---|---|
| **standard** | 0.66 | **3.49** | 3.49 |
| **sprint** | 0.26 | **1.69** | 1.69 |
| **cruise** | 0.11 | **0.62** | 0.62 |

Changing proximity band **2.44%**, crossing the 11 gate **1.14%** — the predictions exactly.
(These two and the gap columns are computed analytically over the captured steps, which is the
same arithmetic the sweep used; the "ends short" row and everything in §4-§5 is measured from
the runs.)

**The build is what was priced.** Every prediction landed inside a rounding place.

## 4. The pacing trap — the important negative result

| | steps | mean step T | vs OFF |
|---|---|---|---|
| flag OFF | 221,037 | 1.0757 | — |
| flag ON | 220,696 | 1.0791 | **+0.32%** |

Against **+11.2%** for the same band applied to `_ag_grid_per_game_sec`. The spread cannot reach
step duration because it is applied in the `final_end_coords` loop, after `t` is frozen and
after `natural_t` has already been consumed by the gate — and
`test_step_duration_is_computed_before_the_spread_is_applied` asserts that ordering in source,
so a later edit that moves the call earlier fails the suite rather than silently slowing the game.

## 5. Gates, CPU and outcomes

| gate (sim, SD=1, seeds 8000-8009) | OFF | ON |
|---|---|---|
| same-moment | 69,440/69,440 = **100%**, max 0.000 | 68,730/68,730 = **100%**, max 0.000 |
| §8.1 continuity corrections | **0** of 1,858 | **0** of 1,855 |
| errors | 0 | 0 |

**CPU** — interleaved, n=40, sim arm, nothing else running:

| | placement ms/game | calls/game | % of wall |
|---|---|---|---|
| OFF | 525.8 ±19.8 | 51,075 | 10.08% |
| ON | 526.7 ±18.9 | 51,074 | 9.44% |

**Paired ON − OFF: +0.9 ms/game ±17.1 — does not clear.** A spread is arithmetic and costs
nothing, as expected, and it agrees with the 510.7 ±19.4 baseline. Wall time reads +0.365 s
±0.350, which marginally clears; I do not attribute that to the spread, because placement time
and call counts are identical to within 1 call — the ON games simply resolve differently.

**Outcomes** — n=120 seeds 8000-8119, played arm, SD=1, seed-paired, 0 errors:

| metric | OFF | ON | ON − OFF |
|---|---|---|---|
| points / team | 74.83 ±1.55 | 74.44 ±1.66 | −0.38 ±1.25 |
| possessions | 38.70 ±1.01 | 39.07 ±1.06 | +0.37 ±0.83 |
| FG% | 40.99 ±0.99 | 40.80 ±1.07 | −0.19 ±0.84 |
| 3PA share | 36.65 ±0.82 | 36.56 ±0.92 | −0.09 ±0.77 |
| paint share | 27.63 ±0.85 | 27.54 ±0.91 | −0.10 ±0.71 |
| rim-attempt share | 4.32 ±0.35 | 4.30 ±0.39 | −0.03 ±0.29 |
| steals | 16.06 ±0.73 | 15.97 ±0.69 | −0.09 ±0.58 |
| deflections | 8.67 ±0.56 | 8.77 ±0.57 | +0.10 ±0.41 |
| blocks | 9.51 ±0.54 | 9.79 ±0.56 | +0.28 ±0.54 |
| fouls | 30.98 ±1.06 | 31.69 ±1.17 | +0.72 ±0.88 |
| freeze-miss | 2.26 ±0.28 | 2.26 ±0.29 | +0.00 ±0.25 |

**Nothing clears.** Fouls (+0.72 ±0.88) and blocks (+0.28 ±0.54) lean the way you would expect
from defenders arriving in more varied places, but neither separates. Nothing was retuned.

## 6. ⚠️ The problem: the endpoint is not in one place

The brief named two call sites, and my own sweep report §7 said the same. **Both were wrong, and
the measurement found it.** `_interrupted_coord` — the function that decides where a rate-limited
defender actually stops — fires **9,706 times per game from eighteen call sites across five
modules**:

| site | share of interrupt mass | wired? |
|---|---|---|
| `dynamic_hct_step_emitter.py:346` | 25.1% | ✅ |
| `transition_bridge.py:851` | 17.5% | ✅ |
| `transition_bridge.py:363` *(the one both documents named)* | 14.6% | ✅ |
| `transition_bridge.py:595` | 8.9% | ✅ |
| `dynamic_hct.py:1932` | 8.5% | ❌ |
| `transition_bridge.py:675` | 7.9% | ✅ |
| `dynamic_hct.py:2014` | 7.2% | ❌ |
| `dynamic_hct.py:2578` | 3.1% | ❌ |
| `fcp_offball_attack.py:364` | 1.9% | ❌ |
| `transition_bridge.py:1083`, `:1183`, `reset_step_helper` ×3 | ~2.2% | ✅ |
| `dynamic_hct.py` ×4 more, `dynamic_hct_step_emitter` ×2 | ~2.9% | ❌ |

**Why it matters.** `stamp_tween_durations` writes one duration for *every* moving player, so
wiring it wires the render everywhere. Wiring only one endpoint site widened the render on ~100%
of defender movements and the endpoint on 14.6% — so `duration × rate` stopped equalling the
distance covered on **18.22%** of movements. That is precisely the failure the brief said must
not happen, in mirror image: the animation stops matching the game.

Wiring the ten sites that share the same local pattern (a `rate = _ag_grid_per_game_sec(...)`
directly above an `_interrupted_coord`, with the offence test already in scope) brought it down:

| | tween/endpoint mismatches | worst |
|---|---|---|
| flag OFF | 194 / 645,259 = **0.030%** | 17.34 grid |
| flag ON, one site wired | 119,136 / 653,900 = **18.22%** | 24.42 grid |
| flag ON, ten sites wired *(current)* | 51,402 / 659,245 = **7.80%** | 24.43 grid |

The 0.030% at flag OFF is **pre-existing**, not introduced here: a handful of builders stamp a
tween capped at T for a distance the player's rate cannot cover, so the sprite is already
slightly ahead of its own speed on those steps.

**What closing it costs.** The remaining sites are in `dynamic_hct.py` (21.5%) and
`fcp_offball_attack.py` (1.9%). They do not share the local shape — the rate is derived
differently and the offence/defence test is not always in scope — so each needs reading rather
than a mechanical swap. I judged that to be the "separate task Jamie has filed" and stopped
rather than open a module of that size unasked. **Estimate: half a day, and it should be done
before any flip**, because a 7.8% render/simulation disagreement is exactly the class of defect
the animation-cleanup project exists to remove.

## 7. Pictures

- [ag-spread-off-2026-09-24.png](reports/ag-spread-off-2026-09-24.png)
- [ag-spread-on-2026-09-24.png](reports/ag-spread-on-2026-09-24.png)

Same four steps in both, one per seed, chosen for a long `standard` move with a wide AG split.
Blue = start, red square = endpoint, grey × = the target, dotted = the full demand; labels give
each defender's AG and the grid units he actually covered.

The clearest panel is seed 8008 step 689: the **AG 11** defender covers **56.8 → 44.7** grid
units when the spread is on, while the **AG 94** defender beside him is unchanged at 54.5. Same
step, same demand, twelve units of separation that did not exist before. Seed 8003 step 707 shows
the same shape, AG 14 dropping from 56.8 to 44.5 alongside an unchanged AG 94.

## 8. Tests and suite

`tests/test_defender_ag_spread_flags.py`, 15 tests. Beyond the defaults and the kill switch they
pin: byte-identity at s=0.10; the preserved midpoint; `DEFENDER_AG_SPREAD` reused not copied;
offence untouched; the spread's **absence** from the shared rate functions; the source ordering
that keeps T out of reach; that **the endpoint and the tween read the same wrapper** and the
tween has not reverted to the raw rate; an end-to-end check that `duration × rate` equals what
`_interrupted_coord` says was covered; and that the wrapper draws no RNG.

| suite | result |
|---|---|
| `tests/` with the flag OFF | **3288 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** |
| `tests/` with `GOB_DEFENDER_AG_SPREAD=1` | **3288 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** |

---

## Tunable Constants

Reported, not changed.

| constant | value | effect |
|---|---|---|
| `GOB_DEFENDER_AG_SPREAD` | `"0"` | gates the spread; built and measured, **not flipped** |
| `DEFENDER_AG_SPREAD` | **0.50** | the band half-width; 0.10 reproduces today byte-for-byte |
| archetype bases | 8 / 13 / 14 / 18 / 32 | unchanged |
| `STANDARD_GRID_PER_GAME_SEC` | 14 | curve anchor, unchanged |
| rate clamp | `[0.5, 60]` | unchanged; nothing clamps for a defender at s=0.50 |
| `ag_to_grid_per_game_sec` | `0.90 + AG/100 × 0.2` | **deliberately untouched** — it feeds step T |

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed−8000)`, CI = 1.96 × SEM. Geometry n=40 seeds 8000-8039, **both arms**,
**`SEED_DEFENSES=1`**; the reference checks cover SD 1 and 0. Outcomes n=120 seeds 8000-8119,
played arm, seed-paired. All other flags at their shipped defaults.

The census wraps `stamp_tween_durations` (rebound in all seventeen modules that import the name
by value) and calls the original first, reading only arguments and return values. Proved, not
asserted: the instrumented flag-OFF run reproduces the reference fingerprint **and** draw count
exactly, 160/160.

**An earlier CPU measurement in this session was discarded**: it ran alongside picture
generation and returned 713.7 ms ±226.3 on a 7.04 s wall against a 5.15 s baseline. It was
re-run with nothing else on the machine; only the clean numbers appear above.

1,120 games: 320 reference (OFF and ON, four cells each) + 240 outcomes + 80 CPU + 40 probes,
plus the discarded contended batch. **0 errors.**

**Flag OFF. Nothing merged. Not ready to flip — see §6.**
