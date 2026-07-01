"""After-steal FB integration for ``resolve_fb_drive_step`` (Phase 2).

Called from ``after_steal_fast_break.resolve_after_steal_fast_break`` when
``USE_FB_DRIVE_RESOLUTION_AFTER_STEAL`` is enabled. Legacy MAKE/MISS-only path
remains in ``after_steal_fast_break._resolve_after_steal_legacy``.
"""

from __future__ import annotations

import logging
import random
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import AWAY_RIM_COORDS, HOME_RIM_COORDS
from BackEnd.constants.fast_break_play_types import AFTER_STEAL
from BackEnd.constants.momentum import MO_AND_ONE_DELTA
from BackEnd.engine.fb_drive_resolution import resolve_fb_drive_step
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec
from BackEnd.utils.fb_geo_helpers import pick_nearest_contesting_defender
from BackEnd.utils.shot_split_tracker import record_shot_split


def _safe_id(p: Any) -> Optional[str]:
    if p is None:
        return None
    if isinstance(p, str):
        return p
    pid = getattr(p, "player_id", None)
    return str(pid) if pid is not None else None


def _coord_of(player: Any) -> Dict[str, float]:
    raw = getattr(player, "coords", None) or {}
    x = raw.get("x", 50.0) if isinstance(raw, dict) else 50.0
    y = raw.get("y", 25.0) if isinstance(raw, dict) else 25.0
    return {"x": float(x), "y": float(y)}


def _mirror_x(home_x: float) -> float:
    return 100.0 - home_x


def _compute_bh_target(is_away_offense: bool) -> Dict[str, float]:
    distance = random.randint(2, 4)
    if is_away_offense:
        x = 9.0 + distance
    else:
        x = 91.0 - distance
    y = float(random.randint(19, 31))
    return {"x": x, "y": y}


def _sample_unique_offense_spots(n: int, is_away_offense: bool) -> List[Dict[str, float]]:
    from BackEnd.engine.after_steal_fast_break import AFTER_STEAL_OFFENSE_SPOT_NAMES
    from BackEnd.constants import HCO_STRING_SPOTS

    pool = list(AFTER_STEAL_OFFENSE_SPOT_NAMES)
    random.shuffle(pool)
    spots: List[Dict[str, float]] = []
    for name in pool:
        if len(spots) >= n:
            break
        raw = HCO_STRING_SPOTS.get(name)
        if not raw:
            continue
        x, y = float(raw["x"]), float(raw["y"])
        if is_away_offense:
            x = _mirror_x(x)
        spots.append({"x": x, "y": y})
    return spots


def _interpolated_position(
    start: Dict[str, float],
    target: Dict[str, float],
    rate: float,
    elapsed: float,
) -> Dict[str, float]:
    dx = target["x"] - start["x"]
    dy = target["y"] - start["y"]
    dist = (dx * dx + dy * dy) ** 0.5
    if dist < 1e-6 or rate <= 0:
        return dict(start)
    traverse_t = dist / rate
    if elapsed >= traverse_t:
        return dict(target)
    frac = elapsed / traverse_t
    return {"x": start["x"] + dx * frac, "y": start["y"] + dy * frac}


@contextmanager
def _temporary_lineup_coords(
    game: Any,
    coords_by_player_id: Dict[str, Dict[str, float]],
):
    originals: Dict[str, Tuple[Any, Any]] = {}
    for team in (getattr(game, "home_team", None), getattr(game, "away_team", None)):
        for player in (getattr(team, "lineup", None) or {}).values():
            pid = _safe_id(player)
            if pid is None or pid not in coords_by_player_id:
                continue
            originals[pid] = (player, getattr(player, "coords", None))
            player.coords = dict(coords_by_player_id[pid])
    try:
        yield
    finally:
        for player, coords in originals.values():
            if coords is None:
                if hasattr(player, "coords"):
                    delattr(player, "coords")
            else:
                player.coords = coords


def _lineup_pos(lineup: Dict[str, Any], player: Any) -> str:
    pid = _safe_id(player)
    for pos, p in (lineup or {}).items():
        if p is not None and _safe_id(p) == pid:
            return str(pos)
    return "PG"


def _lineup_starts_by_pos(lineup: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    return {pos: _coord_of(p) for pos, p in (lineup or {}).items() if p is not None}


def _player_by_id(lineup: Dict[str, Any], player_id: Optional[str]) -> Optional[Any]:
    if not player_id:
        return None
    for p in lineup.values():
        if p is not None and _safe_id(p) == str(player_id):
            return p
    return None


def _build_offense_end_coords(
    *,
    stealer_id: str,
    bh_end: Dict[str, float],
    off_lineup: Dict[str, Any],
    t_elapsed: float,
    is_away_offense: bool,
    base_end_coords: Dict[str, Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    end_coords = dict(base_end_coords)
    end_coords[stealer_id] = dict(bh_end)
    others = [
        p for p in off_lineup.values() if p is not None and _safe_id(p) != stealer_id
    ]
    sampled = _sample_unique_offense_spots(len(others), is_away_offense)
    for player, target in zip(others, sampled):
        pid = _safe_id(player)
        if not pid:
            continue
        rate = _ag_grid_per_game_sec(player, "sprint")
        end_coords[pid] = _interpolated_position(_coord_of(player), target, rate, t_elapsed)
    return end_coords


def _resolve_shot_attempt(
    *,
    game: Any,
    shooter: Any,
    shooter_location: Dict[str, float],
    shot_defender: Optional[Any],
    contested: bool,
    shot_type: str,
    is_paint: bool,
) -> Dict[str, Any]:
    """Shared shot resolution for rim attack and NEUTRAL pull-up paths."""
    from BackEnd.constants.shot_variants import roll_shot_variant_extras, select_shot_variant
    from BackEnd.engine.phase_resolution import check_and_handle_foul_out
    from BackEnd.engine.shot_micro_movements import resolve_contest, select_and_stamp_shot_micro
    from BackEnd.models.shot_manager import ShotManager
    from BackEnd.utils.shared import increment_no_defender_shot_breakdown

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    defense_playcall = (
        game_state.get("defense_playcall")
        or game_state.get("defense_call")
        or "man"
    )
    shot_manager = getattr(game, "shot_manager", None) or ShotManager(game)
    is_three = False

    if contested and shot_defender is not None:
        (
            shot_score,
            shot_score_pre_defense,
            shot_defense_score_for_sfx,
            d_foul,
            foul_player,
            shot_defense_score_raw,
        ) = shot_manager.calculate_shot_score(
            shooter,
            None,
            None,
            shot_defender,
            shot_type,
            defense_playcall,
            is_three,
            is_paint,
            None,
            shooter_location,
            apply_defense=True,
        )
        contest_result, contest_margin = resolve_contest(
            shot_score_pre_defense, shot_defense_score_raw
        )
        shot_threshold = off_team.team_attributes["shot_threshold"]
        made = shot_score >= shot_threshold
    else:
        (
            shot_score,
            shot_score_pre_defense,
            shot_defense_score_for_sfx,
            d_foul,
            foul_player,
            _raw,
        ) = shot_manager.calculate_shot_score(
            shooter,
            None,
            None,
            None,
            shot_type,
            defense_playcall,
            is_three,
            is_paint,
            None,
            shooter_location,
            apply_defense=False,
        )
        contest_result = None
        contest_margin = None
        shot_defense_score_raw = 0.0
        made = True
        game_state["no_defender_shots"] = int(game_state.get("no_defender_shots", 0) or 0) + 1
        increment_no_defender_shot_breakdown(
            game_state, game_state.get("offensive_state"), "after_steal"
        )

    has_and_one = False
    free_throws_remaining = 0
    fouled_out_info: Dict[str, Any] = {}
    if d_foul and foul_player:
        foul_player.record_stat("F")
        def_team.team_fouls += 1
        game_state["foul_team"] = "DEFENSE"
        game_state["shooter"] = shooter
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 1 if made else 2
        game_state["free_throws_remaining"] = game_state["free_throws"]
        game_state["one_and_one"] = False
        fouled_out_info = check_and_handle_foul_out(foul_player, game_state, def_team)
        has_and_one = made
        free_throws_remaining = 1 if made else 2

    if made or not d_foul:
        shooter.record_shot_result(made)
    if made and d_foul and foul_player:
        shooter.add_momentum(MO_AND_ONE_DELTA)

    record_shot_split(
        game, is_three=is_three, defended=contested, made=made, turn_type="Fast Break"
    )

    shot_threshold_for_variant = off_team.team_attributes.get("shot_threshold", 100)
    try:
        shot_variant = select_shot_variant(
            shot_score=shot_score_pre_defense,
            shot_threshold=shot_threshold_for_variant,
            shot_type=shot_type,
            made=made,
        )
        shot_variant_extras = roll_shot_variant_extras(
            shot_variant, shooter_y=shooter_location["y"]
        )
    except Exception:
        shot_variant = None
        shot_variant_extras = {}

    return {
        "made": made,
        "d_foul": d_foul,
        "foul_player": foul_player,
        "has_and_one": has_and_one,
        "free_throws_remaining": free_throws_remaining,
        "fouled_out_info": fouled_out_info,
        "shot_score": shot_score,
        "shot_score_pre_defense": shot_score_pre_defense,
        "shot_defense_score_for_sfx": shot_defense_score_for_sfx,
        "shot_defense_score_raw": shot_defense_score_raw,
        "shot_variant": shot_variant,
        "shot_variant_extras": shot_variant_extras,
        "contest_result": contest_result,
        "contest_margin": contest_margin,
        "shot_type": shot_type,
        "contested": contested,
        "shot_defender": shot_defender,
        "shot_defender_id": _safe_id(shot_defender),
        "select_and_stamp_shot_micro_kwargs": {
            "shot_type": shot_type,
            "shooter_id": str(_safe_id(shooter)),
            "shooter_x": float(shooter_location["x"]),
            "shooter_y": float(shooter_location["y"]),
            "off_lineup": off_lineup,
            "def_lineup": def_lineup,
            "has_contest": bool(contested),
            "contest_result": contest_result if contested else None,
            "contest_margin": contest_margin if contested else None,
            "shot_defense_score_raw": float(shot_defense_score_raw if contested else 0),
        },
    }


def _resolve_rebound_on_miss(
    *,
    game: Any,
    stealer: Any,
    stealer_id: str,
    end_coords: Dict[str, Dict[str, float]],
    is_away_offense: bool,
    d_foul: bool,
) -> Tuple[bool, Optional[str], Optional[Dict[str, float]], Optional[Dict[str, List[str]]], Optional[str]]:
    from BackEnd.utils.shared import (
        FAST_BREAK_REBOUND_GEO_DISTANCE,
        apply_scoring,
        calculate_bounce_spot,
        collect_near_bounce_rebound_attemptors,
        determine_rebounder,
    )

    if d_foul:
        return False, None, None, None, None

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}

    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    bounce_spot = calculate_bounce_spot(game, basket_x=float(rim["x"]), basket_y=25)
    penalize = {stealer_id} if stealer_id else set()
    with _temporary_lineup_coords(game, end_coords):
        new_rebounder, new_team, new_stat = determine_rebounder(
            game,
            bounce_spot,
            set(),
            penalize,
            max_distance_from_bounce=FAST_BREAK_REBOUND_GEO_DISTANCE,
            upper_half_distance=FAST_BREAK_REBOUND_GEO_DISTANCE * 0.5,
            offense_candidate_lineup=off_lineup,
            defense_candidate_lineup=def_lineup,
        )
    rebounder_pid = _safe_id(new_rebounder)
    rebound_attemptors = collect_near_bounce_rebound_attemptors(
        game,
        bounce_spot,
        rebounder_pid,
        max_distance=FAST_BREAK_REBOUND_GEO_DISTANCE,
        coords_already_display_oriented=True,
    )
    rebound_type = str(new_stat) if new_stat else "DREB"
    rebound_ball_spot = {"x": float(bounce_spot["x"]), "y": float(bounce_spot["y"])}

    if new_rebounder is not None:
        canonical = (
            new_team.get_player_by_id(rebounder_pid) if rebounder_pid and new_team else None
        )
        (canonical or new_rebounder).record_stat(rebound_type)

    possession_flips = False
    if rebound_type == "OREB" and new_rebounder is not None:
        game_state["pending_oreb"] = {
            "rebounder": new_rebounder,
            "rebounder_id": rebounder_pid,
            "from_block": False,
        }
    else:
        game_state["offensive_state"] = "HCO"
        game_state["last_rebounder"] = new_rebounder
        possession_flips = True

    return possession_flips, rebound_type, rebound_ball_spot, rebound_attemptors, rebounder_pid


def _record_stats(game, turn_result, stealer, defenders):
    from BackEnd.engine.after_steal_fast_break import _record_after_steal_fast_break_stats

    _record_after_steal_fast_break_stats(game, turn_result, stealer, defenders)


def resolve_after_steal_with_drive_resolution(game: Any) -> Dict[str, Any]:
    """After-steal FB via unified ``resolve_fb_drive_step`` (Phase 2)."""
    from BackEnd.engine.shot_micro_movements import select_and_stamp_shot_micro
    from BackEnd.utils.shared import apply_scoring, get_name_safe

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)
    defenders: List[Any] = [p for p in def_lineup.values() if p is not None]

    stealer = game_state.get("last_stealer") or off_lineup.get("PG")
    if stealer is None:
        logging.warning("🚨 [AFTER_STEAL] last_stealer missing; falling back to off PG")
    stealer_id = _safe_id(stealer)
    if stealer is None or stealer_id is None:
        return {
            "result_type": "MISS",
            "fast_break": True,
            "fast_break_play": AFTER_STEAL,
            "text": "Fast Break! Possession lost.",
            "possession_flips": True,
            "current_turn": "FAST_BREAK",
            "next_play_type": "BASELINE_INBOUND",
        }

    bh_start = (
        dict(game_state["last_stealer_coords"])
        if isinstance(game_state.get("last_stealer_coords"), dict)
        else _coord_of(stealer)
    )
    bh_pos = _lineup_pos(off_lineup, stealer)
    shot_spot = _compute_bh_target(is_away_offense)

    from BackEnd.models.shot_manager import ShotManager

    shot_manager = getattr(game, "shot_manager", None) or ShotManager(game)
    drive = resolve_fb_drive_step(
        bh=stealer,
        bh_pos=bh_pos,
        bh_start=bh_start,
        shot_spot=shot_spot,
        off_lineup=off_lineup,
        off_starts=_lineup_starts_by_pos(off_lineup),
        def_lineup=def_lineup,
        def_starts=_lineup_starts_by_pos(def_lineup),
        off_team=off_team,
        def_team=def_team,
        shot_manager=shot_manager,
        is_away_offense=is_away_offense,
        steal_entry=True,
    )

    outcome = drive.get("outcome")
    t_drive = float(drive.get("t_drive_game_seconds") or 1.0)
    meet = (
        {"x": float(drive["meet_x"]), "y": float(drive["meet_y"])}
        if drive.get("meet_x") is not None
        else None
    )

    # --- Terminal meet outcomes (no shot attempt) -------------------------
    if outcome in ("DEAD BALL", "O_FOUL", "D_FOUL", "CHARGE", "BLOCKING_FOUL"):
        bh_end = meet or dict(shot_spot)
        end_coords = _build_offense_end_coords(
            stealer_id=stealer_id,
            bh_end=bh_end,
            off_lineup=off_lineup,
            t_elapsed=float(drive.get("t_meet_game_seconds") or t_drive),
            is_away_offense=is_away_offense,
            base_end_coords=dict(drive.get("defender_end_coords") or {}),
        )
        stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
        credited = _player_by_id(def_lineup, drive.get("d8_credited_player_id"))

        if outcome == "DEAD BALL":
            result_type = "DEAD BALL"
            possession_flips = True
            game_state["offensive_state"] = "HCO"
            text_tail = "turnover!"
        elif outcome in ("CHARGE", "O_FOUL"):
            result_type = "CHARGE" if outcome == "CHARGE" else "FOUL"
            foul_team = "OFFENSE"
            foul_player = stealer if outcome == "CHARGE" else credited
            possession_flips = True
            game_state["foul_team"] = foul_team
            game_state["offensive_state"] = "HCO"
            if foul_player:
                foul_player.record_stat("F")
            text_tail = "offensive foul!"
        else:
            result_type = "FOUL"
            foul_team = "DEFENSE"
            foul_player = credited or stopper
            possession_flips = False
            game_state["foul_team"] = foul_team
            if foul_player:
                foul_player.record_stat("F")
                def_team.team_fouls += 1
            text_tail = "defensive foul!"
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2
            game_state["free_throws_remaining"] = 2

        stealer_name = get_name_safe(stealer)
        turn_result: Dict[str, Any] = {
            "result_type": result_type,
            "current_turn": "FAST_BREAK",
            "fast_break": True,
            "fast_break_play": AFTER_STEAL,
            "fb_drive_resolution": drive,
            "ball_handler": stealer,
            "shooter": stealer,
            "shooter_id": stealer_id,
            "stopper_id": drive.get("stopper_id"),
            "text": f"Fast Break! {stealer_name} takes it the other way, {text_tail}",
            "possession_flips": possession_flips,
            "offense_team_id": off_team.team_id,
            "quarter": game.quarter,
            "next_play_type": "HCO" if possession_flips else "FREE_THROW",
            "next_turn": "HCO" if possession_flips else "FREE_THROW",
            "score": dict(game.score),
            "after_steal_end_coords": end_coords,
            "t_shooter_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
            "bh_target": dict(bh_end),
            "time_elapsed": max(1, int(round(t_drive + 0.5))),
        }
        if outcome in ("CHARGE", "O_FOUL", "D_FOUL", "BLOCKING_FOUL"):
            turn_result["foul_team"] = foul_team if outcome != "DEAD BALL" else None
            if foul_player:
                turn_result["foul_player_id"] = _safe_id(foul_player)
        _record_stats(game, turn_result, stealer, defenders)
        game_state.pop("last_stealer_coords", None)
        game_state["last_stealer"] = None
        return turn_result

    # --- NEUTRAL stop branch ------------------------------------------------
    if outcome == "NEUTRAL":
        stop = drive.get("stop_decision") or {}
        action = stop.get("action", "HCO")
        bh_end = meet or dict(shot_spot)
        end_coords = _build_offense_end_coords(
            stealer_id=stealer_id,
            bh_end=bh_end,
            off_lineup=off_lineup,
            t_elapsed=float(drive.get("t_meet_game_seconds") or t_drive),
            is_away_offense=is_away_offense,
            base_end_coords=dict(drive.get("defender_end_coords") or {}),
        )

        if action == "HCO":
            game_state["offensive_state"] = "HCO"
            def_team.scouting_data["defense"]["vs_Fast_Break"]["success"] += 1
            stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
            stopper_name = get_name_safe(stopper) if stopper else "Defense"
            turn_result = {
                "result_type": "DEFENSIVE_STOP",
                "current_turn": "FAST_BREAK",
                "fast_break": True,
                "fast_break_play": AFTER_STEAL,
                "fb_drive_resolution": drive,
                "ball_handler": stealer,
                "defender": stopper,
                "stopper_id": drive.get("stopper_id"),
                "text": f"Fast Break! Nice stop by {stopper_name}!",
                "possession_flips": False,
                "offense_team_id": off_team.team_id,
                "quarter": game.quarter,
                "next_play_type": "HCO",
                "next_turn": "HCO",
                "score": dict(game.score),
                "after_steal_end_coords": end_coords,
                "meet_coords": dict(bh_end),
                "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                "bh_target": dict(bh_end),
                "time_elapsed": max(1, int(round(t_drive + 1.0))),
            }
            _record_stats(game, turn_result, stealer, defenders)
            game_state.pop("last_stealer_coords", None)
            game_state["last_stealer"] = None
            return turn_result

        stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
        if action == "pass":
            recv_id = stop.get("receiver_id")
            receiver = _player_by_id(off_lineup, recv_id)
            recv_pos = stop.get("receiver_pos")
            recv_coord = _lineup_starts_by_pos(off_lineup).get(recv_pos or "", bh_end)
            contested, shot_def_id = pick_nearest_contesting_defender(
                end_coords, recv_coord, is_away_offense=is_away_offense
            )
            shot_defender = _player_by_id(def_lineup, shot_def_id)
            shot_type = "attack"
            shooter = receiver or stealer
            shooter_loc = recv_coord
            pass_info = {"receiver_id": recv_id, "receiver_pos": recv_pos}
        else:
            shot_type = stop.get("shot_type") or "outside"
            shooter = stealer
            shooter_loc = bh_end
            shot_defender = stopper
            contested = True
            pass_info = None

        shot = _resolve_shot_attempt(
            game=game,
            shooter=shooter,
            shooter_location=shooter_loc,
            shot_defender=shot_defender,
            contested=contested,
            shot_type=shot_type,
            is_paint=shot_type == "inside",
        )
        made = shot["made"]
        d_foul = shot["d_foul"]
        if made:
            shooter.record_stat("FGA")
            apply_scoring(game, off_team, shooter, 2, ["FGM"])
            shooter.record_stat("FB_PTS", amount=2)
            shooter.record_stat("POT", amount=2)
            text_tail = "and scores, gets fouled!" if shot["has_and_one"] else "and hits the pull-up!"
            possession_flips = not shot["has_and_one"]
        else:
            shooter.record_stat("FGA")
            possession_flips, rebound_type, rebound_ball_spot, rebound_attemptors, rebounder_pid = (
                _resolve_rebound_on_miss(
                    game=game,
                    stealer=shooter,
                    stealer_id=_safe_id(shooter) or stealer_id,
                    end_coords=end_coords,
                    is_away_offense=is_away_offense,
                    d_foul=d_foul,
                )
            )
            text_tail = "but misses, fouled on the shot." if d_foul else "but misses the pull-up."

        stealer_name = get_name_safe(stealer)
        text = f"Fast Break! {stealer_name} takes it the other way, {text_tail}"
        result_type = "MAKE" if made else "MISS"
        turn_result = {
            "result_type": result_type,
            "current_turn": "FAST_BREAK",
            "fast_break": True,
            "fast_break_play": AFTER_STEAL,
            "fb_drive_resolution": drive,
            "ball_handler": stealer,
            "shooter": shooter,
            "shooter_id": _safe_id(shooter),
            "defender": shot_defender,
            "text": text,
            "possession_flips": possession_flips,
            "offense_team_id": off_team.team_id,
            "quarter": game.quarter,
            "next_play_type": "BASELINE_INBOUND" if made and not shot["has_and_one"] else (
                "FREE_THROW" if d_foul else ("OREB" if not made and rebound_type == "OREB" else "HCO")
            ),
            "score": dict(game.score),
            "shot_type": shot_type,
            "shot_score": shot["shot_score"],
            "after_steal_end_coords": end_coords,
            "after_steal_contested": contested,
            "shot_defender_id": shot["shot_defender_id"],
            "t_shooter_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
            "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
            "meet_coords": dict(bh_end),
            "bh_target": dict(shooter_loc),
            "stop_decision_action": action,
            "pass_info": pass_info,
            "time_elapsed": max(1, int(round(t_drive + 1.0))),
        }
        if pass_info:
            turn_result["pass_receiver_id"] = pass_info.get("receiver_id")
        if made:
            turn_result["points"] = 2
            turn_result["scoring_team"] = off_team.name
        if not made and not d_foul and rebound_type:
            turn_result["rebound_type"] = rebound_type
            turn_result["rebounderId"] = rebounder_pid
            if rebound_ball_spot:
                turn_result["ballSpot"] = dict(rebound_ball_spot)
            if rebound_attemptors:
                turn_result["offense_rebounders"] = rebound_attemptors["offense_rebounders"]
                turn_result["defense_rebounders"] = rebound_attemptors["defense_rebounders"]
        select_and_stamp_shot_micro(turn_result, **shot["select_and_stamp_shot_micro_kwargs"])
        if shot["shot_variant_extras"]:
            turn_result.update(shot["shot_variant_extras"])
        _record_stats(game, turn_result, stealer, defenders)
        game_state.pop("last_stealer_coords", None)
        game_state["last_stealer"] = None
        return turn_result

    # --- NO_MEET / POS_O → rim finish ---------------------------------------
    bh_target = dict(shot_spot)
    end_coords = _build_offense_end_coords(
        stealer_id=stealer_id,
        bh_end=bh_target,
        off_lineup=off_lineup,
        t_elapsed=t_drive,
        is_away_offense=is_away_offense,
        base_end_coords=dict(drive.get("defender_end_coords") or {}),
    )
    shot_defender = _player_by_id(def_lineup, drive.get("shot_defender_id"))
    contested = bool(drive.get("contested"))
    shot = _resolve_shot_attempt(
        game=game,
        shooter=stealer,
        shooter_location=bh_target,
        shot_defender=shot_defender,
        contested=contested,
        shot_type="attack",
        is_paint=True,
    )
    made = shot["made"]
    d_foul = shot["d_foul"]
    if made:
        stealer.record_stat("FGA")
        apply_scoring(game, off_team, stealer, 2, ["FGM"])
        stealer.record_stat("FB_PTS", amount=2)
        stealer.record_stat("POT", amount=2)
        text_tail = "and scores, gets fouled!" if shot["has_and_one"] else "and finishes!"
        possession_flips = not shot["has_and_one"]
        pressure_type = None
        if not shot["has_and_one"]:
            try:
                pressure_type = game.turn_manager.determine_defensive_pressure_type()
            except Exception:
                pressure_type = "HCO"
            game_state["offensive_state"] = pressure_type or "HCO"
    else:
        stealer.record_stat("FGA")
        possession_flips, rebound_type, rebound_ball_spot, rebound_attemptors, rebounder_pid = (
            _resolve_rebound_on_miss(
                game=game,
                stealer=stealer,
                stealer_id=stealer_id,
                end_coords=end_coords,
                is_away_offense=is_away_offense,
                d_foul=d_foul,
            )
        )
        text_tail = "but misses, fouled on the shot." if d_foul else "but misses."
        pressure_type = None
        rebound_type = rebound_type  # noqa: F841 — used below

    stealer_name = get_name_safe(stealer)
    text = f"Fast Break! {stealer_name} takes it the other way, {text_tail}"
    turn_result = {
        "result_type": "MAKE" if made else "MISS",
        "current_turn": "FAST_BREAK",
        "fast_break": True,
        "fast_break_play": AFTER_STEAL,
        "fb_drive_resolution": drive,
        "ball_handler": stealer,
        "shooter": stealer,
        "shooter_id": stealer_id,
        "defender": shot_defender,
        "text": text,
        "possession_flips": possession_flips,
        "offense_team_id": off_team.team_id,
        "quarter": game.quarter,
        "next_play_type": "BASELINE_INBOUND",
        "score": dict(game.score),
        "shot_type": "attack",
        "shot_score": shot["shot_score"],
        "after_steal_end_coords": end_coords,
        "after_steal_contested": contested,
        "after_steal_first_arriver_id": drive.get("shot_defender_id"),
        "shot_defender_id": shot["shot_defender_id"],
        "t_shooter_game_seconds": t_drive,
        "bh_target": dict(bh_target),
        "time_elapsed": max(1, int(round(t_drive + 1.0))),
    }
    if made and pressure_type:
        turn_result["next_defensive_setup"] = pressure_type
    if made:
        turn_result["points"] = 2
        turn_result["scoring_team"] = off_team.name
    if not made and not d_foul:
        turn_result["rebound_type"] = rebound_type
        turn_result["rebounderId"] = rebounder_pid
        if rebound_ball_spot:
            turn_result["ballSpot"] = dict(rebound_ball_spot)
        if rebound_attemptors:
            turn_result["offense_rebounders"] = rebound_attemptors["offense_rebounders"]
            turn_result["defense_rebounders"] = rebound_attemptors["defense_rebounders"]
        turn_result["next_play_type"] = "OREB" if rebound_type == "OREB" else "HCO"
    elif d_foul:
        turn_result["next_play_type"] = "FREE_THROW"
    select_and_stamp_shot_micro(turn_result, **shot["select_and_stamp_shot_micro_kwargs"])
    turn_result.update(shot.get("shot_variant_extras") or {})
    turn_result["shot_variant"] = shot.get("shot_variant")
    turn_result["sfx"] = {
        "shot_type": "attack",
        "shot_score_pre_defense": shot["shot_score_pre_defense"],
        "shot_defense_score_for_sfx": shot["shot_defense_score_for_sfx"],
        "shot_variant": shot.get("shot_variant"),
    }
    _record_stats(game, turn_result, stealer, defenders)
    game_state.pop("last_stealer_coords", None)
    game_state["last_stealer"] = None
    return turn_result
