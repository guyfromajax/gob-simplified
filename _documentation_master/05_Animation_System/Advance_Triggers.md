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

_TBD_

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
