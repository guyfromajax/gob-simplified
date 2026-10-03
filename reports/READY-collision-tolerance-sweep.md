# READY — collision-tolerance-sweep.md (verified)

Verified against the sweep brief on 2026-09-24. **Accepted.** Nothing merged; nothing tuned.

## Gates — both parts passed, as briefed
- Collision flags off + `GOB_COLLISION_TOLERANCE` absent: **240/240** fp AND draws (160 + 80),
  480/480 checks, 0 mismatches. Seed 8000 played SD=1 = fp `0c3389cd41d0bbef`, draws `75363` ✓
- Flags ON with the override ABSENT vs flags ON at `GOB_COLLISION_TOLERANCE=0.5`:
  **80/80 byte-identical** on fp AND draws. This is the part that proves the override defaults
  to the shipped constant rather than replacing it.
- Suite 3,651 passed / 0 failed.

## Constants confirmed unchanged on disk
`COLLISION_OVERLAP_TOLERANCE = 0.5`, `COLLISION_MAX_PASSES = 3`,
`COLLISION_MAX_DISPLACEMENT = 2.0`, `PIN_OFFENCE_AT_AUTHORED_LOCATION = True`,
`AUTHORED_LOCATION_TOLERANCE = 0.5`. `overlap_tolerance()` reads the env at CALL time and falls
back to the constant on unset / empty / unparseable / non-positive. Verified by reading
`BackEnd/utils/collision_separation.py` directly, not from the report's own claim.

## Brief deviation — accepted, and the agent was right
The brief said to REUSE the existing 0.5 outcome figures from `collision-phase1-extended.md`.
The agent declined and re-ran 0.5 instead, because those figures were taken with the authored-
location pin **ON** and this sweep runs pin **OFF**; reusing them would have compared two changes
at once and made 0.5 look artificially different from its neighbours. Correct call. The brief was
wrong on this point.

## What could NOT be verified from disk
`PIN_OFFENCE_AT_AUTHORED_LOCATION = False` was applied at run time (no env override exists for
it, and the on-disk default is still True). The runner that patched it is not on disk, so the
pin-off condition is taken from the report's own statement. Low risk — the committed tests
monkeypatch the same attribute the same way — but it is not independently confirmed.

## The finding, and what it overturns
**The tolerance is not the governing constant.** That was my claim after Phase 1 and this sweep
falsifies it. Sprite-width overlap (within 5.25, THE metric) moves 10.3645% -> 9.2142% across the
entire usable range of the constant — **-11.1% at full sprite clearance, which is its ceiling**,
since tolerance 1.00 already targets the whole combined sprite width.

What actually governs it is the **residual** — pairs the pass accepts rather than separates —
which rises 58.49% -> 73.01% as tolerance climbs. That residual is produced by
`COLLISION_MAX_PASSES = 3` and `COLLISION_MAX_DISPLACEMENT = 2.0`, neither of which has been
swept. The cap becomes the limiter early: cap-bound pushes 9.4% -> 21.5% -> 32.4% -> 44.1%, and
p90 push = exactly 2.0 from tolerance 0.85 upward.

**The 0.5 -> 0.7 cliff on "steps with any sub-3.0 overlap" (74.21% -> 54.27%) is a metric
artifact, not a sweet spot.** The median pair threshold crosses 3.0 between those two points
(2.624 -> 3.674). The agent caught this and said so rather than selling it as a result. That is
the correct read and it should not be quoted as a win.

## Cost, for the tuning pass
Outcome significance (n=120, seed-paired, CI = 1.96 x SEM, `*` = CI excludes zero):
0.50 -> **1** metric (OREB); 0.70 -> **0**; 0.85 -> **6**; 1.00 -> **7**.
The step is between 0.70 and 0.85, and it is coherent rather than noisy — offence shoots better
(FG% +1.9 to +2.7, points +2.0 to +3.2) while rebounds and possessions fall. Not retuned.

## Hazard recorded
`separate_defenders` has **no court clamp at all** (unlike `screen_targeting`, which clamps).
Out-of-bounds was 0 at every tolerance — but only because `COLLISION_MAX_DISPLACEMENT = 2.0`
keeps pushes short. **That zero does not survive raising the cap**, and a cap sweep is the
obvious next measurement. A clamp should go in behind the same flag before any cap is raised.

## Untouched, as briefed
Screen flags, SCRA/SCRS, `calculate_screen_score`, the Stage 3 cold-path defects, and the
uncached `find_one` SPC item. Rule 6e footing stated on every figure: worker
`scratch_equiv3_fbdedupe.py`, SD=1, `SEED_DEFENSES=1` (catalogue seeded), n=40 seeds 8000-8039
geometry / n=120 seeds 8000-8119 outcomes.

Item 22: `SHOOTER VIOLATIONS = 0` at all four tolerances (80 games each), so no point in the
sweep is invalidated.
