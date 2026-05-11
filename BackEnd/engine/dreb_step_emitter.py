"""DREB animation step emitter.

Produces a single-step `AnimationStep` payload for the new DREB turn type
introduced by the SS&S animation refactor (see
`_documentation_master/projects/Animation_System_Updated.md`).

Status: parallel-build infrastructure. The DREB-as-its-own-turn pattern
isn't wired into the backend turn flow yet; this emitter exists so the
turn-flow refactor can call it without further design work. Until then,
DREB is still bundled into the MISS turn the legacy way.

Algorithm:
- 1 schema step (rebound capture).
- Trigger: `player_reaches_position` (rebounder → ball bounce coords).
- T = rebounder's AG-driven traversal time at `sprint` archetype.
- Frontcourt-half x-eligibility filter on which non-rebounder players
  participate. Eligible players get `cut` + `sprint` toward random spots
  near the ball; ineligible players are `stationary`.
- Other players' end coords are *interpolated at time T* — they may not
  reach their destination if their full traversal distance > rate × T.
- Ball state: BallLoose at start (ball at bounce coords, no owner) →
  BallAttached(rebounder) at end.
- Next: implicit end (next_step past array) for normal capture; turn_stop
  FOUL for over-the-back fouls.
"""

import math
import random
from typing import Any, Dict, List, Optional

from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    StepEnd,
    StepStart,
)
from BackEnd.utils.shared import calc_ag_segment_seconds

# Court bounds for clamping random near-bounce targets.
_GRID_MIN_X = 4
_GRID_MAX_X = 97
_GRID_MIN_Y = 5
_GRID_MAX_Y = 45

# Random near-bounce target offset bounds (matches existing animateRebound
# proximity logic in fastBreak / ballManager).
_NEAR_BOUNCE_X_RANGE = 6
_NEAR_BOUNCE_Y_RANGE = 8

_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


# --- Helpers ---------------------------------------------------------------


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


def _is_in_frontcourt(coord: GridCoord, is_away_offense: bool) -> bool:
    """Frontcourt-half x-eligibility filter (matches existing FB rebound logic).

    home offense → frontcourt = x >= 50; away offense → x <= 50.
    """
    if is_away_offense:
        return float(coord["x"]) <= 50.0
    return float(coord["x"]) >= 50.0


def _random_near_bounce(bounce: GridCoord) -> GridCoord:
    """Pick a random spot within ±6x, ±8y of the bounce, clamped to court."""
    tx = max(
        _GRID_MIN_X,
        min(_GRID_MAX_X, bounce["x"] + random.randint(-_NEAR_BOUNCE_X_RANGE, _NEAR_BOUNCE_X_RANGE)),
    )
    ty = max(
        _GRID_MIN_Y,
        min(_GRID_MAX_Y, bounce["y"] + random.randint(-_NEAR_BOUNCE_Y_RANGE, _NEAR_BOUNCE_Y_RANGE)),
    )
    return {"x": float(tx), "y": float(ty)}


def _interpolate_at_time(
    start: GridCoord,
    target: GridCoord,
    player: Any,
    t_seconds: float,
    archetype: str = "sprint",
) -> GridCoord:
    """Compute where a player is at time `t_seconds` along start→target.

    If the player's full traversal time (start to target at the given
    archetype's rate) <= t_seconds, they're at target.
    Otherwise they're at the linear-interpolated point along the path
    based on rate × t_seconds vs full distance.
    """
    full_time = calc_ag_segment_seconds(start, target, player, archetype=archetype)
    if full_time <= 0 or full_time <= t_seconds:
        return {"x": float(target["x"]), "y": float(target["y"])}
    progress = t_seconds / full_time
    return {
        "x": float(start["x"] + (target["x"] - start["x"]) * progress),
        "y": float(start["y"] + (target["y"] - start["y"]) * progress),
    }


# --- Top-level emitter -----------------------------------------------------


def build_dreb_animation_steps(
    rebounder_id: str,
    bounce_coords: GridCoord,
    start_coords: Dict[str, GridCoord],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    clock_remaining: float,
    shot_clock_remaining: float,
    otb_foul: Optional[Dict[str, Any]] = None,
    exempt_player_ids: Optional[set] = None,
) -> Optional[List[AnimationStep]]:
    """Build the DREB turn's single AnimationStep.

    Args:
        rebounder_id: stringified player_id of the captor (already picked
            by the rebound system; not re-resolved here).
        bounce_coords: where the ball is at DREB start.
        start_coords: positions of all 10 players at DREB start. Keyed by
            stringified player_id.
        off_lineup, def_lineup: position → Player dicts (the team mappings
            from the missed-shot turn — i.e., offensive team is the team
            that just took the shot, NOT the team about to receive ball).
        is_away_offense: was the team that took the missed shot the away
            team? Used for the frontcourt-half filter.
        clock_remaining, shot_clock_remaining: game-seconds at DREB start.
        otb_foul: if an over-the-back foul fired, dict with `fouler_id`,
            `victim_id`, `foul_team`. None for clean capture.
        exempt_player_ids: player IDs to keep stationary regardless of the
            frontcourt eligibility filter. Get-back (offensive) and release
            (defensive) players have already taken their post-shot positions
            on the shot step and should NOT participate in the rebound
            sprint; they hold their post-shot spots through the DREB step.

    Returns:
        [AnimationStep] (single-element list for interface uniformity with
        multi-step emitters), or None if required inputs are missing.
    """
    if not rebounder_id or not bounce_coords or not start_coords:
        return None

    exempt_ids: set = {str(pid) for pid in (exempt_player_ids or set()) if pid is not None}

    rebounder = _find_player_by_id(rebounder_id, off_lineup, def_lineup)
    if rebounder is None:
        return None
    rebounder_start = start_coords.get(rebounder_id)
    if not rebounder_start:
        return None

    # T = rebounder's traversal time at sprint archetype. This is the
    # canonical step duration; all other players' end coords are
    # interpolated against this T.
    t_game_seconds = calc_ag_segment_seconds(
        rebounder_start, bounce_coords, rebounder, archetype="sprint"
    )

    coords_start: Dict[str, GridCoord] = {}
    coords_end: Dict[str, GridCoord] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, str] = {}
    archetypes: Dict[str, str] = {}

    for player in _player_iter(off_lineup, def_lineup):
        pid = _player_id(player)
        if pid is None:
            continue
        start = start_coords.get(pid)
        if start is None:
            continue
        coords_start[pid] = {"x": float(start["x"]), "y": float(start["y"])}

        if pid == rebounder_id:
            # Rebounder: cut + sprint to bounce. End = bounce (reaches at T).
            coords_end[pid] = {"x": float(bounce_coords["x"]), "y": float(bounce_coords["y"])}
            destinations[pid] = {"x": float(bounce_coords["x"]), "y": float(bounce_coords["y"])}
            actions[pid] = "cut"
            archetypes[pid] = "sprint"
        elif pid in exempt_ids:
            # Get-back / release players already took their post-shot
            # positions on the prior shot step. They do NOT participate
            # in the rebound sprint regardless of geographic eligibility.
            coords_end[pid] = coords_start[pid]
            destinations[pid] = None
            actions[pid] = "stationary"
            archetypes[pid] = "stationary"
        elif _is_in_frontcourt(coords_start[pid], is_away_offense):
            # Eligible non-rebounder: cut + sprint to a random near-bounce
            # spot. End coord interpolated at time T.
            target = _random_near_bounce(bounce_coords)
            destinations[pid] = target
            actions[pid] = "cut"
            archetypes[pid] = "sprint"
            coords_end[pid] = _interpolate_at_time(
                coords_start[pid], target, player, t_game_seconds, archetype="sprint"
            )
        else:
            # Outside frontcourt: stationary.
            coords_end[pid] = coords_start[pid]
            destinations[pid] = None
            actions[pid] = "stationary"
            archetypes[pid] = "stationary"

    # Ball state: loose at start (ball at bounce coords, no owner) →
    # attached to rebounder at end.
    ball_start: BallState = {
        "coords": {"x": float(bounce_coords["x"]), "y": float(bounce_coords["y"])}
    }
    ball_end: BallState = {"owner_player_id": rebounder_id}

    # Trigger.
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

    # Next pointer.
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
        # Implicit end of turn — next_step pointing past the (1-element)
        # array. `playTurn` will return None and caller transitions to
        # the next turn (HCO or FAST_BREAK based on game state).
        next_step = {"kind": "next_step", "index": 999}

    step: AnimationStep = {
        "start": {
            "coords": coords_start,
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": ball_start,
            "clock": clock_start,
            "advance_trigger": trigger,
        },
        "end": {
            "coords": coords_end,
            "ball": ball_end,
            "time_elapsed": float(t_game_seconds),
            "clock": clock_end,
            "next": next_step,
        },
    }
    return [step]
