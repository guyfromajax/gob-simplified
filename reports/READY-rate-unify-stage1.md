# READY — rate-unify stage 1: verified, byte-identical, ready to merge

Report: `reports/rate-unify-stage1.md`. Branch `feature/animation-reward`, refactor applied on
top of `17c611fa4`. Verified against the stage-1 brief by Claude. Every required item present.

## Result

**160/160 on the main reference AND 80/80 on the loose footing — fingerprint AND draw count,
all four cells.** Seed 8000 reproduces fp `a1d150579771387a`, draws `77689`.
Full suite 3,556 passed / 0 failed = pre-refactor baseline of 3,536 plus the 20 new tests, with
NO existing test edited. Rule 6e footing stated: worker `scratch_equiv3_fbdedupe.py`, Lancaster
vs Bentley-Truman, sliders 2 / traps 5, n=40 seeds 8000-8039, `SEED_DEFENSES=1` production
footing (main reference also covers SD=0).

Nine engine files, 251 insertions / 172 deletions, plus `tests/test_movement_rate_accessor.py`.

## Verified: derivation pairing UNCHANGED

59.36% combined / 33.29% IC-only / 2.68% mixed / 4.68% no-clamp — identical to the audit to the
digit, and per turn type as well. Stronger evidence: the per-variant CALL COUNTS are also
identical (`_interpolate_step_end` 111,249 · IC-A strict 71,868 · `_motion_end_toward_dest`
8,230 · IC-B lenient 2,420), and the wrapper-bypassing local stampers still account for exactly
349 steps (rim_runner 267, fb_outlet_pass 82). That proves routing was preserved, not merely
that totals matched.

## Verified: defects PRESERVED, not fixed

- four hardcoded `12.0` fallbacks -> `fallback_rate=12.0`, `STAGE 2` marked, count pinned by test
- three missing `max(0.0, ...)` floors -> a test asserts the floor was NOT added
- both `_interrupted_coord` policies intact: strict still raises `TypeError` on None, lenient
  still returns `(50, 25)` on both-None. 200,000 random inputs per variant plus every degenerate
  case, 0 mismatches.
- `drift_or_hold_coord` untouched — a test asserts `r.random()` is still there and that it does
  not use the shared clamp
- the 11 `_euclid` definitions and the 5 divergent duration helpers untouched

## Verified: the two failure modes the audit exposed

- **by-value imports** — the test walks every module in `BackEnd` via `pkgutil.walk_packages`
  and asserts identity (`is`) for all four names. Broader than the 25 modules the probe needed.
  The three private stampers are tested by patching each emitter's OWN `movement_rate`.
- **injected callables** — the test EXECUTES the injected callable in `fcp_offball_attack`'s
  call shape against a spy on `shared.movement_rate`. Not a grep.

Site counts measured by the test: 117 producers / 32 IC consumers (31 direct + 1 injected) /
13 combined-helper callers. All match.

## How byte-identity was achieved (worth knowing)

`apply_spread` IS the old `is_defender` argument, and `_ag_grid_per_game_sec` /
`defender_movement_rate` became three-line delegates. So all 117 call sites reach the single
accessor WITHOUT any call site being rewritten — that is why this could be byte-identical.
Same trick for `_interrupted_coord`: each legacy module-level name is bound to the wrapper for
the variant that module already reached, which preserves the by-value import routing
(`dynamic_hct` <- `transition_bridge`, `triangle_step_emitter` <- `rim_runner`).

Clamp order preserved exactly — `[0.5, 60]` applied to the AG-scaled STANDARD rate, archetype
multiplies afterwards. Pinned by a test using AG=100000 on `burst` to prove the result CAN
exceed 60, which is only true in that order.

The two AG-extraction paths were deliberately NOT merged: `_archetype_rate` does not coerce to
float or swallow exceptions, `_defender_spread_rate` does both. Merging would move results for
malformed attribute dicts.

## Nothing failed to be byte-identical

Two things stated rather than left implied:

1. `rim_runner_step_emitter` no longer uses its private `_euclid` for `_interrupted_coord` — it
   now goes through `animation_step_helpers._euclid`. Same implementation
   (`(dx*dx+dy*dy)**0.5`, normalised AST hash), so byte-identical, but a real change of which
   object is called.
2. **34 of the 117 producer sites never fired** in the reference run. Their byte-identity rests
   on the function-level equivalence sweep (18,504 + 400,000 comparisons, 0 mismatches), not on
   the reference. The unexercised set is dominated by `covert_release_step_emitter` — **which
   means the four `12.0` fallbacks and the three missing floors are all on COLD PATHS.**

## Consequence for Stage 2 — read this before briefing it

Because the `12.0` fallback and the missing floors live on cold paths, **fixing them will NOT
show up in a 160/160 reference run.** A clean reference is therefore NOT evidence that the fix
worked, and a kill switch on it cannot be validated the usual way. Stage 2 needs a targeted
fixture that actually forces `covert_release` steps, or unit-level proof, before any flag flip.

No new latent findings beyond the audit.

No merge by Claude. Jamie merges.
