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
 *   "sprint" | "burst" | "standard" | "shot_motion" | "cruise" | "stationary"
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
 * @typedef {Object} StepSfx
 *   Backend-resolved SFX cue. FE plays the named file at the appropriate
 *   ball-motion moment (release / arrival).
 * @property {string} file               Asset filename (e.g. "swish.wav").
 * @property {number} [volume]           Defaults to 0.7 if omitted.
 * @property {string} [event]            Telemetry tag for playGameSfx.
 */

/**
 * @typedef {Object} TimedSfx
 *   Backend-resolved SFX cue with an explicit wall-clock offset from step
 *   start. The FE schedules `setTimeout` for each cue. Used for variant
 *   follow-up cues that overlap the next sub-step's motion.
 * @property {string} file
 * @property {number} delay_ms           ms after step start.
 * @property {number} [volume]
 * @property {string} [event]
 */

/**
 * @typedef {Object} Flourish
 *   In-place character "micro-movement" rendered by the FE in RENDER SPACE
 *   only — never mutates gameplay grid coords (cf. the arrival heartbeat).
 *   Backend names the flourish + optional params; the FE owns the visual
 *   vocabulary and supplies defaults (animation_config.js `flourish` block)
 *   for any omitted field. First shipped: "reach_in" (defender steal attempt
 *   on a Dynamic-HCT contest moment). Other kinds are accepted-but-unrendered
 *   placeholders for now.
 * @property {("reach_in"|"pump_fake"|"bite"|"gather"|"rattle"|"shot_dip"|"dribble"|"pickup"|"dunk")} kind
 * @property {number} [amplitude_grid]   Lunge distance in GRID units (rendered, not gameplay). Omitted → FE default.
 * @property {number} [duration_ms]      Wall-clock out-and-back duration. Omitted → FE default.
 * @property {string} [ease]             Phaser ease (e.g. "Back.easeOut"). Omitted → FE default.
 * @property {("ball"|"rim"|"x"|"y")} [target]   What the motion points at. "reach_in" uses "ball".
 * @property {number} [cycles]           Oscillation count (rattle); ignored otherwise.
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
 * @property {("shot"|"pass")} [ball_motion_style]
 *   Optional. Overrides the ball tween duration: "shot" → 27 grid/game-sec
 *   (min 400 ms FE playback floor), "pass" → PASS_GRID_SPOTS_PER_GAME_SECOND
 *   (24). Absent → ball tweens over step T.
 * @property {GridCoord} [ball_arrival_coord]
 *   Optional. Overrides the ball-tween end coord (used for moving-receiver
 *   meet-points). Absent → derived from `step.end.ball` owner / coords.
 * @property {StepSfx} [sfx_on_ball_release]
 *   Optional. Fires at the moment the ball detaches from its start-owner
 *   (= ball-tween start). Used for pass release, shot release, etc.
 * @property {StepSfx} [sfx_on_ball_arrival]
 *   Optional. Fires at the ball-tween onComplete (= ball reaches destination).
 *   Used for reception, shot result, etc.
 * @property {TimedSfx[]} [timed_sfx]
 *   Optional. Follow-up cues fired at `delay_ms` after ball arrival (ball
 *   tween onComplete). Used for BANK_MAKE / BACK_OF_RIM delayed swish.
 * @property {Object<PlayerId, Flourish>} [flourish]
 *   Optional. Per-player in-place micro-movements rendered in RENDER SPACE
 *   only (never mutates gameplay coords). FE fires them fire-and-forget in
 *   PARALLEL with the step's player tweens — they do not gate step T or the
 *   turn boundary. First use: defender "reach_in" on Dynamic-HCT steal
 *   contest moments.
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
