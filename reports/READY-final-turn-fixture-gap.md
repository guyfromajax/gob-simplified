# READY — Final Turn fixture fixed. The finding turned out sharper than expected.

Report: `reports/final-turn-fixture-gap.md`. Verified against the brief by Claude.
Tests-only: `git diff --stat` is two files, both under `tests/`, 54 insertions / 8 deletions.
No `BackEnd/` file touched, so no reference run required — correctly stated and correctly skipped.

## Result

The fixture is complete and **the FT-Task 1 animator build now genuinely runs** — the fallback
fires **0 times** across the whole suite where it previously fired on every one of these five
tests. All five pass. Full suite **3,572 passed / 0 failed** with `GOB_STRICT_EXCEPTIONS=1`.

## THE REAL FINDING — not five bad tests, one untested engine step

Claude predicted at least one assertion had been silently validating fallback output. Wrong, and
the truth is more useful.

The agent forced the build to fail exactly as the incomplete stub did (monkeypatched
`phase_resolution.Animator` to raise the same AttributeError, strict off so the handler swallows
it) and re-ran:

| | result |
|---|---|
| real animator build running (strict on, fixture fixed) | 5 passed |
| build forced to fail -> fallback path (old behaviour) | 5 passed |

**Identical.** But not because the assertions are too loose — because none of the five ever
touches the build's output. Every one asserts on the skeleton, the pacing floors, or the shooter
pick, all produced UPSTREAM of FT-Task 1. The build's job is syncing DEFENDER COORDINATES into
the game before `resolve_shot`, and not one of these tests looks at a defender coordinate.

So each test asserts what its name says and passes for the right reason. The finding is:
**the FT-Task 1 defender coord-sync has ZERO test coverage.** It sat in the middle of five tests'
execution path, failed silently in all of them, and nothing noticed because nothing was looking.
The fixture fix means it now RUNS. It still is not TESTED.

**NEW TASK SURFACED:** a test that asserts a defender coordinate after a Final Turn shot. That is
new coverage for an engine step that currently has none.

## No cascade — one attribute, and one deliberately omitted

`strategy_calls` only. Read from `team_manager.py:435-444` (fresh-game init, 8 keys all `None`),
cross-checked against the restore-from-saved branch (`:421-431`), the defensive re-init at
`turn_manager.py:3501-3517`, and every read site. A shared `_fresh_strategy_calls()` helper in
both files mirrors it.

**`aggression_call` was deliberately NOT added** — it is not part of the canonical init, it is
written per turn by `turn_manager.py:3580-3586`, and every reader uses
`.get("aggression_call", "normal")`. Omitting it reproduces a real fresh game exactly and lets
the failing line resolve through the getter's own default rather than through an invented value.
That is the right call and it is the difference between fixing a fixture and faking one.

Six stubs patched, not five — `_alignment_manager` builds its own team pair and three `_game`
builders share an identical construction.

## The wider surface, measured

32 tests reach an Animator build through `phase_resolution` (measured by wrapping it for the
whole suite and recording calls to `skeleton_to_animations`). The high-volume callers
(`test_quarter_starts`, `test_possession_changes`) use real `GameManager` objects and always had
`strategy_calls` — they were never affected.

**Tests still silently running the FT-Task 1 fallback: 0.**

32 team-shaped stubs across 14 files still lack `strategy_calls`, and the agent deliberately left
them — none reaches the build, and stuffing them all would be the over-stuffed-fixture failure in
the other direction. **`test_final_turn_entry_pass_chain.py` is flagged as latent**: a Final Turn
file with the same incomplete stub shape that does not reach the build today, so it is the next
one to trip if that path widens.

## Two process notes worth keeping

**The agent declined to fabricate Rule 6e fields**, correctly: a pytest run has no worker, no
seeds and no defenses catalogue, and it said so rather than inventing them. The poll brief asked
for 6e on any number; that was over-broad and the pushback was right.

**A false start it recorded rather than hid:** the first patch attempt used `replace(..., 1)` on a
stub pattern that appears THREE times in the coordinate-contract file. The script aborted before
writing, so nothing landed half-done — but without that guard it would have fixed one of three
and left two silently broken, which is precisely the failure class this whole thread exists to
stop.

## Confirmed

No assertion weakened, re-stubbed around, or xfailed. Stage 3 defects untouched.

No merge by Claude. Jamie merges.
