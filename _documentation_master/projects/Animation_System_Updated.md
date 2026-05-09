# Animation System Updated

> **Status:** Schema design — validating against turn types before treating it as locked. Started 2026-05-09.
>
> **Context:** Successor to [`Animation_System_Refactor.md`](Animation_System_Refactor.md). That doc inventoried turn types and surfaced inconsistencies. This doc proposes the unified per-step payload schema and validates it against the most uniform turn type (HCO) and the most divergent (Fast Break).
>
> **Architecture commitment:** advance trigger lives on the backend. Backend pre-computes `T = game-seconds when trigger fires`, then derives all end-state fields (interrupted coords, ball state, clock advance) from T. Frontend is a pure playback engine.

---

## Proposed schema

Each animation step has a **start state**, an **advance trigger**, and a **derived end state**.

### Start of step
- `coords` — `{[player_id]: {x, y}}` for all players on court
- `destination` — `{[player_id]: {x, y} | null}` (null = stationary)
- `action` — `{[player_id]: <closed vocab>}`. Working list: `handle_ball`, `pass`, `receive`, `cut`, `screen`, `shoot`, `stationary`, `sprint`, `guard_ball`, `guard_offball`. May extend during turn-type audits.
- `archetype` — `{[player_id]: <closed vocab>}` (e.g. `default`, `sprint`, `drive`, `shot_motion`, `cruise`, `stationary`) — drives per-player rate via the AG curve
- `ball` — either `{owner_player_id}` or `{in_flight: {from_player_id, to_player_id, current_coords}}`
- `clock` — `{clock_remaining, shot_clock_remaining}` (game-seconds)
- `advance_trigger` — `{condition: <metadata>, T_game_seconds: <computed>}`

### End of step (derived from start + T)
- `coords` — interrupted position per player (formula: along start→destination at distance `rate × T`, or destination if `rate × T ≥ full distance`)
- `ball` — final state at T
- `time_elapsed` — T (game-seconds)
- `clock` — state after T elapses
- `next` — one of:
  - `{kind: "next_step", index}` (linear continuation)
  - `{kind: "branch", outcome, ...}` (outcome-driven; backend already resolved which branch)
  - `{kind: "turn_stop", event, payload}` (turn ends)

### Turn-stopping event types (to be enumerated)
Working list: `SHOT_ATTEMPT`, `FOUL` (variants: O/D/charge/blocking/shooting), `STEAL`, `DEAD_BALL_TURNOVER`, `SHOT_CLOCK_EXPIRED`, `GAME_CLOCK_EXPIRED`, `TIMEOUT`, `JUMP_BALL`. Confirm completeness during turn-type audits.

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

**Verdict:** HCO fits with three concrete upgrades — explicit per-player archetype, explicit ball state, per-step clock + trigger fields.

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

**Verdict:** FB doesn't naturally fit. Restructuring is required. Concretely, "phases" in `fastBreak.js` need to be replaced by discrete backend-emitted steps with computed triggers and pre-computed interrupted coords.

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

First turn type to migrate. Below: the concrete mapping from existing HCT data sources (`dynamic_hct.py`, `phase_resolution.py` HCT branch) to the schema's `AnimationStep[]` shape.

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

The DREB turn is generated by the backend after any MISS turn whose rebounder is on the defensive team. For HCT migration (current scope): DREB after HCT MISS only. HCO/FCP/FB DREB cases are out of scope until those turn types migrate.

### Step decomposition (1 schema step)

| # | Step | Description |
|---|---|---|
| 0 | **Rebound capture** | Rebounder converges on bounce coords; other rebound-attempters (frontcourt-half filter) converge near bounce coords. Step ends when rebounder reaches ball. |

### Trigger + next pointer

- **Trigger condition:** `player_reaches_position` with metadata `{target_player_id: rebounderId, target_coords: bounce_coords}`. T = time for rebounder to traverse start coord → bounce coord at sprint rate.
- **Next pointer:**
  - Normal capture (no foul): implicit end (`next_step` past the array → `playTurn` returns `null`). Caller transitions to next turn (HCO or FAST_BREAK based on game state).
  - Over-the-back foul: `turn_stop: FOUL` with payload `{foul_type: "non_shooting", over_the_back: true, fouler_id, victim_id}`. Caller routes to SIP or FREE_THROW (bonus situation).

### Per-player action and archetype

| Player role | Action | Archetype | End coord |
|---|---|---|---|
| Rebounder (closest to bounce, picked by `choose_rebounder` after frontcourt-half prefilter) | `cut` | `sprint` | Ball bounce coords |
| Other rebound attemptors (other 4 players passing the frontcourt-half x-eligibility filter) | `cut` | `sprint` | Random spot near ball (±6x, ±8y from bounce, court-clamped) |
| Players outside frontcourt-half filter | `stationary` | `stationary` | (no movement) |

The frontcourt-half prefilter is applied uniformly to both teams' lineups.

### Ball state

- **Start:** `BallLoose {coords: bounce_coords}` — ball sits at bounce spot after the previous SHOT_ATTEMPT turn-stop handler animated the ball-on-rim and bounce.
- **End:** `BallAttached {owner_player_id: rebounderId}` — rebounder has secured the ball.

### Coord sources for DREB step start

| Player | Source of start coord |
|---|---|
| All 10 players | Whatever positions they ended at when the previous MISS turn's last step completed. The new schema's `step.start.coords` is set by the emitter from the previous turn's end state. |

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

Files touched: `shot_manager.py`, `game_manager.py`, `turn_manager.py`, `phase_resolution.py`. Estimated 4–5 files.

---

## Resolved

- **Action vocabulary (working):** `handle_ball`, `pass`, `receive`, `cut`, `screen`, `shoot`, `stationary`, `sprint`, `guard_ball`, `guard_offball`. May extend during audits; no `cover_ground` or `drift` (collapsed into `cut`).
- **Archetype vocabulary (working):** `default`, `sprint`, `drive`, `shot_motion`, `cruise`, `stationary`. Drives per-player rate; orthogonal to action.
- **Trigger condition vocabulary (working):** `fixed_duration`, `ball_reaches_player`, `player_reaches_position`, `shot_resolved`, `stopper_action` (covers foul / steal / dead-ball turnover — backend resolves which on fire).
- **Branching: pre-resolved.** Backend rolls dice + emits only the actual path. Frontend has no branch logic. No alternate-history replay capability — accepted trade.
