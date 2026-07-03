# Fast Break → Full UESS Compliance Migration

**Status:** Proposed work plan (not started)
**Owner:** TBD
**Scope:** Make all Fast Break (FB) **backend logic** source player coordinates from the same live/shared state the UESS animation renders from, and close the remaining frontend fallback/observability gaps.

---

## 1. Why this exists

UESS is fundamentally a **playback contract**: it guarantees accurate, step-by-step live coords for the steps it *emits and renders*, with each step starting from the prior step's rendered end. It does **not** guarantee that the *resolver* (the backend logic that decides a turn's outcome) reads the same coordinates the emitter later renders.

For most turn types (e.g. **HCO**) logic and animation already share one source: both seed from `prior_turn.final_coords` (see `dynamic_hct._seed_lineup_coords_from_prior` and `dynamic_hct_step_emitter` `prior_final_coords`). That is the compliance bar.

Fast Breaks are the exception. Some FB resolution logic still borrows the **legacy animator packet** produced by `BackEnd/models/animator.py::capture_fast_break_animation` as its geometry input. Because that packet stores pre-staged / get-back *destination* coords (not live positions), logic and animation can diverge. This is the root cause behind the recent run of FB coord bugs:

- Phantom "Nice stop" defensive stops (defenders seeded at rim get-back destinations). *(Fixed — see §4 Phase 0.)*
- Shots fired "from the other side of the court" (shot spot anchored to a stale/legacy coord).
- RR "jetting" to the rim (drive-onset coord mismatch).

### Definition of "UESS compliant" for FB backend logic

A FB turn type is compliant when **every coordinate the resolver reads to make a decision** comes from a live/shared source — one of:

1. `player.coords` (live), OR
2. `prior_turn.final_coords` / position snapshots (`last_stealer_coords`, `defense_release_coords`, `offense_getback_coords`), OR
3. Deterministic geometry relative to the attacking basket / named HCO string spots.

…and **never** from `capture_fast_break_animation` output (`fb_animations` entry `end` coords, or `fb_roles["_bh_final_x/_y"]` which the animator writes).

`final_coords` (the next-turn seed) must derive from the **UESS emitter's rendered step-end coords**, matching HCO.

---

## 2. Current state matrix

Legend: 🟢 compliant (live/shared/geometric) · 🔴 gap (reads legacy animator) · ⚫ dead code under current flags (latent gap)

| FB type | `bh_start` | `def_starts` (cutoff race) | `shot_spot` / `bh_target` | `final_coords` | Calls `capture_fast_break_animation` on live path? |
|---|---|---|---|---|---|
| **Covert Release** | 🟢 `defense_release_coords`/`offense_getback_coords` → `player.coords` | 🟢 `_defender_outlet_coord` → getback/live | 🟢 `_compute_bh_target` (geometric) | 🟢 UESS step-ends | 🟢 No (resolver returns first) |
| **After-Steal** | 🟢 `last_stealer_coords` → `player.coords` | 🟢 `_lineup_starts_by_pos` (live) | 🟢 `_compute_bh_target` (geometric) | 🟢 UESS step-ends | 🟢 No |
| **Rim Runner** | 🟢 `rim_runner_burst_phase.rr_to` (catch target) *(fixed)* | 🟢 `_lineup_starts_by_pos` (live) *(fixed)* | 🟢 `_compute_bh_target` (rim-relative) *(fixed)* | 🟢 UESS step-ends | 🟠 Yes (render artifact only; no longer feeds logic) |
| **Triangle** | 🟢 `triangle_setup_phase.ball_handler_to` (setup spot) *(fixed)* | 🟢 `_lineup_starts_by_pos` (live) *(fixed)* | 🟢 HCO string spots (`_spot_coords`) | 🟢 UESS step-ends | 🟠 Yes (render artifact only; no longer feeds logic) |

**Bottom line:** All four FB types' backend logic now source `bh_start`, `def_starts`, and `shot_spot` from live/geometric coords — the legacy animator packet no longer feeds any FB logic decision. `capture_fast_break_animation` still runs on RR/Triangle but its output is a render artifact only (Phase 3 confirms/retires the call itself; Phase 4 removes the dead fallback geometry).

### Key references

- `bh_start` (fixed): `BackEnd/engine/rim_runner_drive_integration.py` (`bh_start = _drive_onset_coord(fb_roles, shooter)`; helper sources `rim_runner_burst_phase.rr_to` / `triangle_setup_phase.ball_handler_to`, live `_coord_of` fallback).
- `def_starts` (fixed): `BackEnd/engine/rim_runner_drive_integration.py:154` (`_lineup_starts_by_pos(def_lineup)`).
- RR shot-spot (fixed): all three RR shot seams in `BackEnd/engine/rim_runner_fast_break.py` now set `roles["shot_spot"] = _compute_bh_target(is_away_offense)` (rim-relative). The animator-written `_bh_final_x/_y` (still stamped at `BackEnd/models/animator.py:299-300`) is no longer read by RR logic — remaining `_bh_final` reads live only in the legacy CR/universal branch in `phase_resolution.py` (Phase 4).
- Triangle shot spot (compliant): `BackEnd/engine/rim_runner_fast_break.py:~400` (`fb_roles["shot_spot"]` from `HCO_STRING_SPOTS` via `_spot_coords`).
- `final_coords` (compliant, all types): stamped in `BackEnd/models/game_manager.py:792-798` via `build_final_coords` after `sync_lineup_coords_from_turn` (`BackEnd/utils/shared.py:3542-3562` — schema `animation_steps[-1].end.coords` takes precedence).
- Flags (all `True`): `BackEnd/constants/__init__.py:267-274`.

### Dead code / latent gaps (only reachable if flags flip off)

- ✅ ~~`_apply_universal_geometry_for_rr_shot`~~ **removed (Phase 4)** along with its 3 dead call sites and the `USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR` flag. RR's legacy fallback now goes straight to `resolve_shot` with the rim-relative `roles["shot_spot"]`. Note: `compute_fb_shot_geometry` itself is **kept** — it is still live via `dynamic_hct_shot.py` (broken-HCT FB) and the legacy after-steal path.
- ⚫ `phase_resolution.py:2026-2148` ("FB UNIVERSAL CR" legacy SHOT branch) sources `cr_shooter_start`/`cr_defender_starts` from `fb_animations`. Dead while `USE_FB_DRIVE_RESOLUTION_CR = True`. *(Not removed — CR flag retirement deferred; tracked below.)*
- ⚫ `covert_release_step_emitter._build_outcome_step` (`:1084-1148`) reads `turn_result["animations"]`. Dead while CR routes to `_build_cr_drive_resolution_animation_steps`.

---

## 3. Frontend compliance gaps

Frontend rendering is in good shape but has three non-blocking gaps.

1. **All four FB types render via UESS schema playback** — they are in `MIGRATED_FB_PLAYS` (`FrontEnd/static/js/phaser/animation/AnimationEngine.js:614-617`), so any FB turn carrying non-empty `animation_steps` uses `runSchemaPlaybackTurn()` (NEW_PLAYBACK_ENGINE). No FB type is force-routed to legacy.

2. **Legacy fallback on emitter `None`** *(real coupling risk)* — if a backend emitter returns `None`/empty steps, the turn ships with only a legacy `animations` list, the FE drops to `runFastBreakSequence()` (`fastBreak.js`), **and** that turn's `final_coords` is stamped from legacy `animations` finals instead of UESS step-ends (`shared.py:3510-3530` fallback) — which the *next* turn then seeds from. CR logs an explicit `🚨 [CR EMITTER NULL] … FE → LEGACY` marker; RR / Triangle / After-Steal only log a generic `… failed` warning → **observability parity gap**.

3. **Stale comments** — `AnimationEngine.js:606-613` and `phase_resolution.py:1887-1888, 2286-2287` still claim only CR/RR are migrated, contradicting the code (all four are). Documentation-only.

---

## 4. Work plan

### Phase 0 — Defender seeding (DONE)
`def_starts` for RR/Triangle changed from animator ends to live `_lineup_starts_by_pos(def_lineup)` (`rim_runner_drive_integration.py:154`); buggy `_def_starts_by_pos_from_animations` helper removed. Regression: `tests/test_rr_triangle_drive_resolution.py::test_def_starts_seeded_from_live_coords_not_animation_ends`.

### Phase 1 — RR/Triangle `bh_start` → live/shared source (DONE)
**Goal:** stop seeding the drive resolver's BH origin from the animator packet.

**Resolution.** The legacy `_anim_end_coord(fb_animations, …)` seed was removed and replaced with `_drive_onset_coord(fb_roles, shooter)` (`rim_runner_drive_integration.py`), which sources the drive-onset from the *same backend geometry the UESS step emitters render the drive from*:
- **Rim Runner:** `fb_roles["rim_runner_burst_phase"]["rr_to"]` — the RR's lead-pass **catch target**, i.e. the emitter's lane-pass `catch_grid` (`rim_runner_step_emitter._build_lane_pass_step`).
- **Triangle `triangle_bh_drive`:** `fb_roles["triangle_setup_phase"]["ball_handler_to"]` — the BH's triangle setup spot the emitter moves him to before the drive (`triangle_step_emitter`), i.e. the drive-step start.
- **Fallback:** live `_coord_of(shooter)` (`player.coords`). The animator packet is never read for logic.

This is why Candidates A/B (`player.coords` / `off_starts`) were rejected: for RR both represent end-of-DREB, *upcourt* of the actual catch point, which would start the drive too far back. `rr_to` is the deterministic catch datum available at resolve time and is exactly what the emitter targets, so resolver and animation converge.

- **Behavior note:** this is an intended **value-correcting** change (the prior `bh_start` was a rim-relative random rebounder spot or a `player.coords` fallback that already diverged from the rendered drive), not a zero-behavior-change refactor.
- **Known residual (future work):** on a *lead* lane pass the emitter renders the RR's step-end at the pass **meet point** (which can fall short of `rr_to` when the ball arrives first) and on a truncated burst the sloppy-pass catch is the RR's truncated position — both slightly behind `rr_to`. The resolver seeds `rr_to` (the intended catch target) since the emitter's exact meet point is computed *after* the resolver runs. A fully shared single-source catch point (compute once, consumed by both resolver and emitter) is a larger refactor tracked for a later phase.
- **Tests:** `tests/test_rr_triangle_drive_resolution.py::test_rr_bh_start_seeded_from_rr_to_not_animation_packet` and `::test_triangle_bh_drive_bh_start_seeded_from_ball_handler_to` (spy asserts `bh_start` = the backend datum, not the `fb_animations` end nor live end-of-DREB).

### Phase 2 — RR `shot_spot` → geometric/live (DONE)
**Goal:** RR shot spot no longer sourced from animator-written coords.

**Resolution.** All three RR shot seams in `rim_runner_fast_break.py` (fb_open-with-defender, catch-and-shoot, completion) now set `roles["shot_spot"] = _compute_bh_target(is_away_offense)` — the same rim-relative helper CR and After-Steal use (`x = 91-(2..4)` home / `9+(2..4)` away, `y ∈ [19,31]`). Per the decision recorded in scope, RR adopts **rim-relative** geometry (not Triangle's HCO string spots). Computed once per turn so the pre-shot snapshot, drive resolver (`shot_spot` → `target`), and legacy fallback all share one geometric spot.

- **Behavior note:** value-correcting — the shot spot is now deterministic rim-relative geometry instead of the animator-written `_bh_final_x/_y` catch/heuristic coord that produced the "shot from the complete other side of the court" class of bugs.
- The `_bh_final_x/_y` keys are still stamped by the animator but are **no longer read** by RR logic. Remaining reads live only in the legacy CR/universal branch (`phase_resolution.py`), addressed in Phase 4.
- **Tests:** `tests/test_rr_triangle_drive_resolution.py::test_rr_shot_spot_is_rim_relative_not_animator_packet` (parametrized home/away; asserts the spot the RR seams stamp is within 2–4 grid of the attacking rim, never backcourt).

### Phase 3 — Retire `capture_fast_break_animation` from the RR/Triangle **logic** path (DONE)
**Goal:** the legacy packet is no longer an *input to logic* (it remains a legacy/fallback render artifact until Phase 5).

**Audit result — the packet is render-only on the RR/Triangle path:**
- `_anim_end_coord` no longer exists (removed in Phase 1). `rg _anim_end_coord` → zero hits.
- `rg _bh_final` → hits only in `animator.py` (the *writer* + the animator's own defender-placement render math) and the legacy CR/universal branch in `phase_resolution.py:2015-2256`. **None on the RR/Triangle logic path** (`rim_runner_fast_break.py` now only has explanatory comments).
- The drive resolver reads `fb_animations` only at `_base()` (`rim_runner_drive_integration.py:218`) to store `turn_result["animations"]`; every geometry input comes from `drive` / `_build_offense_end_coords` / `_lineup_starts_by_pos` / `_coord_of`.
- Every `capture_fast_break_animation` call in `rim_runner_fast_break.py` (shot seams + non-shot outcomes: outlet-denied, enter-HCO, hold-up, interception, batted-OOB) stores the result only on `…["animations"]`. Each paired `apply_coords_from_animations_list` is gated `fb_play_key not in (RIM_RUNNER, TRIANGLE)`, so it **never mutates `player.coords`** for RR/Triangle.
- The only logic reader of the packet, `_apply_universal_geometry_for_rr_shot`, is unreachable while `USE_FB_DRIVE_RESOLUTION_RR` is `True` (gated behind `if drive_turn is not None: return`). It is dead fallback code → Phase 4.
- Dispatch confirms isolation: `phase_resolution.resolve_fast_break_logic` routes RR/Triangle to `resolve_rim_runner_fast_break` and `return`s at `:1275`, so RR/Triangle never reach the legacy `_bh_final` shot branch at `:1990`.

**Decision:** the `capture_fast_break_animation` call is **kept** (still needed to populate `turn_result["animations"]` as the frontend's legacy fallback render until Phase 5 hardens the emitter-`None` path) and **marked render-only** in code (`rim_runner_fast_break.py`, primary shot seam).

- **Acceptance met:** `rg` shows zero logic reads of `fb_animations` / `_bh_final_*` on RR/Triangle; emitters seed from live `player.coords` / geometry (`rim_runner_step_emitter._all_player_start_coords`, `triangle_step_emitter`).
- **Tests:** `tests/test_rr_triangle_drive_resolution.py::test_resolver_ignores_animation_packet_for_logic` (empty `fb_animations` still resolves; packet passes through only as the render artifact).

### Phase 4 — Dead-code removal & flag retirement (PARTIAL — RR-scoped DONE)
Scoped to the RR-specific dead code per decision (full flag retirement deferred — see below).

**Done (RR-scoped):**
- Removed `_apply_universal_geometry_for_rr_shot` (function + all 3 dead call sites in `rim_runner_fast_break.py`) and the now-unused `USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR` import.
- Retired the `USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR` flag constant (`BackEnd/constants/__init__.py`). RR's legacy fallback (only reachable if `USE_FB_DRIVE_RESOLUTION_RR` is flipped off) now calls `resolve_shot` directly with the rim-relative `roles["shot_spot"]` from Phase 2.
- **Verified:** `rg USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR` / `_apply_universal_geometry_for_rr_shot` → no live code references (only a historical docstring/comment). 79 FB tests pass, including `test_after_steal_fast_break_stats` (legacy flag-flip path intact).

**Explicitly NOT removed (why):**
- `compute_fb_shot_geometry` — **still live** via `dynamic_hct_shot.py` (broken-HCT FB) and the legacy after-steal path. Must stay.
- `USE_FB_DRIVE_RESOLUTION_*` flags — kept as the reversible safety switch. Legacy after-steal is still exercised by `test_after_steal_fast_break_stats.py` (flag off), so these are not yet permanent.
- CR: the `phase_resolution.py:2026-2148` "FB UNIVERSAL CR" branch + `USE_UNIVERSAL_FB_SHOT_GEOMETRY_CR` + legacy CR `_build_outcome_step` animator reads — deferred (CR flag retirement belongs with the CR migration soak, tracked in `FB_Drive_Cutoff_Work_Plan.md`).

**Remaining for a future full Phase 4** (once CR/after-steal drive resolution is confirmed permanent): delete the CR universal branch + CR/`_CR` flag, then collapse `USE_FB_DRIVE_RESOLUTION_*`.
- **Acceptance (RR portion):** no reachable code path reads the animator packet for RR logic; `USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR` removed.

### Phase 5 — Frontend hardening & observability parity (DONE)
Additive-only (logging + comments); no logic/flow changes. All four FB emitters + their caller wrap sites now emit a consistent, greppable trail whenever a turn drops to the legacy renderer.

**Done — emitter-side `EMITTER NULL` markers (parity with CR):**
- RR (`rim_runner_step_emitter.py`): the previously-silent top-level entry guards now log `🚨 [RR EMITTER NULL] guard={fast_break_play_mismatch,missing_burst_phase,empty_start_coords} — FE will fall to LEGACY_HANDLER`. Deeper sub-step `None` returns were already logged by their sub-builders (`BURST_STEP_NONE`, `OUTLET_PASS_STEP_NONE`, etc.).
- Triangle (`triangle_step_emitter.py`): same three entry-guard markers as RR (`🚨 [TRIANGLE EMITTER NULL] guard=…`). The `_is_full_simulation` early-return is left silent + commented (intentional skip, not a fallback).
- After-Steal (`after_steal_fast_break_step_emitter.py`): **already** had `🐛 [AFTER_STEAL_NONE site=…]` markers at every guard — no change needed.

**Done — caller-side `EMITTER NULL CONSEQUENCE` markers (parity with CR):**
- `phase_resolution.py` RR/Triangle wrap (defensive-stop path) and After-Steal wrap (outcome path) now add the `else:` consequence log (`🚨 [<TYPE> EMITTER NULL CONSEQUENCE] … animation_steps not set, FE → LEGACY`) and upgraded their bare `logging.warning` exception handlers to `logging.exception` with a `🚨 [<TYPE> EMITTER EXCEPTION] … FE → LEGACY` marker. (CR already had both; RR/Triangle/After-Steal were missing the `else` + used non-tracebacked warnings.)

**Done — `final_coords` fallback observability:**
- `sync_lineup_coords_from_turn` (`BackEnd/utils/shared.py`) now logs `🚨 [FB FINAL_COORDS FALLBACK] …` when a `fast_break` turn produced no `animation_steps` and therefore seeded the next turn's `player.coords` from the legacy `animations[]` finals. This is the cross-turn coord-drift counterpart to the per-turn `EMITTER NULL` logs. (Warn-only; no annotation written to `turn_result` to avoid serialization side-effects.)

**Done — stale comments fixed:**
- `AnimationEngine.js:606-613` — removed the "currently only Covert Release and Rim Runner are migrated / un-migrated Triangle / After Steal" wording (all four are migrated; `MIGRATED_FB_PLAYS` already lists all four). Now points at `FB_UESS_Migration.md`.
- `phase_resolution.py` (both CR wrap sites) — "Other FB variants still use legacy rendering until their own migrations land" replaced with the accurate "all FB variants emit unified `AnimationStep[]`; legacy is fallback-only" note.

**Verification:** `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_rr_triangle_drive_resolution.py tests/test_fb_drive_resolution.py tests/test_after_steal_fast_break_stats.py -q` → **31 passed, 1 failed**. The single failure is the pre-existing, unrelated `test_no_meet_all_defenders_to_basket_spot` (documented below). No lint errors on the four edited backend files.

### Post-Phase 5 — Universal drive-step helper (SS&S consolidation) (DONE)
The drive-resolution orchestration (meet / neutral-shoot / neutral-pass / NO_MEET-POS_O drive + shot-micro → post-shot → make-override → terminal-freeze) had been **copy-pasted into three near-identical orchestrators** and had drifted — the `t_drive` traversal floor + crash-to-basket fixes lived only in the RR/Triangle copy, so After-Steal and Covert Release still finished short of the rim and parked the off-ball cast.

**New single source of truth:** `BackEnd/engine/fb_drive_step_emitter.py::build_fb_drive_resolution_steps`. It returns a fresh 0-based `AnimationStep[]` from the `fb_drive_resolution` payload; each caller builds its own preamble (burst / lane pass / outlet / start snapshot), derives `stealer_id` + `start_coords` + `end_coords`, then delegates.

**Callers (now thin adapters):**
- `rim_runner_step_emitter._build_finisher_drive_resolution_steps` (RR + Triangle) → `kind_prefix="rim_runner"`, `stamp_fb_start_announcement=False` (FB banner already stamped on burst/lane), `suppress_stinger=False`. Still returns to `append_lane_pass_to_rr_resolution_steps` which rebases + extends.
- `after_steal_fast_break_step_emitter._build_drive_resolution_animation_steps` → `kind_prefix="after_steal"`, `stamp_fb_start_announcement=True`, `suppress_stinger=True` (Steal FBs show the banner but not the court stinger). No preamble → returns the helper result directly.
- `covert_release_step_emitter._build_cr_drive_resolution_animation_steps` → keeps its optional outlet-pass preamble, then `kind_prefix="covert_release"`, `stamp_fb_start_announcement=True`, `suppress_stinger=False`; rebases + extends the helper's steps onto the outlet step.

**Per-play divergences are parameters** (`kind_prefix` for advance-trigger metadata, `stamp_fb_start_announcement`, `suppress_stinger`); the offense end-coords key (`rr_end_coords` / `after_steal_end_coords` / `cr_end_coords`) and start-coord source stay caller-side.

**Universal behavior decisions (product, July 2026 — all four types now):**
- Driver + cutoff defenders use `finisher_pace` (standard/HCO) on the meet/drive (previously After-Steal/CR sprinted the driver).
- NO_MEET/POS_O drive floors `t_drive` to the shooter's real catch→rim traversal (POS_O against the knot-path length) so he never finishes short of the rim.
- NO_MEET/POS_O drive crashes the off-ball cast toward `basketSpot` at sprint so they advance in stride instead of parking on short-budget end coords.
- DEFENSIVE_STOP uses the named-defender "Nice stop" announcement (`_build_nice_stop_announcement`) everywhere (After-Steal previously used the plain team-only text).
- DEFENSIVE_STOP "Great Stop!" callout (ribbon + `duke-great-stop.wav` stinger + hold) is **gated on the ball crossing midcourt** (`x=50`) toward the offense's basket: home offense fires only at `ball_x >= 50`, away offense only at `ball_x <= 50`. Below that, the whole callout is suppressed (no ribbon, no stinger, no hold). Backend is SS&S: `_build_nice_stop_announcement(..., ball_spot=...)` returns `None` when not crossed; call sites pass the ball handler's stop coord (universal helper → `meet_target`; CR outcome step → ball owner's end coord). The legacy FE path (`fastBreak.js::animateDefensiveStop`) mirrors the same check using the ball handler sprite's `gridX`. Both paths fail open (allow the callout) when the ball coordinate is unavailable.

**No import cycles:** the helper's module-level imports are cycle-free (`constants`, `animation_step_helpers`, `animation_step_schema`, `shared`); the emitter primitives (`_build_drive_step`, `_build_meet_drive_step`, `_build_nice_stop_announcement`, `_suppress_fast_break_stinger`, post-shot/shot-micro/terminal-freeze) are lazy-imported inside the function, and each caller lazy-imports the helper.

**Verification:** `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_rr_triangle_drive_resolution.py tests/test_fast_break_rr_triangle_updates.py tests/test_after_steal_drive_resolution.py tests/test_after_steal_fast_break_stats.py tests/test_covert_release_drive_resolution.py -q` → **57 passed**. No lint errors on the four backend files. The two known pre-existing/unrelated failures (`test_no_meet_all_defenders_to_basket_spot`, `test_outlet_pass_roles_when_rebounder_is_none`) were confirmed to fail identically on a clean tree (resolver/logic layer, not the emitters).

### Post-Phase 5 — Universal outlet-pass helper (SS&S consolidation) (DONE)
The two **live** FB outlet-pass builders (RR/Triangle `_build_outlet_pass_step`, Covert Release `_build_simplified_outlet_pass_step`) were ~60% identical on the pass mechanics and diverged only on the non-key cast's movement. Consolidated the shared core into `BackEnd/engine/fb_outlet_pass_step_emitter.py::build_fb_outlet_pass_step`.

**Shared core (now single source):** sharp/sloppy pass-rate gating on `outlet_score`, `t = max(FB_PASS_MIN_GAME_SECONDS, dist/rate)`, stationary passer(`"pass"`)/receiver(`"receive"`), ball transfer passer→receiver, `ball_reaches_player` advance-trigger (+`outlet_score` metadata), interrupted-coord math, and `_stamp_tween_durations`.

**Flavor (per-play, passed in):** a `mover_targets: {player_id: (target_coord, archetype, action)}` map for the non-key cast.
- RR/Triangle: resolver-authored off `rim_runner_burst_phase` — RR sprints to `rr_to`, outlet defender `guard_ball` to `outlet_defender_to`, `other_players[]` cut/`guard_offball` to explicit spots; honors `rr_archetype_override` (Triangle → `"sprint"`).
- Covert Release: random 1–6 grid forward drift at `standard`/`cut` (no resolver payload).

**No gameplay logic moved.** Diligence confirmed both live outlet emitters are pure resolver renderers — the "right read" that decides outcomes lives entirely in the resolver (`fb_stop_decision.py`, `cutoff_resolution.py`), untouched. The only embedded emitter-side read (`player_read ≥ outlet_score×3` cutoff-vs-retreat positioning) is **cosmetic** and lives solely in the flag-gated CR *legacy* `_build_outlet_pass_step`, which was intentionally **not** migrated — it dies with the deferred `USE_FB_DRIVE_RESOLUTION_CR` retirement.

**Blast radius:** zero on HCO/BIP/SIP/Reset — the FB helper is standalone and does not touch the engine-wide `transition_bridge.build_pass_step` (the deeper "rebase onto the shared pass primitive" option was declined in favor of the contained helper).

**Verification:** `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_rr_triangle_drive_resolution.py tests/test_fast_break_rr_triangle_updates.py tests/test_fast_break_outlet_pass.py tests/test_covert_release_drive_resolution.py tests/test_after_steal_drive_resolution.py tests/test_after_steal_fast_break_stats.py -q` → **58 passed, 1 pre-existing unrelated failure** (`test_outlet_pass_roles_when_rebounder_is_none`, resolver layer). No lint errors.

**Not consolidated (by design):** burst step and lane pass are already shared between their only two consumers (RR + Triangle); wrapping them adds indirection with no payoff and no cross-type drift. After-Steal has no outlet/burst/lane. See discussion in the babysit/decision log.

---

## 5. Testing strategy

- **Unit/spy tests** per phase asserting the exact coord source passed into `resolve_fb_drive_step` (`bh_start`, `shot_spot`) is live/geometric, not the `fb_animations` packet (pattern already established in `tests/test_rr_triangle_drive_resolution.py`).
- **Cross-turn `final_coords` continuity:** assert an FB turn's `final_coords` equals its last `animation_steps[-1].end.coords`, and that the next turn seeds from it.
- **Geometry regressions:** RR/Triangle shot spot rim-relative bounds (home & away); no phantom stops with defenders far from the drive; no drive jetting.
- Run: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_rr_triangle_drive_resolution.py tests/test_fb_drive_resolution.py tests/test_fb_geo_helpers.py tests/test_fast_break_rr_triangle_updates.py -q`.
  - Note: `tests/test_fb_drive_resolution.py::test_no_meet_all_defenders_to_basket_spot` is a **pre-existing** failure unrelated to this migration.

---

## 6. Risks & sequencing notes

- **Drive-onset vs origin coord (Phase 1) — resolved.** The RR drive starts at the lane-pass catch point, not end-of-DREB, so `bh_start` seeds from `rim_runner_burst_phase.rr_to` (the emitter's catch target), not `player.coords`/`off_starts`. Residual: on a lead pass the rendered step-end can fall slightly short of `rr_to` at the pass meet point (see Phase 1 known residual); a single shared catch-point source is deferred.
- **Do Phases 1–2 before removing the animator packet (Phase 3+).** The packet currently backstops legacy rendering and `final_coords` fallback; removing inputs first, artifacts later, keeps rollbacks cheap.
- **Flag-gated rollout:** keep changes reversible via the existing `USE_FB_DRIVE_RESOLUTION_*` flags until Phase 4.
- **CR & After-Steal are already UESS-compliant** for coord sourcing; beyond the Phase 5 observability items, they now also share the universal `build_fb_drive_resolution_steps` helper (see "Post-Phase 5"), which brought their finish drives to parity with RR/Triangle (finisher pace, `t_drive` floor, crash-to-basket, named "Nice stop").
