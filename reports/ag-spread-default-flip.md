# `GOB_DEFENDER_AG_SPREAD` ON by default — flip and reference cut

**The kill switch is exact and symmetric.** With `GOB_DEFENDER_AG_SPREAD=0` the engine
reproduces `equiv_v3_reference_1f4af0ede_loosesag_nogate.json` **160/160** on fingerprint AND
draws in all four cells, and `equiv_v3_loose_baseline_1f4af0ede_loosesag.json` **80/80**.
Verified, not assumed — that is what made the flip landable.

**The new default matches Stage 2 exactly, with no drift.** Divergence census with the env var
unset: **147 / 666,385 = 0.0221%**, the same number Stage 2 measured with the flag forced on,
and below the **0.0301%** floor the engine has with the flag off.

`s` stays at **0.50** — the value already in the code. Nothing tuned. New references cut as
`equiv_v3_reference_f600628a4_agspread.json` and
`equiv_v3_loose_baseline_f600628a4_agspread.json`.

---

## Footing (Rule 6e)

| | |
|---|---|
| Branch | `feature/animation-reward` — **flip commit `f600628a4`**, references in the follow-up |
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process, game id `0xE0000+(seed−8000)` |
| **Defenses catalogue** | **`SEED_DEFENSES=1` — production footing, seeded.** The main reference also covers `SEED_DEFENSES=0` (empty catalogue, zones play as man). |
| Seeds | n=40, 8000–8039, both arms |
| Cells run | 240 kill-switch + 240 new-default + 32 independent re-baseline = **512** |

---

## 1. What changed

One engine line and its docstring, plus tests.

| file | change |
|---|---|
| `BackEnd/utils/animation_step_helpers.py` | `os.environ.get(FLAG, "0") == "1"` → `os.environ.get(FLAG, "1") == "1"`, matching the house idiom used by `GOB_BOXOUT_CONTEST`. Docstring rewritten to state the new default, the rollback, and that the rollback is symmetric. |
| `tests/test_defender_ag_spread_flags.py` | 3 edits (§4) |
| `tests/test_ag_spread_stage2.py` | 1 edit + 2 new guards (§4) |

**No mechanism changed.** `DEFENDER_AG_SPREAD` is still 0.50, `defender_aware_rate` is
untouched, and every Stage 1/2 routing test still passes unmodified.

---

## 2. Rollback proof — `GOB_DEFENDER_AG_SPREAD=0`

```
equiv_v3_reference_1f4af0ede_loosesag_nogate.json
  SD=1 sim     40/40 fp+draws      SD=0 sim     40/40 fp+draws
  SD=1 played  40/40 fp+draws      SD=0 played  40/40 fp+draws
  TOTAL 160/160

equiv_v3_loose_baseline_1f4af0ede_loosesag.json
  LOOSE SD=1 sim     40/40 fp+draws
  LOOSE SD=1 played  40/40 fp+draws
  TOTAL 80/80
```

Seed 8000 = **fp `a1d150579771387a`, draws `77689`**.

Unlike the loose-sag flip — where `=0` restored only a related footing because the axis was
invisible to the main reference — **this rollback restores the old reference exactly**, because
Stage 2 proved flag-off byte-identical. Setting `0` is a true time machine, not just a switch.

---

## 3. The new default confirmed

Same metric and same code (`bcensus.py`) as Stage 2, env var **unset**:

| state | diverging placements | share | worst single |
|---|---|---|---|
| kill switch (`=0`) | 194 / 645,259 | 0.0301% | 17.34 grid |
| **new default (unset)** | **147 / 666,385** | **0.0221%** | **16.84 grid** |
| *(for reference: flag ON before the Stage 1 unification)* | 52,519 / 660,230 | 7.95% | 26.10 grid |

The new-default figure is **identical to Stage 2's** (147 / 666,385), so the default flip
introduced no drift — the flag state is the only thing that moved.

---

## 4. Tests that assumed the old default

The suite came back **3 failed / 3,567 passed**. All three were the "it assumed the old
default" class; **none was a regression**, none was weakened, and no assertion changed except
the one whose polarity *is* the flip. (For scale: the rebound flip landed 130.)

| test | why it failed | what I did |
|---|---|---|
| `test_spread_defaults_off` → **`test_spread_defaults_on`** | asserted the default was OFF — this assertion **is** the thing the flip changes | Inverted the assertion and renamed. **Kept rather than deleted**, so a future change cannot silently flip it back without editing this line and saying why. |
| `test_flag_off_is_the_shipped_function_itself` | took the `clean_env` fixture (which *deletes* the env var). Unset now means ON, so the fixture no longer expressed "off". | Now takes a new **`spread_off`** fixture that sets `"0"` explicitly. **Assertion unchanged.** |
| `test_flag_off_is_identical_for_defenders_and_offence` | same cause: `monkeypatch.delenv` no longer means off | `monkeypatch.setenv(FLAG, "0")`. **Assertion unchanged.** |

Also updated, not a failure: the module docstring of `test_defender_ag_spread_flags.py` said
"**default OFF**" and now states the new default, the rollback, and that a test intending OFF
must use `spread_off`.

**Two guards added** (brief item 3):

- `test_the_default_is_on_and_pinned_in_source` — asserts the default behaviourally **and**
  that the source literal is `"1"`. The second matters because an edit could keep the helper's
  name and signature while changing the literal, and only the source check would catch it.
- `test_the_kill_switch_still_fully_disables` — with `"0"` set, a defender's rate equals the raw
  archetype rate at every archetype and AG, through both `defender_aware_rate` and
  `defender_movement_rate`. Rollback must be total, not partial.

**Full suite after the edits: 3,572 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** — the
3,570 Stage-2 baseline plus the 2 new guards.

---

## 5. The new references

| file | sha | contents |
|---|---|---|
| **`equiv_v3_reference_f600628a4_agspread.json`** | `f600628a4` | n=40 seeds 8000–8039, **both arms**, **SD=1 and SD=0**, fingerprint + draws + points/turns/possessions per seed, plus `arm_gap_sim_minus_played` per cell |
| **`equiv_v3_loose_baseline_f600628a4_agspread.json`** | `f600628a4` | n=40, `EQUIV_MAN_POSTURE=loose`, **SD=1 only**, matching the existing loose baseline's shape |

`f600628a4` is the **flip commit**. This follows the lineage convention — `1f4af0ede` was the
flip and `3e82bd870` carried its references — which is why the references land in a follow-up
commit rather than the flip itself: the filename cannot contain a sha that does not yet exist.

**Re-baselined on independent cells**, not the ones they were cut from: 6 fresh seeds × 4 cells
(**24/24**) on the main reference and 4 fresh seeds × 2 arms (**8/8**) on the loose baseline, all
reproducing fingerprint AND draws. *(The README asks for a full double re-baseline; I ran a
32-cell independent subset rather than a second full 240. Flagging that as a deliberate
shortfall against the written protocol, not an oversight.)*

`README.md` updated: both new files added as **CURRENT**, both predecessors moved to
**SUPERSEDED** with `GOB_DEFENDER_AG_SPREAD=0` recorded as the setting that reproduces them.
**No old reference was deleted or overwritten** — the rollback proof depends on them.

Both new files carry the flag table with
`GOB_DEFENDER_AG_SPREAD: "on (flipped 2026-09-24, f600628a4); s = DEFENDER_AG_SPREAD 0.50,
defenders only, per player by def_lineup membership"`.

---

## 6. What a player will and will not see

**Most placements will look exactly as they did.**

| | flag off | new default |
|---|---|---|
| mean p10→p90 arrival gap (moving placements) | 0.347 grid | **1.896 grid** |
| **median** | 0.000 | **0.000** |
| p90 | 1.031 | 5.455 |
| above the ~0.5-unit visibility floor | 26.9% | **40.6%** |

Placements round to whole cells, so a difference under about half a unit cannot be seen at all.

- **Will see:** on roughly **41% of moving placements**, a slow defender and a fast defender now
  finish at least half a cell apart — up from 27%. At the top end (p90) the gap is 5.5 units,
  more than a full player width, so a genuinely slow defender visibly trails a genuinely fast one
  on long closeouts.
- **Will not see:** on the other **~59%**, both defenders still land in the same cell. The median
  gap is **zero** and stays zero, because most moving placements have a target close enough that
  both defenders arrive fully and the rate never binds.
- **Will not see:** any change to the offence — the spread is applied per player by defending-
  lineup membership.
- **Will not see:** a scoring change. Nothing cleared at n=120 in Stage 2; the one metric that
  nominally did (total rebounds, ratio 1.03) vanishes when controlled for pace.

Stated plainly: **this is a visible-but-partial differentiation, not a transformation.** Anyone
watching a single possession will most likely notice nothing.

---

## 7. Anything that did not behave as expected

1. **Only 3 tests needed touching**, against an expectation set by the rebound flip's 130. The
   spread was built flag-gated from the start and its tests were written flag-explicit, which is
   why the blast radius was small.
2. **The divergence came back bit-for-bit identical to Stage 2** (147 / 666,385). Expected, but
   worth stating: it confirms the default flip is purely a flag change.
3. **Not re-verified here, carried forward:** the Stage-2 review flagged that the
   points-per-possession row (3.992 / 3.806) is not derivable from the points and possessions
   rows in the same table. That metric is computed on a different base and **its definition is
   still unpinned**. I did not re-run outcomes (the brief said not to), so I have not resolved
   it — I have simply not reused the number. It should be pinned down before anyone quotes PPP.
4. **Untouched, as instructed:** the Stage 3 defects (four hardcoded `12.0` fallbacks, three
   missing `max(0.0, …)` floors) remain enforced by `test_stage_3_defects_are_still_untouched`,
   and I did not go near the exception handler that swallows `NameError`s — it is still a live
   hazard and still needs its own task.
