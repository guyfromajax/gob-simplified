# The loose sag axis and the drive help-cutoff gate — both built, both OFF

**The built axis matched what was priced, to within 0.07 of a grid unit.** Measured on the
real runs: weak-side defender→rim **12.07 → 9.46** (priced 9.53), strong side **14.80 → 12.60**
(priced 12.59), and placements sitting inside the shot-contest radius of the ball **50.3% →
26.2%** (priced 25.8%). The four picture panels reproduce yesterday's counterfactual panel for
panel (13.7 / 11.1 / 11.3 / 11.7).

**Removing the gate does what it was meant to do: help arrives.** The share of tier-A blow-bys
demoted by a help cutoff goes **51.8% → 73.8%** at loose, 52.0% → 73.7% at normal and 52.4% →
71.8% at base man. But the effect is **not** mainly the passive fix it was framed as — at the
fixture's slider-2 footing, passive is only 2–3% of attempts, and the gain comes from *normal*
aggression going 0.5 → 1.0 (success rate 53.5% → 73.5%).

**One thing moves the scoreboard, and the two changes fight each other.** The gate alone at
loose is worth **−2.44 ±1.69 points** to the offence, with FG% −1.34 ±0.92, rim share −0.42
±0.41 and steals +0.90 ±0.75 — all clearing. The axis alone is scoreboard-neutral (−0.08 ±2.25)
and moves only paint share (−1.55 ±1.16). Together they give **+0.56 ±2.15** — nothing — because
the axis more than halves the blow-bys the gate feeds on (11.6 → 5.0 per game). **They are not
additive, and that is the decision in front of you.**

Both flags ship **OFF**. Nothing merged.

---

## 0. develop, and the reference

develop was 3 commits ahead and was merged first (`f06c9f6a9`; no engine files). The current
reference `equiv_v3_reference_09f1b0ca9_boxout.json` reproduced **160/160** on fingerprint AND
draws at the merged tree before anything was touched.

**The three pre-existing develop failures are gone** — develop's own #604 ("Clear 6 stale
tests") fixed them upstream. The suite baseline moved from 3191 passed / 112 xfailed / 3 failed
to **3273 passed / 110 xfailed / 0 failed**.

## 1. Change 1 — the loose sag axis (`GOB_MAN_LOOSE_SAG_AXIS`, default OFF)

`3d8a70325`. In the man off-ball HELP branch of `_apply_defender_posture`:

```
sag_target = ball + HELP_BASKET_PULL[posture] × (rim − ball)
HELP_BASKET_PULL = {"normal": 0.0, "loose": 0.25}
```

declared beside `HELP_SAG` and read by name at call time through `_help_sag_target`. Deny and
the inside-man lock return before this branch; the man help shade is untouched and independent;
no clamp; `HELP_SAG`, `HELP_ANCHOR_FLOOR`, `HELP_SAG_JITTER`, `HELP_BASKET_SHADE` and
`POSTURE_DENY_DISTANCE` are all unchanged.

### Acceptance — the reference cannot see this, so it is proved twice over

| check | result |
|---|---|
| `equiv_v3_reference_09f1b0ca9_boxout` with the axis **OFF** | **160/160** fp + draws, all four cells |
| the same reference with the axis **ON** | **160/160** fp + draws, all four cells |
| `EQUIV_MAN_POSTURE=normal`, axis OFF vs ON, both arms | **80/80 byte-identical** |

The ON run is not a kill-switch proof — it is the proof that **normal is untouched**. Base man
resolves to posture normal, where the pull is 0.0, so the ordinary reference is blind to this
change by construction. No re-cut.

### The loose-footing baseline — what change 1 is actually measured against

`equiv_v3_loose_baseline_ef00985ce.json` (n=40 seeds 8000-8039, both arms, SD=1,
`EQUIV_MAN_POSTURE=loose`, both flags off). Arm gap (sim − played) **+1.113 ±3.268**.

| check | result |
|---|---|
| independent reproduction 2 | **80/80** fp + draws |
| independent reproduction 3 | **80/80** fp + draws |
| axis ON vs this baseline | **0/80** — every seed moves, as it must |

### Geometry: measured against priced

n=40 seeds 8000-8039, **both arms**, SD=1, posture loose. 273,053 placements OFF / 284,109 ON
(the ON games diverge, so the populations are not identical).

| | OFF | ON | priced |
|---|---|---|---|
| **weak** defender→rim | 12.07 | **9.46** | 9.53 |
| **strong** defender→rim | 14.80 | **12.60** | 12.59 |
| **middle** defender→rim | 11.39 | 9.59 | 9.36 |
| inside contest radius | 50.3% | **26.2%** | 25.8% |
| `HELP_ANCHOR_FLOOR` binds | 26.4% | 27.2% | 26.6% |

Every headline lands within 0.25 of the counterfactual. Full split:

| | side | share | defender→rim m/p50/p90 | gap to man m/p50/p90 | dist to ball m/p50/p90 | rim-ward | ball-ward |
|---|---|---|---|---|---|---|---|
| **OFF** | strong | 53.4% | 14.80 / 15.60 / 20.60 | 9.39 / 9.10 / 14.60 | 9.62 / 9.40 / 17.00 | 6.22 | **8.15** |
| | middle | 16.8% | 11.39 / 12.50 / 16.30 | 13.49 / 13.20 / 19.10 | 11.00 / 11.70 / 13.60 | 11.98 | 11.15 |
| | weak | 29.8% | 12.07 / 12.40 / 15.30 | 19.16 / 20.10 / 25.50 | 13.76 / 13.10 / 17.00 | 16.81 | **17.44** |
| **ON** | strong | 52.7% | 12.60 / 13.00 / 17.10 | 9.76 / 9.80 / 14.90 | 11.46 / 12.20 / 18.20 | **8.09** | 7.18 |
| | middle | 17.3% | 9.59 / 10.30 / 13.20 | 14.19 / 15.10 / 19.00 | 12.68 / 13.50 / 15.90 | 13.35 | 10.70 |
| | weak | 29.9% | 9.46 / 9.80 / 12.60 | 18.63 / 19.70 / 24.00 | 16.13 / 16.00 / 19.20 | **17.22** | 15.87 |

The rim-ward/ball-ward decomposition inverts on both sides, exactly as priced. The strong-side
gap to his man rises only **+0.37** (9.39 → 9.76) while his rim distance falls 2.20.

The anchor-floor rate rises 0.8 pp where the counterfactual predicted none. That is a population
effect, not the blend pressing on the floor: the flag-on games diverge, so a different set of
steps is sampled. In the counterfactual, which holds the steps fixed, the rate is identical at
every pull value.

## 2. Change 2 — the cutoff gate (`GOB_HCO_CUTOFF_NO_GATE`, default OFF)

`a70c30663`. `hco_cutoff_stop_attempt_prob(aggression)` returns 1.0 for every setting with the
flag on. `HCO_CUTOFF_STOP_ATTEMPT_PROB` is **kept**, gated and read by name, so the rollback is
exact. Only the attempt gate goes — the corridor (11.0), the arrival race and slack (1.0) and
the contest roll are untouched.

**1.0, not `None`, deliberately.** `best_cutoff_on_drive` rolls once per candidate whenever the
probability is not `None`, so this changes *which* candidates are admitted without changing
*how many draws* a drive consumes.

**The stale comment is fixed in both places it appeared** — above the constant and again above
the call site at `attack_drive_clearance.py:1196`. It claimed loose/aggressive defenses "sit
deeper in help lanes and cut off more", which is the inverse of the table (`passive` is the
lowest entry) and mentions a posture that does not enter this path at all.

### Drive path, per game (played arm, SD=1, n=120)

| posture | cell | blow-bys | demoted | demote rate | normal-aggr rate | passive attempts | passive successes |
|---|---|---|---|---|---|---|---|
| loose | off | 11.6 | 6.0 | 51.8% | 53.5% | 0.38/gm | **0.00/gm** |
| loose | **gate** | 11.9 | 8.8 | **73.8%** | **73.5%** | 0.26/gm | 0.23/gm |
| loose | axis | **5.0** | 2.7 | 54.6% | 57.4% | 0.24/gm | 0.00/gm |
| loose | both | **5.1** | 3.4 | 66.9% | 65.8% | 0.33/gm | 0.28/gm |
| normal | off | 12.6 | 6.6 | 52.0% | 53.5% | 0.35/gm | **0.00/gm** |
| normal | **gate** | 12.4 | 9.2 | **73.7%** | 74.0% | 0.28/gm | 0.17/gm |
| base man | off | 11.9 | 6.2 | 52.4% | 53.6% | 0.26/gm | **0.00/gm** |
| base man | **gate** | 12.7 | 9.2 | **71.8%** | 71.9% | 0.36/gm | 0.24/gm |

"Blow-bys" here means *tier-A drives that reached the help-cutoff resolver*, which is the
population the gate acts on.

**The honest framing.** The defect as stated — "a passive defense never attempts a help
rotation" — is real and the flag fixes it (passive successes go from a hard 0.00/gm to
0.17–0.28/gm). But at this fixture's footing the aggression slider is 2, so **passive is only
2–3% of all cutoff attempts**. The measured effect is overwhelmingly *normal* aggression moving
from 0.5 to 1.0. A league where users run passive defenses would see much more of the passive
fix than this footing shows.

**Drives ending with defenders inside the contest radius** (0 / 1 / 2+), at the blow-by moment
before any rotation: essentially unmoved by the gate (loose 1.9/13.7/84.3 → 1.7/13.4/84.9). The
axis shifts it slightly toward more crowding (→ 0.7/10.9/88.4) because its helpers are already
in the lane.

### How far the gate moves the current reference

Not re-cut — both flags ship OFF. For the eventual flip brief:

| cell | arm | fp differing | draws differing | pts/team ref → gate ON (paired) |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | 40/40 | 40/40 | 74.70 → 74.40 (−0.30 ±3.02) |
| `SEED_DEFENSES=1` | played | 40/40 | 40/40 | 71.06 → 73.14 (+2.08 ±3.02) |
| `SEED_DEFENSES=0` | sim | 40/40 | 40/40 | 77.84 → 78.26 (+0.42 ±3.71) |
| `SEED_DEFENSES=0` | played | 40/40 | 40/40 | 75.81 → 76.56 (+0.75 ±3.24) |

Every seed moves in every cell — expected, since the gate fires in every scheme and at every
posture. A flip would need a full re-cut. None of the n=40 point deltas clears its CI.

## 3. Outcomes (played arm, SD=1, n=120 seeds 8000-8119, seed-paired)

CI = 1.96 × SEM of the per-seed difference. `*` = clears.

### Posture LOOSE — the four cells

| metric | off | axis − off | gate − off | both − off |
|---|---|---|---|---|
| points / team | 77.20 ±1.86 | −0.08 ±2.25 | **−2.44 ±1.69 \*** | +0.56 ±2.15 |
| possessions | 38.38 ±1.05 | −1.12 ±1.35 | +0.02 ±0.94 | −1.05 ±1.28 |
| FG% | 42.75 ±1.13 | +0.40 ±1.21 | **−1.34 ±0.92 \*** | +0.14 ±1.16 |
| 3PA share | 38.29 ±0.82 | +0.70 ±1.17 | −0.60 ±1.19 | −0.06 ±1.09 |
| paint share | 26.89 ±0.78 | **−1.55 ±1.16 \*** | −0.77 ±1.02 | **−1.89 ±1.18 \*** |
| rim-attempt share | 4.24 ±0.36 | −0.02 ±0.49 | **−0.42 ±0.41 \*** | −0.07 ±0.48 |
| steals | 16.59 ±0.74 | −0.86 ±1.05 | **+0.90 ±0.75 \*** | −0.38 ±1.08 |
| deflections | 8.87 ±0.55 | −0.24 ±0.78 | +0.61 ±0.61 | −0.25 ±0.81 |
| blocks | 9.50 ±0.62 | −0.78 ±0.85 | −0.28 ±0.73 | −0.78 ±0.81 |
| fouls | 31.93 ±1.16 | −0.85 ±1.57 | +0.53 ±1.28 | −0.68 ±1.59 |
| freeze-miss | 2.50 ±0.30 | −0.20 ±0.41 | −0.02 ±0.39 | **−0.42 ±0.37 \*** |

### Posture NORMAL and BASE MAN — the gate on its own

| metric | normal: gate − off | base man: gate − off |
|---|---|---|
| points / team | +0.34 ±1.52 | +0.80 ±1.64 |
| possessions | +0.78 ±1.19 | −0.83 ±1.08 |
| FG% | −0.36 ±0.97 | −0.05 ±1.08 |
| 3PA share | −0.84 ±0.90 | −0.49 ±0.91 |
| paint share | −0.66 ±1.02 | −0.40 ±1.07 |
| rim-attempt share | +0.11 ±0.46 | −0.04 ±0.46 |
| steals | +0.04 ±0.77 | −0.74 ±0.94 |
| deflections | −0.06 ±0.66 | −0.22 ±0.69 |
| blocks | +0.30 ±0.66 | −0.10 ±0.68 |
| fouls | −0.47 ±1.41 | −0.01 ±1.15 |
| freeze-miss | −0.21 ±0.34 | +0.08 ±0.39 |

**Nothing clears at either posture.** The gate more than doubles help arrivals at both — 52% →
74% demote rate — and the scoreboard does not notice. 0 worker errors, 0 census errors across
all 960 games.

### What this means, plainly

- **The axis does what it was built for and costs nothing.** It is scoreboard-neutral at loose
  (−0.08 ±2.25) while moving the weak-side helper 2.6 units toward the basket and halving
  ball-crowding. Paint share falls 1.55, which is the intended consequence of bodies in the
  lane. On this evidence it is safe to flip on its own merits and should be judged on your eye.
- **The gate is the one that moves the game, and only at loose.** −2.44 points, −1.34 FG%,
  −0.42 rim-attempt share, +0.90 steals. At normal and base man it is invisible. That asymmetry
  makes sense: loose is where the off-ball helper is furthest out of position, so a rotation
  that now actually happens has the most to fix.
- **They are not additive — the axis removes the gate's raw material.** Tier-A blow-bys reaching
  the resolver fall 11.6 → 5.0 per game with the axis on, because helpers already sitting in the
  lane mean fewer drives are graded clean blow-bys in the first place. So the gate's −2.44 at
  loose becomes +0.56 when both are on. **Flipping both is not the same as flipping each.** If
  you want the gate's defensive gain at loose, it is largest *without* the axis; if you want the
  axis's shape, the gate adds little on top of it.

Nothing was retuned to chase any of these numbers.

## 4. Pictures

- [loose-sag-build-off-2026-09-23.png](reports/loose-sag-build-off-2026-09-23.png)
- [loose-sag-build-on-2026-09-23.png](reports/loose-sag-build-on-2026-09-23.png)

Same four steps in both, taken from the flag-OFF run, same seeds as yesterday's counterfactual
PNGs (8009, 8004, 8003, 8005), away-offense steps mirrored, filtered to steps with a man off the
strong side. Mean defender→rim per panel, OFF → ON: **16.9 → 13.7, 13.9 → 11.1, 13.6 → 11.3,
15.1 → 11.7** — identical to
[loose-sag-axis-000/025-2026-09-23.png](reports/loose-sag-axis-025-2026-09-23.png), panel for
panel. The build is the thing that was priced.

## 5. Reported, not fixed: the latent help-defense sign conflict

`BackEnd/utils/shared.py::apply_help_defense_if_triggered` adjusts its help chance by aggression
with the **opposite sign** to the cutoff gate — `passive += 0.20`, `aggressive −= 0.20`, i.e.
passive helps *more* there and *never* here.

**It is dead code.** The function is imported at `BackEnd/main.py:32` and **never called**
anywhere in the tree; `shot_manager.py:3069` documents `help_defender` as "always None now, help
defense removed". So the sign conflict is **latent, not live** — nothing in a running game reads
it. Untouched, as instructed; it is on your list as its own item.

## 6. Suite

| `GOB_MAN_LOOSE_SAG_AXIS` | `GOB_HCO_CUTOFF_NO_GATE` | result |
|---|---|---|
| 0 | 0 | 3273 passed, 20 skipped, 110 xfailed, **0 failed, 0 XPASS** |
| 1 | 0 | 3273 passed, 20 skipped, 110 xfailed, **0 failed, 0 XPASS** |
| 0 | 1 | 3273 passed, 20 skipped, 110 xfailed, **0 failed, 0 XPASS** |
| 1 | 1 | 3273 passed, 20 skipped, 110 xfailed, **0 failed, 0 XPASS** |

26 new guard tests (`ef00985ce`): 15 for the axis, 11 for the gate. Two assertions in my first
draft were wrong and are fixed rather than deleted — the away mirror moves −x not +x, and the
comment test cannot assert the old phrase is absent because the replacement quotes it in order
to correct it, so it pins the correction instead.

---

## Tunable Constants

Reported, not changed.

| constant | value | effect | measured |
|---|---|---|---|
| `GOB_MAN_LOOSE_SAG_AXIS` | `"0"` | gates the blended sag target | built, not flipped |
| `HELP_BASKET_PULL` | normal **0.0**, loose **0.25** | blends the sag target from the ball toward the rim | weak rim 12.07 → 9.46; normal is 0.0 and must stay 0.0 |
| `GOB_HCO_CUTOFF_NO_GATE` | `"0"` | removes the aggression attempt gate | built, not flipped |
| `HCO_CUTOFF_STOP_ATTEMPT_PROB` | passive 0.0 / normal 0.5 / aggressive 1.0 | per-candidate attempt gate | kept and gated; demote rate 52% → 74% when removed |
| `HCO_CUTOFF_PATH_CORRIDOR` | 11.0 | how close a helper must be to rotate | untouched |
| `HCO_CUTOFF_DEFENDER_TIME_SLACK` | 1.0 | arrival-time credit | untouched |
| `HELP_SAG` | normal 0.30 / loose 0.55 | fraction of the way toward the target | untouched |
| `HELP_BASKET_SHADE` | 0.20 | ball-side-scaled rim term | untouched, independent of the axis |
| `HELP_ANCHOR_FLOOR` | 0.30 | min follow in the basket-aligned axis | bind rate 26.4% → 27.2% (population effect) |
| `POSTURE_DENY_DISTANCE` | 2.0 | off-ball deny | untouched; deny returns before this branch |
| `CONTEST_EUCLIDEAN_RADIUS` | 11 | contest proximity gate | ball-crowding 50.3% → 26.2% |

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed−8000)`, CI = 1.96 × SEM. **`SEED_DEFENSES=1`** for all geometry and outcomes
(catalogue seeded with the six real defenses); the reference checks cover SD 1 and 0. Geometry
n=40 seeds 8000-8039, both arms. Outcomes n=120 seeds 8000-8119, played arm, seed-paired.
Posture set through `EQUIV_MAN_POSTURE` (the playbook path). sim arm = `_is_full_simulation`
True throughout; played arm = False only inside the four gated Animator methods at Pattern A.

The drive census wraps `_resolve_hco_help_cutoff` and the posture census wraps
`_apply_defender_posture`; both call the original first and only read arguments and return
values. They draw nothing — proved, not asserted: the reference reproduces 160/160 with the
census installed, in both flag states.

**A note on provenance.** Partway through I repointed a runner at a new cell while a batch was
in flight, which would have left that batch half on one cell and half on another. Those outputs
were discarded and the entire acceptance set was re-run on a single cell. Nothing reported here
comes from the mixed batch.

2,300 games: 160 merge re-confirmation + 160 reference with the axis on + 160 posture-normal
proof + 240 loose baseline and two reproductions + 80 loose geometry with the axis on + 960
outcomes + 160 gate-vs-reference, **0 errors**.

**Both flags OFF. Nothing merged.**
