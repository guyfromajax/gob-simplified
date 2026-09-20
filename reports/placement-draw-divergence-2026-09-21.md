# Placement draw divergence — measured

**Option A. One authoritative draw.** The pre-registered p90 threshold is 2.0 grid units; the measured
p90 is **20.0**, and the decision survives every stricter definition I could apply to it (§4). This is
not a close call and it is not a rounding artefact.

Read-only. **No code of any kind was changed** — `git diff` at `78c7ec46c` is 0 lines, the only new
file is this report, `GOB_BOXOUT_CONTEST` is still `"0"`.

**One thing I could not do:** the brief says to read *"Animation reward workstream — kickoff and
alignment", Finding 2* first. **That document does not exist in the repo** (`_documentation_master/`,
`reports/`) **or in your artifact list.** I worked from the brief's own restatement of Finding 2,
which is detailed enough to act on, and I have re-derived the consumer inventory from the code rather
than trusting it (§2). Where a figure in the inventory cannot be reproduced without that doc, I say so
instead of reconciling to it.

---

## 1. Pre-registered decision rule

> Primary statistic: the PER-DEFENDER SPREAD within a single turn = max distance between any two
> draws of that defender's position in that turn, in grid units.
>
> ACCEPT THE DIVERGENCE (Option B) if p90 spread < 2.0 grid units.
> ONE AUTHORITATIVE DRAW (Option A) if p90 spread >= 2.0 grid units.
>
> 2.0 is roughly a defender's own stance and a quarter of BOXOUT_PAIR_RADIUS — the scale at which
> "he is somewhere else" starts being true rather than pedantic. Jamie set it.

Recorded before the results below and **not adjusted**. Everything from §4 onward is the result.

## 2. The consumers, re-derived from code

The stochastic leaf is `shared_defense.get_defender_coords`, which draws from `sim_rng`
(`shared_defense.py:2` binds `sim_rng as random`) at two layers: the base man/zone placement jitter
(`randint`/`choice`, ~1721–1790) and the posture help-sag at **`shared_defense.py:1987`**:

```python
sag = HELP_SAG.get(posture, 0.30) * (1.0 + random.uniform(-HELP_SAG_JITTER, HELP_SAG_JITTER))
```

Located by `sys.monitoring` on the leaf's code object, walking the whole stack per call — not by
grepping imports, because every call site does `from ... import get_defender_coords` and a module-attr
patch would have missed all of them.

| consumer | where it reads | how it gets there |
|---|---|---|
| **STAMP** — interception / bat contest | `step["_step_state"]["defense"]` | `_stamp_contest_defender_grid` → `Animator.compute_placement_grids` → **its own build, its own draws** |
| **SHOT_CONTEST** — shot contest | every `player.coords` | `_uess_sync_emitted_shot_coords` re-emits the **already-built** `animations`; **it makes no placement draw of its own** (0 leaf calls in a full game) |
| **DRIVE** — drive contest | `defender_end_coords` | `attack_drive_clearance.py:1253` → **its own reconstruction** |
| **RENDER** — next turn (OTB, putback, rebounder) | `positions` | `sync_lineup_coords_from_turn` (`shared.py:3941`) off the last rendered step |

**The repo already says this in a docstring.** `animator.py:1265–1268`, on `compute_defender_grid`:

> *"the 'ONE identical computation' claim above is **aspirational** — the contest's grid and the
> render's animations are still two separate computations that **both draw from `sim_rng`**. That is
> what commit 2 fixes; this commit only moved the code."*

Commit 2 did not land. Finding 2 is that comment, measured.

**The drive reconstruction is confirmed NO-POSTURE.** `defender_placement.py` passes `posture=posture`
at all four of its placement calls (1096, 1121, 1182, 1207), read from
`game.game_state["_hco_defense_posture"]`. `attack_drive_clearance.py:1253` passes **no `posture`
argument at all**, so it defaults to `None` and `_apply_defender_posture` returns the untouched
aggression-era base (`shared_defense.py:1969–1970`).

### Draw counts (§1 of the brief)

Per HCO turn (`current_turn == "HCO"`, not fast break):

| | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| STAMP builds | 2.14 | 2.23 | 2.15 | 2.24 |
| SHOT_CONTEST syncs | 0.75 | 0.78 | 0.74 | 0.78 |
| DRIVE reconstructions | 0.24 | 0.37 | 0.24 | 0.35 |
| RENDER | 1.00 | 1.00 | 1.00 | 1.00 |
| **total placement-bearing events** | **4.13** | **4.37** | **4.14** | **4.37** |
| **draws per defender per turn** | **4.21** | **4.48** | **4.22** | **4.48** |

STAMP alone fires **1–5 times in a single turn** (`_stamp_contest_defender_grid` is called pre-walk
and again on the final skeleton), each time a fresh build with fresh draws.

**On the inventory's 5.1 / 4.2 / 3.1:** my four cells land in **4.13–4.48**, so the middle figure
reproduces and the outer two do not. I cannot confirm or correct them properly, because "played /
wrap / raw" is a three-arm taxonomy that does not map onto this harness's `sim` / `played` arms, and
the document defining it is the one I could not find. **Not reconciled deliberately** — guessing at
which arm is which would be the kind of reconciliation that hides a disagreement.

## 3. Footing and RNG-neutrality

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
n=40 seeds 8000–8039, **both arms × both `SEED_DEFENSES`** = 160 games. **0 errors.**

**Extended rule — the defenses catalogue is stated per cell.** `SEED_DEFENSES=1` seeds the six real
defenses; `SEED_DEFENSES=0` leaves the catalogue empty, and **every zone call then plays man**. That is
visible in the data: at SD=0, `posture_fired=False` has **n=0** — with no catalogue there are no zone
turns, so posture applies on every HCO turn. Any SD=0 number here is a man-only number.

**The probe consumes no RNG.** `sys.monitoring` callbacks read frame locals and append to lists; they
call no engine code. Proved, not asserted, in every cell:

| cell | fingerprint vs `equiv_v3_reference_70f7dd021_b1a.json` | draws |
|---|---|---|
| sim SD=1 | **40/40** | **40/40** |
| sim SD=0 | **40/40** | **40/40** |
| played SD=1 | **40/40** | **40/40** |
| played SD=0 | **40/40** | **40/40** |

## 4. The spread (§2)

### Primary statistic, as pre-registered

| cell | mean | p50 | **p90** | max | share ≥ 2.0 |
|---|---|---|---|---|---|
| sim SD=1 | 12.37 | 12.07 | **20.02** | 44.92 | 97.5 % |
| sim SD=0 | 12.85 | 12.53 | **20.25** | 44.07 | 98.3 % |
| played SD=1 | 12.50 | 12.17 | **20.00** | 45.22 | 97.6 % |
| played SD=0 | 12.86 | 12.53 | **20.25** | 44.28 | 98.3 % |

**p90 = 20.0 against a threshold of 2.0 — ten times over, in all four cells. Option A.**

### The decision does not depend on that number

The primary statistic has a confound I should name rather than bury: **RENDER is the end-of-turn
position**, so part of its distance from the others is the defender legitimately *moving*, not a
different draw. Two stricter cuts, both pre-2.0-threshold-blind:

| cut | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| **Resolving consumers only** (STAMP+SHOT+DRIVE, RENDER dropped) — p90 | 17.09 | 18.03 | 17.20 | 18.03 |
| ” share ≥ 2.0 | 85.1 % | 93.1 % | 86.2 % | 93.7 % |
| **Pure redraw** (two STAMP builds, same step index, same skeleton length, **identical offense grid**) — p90 | 3.00 | 2.00 | 3.00 | 2.00 |
| ” identical | 61.6 % | 64.7 % | 61.4 % | 64.4 % |
| ” share ≥ 2.0 | 22.0 % | 11.6 % | 21.9 % | 11.8 % |

The last row is the tightest control available: **same code, same step, same skeleton, and the offense
in exactly the same place** — every difference is the redraw and nothing else. Even there the p90 is
**3.00** (SD=1) and **2.00** (SD=0), i.e. at or above the threshold. The distribution is bimodal: ~62 %
land on exactly the same grid cell, and the rest scatter with a tail to 26 units. **That tail is not
jitter** — it is too large for a ±10 % shade on a 0.30 sag (§6) and is the signature of a defender
being placed against a *different assignment* on the redraw.

### Pairwise matrix (§2) — sim SD=1; the other three cells agree within ~0.5

| pair | n | mean | p50 | p90 | max |
|---|---|---|---|---|---|
| **SHOT vs STAMP** | 17,760 | **1.09** | **0.00** | 3.61 | 20.62 |
| DRIVE vs SHOT | 5,115 | 3.85 | 2.04 | 10.05 | 29.43 |
| DRIVE vs STAMP | 5,740 | 4.93 | 3.61 | 11.07 | 29.21 |
| RENDER vs STAMP | 23,545 | 7.80 | 7.10 | 14.87 | 36.65 |
| DRIVE vs RENDER | 5,740 | 8.23 | 8.06 | 15.21 | 37.00 |
| RENDER vs SHOT | 17,760 | 8.95 | 8.60 | 16.97 | 38.91 |

**They do not all scatter equally — the matrix has a clear shape.** SHOT and STAMP are nearly the same
answer (p50 exactly 0). DRIVE sits apart from both. RENDER sits apart from everything. So there is one
tight cluster (the two contest consumers), one outlier by construction (the no-posture drive
reconstruction), and the render, which is a different moment as well as a different draw.

## 5. Posture split (§3)

**The divergence is NOT concentrated in posture-fired turns, so the missing help-sag term is not the
cause.** Pure-redraw distances, split:

| cell | posture fired | n | mean | p50 | p90 |
|---|---|---|---|---|---|
| sim SD=1 | **yes** | 22,980 | **2.76** | 1.00 | 9.22 |
| sim SD=1 | no | 44,610 | **2.25** | 0.00 | 8.06 |
| played SD=1 | **yes** | 24,450 | **2.81** | 1.00 | 9.22 |
| played SD=1 | no | 43,505 | **2.30** | 0.00 | 8.25 |

A 0.5-unit difference on a mean of ~2.5. Posture-fired turns are *marginally* worse, not categorically
worse. **This kills the neatest available hypothesis** — "the drive contest's no-posture
reconstruction is the whole story" — and that is worth saying plainly, because it was the one finding
that would have been specific and nameable.

### The help-sag term's own magnitude, for comparison

| | n | mean | p50 | p90 | max |
|---|---|---|---|---|---|
| displacement from base → posture coord | 252,458 | **3.25** | 2.24 | 8.06 | 38.64 |
| the `sag` fraction actually drawn | 141,597 | 0.3001 | — | — | range **0.27 – 0.33** |

Two things follow. **The posture term is large** — it moves a defender 3.25 units on average, *bigger*
than the mean pure-redraw divergence (1.15). So a consumer that omits posture is systematically
somewhere else, which is exactly what DRIVE-vs-STAMP (mean 4.93) shows. **The jitter inside it is
tiny** — `sag` spans 0.27–0.33 around a nominal 0.30, so the stochastic part contributes at most
`0.03 × |ball − man|`, well under a grid unit at normal spacing. **The divergence is not the jitter.
It is that the four consumers compute different things.**

## 6. Does it matter to outcomes? (§5)

The shot contest has a hard binary threshold: `CONTEST_EUCLIDEAN_RADIUS = 11`
(`constants/__init__.py:364`), applied at `shot_manager.py:1082` — inside 11 grid units of the shot
spot the defender contests, outside he does not. So "would the two draws land on opposite sides" is
directly answerable. Per pair, share of defender-turns where the two consumers disagree about whether
that defender contests:

| pair | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| **SHOT vs STAMP** | **4.8 %** | 4.6 % | 4.8 % | 4.5 % |
| DRIVE vs SHOT | 16.0 % | 10.6 % | 15.5 % | 10.1 % |
| DRIVE vs STAMP | 23.2 % | 18.5 % | 22.8 % | 18.1 % |
| RENDER vs SHOT | 30.8 % | 31.3 % | 31.4 % | 31.7 % |
| RENDER vs STAMP | 31.3 % | 31.3 % | 32.1 % | 31.5 % |
| DRIVE vs RENDER | 37.4 % | 38.0 % | 36.6 % | 37.4 % |

**Take the most conservative row.** SHOT vs STAMP is the pair with no moment confound at all and a mean
separation of barely one grid unit — and it still flips the contest **4.8 %** of the time. The brief's
own calibration was *"a 1-unit spread that flips a contest 8 % of the time is not [cosmetic]"*. This is
a 1-unit spread flipping it ~5 % of the time between the two consumers that are supposed to agree, and
10–23 % of the time once the drive reconstruction is involved. **It is not cosmetic.**

## 7. Is the render draw even stable across arms? (§6)

**The question cannot be answered per-turn, and that is a fact about the harness, not a finding about
placement.** The two arms are different code paths by construction (`_is_full_simulation` is False
inside the four gated Animator methods on the played arm), so they consume different draws and stop
being the same game early:

| | SD=1 | SD=0 |
|---|---|---|
| reference fingerprints identical sim vs played | **0 / 40** | **0 / 40** |
| turns whose RENDER map is byte-identical across arms | 9.0 % | 10.8 % |
| **first turn index at which RENDER differs** | p50 **12**, min 3, max 52 | p50 **12**, min 3, max 51 |
| seeds where every compared turn matched | 0 / 40 | 0 / 40 |

Up to that first divergence the arms' render draws are **identical**; after it they are different
games, and the large per-player deltas past that point (mean 33.5) are comparing unrelated turns, not
measuring disagreement. **So: no parity finding, and the decision is unchanged.** I am reporting the
33.5 only to say explicitly that it is meaningless and should not be quoted.

## 8. Trace — one turn, five defenders, every draw

**seed 8000, turn 145, HCO → MAKE, `3-2-zone`, sim SD=1.** Shot spot `(20.0, 25.0)`.

I asked for the turn nearest **p90 (20.02)** that carries all four consumers; the closest such turn has
a max spread of **18.97**, so this is a p90-band turn, not a median one — as the brief asked — but 1.05
units short of the exact p90 because turns carrying a DRIVE capture are a 23 % subset.

```
PG  b42d8179     STAMP build 1  (last step 5)   (17.00, 25.00)   d=3.00   CONTEST
                 STAMP build 2  (last step 9)   (17.00, 25.00)   d=3.00   CONTEST
                 SHOT_CONTEST                   (17.00, 25.00)   d=3.00   CONTEST
                 DRIVE (no posture)             (18.00, 32.00)   d=7.28   CONTEST
                 RENDER -> next turn            (15.00, 19.00)   d=7.81   CONTEST      spread 13.34

SG  b43726fc     STAMP build 1                  (20.00, 30.00)   d=5.00   CONTEST
                 STAMP build 2                  (18.00, 29.00)   d=4.47   CONTEST
                 SHOT_CONTEST                   (20.68, 30.67)   d=5.71   CONTEST
                 DRIVE (no posture)             (18.00, 32.00)   d=7.28   CONTEST
                 RENDER -> next turn            (11.00, 27.00)   d=9.22   CONTEST      spread 10.35

SF  9c044323     STAMP build 1                  (24.00, 14.00)   d=11.70  --  no contest
                 STAMP build 2                  (17.00, 16.00)   d=9.49   CONTEST
                 SHOT_CONTEST                   (17.00, 16.00)   d=9.49   CONTEST
                 DRIVE (no posture)             (18.00, 32.00)   d=7.28   CONTEST
                 RENDER -> next turn            (13.00, 28.00)   d=7.62   CONTEST      spread 18.97

PF  e5fd9c60     STAMP build 1                  (17.00, 23.00)   d=3.61   CONTEST
                 STAMP build 2                  (17.00, 23.00)   d=3.61   CONTEST
                 SHOT_CONTEST                   (17.00, 24.98)   d=3.00   CONTEST
                 DRIVE (no posture)             (18.00, 32.00)   d=7.28   CONTEST
                 RENDER -> next turn            (13.00, 23.00)   d=7.28   CONTEST      spread 10.30

C   3a9fb6c4     STAMP build 1                  (17.00, 27.00)   d=3.61   CONTEST
                 STAMP build 2                  (17.00, 27.00)   d=3.61   CONTEST
                 SHOT_CONTEST                   (17.00, 27.00)   d=3.61   CONTEST
                 DRIVE (no posture)             (18.00, 32.00)   d=7.28   CONTEST
                 RENDER -> next turn            (15.00, 21.00)   d=6.40   CONTEST      spread 11.40
```

**Read SF first.** Build 1 puts him at `(24, 14)` — 11.70 from the shot, **outside** the contest
radius. Build 2, the *same consumer, same turn, same code*, puts him at `(17, 16)` — 9.49, **inside**.
Whether this defender contests the shot depends on which of two calls to the same function you happen
to read. That is §6's 4.8 % as a single readable case.

**Two things to notice beyond the headline.** The DRIVE row is `(18, 32)` **for all five defenders** —
the no-posture reconstruction has collapsed the entire defence onto one point on this zone turn
(`attack_drive_clearance.py:1262–1270`, the unmatched-zone-defender branch). And RENDER, the draw
Jamie's eye actually verifies, is 6–10 units from every resolving consumer for every defender on this
turn.

## 9. What this does and does not say

- **Option A is indicated.** Per the brief, this report says so and stops. **I have not designed or
  scoped the authoritative-draw refactor**, and nothing here should be read as a design for it.
- **The cause is not the help-sag jitter** (§5) and not posture (§5). It is that four consumers run
  **separate computations**, two of which (STAMP, the render build) redraw from `sim_rng`, and one of
  which (DRIVE) computes a materially different thing by omitting posture entirely.
- **The pure-redraw divergence is mostly small** — 62 % of the time the two builds agree exactly. The
  damage is in a tail, and in the systematic offset of the drive reconstruction, not in a uniform
  fuzz.
- **Not measured:** whether the interception contest's own threshold flips at the same rate (it has no
  single distance cutoff comparable to `CONTEST_EUCLIDEAN_RADIUS`; its gates are tiered scores).
  §6 is the shot contest only.
- **Not measured:** the rebounder/putback consumer downstream of RENDER. RENDER is measured as a
  position; what the next turn *does* with it is out of scope.
- **Not chased:** the `(18, 32)` five-defender collapse in §8. It appears in a zone drive and it may be
  correct-by-design for the rim-guardian branch. It is flagged, not diagnosed.

## 10. Tunable constants

| constant | where | value | effect |
|---|---|---|---|
| `CONTEST_EUCLIDEAN_RADIUS` | `constants/__init__.py:364` | `11` | the binary the §6 flip rates are measured against; widening it makes divergence matter less at the edge and more in the middle |
| `HELP_SAG` | `shared_defense.py:1937` | `{normal: 0.30, loose: 0.55}` | how far an off-ball help defender sits toward the ball |
| `HELP_SAG_JITTER` | `shared_defense.py:1938` | `0.10` | the ±10 % on `sag`; measured span 0.27–0.33, sub-grid-unit in effect |
| `HELP_BASKET_SHADE` | `shared_defense.py:1939` | `0.20` | shade toward the rim |
| `HELP_ANCHOR_FLOOR` | `shared_defense.py:1940` | `0.30` | min follow in the basket-aligned axis |
| `ONBALL_POSTURE_DIST` | `shared_defense.py:1932` | `{tight 2.5, normal 3.5, loose 4.5}` | on-ball cushion |
| `POSTURE_DENY_DISTANCE` | `shared_defense.py:1934` | `2.0` | off-ball deny distance |
| `BOXOUT_PAIR_RADIUS` | `utils/boxout_contest.py` | `8.0` | the scale the 2.0 threshold was set against |
