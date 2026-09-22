# Zone help shade — flipped, reference re-cut

**`GOB_ZONE_HELP_SHADE` is ON by default at `32db56c77`. The reference is re-cut and double
re-baselined. Not merged — Jamie merges.**

| gate | result |
|---|---|
| **kill switch, checked BEFORE re-cutting** | `GOB_ZONE_HELP_SHADE=0` reproduces `equiv_v3_reference_5ea94694f_sinkescape.json` **40/40 on fingerprint AND draws in all four cells** |
| **double re-baseline** | two further **independent** full runs each reproduce the new file **40/40 in all four cells** |
| **`SEED_DEFENSES=0` vs the superseded file** | **byte-identical, 40/40 on both arms** |
| **played-arm freeze-miss** | **the +0.70 was noise — it does not hold** (§5) |
| **same-moment gate** | **100.000 %** identical, 111,145 pairs |
| **§8.1 corrections** | **0** |
| **suite** | **3175 passed, 0 failed, 0 XPASS** — new default *and* kill switch |
| **errors** | **0** across 800 games |

---

## 1. The flip

`BackEnd/utils/shared_defense.py`, commit **`32db56c77`** — default only: `GOB_ZONE_HELP_SHADE`
`"0"` → **`"1"`**. Verified: no env → `True`; `=0` → `False`; `=1` → `True`.

**Nothing else changed.** `HELP_BASKET_SHADE` 0.20, `SIDE_SPAN` 30.0, `CENTRALITY_PLATEAU` (23, 28)
and `CENTRALITY_OUTER` (18, 33) are untouched and still owned by their original callers; `HELP_SAG`
and `HELP_ANCHOR_FLOOR` remain unused by this path; **no clamp was added**; `GOB_BOXOUT_CONTEST`
still `"0"`; nothing retuned.

## 2. The kill switch, proved before anything was re-cut

| cell | fingerprint | draws | errors |
|---|---|---|---|
| sim SD=1 | **40/40** | **40/40** | 0 |
| sim SD=0 | **40/40** | **40/40** | 0 |
| played SD=1 | **40/40** | **40/40** | 0 |
| played SD=0 | **40/40** | **40/40** | 0 |

## 3. The new reference

**`_documentation_master/projects/references/equiv_v3_reference_32db56c77_helpshade.json`** — n=40
seeds 8000–8039, both arms, both `SEED_DEFENSES`, per-seed `fp` / `draws` / `points_per_team` /
`turns` / `possessions`, plus `arm_gap_sim_minus_played` as the **paired per-seed** difference.

### Double re-baseline

| run | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| **B** | **40/40** | **40/40** | **40/40** | **40/40** |
| **C** | **40/40** | **40/40** | **40/40** | **40/40** |

**0 errors across all 480 games.**

### What moved

| | vs the superseded reference |
|---|---|
| **`SEED_DEFENSES=0`, both arms** | **byte-identical — 40/40 fingerprint and 40/40 draws** |
| `SEED_DEFENSES=1`, sim | **40 of 40** seeds differ |
| `SEED_DEFENSES=1`, played | **40 of 40** seeds differ |

Every seed moves at SD=1 here, unlike the sink escape where a handful did not — this shade touches
70 % of zone-with-a-man placements rather than a minority branch.

## 4. `references/README.md`

`equiv_v3_reference_32db56c77_helpshade.json` is **Current**; `equiv_v3_reference_5ea94694f_sinkescape.json`
moved to **Superseded — kept deliberately**, reproduced by **`GOB_ZONE_HELP_SHADE=0`**, with its own
description carried into the superseded row so nothing is lost. **No file deleted**, and every
reference file on disk is listed (13/13, checked).

## 5. The played-arm freeze-miss — it was noise

The flag stage measured the played arm rising **+0.700 ± 0.571 (RESOLVED)** at n=40, and I flagged it
rather than calling it a pass. The brief asked for it again at n=120 from the three reference runs.

**The three reference runs cannot answer it.** A double re-baseline is three *byte-identical* runs of
the same 40 seeds — they carry no information about seed-to-seed variance, so pooling them to 120
would shrink the interval without adding evidence. Reporting ±0.21 off that pooling would have been
wrong.

So I ran **80 fresh seeds (8040–8119)** on the played arm at both flag states:

| seeds | n | OFF | ON | paired Δ | |
|---|---|---|---|---|---|
| 8000–8039 *(the flag stage's own seeds)* | 40 | 1.57 | 2.27 | **+0.700 ± 0.571** | RESOLVED |
| **8040–8119 (fresh)** | **80** | 2.48 | 2.09 | **−0.388 ± 0.451** | within CI |
| all | **120** | 2.17 | 2.15 | **−0.025 ± 0.366** | within CI |

**It does not hold. On independent seeds the effect reverses, and pooled across 120 it is −0.025 —
essentially zero.** The original crossing was one marginal result on one arm out of many comparisons.
Freeze-miss at the new default sits at **2.02/game sim SD=1** and **2.27 played SD=1**, both inside the
2.2–2.5 band, with no new consumer or reason category (`shot_contest_defender_selection` +
`_hco_step_def_xy`; `stamped_empty` + `appended_after_last_stamp`).

## 6. The rest of the gates

| | |
|---|---|
| same-moment gate (contest row vs the coords the emit renders for that step) | **100.000 %** identical, 111,145 pairs, max 0.00 |
| §8.1 per-player coord continuity | **0 corrections**, 187.2 guard calls/game |
| errors | **0** across 800 games |

### Suite

| | passed | failed | XPASS | skipped | xfailed |
|---|---|---|---|---|---|
| new default | **3175** | **0** | **0** | 20 | 112 |
| kill switch | **3175** | **0** | **0** | 20 | 112 |

**No existing test referenced the flag**, so none needed updating and no assertion was relaxed. One
test added (3166 → 3175): `tests/test_zone_help_shade_flags.py`.

| test | why |
|---|---|
| `test_shade_defaults_on` / `test_shade_kill_switch` | the shipped default and the rollback path |
| **`test_constants_are_reused_not_copied`** | doubling `HELP_BASKET_SHADE` must double the shade — inlining 0.20 fails instead of leaving a duplicate to drift from its owner |
| **`test_ramp_is_the_sinks_own`** | widening `zone_sink.SIDE_SPAN` must shrink the shade — same protection for the ramp |
| `test_central_ball_gets_no_shade` | the sink's "ball in the middle, no weak side" rule, which is why the strong side is spared |
| `test_weak_side_moves_toward_the_defended_rim` | the behaviour itself |
| **`test_away_offense_uses_the_mirrored_rim`** | get this wrong and the defender helps at the other end of the floor |
| `test_flag_off_is_a_no_op` | the kill switch at the function, not just the flag |
| **`test_no_clamp_is_applied`** | asserts the signature takes no ring, so a clamp cannot be added later without a deliberate edit — the defenders already outside their polygon are the ones already nearest the rim, so a clamp would undo the fix |

The default test clears the variable, so it pins the **default** rather than the ambient value — which
is why the suite reads 3175 under the kill switch too.

## 7. Footing

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
CI = 1.96 × SEM. **sim arm** = `_is_full_simulation` True throughout; **played arm** = False only
inside the four gated Animator methods at Pattern A.

**Catalogue-seeded state per table**: `SEED_DEFENSES=1` seeds the six real defenses; `SEED_DEFENSES=0`
leaves the catalogue empty and **every zone call plays man**, which is why the SD=0 cells are
byte-identical to the superseded reference. **SD=1 is the footing this change lives in.**

800 games: 160 kill-switch, 480 reference (A, B, C), 160 fresh-seed freeze-miss test (§5), plus 16
same-moment and 16 §8.1. **0 errors.**

## 8. Commits

| commit | contents |
|---|---|
| `32db56c77` | the flip — the default, nothing else |
| `f742088c0` | the new reference + `references/README.md` |
| `e1ee20bcf` | `tests/test_zone_help_shade_flags.py` |

Explicit-path `git add` throughout; no `git add -A`. Working tree clean.

## 9. Not done

- **Not merged.** Jamie merges.
- **No clamp** (§1, and pinned by test). The measured reason is in
  `reports/zone-help-shade-2026-09-22.md` §2.
- **No constant retuned.** If zone wants a different shade strength than man's 0.20, that is the
  tuning pass; it ships reusing the existing value.
- **Outcomes were not re-measured at the flip** — the flag stage's n=120 stands (nothing resolves,
  including paint shots and the inside share).
- **Still open, unrelated to this flip:** `reach_perimeter` is the binding constraint on the
  empty-area sink (`reports/zone-sink-escape-2026-09-21.md` §4).
