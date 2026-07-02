"""Covert Release FB integration for ``resolve_fb_drive_step`` (Phase 3).

Outlet pass completes → attack drive step runs the unified geo resolver.
Legacy outlet-phase cutoff in ``resolve_fast_break_logic`` is bypassed when
``USE_FB_DRIVE_RESOLUTION_CR`` is enabled.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants.fast_break_play_types import COVERT_RELEASE, ensure_fast_break_plays
from BackEnd.engine.after_steal_drive_integration import (
    _build_offense_end_coords,
    _compute_bh_target,
    _coord_of,
    _lineup_pos,
    _lineup_starts_by_pos,
    _player_by_id,
    _resolve_rebound_on_miss,
    _resolve_shot_attempt,
    _safe_id,
)
from BackEnd.engine.fb_drive_resolution import resolve_fb_drive_step
from BackEnd.engine.phase_resolution import (
    _find_most_recent_shot_turn,
    _record_fast_break_stats,
    _record_outlet_pass_stats,
    apply_fast_break_cg_time,
    apply_fb_meet_non_shooting_defensive_foul,
    calculate_outlet_pass_score,
    get_in_play_defenders,
)
from BackEnd.utils.shared import apply_scoring, get_name_safe


def _defender_outlet_coord(
    defender: Any,
    defender_id: Optional[str],
    most_recent_shot_turn: Optional[Dict[str, Any]],
) -> Dict[str, float]:
    if most_recent_shot_turn and defender_id:
        getback = most_recent_shot_turn.get("offense_getback_coords") or {}
        if defender_id in getback:
            c = getback[defender_id]
            return {"x": float(c["x"]), "y": float(c["y"])}
    return _coord_of(defender)


def _build_cr_context(game: Any) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], bool]:
    """Return ``(fb_roles, bh_start, def_starts_by_pos, is_away_offense)``."""
    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)

    game_state["last_rebound"] = ""

    release_player = game_state.get("last_release_player")
    rebounder = game_state.get("last_rebounder")
    most_recent_shot_turn = _find_most_recent_shot_turn(game, max_turns=10)
    getback_player_ids = (
        list(most_recent_shot_turn.get("offense_getback", []))
        if most_recent_shot_turn
        else []
    )

    if release_player:
        ball_handler = release_player
        game_state["last_release_player"] = None
    else:
        bh_pos = random.choices(["PG", "SG", "SF"], weights=[75, 15, 10])[0]
        ball_handler = off_lineup[bh_pos]

    ball_handler_id = _safe_id(ball_handler)
    bh_start_x = bh_start_y = None
    if most_recent_shot_turn and ball_handler_id:
        release_coords = most_recent_shot_turn.get("defense_release_coords") or {}
        if ball_handler_id in release_coords:
            stored = release_coords[ball_handler_id]
            bh_start_x = stored.get("x")
            bh_start_y = stored.get("y")
        if bh_start_x is None:
            getback_coords = most_recent_shot_turn.get("offense_getback_coords") or {}
            if ball_handler_id in getback_coords:
                stored = getback_coords[ball_handler_id]
                bh_start_x = stored.get("x")
                bh_start_y = stored.get("y")
    if bh_start_x is None or bh_start_y is None:
        bh_start_x = _coord_of(ball_handler)["x"]
        bh_start_y = _coord_of(ball_handler)["y"]

    bh_start = {"x": float(bh_start_x), "y": float(bh_start_y)}

    fb_roles: Dict[str, Any] = {
        "offense": [],
        "defense": [],
        "ball_handler": ball_handler,
        "ball_handler_id": ball_handler_id,
        "outlet_passer": None,
        "outlet_receiver": None,
        "fast_break_play": COVERT_RELEASE,
        "getback_player_ids": getback_player_ids,
        "is_away_offense": is_away_offense,
    }

    if rebounder and ball_handler and rebounder != ball_handler:
        fb_roles["outlet_passer"] = _safe_id(rebounder)
        fb_roles["outlet_receiver"] = ball_handler_id
        rebounder_coords = getattr(rebounder, "coords", None) or {}
        if isinstance(rebounder_coords, dict):
            fb_roles["outlet_passer_x"] = rebounder_coords.get("x")
            fb_roles["outlet_passer_y"] = rebounder_coords.get("y")
        fb_roles["outlet_score"] = calculate_outlet_pass_score(rebounder)
    else:
        fb_roles["outlet_score"] = None

    target_is_away = is_away_offense
    fb_roles["defense"] = get_in_play_defenders(ball_handler, def_lineup, target_is_away)
    if not fb_roles["defense"]:
        defensive_pg = def_lineup.get("PG")
        if defensive_pg:
            fb_roles["defense"] = [defensive_pg]

    def_starts: Dict[str, Dict[str, float]] = {}
    for pos, defender in def_lineup.items():
        if defender is None:
            continue
        did = _safe_id(defender)
        def_starts[pos] = _defender_outlet_coord(defender, did, most_recent_shot_turn)

    return fb_roles, bh_start, def_starts, is_away_offense


def resolve_covert_release_fast_break(game: Any) -> Dict[str, Any]:
    """Covert Release DREB FB via ``resolve_fb_drive_step`` (Phase 3)."""
    from BackEnd.engine.shot_micro_movements import select_and_stamp_shot_micro
    from BackEnd.models.shot_manager import ShotManager

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    off_scouting = off_team.scouting_data
    def_scouting = def_team.scouting_data

    fb_roles, bh_start, def_starts, is_away_offense = _build_cr_context(game)
    ball_handler = fb_roles["ball_handler"]
    bh_id = _safe_id(ball_handler)
    if ball_handler is None or bh_id is None:
        return {
            "result_type": "MISS",
            "fast_break": True,
            "fast_break_play": COVERT_RELEASE,
            "text": "Fast Break! Possession lost.",
            "possession_flips": True,
            "current_turn": "FAST_BREAK",
            "next_play_type": "HCO",
        }

    bh_pos = _lineup_pos(off_lineup, ball_handler)
    shot_spot = _compute_bh_target(is_away_offense)
    shot_manager = getattr(game, "shot_manager", None) or ShotManager(game)

    drive = resolve_fb_drive_step(
        bh=ball_handler,
        bh_pos=bh_pos,
        shot_spot=shot_spot,
        off_lineup=off_lineup,
        off_starts=_lineup_starts_by_pos(off_lineup),
        def_lineup=def_lineup,
        def_starts=def_starts,
        off_team=off_team,
        def_team=def_team,
        shot_manager=shot_manager,
        is_away_offense=is_away_offense,
        steal_entry=False,
    )

    outcome = drive.get("outcome")
    t_drive = float(drive.get("t_drive_game_seconds") or 1.0)
    meet = (
        {"x": float(drive["meet_x"]), "y": float(drive["meet_y"])}
        if drive.get("meet_x") is not None
        else None
    )
    fb_roles["stopper_id"] = drive.get("stopper_id")

    def _record_outlet(success: bool) -> None:
        oid = fb_roles.get("outlet_passer")
        score = fb_roles.get("outlet_score")
        if oid and score is not None:
            _record_outlet_pass_stats(oid, score, success, game)

    def _finalize(turn_result: Dict[str, Any], *, shot_attempted: bool) -> Dict[str, Any]:
        turn_result["roles"] = fb_roles
        turn_result["fast_break"] = True
        turn_result["fast_break_play"] = COVERT_RELEASE
        turn_result["current_turn"] = "FAST_BREAK"
        turn_result["offense_team_id"] = off_team.team_id
        turn_result["quarter"] = game.quarter
        turn_result["score"] = dict(game.score)
        turn_result["fb_drive_resolution"] = drive
        turn_result["cr_end_coords"] = turn_result.get("cr_end_coords") or {}
        _record_fast_break_stats(fb_roles, turn_result, game)
        apply_fast_break_cg_time(turn_result, shot_attempted=shot_attempted)
        rt = turn_result.get("result_type")
        if rt == "MAKE":
            off_scouting["offense"]["Fast_Break_Success"] += 1
            ensure_fast_break_plays(off_scouting["offense"])[COVERT_RELEASE]["S"] += 1
        elif rt == "FOUL" and game_state.get("foul_team") == "DEFENSE":
            off_scouting["offense"]["Fast_Break_Success"] += 1
            ensure_fast_break_plays(off_scouting["offense"])[COVERT_RELEASE]["S"] += 1
        elif rt == "FOUL" and game_state.get("foul_team") == "OFFENSE":
            def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
        elif rt in ("MISS", "BLOCK", "TURNOVER", "DEAD BALL", "DEFENSIVE_STOP"):
            def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
        elif rt == "CHARGE":
            def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
        return turn_result

    # --- Terminal meet outcomes ---------------------------------------------
    if outcome in ("DEAD BALL", "O_FOUL", "D_FOUL", "CHARGE", "BLOCKING_FOUL"):
        bh_end = meet or dict(shot_spot)
        end_coords = _build_offense_end_coords(
            stealer_id=bh_id,
            bh_end=bh_end,
            off_lineup=off_lineup,
            t_elapsed=float(drive.get("t_meet_game_seconds") or t_drive),
            is_away_offense=is_away_offense,
            base_end_coords=dict(drive.get("defender_end_coords") or {}),
        )
        stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
        credited = _player_by_id(def_lineup, drive.get("d8_credited_player_id"))
        _record_outlet(outcome not in ("DEAD BALL", "O_FOUL", "CHARGE"))
        foul_transition = None
        foul_player = None
        next_play_type = "HCO"
        next_turn = "HCO"
        possession_flips = False

        if outcome == "DEAD BALL":
            result_type = "DEAD BALL"
            possession_flips = True
            game_state["offensive_state"] = "HCO"
            text_tail = "turnover!"
        elif outcome in ("CHARGE", "O_FOUL"):
            result_type = "CHARGE" if outcome == "CHARGE" else "FOUL"
            foul_player = ball_handler if outcome == "CHARGE" else credited
            possession_flips = True
            game_state["foul_team"] = "OFFENSE"
            game_state["offensive_state"] = "HCO"
            if foul_player:
                foul_player.record_stat("F")
            text_tail = "offensive foul!"
        else:
            result_type = "FOUL"
            foul_player = credited or stopper
            text_tail = "defensive foul!"
            foul_transition = apply_fb_meet_non_shooting_defensive_foul(
                game,
                ball_handler=ball_handler,
                foul_player=foul_player,
                time_elapsed_override=max(1, int(round(t_drive + 0.5))),
            )
            possession_flips = foul_transition["possession_flips"]
            next_play_type = foul_transition["next_play_type"]
            next_turn = foul_transition["next_turn"]

        bh_name = get_name_safe(ball_handler)
        turn_result = _finalize(
            {
                "result_type": result_type,
                "ball_handler": ball_handler,
                "shooter": ball_handler,
                "shooter_id": bh_id,
                "stopper_id": drive.get("stopper_id"),
                "text": f"Fast Break! {bh_name} pushes, {text_tail}",
                "possession_flips": possession_flips,
                "next_play_type": next_play_type,
                "next_turn": next_turn,
                "cr_end_coords": end_coords,
                "meet_coords": dict(bh_end),
                "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                "bh_target": dict(bh_end),
                "time_elapsed": max(1, int(round(t_drive + 0.5))),
            },
            shot_attempted=False,
        )
        if result_type in ("FOUL", "CHARGE"):
            turn_result["foul_team"] = game_state.get("foul_team")
            if foul_transition is not None:
                if foul_transition.get("foul_player_id"):
                    turn_result["foul_player_id"] = foul_transition["foul_player_id"]
                if foul_transition.get("fouled_out"):
                    turn_result["fouled_out"] = True
                    turn_result["foul_out_player"] = foul_transition.get("foul_out_player")
                    turn_result["foul_count"] = foul_transition.get("foul_count")
            elif foul_player:
                turn_result["foul_player_id"] = _safe_id(foul_player)
        return turn_result

    # --- NEUTRAL stop -------------------------------------------------------
    if outcome == "NEUTRAL":
        stop = drive.get("stop_decision") or {}
        action = stop.get("action", "HCO")
        bh_end = meet or dict(shot_spot)
        end_coords = _build_offense_end_coords(
            stealer_id=bh_id,
            bh_end=bh_end,
            off_lineup=off_lineup,
            t_elapsed=float(drive.get("t_meet_game_seconds") or t_drive),
            is_away_offense=is_away_offense,
            base_end_coords=dict(drive.get("defender_end_coords") or {}),
        )

        if action == "HCO":
            game_state["offensive_state"] = "HCO"
            _record_outlet(False)
            stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
            stopper_name = get_name_safe(stopper) if stopper else "Defense"
            return _finalize(
                {
                    "result_type": "DEFENSIVE_STOP",
                    "ball_handler": ball_handler,
                    "defender": stopper,
                    "stopper_id": drive.get("stopper_id"),
                    "text": f"Fast Break! Nice stop by {stopper_name}!",
                    "possession_flips": False,
                    "next_play_type": "HCO",
                    "next_turn": "HCO",
                    "cr_end_coords": end_coords,
                    "meet_coords": dict(bh_end),
                    "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                    "bh_target": dict(bh_end),
                    "time_elapsed": max(1, int(round(t_drive + 1.0))),
                },
                shot_attempted=False,
            )

        stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
        if action == "pass":
            recv_id = stop.get("receiver_id")
            receiver = _player_by_id(off_lineup, recv_id)
            recv_pos = stop.get("receiver_pos")
            recv_coord = _lineup_starts_by_pos(off_lineup).get(recv_pos or "", bh_end)
            from BackEnd.utils.fb_geo_helpers import pick_nearest_contesting_defender

            contested, shot_def_id = pick_nearest_contesting_defender(
                end_coords, recv_coord, is_away_offense=is_away_offense
            )
            shot_defender = _player_by_id(def_lineup, shot_def_id)
            shot_type = "attack"
            shooter = receiver or ball_handler
            shooter_loc = recv_coord
            pass_info = {"receiver_id": recv_id, "receiver_pos": recv_pos}
        else:
            shot_type = stop.get("shot_type") or "outside"
            shooter = ball_handler
            shooter_loc = bh_end
            shot_defender = stopper
            contested = True
            pass_info = None

        _record_outlet(True)
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
        rebound_type = rebound_ball_spot = rebound_attemptors = rebounder_pid = None
        if made:
            shooter.record_stat("FGA")
            apply_scoring(game, off_team, shooter, 2, ["FGM"])
            shooter.record_stat("FB_PTS", amount=2)
            text_tail = "and scores!"
            possession_flips = not shot["has_and_one"]
        else:
            shooter.record_stat("FGA")
            possession_flips, rebound_type, rebound_ball_spot, rebound_attemptors, rebounder_pid = (
                _resolve_rebound_on_miss(
                    game=game,
                    stealer=shooter,
                    stealer_id=_safe_id(shooter) or bh_id,
                    end_coords=end_coords,
                    is_away_offense=is_away_offense,
                    d_foul=d_foul,
                )
            )
            text_tail = "but misses."

        turn_result = _finalize(
            {
                "result_type": "MAKE" if made else "MISS",
                "ball_handler": ball_handler,
                "shooter": shooter,
                "shooter_id": _safe_id(shooter),
                "defender": shot_defender,
                "text": f"Fast Break! {get_name_safe(ball_handler)} pushes, {text_tail}",
                "possession_flips": possession_flips,
                "next_play_type": "BASELINE_INBOUND" if made else "HCO",
                "shot_type": shot_type,
                "shot_score": shot["shot_score"],
                "cr_end_coords": end_coords,
                "contested": contested,
                "shot_defender_id": shot["shot_defender_id"],
                "t_shooter_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                "meet_coords": dict(bh_end),
                "bh_target": dict(shooter_loc),
                "stop_decision_action": action,
                "pass_info": pass_info,
                "time_elapsed": max(1, int(round(t_drive + 1.0))),
            },
            shot_attempted=True,
        )
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
        select_and_stamp_shot_micro(turn_result, **shot["select_and_stamp_shot_micro_kwargs"])
        return turn_result

    # --- NO_MEET / POS_O rim finish -----------------------------------------
    bh_target = dict(shot_spot)
    end_coords = _build_offense_end_coords(
        stealer_id=bh_id,
        bh_end=bh_target,
        off_lineup=off_lineup,
        t_elapsed=t_drive,
        is_away_offense=is_away_offense,
        base_end_coords=dict(drive.get("defender_end_coords") or {}),
    )
    shot_defender = _player_by_id(def_lineup, drive.get("shot_defender_id"))
    contested = bool(drive.get("contested"))
    _record_outlet(True)
    shot = _resolve_shot_attempt(
        game=game,
        shooter=ball_handler,
        shooter_location=bh_target,
        shot_defender=shot_defender,
        contested=contested,
        shot_type="attack",
        is_paint=True,
    )
    made = shot["made"]
    d_foul = shot["d_foul"]
    pressure_type = None
    rebound_type = rebound_ball_spot = rebound_attemptors = rebounder_pid = None
    if made:
        ball_handler.record_stat("FGA")
        apply_scoring(game, off_team, ball_handler, 2, ["FGM"])
        ball_handler.record_stat("FB_PTS", amount=2)
        text_tail = "and finishes!"
        possession_flips = not shot["has_and_one"]
        if not shot["has_and_one"]:
            try:
                pressure_type = game.turn_manager.determine_defensive_pressure_type()
            except Exception:
                pressure_type = "HCO"
            game_state["offensive_state"] = pressure_type or "HCO"
    else:
        ball_handler.record_stat("FGA")
        possession_flips, rebound_type, rebound_ball_spot, rebound_attemptors, rebounder_pid = (
            _resolve_rebound_on_miss(
                game=game,
                stealer=ball_handler,
                stealer_id=bh_id,
                end_coords=end_coords,
                is_away_offense=is_away_offense,
                d_foul=d_foul,
            )
        )
        text_tail = "but misses."

    turn_result = _finalize(
        {
            "result_type": "MAKE" if made else "MISS",
            "ball_handler": ball_handler,
            "shooter": ball_handler,
            "shooter_id": bh_id,
            "defender": shot_defender,
            "text": f"Fast Break! {get_name_safe(ball_handler)} pushes, {text_tail}",
            "possession_flips": possession_flips,
            "next_play_type": "BASELINE_INBOUND",
            "shot_type": "attack",
            "shot_score": shot["shot_score"],
            "shot_score_pre_defense": shot["shot_score_pre_defense"],
            "shot_defense_score_for_sfx": shot["shot_defense_score_for_sfx"],
            "shot_variant": shot.get("shot_variant"),
            "cr_end_coords": end_coords,
            "contested": contested,
            "shot_defender_id": shot["shot_defender_id"],
            "t_shooter_game_seconds": t_drive,
            "bh_target": dict(bh_target),
            "time_elapsed": max(1, int(round(t_drive + 1.0))),
        },
        shot_attempted=True,
    )
    if made and pressure_type:
        turn_result["next_defensive_setup"] = pressure_type
    if made:
        turn_result["points"] = 2
        turn_result["scoring_team"] = off_team.name
    if not made and not d_foul and rebound_type:
        turn_result["rebound_type"] = rebound_type
        turn_result["rebounderId"] = rebounder_pid
        turn_result["next_play_type"] = "OREB" if rebound_type == "OREB" else "HCO"
    turn_result["sfx"] = {
        "shot_type": "attack",
        "shot_score_pre_defense": shot["shot_score_pre_defense"],
        "shot_defense_score_for_sfx": shot["shot_defense_score_for_sfx"],
        "shot_variant": shot.get("shot_variant"),
    }
    select_and_stamp_shot_micro(turn_result, **shot["select_and_stamp_shot_micro_kwargs"])
    if shot.get("shot_variant_extras"):
        turn_result.update(shot["shot_variant_extras"])
    return turn_result
