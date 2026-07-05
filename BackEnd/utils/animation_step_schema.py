"""Animation step schema — canonical types for the unified animation system.

See `_documentation_master/05_UESS_System/UESS_System.md` §3 for the
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

from typing import Dict, List, Literal, Optional, TypedDict, Union

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
    "sprint",
    "burst",
    "standard",
    "shot_motion",
    "cruise",
    "drift",
    "stationary",
]
"""Movement-rate selector. Multiplied with the player AG curve to produce
grid/game-second rate. Orthogonal to action — the same action may run at
different archetypes (e.g. relaxed `cut` vs. fast-break `cut`)."""

TriggerCondition = Literal[
    "fixed_duration",
    "ball_reaches_player",
    "player_reaches_position",
    "offense_players_reach_position",
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


class StepSfx(TypedDict, total=False):
    """Backend-resolved SFX cue. Frontend plays the named file at the
    appropriate ball-motion moment (release / arrival) — no FE-side decision
    logic. ``file`` is the asset filename (e.g. ``"pass-medium.wav"``);
    ``volume`` defaults to 0.7 if omitted; ``event`` is a debug/telemetry
    tag forwarded to ``playGameSfx``."""

    file: str
    volume: float
    event: str


class TimedSfx(TypedDict, total=False):
    """Backend-resolved SFX cue with an explicit wall-clock offset relative to
    the step's start. The FE schedules a ``setTimeout``-style fire at
    ``delay_ms`` and plays ``file``. Used for variant-specific follow-up
    cues that overlap the next sub-step's motion (e.g. BANK_MAKE: swish.wav
    100 ms after bb-rim-swish; BACK_OF_RIM make: swish.wav 150 ms after
    back-of-rim.wav). Multiple cues per step are supported."""

    file: str
    delay_ms: float
    volume: float
    event: str


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

    style: Literal["primary", "secondary", "and_one", "shooting_foul"]
    """Optional. ``"primary"`` (default — large centered banner via
    ``showAnnouncement``) or ``"secondary"`` (compact side banner via
    ``showSecondaryAnnouncement``). ``"and_one"`` → foul card with shooter +
    fouler. ``"shooting_foul"`` → ``FOUL_SHOOTING`` dispatcher + whistle.
    Absent → ``"primary"``."""


class Flourish(TypedDict, total=False):
    """In-place character "micro-movement" rendered by the FE in RENDER SPACE
    only — it never mutates the player's gameplay grid coords (cf. the arrival
    heartbeat). The backend names the flourish + optional params; the FE owns
    the visual vocabulary and supplies defaults (see ``animation_config.js``
    ``flourish`` block) for any field omitted here.

    First shipped: ``"reach_in"`` — an on-ball defender's reach-in steal
    attempt on a Dynamic-HCT contest moment (stamped per pressure/trap moment,
    regardless of outcome). The other kinds are accepted-but-unrendered
    placeholders for now.
    """

    kind: Literal[
        "reach_in", "pump_fake", "bite", "gather",
        "rattle", "shot_dip", "dribble", "pickup", "dunk", "fumble",
    ]
    amplitude_grid: float
    """Lunge distance in GRID units (converted to px + rendered, NOT gameplay).
    Omitted → FE default."""
    duration_ms: float
    """Wall-clock out-and-back duration. Omitted → FE default."""
    ease: str
    """Phaser ease, e.g. ``"Back.easeOut"``. Omitted → FE default."""
    target: Literal["ball", "rim", "x", "y"]
    """What the motion points at. ``"reach_in"`` uses ``"ball"``."""
    cycles: int
    """Oscillation count (``"rattle"``); ignored by other kinds."""
    mag_px: float
    """Render-space stumble amplitude (``"fumble"``). Omitted → FE default."""
    freq_hz: float
    """Stumble oscillation rate (``"fumble"``). Omitted → FE default."""
    rim_unit_x: float
    """Toward-rim unit vector x (display orientation, ``"fumble"``)."""
    rim_unit_y: float
    """Toward-rim unit vector y (display orientation, ``"fumble"``)."""
    perp_x: float
    """Rim-perpendicular unit vector x (``"fumble"``)."""
    perp_y: float
    """Rim-perpendicular unit vector y (``"fumble"``)."""


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

    ball_motion_style: Literal["shot", "pass"]
    """Optional. Overrides the ball's tween duration for this step. Without
    this field, the ball tweens over the step's total T (gating on slowest
    mover).

    Values:
      - ``"shot"`` — shot ball rate (~16 grid/game-sec). Used for the HCO
        [ball_flight] sub-step (shot arc) and any other case where the ball
        moves at shot speed regardless of step T (e.g., BIP step 1). Slower
        than passes by design — shooters are deliberate, passes are
        quick-twitch.
      - ``"pass"`` — half-court pass rate (30 grid/game-sec). Used by HCO
        mid-skeleton pass steps so the ball renders at the canonical pass
        speed even when step T is gated by the slowest player (and would
        otherwise drag the ball below 24).

    Paired field for ``"pass"``: ``ball_arrival_coord`` (see below). On
    pass tween completion the FE re-attaches the ball to ``step.end.ball``'s
    owner so the ball moves with them for the remainder of step T."""

    ball_arrival_coord: GridCoord
    """Optional. Overrides where the ball's tween terminates (the
    pixel/grid target the FE tweens toward). Without this field, the ball
    tweens to the coord derived from ``step.end.ball`` (i.e., the
    end-state owner's step-end position).

    Used by HCO mid-skeleton pass steps so the ball lands on the
    *receiver's position at ball-arrival time* (= meet-point computed
    from the receiver's archetype rate vs. the 30 grid/game-sec pass
    rate) rather than the receiver's step-end coord — critical when the
    receiver is still moving during the pass (e.g., catching while
    cutting). Backend pre-resolves the meet-point; FE consumes it
    without recomputing."""

    pass_grid_per_game_second: float
    """Optional. When ``ball_motion_style="pass"``, the FE ball tween uses
    this grid/game-sec rate instead of the HCO default (24). FB lane-pass
    steps stamp 40 (sharp) or 30 (sloppy) from the backend pass-quality roll."""

    sfx_on_step_start: StepSfx
    """Optional. SFX cue fired at the START of step processing in the FE
    (``playAnimationStep``), BEFORE any tween / ball motion and independent
    of the ball. Distinct from ``sfx_on_ball_release`` (which is occupied by
    the shot/pass launch sound). Used by Dynamic HCO Motion to fire the
    hot-read coach VO as the break begins. See SFX_System.md."""

    sfx_on_ball_release: StepSfx
    """Optional. SFX cue fired at the moment the ball detaches from its
    start-owner (= start of the ball tween in the FE). Used for pass
    release SFX (``pass-{tier}.wav``) on HCO mid-skeleton pass steps;
    backend picks the tier from the passer's PS attribute. Generic
    mechanism — can layer on any step where the ball detaches."""

    sfx_on_ball_arrival: StepSfx
    """Optional. SFX cue fired at the moment the ball arrives at its
    destination (= ball tween onComplete in the FE). Used for reception
    SFX (``receive-{tier}.wav``) on HCO mid-skeleton pass steps;
    backend picks the tier from the receiver's (IQ + CH). Generic
    mechanism — can layer on any step where the ball arrives at a
    target."""

    timed_sfx: List[TimedSfx]
    """Optional. Ordered list of SFX cues fired at explicit offsets from
    step start. Each cue runs independently of ball motion (the FE schedules
    a ``setTimeout`` for each). Used for variant-specific follow-up cues
    that overlap the next sub-step's motion (BANK_MAKE swish at 100 ms,
    BACK_OF_RIM make swish at 150 ms). Empty / absent → no extra cues."""

    flourish: Dict[PlayerId, Flourish]
    """Optional. Per-player in-place micro-movements rendered in RENDER SPACE
    only (never mutates gameplay coords). The FE fires these fire-and-forget
    in PARALLEL with the step's player tweens — they do not gate step T or the
    turn boundary. See ``Flourish`` above. First use: defender ``reach_in`` on
    Dynamic-HCT steal contest moments."""


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
