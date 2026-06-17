"""Dynamic-HCT shot resolution (§7 Goal Achievement).

Cut 2 / Phase 2D-1 — the **broken-HCT fast break (D18)**.

When a broken-HCT open-floor attack reaches the topLane spot (the perfect PSA
spot is behind the ball handler), the offense has beaten the trap with a
numbers/space advantage and attacks the rim. This resolves the equivalent of a
Steal Fast Break (``after_steal_fast_break``): the dribbler drives to the
basket and we resolve a single contested-vs-uncontested rim attempt against the
**one defender closest to the basket** (the lone rim protector — not all five
sprinting back, per the D18 reuse note).

This module owns only the *resolution* (geometry + shot score + make/miss +
rebound/foul/possession + stats). The pre-shot choreography (entry walk-up +
loop segments up to the topLane drive) is produced by ``dynamic_hct`` and the
drive + post-shot sub-steps are rendered by ``dynamic_hct_step_emitter``.

Reuse
-----
- ``fast_break_shot_geometry.compute_fb_shot_geometry`` — shooter target,
  rim-defender race, contested decision, ``t_shooter``.
- ``ShotManager.calculate_shot_score`` — same call shape as after_steal.
- ``skeleton_step_emitter._build_post_shot_sub_steps`` (called by the emitter)
  consumes the standard shot fields stamped here.

Outputs (turn_result fields consumed by the emitter)
----------------------------------------------------
Standard shot turn fields (``result_type`` MAKE/MISS, ``shooter``,
``shot_variant``, ``points``/scoring on make, ``ball_bounce_x/y`` + rebound on
miss, foul fields) plus the HCT-FB drive seed:

- ``hct_fb_shooter_id`` — the driving ball handler (presence flags the FB-shot
  path to the emitter).
- ``hct_fb_bh_target`` — the shooter's rim target.
- ``hct_fb_defender_end`` — ``{defender_id: {x, y}}`` end coord for the rim
  protector at the shot moment.
- ``hct_fb_t_shooter`` — shooter traversal time (drive step ``T_game_seconds``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from BackEnd.constants import AWAY_RIM_COORDS, HOME_RIM_COORDS


def _safe_id(p: Any) -> Optional[str]:
    if p is None:
        return None
    if isinstance(p, str):
        return p
    pid = getattr(p, "player_id", None)
    return str(pid) if pid is not None else None


def _euclid(a: Dict[str, float], b: Dict[str, float]) -> float:
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def _clampf(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def resolve_hct_fast_break_shot(game: Any, dyn: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the D18 broken-HCT fast-break rim attempt.

    ``dyn`` is the ``compute_dynamic_hct_turn`` return dict; ``dyn["fb_seed"]``
    carries the shooter position and the post-drive offense/defense coords (by
    position, current orientation). Returns a shot turn_result dict (the caller
    merges the HCT loop intermediate data into it for the emitter).
    """
    from BackEnd.models.shot_manager import ShotManager
    from BackEnd.utils.shared import (
        apply_scoring,
        calculate_bounce_spot,
        determine_rebounder,
        get_name_safe,
        increment_no_defender_shot_breakdown,
    )
    from BackEnd.constants.shot_variants import (
        select_shot_variant,
        roll_shot_variant_extras,
    )
    from BackEnd.utils.fast_break_shot_geometry import compute_fb_shot_geometry

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)

    seed = dyn.get("fb_seed") or {}
    shooter_pos = seed.get("shooter_pos") or "PG"
    seed_off = seed.get("off_coords") or {}
    seed_def = seed.get("def_coords") or {}

    shooter = off_lineup.get(shooter_pos)
    shooter_id = _safe_id(shooter)
    shooter_start = seed_off.get(shooter_pos)

    # --- Rim protector: the single defender closest to the basket -----------
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    basket = {"x": float(rim["x"]), "y": float(rim["y"])}

    rim_defender = None
    rim_defender_id: Optional[str] = None
    rim_defender_start: Optional[Dict[str, float]] = None
    best_dist = None
    for pos, player in def_lineup.items():
        if player is None:
            continue
        coord = seed_def.get(pos)
        if not isinstance(coord, dict):
            continue
        d = _euclid({"x": float(coord["x"]), "y": float(coord["y"])}, basket)
        if best_dist is None or d < best_dist:
            best_dist = d
            rim_defender = player
            rim_defender_id = _safe_id(player)
            rim_defender_start = {"x": float(coord["x"]), "y": float(coord["y"])}

    if shooter is None or shooter_id is None or not isinstance(shooter_start, dict):
        # Defensive bail — should not happen; let the caller fall back to HCO.
        logging.warning("🚨 [HCT_FB] missing shooter seed; bailing to HCO")
        return {"result_type": "HCO", "_hct_fb_bail": True}

    shooter_start = {"x": float(shooter_start["x"]), "y": float(shooter_start["y"])}

    # --- Geometry + contested decision (lone rim protector race pool) --------
    available_defenders: List[Any] = [rim_defender] if rim_defender is not None else []
    defender_starts: Dict[str, Dict[str, float]] = {}
    if rim_defender_id and rim_defender_start is not None:
        defender_starts[rim_defender_id] = rim_defender_start

    geometry = compute_fb_shot_geometry(
        shooter=shooter,
        shooter_start=shooter_start,
        available_defenders=available_defenders,
        defender_starts=defender_starts,
        is_away_offense=is_away_offense,
    )
    bh_target = geometry["shooter_target"]
    contested = geometry["contested"]
    shot_defender_id = geometry["shot_defender_id"]
    t_shooter = geometry["t_shooter_game_seconds"]
    defender_end_coords: Dict[str, Dict[str, float]] = dict(
        geometry["defender_end_coords"]
    )

    shot_defender = rim_defender if (contested and shot_defender_id) else None

    # --- Shot resolution (mirrors after_steal) ------------------------------
    shot_manager = getattr(game, "shot_manager", None) or ShotManager(game)
    defense_playcall = (
        game_state.get("defense_playcall")
        or game_state.get("defense_call")
        or "man"
    )
    shot_type = "inside"  # at-the-rim attack
    is_three = False

    if contested and shot_defender is not None:
        (
            shot_score,
            shot_score_pre_defense,
            shot_defense_score_for_sfx,
            d_foul,
            foul_player,
        ) = shot_manager.calculate_shot_score(
            shooter, None, None, shot_defender, shot_type, defense_playcall,
            is_three, True, None, bh_target, apply_defense=True,
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
        ) = shot_manager.calculate_shot_score(
            shooter, None, None, None, shot_type, defense_playcall,
            is_three, True, None, bh_target, apply_defense=False,
        )
        made = True
        game_state["no_defender_shots"] = int(
            game_state.get("no_defender_shots", 0) or 0
        ) + 1
        increment_no_defender_shot_breakdown(
            game_state, game_state.get("offensive_state"), "hct_fast_break",
        )

    # --- Foul book-keeping (mirrors after_steal / OREB putback) -------------
    has_and_one = False
    free_throws_remaining = 0
    fouled_out_info: Dict[str, Any] = {}
    if d_foul and foul_player:
        from BackEnd.engine.phase_resolution import check_and_handle_foul_out

        foul_player.record_stat("F")
        def_team.team_fouls += 1
        game_state["foul_team"] = "DEFENSE"
        game_state["shooter"] = shooter
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 1 if made else 2
        game_state["free_throws_remaining"] = game_state["free_throws"]
        game_state["one_and_one"] = False
        fouled_out_info = check_and_handle_foul_out(foul_player, game_state, def_team)
        free_throws_remaining = 1 if made else 2
        has_and_one = made

    # --- Variant + extras ---------------------------------------------------
    shot_threshold_for_variant = off_team.team_attributes.get("shot_threshold", 100)
    try:
        shot_variant = select_shot_variant(
            shot_score=shot_score_pre_defense,
            shot_threshold=shot_threshold_for_variant,
            shot_type=shot_type,
            made=made,
        )
        shot_variant_extras = roll_shot_variant_extras(
            shot_variant, shooter_y=bh_target["y"],
        )
    except Exception:
        shot_variant = None
        shot_variant_extras = {}

    # --- Scoring + rebound resolution (mirrors after_steal) -----------------
    rebound_type: Optional[str] = None
    rebounder_pid: Optional[str] = None
    rebound_ball_spot: Optional[Dict[str, float]] = None
    if made:
        shooter.record_stat("FGA")
        apply_scoring(game, off_team, shooter, 2, ["FGM"])
        text_outcome = "and scores, gets fouled!" if has_and_one else "and finishes!"
        possession_flips = not has_and_one
    else:
        shooter.record_stat("FGA")
        possession_flips = False
        if not d_foul:
            basket_x = float(rim["x"])
            bounce_spot = calculate_bounce_spot(game, basket_x=basket_x, basket_y=25)
            penalize_player_ids = {shooter_id} if shooter_id else set()
            exclude_player_ids: set = set()
            new_rebounder, new_team, new_stat = determine_rebounder(
                game, bounce_spot, exclude_player_ids, penalize_player_ids,
            )
            rebound_type = str(new_stat) if new_stat else "DREB"
            rebounder_pid = _safe_id(new_rebounder)
            rebound_ball_spot = {
                "x": float(bounce_spot["x"]),
                "y": float(bounce_spot["y"]),
            }
            if new_rebounder is not None:
                canonical = (
                    new_team.get_player_by_id(rebounder_pid)
                    if rebounder_pid and new_team
                    else None
                )
                (canonical or new_rebounder).record_stat(rebound_type)

            if rebound_type == "OREB" and new_rebounder is not None:
                game_state["pending_oreb"] = {
                    "rebounder": new_rebounder,
                    "rebounder_id": rebounder_pid,
                    "from_block": False,
                }
                possession_flips = False
            else:
                game_state["offensive_state"] = "HCO"
                game_state["last_rebounder"] = new_rebounder
                possession_flips = True

        text_outcome = (
            "but misses, fouled on the shot." if d_foul else "but misses."
        )

    shooter_name = get_name_safe(shooter)
    text_suffix = f" open floor — fast break! {shooter_name} {text_outcome}"

    # --- Pressure-type for the next possession (make, no and-1) -------------
    pressure_type: Optional[str] = None
    if made and not has_and_one:
        try:
            pressure_type = game.turn_manager.determine_defensive_pressure_type()
        except Exception as e:
            logging.warning("🚨 [HCT_FB] pressure-type failed: %s; HCO", e)
            pressure_type = "HCO"
        game_state["offensive_state"] = pressure_type

    # --- next_play_type -----------------------------------------------------
    if has_and_one:
        next_play_type = "FREE_THROW"
    elif made:
        next_play_type = "BASELINE_INBOUND"
    elif d_foul and free_throws_remaining > 0:
        next_play_type = "FREE_THROW"
    elif rebound_type == "OREB":
        next_play_type = "OREB"
    else:
        next_play_type = "HCO"

    result_type = "MAKE" if made else "MISS"
    turn_result: Dict[str, Any] = {
        "result_type": result_type,
        "current_turn": "HCT",
        "ball_handler": shooter,
        "shooter": shooter,
        "shooter_id": shooter_id,
        "shooter_team_id": off_team.team_id,
        "defender": shot_defender,
        "defender_id": _safe_id(shot_defender),
        "text_suffix": text_suffix,
        "possession_flips": possession_flips,
        "offense_team_id": off_team.team_id,
        "quarter": game.quarter,
        "next_play_type": next_play_type,
        "next_turn": next_play_type,
        "shot_type": shot_type,
        "shot_score": shot_score,
        "shot_score_pre_defense": shot_score_pre_defense,
        "shot_defense_score_for_sfx": shot_defense_score_for_sfx,
        "shot_variant": shot_variant,
        "sfx": {
            "shot_type": shot_type,
            "shot_score_pre_defense": shot_score_pre_defense,
            "shot_defense_score_for_sfx": shot_defense_score_for_sfx,
            "shot_variant": shot_variant,
        },
        # --- HCT-FB drive seed for the emitter ---
        "hct_fb_shooter_id": shooter_id,
        "hct_fb_bh_target": {"x": float(bh_target["x"]), "y": float(bh_target["y"])},
        "hct_fb_defender_end": {
            did: {"x": float(c["x"]), "y": float(c["y"])}
            for did, c in defender_end_coords.items()
        },
        "hct_fb_t_shooter": float(t_shooter),
        "hct_fb_contested": contested,
    }
    if made:
        turn_result["points"] = 2
        turn_result["scoring_team"] = off_team.name
        if pressure_type is not None:
            turn_result["next_defensive_setup"] = pressure_type
    else:
        if rebound_ball_spot is not None:
            turn_result["ball_bounce_x"] = rebound_ball_spot["x"]
            turn_result["ball_bounce_y"] = rebound_ball_spot["y"]
        else:
            turn_result["ball_bounce_x"] = float(rim["x"])
            turn_result["ball_bounce_y"] = float(rim["y"])
        if rebound_type is not None:
            turn_result["rebound_type"] = rebound_type
            turn_result["rebounderId"] = rebounder_pid
            if rebound_ball_spot is not None:
                turn_result["ballSpot"] = dict(rebound_ball_spot)

    if shot_variant_extras:
        turn_result.update(shot_variant_extras)

    if d_foul and foul_player:
        turn_result["foul_player_id"] = _safe_id(foul_player)
        turn_result["foul_team"] = "DEFENSE"
        turn_result["free_throws_remaining"] = free_throws_remaining
        if has_and_one:
            turn_result["has_and_one"] = True
        if fouled_out_info.get("fouled_out"):
            turn_result["fouled_out"] = True
            turn_result["foul_out_player"] = {
                "player_id": fouled_out_info["foul_player_id"],
                "name": fouled_out_info["foul_player_name"],
                "photo": fouled_out_info["foul_player_photo"],
                "team": fouled_out_info["foul_player_team"],
            }
            turn_result["foul_count"] = fouled_out_info["foul_count"]

    return turn_result


# --- §7 in-Attack-Basket shot (2D-2a: shoot-in-place) ----------------------

# Shot-gather → release beat (game-seconds). The defenders collapse for this
# long, and the D6 contest is evaluated at their release-time positions.
AB_SHOT_BEAT_SECONDS = 0.8
# D6 shot-defender proximity box (relative to the shooter, in grid spots).
AB_SHOT_DEFENDER_X_BOX = 4
AB_SHOT_DEFENDER_Y_BOX = 6
# Distance-to-rim split for the shoot-in-place shot type.
AB_INSIDE_SHOT_MAX_DIST = 12.0


def resolve_hct_attack_basket_shot(game: Any, dyn: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the §7 in-Attack-Basket shot attempt (2D-2a — shoot in place).

    ``dyn["ab_seed"]`` carries the shooter position + the offense/defense coords
    at the moment the BH reached the Attack Basket Area. We apply the **D5**
    rim-protection collapse (defenders close toward the rim cluster), pick the
    **D6** shot defender (any defender ending within 4x/6y of the shooter at the
    shot release), and resolve a contested-or-not jump shot via
    ``ShotManager.calculate_shot_score`` (no auto-make — half-court shots are
    rolled against the threshold). Returns a shot turn_result; the caller merges
    the HCT loop intermediate data for the emitter.
    """
    from BackEnd.models.shot_manager import ShotManager
    from BackEnd.utils.shared import (
        apply_scoring,
        calculate_bounce_spot,
        determine_rebounder,
        get_name_safe,
    )
    from BackEnd.constants.shot_variants import (
        select_shot_variant,
        roll_shot_variant_extras,
    )
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec
    from BackEnd.utils.transition_bridge import _interrupted_coord
    from BackEnd.engine.dynamic_hct import (
        RIM_PROTECT_X_MIN,
        RIM_PROTECT_X_MAX,
        RIM_PROTECT_Y_MIN,
        RIM_PROTECT_Y_MAX,
    )

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)

    seed = dyn.get("ab_seed") or {}
    shooter_pos = seed.get("shooter_pos") or "PG"
    seed_off = seed.get("off_coords") or {}
    seed_def = seed.get("def_coords") or {}

    shooter = off_lineup.get(shooter_pos)
    shooter_id = _safe_id(shooter)
    shooter_start = seed_off.get(shooter_pos)

    if shooter is None or shooter_id is None or not isinstance(shooter_start, dict):
        logging.warning("🚨 [HCT_AB] missing shooter seed; bailing to HCO")
        return {"result_type": "HCO", "_hct_ab_bail": True}

    shooter_start = {"x": float(shooter_start["x"]), "y": float(shooter_start["y"])}
    bh_target = dict(shooter_start)  # shoot in place

    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    basket = {"x": float(rim["x"]), "y": float(rim["y"])}

    # --- D5 rim-protection collapse (defenders close toward the rim band) ----
    if is_away_offense:
        band_x_lo, band_x_hi = 100 - RIM_PROTECT_X_MAX, 100 - RIM_PROTECT_X_MIN
    else:
        band_x_lo, band_x_hi = RIM_PROTECT_X_MIN, RIM_PROTECT_X_MAX

    defender_end_coords: Dict[str, Dict[str, float]] = {}
    for pos, player in def_lineup.items():
        if player is None:
            continue
        did = _safe_id(player)
        start = seed_def.get(pos)
        if did is None or not isinstance(start, dict):
            continue
        start = {"x": float(start["x"]), "y": float(start["y"])}
        target = {
            "x": _clampf(start["x"], band_x_lo, band_x_hi),
            "y": _clampf(start["y"], RIM_PROTECT_Y_MIN, RIM_PROTECT_Y_MAX),
        }
        rate = _ag_grid_per_game_sec(player, "standard")
        end = (
            _interrupted_coord(start, target, rate, AB_SHOT_BEAT_SECONDS)
            if rate > 0
            else dict(target)
        )
        defender_end_coords[did] = {"x": float(end["x"]), "y": float(end["y"])}

    # --- D6 shot defender: nearest defender within 4x/6y of the shooter ------
    shot_defender = None
    shot_defender_id: Optional[str] = None
    best = None
    for pos, player in def_lineup.items():
        did = _safe_id(player)
        if did is None or did not in defender_end_coords:
            continue
        end = defender_end_coords[did]
        if (
            abs(end["x"] - bh_target["x"]) <= AB_SHOT_DEFENDER_X_BOX
            and abs(end["y"] - bh_target["y"]) <= AB_SHOT_DEFENDER_Y_BOX
        ):
            d = _euclid(end, bh_target)
            if best is None or d < best:
                best = d
                shot_defender = player
                shot_defender_id = did
    contested = shot_defender is not None

    # --- Shot type + resolution (rolled vs. threshold, no auto-make) ---------
    dist_to_rim = _euclid(bh_target, basket)
    shot_type = "inside" if dist_to_rim <= AB_INSIDE_SHOT_MAX_DIST else "outside"
    is_three = False

    shot_manager = getattr(game, "shot_manager", None) or ShotManager(game)
    defense_playcall = (
        game_state.get("defense_playcall")
        or game_state.get("defense_call")
        or "man"
    )
    (
        shot_score,
        shot_score_pre_defense,
        shot_defense_score_for_sfx,
        d_foul,
        foul_player,
    ) = shot_manager.calculate_shot_score(
        shooter, None, None, shot_defender if contested else None, shot_type,
        defense_playcall, is_three, True, None, bh_target,
        apply_defense=contested,
    )
    shot_threshold = off_team.team_attributes["shot_threshold"]
    made = shot_score >= shot_threshold

    # --- Foul book-keeping (mirrors after_steal / FB resolver) --------------
    has_and_one = False
    free_throws_remaining = 0
    fouled_out_info: Dict[str, Any] = {}
    if d_foul and foul_player:
        from BackEnd.engine.phase_resolution import check_and_handle_foul_out

        foul_player.record_stat("F")
        def_team.team_fouls += 1
        game_state["foul_team"] = "DEFENSE"
        game_state["shooter"] = shooter
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 1 if made else 2
        game_state["free_throws_remaining"] = game_state["free_throws"]
        game_state["one_and_one"] = False
        fouled_out_info = check_and_handle_foul_out(foul_player, game_state, def_team)
        free_throws_remaining = 1 if made else 2
        has_and_one = made

    # --- Variant + extras ---------------------------------------------------
    shot_threshold_for_variant = off_team.team_attributes.get("shot_threshold", 100)
    try:
        shot_variant = select_shot_variant(
            shot_score=shot_score_pre_defense,
            shot_threshold=shot_threshold_for_variant,
            shot_type=shot_type,
            made=made,
        )
        shot_variant_extras = roll_shot_variant_extras(
            shot_variant, shooter_y=bh_target["y"],
        )
    except Exception:
        shot_variant = None
        shot_variant_extras = {}

    # --- Scoring + rebound resolution ---------------------------------------
    rebound_type: Optional[str] = None
    rebounder_pid: Optional[str] = None
    rebound_ball_spot: Optional[Dict[str, float]] = None
    if made:
        shooter.record_stat("FGA")
        apply_scoring(game, off_team, shooter, 2, ["FGM"])
        text_outcome = "and scores, gets fouled!" if has_and_one else "and scores!"
        possession_flips = not has_and_one
    else:
        shooter.record_stat("FGA")
        possession_flips = False
        if not d_foul:
            basket_x = float(rim["x"])
            bounce_spot = calculate_bounce_spot(game, basket_x=basket_x, basket_y=25)
            penalize_player_ids = {shooter_id} if shooter_id else set()
            exclude_player_ids: set = set()
            new_rebounder, new_team, new_stat = determine_rebounder(
                game, bounce_spot, exclude_player_ids, penalize_player_ids,
            )
            rebound_type = str(new_stat) if new_stat else "DREB"
            rebounder_pid = _safe_id(new_rebounder)
            rebound_ball_spot = {
                "x": float(bounce_spot["x"]),
                "y": float(bounce_spot["y"]),
            }
            if new_rebounder is not None:
                canonical = (
                    new_team.get_player_by_id(rebounder_pid)
                    if rebounder_pid and new_team
                    else None
                )
                (canonical or new_rebounder).record_stat(rebound_type)

            if rebound_type == "OREB" and new_rebounder is not None:
                game_state["pending_oreb"] = {
                    "rebounder": new_rebounder,
                    "rebounder_id": rebounder_pid,
                    "from_block": False,
                }
                possession_flips = False
            else:
                game_state["offensive_state"] = "HCO"
                game_state["last_rebounder"] = new_rebounder
                possession_flips = True

        text_outcome = (
            "but misses, fouled on the shot." if d_foul else "but misses."
        )

    shooter_name = get_name_safe(shooter)
    text_suffix = f" they go to work in the paint — {shooter_name} {text_outcome}"

    # --- Pressure-type for the next possession (make, no and-1) -------------
    pressure_type: Optional[str] = None
    if made and not has_and_one:
        try:
            pressure_type = game.turn_manager.determine_defensive_pressure_type()
        except Exception as e:
            logging.warning("🚨 [HCT_AB] pressure-type failed: %s; HCO", e)
            pressure_type = "HCO"
        game_state["offensive_state"] = pressure_type

    # --- next_play_type -----------------------------------------------------
    if has_and_one:
        next_play_type = "FREE_THROW"
    elif made:
        next_play_type = "BASELINE_INBOUND"
    elif d_foul and free_throws_remaining > 0:
        next_play_type = "FREE_THROW"
    elif rebound_type == "OREB":
        next_play_type = "OREB"
    else:
        next_play_type = "HCO"

    result_type = "MAKE" if made else "MISS"
    turn_result: Dict[str, Any] = {
        "result_type": result_type,
        "current_turn": "HCT",
        "ball_handler": shooter,
        "shooter": shooter,
        "shooter_id": shooter_id,
        "shooter_team_id": off_team.team_id,
        "defender": shot_defender,
        "defender_id": shot_defender_id,
        "text_suffix": text_suffix,
        "possession_flips": possession_flips,
        "offense_team_id": off_team.team_id,
        "quarter": game.quarter,
        "next_play_type": next_play_type,
        "next_turn": next_play_type,
        "shot_type": shot_type,
        "shot_score": shot_score,
        "shot_score_pre_defense": shot_score_pre_defense,
        "shot_defense_score_for_sfx": shot_defense_score_for_sfx,
        "shot_variant": shot_variant,
        "sfx": {
            "shot_type": shot_type,
            "shot_score_pre_defense": shot_score_pre_defense,
            "shot_defense_score_for_sfx": shot_defense_score_for_sfx,
            "shot_variant": shot_variant,
        },
        # --- HCT in-Attack-Basket shot seed for the emitter ---
        "hct_ab_shooter_id": shooter_id,
        "hct_ab_shooter_target": {"x": float(bh_target["x"]), "y": float(bh_target["y"])},
        "hct_ab_defender_end": {
            did: {"x": float(c["x"]), "y": float(c["y"])}
            for did, c in defender_end_coords.items()
        },
        "hct_ab_t_shot": float(AB_SHOT_BEAT_SECONDS),
        "hct_ab_contested": contested,
    }
    if made:
        turn_result["points"] = 2
        turn_result["scoring_team"] = off_team.name
        if pressure_type is not None:
            turn_result["next_defensive_setup"] = pressure_type
    else:
        if rebound_ball_spot is not None:
            turn_result["ball_bounce_x"] = rebound_ball_spot["x"]
            turn_result["ball_bounce_y"] = rebound_ball_spot["y"]
        else:
            turn_result["ball_bounce_x"] = float(rim["x"])
            turn_result["ball_bounce_y"] = float(rim["y"])
        if rebound_type is not None:
            turn_result["rebound_type"] = rebound_type
            turn_result["rebounderId"] = rebounder_pid
            if rebound_ball_spot is not None:
                turn_result["ballSpot"] = dict(rebound_ball_spot)

    if shot_variant_extras:
        turn_result.update(shot_variant_extras)

    if d_foul and foul_player:
        turn_result["foul_player_id"] = _safe_id(foul_player)
        turn_result["foul_team"] = "DEFENSE"
        turn_result["free_throws_remaining"] = free_throws_remaining
        if has_and_one:
            turn_result["has_and_one"] = True
        if fouled_out_info.get("fouled_out"):
            turn_result["fouled_out"] = True
            turn_result["foul_out_player"] = {
                "player_id": fouled_out_info["foul_player_id"],
                "name": fouled_out_info["foul_player_name"],
                "photo": fouled_out_info["foul_player_photo"],
                "team": fouled_out_info["foul_player_team"],
            }
            turn_result["foul_count"] = fouled_out_info["foul_count"]

    return turn_result
