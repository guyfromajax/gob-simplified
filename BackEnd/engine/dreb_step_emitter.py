"""DREB animation step emitter.

Produces a single-step `AnimationStep` payload for the DREB turn type
introduced by the SS&S animation refactor (see
`_documentation_master/05_UESS_System/UESS_System.md` §3;
`Rebound_System.md` §DREB).

Design — single-placement-authority model:
- `shot_manager` is the sole authority for post-shot player positions. It
  populates `offense_rebounder_coords`, `defense_rebounder_coords`,
  `offense_getback_coords`, and `defense_release_coords` on the MISS turn,
  and the MISS turn emitter absorbs those into its final step's
  `end.coords`. Sync writes them to `player.coords`.
- The DREB turn animates only the rebound capture itself: the rebounder
  moves from his post-shot position to the bounce coords. Every other
  player holds the position shot_manager assigned. This avoids the
  brittle "two authorities racing via player-id matching" pattern that
  caused release / get-back players to get yanked to the rim cluster.

Algorithm:
- 1 schema step.
- Trigger: `player_reaches_position` (rebounder → ball bounce coords).
- T = rebounder's AG-driven traversal time at `sprint` archetype.
- Rebounder: `cut` + `sprint` → bounce coords.
- Rebound attemptors (`offense_rebounders` + `defense_rebounders` from the
  prior MISS turn, minus captor): `cut` + `standard` → bounce ± (4 x, 6 y).
  (DREB-Task 2 / L-3: `stamp_rebound_capture_player_motion`'s
  `attemptor_archetype` defaults to `standard` and is not overridden here —
  corrected from the earlier "cruise" claim.)
- Everyone else: `stationary` at post-shot coords (get-back / release).
- Ball: BallLoose at bounce → BallAttached(rebounder).
- Next: implicit end for normal capture; turn_stop FOUL for over-the-back.
"""

from typing import Any, Dict, List, Optional

from BackEnd.constants import HCO_STEP_T_FLOOR_GAME_SECONDS
from BackEnd.utils.animation_step_helpers import (
    build_foul_announcement,
    rebound_attemptor_ids,
    stamp_rebound_capture_player_motion,
    stamp_tween_durations,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
)
from BackEnd.utils.shared import calc_ag_segment_seconds


_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]

# Revertible toggle (2026-06-30): the DREB "Rebound!" banner carries hold_ms:1000, which
# freezes the court for a full second at the turn boundary. When the next play is a fast
# break that pause is dead air that delays the break. Suppress the banner (and its hold)
# on DREB→FAST_BREAK only. To restore the old behavior, flip this to False — nothing else
# needs to change. See Announcement_System.md → "Announcements That Carry a Hold".
SUPPRESS_DREB_REBOUND_ANNOUNCE_ON_FAST_BREAK = True


def _player_iter(off_lineup: Dict[str, Any], def_lineup: Dict[str, Any]):
    for pos in _OFFENSE_POSITIONS:
        for lineup in (off_lineup, def_lineup):
            player = lineup.get(pos)
            if player is not None:
                yield player


def _player_id(player) -> Optional[str]:
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


def _find_player_by_id(pid: str, off_lineup: Dict[str, Any], def_lineup: Dict[str, Any]):
    for player in _player_iter(off_lineup, def_lineup):
        if _player_id(player) == pid:
            return player
    return None


def build_dreb_animation_steps(
    rebounder_id: str,
    bounce_coords: GridCoord,
    start_coords: Dict[str, GridCoord],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    clock_remaining: float,
    shot_clock_remaining: float,
    otb_foul: Optional[Dict[str, Any]] = None,
    offense_rebounders: Optional[List[Any]] = None,
    defense_rebounders: Optional[List[Any]] = None,
    away_offense: bool = False,
    next_is_fast_break: bool = False,
) -> Optional[List[AnimationStep]]:
    """Build the DREB turn's single AnimationStep.

    Args:
        rebounder_id: stringified player_id of the captor (already picked
            by the rebound system; not re-resolved here).
        bounce_coords: where the ball is at DREB start.
        start_coords: post-shot positions of all 10 players (i.e., the
            MISS turn's `animation_steps[-1].end.coords`). Keyed by
            stringified player_id. shot_manager is the source of truth
            for these — DREB does not override them for non-rebounders.
        off_lineup, def_lineup: position → Player dicts from the missed-
            shot turn (offensive team = team that just shot, NOT the
            team about to receive the ball).
        clock_remaining, shot_clock_remaining: game-seconds at DREB start.
        otb_foul: if an over-the-back foul fired, dict with `fouler_id`,
            `victim_id`, `foul_team`. None for clean capture.

    Returns:
        [AnimationStep] (single-element list for interface uniformity with
        multi-step emitters), or None if required inputs are missing.
    """
    if not rebounder_id or not bounce_coords or not start_coords:
        return None

    rebounder = _find_player_by_id(rebounder_id, off_lineup, def_lineup)
    if rebounder is None:
        return None
    rebounder_start = start_coords.get(rebounder_id)
    if not rebounder_start:
        return None

    # T = rebounder's traversal time at sprint (gates the step).
    t_game_seconds = max(
        HCO_STEP_T_FLOOR_GAME_SECONDS,
        calc_ag_segment_seconds(
            rebounder_start, bounce_coords, rebounder, archetype="sprint",
        ),
    )

    attemptor_ids = rebound_attemptor_ids(
        offense_rebounders, defense_rebounders, rebounder_id,
    )

    coords_start: Dict[str, GridCoord] = {}
    coords_end: Dict[str, GridCoord] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, str] = {}
    archetypes: Dict[str, str] = {}
    tween_durations: Dict[str, float] = {}

    for player in _player_iter(off_lineup, def_lineup):
        pid = _player_id(player)
        if pid is None:
            continue
        start = start_coords.get(pid)
        if start is None:
            continue
        coords_start[pid] = {"x": float(start["x"]), "y": float(start["y"])}
        coords_end[pid] = dict(coords_start[pid])
        destinations[pid] = None
        actions[pid] = "stationary"
        archetypes[pid] = "stationary"

    stamp_rebound_capture_player_motion(
        start_coords=coords_start,
        end_coords=coords_end,
        destinations=destinations,
        actions=actions,
        archetypes=archetypes,
        tween_durations=tween_durations,
        rebounder_id=str(rebounder_id),
        bounce_coords=bounce_coords,
        attemptor_ids=attemptor_ids,
        step_t=float(t_game_seconds),
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )

    ball_start: BallState = {
        "coords": {"x": float(bounce_coords["x"]), "y": float(bounce_coords["y"])}
    }
    ball_end: BallState = {"owner_player_id": rebounder_id}

    trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t_game_seconds),
        "metadata": {
            "target_player_id": rebounder_id,
            "target_coords": {
                "x": float(bounce_coords["x"]),
                "y": float(bounce_coords["y"]),
            },
        },
    }

    clock_start: ClockState = {
        "clock_remaining": float(clock_remaining),
        "shot_clock_remaining": float(shot_clock_remaining),
    }
    clock_end: ClockState = {
        "clock_remaining": float(clock_remaining) - float(t_game_seconds),
        "shot_clock_remaining": float(shot_clock_remaining) - float(t_game_seconds),
    }

    next_step: NextStep
    if otb_foul:
        next_step = {
            "kind": "turn_stop",
            "event": "FOUL",
            "payload": {
                "foul_type": "non_shooting",
                "over_the_back": True,
                "fouler_id": otb_foul.get("fouler_id"),
                "victim_id": otb_foul.get("victim_id") or rebounder_id,
                "foul_team": otb_foul.get("foul_team"),
            },
        }
    else:
        next_step = {"kind": "next_step", "index": 999}

    if otb_foul:
        # Canonical UESS foul-announcement builder. Stamps meta.sfx="foul"
        # so the whistle fires at overlay mount. Going through the helper
        # is what guarantees the SFX — building this dict by hand is what
        # caused OTB to ship silent originally.
        announcement = build_foul_announcement(
            text="Over The Back!",
            team=(
                otb_foul.get("announcement_team")
                or ("home" if away_offense else "away")
            ),
            fouler_id=otb_foul.get("fouler_id") or rebounder_id,
        )
    elif next_is_fast_break and SUPPRESS_DREB_REBOUND_ANNOUNCE_ON_FAST_BREAK:
        # DREB→FAST_BREAK: suppress the "Rebound!" banner + its 1000ms hold so the break
        # starts immediately (no boundary freeze). Revertible via the module constant.
        # The rebound SFX cue (start.sfx_on_ball_arrival) is unaffected and still fires.
        announcement = None
    else:
        announcement = {
            "text": "Rebound!",
            "team": "home" if away_offense else "away",
            "hold_ms": 1000,
            "style": "primary",
            "player_data": {"playerId": str(rebounder_id)},
        }

    step: AnimationStep = {
        "start": {
            "coords": coords_start,
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": ball_start,
            "clock": clock_start,
            "advance_trigger": trigger,
            # Rebound SFX cue (SFX_System.md → "Rebound SFX").
            # Fires when the ball attaches to the rebounder's sprite, which
            # in the DREB step happens at step-end snap (the ball is
            # already sitting at bounce_coords at step start; only the
            # rebounder moves). FE fires this cue from the step-end snap
            # path when the ball tween early-returns (no ball movement),
            # so the SFX still hits the moment of attach.
            "sfx_on_ball_arrival": {
                "file": "attack-shot-strong.wav",
                "volume": 0.7,
                "event": "rebound_dreb",
            },
        },
        "end": {
            "coords": coords_end,
            "ball": ball_end,
            "time_elapsed": float(t_game_seconds),
            "clock": clock_end,
            # The headline fires AFTER sprites snap to end coords — i.e.,
            # the moment the rebounder visually has the ball. OTB keeps the
            # same rebound movement/attach timing but announces the foul
            # instead of a clean rebound.
            "announcement": announcement,
            "next": next_step,
        },
    }
    if tween_durations:
        step["start"]["tween_durations"] = tween_durations
    return [step]
