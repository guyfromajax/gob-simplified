# READY — AG spread ON by default: landed, verified, one open item

Report: `reports/ag-spread-default-flip.md`. Branch `feature/animation-reward`, flip commit
`f600628a4`, references in the follow-up commit. Verified against the default-flip brief by
Claude. Every required item present.

## Result

**Kill switch is exact and symmetric.** `GOB_DEFENDER_AG_SPREAD=0` reproduces
`equiv_v3_reference_1f4af0ede_loosesag_nogate.json` 160/160 and
`equiv_v3_loose_baseline_1f4af0ead_loosesag.json` 80/80 — fingerprint AND draws, all four cells.
Seed 8000 = fp `a1d150579771387a`, draws `77689`. Verified, not assumed.

Unlike the loose-sag flip (where `=0` restored only a related footing because the axis was
invisible to the main reference), **this rollback restores the old reference exactly**, because
Stage 2 proved flag-off byte-identical. `=0` is a true time machine.

**New default introduced zero drift.** Divergence with the env var unset: **147 / 666,385 =
0.0221%** — bit-for-bit the number Stage 2 measured with the flag forced on, and below the
0.0301% kill-switch floor.

`s` unchanged at **0.50**. Nothing tuned. 512 cells run total (240 kill-switch + 240 new-default
+ 32 re-baseline). Rule 6e footing stated throughout, `SEED_DEFENSES=1` production footing, main
reference also covers SD=0.

## The change is one line

`os.environ.get(FLAG, "0") == "1"` -> `os.environ.get(FLAG, "1") == "1"` in
`animation_step_helpers.py`, matching the house idiom used by `GOB_BOXOUT_CONTEST`. No mechanism
changed — `DEFENDER_AG_SPREAD` still 0.50, `defender_aware_rate` untouched, every Stage 1/2
routing test passes unmodified.

## Tests: 3 touched, none weakened

Suite came back 3 failed / 3,567 passed. All three were the "assumed the old default" class, no
regressions. (The rebound flip landed 130 — this was small because the spread was built
flag-gated from the start with flag-explicit tests.)

- `test_spread_defaults_off` -> `test_spread_defaults_on` — the ONLY assertion inverted, and it
  is the assertion the flip exists to change. Kept rather than deleted, so a future change
  cannot silently flip it back without editing that line.
- `test_flag_off_is_the_shipped_function_itself` — the `clean_env` fixture DELETES the env var,
  which now means ON. Moved to a new `spread_off` fixture that sets `"0"` explicitly.
  **Assertion unchanged.**
- `test_flag_off_is_identical_for_defenders_and_offence` — same cause, `monkeypatch.setenv(FLAG,
  "0")`. **Assertion unchanged.**

Two guards added: `test_the_default_is_on_and_pinned_in_source` (checks the behaviour AND that
the source literal is `"1"` — an edit could keep the signature and change the literal) and
`test_the_kill_switch_still_fully_disables` (with `"0"`, a defender's rate equals the raw
archetype rate at every archetype and AG, through both entry points — rollback must be total,
not partial).

Full suite after edits: **3,572 passed, 0 failed** = Stage-2 baseline of 3,570 plus the 2 guards.

## New references

- `equiv_v3_reference_f600628a4_agspread.json` — n=40 seeds 8000-8039, both arms, SD=1 AND SD=0,
  fp + draws + points/turns/possessions per seed, plus `arm_gap_sim_minus_played` per cell
- `equiv_v3_loose_baseline_f600628a4_agspread.json` — n=40, `EQUIV_MAN_POSTURE=loose`, SD=1 only

Both carry the flag table entry recording the flip date, `s = 0.50`, defenders only, per player
by `def_lineup` membership. `README.md` updated — both new files CURRENT, both predecessors
SUPERSEDED with `GOB_DEFENDER_AG_SPREAD=0` recorded as the setting that reproduces them. **No old
reference deleted or overwritten** — the rollback proof depends on them.

Lineage is now: `32db56c77_helpshade` -> `f2a060488_manhelpshade` -> `09f1b0ca9_boxout` ->
`1f4af0ede_loosesag_nogate` -> **`f600628a4_agspread`**. Everything downstream, including the
collision/screens work, gets measured against `_agspread` from here.

## OPEN ITEM — re-baseline is a subset, not the full protocol

The agent flagged this itself rather than letting it pass. The README protocol calls for a full
double re-baseline; what was run was a **32-cell independent subset** — 6 fresh seeds x 4 cells
(24/24) on the main reference and 4 fresh seeds x 2 arms (8/8) on the loose baseline, all
reproducing fingerprint AND draws.

Claude's read: 24/24 + 8/8 on fresh seeds is decent evidence, but it leaves a small real gap —
a per-seed nondeterminism that only appears outside those 10 seeds would not have been caught.
This reference is load-bearing for every measurement from here on, and the cost is machine time,
not judgment. **Recommendation: complete the full second 240 before relying on it.** Jamie's
call.

## Untouched, as instructed

Stage 3 defects (four hardcoded `12.0` fallbacks, three missing `max(0.0, ...)` floors) still
enforced by `test_stage_3_defects_are_still_untouched`. The exception handler that swallows
`NameError`s was not touched — **still a live hazard, still needs its own task.**

## Carried forward, unresolved

The points-per-possession row (3.992 / 3.806) still does not reconcile with the points and
possessions rows beside it. Outcomes were not re-run (per the brief), so the definition is still
unpinned. The number was not reused anywhere. Pin it before anyone quotes PPP.

## What a player will and will not see

- **Will see:** on ~41% of moving placements a slow and a fast defender now finish at least half
  a cell apart, up from 27%. At p90 the gap is 5.455 grid units — more than a full player width
  — so a genuinely slow defender visibly trails on long closeouts.
- **Will not see:** on the other ~59%, both land in the same cell. Median gap is 0.000 and stays
  0.000, because most moving placements have a target close enough that both defenders arrive
  fully and the rate never binds.
- **Will not see:** any offence change, or any scoring change (nothing cleared at n=120).

Visible-but-partial differentiation, not a transformation. Anyone watching a single possession
will most likely notice nothing.

No merge by Claude. Jamie merges.
