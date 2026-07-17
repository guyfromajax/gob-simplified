"""Fast Break attack-drive cutoff + stop resolution (Phase 1 core).

Orchestrates geo cutoff, D8 meet contest, charge, POS_O shimmy path, NEUTRAL
stop decision, and no-meet rim contest. Pure resolver — stamps payload for
UESS emitters; does not mutate game state.

Spec: ``_documentation_master/06_Gameplay_Systems/Fast_Break_System.md``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

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

# Charge / blocking-foul is only read near the attacking basket. The meet must
# be at least this far downcourt: x >= 64 for home offense (attacking high x),
# x <= 37 for away offense (attacking low x, mirrored).
_CHARGE_READ_MIN_X_HOME = 64.0
_CHARGE_READ_MAX_X_AWAY = 37.0


def _charge_read_in_play(meet_x: float, *, is_away_offense: bool) -> bool:
    """Charge/block is only live when the meet is near the attacking basket."""
    if is_away_offense:
        return meet_x <= _CHARGE_READ_MAX_X_AWAY
    return meet_x >= _CHARGE_READ_MIN_X_HOME


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


def _reachable_defender_ends(
    ends: Dict[str, GridCoordDict],
    *,
    def_lineup: Dict[str, Any],
    def_starts: Dict[str, GridCoordDict],
    archetypes: Dict[str, str],
    time_budget: Optional[float],
    stopper_pos: Optional[str] = None,
) -> Dict[str, GridCoordDict]:
    """Clamp each non-stopper defender's sprint-to-basket end to what he can
    actually reach in ``time_budget`` game-seconds.

    ``_build_defender_ends_at_basket`` optimistically drops every non-stopper
    defender onto the rim. Downstream rebound selection
    (``_resolve_rebound_on_miss`` → ``determine_rebounder``) and shot-contest
    selection (``_contest_at_shot``) then treat a defender who never got back
    as if he's standing under the basket — so a player who renders far away can
    win the board or be designated the contester (which also feeds a closeout
    jet). Interrupting each defender at his archetype rate × ``time_budget``
    makes the selection geometry match what the animation actually renders. The
    stopper (who by construction reaches the meet) is left untouched.
    """
    if not time_budget or time_budget <= 0:
        return ends
    from BackEnd.utils.animation_step_helpers import (
        _ag_grid_per_game_sec,
        _motion_end_toward_dest,
    )

    clamped = dict(ends)
    for pos in POSITIONS:
        if pos == stopper_pos:
            continue
        defender = def_lineup.get(pos)
        if defender is None or pos not in def_starts:
            continue
        pid = _player_id(defender)
        if not pid or pid not in clamped:
            continue
        rate = _ag_grid_per_game_sec(defender, archetypes.get(pid, "sprint"))
        new_end, _ = _motion_end_toward_dest(
            def_starts[pos], clamped[pid], rate, float(time_budget)
        )
        clamped[pid] = new_end
    return clamped


def _contest_at_shot(
    defender_ends: Dict[str, GridCoordDict],
    shooter_pos: GridCoordDict,
    *,
    is_away_offense: bool,
) -> Tuple[bool, Optional[str]]:
    return pick_nearest_contesting_defender(
        defender_ends, shooter_pos, is_away_offense=is_away_offense
    )


def _stamp_rendered_defender_ends(
    payload: Dict[str, Any],
    *,
    off_lineup: Dict[str, Any],
    off_starts: Dict[str, GridCoordDict],
    def_lineup: Dict[str, Any],
    def_starts: Dict[str, GridCoordDict],
    bh_start: GridCoordDict,
    bh_end: GridCoordDict,
    is_away_offense: bool,
) -> Dict[str, GridCoordDict]:
    """Author the coordinated transition spread the emitter will RENDER (via the
    shared ``author_transition_end_coords`` planner) and stamp the defender ends
    onto ``payload["rendered_defender_end_coords"]``. RNG-isolated inside
    ``fb_rendered_defender_ends`` (the rendered contester is deterministic) so
    ``resolve_shot``'s make/miss is byte-identical. Non-mutating w.r.t.
    ``payload["defender_end_coords"]`` (emitter crash budget + rebound path).
    """
    from BackEnd.engine.rendered_contest import fb_rendered_defender_ends

    off_by_id: Dict[str, GridCoordDict] = {}
    def_by_id: Dict[str, GridCoordDict] = {}
    for pos in POSITIONS:
        opid = _player_id(off_lineup.get(pos))
        if opid and pos in off_starts:
            off_by_id[opid] = dict(off_starts[pos])
        dpid = _player_id(def_lineup.get(pos))
        if dpid and pos in def_starts:
            def_by_id[dpid] = dict(def_starts[pos])

    bh_id = payload.get("bh_id")
    if bh_id and bh_id in off_by_id:
        off_by_id[bh_id] = dict(bh_start)  # match the emitter's bh_start override

    rendered = fb_rendered_defender_ends(
        turn_result={
            "stop_decision_action": (payload.get("stop_decision") or {}).get("action")
        },
        fb_drive=payload,
        stealer_id=bh_id,
        off_start_by_id=off_by_id,
        def_start_by_id=def_by_id,
        bh_start=dict(bh_start),
        bh_end=dict(bh_end),
        is_away_offense=is_away_offense,
    )
    payload["rendered_defender_end_coords"] = rendered
    return rendered


def _apply_rendered_spread_contest(
    payload: Dict[str, Any],
    *,
    off_lineup: Dict[str, Any],
    off_starts: Dict[str, GridCoordDict],
    def_lineup: Dict[str, Any],
    def_starts: Dict[str, GridCoordDict],
    bh_start: GridCoordDict,
    shot_spot: GridCoordDict,
    is_away_offense: bool,
) -> Tuple[bool, Optional[str]]:
    """Rim-finish contest: re-derive ``contested`` / ``shot_defender_id`` from the
    RENDERED transition spread instead of the ``basketSpot`` sprint-clamp — the
    UESS single-coord-source fix. ``bh_end == shot_spot`` for a rim finish.
    """
    rendered = _stamp_rendered_defender_ends(
        payload,
        off_lineup=off_lineup,
        off_starts=off_starts,
        def_lineup=def_lineup,
        def_starts=def_starts,
        bh_start=bh_start,
        bh_end=shot_spot,  # rim finish: bh_end == shot spot
        is_away_offense=is_away_offense,
    )
    contested, shot_def_id = _contest_at_shot(
        rendered, shot_spot, is_away_offense=is_away_offense
    )
    payload["contested"] = contested
    payload["shot_defender_id"] = shot_def_id
    return contested, shot_def_id


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

    def _no_meet_payload(*, steal_meet_rejected: bool = False) -> Dict[str, Any]:
        payload["outcome"] = "NO_MEET"
        if steal_meet_rejected:
            payload["steal_meet_rejected"] = True
        ends, arch = _build_defender_ends_at_basket(
            def_lineup,
            def_starts,
            is_away_offense=is_away_offense,
            drift_defender_ids=drift_ids,
        )
        ends = _reachable_defender_ends(
            ends,
            def_lineup=def_lineup,
            def_starts=def_starts,
            archetypes=arch,
            time_budget=payload["t_drive_game_seconds"],
        )
        payload["defender_end_coords"] = ends
        payload["defender_archetypes"] = arch
        _, shot_def_id = _apply_rendered_spread_contest(
            payload,
            off_lineup=off_lineup,
            off_starts=off_starts,
            def_lineup=def_lineup,
            def_starts=def_starts,
            bh_start=bh_start,
            shot_spot=shot_spot,
            is_away_offense=is_away_offense,
        )
        _stamp_geo_ids(shot_def_id)
        return payload

    # Pick earliest cutoff; for after-steal, skip meets that fail the x-ahead
    # filter and try the next-soonest defender until one is valid or none remain.
    steal_meet_rejected_any = False
    cutoff_pos: Optional[str] = None
    cutoff_meet: Optional[GridCoordDict] = None
    skip_ids = set(excluded)
    while True:
        filtered_def_starts: Dict[str, GridCoordDict] = {}
        for pos in POSITIONS:
            defender = def_lineup.get(pos)
            if defender is None or pos not in def_starts:
                continue
            pid = _player_id(defender)
            if pid and pid in skip_ids:
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
        if cutoff_pos is None or cutoff_meet is None:
            return _no_meet_payload(steal_meet_rejected=steal_meet_rejected_any)

        meet = _clamp_drive_coord(cutoff_meet)
        stopper = def_lineup.get(cutoff_pos)
        stopper_id = _player_id(stopper)
        if (
            steal_entry
            and not steal_meet_x_ahead_valid(
                meet, bh_start, is_away_offense=is_away_offense
            )
        ):
            steal_meet_rejected_any = True
            if stopper_id:
                skip_ids.add(stopper_id)
            else:
                return _no_meet_payload(steal_meet_rejected=True)
            continue
        break

    payload["meet_x"] = float(meet["x"])
    payload["meet_y"] = float(meet["y"])
    payload["stopper_id"] = stopper_id
    payload["stopper_pos"] = cutoff_pos
    if steal_meet_rejected_any:
        payload["steal_meet_rejected"] = True

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
        stopper_arch = arch.get(stopper_id, "sprint")
        payload["t_drive_game_seconds"] = max(
            _traverse_seconds(bh_start, meet, bh, "sprint"),
            _traverse_seconds(def_starts[cutoff_pos], meet, stopper, stopper_arch),
        )
        ends = _reachable_defender_ends(
            ends,
            def_lineup=def_lineup,
            def_starts=def_starts,
            archetypes=arch,
            time_budget=payload["t_drive_game_seconds"],
            stopper_pos=cutoff_pos,
        )
        payload["defender_end_coords"] = ends
        payload["defender_archetypes"] = arch
        _stamp_geo_ids(stopper_id)
        return payload

    charge_outcome = (
        calculate_charge(bh, stopper, off_team, def_team)
        if _charge_read_in_play(float(meet["x"]), is_away_offense=is_away_offense)
        else None
    )
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
        stopper_arch = arch.get(stopper_id, "sprint")
        payload["t_drive_game_seconds"] = max(
            _traverse_seconds(bh_start, meet, bh, "sprint"),
            _traverse_seconds(def_starts[cutoff_pos], meet, stopper, stopper_arch),
        )
        ends = _reachable_defender_ends(
            ends,
            def_lineup=def_lineup,
            def_starts=def_starts,
            archetypes=arch,
            time_budget=payload["t_drive_game_seconds"],
            stopper_pos=cutoff_pos,
        )
        payload["defender_end_coords"] = ends
        payload["defender_archetypes"] = arch
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
        ends = _reachable_defender_ends(
            ends,
            def_lineup=def_lineup,
            def_starts=def_starts,
            archetypes=arch,
            time_budget=payload["t_drive_game_seconds"],
            stopper_pos=cutoff_pos,
        )
        payload["defender_end_coords"] = ends
        _, shot_def_id = _apply_rendered_spread_contest(
            payload,
            off_lineup=off_lineup,
            off_starts=off_starts,
            def_lineup=def_lineup,
            def_starts=def_starts,
            bh_start=bh_start,
            shot_spot=shot_spot,
            is_away_offense=is_away_offense,
        )
        _stamp_geo_ids(stopper_id, shot_def_id)
        return payload

    # NEUTRAL — dynamic stop decision (two schema steps in emitters)
    payload["outcome"] = "NEUTRAL"
    payload["t_drive_game_seconds"] = payload["t_meet_game_seconds"]
    payload["advance_trigger"] = "meet_reached"
    ends = _reachable_defender_ends(
        ends,
        def_lineup=def_lineup,
        def_starts=def_starts,
        archetypes=arch,
        time_budget=payload["t_meet_game_seconds"],
        stopper_pos=cutoff_pos,
    )
    payload["defender_end_coords"] = ends

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
        else:
            # pass / HCO: the integration re-selects the contester at the receiver
            # spot — give it the RENDERED spread (BH stops at the meet) to read.
            _stamp_rendered_defender_ends(
                payload,
                off_lineup=off_lineup,
                off_starts=off_starts,
                def_lineup=def_lineup,
                def_starts=def_starts,
                bh_start=bh_start,
                bh_end=meet,
                is_away_offense=is_away_offense,
            )
    _stamp_geo_ids(stopper_id)
    return payload


def resolve_fb_drive_with_cascade(
    *,
    resolve_kwargs: Dict[str, Any],
    shot_spot: Dict[str, float],
    max_attempts: Optional[int] = None,
    resolve_fn=None,
) -> Dict[str, Any]:
    """Resolve a drive with POS_O cutoff cascade (universal helper).

    On ``POS_O``, re-ranks remaining defenders from the BH shimmy (path changes)
    with beaten stoppers excluded. Continues until a non-``POS_O`` outcome or no
    defenders remain. ``max_attempts=None`` means uncapped (bounded by on-floor
    defenders). After-steal is the first caller; other FB plays may opt in later.

    ``resolve_fn`` defaults to ``resolve_fb_drive_step``; callers may pass their
    module-local binding so tests can monkeypatch it.
    """
    if resolve_fn is None:
        resolve_fn = resolve_fb_drive_step
    beaten: List[str] = []
    knots: Optional[List[Dict[str, float]]] = None
    total_t = 0.0
    cur_start = dict(resolve_kwargs["bh_start"])
    drive: Dict[str, Any] = {}
    # Safety bound: initial attempt + one per on-floor defender.
    hard_ceiling = (
        max_attempts if max_attempts is not None else (len(POSITIONS) + 1)
    )

    for attempt in range(max(1, hard_ceiling)):
        kw = dict(resolve_kwargs)
        kw["bh_start"] = cur_start
        kw["excluded_stopper_ids"] = set(beaten)
        drive = resolve_fn(**kw)
        if drive.get("outcome") != "POS_O" or not drive.get("stopper_id"):
            break
        # Cap: this POS_O is the final attempt (legacy callers).
        if max_attempts is not None and attempt >= max_attempts - 1:
            break
        meet = {"x": float(drive["meet_x"]), "y": float(drive["meet_y"])}
        shimmy_raw = drive.get("shimmy") or meet
        shimmy = {"x": float(shimmy_raw["x"]), "y": float(shimmy_raw["y"])}
        if knots is None:
            start_knot = drive.get("bh_start") or cur_start
            knots = [{"x": float(start_knot["x"]), "y": float(start_knot["y"])}]
        knots.append(dict(meet))
        knots.append(dict(shimmy))
        segs = drive.get("path_segment_game_seconds") or []
        total_t += float(segs[0]) if len(segs) >= 1 else 0.0
        total_t += float(segs[1]) if len(segs) >= 2 else 0.0
        beaten.append(str(drive.get("stopper_id")))
        cur_start = dict(shimmy)

    if beaten and drive:
        drive["cascade_beaten_stopper_ids"] = beaten
        if drive.get("outcome") in ("NO_MEET", "POS_O"):
            # BH ultimately reaches the rim after beating ≥1 defender: render as
            # one curved POS_O drive threading all shimmy knots to the finish.
            if knots is None:
                knots = [dict(cur_start)]
            final = drive.get("shot_spot") or shot_spot
            knots.append({"x": float(final["x"]), "y": float(final["y"])})
            total_t += float(drive.get("t_drive_game_seconds") or 0.0)
            drive["outcome"] = "POS_O"
            drive["bh_path_knots"] = knots
            drive.pop("path_segment_game_seconds", None)
            if total_t > 0:
                drive["t_drive_game_seconds"] = total_t
        # NEUTRAL / terminal: keep the final defender's own meet + outcome.
    return drive
