# Zone sink escape — flipped, reference re-cut

**`GOB_ZONE_SINK_ESCAPE` is ON by default at `5ea94694f`. The reference is re-cut and double
re-baselined. Not merged — Jamie merges.**

| gate | result |
|---|---|
| **kill switch, checked BEFORE re-cutting** | `GOB_ZONE_SINK_ESCAPE=0` reproduces `equiv_v3_reference_5cc98ee3e_freeze.json` **40/40 on fingerprint AND draws in all four cells**, every escape counter **0** |
| **double re-baseline** | two further **independent** full runs each reproduce the new file **40/40 on fp AND draws in all four cells** |
| **`SEED_DEFENSES=0` vs the superseded file** | **byte-identical, 40/40 on both arms** — zone does not exist there, so the escape cannot fire |
| **freeze-miss** | 2.48 /game sim SD=1 — **within noise** of 2.20 (§5) |
| **same-moment gate** | **100.000 %** identical, 111,805 pairs |
| **§8.1 corrections** | **0** (183.0 guard calls/game) |
| **suite** | **3160 passed, 0 failed, 0 XPASS** — at the new default *and* under the kill switch |
| **errors** | **0** across 640 games |

---

## 1. The flip

`BackEnd/utils/zone_sink.py`, commit **`5ea94694f`** — default only:

| flag | was | now |
|---|---|---|
| `GOB_ZONE_SINK_ESCAPE` | `"0"` | **`"1"`** |

Verified directly: no env → `True`; `=0` → `False`; `=1` → `True`.

**Nothing else changed.** `RIM_FLOOR` 4.0 and `MIN_SEPARATION` 2.0 unchanged; `reach_perimeter` 8.0 /
`reach_spanning` 7.0 / `reach_interior` 5.0 and `basket_weak` 0.75 / `basket_strong` 0.15 untouched;
`GOB_BOXOUT_CONTEST` still `"0"`; nothing retuned.

## 2. The kill switch, proved before anything was re-cut

At the **new default**, with `GOB_ZONE_SINK_ESCAPE=0` set explicitly:

| cell | fingerprint | draws | escape counters | errors |
|---|---|---|---|---|
| sim SD=1 | **40/40** | **40/40** | 0 | 0 |
| sim SD=0 | **40/40** | **40/40** | 0 | 0 |
| played SD=1 | **40/40** | **40/40** | 0 | 0 |
| played SD=0 | **40/40** | **40/40** | 0 | 0 |

The counters being zero is the part that matters: the old numbers are reproduced because the new code
is genuinely inert, not because two different code paths happen to agree.

## 3. The new reference

**`_documentation_master/projects/references/equiv_v3_reference_5ea94694f_sinkescape.json`**

n=40 seeds 8000–8039, both arms, both `SEED_DEFENSES`, per-seed `fp` / `draws` / `points_per_team` /
`turns` / `possessions`, plus `arm_gap_sim_minus_played` as the **paired per-seed** difference, and
the flags block updated.

### Double re-baseline

| run | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| **B** — fp / draws | **40/40** | **40/40** | **40/40** | **40/40** |
| **C** — fp / draws | **40/40** | **40/40** | **40/40** | **40/40** |

**0 errors across all 480 games.**

### What moved, and what did not

| | vs the superseded reference |
|---|---|
| **`SEED_DEFENSES=0`, both arms** | **byte-identical — 40/40 fingerprint and 40/40 draws** |
| `SEED_DEFENSES=1`, sim | **36 of 40** seeds differ |
| `SEED_DEFENSES=1`, played | **37 of 40** seeds differ |

The SD=0 identity is the structural check: without the catalogue every zone call plays man, there is
no empty-area defender, and the escape cannot fire. The reference now records that rather than leaving
it to be inferred.

**The four sim seeds (and three played) whose fingerprint is unchanged are seeds where the escape
never changed a decision** — it still moved defenders on those turns, it just never moved one across
a contest boundary. "Every seed differs" would have been the natural thing to write and it would have
been wrong.

## 4. `references/README.md`

- `equiv_v3_reference_5ea94694f_sinkescape.json` is **Current**, with tree, date and one line on what
  changed, including the SD=0 identity.
- `equiv_v3_reference_5cc98ee3e_freeze.json` moved to **Superseded — kept deliberately**, reproduced
  by **`GOB_ZONE_SINK_ESCAPE=0`**. **No file was deleted.**

## 5. Gates at the new default

### Freeze-miss

**2.48 /game at sim SD=1** (n=120 games, from the three reference runs), against the 2.20 baseline.

Consumers and reasons are unchanged in kind — `shot_contest_defender_selection` 246 +
`_hco_step_def_xy` 51, reasons `stamped_empty` 270 + `appended_after_last_stamp` 27 — **no new
consumer and no new reason category**. The paired measurement in
`reports/zone-sink-escape-2026-09-21.md` §2 put the difference at **+0.275 ± 0.530 (within CI)** with
the played arm moving **equal and opposite** (−0.275 ± 0.525), which is the signature of noise rather
than a regression. **Within noise, as the brief required — stated as a measurement, not as a pass.**

### Escape counters at the new default (sim SD=1, per game)

| counter | /game |
|---|---|
| `clamp_would_bind` | 3,660 |
| **`escaped`** | **2,551** (69.7 %) |
| `not_rim_ward` (still clamped, as designed) | 1,109 (30.3 %) |
| `rim_floor_bound` | 11.3 |
| `separation_bound` | 36.8 |
| `escape_nulled` | 0.0 |

The guardrails bind on **1.9 %** of escapes — bounds, not shapers, exactly as at the flag stage.

### The rest

| | |
|---|---|
| same-moment gate (contest row vs the coords the emit renders for that step) | **100.000 %** identical, 111,805 pairs, max 0.00 |
| §8.1 per-player coord continuity | **0 corrections**, 183.0 guard calls/game |
| errors | **0** across 640 games |

### Suite

| | passed | failed | XPASS | skipped | xfailed |
|---|---|---|---|---|---|
| new default | **3160** | **0** | **0** | 20 | 112 |
| kill switch (`GOB_ZONE_SINK_ESCAPE=0`) | **3160** | **0** | **0** | 20 | 112 |

**No existing test referenced the flag**, so none needed updating and no assertion was relaxed. One
test was **added** (3151 → 3160): `tests/test_zone_sink_escape_flags.py`, following
`tests/test_placement_freeze_flags.py`.

| test | why |
|---|---|
| `test_escape_defaults_on` | the shipped default |
| `test_escape_kill_switch` | the rollback path to the superseded reference |
| **`test_rim_floor_is_the_basket_spot_distance`** | asserts `RIM_FLOOR` **equals the computed rim→`basketSpot` distance**, not the literal 4.0 — so a court-geometry change fails the test instead of silently invalidating the derivation |
| `test_min_separation_unchanged` | the measured p5; changing it is a tuning decision |
| `test_reach_and_sink_weights_untouched` | reach and the basket weights are the **next** lever and the report prices them; this catches a silent pull |
| `test_escape_only_keeps_rim_ward_movement` | the rule itself — rim-ward escapes, away-from-rim stays clamped |
| `test_escape_stops_at_the_rim_floor` / `test_escape_respects_minimum_separation` | a guardrail that binds stops him rather than letting him pass |
| `test_counters_exist_and_reset` | the counters the acceptance test is read through |

The default test uses a fixture that clears the variable, so it pins the **default** rather than
whatever is ambient — which is why the suite reads 3160 under the kill switch too.

## 6. Footing

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
n=40 seeds 8000–8039, CI = 1.96 × SEM. **sim arm** = `_is_full_simulation` True throughout;
**played arm** = False only inside the four gated Animator methods at Pattern A.

**Catalogue-seeded state stated per table**: `SEED_DEFENSES=1` seeds the six real defenses;
`SEED_DEFENSES=0` leaves the catalogue empty and **every zone call plays man** — which is exactly why
the SD=0 cells are byte-identical to the superseded reference. **SD=1 is the footing this change
lives in.**

640 games: 160 kill-switch + 480 reference (A, B, C), plus 16 same-moment and 16 §8.1. **0 errors.**

## 7. Commits

| commit | contents |
|---|---|
| `5ea94694f` | the flip — the default, nothing else |
| `409aac554` | the new reference + `references/README.md` |
| `10e651987` | `tests/test_zone_sink_escape_flags.py` |

Explicit-path `git add` throughout; no `git add -A`. Working tree clean.

## 8. Not done

- **Not merged.** Jamie merges.
- **`reach_perimeter` is now the binding constraint** and was not touched
  (`reports/zone-sink-escape-2026-09-21.md` §4: lifting it would move the perimeter defender a further
  **1.69** units toward the rim, roughly the same size as the escape itself). That is the next lever
  and it belongs in the tuning pass.
- **Out of scope, unchanged:** the zone defender *with* a man in his area still has no basket shade
  (`reports/offball-ball-read-2026-09-21.md` §4). Separate item.
- **The played arm was not re-run at n=120** for outcomes; the n=40 and n=120 sim results in the flag
  report stand (nothing resolves, including paint shots).
