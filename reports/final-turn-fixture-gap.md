# Final Turn fixture gap — completed, and what those tests were actually testing

**The fixture is fixed and the animator build now genuinely runs** — the FT-Task 1 fallback
fires **0 times** where it previously fired on every one of these tests. All five pass, and the
full suite is green at **3,572 passed / 0 failed** with `GOB_STRICT_EXCEPTIONS=1`.

**But the more useful answer is to the second question.** Those five tests pass **identically on
both paths** — with the real animator build running *and* with it forced to fail. Their
assertions cannot tell the two apart. They were never testing the animator build; it merely ran
on the way past. **The Final Turn defender coord-sync has no test coverage at all**, and until
now it was not even being executed.

**No engine change was needed.** `git diff --stat` is two files, both under `tests/`.

---

## Footing

This is a **tests-only** change, so **no reference run is required** and none was performed —
nothing under `BackEnd/` was touched, so the equiv-v3 fingerprints cannot move. If that had
stopped being true I would have stopped and said so.

The one measured number below (the suite) is: `pytest` over the whole repo,
`GOB_STRICT_EXCEPTIONS=1` (the conftest default since `a4359b8aa`), `GOB_DEFENDER_AG_SPREAD`
unset = ON. No equiv-v3 worker, no seeds, no defenses catalogue involved — Rule 6e's footing
fields do not apply to a pytest run, and I am not going to invent them.

---

## 1. Where I read the real `strategy_calls` shape

`BackEnd/models/team_manager.py:435-444` — `TeamManager.__init__`'s **fresh-game**
initialisation. Eight keys, every value `None`:

```python
self.strategy_calls = {
    "offense_call": None, "defense_call": None,
    "aggression_override": None, "tempo_override": None,
    "press_override": None, "trap_override": None,
    "press_trap_override": None, "aggression_roll": None,
}
```

Cross-checked three ways:

- `team_manager.py:421-431` — the *restore-from-saved* branch merges saved calls over exactly
  the same default keys, so the key set is the same either way.
- `turn_manager.py:3501-3517` — a defensive re-init if the attribute is missing entirely, with
  the same names.
- Every read site: `aggression_call` ×12, `offense_call` ×6, `defense_call` ×4,
  `aggression_override` ×4, `tempo_override` ×2, `tempo_call` ×2, `press_trap_override` ×2.

### `aggression_call` is deliberately NOT in the stub

It is the key the failing line reads — and it is **not part of the canonical init**. It is
written per turn by `turn_manager.py:3580-3586`, and every reader uses
`.get("aggression_call", "normal")`. So omitting it reproduces a real fresh game exactly, and
the failing line resolves to `"normal"` through the getter's own default rather than through a
value I made up. Adding it would have been inventing production state.

---

## 2. Attributes added — and the cascade that never happened

**One attribute. That is all.**

| attribute | added to | the real-path requirement that justifies it |
|---|---|---|
| `strategy_calls` | 4 team stubs in `test_final_turn_coordinate_contract.py`, 2 in `test_final_turn_pacing.py` | `defender_placement.py:1030` — `game.defense_team.strategy_calls.get("aggression_call", "normal")`, reached once the FT-Task 1 animator build actually runs |

Both files gained a shared `_fresh_strategy_calls()` helper that mirrors `TeamManager.__init__`
and documents why `aggression_call` is absent.

> **The brief expected a cascade and there wasn't one.** Once `strategy_calls` was present the
> animator build completed on the first attempt — no second missing attribute, no third. The
> existing stubs were already complete enough for the whole build; they were one key short of
> ever being allowed to try. Nothing was added that the path does not demand.

Six stubs were patched, not five, because `_alignment_manager` in the coordinate-contract file
builds its own team pair, and three separate `_game`-style builders share an identical two-line
team construction.

---

## 3. What those five tests are actually testing

### They all pass — on both paths

I forced the animator build to fail exactly as the incomplete stub used to (monkeypatched
`phase_resolution.Animator` to raise the same `AttributeError`, with strict off so the handler
swallows it), and re-ran the five:

| | result |
|---|---|
| real animator build running (`strict on`, fixture fixed) | **5 passed** |
| build forced to fail → fallback path (the old behaviour) | **5 passed** |

**Identical. The assertions cannot distinguish the two paths.**

### Why — and why this is not a mis-assertion

| test | asserts | does the animator build affect it? |
|---|---|---|
| `test_final_turn_attack_shot_unwraps_attack_drive_steps` | `final_turn`, `late_clock_eoq`, skeleton has 4 steps, step 2 = `drive`, step 3 = `shoot`, step-0 floor ≈ 3.0 | **No** |
| `test_final_turn_attack_step0_floor_stamps_hold` | `15 < floor < 29` | **No** |
| `test_final_turn_outside_step0_floor_stamps_hold` | `final_turn`, `late_clock_eoq`, `15 < floor < 29` | **No** |
| `test_pacing_hold_floor_accounts_for_move_beats` | not FLSS-routed, `floor < 26` | **No** |
| `test_resolve_reuses_gate_shooter_without_repick` | gate shooter not re-picked (`calls["n"] == 0`) | **No** |

Every one asserts on the **skeleton, the pacing floors, or the shooter pick** — all produced
*upstream* of FT-Task 1. The build's job is to sync **defender coordinates** into the game before
`resolve_shot`; none of these tests looks at a defender coordinate.

> **So the five are not testing the wrong thing, and their assertions are not too loose for what
> they claim.** Each asserts what its name says, and each passes for the right reason. The
> finding is narrower and sharper: **the FT-Task 1 defender coord-sync itself has zero test
> coverage.** It sat in the middle of five tests' execution path, failed silently in all of
> them, and not one assertion noticed — because not one was ever looking at it.
>
> The fixture fix means it now *runs*. It still is not *tested*. A test that asserts a defender
> coordinate after a Final Turn shot would be new coverage, and is a separate task.

**Nothing was weakened, re-stubbed around, or marked xfail.** No assertion was touched.

---

## 4. The wider surface

### Tests that reach an Animator build through `phase_resolution` — 32

Measured by wrapping `phase_resolution.Animator` for the whole suite and recording which tests
call `skeleton_to_animations`:

| area | tests | calls |
|---|---|---|
| `test_quarter_starts.py` | 9 | 50–114 each |
| `test_possession_changes.py` | 5 | 4–42 each |
| `test_sim_crash_apply.py` · `test_sim_hco_coord_write.py` | 4 | 25–33 each |
| **the five fixed here** | 5 | 1 each |
| `test_turn_manager.py` · `test_turn.py` · `test_game_manager.py` | 5 | 1 each |
| `test_lineup_change_sprites.py` · `test_real_quarter_stats.py` · `test_settings_persistence.py` | 3 | 23–26 each |

### Tests where the build FAILED and silently fell back — **0**

After the fix, **no test in the suite is running the FT-Task 1 fallback**. Before it, the five
above were.

The high-volume callers (`test_quarter_starts`, `test_possession_changes`, …) use **real
`GameManager` objects**, so they always had `strategy_calls` and were never affected.

### Stubs that still lack `strategy_calls` — 32 across 14 files, and why I left them

A scan for team-shaped `SimpleNamespace` stubs (`team_id` + `lineup`) found **46** across 18
files; **14 now carry `strategy_calls`** (the 12 here plus 2 pre-existing in
`test_dynamic_fcp_engine.py` and `test_hco_post_subtle_grid.py`).

The other 32 are in `test_dreb_fast_break_arming`, `test_eoq_clock_progression`,
`test_fast_break_rr_triangle_updates`, `test_fb_shot_logical_coords`, `test_fb_step_state_contract`,
`test_fcp_hct_uess_contract`, `test_final_turn_entry_pass_chain`, `test_loose_ball`,
`test_motion_shot_spot_classification`, `test_opening_lineup_snapshot`,
`test_quarter_and_foulout_sync`, `test_shot_system_regressions`, `test_sim_crash_apply`,
`test_steal_fast_break_routing`.

**None of them reaches the FT-Task 1 build** — the fallback counter is 0 for the whole suite, and
none appears in the reached-list except `test_sim_crash_apply`, which gets there through a real
`GameManager`. Adding `strategy_calls` to all 32 would be the over-stuffed-fixture failure in the
other direction, so I did not. **`test_final_turn_entry_pass_chain.py` is worth a note**: it is a
Final Turn file whose stubs lack the key, but it does not reach the build on any current test, so
it is latent rather than live.

---

## 5. `git diff --stat`

```
 tests/test_final_turn_coordinate_contract.py | 38 +++++++++++++++++++++++-----
 tests/test_final_turn_pacing.py              | 24 ++++++++++++++++--
 2 files changed, 54 insertions(+), 8 deletions(-)
```

**Only files under `tests/`.** No `BackEnd/` file appears. This is why no reference run is
required.

**Full suite: 3,572 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS** with
`GOB_STRICT_EXCEPTIONS=1` — the same 3,572 as before the fix, but now with the five passing
*through the real path* instead of failing on it.

---

## 6. Anything that did not behave as expected

1. **No cascade.** The brief anticipated a chain of missing attributes; there was exactly one.
   The stubs were otherwise complete enough for the whole animator build.
2. **The five tests were not mis-asserting.** I expected to find at least one assertion that had
   been silently validating fallback output. Instead none of the five ever touched the build's
   output — which is a different and, I think, more actionable finding: an engine step with no
   coverage, not five tests with bad coverage.
3. **A false start worth recording:** my first patch attempt asserted `count == 1` on a stub
   pattern that appears **three** times in the coordinate-contract file. The script aborted
   before writing, so nothing landed half-done — but a `replace(..., 1)` without that guard would
   have fixed one of three and left two silently broken.
4. **Not fixed, flagged:** `test_final_turn_entry_pass_chain.py` has the same incomplete stub
   shape on the Final Turn path. It does not reach the build today, so completing it would be
   speculative — but it is the next one to trip if that path widens.
