# Zone-defender crash fix, and why a 5.5-unit push-back does not move the rebound split

Two tasks. **Task A** lands a crash fix (committed separately, `c79316c82`). **Task B** is read-only: no engine code was touched, and `GOB_BOXOUT_CONTEST` stays default `"0"` in the tree.

---

# Task A — the `assign_all_zone_defenders` `UnboundLocalError`

## What line 1494 actually does with `ball_handler_id`, and why that decides the fix

```python
            # Track that this defender is guarding the ball handler
            if ball_handler_id:
                defender_to_offensive_player[closest_defender] = ball_handler_id
```

It is a **value written into `defender_to_offensive_player`** — the map of defender slot → the offensive player that defender is credited with guarding. It is **not compared and not used as an index**, and the write is **already guarded by `if ball_handler_id:`**.

So `None` would be a *safe* no-op at those two lines — it would not produce a wrong answer there. **But it would still be the wrong fix**, because `None` is not what the code means at that point. The whole block exists to credit a defender with guarding the ball handler, and it is reached only when the fallback has established that **there is** a ball handler who is **not yet guarded**. Defaulting to `None` would convert a crash into a **silently missing guard credit**, and that map is consumed downstream by `_apply_multi_defender_offsets` (which spreads defenders guarding the same man) and by the zone credit path. That is exactly the "papering over a crash with a value that makes the function return something bogus" the brief warns against.

**The right fix is to hoist the binding**, because the value is recoverable — it was never unknowable, just unreachable:

```python
ball_handler_id = None
for p in offensive_players:
    if p.get("is_ball_handler"):
        ball_handler_id = p.get("player_id")
        break
```

That scan reads **only `offensive_players`**, which this function never mutates — verified by AST walk over the whole function (no `append`/`extend`/`insert`/`remove`/`pop`/`clear`/rebind/item-assign). It is therefore **loop-invariant**: it computed an identical value on every one of the up-to-five iterations. Moving it above the loop yields the value the code already intended, on every path, and is a no-op wherever the loop previously reached it. It also removes a redundant O(n) rescan per defender, though that is incidental.

## Correcting the premise — an empty `zone_boundaries` is **not** the trigger

`reports/boxout-stage15-2026-09-20.md` (mine) and the brief both said the crash needs `zone_boundaries` missing all five slots. **That is wrong, and a synthetic empty-map test does not reproduce it** — it passes on the pre-fix code, because the fallback block's own loop skips on the same condition, so `closest_defender` stays `None` and the read never happens.

I captured the real state from the live crash instead (seed 8093, flag ON, sim):

```
slots_present     : [C, PF, PG, SF, SG]      <- all five
slots_with_coords : [C, PF, PG, SF, SG]      <- all five, non-empty
ball_handler_flagged : 1
overlap_map : { 104c7b0f...: [SG, SF],  a0a0f2d7...: [PG, PF, C] }
ball_spot : "key"   is_away_offense : True
```

**The real trigger is the loop's SECOND `continue`.** A defender with an overlap assignment guards that player and skips the rest of the body — before the binding. Here two overlap players claimed **all five** defenders between them, so every iteration took that path. Neither overlap player was the ball handler, so `ball_handler_guarded` stayed False, the fallback block ran, its own loop (which has no overlap skip) found a `closest_defender`, and the read raised.

A third condition is needed and is easy to miss: **the ball handler must be outside every defender's zone**, or the first `ball_handler_guarded` check marks him guarded and the block never runs. My first two attempts at a regression test failed for exactly that reason, and I only got it right after capturing the live state.

## How often does this happen in normal play? **Zero times.**

Read-only `sys.monitoring` counter over the **160 reference games with the flag OFF**, counting calls where the loop never reached the binding **and** the post-loop read ran (the two conditions that together raise). The probe reproduces the reference 40/40 on fingerprint and draws in every cell.

| cell | calls | loop never reached binding | post-loop read ran | **would raise** |
|---|---|---|---|---|
| `SD=1` sim | 290,630 | 9,147 | 17,898 | **0** |
| `SD=1` played | 281,190 | 8,048 | 16,248 | **0** |
| `SD=0` sim | 0 | 0 | 0 | 0 |
| `SD=0` played | 0 | 0 | 0 | 0 |
| **total** | **571,820** | **17,195** | **34,146** | **0** |

(`SEED_DEFENSES=0` contributes no calls at all: with an empty defense catalogue every zone call plays man, so this function never runs — the footing noted in the earlier zone work.)

**Plainly: this is not a bug we have been shipping into user games**, on this evidence. It became reachable only under `GOB_BOXOUT_CONTEST=1`, a default-OFF experimental flag, on 1 seed in 120.

**But it is a near-miss, not a safe design.** Both component conditions fire constantly — the loop skips the binding 17,195 times and the post-loop read runs 34,146 times across those same 160 games. They simply never coincided. That is luck, not structure, and it is why this is worth fixing rather than noting. It also belongs with `reports/zone-empty-branch-2026-09-18.md`, which already flagged the empty-zone branch as suspect — the overlap rung claiming every slot is the same family of "the zone map came back in a shape nobody designed for".

## Proof the fix is safe

| check | result |
|---|---|
| **flag OFF vs `equiv_v3_reference_70f7dd021_b1a.json`** | **40/40 fingerprint AND draws, all four cells** (`SD=1`/`=0` × sim/played), 0 errors |
| seed 8093, flag ON, sim | **438 turns, completes, 0 errors** (was: died at turn 19) |
| seed 8093, flag ON, played | **371 turns, completes, 0 errors** (was: died at turn 19) |
| regression test on the **pre-fix** code | **raises `UnboundLocalError` at `shared_defense.py:1483`** |
| regression test on the **post-fix** code | **7 passed** |
| full suite | **2848 passed, 0 failed, 0 XPASS** |

`tests/test_zone_empty_boundaries_crash.py` carries both the captured-state reproduction and a structural guard (AST: every bind of `ball_handler_id` must precede the skippable loop, and every read must follow a bind) — the structural guard also fails on the pre-fix code, so moving the binding back inside the loop cannot pass silently.

---

# Task B — why the push-back does not move the rebound split

**Read-only. No engine code changed.** `SEED_DEFENSES=1`, n=40, both arms, flag ON for the probe runs only.

## The hypothesis is wrong. The travel cap is not the cause.

The hypothesis was that players cover only a fraction of the line to their destination before the ball comes down, so a 5.5-unit destination shift becomes a much smaller arrival shift. **Measured, it does not:**

### 1. Travel fraction

| arm | group | n | mean | p10 | p25 | p50 | p75 | p90 | **reach 1.0** |
|---|---|---|---|---|---|---|---|---|---|
| sim | **box-out losers** | 3,256 | **0.9795** | 0.957 | 1.000 | 1.000 | 1.000 | 1.000 | **90.4%** |
| sim | everyone else | 12,607 | 0.9700 | 0.894 | 1.000 | 1.000 | 1.000 | 1.000 | 85.3% |
| played | **box-out losers** | 3,195 | **0.9794** | 0.966 | 1.000 | 1.000 | 1.000 | 1.000 | **90.2%** |
| played | everyone else | 12,243 | 0.9718 | 0.908 | 1.000 | 1.000 | 1.000 | 1.000 | 85.8% |

**Crashers essentially always arrive.** The median is 1.0, the 25th percentile is 1.0, and 85–90% reach the destination exactly. The post-shot window is long enough, at `_ag_grid_per_game_sec`'s rates, to cover these distances.

### 2. Attenuation — the number that answers the hypothesis

For box-out losers, the arrival point recomputed with and without the push-back (`rebound_arrival.arrival_point`, pure geometry, no RNG):

| arm | destination shift | arrival shift | **ratio** | p10 | p50 |
|---|---|---|---|---|---|
| sim | 5.519 | 5.055 | **0.9680** | 0.904 | **1.000** |
| played | 5.505 | 5.049 | **0.9664** | 0.915 | **1.000** |

**The ratio is 0.97, not 0.2.** The push-back survives into the arrival point essentially intact — a 5.5-unit destination shift becomes a 5.05-unit arrival shift, and at the median it is lossless. **The cause is downstream of the cap.**

### 3. The cleanest number — and the box-out works

Among paired players only, flag ON:

| arm | | n | P(gets the rebound) | |
|---|---|---|---|---|
| sim | box-out **winner** | 3,256 | **15.57% ±1.25** | |
| sim | box-out **loser** | 3,256 | **8.97% ±0.98** | |
| | **difference** | | **+6.60 pp ±1.59** | **DISTINGUISHABLE — 1.74×** |
| played | box-out **winner** | 3,195 | **15.12% ±1.24** | |
| played | box-out **loser** | 3,195 | **9.36% ±1.01** | |
| | **difference** | | **+5.76 pp ±1.60** | **DISTINGUISHABLE — 1.62×** |

**Winning a box-out makes you ~1.7× more likely to get that rebound.** The feature is not inert; it is one of the larger single-position effects measured in this codebase, and both arms agree.

### 4. Swamping — the position signal is visible, not buried

Spread across the candidates on one contested board:

| arm | position term `1/(1 + d/8)` (range 0–1) | composite `RB·.5+ST·.3+IQ·.1+CH·.1` (range 0–100) |
|---|---|---|
| sim | mean **0.3133**, p50 0.3266 | mean 46.07, p50 45.85 |
| played | mean **0.3187**, p50 0.3325 | mean 46.70, p50 46.75 |

The position term varies by ~0.31 of its full 0–1 range across the candidates on a typical board — a **~31% multiplicative swing**, against a composite that varies ~46 points on a ~50-centred scale. They are **comparable in size**, and the `randint(1,6)` multiplies the whole product by 1–6 on every candidate, so it adds noise to all of them equally rather than specifically drowning position. That is consistent with §3: position clearly moves the individual outcome.

## The mechanism: the contest is symmetric, so it cancels at team level

Putting §3 together with the Stage 1 census:

- **36%** of defensive crashers pair, giving ~81 box-outs a game.
- The defender wins **47.3%** of them (Stage 1) — near a coin flip, because `ST × rand(1,6)` is a fair contest between two similar populations, with only a tie-break edge to the defender.
- So in **47.3%** of pairs the **offensive** crasher is pushed back (helps the defence), and in **52.7%** the **defender** is pushed back (helps the offence).
- Each push-back moves that player from ~15.6% to ~9.0% on that board.

**The individual effect is large and real; the two directions occur in near-equal measure and net out.** A team-level metric like OREB share is the difference between those two flows, and they are almost exactly balanced — which is precisely what Stage 1.5 found at n=119 (sim +0.139 ±1.422, played −0.316 ±1.590, both ≈ 0).

The slight tilt (52.7% of pushed-back players are defenders) predicts a *small* net gain for the offence. That is consistent with the measured sign on the sim arm, but it is an inference from two separately-measured quantities, **not an independent measurement**, and it is well inside the noise either way. I am not claiming it.

## The smallest honest change — described, not built

**If the goal is for the box-out to move the rebound split, the lever is the symmetry, not the cap.**

A box-out in basketball is something the **defender** does: he puts a body between his man and the rim. The current model lets the offensive crasher "win" and push the *defender* back, which is really a seal or a swim move — a different action wearing the same name. Making the contest one-directional (the defender either succeeds in boxing out, or nothing happens; the offensive crasher is never the one displaced) would remove the offsetting flow and leave only the OREB-suppressing one.

**What it would cost:** no new draws — the same number of contests, the same two `rand(1,6)` rolls — so the *draw count* is unchanged, but **which player is displaced changes**, so results move and the reference needs a re-cut. It would also push OREB share **down** by roughly the size of the flow it removes, which on these numbers is material rather than marginal, so it is a balance decision and not a correctness one.

**That is Jamie's call, and it is a change to the design he specified** ("the loser's crash destination is pushed back"), not a defect in the implementation of it. **Nothing was built.**

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM. **sim arm** = `_is_full_simulation` True throughout; **played arm** = False only inside the four gated Animator methods at Pattern A. Task A's neutrality and counting runs cover both footings; Task B is `SEED_DEFENSES=1` as briefed. Every probe is read-only and RNG-neutral — the counter reproduces the reference 40/40 in all four cells, and the arrival probe recomputes `arrival_point`/`travel_fraction` (pure geometry) and the rebound composite **from attributes**, never calling `calculate_rebound_score`, which would roll the d6 and perturb the run.

## Not covered

- **Nothing retuned:** `randint(1,6)`, the rebound composite, the team bonus, the 0.8 discounts, `REBOUND_DISTANCE_SCALE`, `_ag_grid_per_game_sec` — all untouched.
- **`crash_destination.py`'s clairvoyance guard untouched**, and the box-out flag stays default `"0"`. Reference not re-cut, nothing merged.
- **Task B changed no engine code at all.**
- **Not measured:** the net OREB flow decomposed directly (offence-helping vs defence-helping pushes and their realised rebound outcomes). The cancellation above is inferred from the 47.3% win rate and the §3 probabilities; measuring it directly would settle the small residual tilt.
- **Not investigated:** why 10–15% of crashers fail to reach their destination, or whether those are concentrated on long crashes from the arc.
