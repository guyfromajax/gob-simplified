# `GOB_MAN_LOOSE_SAG_AXIS` and `GOB_HCO_CUTOFF_NO_GATE` flipped ON — both references re-cut

**Both kill switches proved out, three ways.** With `GOB_MAN_LOOSE_SAG_AXIS=0
GOB_HCO_CUTOFF_NO_GATE=0` at the flipped tree, `equiv_v3_reference_09f1b0ca9_boxout.json`
reproduces **160/160** on fingerprint AND draws in all four cells; `axis=1 gate=0` reproduces
the same reference **160/160** (the axis is invisible at base man, where the pull is 0.0); and
`axis=0 gate=1` reproduces the gate-only state measured at the build stage, also **160/160**.

**Both re-baselines held.** `equiv_v3_reference_1f4af0ede_loosesag_nogate.json` was reproduced
**160/160** by each of two further independent full runs, and the new loose-footing baseline
`equiv_v3_loose_baseline_1f4af0ede_loosesag.json` **80/80** by each of two.

---

## 0. develop

develop was 1 commit ahead (`a170bbb4c`) and was merged first. It was a fast-forward of this
branch into develop and back — **zero files differ**, so the tree is byte-identical to
`d26239df1`, at which the current reference had already been verified 160/160. The both-off
kill-switch run in §2 re-proves it at the flipped tree regardless.

## 1. The flips

| commit | flag | change |
|---|---|---|
| `3301d2361` | `GOB_MAN_LOOSE_SAG_AXIS` | default `"0"` → `"1"` |
| `055175781` | `GOB_HCO_CUTOFF_NO_GATE` | default `"0"` → `"1"` |

Defaults only. All nine flag combinations resolve correctly and independently:

| | gate unset | `gate=0` | `gate=1` |
|---|---|---|---|
| **axis unset** | True / True | True / False | True / True |
| **`axis=0`** | False / True | False / False | False / True |
| **`axis=1`** | True / True | True / False | True / True |

Verified untouched at the flipped tree, by direct runtime check:

| | |
|---|---|
| `HELP_BASKET_PULL` | `{"normal": 0.0, "loose": 0.25}` — **normal is 0.0** |
| sag target at normal | the ball **exactly** (`(68.0, 44.0)` in, `(68.0, 44.0)` out) |
| `HELP_SAG` / `HELP_ANCHOR_FLOOR` / `HELP_SAG_JITTER` / `HELP_BASKET_SHADE` | 0.30-0.55 / 0.30 / 0.10 / 0.20 |
| `POSTURE_DENY_DISTANCE` | 2.0 |
| `HCO_CUTOFF_STOP_ATTEMPT_PROB` | `{"passive": 0.0, "normal": 0.5, "aggressive": 1.0}` — **kept and gated, not deleted** |
| `HCO_CUTOFF_PATH_CORRIDOR` / `..._TIME_SLACK` | 11.0 / 1.0 |

And, comparing the flag off against the shipped default on the same geometry: **normal, deny,
the inside-man lock and the on-ball cushion are all byte-identical**. No clamp. Nothing retuned.
Every other flag keeps its default — `GOB_BOXOUT_CONTEST`, `GOB_MAN_HELP_SHADE`,
`GOB_ZONE_HELP_SHADE`, `GOB_ZONE_SINK_ESCAPE`, `GOB_PLACEMENT_FREEZE` all still `"1"`.

## 2. The three kill-switch proofs, before any re-cut

| configuration | target | result |
|---|---|---|
| `axis=0 gate=0` | `equiv_v3_reference_09f1b0ca9_boxout` | **160/160** fp + draws, all four cells |
| `axis=1 gate=0` | the same reference, unchanged | **160/160** |
| `axis=0 gate=1` | the gate-only state measured at the build stage | **160/160** |

The middle row is the one worth pausing on: **the axis flag changes nothing at all at the
reference footing**, because that footing runs base man → posture normal → pull 0.0. So while
the README records the rollback as needing both flags by convention,
**`GOB_HCO_CUTOFF_NO_GATE=0` alone is what actually restores the fingerprints.** The axis's own
rollback target is the loose baseline.

## 3. The re-cut — `equiv_v3_reference_1f4af0ede_loosesag_nogate.json`

n=40 seeds 8000-8039, both arms, both `SEED_DEFENSES`, standard equiv-v3 footing.

| independent run | result |
|---|---|
| run 2 (`rb1`) | **160/160** fp + draws |
| run 3 (`rb2`) | **160/160** fp + draws |

Arm gap (sim − played, paired): `SEED_DEFENSES=1` **+1.262 ±3.057**, `SEED_DEFENSES=0`
**+1.700 ±3.381**.

### How each footing moved

| cell | arm | fp differing | draws differing | pts/team old → new (paired) |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | 40/40 | 40/40 | 74.70 → 74.40 (−0.30 ±3.02) |
| `SEED_DEFENSES=1` | played | 40/40 | 40/40 | 71.06 → 73.14 (+2.08 ±3.02) |
| `SEED_DEFENSES=0` | sim | 40/40 | 40/40 | 77.84 → 78.26 (+0.42 ±3.71) |
| `SEED_DEFENSES=0` | played | 40/40 | 40/40 | 75.81 → 76.56 (+0.75 ±3.24) |

**Every seed moves in every cell, and no cell is unexpectedly byte-identical** — which is what
the brief asked me to watch for, since a byte-identical cell would have meant the gate was not
firing there. It fires in all four.

**The cross-check that the movement is entirely the gate:** these four point means are
*identical* to the gate-only measurement taken at the build stage (74.40 / 73.14 / 78.26 /
76.56). The axis contributes nothing here, exactly as §2 predicts. None of the n=40 deltas
clears its CI.

## 4. The new loose-footing baseline — `equiv_v3_loose_baseline_1f4af0ede_loosesag.json`

`EQUIV_MAN_POSTURE=loose`, `SEED_DEFENSES=1`, both arms, n=40. Arm gap **−0.562 ±3.577**.

| independent run | result |
|---|---|
| reproduction 2 (`lrb1`) | **80/80** fp + draws |
| reproduction 3 (`lrb2`) | **80/80** fp + draws |

Against the superseded `equiv_v3_loose_baseline_ef00985ce.json` (both flags off):

| arm | seeds differing | pts/team old → new (paired) |
|---|---|---|
| sim | 40/40 | 78.29 → 76.10 (−2.19 ±3.04) |
| played | 40/40 | 77.17 → 76.66 (−0.51 ±3.90) |

Every seed differs, as it must — this is the footing where both flags act. Future loose work
measures against the new file.

## 5. Gates at the new defaults

Sim arm, `SEED_DEFENSES=1`, seeds 8000-8009:

| | new defaults (both ON) | both kill switches |
|---|---|---|
| same-moment gate | 69,440 / 69,440 = **100%**, max 0.000 | 69,120 / 69,120 = **100%**, max 0.000 |
| §8.1 continuity corrections | **0** of 1,858 calls | **0** of 1,748 calls |
| errors | 0 | 0 |

**Freeze-miss per game, n=120 (seeds 8000-8119), SD=1** — the build stage found nothing
clearing, and that holds:

| arm | both kill switches | new defaults | paired |
|---|---|---|---|
| sim | 2.17 ±0.26 | 2.40 ±0.29 | +0.23 ±0.35 |
| played | 2.17 ±0.31 | 2.26 ±0.28 | +0.08 ±0.39 |

Neither clears. 0 worker errors across those 480 games.

### Drive census at the new defaults

Reported at **both** footings, because the expectation in the brief (≈5.1 blow-bys/game, ≈66.9%
demote) was measured at posture *loose*, and at base man the axis is inert so the gate-only
numbers apply instead.

| footing | cell | blow-bys/gm | demoted/gm | demote rate | normal-aggr rate | passive successes |
|---|---|---|---|---|---|---|
| **loose** | new defaults | **5.3** | 3.7 | **68.9%** | 68.2% | 0.36/gm |
| base man | new defaults | 12.2 | 8.9 | 73.5% | 73.6% | 0.28/gm |
| base man | both kill switches | 12.9 | 6.8 | 52.5% | 54.2% | **0.00/gm** |

The loose footing lands on **5.3 / 68.9%** against the expected ≈5.1 / ≈66.9% — a match (the
build figure was n=120 played, this is n=40 across both arms). Base man matches the gate-only
cell (12.7 / 71.8%), as it must with the axis inert. And the kill-switch row reproduces the
pre-flip behaviour including **passive's hard 0.00 successes**, which is the defect the gate
flag removes. 0 census errors throughout.

Defenders inside the contest radius at the blow-by moment (0 / 1 / 2+): base man
1.9/12.1/85.9% → 2.1/11.1/86.8%; loose 1.2/12.7/86.1%.

## 6. Suite

| configuration | result |
|---|---|
| new defaults (both ON) | **3273 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** |
| `GOB_MAN_LOOSE_SAG_AXIS=0 GOB_HCO_CUTOFF_NO_GATE=0` | **3273 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** |

Tests updated (`1f4af0ede`): the default tests now pin **ON** and the kill-switch tests pin the
rollbacks — which are *different targets*, and the files now say so. No other assertion was
relaxed. Every paired before/after test sets its flag to `"0"` explicitly for the "before"
state; without that they would have silently compared ON against ON. The same applies to the
gate tests that need the gated behaviour — `passive` 0.0, the unmapped 0.5 default, and the
constant-reused check, which would otherwise read 1.0 regardless of the table. The independence
test additionally pins that with both flags unset, both read ON.

## 7. references/README.md

- `equiv_v3_reference_09f1b0ca9_boxout.json` → **Superseded**, reproduced by
  **`GOB_MAN_LOOSE_SAG_AXIS=0 GOB_HCO_CUTOFF_NO_GATE=0`** — both stated explicitly, with the
  note that the gate flag alone is what restores the fingerprints.
- `equiv_v3_reference_1f4af0ede_loosesag_nogate.json` → **Current**.
- `equiv_v3_loose_baseline_1f4af0ede_loosesag.json` → **current loose baseline**;
  `..._ef00985ce.json` marked superseded beside it, with its own rollback recorded.
- **Nothing deleted.** All **18** reference files on disk are listed (verified: 1 `## Current`,
  1 `## Superseded`, 1 `## Posture-footing baselines`, 0 missing).

---

## Tunable Constants

Reported, not changed. Both flips moved a default, not a number.

| constant | value | effect |
|---|---|---|
| `GOB_MAN_LOOSE_SAG_AXIS` | **`"1"` (flipped)** | blends the off-ball help sag target toward the rim; `=0` restores the loose baseline |
| `HELP_BASKET_PULL` | normal **0.0**, loose **0.25** | how far toward the rim; normal 0.0 is why the main reference is blind to this flag |
| `GOB_HCO_CUTOFF_NO_GATE` | **`"1"` (flipped)** | removes the aggression attempt gate; `=0` restores the superseded reference |
| `HCO_CUTOFF_STOP_ATTEMPT_PROB` | passive 0.0 / normal 0.5 / aggressive 1.0 | kept and gated so the rollback is exact |
| `HCO_CUTOFF_PATH_CORRIDOR` / `..._TIME_SLACK` | 11.0 / 1.0 | the race a rotation must still win |
| `HELP_SAG` | normal 0.30 / loose 0.55 | fraction of the way toward the target |
| `HELP_BASKET_SHADE` | 0.20 | ball-side-scaled rim term, independent of the axis |
| `HELP_ANCHOR_FLOOR` | 0.30 | min follow in the basket-aligned axis |
| `HELP_SAG_JITTER` | 0.10 | ±0-10% on the sag |
| `POSTURE_DENY_DISTANCE` | 2.0 | off-ball deny; byte-identical either way |

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed−8000)`, n=40 seeds 8000-8039, CI = 1.96 × SEM. sim arm = `_is_full_simulation`
True throughout; played arm = False only inside the four gated Animator methods at Pattern A.
**Catalogue-seeded state:** `SEED_DEFENSES=1` seeds the six real defenses; `SEED_DEFENSES=0`
leaves the catalogue empty so every zone call plays man. The main reference covers both; the
loose baseline and all gate/freeze-miss numbers are SD=1. Runs at the new defaults set neither
flag, so they walk the shipped defaults. Posture set through `EQUIV_MAN_POSTURE` (the playbook
path).

The drive and posture censuses wrap `_resolve_hco_help_cutoff` and `_apply_defender_posture`,
call the original first and only read arguments and return values. They draw nothing — proved,
not asserted: the reference reproduces 160/160 with them installed, in three flag states.

1,760 games: 480 kill-switch proofs + 480 re-cut and double re-baseline + 240 loose baseline and
two reproductions + 480 freeze-miss, plus 40 probe games. **0 errors.**

**Not merged. Jamie merges.**
