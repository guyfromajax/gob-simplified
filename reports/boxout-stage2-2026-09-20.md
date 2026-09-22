# Box-out Stage 2 — the contest score becomes a composite

**One change: `boxout_score` is now `(0.4·RB + 0.4·ST + 0.1·IQ + 0.1·CH) × randint(1,6)`.** Nothing else moved — pairing, push-back, two-directional, tie-to-defender and the `randint(1,6)` roll itself are all untouched. `GOB_BOXOUT_CONTEST` **stays default `"0"`**; the flag was not flipped, the reference was not re-cut, nothing was merged, nothing retuned.

**The weights live in `BOXOUT_SCORE_WEIGHTS` in `BackEnd/utils/boxout_contest.py`** — a module-level dict, the one place the tuning pass needs to edit. It sums to 1.0, which is the house contract for a composite that gets multiplied by a d6.

## Headline

| | Stage 1 (pure ST) | **Stage 2 (composite)** |
|---|---|---|
| win rate by gap band | 50.2 / 62.3 / 72.7 / **85.7%** | 57.3 / 63.2 / 73.0 / **87.5%** |
| defender win rate, all gaps | 47.3% | **48.5%** |
| P(rebound \| winner) vs loser, sim `SD=1` | 15.57% vs 8.97% — **1.74×** | 16.07% vs 8.10% — **1.98×** |
| box-outs/game, pair rate | 81.4, 36.0% | 79.1, **35.6%** |
| RB top-quartile share of rebounds | 70.28% | **66.97%** (flag OFF: 67.16%) |
| OREB share, n=120 paired | sim +0.139 ±1.422 | sim **+0.654 ±1.367** |

**The model still behaves. The compounding risk did not materialise. OREB still does not resolve.**

---

## 1. Win rate by composite-gap band

Flag ON, n=40, the stronger composite wins:

| cell | **<5** | **5–15** | **15–30** | **>30** | gap 0 (→ defender) |
|---|---|---|---|---|---|
| sim `SD=1` | **57.3%** (621) | **63.2%** (1027) | **73.0%** (1066) | **87.5%** (448) | 71.4% (7) |
| played `SD=1` | 60.6% (703) | 62.4% (977) | 72.2% (1031) | 88.3% (445) | 33.3% (6) |
| sim `SD=0` | 61.7% (830) | 60.6% (1375) | 72.5% (1275) | 84.4% (531) | 46.7% (15) |
| played `SD=0` | 59.8% (914) | 62.9% (1427) | 73.5% (1307) | 85.0% (534) | 66.7% (12) |

**Monotonic in three of four cells and topping out at 84–88% — well short of certainty.** (`sim SD=0` dips 61.7 → 60.6 between the first two bands; both have wide enough counts that this is ordinary sampling noise, and every other cell rises cleanly.)

### The `<5` band looks like it moved. It did not — that is a measurement artefact, and worth naming

Stage 1's `<5` band read **50.2%**; it now reads **57.3%**. Nothing about close contests changed. The cause is **exact ties**:

- Under pure ST both scores were **integers**, so `ST_d × a == ST_o × b` happened often — 61 gap-0 pairs in the `<5` band of 508.
- The band counts "the **stronger** player wins", and at gap 0 there is no stronger player, so those pairs entered the denominator and could never enter the numerator. That dragged the band down by roughly 12% × 58% ≈ 7 pp.
- Composites are **floats**, so exact ties are now vanishingly rare — **7 gap-0 pairs in 621**. The artefact disappears, and 50.2 + 7 ≈ 57.3.

**A real consequence follows from the same fact:** the tie-to-defender rule has lost almost all of its effect, because it now almost never fires. Under pure ST it gave the defence a 58.3% floor at equal ST; that floor is gone. The gap-0 column above is now too sparse (6–15 pairs) to mean anything.

## 2. Defender win rate, and why it sits below 50%

| cell | defender wins | | RB | ST | IQ | CH | **composite** |
|---|---|---|---|---|---|---|---|
| sim `SD=1` | **48.5%** | defenders | 42.79 | 44.00 | 52.65 | 49.17 | **44.90** |
| | | crashers | 44.58 | 46.21 | 51.84 | 49.93 | **46.49** |
| played `SD=1` | 46.9% | defenders | 43.73 | 44.72 | 52.83 | 49.06 | 45.57 |
| | | crashers | 45.95 | 47.37 | 52.55 | 50.17 | 47.60 |
| sim `SD=0` | 48.6% | defenders | 43.40 | 44.68 | 53.00 | 49.24 | 45.45 |
| | | crashers | 45.77 | 47.00 | 51.77 | 50.78 | 47.36 |
| played `SD=0` | 48.8% | defenders | 44.00 | 45.26 | 53.37 | 49.37 | 45.98 |
| | | crashers | 45.93 | 47.41 | 52.25 | 49.60 | 47.52 |

**It barely moved: 47.3% → 48.5%.** And the attribute means say why it is below 50% at all, under either score: **the defensive crasher pool is systematically weaker than the offensive crasher pool** — RB 42.79 vs 44.58, ST 44.00 vs 46.21, composite **44.90 vs 46.49**, a ~1.6-point deficit that is consistent across all four cells. Defenders do score better on IQ (52.65 vs 51.84), but at weight 0.1 that recovers little.

So the defence loses the contest slightly more often than it wins because the players who end up crashing on defence are simply worse at the four attributes involved — not because of anything in the contest design. The 1.2 pp rise from Stage 1 is the tie-rule effect draining away (§1) partly offset by defenders' small IQ edge now counting.

## 3. Per-player effect — held, and on the primary cell it grew

P(gets the rebound), among paired players only:

| cell | score | winner | loser | difference | ratio |
|---|---|---|---|---|---|
| sim `SD=1` | **composite** | **16.07% ±1.28** | **8.10% ±0.95** | **+7.97 pp ±1.59** | **1.98×** |
| sim `SD=1` | pure ST | 15.57% ±1.25 | 8.97% ±0.98 | +6.60 pp ±1.59 | 1.74× |
| played `SD=1` | **composite** | 14.83% ±1.24 | 8.75% ±0.99 | +6.08 pp ±1.58 | **1.70×** |
| played `SD=1` | pure ST | 15.12% ±1.24 | 9.36% ±1.01 | +5.76 pp ±1.60 | 1.62× |
| sim `SD=0` | **composite** | 15.11% ±1.11 | 8.93% ±0.88 | +6.18 pp ±1.42 | **1.69×** |
| sim `SD=0` | pure ST | 15.55% ±1.12 | 8.61% ±0.87 | +6.94 pp ±1.41 | 1.81× |
| played `SD=0` | **composite** | 15.02% ±1.08 | 8.11% ±0.83 | +6.91 pp ±1.36 | **1.85×** |
| played `SD=0` | pure ST | 14.12% ±1.06 | 8.94% ±0.87 | +5.18 pp ±1.37 | 1.58× |

**The effect held: 1.69–1.98× under the composite against 1.58–1.81× under pure ST.** It is larger in three of four cells, and largest on the primary cell (sim `SD=1`, 1.98×). But the per-cell CIs on the difference are ±1.4–1.6 pp and the composite-vs-ST gaps are 0.3–1.7 pp, so **no individual cell separates the two scores** — the honest claim is that the effect is at least as strong, not that it improved.

The pure-ST column is a **fresh measurement, not a memory**: the probe monkeypatches `boxout_score` back to Stage 1's `ST × rand(1,6)` for those runs, so both scores were measured on this tree with the same harness.

## 4. Census — unchanged, as it must be

| cell | score | box-outs/game | **pair rate** | push mean | p50 | p90 |
|---|---|---|---|---|---|---|
| sim `SD=1` | composite | 79.05 | **35.6%** | 5.55 | 5.01 | 9.64 |
| sim `SD=1` | pure ST | 81.40 | **36.0%** | 5.50 | 5.01 | 9.37 |
| played `SD=1` | composite | 78.90 | **35.8%** | 5.43 | 4.96 | 9.28 |
| played `SD=1` | pure ST | 79.88 | **36.3%** | 5.50 | 5.03 | 9.30 |
| sim `SD=0` | composite | 100.28 | **42.7%** | 5.36 | 4.97 | 9.34 |
| sim `SD=0` | pure ST | 100.80 | **43.1%** | 5.40 | 4.96 | 9.50 |
| played `SD=0` | composite | 104.55 | **43.3%** | 5.44 | 5.01 | 9.51 |
| played `SD=0` | pure ST | 104.30 | **43.8%** | 5.46 | 5.02 | 9.53 |

**Pair rate is the invariant to check, and it moves by at most 0.5 pp in every cell.** Push-back statistics are likewise flat (mean 5.36–5.55, p50 4.96–5.03). The small box-outs/game differences are not a pairing change — they are the games themselves diverging: a different contest winner means a different push-back, a different rebound, a different possession, and from there a different game with a slightly different number of shot attempts. Pairing is pure geometry and it did not change.

## 5–6. Compounding — the risk did not materialise

The concern was that a composite close to the rebound composite (`RB·.5 + ST·.3 + IQ·.1 + CH·.1`) would let good rebounders win the box-out *and* score well on the board, concentrating rebounds. Three-way, per team-game, 80 team-games per cell, rosters of 12 so the top quartile is 3 players:

**Share of team rebounds taken by the top quartile by RB:**

| cell | flag OFF | pure ST (old) | **composite (new)** | OFF → composite |
|---|---|---|---|---|
| sim `SD=1` | 67.16% ±2.34 | 70.28% ±2.09 | **66.97% ±2.89** | **−0.19 pp** |
| played `SD=1` | 68.24% ±2.42 | 69.19% ±2.09 | **68.80% ±2.02** | +0.56 pp |
| sim `SD=0` | 65.52% ±3.00 | 65.42% ±2.36 | **66.05% ±2.48** | +0.54 pp |
| played `SD=0` | 68.25% ±2.14 | 67.46% ±2.35 | **68.76% ±2.36** | +0.51 pp |

**Rebounds per game for the single highest-RB player on each team:**

| cell | flag OFF | pure ST (old) | **composite (new)** | OFF → composite |
|---|---|---|---|---|
| sim `SD=1` | 7.81 ±0.95 | 8.43 ±0.88 | **8.54 ±0.92** | +0.72 |
| played `SD=1` | 8.85 ±0.91 | 8.84 ±0.85 | **8.43 ±0.74** | −0.42 |
| sim `SD=0` | 9.04 ±0.98 | 9.09 ±0.88 | **8.72 ±0.85** | −0.31 |
| played `SD=0` | 9.26 ±0.91 | 9.00 ±1.02 | **9.21 ±1.10** | −0.05 |

**Not material.** Top-quartile share moves between −0.19 and +0.56 pp against CIs of ±2.0–3.0; the top rebounder's count moves between −0.42 and +0.72 against CIs of ±0.74–1.10, and changes sign across cells. Nothing here is distinguishable from noise, and the composite is not systematically more concentrating than pure ST.

**Why it does not concentrate, mechanically:** per `reports/zone-crash-and-arrival-cap-2026-09-20.md`, the contest is two-directional and near a coin flip, so a good rebounder is about as likely to be the *defensive* crasher who wins a box-out as the offensive one. Winning displaces an opponent on either team equally often, so the extra rebounds a strong rebounder wins on one end are offset by the ones he denies at the other. Concentration would be the thing to re-check first if the model ever goes one-directional.

## 7. OREB share, n=120 seed-paired (`SEED_DEFENSES=1`)

Stage 1.5 established that n=40 cannot resolve a 1–2 point move on this metric, so this is the only OREB number quoted. Seeds 8000–8119, four configs, seed-paired, 0 errors:

| metric | sim ON−OFF | played ON−OFF | difference-of-deltas |
|---|---|---|---|
| **OREB share %** | **+0.654 ±1.367** | **−0.978 ±1.666** | **+1.631 ±2.143** |
| OREB | +0.808 ±1.077 | −0.717 ±1.302 | +1.525 ±1.629 |
| DREB | +0.550 ±1.335 | +0.275 ±1.307 | +0.275 ±1.784 |
| pts/team | −0.912 ±2.060 | −0.287 ±1.771 | −0.625 ±2.503 |
| possessions | +0.217 ±1.281 | +0.483 ±1.311 | −0.267 ±1.768 |

Cell means: sim 29.26 ±0.92 → **29.91 ±1.02**; played 29.66 ±1.06 → **28.68 ±1.12**.

**Every CI straddles zero, including the difference-of-deltas.** The point estimates are larger than Stage 1.5's under pure ST (+0.139 / −0.316), and they lean the same way the raw pattern did — sim up, played down — but the CIs are the same width, so **nothing is resolved.** On the evidence, **the composite does not move the team-level rebound split either**, which is the answer `zone-crash-and-arrival-cap` predicted: the contest is symmetric, so per-player effects cancel at team level regardless of what score decides them.

## Gates

| gate | result |
|---|---|
| **flag OFF vs `equiv_v3_reference_70f7dd021_b1a.json`** | **40/40 fingerprint AND draws, all four cells**, 0 errors |
| **§8.1 per-player coord-continuity corrections** | **0 across 160 flag-ON games** |
| **clairvoyance** | `crash_destination.py` and `tests/test_crash_destination.py` **untouched** (`git diff` empty), **14 passed / 1 skipped**. The contest still reads only the two players' shot-moment coords, their destinations and their attributes; the AST guard asserting the box-out module's code never names `result`/`bounce_spot`/`rebounder` still passes, with its poison test. |
| FT-honour windowed / strict | 99.4–99.7% / 95.3–96.9% |
| **errors** | **0 across 160 flag-ON reference games and 0 across the 480 census games** |
| **full suite** | **2850 passed, 0 failed, 0 XPASS** |

### Which test assertions changed, and why

`tests/test_boxout_contest.py`, 28 → **30 passed**:

- **`test_score_is_st_times_a_d6` → `test_score_is_the_weighted_composite_times_a_d6`.** It asserted `score ∈ {ST × 1..6}`; that is no longer what the function computes. It now builds a player with four *different* attributes (RB 80, ST 40, IQ 20, CH 60 → composite 56.0) and asserts `score ∈ {56.0 × 1..6}` with all six values seen. Strictly stronger: the old version could not have caught a wrong weight, because every attribute was equal.
- **`_P` gained `rb`/`iq`/`ch`, defaulting to `st`.** A `_P(..., st=N)` now has composite `== N`, so every existing single-attribute test still reads as written and still tests a real composite gap. No assertion was relaxed to accommodate this.
- **`test_strength_tilts_but_does_not_dominate` → `test_the_composite_tilts_but_does_not_dominate`.** Same thresholds (`edge > even`, `big > edge`, `big < 90.0`); only the name and messages changed, because the gap it varies is now a composite gap.
- **Two new tests.** `test_the_weights_are_named_sum_to_one_and_are_the_only_tuning_surface` pins `BOXOUT_SCORE_WEIGHTS` and its sum to 1.0. `test_rebounding_now_counts_where_it_did_not_before` asserts a better rebounder beats an equally strong man on the same die — the property Stage 2 exists to add, which would have been impossible to state under pure ST.

**Nothing was weakened.** The pairing, push-back, tie, determinism, no-RNG-in-pairing and clairvoyance assertions are all byte-identical.

## 8. Trace — eight box-outs, seed 8000, sim, `SD=1`

`composite = 0.4·RB + 0.4·ST + 0.1·IQ + 0.1·CH`; `score = composite × rand(1,6)`.

```
[1] pair gap 7.81
    DEF 80f3ca79  RB  87 ST  78 IQ  59 CH  63  -> comp 78.20 x d6 5 =  391.0
    OFF 60d85fb6  RB  88 ST  83 IQ  65 CH  22  -> comp 77.10 x d6 4 =  308.4   => DEFENDER WINS
    loser 60d85fb6 pushed (82.0,30.0) -> (77.9,32.3)   4.71 units

[2] pair gap 8.00
    DEF 104c7b0f  RB  24 ST  31 IQ  92 CH   5  -> comp 31.70 x d6 1 =   31.7
    OFF e590d342  RB  57 ST  51 IQ  63 CH  55  -> comp 55.00 x d6 1 =   55.0   => OFFENSE WINS
    loser 104c7b0f pushed (86.0,19.0) -> (80.1,11.9)   9.19 units

[3] pair gap 3.61
    DEF e590d342  RB  55 ST  49 IQ  63 CH  55  -> comp 53.40 x d6 1 =   53.4
    OFF 104c7b0f  RB  24 ST  31 IQ  92 CH   5  -> comp 31.70 x d6 4 =  126.8   => OFFENSE WINS
    loser e590d342 pushed (13.0,21.0) -> (17.1,16.9)   5.83 units

[4] pair gap 6.33
    DEF 60d85fb6  RB  82 ST  78 IQ  65 CH  22  -> comp 72.70 x d6 2 =  145.4
    OFF 7219a92c  RB  77 ST  70 IQ  49 CH  75  -> comp 71.20 x d6 1 =   71.2   => DEFENDER WINS
    loser 7219a92c pushed (11.0,25.0) -> (14.8,25.0)   3.81 units

[5] pair gap 6.00
    DEF 19b6cdb5  RB  43 ST  68 IQ  37 CH  35  -> comp 51.60 x d6 6 =  309.6
    OFF 60d85fb6  RB  80 ST  75 IQ  65 CH  22  -> comp 70.70 x d6 5 =  353.5   => OFFENSE WINS
    loser 19b6cdb5 pushed (86.0,28.0) -> (85.1,28.5)   1.00 units

[6] pair gap 0.13
    DEF e590d342  RB  52 ST  47 IQ  63 CH  55  -> comp 51.40 x d6 3 =  154.2
    OFF 7219a92c  RB  73 ST  67 IQ  49 CH  75  -> comp 68.40 x d6 3 =  205.2   => OFFENSE WINS
    loser e590d342 pushed (14.0,25.0) -> (20.2,25.0)   6.23 units

[7] pair gap 5.00
    DEF 9c044323  RB  75 ST  61 IQ  60 CH  48  -> comp 65.20 x d6 1 =   65.2
    OFF 104c7b0f  RB  23 ST  30 IQ  92 CH   5  -> comp 30.90 x d6 3 =   92.7   => OFFENSE WINS
    loser 9c044323 pushed (12.0,31.0) -> (16.6,40.3)  10.41 units

[8] pair gap 7.81
    DEF f608a824  RB  51 ST  33 IQ  64 CH  23  -> comp 42.30 x d6 6 =  253.8
    OFF 9c044323  RB  73 ST  59 IQ  60 CH  48  -> comp 63.60 x d6 1 =   63.6   => DEFENDER WINS
    loser 9c044323 pushed (89.0,23.0) -> (84.7,18.7)   6.02 units
```

**Three things to read off it.** [1] is the composite doing its job — two near-identical big men (78.20 vs 77.10) separated by one pip. [7] and [8] are the die overruling a large composite edge in both directions (65.20 loses to 30.90; 42.30 beats 63.60), which is the "humans playing the game" behaviour the d6 is there for. [2] and [3] are the *same pair* on different possessions with the roles reversed — 104c7b0f (RB 24, ST 31, IQ 92) is a poor box-out player whose high IQ barely helps at weight 0.1, and he is pushed back 9.19 units in [2] before winning [3] on a 4.

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` True throughout; **played arm** = False only inside the four gated Animator methods at Pattern A. §1–6 and the gates are n=40 seeds 8000–8039 per cell; §7 is n=120 seeds 8000–8119, `SEED_DEFENSES=1`, seed-paired. The pure-ST comparison is a live re-measurement on this tree, not a quote from Stage 1. All probes are read-only; the concentration figures come from the final box score and consume no RNG.

## Not covered

- **Flag not flipped, reference not re-cut, not merged.**
- **Two-directional kept**, per the brief — Jamie eye-tests it this way before deciding on one-directional. That decision remains the live lever on the team-level split, per `zone-crash-and-arrival-cap-2026-09-20.md`.
- **Nothing else retuned:** rebound composite, team bonus, the 0.8 discounts, `REBOUND_DISTANCE_SCALE`, `_ag_grid_per_game_sec`, `BOXOUT_PAIR_RADIUS`, `BOXOUT_PUSHBACK_FRACTION` — untouched.
- **Not resolved:** whether the composite beats pure ST on any metric. Every per-cell difference between the two scores is inside its CI; the composite is at least as good, and better basketball, but this pass cannot call it better by the numbers.
- **Not measured:** whether the loss of the tie-to-defender floor (§1) matters. It was worth ~8 pp at exactly-equal ST under integers and is now near-dead; nothing downstream appeared to notice, but it was not probed directly.
