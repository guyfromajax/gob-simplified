# Final Turn (+ FLSS) ↔ UESS Compliance Audit

**Date:** 2026-07-04 · **Scope:** Final Turn (end-of-quarter ≤30s shot) **and its FLSS / EOQ-Perfection sub-branch** · **Method:** read-only trace, 4 parallel audits (single-coord-source, clock/EOQ, ball-seam, player-coord) · **Audit only — no code changed.** · Turn #1 of the 11-turn UESS sweep (after HCO).

**FLSS confirmed part of Final Turn:** `turn_manager.resolve_final_turn_shot` → `resolve_final_turn_shot_logic` → if `route_flss` → `eoq_perfection.resolve_flss_shot_logic` → shared `_emit_hco_animation_steps`. Both audited here.

---

## ⭐ TL;DR (human topline — read this first)

**Final Turn shares HCO's emitter, so the HCO ball/coord fixes mostly carry over — but its shot *resolver* is a different, un-migrated path, and that's where the serious bug is.** The clock is clean. The headline problem is that **end-of-quarter shots are resolved as essentially uncontested** because the resolver never syncs the defenders before deciding the shot.

| Symptom | Root cause | Verdict |
|---|---|---|
| End-of-quarter shots feel too easy / defenders "don't matter" | Final Turn resolver **builds no animator and never syncs defenders** before `resolve_shot` → contest reads a **stale/empty** `zone_defender_assignments_by_step` + prior-turn `def_lineup` coords → shot scored **uncontested**, then the FE renders defenders on the shooter | ❌ **HIGH** |
| FLSS (last-second heave) ball looks detached / no clear handler | Every FLSS turn emits pre-shot steps with ball `owner_player_id = ""` (FLSS skeleton never uses `handle_ball`/`pass`; roles fallback empty) | ❌ **HIGH (FLSS only, rare)** |
| FLSS "sprint drive" shows no motion, shooter jumps forward | FLSS seeds the shooter's step-0 **start** at the drive **END** coord, not his prior position | ⚠️ **MED** |
| Rare ball teleport entering a Final Turn | Step-0 ball pin fires even when the handoff **self-skips** (didn't deliver) | ⚠️ **MED (edge)** |
| Clock at end of quarter | Correct — ledger-derived, monotonic, drains to 0 on the terminal turn | ✅ **Compliant** |

### Compliance scorecard

| UESS contract | Final Turn status |
|---|---|
| Single coord source for logic (§1/§7) | ✅ **Fixed (FT-Task 1, 2026-07-04)** — defenders synced from the single build before resolve |
| Ball step-seam continuity, within turn (§8.4 inv.1) | ✅ non-FLSS · ✅ **FLSS owner fixed (FT-Task 2)** |
| Ball ownership within-step (§8.4 inv.2) | ✅ non-FLSS |
| Ball turn-seam continuity (§8.4 inv.4) | ✅ **handoff self-skip pin guarded (FT-Task 3)** · ✅ **FLSS entry fixed (FT-Task 2)** |
| Player coord step-seam continuity (§8.1) | ✅ non-FLSS · ✅ **FLSS drive seam fixed (FT-Task 2)** |
| All-10 step-0 coverage (§8.2) | ✅ sound (`hco_seed` load-bearing — do not regress) |
| Clock authority (§5) | ✅ Compliant (doc-drift only) |
| Entry continuity / Task 3a interaction | ✅ no conflict (pin governs; 3a dormant) |
| Seam teleport detection (`[UESS SEAM]`) | ✅ **wired for Final Turn/FLSS (FT-Task 4)** |

### Which HCO fixes carry over (important)

| HCO fix | Carries to Final Turn? |
|---|---|
| **Task 1** single animator build | ❌ **No** — different resolver; Final Turn needs its own version (this is HIGH-1) |
| **Task 2** clock realignment | ✅ Applies, **no regression**, special-cases preserved |
| **Task 3a** step-0 owner reconcile | ➖ Dormant (Final Turn `reset_count`==0) — no conflict with the pin |
| **Task 3b** `final_ball_coords` snapshot | ✅ Stamped for Final Turn too |
| **Task 3b** `[UESS SEAM]` detection | ❌ Excludes final_turn/flss (LOW gap) |
| **Task 4** cold-start backfill | ✅ Applies (coverage already sound via `hco_seed`) |

### Fix status — ALL SHIPPED (2026-07-04, uncommitted; not yet prototype-tested)
1. ✅ **HIGH-1** (FT-Task 1) — defenders synced before the Final Turn shot resolves; EOQ shots now contested. Guarded/defensive.
2. ✅ **HIGH-2 + MED-1** (FT-Task 2) — FLSS pre-shot ball attaches to the shooter; drive renders from his prior position.
3. ✅ **MED-2** (FT-Task 3) — step-0 ball pin guarded on actual delivery.
4. ✅ **L-1** (FT-Task 4) — `[UESS SEAM]` detection wired for Final Turn/FLSS.

**Remaining follow-ups (not blocking):** watch `[UESS SEAM]` logs; re-tune EOQ FG% (drops now that logic == render); the residual LOW items (L-2 alignment-floor, L-3 cosmetic drift, L-4 clock docstring) and the pre-existing `test_final_turn_coordinate_contract` / `_append_final_turn_entry_pass_if_needed` test breakage.

### What's genuinely fine (don't touch)
Non-FLSS Final Turn ball chain (handoff→pin→drive→shoot→flight→bounce all continuous) · clock/quarter-end handling · all-10 step-0 coverage · Task 3a/pin mutual exclusion · `hco_seed_coords` at `skeleton_step_emitter.py:1440` (**load-bearing — must keep the no-`final_turn` gate**).

---
---

## Full audit detail (agent-facing)

### Method
Four read-only traces against the UESS contract ([UESS_System.md](../05_UESS_System/UESS_System.md)): single-coord-source (§1/§7), clock/EOQ (§5), ball-seam (§8.4), player-coord (§8.1–8.3, §9.5). Primary files: [`turn_manager.py`](../../BackEnd/models/turn_manager.py) (`resolve_final_turn_shot`, `_emit_hco_animation_steps`, alignment builders), [`phase_resolution.py`](../../BackEnd/engine/phase_resolution.py) (`resolve_final_turn_shot_logic`), [`eoq_perfection.py`](../../BackEnd/engine/eoq_perfection.py) (`resolve_flss_shot_logic`, `build_flss_skeleton_steps`), [`eoq_clock_progression.py`](../../BackEnd/utils/eoq_clock_progression.py) (`finalize_flss_post_emit`), [`final_turn_pacing.py`](../../BackEnd/engine/final_turn_pacing.py), [`skeleton_step_emitter.py`](../../BackEnd/engine/skeleton_step_emitter.py) (shared emitter). Doc: [`EOQ_System.md`](../06_Gameplay_Systems/EOQ_System.md).

---

### HIGH-1 — Final Turn resolves defender/contest from a stale (prior-turn) or empty source (§1/§7)

The Final Turn analog of HCO's Task 1 — but **worse and structurally different**: HCO built the animator *twice* (RNG mismatch). Final Turn builds it **zero** times in the resolver, so `resolve_shot` decides the shot from data that was never synced this turn.

**Order of operations (`resolve_final_turn_shot_logic`, `phase_resolution.py:5927-6223`):**
- Builds a skeleton, `assign_roles(... skeleton=…)` (`6157`), syncs **only the shooter** via `set_shooter_coords_from_skeleton_last_step` (`6173`), then `resolve_shot(roles)` (`6177`).
- **No `Animator(...).skeleton_to_animations`, no `apply_coords_from_animations_list`, no `shot_result["animations"] = …`.** Stamps only `shot_result["skeleton"]` (`6202`).

**Why the defender is stale:**
- Final Turn is tagged `offensive_state == "HCO"`, so defender resolution goes through `_resolve_hco_shot_defenders` (`shot_manager.py:613 → 146-177`). The zone branch reads `game.zone_defender_assignments_by_step[shot_step_index]`.
- **That map is populated ONLY inside `animator.py:1922-1924` during `skeleton_to_animations`.** Since the resolver never runs the animator, the map holds the **previous turn's** assignments (different step indices) or is empty → filtered by the current shooter id → `[]` → `primary/secondary = None` → falls back to the `roles` default.
- The Euclidean-contest fallback (`shot_manager.py:799-806`) and double-team probe (`589-611`) also read `def_lineup[*].coords`, which were snapshotted at the **end of the prior turn** (`build_final_coords`) and never re-synced.
- Net: `has_contest = bool(defender or second_defender)` (`shot_manager.py:810`) with both `None` → **uncontested**. Then the emitter runs (`_emit_hco_animation_steps` → `build_skeleton_animation_steps`), rebuilds the animator (Finding HIGH-2 enabler), places zone defenders on the shooter, and **now** populates the zone map — after the outcome is fixed.

- **Severity: HIGH** — make/miss on every EOQ shot resolved from defender geometry the FE never shows (usually from *no* defender).
- **Repro:** Q-end zone Final Shot after any prior turn with a different lineup/step layout → `zone_defender_assignments_by_step[shot_step_index]` returns stale/empty → shot scored uncontested → emitter renders zone D on the shooter.
- **Fix direction:** the HCO stamp-`animations` fix **alone is insufficient** — Final Turn never builds an animator to stamp *and* never syncs `def_lineup`/`zone_defender_assignments_by_step`. Insert the **full HCO pattern** before `resolve_shot` at `phase_resolution.py:6177`, mirroring HCO `phase_resolution.py:7234-7251`:
  ```python
  animations = Animator(game).skeleton_to_animations(skeleton, off_lineup, def_lineup, add_defenders=True)
  apply_coords_from_animations_list(game, animations)   # syncs def_lineup coords + zone map
  set_shooter_coords_from_skeleton_last_step(game, skeleton, roles)
  shot_result = game.shot_manager.resolve_shot(roles)
  if animations: shot_result["animations"] = animations  # emitter reuses; no 2nd build
  ```
- **FLSS is comparatively clean:** shooter synced from the drive plan; defender only for `zone=="penalty"` where FLSS stamps `defender.coords` explicitly, and the penalty is an **attribute** formula (`roles["flss_penalty"]`), not defender geometry — so FLSS make/miss is coord-insensitive. Residual: a carried-over zone `defense_playcall` could still hit the stale `zone_defender_assignments_by_step` and override FLSS's own `roles["defender"]` (LOW–MED, cosmetic).

---

### HIGH-2 — FLSS pre-shot ball owner is empty (`""`) on every FLSS turn (§8.4 inv.1 & inv.4)

- The FLSS skeleton (`build_flss_skeleton_steps`, `eoq_perfection.py:305-357`) uses only `drive`/`shoot`/`stand` actions — **never `handle_ball`/`pass`**. `_walk_ball_owners` (`skeleton_step_emitter.py:365-366`) only assigns an owner on `handle_ball`/`pass`, so it returns `(None, None)` for every FLSS step.
- Ball then falls back to `bh_id_fallback = _safe_id(roles.get("ball_handler")) or ""` (`skeleton_step_emitter.py:1604`). But `resolve_flss_shot_logic` never stamps `result["roles"]`, so `turn_result.get("roles")` is `{}` → `bh_id_fallback = ""`.
- Result: `ball_start = ball_end = {"owner_player_id": ""}` on the drive step **and** the shoot step. Prior turn's real owner → entry-seam owner jump to `""`; `[shoot].end {owner:""}` → `[ball_flight].start {coords: shot_spot}`.
- **Severity: HIGH** (invalid ball state on 100% of FLSS turns; FLSS itself is rare).
- **Repro:** any end-of-quarter FLSS → inspect `animation_steps[0].start.ball` → `{"owner_player_id": ""}`.
- **Fix direction:** stamp `result["roles"]` (or attach the ball to the shooter/BH) so FLSS pre-shot steps carry a real owner. **Fix with MED-1** — attaching the ball to the shooter makes the drive-END coord seed (MED-1) a direct ball teleport, so they must be fixed together.

---

### MED-1 — FLSS drive: shooter step-0 **start** seeded at the drive **END** (§8.1/§8.2 seam)

- `build_flss_skeleton_steps` is passed `start_coords={sx,sy}` (real prior position) **but never references it**; the drive step's coords come from `end_coords` (drive END `ex,ey`) — `eoq_perfection.py:308-322`. Confirmed by the emitter: `flss_seed_coords[shooter] = shooter_coords` where `shooter_coords` was reassigned to the drive end (`eoq_perfection.py:442-443`, carried at `523/629`; emitter `skeleton_step_emitter.py:1432-1435`).
- Consequence: step-0 `start.coords[shooter] == dest == ex,ey` → **zero coord motion on the "sprint drive,"** and the shooter **teleports `sx → ex`** at the FLSS turn seam (gap = `compute_flss_drive_plan` drive distance, `eoq_perfection.py:254`).
- **Severity: MED** (drive-bearing FLSS only; pull-up FLSS with `ex≈sx` unaffected). **Caveat:** `advance_trigger.reason="flss_sprint_drive"` (`skeleton_step_emitter.py:1818-1819`) may trigger FE-side special tweening that masks it — verify in prototype.
- **Fix direction:** use `start_coords` for the drive step-0 position in `build_flss_skeleton_steps`, and/or seed `flss_seed_coords[shooter]` to `sx,sy` (not the drive end) at `skeleton_step_emitter.py:1432-1435`.

---

### MED-2 — Handoff self-skip leaves the step-0 pin fabricating ownership → turn-seam teleport (§8.4 inv.4)

- The step-0 pin (`skeleton_step_emitter.py:1620-1631`) sets `ball_start=ball_end={owner: ft_bh_id}` **unconditionally** when `final_turn` + `reset_count==0` + `prior_turn` is a dict — it does **not** check whether the handoff actually delivered.
- When a handoff *is* needed (`prior_owner != ft_bh_id`) but self-skips — `prior_owner`/`ft_bh_id` missing from `start_coords` (`skeleton_step_emitter.py:458`; `build_handoff_step` returns `[]`, `transition_bridge.py:457-458`), or `ValueError`/empty (`481-484`) — no delivery step emits, yet step 0 still pins to `ft_bh_id`. Prior ball rested on `prior_owner` (different player) → ball jumps `prior_owner`→`ft_bh_id` across the seam with no pass step.
- **Severity: MED** (definite teleport, but only on the coord-missing edge; a prepended walk-up makes it near-impossible since it gates all players present).
- **Repro:** Final Turn where the resolved `prior_owner` (e.g. from the `hco_setup.inbound_pass.from_player_id` fallback in `_resolve_prior_ball_handler_id`) is absent from `prior_turn.final_coords`, with `prior_owner != ft_bh_id`.
- **Fix direction:** guard the pin on `final_turn_handoff_prepended`/delivery success, or verify `ft_bh_id` == the actually-delivered owner before pinning.

---

### LOW findings

| ID | Finding | Location |
|---|---|---|
| L-1 | Final Turn + FLSS entry seams have **no `[UESS SEAM]` teleport detection** — the Task 3b detector is nested in `if is_hco_turn:` (`turn_type=="HCO" and not final_turn and not flss`), so HIGH-2/MED-1/MED-2 fire silently | `skeleton_step_emitter.py:1149-1178` (gated at `1122-1128`) |
| L-2 | Final Turn step-0 (alignment) gates on slowest offensive player, step T pinned to anchor `step_floor` **without** `max(floor, natural_t)` → the other 9 freeze short of EOQ alignment spots. §9.5-compliant (destinations are intent), carries forward continuously | `skeleton_step_emitter.py:1755-1763` |
| L-3 | Non-drive FLSS non-shooters drift toward "key" (their `stand` destination) — cosmetic, §9.5-compliant, coord-continuous | `eoq_perfection.py:306, 317, 351` |
| L-4 | **Doc drift:** stale docstrings claim `resolve_final_turn_shot_logic` sets `time_elapsed = time_remaining` / "clock runs to 0 this turn." It does **not** — `time_elapsed` is schema-derived at emit; full drain only via `ensure_quarter_end_clock_drain` on terminal turns. Canonical `UESS_System.md:36` is correct | `phase_resolution.py:5931`; `turn_manager.py:3578-3581` |
| INFO | Shooter/defender `player.coords` written pre-emit (in resolution, not mid-emit) → emitter is §8.1-clean; latent fragility only if the shooter were ever missing from step-0 seeding (not reachable in practice) | `phase_resolution.py:4409`; `eoq_perfection.py:443, 499` |
| INFO | **Premise correction — do not regress:** `hco_seed_coords` at `skeleton_step_emitter.py:1440` has **no `not final_turn` clause**. For pg_direct/skip_handoff Final Turns (no prepend) it is the ONLY thing seeding step-0 from prior `final_coords`. Adding `not final_turn` would teleport all 10 to EOQ alignment spots. Keep as-is | `skeleton_step_emitter.py:1440-1443` |

---

### Verified COMPLIANT (coverage — do not "fix")

| Boundary / contract | Evidence | Result |
|---|---|---|
| Clock: `time_elapsed` derived from emitted steps; ledger authority; monotonic; quarter-end drain | `turn_manager.py:3605-3623, 295-296, 5069-5086, 409-410`; `eoq_clock_progression.py:382-426` | ✅ §5 |
| Task 2 widening preserved Final Turn/FLSS special-cases (`max(1,te)` floor + MAKE clock-out) | `turn_manager.py:3614, 3616-3623` | ✅ no regression |
| `finalize_flss_post_emit` idempotent with `ensure_quarter_end_clock_drain` (both read pre-decrement `clock_before`) | `eoq_clock_progression.py:390-407`; `turn_manager.py:1813, 1835` | ✅ no double-count |
| `verify_animation_steps_anchor` validation-only (no clock mutation) | `final_turn_pacing.py:619-634` (logging-only call `turn_manager.py:3629-3632`) | ✅ |
| Non-FLSS ball chain: handoff converge→pass→walkup→pin→step1 pass→drive/shoot→[ball_flight]→[hold]/[bounce] | `transition_bridge.py:517,652,751-756`; `skeleton_step_emitter.py:1492-1493, 1626-1629, 2693, 2798, 2835-2992` | ✅ continuous |
| Handoff end → step-0 pin: `receiver_id` and `ft_bh_id` both `_final_turn_skeleton_bh_id(...)` (same helper) | `skeleton_step_emitter.py:433 vs 1626` | ✅ no owner jump |
| Task 3a reconciler vs final_turn pin — mutually exclusive `reset_count` guards | `skeleton_step_emitter.py:1582 (i==0 & reset>0) vs 1620 (i==0 & reset==0 & final_turn)` | ✅ no conflict |
| Player step[N+1].start == step[N].end (all 10) | `skeleton_step_emitter.py:1492-1493, 1512-1522` | ✅ §8.1 |
| All-10 end.coords every step (stationary carry) | `_build_step_end_coords_with_interrupts` iterates start (`754-792`) | ✅ |
| Final Turn step-0 all-10 coverage (pg_direct via `hco_seed`; walkup/handoff via prepend end; + Task-4 backfill) | `skeleton_step_emitter.py:1440-1443, 1492-1493` | ✅ sound |
| Emitter writes `player.coords` mid-emit | none (read-only backfill) | ✅ §8.1 |
| FLSS carries all 10 at step 0 | `flss_seed_coords` = prior `final_coords` (9) + shooter override | ✅ (shooter coord is MED-1) |
| Shooter spot 2PT/3PT classification from skeleton (deterministic) | `phase_resolution.py:4325-4410`, `set_shooter_coords_from_skeleton_last_step` | ✅ |

---

### Root-cause map to symptoms
- **EOQ shots too easy / defenders don't matter** → **HIGH-1** (contest resolved from stale/empty defender source → uncontested).
- **FLSS ball detached** → **HIGH-2** (empty owner every FLSS turn).
- **FLSS drive no motion / shooter jumps** → **MED-1** (drive-END coord seed).
- **Rare teleport entering Final Turn** → **MED-2** (handoff self-skip pin).

### Work Plan — Final Turn → 100% UESS alignment

Order **1 → 2 → 3 → 4**. Tasks 1 & 2 are the correctness wins; 3 & 4 are hardening/detection.

**FT-Task 1 — Sync defenders before the Final Turn shot resolves (fixes HIGH-1, §1/§7) — ✅ DONE & VERIFIED (2026-07-04).**
Shipped in `resolve_final_turn_shot_logic` ([`phase_resolution.py:6169-6203`](../../BackEnd/engine/phase_resolution.py#L6169)): before `resolve_shot`, `Animator(game).skeleton_to_animations(...)` → `apply_coords_from_animations_list(...)` (syncs `def_lineup` + `zone_defender_assignments_by_step`) → `set_shooter_coords_from_skeleton_last_step` → `resolve_shot` → stamp `shot_result["animations"]` (emitter reuses, no 2nd build). Idle motion is unaffected (it lives on the skeleton `_subtle_movement`, read independently by the emitter at `skeleton_step_emitter.py:1928`).
**Verification (mongomock, driven Final Turn):** call order `skeleton_to_animations → apply_coords → resolve_shot`; `shot_result["animations"]` stamped (single build, emitter does not rebuild); **defenders synced at resolve_shot: 5/5 after vs 0/5 before** (pre-fix `resolve_shot` saw all defenders at stale coords — the HIGH-1 bug). Regression: all EOQ/final-turn failures are **pre-existing** (2 coordinate-contract tests fail on clean code; 2 test files error at import on a function removed before this session; the `make_shot_family` synthetic MAKE test is the known pre-existing failure). 18 importable EOQ/final tests pass.
**Gameplay consequence (accepted):** EOQ FG% will drop toward realistic (was inflated by uncontested resolution) — expected, ties to the shot-tuning thread.

**FT-Task 2 — FLSS ball ownership + drive seam (fixes HIGH-2 + MED-1 together) — ✅ DONE & VERIFIED (2026-07-04).**
- **HIGH-2** ([`turn_manager.py`](../../BackEnd/models/turn_manager.py), after the FLSS resolve ~L3721): stamp `result["roles"].setdefault("ball_handler", result["shooter_id"])` so the emitter's ball-owner fallback (`_safe_id(roles["ball_handler"])`) attaches the ball to the shooter across the FLSS drive+shoot (was `""`).
- **MED-1** ([`skeleton_step_emitter.py`](../../BackEnd/engine/skeleton_step_emitter.py) `flss_seed_coords`): removed the shooter override to the drive-END coord — the shooter now inherits the prior-final-coords seed like the other 9 (== drive start `sx,sy`), so the sprint-drive renders real motion and the ball stays seam-continuous with the prior turn's rest.
- **Verification (mongomock, 5 FLSS turns):** pre-shot step ball owners went from `['', '', …]` (empty) **before** → `['P1'(shooter), 'P1', …]` **after** (the post-shot `None` is the `[ball_flight]` detach, correct). MED-1 construction-verified (mock's first turn has `prior_turn=None`, so the drive seam only activates with a real prior turn). Regression: FLSS/EOQ/ownership/serialization pass; only the 2 pre-existing `test_final_turn_coordinate_contract` failures remain.
- **FT-Task 1 hardened:** the pre-resolve animator build is now wrapped in try/except (mirrors the emitter's guarded build) — on failure it falls back to the emitter rebuild instead of crashing. This also fixed `test_final_turn_pacing::test_pacing_hold_floor_accounts_for_move_beats`, whose lightweight `SimpleNamespace` mock lacked `strategy_calls` for the new build. Real-game defender sync still verified 5/5.

**FT-Task 3 — Guard the step-0 ball pin on actual delivery (fixes MED-2) — ✅ DONE & VERIFIED (2026-07-04).**
[`skeleton_step_emitter.py`](../../BackEnd/engine/skeleton_step_emitter.py) final-turn step-0 pin: now pins `ball_start/end = ft_bh_id` only when **delivered** — `final_turn_handoff_prepended`, or `prior_owner == ft_bh_id` (pg_direct / skip_handoff). When a handoff was needed but self-skipped and both `prior_owner` + `ft_bh_id` have step-0 coords, it expresses the delivery as a **within-step pass** (`prior_owner → ft_bh_id`, tweened) instead of teleporting; otherwise falls back to the pin (best effort, degenerate coord-missing case).
**Verification:** compile ✓; regression 30 passed (EOQ/final-turn/ownership/bounds). Delivered case is byte-identical to the old pin (no regression by construction). The within-step-transfer branch is construction-verified — the coord-missing handoff self-skip can't be triggered in the mock harness; the prototype + FT-Task 4's `[UESS SEAM]` detection will surface it.

**FT-Task 4 — Extend `[UESS SEAM]` detection to Final Turn/FLSS (fixes L-1) — ✅ DONE & VERIFIED (2026-07-04).**
Added a **post-build** seam check at the end of `build_skeleton_animation_steps` ([`skeleton_step_emitter.py`](../../BackEnd/engine/skeleton_step_emitter.py), before `return steps`), scoped to `final_turn`/`flss`: resolves the emitted step-0 ball position (attached → owner's step-0 coord; loose/in-flight → explicit) and compares it to the prior turn's `final_ball_coords`; logs `🎯 [UESS SEAM] FINAL_TURN|FLSS entry ball teleport candidate…` when they diverge > `UESS_SEAM_TELEPORT_GRID_EPSILON` (1.5 grid). Detection-only, behavior-neutral.
**Verification:** compile ✓; Final Turn 10/10 and FLSS 10/10 resolve without crash; regression 42 passed. (Fires only on a real prior-turn seam divergence — grep `[UESS SEAM]` in prototype logs.)

### Appendix — key line index
- Single-coord-source: `phase_resolution.py:5927-6223, 6157, 6173, 6177, 6202` (resolver); `shot_manager.py:146-177, 589-611, 799-810, 613`; `animator.py:1922-1924`; HCO reference fix `phase_resolution.py:7234-7251`.
- Clock: `turn_manager.py:3605-3623, 295-296, 1813, 1835, 5069-5086`; `eoq_clock_progression.py:382-426`; `final_turn_pacing.py:619-634`.
- Ball seams: `skeleton_step_emitter.py:365-366, 1604-1609, 1620-1631, 1149-1178`; `eoq_perfection.py:305-357`; `transition_bridge.py:457-458, 651-756`.
- Player coords: `eoq_perfection.py:254, 308-322, 442-443`; `skeleton_step_emitter.py:1425-1443, 1492-1522, 1755-1763`; `turn_manager.py:3756-3830` (alignment builders).
