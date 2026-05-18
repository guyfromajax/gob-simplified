/**
 * Animation step schema — JSDoc mirror of
 * `BackEnd/utils/animation_step_schema.py`. See
 * `_documentation_master/projects/Animation_System_Updated.md` for design
 * rationale.
 *
 * Each animation step has a start state, an advance trigger (condition +
 * computed T in game-seconds), and a derived end state. Backend is the
 * source of truth; frontend is a pure playback engine — no advance-
 * trigger detection, no destination calculation.
 *
 * This file is documentation only — no runtime exports. Keep in lockstep
 * with the Python module.
 */

/**
 * @typedef {string} PlayerId
 *   Stringified player_id throughout for consistency.
 */

/**
 * @typedef {(
 *   "handle_ball" | "pass" | "receive" | "cut" | "screen" | "shoot"
 *   | "stationary" | "sprint" | "guard_ball" | "guard_offball" | "post_up"
 * )} PlayerAction
 *   Semantic role a player performs during the step. Drives renderer
 *   behavior (sprite frames, ball events). Orthogonal to archetype.
 */

/**
 * @typedef {(
 *   "default" | "sprint" | "drive" | "shot_motion" | "cruise" | "stationary"
 * )} PlayerArchetype
 *   Movement-rate selector. Multiplied with player AG curve to produce
 *   grid/game-second rate. Orthogonal to action.
 */

/**
 * @typedef {(
 *   "fixed_duration" | "ball_reaches_player" | "player_reaches_position"
 *   | "shot_resolved" | "stopper_action"
 * )} TriggerCondition
 *   Step-end gate. `stopper_action` collapses foul / steal / dead-ball
 *   turnover — backend resolves which on fire.
 */

/**
 * @typedef {(
 *   "SHOT_ATTEMPT" | "FOUL" | "STEAL" | "DEAD_BALL_TURNOVER"
 *   | "SHOT_CLOCK_EXPIRED" | "GAME_CLOCK_EXPIRED" | "TIMEOUT" | "JUMP_BALL"
 * )} TurnStopEvent
 */

/**
 * @typedef {Object} GridCoord
 * @property {number} x
 * @property {number} y
 */

/**
 * @typedef {Object} BallAttached
 * @property {PlayerId} owner_player_id
 */

/**
 * @typedef {Object} BallInFlight
 * @property {PlayerId} from_player_id
 * @property {PlayerId} to_player_id
 * @property {GridCoord} current_coords
 */

/**
 * @typedef {Object} BallLoose
 *   Ball at rest at coords with no owner. Used between a missed shot and
 *   the rebound capture (e.g., DREB step start). Discriminated from
 *   BallInFlight by the absence of `from_player_id` / `to_player_id`.
 * @property {GridCoord} coords
 */

/**
 * @typedef {(BallAttached | BallInFlight | BallLoose)} BallState
 */

/**
 * @typedef {Object} ClockState
 * @property {number} clock_remaining       Game-seconds.
 * @property {number} shot_clock_remaining  Game-seconds.
 */

/**
 * @typedef {Object} AdvanceTrigger
 * @property {TriggerCondition} condition
 * @property {number} T_game_seconds
 * @property {Object<string, *>} metadata
 *   Condition-specific extras (e.g. `target_player_id` for
 *   `ball_reaches_player`, `position` for `player_reaches_position`).
 *   Loose by design.
 */

/**
 * @typedef {Object} Announcement
 *   In-step announcement with mandatory pause-the-world behavior. Optional
 *   field on StepStart (plays before step tweens fire) or StepEnd (plays
 *   after step tweens complete and sprites snap). Playback engine pauses
 *   `gameClock` and `shotClock`, calls `showAnnouncement`, awaits the
 *   hold duration, then resumes clocks.
 * @property {string} text                Announcement copy (e.g. "Nice Stop!").
 * @property {("home"|"away"|"defense"|"neutral")} team
 * @property {Object<string,*>|null} [player_data]  Optional headshot card payload.
 * @property {Object<string,*>|null} [meta]         Optional { decision_pill_text?, decision_pill_tone?, sfx? }.
 * @property {number} [hold_ms]                     Wall-clock pause duration (default 1000).
 * @property {("primary"|"secondary")} [style]      Routing: "primary" (default; showAnnouncement) or "secondary" (showSecondaryAnnouncement).
 */

/**
 * @typedef {Object} StepStart
 * @property {Object<PlayerId, GridCoord>}        coords
 * @property {Object<PlayerId, (GridCoord|null)>} destination
 * @property {Object<PlayerId, PlayerAction>}     action
 * @property {Object<PlayerId, PlayerArchetype>}  archetype
 * @property {BallState}                          ball
 * @property {ClockState}                         clock
 * @property {AdvanceTrigger}                     advance_trigger
 * @property {Announcement} [announcement]
 *   Optional. Plays BEFORE step tweens fire. Used for entry-of-turn
 *   announcements like "Trap!" / "Fast Break!".
 * @property {Object<PlayerId, number>} [tween_durations]
 *   Optional. Per-player tween duration in game-seconds. When present, the
 *   playback engine tweens each player for their individual duration;
 *   fast finishers idle until step T elapses. When absent, fallback to
 *   step T (which stretches fast finishers — the "lazy drift" anti-pattern).
 *   Backend always stamps when it has per-player rate info.
 */

/**
 * @typedef {Object} NextLinear
 * @property {"next_step"} kind
 * @property {number}      index
 */

/**
 * @typedef {Object} NextBranch
 * @property {"branch"} kind
 * @property {string}   outcome
 * @property {number}   next_step_index
 */

/**
 * @typedef {Object} NextTurnStop
 * @property {"turn_stop"}     kind
 * @property {TurnStopEvent}   event
 * @property {Object<string,*>} payload
 */

/**
 * @typedef {(NextLinear | NextBranch | NextTurnStop)} NextStep
 */

/**
 * @typedef {Object} StepEnd
 * @property {Object<PlayerId, GridCoord>} coords
 *   Interrupted positions at T. Backend computes:
 *   `start.coords + min(rate × T, full_distance)` along start→destination,
 *   where `rate` = player AG curve × archetype multiplier.
 * @property {BallState} ball
 * @property {number}    time_elapsed
 *   = AdvanceTrigger.T_game_seconds. Canonical step duration.
 * @property {ClockState} clock
 * @property {NextStep}   next
 * @property {Announcement} [announcement]
 *   Optional. Plays AFTER step tweens complete and sprites snap, BEFORE
 *   returning `next`. Used for mid-turn announcements like "Nice Stop!".
 */

/**
 * @typedef {Object} AnimationStep
 * @property {StepStart} start
 * @property {StepEnd}   end
 */

// No runtime exports — this file is documentation only.
export {};
