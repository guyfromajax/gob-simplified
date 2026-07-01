"""Fast Break attack-drive cutoff + stop resolution (Phase 1 core).

Orchestrates geo cutoff, D8 meet contest, charge, POS_O shimmy path, NEUTRAL
stop decision, and no-meet rim contest. Pure resolver — stamps payload for
UESS emitters; does not mutate game state.

Spec: ``_documentation_master/06_Gameplay_Systems/Fast_Break_System.md``
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.constants.fast_break_constants import (
    FB_DRIVE_CUTOFF_PATH_CORRIDOR,
    FB_DRIVE_CUTOFF_TIME_SLACK,
)
from BackEnd.engine.cutoff_resolution import (
    POSITIONS,
    best_cutoff_on_drive,
    resolve_cutoff_contest,
)
from BackEnd.engine.fb_stop_decision import resolve_fb_stop_decision
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec, _euclid
from BackEnd.utils.fb_geo_helpers import (
    compute_pos_o_shimmy_from_segment,
    pick_nearest_contesting_defender,
    steal_meet_x_ahead_valid,
)
from BackEnd.utils.shared import calculate_charge, get_away_player_coords

GridCoordDict = Dict[str, float]

_TERMINAL_D8 = frozenset({"DEAD BALL", "O_FOUL", "D_FOUL"})
_TERMINAL_CHARGE = frozenset({"CHARGE", "BLOCKING_FOUL"})


def _player_id(player: Any) -> Optional[str]:
    if player is None:
        return None
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


def _clamp_drive_coord(coord: GridCoordDict) -> GridCoordDict:
    return {
        "x": int(max(4, min(97, round(float(coord["x"]))))),
        "y": int(max(1, min(49, round(float(coord["y"]))))),
    }


def _fb_spot_coords(spot: str, *, is_away_offense: bool) -> GridCoordDict:
    coords = dict(HCO_STRING_SPOTS.get(spot, {"x": 50, "y": 25}))
    if is_away_offense:
        coords = get_away_player_coords(coords)
    return {"x": float(coords["x"]), "y": float(coords["y"])}


def _traverse_seconds(
    start: GridCoordDict,
    end: GridCoordDict,
    player: Any,
    archetype: str,
) -> float:
    rate = _ag_grid_per_game_sec(player, archetype)
    dist = _euclid(start, end)
    if rate <= 0:
        return 0.5
    return max(0.1, dist / rate)


def _defender_archetype(player: Any, drift_defender_ids: Set[str]) -> str:
    pid = _player_id(player)
    if pid and pid in drift_defender_ids:
        return "drift"
    return "sprint"


def _build_defender_ends_at_basket(
    def_lineup: Dict[str, Any],
    def_starts: Dict[str, GridCoordDict],
    *,
    is_away_offense: bool,
    stopper_pos: Optional[str] = None,
    meet: Optional[GridCoordDict] = None,
    drift_defender_ids: Optional[Set[str]] = None,
) -> Tuple[Dict[str, GridCoordDict], Dict[str, str]]:
    """Assign stopper to meet; all others sprint to basketSpot."""
    drift_ids = drift_defender_ids or set()
    basket_spot = _fb_spot_coords("basketSpot", is_away_offense=is_away_offense)
    ends: Dict[str, GridCoordDict] = {}
    archetypes: Dict[str, str] = {}
    for pos in POSITIONS:
        defender = def_lineup.get(pos)
        if defender is None or pos not in def_starts:
            continue
        pid = _player_id(defender)
        if not pid:
            continue
        arch = _defender_archetype(defender, drift_ids)
        if pos == stopper_pos and meet is not None:
            ends[pid] = {"x": float(meet["x"]), "y": float(meet["y"])}
        else:
            ends[pid] = dict(basket_spot)
        archetypes[pid] = arch
    return ends, archetypes


def _contest_at_shot(
    defender_ends: Dict[str, GridCoordDict],
    shooter_pos: GridCoordDict,
    *,
    is_away_offense: bool,
) -> Tuple[bool, Optional[str]]:
    return pick_nearest_contesting_defender(
        defender_ends, shooter_pos, is_away_offense=is_away_offense
    )


def _geo_corridor_participants(
    bh_start: GridCoordDict,
    shot_spot: GridCoordDict,
    def_starts: Dict[str, GridCoordDict],
    *,
    corridor: float,
) -> Set[str]:
    """Defender positions within the drive path corridor (for stats)."""
    from BackEnd.engine.cutoff_resolution import _perpendicular_distance_to_segment

    ax, ay = float(bh_start["x"]), float(bh_start["y"])
    bx, by = float(shot_spot["x"]), float(shot_spot["y"])
    ids: Set[str] = set()
    for pos in POSITIONS:
        if pos not in def_starts:
            continue
        dxy = def_starts[pos]
        dist = _perpendicular_distance_to_segment(
            float(dxy["x"]), float(dxy["y"]), ax, ay, bx, by
        )
        if dist <= corridor:
            ids.add(pos)
    return ids


def resolve_fb_drive_step(
    *,
    bh,
    bh_pos: str,
    bh_start: GridCoordDict,
    shot_spot: GridCoordDict,
    off_lineup: Dict[str, Any],
    off_starts: Dict[str, GridCoordDict],
    def_lineup: Dict[str, Any],
    def_starts: Dict[str, GridCoordDict],
    off_team,
    def_team,
    shot_manager=None,
    is_away_offense: bool,
    steal_entry: bool = False,
    excluded_stopper_ids: Optional[Set[str]] = None,
    drift_defender_ids: Optional[Set[str]] = None,
    defense_playcall: str = "man",
) -> Dict[str, Any]:
    """Resolve one FB attack-drive step. Returns ``fb_drive_resolution`` payload."""
    excluded = set(excluded_stopper_ids or [])
    drift_ids = set(drift_defender_ids or [])
    bh_start = _clamp_drive_coord(bh_start)
    shot_spot = _clamp_drive_coord(shot_spot)

    bh_rate = _ag_grid_per_game_sec(bh, "sprint")

    def get_defender_rate(defender):
        arch = _defender_archetype(defender, drift_ids)
        return _ag_grid_per_game_sec(defender, arch)

    filtered_def_starts: Dict[str, GridCoordDict] = {}
    for pos in POSITIONS:
        defender = def_lineup.get(pos)
        if defender is None or pos not in def_starts:
            continue
        pid = _player_id(defender)
        if pid and pid in excluded:
            continue
        filtered_def_starts[pos] = def_starts[pos]

    cutoff_pos, cutoff_meet = best_cutoff_on_drive(
        bh_start,
        shot_spot,
        bh_rate,
        filtered_def_starts,
        def_lineup,
        get_defender_rate=get_defender_rate,
        path_corridor=FB_DRIVE_CUTOFF_PATH_CORRIDOR,
        defender_time_slack=FB_DRIVE_CUTOFF_TIME_SLACK,
        stop_attempt_prob=None,
        clamp_fn=_clamp_drive_coord,
    )

    geo_participant_positions = _geo_corridor_participants(
        bh_start, shot_spot, def_starts, corridor=FB_DRIVE_CUTOFF_PATH_CORRIDOR
    )

    payload: Dict[str, Any] = {
        "bh_id": _player_id(bh),
        "bh_pos": bh_pos,
        "bh_start": dict(bh_start),
        "shot_spot": dict(shot_spot),
        "steal_entry": steal_entry,
        "geo_participant_defender_ids": [],
        "defender_end_coords": {},
        "defender_archetypes": {},
        "bh_path_knots": [dict(bh_start), dict(shot_spot)],
        "stop_decision": None,
        "shot_defender_id": None,
        "contested": False,
        "t_drive_game_seconds": _traverse_seconds(bh_start, shot_spot, bh, "sprint"),
        "advance_trigger": "bh_reaches_shot_spot",
    }

    def _stamp_geo_ids(*extra_player_ids: Optional[str]) -> None:
        ids = []
        for pos in geo_participant_positions:
            d = def_lineup.get(pos)
            pid = _player_id(d)
            if pid:
                ids.append(pid)
        for pid in extra_player_ids:
            if pid and pid not in ids:
                ids.append(pid)
        payload["geo_participant_defender_ids"] = ids

    # --- No geometric meet -------------------------------------------------
    if cutoff_pos is None or cutoff_meet is None:
        payload["outcome"] = "NO_MEET"
        ends, arch = _build_defender_ends_at_basket(
            def_lineup,
            def_starts,
            is_away_offense=is_away_offense,
            drift_defender_ids=drift_ids,
        )
        payload["defender_end_coords"] = ends
        payload["defender_archetypes"] = arch
        contested, shot_def_id = _contest_at_shot(ends, shot_spot, is_away_offense=is_away_offense)
        payload["contested"] = contested
        payload["shot_defender_id"] = shot_def_id
        _stamp_geo_ids(shot_def_id)
        return payload

    meet = _clamp_drive_coord(cutoff_meet)
    stopper = def_lineup.get(cutoff_pos)
    stopper_id = _player_id(stopper)

    if steal_entry and not steal_meet_x_ahead_valid(meet, bh_start, is_away_offense=is_away_offense):
        payload["outcome"] = "NO_MEET"
        payload["steal_meet_rejected"] = True
        ends, arch = _build_defender_ends_at_basket(
            def_lineup,
            def_starts,
            is_away_offense=is_away_offense,
            drift_defender_ids=drift_ids,
        )
        payload["defender_end_coords"] = ends
        payload["defender_archetypes"] = arch
        contested, shot_def_id = _contest_at_shot(ends, shot_spot, is_away_offense=is_away_offense)
        payload["contested"] = contested
        payload["shot_defender_id"] = shot_def_id
        _stamp_geo_ids(shot_def_id)
        return payload

    payload["meet_x"] = float(meet["x"])
    payload["meet_y"] = float(meet["y"])
    payload["stopper_id"] = stopper_id
    payload["stopper_pos"] = cutoff_pos

    d8_outcome, _ratio, credited = resolve_cutoff_contest(
        off_team,
        def_team,
        bh,
        stopper,
        exclude_steal=True,
    )
    payload["d8_outcome"] = d8_outcome
    payload["d8_credited_player_id"] = _player_id(credited)

    if d8_outcome in _TERMINAL_D8:
        payload["outcome"] = d8_outcome
        ends, arch = _build_defender_ends_at_basket(
            def_lineup,
            def_starts,
            is_away_offense=is_away_offense,
            stopper_pos=cutoff_pos,
            meet=meet,
            drift_defender_ids=drift_ids,
        )
        payload["defender_end_coords"] = ends
        payload["defender_archetypes"] = arch
        stopper_arch = arch.get(stopper_id, "sprint")
        payload["t_drive_game_seconds"] = max(
            _traverse_seconds(bh_start, meet, bh, "sprint"),
            _traverse_seconds(def_starts[cutoff_pos], meet, stopper, stopper_arch),
        )
        _stamp_geo_ids(stopper_id)
        return payload

    charge_outcome = calculate_charge(bh, stopper, off_team, def_team)
    if charge_outcome in _TERMINAL_CHARGE:
        payload["outcome"] = charge_outcome
        ends, arch = _build_defender_ends_at_basket(
            def_lineup,
            def_starts,
            is_away_offense=is_away_offense,
            stopper_pos=cutoff_pos,
            meet=meet,
            drift_defender_ids=drift_ids,
        )
        payload["defender_end_coords"] = ends
        payload["defender_archetypes"] = arch
        stopper_arch = arch.get(stopper_id, "sprint")
        payload["t_drive_game_seconds"] = max(
            _traverse_seconds(bh_start, meet, bh, "sprint"),
            _traverse_seconds(def_starts[cutoff_pos], meet, stopper, stopper_arch),
        )
        _stamp_geo_ids(stopper_id)
        return payload

    ends, arch = _build_defender_ends_at_basket(
        def_lineup,
        def_starts,
        is_away_offense=is_away_offense,
        stopper_pos=cutoff_pos,
        meet=meet,
        drift_defender_ids=drift_ids,
    )
    payload["defender_end_coords"] = ends
    payload["defender_archetypes"] = arch

    t_bh = _traverse_seconds(bh_start, meet, bh, "sprint")
    t_stop = _traverse_seconds(
        def_starts[cutoff_pos], meet, stopper, arch.get(stopper_id, "sprint")
    )
    payload["t_meet_game_seconds"] = max(t_bh, t_stop)

    if d8_outcome == "POS_O":
        stopper_at_meet = {"x": float(meet["x"]), "y": float(meet["y"])}
        shimmy = compute_pos_o_shimmy_from_segment(meet, stopper_at_meet, bh_start)
        payload["outcome"] = "POS_O"
        payload["shimmy"] = shimmy
        payload["bh_path_knots"] = [
            dict(bh_start),
            dict(meet),
            dict(shimmy),
            dict(shot_spot),
        ]
        t_shimmy = _traverse_seconds(meet, shimmy, bh, "sprint")
        t_rim = _traverse_seconds(shimmy, shot_spot, bh, "sprint")
        payload["t_drive_game_seconds"] = t_bh + t_shimmy + t_rim
        payload["path_segment_game_seconds"] = [t_bh, t_shimmy, t_rim]
        contested, shot_def_id = _contest_at_shot(ends, shot_spot, is_away_offense=is_away_offense)
        payload["contested"] = contested
        payload["shot_defender_id"] = shot_def_id
        _stamp_geo_ids(stopper_id, shot_def_id)
        return payload

    # NEUTRAL — dynamic stop decision (two schema steps in emitters)
    payload["outcome"] = "NEUTRAL"
    payload["t_drive_game_seconds"] = payload["t_meet_game_seconds"]
    payload["advance_trigger"] = "meet_reached"

    if shot_manager is not None:
        payload["stop_decision"] = resolve_fb_stop_decision(
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
        if payload["stop_decision"]["action"] == "shoot":
            payload["contested"] = True
            payload["shot_defender_id"] = stopper_id
    _stamp_geo_ids(stopper_id)
    return payload
