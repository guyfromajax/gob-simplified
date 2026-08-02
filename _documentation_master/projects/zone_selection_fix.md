# Zone On-Ball Defender Selection — work plan

**Status:** BANKED — scoped, localized, evidenced; NOT started. Spun out of the HCO roles audit
(2026-07-24) once that audit's finalization seams were closed and this residual was isolated to a
different layer.

> **Problem in one line:** in **zone** defense, HCO on-ball **moment-steals** are rolled + credited +
> animated on a zone defender who is **not the one guarding the ball handler** — a defender across
> the zone gets the strip. Man defense is correct. This is the "some steals stolen by a defender not
> guarding the BH" the product owner sees by eye.

---

## Evidence (discriminator probe, 70 moment-steals, 20 exhibition games)
Sim-safe `compute_defender_grid`/`_build_all_animations`; ranked the credited defender by distance-to-BH.

| Defense | Credited defender = nearest to BH | Avg credited dist | Avg nearest dist |
|---|---|---|---|
| **Man** | **100%** of measurable | 3.7 | 3.7 |
| **Zone** | **~38%** (rank dist 1:12 / 2:8 / 3:11 / 4:1) | **7.3** | **3.1** |

So on a majority of zone moment-steals the credited defender is **>2× farther** from the BH than the
actual nearest defender. (24/70 were "rank 0" — credited defender or BH had no coord at the stop step,
itself possibly a symptom worth checking.)

## Not the roles audit — a different layer
- Roles-finalization audit is **done**: fouls, DBTOs, interceptions, man steals all correct; Seam 3
  (prefer the moment stash) closed the big one and is committed + eye-confirmed "significantly better".
- This bug is **upstream** of finalization — the moment faithfully credits/renders whatever defender
  it was handed. The wrong hand-off is in **zone on-ball-defender selection**, which lives in the
  **defender-grid / dynamic-defense** territory.

## Prime suspect
`_zone_bh_defender(defense_playcall, bh_location, is_away_offense, def_lineup, bh_pos)` —
`BackEnd/engine/phase_resolution.py:6200`. Its result is used at **L6292** as the moment's `bh_defender`
(man path L6294 = the matchup, correct). `decide_step_action`'s contract (`motion_step_decision.py:502`)
says `bh_defender` should be "the man matchup, **or nearest zone defender**" — the measurement says the
zone branch is often NOT nearest. Suspect it selects by slot/spot heuristic rather than the actual
rendered-grid nearest.

## Open design question (sets the effort size + verification tier)
`bh_defender` from `_zone_bh_defender` feeds **both** the strip **roll** (via `decide_step_action`) and
the **credit** (stash `_hco_moment_defender_id`, L6292/L6304/L6508). So almost certainly the moment is
**rolling the strip against the wrong (far) zone defender**, not merely mislabelling a correct roll.
- **Confirm first (cheap):** is the wrong defender in the ROLL, or only the CREDIT? Roll → gameplay
  change (different defender's attributes contest → outcomes move). Credit-only → attribution/render
  (cheaper). Expect ROLL.

## ✅ UPDATE 2026-07-24 — Attempt 2 (guard-map) WORKS; implemented, uncommitted, distributional-verify owed
Fix (4 targeted edits, `phase_resolution.py`): (1) `_stamp_contest_defender_grid` stamps the render's
per-step guard map `step["_step_state"]["guard"] = game.zone_defender_assignments_by_step.get(i)`
(ZONE-only; freshly populated by the `compute_defender_grid` it already calls). (2) `_zone_bh_defender`
gains `step`+`bh_player_id`, returns the defender whose guarded player == the BH (inverts the map);
polygon path kept as unstamped fallback. (3)+(4) moment (L6519) + pass-contest (L5673) callers pass
`step`+`bh_player_id`. attack_drive twin still deferred.
- **Functional (re-probe):** ZONE credited-defender-is-nearest **38%→65%**, and the farthest-defender
  picks Attempt-1 introduced are GONE (rank dist tops at r3). MAN still 100%. The remaining r2/r3 are
  cases where the render's *own* guardian isn't the raw-nearest — the fix now MATCHES the render by
  construction (credited == who the render draws guarding the BH). Any residual is the render's
  `assign_all_zone_defenders` assignment quality — a deeper/separate layer, not this fix.
- **Perf: FREE.** Poison-isolated (guard code runs, old result returned → identical 7914-turn games) →
  cpu/turn **5.46 ≈ baseline 5.48**. The stamp-read + inversion loop add nothing. Sim Perf not disrupted.
- **Owed before done:** user in-app visual confirm + distributional multi-seed verification + reference
  re-cut (batch w/ Seam-3's, pause for human OK). Fix is **uncommitted** in the working tree.

## ⚠️ UPDATE 2026-07-24 — Attempt 1 (distance-in-grid) FAILED; use the `_guard` map

**Confirmed:** it's the ROLL (not just the credit). `_zone_bh_defender`'s result feeds both the strip
roll (`decide_step_action`) and the stash — the moment rolls the strip against the wrong zone defender.
So the fix is a gameplay change (distributional verify + re-cut), as expected.

**Attempt 1 — make `_zone_bh_defender` pick the NEAREST defender in the stamped grid — DID NOT WORK.**
Implemented (added optional `step`, read `step["_step_state"]["defense"]`, nearest by squared distance,
polygon fallback; passed `step` at the moment L6519 + pass-contest L5673 callers). The functional
re-probe showed zone got **worse** (credited-defender-is-nearest fell, and *farthest*-defender picks
appeared). Root cause: the stamp holds **defender** coords only, so I compared them to the **idealized
BH spot** (`_spot_display_coords(bh_location)`) — but the rendered BH is *nudged* off its spot, and
there's a coord-frame subtlety. **Reconstructing "who guards the BH" by distance is too fragile.**
Reverted.

**Perf, however, is a NON-issue** (poison-isolated: run the grid-read code but return the OLD result →
byte-identical games → **cpu/turn 5.43 == baseline 5.43**). Reading the stamped grid is free. The
blocker is *correctness of the selection*, not speed.

**Correct approach — the render's own guard map.** `assign_all_zone_defenders` (`shared_defense.py:1070`)
already returns `(def_xy, _guard)` where **`_guard` = {def_pos: guarded_offensive_player_id}** — the
exact "which defender guards the BH", frame-independent, the same assignment the render draws. It is
**discarded everywhere** (e.g. `_hco_step_def_xy` L4978 unpacks `_guard` and throws it away). The
on-ball zone defender = the def_pos whose `_guard` value == the BH's player_id. No distance guessing.

**Plumbing needed (the real work):** `_guard` is NOT in the stamp (`_step_state.defense` = coords only).
Options: (a) **stamp the guard map** alongside the grid — thread it through `compute_defender_grid` /
`_stamp_contest_defender_grid` so the moment reads it cheaply per-step (preferred; one grid, one
source); or (b) call `assign_all_zone_defenders` inside `_zone_bh_defender` (rebuilds offense coords
per-step → a real per-step cost — avoid). Prefer (a).

## Work plan (revised)
1. ~~Confirm roll-vs-credit~~ ✅ ROLL. ~~distance approach~~ ✅ tried, failed (above).
2. **Surface `_guard`**: extend the defender-grid stamp to also carry the render's guard map
   (`assign_all_zone_defenders`'s 2nd return), per step — the single-source of "who guards whom".
3. **Fix `_zone_bh_defender`**: when the guard map is stamped, return the defender whose guarded
   player == the BH (exact); polygon path stays as the unstamped fallback. Pass `step` at the moment
   (L6519) + pass-contest (L5673) callers (attack_drive twin deferred).
4. **Verify**: functional re-probe (credited zone defender now == guarded/nearest) → distributional
   multi-seed + reference re-cut (batched with Seam-3's owed one), pausing for human OK on the re-cut.
   Perf: already shown free; re-confirm with the poison isolation after the guard-map plumbing.

## Verification (Plan A + Sim-Perf non-disruption)
- **Per-change draw check:** if it changes the roll (expected) → **draw-moving → distributional
  multi-seed verification + reference re-cut**, NOT exact-diff.
- **Batch the re-cut:** the Seam-3 fix is committed but still owes a distributional pass + re-cut of the
  seeded perf reference (`refstats_postB…`, now stale). Do this fix, then **one** distributional pass +
  **one** re-cut covering both. Re-cut needs explicit human OK (harness-access decision).
- **Sim-Perf constraints (`Sim_Perf_Capstone.md`):** the moment path is per-possession, not per-step —
  keep it that way; RNG only via `sim_rng`; any diagnostics gated OFF for full-sim/CPU-week/PS; profile
  before/after any hot-path touch. Do NOT regress the pooled-sim speed.
- **Measure-first discipline:** this pattern (probe before fixing) already stopped three wrong turns
  (Seam 1 dead-in-practice, Seam 2 Path-B correct, and this being selection not render). Keep it.

## Key files
- `BackEnd/engine/phase_resolution.py` — `_zone_bh_defender` (L6200), moment `bh_defender` (L6292/6294),
  stash writes (L6304/L6508), moment-steal finalization (L8144/L8206).
- `BackEnd/models/animator.py` — `compute_defender_grid` / `defender_grid_from_animations` (the rendered
  grid = the source of truth for "nearest").
- `BackEnd/utils/shared_defense.py` — `assign_all_zone_defenders`.
- `BackEnd/engine/motion_step_decision.py` — `decide_step_action` (consumes `bh_defender`).

## Cross-links
- [hco_roles_audit.md](hco_roles_audit.md) — parent; finalization done, this is the residual root cause.
- [StepState.md](Z-Completed/StepState.md) / [UESS System §12.3](../05_UESS_System/UESS_System.md#123-stepstate-upstream-ownership-gap) — the defender-grid / emitter-as-god law this fix should follow.
- [Sim_Perf_Capstone.md](Sim_Perf_Capstone.md) — the perf contract this must not disrupt + the verification toolkit.
