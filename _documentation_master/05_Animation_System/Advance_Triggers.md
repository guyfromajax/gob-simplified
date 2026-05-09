# Advance Triggers

Per-step advance triggers for each turn type in the unified animation system. The advance trigger is the condition that ends a step; backend pre-computes its time `T` (game-seconds) and the frontend playback engine awaits exactly that duration before rendering step end.

See [Animation_System_Updated.md](../projects/Animation_System_Updated.md) for the schema and architecture.

**Trigger conditions (closed vocab):**
- `fixed_duration` — step ends after a backend-computed duration. T = the duration.
- `ball_reaches_player` — step ends when the ball arrives at a target player. T = pass distance ÷ pass speed.
- `player_reaches_position` — step ends when a target player arrives at a target coord. T = traversal time at the player's archetype rate.
- `shot_resolved` — step ends when shot outcome is determined.
- `stopper_action` — step ends on backend-rolled foul / steal / dead-ball turnover event.

---

## HCT

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Setup | `player_reaches_position` | slowest setup mover (max start→end distance) | `step_clock_seconds[0]` |
| 1 | BH advance | `player_reaches_position` | BH | `step_clock_seconds[1]` |
| 2 | PG converge | `player_reaches_position` | PG defender (defender on BH) | `step_clock_seconds[2]` |
| 3 | Outcome | `player_reaches_position` | BH | `step_clock_seconds[3]` |

## DREB

| # | Step | Trigger | T |
|---|---|---|---|
| 0 | Rebound capture | `player_reaches_position` (rebounder → ball bounce coords) | rebounder traversal time at `sprint` archetype |

---

## Not yet migrated

Sections below are placeholders. Populated as each turn type migrates to the new system.

## HCO

HCO is skeleton-driven. The emitter walks `skeleton.steps[i]` + `step_clock_seconds[i]` and emits one AnimationStep per skeleton step. The number of steps varies by playcall / variant — typically 4–10 after inbound trim.

Per-step trigger uniformly = `player_reaches_position`. T = `step_clock_seconds[i]`. Faster movers reach their destinations earlier and idle until T.

Gating player:
- Steps `0..N−2`: **slowest mover** (player with the largest start→end distance).
- Step `N−1` (final): **shooter** (offense player with `shoot` in pos_actions); falls back to slowest mover if the final step has no shoot action (e.g., non-shot outcomes like steals or dead-ball turnovers).

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0..N−2 | Skeleton step i | `player_reaches_position` | slowest mover for step i | `step_clock_seconds[i]` |
| N−1 | Final step (outcome) | `player_reaches_position` | shooter on shot outcomes; slowest mover otherwise | `step_clock_seconds[N−1]` |

Final step branches on `result_type` (same outcome map as HCT step 3):
- `MAKE`/`MISS`/`BLOCK` → `turn_stop: SHOT_ATTEMPT`
- `D_FOUL`/`O_FOUL`/`FOUL` → `turn_stop: FOUL`
- `STEAL` → `turn_stop: STEAL`
- `DEAD_BALL` / `DEAD_BALL_TURNOVER` / `TURNOVER` → `turn_stop: DEAD_BALL_TURNOVER`
- `SHOT_CLOCK_EXPIRED` → `turn_stop: SHOT_CLOCK_EXPIRED`

After HCO MISS with defensive rebound, a discrete DREB turn is generated (parallel to OREB). See DREB section above.

## FCP

_TBD_

## Fast Break

Phase 2 rows (shot motion / shot resolution / defensive stop) below are **best-effort** mappings against the existing `fastBreak.js` orchestration. Where the current code doesn't expose a clean per-step gate (defensive stop, hold-up lead-in, outlet-denied beat), the row is marked _TBD_ to be scoped during the FB migration.

After Steal sub-variant is intentionally out of scope here.

### Covert Release

Single lead-in step (outlet pass). Then the FB resolves to either a shot or a defensive stop.

#### Branch: Outlet → Shot Attempt

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Outlet pass | `ball_reaches_player` | outlet receiver (passer → receiver) | pass flight time |
| 1 | Shot motion | `player_reaches_position` | shooter (reaches shot spot) | shooter traversal time |
| 2 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: Outlet → Defensive Stop

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Outlet pass | `ball_reaches_player` | outlet receiver | pass flight time |
| 1 | Defensive stop | _TBD_ — `animateDefensiveStop` has no clean per-step gate exposed in current code | _TBD_ | _TBD_ |

Note: per current `animateOutletPhase`, only the ball moves during step 0 — players hold position. (Parallel non-getback advancement is commented out.)

### Rim Runner

Five terminal branches. All share steps 0–1 (burst + outlet pass) except outlet-denied, which forks at step 1.

#### Branch: Burst → Outlet → Lane Pass → Shot

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver (reaches `receiver_to`) | receiver traversal at sprint |
| 1 | Outlet pass | `ball_reaches_player` | outlet receiver | pass flight time |
| 2 | Lane pass | `ball_reaches_player` | rim runner (ball + RR co-arrive at catch grid) | RR traversal at sprint |
| 3 | Shot motion | `player_reaches_position` | shooter (reaches shot spot) | shooter traversal time |
| 4 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: Burst → Outlet Denied → Defensive Stop

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver (reaches `receiver_to`) | receiver traversal at sprint |
| 1 | Outlet denied beat | _TBD_ — `animateRimRunnerOutletDeniedBeat` runs receiver cut + announcement + outlet defender pursuit; no single clean gate | _TBD_ | _TBD_ |
| 2 | Defensive stop | _TBD_ — see Covert Release defensive stop | _TBD_ | _TBD_ |

#### Branch: Burst → Outlet → Lane Pass Intercepted (STEAL)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver | receiver traversal at sprint |
| 1 | Outlet pass | `ball_reaches_player` | outlet receiver | pass flight time |
| 2 | Lane pass intercepted | `ball_reaches_player` | interceptor (ball reaches interception contact grid) | partial pass flight time |
| 3 | `turn_stop: STEAL` | — | — | — |

#### Branch: Burst → Outlet → Lane Pass Batted OOB

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver | receiver traversal at sprint |
| 1 | Outlet pass | `ball_reaches_player` | outlet receiver | pass flight time |
| 2 | Lane pass batted OOB | `ball_reaches_player` | OOB destination (ball reaches OOB grid post-deflection) | partial pass flight + OOB drift |
| 3 | `turn_stop: DEAD_BALL_TURNOVER` | — | — | — |

#### Branch: Burst → Outlet → Hold-up → HCO Settle

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver | receiver traversal at sprint |
| 1 | Outlet pass | `ball_reaches_player` | outlet receiver | pass flight time |
| 2 | Hold-up lead-in | _TBD_ — `animateRimRunnerHoldUpLeadIn` has no exposed per-step gate | _TBD_ | _TBD_ |
| 3 | HCO settle | _TBD_ — `finalizeRimRunnerNonShotTurn` | _TBD_ | _TBD_ |

### Triangle

Drafts off the Rim Runner burst (steps 0–1). Adds Triangle setup (step 2), then a branch-specific decision lead-in (step 3+) per `triangle_branch`. If the outlet is denied (`rim_runner_outlet_failed`), Triangle setup is skipped and the path falls through to the Rim Runner outlet-denied branch above.

Common lead-in (steps 0–2, shared by all branches below):

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver | receiver traversal at sprint |
| 1 | Outlet pass | `ball_reaches_player` | outlet receiver | pass flight time |
| 2 | Triangle setup | `player_reaches_position` | slowest of {BH, RR, trailer, corner players, defenders} reaching setup target | slowest mover traversal |

#### Branch: triangle_rr_post (BH → RR pass → RR shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH→RR pass | `ball_reaches_player` | RR | pass flight time |
| 4 | Shot motion | `player_reaches_position` | RR (reaches shot spot) | RR traversal time |
| 5 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_corner_three (BH → corner pass → corner shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH→corner pass | `ball_reaches_player` | same-side corner | pass flight time |
| 4 | Shot motion | `player_reaches_position` | corner shooter (reaches shot spot) | corner traversal time |
| 5 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_bh_wing_three (BH wing shot, no pass)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | Shot motion | `player_reaches_position` | BH (reaches shot spot) | BH traversal time |
| 4 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_bh_drive (BH + RR drive, BH shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH + RR drive | `player_reaches_position` | slower of {BH (`triangle_drive_to`), RR (`triangle_rr_drive_to`)} | slower mover traversal |
| 4 | Shot motion | `player_reaches_position` | BH (reaches shot spot) | BH traversal time |
| 5 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_drive_rr_feed (BH + RR drive → BH→RR pass → RR shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH + RR drive | `player_reaches_position` | slower of {BH, RR} reaching their drive targets | slower mover traversal |
| 4 | BH→RR pass | `ball_reaches_player` | RR | pass flight time |
| 5 | Shot motion | `player_reaches_position` | RR (reaches shot spot) | RR traversal time |
| 6 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_drive_corner_kick (BH + RR drive → BH→corner pass → corner shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH + RR drive | `player_reaches_position` | slower of {BH, RR} reaching their drive targets | slower mover traversal |
| 4 | BH→corner pass | `ball_reaches_player` | same-side corner | pass flight time |
| 5 | Shot motion | `player_reaches_position` | corner shooter (reaches shot spot) | corner traversal time |
| 6 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_hco_settle (no shot, settle to HCO)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | HCO settle | _TBD_ — `animateTriangleHcoSettle` calls `finalizeRimRunnerNonShotTurn`; no per-step gate exposed | _TBD_ | _TBD_ |

## OREB

_TBD_

## BIP

_TBD_

## SIP

_TBD_

## Free Throw

_TBD_

## Opening Tip

_TBD_

## Timeout

_TBD_
