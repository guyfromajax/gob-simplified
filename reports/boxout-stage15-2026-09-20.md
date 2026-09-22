# Stage 1.5 — settling the `SEED_DEFENSES=1` OREB sign disagreement

**Measurement only. No engine code was changed** — `git status` was clean of tracked modifications before this pass and after it. `GOB_BOXOUT_CONTEST` stays default `"0"`. Nothing flipped, nothing re-cut, nothing retuned, not merged.

## The question

Stage 1 (`reports/boxout-stage1-2026-09-20.md`) measured the box-out contest at n=40 and found OREB share moving in **opposite directions on the two arms** at `SEED_DEFENSES=1` — sim **+0.05**, played **−1.80** — while both rose at `=0`. Every one of those deltas sat inside its own CI, so the disagreement may be nothing.

My Stage 1 reading was that the played arm's flag-OFF 31.56% was the outlier and the contest pulled it onto the sim arm's number. **That was an interpretation of deltas inside their CIs, not a measurement.** This pass settles it.

The reason Stage 1 could not: it compared two independently-estimated means, each carrying its own ±1.5–1.9 CI. All four configs here run the **same seed list**, so every comparison below is **per-seed paired** — the seed-to-seed variance cancels and the CI on the quantity of interest is far tighter than on either mean.

## Pre-registered decision rule

**Written before the runs completed and not adjusted afterwards.** The primary metric is OREB share; the other metrics are reported but do not drive the verdict.

> **GREEN — the disagreement was noise, Stage 2 may flip:**
> the per-seed ON−OFF OREB-share delta has the **same sign on both arms**, **or**
> the two arms' deltas differ by an amount whose **paired CI straddles zero**;
> **AND** the arm gap does not widen — the OFF→ON change in |arm gap| is **≤ 0**, or its **CI straddles zero**.
>
> **RED — investigate before flipping:**
> the two arms' OREB-share deltas differ with a **paired CI that excludes zero**, **or**
> the arm gap **widens** with a **CI that excludes zero**.
>
> **If RED: do not start fixing.** Trace only far enough to name the mechanism — which arm's crash destinations differ at the moment the contest resolves, and why — and stop with the finding.

## Method

Same harness and footing as Stage 1 (rule 6e). equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, **`SEED_DEFENSES=1` only**, CI = 1.96 × SEM. **sim arm** = `_is_full_simulation` True throughout; **played arm** = False only inside the four gated Animator methods at Pattern A.

**n=120, seeds 8000–8119, four configs** (sim/played × flag OFF/ON) = **480 games**, run in three seed blocks of 40 so a partial result stays usable.

## Verdict: **GREEN** — the Stage 1 disagreement was noise

Under the rule above: the two arms' OREB-share deltas differ by **0.455 ±1.963**, a paired CI that **straddles zero**; and the arm gap **does not widen** — its OFF→ON change is **−0.062 ±1.096**, negative and straddling zero. Both conditions met.

**The single most convincing number is not in the rule.** Run the three seed blocks separately and the "disagreement" **reverses direction**:

| block | seeds | sim ON−OFF | played ON−OFF | difference-of-deltas |
|---|---|---|---|---|
| **b1** | 8000–8039 | +0.049 | **−1.804** | **+1.853 ±3.196** |
| **b2** | 8040–8079 | −0.197 | **+1.681** | **−1.878 ±3.436** |
| **b3** | 8080–8119 | +0.575 | −0.838 | +1.413 ±3.529 |

Block b1 *is* Stage 1 — same seeds, same numbers. Block b2 shows the **played arm rising and the sim arm falling**, the exact opposite pattern. A quantity whose sign reverses between adjacent 40-seed blocks, with every block's CI straddling zero, is not measuring anything.

**A second demonstration, accidental but decisive.** One game errored (below), and excluding it moves the sign of the pooled result:

| | sim ON−OFF | played ON−OFF | same sign? |
|---|---|---|---|
| n=120 (all seeds) | −0.046 ±1.456 | −0.557 ±1.646 | **yes, both negative** |
| **n=119 (primary, seed 8093 excluded)** | **+0.139 ±1.422** | **−0.316 ±1.590** | no |

**One 19-turn stub game flips the sign of the headline.** That is what a ±1.4 CI on a quantity of magnitude 0.1–0.3 means in practice.

## Correcting my Stage 1 reading

My Stage 1 interpretation was that played's flag-OFF 31.56% was an outlier **and that the contest pulled it onto the sim arm's number**. The first half is right; **the second half is not supported and I withdraw it.**

| OREB share, `SEED_DEFENSES=1` | Stage 1 (n=40) | **Stage 1.5 (n=119)** |
|---|---|---|
| sim, flag OFF | 29.34 ±1.48 | **29.32 ±0.92** |
| sim, flag ON | 29.39 ±1.69 | **29.46 ±0.96** |
| played, flag OFF | **31.56 ±1.89** | **29.66 ±1.07** |
| played, flag ON | 29.75 ±1.79 | **29.35 ±1.11** |

Stage 1's played flag-OFF **31.56%** sits **1.90 points above** the n=119 value of 29.66% — an n=40 artifact, confirmed. But the four cell means at n=119 are **29.32 / 29.46 / 29.66 / 29.35**, a spread of **0.34** with CIs of ±1.0 that overlap completely. There was no convergence to observe, because there was no divergence: **the box-out contest does not move OREB share on either arm.** Stage 1's +0.05 and −1.80 were both noise around approximately zero.

## Results, n=119 (seed 8093 excluded), `SEED_DEFENSES=1`

### 1. Per-seed ON−OFF delta, within each arm

| metric | sim ON−OFF | +ve | played ON−OFF | +ve | same sign |
|---|---|---|---|---|---|
| **OREB share %** | **+0.139 ±1.422** | 62/119 | **−0.316 ±1.590** | 60/119 | no |
| OREB | +0.420 ±1.115 | 64/119 | −0.319 ±1.275 | 57/119 | no |
| DREB | +0.790 ±1.471 | 64/119 | −0.143 ±1.258 | 53/119 | no |
| pts/team | −0.592 ±2.012 | 50/119 | +0.038 ±1.824 | 63/119 | no |
| possessions | +0.588 ±1.370 | 57/119 | −0.092 ±1.275 | 53/119 | no |
| FG% | −0.588 ±1.119 | 55/119 | +0.178 ±1.119 | 57/119 | no |
| fouls | −0.513 ±1.994 | 56/119 | −0.723 ±1.901 | 56/119 | yes |
| draws/game | +324.7 ±776.4 | 62/119 | +273.6 ±780.8 | 60/119 | yes |

**Every CI straddles zero.** The seed-positive counts hover at 50–54% throughout, which is what a null effect looks like; the only metric with a visible lean is pts/team on the sim arm (50/119 positive) and even that CI covers zero comfortably.

### 1b. Do the two arms' deltas differ?

Per-seed `(sim ON−OFF) − (played ON−OFF)`:

| metric | difference-of-deltas | CI excludes 0? |
|---|---|---|
| **OREB share %** | **+0.455 ±1.963** | **no — straddles 0** |
| OREB | +0.739 ±1.516 | no |
| DREB | +0.933 ±1.837 | no |
| pts/team | −0.630 ±2.559 | no |
| possessions | +0.681 ±1.769 | no |
| FG% | −0.766 ±1.531 | no |
| fouls | +0.210 ±2.733 | no |
| draws/game | +51.1 ±1042.5 | no |

**Not one metric shows the arms responding differently.**

### 2. Arm gap (sim − played), and its OFF→ON change

| metric | gap OFF | gap ON | change in \|gap\| | verdict |
|---|---|---|---|---|
| **OREB share %** | −0.345 ±1.433 | +0.110 ±1.334 | **−0.062 ±1.096** | CI straddles 0 |
| OREB | −0.387 ±1.064 | +0.353 ±1.042 | −0.067 ±0.839 | CI straddles 0 |
| DREB | +0.084 ±1.448 | +1.017 ±1.363 | −0.227 ±1.232 | CI straddles 0 |
| pts/team | +0.462 ±1.941 | −0.168 ±1.848 | −0.563 ±1.699 | CI straddles 0 |
| possessions | +0.538 ±1.479 | +1.218 ±1.240 | −0.462 ±1.191 | CI straddles 0 |
| FG% | +0.618 ±1.145 | −0.148 ±1.159 | +0.064 ±0.981 | CI straddles 0 |
| fouls | −0.479 ±1.958 | −0.269 ±1.827 | −0.261 ±1.574 | CI straddles 0 |
| draws/game | +1025.5 ±801.9 | +1076.6 ±734.4 | −53.5 ±666.4 | CI straddles 0 |

**No metric's arm gap widens.** Six of eight point estimates are negative (narrowing); none is significant.

### 3. The four cell means

| metric | sim OFF | sim ON | played OFF | played ON |
|---|---|---|---|---|
| **OREB share %** | 29.32 ±0.92 | 29.46 ±0.96 | 29.66 ±1.07 | 29.35 ±1.11 |
| OREB | 18.50 ±0.82 | 18.92 ±0.80 | 18.88 ±0.93 | 18.56 ±0.94 |
| DREB | 44.44 ±1.30 | 45.23 ±1.36 | 44.35 ±1.13 | 44.21 ±1.19 |
| pts/team | 74.27 ±1.92 | 73.68 ±1.80 | 73.81 ±1.61 | 73.85 ±1.62 |
| possessions | 40.49 ±1.16 | 41.08 ±1.18 | 39.95 ±1.05 | 39.86 ±1.04 |
| FG% | 45.95 ±1.27 | 45.36 ±1.33 | 45.33 ±1.13 | 45.51 ±1.20 |
| fouls | 52.02 ±1.57 | 51.50 ±1.36 | 52.50 ±1.52 | 51.77 ±1.41 |
| draws/game | 82,534 ±549 | 82,859 ±563 | 81,509 ±581 | 81,782 ±559 |

**A Stage 1 finding that did not survive.** Stage 1 reported pts/team down 1.66–1.80 on both arms and fouls down 3.50 on sim. At n=119 those are **−0.59 / +0.04** and **−0.51 / −0.72**, all straddling zero. The consistent-looking drops at n=40 were noise as well. I am flagging this against my own Stage 1 write-up, which presented them as "consistent across all four cells".

## The pairing bought less than the brief expected — and it is worth saying why

The brief's premise was that a paired CI would be "far tighter" than differencing two independent means. Measured, on OREB share at n=119:

| | CI on the difference-of-deltas |
|---|---|
| unpaired (differencing two independent means) | ±2.133 |
| **paired (per-seed deltas)** | **±1.963** |
| | **8.0% narrower** |

**Pairing helps only marginally here, and the reason is structural:** the box-out consumes RNG, so flipping the flag **re-phases the stream**. The ON and OFF runs for a given seed are *different games* sharing only their initial conditions (rosters, schedule, seed-derived setup) — not the same game with one variable changed. Most of the seed-to-seed variance the pairing is meant to cancel has already diverged by the first possession.

This does not change the verdict — it was reached on a CI that straddles zero either way — but it does bound what this pass can claim. See the power note below.

## What this pass can and cannot claim

**Can:** there is no detectable difference between how the two arms respond to the box-out contest, on any of the eight metrics, at n=119.

**Cannot:** that no difference exists. The paired CI on the OREB-share difference-of-deltas is **±1.96**, so an arm-to-arm difference smaller than about **2 OREB-share points** would not be visible here. The observed difference is **0.46**. What is ruled out is a difference of the size Stage 1 appeared to show (**1.85**) — that one is now inside the noise, and the block-level sign reversal shows why.

## Integrity

| check | result |
|---|---|
| flag-OFF, seeds 8000–8039, **sim** vs `equiv_v3_reference_70f7dd021_b1a.json` | **fp 40/40, draws 40/40** |
| flag-OFF, seeds 8000–8039, **played** vs the same reference | **fp 40/40, draws 40/40** |
| seeds 8040–8119 | **no reference entry exists** — the references are cut at n=40, seeds 8000–8039. These 80 seeds were **not** scored against a reference; they are used only for the paired ON−OFF comparisons, which are self-contained. Stated rather than silently skipped. |
| independence spot-check, seed 8000 × 3 processes, flag ON | **sim PASS, played PASS** (1 distinct `(fp, draws)` each) |
| **errors across 480 games** | **2** — see below |
| engine code changed | **none.** `git status` showed no tracked modifications before or after; the only file added is this report. |

### The 2 errors — a pre-existing latent bug the flag exposed, not one it caused

Both errors are the **same seed (8093), flag ON, on both arms**, dying at turn 19:

```
UnboundLocalError: cannot access local variable 'ball_handler_id'
where it is not associated with a value
```

Traced structurally (AST over `shared_defense.assign_all_zone_defenders`, lines 1199–1495):

- `ball_handler_id` is **bound only at line 1312**, inside the `for defender_pos in ['PG','SG','SF','PF','C']` loop that spans 1258–1371.
- It is **read at lines 1483–1484**, outside that loop.
- The loop's first statement is `if defender_pos not in zone_boundaries: continue` (1259–1260). **If none of the five slots is present in `zone_boundaries`, all five iterations `continue` before 1312**, the name is never bound, and 1483 raises.

**This is not the box-out's doing.** `boxout_contest.py` contains **zero** references to zone defence or `shared_defense` (grep count 0), and the box-out cannot reach that code. All the flag did was re-phase the RNG stream into a game state where the zone-boundaries map came back empty for every slot — a condition already flagged as suspect in `reports/zone-empty-branch-2026-09-18.md`.

**Not fixed** — this is a measurement pass and the brief says to stop rather than edit engine code. It is a real defect and belongs in the backlog: an empty `zone_boundaries` should not be able to crash a game, and the fix is to bind `ball_handler_id = None` before the loop.

**Seed 8093 is excluded from the primary analysis** because two of its four configs are 19-turn stubs whose box-score metrics would corrupt the paired deltas. The n=120 figures including it are shown above for completeness, and they do not change the verdict.

## Not covered

- **Flag not flipped, reference not re-cut, not merged, nothing retuned.** No engine code was touched.
- **`SEED_DEFENSES=0` was not re-run** — the brief scoped this pass to `=1`, which is where the disagreement was. The `=0` Stage 1 result (both arms up) stands unexamined at n=40 and is subject to exactly the same noise caveat; on this evidence I would not trust its sign either.
- **Not fixed:** the `assign_all_zone_defenders` `UnboundLocalError`.
- **Not investigated:** whether the box-out's near-zero effect on OREB share is itself the finding worth acting on. It changes 81 crash destinations per game and moves the rebound split by ~0.1–0.3 points, which may mean the push-back is landing in places that do not alter who is nearest the ball. That is a Stage 2 question, not this one.

