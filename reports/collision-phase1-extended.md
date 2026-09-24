# Collision Phase 1 EXTENDED — separation for all ten players

`GOB_COLLISION_SEPARATION_ALL`, **default OFF**, requires `GOB_COLLISION_SEPARATION=1`. Branch
`feature/animation-reward`. Not merged.

**Rule 6e footing**: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2
/ traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process,
`SEED_DEFENSES=1`, `GOB_DEFENDER_AG_SPREAD` unset (ON), all screen flags OFF,
`GOB_STRICT_EXCEPTIONS=1` on flag-on runs. n=40 seeds 8000–8039 both arms for (a)–(f); n=120
seeds 8000–8119 played for (g).

---

## THE HEADLINE — within 2.0 grid units

| | pairs within 2.0 | share of all pairs | vs flags-off |
|---|---|---|---|
| flags off | **156,232** | 1.5559% | — |
| base only (defender-defender) | **135,250** | 1.3670% | **−12.1%** |
| **base + ALL (ten players)** | **109,706** | **1.1050%** | **−29.0%** |
| base + ALL, authored pin off | 100,373 | 1.0144% | −34.8% |

Shares are used for the comparison because each flag state runs a different trajectory (step
counts differ by ~1%); the raw counts tell the same story.

### And the caveat that matters more than the headline

| | flags off | base | base+ALL |
|---|---|---|---|
| within 5.25 (**sprite width**) | 10.3645% | 10.3695% | **10.2934%** (−0.7%) |
| steps with ANY sub-3.0 overlap | 74.21% | 74.34% | **73.69%** |

**The pass cannot fix what a viewer actually sees, and that is structural, not a bug.** The
separation target is `COLLISION_OVERLAP_TOLERANCE × (r_a + r_b)` = ~2.62 grid for two median
players, but a sprite is ~5.25 grid wide. Two players pushed to exactly the threshold are still
overlapping on screen by half a sprite. So near-2.0 crowding drops 29% while sprite-width overlap
moves **0.7%** and the share of steps containing any sub-3.0 overlap moves from 74.21% to 73.69%.

Fixing that needs `COLLISION_OVERLAP_TOLERANCE` raised toward 1.0, which is a balance constant
and explicitly out of scope here. **This is the number to decide on before flipping anything.**

---

## Gate

| | result |
|---|---|
| both collision flags off, 240 cells | **240/240** fp AND draws, 480/480 checks, **0 mismatches** |
| seed 8000 played SD=1 | fp `0c3389cd41d0bbef`, draws `75363` ✓ |
| flag-ON must differ | base `cb79c381726cbcb9`, base+ALL `7433d510d091deb0`, no-pin `edb48d57346d750a` — all differ ✓ |
| ALL=1 with base OFF | **8/8 byte-identical to flags-off**, `enabled_calls=0`, warning logged once ✓ |
| suite | **3,646 passed** / 20 skipped / 110 xfailed / **0 failed** |

---

## (e) THE ITEM 22 CHECK — read this first

`_documentation_master/projects/bugs.md`: **26.8% played / 27.6% wrap of shots are decided by
`<=` against a ZERO MARGIN** on the arc, and moving authored spot coordinates to create margin is
"a balance change wearing a tidy-up costume".

**I exempted the shooter outright**, at every step, identified from the authored `shoot` action
in the skeleton (play intent, not outcome — not clairvoyant). It is proved two ways, not argued:

**1. The mechanism.** A probe snapshots every coordinate before the pass and diffs after:

```
SHOOTER VIOLATIONS: 0        (all four flag states, 80 games each)
```

If the shooter's coordinate is never written, no shot can be reclassified by this pass.

**2. The aggregate**, since a changed trajectory changes shot selection even with the shooter pinned:

| | 3PA | 2PA | FGA | 3PA share |
|---|---|---|---|---|
| flags off | 2,956 | 5,398 | 8,354 | 35.38% |
| base only | 3,082 | 5,197 | 8,279 | 37.23% |
| base + ALL | 3,014 | 5,287 | 8,301 | 36.31% |

The raw n=40 counts do move. **Seed-paired at n=120 they do not**: 3PA share **+0.502 ± 1.073**
and 3PT% **+0.454 ± 2.010**, both CIs comfortably spanning zero (full table in (g)). Note the
already-shipped base flag moves 3PA share *more* than the extension does, so what movement exists
is the known consequence of changing defender positions, not of touching the offence.

**Item 22 is not tripped.** Nothing retuned.

---

## (b) Placements moved and push distribution

| | placements | moved | def | off | p50 | p90 | max | ≥0.5 (visibility floor) |
|---|---|---|---|---|---|---|---|---|
| base | 1,104,380 | 140,923 (12.76%) | 140,923 | **0** | 0.5 | 1.3 | 2.0 | 55.8% |
| base + ALL | 2,178,835 | 227,680 (**10.45%**) | 200,048 | **27,632** | 0.6 | 1.4 | 2.0 | **60.3%** |
| ALL, no authored pin | 2,167,710 | 290,677 (13.41%) | 200,141 | 90,536 | 0.6 | 1.4 | 2.0 | 56.5% |

Base still moves **zero** offensive placements — Phase 1 remains independently rollback-able, as
required. 60.3% of pushes clear the ~0.5-unit visibility floor.

## (c) Residual after the capped relaxation — worse, as predicted

| | overlapping pairs | residual | residual share |
|---|---|---|---|
| base | 78,901 | 38,769 | **49.14%** |
| base + ALL | 233,577 | 155,446 | **66.55%** |
| ALL, no authored pin | 232,880 | 136,211 | 58.49% |

Ten players in one relaxation produce three times the overlapping pairs and more pileups, so
`COLLISION_MAX_PASSES = 3` resolves proportionally less. **Caps NOT tuned**, per the brief. Two
thirds of overlapping pairs are accepted rather than fixed, which is the honest cost of an O(1)
pass and is the second reason (after the sprite-width point) not to expect this to look fixed.

## (d) Per class

| | moved (def) | moved (off) | residual def-def | residual def-off | residual off-off |
|---|---|---|---|---|---|
| base + ALL | 202,747 | 27,696 | 45,142 | **93,282** | 17,022 |
| ALL, no authored pin | 202,788 | 90,633 | 44,039 | 77,916 | 14,256 |

**def-off is 60% of the residual.** That is where the crowding actually lives, and it is the class
the base flag could not touch at all.

### The exempt set, and how much of the offence it removes

| pin reason | count | share of all pins |
|---|---|---|
| **authored location** | 485,085 | **49%** |
| ball action this step | 188,822 | 19% |
| **shooter (all steps)** | 164,097 | 17% |
| no writable entry at this timestamp | 71,183 | 7% |
| defender on his man (existing Phase 1 pin) | 56,217 | 6% |
| already written this pass | 23,511 | 2% |

## (f) Screen-vs-game divergence — **IT ROSE**

| | checked | over tolerance | share | worst |
|---|---|---|---|---|
| flags off | 666,385 | 147 | **0.0221%** | 16.84 |
| base only | 666,364 | 138 | 0.0207% | 16.76 |
| **base + ALL** | 677,585 | **179** | **0.0264%** | **19.56** |
| ALL, no authored pin | 676,235 | 169 | 0.0250% | 15.40 |

**The brief's condition was "must not rise". It rose, from 0.0221% to 0.0264%** (+32 placements
in 677,585, 0.0047pp). The base flag alone still goes *down* (0.0207%), so this is specifically
the ten-player extension.

It is **not** a write-ordering fault: the pass runs inside `build_all_animations` before the
return, exactly where the base pass runs, and the base pass measures clean through the same
probe. The shape matches the reachability class already documented for the Stage B switch — a
player is moved to a point he cannot reach within `rate × step_t`, so `duration × rate ≠ distance`
and `bcensus` counts it. I did not attribute the 32 placements individually and am not claiming
which of the three pair classes produces them.

---

## (g) Outcomes, n=120, seed-paired

Played arm, SD=1, seeds 8000–8119, CI = 1.96 × SEM of the **per-seed difference**.

| metric | baseline | base only | base + ALL |
|---|---|---|---|
| points/team | 73.37 | −0.09 ± 1.71 | +0.96 ± 1.72 |
| FG% | 40.58 | −0.11 ± 1.10 | +0.55 ± 1.10 |
| 3PA share% | 35.82 | +0.50 ± 1.02 | +0.50 ± 1.07 |
| 3PT% | 33.23 | +1.85 ± 2.00 | +0.45 ± 2.01 |
| fouls | 31.70 | −0.73 ± 1.11 | −0.52 ± 1.25 |
| OREB | 14.76 | −0.43 ± 0.91 | −0.82 ± 0.89 |
| DREB | 43.09 | −0.43 ± 1.22 | −0.24 ± 1.25 |
| blocks | 10.06 | −0.23 ± 0.67 | −0.31 ± 0.70 |
| steals | 16.55 | −0.19 ± 0.97 | −0.16 ± 0.95 |
| possessions | 39.70 | −0.48 ± 1.27 | −0.15 ± 1.23 |

**Nothing excludes zero, in either state.** OREB at −0.82 ± 0.89 is the closest and does not
cross. Nothing retuned.

---

## Exemptions chosen, and why

1. **Shooter — exempt at every step.** Item 22. Proved by invariant, not argument.
2. **Ball handler — exempt at every step where his action is a ball action**
   (`handle_ball`/`receive`/`pass`/`drive`/`shoot`). The brief allowed moving him only on proof
   that no shot distance, pass origin or drive corridor changes. I cannot show that, so he is
   pinned. 19% of pins.
3. **Existing defender pin kept** (within 2.5 of his assigned man) — 6% of pins.
4. **Carried-forward offensive players are pinned**, not written. An offensive player's
   `movement[i]` is not step `i`; he only has an entry on steps where he has a `pos_action`. A
   player with no entry at this timestamp has nowhere to write, so he takes part as an obstacle
   and is counted (7% of pins) rather than written to the wrong beat.

### Recommendation on the authored-location pin: **DROP IT**

Measured both ways:

| | within 2.0 | off placements moved | residual | divergence |
|---|---|---|---|---|
| pin ON | 1.1050% (−29.0%) | 27,632 | 66.55% | 0.0264% |
| **pin OFF** | **1.0144% (−34.8%)** | 90,536 | **58.49%** | **0.0250%** |

Dropping it is better on **every** axis: more separation, less residual, and *lower* divergence.
The argument for pinning was symmetry with the defender pin, but it is not the same argument —
a defender on his man is executing coverage *against an opponent*, whereas an offensive player
standing on his authored spot is at a **static table coordinate** that the coincidence audit
already showed is shared by design (73.9% of the O-C/O-PF stack sits on one named spot). Pinning
it protects exactly the coordinate that causes the crowding. It is also the single largest pin
(49%), so it is doing most of the limiting.

I left the shipped default at `PIN_OFFENCE_AT_AUTHORED_LOCATION = True` (the conservative choice)
rather than changing behaviour on my own recommendation. Flipping it is a one-line change with
the measurement above already in hand.

---

## What did not behave as expected

1. **A real defect in my own pass, found and fixed mid-audit.** Defender movement is
   step-indexed, but offensive entries are matched by **timestamp** — and **26.8% of defender
   movement lists repeat a timestamp** (sub-steps). The same offensive entry could therefore be
   selected at more than one index and written twice, applying `COLLISION_MAX_DISPLACEMENT`
   twice: measured at a **4.0 displacement against a 2.0 cap**. Fixed with a one-write-per-entry
   guard (`pinned_already_written`, 2% of pins), covered by a test, and **every number in this
   report was re-measured afterwards** — max displacement is now 2.0. It was **not** the cause of
   the divergence rise (0.0266% before the fix, 0.0264% after).
2. **The divergence rise survives the fix** and remains unexplained at placement level. Reported
   above rather than attributed on a guess.
3. **The headline win does not translate to the visible problem.** −29% on within-2.0 against
   −0.7% on sprite-width overlap. That is the tolerance constant, not the pass.
4. Residual got substantially worse (49% → 67%), which was predicted in the brief and is not
   tuned away.

## Bottom line

The extension does what it was asked to do on the metric it was asked to be judged on: **within
2.0 grid drops 29.0%**, and **def-off — the class the base flag could not reach — is 60% of the
remaining residual**. Item 22 is clean, by invariant and by CI. No outcome moves.

But **I would not flip it yet**, for two reasons, both measured: divergence rose against a
must-not-rise condition, and the visible sprite-width overlap barely moved because
`COLLISION_OVERLAP_TOLERANCE` is half a sprite. The second is a balance decision that belongs to
Jamie's tuning pass; the first should be understood first.

## Tunable Constants

| Constant | Value | Effect |
|---|---|---|
| `GOB_COLLISION_SEPARATION_ALL` | **off** | Ten-player separation. Requires the base flag; alone it logs once and no-ops. |
| `GOB_COLLISION_SEPARATION` | off | Base defender-defender pass, behaviour unchanged. |
| `COLLISION_OVERLAP_TOLERANCE` | 0.5 | Fraction of combined sprite width tolerated. **The lever that decides whether this fixes what is visible.** Not tuned. |
| `COLLISION_MAX_PASSES` | 3 | Relaxation passes. Residual accepted, not chased. Not tuned. |
| `COLLISION_MAX_DISPLACEMENT` | 2.0 | Per-player, per-step cap. Not tuned. |
| `PIN_OFFENCE_AT_AUTHORED_LOCATION` | True | Whether an offensive player on his authored spot is pinned. **Recommended: False** — better on every measured axis. |
| `AUTHORED_LOCATION_TOLERANCE` | 0.5 | Grid rounding tolerance for "at" the spot. Not a balance constant. |

Nothing above was tuned. Jamie tunes once, at the end.
