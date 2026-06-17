# Dynamic HCT — Cut 2 Build Plan

Companion to `Dynamic_HCT_Turns.md` (the spec) and its §11 list. Cut 1 (setup →
converge → single DEAD BALL | HCO outcome, BH = PG) is built and conformant. Cut 2
builds the **full §4 loop**. Build in testable phases.

## Architecture change (foundation for the whole loop)

- **Engine** (`engine/dynamic_hct.py`): `compute_dynamic_hct_turn` returns a
  **variable-length `segments` list** produced by an internal loop, instead of fixed
  `converge`/`attack` fields.
- **Emitter** (`engine/dynamic_hct_step_emitter.py`): consume `segments` generically
  (one schema step per segment) instead of the hardcoded 3-step builder.
- **Wrapper** (`phase_resolution._resolve_half_court_trap_dynamic_first_cut`): pass the
  `segments` payload through to the emitter; keep result/possession/next-play wiring.

## Phase 2A — Loop spine  ✅ DONE

- Refactor engine → `segments` loop; refactor emitter → N generic steps. Preserve the
  Cut 1 visual (walk-up → converge → attack) for the first-iteration terminal case.
- Adopt the **§5 banded contested formula** with three outcomes: DEAD BALL / HCO /
  **neutral**.
- **Neutral-advance iterations**: on neutral, BH advances `rand(6,12)` x toward basket,
  `rand(-6,6)` y; PG defender re-poses; loop re-evaluates.
- **Zone precedence** at top of each iteration: BH in PSA → HCO terminal.
  (Attack-Basket → §7 deferred to 2D; until then, x past the PSA also resolves HCO.)
- **Time terminals** each iteration: `shot_clock ≤ 0` → shot-clock violation;
  `shot_clock ≤ 20` and ball not past half court → 10-second violation. Decrement the
  running shot clock per segment. Defensive iteration cap as a backstop.
- **Reads** (`read(BH)` → attack/pass/hold): wired; **attack** fully resolved this
  phase. **pass** and **hold** temporarily route to neutral-advance (placeholders,
  replaced in 2B/2C).
- Apply universal clamps (`clamp_animation_grid_coords`) to every per-player target.

## Phase 2B — Moment resolutions (§5)  ✅ DONE

- Real detection: none / pressure (1 def ≤11 ahead) / trap (≥2 ≤11, ≥1 ahead). Done
  via `_detect_moment` + nearest-first in-range list.
- Trap selection rule (PG + closest; two-closest fallback) → `_select_trappers`.
- Shift-based defensive formation reusing `compute_hct_trap_formation` (upper → PG+SG,
  lower → PG+SF) plus the center defender → `_position_defense`.
- Pressure vs Trap banded resolution (`_resolve_moment`; trap adds 0.5× trapper
  pressure) + broken-HCT reduced read thresholds (`_read_decision(broken=…)`).
- **hold** resolution (time-boxed `random(1,3)s`; re-detect → trap moment / broken-HCT /
  pressure-return-to-loop). Hold uses a `fixed_duration` gate.
- Steal/foul outcomes inside moments are **stubbed** (D8): pressure-no-steal returns to
  the loop; only the non-steal outcomes (o-win advance, neutral, DEAD BALL) are wired.

  Deferred from 2B by design: broken-HCT topLane **fast break** (→ 2D, D18); full
  non-trapping defender + teammate re-pose every segment (→ 2F, D15).

## Phase 2C — Pass branch + movement (§6) + D19  ✅ DONE (movement simplified)

- Pass mechanic: receiver = one of the two teammates closest to the BH (random of the
  two) → `_select_pass_receiver`. Ball flight rendered via the universal
  `build_pass_step` (BallInFlight → BallAttached, `ball_reaches_player` gate, SFX),
  then a reception/hold beat; the **receiver becomes the new ball handler** and the
  loop continues from him.
- Per-segment **ball ownership** (`ball_owner_pos` on every segment; emitter sets the
  ball owner + nearest-defender `guard_ball` per segment).
- **D19** — pass-defense formation computed **once** (around the receiver) and persisted
  across the flight + reception segments (no re-randomized jitter).
- **D7** — the HCT-end BH can now be a non-PG. `_maybe_stamp_hco_setup` early-returns for
  `current_turn == "HCT"`, so the PG override is suppressed and the HCO orchestrator uses
  the skeleton-derived step-0 initiator; `final_ball_handler_id` (universal) carries the
  real HCT-end BH.

  Simplified vs. spec (flagged refinement): the exact §6 **Vertical-Half / Central**
  per-player offense choreography is approximated — offense holds spacing and the defense
  re-forms on the receiver via the tested `_position_defense`. The detailed per-player
  pass-movement spot assignments are a follow-up. Stat attribution of a post-pass
  turnover to the receiver is deferred to D8/D16.

## Phase 2D — Goal achievement (§7)

Built as vertical slices because this is the first HCT path that produces a
**real shot** (make/miss + scoring + rebound + possession + post-shot animation).

### 2D-1 — broken-HCT **fast break** (D18)  ✅ DONE

- **Engine** (`dynamic_hct.py`): the §5 broken-HCT open-floor attack now branches
  on `_psa_is_behind` — perfect-PSA-spot ahead → drive there → HCO (unchanged);
  PSA behind → drive to the **topLane** spot → `result_type = "FAST_BREAK_SHOT"`
  with a `fb_seed` (shooter pos + post-drive off/def coords).
- **Resolver** (new `engine/dynamic_hct_shot.py::resolve_hct_fast_break_shot`):
  Steal-FB-equivalent rim attempt. Reuses `compute_fb_shot_geometry` with a
  **single rim protector** (the defender closest to the basket — per the D18
  reuse note, not all five) + `ShotManager.calculate_shot_score`. Produces a full
  MAKE/MISS shot turn_result (scoring via `apply_scoring`, rebound chain via
  `determine_rebounder`, defensive-foul → FT, possession flip, `next_play_type`,
  shot variant/SFX) mirroring `after_steal_fast_break`.
- **Wrapper** (`phase_resolution`): `FAST_BREAK_SHOT` → call the resolver, merge
  with the HCT loop intermediate data (`_assemble_hct_fb_shot_result`); HCT
  scouting parity via `_record_hct_stats`.
- **Emitter** (`dynamic_hct_step_emitter`): loop segments stay non-terminal; the
  **drive step** (shooter `shoot` motion → rim target, lone rim protector to his
  contest spot) + shared `_build_post_shot_sub_steps` (ball-flight / variant /
  hold-or-bounce) are appended. Terminal = `SHOT_ATTEMPT` turn_stop.
- **Clock** (`turn_manager`): MAKE/MISS/BLOCK HCT turns realign `time_elapsed` to
  the schema game-clock burn (mirrors the FCP realignment) so the
  ball-flight/bounce sub-steps are counted.
- Verified with an offline smoke test (engine branch, geometry, resolver
  MAKE+MISS, drive step, post-shot append, full walk-up→loop→drive→post-shot
  chain). 

  > ⚠️ **Reachability dependency:** the broken-HCT (`moment == "none"`) branch
  > rarely fires today because `_position_defense` re-converges the PG onto the
  > BH every segment, so a defender is almost always "ahead in range." D18 is
  > wired and tested but won't trigger in normal play until **step-N defender
  > movement (D15, Phase 2F)** lets the offense actually beat the trap.

### 2D-2 — in-Attack-Basket shot-attempt tree  ⏳ TODO

- Shot-attempt decision tree (D4): shoot / drive / pass; drive targets; inside spots.
- Rim-protection cluster (D5); shot-defender pick at shot moment (D6).

### 2D-3 — top-level pass  ⏳ TODO

- Top-level pass to a teammate past x=64 + receiver actions (attack / Kick-Out→HCO /
  re-enter loop).

## Phase 2E — HCO entry polish

- Handoff/Kickout selector via the Attack-Basket test (entry **step type** only;
  receiver = skeleton-derived initiator).

## Phase 2F — Violations + remaining movement + stats

- 10-second-violation runtime wiring (D9).
- Step-N movement for the other defenders / teammates, not just the PG defender (D15).
- Stats parity vs. the skeleton path (D16).

## Deferred (not in Cut 2, per design owner)

- Fouls / steals / dead-ball-turnover emergent outcomes (D8).
- Mid-flight pass interception (D11).
- Per-tick energy decay (D12), seeded RNG/determinism (D13), distant-sim
  short-circuit (D14).
