# StepState — Remaining UESS-Compliance Gaps

**Context:** the Dynamic HCO refactor (see `StepState.md`) unified HCO turns onto one per-step
resolution spine and made the interception contest judge against the **rendered** defender positions.
This file records where full UESS ("**resolve once → freeze into StepState → project to emitter → draw**;
one value read everywhere") is **not yet met**, so the claim isn't overstated. Snapshot: 2026-07-13.

## ✅ What IS single-source today
- **Interception contest ↔ render defender grid** — the contest judges the SAME defender placement
  that gets drawn (man + zone). Live `🔬 STEPSTATE GAP` measured **0%** (was man 22–64%, zone up to 100%).
- **OOB exit points** — `nearest_oob_point` is engine-owned for HCO **and** HCT; the FE reads
  `bat_oob_target` instead of recomputing. All of HCO/HCT/FCP source the exit from the backend.
- **One resolution spine** — motion + set play + the on-ball moment + interception all resolve inside
  `_resolve_hco_offense_shot_dynamic` (one walk), not stacked separate passes.

## ⚠️ Open gaps (full UESS not met)

| # | Gap | Where | Why it exists | To close | Priority |
|---|-----|-------|---------------|----------|----------|
| 1 | **Defender grid drawn TWICE, not frozen once** | contest: `_stamp_contest_defender_grid` → `Animator.compute_defender_grid` (pre-emit); render: `skeleton_to_animations` (emit) | The contest must decide the interception BEFORE the emit exists (its outcome truncates the skeleton the emit draws → circular). So it draws its own grid pre-emit. | Resolve the contest against a provisional emit, then re-emit if truncated (complex), OR accept it. Same code + ~2px RNG → **measured 0% gap**, so they agree; it's "two draws that match," not one frozen value. | Low — immaterial in numbers |
| 2 | **Bat-OOB ball trajectory is flown IMPERATIVELY by the FE**, not projected from StepState steps | `AnimationEngine._runHctBatOobBallSend` (FE) — driven by `turnData.bat_oob_*` | The step schema pipeline can't fly a deflected ball off-court; the imperative send does passer→contact→OOB after the steps settle. | Encode the OOB ball motion as StepState sub-steps (smooth contact→OOB + bounce SFX) so the emitter projects it. Positions (contact, exit) are already engine-owned; only the bounce **shape** is FE animation logic (cosmetic). | Low — positions are engine-owned; shape is cosmetic |
| 3 | **Emitter/animator still re-derive some per-step facts** | animator/emitter — meet-points, step timing, interrupts | Pre-refactor smearing the `StepState.md` "Governing law" section itself flags. This refactor pulled the **defender grid** back into the engine; the rest was out of scope. | Pull each remaining game-relevant re-derivation (pass meet-point, per-step timing) into the engine + freeze into StepState. | Med — the real remaining UESS work |

## Related "not one path" nuance (not a data gap)
- **Coverage patch `_hco_contest_final_skeleton`** runs as a SECOND contest sweep (after the walk) for
  dish steps the per-step paths don't tag. **Measured load-bearing (~18% of interceptions)** and
  deliberately kept — retiring it would drop the steal rate. It reads the same stamped grid, so it's
  not a data-divergence gap, but it means interception contesting has two sites, not one.

## Classification test (from the Governing law)
For any value: *could computing it differently change an outcome / stat / contest / position / clock?*
- **Yes → must be engine / `StepState`.** Gaps 1 (position) and 3 (meet-point/timing) are Yes-values still
  computed in >1 place (though gap 1's two draws agree to ~0%).
- **No, only how it looks → emitter/FE is fine.** Gap 2's bounce *shape* is a legit No (cosmetic); its
  *positions* are already engine-owned.
