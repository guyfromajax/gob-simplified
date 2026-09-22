# Placement freeze + single build — flipped, reference re-cut

**Both defaults are ON at `5cc98ee3e`. The reference is re-cut and double re-baselined. Not merged —
Jamie merges.**

| gate | result |
|---|---|
| **kill switch, checked BEFORE re-cutting** | `GOB_PLACEMENT_FREEZE=0 GOB_PLACEMENT_SINGLE_BUILD=0` reproduces `equiv_v3_reference_70f7dd021_b1a.json` **40/40 on fingerprint AND draws in all four cells**, counters at zero |
| **double re-baseline** | two further **independent** full runs each reproduce the new file **40/40 on fp AND draws in all four cells** |
| **freeze-miss** | **2.20 / game** at sim SD=1 — equal to Stage 3, not higher |
| **same-moment gate** | **100.000 %** identical, 139,890 pairs |
| **§8.1 corrections** | **0** (186.5 guard calls/game) |
| **suite** | **2858 passed, 0 failed, 0 XPASS** — at the new defaults *and* under the kill switch |
| **errors** | **0** across 640 games |

---

## 1. The flip

`BackEnd/utils/placement_freeze.py`, commit **`5cc98ee3e`** — defaults only:

| flag | line | was | now |
|---|---|---|---|
| `GOB_PLACEMENT_FREEZE` | `enabled()` | `"0"` | **`"1"`** |
| `GOB_PLACEMENT_SINGLE_BUILD` | `single_build_enabled()` | `"0"` | **`"1"`** |

**Both kill switches still work, and the conjunction is untouched.** Verified directly:

| env | `enabled()` | `single_build_enabled()` |
|---|---|---|
| *(none — shipped default)* | True | True |
| `FREEZE=0` | False | **False** |
| `SINGLE_BUILD=0` | True | **False** — drops back to 2a |
| `FREEZE=0 SINGLE_BUILD=1` | False | **False** — the conjunction holds |

Nothing else changed. `GOB_BOXOUT_CONTEST` is still `"0"` in the tree, nothing was retuned, and
`crash_destination.py` was not touched.

## 2. The kill switch, proved before anything was re-cut

At the **new defaults**, with `GOB_PLACEMENT_FREEZE=0 GOB_PLACEMENT_SINGLE_BUILD=0` set explicitly:

| cell | fingerprint | draws | freeze-miss | builds skipped | errors |
|---|---|---|---|---|---|
| sim SD=1 | **40/40** | **40/40** | 0 | 0 | 0 |
| sim SD=0 | **40/40** | **40/40** | 0 | 0 | 0 |
| played SD=1 | **40/40** | **40/40** | 0 | 0 | 0 |
| played SD=0 | **40/40** | **40/40** | 0 | 0 | 0 |

The old behaviour is still reachable, and the counters prove the new code is genuinely inert rather
than merely producing the same numbers.

## 3. The new reference

**`_documentation_master/projects/references/equiv_v3_reference_5cc98ee3e_freeze.json`**

n=40 seeds 8000–8039, both arms, both `SEED_DEFENSES`, per-seed `fp` / `draws` /
`points_per_team` / `turns` / `possessions`, plus `arm_gap_sim_minus_played` as the **paired per-seed**
difference (not quadrature), and the flags block updated with both new defaults.

### Double re-baseline

Run A cut the file. Runs B and C are independent full re-runs:

| run | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| **B** — fp / draws | **40/40** | **40/40** | **40/40** | **40/40** |
| **C** — fp / draws | **40/40** | **40/40** | **40/40** | **40/40** |

**0 errors across all 480 games.** A reference that cannot reproduce itself is not a reference; this
one reproduces itself twice.

## 4. `references/README.md`

- `equiv_v3_reference_5cc98ee3e_freeze.json` is **Current**, with the tree, the date, and one line on
  what changed.
- `equiv_v3_reference_70f7dd021_b1a.json` moved to **Superseded — kept deliberately**, reproduced by
  **`GOB_PLACEMENT_FREEZE=0 GOB_PLACEMENT_SINGLE_BUILD=0`**, with the note that the freeze switch
  alone suffices because Stage 3 is inert without it. **No file was deleted.**

## 5. Gates at the new defaults

### Freeze-miss — runs A+B+C, 120 games per cell

| cell | per game | consumers | reasons | builds skipped (ceiling) |
|---|---|---|---|---|
| **sim SD=1** | **2.20** | shot-contest 234, `_hco_step_def_xy` 30 | `stamped_empty` 249, `appended` 15 | 11.5 % (11.5 %) |
| sim SD=0 | 0.38 | `_hco_step_def_xy` 45 | `appended` 45 | 5.9 % (5.9 %) |
| played SD=1 | 1.85 | shot-contest 204, `_hco_step_def_xy` 18 | `stamped_empty` 207, `appended` 15 | 12.3 % (12.3 %) |
| played SD=0 | 0.28 | `_hco_step_def_xy` 33 | `appended` 33 | 5.8 % (5.8 %) |

**2.20/game at sim SD=1 — identical to Stage 3's figure, not higher.** Skips still sit exactly at the
ceiling, so nothing available is being left behind. As before, ~89 % of the residual is the
shot-contest selection reaching a step whose stamp produced an *empty* row: a pre-existing gap the
freeze surfaces rather than creates.

### Same-moment gate, §8.1, errors

| | |
|---|---|
| same-moment gate (contest row vs the coords the emit renders for that same step), sim SD=1, n=20 | **100.000 % identical**, 139,890 pairs, mean 0.0000, max 0.00 |
| §8.1 per-player coord continuity | **0 corrections**, 186.5 guard calls/game |
| errors | **0** across 640 games |

### Suite

| | passed | failed | XPASS | skipped | xfailed |
|---|---|---|---|---|---|
| new defaults | **2858** | **0** | **0** | 20 | 112 |
| kill switch (`FREEZE=0 SINGLE_BUILD=0`) | **2858** | **0** | **0** | 20 | 112 |

**No test pinned the old `"0"` defaults, so no test needed updating** — I grepped `tests/` for both
flag names and for `placement_freeze` and found nothing. **No assertion anywhere was relaxed.**

**One test was added** (2850 → 2858), `tests/test_placement_freeze_flags.py`, matching the precedent
of `tests/test_rebound_arrival_flags.py` at the rebound-arrival flip. It pins:

| test | why |
|---|---|
| `test_freeze_defaults_on` / `test_single_build_defaults_on` | the two shipped defaults — flipping either should require editing this file and saying why |
| `test_freeze_kill_switch_turns_both_off` | the rollback path to the superseded reference |
| `test_single_build_kill_switch_leaves_the_freeze_on` | the intermediate state (2a without Stage 3) stays reachable |
| `test_single_build_is_inert_without_the_freeze` | **the conjunction** — the one property that makes the two flags safe to ship together |
| `test_discardable_needs_both_rows` | the skip predicate must demand a defender **and** an offense row, or a pre-seeded post-subtle beat qualifies and the SIM arm's coord write at `:5030` loses its offense row |
| `test_frozen_defense_never_invents_a_row` | rule 26 — absent means absent |
| `test_miss_reason_distinguishes_never_stamped_from_stamped_empty` | the freeze-miss reason the acceptance test is read through |

## 6. What the flip moved, for the record

Kill switch (= the superseded reference) vs the new defaults, n=40 paired per seed:

| cell | resolved at n=40 | within CI |
|---|---|---|
| **sim SD=1** | draws/game **−4,676 ± 1,157** | pts/team −1.39 ± 3.96, FG% −0.61 ± 1.94, interceptions +0.55 ± 0.88, possessions −0.25 ± 2.35, turns −0.30 ± 11.93 |
| sim SD=0 | *(none)* | everything, incl. draws −628 ± 723 |
| **played SD=1** | draws −5,117 ± 1,291; turns −10.70 ± 8.95; fouls −2.88 ± 2.00 | pts/team −2.77 ± 3.10, FG% −1.42 ± 1.90, interceptions +0.00 ± 0.75 |
| played SD=0 | draws −1,015 ± 656 | everything else |

`draws` is mechanical — Stage 3 removes them by construction. **The three played-SD=1 crossings
(turns, fouls) are the same marginal ones Stage 3 flagged**, out of ~36 metric×cell comparisons, and
they remain **unresolved**: the n=120 run in Stage 3 was sim-arm only. They are carried forward as an
open item, not as a finding, and not as something the flip settled.

Stage 3's n=120 sim SD=1 result stands: interceptions +0.225 ± 0.521, pts/team −0.592 ± 2.134,
FG% −0.346 ± 1.177 — **nothing resolves**, and resolving a +0.40/game interception shift would need
**n ≈ 204**.

## 7. Footing

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
n=40 seeds 8000–8039, CI = 1.96 × SEM. **sim arm** = `_is_full_simulation` True throughout;
**played arm** = False only inside the four gated Animator methods at Pattern A.

**Catalogue-seeded state stated per table**: `SEED_DEFENSES=1` seeds the six real defenses;
`SEED_DEFENSES=0` leaves the catalogue empty and **every zone call plays man**, which is why the
freeze-miss rate is ~7× lower and the build-skip rate halves at SD=0. **SD=1 is the production
footing.**

640 games total: 160 kill-switch + 480 reference (A, B, C). **0 errors.**

## 8. Commits

| commit | contents |
|---|---|
| `5cc98ee3e` | the flip — both defaults, nothing else |
| `52c999893` | the new reference + `references/README.md` |
| `486ee96e5` | `tests/test_placement_freeze_flags.py` |

Explicit-path `git add` throughout; no `git add -A`. Working tree clean.

## 9. Not done

- **Not merged.** Jamie merges.
- **Seam B** (the drive reconstruction, `attack_drive_clearance.py:1230–1272`) is still open — it
  cannot read the frozen grid because it computes ends for beats it is creating. It needs its own
  design.
- **The played-arm n=120** was not run, so §6's three marginal crossings stay open.
- **The `stamped_empty` freeze-miss residual** (~2/game, sim SD=1) is reported, not fixed — it is a
  pre-existing gap in what the build produces for some steps.
