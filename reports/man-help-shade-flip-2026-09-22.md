# `GOB_MAN_HELP_SHADE` flipped ON by default — reference re-cut

**The kill switch is proven.** With `GOB_MAN_HELP_SHADE=0` set explicitly at the flipped tree,
`equiv_v3_reference_32db56c77_helpshade.json` reproduces **160/160** on fingerprint AND draws
across all four cells, with every man-shade counter at zero — checked *before* anything was
re-cut.

**The re-baseline held.** `equiv_v3_reference_f2a060488_manhelpshade.json` was cut at the new
default and then reproduced **160/160** by each of two further independent full runs.

---

## 1. The flip

`BackEnd/utils/shared_defense.py`, commit **`f2a060488`** — the default only:

```
-    return os.environ.get(MAN_HELP_SHADE_FLAG, "0") == "1"
+    return os.environ.get(MAN_HELP_SHADE_FLAG, "1") == "1"
```

| state | `man_help_shade_enabled()` |
|---|---|
| no env var | **True** |
| `GOB_MAN_HELP_SHADE=0` | False |
| `GOB_MAN_HELP_SHADE=1` | True |

Untouched, verified after the flip: `HELP_BASKET_SHADE` 0.20, the `(1 + weakness)` scale,
`help_side_weakness`, `zone_sink.SIDE_SPAN` 30.0, `CENTRALITY_PLATEAU` (23.0, 28.0),
`HELP_SAG` {normal 0.30, loose 0.55}, `HELP_SAG_JITTER` 0.10, `HELP_ANCHOR_FLOOR` 0.30,
`POSTURE_DENY_DISTANCE` 2.0. **No clamp. Nothing retuned. Posture still does not scale the
shade** — §7 of the build report stays unbuilt. `GOB_BOXOUT_CONTEST` still defaults `"0"`.

## 2. Kill switch, before the re-cut

`GOB_MAN_HELP_SHADE=0` at `f2a060488` vs `equiv_v3_reference_32db56c77_helpshade.json`:

| cell | sim | played |
|---|---|---|
| `SEED_DEFENSES=1` | 40/40 | 40/40 |
| `SEED_DEFENSES=0` | 40/40 | 40/40 |

**160/160 on fingerprint AND draws.** Every man-shade counter in those 160 games reads
`{considered 0, shaded 0, no_shade_middle 0}` — the flag is genuinely inert, not merely
numerically coincident.

## 3. The re-cut and the double re-baseline

`equiv_v3_reference_f2a060488_manhelpshade.json` — n=40 seeds 8000-8039, both arms, both
`SEED_DEFENSES`, standard equiv-v3 footing.

| independent run | fp + draws vs the new reference |
|---|---|
| run 2 (`rb1`) | **160/160** |
| run 3 (`rb2`) | **160/160** |

Arm gap (sim − played, paired): `SEED_DEFENSES=1` **+2.050 ±2.923**, `SEED_DEFENSES=0`
**+5.300 ±3.309**.

### `SEED_DEFENSES=0` is **not** byte-identical, and that is expected

| cell | arm | seeds differing (fp) | seeds differing (draws) |
|---|---|---|---|
| `SEED_DEFENSES=1` | sim | 40 / 40 | 40 / 40 |
| `SEED_DEFENSES=1` | played | 40 / 40 | 40 / 40 |
| `SEED_DEFENSES=0` | sim | 40 / 40 | 40 / 40 |
| `SEED_DEFENSES=0` | played | 40 / 40 | 40 / 40 |

**Why.** This is the mirror image of the zone help shade. There, `SEED_DEFENSES=0` was
byte-identical to its predecessor because an empty defense catalogue means **zone never runs** —
every zone call plays man — so a zone-only change could not touch that footing. Here the change
is to **man** help, and man is exactly what an empty catalogue produces *more* of. The shade
counters say so directly:

| cell | arm | considered | shaded | no-shade (central ball) | shaded / game |
|---|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | 142,412 | 106,758 | 35,654 | 2,669 |
| `SEED_DEFENSES=1` | played | 143,207 | 105,623 | 37,584 | 2,641 |
| `SEED_DEFENSES=0` | sim | 294,381 | **219,098** | 75,283 | **5,477** |
| `SEED_DEFENSES=0` | played | 290,105 | 215,661 | 74,444 | 5,392 |

`SEED_DEFENSES=0` carries **2.05× as many shaded placements** as `SEED_DEFENSES=1`. It moves
*more*, not less. An unexplained SD=0 difference would have been a failure; this one is the
documented footing behaving as documented.

Points per team at the reference cells (n=40, paired vs the superseded file) — reported for
completeness, not as the outcome measurement:

| cell | arm | before | after | paired |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | 73.54 | 75.08 | +1.54 ±2.61 |
| `SEED_DEFENSES=1` | played | 74.12 | 73.03 | −1.10 ±3.97 |
| `SEED_DEFENSES=0` | sim | 76.94 | 80.74 | +3.80 ±3.55 |
| `SEED_DEFENSES=0` | played | 76.08 | 75.44 | −0.64 ±3.81 |

None clears its CI, and all four are consistent with the authoritative n=120 seed-paired
measurement at the flag stage (points −0.06 ±2.10 at normal, +0.53 ±1.87 at loose).

## 4. Gates at the new default

Sim arm, `SEED_DEFENSES=1`, seeds 8000-8009:

| | new default | kill switch |
|---|---|---|
| same-moment gate | 68,050 / 68,050 = **100%**, max 0.000 | 68,910 / 68,910 = **100%**, max 0.000 |
| §8.1 continuity corrections | **0** of 1,884 calls | **0** of 1,870 calls |
| errors | 0 | 0 |

**Freeze-miss per game, n=120 (seeds 8000-8119), SD=1**, reference footing — the flag stage found
nothing clearing its CI, and that holds:

| arm | kill switch | new default | ON − OFF paired |
|---|---|---|---|
| sim | 1.98 ±0.24 | 2.29 ±0.29 | +0.31 ±0.33 |
| played | 2.15 ±0.28 | 2.17 ±0.27 | +0.03 ±0.37 |

Neither clears. 0 worker errors across those 480 games.

**Deny and the inside-man lock, at the new default** (posture=deny, sim, SD=1, n=40), default vs
kill switch:

| check | result |
|---|---|
| identical fingerprint AND draws | **40/40** |
| off-ball calls | 194,569 vs 194,569 |
| inside-man lock | 53,176 (27.33%) vs 53,176 (27.33%) |

Byte-identical. Deny returns before the shade is reached, and the inside-man lock returns before
it too.

## 5. Suite

| run | result |
|---|---|
| `tests/` at the new default | **3191 passed, 20 skipped, 112 xfailed, 0 failed, 0 XPASS** |
| `tests/` under `GOB_MAN_HELP_SHADE=0` | **3191 passed, 20 skipped, 112 xfailed, 0 failed, 0 XPASS** |

`tests/test_man_help_shade_flags.py` updated (`a10de9b2c`): the default test now pins **ON** and
the kill-switch test pins the rollback. **No other assertion was relaxed.** The paired
before/after tests now set `GOB_MAN_HELP_SHADE=0` explicitly for the "before" state — without
that they would have silently compared ON against ON, which is the one way this update could
have quietly weakened the guard.

## 6. references/README.md

- `equiv_v3_reference_32db56c77_helpshade.json` → **Superseded**, reproduced today by
  **`GOB_MAN_HELP_SHADE=0`**.
- `equiv_v3_reference_f2a060488_manhelpshade.json` → **Current**, `f2a060488` (2026-09-22), with
  one line on what changed and why both footings move.
- **Nothing deleted.** All **14** reference files on disk are listed (verified: 1 `## Current`
  heading, 1 `## Superseded` heading, 0 files missing).

---

## Tunable Constants

Reported, not changed. The flip moved a default, not a number.

| constant | value | effect |
|---|---|---|
| `GOB_MAN_HELP_SHADE` | **`"1"` (flipped)** | gates the weak-side scaling; `=0` is the rollback |
| `HELP_BASKET_SHADE` | 0.20 | base of the scaled rim-ward term |
| the scale | `1 + weakness` | 1.0 strong / central ball, 2.0 far weak side |
| `zone_sink.SIDE_SPAN` | 30.0 | the strong/weak ramp, shared with the zone shade |
| `zone_sink.CENTRALITY_PLATEAU` | (23.0, 28.0) | central ball ⇒ no weak side ⇒ no shade (~25% of calls) |
| `HELP_SAG` | normal 0.30 / loose 0.55 | fraction of the way toward the **ball**; untouched |
| `HELP_ANCHOR_FLOOR` | 0.30 | min follow in the basket-aligned axis; bind rate fell 27.3% → 25.8% |
| `HELP_SAG_JITTER` | 0.10 | ±0-10% on the sag |
| `POSTURE_DENY_DISTANCE` | 2.0 | off-ball deny; untouched, and deny is byte-identical |
| `GOB_BOXOUT_CONTEST` | `"0"` | unrelated; still off in the tree |

## Footing

equiv-v3 worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id
`0xE0000+(seed-8000)`, n=40 seeds 8000-8039, CI = 1.96 × SEM. sim arm = `_is_full_simulation`
True throughout; played arm = False only inside the four gated Animator methods at Pattern A.
**Catalogue-seeded state:** `SEED_DEFENSES=1` seeds the six real defenses from
`defenses_export.json`; `SEED_DEFENSES=0` leaves the catalogue empty, so **every zone call plays
man** — which is why SD=0 moves more here, not less. Reference cells use the unset posture (base
man). Runs at the new default set no `GOB_MAN_HELP_SHADE` at all, so they walk the shipped
default rather than an override.

1,120 games in total: 160 kill switch + 480 re-cut and double re-baseline + 480 freeze-miss and
deny, plus 40 probe games. **0 errors.**

**Not merged. Jamie merges.**
