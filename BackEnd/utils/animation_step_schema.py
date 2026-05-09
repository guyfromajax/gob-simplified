"""Animation step schema — canonical types for the unified animation system.

See `_documentation_master/projects/Animation_System_Updated.md` for the
design rationale. This module is the single source of truth for the
backend-emitted per-step animation payload shape. FrontEnd has a JSDoc
mirror at `FrontEnd/static/js/phaser/animation/animationStepSchema.js`;
keep both in lockstep.

Architecture: each animation step has a start state, an advance trigger
(condition + computed T in game-seconds), and a derived end state. All
end-state fields are computed from (start + T) on the backend. The
frontend is a pure playback engine — no advance-trigger detection, no
destination calculation.
"""

from typing import Dict, Literal, Optional, TypedDict, Union

# --- Closed vocabularies ----------------------------------------------------

PlayerId = str
"""Stringified player_id throughout for consistency."""

PlayerAction = Literal[
    "handle_ball",
    "pass",
    "receive",
    "cut",
    "screen",
    "shoot",
    "stationary",
    "sprint",
    "guard_ball",
    "guard_offball",
]
"""Semantic role a player performs during the step. Drives renderer
behavior (sprite frames, ball events). Orthogonal to archetype."""

PlayerArchetype = Literal[
    "default",
    "sprint",
    "drive",
    "shot_motion",
    "cruise",
    "stationary",
]
"""Movement-rate selector. Multiplied with the player AG curve to produce
grid/game-second rate. Orthogonal to action — the same action may run at
different archetypes (e.g. relaxed `cut` vs. fast-break `cut`)."""

TriggerCondition = Literal[
    "fixed_duration",
    "ball_reaches_player",
    "player_reaches_position",
    "shot_resolved",
    "stopper_action",
]
"""Step-end gate. `stopper_action` collapses foul / steal / dead-ball
turnover — backend resolves which on fire."""

TurnStopEvent = Literal[
    "SHOT_ATTEMPT",
    "FOUL",
    "STEAL",
    "DEAD_BALL_TURNOVER",
    "SHOT_CLOCK_EXPIRED",
    "GAME_CLOCK_EXPIRED",
    "TIMEOUT",
    "JUMP_BALL",
]


# --- Primitives -------------------------------------------------------------


class GridCoord(TypedDict):
    x: float
    y: float


class BallAttached(TypedDict):
    owner_player_id: PlayerId


class BallInFlight(TypedDict):
    from_player_id: PlayerId
    to_player_id: PlayerId
    current_coords: GridCoord


class BallLoose(TypedDict):
    """Ball at rest at coords with no owner. Used between a missed shot and
    the rebound capture (e.g., DREB step start). Discriminated from
    BallInFlight by the absence of `from_player_id` / `to_player_id`."""
    coords: GridCoord


BallState = Union[BallAttached, BallInFlight, BallLoose]


class ClockState(TypedDict):
    clock_remaining: float
    shot_clock_remaining: float


# --- Advance trigger --------------------------------------------------------


class AdvanceTrigger(TypedDict):
    condition: TriggerCondition
    T_game_seconds: float
    metadata: Dict[str, object]
    """Condition-specific extras (e.g. `target_player_id` for
    `ball_reaches_player`, `position` for `player_reaches_position`).
    Loose by design — strictly typing per-condition would explode the
    type system. Tighten later if useful."""


# --- Step start / end -------------------------------------------------------


class StepStart(TypedDict):
    coords: Dict[PlayerId, GridCoord]
    destination: Dict[PlayerId, Optional[GridCoord]]
    action: Dict[PlayerId, PlayerAction]
    archetype: Dict[PlayerId, PlayerArchetype]
    ball: BallState
    clock: ClockState
    advance_trigger: AdvanceTrigger


class NextLinear(TypedDict):
    kind: Literal["next_step"]
    index: int


class NextBranch(TypedDict):
    kind: Literal["branch"]
    outcome: str
    next_step_index: int


class NextTurnStop(TypedDict):
    kind: Literal["turn_stop"]
    event: TurnStopEvent
    payload: Dict[str, object]


NextStep = Union[NextLinear, NextBranch, NextTurnStop]


class StepEnd(TypedDict):
    coords: Dict[PlayerId, GridCoord]
    """Interrupted positions at T. For each player:
    `start.coords + min(rate × T, full_distance)` along start→destination,
    where `rate` derives from player AG × archetype multiplier. Players
    whose movement completes before T sit at their destination."""
    ball: BallState
    time_elapsed: float
    """= advance_trigger.T_game_seconds. Canonical step duration."""
    clock: ClockState
    next: NextStep


class AnimationStep(TypedDict):
    start: StepStart
    end: StepEnd
