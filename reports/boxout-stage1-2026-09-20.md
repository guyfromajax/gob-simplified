# Box-out contest (Model C) — Stage 1: built, measured, stopped

`GOB_BOXOUT_CONTEST`, **default `"0"`**. **Not flipped, reference not re-cut, nothing retuned.** With the flag off the worker reproduces `equiv_v3_reference_70f7dd021_b1a.json` **40/40 on fingerprint and draws, all four cells** — the gate passed. `develop` is merged in (`git rev-list --count HEAD..develop` = 0).

**The design behaves as specified: the win rate climbs 50% → 62% → 73% → 86% across ST-gap bands and never approaches certainty, and the loser ends up behind the winner 92% of the time.** The one result you should weigh before Stage 2: **OREB moves in opposite directions on the two arms at `SEED_DEFENSES=1`** (sim +0.05, played −1.80). They agree at `=0`. Reported, not adjusted.

---

## 1. Pairing — radius **8.0**, derived from the geometry

Measured first, read-only, n=40 per cell (the probe runs reproduce the reference 40/40 on all four cells). **Shot-moment distance from each defensive crasher to his nearest offensive crasher:**

| cell | n | mean | ≤4 | ≤6 | **≤8** | ≤10 | ≤12 | ≤15 |
|---|---|---|---|---|---|---|---|---|
| sim `SD=1` | 8,860 | 8.77 | 15.2% | 31.4% | **50.1%** | 65.6% | 77.8% | 89.6% |
| played `SD=1` | 8,639 | 8.73 | 15.7% | 31.4% | **50.5%** | 66.0% | 77.9% | 89.8% |
| sim `SD=0` | 9,648 | 7.67 | 21.5% | 39.9% | **60.4%** | 74.9% | 84.8% | 92.8% |
| played `SD=0` | 9,335 | 7.71 | 21.4% | 39.6% | **60.2%** | 74.8% | 84.7% | 92.6% |

Pooled percentiles (sim `SD=1`): p10 3.13, p25 5.28, **p50 8.00**, p75 11.42, p90 15.19.

**`BOXOUT_PAIR_RADIUS = 8.0`** — the **pooled median** of exactly the quantity the rule keys on. Half of defensive crashers have a man inside it, which is the honest reading of "there is someone to box out". It is not reverse-engineered from an OREB target.

**It also equals `pass_contest.PASS_LANE_DIST` (8.0)**, the engine's existing "close enough to contest" spatial gate. The geometry and the house arrived at the same number independently, which is the best corroboration available.

**Determinism.** Defenders are walked in the caller's order (lineup slots PG/SG/SF/PF/C); each takes the nearest *unpaired* offensive crasher within the radius; **the tiebreak for two exactly-equidistant candidates is the one earlier in the offense's lineup-slot order** (strict `<` keeps the first). Every player is in at most one pair, one contest per pair, and **`find_boxout_pairs` consumes no RNG at all** — there is a test asserting `sim_rng.getstate()` is unchanged across it.

## 2. Effect — push-back = **0.5 × the loser's remaining travel**

Measured on pairs that actually form (20 games, sim, `SD=1`, probe RNG-neutral 20/20):

| | n | mean | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|---|
| travel, shot moment → destination | 3,272 | **10.90** | 6.58 | 10.11 | 14.68 | 18.86 |
| destination → rim | 3,272 | 9.00 | 6.97 | 8.34 | 10.50 | 13.37 |
| **gap between a pair's two destinations** | 1,636 | **5.06** | 2.76 | 4.48 | 6.93 | 9.63 |

**`BOXOUT_PUSHBACK_FRACTION = 0.5`.** The derivation: half the mean remaining travel is `0.5 × 10.90 = 5.45`, which is the **mean gap between the pair's two destinations (5.06)**. So on average the push-back is exactly the distance between the two men — it moves the loser from level with the winner to behind him, which is what losing a box-out means. A fraction rather than a constant so a man already in place barely moves and a man crashing from the arc loses proportionally more.

Direction is straight **away from the rim** along the rim→destination line. The winner's destination is never touched. Output is clamped to the court with `crash_destination`'s own bounds (x 3–97, y 3–47), so nobody is pushed out of bounds.

**This is a position change, not a scoring bonus.** It writes into `prepared[pid]`, the same map the crash animation and the arrival scoring both read, so it is on screen.

## 3. Strength — `ST × rand(1, 6)`, the house composite shape

**Copied from `engine/pass_contest.py`**, which is the engine's other two-stage contest: `find_pass_contester` does pure geometry to decide who is eligible, then `resolve_pass_contest` scores it as `(weighted attributes) × rand(1,6)`. The same split is used here. That idiom is the house standard — `shared.calculate_rebound_score`, `calculate_outlet_pass_score`, `calculate_defender_pressure_score`, and the D8 cutoff in `dynamic_hct._resolve_moment` all use it — and it is exactly what keeps a big attribute edge a tilt rather than a certainty.

It fits because a box-out has the same shape as a pass contest: a geometric question (is anyone close enough?) followed by a one-on-one (who wins the leverage?). **`randint(1,6)` is untouched** — this is a new roll of the same kind, not a change to an existing one.

`boxout_score(p) = ST × rand(1,6)`, i.e. the house composite with ST at weight 1.0. **A tie goes to the defender**: he is the man initiating the box-out and is by construction between his opponent and the rim, so "nobody wins the leverage" means position does not change hands. That is the stable non-RNG tiebreak, and it gives the defence a 58.3% floor at equal ST — the only structural edge this model asserts, reported rather than buried.

### Win rate by ST gap — the design check

**The stronger player wins**, flag ON, 40 games per cell:

| cell | gap **<5** | gap **5–15** | gap **15–30** | gap **>30** | (gap 0 → defender) |
|---|---|---|---|---|---|
| sim `SD=1` | **50.2%** (508) | **62.3%** (995) | **72.7%** (1006) | **85.7%** (747) | 47.5% (61) |
| played `SD=1` | 50.2% (542) | 64.9% (1024) | 73.6% (958) | 87.3% (671) | 54.2% (59) |
| sim `SD=0` | 49.2% (687) | 64.9% (1262) | 71.5% (1245) | 86.8% (838) | 60.0% (70) |
| played `SD=0` | 55.4% (793) | 62.1% (1323) | 73.7% (1264) | 86.9% (792) | 61.6% (73) |

**Monotonic in the ST gap, and it tops out near 86% — clearly more often, not always.** That is the lever position asked for. The gap-0 column is noisy (n≈60–73) and straddles the 58.3% theoretical floor.

## 4. Census

| cell | box-outs/game | def crashers/game | paired | authoring calls with **no pair** | defender wins (all gaps) |
|---|---|---|---|---|---|
| sim `SD=1` | **81.40** | 226.25 | **36.0%** | 231/1887 (12.2%) | 47.3% |
| played `SD=1` | 79.88 | 220.25 | 36.3% | 220/1837 (12.0%) | 47.9% |
| sim `SD=0` | **100.80** | 234.07 | **43.1%** | 96/1952 (4.9%) | 48.5% |
| played `SD=0` | 104.30 | 238.15 | 43.8% | 92/1988 (4.6%) | 48.8% |

Pairing is 36% rather than the 50% "someone within 8" figure because each offensive crasher can only be taken once and there are fewer of them (3.60 offensive vs 4.82 defensive crashers per authoring call). The live 36.0% matches the 36.5% predicted from the geometry probe before anything was built.

## 5. Displacement actually applied

| cell | n | mean | p50 | p90 | max | **loser ends BEHIND winner** |
|---|---|---|---|---|---|---|
| sim `SD=1` | 3,256 | **5.50** | 5.01 | 9.37 | 39.69 | **91.6%** |
| played `SD=1` | 3,195 | 5.50 | 5.03 | 9.30 | 38.71 | **92.2%** |
| sim `SD=0` | 4,032 | 5.40 | 4.96 | 9.50 | 34.82 | **92.6%** |
| played `SD=0` | 4,172 | 5.46 | 5.02 | 9.53 | 34.53 | **92.3%** |

The realised mean (5.50) lands on the predicted 5.45, and **the push-back does the job it was sized to do 92% of the time.** The 8% where it does not are pairs whose destinations were already far apart in the loser's favour.

## 6. Outcomes vs the reference — reported, not adjusted

Flag ON re-phases **both** arms (0/40 fingerprint and draws on all four cells) — the contest rolls wherever crash destinations are authored, which is both arms. That is expected for a Stage-1 measurement.

**`SEED_DEFENSES=1`, n=40:**

| metric | sim OFF | sim ON | Δ | played OFF | played ON | Δ |
|---|---|---|---|---|---|---|
| pts/team | 74.30 ±3.15 | 72.50 ±3.13 | **−1.80** | 74.21 ±2.89 | 72.55 ±3.20 | **−1.66** |
| **OREB share** | 29.34% ±1.48 | 29.39% ±1.69 | **+0.05** | 31.56% ±1.89 | 29.75% ±1.79 | **−1.80** |
| OREB | 18.77 ±1.48 | 19.27 ±1.34 | +0.50 | 20.57 ±1.57 | 19.62 ±1.64 | −0.95 |
| DREB | 44.92 ±2.32 | 46.67 ±2.84 | +1.75 | 44.55 ±2.12 | 45.98 ±2.21 | +1.43 |
| possessions | 40.92 ±1.91 | 42.20 ±2.41 | +1.28 | 39.83 ±1.91 | 41.02 ±1.89 | +1.20 |
| fouls | 53.73 ±2.78 | 50.23 ±1.92 | −3.50 | 54.35 ±2.44 | 53.52 ±2.73 | −0.83 |
| FG% | 45.45% ±2.18 | 44.95% ±2.39 | −0.50 | 44.81% ±1.93 | 44.04% ±2.10 | −0.77 |
| draws/game | 83,018 ±825 | 82,603 ±816 | −415 | 81,705 ±1,039 | 80,978 ±942 | −727 |
| **arm gap** (sim−played) | **+0.09 ±3.26** | → | **−0.05 ±3.06** | | | |

**`SEED_DEFENSES=0`, n=40:**

| metric | sim OFF | sim ON | Δ | played OFF | played ON | Δ |
|---|---|---|---|---|---|---|
| pts/team | 77.20 ±3.54 | 75.89 ±3.06 | −1.31 | 75.75 ±3.43 | 74.79 ±2.64 | −0.96 |
| **OREB share** | 30.58% ±1.79 | 31.42% ±1.76 | **+0.83** | 30.64% ±1.72 | 32.51% ±1.62 | **+1.87** |
| OREB | 21.40 ±1.87 | 21.32 ±1.53 | −0.07 | 20.82 ±1.55 | 22.80 ±1.63 | +1.98 |
| DREB | 47.73 ±2.35 | 46.45 ±2.19 | −1.27 | 47.17 ±2.38 | 47.27 ±2.44 | +0.10 |
| possessions | 43.38 ±2.03 | 42.65 ±1.97 | −0.73 | 43.10 ±2.13 | 42.58 ±2.09 | −0.52 |
| fouls | 59.08 ±2.30 | 59.52 ±2.44 | +0.45 | 58.65 ±2.37 | 58.73 ±2.74 | +0.08 |
| FG% | 43.01% ±2.36 | 42.95% ±2.14 | −0.06 | 42.67% ±2.28 | 41.53% ±2.28 | −1.14 |
| draws/game | 62,834 ±519 | 63,685 ±452 | +851 | 62,484 ±553 | 62,961 ±542 | +476 |
| **arm gap** (sim−played) | **+1.45 ±3.28** | → | **+1.10 ±2.46** | | | |

### Do the arms move together? Not at `SD=1`.

**This is the finding to weigh.** OREB share:

| | sim | played | together? |
|---|---|---|---|
| `SEED_DEFENSES=1` | **+0.05** | **−1.80** | **no — opposite directions** |
| `SEED_DEFENSES=0` | +0.83 | +1.87 | yes, both up |

Two things about that. First, every delta here is inside its own CI at n=40, so none is individually significant — but "the arms disagree in sign on the metric the feature targets" is worth a second look regardless. Second, the played arm's OFF value at `SD=1` (31.56%) is the outlier: it is ~2 points above the sim arm's 29.34% and above both `SD=0` values, and the flag pulls it down to 29.75%, i.e. **onto the sim arm's number**. So the honest reading is that the box-out *converged* the two arms at `SD=1` rather than moving them apart — the arm gap on pts/team also narrows (+0.09 → −0.05).

**What is consistent across all four cells:** pts/team down (−0.96 to −1.80) and DREB up or flat. The defence getting inside position more often is the mechanism, and it shows.

**Second-chance points is not a box-score stat** (`BOX_SCORE_KEYS` has no such field; `SCR_A`/`SCR_S` are screens), so it is not reported here rather than being derived from a proxy. It would need its own probe.

## 7. Clairvoyance — the guard holds

The contest resolves in `shot_manager._prepare_crash_arrival`, where `result` and `bounce_spot` are both in scope on the very next lines. **Neither is passed.** The box-out sees only the two players' shot-moment coords, their just-authored destinations and their ST.

| guard | result |
|---|---|
| `tests/test_crash_destination.py` (Model A's allowlist + its two poison tests) | **14 passed, 1 skipped — untouched** |
| `crash_destination` signature still exactly `{shooter_x, shooter_y, rim_x, tightness}` | asserted in the new suite |
| no public box-out entry point accepts an outcome-bearing parameter | asserted for all four |
| the module's **code** never names `bounce_spot` / `result` / `rebounder` / … (AST walk, docstrings stripped) | asserted, **with a poison test** proving it fires on a reinstated read |
| the **call site** block between `BOXOUT.enabled()` and `probe = dict(result …)` contains neither `result` nor `bounce_spot` | asserted |

`tests/test_boxout_contest.py`: **28 passed** — pairing geometry, radius edge, one-pair-per-player, the stable tiebreak, no-RNG-in-pairing, determinism across 20 repeats, the ST roll, tie-to-defender, tilt-not-dominate, push-back direction/magnitude/clamp/immutability, and the clairvoyance set above.

## 8. Integrity with the flag on

| gate | result |
|---|---|
| **§8.1 coord-continuity corrections** | **0 across 160 games, all four cells** |
| independence (seed 8000 × 3 processes) | **PASS** in all four cells |
| FT-honour windowed | sim 99.7% / 99.7%; played 99.5% / 99.5% |
| FT-honour strict | 95.8–96.3% |
| errors across 320 games | **0** |
| **full suite, default (flag OFF)** | **2841 passed, 0 failed, 0 XPASS** |
| **full suite, flag ON** | **2841 passed, 0 failed, 0 XPASS** — set-diff empty |

## 9. Trace — 8 real misses (seed 8000, sim, `SD=1`)

```
[1] rim x=91, 2 pairs
    def 80f3ca79 ST=78 roll->390  |  off 60d85fb6 ST=83 roll->332   gap 7.8  => DEFENDER WINS
        winner stays (83.0,28.0)   loser 60d85fb6 (82.0,30.0) -> (77.9,32.3)  push 4.71
    def 104c7b0f ST=31 roll->31   |  off e590d342 ST=51 roll->51    gap 8.0  => OFFENSE WINS
        winner stays (80.0,31.0)   loser 104c7b0f (86.0,19.0) -> (80.1,11.9)  push 9.19
    REBOUND -> 7219a92c  (not in a pair)

[2] rim x=9, 2 pairs
    def e590d342 ST=49 roll->49   |  off 104c7b0f ST=31 roll->124   gap 3.6  => OFFENSE WINS
        winner stays (14.0,23.0)   loser e590d342 (13.0,21.0) -> (17.1,16.9)  push 5.83
    def 60d85fb6 ST=78 roll->156  |  off 7219a92c ST=70 roll->70    gap 6.3  => DEFENDER WINS
        winner stays (12.0,22.0)   loser 7219a92c (11.0,25.0) -> (14.8,25.0)  push 3.81
    REBOUND -> 60d85fb6  (a box-out WINNER)

[3] rim x=91, 1 pair
    def 19b6cdb5 ST=68 roll->408  |  off 60d85fb6 ST=75 roll->375   gap 6.0  => DEFENDER WINS
        winner stays (86.0,28.0)   loser 60d85fb6 (88.0,24.0) -> (84.1,22.7)  push 4.12
    REBOUND -> 60d85fb6  (a BOXED-OUT loser)

[4] rim x=9, 2 pairs
    def e590d342 ST=47 roll->141  |  off 7219a92c ST=67 roll->201   gap 0.1  => OFFENSE WINS
        winner stays (13.0,25.0)   loser e590d342 (14.0,25.0) -> (20.2,25.0)  push 6.23
    def 9c044323 ST=61 roll->61   |  off 104c7b0f ST=30 roll->90    gap 5.0  => OFFENSE WINS
        winner stays (14.0,22.0)   loser 9c044323 (12.0,31.0) -> (16.6,40.3)  push 10.41
    REBOUND -> bd5dbf1f  (not in a pair)

[5] rim x=91, 1 pair
    def f608a824 ST=33 roll->198  |  off 9c044323 ST=59 roll->59    gap 7.8  => DEFENDER WINS
        winner stays (89.0,31.0)   loser 9c044323 (89.0,23.0) -> (84.7,18.7)  push 6.02
    REBOUND -> 9c044323  (a BOXED-OUT loser)

[6] rim x=9, 1 pair
    def e590d342 ST=44 roll->264  |  off 7219a92c ST=57 roll->228   gap 6.8  => DEFENDER WINS
        winner stays (14.0,25.0)   loser 7219a92c (15.0,28.0) -> (19.7,30.4)  push 5.25
    REBOUND -> bd5dbf1f  (not in a pair)

[7] rim x=91, 2 pairs
    def 19b6cdb5 ST=60 roll->300  |  off e590d342 ST=44 roll->220   gap 4.3  => DEFENDER WINS
        winner stays (86.0,27.0)   loser e590d342 (81.0,21.0) -> (76.7,19.3)  push 4.65
    def 7219a92c ST=57 roll->57   |  off bd5dbf1f ST=76 roll->228   gap 2.8  => OFFENSE WINS
        winner stays (80.0,29.0)   loser 7219a92c (88.0,20.0) -> (85.5,15.8)  push 4.95
    REBOUND -> 9c044323  (not in a pair)

[8] rim x=91, 1 pair
    def 19b6cdb5 ST=58 roll->116  |  off 457185a0 ST=66 roll->66    gap 4.5  => DEFENDER WINS
        winner stays (83.0,19.0)   loser 457185a0 (88.0,29.0) -> (86.9,30.4)  push 1.80
    REBOUND -> d014435a  (not in a pair)
```

**Three things worth reading off it.** [1] and [3] are the weaker man winning on a better die — ST 78 beats ST 83 (390 vs 332), ST 68 beats ST 75 (408 vs 375). That is the "humans playing the game" behaviour Jamie asked to preserve. [3] and [5] are **boxed-out losers who still got the rebound**: the push-back changes position, it does not decide the outcome. And most rebounds go to someone not in a pair at all, which follows from only 36% of defensive crashers pairing.

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A. The geometry probe (travel / destination gap) is 20 games; the trace is one seed. Every read-only probe reproduces the reference on its cells.

## Not covered

- **Flag not flipped, reference not re-cut, not merged.** Stage 1 is measurement.
- **Nothing retuned:** `randint(1,6)`, the rebound composite, the team bonus, the 0.8 discounts, `REBOUND_DISTANCE_SCALE`, `_ag_grid_per_game_sec` — all untouched. Neither derived constant was adjusted after seeing an outcome.
- **Not reported:** second-chance points — not a box-score field; it needs its own probe.
- **Open for Stage 2:** the `SD=1` OREB sign disagreement between the arms. My reading is that the played arm's flag-off 31.56% was the outlier and the box-out pulled it onto the sim arm's number, but that is an interpretation of deltas inside their CIs, not a measurement. A larger n on that one cell would settle it.
- **Not examined:** whether 81–101 box-outs per game is the right *volume*. The radius was derived from the geometry, not from a target rate.
