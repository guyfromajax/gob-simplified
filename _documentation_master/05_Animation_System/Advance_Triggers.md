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

Per-step trigger uniformly = `player_reaches_position`, gated on the **slowest mover** for that step (player with the largest start→end distance). T = `step_clock_seconds[i]`. Faster movers reach their destinations earlier and idle until T.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0..N−2 | Skeleton step i | `player_reaches_position` | slowest mover for step i | `step_clock_seconds[i]` |
| N−1 | Final step (outcome) | `player_reaches_position` | slowest mover for final step | `step_clock_seconds[N−1]` |

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

_TBD_ (4 sub-variants: Covert Release, Rim Runner, Triangle, After Steal)

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
