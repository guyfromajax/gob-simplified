"""Rim Runner / Triangle attack-drive integration (Phase 4).

Replaces ``_apply_universal_geometry_for_rr_shot`` + ``resolve_shot`` on finisher
attack paths with ``resolve_fb_drive_step``. Spot-up Triangle branches use unified
11 + x-trail contest only (no drive resolver).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from BackEnd.constants.fast_break_play_types import RIM_RUNNER, TRIANGLE, ensure_fast_break_plays
from BackEnd.engine.after_steal_drive_integration import (
    _build_offense_end_coords,
    _compute_bh_target,
    _coord_of,
    _fb_shot_next_play_type,
    _lineup_pos,
    _lineup_starts_by_pos,
    _player_by_id,
    _resolve_rebound_on_miss,
    _resolve_shot_attempt,
    _safe_id,
    _stamp_fb_shooting_foul_on_turn,
)
from BackEnd.utils.player_momentum import apply_made_dunk_momentum
from BackEnd.engine.fb_drive_resolution import resolve_fb_drive_step
from BackEnd.engine.phase_resolution import (
    _record_fast_break_stats,
    apply_fast_break_cg_time,
    apply_fb_meet_non_shooting_defensive_foul,
)
from BackEnd.utils.fb_geo_helpers import (
    pick_nearest_contesting_defender,
    stamp_fb_miss_bounce_coords,
)
from BackEnd.utils.shared import apply_scoring, get_name_safe
from BackEnd.utils.position_snapshot_ledger import attach_position_snapshots, build_fast_break_pre_shot_snapshot


def _drive_onset_coord(
    fb_roles: Dict[str, Any],
    shooter: Any,
) -> Dict[str, float]:
    """Value-correcting drive-onset seed for the finisher drive resolver.

    Sourced from the same backend geometry the UESS step emitters render the
    drive from, so resolver logic and animation converge on one catch /
    drive-onset spot (instead of the legacy ``capture_fast_break_animation``
    packet, whose shooter ``end`` is a rim-relative random rebounder spot or a
    ``player.coords`` fallback that already diverges from the rendered drive):

    - Rim Runner: the RR's lead-pass catch target
      (``rim_runner_burst_phase.rr_to``), which the emitter uses as the
      lane-pass ``catch_grid`` (see ``rim_runner_step_emitter._build_lane_pass_step``).
    - Triangle ``triangle_bh_drive``: the ball handler's triangle setup spot
      (``triangle_setup_phase.ball_handler_to``), which the emitter moves him to
      in the setup step before driving to ``triangle_drive_to``
      (see ``triangle_step_emitter``).

    Never reads the legacy animation packet. Falls back to the shooter's live
    ``player.coords`` if neither backend datum is available.
    """
    burst = fb_roles.get("rim_runner_burst_phase") or {}
    rr_to = burst.get("rr_to")
    if isinstance(rr_to, dict) and "x" in rr_to and "y" in rr_to:
        return {"x": float(rr_to["x"]), "y": float(rr_to["y"])}

    if fb_roles.get("triangle_branch") == "triangle_bh_drive":
        setup = fb_roles.get("triangle_setup_phase") or {}
        bh_to = setup.get("ball_handler_to")
        if isinstance(bh_to, dict) and "x" in bh_to and "y" in bh_to:
            return {"x": float(bh_to["x"]), "y": float(bh_to["y"])}

    return _coord_of(shooter)


def _pick_unified_contest_defender(
    def_lineup: Dict[str, Any],
    shot_spot: Dict[str, float],
    *,
    is_away_offense: bool,
) -> Tuple[Optional[Any], bool]:
    def_ends: Dict[str, Dict[str, float]] = {}
    for defender in def_lineup.values():
        if defender is None:
            continue
        pid = _safe_id(defender)
        if pid:
            def_ends[pid] = _coord_of(defender)
    contested, def_id = pick_nearest_contesting_defender(
        def_ends, shot_spot, is_away_offense=is_away_offense
    )
    return _player_by_id(def_lineup, def_id), contested


def _drive_resolution_enabled(fb_play_key: str) -> bool:
    from BackEnd.constants import (
        USE_FB_DRIVE_RESOLUTION_RR,
        USE_FB_DRIVE_RESOLUTION_TRIANGLE,
    )

    if fb_play_key == RIM_RUNNER:
        return bool(USE_FB_DRIVE_RESOLUTION_RR)
    if fb_play_key == TRIANGLE:
        return bool(USE_FB_DRIVE_RESOLUTION_TRIANGLE)
    return False


def _apply_finisher_scouting(
    turn_result: Dict[str, Any],
    *,
    off_team: Any,
    def_team: Any,
    fb_play_key: str,
) -> None:
    rt = turn_result.get("result_type")
    if rt == "MAKE":
        off_team.scouting_data["offense"]["Fast_Break_Success"] = (
            off_team.scouting_data["offense"].get("Fast_Break_Success", 0) + 1
        )
        ensure_fast_break_plays(off_team.scouting_data["offense"])[fb_play_key]["S"] += 1
    elif rt == "MISS":
        def_team.scouting_data["defense"]["vs_Fast_Break"]["success"] = (
            def_team.scouting_data["defense"]["vs_Fast_Break"].get("success", 0) + 1
        )
    elif rt == "DEFENSIVE_STOP":
        def_team.scouting_data["defense"]["vs_Fast_Break"]["success"] = (
            def_team.scouting_data["defense"]["vs_Fast_Break"].get("success", 0) + 1
        )


def _rendered_starts_by_pos(
    lineup: Dict[str, Any], rendered_by_id: Dict[str, Dict[str, float]]
) -> Dict[str, Dict[str, float]]:
    """Map the emitter's rendered ``{player_id: coord}`` to ``{pos: coord}`` for
    the resolver's start-of-drive seeds — the single-coord-source seat. Falls back
    to the player's live coord for any id the render didn't cover."""
    out: Dict[str, Dict[str, float]] = {}
    for pos, p in (lineup or {}).items():
        if p is None:
            continue
        pid = _safe_id(p)
        c = rendered_by_id.get(pid) if pid else None
        out[pos] = (
            {"x": float(c["x"]), "y": float(c["y"])}
            if c
            else _coord_of(p)  # coord-source-ok: per-player fallback when render lacks this id
        )
    return out


def resolve_attack_drive_finisher_turn(
    *,
    game: Any,
    shooter: Any,
    shot_spot: Optional[Dict[str, float]],
    fb_roles: Dict[str, Any],
    fb_animations: List[Dict[str, Any]],
    fb_play_key: str,
    off_team: Any,
    def_team: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    ball_handler: Any = None,
    passer: Any = None,
    pass_attempted: Optional[bool] = None,
    fb_open: Optional[bool] = None,
    apply_rr_metadata=None,
    rr_snap_roles: Optional[Dict[str, Any]] = None,
    extra_turn_fields: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve an attack-drive finisher via ``resolve_fb_drive_step``."""
    if not _drive_resolution_enabled(fb_play_key):
        return None

    from BackEnd.engine.shot_micro_movements import select_and_stamp_shot_micro
    from BackEnd.models.shot_manager import ShotManager

    shooter_id = _safe_id(shooter)
    if shooter is None or shooter_id is None:
        return None

    game_state = game.game_state
    # Seed the drive-onset from live/backend geometry (the same catch/setup spot
    # the UESS step emitters render the drive from), NOT the legacy
    # `capture_fast_break_animation` packet. The animation packet's shooter `end`
    # is a rim-relative random rebounder spot (or a `player.coords` fallback) that
    # already diverges from the rendered drive, which desynced resolver geometry
    # (phantom stops / wrong-spot shots) from the animation.
    bh_start = _drive_onset_coord(fb_roles, shooter)
    bh_pos = _lineup_pos(off_lineup, shooter)
    target = dict(shot_spot) if shot_spot else _compute_bh_target(is_away_offense)
    # UESS emit-then-resolve (single-coord-source): build the drive PREAMBLE
    # (burst→outlet→lane-pass) first and seed the cutoff/meet/contest race from
    # the RENDERED drive-start coords (the lane-pass end) — where the defenders
    # actually got back to ON SCREEN — NOT stale start-of-break `player.coords`.
    # (The prior seeding used player.coords because the LEGACY animator teleported
    # get-back defenders near the rim; the UESS lane-pass render is honest, so we
    # read it.) Stash the preamble in fb_roles so the emitter REUSES it — one
    # build, one RNG draw. Falls back to player.coords only if it can't be built.
    from BackEnd.engine.rim_runner_step_emitter import build_rr_drive_preamble

    _preamble = build_rr_drive_preamble({"roles": fb_roles}, game)
    if _preamble is not None:
        _pre_steps, _lane_end = _preamble
        fb_roles["rr_preamble_steps"] = _pre_steps
        fb_roles["rr_drive_start_coords"] = _lane_end
        def_starts = _rendered_starts_by_pos(def_lineup, _lane_end)
        off_starts = _rendered_starts_by_pos(off_lineup, _lane_end)
    else:
        def_starts = _lineup_starts_by_pos(def_lineup)  # coord-source-ok: fallback when no rendered preamble
        off_starts = _lineup_starts_by_pos(off_lineup)  # coord-source-ok: fallback when no rendered preamble
    shot_manager = getattr(game, "shot_manager", None) or ShotManager(game)

    drive = resolve_fb_drive_step(
        bh=shooter,
        bh_pos=bh_pos,
        bh_start=bh_start,
        shot_spot=target,
        off_lineup=off_lineup,
        off_starts=off_starts,
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
    shooter_name = get_name_safe(shooter)
    prefix = "Fast Break! "

    def _base(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        turn: Dict[str, Any] = {
            "current_turn": "FAST_BREAK",
            "fast_break": True,
            "fast_break_play": fb_play_key,
            "fb_drive_resolution": drive,
            "roles": fb_roles,
            "animations": fb_animations,
            "offense_team_id": off_team.team_id,
            "quarter": game.quarter,
            "score": dict(game.score),
            "ball_handler": ball_handler or shooter,
        }
        if extra:
            turn.update(extra)
        if extra_turn_fields:
            turn.update(extra_turn_fields)
        if apply_rr_metadata is not None and pass_attempted is not None and fb_open is not None:
            apply_rr_metadata(turn, pass_attempted=pass_attempted, fb_open=fb_open)
        return turn

    # --- Terminal meet outcomes ---------------------------------------------
    if outcome in ("DEAD BALL", "O_FOUL", "D_FOUL", "CHARGE", "BLOCKING_FOUL"):
        bh_end = meet or dict(target)
        end_coords = _build_offense_end_coords(
            stealer_id=shooter_id,
            bh_end=bh_end,
            off_lineup=off_lineup,
            t_elapsed=float(drive.get("t_meet_game_seconds") or t_drive),
            is_away_offense=is_away_offense,
            base_end_coords=dict(drive.get("defender_end_coords") or {}),
        )
        stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
        credited = _player_by_id(def_lineup, drive.get("d8_credited_player_id"))
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
            foul_player = shooter if outcome == "CHARGE" else credited
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
                ball_handler=shooter,
                foul_player=foul_player,
                time_elapsed_override=max(1, int(round(t_drive + 0.5))),
            )
            possession_flips = foul_transition["possession_flips"]
            next_play_type = foul_transition["next_play_type"]
            next_turn = foul_transition["next_turn"]

        turn_result = _base(
            {
                "result_type": result_type,
                "shooter": shooter,
                "shooter_id": shooter_id,
                "stopper_id": drive.get("stopper_id"),
                "text": prefix + text_tail,
                "possession_flips": possession_flips,
                "next_play_type": next_play_type,
                "next_turn": next_turn,
                "rr_end_coords": end_coords,
                "meet_coords": dict(bh_end),
                "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                "bh_target": dict(bh_end),
                "time_elapsed": max(1, int(round(t_drive + 0.5))),
            }
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
        _record_fast_break_stats(fb_roles, turn_result, game)
        apply_fast_break_cg_time(turn_result, shot_attempted=False)
        return turn_result

    # --- NEUTRAL stop -------------------------------------------------------
    if outcome == "NEUTRAL":
        stop = drive.get("stop_decision") or {}
        action = stop.get("action", "HCO")
        bh_end = meet or dict(target)
        end_coords = _build_offense_end_coords(
            stealer_id=shooter_id,
            bh_end=bh_end,
            off_lineup=off_lineup,
            t_elapsed=float(drive.get("t_meet_game_seconds") or t_drive),
            is_away_offense=is_away_offense,
            base_end_coords=dict(drive.get("defender_end_coords") or {}),
        )

        if action == "HCO":
            game_state["offensive_state"] = "HCO"
            stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
            stopper_name = get_name_safe(stopper) if stopper else "Defense"
            turn_result = _base(
                {
                    "result_type": "DEFENSIVE_STOP",
                    "defender": stopper,
                    "stopper_id": drive.get("stopper_id"),
                    "text": f"{prefix}Nice stop by {stopper_name}!",
                    "possession_flips": False,
                    "next_play_type": "HCO",
                    "next_turn": "HCO",
                    "rr_end_coords": end_coords,
                    "meet_coords": dict(bh_end),
                    "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                    "bh_target": dict(bh_end),
                    "time_elapsed": max(1, int(round(t_drive + 1.0))),
                }
            )
            _apply_finisher_scouting(turn_result, off_team=off_team, def_team=def_team, fb_play_key=fb_play_key)
            _record_fast_break_stats(fb_roles, turn_result, game)
            apply_fast_break_cg_time(turn_result, shot_attempted=False)
            return turn_result

        stopper = _player_by_id(def_lineup, drive.get("stopper_id"))
        if action == "pass":
            recv_id = stop.get("receiver_id")
            receiver = _player_by_id(off_lineup, recv_id)
            recv_pos = stop.get("receiver_pos")
            recv_coord = _lineup_starts_by_pos(off_lineup).get(recv_pos or "", bh_end)
            contest_ends = drive.get("rendered_defender_end_coords") or end_coords
            contested, shot_def_id = pick_nearest_contesting_defender(
                contest_ends, recv_coord, is_away_offense=is_away_offense
            )
            shot_defender = _player_by_id(def_lineup, shot_def_id)
            shot_type = "attack"
            shot_shooter = receiver or shooter
            shooter_loc = recv_coord
            pass_info = {"receiver_id": recv_id, "receiver_pos": recv_pos}
        else:
            shot_type = stop.get("shot_type") or "outside"
            shot_shooter = shooter
            shooter_loc = bh_end
            shot_defender = stopper
            contested = True
            pass_info = None

        shot = _resolve_shot_attempt(
            game=game,
            shooter=shot_shooter,
            shooter_location=shooter_loc,
            shot_defender=shot_defender,
            contested=contested,
            shot_type=shot_type,
            is_paint=shot_type == "inside",
        )
        made = shot["made"]
        d_foul = shot["d_foul"]
        rebound_type = rebound_ball_spot = rebound_attemptors = rebounder_pid = None
        pressure_type = None
        if made:
            shot_shooter.record_stat("FGA")
            apply_scoring(game, off_team, shot_shooter, 2, ["FGM"])
            shot_shooter.record_stat("FB_PTS", amount=2)
            text_tail = "and scores!"
            possession_flips = not shot["has_and_one"]
            # Reset offensive_state off FAST_BREAK so the flipped possession
            # after the baseline inbound doesn't loop back into another FB.
            # main.py reads offensive_state at BIP to set the next defensive
            # pressure; without this it stays "FAST_BREAK". Mirrors the
            # after-steal / covert-release make handling.
            if not shot["has_and_one"]:
                try:
                    pressure_type = game.turn_manager.determine_defensive_pressure_type()
                except Exception:
                    pressure_type = "HCO"
                game_state["offensive_state"] = pressure_type or "HCO"
        else:
            shot_shooter.record_stat("FGA")
            possession_flips, rebound_type, rebound_ball_spot, rebound_attemptors, rebounder_pid = (
                _resolve_rebound_on_miss(
                    game=game,
                    stealer=shot_shooter,
                    stealer_id=_safe_id(shot_shooter) or shooter_id,
                    end_coords=end_coords,
                    is_away_offense=is_away_offense,
                    d_foul=d_foul,
                )
            )
            text_tail = "but misses."

        turn_result = _base(
            {
                "result_type": "MAKE" if made else "MISS",
                "shooter": shot_shooter,
                "shooter_id": _safe_id(shot_shooter),
                "defender": shot_defender,
                "text": f"{prefix}{shooter_name} attacks, {text_tail}",
                "possession_flips": possession_flips,
                "next_play_type": _fb_shot_next_play_type(
                    made=made,
                    d_foul=d_foul,
                    has_and_one=shot.get("has_and_one", False),
                ),
                "shot_type": shot_type,
                "shot_score": shot["shot_score"],
                "rr_end_coords": end_coords,
                "contested": contested,
                "shot_defender_id": shot["shot_defender_id"],
                "t_shooter_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                "t_meet_game_seconds": float(drive.get("t_meet_game_seconds") or t_drive),
                "meet_coords": dict(bh_end),
                "bh_target": dict(shooter_loc),
                "stop_decision_action": action,
                "pass_info": pass_info,
                "time_elapsed": max(1, int(round(t_drive + 1.0))),
            }
        )
        if pass_info:
            turn_result["pass_receiver_id"] = pass_info.get("receiver_id")
        if made:
            turn_result["points"] = 2
            turn_result["scoring_team"] = off_team.name
            if pressure_type:
                turn_result["next_defensive_setup"] = pressure_type
        if not made and not d_foul and rebound_type:
            turn_result["rebound_type"] = rebound_type
            turn_result["rebounderId"] = rebounder_pid
            if rebound_ball_spot:
                turn_result["ballSpot"] = dict(rebound_ball_spot)
            if rebound_attemptors:
                turn_result["offense_rebounders"] = rebound_attemptors["offense_rebounders"]
                turn_result["defense_rebounders"] = rebound_attemptors["defense_rebounders"]
            stamp_fb_miss_bounce_coords(turn_result, rebound_ball_spot, shooter_loc)
        _stamp_fb_shooting_foul_on_turn(turn_result, shot)
        select_and_stamp_shot_micro(turn_result, **shot["select_and_stamp_shot_micro_kwargs"])
        apply_made_dunk_momentum(
            shot["select_and_stamp_shot_micro_kwargs"]["shooter_player"],
            made=bool(shot["made"]),
            family_id=turn_result.get("micro_movement_family"),
        )
        _apply_finisher_scouting(turn_result, off_team=off_team, def_team=def_team, fb_play_key=fb_play_key)
        _record_fast_break_stats(fb_roles, turn_result, game)
        apply_fast_break_cg_time(turn_result, shot_attempted=True)
        return turn_result

    # --- NO_MEET / POS_O rim finish -----------------------------------------
    bh_target = dict(target)
    end_coords = _build_offense_end_coords(
        stealer_id=shooter_id,
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
        shooter=shooter,
        shooter_location=bh_target,
        shot_defender=shot_defender,
        contested=contested,
        shot_type="attack",
        is_paint=True,
    )
    made = shot["made"]
    d_foul = shot["d_foul"]
    rebound_type = rebound_ball_spot = rebound_attemptors = rebounder_pid = None
    pressure_type = None
    if made:
        shooter.record_stat("FGA")
        apply_scoring(game, off_team, shooter, 2, ["FGM"])
        shooter.record_stat("FB_PTS", amount=2)
        text_tail = "and finishes!"
        possession_flips = not shot["has_and_one"]
        # Reset offensive_state off FAST_BREAK on a made finish so the next
        # possession (after the baseline inbound) isn't routed into another FB.
        # Mirrors the after-steal / covert-release make handling.
        if not shot["has_and_one"]:
            try:
                pressure_type = game.turn_manager.determine_defensive_pressure_type()
            except Exception:
                pressure_type = "HCO"
            game_state["offensive_state"] = pressure_type or "HCO"
    else:
        shooter.record_stat("FGA")
        possession_flips, rebound_type, rebound_ball_spot, rebound_attemptors, rebounder_pid = (
            _resolve_rebound_on_miss(
                game=game,
                stealer=shooter,
                stealer_id=shooter_id,
                end_coords=end_coords,
                is_away_offense=is_away_offense,
                d_foul=d_foul,
            )
        )
        text_tail = "but misses."

    turn_result = _base(
        {
            "result_type": "MAKE" if made else "MISS",
            "shooter": shooter,
            "shooter_id": shooter_id,
            "defender": shot_defender,
            "text": f"{prefix}{shooter_name} attacks, {text_tail}",
            "possession_flips": possession_flips,
            "next_play_type": _fb_shot_next_play_type(
                made=made,
                d_foul=d_foul,
                has_and_one=shot.get("has_and_one", False),
            ),
            "shot_type": "attack",
            "shot_score": shot["shot_score"],
            "shot_score_pre_defense": shot["shot_score_pre_defense"],
            "shot_defense_score_for_sfx": shot["shot_defense_score_for_sfx"],
            "shot_variant": shot.get("shot_variant"),
            "rr_end_coords": end_coords,
            "contested": contested,
            "shot_defender_id": shot["shot_defender_id"],
            "t_shooter_game_seconds": t_drive,
            "bh_target": dict(bh_target),
            "time_elapsed": max(1, int(round(t_drive + 1.0))),
        }
    )
    if made:
        turn_result["points"] = 2
        turn_result["scoring_team"] = off_team.name
        if pressure_type:
            turn_result["next_defensive_setup"] = pressure_type
    if not made and not d_foul and rebound_type:
        turn_result["rebound_type"] = rebound_type
        turn_result["rebounderId"] = rebounder_pid
        if rebound_ball_spot:
            turn_result["ballSpot"] = dict(rebound_ball_spot)
        if rebound_attemptors:
            turn_result["offense_rebounders"] = rebound_attemptors["offense_rebounders"]
            turn_result["defense_rebounders"] = rebound_attemptors["defense_rebounders"]
        stamp_fb_miss_bounce_coords(turn_result, rebound_ball_spot, bh_target)
        turn_result["next_play_type"] = "OREB" if rebound_type == "OREB" else "HCO"
    _stamp_fb_shooting_foul_on_turn(turn_result, shot)
    turn_result["sfx"] = {
        "shot_type": "attack",
        "shot_score_pre_defense": shot["shot_score_pre_defense"],
        "shot_defense_score_for_sfx": shot["shot_defense_score_for_sfx"],
        "shot_variant": shot.get("shot_variant"),
    }
    select_and_stamp_shot_micro(turn_result, **shot["select_and_stamp_shot_micro_kwargs"])
    apply_made_dunk_momentum(
        shot["select_and_stamp_shot_micro_kwargs"]["shooter_player"],
        made=bool(shot["made"]),
        family_id=turn_result.get("micro_movement_family"),
    )
    if shot.get("shot_variant_extras"):
        turn_result.update(shot["shot_variant_extras"])
    if rr_snap_roles:
        rr_snap = build_fast_break_pre_shot_snapshot(
            game, off_lineup, def_lineup, rr_snap_roles, "fb_rr_pre_shot"
        )
        attach_position_snapshots(turn_result, [rr_snap])
    _apply_finisher_scouting(turn_result, off_team=off_team, def_team=def_team, fb_play_key=fb_play_key)
    _record_fast_break_stats(fb_roles, turn_result, game)
    apply_fast_break_cg_time(turn_result, shot_attempted=True)
    return turn_result


def apply_triangle_unified_contest(
    *,
    def_lineup: Dict[str, Any],
    shot_spot: Dict[str, float],
    is_away_offense: bool,
    branch: str,
) -> Tuple[Optional[Any], int]:
    """Return (defender, defender_count) using 11 + x-trail contest rules."""
    from BackEnd.constants import USE_FB_DRIVE_RESOLUTION_TRIANGLE

    if not USE_FB_DRIVE_RESOLUTION_TRIANGLE:
        return None, -1
    if branch not in (
        "triangle_corner_three",
        "triangle_bh_wing_three",
        "triangle_drive_corner_kick",
    ):
        return None, -1
    defender, contested = _pick_unified_contest_defender(
        def_lineup, shot_spot, is_away_offense=is_away_offense
    )
    return defender, (1 if contested and defender is not None else 0)
