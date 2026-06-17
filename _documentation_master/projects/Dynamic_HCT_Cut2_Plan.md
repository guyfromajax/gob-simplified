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

### 2D-2 — in-Attack-Basket shot-attempt tree

Built as sub-slices (shoot → drive → pass), starting with the most common outcome.

#### 2D-2a — Attack-Basket fork + shoot-in-place  ✅ DONE

- **Engine** (`dynamic_hct.py`): split the zone-precedence check — PSA → HCO
  (unchanged); `_in_attack_basket_area` (past PSA AND y 10-30) → §7 goal
  achievement; past-PSA-but-off-band → HCO (a 2D-3 "re-enter loop" item).
  §7 fork: `_count_in_attack_basket` offense/defense; `defenders>offenders` →
  HCO is optimal (ties → attack); a goal-achievement read (`>200` → optimal,
  else random) picks HCO vs. shot. Shot → `result_type="ATTACK_BASKET_SHOT"`
  + `ab_seed` (shooter pos + off/def coords). Drive / top-level-pass options
  are deferred to 2D-2b / 2D-2c (this slice always shoots in place).
- **Resolver** (`dynamic_hct_shot.py::resolve_hct_attack_basket_shot`): **D5**
  rim-protection collapse (each defender interrupted toward the x∈[77,87],
  y∈[19,31] band at standard pace over the shot beat) + **D6** shot-defender
  pick (nearest defender ending within 4x/6y of the shooter). Contested →
  `calculate_shot_score(apply_defense=True)`, uncontested → `apply_defense=False`;
  **made = shot_score ≥ threshold either way (no auto-make — half-court shots
  are rolled, unlike the FB layup rule)**. Full MAKE/MISS turn (scoring /
  rebound / defensive-foul-FT / possession / `next_play_type`), `shot_type`
  inside/outside by distance-to-rim. Emits `hct_ab_*` seed for the emitter.
- **Wrapper** (`phase_resolution`): `ATTACK_BASKET_SHOT` → resolver →
  `_assemble_hct_ab_shot_result` (sibling of the FB assembler).
- **Emitter** (`dynamic_hct_step_emitter`): loop segments stay non-terminal;
  `_build_ab_shot_step` (shooter `shoot` in place, defenders to their D5
  release coords, `fixed_duration` gate) + shared `_build_post_shot_sub_steps`.
- **Clock** (`turn_manager`): already realigns MAKE/MISS/BLOCK HCT turns
  generically (added in 2D-1) — no change needed.
- Verified with an offline smoke test (zone helpers, D5/D6 geometry, contested
  make + uncontested miss, full walk-up→loop→shot→post-shot emitter chain).

  > Reachability: reached when the BH advances past x=64 at a y outside the PSA
  > band (≈ y 10-18). Unlike D18 this fires in normal play (the neutral advance
  > jitters y by ±6), though a central advance hits the PSA → HCO first.

#### 2D-2b — drive + drive→dish  ✅ DONE

- **Engine**: the AB "attack" leaf now runs the §7 shoot/drive/pass tree
  (`_choose_shot_attempt`): optimal = SH>80 shoot / SC+AG>105 drive / else pass,
  gated by a read (>200 optimal, else random over the three); no defender in
  range → always drive. shoot→`ATTACK_BASKET_SHOT` (2D-2a); drive→
  `ATTACK_BASKET_DRIVE`; pass (top-level, 2D-2c) falls back to the offense-optimal
  of {drive, shoot} until 2D-2c lands.
- **Resolver** (`resolve_hct_attack_basket_drive`): driver drives to a rim target
  by starting y (y>30 upper lowPost / y<20 lower lowPost / else basketSpot);
  x>64 teammates relocate to distinct inside spots (upper/lower half by their y,
  midLane central, no shared spot). If ≥1 inside teammate → 50/50 finish-vs-dish;
  dish → closest-to-basket inside teammate shoots an **inside** shot, else the
  driver shoots an **attack** shot at the rim. Shared D5 collapse + D6 pick +
  shot roll + make/miss tail were **refactored out** of the 2D-2a resolver into
  `_collapse_defenders_and_pick` / `_roll_ab_shot` / `_finalize_ab_shot` (reused
  by both).
- **Wrapper**: routes both `ATTACK_BASKET_SHOT` and `ATTACK_BASKET_DRIVE`.
- **Emitter**: `_build_ab_drive_step` (driver sprints to rim, teammates cut to
  inside spots, defenders collapse). No-dish → driver ends in shot motion → post-
  shot. Dish → drive step (driver `handle_ball`) + `build_pass_step` (driver→
  receiver) + `_build_ab_shot_step` (receiver shoots in place) + post-shot.
- Verified offline (shoot/drive/pass decision incl. no-defender + random gate;
  drive make + drive→dish miss/rebound; drive target by y; emitter chains for
  drive and drive→dish with monotonic clocks) and 2D-2a regression re-checked.

#### 2D-2c — top-level pass  ✅ DONE

- **Engine**: the §7 "pass" leaf now emits a real top-level pass.
  `_select_top_level_pass_receiver` — pool = teammates past x=64; default = the
  closest to the BH; open-rim override = a teammate within 9 of the basket with
  no defender within 9 (random among qualifiers). The pass reuses the proven §6
  primitives (`_position_defense` D19 formation + `_pass_segment`), then the
  receiver becomes the new BH. **Receiver post-catch resolution:**
  - Catches inside the Attack Basket Area → AB offender/defender count:
    `defenders ≤ offenders` → **attack** via the D18 fast-break bridge
    (`_seed_fast_break` → `FAST_BREAK_SHOT`); `defenders > offenders` → **HCO**
    (Kick-Out entry, since the receiver is inside the AB area).
  - Catches past x=64 but outside the AB y-band → receiver re-enters the loop
    (settles to HCO today; full detect→read re-entry is the 2D-3 item).
  - No teammate past x=64 → falls back to the offense-optimal solo finish.
- The forward-only candidate pool means the over-and-back guard is satisfied by
  construction. No resolver/emitter changes — both branches reuse existing
  paths (`FAST_BREAK_SHOT` → the D18 resolver/emitter; `HCO` → the HCO entry
  orchestrator's kickout step).
- Verified offline (receiver selection incl. open-rim + away orientation;
  pass→FAST_BREAK, pass→HCO, pass→off-band, each emitting the pass segment).

**2D-2 in-Attack-Basket shot tree is complete (shoot / drive / drive→dish / pass).**

### 2D-3 — top-level pass  ⏳ TODO

- Top-level pass to a teammate past x=64 + receiver actions (attack / Kick-Out→HCO /
  re-enter loop).

## Phase 2E — HCO entry polish

- Handoff/Kickout selector via the Attack-Basket test (entry **step type** only;
  receiver = skeleton-derived initiator).

## Phase 2F — Violations + remaining movement + stats

- 10-second-violation runtime wiring (D9).
- Step-N movement for the other defenders / teammates, not just the PG defender (D15).
  - ✅ *Render:* `_build_loop_step` clamps every mover to its archetype rate via the interrupted-coord pattern (`start + rate × T`) and carries the result forward, so off-ball offense progress toward setup at sprint across loop steps instead of being snapped to the full target each segment (fixes the off-ball "jet"). Off-ball offense use the `sprint` archetype; BH/defenders use `standard`. This is also a universal "no one exceeds their archetype rate within a step" safety net.
  - ✅ **DONE (engine model — defender side):** `_defense_targets` (pure §6 target computation) + `_move_defense` (interrupted, position-tracking, per-defender `standard` AG rate via `_interrupted_coord`) replace the per-segment snap in the **advance / hold / broken-HCT-drive** segments. A quicker BH now gains real separation → the chasing defender trails (not "ahead") → `_detect_moment == "none"` → broken-HCT/D18 reachable in normal play (verified via offline checks). Converge + pass-defense formation still snap by design.
  - ✅ **DONE (engine model — offense side, D15b):** `_walk_up_loop_start_offense` seeds loop-start off-ball coords by replaying the BH-gated walk-up (off-ball at `sprint`, interrupted; reads the prior turn's `final_coords`, mirrors `build_walk_up_step`); `_move_offense` advances them toward setup each time-advancing segment (converge / advance / hold / broken-HCT drive / pass flight / reception), excluding the BH + any mid-catch receiver. The Attack-Basket count (`_count_in_attack_basket`) and pass-targeting (`_select_pass_receiver`, `_select_top_level_pass_receiver`) now read real lagging coords (verified). Falls back to "arrived at setup" with no prior-turn coords. Engine + render stay aligned (emitter consumes the engine's tracked coords; its interrupted clamp is now a no-op safety net).
- Stats parity vs. the skeleton path (D16).

## Deferred (not in Cut 2, per design owner)

- Fouls / steals / dead-ball-turnover emergent outcomes (D8).
- Mid-flight pass interception (D11).
- Per-tick energy decay (D12), seeded RNG/determinism (D13), distant-sim
  short-circuit (D14).
