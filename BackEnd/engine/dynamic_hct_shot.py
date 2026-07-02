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
import random
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from BackEnd.constants import AWAY_RIM_COORDS, CONTEST_EUCLIDEAN_RADIUS, HOME_RIM_COORDS
from BackEnd.constants.momentum import MO_AND_ONE_DELTA
from BackEnd.utils.shot_geometry import classify_shot_value
from BackEnd.utils.shot_split_tracker import record_shot_split


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


def _coords_by_player_id(
    lineup: Dict[str, Any],
    coords_by_pos: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    """Convert position-keyed HCT coords into player-id keyed coords."""
    out: Dict[str, Dict[str, float]] = {}
    for pos, player in (lineup or {}).items():
        pid = _safe_id(player)
        coords = (coords_by_pos or {}).get(pos)
        if pid is None or not isinstance(coords, dict):
            continue
        try:
            out[pid] = {"x": float(coords["x"]), "y": float(coords["y"])}
        except (KeyError, TypeError, ValueError):
            continue
    return out


@contextmanager
def _temporary_lineup_coords(
    game: Any,
    coords_by_player_id: Dict[str, Dict[str, float]],
) -> Iterator[None]:
    """Temporarily apply HCT shot-moment coords for geography reads.

    Dynamic HCT shot resolvers carry authoritative shot-moment positions in
    seeds, while generic rebound helpers read ``player.coords``. This context
    keeps rebound winner selection and failed-attemptor collection in the same
    coordinate frame without leaking those temporary coords beyond resolution.
    """
    originals: Dict[str, tuple[Any, Any]] = {}
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
        collect_near_bounce_rebound_attemptors,
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
            shot_defense_score_raw,
        ) = shot_manager.calculate_shot_score(
            shooter, None, None, shot_defender, shot_type, defense_playcall,
            is_three, True, None, bh_target, apply_defense=True,
        )
        from BackEnd.engine.shot_micro_movements import resolve_contest
        contest_result, contest_margin = resolve_contest(
            shot_score_pre_defense, shot_defense_score_raw,
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
            _shot_defense_score_raw,
        ) = shot_manager.calculate_shot_score(
            shooter, None, None, None, shot_type, defense_playcall,
            is_three, True, None, bh_target, apply_defense=False,
        )
        contest_result = None
        contest_margin = None
        shot_defense_score_raw = 0.0
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
        fouled_out_info = check_and_handle_foul_out(foul_player, game_state, def_team, perform_removal=False)
        free_throws_remaining = 1 if made else 2
        has_and_one = made

    # Player Momentum (Player_Momentum_System.md): self-contained HCT shot path
    # bypasses ShotManager.resolve_shot — record the FG attempt for the
    # consecutive-shot streak (skip a miss that drew a shooting foul) and apply
    # the and-1 bonus on a made foul. Blocks/charges don't occur on this path.
    if made or not d_foul:
        shooter.record_shot_result(made)
    if made and d_foul and foul_player:
        shooter.add_momentum(MO_AND_ONE_DELTA)

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
    rebound_attemptors: Optional[Dict[str, List[str]]] = None
    # Shot diagnostics: HCT fast-break drive is always a 2pt at-rim attempt.
    record_shot_split(game, is_three=is_three, defended=contested, made=made, turn_type="HCT")
    if made:
        shooter.record_stat("FGA")
        apply_scoring(game, off_team, shooter, 2, ["FGM"])
        text_outcome = "and scores, gets fouled!" if has_and_one else "and finishes!"
        possession_flips = not has_and_one
    else:
        shooter.record_stat("FGA")
        possession_flips = False
        if not d_foul:
            # D16 parity: a clean defensive stop (miss, no shooting foul) counts
            # as an HCT defensive success, matching the skeleton SHOT-miss path.
            def_team.scouting_data["defense"]["HCT"]["success"] += 1
            basket_x = float(rim["x"])
            bounce_spot = calculate_bounce_spot(game, basket_x=basket_x, basket_y=25)
            penalize_player_ids = {shooter_id} if shooter_id else set()
            exclude_player_ids: set = set()
            shot_moment_coords = _coords_by_player_id(off_lineup, seed_off)
            shot_moment_coords.update(_coords_by_player_id(def_lineup, seed_def))
            shot_moment_coords[shooter_id] = {
                "x": float(bh_target["x"]),
                "y": float(bh_target["y"]),
            }
            shot_moment_coords.update(
                {
                    did: {"x": float(c["x"]), "y": float(c["y"])}
                    for did, c in defender_end_coords.items()
                }
            )
            with _temporary_lineup_coords(game, shot_moment_coords):
                new_rebounder, new_team, new_stat = determine_rebounder(
                    game,
                    bounce_spot,
                    exclude_player_ids,
                    penalize_player_ids,
                    max_distance_from_bounce=20,
                    upper_half_distance=10,
                    offense_candidate_lineup=off_lineup,
                    defense_candidate_lineup=def_lineup,
                )
                rebounder_pid = _safe_id(new_rebounder)
                rebound_attemptors = collect_near_bounce_rebound_attemptors(
                    game,
                    bounce_spot,
                    rebounder_pid,
                    coords_already_display_oriented=True,
                )
            rebound_type = str(new_stat) if new_stat else "DREB"
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
            if rebound_attemptors is not None:
                turn_result["offense_rebounders"] = rebound_attemptors["offense_rebounders"]
                turn_result["defense_rebounders"] = rebound_attemptors["defense_rebounders"]
            if rebound_ball_spot is not None:
                turn_result["ballSpot"] = dict(rebound_ball_spot)

    if shot_variant_extras:
        turn_result.update(shot_variant_extras)

    from BackEnd.engine.shot_micro_movements import select_and_stamp_shot_micro
    select_and_stamp_shot_micro(
        turn_result,
        shot_type=shot_type,
        shooter_id=str(shooter_id),
        shooter_x=float(bh_target["x"]),
        shooter_y=float(bh_target["y"]),
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        has_contest=bool(contested),
        contest_result=contest_result if contested else None,
        contest_margin=contest_margin if contested else None,
        shot_defense_score_raw=float(shot_defense_score_raw if contested else 0),
    )

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


# --- §7 in-Attack-Basket shot (2D-2a shoot / 2D-2b drive) ------------------

# Shot-gather → release beat (game-seconds). The defenders collapse for this
# long, and the D6 contest is evaluated at their release-time positions.
AB_SHOT_BEAT_SECONDS = 0.8
# D6 shot-defender proximity: Euclidean grid spots (``CONTEST_EUCLIDEAN_RADIUS``).
# Distance-to-rim split for the shoot-in-place shot type.
AB_INSIDE_SHOT_MAX_DIST = 12.0
# §7 drive (2D-2b): minimum drive duration, dish probability, inside-spot pool
# the x>64 teammates fill (upper y>25 / lower y<25 halves; midLane is central).
AB_DRIVE_MIN_SECONDS = 0.35
AB_DISH_PROB = 0.5
AB_INSIDE_UPPER = ("upper lowPost", "upper midPost", "upper midBaseline")
AB_INSIDE_LOWER = ("lower lowPost", "lower midPost", "lower midBaseline")
AB_INSIDE_CENTRAL = ("midLane",)


def _mirror_x(coord: Dict[str, Any], is_away_offense: bool) -> Dict[str, float]:
    """HCO string spots are authored in home (attacking x=91) orientation; flip
    x around 50 for away offense. y is unaffected."""
    x = float(coord["x"])
    return {"x": (100.0 - x) if is_away_offense else x, "y": float(coord["y"])}


def _collapse_defenders_and_pick(
    def_lineup: Dict[str, Any],
    seed_def: Dict[str, Any],
    shot_spot: Dict[str, float],
    is_away_offense: bool,
    t: float,
):
    """§7 D5 rim-protection collapse + D6 shot-defender pick.

    Each defender moves (standard pace, interrupted to ``t`` game-seconds) toward
    the rim band; returns ``(defender_end_coords, shot_defender, shot_defender_id,
    contested)`` where the shot defender is the nearest defender ending within
    ``CONTEST_EUCLIDEAN_RADIUS`` grid spots of ``shot_spot`` (``None`` → uncontested).
    """
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec
    from BackEnd.utils.transition_bridge import _interrupted_coord
    from BackEnd.engine.dynamic_hct import (
        RIM_PROTECT_X_MIN,
        RIM_PROTECT_X_MAX,
        RIM_PROTECT_Y_MIN,
        RIM_PROTECT_Y_MAX,
    )

    if is_away_offense:
        band_x_lo, band_x_hi = 100 - RIM_PROTECT_X_MAX, 100 - RIM_PROTECT_X_MIN
    else:
        band_x_lo, band_x_hi = RIM_PROTECT_X_MIN, RIM_PROTECT_X_MAX

    end_coords: Dict[str, Dict[str, float]] = {}
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
            _interrupted_coord(start, target, rate, t) if rate > 0 else dict(target)
        )
        end_coords[did] = {"x": float(end["x"]), "y": float(end["y"])}

    shot_defender = None
    shot_defender_id: Optional[str] = None
    best = None
    for pos, player in def_lineup.items():
        did = _safe_id(player)
        if did is None or did not in end_coords:
            continue
        end = end_coords[did]
        d = _euclid(end, shot_spot)
        if d <= CONTEST_EUCLIDEAN_RADIUS and (best is None or d < best):
            best, shot_defender, shot_defender_id = d, player, did
    return end_coords, shot_defender, shot_defender_id, shot_defender is not None


def _roll_ab_shot(
    game: Any,
    off_team: Any,
    game_state: Dict[str, Any],
    shooter: Any,
    shot_defender: Any,
    contested: bool,
    shot_type: str,
    shot_spot: Dict[str, float],
):
    """Resolve the shot score (defended iff contested) and make/miss. No
    auto-make — half-court shots are rolled vs. the team shot threshold."""
    from BackEnd.models.shot_manager import ShotManager

    shot_manager = getattr(game, "shot_manager", None) or ShotManager(game)
    defense_playcall = (
        game_state.get("defense_playcall")
        or game_state.get("defense_call")
        or "man"
    )
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)
    shot_classification = classify_shot_value(
        shot_spot,
        is_away_offense=is_away_offense,
        classification_source="dynamic_hct_shot_spot",
    )
    is_three = bool(shot_classification["is_three_point_shot"])
    is_paint = not is_three and shot_type in ("inside", "attack")
    (
        shot_score,
        shot_score_pre_defense,
        shot_defense_score_for_sfx,
        d_foul,
        foul_player,
        shot_defense_score_raw,
    ) = shot_manager.calculate_shot_score(
        shooter, None, None, shot_defender if contested else None, shot_type,
        defense_playcall, is_three, is_paint, None, shot_spot,
        apply_defense=contested,
    )
    made = shot_score >= off_team.team_attributes["shot_threshold"]
    return made, shot_score, shot_score_pre_defense, shot_defense_score_for_sfx, d_foul, foul_player, is_three, shot_classification, shot_defense_score_raw


def _finalize_ab_shot(
    game: Any,
    *,
    shooter: Any,
    shooter_id: Optional[str],
    shot_defender: Any,
    shot_defender_id: Optional[str],
    contested: bool,
    shot_type: str,
    shot_spot: Dict[str, float],
    made: bool,
    shot_score: float,
    shot_score_pre_defense: float,
    shot_defense_score_for_sfx: float,
    d_foul: bool,
    foul_player: Any,
    defender_end_coords: Dict[str, Dict[str, float]],
    t_shot: float,
    is_three: bool = False,
    shot_classification: Optional[Dict[str, Any]] = None,
    shot_moment_coords: Optional[Dict[str, Dict[str, float]]] = None,
    extra_seed: Optional[Dict[str, Any]] = None,
    text_prefix: str = " they go to work in the paint",
    shot_defense_score_raw: float = 0.0,
) -> Dict[str, Any]:
    """Shared make/miss → turn_result tail for the §7 in-Attack-Basket shots
    (foul FTs, variant, scoring, rebound, pressure-type, next_play_type, plus
    the ``hct_ab_*`` emitter seed). ``extra_seed`` carries drive-specific keys."""
    from BackEnd.utils.shared import (
        apply_scoring,
        calculate_bounce_spot,
        collect_near_bounce_rebound_attemptors,
        determine_rebounder,
        get_name_safe,
    )
    from BackEnd.constants.shot_variants import (
        select_shot_variant,
        roll_shot_variant_extras,
    )

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)
    if shot_classification is None:
        shot_classification = classify_shot_value(
            shot_spot,
            is_away_offense=is_away_offense,
            classification_source="dynamic_hct_shot_spot",
        )
    is_three = bool(shot_classification.get("is_three_point_shot"))
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS

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
        game_state["free_throws"] = 1 if made else (3 if is_three else 2)
        game_state["free_throws_remaining"] = game_state["free_throws"]
        game_state["one_and_one"] = False
        fouled_out_info = check_and_handle_foul_out(foul_player, game_state, def_team, perform_removal=False)
        free_throws_remaining = game_state["free_throws"]
        has_and_one = made

    # Player Momentum (Player_Momentum_System.md): self-contained AB shot path
    # bypasses ShotManager.resolve_shot — record the FG attempt for the
    # consecutive-shot streak (skip a miss that drew a shooting foul) and apply
    # the and-1 bonus on a made foul. Blocks/charges don't occur on this path.
    if made or not d_foul:
        shooter.record_shot_result(made)
    if made and d_foul and foul_player:
        shooter.add_momentum(MO_AND_ONE_DELTA)

    shot_threshold_for_variant = off_team.team_attributes.get("shot_threshold", 100)
    try:
        shot_variant = select_shot_variant(
            shot_score=shot_score_pre_defense,
            shot_threshold=shot_threshold_for_variant,
            shot_type=shot_type,
            made=made,
        )
        shot_variant_extras = roll_shot_variant_extras(
            shot_variant, shooter_y=shot_spot["y"],
        )
    except Exception:
        shot_variant = None
        shot_variant_extras = {}

    rebound_type: Optional[str] = None
    rebounder_pid: Optional[str] = None
    rebound_ball_spot: Optional[Dict[str, float]] = None
    rebound_attemptors: Optional[Dict[str, List[str]]] = None
    # Shot diagnostics: HCT attack-basket shot (can be 2pt or 3pt).
    record_shot_split(game, is_three=is_three, defended=contested, made=made, turn_type="HCT")
    if made:
        shooter.record_stat("FGA")
        if is_three:
            shooter.record_stat("3PTA")
        apply_scoring(game, off_team, shooter, 3 if is_three else 2, ["FGM", "3PTM"] if is_three else ["FGM"])
        text_outcome = "and scores, gets fouled!" if has_and_one else "and scores!"
        possession_flips = not has_and_one
    else:
        shooter.record_stat("FGA")
        if is_three:
            shooter.record_stat("3PTA")
        possession_flips = False
        if not d_foul:
            # D16 parity: a clean defensive stop (miss, no shooting foul) counts
            # as an HCT defensive success, matching the skeleton SHOT-miss path.
            def_team.scouting_data["defense"]["HCT"]["success"] += 1
            bounce_spot = calculate_bounce_spot(
                game, basket_x=float(rim["x"]), basket_y=25,
            )
            penalize_player_ids = {shooter_id} if shooter_id else set()
            shot_moment_coords = dict(shot_moment_coords or {})
            shot_moment_coords[shooter_id] = {
                "x": float(shot_spot["x"]),
                "y": float(shot_spot["y"]),
            }
            shot_moment_coords.update(
                {
                    did: {"x": float(c["x"]), "y": float(c["y"])}
                    for did, c in (defender_end_coords or {}).items()
                }
            )
            with _temporary_lineup_coords(game, shot_moment_coords):
                new_rebounder, new_team, new_stat = determine_rebounder(
                    game,
                    bounce_spot,
                    set(),
                    penalize_player_ids,
                    max_distance_from_bounce=20,
                    upper_half_distance=10,
                    offense_candidate_lineup=game.offense_team.lineup or {},
                    defense_candidate_lineup=game.defense_team.lineup or {},
                )
                rebounder_pid = _safe_id(new_rebounder)
                rebound_attemptors = collect_near_bounce_rebound_attemptors(
                    game,
                    bounce_spot,
                    rebounder_pid,
                    coords_already_display_oriented=True,
                )
            rebound_type = str(new_stat) if new_stat else "DREB"
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

    text_suffix = f"{text_prefix} — {get_name_safe(shooter)} {text_outcome}"

    pressure_type: Optional[str] = None
    if made and not has_and_one:
        try:
            pressure_type = game.turn_manager.determine_defensive_pressure_type()
        except Exception as e:
            logging.warning("🚨 [HCT_AB] pressure-type failed: %s; HCO", e)
            pressure_type = "HCO"
        game_state["offensive_state"] = pressure_type

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
        "is_three_point_shot": bool(is_three),
        "shot_value": int(shot_classification.get("shot_value") or 2),
        "shot_spot": dict(shot_classification["classification_coord"]) if isinstance(shot_classification.get("classification_coord"), dict) else {"x": float(shot_spot["x"]), "y": float(shot_spot["y"])},
        "shot_classification_coord": dict(shot_classification["classification_coord"]) if isinstance(shot_classification.get("classification_coord"), dict) else {"x": float(shot_spot["x"]), "y": float(shot_spot["y"])},
        "shot_classification": dict(shot_classification),
        "shot_classification_source": shot_classification.get("classification_source"),
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
        "hct_ab_shooter_target": {"x": float(shot_spot["x"]), "y": float(shot_spot["y"])},
        "hct_ab_defender_end": {
            did: {"x": float(c["x"]), "y": float(c["y"])}
            for did, c in (defender_end_coords or {}).items()
        },
        "hct_ab_t_shot": float(t_shot),
        "hct_ab_contested": contested,
    }
    if extra_seed:
        turn_result.update(extra_seed)
    if made:
        turn_result["points"] = 3 if is_three else 2
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
            if rebound_attemptors is not None:
                turn_result["offense_rebounders"] = rebound_attemptors["offense_rebounders"]
                turn_result["defense_rebounders"] = rebound_attemptors["defense_rebounders"]
            if rebound_ball_spot is not None:
                turn_result["ballSpot"] = dict(rebound_ball_spot)

    if shot_variant_extras:
        turn_result.update(shot_variant_extras)

    from BackEnd.engine.shot_micro_movements import resolve_contest, select_and_stamp_shot_micro
    contest_result = None
    contest_margin = None
    if contested:
        contest_result, contest_margin = resolve_contest(
            shot_score_pre_defense, shot_defense_score_raw,
        )
    select_and_stamp_shot_micro(
        turn_result,
        shot_type=shot_type,
        shooter_id=str(shooter_id),
        shooter_x=float(shot_spot["x"]),
        shooter_y=float(shot_spot["y"]),
        off_lineup=off_team.lineup or {},
        def_lineup=def_team.lineup or {},
        has_contest=bool(contested),
        contest_result=contest_result,
        contest_margin=contest_margin,
        shot_defense_score_raw=float(shot_defense_score_raw),
    )

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


def resolve_hct_attack_basket_shot(game: Any, dyn: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the §7 in-Attack-Basket shot attempt (2D-2a — shoot in place).

    ``dyn["ab_seed"]`` carries the shooter position + the offense/defense coords
    at the moment the BH reached the Attack Basket Area. We apply the **D5**
    rim-protection collapse (defenders close toward the rim cluster), pick the
    **D6** shot defender (any defender ending within ``CONTEST_EUCLIDEAN_RADIUS`` of the shooter at the
    shot release), and resolve a contested-or-not jump shot via
    ``ShotManager.calculate_shot_score`` (no auto-make — half-court shots are
    rolled against the threshold). Returns a shot turn_result; the caller merges
    the HCT loop intermediate data for the emitter.
    """
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

    shot_spot = {"x": float(shooter_start["x"]), "y": float(shooter_start["y"])}  # shoot in place
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    basket = {"x": float(rim["x"]), "y": float(rim["y"])}

    defender_end_coords, shot_defender, shot_defender_id, contested = (
        _collapse_defenders_and_pick(
            def_lineup, seed_def, shot_spot, is_away_offense, AB_SHOT_BEAT_SECONDS,
        )
    )
    shot_type = (
        "inside" if _euclid(shot_spot, basket) <= AB_INSIDE_SHOT_MAX_DIST else "outside"
    )
    made, shot_score, pre, sfx_score, d_foul, foul_player, is_three, shot_classification, shot_defense_score_raw = _roll_ab_shot(
        game, off_team, game.game_state, shooter, shot_defender, contested,
        shot_type, shot_spot,
    )
    return _finalize_ab_shot(
        game,
        shooter=shooter, shooter_id=shooter_id,
        shot_defender=shot_defender, shot_defender_id=shot_defender_id,
        contested=contested, shot_type=shot_type, shot_spot=shot_spot,
        made=made, shot_score=shot_score, shot_score_pre_defense=pre,
        shot_defense_score_for_sfx=sfx_score, d_foul=d_foul, foul_player=foul_player,
        defender_end_coords=defender_end_coords, t_shot=AB_SHOT_BEAT_SECONDS,
        is_three=is_three, shot_classification=shot_classification,
        shot_moment_coords=_coords_by_player_id(off_lineup, seed_off),
        text_prefix=" they go to work in the paint",
        shot_defense_score_raw=shot_defense_score_raw,
    )


def resolve_hct_attack_basket_drive(game: Any, dyn: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the §7 / 2D-2b in-Attack-Basket **drive** (and drive→dish).

    The ball handler drives to a rim target (by his starting y); any teammate
    with x>64 relocates to a distinct inside spot. If the BH has an inside
    teammate it's a 50/50 between finishing himself (an **attack** shot at the
    rim) and **dishing** to the closest-to-basket inside teammate (who shoots an
    **inside** shot). D5 rim collapse + D6 shot defender as in the shoot path.
    """
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec
    from BackEnd.constants import HCO_STRING_SPOTS

    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup or {}
    def_lineup = def_team.lineup or {}
    is_away_offense = bool(off_team.team_id == game.away_team.team_id)

    seed = dyn.get("ab_seed") or {}
    driver_pos = seed.get("shooter_pos") or "PG"
    seed_off = seed.get("off_coords") or {}
    seed_def = seed.get("def_coords") or {}

    driver = off_lineup.get(driver_pos)
    driver_id = _safe_id(driver)
    driver_start = seed_off.get(driver_pos)
    if driver is None or driver_id is None or not isinstance(driver_start, dict):
        logging.warning("🚨 [HCT_AB] missing driver seed; bailing to HCO")
        return {"result_type": "HCO", "_hct_ab_bail": True}
    driver_start = {"x": float(driver_start["x"]), "y": float(driver_start["y"])}

    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    basket = {"x": float(rim["x"]), "y": float(rim["y"])}

    # Drive target by starting y (home orientation, mirrored for away).
    if driver_start["y"] > 30:
        drive_name = "upper lowPost"
    elif driver_start["y"] < 20:
        drive_name = "lower lowPost"
    else:
        drive_name = "basketSpot"
    driver_target = _mirror_x(HCO_STRING_SPOTS[drive_name], is_away_offense)

    # x>64 teammates relocate to distinct inside spots (their y picks the half).
    def _past_64(c: Dict[str, float]) -> bool:
        return (100 - c["x"]) > 64 if is_away_offense else c["x"] > 64

    taken = {drive_name}
    teammate_targets: Dict[str, Dict[str, float]] = {}
    inside_teammates: List = []  # (off_id, coord, player)
    for pos, player in off_lineup.items():
        if pos == driver_pos or player is None:
            continue
        start = seed_off.get(pos)
        if not isinstance(start, dict):
            continue
        start = {"x": float(start["x"]), "y": float(start["y"])}
        if not _past_64(start):
            continue
        half = AB_INSIDE_UPPER if start["y"] > 25 else AB_INSIDE_LOWER
        pool = [n for n in (tuple(half) + AB_INSIDE_CENTRAL) if n not in taken]
        if not pool:
            continue
        name = random.choice(pool)
        taken.add(name)
        coord = _mirror_x(HCO_STRING_SPOTS[name], is_away_offense)
        oid = _safe_id(player)
        teammate_targets[oid] = coord
        inside_teammates.append((oid, coord, player))

    drive_rate = _ag_grid_per_game_sec(driver, "sprint")
    t_drive = (
        max(AB_DRIVE_MIN_SECONDS, _euclid(driver_start, driver_target) / drive_rate)
        if drive_rate > 0
        else AB_DRIVE_MIN_SECONDS
    )

    dish = bool(inside_teammates) and (random.random() < AB_DISH_PROB)
    if dish:
        recv_id, recv_coord, receiver = min(
            inside_teammates, key=lambda it: _euclid(it[1], basket)
        )
        shooter, shooter_id, shot_spot = receiver, recv_id, recv_coord
        shot_type = "inside"
        collapse_t = t_drive + AB_SHOT_BEAT_SECONDS
        mode = "drive_dish"
    else:
        shooter, shooter_id, shot_spot = driver, driver_id, driver_target
        shot_type = "attack"
        collapse_t = t_drive
        mode = "drive"

    defender_end_coords, shot_defender, shot_defender_id, contested = (
        _collapse_defenders_and_pick(
            def_lineup, seed_def, shot_spot, is_away_offense, collapse_t,
        )
    )
    made, shot_score, pre, sfx_score, d_foul, foul_player, is_three, shot_classification, shot_defense_score_raw = _roll_ab_shot(
        game, off_team, game.game_state, shooter, shot_defender, contested,
        shot_type, shot_spot,
    )

    extra_seed: Dict[str, Any] = {
        "hct_ab_mode": mode,
        "hct_ab_driver_id": driver_id,
        "hct_ab_driver_target": {
            "x": float(driver_target["x"]), "y": float(driver_target["y"]),
        },
        "hct_ab_teammate_targets": {
            oid: {"x": float(c["x"]), "y": float(c["y"])}
            for oid, c in teammate_targets.items()
        },
        "hct_ab_t_drive": float(t_drive),
    }
    if dish:
        extra_seed["hct_ab_dish_receiver_id"] = shooter_id
        extra_seed["hct_ab_dish_receiver_target"] = {
            "x": float(shot_spot["x"]), "y": float(shot_spot["y"]),
        }

    shot_moment_coords = _coords_by_player_id(off_lineup, seed_off)
    if driver_id is not None:
        shot_moment_coords[driver_id] = {
            "x": float(driver_target["x"]),
            "y": float(driver_target["y"]),
        }
    shot_moment_coords.update(
        {
            oid: {"x": float(c["x"]), "y": float(c["y"])}
            for oid, c in teammate_targets.items()
            if oid is not None
        }
    )

    return _finalize_ab_shot(
        game,
        shooter=shooter, shooter_id=shooter_id,
        shot_defender=shot_defender, shot_defender_id=shot_defender_id,
        contested=contested, shot_type=shot_type, shot_spot=shot_spot,
        made=made, shot_score=shot_score, shot_score_pre_defense=pre,
        shot_defense_score_for_sfx=sfx_score, d_foul=d_foul, foul_player=foul_player,
        defender_end_coords=defender_end_coords, t_shot=AB_SHOT_BEAT_SECONDS,
        is_three=is_three, shot_classification=shot_classification,
        shot_moment_coords=shot_moment_coords,
        extra_seed=extra_seed, text_prefix=" they attack the rim",
        shot_defense_score_raw=shot_defense_score_raw,
    )
