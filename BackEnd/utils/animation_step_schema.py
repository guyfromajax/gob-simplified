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
    "post_up",
]
"""Semantic role a player performs during the step. Drives renderer
behavior (sprite frames, ball events). Orthogonal to archetype."""

PlayerArchetype = Literal[
    "default",
    "sprint",
    "burst",
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


class Announcement(TypedDict, total=False):
    """In-step announcement with mandatory pause-the-world behavior. Optional
    field on StepStart (plays before step tweens fire) or StepEnd (plays
    after step tweens complete and sprites snap). Playback engine pauses
    `gameClock` and `shotClock`, calls the announcement system, awaits the
    hold duration, then resumes clocks.
    """

    text: str
    """Announcement copy (e.g. ``"Nice Stop!"``, ``"Trap!"``)."""

    team: str
    """``"home"`` / ``"away"`` / ``"defense"`` / ``"neutral"``."""

    player_data: Optional[Dict[str, object]]
    """Optional headshot card payload: ``{player_id, photo, team_name, ...}``."""

    meta: Optional[Dict[str, object]]
    """Optional extras: ``{decision_pill_text?, decision_pill_tone?, sfx?}``."""

    hold_ms: float
    """Wall-clock duration to keep the world paused (default 1000)."""

    style: Literal["primary", "secondary"]
    """Optional. ``"primary"`` (default — large centered banner via
    ``showAnnouncement``) or ``"secondary"`` (compact side banner via
    ``showSecondaryAnnouncement``). Explicit routing signal — replaces the
    legacy text-string sniffing in the playback engine. Absent → ``"primary"``."""


# --- Step start / end -------------------------------------------------------


class StepStart(TypedDict, total=False):
    coords: Dict[PlayerId, GridCoord]
    destination: Dict[PlayerId, Optional[GridCoord]]
    action: Dict[PlayerId, PlayerAction]
    archetype: Dict[PlayerId, PlayerArchetype]
    ball: BallState
    clock: ClockState
    advance_trigger: AdvanceTrigger
    announcement: Announcement
    """Optional. When present, playback engine pauses clocks, shows the
    announcement, awaits ``hold_ms``, then resumes clocks BEFORE spawning
    the step's tweens. Used for entry-of-turn announcements like
    ``"Trap!"`` / ``"Fast Break!"``."""

    tween_durations: Dict[PlayerId, float]
    """Optional. Per-player tween duration in **game-seconds**. When present,
    the playback engine tweens each player for their individual duration
    (typically ``min(natural_distance / player_rate, step_T)``); players who
    finish before step T idle at their end coord until the step's clock
    elapses. When absent for a player (or when this field is missing
    entirely), the playback engine falls back to the step's total T —
    which stretches fast-finishing players' tweens over T, producing the
    visible "lazy drift" anti-pattern we want to avoid.

    Backend stamps this when it has per-player rate info (which is always —
    AG + archetype determine rate). Frontend never recomputes."""


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


class StepEnd(TypedDict, total=False):
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
    announcement: Announcement
    """Optional. When present, playback engine snaps sprites to end coords,
    pauses clocks, shows the announcement, awaits ``hold_ms``, then resumes
    clocks BEFORE returning ``next``. Used for mid-turn announcements like
    ``"Nice Stop!"`` that play after a movement beat completes."""


class AnimationStep(TypedDict):
    start: StepStart
    end: StepEnd
