# READY — movement-rate inventory audit: verified

Report: `reports/movement-rate-inventory.md` (branch `feature/animation-reward`, HEAD `f19a2e13a`).
Verified against the brief by Claude. All three questions answered. Rule 6e footing stated:
worker `scratch_equiv3_fbdedupe.py`, n=8 seeds 8000-8007, played arm, `SEED_DEFENSES=1`
(production footing). Probe proved RNG-neutral — seed 8000 reproduced reference fp
`a1d150579771387a` AND draws `77689`.

## Verdict accepted

**NOT a pure refactor.** Unifying the rate and `_interrupted_coord` is a behaviour change and
needs a kill switch plus a full equiv-v3 run.

## Counts corrected (the brief's numbers were wrong)

- 117 rate-derivation call sites, not 31. The 31 was the `_interrupted_coord` CONSUMER count,
  a different thing. Actual IC consumer count is 32 (one invisible to static analysis).
- Four `_interrupted_coord` definitions but only TWO distinct arithmetic variants.
- 84 of 117 static sites fired in 8 games; 34 never fired.
- One implementation of the AG curve (`shared.py:744`). No site re-implements the arithmetic.

## The real structural split

- **33.29% of steps** take the endpoint from `_interrupted_coord` and have the duration
  RE-DERIVED independently by a stamper — two rate look-ups for one player in one step.
- **2.68% more** mix both families within a single step.
- **59.36%** use the combined helpers and CANNOT diverge.
- Worst turn types: FCP (48.67% IC-only, 7.07% mixed) and HCT (43.20% / 8.09%).

Correction to the prior framing: the two combined helpers
(`_motion_end_toward_dest`, `_interpolate_step_end` — byte-identical to each other) are
INTERNALLY CONSISTENT on endpoint-vs-duration. They are the AG-spread blocker (both pass raw
`_ag_grid_per_game_sec`, never the wrapper), not the endpoint/duration drift source. Those are
two separate problems.

## Turn-type coverage

22,234 stamped steps / 8 games. HCO 66.29%, FREE_THROW 9.16%, FCP 8.42%, HCT 8.28%,
FAST_BREAK 7.86%. `offensive_state` has only five values — inbound/dead ball, zone shell,
rebound scramble and end of period are sub-phases inside these, not separate states.
Every turn type reaches all four clamp families.

## Why it is a behaviour change

1. `covert_release_step_emitter.py:493/1067/1307/1718` substitute a hardcoded **12.0** when the
   player lookup fails. Canonical is the archetype base — wrong by **-20.0 on burst**, -6.0 on
   sprint, +4.0 on drift. Routing to canonical moves real endpoints.
2. Three emitters carry PRIVATE copies of `stamp_tween_durations` calling raw
   `_ag_grid_per_game_sec` while their endpoints call `defender_movement_rate`:
   `rim_runner_step_emitter.py:297`, `fb_outlet_pass_step_emitter.py:87`,
   `covert_release_step_emitter.py:877`. Unifying pulls **349 steps / 8 games (1.57%)** onto the
   wrapper — inert only because `GOB_DEFENDER_AG_SPREAD` is OFF.
3. Three `max_traversal = rate * t` sites lack the `max(0.0, ...)` floor and would gain it.
4. `fcp_offball_attack.py:360/364` receives BOTH the rate fn and the clamp fn as INJECTED
   CALLABLES from `dynamic_hct.py:2629-2630` (1,989 calls). A name-based refactor silently
   misses it.
5. Variant A raises `TypeError` on a None coordinate; variant B returns one — centre court
   (50,25) when both are None. Picking either changes those paths.

## Constraints for the build

- The [0.5, 60] clamp is applied to the AG-scaled STANDARD rate BEFORE the archetype
  multiplier, not to the final rate. Standard spans 12.6-15.4, so **the clamp never binds in
  play**. Re-implementing it in the other order is a silent behaviour change at extreme AG.
- `drift_or_hold_coord` (`animation_step_helpers.py:871`) **consumes RNG** (`r.random()`) inside
  its clamp. It can never be folded into a shared pure helper without changing the draw stream.
- 11 `_euclid` definitions, 7 distinct (`**0.5` vs `math.hypot`, not bit-identical). The two
  reached by `_interrupted_coord` are the same variant, so no drift there — but do not assume.
- 5 duration helpers have divergent degenerate fallbacks: `_traverse_seconds` returns 0.5 and
  floors at 0.1; `_travel_seconds` returns 0.05; `_traversal_seconds` returns 0.0.

## Agreed sequence

Land the mechanical de-duplication behind a flag with the EXISTING arithmetic preserved exactly
— including the 12.0 and the raw-rate stampers — prove 160/160 (fingerprint AND draws, all four
cells), and only then correct each defect one flag at a time.

## Latent bugs: reported, NOT fixed

- hardcoded 12.0 fallback (x4)
- missing `max(0.0, ...)` floor (x3)
- centre-court (50,25) return when both coordinates are None

No merge. Jamie merges.
