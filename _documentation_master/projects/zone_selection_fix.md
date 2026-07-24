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

## Work plan
1. **Confirm roll-vs-credit** (read `_zone_bh_defender` + the moment roll path; one targeted probe if needed).
2. **Root-cause `_zone_bh_defender`**: why it returns a non-nearest zone defender (heuristic vs. the
   rendered grid). The grid already knows the true positions (`compute_defender_grid`); the on-ball
   pick should agree with "nearest in the grid".
3. **Design the fix**: make the zone on-ball defender = the actual nearest defender in the rendered
   grid (single source with `compute_defender_grid`, mirroring the emitter-as-god principle). Watch
   for the pass-contest which already *excludes* `_zone_bh_defender` from picking its own passer's pass
   — keep that consistent.
4. **Implement + verify** (see below).

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
- [StepState.md](StepState.md) / [project_emitter_as_god] — the defender-grid / emitter-as-god law this fix should follow.
- [Sim_Perf_Capstone.md](Sim_Perf_Capstone.md) — the perf contract this must not disrupt + the verification toolkit.
