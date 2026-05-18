# Animation System Updated

> **Status:** Schema **locked**. Migration in progress. Started 2026-05-09; last major update 2026-05-17.
>
> **Migration progress (high level):**
> - ✅ **Covert Release Fast Break** — fully migrated; schema-driven via `covert_release_step_emitter.py`. Frontend routes through `playAnimationStep`.
> - ✅ **DREB** — promoted to its own turn type; `dreb_step_emitter.py` shipped.
> - ✅ **Rim Runner Fast Break** — schema-driven via `rim_runner_step_emitter.py`. All 5 branches (Shot / STEAL / Bat OOB / Hold-up / Outlet Denied) emit `animation_steps`. Reusable `_build_burst_step` + `_build_outlet_pass_step` builders factored for Triangle's upcoming migration. Frontend routes through `playAnimationStep` when present.
> - 🟡 **HCO / HCT** — schema emitters exist (`skeleton_step_emitter.py`, `hct_step_emitter.py`) and emit `animation_steps`; frontend routes them through `playAnimationStep` when present. Some legacy paths still fire when emitters return None for missing skeleton/animations.
> - ⏳ **Triangle FB, FCP, Free Throw, BIP/SIP, OREB, Opening Tip, Timeout** — still on legacy frontend animation paths.
>
> **Context:** This doc proposes the unified per-step payload schema, validates it against every turn type, and tracks the per-turn-type migration as each emitter lands. It succeeds an earlier scoping doc (`Animation_System_Refactor.md`, since removed) that inventoried turn types and surfaced inconsistencies — the inventory has been folded into the schema validation below.
>
> **Architecture commitment:** advance trigger lives on the backend. Backend pre-computes `T = game-seconds when trigger fires`, then derives all end-state fields (interrupted coords, ball state, clock advance) from T. Frontend is a pure playback engine. Game-time and wall-time stay 1:1 synced: `tickMs = 350` (1 game-sec = 350 ms wall-clock), no per-step cap in the schema engine, so backend-authored T directly drives both clock burn and animation duration.

---

## Proposed schema

Each animation step has a **start state**, an **advance trigger**, and a **derived end state**. Canonical source: [`BackEnd/utils/animation_step_schema.py`](../../BackEnd/utils/animation_step_schema.py) (with JSDoc mirror at [`FrontEnd/static/js/phaser/animation/animationStepSchema.js`](../../FrontEnd/static/js/phaser/animation/animationStepSchema.js)). Keep the two in lockstep when the schema evolves.

### Start of step (`StepStart`)

**Required fields:**
- `coords` — `{[player_id]: {x, y}}` for all players on court
- `destination` — `{[player_id]: {x, y} | null}` (null = stationary)
- `action` — `{[player_id]: <closed vocab>}`. Current vocab: `handle_ball`, `pass`, `receive`, `cut`, `screen`, `shoot`, `stationary`, `sprint`, `guard_ball`, `guard_offball`, `post_up`. May extend during further turn-type audits.
- `archetype` — `{[player_id]: <closed vocab>}` (`default`, `sprint`, `drive`, `shot_motion`, `cruise`, `stationary`) — drives per-player rate via the AG curve
- `ball` — one of:
  - `BallAttached`: `{owner_player_id}`
  - `BallInFlight`: `{from_player_id, to_player_id, current_coords}`
  - `BallLoose`: `{coords}` (no owner; e.g., DREB step start, batted-OOB step end)
- `clock` — `{clock_remaining, shot_clock_remaining}` (game-seconds)
- `advance_trigger` — `{condition, T_game_seconds, metadata}` — condition is the closed-vocab trigger type (e.g. `player_reaches_position`, `ball_reaches_player`, `fixed_duration`, `shot_resolved`, `stopper_action`), `T_game_seconds` is the precomputed step duration, and `metadata` carries condition-specific extras (e.g. `target_player_id`, `target_coords`, `contact_coords`, `outlet_score`).

**Optional fields:**
- `announcement` — `Announcement` payload. When present, playback engine pauses clocks, shows the announcement, awaits `hold_ms`, then resumes clocks **BEFORE** the step's tweens fire. Used for entry-of-turn announcements like `"Fast Break!"` / `"No Fast Break"` / `"Trap!"`. Carries `{text, team, player_data?, meta?, hold_ms, style}` where `style ∈ {"primary", "secondary"}` routes to the correct banner renderer.
- `tween_durations` — `{[player_id]: game_seconds}`. Per-player tween duration. When present, playback tweens each player for their individual duration; fast finishers idle at their end coord until step T elapses. When absent, playback falls back to step T (which stretches fast finishers' tweens — the "lazy drift" anti-pattern). Backend always stamps when it has per-player rate info; frontend never recomputes.

### End of step (`StepEnd`, derived from start + T)

**Required fields:**
- `coords` — interrupted position per player (formula: along start→destination at distance `rate × T`, or destination if `rate × T ≥ full distance`)
- `ball` — `BallAttached | BallInFlight | BallLoose` at T
- `time_elapsed` — T (game-seconds). Equal to `advance_trigger.T_game_seconds`.
- `clock` — state after T elapses
- `next` — one of:
  - `{kind: "next_step", index}` (linear continuation; an index past the array length terminates the turn implicitly — caller transitions to the next turn)
  - `{kind: "branch", outcome, next_step_index}` (outcome-driven; backend already resolved which branch)
  - `{kind: "turn_stop", event, payload}` (turn ends — see event types below)

**Optional fields:**
- `announcement` — same shape as `StepStart.announcement`. When present, playback snaps sprites to end coords, pauses clocks, shows the announcement, awaits `hold_ms`, then resumes clocks **BEFORE** returning `next`. Used for mid-turn announcements like `"Nice Stop!"` / `"Interception!"` / `"FB Outlet Pass Denied!"` that play after a movement beat completes.

### Turn-stopping event types

Closed vocab: `SHOT_ATTEMPT`, `FOUL` (variants: `O_FOUL`/`D_FOUL`/`charge`/`blocking`/`shooting`), `STEAL`, `DEAD_BALL_TURNOVER`, `SHOT_CLOCK_EXPIRED`, `GAME_CLOCK_EXPIRED`, `TIMEOUT`, `JUMP_BALL`. Confirm completeness during further turn-type audits.

---

## HCO validation

| Schema field | HCO today | Gap |
|---|---|---|
| `coords` (start) | Derivable from prev end / skeleton step 0 | None |
| `destination` | `pos_actions[pos].location` → `HCO_STRING_SPOTS` | None |
| `action` | `pos_actions[pos].action` | Vocabulary already aligned |
| `archetype` | Implicit (`shoot` step → shot_motion, others → default/cruise) | **Needs to become explicit per player per step** |
| `ball` | Implicit (player whose action is `handle_ball` / `pass` / etc.) | **Needs explicit field** |
| `clock` | Turn-level (`step_clock_seconds[i]` parallel array) | **Needs to be on the step itself** |
| `advance_trigger` | Time-based: step ends after `step_clock_seconds[i]` seconds | **Schema must support time-based trigger as a first-class variant** (`condition: "fixed_duration"`, `T = step_clock_seconds[i]`) |
| `coords` (end) | Destination = end (HCO is paced — all players reach destination at T) | Schema's degenerate case (`rate × T ≥ full distance` for everyone) |
| `next` | Implicit `i + 1`; events lead to `turn_stop` | Maps cleanly |

**Verdict (historical):** HCO fits with three concrete upgrades — explicit per-player archetype, explicit ball state, per-step clock + trigger fields. **Status: implemented** in `skeleton_step_emitter.py`. Schema steps emit alongside legacy `animations[]`; frontend takes the new engine when `animation_steps` is present, falls back to legacy otherwise.

---

## Fast Break validation

| Schema field | FB today | Gap |
|---|---|---|
| `coords` (start) | Scattered across `animations[i].movement[0]`, `roles.rim_runner_burst_phase.rr_from`, `roles.ball_handler_outlet_x/y` | **No canonical step-start coords** |
| `destination` | Scattered across `animations[i].end`, `phase.rr_to`, `phase.receiver_to`, `phase.outlet_defender_to`, `phase.other_players[]` | **No canonical destination field** |
| `action` | Implicit in role assignment (ball_handler, outlet_receiver, rim_runner, etc.) | **Action vocabulary for FB needs definition** (sprint to rim, outlet receive, cover ground, contest pass, etc.) |
| `archetype` | Hardcoded per call site (frontend `getPlayerDuration` + `burst=true` flag) | **Per-player archetype per step needs backend stamping** |
| `ball` | Tracked via roles + `BallController` ownership flips | Already exists in concept; needs to be in step-payload form |
| `clock` | Turn-level only | **Per-step needs adding** |
| `advance_trigger` | Event-based, frontend-detected (Promise resolution on tween completion / pass arrival) | **Needs to move to backend with computed T** |
| `coords` (end) | Partially in `animations[i].end` (assumes player reaches destination); interrupted coords don't exist as data | **Interrupted-coord math doesn't exist today** — backend must compute |
| `next` | Implicit phase transitions in `fastBreak.js` (`if/else` chains, `phase2Kind` routing) | **Needs explicit branching in payload** (outlet_denied / not, intercept tier, MAKE / MISS / BLOCK, etc.) |

**Verdict (historical):** FB doesn't naturally fit. Restructuring is required. Concretely, "phases" in `fastBreak.js` need to be replaced by discrete backend-emitted steps with computed triggers and pre-computed interrupted coords. **Status: implemented for Covert Release** in `covert_release_step_emitter.py` (2-step or 3-step depending on outcome). RR / Triangle / After-Steal variants still on legacy `fastBreak.js`. See "Covert Release FB emitter — scoping" below.

### FB step shape (sketch — for one Rim Runner outcome)

| # | Step | Trigger | Stops if |
|---|---|---|---|
| 1 | Burst | Receiver reaches receive position | (always continues) |
| 2 | Outlet pass | Ball reaches receiver | Pass intercepted → `STEAL` turn_stop |
| 3 | Lane pass | Ball reaches RR catch position | Bat OOB → `DEAD_BALL_TURNOVER` turn_stop |
| 4 | Shot motion | Shooter reaches shot spot | (always continues to shot resolution) |
| 5 | Shot resolution | Shot result computed | `SHOT_ATTEMPT` turn_stop with MAKE/MISS/BLOCK |

(Outlet-denied path replaces steps 2–5 with a single step ending in `DEFENSIVE_STOP` turn_stop.)

---

## What the validation reveals

1. **Trigger types must be heterogeneous.** HCO uses time-based ("fixed_duration"). FB uses event-based ("ball_reaches_player", "shooter_reaches_spot", "shot_resolved"). Schema's `advance_trigger.condition` is metadata — backend computes `T` regardless of condition type.

2. **Step granularity is per-turn-type.** HCO step ≈ one position transition (~300 ms game-seconds). FB step ≈ one phase (~1.5–3 game-seconds). Both fit the same schema; granularity is a turn-type implementation detail, not a schema concern.

3. **Branching belongs in `next`, not in frontend code.** Today FB has frontend `if/else` chains for outlet-denied vs intercept-tier vs etc. In the new system, backend resolves the branch and emits `next: {kind: "branch", ...}` or `next: {kind: "next_step", ...}` directly.

4. **Backend ownership of timing math is non-negotiable.** Once trigger T is computed, every end-state field follows mechanically. This is what makes the system simple — no per-turn-type rendering logic on the frontend.

5. **Per-player archetype is the cleanest extension point.** HCO needs it added; FB needs it added. Once it's a first-class field, any future archetype (e.g., `clutch_sprint`, `injured_hobble`) plugs in without schema changes.

---

## Validation against remaining turn types

### HCT / FCP
Same payload shape as HCO (`skeleton`, `step_clock_seconds[]`, `animations[]`, `roles{}`, `time_elapsed`). Outcomes: shot, foul, steal, dead-ball turnover, transition to HCO.
**Gaps:** identical to HCO — needs explicit per-player archetype, explicit ball state, per-step clock + trigger.
**Verdict:** fits, same upgrades.

### BIP / SIP (Baseline / Side Inbound)
Setup-only turns: players move to inbound positions, then a pass. Today: `result_type = "BASELINE_INBOUND" / "SIDE_INBOUND"`, `next_defensive_setup` (`FCP` / `HCT` / null → HCO), per-player setup positions from `FCP_SETUP_POSITIONS` / `HCT_SETUP_POSITIONS` / HCO equivalents.
**Gaps:** archetype (likely `cruise` or `default`), explicit ball state during/after pass, per-step clock + trigger. Today the "step" concept is implicit — frontend renders setup as one tween + pass as another.
**Verdict:** fits as **2 steps** — (1) setup positioning, (2) inbound pass.

### Free Throw
Multi-attempt structure. Each attempt = shooter at FT line, lane positions for box-out, shot resolution. `attempts[]` array carries per-attempt results. Backend builds animation via `capture_free_throw_animation`.
**Gaps:** archetype (`stationary` for everyone except shooter; `shot_motion` for shooter), trigger per attempt = `shot_resolved`. Action vocab may need `box_out` (or absorb into `guard_offball`).
**Verdict:** fits as **N+1 steps** per turn — one step per attempt + one step for the post-attempt rebound (when applicable).

### OREB (Putback)
Separate turn appended after a MISS. Outcomes: `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`. One putback shot animation.
**Gaps:** archetype (`shot_motion` for putback), trigger = `shot_resolved`. Kickout variant routes ball to perimeter — needs a different action (`pass` after rebound).
**Verdict:** fits as **1–2 steps** — (1) putback shot, OR (1) rebound→kickout pass + (2) shot from receiver.

### Opening Tip
`animations[]` with start/end/action (`CONVERGE_ON_BALL`), `ball_landing_coords`, `home_wins`, `winner`. Tip is jump ball resolved by backend dice; players converge on ball.
**Gaps:** action vocab needs jump-ball variant (or absorb into `cut`/`sprint`); archetype (`cruise`/`sprint`); trigger = backend-rolled outcome (similar to `stopper_action`).
**Verdict:** fits as **1–2 steps** — (1) jump (backend resolves winner), (2) converge to start positions.

### Timeout
Almost no payload — `result_type = "TIMEOUT"`, duration. No sprite movement.
**Gaps:** doesn't need the schema's movement machinery. Could be expressed as a 1-step "no-op" turn with action `stationary` for everyone and a fixed_duration trigger.
**Verdict:** fits trivially. Edge case — most schema fields are no-ops.

---

## Cross-cut observations from validation

1. **The schema fits all turn types** with consistent upgrades (per-player archetype, explicit ball state, per-step clock + trigger). No fundamental shape changes required.
2. **Step granularity varies meaningfully**:
   - HCO/HCT/FCP: ~1 step per skeleton sub-action (~300 ms each, ~5–20 steps per turn)
   - FB: ~5 steps per turn (sketched above)
   - BIP/SIP: 2 steps per turn
   - FT: N+1 steps per turn (variable by attempts)
   - OREB: 1–2 steps per turn
   - Opening Tip: 1–2 steps per turn
   - Timeout: 1 step (no-op)
3. **Action vocabulary may need 1–2 additions** during implementation (jump-ball variant, possibly `box_out` for FT). Working list is close to complete.
4. **Trigger vocabulary covers all observed cases**. `fixed_duration` for HCO/Timeout/Opening-Tip-converge; `ball_reaches_player` for FB pass arrival; `player_reaches_position` for FB sprint targets; `shot_resolved` for FT/OREB/FB shot phases; `stopper_action` for foul/steal/turnover events.

---

## HCT emitter — scoping

**Status:** Implemented in `BackEnd/engine/hct_step_emitter.py`. Frontend routes HCT turns with `animation_steps` through `playAnimationStep`. Coverage gaps where the emitter returns None still fall back to legacy.

Below: the concrete mapping from existing HCT data sources (`dynamic_hct.py`, `phase_resolution.py` HCT branch) to the schema's `AnimationStep[]` shape.

### Step decomposition (4 schema steps)

| # | Step | Description |
|---|---|---|
| 0 | **Setup** | Players move from BIP positions to HCT step-0 positions (`HCT_SETUP_POSITIONS`). |
| 1 | **BH advance** | BH dribbles toward half-court; non-BH offense + defenders take their step-1 positions. |
| 2 | **PG converge** | PG defender converges on BH at the engagement spot. Other players continue tracking. |
| 3 | **Outcome** | BH resolves to one of: shot, drive, pass-out, foul, steal, dead-ball turnover, transition to HCO. |

### Per-step trigger + linear next pointer

| # | Trigger condition | Next |
|---|---|---|
| 0 | `fixed_duration` (T = step_clock_seconds[0]) | `next_step(1)` |
| 1 | `fixed_duration` (T = step_clock_seconds[1]) | `next_step(2)` |
| 2 | `fixed_duration` (T = step_clock_seconds[2]) | `next_step(3)` |
| 3 | `fixed_duration` (T = step_clock_seconds[3]) | depends on outcome (table below) |

### Step 3 outcome → next pointer

Step 3 is where HCT branches. Backend pre-resolves which outcome and emits the corresponding next pointer.

| HCT outcome | Step 3 `next` | Notes |
|---|---|---|
| Shot (MAKE / MISS / BLOCK) | `turn_stop: SHOT_ATTEMPT` | Payload: `{result, shooter_id, defender_id, ball_bounce_coords?}`. Handler renders shot arc + ball-on-rim + outcome marker. **Rebound is NOT in this handler** — it's a separate turn (DREB or OREB) that the caller transitions to next. |
| Defensive shooting foul | `turn_stop: FOUL` | Payload: `{foul_type: "shooting", fouler_id, victim_id}`. Handler runs FT setup. |
| Non-shooting foul (D or O) | `turn_stop: FOUL` | Payload: `{foul_type: "non_shooting", ...}`. Handler runs SIP setup. |
| Steal | `turn_stop: STEAL` | Payload: `{stealer_id, victim_id}`. Handler runs steal visual; next turn may be FAST_BREAK. |
| Dead-ball turnover | `turn_stop: DEAD_BALL_TURNOVER` | Payload: `{victim_id}`. Handler runs SIP setup. |
| Shot-clock expired | `turn_stop: SHOT_CLOCK_EXPIRED` | Payload: `{}`. Handler runs SIP setup. |
| Continue to HCO | `next_step` past array (implicit end) | No turn_stop. Steps 0–3 complete naturally; HCO is the next turn. |

### Per-player archetype mapping

Lifted from Movement Rate Refactor decisions, made explicit per step:

| Step | BH | Non-BH offense | PG defender (vs BH) | Other defenders |
|---|---|---|---|---|
| 0 (setup) | `cruise` | `cruise` | `cruise` | `cruise` |
| 1 (BH advance) | `cruise` (BH random rate) | `cruise` (baseline rate) | `cruise` | `cruise` |
| 2 (PG converge) | `default` | `default` | `default` (AG-driven, was COF=16) | `default` |
| 3 (outcome) | `drive` (all outcomes) | `default` | `default` | `default` |

### Per-player action mapping

Existing skeleton actions for HCT map directly to schema vocab. No HCO-specific terms (`post_up`, `get_open`) appear in HCT — those are handled in HCO migration.

| Existing skeleton action | Schema action |
|---|---|
| `handle_ball` | `handle_ball` |
| `pass` | `pass` |
| `receive` | `receive` |
| `cut` | `cut` |
| `screen` | `screen` |
| `shoot` | `shoot` |
| `stationary` | `stationary` |
| (defenders) `guard_ball` | `guard_ball` |
| (defenders) `guard_offball` | `guard_offball` |

### Ball-state continuity rule

The schema requires `step.start.ball` at step N to match the rendered ball state at end of step N−1. The emitter enforces this:

- If a player's action at end of step N is `receive`, that player's action at start of step N+1 defaults to `handle_ball`. Implicit handoff.
- A `pass` action at step N transfers ball ownership to the receiver at step N's end.
- Ball ownership transitions during a step (e.g., a pass) are reflected in `step.end.ball` (the new owner) vs `step.start.ball` (the old owner).

The emitter walks the skeleton and maintains a running ball-owner pointer; each step's `start.ball` and `end.ball` are derived from that walk.

### Resolved scoping items

- Implicit end of turn for "continue to HCO" — no turn_stop event; `playTurn` returns `null`.
- Step 3 BH archetype is `drive` for all outcomes (drive / shoot / pass).
- **HCT shot drops get-back / release mechanics.** HCT is treated like Fast Break — no offense_getback or defense_release computed when the shot fires. Backend change in `shot_manager.py:resolve_shot()` to gate the get-back/release blocks on `is_hct == False`. (FB and FCP get the same treatment when their migrations land; for now we only do HCT.)
- **HCT MISS rebound prefilter** = frontcourt-half x-eligibility (home offense → x ≥ 50, away offense → x ≤ 50). Same as FB's existing prefilter. See [`Rebound_System.md`](../05_GP_Supporting_Systems/Rebound_System.md) "Rebounder selection per turn type" grid.
- **DREB promoted to its own turn type** (parallel to OREB). The HCT MISS turn ends with `SHOT_ATTEMPT`; the DREB turn is the next turn. This affects:
  - **Animation system:** SHOT_ATTEMPT handler is much simpler (shot arc + ball-on-rim only, no rebound logic). DREB runs through the uniform step-based engine.
  - **Backend turn flow:** `turn_manager.py` / `phase_resolution.py` need to emit DREB as a discrete turn after a missed shot, instead of bundling rebounderId into the MISS turn payload. This is real refactor work, scoped into the HCT migration.
  - **Existing OREB turn pattern is the template** — DREB is symmetric (same rebound-capture choreography; different post-rebound outcome — possession flip vs. putback opportunity).
- **Schema needs a `BallLoose` variant** — ball at rest at coords with no owner. Used for DREB step start (ball sits at bounce coords waiting for the rebounder). Today's schema only has `BallAttached` and `BallInFlight`. Adding a third variant with `{coords: GridCoord}`.

---

## DREB emitter — scoping

**Status:** Implemented in `BackEnd/engine/dreb_step_emitter.py`. DREB is promoted to its own turn type; `game_manager._build_dreb_turn_from_miss` ([line 541](../../BackEnd/models/game_manager.py)) emits the DREB turn immediately after any MISS turn whose rebounder is on the defensive team. Frontend routes DREB through `playAnimationStep`.

### Single-placement-authority model

`shot_manager` is the **sole authority** for post-shot player positions. It populates `offense_rebounder_coords`, `defense_rebounder_coords`, `offense_getback_coords`, and `defense_release_coords` on the MISS turn. The MISS turn's emitter absorbs those into its final step's `end.coords`. Sync writes them to `player.coords`.

The DREB turn does **not** re-decide post-shot positions for anyone. It animates only the rebound capture: the rebounder moves from his post-shot position to the bounce coords. Every other player holds the position shot_manager assigned.

This replaces the earlier "two placement authorities racing via player-id matching" design, which was brittle: if a release / get-back player's id happened to also appear (or fail to appear) in any of the four overlay maps, DREB could yank them to the rim cluster on the next sync.

### Step decomposition (1 schema step)

| # | Step | Description |
|---|---|---|
| 0 | **Rebound capture** | Rebounder converges on bounce coords. Every other player is stationary at the position shot_manager assigned them on the MISS turn. Step ends when rebounder reaches the ball. |

### Trigger + next pointer

- **Trigger condition:** `player_reaches_position` with metadata `{target_player_id: rebounderId, target_coords: bounce_coords}`. T = time for rebounder to traverse start coord → bounce coord at sprint rate.
- **Next pointer:**
  - Normal capture (no foul): implicit end (`next_step` past the array → `playTurn` returns `null`). Caller transitions to next turn (HCO or FAST_BREAK based on game state).
  - Over-the-back foul: `turn_stop: FOUL` with payload `{foul_type: "non_shooting", over_the_back: true, fouler_id, victim_id}`. Caller routes to SIP or FREE_THROW (bonus situation).

### Per-player action and archetype

| Player role | Action | Archetype | End coord |
|---|---|---|---|
| Rebounder (picked by `choose_rebounder` upstream) | `cut` | `sprint` | Ball bounce coords |
| All 9 non-rebounders | `stationary` | `stationary` | Their own `start.coords` (= position shot_manager assigned on the MISS turn) |

No frontcourt filter, no random near-bounce spots, no `exempt_player_ids` plumbing.

### Ball state

- **Start:** `BallLoose {coords: bounce_coords}` — ball sits at bounce spot after the previous SHOT_ATTEMPT turn-stop handler animated the ball-on-rim and bounce.
- **End:** `BallAttached {owner_player_id: rebounderId}` — rebounder has secured the ball.

### Coord sources for DREB step start

| Player | Source of start coord |
|---|---|
| All 10 players | `player.coords` (live state, post-MISS-sync). `sync_lineup_coords_from_turn` is the only place that applies the **full** post-shot picture — schema `animation_steps[-1].end.coords` + every overlay map in the correct precedence. The schema's own `end.coords` only reflects overlays the MISS-turn emitter's `_apply_post_shot_overlay` happened to write; if that emitter returned None or didn't cover a player, the schema value is the pre-overlay legacy animation end and is stale relative to `player.coords`. Reading `player.coords` guarantees DREB sees what shot_manager actually decided. |

### Outcome → next pointer mapping

| Outcome | DREB step `next` |
|---|---|
| Clean capture, no foul | `next_step` past array → implicit end. Backend's `next_play_type` (HCO / FAST_BREAK) determines what turn comes after. |
| Over-the-back foul | `turn_stop: FOUL` with `{foul_type: "non_shooting", over_the_back: true, ...}`. |

### Backend turn-flow change

Currently `shot_manager.py` bundles `rebounderId` + `rebound_type` + `ball_bounce_x/y` into the MISS turn payload. After the migration:
- MISS turn payload contains only the shot result (no rebounderId, no rebound_type).
- A new DREB turn is generated immediately after by `game_manager.py` (mirror the existing OREB turn-creation pattern at `game_manager.py:664-694`).
- The DREB turn payload contains the rebounder selection, ball bounce coords, and the steps array.
- DREB turn's `next_play_type` (HCO / FAST_BREAK) is what the existing logic puts on the MISS turn today — it just lives on the DREB turn now.

Files touched (delivered): `shot_manager.py`, `game_manager.py`, `turn_manager.py`, `phase_resolution.py`, plus the new `dreb_step_emitter.py`.

---

## Covert Release FB emitter — scoping

**Status:** First fully-migrated fast-break variant. Implemented in `BackEnd/engine/covert_release_step_emitter.py`. Frontend takes the new engine when `turnData.fast_break_play === "covert_release"` and `turnData.animation_steps` is present ([AnimationEngine.js:302-328](../../FrontEnd/static/js/phaser/animation/AnimationEngine.js)).

### Step decomposition

| # | Step | Trigger | Notes |
|---|---|---|---|
| 0 | **Outlet pass** (skipped when rebounder == receiver) | `ball_reaches_player` | T derived from Euclidean distance / pass rate (varies by outlet quality, see below). |
| 1 | **Outcome** | `player_reaches_position` (BH at outcome spot, or stopper for DEFENSIVE_STOP) | `next: turn_stop` for MAKE / MISS / BLOCK / FOUL / STEAL / DEAD_BALL. DEFENSIVE_STOP continues to step 2. |
| 2 | **Step-back / HCO setup** (DEFENSIVE_STOP only) | `player_reaches_position` | Implicit end. Caller's next turn is HCO. |

### Outlet pass quality (step 0)

Two coupled effects gate on `fb_roles["outlet_score"]`:

- **Pass speed**:
  - `outlet_score >= 50` → `FB_PASS_GRID_SPOTS_PER_GAME_SECOND = 30` grid/game-sec (sharp).
  - `outlet_score < 50` → 22 grid/game-sec (sloppy; hangs longer).
  - Floored at 0.5 game-sec for very short passes.
- **Defender read-to-stop** (sharp outlets only): get-back defenders must pass a `player_read` roll (IQ × 0.8 + CH × 0.2 × 1d6) vs threshold `outlet_score × 3` to claim the cut-off stop position; otherwise they retreat to basket defense. Eligibility filtered by x position relative to receiver. Full spec in [`Fast_Break_System.md`](../05_GP_Supporting_Systems/Fast_Break_System.md) — Covert Release — Get-back defender read on outlet pass (step 0).

### Per-player movement (step 0)

- **Outlet passer** (rebounder): stationary at rebound site.
- **Outlet receiver** (= BH): stationary at release coord.
- **Get-back defenders**: see read-to-stop spec above.
- **All others**: drift `random.randint(1, 6)` toward attacking basket along x, holding y, archetype `cruise`. Keeps step 0 focused on the pass; supporting sprinters ramp up on step 1.

### Step metadata for frontend effects

The outlet pass step's `advance_trigger.metadata` carries `outlet_score` (in addition to the standard `from_player_id` / `to_player_id` / `target_coords`). Frontend reads this to gate:
- **Ball trail effect** ([createBallTrail.js](../../FrontEnd/static/js/phaser/animation/createBallTrail.js)) on `outlet_score >= 50`.
- **SFX** (`outlet-pass-great.wav` vs `outlet-pass-bad.wav`) on the same threshold, fired at the moment of `detachBall`.

### Files

- Emitter: `BackEnd/engine/covert_release_step_emitter.py`
- Caller: `phase_resolution.resolve_fast_break_logic` (covert branch); attaches `animation_steps` to the turn payload.
- Frontend routing: `AnimationEngine.js:302-328`
- Frontend playback: `animationPlayback.js` (`renderBallTransition`, `runShotAttempt`).

---

## Rim Runner FB emitter — scoping

**Status:** Schema-driven. Implemented in `BackEnd/engine/rim_runner_step_emitter.py`. Frontend takes the new engine when `turnData.fast_break_play === "rim_runner"` and `turnData.animation_steps` is present ([AnimationEngine.js:302-330](../../FrontEnd/static/js/phaser/animation/AnimationEngine.js)).

### Step decomposition (5 terminal branches)

Branches share steps 0–1 (Burst, Outlet pass); outlet-denied forks at step 1.

| Branch | Steps | Terminal `next` |
|---|---|---|
| **Outlet → Shot** | 0 Burst → 1 Outlet pass → 2 Lane pass (BH→RR catch; "Fast Break!" announcement) → 3 Shot motion | `turn_stop: SHOT_ATTEMPT` |
| **Outlet → STEAL** | 0 → 1 → 2 Lane pass intercepted ("Interception!" announcement) | `turn_stop: STEAL` |
| **Outlet → Bat OOB** | 0 → 1 → 2 Lane pass batted ("Out of bounds!" announcement) | `turn_stop: DEAD_BALL_TURNOVER` |
| **Outlet → Hold-up → HCO settle** | 0 → 1 → 2 Hold-up lead-in ("No Fast Break" announcement) | implicit end → HCO |
| **Outlet Denied → HCO settle** | 0 → 1 Defender close-out ("FB Outlet Pass Denied!" announcement) → 2 Receiver cutback + drift → 3 Recovery pass | implicit end → HCO |

Edge case: when rebounder == outlet receiver (`skip_outlet_pass = true`), step 1 is skipped — burst chains directly to the branch's step 2 (or step 1 for outlet-denied).

### Branch dispatch (keyed off `turn_result` flags)

| Flag | Routes to |
|---|---|
| `rim_runner_outlet_failed` | Outlet Denied |
| `rim_runner_no_lane_pass` | Hold-up |
| `rim_runner_interception` | STEAL |
| `rim_runner_bat_oob` | Bat OOB |
| otherwise (`result_type` ∈ {MAKE, MISS, BLOCK, FOUL}) | Shot |

### Reusable builders (for Triangle)

- `_build_burst_step` — Step 0 burst. All burst movers fire in parallel toward `rim_runner_burst_phase.{rr_to, receiver_to, outlet_defender_to, other_players[i]}`; gate = outlet receiver reaches `receiver_to` at default archetype.
- `_build_outlet_pass_step` — Step 1 outlet pass. Sharp/sloppy rate branch on `outlet_score` (mirrors CR); drift continues for supporting movers through the pass.

Triangle's emitter (next migration) imports both directly — Triangle's lead-in matches RR's burst + outlet exactly; divergence starts at step 2.

### Outlet-denied distance gate (sim)

Outlet defender must be within **10 grid Euclidean** of the outlet passer (rebounder) to claim the denial. Beyond that, the contest auto-succeeds regardless of attribute rolls — denial is geometrically implausible at distance. Enforced in [rim_runner_fast_break.py](../../BackEnd/engine/rim_runner_fast_break.py) at Step A (outlet contest). All RR animation is unaffected by the gate (defender still tweens toward the contest spot in burst step 0); only the sim outcome shifts.

### Step metadata for frontend effects

Per-branch announcement payloads carry headshot card data + decision pill + SFX hints via `Announcement.meta`. All RR announcements are `style: "secondary"`.

| Cue | Step + position | meta |
|---|---|---|
| "Fast Break!" + decision pill + FB play subtitle (Shot branch) | step 2 (lane pass) `start.announcement` | `decisionPillText`, `decisionPillTone`, `eventSubtitle` |
| "Interception!" (STEAL) | step 2 (lane pass intercepted) `end.announcement` | `sfx: "steal"` |
| "Out of bounds!" (Bat OOB) | step 2 (lane pass batted) `end.announcement` | `text_scroll: "Batted out of bounds."`, `hold_ms: 650` |
| "No Fast Break" + decision pill (Hold-up) | step 2 (hold-up lead-in) `start.announcement` | `decisionPillText`, `decisionPillTone` |
| "FB Outlet Pass Denied!" + court SFX (Outlet Denied) | step 1 (defender close-out) `end.announcement` | `sfx: "fb_outlet_denied_court"` |

Intercept / Bat OOB contact-point math (`_compute_interception_contact_grid`) and OOB grid resolution (`_nearest_oob_grid`) are mirrored from the frontend helpers (`resolveFbInterceptionContactGrid`, `resolveNearestOutOfBoundsGrid`) so the backend can stamp `advance_trigger.metadata.contact_coords` (and `oob_coords` for batted) without the frontend recomputing them.

### `hco_setup` (FB → next HCO turn signal)

When the FB ends with the BH (outlet receiver) holding the ball away from the offensive PG (Hold-up or Outlet Denied branches), the emitter stamps `turn_result["hco_setup"] = {"inbound_pass": {from_player_id, to_player_id, from_coords}}`. `game_manager.run_micro_turn` propagates this onto the next HCO turn payload at the turn-append seam. Replaces the historical frontend `scene._rimRunnerHoldUpInboundPass` flag (which had since been removed; the new signal is the backend source of truth). HCO consumer wiring deferred to HCO's full migration — until then, the data rides on the HCO turn payload unread.

### Files

- Emitter: `BackEnd/engine/rim_runner_step_emitter.py`
- Caller: `phase_resolution.resolve_fast_break_logic` (RR branch); attaches `animation_steps` to the turn payload.
- Sim: `BackEnd/engine/rim_runner_fast_break.py` (outlet contest distance gate at Step A).
- HCO setup propagation: `BackEnd/models/game_manager.py` (`run_micro_turn` turn-append seam).
- Frontend routing: `AnimationEngine.js:302-330` (RR added to `MIGRATED_FB_PLAYS` set).
- Frontend playback: `animationPlayback.js` (`renderBallTransition`, `runShotAttempt`, `runStepAnnouncement`).

---

## Cross-cutting invariants

These rules apply to every schema-driven turn and to legacy turns that share the same data plumbing (overlay maps, coord sync).

### Single-overlay-authority (post-shot positions)

`shot_manager` is the **sole authority** for where every player ends up after a shot. It populates four overlay maps on the turn result:
- `offense_rebounder_coords`
- `defense_rebounder_coords`
- `offense_getback_coords`
- `defense_release_coords`

The invariant: **each player appears in at most one overlay map.** Enforced by `canonicalize_post_shot_overlays` ([shared.py:2659](../../BackEnd/utils/shared.py)), which runs:
1. At every return point in `shot_manager.resolve_shot` (catches the shooter — exempted from all four maps).
2. Inside the CR FB emitter, after `fb_roles` is attached (catches the outlet passer — exempted from rebounder maps).
3. Inside `sync_lineup_coords_from_turn` before the overlay-apply loop (safety net).

Idempotent; safe to call multiple times. Priority: **shooter > outlet passer > release > getback > rebound cluster.**

This replaces an earlier ad-hoc pattern where each consumer (schema emitter, sync) had its own exemption logic — which leaked when role conflicts arose (shooter accidentally in `offense_getback_coords`, rebounder in rebounder cluster, release player in rebounder cluster, etc.).

### Overlay precedence (sync)

`TURN_COORDS_OVERLAY_KEYS` order is load-bearing ([shared.py:2645](../../BackEnd/utils/shared.py)):
```
("offense_rebounder_coords", "defense_rebounder_coords",
 "offense_getback_coords", "defense_release_coords")
```
Rebounder maps apply FIRST (default for everyone eligible); get-back / release apply LAST so they override for designated non-rebounders. Reversing this order pulls release players back to the rim cluster.

### AG curve (player movement rates)

Single AG curve in [shared.py:606](../../BackEnd/utils/shared.py):
```
rate = 9 + (AG / 100) × 6
```
Anchored at AG=50 base = 12 (matches `CRUISE_BASELINE_GRID_PER_GAME_SEC`). Slope ×6 gives a moderate spread (AG=0 → 9, AG=100 → 15, AG=150 → 18). Multiplied by archetype factors (sprint=14/12, drive=1.0, shot_motion=10/12) at use sites. So sprint at AG=50 = 14 grid/game-sec, matching documented intent.

Tune by adjusting slope (each ±1 of slope = ±0.5 grid/game-sec swing at AG=100); intercept auto-compensates to keep AG=50 = 12.

### Game-time / wall-time sync

- `tickMs = 350` (1 game-sec = 350 ms wall-clock) — set on `scene.gameClock`.
- Schema playback engine renders each step at `step.end.time_elapsed × tickMs` wall-clock. **No cap.**
- Result: backend-computed game-time directly drives both clock-burn and animation duration. Long passes (sloppy outlets, long drives) take proportionally longer in wall-clock too. This is intentional — the user's design goal is "everything synced."

### Coords cross-turn contract

The DREB / migrated-turn emitters read **`player.coords`** (post-sync) for their step 0 start coords, NOT `miss_turn.animation_steps[-1].end.coords`. Reason: `sync_lineup_coords_from_turn` is the only place that applies the FULL post-shot picture (schema end coords + every overlay map in canonical order). The schema's own end.coords only reflects what `_apply_post_shot_overlay` actually wrote — which is partial if a player isn't in any overlay map, or if the emitter returned None.

---

## Resolved

- **Action vocabulary (working):** `handle_ball`, `pass`, `receive`, `cut`, `screen`, `shoot`, `stationary`, `sprint`, `guard_ball`, `guard_offball`, `post_up`. `post_up` added during HCO migration (distinct interior-positioning semantics warranted first-class). `get_open` collapses into `cut` (movement to space — same precedent as `cover_ground`/`drift` → `cut`). May extend further during audits.
- **Archetype vocabulary (working):** `default`, `sprint`, `drive`, `shot_motion`, `cruise`, `stationary`. Drives per-player rate; orthogonal to action.
- **Trigger condition vocabulary (working):** `fixed_duration`, `ball_reaches_player`, `player_reaches_position`, `shot_resolved`, `stopper_action` (covers foul / steal / dead-ball turnover — backend resolves which on fire).
- **Branching: pre-resolved.** Backend rolls dice + emits only the actual path. Frontend has no branch logic. No alternate-history replay capability — accepted trade.

---

## Coords Tracking System

Player coordinates are tracked at two levels: **within a turn** (step-to-step) and **across turns** (turn-to-turn transitions). Both must stay consistent for the animation system to work correctly.

### Within a turn (step-to-step)

**Backend (during emit):** Each step emitter walks the steps in order. Step N+1's `start.coords` is set from step N's `end.coords` (the schema's interrupted-coord output). The chain is internal to the emitter — it doesn't write to `player.coords` mid-emit. See `hct_step_emitter.py`, `skeleton_step_emitter.py`, `covert_release_step_emitter.py` for examples.

**Frontend (during playback):** `playAnimationStep` in `animationPlayback.js` snaps each sprite to `step.end.coords` at the end of every step (sets `sprite.gridX/gridY` and pixel position). So sprite state stays in sync with the schema step-by-step. The next step's tween starts from the snapped position.

### Turn-to-turn transitions

**Backend:** `sync_lineup_coords_from_turn` (in `BackEnd/utils/shared.py`) is the single end-of-turn coord-sync entry point on the backend. It reads from BOTH:
1. **Legacy `animations[]`** field — used for un-migrated turn types (FCP, Free Throw, OREB, BIP/SIP, Opening Tip, Timeout, Fast Break Rim Runner / Triangle / After Steal). Reads each animation row's final coord via `_final_xy_from_animation_row` and applies via `_normalize_animation_coords_to_runtime_home`.
2. **New schema `animation_steps[]`** field — used for migrated turn types (HCT, HCO, DREB, Covert Release FB). Reads the LAST step's `end.coords` map and applies the same `_normalize_animation_coords_to_runtime_home` normalization.

The `animation_steps[]` block runs AFTER the `animations[]` block, so when a turn carries both (parallel-build during migration), the new schema takes precedence. If a turn carries neither, `player.coords` carries forward unchanged from before the turn.

**Frontend:** Sprite `gridX`/`gridY` persist across turns naturally — no reset between turns. The next turn's first step reads sprite state directly. Backend-set `player.coords` are passed to the next turn's emitter as the starting coords, so backend and frontend stay in sync at the seam.

### Why this matters

When `sync_lineup_coords_from_turn` ignored `animation_steps[]` (the bug we fixed during CR FB migration), every turn-to-turn transition AFTER a migrated turn used stale `player.coords` from before the migrated turn. Symptoms:
- After a DREB turn, the subsequent FB turn would read pre-DREB coords (rebound never registered on the backend).
- After an HCT turn, the subsequent BIP/HCO would read pre-HCT coords.

The fix made `sync_lineup_coords_from_turn` schema-aware. Now both legacy and migrated turns properly update `player.coords` at end-of-turn.

### Contract for new emitter migrations

When migrating a turn type to the new schema:
1. Emit `animation_steps[]` with each step's `end.coords` populated for every active player (10 in standard 5v5).
2. Trust that `sync_lineup_coords_from_turn` will pick up the LAST step's `end.coords` and apply to `player.coords`.
3. Do NOT manually write to `player.coords` during the emit — let the sync handle it.
4. Within the emitter, ensure step N+1's `start.coords` matches step N's `end.coords` for every player. The schema relies on this contract; the playback engine does not snap sprites to `step.start.coords` between steps (snap happens only at step end).

### Files

- Sync function: [BackEnd/utils/shared.py](../../BackEnd/utils/shared.py) — `sync_lineup_coords_from_turn` (around line 2731)
- Coord normalization: same file — `_normalize_animation_coords_to_runtime_home`
- Frontend sprite snap: [FrontEnd/static/js/phaser/animation/animationPlayback.js](../../FrontEnd/static/js/phaser/animation/animationPlayback.js) — `playAnimationStep` end-of-step snap loop

---

## Next steps / open work

Tracked here as a punch list so the work plan stays visible. Order is suggested, not strict.

### Frontend cleanup once a turn type is fully migrated

When a turn type is 100% on the schema engine (no legacy fallback firing), the corresponding legacy frontend file can shrink or be deleted. Track in [`Animation_Cleanup.md`](Animation_Cleanup.md). Current candidates with the most legacy surface area:
- `fastBreak.js` — currently still hosts RR / Triangle / After-Steal paths. CR FB usage has been removed but the file is still loaded.
- `turnAnimation.js` — main step loop + legacy inbound / rebound helpers. Will shrink once BIP/SIP/FT/OREB migrate.

### Migration order (proposed)

| Order | Turn type | Notes |
|---|---|---|
| 1 | **RR / Triangle FB** | Largest legacy surface; high overlap with CR FB infrastructure. Once these land, all FB variants are schema-driven and `fastBreak.js` can shrink dramatically. |
| 2 | **BIP / SIP** | 2 steps per turn (setup + inbound pass). Simple shape; good practice turn for the schema. |
| 3 | **OREB putback** | 1–2 steps. Shares the SHOT_ATTEMPT turn_stop with HCO / HCT / FB so most plumbing exists. |
| 4 | **Free Throw** | N+1 steps. Shooter at FT line is conceptually simple; multi-attempt flow needs careful step decomposition. |
| 5 | **FCP** | Same shape as HCO / HCT; mostly mechanical. |
| 6 | **Opening Tip, Timeout** | Edge cases. Tip is jump-ball + converge; timeout is essentially a no-op turn. |

### Shooter `get_player_position` mismatch (away offense)

Known cosmetic upstream bug: on away-offense FB MAKE, `get_player_position(off_lineup, shooter)` can return None (Python `==` identity mismatch between `fb_roles["shooter"]` and `off_team.lineup[shooter_pos]`). The canonicalize-overlays layer masks this — the shooter is stripped from all overlay maps regardless — but the upstream identity quirk should be traced and fixed eventually. Not blocking.

### Pass animation system

- Pass speed for CR FB is backend-driven via `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` (30 sharp / 22 sloppy) + outlet-quality branch. RR / Triangle still use frontend pixel-speed (`DEFAULT_BALL_SPEED = 450 px/sec`, capped at 1000ms wall-clock). After RR / Triangle migrate, all FB passes share the same backend-driven model and the frontend `runPass` becomes vestigial.
- HCO half-court passes still use `PASS_GRID_SPOTS_PER_GAME_SECOND = 36` (canonical). Separate constant from FB so HCO clock-burn accounting is unaffected by FB tuning.

### Diagnostic logs still in code

- `🐛 [BUG B]` warning logs in `covert_release_step_emitter.py` (~5 of them around the BH end-coord pipeline) helped trace the shooter-in-getback bug. Safe to remove once the AG / overlay system has burned in for a couple more turn-type migrations.
- `🐛 [BALL DETACH]` console logs in `animationPlayback.js` (renderBallTransition) confirm the detach-before-tween fix is firing. Useful for verifying any new pass animation; remove when no longer instructive.

### Production thresholds (verify before shipping)

- Ball trail effect + outlet SFX: gated on `outlet_score >= 50` in `animationPlayback.js`. This is the production target.
- `FB_PASS_GRID_SPOTS_PER_GAME_SECOND = 30` (sharp), hardcoded `22.0` (sloppy) in `covert_release_step_emitter.py`. Tune via these two numbers if pass speed needs adjustment.
- AG curve slope = 6 in `ag_to_grid_per_game_sec` (`rate = 9 + (AG/100) × 6`). Tune slope to adjust the AG=0↔AG=150 speed spread; intercept auto-compensates to hold AG=50 = 12.
