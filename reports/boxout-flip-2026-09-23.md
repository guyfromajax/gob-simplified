# `GOB_BOXOUT_CONTEST` flipped ON by default, two-directional — reference re-cut

**Team-level rebounding stayed flat at n=120.** Re-measured at *this* tree, seed-paired,
played arm, `SEED_DEFENSES=1`: OREB **−0.36 ±1.27**, DREB **−0.53 ±1.49**, total rebounds
**−0.88 ±1.95**, OREB share **−0.42 ±1.59**, second-chance points **−0.38 ±1.42** — and in
fact **not one** of the fifteen metrics measured clears its CI. The per-player effect is
still real and still cancels: across 8,792 resolved pairs, P(rebound | box-out winner) is
**14.34% ±0.73** against **8.46% ±0.58** for the loser — **1.69×**, +5.88 pp, CIs that do
not overlap.

**The kill switch and the double re-baseline both held.** `GOB_BOXOUT_CONTEST=0` at the
flipped tree reproduces `equiv_v3_reference_f2a060488_manhelpshade.json` **160/160** on
fingerprint AND draws with every box-out counter at zero, and
`equiv_v3_reference_09f1b0ca9_boxout.json` was then reproduced **160/160** by each of two
further independent full runs.

---

## 0. develop was merged first

develop was 23 commits ahead. It was merged before anything else (fast-forward to
`881e4ac70`; the branch was already in develop). It touches `api.py`,
`franchise_routes.py`, persistence and a large vendored Phaser drop — **no engine or sim
file**. The current reference was re-confirmed at the merged tree before the flip:

| cell | sim | played |
|---|---|---|
| `SEED_DEFENSES=1` | 40/40 | 40/40 |
| `SEED_DEFENSES=0` | 40/40 | 40/40 |

**160/160.** Four untracked `reports/READY-*.md` files blocked the merge; each was
byte-identical to develop's committed copy, so removing the local duplicates lost nothing.

## 1. The outcome evidence

A seed-paired n=120 measurement **had** been run and reported — `reports/boxout-stage2-2026-09-20.md`
§7, `SEED_DEFENSES=1`, four configs, seeds 8000–8119:

| metric (Stage 2, 2026-09-20) | sim | played |
|---|---|---|
| OREB share % | +0.654 ±1.367 | −0.978 ±1.666 |
| OREB | +0.808 ±1.077 | −0.717 ±1.302 |
| DREB | +0.550 ±1.335 | +0.275 ±1.307 |
| pts/team | −0.912 ±2.060 | −0.287 ±1.771 |
| possessions | +0.217 ±1.281 | +0.483 ±1.311 |

Every CI straddled zero. **But those numbers describe a tree four behaviour flips ago** —
the placement freeze, the zone sink escape, the zone help shade and the man help shade have
all shipped since, and the last of them moves exactly the off-ball defenders who then crash
and box out. So it was re-run at the current tree before flipping, with the wider metric set
the brief asked for.

### n=120, seeds 8000-8119, played arm, `SEED_DEFENSES=1`, seed-paired

| metric | OFF | ON | ON − OFF |
|---|---|---|---|
| points / team | 73.53 ±1.93 | 74.03 ±1.77 | +0.50 ±1.99 |
| possessions | 40.11 ±1.18 | 39.53 ±0.92 | −0.57 ±1.44 |
| FGA | 103.18 ±0.95 | 103.72 ±1.00 | +0.53 ±1.17 |
| FG% | 40.95 ±1.08 | 41.04 ±1.15 | +0.10 ±1.19 |
| **OREB** | 18.96 ±0.84 | 18.60 ±0.93 | **−0.36 ±1.27** |
| **DREB** | 45.07 ±1.32 | 44.54 ±1.07 | **−0.53 ±1.49** |
| **total rebounds** | 64.03 ±1.65 | 63.14 ±1.60 | **−0.88 ±1.95** |
| **OREB share** | 29.58 ±1.04 | 29.16 ±1.03 | **−0.42 ±1.59** |
| **second-chance points** | 12.17 ±0.92 | 11.79 ±1.02 | **−0.38 ±1.42** |
| 3PA share | 36.98 ±0.89 | 37.14 ±0.83 | +0.16 ±1.07 |
| paint share | 28.38 ±0.86 | 28.03 ±0.84 | −0.34 ±1.16 |
| steals | 16.81 ±0.69 | 16.80 ±0.71 | −0.01 ±0.92 |
| blocks | 9.80 ±0.61 | 9.61 ±0.53 | −0.19 ±0.76 |
| fouls | 31.76 ±1.13 | 30.98 ±1.20 | −0.78 ±1.45 |
| freeze-miss | 2.17 ±0.27 | 2.17 ±0.31 | +0.00 ±0.40 |

**Nothing clears its CI.** 0 worker errors, 0 census errors, and the flag-OFF box-out
counters total exactly 0.

### The per-player effect, and why it cancels

| | n | rebounds | P(rebound) |
|---|---|---|---|
| box-out **winner** | 8,792 | 1,261 | **14.34% ±0.73** |
| box-out **loser** | 8,792 | 744 | **8.46% ±0.58** |

**1.69×**, a +5.88 pp gap whose CIs do not overlap — squarely in the 1.7–2.0× band Stage 2
reported. It cancels at team level because the contest is **symmetric**: the defender won
48.3% of 8,792 contests, so for every defensive crasher who gains ground there is an
offensive crasher who does too, at almost exactly the same rate. Rebounding is redistributed
between individuals, not shifted between teams. That is the model behaving as designed, and
it is why team rebounding does not move.

Team rebounding stayed inside its CI, so the flip proceeded.

## 2. The flip

`BackEnd/utils/boxout_contest.py`, commit **`09f1b0ca9`** — the default only (one file, 7
insertions):

```
-    return os.environ.get("GOB_BOXOUT_CONTEST", "0") == "1"
+    return os.environ.get("GOB_BOXOUT_CONTEST", "1") == "1"
```

| state | `enabled()` |
|---|---|
| no env var | **True** |
| `GOB_BOXOUT_CONTEST=0` | False |
| `GOB_BOXOUT_CONTEST=1` | True |

Verified untouched after the flip: `BOXOUT_SCORE_WEIGHTS` {RB .4, ST .4, IQ .1, CH .1}
(sum 1.0), `BOXOUT_PUSHBACK_FRACTION` 0.5, `BOXOUT_PAIR_RADIUS` 8.0, and `randint(1, 6)`.
**Two-directional stays** — the defender is not privileged and can be the one pushed back.
Every other flag keeps its current default (`GOB_REBOUND_FROM_ARRIVAL`, `GOB_PLACEMENT_FREEZE`,
`GOB_PLACEMENT_SINGLE_BUILD`, `GOB_MAN_HELP_SHADE`, `GOB_ZONE_HELP_SHADE`,
`GOB_ZONE_SINK_ESCAPE` all ON; `GOB_REBOUND_RACE` still OFF).

## 3. Kill switch, before the re-cut

`GOB_BOXOUT_CONTEST=0` at `09f1b0ca9` vs `equiv_v3_reference_f2a060488_manhelpshade.json`:

| cell | sim | played |
|---|---|---|
| `SEED_DEFENSES=1` | 40/40 | 40/40 |
| `SEED_DEFENSES=0` | 40/40 | 40/40 |

**160/160 on fingerprint AND draws**, and across all 160 games every box-out counter —
defenders seen, pairs, contests, pushbacks, radius binds — reads **0**. The contest is
genuinely absent, not merely numerically coincident.

## 4. The re-cut and the double re-baseline

`equiv_v3_reference_09f1b0ca9_boxout.json` — n=40 seeds 8000-8039, both arms, both
`SEED_DEFENSES`, standard equiv-v3 footing.

| independent run | fp + draws vs the new reference |
|---|---|
| run 2 (`rb1`) | **160/160** |
| run 3 (`rb2`) | **160/160** |

Arm gap (sim − played, paired): `SEED_DEFENSES=1` **+3.638 ±3.861**, `SEED_DEFENSES=0`
**+2.025 ±3.210**.

### How each footing moved, and why

| cell | arm | fp differing | draws differing | pts/team before → after (paired) |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | 40/40 | 40/40 | 75.08 → 74.70 (−0.38 ±2.93) |
| `SEED_DEFENSES=1` | played | 40/40 | 40/40 | 73.03 → 71.06 (−1.96 ±3.17) |
| `SEED_DEFENSES=0` | sim | 40/40 | 40/40 | 80.74 → 77.84 (−2.90 ±3.16) |
| `SEED_DEFENSES=0` | played | 40/40 | 40/40 | 75.44 → 75.81 (+0.38 ±3.50) |

**Both footings move completely, and that is the expected pattern.** The box-out is
**scheme-independent**: it keys on crasher geometry at the shot moment, not on man vs zone,
so an empty defense catalogue does not exempt `SEED_DEFENSES=0` the way it exempted the zone
help shade. The counters confirm the mechanism rather than just the outcome:

| cell | arm | defenders seen | pairs formed | pair rate | radius binds | bind rate |
|---|---|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | 8,660 | 3,101 | 35.8% | 4,325 | 49.9% |
| `SEED_DEFENSES=1` | played | 8,687 | 2,983 | 34.3% | 4,425 | 50.9% |
| `SEED_DEFENSES=0` | sim | 9,143 | 3,671 | **40.2%** | 3,837 | **42.0%** |
| `SEED_DEFENSES=0` | played | 8,869 | 3,496 | 39.4% | 3,797 | 42.8% |

SD=0 pairs *more* and binds the radius *less* — the all-man footing packs crashers slightly
tighter, so more defenders have someone inside 8.0. Nothing here is unexplained. The n=40
points deltas all straddle zero and are consistent with the authoritative n=120 result above.

## 5. Gates at the new default

Sim arm, `SEED_DEFENSES=1`, seeds 8000-8009:

| | new default | kill switch |
|---|---|---|
| same-moment gate | 69,120 / 69,120 = **100%**, max 0.000 | 68,050 / 68,050 = **100%**, max 0.000 |
| §8.1 continuity corrections | **0** of 1,748 calls | **0** of 1,884 calls |
| errors | 0 | 0 |

**Box-out counters per game** (n=120, played, SD=1, flag ON): **73.3 pairs formed**, 73.3
contests resolved, **73.2 push-backs applied** (99.8% of contests — the remainder are losers
already standing on their destination, who by design do not move). Of 25,143 defenders seen,
35.0% formed a pair and **50.8% had their nearest offensive crasher outside
`BOXOUT_PAIR_RADIUS`** — the radius binds about half the time, which is exactly what a
constant set to the *median* of that distance should do. Defender wins **48.3%**.

**Freeze-miss** (n=120, played, SD=1): kill switch 2.17 ±0.27, new default 2.17 ±0.31,
paired **+0.00 ±0.40**. At the reference cells (n=40): sim −0.17 ±0.57, played −0.57 ±0.84.
Nothing clears.

**Rebound-from-arrival and the placement freeze are unaffected.** `GOB_REBOUND_FROM_ARRIVAL`
is still ON and `GOB_REBOUND_RACE` still OFF; the flip changed one file and one default, and
the box-out only rewrites a loser's crash *destination* — the arrival model then reads those
destinations exactly as before. Placement-freeze blocked writes are unchanged: 114 → 116 per
game on the sim arm, 116 → 115 on the played arm.

## 6. Suite

| run | result |
|---|---|
| `tests/` at the new default | 3242 passed, 20 skipped, 112 xfailed, **0 XPASS**, 3 failed |
| `tests/` under `GOB_BOXOUT_CONTEST=0` | 3242 passed, 20 skipped, 112 xfailed, **0 XPASS**, 3 failed |

**The three failures are inherited from develop, not from this flip** — verified identical at
`881e4ac70` (the merge commit, before the flip) in a clean worktree, and identical with the
kill switch on:

| test | cause |
|---|---|
| `test_generate_ball_tween_flag.py::test_ball_tween_respects_flag` | shells out to `node`; `ERR_MODULE_NOT_FOUND` because `node_modules` is absent |
| `test_run_pass_tween_flag.py::test_run_pass_respects_flag` | same |
| `test_screenshot_tool.py::test_retired_capture_runtime_cannot_be_reintroduced_silently` | develop's vendored `phaser-3.60/3.70.esm.js` contain `preserveDrawingBuffer`; the guard does not exclude `FrontEnd/static/js/vendor/` |

I could not clear the first two here: there is no `package-lock.json`, so `npm ci` cannot
run, and reshaping the repo's JS tooling is not this brief. The third is a one-line exclusion
in develop's own guard. **All three are flagged rather than absorbed; none is box-out.**

Box-out tests: **39 pass**. `tests/test_boxout_contest_flags.py` is new (default ON, kill
switch, two-directional, d6 intact, constants reused not copied, tie to the defender);
`tests/test_boxout_contest.py::test_flag_defaults_off` became `test_flag_defaults_on` with no
other assertion relaxed.

## 7. references/README.md

- `equiv_v3_reference_f2a060488_manhelpshade.json` → **Superseded**, reproduced today by
  **`GOB_BOXOUT_CONTEST=0`**.
- `equiv_v3_reference_09f1b0ca9_boxout.json` → **Current**, `09f1b0ca9` (2026-09-23).
- **Nothing deleted.** All **15** reference files on disk are listed (verified: 1 `## Current`,
  1 `## Superseded`, 0 missing).

---

## Tunable Constants

Reported, not changed. The flip moved a default, not a number.

| constant | value | effect | note |
|---|---|---|---|
| `GOB_BOXOUT_CONTEST` | **`"1"` (flipped)** | gates the contest; `=0` is the rollback | |
| `BOXOUT_SCORE_WEIGHTS` | RB .4, ST .4, IQ .1, CH .1 | the contest score, × d6 | sums to 1.0; **the one place to edit for tuning** |
| `BOXOUT_PAIR_RADIUS` | 8.0 | how close a crasher must be to be boxed out | DERIVED: pooled median crasher-to-crasher distance. Binds on 50.8% of defenders — as a median should |
| `BOXOUT_PUSHBACK_FRACTION` | 0.5 | share of the loser's remaining travel he is pushed back | DERIVED: half of a mean 10.90 travel ≈ the 5.06 gap between a pair's destinations |
| the die | `randint(1, 6)` | keeps an attribute edge a tilt, not a certainty | untouched |
| tie-break | tie → defender | the one structural edge the model asserts | 48.3% defender win rate overall |

**A note for whoever tunes these:** `find_boxout_pairs` and `push_back` take their constant
as a **default argument**, bound once at import. Editing the constant in source works;
monkeypatching the module attribute at runtime does not reach it. The tests pin the binding
so no literal can be inlined.

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps
5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed-8000)`, n=40 seeds 8000-8039, CI = 1.96 × SEM. sim arm = `_is_full_simulation`
True throughout; played arm = False only inside the four gated Animator methods at Pattern A.
**Catalogue-seeded state:** `SEED_DEFENSES=1` seeds the six real defenses from
`defenses_export.json`; `SEED_DEFENSES=0` leaves the catalogue empty, so every zone call plays
man — which here means slightly *tighter* crasher spacing and a *higher* pair rate, not an
exemption. Outcomes n=120 seeds 8000-8119, played arm, SD=1, seed-paired. Runs at the new
default set no `GOB_BOXOUT_CONTEST` at all, so they walk the shipped default.

The box-out census wraps `find_boxout_pairs` and `ShotManager._prepare_crash_arrival`, calls
the original first, and only reads inputs, the returned pairs and the existing `_boxout_log`
— it draws nothing. Proved, not asserted: every reference-reproduction run above had the
census **on**.

1,120 games: 160 merge re-confirmation + 240 outcomes + 160 kill switch + 480 re-cut and
double re-baseline, plus 40 probe games. **0 errors.**

**Not merged. Jamie merges.**
