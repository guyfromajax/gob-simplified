"""Fast Break NEUTRAL stop decision (pass → shoot → HCO + read gate).

Spec: ``_documentation_master/06_Gameplay_Systems/Fast_Break_System.md``
(section FB Drive Cutoff & Stop Decision — Dynamic stop decision).
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional, Tuple

from BackEnd.constants.shot_threshold_scale import MID as SHOT_THRESHOLD_MID
from BackEnd.engine.attack_drive_clearance import ATTACK_DRIVE_INSIDE_RADIUS
from BackEnd.engine.dynamic_hct import (
    ABA_READ_MID_THRESHOLD,
    GOAL_ACHIEVEMENT_READ_THRESHOLD,
    _player_read,
)
from BackEnd.utils.fb_geo_helpers import (
    attacking_basket_coord,
    euclidean_to_basket,
    fb_pass_receiver_geo_eligible,
    fb_shoot_geo_eligible,
)

GridCoordDict = Dict[str, float]
POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player_id(player: Any) -> Optional[str]:
    if player is None:
        return None
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


def _stop_shoot_type(meet: GridCoordDict, *, is_away_offense: bool) -> str:
    if euclidean_to_basket(meet, is_away_offense=is_away_offense) <= ATTACK_DRIVE_INSIDE_RADIUS:
        return "inside"
    return "outside"


def _closest_pass_receiver(
    bh_pos: str,
    off_lineup: Dict[str, Any],
    off_starts: Dict[str, GridCoordDict],
    *,
    is_away_offense: bool,
) -> Tuple[Optional[str], Optional[Any]]:
    """Closest eligible teammate to the attacking basket."""
    best_pos: Optional[str] = None
    best_player: Optional[Any] = None
    best_dist = float("inf")
    for pos in POSITIONS:
        if pos == bh_pos:
            continue
        player = off_lineup.get(pos)
        if player is None or pos not in off_starts:
            continue
        attrs = getattr(player, "attributes", None) or {}
        if float(attrs.get("SH", 0) or 0) <= 49:
            continue
        coord = off_starts[pos]
        if not fb_pass_receiver_geo_eligible(coord, is_away_offense=is_away_offense):
            continue
        dist = euclidean_to_basket(coord, is_away_offense=is_away_offense)
        if dist < best_dist:
            best_dist = dist
            best_pos = pos
            best_player = player
    return best_pos, best_player


def _shoot_eligible_at_meet(meet: GridCoordDict, *, is_away_offense: bool) -> bool:
    return fb_shoot_geo_eligible(meet, is_away_offense=is_away_offense)


def _compute_optimal_action(
    bh,
    meet: GridCoordDict,
    stopper,
    off_lineup: Dict[str, Any],
    off_starts: Dict[str, GridCoordDict],
    off_team,
    shot_manager,
    *,
    is_away_offense: bool,
    bh_pos: str,
    defense_playcall: str = "man",
) -> Tuple[str, Optional[str], Optional[Any], Optional[str], Optional[float], Optional[float]]:
    """Return (action, receiver_pos, receiver, shot_type, shot_score, shot_threshold)."""
    recv_pos, recv_player = _closest_pass_receiver(
        bh_pos, off_lineup, off_starts, is_away_offense=is_away_offense
    )
    if recv_player is not None:
        return "pass", recv_pos, recv_player, None, None, None

    if not _shoot_eligible_at_meet(meet, is_away_offense=is_away_offense):
        return "HCO", None, None, None, None, None

    shot_type = _stop_shoot_type(meet, is_away_offense=is_away_offense)
    is_paint = shot_type == "inside"
    (
        shot_score,
        _pre,
        _sfx,
        _d_foul,
        _foul_player,
        _raw,
    ) = shot_manager.calculate_shot_score(
        bh,
        None,
        None,
        stopper,
        shot_type,
        defense_playcall,
        False,
        is_paint,
        None,
        meet,
        apply_defense=True,
    )
    shot_threshold = float((off_team.team_attributes or {}).get("shot_threshold", SHOT_THRESHOLD_MID))
    if shot_score >= shot_threshold:
        return "shoot", None, None, shot_type, float(shot_score), shot_threshold
    return "HCO", None, None, None, float(shot_score), shot_threshold


def _random_geo_valid_action(
    bh,
    meet: GridCoordDict,
    stopper,
    off_lineup: Dict[str, Any],
    off_starts: Dict[str, GridCoordDict],
    off_team,
    shot_manager,
    *,
    is_away_offense: bool,
    bh_pos: str,
    defense_playcall: str,
    rng,
) -> Tuple[str, Optional[str], Optional[Any], Optional[str], Optional[float], Optional[float]]:
    pool = ["HCO"]
    recv_pos, recv_player = _closest_pass_receiver(
        bh_pos, off_lineup, off_starts, is_away_offense=is_away_offense
    )
    if recv_player is not None:
        pool.append("pass")
    if _shoot_eligible_at_meet(meet, is_away_offense=is_away_offense):
        pool.append("shoot")

    choice = rng.choice(pool)
    if choice == "pass":
        return "pass", recv_pos, recv_player, None, None, None
    if choice == "HCO":
        return "HCO", None, None, None, None, None

    shot_type = _stop_shoot_type(meet, is_away_offense=is_away_offense)
    is_paint = shot_type == "inside"
    (
        shot_score,
        _pre,
        _sfx,
        _d_foul,
        _foul_player,
        _raw,
    ) = shot_manager.calculate_shot_score(
        bh,
        None,
        None,
        stopper,
        shot_type,
        defense_playcall,
        False,
        is_paint,
        None,
        meet,
        apply_defense=True,
    )
    shot_threshold = float((off_team.team_attributes or {}).get("shot_threshold", SHOT_THRESHOLD_MID))
    return "shoot", None, None, shot_type, float(shot_score), shot_threshold


def resolve_fb_stop_decision(
    bh,
    meet: GridCoordDict,
    stopper,
    off_lineup: Dict[str, Any],
    off_starts: Dict[str, GridCoordDict],
    off_team,
    shot_manager,
    *,
    is_away_offense: bool,
    bh_pos: str = "PG",
    defense_playcall: str = "man",
    read_score: Optional[int] = None,
    rng=None,
) -> Dict[str, Any]:
    """Resolve NEUTRAL hold-up: optimal tree gated by BH read (200 / 125)."""
    if rng is None:
        rng = random
    read = int(read_score if read_score is not None else _player_read(bh))

    optimal_action, recv_pos, recv_player, shot_type, shot_score, shot_threshold = (
        _compute_optimal_action(
            bh,
            meet,
            stopper,
            off_lineup,
            off_starts,
            off_team,
            shot_manager,
            is_away_offense=is_away_offense,
            bh_pos=bh_pos,
            defense_playcall=defense_playcall,
        )
    )

    if read > GOAL_ACHIEVEMENT_READ_THRESHOLD:
        action = optimal_action
        action_source = "optimal"
    elif read > ABA_READ_MID_THRESHOLD:
        action = "HCO"
        action_source = "safe_read"
    else:
        action, recv_pos, recv_player, shot_type, shot_score, shot_threshold = (
            _random_geo_valid_action(
                bh,
                meet,
                stopper,
                off_lineup,
                off_starts,
                off_team,
                shot_manager,
                is_away_offense=is_away_offense,
                bh_pos=bh_pos,
                defense_playcall=defense_playcall,
                rng=rng,
            )
        )
        action_source = "random_geo"

    contested = action == "shoot"
    return {
        "action": action,
        "receiver_pos": recv_pos,
        "receiver_id": _player_id(recv_player),
        "shot_type": shot_type,
        "shot_score": shot_score,
        "shot_threshold": shot_threshold,
        "contested": contested,
        "read_score": read,
        "optimal_action": optimal_action,
        "action_source": action_source,
        "meet": dict(meet),
        "basket_coord": attacking_basket_coord(is_away_offense=is_away_offense),
    }
