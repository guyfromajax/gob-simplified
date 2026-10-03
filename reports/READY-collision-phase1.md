# READY — Collision Phase 1: gate clean, exemption perfect, residual high by design

Report: `reports/collision-phase1.md`. Verified against the Collision Phase 1 brief by Claude.
`GOB_COLLISION_SEPARATION`, default OFF.

## Gate

**240/240 flag-off**, fingerprint AND draws, seed 8000 played SD=1 = fp `0c3389cd41d0bbef`,
draws `75363` (the post-flip reference, not the superseded one). Plus the check I did not ask
for and should have: **all 40 flag-ON cells DIFFER** from the reference — byte-identity with the
flag on would have meant the pass never fired.

Rule 6e footing stated throughout: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs
Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game
per process, `SEED_DEFENSES=1` production footing, `GOB_DEFENDER_AG_SPREAD` unset = ON,
`GOB_STRICT_EXCEPTIONS=1` on the flag-on runs.

Engine footprint is one new module plus **one call site**: `collision_separation.py` and a
+27/-1 hook in `defender_placement.build_all_animations`. Suite 3,587 passed = 3,572 + 15 new
guards, no existing test edited.

## Headline numbers

| | flat-3.0 baseline | Phase 1 |
|---|---|---|
| defender placements moved | 25.32% | **12.76%** (140,923 of 1,104,380) |
| separated pairs that were deliberate coverage | 28.6% | **9.18%** |
| defenders pushed OFF deliberate coverage | — | **0** |
| screen-vs-game divergence | 0.0221% | **0.0207%** — did not rise |
| offensive coordinates moved | — | **0** |
| outcomes clearing CI at n=120 | — | **none** |

## The exemption is better than "reduced"

A defender within `max(POSTURE_DENY_DISTANCE 2.0, ONBALL_POSTURE_DIST["tight"] 2.5) = 2.5` of his
assigned man is PINNED and never moves — read at call time from `shared_defense`, so a posture
retune moves with it. Both pinned -> pair skipped. One pinned -> the partner absorbs the WHOLE
push (midpoint deliberately not preserved). Neither -> each moves (threshold-d)/2.

**Zero defenders were pushed off deliberate coverage.** The residual 9.18% is pairs that merely
touch a pinned defender, where only the unpinned partner moved.

## THE HONEST WEAK POINT — 49.14% residual, and what you will actually see

**About half of overlapping pairs (38,769) are still inside threshold after the capped
relaxation.** That is the designed trade — 3 passes, 2.0-unit displacement cap, in exchange for
determinism and no oscillation. Three causes: a pinned partner must be cleared by one defender
alone; both-pinned pairs are skipped by design; a multi-defender pileup cannot be undone inside
the cap. Those pairs are REDUCED, not resolved. Levers are `COLLISION_MAX_PASSES` (3) and
`COLLISION_MAX_DISPLACEMENT` (2.0). **Neither touched** — that is Jamie's one tuning pass.

**Claude's expectation-setting for the eye test, stated plainly:** push median is **0.542 grid
units**, and this project's established visibility floor is ~0.5 units because placements round
to whole cells. So roughly half of all pushes sit at or below the threshold of perceptibility.
Combined with the 49.14% residual, the realistic visible effect is **partial** — the p90 push of
1.312 units is clearly visible, the median one often is not, and the worst pileups are still
there. This is a correct, measured first slice, not a transformation. Expect to still see
overlap.

## Where it runs — proved, not asserted

One hook in `build_all_animations`, immediately before its return. The agent found **four**
placement paths, not the two the brief named (FCP, HCT, zone `position_zone_defenders`, man
`position_standard_defenders`) — and one hook covers all four, because every one builds
defender-outer / step-inner, so "every defender at step i" exists exactly once, right there.
That also means the audit's "51% placed outside `_apply_defender_posture`" split does not
fragment the hook.

Ordering confirmed by instrumenting the grid read and comparing every cell against the
post-separation animation coords: **10,245 cells built, 0 disagreements**, 9,990 stamped. The
frozen row carries the post-separation coordinate. Measurement (e) is the independent
cross-check — a pass writing after the stamp would spike divergence, and it fell slightly.

A false alarm the agent recorded rather than hid: its first ordering probe logged the stamp at
function ENTRY and reported "1 read before any separation" — an artefact, since separation
happens inside the stamp call. The cell-by-cell comparison is what settles it.

## Determinism

`sorted(coords)` iteration, with a test that shuffles the input 25 ways and asserts an identical
result. `COLLISION_MAX_PASSES = 3`, residual accepted not iterated away.
`COLLISION_MAX_DISPLACEMENT = 2.0` per defender per step (under half a sprite width; push max
came in at exactly 2.000). **Zero RNG** — ties break on player id, and a test asserts both
`random` and `sim_rng` states are unchanged.

Threshold derived from height mirroring `createHeadshotMarkerV2.js`; the 4.15 / 5.25 / 6.35
widths reproduce as OUTPUT, and a test asserts the clamp so they cannot be hardcoded back in.
`COLLISION_OVERLAP_TOLERANCE = 0.5`, named, not inlined, not tuned.

## Openness floors

`BACKDOOR_OPENNESS_MIN` 3.0: net **+3,235 closed**. `STEP_IN_OPENNESS_MIN` 5.0: net **+1,485
opened**. ~1.2% and ~0.5% of 1.1M placements. The two move in OPPOSITE directions, which is what
a pass that pushes defenders off each other rather than toward or away from the ball should do.
The 11-unit contest gate correctly not reported as a consumer.

## Outcomes

Nothing clears at n=120. Every delta is negative but small and well inside its CI — points
-0.087 (CI 1.710), fouls -0.725 (CI 1.109), total rebounds -0.858 (CI 1.339). Consistent with a
pass that nudges defenders apart without changing what the defence achieves. Nothing retuned.

## Untouched, as instructed

Offence, in any direction. The frontend. The screen-script targeting — the O-C/O-PF stack (3,367
coincidences, screener sent to the receiver's own named `location` on 90.5% of screens) is
untouched by design, because separating offence would only mask it. That is Phase 2, and it is
the overlap Jamie is most likely to still notice. Stage 3 defects untouched.

## Open decision

Whether to flip the default on as-is, or tune `COLLISION_MAX_PASSES` / `COLLISION_MAX_DISPLACEMENT`
first to bring the 49.14% residual down. Claude's read: eye-test it at the current settings
before tuning, since the measured cost so far is zero.

No merge by Claude. Jamie merges.
