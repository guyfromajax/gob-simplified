# Fast Break Refactor — Next-Thread Handoff Prompt

> **Purpose:** Copy-paste this into a fresh thread to continue work on Fast Break animation + advance-trigger issues. Self-contained — assumes no memory of the prior thread.

---

## What just shipped (prior thread, May 2026)

**Movement Rate Refactor** — full phase 0 → 4d. Status: ✅ shipped, prototype-confirmed.

- Two-tier movement model: **AG-driven** (max-effort) vs **cruise-speed** (HCO/HCT bring-up)
- Backend AG curve `ag_to_grid_per_game_sec(ag)` in `BackEnd/utils/shared.py`: linear, AG=0→10, AG=50→16, AG=100→22, soft-cap 30
- Per-player game-clock burn via `calc_ag_segment_seconds(start, end, player, archetype="default|drive|shot_motion|compressed_hco")`
- Per-player visual via `waypoint.game_seconds` (HCT) and `turnData.bringup_per_player_seconds` (HCO bring-up) — frontend uses `× clockSecondMs` as authoritative tween duration, falls back to AG-px-per-sec when absent
- Legacy pace constants (OF=20, COF=16, Drive=12, Compressed HCO=10, HCO Shot=10) **retired** from `BackEnd/constants/__init__.py`. `PASS_GRID_SPOTS_PER_GAME_SECOND=36` kept (ball physics, not AG)
- 10 `calc_skeleton_step_timing_contract` callers in `phase_resolution.py` and `shot_manager.py` migrated to pass `off_lineup`
- `apply_fast_break_cg_time` in `phase_resolution.py` migrated for BH cover-ground (only fast-break touch in this refactor)

Full record: `_documentation_master/projects/Movement_Rate_Refactor.md`.

**Critical invariant:** AG=50 player produces the EXACT legacy timing for every archetype. This made phased migration safe — average lineups behave identically; only fast/slow players see speed differences.

---

## The new problem: Fast Break

The user reports two classes of issues with Fast Break turns:

1. **Advance triggers not taking hold** — phase boundaries inside fast break sequences don't reliably fire. Outlet → BH cover-ground → shot transitions sometimes hang or short-circuit.
2. **Animation timing issues** — visual pacing during fast breaks feels off (no specific reproduction yet, the user hasn't drilled in).

The user has not done a detailed diagnosis — they want a fresh trace and a project plan.

---

## Why this work has good foundations

The Movement Rate Refactor's patterns are reusable for fast break:

- **AG curve + archetype multipliers** — `calc_ag_segment_seconds` is ready to call wherever a Player is in scope
- **Per-player `game_seconds` on waypoints** — pattern from `dynamic_hct.py`, frontend already respects it in `playTurnAnimation`'s step loop
- **Per-turn `bringup_per_player_seconds`-style dict** — pattern from `_calc_hco_bringup_per_player_seconds`, frontend respects in `runSetupTween`
- **Dual-path safety** — every helper has a `player=None` / `off_lineup=None` legacy fallback, so partial migration doesn't break unmigrated sites

Apply the same incremental pattern: helper-only Phase 1 → wire one site at a time → test in prototype between → retire any leftover legacy paths.

---

## Code pointers (don't trust as exhaustive — verify)

**Frontend:**
- `FrontEnd/static/js/phaser/animation/fastBreak.js` — main fast-break choreography (very long file, ~2000+ lines per prior memory). `runFastBreakSequence` is the entry. Contains outlet receiver setup, BH cover-ground, trailers, shot, etc.
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` `handleFastBreak` — top-level handler. Routes to `runFastBreakSequence`.
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — `playTurnAnimation` step loop is for HCO/HCT/FCP, NOT fast break. Fast break uses its own sequence.

**Backend:**
- `BackEnd/engine/phase_resolution.py` — `resolve_fast_break_logic`, `apply_fast_break_cg_time` (already AG-migrated for BH cover-ground)
- `BackEnd/models/animator.py` — `capture_fast_break_animation` (constructs the animation payload)
- `BackEnd/models/shot_manager.py` — handles the fast-break shot moment (separate from cover-ground timing)

**Sub-flows known to exist:**
- **Covert Release** — outlet pass + cover-ground variant
- **Rim Runner** — different choreography where a runner sprints ahead and the BH catches up
- (Verify in code; there may be others)

---

## Suggested process for the new thread

Mirror what worked for Movement Rate Refactor:

### Phase 0 — Discovery + Scoping (no code)
- Read `runFastBreakSequence` in `fastBreak.js` end-to-end
- Map out the advance triggers ("we proceed to next phase when X")
- Map out the timing logic (where does fast break compute durations? Are there hardcoded numbers? Does it use `getPlayerDuration`?)
- Identify the sub-flows and their differences
- Catalog the bugs the user reports (ask the user to demonstrate in prototype if specifics are missing)
- Output: `Fast_Break_Refactor.md` — design doc with current-state map, bugs, proposed fixes, phase plan

### Phase 1+ — Incremental migration / fixes
- Each phase is one PR
- AG=50 invariant pattern: any new helper or migration must produce identical timing for AG=50 players
- Smoke test backend with inline Python (no DB writes)
- Prototype-test in browser between phases
- Use `is_user_facing_game(game)` from `BackEnd/utils/shared.py` to gate any diag logs (franchise mode runs CPU sims in parallel — gating prevents log noise)

### Standing rules (from prior thread)

1. **Pytest is conditionally allowed** — only against `gob-staging` DB AND only if no existing docs are deleted/replaced. If a test fixture clears collections, refuse to run it. (See `feedback_no_pytest.md` in user memory.)
2. **Confirm risky actions before taking them** — git pushes, force operations, anything destructive should be confirmed by the user first.
3. **Eyeball-test feature behavior** — type checks and smoke tests verify correctness, not feature feel. Browser prototype testing is the verification path.
4. **Per-player AG access** — `player.attributes.get("AG", 50)` is the canonical pattern. Default to 50 (average) when missing.
5. **Coord conventions** — HOME on offense advances toward x=91; AWAY toward x=9. `get_away_player_coords` flips x → 100-x for AWAY. `animator.py` is the source of truth for orientation.

---

## Carry-over context

**Player coord staleness is a known unrelated issue.** `player.coords` doesn't always reflect post-BIP positions because BIP setup updates the sprite, not the Player object. We patched it for HCT (`_hct_setup_start_coords` reads from `HCT_SETUP_POSITIONS` directly). Same staleness probably exists in fast break — be alert if you read `player.coords` in fast break code paths.

**Outstanding from prior thread:** the Phase 3 "retire/simplify the contract/tolerance system at `turnAnimation.js:4900-5075`" goal was deferred. The system still works (just no longer detects anything since clock and visual are synced by construction). It's ~125 lines of overhead per step. Optional cleanup; not urgent.

**BIP responsiveness updates landed alongside:** `inboundHoldMs` 2 × 200 ms holds removed for BIP path; BIP `runPass` duration set to 250 ms. SIP path retains a single 200 ms hold.

---

## First message to send the new thread

Use something like this as your opening prompt:

> I want to refactor the Fast Break system. Read `_documentation_master/projects/Fast_Break_Handoff.md` for full context — it captures everything from the prior thread (Movement Rate Refactor shipped, patterns to apply, code pointers, process). Don't write code yet. Start with Phase 0: trace `runFastBreakSequence` end-to-end, identify the advance triggers and timing computation, and write a `Fast_Break_Refactor.md` project doc with current-state map and proposed phased plan. Once that doc is ready, we'll align on scope before any code changes.

---

## Quick-reference: key shipped artifacts

- `_documentation_master/projects/Movement_Rate_Refactor.md` — design + phase history
- `_documentation_master/projects/Animation_Cleanup.md` — broader animation tech-debt queue
- `_documentation_master/05_Animation_System/Core_Animation_System.md` — core architecture (updated with tween-duration-authority section)
- `_documentation_master/05_Animation_System/AG_Implementation.md` — AG curve canon (updated for AG v2)
- `_documentation_master/05_Animation_System/Transition_Systems.md` — hold/delay reference (updated for BIP responsiveness)
- `BackEnd/utils/shared.py` — timing helpers (`calc_ag_segment_seconds`, `calc_cruise_segment_seconds`, `ag_to_grid_per_game_sec`, `_calc_hco_bringup_per_player_seconds`, `calc_skeleton_step_timing_contract`)
- `BackEnd/constants/__init__.py` — `CRUISE_BASELINE_GRID_PER_GAME_SEC`, `BH_CRUISE_MIN/MAX`, `DRIVE_MULTIPLIER`, `SHOT_MOTION_MULTIPLIER`, `PASS_GRID_SPOTS_PER_GAME_SECOND`
