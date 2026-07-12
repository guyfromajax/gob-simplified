import random
import logging
import copy
import time
import json
from typing import TYPE_CHECKING, Dict
from BackEnd.constants.momentum import (
    MO_STEAL_DELTA,
    MO_FT_ALL_MISS_DELTA,
    MO_FT_ALL_MAKE_DELTA,
    MO_FT_MIN_ATTEMPTS,
    MO_FT_SECOND_CHANCE_ROLL,
    MO_SET_PLAY_DELTA,
)
from fastapi import HTTPException
from BackEnd.utils.shared import (
    get_name_safe, 
    get_player_position,
    get_quarter_index_from_game
)
from BackEnd.models.shot_manager import ShotManager
from BackEnd.utils.situational_logic import slow_it_down_defense_setting
if TYPE_CHECKING:
    from BackEnd.models.turn_manager import TurnManager
if TYPE_CHECKING:
    from BackEnd.models.game_manager import GameManager
from BackEnd.models.animator import Animator

from BackEnd.utils.home_crowd import effective_ft_miss_to_make_second_chance
from BackEnd.utils.shared import (
    get_name_safe,
    get_time_elapsed,
    calc_skeleton_time_elapsed,
    calc_skeleton_step_timing_contract,
    calc_ag_segment_seconds,
    calc_isotropic_segment_seconds,
    calc_pass_segment_seconds,
    clamp_turn_time_elapsed,
    fast_break_probability_from_slider,
    calculate_rebound_score,
    calculate_outlet_pass_score,
    resolve_offensive_rebound,
    apply_scoring,
    unpack_game_context,
    calculate_bounce_spot,
    determine_rebounder,
    FREE_THROW_REBOUND_MAX_X_DELTA,
    apply_coords_from_animations_list,
    get_away_player_coords,
    resolve_game_player_reference,
)
from BackEnd.utils.position_snapshot_ledger import (
    attach_position_snapshots,
    build_fast_break_pre_shot_snapshot,
    build_free_throw_snapshot,
    build_hco_pre_resolve_shot_snapshot,
    build_phase_post_stopper_snapshot,
    build_skeleton_pre_resolve_shot_snapshot,
)
from BackEnd.playcall_skeletons.fcp_skeletons import FCP_1, FCP_SKELETONS_DICT
from BackEnd.playcall_skeletons.inside_skeletons import INSIDE_SCENES
from BackEnd.utils.defense_identity import (
    defense_scouting_row_key,
    defense_zone_shell_variant,
    offense_vs_key_from_defense_input,
)
from BackEnd.utils.defense_utils import (
    defender_player_from_random_slot_fallback,
    random_defender_fallback_position,
)

_CANONICAL_SET_PLAY_POSITIONS = ("PG", "SG", "SF", "PF", "C")
_SET_PLAY_EVENT_POSITION_FIELDS = ("by", "for", "from", "to")


def get_in_play_defenders(ball_handler, defense_lineup, target_is_away):
    """Return defenders ahead of the ball handler on the fast break.

    Args:
        ball_handler (Player): The player leading the break.
        defense_lineup (dict): Mapping of positions to defensive players.
        target_is_away (bool): True if the offense is attacking the away hoop.

    Returns:
        list[Player]: Defensive players considered in play.
    """

    bh_x = getattr(ball_handler, "coords", {}).get("x", 0)
    in_play = []
    for defender in defense_lineup.values():
        d_x = getattr(defender, "coords", {}).get("x", 0)
        if target_is_away:
            if d_x < bh_x:
                in_play.append(defender)
        else:
            if d_x > bh_x:
                in_play.append(defender)
    return in_play


def _build_set_play_alias_map(target_shooter):
    """Map staging set-play aliases back to canonical lineup positions."""
    if target_shooter not in _CANONICAL_SET_PLAY_POSITIONS:
        return {}

    remaining = [pos for pos in _CANONICAL_SET_PLAY_POSITIONS if pos != target_shooter]
    alias_map = {"target_shooter": target_shooter}
    for index, position in enumerate(remaining, start=1):
        alias_map[f"pos{index}"] = position
    return alias_map


def _remap_set_play_event_positions(event, alias_map):
    if not isinstance(event, dict) or not alias_map:
        return event

    updated = copy.deepcopy(event)
    for field in _SET_PLAY_EVENT_POSITION_FIELDS:
        value = updated.get(field)
        if value in alias_map:
            updated[field] = alias_map[value]
    return updated


def _remap_set_play_steps_to_canonical(steps, target_shooter):
    alias_map = _build_set_play_alias_map(target_shooter)
    if not alias_map:
        return steps

    updated_steps = []
    changed = False

    for step in steps or []:
        if not isinstance(step, dict):
            updated_steps.append(step)
            continue

        updated_step = copy.deepcopy(step)
        pos_actions = updated_step.get("pos_actions") or {}
        remapped_pos_actions = {}

        for position, action_info in pos_actions.items():
            mapped_position = alias_map.get(position, position)
            remapped_pos_actions[mapped_position] = action_info
            if mapped_position != position:
                changed = True

        updated_step["pos_actions"] = remapped_pos_actions

        events = updated_step.get("events")
        if isinstance(events, list):
            remapped_events = [_remap_set_play_event_positions(event, alias_map) for event in events]
            if remapped_events != events:
                changed = True
            updated_step["events"] = remapped_events

        updated_steps.append(updated_step)

    return updated_steps if changed else steps


def _apply_set_play_runtime_position_mapping(skeleton, target_shooter):
    """
    Convert DB alias positions back to canonical lineup positions for runtime use.
    """
    if not skeleton or "steps" not in skeleton:
        return skeleton

    remapped_steps = _remap_set_play_steps_to_canonical(skeleton.get("steps") or [], target_shooter)
    if remapped_steps == skeleton.get("steps"):
        return skeleton

    updated_skeleton = copy.deepcopy(skeleton)
    updated_skeleton["steps"] = remapped_steps
    return updated_skeleton


def _select_default_set_play_skeleton(play_doc):
    """Return a usable successful set-play skeleton from either steps or versions."""
    skeletons = play_doc.get("skeletons", {})
    successful = skeletons.get("successful")
    if not isinstance(successful, dict):
        return None

    versions = successful.get("versions")
    if isinstance(versions, list):
        non_empty_versions = [v for v in versions if isinstance(v, dict) and v.get("steps")]
        if non_empty_versions:
            selected_version = non_empty_versions[0]
            return {
                "steps": selected_version.get("steps", []),
                "version": selected_version.get("version", "v0"),
            }

    if successful.get("steps"):
        return successful

    return None


def apply_energy_decay(off_lineup, def_lineup, omit_zeros_for_defense=False):
    """
    Apply energy decay to all players in both lineups.
    
    This is extracted from determine_event_type() to ensure energy decay
    happens for all HCO turns, regardless of whether determine_event_type()
    is called (e.g., when stopper system bypasses it for SHOT results).
    
    Args:
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
        omit_zeros_for_defense: If True, defensive players will have zero values
                                omitted from their depletion lists (used for HCT/FCP turns).
                                Offensive players always use normal depletion (with zeros).
    """
    for player in off_lineup.values():
        if player and hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
            player.decay_energy(player.get_fatigue_decay_amount())
    for player in def_lineup.values():
        if player and hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
            # ✅ FCP/HCT DEFENSIVE PLAYERS: Omit zeros from depletion list for defensive players on pressure defense turns
            player.decay_energy(player.get_fatigue_decay_amount(omit_zeros=omit_zeros_for_defense))


def apply_bench_energy_recharge(game):
    """
    Recharge energy for players not in the active lineup.
    
    For each bench player (not in active lineup), per turn:
    - 20% chance: no recharge (0)
    - 70% chance: recharge +0.01 energy
    - 10% chance: recharge +0.02 energy
    
    Args:
        game: GameManager instance containing home and away teams
    """
    # Get all lineup player IDs from both teams
    lineup_player_ids = set()
    for team in [game.home_team, game.away_team]:
        for player in team.lineup.values():
            if player and hasattr(player, "player_id"):
                lineup_player_ids.add(player.player_id)
    
    # Recharge bench players (not in lineup)
    for team in [game.home_team, game.away_team]:
        for player in team.get_all_players():
            if player and hasattr(player, "player_id") and player.player_id not in lineup_player_ids:
                if hasattr(player, "recharge_energy"):
                    roll = random.random()
                    if roll < 0.2:
                        # 20% chance: no recharge
                        pass
                    elif roll < 0.9:
                        # 70% chance: recharge +0.01
                        player.recharge_energy(0.01)
                    else:
                        # 10% chance: recharge +0.02
                        player.recharge_energy(0.02)


def check_and_handle_foul_out(foul_player, game_state, foul_team, *, perform_removal=True):
    """
    Check if player fouled out (5+ fouls) and handle accordingly.
    Returns dict with foul_out info.

    Args:
        perform_removal: When True (default), immediately remove the fouled-out
            player from the lineup and sub in a replacement. Inline callers that
            run DURING turn resolution should pass ``perform_removal=False`` so the
            fouled-out player stays in the lineup while the turn's animation payload
            (coords / overlay maps / final_coords) is built — otherwise his sprite
            has no movement for that turn and renders as a dead, stationary sprite.
            The removal is then applied once, after the payload is built, by the
            universal end-of-turn funnel (``GameManager._check_lineups_for_foul_out``).
    """
    if not foul_player:
        return {"fouled_out": False, "foul_count": 0}
    
    foul_count = foul_player.get_stat("F", "game")
    locked_player_ids = {
        str(pid)
        for pid in ((game_state or {}).get("locked_exhausted_lineup_player_ids") or [])
    }
    emergency_player_ids = {
        str(pid)
        for pid in (
            (game_state or {}).get("emergency_fouled_out_lineup_player_ids") or []
        )
    }
    allow_emergency_reentry = bool(
        (game_state and game_state.get("allow_fouled_out_lineup_reentry"))
        or not getattr(foul_team, "is_user_team", False)
    )
    exempt_player_ids = (
        locked_player_ids
        | (emergency_player_ids if allow_emergency_reentry else set())
    )
    if str(getattr(foul_player, "player_id", "")) in exempt_player_ids:
        return {"fouled_out": False, "foul_count": foul_count}
    fouled_out = foul_count >= 5
    
    if fouled_out and perform_removal:
        # Remove from lineup if currently in lineup (eligibility is derived from F >= 5 elsewhere)
        for pos, player in list(foul_team.lineup.items()):
            if player and hasattr(player, "player_id") and player.player_id == foul_player.player_id:
                foul_team.lineup[pos] = None
                # Immediately replace the fouled-out player to ensure lineup is always complete
                from BackEnd.main import _ensure_complete_lineup
                _ensure_complete_lineup(
                    foul_team,
                    game_state,
                    allow_incomplete_user_foul_out_transition=True,
                )
                break
    
    return {
        "fouled_out": fouled_out,
        "foul_count": foul_count,
        "foul_player_id": foul_player.player_id if fouled_out else None,
        "foul_player_name": foul_player.get_name() if fouled_out else None,
        "foul_player_photo": getattr(foul_player, "photo", None) if fouled_out else None,
        "foul_player_team": foul_team.name if fouled_out else None
    }

def _find_most_recent_shot_turn(game, max_turns=10):
    """
    Find the most recent shot-like turn that may carry Covert Release
    ``offense_getback`` / ``defense_release`` stamps (HCO MISS/MAKE/BLOCK,
    FT final miss, putback miss, FB miss).

    Args:
        game: Game object with turns list
        max_turns: Maximum number of turns to check (default: 10)

    Returns:
        dict: Most recent matching turn, or None if not found
    """
    if not game.turns or len(game.turns) == 0:
        return None

    # FREE_THROW / PUTBACK_MISS are DREB→FB arming sources that stamp CR fields
    # the same way HCO MISS does (see dreb_fast_break_arming.py).
    _SHOT_LIKE = ("MISS", "MAKE", "BLOCK", "FREE_THROW", "PUTBACK_MISS")
    for turn in reversed(game.turns[-max_turns:]):
        if turn.get("result_type") in _SHOT_LIKE:
            return turn

    return None

def get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=None):
    """
    Determine the ball handler from skeleton steps.
    
    Args:
        skeleton: Skeleton dict with "steps" key
        off_lineup: Dictionary of offensive players by position
        step_index: Optional step index to check (defaults to last step if None)
    
    Returns:
        Player object who has the ball, or PG (or first player) as fallback
    """
    if not skeleton or not skeleton.get("steps"):
        # Fallback: use PG or first player
        return off_lineup.get("PG", list(off_lineup.values())[0])
    
    steps = skeleton.get("steps", [])
    if not steps:
        return off_lineup.get("PG", list(off_lineup.values())[0])
    
    # When ``step_index`` is explicit (including 0), inspect ONLY that step.
    # HCO entry orchestrator passes ``step_index=0`` for the playcall's step-0
    # BH — walking backwards would pick an earlier handle_ball and mis-route
    # Handoff/Kickout/Walk Up. When ``step_index`` is omitted, walk backwards
    # from the last step (shot / event resolution semantics).
    explicit_step = step_index is not None
    if step_index is None:
        step_index = len(steps) - 1

    step_index = max(0, min(step_index, len(steps) - 1))
    search_indices = [step_index] if explicit_step else range(step_index, -1, -1)

    for i in search_indices:
        step = steps[i]
        pos_actions = step.get("pos_actions", {})
        
        # Find who has ball at this step (normalize action so we don't miss due to casing)
        for pos, action_info in pos_actions.items():
            action = (action_info.get("action") or "").lower().strip()
            # Actions that indicate ball possession
            if action in ["handle_ball", "receive", "shoot"]:
                # Found ball handler position
                ball_handler_player = off_lineup.get(pos)
                if ball_handler_player:
                    return ball_handler_player
    
    # Fallback: use PG or first player (only when no step had a clear ball handler)
    return off_lineup.get("PG", list(off_lineup.values())[0])


def _get_fcp_hct_post_inbound_start_index(skeleton, game):
    """
    Determine where FCP/HCT should start after an inbound pass.

    Default behavior remains "skip step 0" (legacy behavior). When this turn
    directly follows BASELINE_INBOUND, dynamically skip all leading
    inbound-equivalent setup/pass steps so BIP remains the single inbound owner.
    """
    steps = (skeleton or {}).get("steps") or []
    if not steps:
        return 0

    default_start_index = 1 if len(steps) > 1 else 0

    prev_turn = game.turns[-1] if getattr(game, "turns", None) else {}
    prev_turn_type = (
        prev_turn.get("turn_type")
        or prev_turn.get("current_turn")
        or prev_turn.get("result_type")
        or ""
    )
    if str(prev_turn_type).upper() != "BASELINE_INBOUND":
        return default_start_index

    def _normalize_action(pos_actions, pos):
        action = (pos_actions.get(pos, {}) or {}).get("action")
        return str(action or "").strip().lower()

    def _is_inbound_equivalent_step(step):
        pos_actions = step.get("pos_actions") or {}
        sf_action_info = pos_actions.get("SF") or {}
        sf_location = (sf_action_info.get("location") or sf_action_info.get("spot") or "").strip().lower()
        if sf_location not in {"inbound_left", "inbound_right"}:
            return False

        sf_action = _normalize_action(pos_actions, "SF")
        pg_action = _normalize_action(pos_actions, "PG")

        # Canonical inbound release in many skeletons.
        if sf_action == "pass" and pg_action == "receive":
            return True

        # Pre-release inbound staging in some versions (step 0 hold, step 1 pass).
        if sf_action in {"handle_ball", "stationary", "get_open"}:
            return True

        return False

    start_index = 0
    while start_index < len(steps) and _is_inbound_equivalent_step(steps[start_index]):
        start_index += 1

    # Keep legacy safety floor and never trim all steps.
    start_index = max(start_index, default_start_index)
    return min(start_index, len(steps) - 1)


def get_stealer_position_from_skeleton_step(skeleton, step_index, ball_handler_pos, defender, off_team, def_team, game):
    """
    Extract the stealer's (defender's) position from a specific skeleton step.
    
    Args:
        skeleton: Skeleton dict with "steps" key
        step_index: Index of the step where steal occurs
        ball_handler_pos: Position of the ball handler (e.g., "PG", "SG")
        defender: Defender (stealer) player object
        off_team: Offensive team object
        def_team: Defensive team object
        game: GameManager instance
    
    Returns:
        dict: Stealer's coordinates {"x": int, "y": int} or None if cannot determine
    """
    if not skeleton or not skeleton.get("steps"):
        return None
    
    steps = skeleton.get("steps", [])
    if step_index < 0 or step_index >= len(steps):
        return None
    
    step = steps[step_index]
    pos_actions = step.get("pos_actions", {})
    
    # Get ball handler's position from this step
    ball_handler_action = pos_actions.get(ball_handler_pos, {})
    ball_handler_location = ball_handler_action.get("location") or ball_handler_action.get("spot") or "key"
    
    # Convert location string to coordinates
    from BackEnd.constants import HCO_STRING_SPOTS
    ball_handler_coords = HCO_STRING_SPOTS.get(ball_handler_location, {"x": 50, "y": 25})
    
    # Calculate defender's position based on ball handler's position
    from BackEnd.utils.shared_defense import get_defender_coords
    
    # Determine if away team is on offense
    is_away_offense = off_team.team_id == game.away_team.team_id
    
    # Get defense aggression level
    aggression_level = slow_it_down_defense_setting(
        game.game_state, def_team, "aggression",
        def_team.strategy_settings.get("aggression", "normal"),
    )
    aggression_map = {0: "passive", 1: "passive", 2: "normal", 3: "aggressive", 4: "aggressive"}
    aggression = aggression_map.get(aggression_level, "normal")
    
    # Calculate defender coordinates (stealer is the ball handler's defender)
    stealer_coords = get_defender_coords(
        ball_handler_coords,
        is_away_offense,
        aggression,
        ball_handler_location,
        None,
        is_ball_handler=True
    )
    
    return stealer_coords


def select_foul_player(foul_team_type, ball_handler, off_lineup, def_lineup):
    """
    Select which player committed the foul based on probabilistic logic.
    
    Args:
        foul_team_type: "OFFENSE" or "DEFENSE"
        ball_handler: The current ball handler
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
    
    Returns:
        Player object who committed the foul
    """
    if foul_team_type == "OFFENSE":
        # 60% chance it's the ball handler, 40% distributed among other 4 players (10% each)
        players = list(off_lineup.values())
        weights = []
        for player in players:
            if player == ball_handler:
                weights.append(0.6)
            else:
                weights.append(0.1)
        
        foul_player = random.choices(players, weights=weights)[0]
    
    else:  # DEFENSE
        # 60% chance it's the defender matched to ball handler's position
        # 40% distributed among other 4 defenders (10% each)
        ball_handler_pos = getattr(ball_handler, 'position', None)
        matched_defender = def_lineup.get(ball_handler_pos) if ball_handler_pos else None
        
        players = list(def_lineup.values())
        weights = []
        for player in players:
            if matched_defender and player == matched_defender:
                weights.append(0.6)
            else:
                weights.append(0.1)
        
        foul_player = random.choices(players, weights=weights)[0]
    
    return foul_player


def grid_coords_from_player(player, fallback=None):
    """Return ``{x, y}`` grid coords from a player's current ``coords`` attribute."""
    coords = getattr(player, "coords", None) or {}
    if isinstance(coords, dict) and coords.get("x") is not None and coords.get("y") is not None:
        try:
            return {"x": float(coords["x"]), "y": float(coords["y"])}
        except (TypeError, ValueError):
            pass
    if isinstance(fallback, dict) and fallback.get("x") is not None and fallback.get("y") is not None:
        try:
            return {"x": float(fallback["x"]), "y": float(fallback["y"])}
        except (TypeError, ValueError):
            pass
    return {"x": 50.0, "y": 25.0}


def defender_coords_by_pos_from_lineup(def_lineup):
    """Build position -> grid coords from each defender's live ``Player.coords``."""
    coords_by_pos = {}
    for pos, defender in (def_lineup or {}).items():
        if defender is None:
            continue
        coords_by_pos[pos] = grid_coords_from_player(defender)
    return coords_by_pos or None


def pick_force_foul_defender_spot(
    victim_coords,
    foul_player,
    def_lineup,
    defender_coords_by_pos=None,
    max_radius=None,
    rng=None,
):
    """
    Grid spot for a force-foul defender: a random spot within ``max_radius``
    Euclidean units of the victim (uniform in the disk, so the foul setup does
    not look mechanical). Defaults to ``QUICK_FOUL_APPROACH_RADIUS_GRID`` (4).

    ``foul_player``/``defender_coords_by_pos`` are accepted for signature
    back-compat; the spot no longer biases toward the fouler (the sprint/converge
    step at HCO-start carries him in from wherever he is).
    """
    import math
    import random as _random
    from BackEnd.constants import QUICK_FOUL_APPROACH_RADIUS_GRID

    r_rng = rng or _random
    radius = float(QUICK_FOUL_APPROACH_RADIUS_GRID if max_radius is None else max_radius)
    vx = float(victim_coords.get("x", 50))
    vy = float(victim_coords.get("y", 25))
    r = radius * math.sqrt(r_rng.random())
    theta = r_rng.random() * 2.0 * math.pi
    x = max(1.0, min(99.0, vx + r * math.cos(theta)))
    y = max(1.0, min(49.0, vy + r * math.sin(theta)))
    return {"x": round(x, 2), "y": round(y, 2)}


def select_defender_closest_to_victim(victim_coords, def_lineup, defender_coords_by_pos=None):
    """
    For intentional foul (situational Force Foul): select the defender closest to the victim
    by Euclidean distance in court coordinates.

    Args:
        victim_coords: dict with "x" and "y" (player coords, inbound oDestinations, etc.)
        def_lineup: dict position -> Player
        defender_coords_by_pos: optional dict position -> {"x", "y"}. If None, use position-based
            default spots (key) for all defenders as fallback.

    Returns:
        Player object that is closest to victim_coords, or None if def_lineup empty.
    """
    if not def_lineup or not victim_coords:
        return None
    vx = victim_coords.get("x", 50)
    vy = victim_coords.get("y", 25)
    from BackEnd.constants import HCO_STRING_SPOTS
    best_defender = None
    best_dist_sq = float("inf")
    for pos, defender in def_lineup.items():
        if defender is None:
            continue
        if defender_coords_by_pos and pos in defender_coords_by_pos:
            coords = defender_coords_by_pos[pos]
            dx = coords.get("x", 50)
            dy = coords.get("y", 25)
        else:
            coords = HCO_STRING_SPOTS.get(pos, {"x": 50, "y": 25})
            dx = coords.get("x", 50)
            dy = coords.get("y", 25)
        dist_sq = (dx - vx) ** 2 + (dy - vy) ** 2
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_defender = defender
    return best_defender

    
def resolve_non_shooting_foul(roles, game, time_elapsed_override=None):
    """
    time_elapsed_override: if provided (e.g. situational Force Foul), use instead of tempo-based time.
    """
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    foul_team = off_team if game_state["foul_team"] == "OFFENSE" else def_team
    
    ball_handler = roles["ball_handler"]
    defender = roles.get("defender", "")
    foul_player = roles["foul_player"]
    shooter = roles["shooter"]
    screener = roles.get("screener", "")
    passer = roles.get("passer", "")
    if time_elapsed_override is not None:
        time_elapsed = time_elapsed_override
    else:
        steps = roles.get("steps", [])
        event_step_index = roles.get("event_step")
        if steps:
            time_elapsed = calc_skeleton_time_elapsed(steps, event_step_index)
        else:
            time_elapsed = random.randint(1, 5)

    # Track the foul
    foul_player.record_stat("F")
    
    # Check if player fouled out and handle accordingly. Detect-only: the lineup
    # removal is deferred to the end-of-turn funnel so the fouled-out player stays
    # animated for this turn (see check_and_handle_foul_out docstring).
    foul_out_info = check_and_handle_foul_out(foul_player, game_state, foul_team, perform_removal=False)
    
    if foul_team == def_team:
        def_team.team_fouls += 1
        text = f"{get_name_safe(foul_player)} fouls {get_name_safe(ball_handler)}!"
    else:
        off_team.team_fouls += 1
        text = f"{get_name_safe(foul_player)} commits an offensive foul!"

    # Bonus free throw logic - ONLY for defensive fouls
    # Offensive fouls NEVER award free throws (always possession change)
    if foul_team == def_team:
        # Defensive foul - check for bonus free throws
        if def_team.team_fouls >= 10:
            # Double bonus (10+ fouls): 2 free throws, no 1 & 1
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2
            game_state["free_throws_remaining"] = 2
            game_state["one_and_one"] = False
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        elif def_team.team_fouls >= 5:
            # Bonus (5-9 fouls): 1 & 1 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2  # Maximum possible (if front end is made)
            game_state["free_throws_remaining"] = 1  # Start with 1 (front end)
            game_state["one_and_one"] = True
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        else:
            # Less than 5 fouls: possession change, side inbound
            game_state["offensive_state"] = "HCO"
            game_state["free_throws"] = 0
            game_state["free_throws_remaining"] = 0
    else:
        # Offensive foul - ALWAYS possession change, no free throws
        game_state["offensive_state"] = "HCO"
        game_state["free_throws"] = 0
        game_state["free_throws_remaining"] = 0

    bh_pos = get_player_position(off_team.lineup, ball_handler)
    
    # ✅ SS&S FIX: Set possession_flips based on foul_team (matches FCP/HCT logic)
    # Offensive fouls always flip possession, defensive fouls don't (handled by bonus logic)
    possession_flips = (foul_team == off_team)  # True for offensive fouls, False for defensive
    
    # ✅ FIX: Do NOT flip possession here for offensive fouls - let SIP setup handle it
    # This prevents double-flipping: resolve_non_shooting_foul() sets possession_flips=True,
    # then game_manager.py SIP setup flips based on that flag (same pattern as dead ball turnovers)
    # The flip happens in game_manager.py simulate_macro_turn() before setup_side_inbound()
    # This ensures consistent behavior: all possession flips for SIP transitions happen in one place

    # next_play_type so turn_manager._should_reset_shot_clock resets on D_FOUL → SIDE_INBOUND (Shot_Clock_System.md)
    next_play_type = "FREE_THROW" if game_state.get("offensive_state") == "FREE_THROW" else "SIDE_INBOUND"
    result = {
        "result_type": "FOUL",
        "ball_handler": ball_handler,
        "screener": screener,
        "passer": passer,
        "defender": defender,
        "text": text,
        "possession_flips": possession_flips,
        "time_elapsed": time_elapsed,
        "offense_team_id": game.offense_team.team_id,  # ✅ SS&S: Add offense_team_id to all results
        "current_turn": "HCO",  # ✅ SS&S: Standalone fouls occur in HCO context
        "foul_player_id": getattr(foul_player, "player_id", None) if foul_player else None,
        "foul_team": game_state.get("foul_team"),
        "foul_count": foul_out_info["foul_count"],
        "fouled_out": foul_out_info["fouled_out"],
        "next_play_type": next_play_type,
        "next_turn": next_play_type,
    }
    
    # Add foul out player info if applicable
    if foul_out_info["fouled_out"]:
        result["foul_out_player"] = {
            "player_id": foul_out_info["foul_player_id"],
            "name": foul_out_info["foul_player_name"],
            "photo": foul_out_info["foul_player_photo"],
            "team": foul_out_info["foul_player_team"]
        }
        
        # ✅ FOUL OUT: Store foul context for timeout creation
        # This allows setup_timeout_turn() to determine next_play_type correctly
        is_bonus = def_team.team_fouls >= 5 if foul_team == def_team else False
        next_play_type = "FREE_THROW" if game_state.get("offensive_state") == "FREE_THROW" else "SIDE_INBOUND"
        
        game_state["foul_out_context"] = {
            "foul_type": "OFFENSIVE" if foul_team == off_team else "DEFENSIVE",
            "is_shooting_foul": False,
            "is_bonus": is_bonus,
            "next_play_type": next_play_type,
            "shooter": ball_handler if game_state.get("offensive_state") == "FREE_THROW" else None
        }
        logging.info(f"✅ FOUL OUT: Stored foul context - type={game_state['foul_out_context']['foul_type']}, next={next_play_type}")
    
    return result


def apply_fb_meet_non_shooting_defensive_foul(
    game,
    *,
    ball_handler,
    foul_player,
    time_elapsed_override=None,
):
    """Bonus / SIP vs FT transition for meet-terminal non-shooting defensive FB fouls.

    Wraps ``resolve_non_shooting_foul`` so FB drive integrations share the same
    team-foul, bonus, and foul-out rules as HCO / legacy FB cutoff paths.
    """
    if foul_player is None:
        raise ValueError("foul_player required for meet defensive foul")
    game.game_state["foul_team"] = "DEFENSE"
    return resolve_non_shooting_foul(
        {
            "ball_handler": ball_handler,
            "defender": foul_player,
            "foul_player": foul_player,
            "shooter": ball_handler,
            "screener": None,
            "passer": None,
        },
        game,
        time_elapsed_override=time_elapsed_override,
    )


# #FAST BREAK
from BackEnd.constants.fast_break_constants import (
    BALL_HANDLER_MOVE_X_MIN,
    BALL_HANDLER_MOVE_X_MAX,
    BALL_HANDLER_MOVE_Y_RANGE,
    DEFENSIVE_STOP_Y_RANGE,
    DEFENSIVE_STOP_Y_RANGE_DREB_OUTLET,
    FB_CUTOFF_DEFENDER_TIME_SLACK_DREB,
    FB_CUTOFF_DEFENDER_TIME_SLACK_STEAL,
    FB_CUTOFF_PATH_CORRIDOR_DREB,
    FB_CUTOFF_PATH_CORRIDOR_STEAL,
    STEAL_ENTRY_MOVE_X_MIN,
    STEAL_ENTRY_MOVE_X_MAX,
    STEAL_ENTRY_MOVE_Y_RANGE,
    STEAL_ENTRY_Y_MIN,
    STEAL_ENTRY_Y_MAX,
    STEAL_HCO_SETUP_MOVE_X_MIN,
    STEAL_HCO_SETUP_MOVE_X_MAX,
    STEAL_HCO_SETUP_MOVE_Y_RANGE,
    STEAL_HCO_SETUP_Y_MIN,
    STEAL_HCO_SETUP_Y_MAX,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE,
    STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN,
    STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MAX,
)

def _record_fast_break_stats(fb_roles, turn_result, game):
    """
    Record Fast Break statistics for release player (offensive) and get-back players (defensive).
    
    Args:
        fb_roles: Fast Break roles dict with outlet_receiver, getback_player_ids
        turn_result: Final turn result dict with result_type
        game: GameManager instance
    """
    result_type = turn_result.get("result_type")
    if not result_type:
        return
    
    # Determine success/failure criteria (aligned with team-level Fast_Break_Success)
    # FB_S (offense): Shot Make, Defensive Foul (non-shooting)
    # Note: MISS does NOT count as success (matches team-level criteria)
    # Offensive FB_F / FB_N retired — only FB_A and FB_S tracked for offense
    # FB_S_D (defense): DEFENSIVE_STOP
    # FB_F_D (defense): Shot Make, Shot Miss, Defensive Foul (any shot attempt or defensive foul)
    
    is_fb_s_offense = result_type == "MAKE" or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    is_fb_s_defense = result_type == "DEFENSIVE_STOP"
    is_fb_f_defense = result_type in ["MAKE", "MISS", "BLOCK"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    
    # Track stats for offensive player - OFFENSIVE stats
    # ✅ SS&S FIX: For DREB-initiated Fast Breaks, use outlet_receiver
    # For STEAL-initiated Fast Breaks, use ball_handler (stealer)
    outlet_receiver_id = fb_roles.get("outlet_receiver")
    ball_handler = fb_roles.get("ball_handler")
    
    offensive_player = None
    if outlet_receiver_id:
        # DREB-initiated: Use outlet receiver
        for team in (game.home_team, game.away_team):
            for player in team.get_all_players():
                if getattr(player, "player_id", None) == outlet_receiver_id:
                    offensive_player = player
                    break
            if offensive_player:
                break
    elif ball_handler:
        # STEAL-initiated: Use ball handler (stealer)
        offensive_player = ball_handler
    
    if offensive_player:
        # Always increment FB_A (Fast Break Attempt)
        offensive_player.record_stat("FB_A", 1)
        if is_fb_s_offense:
            offensive_player.record_stat("FB_S", 1)
    
    # Track stats for get-back players - DEFENSIVE stats
    # ✅ SS&S FIX: For DREB-initiated Fast Breaks, use getback_player_ids
    # For STEAL-initiated Fast Breaks, use fb_roles["defense"] (defensive players)
    getback_player_ids = fb_roles.get("getback_player_ids", [])
    defensive_players = []
    
    if getback_player_ids:
        # DREB-initiated: Use get-back players
        for getback_id in getback_player_ids:
            getback_player = None
            for team in (game.home_team, game.away_team):
                for player in team.get_all_players():
                    if getattr(player, "player_id", None) == getback_id:
                        getback_player = player
                        break
                if getback_player:
                    break
            if getback_player:
                defensive_players.append(getback_player)
    else:
        # STEAL-initiated: Use defensive players from fb_roles["defense"]
        defensive_players = fb_roles.get("defense", [])
    
    # Record defensive stats for all defensive players
    for defensive_player in defensive_players:
        if defensive_player:
            # Always increment FB_A_D (Fast Break Attempt Defense)
            defensive_player.record_stat("FB_A_D", 1)
            
            # Increment FB_S_D or FB_F_D based on result
            if is_fb_s_defense:
                defensive_player.record_stat("FB_S_D", 1)
            elif is_fb_f_defense:
                defensive_player.record_stat("FB_F_D", 1)
            # FB_S_N removed (no instances)

def _record_outlet_pass_stats(outlet_passer_id, outlet_score, is_successful, game):
    """
    Record outlet pass statistics for the outlet passer.
    
    Args:
        outlet_passer_id: Player ID of the outlet passer
        outlet_score: Scaled outlet pass score (1-100)
        is_successful: True if outlet pass led to shot attempt, False if defensive stop
        game: GameManager instance
    """
    if not outlet_passer_id or outlet_score is None:
        return
    
    # Find outlet passer player object
    outlet_passer = None
    for team in (game.home_team, game.away_team):
        for player in team.get_all_players():
            if getattr(player, "player_id", None) == outlet_passer_id:
                outlet_passer = player
                break
        if outlet_passer:
            break
    
    if not outlet_passer:
        return
    
    # Record Outlet_A (always increment on outlet pass)
    outlet_passer.record_stat("Outlet_A", 1)
    
    # Record Outlet_S if successful (led to shot attempt)
    if is_successful:
        outlet_passer.record_stat("Outlet_S", 1)
    
    # Update Outlet_Score_List (append score to array)
    outlet_passer.stats["game"]["Outlet_Score_List"].append(outlet_score)
    
    # Calculate and update Outlet_Score (average of list)
    score_list = outlet_passer.stats["game"]["Outlet_Score_List"]
    if score_list:
        outlet_passer.stats["game"]["Outlet_Score"] = int(round(sum(score_list) / len(score_list)))
    
    # Update Outlet_Score_Cum (cumulative sum)
    outlet_passer.stats["game"]["Outlet_Score_Cum"] += outlet_score

def _record_fcp_stats(fcp_roles, turn_result, game, off_lineup, def_lineup):
    """
    Record FCP (Full Court Press) statistics for all players in active lineups.
    
    Args:
        fcp_roles: FCP roles dict with ball_handler, shooter, defender, etc.
        turn_result: Final turn result dict with result_type
        game: GameManager instance
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
    """
    result_type = turn_result.get("result_type")
    if not result_type:
        return
    
    # Determine success criteria
    # FCP_S (offense): MAKE, HCO (press break), Defensive Foul
    # FCP_S_D (defense): MISS, O_FOUL, DEAD_BALL_TURNOVER, STEAL
    
    is_fcp_s_offense = result_type in ["MAKE", "HCO"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    is_fcp_s_defense = result_type in ["MISS", "BLOCK", "TURNOVER", "STEAL", "DEAD BALL"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "OFFENSE"
    )
    
    # Track stats for ALL offensive players in active lineup
    for player in off_lineup.values():
        if player:
            player.record_stat("FCP_A", 1)
            if is_fcp_s_offense:
                player.record_stat("FCP_S", 1)
    
    # Track stats for ALL defensive players in active lineup
    for player in def_lineup.values():
        if player:
            player.record_stat("FCP_A_D", 1)
            if is_fcp_s_defense:
                player.record_stat("FCP_S_D", 1)

def _record_hct_stats(hct_roles, turn_result, game, off_lineup, def_lineup):
    """
    Record HCT (Half Court Trap) statistics for all players in active lineups.
    
    Args:
        hct_roles: HCT roles dict with ball_handler, shooter, defender, etc.
        turn_result: Final turn result dict with result_type
        game: GameManager instance
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
    """
    result_type = turn_result.get("result_type")
    if not result_type:
        return
    
    # Determine success criteria (same as FCP)
    # HCT_S (offense): MAKE, HCO (trap break), Defensive Foul
    # HCT_S_D (defense): MISS, O_FOUL, DEAD_BALL_TURNOVER, STEAL
    
    is_hct_s_offense = result_type in ["MAKE", "HCO"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    is_hct_s_defense = result_type in ["MISS", "BLOCK", "TURNOVER", "STEAL", "DEAD BALL"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "OFFENSE"
    )
    
    # Track stats for ALL offensive players in active lineup
    for player in off_lineup.values():
        if player:
            player.record_stat("HCT_A", 1)
            if is_hct_s_offense:
                player.record_stat("HCT_S", 1)
    
    # Track stats for ALL defensive players in active lineup
    for player in def_lineup.values():
        if player:
            player.record_stat("HCT_A_D", 1)
            if is_hct_s_defense:
                player.record_stat("HCT_S_D", 1)

    # Per-trap-play A/S (defense-side, mirrors FB's offense-side fast_break_plays).
    # _record_hct_stats is the single stats sink for an HCT turn, so counting here
    # is exactly once per possession. Defense success criteria == HCT_S_D above.
    play_key = game.game_state.get("hct_trap_play")
    if play_key:
        from BackEnd.constants.hct_trap_play_types import ensure_hct_trap_plays

        def_scouting = getattr(game.defense_team, "scouting_data", None)
        if isinstance(def_scouting, dict) and isinstance(def_scouting.get("defense"), dict):
            hct_plays = ensure_hct_trap_plays(def_scouting["defense"])
            if play_key in hct_plays:
                hct_plays[play_key]["A"] += 1
                if is_hct_s_defense:
                    hct_plays[play_key]["S"] += 1


def apply_fast_break_cg_time(turn_result, shot_attempted=False):
    """
    Cover-ground timing for fast breaks (shared by Covert Release and Rim Runner).
    """
    roles_data = turn_result.get("roles", {}) or {}
    animations_data = turn_result.get("animations", []) or []
    path_points = []

    bh = roles_data.get("ball_handler")
    bh_id = getattr(bh, "player_id", None) if bh else None
    if bh_id:
        for anim in animations_data:
            if anim.get("playerId") == bh_id:
                movement = anim.get("movement", []) or []
                for step in movement:
                    coords = step.get("coords") or {}
                    if "x" in coords and "y" in coords:
                        path_points.append({"x": coords["x"], "y": coords["y"]})
                break

    if len(path_points) < 2:
        start = {
            "x": roles_data.get("ball_handler_outlet_x"),
            "y": roles_data.get("ball_handler_outlet_y"),
        }
        end = turn_result.get("shot_spot")
        if not end and bh_id:
            for anim in animations_data:
                if anim.get("playerId") == bh_id and isinstance(anim.get("end"), dict):
                    end = anim.get("end")
                    break
        if isinstance(start.get("x"), (int, float)) and isinstance(start.get("y"), (int, float)) and end:
            path_points = [start, {"x": end.get("x", start["x"]), "y": end.get("y", start["y"])}]

    # AG-driven (Phase 4b): fast-break BH cover-ground scales with the BH's AG
    # attribute. At AG=50 the result equals the legacy COF=16 rate exactly, so
    # average-AG ball handlers produce identical timing to pre-migration. Falls
    # back to legacy when bh is missing.
    distance_seconds = 0.0
    if len(path_points) >= 2:
        for idx in range(1, len(path_points)):
            distance_seconds += calc_ag_segment_seconds(
                path_points[idx - 1], path_points[idx], bh, archetype="standard"
            )

    overhead_seconds = 0.0
    outlet_passer_x = roles_data.get("outlet_passer_x")
    outlet_passer_y = roles_data.get("outlet_passer_y")
    receiver_x = roles_data.get("ball_handler_outlet_x")
    receiver_y = roles_data.get("ball_handler_outlet_y")
    if (
        roles_data.get("outlet_passer")
        and roles_data.get("outlet_receiver")
        and isinstance(outlet_passer_x, (int, float))
        and isinstance(outlet_passer_y, (int, float))
        and isinstance(receiver_x, (int, float))
        and isinstance(receiver_y, (int, float))
    ):
        passer_coords = {"x": outlet_passer_x, "y": outlet_passer_y}
        receiver_coords = {"x": receiver_x, "y": receiver_y}
        overhead_seconds += calc_pass_segment_seconds(passer_coords, receiver_coords)
    elif roles_data.get("outlet_passer") and roles_data.get("outlet_receiver"):
        overhead_seconds += 2.0
    if shot_attempted:
        overhead_seconds += 1.0

    turn_result["time_elapsed"] = clamp_turn_time_elapsed(
        round(distance_seconds + overhead_seconds),
        cap=30,
    )
    return turn_result


def resolve_fast_break_logic(game: "GameManager"):
    from BackEnd.models.game_manager import GameManager
    # print("Entering resolve_fast_break()")
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    # ✅ Apply energy decay for active players during Fast Break
    apply_energy_decay(off_lineup, def_lineup)
    
    # ✅ NOTE: Bench recharge does NOT happen during Fast Break turns (only during HCO turns)
    
    # DREB outlet → covert_release (incl. fallback outlet); steal entry → after_steal
    rebound = game_state.get("last_rebound") == "DREB"
    from BackEnd.constants.fast_break_play_types import (
        AFTER_STEAL,
        COVERT_RELEASE,
        RIM_RUNNER,
        TRIANGLE,
        ensure_fast_break_plays,
        play_key_for_fast_break_entry,
    )

    if rebound:
        fb_play_key = game_state.pop("pending_dreb_fb_play_key", None)
        if fb_play_key is None:
            fb_play_key = play_key_for_fast_break_entry(
                True,
                getattr(off_team, "playbook_settings", None),
            )
    else:
        fb_play_key = play_key_for_fast_break_entry(rebound)

    off_scouting = off_team.scouting_data
    def_scouting = def_team.scouting_data
    fb_plays = ensure_fast_break_plays(off_scouting["offense"])
    fb_plays[fb_play_key]["A"] += 1
    off_scouting["offense"]["Fast_Break_Entries"] += 1
    def_scouting["defense"]["vs_Fast_Break"]["used"] += 1

    fb_roles = {
        "offense": [],
        "defense": [],
        "ball_handler": None,
        "outlet_passer": None,
        "outlet_receiver": None,
        "fast_break_play": fb_play_key,
    }
    # Wider y-band for DREB/outlet breaks (Covert Release); steals keep ±6
    defensive_stop_y_range = (
        DEFENSIVE_STOP_Y_RANGE_DREB_OUTLET if rebound else DEFENSIVE_STOP_Y_RANGE
    )

    # AFTER_STEAL FB short-circuit: the new resolver builds the complete
    # turn_result (geometry, contested decision, shot resolution, end coords
    # for all 10 players). The legacy steal-entry + stopper / hold_up logic
    # downstream is BYPASSED for this path (left intact for DREB FBs).
    # Schema emission is also handled here so the FE renders from the
    # turn_result["animation_steps"] payload. See
    # BackEnd/engine/after_steal_fast_break.py for the spec.
    if not rebound and fb_play_key == AFTER_STEAL:
        from BackEnd.engine.after_steal_fast_break import (
            resolve_after_steal_fast_break,
        )

        turn_result = resolve_after_steal_fast_break(game)

        # Schema emission for after_steal — same emitter as before, but the
        # refactored version reads from turn_result["after_steal_end_coords"]
        # and builds a single drive step + skeleton post-shot sub-steps.
        try:
            from BackEnd.engine.after_steal_fast_break_step_emitter import (
                build_after_steal_fast_break_animation_steps,
            )

            anim_steps = build_after_steal_fast_break_animation_steps(
                turn_result, game,
            )
            if anim_steps is not None:
                turn_result["animation_steps"] = anim_steps
        except Exception as e:  # pragma: no cover
            logging.warning(
                "build_after_steal_fast_break_animation_steps failed: %s", e
            )

        # Track per-play "attempted" aggregate (parity with line 1025).
        # Already incremented above for all FB paths; "S" increment is in
        # the new resolver.
        return turn_result

    if rebound and fb_play_key in (RIM_RUNNER, TRIANGLE):
        from BackEnd.engine.rim_runner_fast_break import resolve_rim_runner_fast_break

        rr_result = resolve_rim_runner_fast_break(game, fb_play_key)

        # Parallel-build: unified AnimationStep[] for Rim Runner and Triangle.
        # Emitters re-canonicalize post-shot overlays and stamp
        # ``hco_setup.inbound_pass`` on hold-up / outlet-denied when BH != PG.
        if fb_play_key == "rim_runner":
            try:
                from BackEnd.engine.rim_runner_step_emitter import (
                    build_rim_runner_animation_steps,
                )

                anim_steps = build_rim_runner_animation_steps(rr_result, game)
                if anim_steps is not None:
                    rr_result["animation_steps"] = anim_steps
                else:
                    # The emitter logs its own 🚨 [RR EMITTER NULL] guard line.
                    logging.warning(
                        "🚨 [RR EMITTER NULL CONSEQUENCE] result_type=%s "
                        "next_play_type=%s — animation_steps not set, FE → LEGACY",
                        rr_result.get("result_type"),
                        rr_result.get("next_play_type"),
                    )
            except Exception as e:
                logging.exception(
                    "🚨 [RR EMITTER EXCEPTION] result_type=%s: %s "
                    "— animation_steps not set, FE → LEGACY",
                    rr_result.get("result_type"), e,
                )
        elif fb_play_key == TRIANGLE:
            try:
                from BackEnd.engine.triangle_step_emitter import (
                    build_triangle_animation_steps,
                )

                anim_steps = build_triangle_animation_steps(rr_result, game)
                if anim_steps is not None:
                    rr_result["animation_steps"] = anim_steps
                else:
                    # The emitter logs its own 🚨 [TRIANGLE EMITTER NULL] guard line.
                    logging.warning(
                        "🚨 [TRIANGLE EMITTER NULL CONSEQUENCE] result_type=%s "
                        "next_play_type=%s — animation_steps not set, FE → LEGACY",
                        rr_result.get("result_type"),
                        rr_result.get("next_play_type"),
                    )
            except Exception as e:
                logging.exception(
                    "🚨 [TRIANGLE EMITTER EXCEPTION] result_type=%s: %s "
                    "— animation_steps not set, FE → LEGACY",
                    rr_result.get("result_type"), e,
                )

        return rr_result

    if rebound and fb_play_key == COVERT_RELEASE:
        from BackEnd.constants import USE_FB_DRIVE_RESOLUTION_CR

        if USE_FB_DRIVE_RESOLUTION_CR:
            from BackEnd.engine.covert_release_drive_integration import (
                resolve_covert_release_fast_break,
            )

            turn_result = resolve_covert_release_fast_break(game)
            try:
                from BackEnd.engine.covert_release_step_emitter import (
                    build_covert_release_animation_steps,
                )

                anim_steps = build_covert_release_animation_steps(turn_result, game)
                if anim_steps is not None:
                    turn_result["animation_steps"] = anim_steps
            except Exception as e:
                logging.warning(
                    "build_covert_release_animation_steps failed: %s", e
                )
            return turn_result

    if rebound:
        #resetting last_rebound to avoid carry over bugs
        game_state["last_rebound"] = "" 
        
        # Choose outlet passer (rebounder)
        rebounder = game_state.get("last_rebounder", None)
        
        # ✅ Covert Release only: release player = outlet receiver from shot turn; else random PG/SG/SF
        release_player = game_state.get("last_release_player", None)
        
        if release_player:
            # Use release player as ball handler and outlet receiver
            ball_handler = release_player
            fb_roles["ball_handler"] = ball_handler
            fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)  # ✅ Store ID for frontend
            
            # Clear release player after use to avoid carry-over bugs
            game_state["last_release_player"] = None
            
            # Ensure outlet passer and receiver are set to IDs and only if different
            if rebounder and rebounder != ball_handler:
                fb_roles["outlet_passer"] = getattr(rebounder, "player_id", None)
                fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
                rebounder_coords = getattr(rebounder, "coords", None) or {}
                if isinstance(rebounder_coords, dict):
                    fb_roles["outlet_passer_x"] = rebounder_coords.get("x")
                    fb_roles["outlet_passer_y"] = rebounder_coords.get("y")
                else:
                    fb_roles["outlet_passer_x"] = fb_roles["outlet_passer_y"] = None
                # Calculate outlet pass score for stat tracking
                outlet_score = calculate_outlet_pass_score(rebounder)
                fb_roles["outlet_score"] = outlet_score
                
                # ✅ COMMENTED OUT: Fast break outlet pass logs (cluttering transition debugging)
                # logging.warning(f"🏀 Fast Break outlet pass: outlet_passer={get_name_safe(rebounder)} (rebounder), outlet_receiver={get_name_safe(ball_handler)} (release player)")
            else:
                fb_roles["outlet_passer"] = None
                fb_roles["outlet_receiver"] = None
                fb_roles["outlet_passer_x"] = fb_roles["outlet_passer_y"] = None
                fb_roles["outlet_score"] = None
        else:
            # Fallback: Random ball handler if no release player (shouldn't happen, but safety check)
            bh_pos = random.choices(["PG", "SG", "SF"], weights=[75, 15, 10])[0]
            ball_handler = off_lineup[bh_pos]

            fb_roles["ball_handler"] = ball_handler
            fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)  # ✅ Store ID for frontend

            # Ensure outlet passer and receiver are set to IDs and only if different
            if rebounder and rebounder != ball_handler:
                fb_roles["outlet_passer"] = getattr(rebounder, "player_id", None)
                fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
                rebounder_coords = getattr(rebounder, "coords", None) or {}
                if isinstance(rebounder_coords, dict):
                    fb_roles["outlet_passer_x"] = rebounder_coords.get("x")
                    fb_roles["outlet_passer_y"] = rebounder_coords.get("y")
                else:
                    fb_roles["outlet_passer_x"] = fb_roles["outlet_passer_y"] = None
                # Calculate outlet pass score for stat tracking
                outlet_score = calculate_outlet_pass_score(rebounder)
                fb_roles["outlet_score"] = outlet_score
                
                # ✅ COMMENTED OUT: Fast break outlet pass logs (cluttering transition debugging)
                # logging.warning(f"⚠️ Fast Break outlet pass (FALLBACK - no release player): outlet_passer={get_name_safe(rebounder)} (rebounder), outlet_receiver={get_name_safe(ball_handler)} (random)")
            else:
                fb_roles["outlet_passer"] = None
                fb_roles["outlet_receiver"] = None
                fb_roles["outlet_passer_x"] = fb_roles["outlet_passer_y"] = None
                fb_roles["outlet_score"] = None

        # No additional offensive players when starting from a rebound
        fb_roles["offense"] = []


    else:  # STEAL
        ball_handler = game_state.get("last_stealer")
        
        if ball_handler is None:
            ball_handler = off_lineup["PG"]
        
        fb_roles["ball_handler"] = ball_handler
        fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)  # ✅ Store ID for frontend
        fb_roles["outlet_passer"] = None
        fb_roles["outlet_receiver"] = None
        fb_roles["outlet_score"] = None  # No outlet pass on steals

        # Previous logic added additional offensive players to the fast break,
        # potentially scheduling runners beyond the ball handler. The current
        # approach freezes all non-ball-handlers so no extra offense is added
        # to the break.
        # for pos in ["PG", "SG", "SF"]:
        #     if off_lineup[pos] != ball_handler:
        #         if random.random() < {"PG": 0.5, "SG": 0.4, "SF": 0.05}.get(pos, 0):
        #             fb_roles["offense"].append(off_lineup[pos])

    target_is_away = off_team.team_id == game.away_team.team_id
    fb_roles["defense"] = get_in_play_defenders(ball_handler, def_lineup, target_is_away)
    
    # If no defenders are ahead, add defensive PG as chaser
    # This ensures we always have at least one defender for animation purposes
    if not fb_roles["defense"]:
        defensive_pg = def_lineup.get("PG")
        if defensive_pg:
            fb_roles["defense"] = [defensive_pg]
            print(f"⚡ Fast Break: No defenders ahead, adding defensive PG {get_name_safe(defensive_pg)} as chaser")

    # Defensive pressure check is computed downstream in the
    # defender-ahead branch (geography gate + aggression gate + skill
    # check). Any earlier roll here would use stale (pre-outlet) coords
    # and is unused. See Step_By_Step_System.md "Fast Break — Backend
    # Resolution Stages" for the canonical skill-check formula.
    hold_up = False
    stopper_id = None

    # ✅ NEW LOGIC: Determine event type based on defender positions relative to ball handler
    # Note: This will override hold_up/stopper_id if a defender is ahead after outlet pass
    # after outlet pass simulation (matching frontend outlet pass animation)
    
    # ✅ SS&S: Determine if away team is on offense using offense_team_id
    # Using team_id is more explicit and traceable than a derived boolean
    is_away_offense = off_team.team_id == game.away_team.team_id
    
    # ✅ DEBUG: Log offense team determination
    # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Offense team determination:")
    # logging.debug(f"  off_team.team_id: {off_team.team_id}")
    # logging.debug(f"  game.away_team.team_id: {game.away_team.team_id}")
    # logging.debug(f"  game.home_team.team_id: {game.home_team.team_id}")
    # logging.debug(f"  is_away_offense: {is_away_offense}")
    
    # Determine direction toward basket
    # Home offense: basket at x=91, so direction = +1 (right)
    # Away offense: basket at x=9, so direction = -1 (left)
    if is_away_offense:
        # Away offense: smaller x is closer to basket
        direction = -1
        basket_x = 9
    else:
        # Home offense: larger x is closer to basket
        direction = 1
        basket_x = 91
    
    # ============================================================================
    # STEAL ENTRY vs OUTLET PASS: Different logic for steals vs rebounds
    # ============================================================================
    if rebound:
        # ==================== DREB → FAST BREAK: OUTLET PASS LOGIC ====================
        # Simulate ball handler position after outlet pass
        # Frontend logic: ball handler moves 5-10 spots toward basket, ±6 Y
        # ✅ SS&S: PRIORITIZE release/get-back coordinates for ball handler
        # The outlet receiver is typically a release player (defensive team), so check release coords first
        # Then check get-back coordinates (for offensive players who might be ball handler)
        ball_handler_start_x = None
        ball_handler_start_y = None
        
        ball_handler_id = getattr(ball_handler, "player_id", None)
        # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Looking for coordinates for ball_handler_id: {ball_handler_id}")
        
        # ✅ SS&S: Use helper function to find most recent shot turn
        most_recent_shot_turn = _find_most_recent_shot_turn(game, max_turns=10)
        if most_recent_shot_turn:
            # FIRST: Check if ball handler is a release player (outlet receiver is typically a release player)
            release_coords = most_recent_shot_turn.get("defense_release_coords", {})
            if release_coords and ball_handler_id and ball_handler_id in release_coords:
                stored_coords = release_coords[ball_handler_id]
                ball_handler_start_x = stored_coords.get("x")
                ball_handler_start_y = stored_coords.get("y")
                # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] ✅ Using release coords for ball handler: {ball_handler_start_x}, {ball_handler_start_y}")
            else:
                # SECOND: Check if ball handler is a get-back player
                getback_coords = most_recent_shot_turn.get("offense_getback_coords", {})
                if getback_coords and ball_handler_id and ball_handler_id in getback_coords:
                    stored_coords = getback_coords[ball_handler_id]
                    ball_handler_start_x = stored_coords.get("x")
                    ball_handler_start_y = stored_coords.get("y")
                    # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] ✅ Using get-back coords for ball handler: {ball_handler_start_x}, {ball_handler_start_y}")
        
        # FALLBACK: Use player.coords if not a release/get-back player or coords not found
        if ball_handler_start_x is None or ball_handler_start_y is None:
            ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
            ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)
            # logging.warning(f"🏀 [FAST BREAK PHASE DEBUG] ⚠️ Using player.coords (fallback): {ball_handler_start_x}, {ball_handler_start_y}")
            # logging.warning(f"🏀 [FAST BREAK PHASE DEBUG] ⚠️ This suggests ball handler is NOT a release/get-back player or coords not found in previous turn")
        
        # Simulate ball handler position after outlet pass (NO MOVEMENT - receives pass at starting position)
        # Ball handler will only move during defensive stop/shot attempt step
        ball_handler_move_x = 0
        ball_handler_move_y = 0
        ball_handler_outlet_x = ball_handler_start_x  # No movement during outlet pass
        ball_handler_outlet_y = ball_handler_start_y  # No movement during outlet pass
        
        # ✅ DEBUG: Log outlet position calculation
        # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Outlet position calculation:")
        # logging.debug(f"  ball_handler_start_x: {ball_handler_start_x}")
        # logging.debug(f"  ball_handler_start_y: {ball_handler_start_y}")
        # logging.debug(f"  direction: {direction}")
        # logging.debug(f"  ball_handler_move_x: {ball_handler_move_x}")
        # logging.debug(f"  ball_handler_move_y: {ball_handler_move_y}")
        # logging.debug(f"  ball_handler_outlet_x: {ball_handler_outlet_x}")
        # logging.debug(f"  ball_handler_outlet_y: {ball_handler_outlet_y}")
        # logging.debug(f"  calculation: {ball_handler_start_x} + {direction} * {ball_handler_move_x} = {ball_handler_outlet_x}")
        # logging.debug(f"📍 [OUTLET RECEIVER] Receives pass at: x={ball_handler_outlet_x}, y={ball_handler_outlet_y} (HOME orientation)")
    else:
        # ==================== STEAL → FAST BREAK: STEAL ENTRY LOGIC ====================
        # Stealer (ball handler) moves 5-10 x spots toward basket, ±4 y spots (clamped to 3-47)
        # This movement happens BEFORE checking for defensive stop vs shot
        # ✅ FIX: Use stored stealer position from skeleton step (if available)
        if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
            stealer_coords = game_state["last_stealer_coords"]
            ball_handler_start_x = stealer_coords.get("x", 50)
            ball_handler_start_y = stealer_coords.get("y", 25)
        else:
            ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
            ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)
        
        # Calculate steal entry movement
        steal_entry_move_x = random.randint(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX)
        steal_entry_move_y = random.randint(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE)
        
        # Apply movement toward basket
        ball_handler_after_entry_x = ball_handler_start_x + (direction * steal_entry_move_x)
        ball_handler_after_entry_y = max(STEAL_ENTRY_Y_MIN, min(STEAL_ENTRY_Y_MAX, ball_handler_start_y + steal_entry_move_y))
        
        # Store steal entry movement for animation
        ball_handler_move_x = steal_entry_move_x
        ball_handler_move_y = steal_entry_move_y
        ball_handler_outlet_x = ball_handler_after_entry_x  # Position after steal entry movement
        ball_handler_outlet_y = ball_handler_after_entry_y  # Position after steal entry movement
    
    # Store ball handler position for animation (after outlet pass for DREB, after steal entry for steals)
    fb_roles["ball_handler_outlet_x"] = ball_handler_outlet_x
    fb_roles["ball_handler_outlet_y"] = ball_handler_outlet_y
    fb_roles["ball_handler_move_x"] = ball_handler_move_x
    fb_roles["ball_handler_move_y"] = ball_handler_move_y
    fb_roles["is_away_offense"] = is_away_offense  # ✅ Store for animator to use
    fb_roles["is_steal_entry"] = not rebound  # ✅ Flag to indicate steal entry vs outlet pass
    
    # ✅ SS&S: Clear steal-related data after using it (so it doesn't persist to subsequent turns)
    if not rebound:
        game_state.pop("last_stealer_coords", None)
        game_state["last_stealer"] = None
    
    # ✅ FIX: Use actual defender coordinates instead of simulating random positions
    # Defenders are already positioned on the court after the shot attempt
    # They don't move during the outlet pass - only the ball handler moves
    # So we compare ball handler's outlet position to defender's actual current position
    # Drive-cutoff geometry (shared with HCT via ``cutoff_resolution``).
    # Each defender's outlet position is stored; earliest path intercept wins.
    # Aggression gate (strategy_calls) rolls per-defender stop-attempt probability.
    def_coords_cutoff: Dict[str, Dict[str, int]] = {}
    closest_defender_overall = None  # Closest defender overall (for shot attempts, uses Euclidean distance)
    closest_distance_overall = float('inf')
    # Per-CR spec (see _documentation_master/00_General_Systems/Step_By_Step_System.md
    # "CR Defensive Stop sub-step logic"). The defense team's strategy_calls
    # was already rolled by `set_strategy_calls()` at the start of the turn.
    # Each defender that can geometrically cut off the drive also rolls against
    # this probability; failures are skipped for that drive (not stop candidates).
    _agg_call = (
        getattr(def_team, "strategy_calls", {}) or {}
    ).get("aggression_call", "normal")
    _stop_attempt_prob = {
        "passive": 0.0,
        "normal": 0.5,
        "aggressive": 1.0,
    }.get(_agg_call, 0.5)
    
    # ✅ Find the most recent MISS/MAKE turn
    # Only use get-back coords from THIS turn, not from previous turns
    # ✅ SS&S: Use helper function to find most recent shot turn
    most_recent_shot_turn = _find_most_recent_shot_turn(game, max_turns=10)
    getback_player_ids = []
    if most_recent_shot_turn:
        getback_player_ids = most_recent_shot_turn.get("offense_getback", [])
    
    # ✅ Store get-back player IDs in fb_roles for animator to use
    fb_roles["getback_player_ids"] = getback_player_ids
    
    # ✅ Log all get-back players and their coordinates from the most recent shot attempt
    # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Most recent shot turn:")
    # if most_recent_shot_turn:
    #     turn_result_type = most_recent_shot_turn.get("result_type")
    #     getback_coords = most_recent_shot_turn.get("offense_getback_coords", {})
    #     getback_player_ids = most_recent_shot_turn.get("offense_getback", [])
    #     
    #     logging.debug(f"  Found {turn_result_type} turn:")
    #     logging.debug(f"  offense_getback (player IDs): {getback_player_ids}")
    #     logging.debug(f"  offense_getback_coords keys: {list(getback_coords.keys()) if getback_coords else 'None'}")
    #     
    #     if getback_coords:
    #         logging.debug(f"  Get-back players with coordinates:")
    #         for player_id, coords in getback_coords.items():
    #             logging.debug(f"    Get-back player {player_id}: x={coords.get('x')}, y={coords.get('y')}")
    #     elif getback_player_ids:
    #         logging.warning(f"  ⚠️ WARNING: Get-back player IDs exist but no coordinates stored!")
    #         logging.warning(f"    Player IDs: {getback_player_ids}")
    #     else:
    #         logging.debug(f"  No get-back players in this turn")
    # else:
    #     logging.warning(f"  ⚠️ No MISS or MAKE turn found in last 10 turns")
    
    # ✅ FIX: Check ALL defenders in def_lineup, not just those in fb_roles["defense"]
    # The get_in_play_defenders() function uses stale ball_handler.coords, which might exclude
    # get-back players who are actually ahead of the outlet receiver position
    # We need to check all defenders against the outlet receiver position (ball_handler_outlet_x)
    # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Checking {len(def_lineup)} defenders for defensive stop")
    # logging.debug(f"  Ball handler outlet position: x={ball_handler_outlet_x}, y={ball_handler_outlet_y}")
    
    for pos, defender in def_lineup.items():
        # Use defender's actual coordinates (where they are on the court)
        # These defenders are the team that was on offense during the shot attempt
        # They might have get-back coordinates stored, so check those first
        defender_actual_x = None
        defender_actual_y = None
        defender_id = getattr(defender, "player_id", None)
        
        # ✅ Check if defender has get-back coordinates from the MOST RECENT shot attempt only
        # Only use get-back coords if this defender was actually a get-back player in the turn that triggered this fast break
        if most_recent_shot_turn and defender_id:
            # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Looking for get-back coords for defender {defender_id}")
            getback_coords = most_recent_shot_turn.get("offense_getback_coords", {})
            # logging.debug(f"  Most recent {most_recent_shot_turn.get('result_type')} turn, getback_coords keys: {list(getback_coords.keys()) if getback_coords else 'None'}")
            if getback_coords and defender_id in getback_coords:
                stored_coords = getback_coords[defender_id]
                defender_actual_x = stored_coords.get("x")
                defender_actual_y = stored_coords.get("y")
                # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] ✅ Using get-back coords for defender {defender_id}: {defender_actual_x}, {defender_actual_y}")
            # elif getback_coords:
            #     logging.debug(f"  ⚠️ Defender {defender_id} not found in getback_coords (not a get-back player in most recent shot)")
            # else:
            #     logging.debug(f"  ⚠️ No getback_coords in most recent shot turn")
        
        # Fallback to defender's current coords if no get-back coords found
        if defender_actual_x is None or defender_actual_y is None:
            defender_actual_x = getattr(defender, "coords", {}).get("x", 50)
            defender_actual_y = getattr(defender, "coords", {}).get("y", 25)
            # Debug log removed to declutter output
        
        # ✅ Defender position after outlet step (NO MOVEMENT - same as ball handler)
        # Defenders stay at their starting position during outlet pass, only move during defensive stop/shot attempt
        defender_move_x = 0
        defender_move_y = 0
        defender_outlet_x = defender_actual_x  # No movement during outlet pass
        defender_outlet_y = defender_actual_y  # No movement during outlet pass
        
        # Store defender outlet position for animation
        if not hasattr(defender, "outlet_coords"):
            defender.outlet_coords = {}
        defender.outlet_coords["x"] = defender_outlet_x
        defender.outlet_coords["y"] = defender_outlet_y
        def_coords_cutoff[pos] = {
            "x": int(defender_outlet_x),
            "y": int(defender_outlet_y),
        }
        
        # Calculate distance for closest defender tracking (for shot attempts)
        x_distance = abs(defender_outlet_x - ball_handler_outlet_x)
        y_distance = abs(defender_outlet_y - ball_handler_outlet_y)
        total_distance = (x_distance ** 2 + y_distance ** 2) ** 0.5  # Euclidean distance
        
        # Track closest defender overall (for shot attempts) - ONLY among get-back players
        # Shot defender exists only when there are 1 or 2 get-back players (set after loop)
        if defender_id and defender_id in getback_player_ids and total_distance < closest_distance_overall:
            closest_distance_overall = total_distance
            closest_defender_overall = defender
    
    # --- Unified drive cutoff (shared with HCT ``cutoff_resolution``) ------------
    from BackEnd.engine.cutoff_resolution import (
        best_cutoff_on_drive,
        map_cutoff_outcome_to_fb,
        resolve_cutoff_contest,
    )
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec

    move_distance = random.randint(BALL_HANDLER_MOVE_X_MIN, BALL_HANDLER_MOVE_X_MAX)
    additional_move_x = direction * move_distance
    additional_move_y = random.randint(-BALL_HANDLER_MOVE_Y_RANGE, BALL_HANDLER_MOVE_Y_RANGE)
    fb_roles["ball_handler_drive_roll_x"] = additional_move_x
    fb_roles["ball_handler_drive_roll_y"] = additional_move_y

    bh_start = {
        "x": int(ball_handler_outlet_x),
        "y": int(ball_handler_outlet_y),
    }
    drive_target = {
        "x": max(4, min(97, int(ball_handler_outlet_x + additional_move_x))),
        "y": max(1, min(49, int(ball_handler_outlet_y + additional_move_y))),
    }
    bh_drive_rate = _ag_grid_per_game_sec(ball_handler, "sprint")

    if rebound:
        _cutoff_corridor = FB_CUTOFF_PATH_CORRIDOR_DREB
        _cutoff_slack = FB_CUTOFF_DEFENDER_TIME_SLACK_DREB
    else:
        _cutoff_corridor = FB_CUTOFF_PATH_CORRIDOR_STEAL
        _cutoff_slack = FB_CUTOFF_DEFENDER_TIME_SLACK_STEAL

    cutoff_pos, cutoff_meet = best_cutoff_on_drive(
        bh_start,
        drive_target,
        bh_drive_rate,
        def_coords_cutoff,
        def_lineup,
        get_defender_rate=lambda d: _ag_grid_per_game_sec(d, "sprint"),
        path_corridor=_cutoff_corridor,
        defender_time_slack=_cutoff_slack,
        stop_attempt_prob=_stop_attempt_prob,
    )
    closest_stopping_defender = (
        def_lineup.get(cutoff_pos) if cutoff_pos else None
    )
    if cutoff_meet is not None:
        fb_roles["cutoff_meet_x"] = cutoff_meet["x"]
        fb_roles["cutoff_meet_y"] = cutoff_meet["y"]

    # ✅ If we found a stopping defender who wasn't in fb_roles["defense"], add them for animation
    if closest_stopping_defender and closest_stopping_defender not in fb_roles["defense"]:
        fb_roles["defense"].append(closest_stopping_defender)
        # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Added stopping defender to fb_roles['defense']: {get_name_safe(closest_stopping_defender)} (was not in initial list)")
    
    # ✅ For shot attempts: shot defender only when 1 or 2 get-back players (get-back only)
    num_getback = len(getback_player_ids)
    if num_getback in (1, 2) and closest_defender_overall:
        fb_roles["shot_defender"] = closest_defender_overall
        # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Closest defender overall (get-back only): {get_name_safe(closest_defender_overall)}, distance: {closest_distance_overall:.2f}")
    
    # Determine event type based on defender positions
    d_count = len(fb_roles["defense"])
    
    # ==================== STAT TRACKING ====================
    # Track Fast Break defender count for offense team (team running the break)
    if not hasattr(off_team, 'team_stats'):
        off_team.team_stats = {}
    
    if d_count == 0:
        off_team.team_stats['zero_defenders_back'] = off_team.team_stats.get('zero_defenders_back', 0) + 1
    elif d_count == 1:
        off_team.team_stats['one_defender_back'] = off_team.team_stats.get('one_defender_back', 0) + 1
    else:  # d_count >= 2
        off_team.team_stats['two_defenders_back'] = off_team.team_stats.get('two_defenders_back', 0) + 1
    # ==================== END STAT TRACKING ====================

    # ✅ NEW LOGIC: Cutoff meet → D8 contest; otherwise shot attempt
    # logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Final determination:")
    # logging.debug(f"  d_count: {d_count}")
    # logging.debug(f"  defender_ahead: {defender_ahead}")
    # logging.debug(f"  ball_handler_outlet_x: {ball_handler_outlet_x}")
    # logging.debug(f"  is_away_offense: {is_away_offense}")
    
    if d_count == 0:
        # 0 defenders: Always shot
        event_type = "SHOT"
        logging.debug(f"  ✅ Decision: SHOT (0 defenders)")
        # Shot defender only when 1 or 2 get-back players (get-back pool only)
        if num_getback in (1, 2) and closest_defender_overall:
            fb_roles["defender"] = closest_defender_overall
            fb_roles["defender_count"] = num_getback
        else:
            fb_roles["defender"] = None
            fb_roles["defender_count"] = 0
    elif cutoff_meet is not None and closest_stopping_defender:
        outcome, _ratio, credited = resolve_cutoff_contest(
            off_team,
            def_team,
            ball_handler,
            closest_stopping_defender,
            exclude_steal=True,
        )
        event_type, cutoff_flags = map_cutoff_outcome_to_fb(outcome)
        stopper_id = closest_stopping_defender.player_id
        best_defender = closest_stopping_defender
        hold_up = True
        closest_defender = closest_stopping_defender
        fb_roles["stopper_id"] = stopper_id

        if cutoff_flags.get("ball_handler_beats_defender"):
            fb_roles["ball_handler_beats_defender"] = True
            shot_def = None
            shot_dist = float("inf")
            for d in def_lineup.values():
                did = getattr(d, "player_id", None)
                if not did or did not in getback_player_ids or did == stopper_id:
                    continue
                ox = getattr(d, "outlet_coords", {}).get("x", 50)
                oy = getattr(d, "outlet_coords", {}).get("y", 25)
                td = (
                    (ox - ball_handler_outlet_x) ** 2
                    + (oy - ball_handler_outlet_y) ** 2
                ) ** 0.5
                if td < shot_dist:
                    shot_dist = td
                    shot_def = d
            fb_roles["defender"] = shot_def
            fb_roles["defender_count"] = 1 if shot_def else 0
        elif event_type == "FOUL":
            game_state["foul_team"] = cutoff_flags.get("foul_team", "DEFENSE")
            fb_roles["foul_player"] = credited or closest_stopping_defender
            fb_roles["defender"] = credited or closest_stopping_defender
            fb_roles["defender_count"] = 1
        elif event_type == "DEFENSIVE_STOP":
            fb_roles["defender"] = closest_stopping_defender
            fb_roles["defender_count"] = 1
        elif event_type == "DEAD BALL":
            fb_roles["defender"] = closest_stopping_defender
            fb_roles["defender_count"] = 1

        logging.debug(
            "  🎯 Cutoff contest: outcome=%s → event_type=%s stopper=%s",
            outcome,
            event_type,
            stopper_id,
        )
    else:
        # No cutoff meet: shot attempt (no separate skill check)
        # Shot defender only when 1 or 2 get-back players (closest among get-back only)
        event_type = "SHOT"
        if num_getback in (1, 2) and closest_defender_overall:
            fb_roles["defender"] = closest_defender_overall
            fb_roles["defender_count"] = num_getback
        else:
            fb_roles["defender"] = None
            fb_roles["defender_count"] = 0

    # ==================== OUTLET PASS STAT TRACKING ====================
    # Record outlet pass stats if outlet pass occurred
    outlet_passer_id = fb_roles.get("outlet_passer")
    outlet_score = fb_roles.get("outlet_score")
    if outlet_passer_id and outlet_score is not None:
        # Outlet pass is successful if it leads to a shot attempt (not defensive stop)
        is_successful = (event_type == "SHOT")
        _record_outlet_pass_stats(outlet_passer_id, outlet_score, is_successful, game)
    # ==================== END OUTLET PASS STAT TRACKING ====================

    # If defensive stop triggered, defense stopped the fast break
    # NOTE: This should NOT happen if has_outlet_pass is True (handled above)
    if event_type == "DEFENSIVE_STOP":
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
        game.game_state["offensive_state"] = "HCO"
        
        # Build animation packet for the fast break play (for outlet pass animation)
        animator = Animator(game)
        animations = animator.capture_fast_break_animation(
            fb_roles, hold_up, stopper_id
        )
        
        # Return a defensive stop result but include Fast Break roles and flags
        # This ensures the frontend can animate the outlet pass before showing the stop
        ball_handler = fb_roles["ball_handler"]
        defender_name = get_name_safe(best_defender) if best_defender else "Defense"
        result = {
            "result_type": "DEFENSIVE_STOP",
            "ball_handler": ball_handler,
            "defender": best_defender,
            "text": f"Fast Break! Nice stop by {defender_name}!",
            "possession_flips": False,
            "time_elapsed": 0,
            "animations": animations,
            "current_turn": "FAST_BREAK",  # ✅ SS&S: Explicit turn type
            "next_play_type": "HCO",
            "next_turn": "HCO",  # ✅ SS&S: Explicit next turn
            "offense_team_id": off_team.team_id,  # ✅ FIX: Add offense_team_id (possession doesn't flip, same team continues)
            "roles": fb_roles,  # ✅ Include roles so frontend can animate outlet pass
            "fast_break": True,  # Legacy flag for backwards compatibility
            "fast_break_play": fb_play_key,
        }
        
        # 🏀 [FAST BREAK RESULT] One-line debug for animation tuning (ball_handler end = where they are when turn ends)
        bh = result.get("roles", {}).get("ball_handler")
        bh_id = getattr(bh, "player_id", None) if bh else None
        bh_end = None
        for a in (result.get("animations") or []):
            if a.get("playerId") == bh_id and "end" in a:
                bh_end = a["end"]
                break
        if bh_end is not None:
            logging.debug("🏀 [FAST BREAK RESULT] Defensive Stop (ball_handler_end: x=%s, y=%s)", bh_end.get("x"), bh_end.get("y"))
        else:
            logging.debug("🏀 [FAST BREAK RESULT] Defensive Stop (ball_handler_end: n/a)")
        if hold_up:
            result["hold_up"] = True
            result["stopper_id"] = stopper_id
        
        # ==================== FAST BREAK STAT TRACKING ====================
        # Record Fast Break stats for release player (offensive) and get-back players (defensive)
        _record_fast_break_stats(fb_roles, result, game)
        # ==================== END FAST BREAK STAT TRACKING ====================
        apply_fast_break_cg_time(result, shot_attempted=False)

        # Parallel-build: emit unified AnimationStep[] for Covert Release.
        # All FB variants (CR / RR / Triangle / After-Steal) now emit unified
        # AnimationStep[] via their own emitters; the legacy renderer is only a
        # fallback when an emitter returns None (logged as … EMITTER NULL). See
        # _documentation_master/projects/FB_UESS_Migration.md.
        if fb_play_key == "covert_release":
            try:
                from BackEnd.engine.covert_release_step_emitter import (
                    build_covert_release_animation_steps,
                )
                anim_steps = build_covert_release_animation_steps(result, game)
                if anim_steps is not None:
                    result["animation_steps"] = anim_steps
                else:
                    # The emitter logs its own 🚨 [CR EMITTER NULL] line with
                    # the specific guard that fired.
                    logging.warning(
                        "🚨 [CR EMITTER NULL CONSEQUENCE] (defensive_stop) "
                        "result_type=%s — animation_steps not set, FE → LEGACY",
                        result.get("result_type"),
                    )
            except Exception as e:
                logging.exception(
                    "🚨 [CR EMITTER EXCEPTION] (defensive_stop) result_type=%s: %s "
                    "— animation_steps not set, FE → LEGACY",
                    result.get("result_type"), e,
                )

        return result

    #get shooter and passer (if applicable)
    # Assign shooter and passer for shot, turnover, or foul scenarios
    offense_in_play = [fb_roles["ball_handler"]] + fb_roles["offense"]
    shooter = random.choice(offense_in_play)

    fb_roles["shooter"] = shooter
    
    # Determine passer for assist tracking
    shooter_id = getattr(shooter, "player_id", None)
    outlet_receiver_id = fb_roles.get("outlet_receiver")
    outlet_passer_id = fb_roles.get("outlet_passer")
    
    # If shooter is the outlet receiver (who received the outlet pass after DREB), passer is the outlet passer (rebounder)
    if outlet_receiver_id and outlet_passer_id and shooter_id == outlet_receiver_id:
        # Find the outlet passer player object
        passer = None
        for player in off_team.get_all_players():
            if getattr(player, "player_id", None) == outlet_passer_id:
                passer = player
                break
        fb_roles["passer"] = passer
    # Otherwise, if shooter is not the ball handler, then ball handler is the passer
    elif shooter != fb_roles["ball_handler"]:
        fb_roles["passer"] = fb_roles["ball_handler"]
    else:
        fb_roles["passer"] = None
    
    fb_roles["screener"] = None

    # Foul or turnover possibilities
    if event_type == "O_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "OFFENSE"
    elif event_type == "D_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "DEFENSE"

    # print(f"Event type: {event_type}")
    # print(f"Roles: {fb_roles}")
    
    fb_animations = None  # Set in SHOT branch when we capture before resolve_shot (for block reconciliation shot spot)
    
    if event_type == "SHOT":
        # Route Fast Break shot through attack shot execution (resolve_shot) via adapter
        shooter = fb_roles["shooter"]
        defender = fb_roles.get("defender")
        defender_count = fb_roles.get("defender_count", len(fb_roles.get("defense", [])))

        roles = {
            "shooter": shooter,
            "passer": fb_roles.get("passer"),
            "screener": None,
            "defender": defender,
            "shot_type": "attack",
            "is_fast_break": True,
            "motion_playcall": "Attack",
            "defender_count": defender_count,
        }

        # Fast Break shot threshold: use effective defender count (reduce by 1 if defender attempted stop and failed)
        # Stats/animation still use actual defender_count; only threshold uses effective count
        effective_defender_count = defender_count
        if fb_roles.get("ball_handler_beats_defender"):
            effective_defender_count = max(0, defender_count - 1)
        base_threshold = off_team.team_attributes["shot_threshold"]
        def_chemistry = int((def_team.team_attributes.get("team_chemistry") or 0))
        off_fight = int((off_team.team_attributes.get("fight") or 0) * 2)
        if effective_defender_count == 0:
            shot_threshold = 1
        elif effective_defender_count >= 2:
            shot_threshold = base_threshold + 100 + def_chemistry - off_fight
        else:
            shot_threshold = base_threshold
        game_state["fast_break_shot_threshold_override"] = shot_threshold

        # Capture Fast Break animation first so fb_roles gets _bh_final_x/y (shot spot); set shooter coords for block reconciliation
        animator = Animator(game)
        fb_animations = animator.capture_fast_break_animation(fb_roles, hold_up, stopper_id)
        # SS&S migration: migrated FB variants (CR) build their own start coords
        # from `player.coords`, so applying the legacy animator's pre-staged
        # positions here would create a discontinuity between the prior turn's
        # end coords and step 0 start coords (visible as players "jetting" down
        # the court at the FB→step-0 boundary, or a horizontal mirror-flip
        # teleport when offense is AWAY since the animator pre-stages in
        # display orientation via `get_away_player_coords`). Skip apply_coords
        # for migrated variants. RR + Triangle have the analogous skip gated
        # by `fb_play_key not in (RIM_RUNNER, TRIANGLE)` at five call sites
        # inside `resolve_rim_runner_fast_break`. Steal-FB does not call
        # `apply_coords_from_animations_list` (migrated cleanly without the
        # legacy animator path).
        if fb_play_key != "covert_release":
            apply_coords_from_animations_list(game, fb_animations)
        # Pass the shot spot to `resolve_shot` via `roles["shot_spot"]` ONLY.
        # Do NOT mutate `shooter.coords` here — that would overwrite the BH's
        # release-position `player.coords` (the prior turn's end coord, which
        # the CR emitter needs for step 0 START). Block reconciliation in
        # shot_manager reads from `roles["shot_spot"]` (line ~790) with
        # shooter.coords only as a fallback when roles is missing — which
        # doesn't happen here. See UESS_System.md §9 (cross-turn coord sync).
        if fb_roles.get("_bh_final_x") is not None and fb_roles.get("_bh_final_y") is not None:
            shot_spot = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
            roles["shot_spot"] = shot_spot
        snap_roles = {**roles, "ball_handler": fb_roles.get("ball_handler")}
        fb_snap = build_fast_break_pre_shot_snapshot(
            game, off_lineup, def_lineup, snap_roles, "fb_logic_pre_shot"
        )
        # Universal geometry: CR shot path. Overrides shot_spot + defender
        # + threshold using the helper. Gated by feature flag for revert.
        # Race pool: all defenders EXCEPT stopper (CR has no outlet defender
        # concept). See _documentation_master/projects/fast_break_*.md.
        if fb_play_key == "covert_release":
            from BackEnd.constants import USE_UNIVERSAL_FB_SHOT_GEOMETRY_CR
            if USE_UNIVERSAL_FB_SHOT_GEOMETRY_CR:
                from BackEnd.utils.fast_break_shot_geometry import (
                    compute_fb_shot_geometry,
                )

                cr_shooter = fb_roles["shooter"]
                cr_shooter_id = (
                    str(getattr(cr_shooter, "player_id", "")) or None
                )
                cr_stopper_id = (
                    str(stopper_id) if stopper_id is not None else None
                )
                cr_available: list = []
                cr_defender_starts: dict = {}
                for _d in def_lineup.values():
                    if _d is None:
                        continue
                    _did = getattr(_d, "player_id", None)
                    if _did is None:
                        continue
                    _did_s = str(_did)
                    if cr_stopper_id is not None and _did_s == cr_stopper_id:
                        continue
                    cr_available.append(_d)
                    # Start coord = end of preceding step. Source from
                    # animator output; fall back to live coords.
                    _anim_end = None
                    for _entry in (fb_animations or []):
                        if str(_entry.get("playerId")) == _did_s:
                            _anim_end = (
                                _entry.get("end") or _entry.get("end_coords")
                            )
                            if isinstance(_anim_end, dict):
                                break
                    if isinstance(_anim_end, dict) and "x" in _anim_end and "y" in _anim_end:
                        cr_defender_starts[_did_s] = {
                            "x": float(_anim_end["x"]),
                            "y": float(_anim_end["y"]),
                        }
                    else:
                        _raw = getattr(_d, "coords", None) or {}
                        cr_defender_starts[_did_s] = {
                            "x": float(_raw.get("x", 50.0)),
                            "y": float(_raw.get("y", 25.0)),
                        }

                # Shooter start: animator end → live coords fallback.
                cr_shooter_start = {"x": 50.0, "y": 25.0}
                _found = False
                for _entry in (fb_animations or []):
                    if str(_entry.get("playerId")) == cr_shooter_id:
                        _anim_end = (
                            _entry.get("end") or _entry.get("end_coords")
                        )
                        if isinstance(_anim_end, dict) and "x" in _anim_end and "y" in _anim_end:
                            cr_shooter_start = {
                                "x": float(_anim_end["x"]),
                                "y": float(_anim_end["y"]),
                            }
                            _found = True
                            break
                if not _found:
                    _raw = getattr(cr_shooter, "coords", None) or {}
                    if isinstance(_raw, dict) and "x" in _raw and "y" in _raw:
                        cr_shooter_start = {
                            "x": float(_raw["x"]),
                            "y": float(_raw["y"]),
                        }

                cr_geometry = compute_fb_shot_geometry(
                    shooter=cr_shooter,
                    shooter_start=cr_shooter_start,
                    available_defenders=cr_available,
                    defender_starts=cr_defender_starts,
                    is_away_offense=is_away_offense,
                )

                # Override shot_spot + defender + threshold.
                roles["shot_spot"] = dict(cr_geometry["shooter_target"])
                # UESS: contest was decided here from the render-matched defender
                # ends — tell resolve_shot to honor roles["defender"] instead of
                # re-deriving from stale (pre-race) def_lineup.coords, so the block
                # path fires on contested CR. See Coord_Consumer_UESS_Audit.md #2.
                roles["fb_geometry_contest_resolved"] = True
                if cr_geometry["contested"] and cr_geometry["shot_defender_id"]:
                    for _d in def_lineup.values():
                        if _d is None:
                            continue
                        if str(getattr(_d, "player_id", "")) == cr_geometry["shot_defender_id"]:
                            roles["defender"] = _d
                            fb_roles["defender"] = _d
                            fb_roles["defender_count"] = 1
                            break
                else:
                    roles["defender"] = None
                    fb_roles["defender"] = None
                    fb_roles["defender_count"] = 0
                    game_state["fast_break_shot_threshold_override"] = 1

                # Update fb_animations end coords for shooter + racing
                # defenders so the schema emitter renders new positions.
                # Must write BOTH `entry["end"]` (downstream BE wiring +
                # FE legacy paths) AND `entry["movement"][-1]["coords"]`
                # (UESS emitter reads via `_movement_end_coord`). Writing
                # only `entry["end"]` silently drops the override at the
                # emitter — BH renders at the legacy animator's spot.
                _override = dict(cr_geometry["defender_end_coords"])
                if cr_shooter_id:
                    _override[cr_shooter_id] = cr_geometry["shooter_target"]
                _override_applied = 0
                for _entry in (fb_animations or []):
                    _pid_s = str(_entry.get("playerId"))
                    if _pid_s in _override:
                        _new = dict(_override[_pid_s])
                        _entry["end"] = _new
                        _mv = _entry.get("movement") or []
                        if _mv and isinstance(_mv[-1], dict):
                            _mv[-1]["coords"] = dict(_new)
                        _override_applied += 1
                logging.warning(
                    "🔍 [FB UNIVERSAL CR] shot_spot=%s contested=%s shot_def=%s applied_overrides=%d",
                    cr_geometry["shooter_target"],
                    cr_geometry["contested"],
                    cr_geometry["shot_defender_id"],
                    _override_applied,
                )

        turn_result = game.shot_manager.resolve_shot(roles)
        game_state.pop("fast_break_shot_threshold_override", None)
        attach_position_snapshots(turn_result, [fb_snap])

        turn_result["defender_count"] = defender_count
        turn_result["outlet_passer_id"] = fb_roles.get("outlet_passer")

        if turn_result.get("result_type") == "MAKE":
            points = turn_result.get("points", 2)
            shooter.record_stat("FB_PTS", amount=points)
            if fb_roles.get("is_steal_entry"):
                pot_points = 3 if fb_roles.get("is_three_point_shot") else points
                shooter.record_stat("POT", amount=pot_points)

    elif event_type == "TURNOVER":
        turnover_type = random.choice(["STEAL", "DEAD BALL"])
        turn_result = resolve_turnover_logic(fb_roles, game, turnover_type)
    elif event_type == "DEAD BALL":
        turn_result = resolve_turnover_logic(
            fb_roles, game, "DEAD BALL", from_resolution_system=True,
        )
    elif event_type == "FOUL":
        turn_result = resolve_non_shooting_foul(fb_roles, game)
    
    if turn_result["result_type"] == "MAKE": #def_scouting
        off_scouting["offense"]["Fast_Break_Success"] += 1
        ensure_fast_break_plays(off_scouting["offense"])[fb_play_key]["S"] += 1

    elif turn_result["result_type"] == "FOUL":
        if game_state.get("foul_team") == "DEFENSE":
            off_scouting["offense"]["Fast_Break_Success"] += 1
            ensure_fast_break_plays(off_scouting["offense"])[fb_play_key]["S"] += 1
        elif game_state.get("foul_team") == "OFFENSE":
            def_scouting["defense"]["vs_Fast_Break"]["success"] += 1

    elif turn_result["result_type"] in ["MISS", "BLOCK", "TURNOVER"]:
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1


    # Build animation packet for the fast break play (reuse fb_animations if we already captured for SHOT)
    if fb_animations is not None:
        turn_result["animations"] = fb_animations
    else:
        turn_result["animations"] = Animator(game).capture_fast_break_animation(
            fb_roles, hold_up, stopper_id
        )
    turn_result["roles"] = fb_roles
    turn_result["fast_break"] = True  # ✅ Add fast_break flag for frontend routing
    apply_fast_break_cg_time(turn_result, shot_attempted=(event_type == "SHOT"))

    rt_fb = turn_result.get("result_type")
    if rt_fb in ("STEAL", "DEAD BALL", "FOUL"):
        fb_anims = turn_result.get("animations") or []
        if fb_anims:
            apply_coords_from_animations_list(game, fb_anims)
        outcome_kind = "non_shooting_foul" if rt_fb == "FOUL" else "turnover"
        attach_position_snapshots(
            turn_result,
            [
                build_phase_post_stopper_snapshot(
                    game,
                    off_lineup,
                    def_lineup,
                    None,
                    fb_roles,
                    "FAST_BREAK",
                    outcome_kind,
                    f"fb_{outcome_kind}_post_stopper",
                )
            ],
        )

    # ✅ SS&S: Backend is single source of truth for shot spot and defender placement on Fast Break shots
    # Expose so frontend uses these instead of recomputing (avoids mismatch and missing defender)
    if not hold_up and fb_roles.get("_bh_final_x") is not None and fb_roles.get("_bh_final_y") is not None:
        turn_result["shot_spot"] = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
    shot_def = fb_roles.get("defender")
    defender_id = getattr(shot_def, "player_id", None) if shot_def else None
    if defender_id:
        turn_result["defender_id"] = defender_id
        # Defender spot is in the animation entry for this player
        for anim in (turn_result.get("animations") or []):
            if anim.get("playerId") == defender_id and "end" in anim:
                turn_result["defender_spot"] = anim["end"]
                break

    # ==================== FAST BREAK STAT TRACKING ====================
    # Record Fast Break stats for release player (offensive) and get-back players (defensive)
    _record_fast_break_stats(fb_roles, turn_result, game)
    # ==================== END FAST BREAK STAT TRACKING ====================

    # 🏀 [FAST BREAK RESULT] One-line debug for animation tuning (ball_handler end = where shooter/BH is when turn ends)
    rt = turn_result.get("result_type")
    if rt == "MAKE":
        label = "Make (and-1)" if turn_result.get("next_play_type") == "FREE_THROW" and game_state.get("foul_team") == "DEFENSE" else "Make"
    elif rt == "MISS":
        reb = turn_result.get("rebound_type", "?")
        label = f"Miss ({reb})"
    elif rt == "CHARGE":
        label = "Charge"
    elif rt == "FOUL":
        label = "Foul (blocking)"
    elif rt == "TURNOVER":
        label = turn_result.get("text", "Turnover")[:40]  # STEAL or DEAD BALL style
    else:
        label = str(rt)
    bh_end = turn_result.get("shot_spot")  # Set for shot attempts from _bh_final_x/y
    if bh_end is None:
        bh = turn_result.get("roles", {}).get("ball_handler")
        bh_id = getattr(bh, "player_id", None) if bh else None
        for a in (turn_result.get("animations") or []):
            if a.get("playerId") == bh_id and "end" in a:
                bh_end = a["end"]
                break
    if bh_end is not None:
        logging.debug("🏀 [FAST BREAK RESULT] %s (ball_handler_end: x=%s, y=%s)", label, bh_end.get("x"), bh_end.get("y"))
    else:
        logging.debug("🏀 [FAST BREAK RESULT] %s (ball_handler_end: n/a)", label)
    # 🔍 ANNOUNCEMENT DIAGNOSTIC: Confirm payload sent to frontend has fast_break (so announcements can run)
    logging.warning(
        "📢 [ANNOUNCEMENT DIAGNOSTIC] resolve_fast_break_logic returning turn: result_type=%s fast_break=%s (type=%s) has_roles=%s",
        turn_result.get("result_type"),
        turn_result.get("fast_break"),
        type(turn_result.get("fast_break")).__name__,
        "roles" in turn_result,
    )
    if hold_up:
        turn_result["hold_up"] = True
        turn_result["stopper_id"] = stopper_id
    
    # Prepend "Fast Break!" to the text
    turn_result["text"] = "Fast Break! " + turn_result.get("text", "")

    turn_result["fast_break_play"] = fb_play_key

    # Parallel-build: emit unified AnimationStep[] for Covert Release.
    # All FB variants (CR / RR / Triangle / After-Steal) now emit unified
    # AnimationStep[] via their own emitters; the legacy renderer is only a
    # fallback when an emitter returns None (logged as … EMITTER NULL). See
    # _documentation_master/projects/FB_UESS_Migration.md.
    if fb_play_key == "covert_release":
        try:
            from BackEnd.engine.covert_release_step_emitter import (
                build_covert_release_animation_steps,
            )
            anim_steps = build_covert_release_animation_steps(turn_result, game)
            if anim_steps is not None:
                turn_result["animation_steps"] = anim_steps
            else:
                # The emitter logs its own 🚨 [CR EMITTER NULL] line with the
                # specific guard that fired. This log marks the consequence
                # (FE will route to LEGACY_HANDLER → potential double-rebound
                # on CR FB MISS when DREB promotion fires).
                logging.warning(
                    "🚨 [CR EMITTER NULL CONSEQUENCE] result_type=%s rebound_type=%s "
                    "next_play_type=%s — animation_steps not set, FE → LEGACY",
                    turn_result.get("result_type"),
                    turn_result.get("rebound_type"),
                    turn_result.get("next_play_type"),
                )
        except Exception as e:
            logging.exception(
                "🚨 [CR EMITTER EXCEPTION] (outcome) result_type=%s rebound_type=%s: %s "
                "— animation_steps not set, FE → LEGACY",
                turn_result.get("result_type"),
                turn_result.get("rebound_type"),
                e,
            )

    # Parallel-build: emit unified AnimationStep[] for steal-initiated FBs
    # (after_steal). Schema-driven choreography includes burst, shot motion,
    # post-shot variant sub-steps (RATTLE hops / bank / etc.), and the
    # defensive-stop step-back step whose end.coords becomes the
    # authoritative coord snapshot for the next HCO turn's handoff.
    if fb_play_key == AFTER_STEAL:
        try:
            from BackEnd.engine.after_steal_fast_break_step_emitter import (
                build_after_steal_fast_break_animation_steps,
            )
            anim_steps = build_after_steal_fast_break_animation_steps(
                turn_result, game,
            )
            if anim_steps is not None:
                turn_result["animation_steps"] = anim_steps
            else:
                # The emitter logs its own 🐛 [AFTER_STEAL_NONE site=...] line.
                logging.warning(
                    "🚨 [AFTER_STEAL EMITTER NULL CONSEQUENCE] result_type=%s "
                    "rebound_type=%s next_play_type=%s — animation_steps not set, "
                    "FE → LEGACY",
                    turn_result.get("result_type"),
                    turn_result.get("rebound_type"),
                    turn_result.get("next_play_type"),
                )
        except Exception as e:
            logging.exception(
                "🚨 [AFTER_STEAL EMITTER EXCEPTION] result_type=%s: %s "
                "— animation_steps not set, FE → LEGACY",
                turn_result.get("result_type"), e,
            )

    # ✅ Add safety checks before returning
    assert turn_result is not None, "turn_result is None"
    assert "time_elapsed" in turn_result, "turn_result missing 'time_elapsed'"
    return turn_result


def resolve_free_throw_logic(game):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    shooter_reference = game_state.get("shooter") or game_state.get("last_ball_handler")
    shooter = resolve_game_player_reference(game, shooter_reference)
    if shooter is None:
        raise HTTPException(
            status_code=400,
            detail="Free throw shooter could not be resolved to a player",
        )
    game_state["shooter"] = shooter
    attrs = shooter.attributes

    # Momentum: track this trip's FT attempts/makes across the per-FT calls so a
    # player who attempts >1 FT and misses them ALL takes a flat MO penalty at
    # trip end (Player_Momentum_System.md). Counters live in game_state so they
    # survive a mid-trip timeout/resume; cleared when the trip concludes.
    if not game_state.get("mo_ft_trip_active"):
        game_state["mo_ft_trip_active"] = True
        game_state["mo_ft_trip_attempts"] = 0
        game_state["mo_ft_trip_makes"] = 0

    # FT outcome calculation
    # Formula: (FT * 0.8) + (CH * 0.2)
    ft_shot_score = (attrs["FT"] * 0.8) + (attrs["CH"] * 0.2)
    ft_primary_roll = random.randint(1, 100)
    text = f"ft_shot_score: {ft_shot_score}, roll: {ft_primary_roll}  "
    makes_shot = ft_primary_roll < ft_shot_score
    ft_made_on_second_chance = False

    # Secondary check: miss → make. Base % is crowd-tiered (home default; away
    # drops with crowd factor), nudged by the shooter's momentum
    # (Player_Momentum_System.md § Free Throw Impact): threshold = base% +
    # MO × randint(*MO_FT_SECOND_CHANCE_ROLL), clamped to [0,100]; a 1–100 roll
    # below the threshold upgrades the miss to a make.
    if not makes_shot:
        second_chance_pct = effective_ft_miss_to_make_second_chance(game, off_team) * 100
        ft_mo = int(attrs.get("MO", 0) or 0)
        _sc_lo, _sc_hi = MO_FT_SECOND_CHANCE_ROLL
        second_chance_threshold = second_chance_pct + ft_mo * random.randint(_sc_lo, _sc_hi)
        second_chance_threshold = max(0, min(100, second_chance_threshold))
        if random.randint(1, 100) < second_chance_threshold:
            makes_shot = True
            ft_made_on_second_chance = True

    shooter.record_stat("FTA")
    game_state["mo_ft_trip_attempts"] = game_state.get("mo_ft_trip_attempts", 0) + 1
    if makes_shot:
        game_state["mo_ft_trip_makes"] = game_state.get("mo_ft_trip_makes", 0) + 1
    text += f"{get_name_safe(shooter)} steps to the line... "
    possession_flips = False

    attempts = ["MAKE" if makes_shot else "MISS"]
    animator = Animator(game)
    animations = animator.capture_free_throw_animation(
        game,
        shooter,
        attempts,
        offense_is_home=(off_team.team_id == game.home_team.team_id),
        no_lane=game_state.get("no_lane", False),
    )
    # Keep lineup coordinates in sync with the FT lane/setup animation before
    # any rebound geography logic runs. Without this, missed-FT rebound
    # selection can read stale half-court coords.
    apply_coords_from_animations_list(game, animations)
    shooter_pos = get_player_position(off_lineup, shooter)

    from BackEnd.constants.shot_variants import (
        SHOT_VARIANT_AIRBALL,
        roll_shot_variant_extras,
        select_ft_shot_variant,
    )

    shooter_sc = getattr(shooter, "coords", None) or {}
    try:
        shooter_y = float(shooter_sc.get("y", 25))
    except (TypeError, ValueError):
        shooter_y = 25.0
    shot_variant = select_ft_shot_variant(
        ft_shot_score,
        ft_primary_roll,
        makes_shot,
        ft_made_on_second_chance,
    )
    ft_variant_fields = {
        "ft_shot_score": ft_shot_score,
        "ft_primary_roll": ft_primary_roll,
        "ft_made_on_second_chance": ft_made_on_second_chance,
        "shot_variant": shot_variant,
        "make_settle_sfx_file": "free-throw-swish.wav",
        **roll_shot_variant_extras(shot_variant, shooter_y=shooter_y),
    }

    ft_snap = build_free_throw_snapshot(game, off_lineup, def_lineup, shooter)

    if makes_shot:
        apply_scoring(game, off_team, shooter, 1, ["FTM"])
        text += "and hits the free throw!"
    else:
        text += "but misses the free throw."

    # Handle 1-and-1 front-end logic
    decrement_ft_remaining = True
    if game_state.get("one_and_one", False):
        if game_state["free_throws_remaining"] == 1:
            if makes_shot:
                # Made front end → unlock second FT
                game_state["free_throws_remaining"] = 1
                game_state["one_and_one"] = False
                ooo = {
                    "result_type": "FREE_THROW",
                    "ball_handler": shooter,
                    "shooter": shooter,
                    "text": text,
                    "time_elapsed": 0,
                    "possession_flips": False,
                    "points": 1,
                    "scoring_team": off_team.name,
                    "animations": animations,
                    "attempts": attempts,
                    "shooter_id": getattr(shooter, "player_id", None),
                    "shooter_pos": shooter_pos,
                    "offense_team_id": off_team.team_id,
                    "no_lane": game_state.get("no_lane", False),
                    "free_throws_remaining": game_state["free_throws_remaining"],  # ✅ FIX: Include free_throws_remaining so frontend knows more FTs remain
                    "one_and_one": False,  # ✅ FIX: Include one_and_one flag (now False since second FT is unlocked)
                }
                ooo.update(ft_variant_fields)
                attach_position_snapshots(ooo, [ft_snap])
                return ooo
            else:
                # Missed front end → dead ball, rebound
                game_state["free_throws_remaining"] = 0
                game_state["one_and_one"] = False
                game_state["offensive_state"] = "HCO"
                # Already at 0; do not run the shared decrement (would become -1 and break
                # frontend isFinal === (free_throws_remaining === 0) for rebound/outlet).
                decrement_ft_remaining = False

    # Standard decrement when this attempt still consumes one FT from the remaining count
    if decrement_ft_remaining:
        game_state["free_throws_remaining"] -= 1

    # If no FTs remain, determine next state
    if game_state["free_throws_remaining"] <= 0:
        # Momentum: trip concluded (>1 FT attempted) — flat, once per trip:
        # all missed → penalty, all made → bonus (mixed → nothing). Then clear
        # the trip counters. (Player_Momentum_System.md)
        _ft_attempts = game_state.get("mo_ft_trip_attempts", 0)
        _ft_makes = game_state.get("mo_ft_trip_makes", 0)
        if _ft_attempts >= MO_FT_MIN_ATTEMPTS:
            if _ft_makes == 0:
                shooter.add_momentum(MO_FT_ALL_MISS_DELTA)
            elif _ft_makes == _ft_attempts:
                shooter.add_momentum(MO_FT_ALL_MAKE_DELTA)
        game_state["mo_ft_trip_active"] = False
        game_state["mo_ft_trip_attempts"] = 0
        game_state["mo_ft_trip_makes"] = 0

        # Check for defensive pressure if the last FT was made
        if makes_shot:
            from BackEnd.models.turn_manager import TurnManager
            pressure_type = TurnManager(game).determine_defensive_pressure_type()
            game_state["offensive_state"] = pressure_type
            # print(f"🏀 Last FT made - setting offensive_state to: {pressure_type}")
        else:
            game_state["offensive_state"] = "HCO"

        if not makes_shot:
            is_final_airball = shot_variant == SHOT_VARIANT_AIRBALL
            if is_final_airball:
                possession_flips = True
            else:
                # Unified geography-based rebound system for free throws
                # Calculate bounce spot (free throw is at the basket being attacked)
                is_away_offense = off_team.team_id == game.away_team.team_id
                # Home team attacks away basket (x=91), away team attacks home basket (x=9)
                basket_x = 9 if is_away_offense else 91
                bounce_spot = calculate_bounce_spot(game, basket_x=basket_x, basket_y=25)

                rebounder, rebound_team, stat = determine_rebounder(
                    game,
                    bounce_spot,
                    max_x_delta_from_bounce=FREE_THROW_REBOUND_MAX_X_DELTA,
                )
                # Stamped here so ``ft_step_emitter`` + discrete OREB/DREB share one bounce.
                game_state["_ft_last_bounce_spot"] = dict(bounce_spot)

                game_state.pop("_ft_rebound_x_gate_fallback", None)

                game_state["last_rebound"] = stat
                game_state["last_rebounder"] = rebounder

                # ✅ Record rebound stat BEFORE checking team (applies to both DREB and OREB)
                rebounder.record_stat(stat)

                if rebound_team == def_team:
                    possession_flips = True
                    text += f" {get_name_safe(rebounder)} grabs the defensive rebound."
                    from BackEnd.engine.dreb_fast_break_arming import (
                        SOURCE_FT,
                        arm_dreb_fast_break,
                    )

                    # Arm onto a temp dict; fields are copied onto ``result`` below.
                    _ft_arm_stamp: dict = {}
                    arm_dreb_fast_break(
                        game,
                        source=SOURCE_FT,
                        rebounder=rebounder,
                        rebounding_team=def_team,
                        result=_ft_arm_stamp,
                        ft_offense_lineup=off_lineup,
                        ft_defense_lineup=def_lineup,
                    )
                    game_state["_ft_dreb_fb_arm_stamp"] = _ft_arm_stamp
                else:
                    # Offensive rebound - store for separate turn processing
                    game_state["pending_oreb"] = {
                        "rebounder": rebounder,
                        "rebounder_id": getattr(rebounder, "player_id", None),
                    }
                    text += f" {get_name_safe(rebounder)} grabs the offensive rebound."
                    # OREB will be processed as a separate turn
        else:
            if not game_state.get("no_lane", False):
                possession_flips = True
    # When additional free throws remain, possession stays with the shooter’s team

    result = {
        "result_type": "FREE_THROW",
        "ball_handler": shooter,
        "shooter": shooter,
        "text": text,
        "time_elapsed": 0,  # clock does not run
        "possession_flips": possession_flips,
        "animations": animations,
        "attempts": attempts,
        "shooter_id": getattr(shooter, "player_id", None),
        "shooter_pos": shooter_pos,
        "offense_team_id": off_team.team_id,
        "current_turn": "FREE_THROW",  # ✅ SS&S: Explicit turn type
        "no_lane": game_state.get("no_lane", False),
        "free_throws_remaining": game_state["free_throws_remaining"],  # For frontend to know if final FT
        "one_and_one": game_state.get("one_and_one", False),  # For frontend 1&1 display
    }
    result.update(ft_variant_fields)

    if makes_shot:
        result["points"] = 1
        result["scoring_team"] = off_team.name
        # Add next_defensive_setup if final FT was made
        if game_state["free_throws_remaining"] <= 0:
            result["next_defensive_setup"] = game_state.get("offensive_state", "HCO")
            # ✅ FIX 2: Set next_play_type so backend creates BASELINE_INBOUND turn (Pattern A)
            result["next_play_type"] = "BASELINE_INBOUND"
            result["next_turn"] = "BASELINE_INBOUND"  # ✅ SS&S: Explicit next turn
    else:
        # Add rebounder information for missed free throws
        if shot_variant == SHOT_VARIANT_AIRBALL and game_state.get("free_throws_remaining", 0) <= 0:
            result["next_play_type"] = "BASELINE_INBOUND"
            result["next_turn"] = "BASELINE_INBOUND"
        elif game_state.get("last_rebounder"):
            result["rebounderId"] = getattr(game_state["last_rebounder"], "player_id", None)
            result["rebound_type"] = game_state.get("last_rebound", "")
            # Add next play type for defensive rebounds
            if game_state.get("last_rebound") == "DREB":
                arm_stamp = game_state.pop("_ft_dreb_fb_arm_stamp", None) or {}
                for k, v in arm_stamp.items():
                    result[k] = v
                result["next_play_type"] = game_state.get(
                    "offensive_state", result.get("next_play_type", "HCO")
                )
            else:
                game_state.pop("_ft_dreb_fb_arm_stamp", None)

    # Non-final miss: visual bounce only (``calculate_bounce_spot``); no rebound.
    if (
        not makes_shot
        and game_state.get("free_throws_remaining", 0) > 0
        and shot_variant != SHOT_VARIANT_AIRBALL
    ):
        is_away_offense = off_team.team_id == game.away_team.team_id
        basket_x = 9 if is_away_offense else 91
        bounce_spot = calculate_bounce_spot(game, basket_x=basket_x, basket_y=25)
        result["ball_bounce_x"] = float(bounce_spot["x"])
        result["ball_bounce_y"] = float(bounce_spot["y"])

    # Final miss: authoritative bounce + crash lists for schema + discrete rebound turns.
    if (
        not makes_shot
        and game_state.get("free_throws_remaining", 0) <= 0
        and shot_variant != SHOT_VARIANT_AIRBALL
    ):
        bounce_spot = game_state.pop("_ft_last_bounce_spot", None)
        if isinstance(bounce_spot, dict) and "x" in bounce_spot and "y" in bounce_spot:
            result["ball_bounce_x"] = float(bounce_spot["x"])
            result["ball_bounce_y"] = float(bounce_spot["y"])
        rebounder_id = result.get("rebounderId")
        shooter_id = result.get("shooter_id")
        bx = result.get("ball_bounce_x")
        by = result.get("ball_bounce_y")
        if rebounder_id and shooter_id and bx is not None and by is not None:
            from BackEnd.engine.ft_step_emitter import collect_ft_rebound_crashers

            off_crash, def_crash = collect_ft_rebound_crashers(
                off_lineup,
                def_lineup,
                {"x": float(bx), "y": float(by)},
                rebounder_id=str(rebounder_id),
                shooter_id=str(shooter_id),
                max_x_delta=float(FREE_THROW_REBOUND_MAX_X_DELTA),
            )
            result["offense_rebounders"] = off_crash
            result["defense_rebounders"] = def_crash

    if game_state["free_throws_remaining"] <= 0:
        from BackEnd.utils.eoq_clock_progression import apply_eoq_final_free_throw_routing

        apply_eoq_final_free_throw_routing(game, result, makes_shot=makes_shot)

    attach_position_snapshots(result, [ft_snap])
    return result


def resolve_turnover_logic(roles, game, turnover_type="DEAD BALL", from_resolution_system=False):

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    ball_handler = roles["ball_handler"]
    defender = roles.get("defender")
    ball_handler.record_stat("TO")
    
    # ✅ FIX: Respect resolution system's determination
    # If turnover_type comes from the resolution system, don't randomly convert it
    if from_resolution_system:
        # Resolution system has already determined the type, respect it
        if turnover_type == "DEAD BALL":
            turnover_type = "DEAD BALL"  # Keep as dead ball turnover
        elif turnover_type == "STEAL":
            turnover_type = "STEAL"  # Keep as steal
        elif turnover_type == "SHOT_CLOCK":
            turnover_type = "SHOT_CLOCK"  # Shot clock violation (announced as such; result_type stays DEAD BALL)
        # No random conversion when from resolution system
    else:
        # Legacy behavior: Only use random choice if turnover_type is not explicitly provided
        # This respects the actual turnover type instead of always randomizing
        if turnover_type == "DEAD BALL" and defender:
            # If defender is present, could be either STEAL or DEAD BALL
            # Use random choice only when both are possible
            turnover_type = random.choice(["STEAL", "DEAD BALL"])
        elif turnover_type == "DEAD BALL":
            # No defender, must be DEAD BALL
            turnover_type = "DEAD BALL"
        # If turnover_type is already "STEAL", keep it as STEAL
    game_state["last_turnover_player"] = ball_handler

    # Pre-compute IDs/names for logging and return payload
    stealer_id = getattr(defender, "player_id", None)
    stealer_name = get_name_safe(defender) if defender else None
    victim_id = getattr(ball_handler, "player_id", None)
    victim_name = get_name_safe(ball_handler)
    events = []

    if turnover_type == "STEAL" and defender:
        defender.record_stat("STL")
        # Momentum: stealer +, victim −.
        defender.add_momentum(MO_STEAL_DELTA)
        if ball_handler:
            ball_handler.add_momentum(-MO_STEAL_DELTA)
        text = f"{stealer_name} jumps the pass"
        # Stealing team = def_team; single roll uses their aggression only.
        p_steal = fast_break_probability_from_slider(
            slow_it_down_defense_setting(
                game_state, def_team, "aggression",
                def_team.strategy_settings.get("aggression", 2),
            )
        )
        fast_break_roll = random.random()
        if fast_break_roll < p_steal:
            game_state["offensive_state"] = "FAST_BREAK"
            text += " and takes it the other way!"
        else:
            game_state["offensive_state"] = "HCO"
            text += " and waits to set up the half-court offense."
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""
        
        # ✅ FIX: Use stored stealer position from skeleton step (if available)
        # This ensures intermediate steps use the position at the exact moment of the steal
        if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
            stealer_coords = game_state["last_stealer_coords"]
            defender.coords = stealer_coords.copy()
            logging.debug(f"🏀 [STEAL POSITION] Using stored stealer position: x={stealer_coords['x']}, y={stealer_coords['y']}")
        else:
            logging.debug(f"⚠️ [STEAL POSITION] No stored stealer position, using defender.coords: x={getattr(defender, 'coords', {}).get('x', 'N/A')}, y={getattr(defender, 'coords', {}).get('y', 'N/A')}")
        
        # ✅ DEBUG: Log steal flow for HCO steals
        logging.debug(f"🏀 [STEAL FLOW] HCO Steal detected:")
        logging.debug(f"  Stealer: {get_name_safe(defender)} (ID: {stealer_id})")
        logging.debug(f"  Victim: {get_name_safe(ball_handler)} (ID: {victim_id})")
        logging.debug(f"  Fast break chance: {p_steal:.2%}, Roll: {fast_break_roll:.3f}")
        logging.debug(f"  Next offensive_state: {game_state['offensive_state']}")
        logging.debug(f"  last_stealer SET: {get_name_safe(defender)} (ID: {stealer_id})")

        events.append({
            "event_type": "STEAL",
            "stealer_id": stealer_id,
            "victim_id": victim_id,
            "timestamp": game_state.get("time_remaining"),
            "coords": getattr(defender, "coords", None),
        })
    else:
        game_state["offensive_state"] = "HCO"
        if turnover_type == "SHOT_CLOCK":
            text = "Shot Clock Violation"
        else:
            description = random.choice([
                "throws it out of bounds",
                "commits a travel.",
                "commits a double dribble.",
                "travels with the ball.",
                "with an errant pass.",
                "dribbles it off his foot and the ball goes out of bounds."
            ])
            text = f"{victim_name} {description}"
        game_state["last_stealer"] = None

    bh_pos = get_player_position(off_lineup, ball_handler)

    # ✅ SS&S FIX: Set next_play_type when offensive_state is FAST_BREAK
    # This allows game_manager.py to flip possession before the Fast Break turn
    # Matches the pattern used in FCP/HCT steals (lines 2482, 3330)
    next_play_type = None
    if game_state.get("offensive_state") == "FAST_BREAK":
        next_play_type = "FAST_BREAK"
    elif turnover_type == "SHOT_CLOCK":
        next_play_type = "SIDE_INBOUND"
    elif game_state.get("offensive_state") == "HCO":
        next_play_type = "HCO"

    # API: shot clock violation uses result_type "DEAD BALL" + turnover_type "SHOT_CLOCK" for announcement
    result_type_for_api = "DEAD BALL" if turnover_type == "SHOT_CLOCK" else turnover_type
    result = {
        "result_type": result_type_for_api,
        "ball_handler": ball_handler,
        "text": text,
        "time_elapsed": random.randint(3, 8),
        "possession_flips": True,  # Let the turn loop handle the flip
        "offense_team_id": game.offense_team.team_id,  # ✅ SS&S: Add offense_team_id to all results
        "current_turn": "HCO",  # ✅ SS&S: Standalone turnovers occur in HCO context
        "victim_id": victim_id,
        "victim_name": victim_name,
    }
    
    # ✅ SS&S FIX: Add next_play_type to result (only if set)
    if next_play_type:
        result["next_play_type"] = next_play_type
        result["next_turn"] = next_play_type  # ✅ SS&S: Explicit next turn

    # Only actual steals should expose stealer_id. Dead-ball turnovers may have
    # a pressure defender in roles["defender"], but stamping that defender as a
    # stealer makes downstream systems classify the turn as steal-like and skip
    # dead-ball fumble animation.
    if turnover_type == "STEAL" and stealer_id:
        result["stealer_id"] = stealer_id
        result["stealer_name"] = stealer_name
    if turnover_type == "SHOT_CLOCK":
        result["turnover_type"] = "SHOT_CLOCK"
    if events:
        result["events"] = events

    return result


def _check_standard_fouls(calibrated_o_foul, calibrated_d_foul):
    """
    Check for standard fouls (O_FOUL or D_FOUL).
    
    Args:
        calibrated_o_foul: Calibrated offensive foul threshold
        calibrated_d_foul: Calibrated defensive foul threshold
    
    Returns:
        tuple: ("O_FOUL", None) or ("D_FOUL", None) if foul occurs, None otherwise
    """
    foul_roll = random.randint(1, 100)
    # logging.warning(f"🔍 [HCO RESOLUTION] Standard Foul Check:")
    # logging.warning(f"   Roll: {foul_roll} (1-100)")
    # logging.warning(f"   O_FOUL threshold: <= {calibrated_o_foul}")
    # logging.warning(f"   D_FOUL threshold: >= {calibrated_d_foul}")
    if foul_roll <= calibrated_o_foul:
        return ("O_FOUL", None, None)
    elif foul_roll >= calibrated_d_foul:
        # logging.warning(f"   ✅ RESULT: D_FOUL (roll {foul_roll} >= {calibrated_d_foul})")
        # logging.warning("")  # Blank line after standard foul check
        return ("D_FOUL", None, None)
    else:
        # logging.warning(f"   ➡️  No foul ({calibrated_o_foul} < {foul_roll} < {calibrated_d_foul})")
        # logging.warning("")  # Blank line after standard foul check
        return None


def _check_steal_attempt(game, skeleton, calibrated_hard_steal, calibrated_soft_steal, 
                         calibrated_hard_foul, calibrated_soft_foul, steal_attempt_rate):
    """
    Check for steal attempt and resolve it.
    
    Args:
        game: GameManager object
        skeleton: Skeleton dict
        calibrated_hard_steal: Calibrated hard steal threshold
        calibrated_soft_steal: Calibrated soft steal threshold
        calibrated_hard_foul: Calibrated hard foul threshold
        calibrated_soft_foul: Calibrated soft foul threshold
        steal_attempt_rate: Steal attempt rate percentage
    
    Returns:
        tuple: ("STEAL", None), ("D_FOUL", None), or None if no event
    """
    from BackEnd.utils.shared import (
        calculate_ball_handling_score, calculate_defender_pressure_score,
        get_player_position, get_name_safe
    )
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.shared import resolve_steal_attempt
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    steal_roll = random.randint(1, 100)
    
    # Get aggression setting for debug log
    aggression_level = def_team.strategy_calls.get("aggression_call", "normal")
    base_steal_attempt = 20  # STEAL_ATTEMPT constant
    was_adjusted = steal_attempt_rate != base_steal_attempt
    
    # logging.warning(f"🔥 [HCO RESOLUTION] Steal Attempt Check:")
    # logging.warning(f"   Defense team aggression: {aggression_level}")
    # logging.warning(f"   Base STEAL_ATTEMPT: {base_steal_attempt}%")
    if was_adjusted:
        adjustment = steal_attempt_rate - base_steal_attempt
        # logging.warning(f"   ✅ Adjusted by aggression: {base_steal_attempt}% → {steal_attempt_rate}% ({adjustment:+d})")
    # else:
    #     logging.warning(f"   ➡️  No adjustment (aggression: {aggression_level})")
    # logging.warning(f"   Final steal attempt rate: {steal_attempt_rate}%")
    # logging.warning(f"   Roll: {steal_roll} (1-100)")
    if steal_roll < steal_attempt_rate:
        # logging.warning(f"   ✅ Steal attempt occurs ({steal_roll} < {steal_attempt_rate})")
        # Steal attempt occurs - select random step and determine ball handler/defender
        if skeleton and "steps" in skeleton and len(skeleton["steps"]) > 0:
            steps = skeleton["steps"]
            # Exclude step 0 (initial setup)
            available_steps = [i for i in range(1, len(steps)) if i < len(steps)]
            if available_steps:
                selected_step_index = random.choice(available_steps)
                game_state["steal_stop_step_index"] = selected_step_index
                
                # Get ball handler at selected step
                ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=selected_step_index)
                if ball_handler:
                    ball_handler_pos = get_player_position(off_lineup, ball_handler)
                    defense_call = game_state.get("defense_playcall", "man")
                    
                    # Get defender (zone or man defense logic)
                    if is_zone_defense(defense_call):
                        # Zone defense: use zone assignment logic
                        from BackEnd.utils.shared_defense import (
                            _get_23_zone_boundaries, _get_32_zone_boundaries, _get_131_zone_boundaries,
                            assign_all_zone_defenders
                        )
                        from BackEnd.constants import HCO_STRING_SPOTS
                        from BackEnd.utils.shared import get_away_player_coords
                        
                        # Get ball handler's location from step
                        ball_handler_spot = "key"  # Default
                        step = steps[selected_step_index]
                        pos_actions = step.get("pos_actions", {})
                        if ball_handler_pos in pos_actions:
                            action_info = pos_actions[ball_handler_pos]
                            ball_handler_spot = action_info.get("location") or action_info.get("spot") or "key"
                        
                        # Get ball handler coordinates
                        if ball_handler_spot in HCO_STRING_SPOTS:
                            ball_handler_coords = HCO_STRING_SPOTS[ball_handler_spot]
                        else:
                            ball_handler_coords = {"x": 64, "y": 25}  # Default to key
                        
                        # Determine court orientation and flip coordinates if away team is on offense
                        is_away_offense = off_team.team_id == game.away_team.team_id
                        if is_away_offense:
                            ball_handler_coords = get_away_player_coords(ball_handler_coords)
                        
                        # Get zone boundaries based on ball location (applies shifts)
                        zv = defense_zone_shell_variant(defense_call) or "23"
                        if zv == "32":
                            zone_boundaries = _get_32_zone_boundaries(ball_handler_spot, is_away_offense)
                        elif zv == "131":
                            zone_boundaries = _get_131_zone_boundaries(ball_handler_spot, is_away_offense)
                        else:
                            zone_boundaries = _get_23_zone_boundaries(ball_handler_spot, is_away_offense)
                        
                        # Build offensive players list for zone assignment
                        ball_handler_id = getattr(ball_handler, "player_id", None)
                        offensive_players = []
                        for pos, player in off_lineup.items():
                            player_id = getattr(player, "player_id", None)
                            player_coords = getattr(player, "coords", {})
                            # Get player's spot from skeleton if available
                            player_spot = "key"
                            if skeleton and "steps" in skeleton:
                                steps = skeleton.get("steps", [])
                                if steps and selected_step_index < len(steps):
                                    step = steps[selected_step_index]
                                    pos_actions = step.get("pos_actions", {})
                                    if pos in pos_actions:
                                        action_info = pos_actions[pos]
                                        player_spot = action_info.get("location") or action_info.get("spot") or "key"
                            
                            # Convert spot to coordinates
                            spot_coords = HCO_STRING_SPOTS.get(player_spot, {"x": 50, "y": 25})
                            if is_away_offense:
                                spot_coords = get_away_player_coords(spot_coords)
                            
                            # Use player's coords if available, otherwise use spot coords
                            final_coords = player_coords if player_coords.get("x") and player_coords.get("y") else spot_coords
                            
                            offensive_players.append({
                                "player_id": player_id,
                                "coords": final_coords,
                                "spot": player_spot,
                                "is_ball_handler": (player_id == ball_handler_id)
                            })
                        
                        # Get aggression level
                        aggression_level = slow_it_down_defense_setting(
                            game.game_state, def_team, "aggression",
                            def_team.strategy_settings.get("aggression", 2),
                        )
                        aggression_map = {0: "passive", 1: "passive", 2: "normal", 3: "aggressive", 4: "aggressive"}
                        aggression = aggression_map.get(aggression_level, "normal")
                        
                        # Call zone assignment logic to get actual defender assignments
                        _, defender_to_offensive_player = assign_all_zone_defenders(
                            zone_boundaries,
                            offensive_players,
                            ball_handler_coords,
                            ball_handler_spot,
                            aggression,
                            is_away_offense
                        )
                        
                        # Find which defender(s) are actually guarding the ball handler
                        defender = None
                        for def_pos, guarded_player_id in defender_to_offensive_player.items():
                            if guarded_player_id == ball_handler_id:
                                defender = def_lineup.get(def_pos)
                                break
                        
                        if not defender:
                            # Fallback: use ball handler's position
                            defender = def_lineup.get(ball_handler_pos)
                    else:
                        # Man defense: use matchups for the defending team (user vs computer)
                        from BackEnd.utils.man_defense_matchups import get_defender_position_for_man_defense
                        defending_team_is_user = getattr(game.defense_team, "is_user_team", False)
                        defender_pos = get_defender_position_for_man_defense(
                            ball_handler_pos, game.game_state, defending_team_is_user=defending_team_is_user
                        )
                        defender = def_lineup.get(defender_pos)
                    
                    if defender:
                        # Calculate offense and defense values
                        bh_score = calculate_ball_handling_score(ball_handler)
                        pressure = calculate_defender_pressure_score(defender, defense_call)
                        
                        # Resolve steal attempt
                        delta = bh_score - pressure
                        # logging.warning(f"      Ball handler: {get_name_safe(ball_handler)} (pos: {ball_handler_pos})")
                        # logging.warning(f"      Defender: {get_name_safe(defender)}")
                        # logging.warning(f"      BH score: {bh_score}")
                        # logging.warning(f"      Defender pressure: {pressure}")
                        # logging.warning(f"      Delta (BH - pressure): {delta}")
                        # logging.warning(f"      Thresholds: HARD_STEAL={calibrated_hard_steal}, SOFT_STEAL={calibrated_soft_steal}, SOFT_FOUL={calibrated_soft_foul}, HARD_FOUL={calibrated_hard_foul}")
                        
                        steal_result = resolve_steal_attempt(
                            bh_score, pressure,
                            calibrated_soft_steal, calibrated_hard_steal,
                            calibrated_soft_foul, calibrated_hard_foul
                        )
                        
                        # logging.warning(f"      ✅ Steal attempt result: {steal_result}")
                        if steal_result == "STEAL":
                            return ("STEAL", None, None)
                        elif steal_result == "D_FOUL":
                            return ("D_FOUL", None, None)
                        # If "NO_EVENT", return None
                        # logging.warning(f"      ➡️  No event ({steal_result})")
                        pass
    else:
        # logging.warning(f"   ➡️  No steal attempt ({steal_roll} >= {steal_attempt_rate})")
        pass
    
    return None


def _check_dead_ball_turnover(game, skeleton, calibrated_dead_ball_to):
    """
    Check for dead ball turnover.
    
    Args:
        game: GameManager object
        skeleton: Skeleton dict
        calibrated_dead_ball_to: Calibrated dead ball turnover threshold
    
    Returns:
        tuple: ("DEAD_BALL_TURNOVER", None) if turnover occurs, None otherwise
    """
    from BackEnd.utils.shared import (
        calculate_ball_handling_score, calculate_defender_pressure_score,
        get_player_position, get_name_safe
    )
    from BackEnd.utils.defense_utils import is_zone_defense
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    turnover_roll = random.randint(1, 100)
    # logging.warning(f"🔍 [HCO RESOLUTION] Dead Ball Turnover Check:")
    # logging.warning(f"   DEAD_BALL_TURNOVER threshold: < {calibrated_dead_ball_to}")
    # logging.warning(f"   Roll: {turnover_roll} (1-100)")
    if turnover_roll < calibrated_dead_ball_to:
        # logging.warning(f"   ✅ Turnover check occurs ({turnover_roll} < {calibrated_dead_ball_to})")
        # Turnover check occurs - select random step (may differ from Step 4)
        if skeleton and "steps" in skeleton and len(skeleton["steps"]) > 0:
            steps = skeleton["steps"]
            available_steps = [i for i in range(1, len(steps)) if i < len(steps)]
            if available_steps:
                selected_step_index = random.choice(available_steps)
                game_state["turnover_stop_step_index"] = selected_step_index
                
                # Get ball handler at selected step
                ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=selected_step_index)
                if ball_handler:
                    ball_handler_pos = get_player_position(off_lineup, ball_handler)
                    defense_call = game_state.get("defense_playcall", "man")
                    
                    # Get defender
                    if is_zone_defense(defense_call):
                        # Zone defense: use zone assignment logic
                        from BackEnd.utils.shared_defense import (
                            _get_23_zone_boundaries, _get_32_zone_boundaries, _get_131_zone_boundaries,
                            assign_all_zone_defenders
                        )
                        from BackEnd.constants import HCO_STRING_SPOTS
                        from BackEnd.utils.shared import get_away_player_coords
                        
                        # Get ball handler's location from step
                        ball_handler_spot = "key"  # Default
                        step = steps[selected_step_index]
                        pos_actions = step.get("pos_actions", {})
                        if ball_handler_pos in pos_actions:
                            action_info = pos_actions[ball_handler_pos]
                            ball_handler_spot = action_info.get("location") or action_info.get("spot") or "key"
                        
                        # Get ball handler coordinates
                        if ball_handler_spot in HCO_STRING_SPOTS:
                            ball_handler_coords = HCO_STRING_SPOTS[ball_handler_spot]
                        else:
                            ball_handler_coords = {"x": 64, "y": 25}  # Default to key
                        
                        # Determine court orientation and flip coordinates if away team is on offense
                        is_away_offense = off_team.team_id == game.away_team.team_id
                        if is_away_offense:
                            ball_handler_coords = get_away_player_coords(ball_handler_coords)
                        
                        # Get zone boundaries based on ball location (applies shifts)
                        zv = defense_zone_shell_variant(defense_call) or "23"
                        if zv == "32":
                            zone_boundaries = _get_32_zone_boundaries(ball_handler_spot, is_away_offense)
                        elif zv == "131":
                            zone_boundaries = _get_131_zone_boundaries(ball_handler_spot, is_away_offense)
                        else:
                            zone_boundaries = _get_23_zone_boundaries(ball_handler_spot, is_away_offense)
                        
                        # Build offensive players list for zone assignment
                        ball_handler_id = getattr(ball_handler, "player_id", None)
                        offensive_players = []
                        for pos, player in off_lineup.items():
                            player_id = getattr(player, "player_id", None)
                            player_coords = getattr(player, "coords", {})
                            # Get player's spot from skeleton if available
                            player_spot = "key"
                            if skeleton and "steps" in skeleton:
                                steps = skeleton.get("steps", [])
                                if steps and selected_step_index < len(steps):
                                    step = steps[selected_step_index]
                                    pos_actions = step.get("pos_actions", {})
                                    if pos in pos_actions:
                                        action_info = pos_actions[pos]
                                        player_spot = action_info.get("location") or action_info.get("spot") or "key"
                            
                            # Convert spot to coordinates
                            spot_coords = HCO_STRING_SPOTS.get(player_spot, {"x": 50, "y": 25})
                            if is_away_offense:
                                spot_coords = get_away_player_coords(spot_coords)
                            
                            # Use player's coords if available, otherwise use spot coords
                            final_coords = player_coords if player_coords.get("x") and player_coords.get("y") else spot_coords
                            
                            offensive_players.append({
                                "player_id": player_id,
                                "coords": final_coords,
                                "spot": player_spot,
                                "is_ball_handler": (player_id == ball_handler_id)
                            })
                        
                        # Get aggression level
                        aggression_level = slow_it_down_defense_setting(
                            game.game_state, def_team, "aggression",
                            def_team.strategy_settings.get("aggression", 2),
                        )
                        aggression_map = {0: "passive", 1: "passive", 2: "normal", 3: "aggressive", 4: "aggressive"}
                        aggression = aggression_map.get(aggression_level, "normal")
                        
                        # Call zone assignment logic to get actual defender assignments
                        _, defender_to_offensive_player = assign_all_zone_defenders(
                            zone_boundaries,
                            offensive_players,
                            ball_handler_coords,
                            ball_handler_spot,
                            aggression,
                            is_away_offense
                        )
                        
                        # Find which defender(s) are actually guarding the ball handler
                        defender = None
                        for def_pos, guarded_player_id in defender_to_offensive_player.items():
                            if guarded_player_id == ball_handler_id:
                                defender = def_lineup.get(def_pos)
                                break
                        
                        if not defender:
                            # Fallback: use ball handler's position
                            defender = def_lineup.get(ball_handler_pos)
                    else:
                        # Man defense: use matchups for the defending team (user vs computer)
                        from BackEnd.utils.man_defense_matchups import get_defender_position_for_man_defense
                        defending_team_is_user = getattr(game.defense_team, "is_user_team", False)
                        defender_pos = get_defender_position_for_man_defense(
                            ball_handler_pos, game.game_state, defending_team_is_user=defending_team_is_user
                        )
                        defender = def_lineup.get(defender_pos)
                    
                    if defender:
                        # Calculate scores
                        bh_score = calculate_ball_handling_score(ball_handler)
                        defender_score = calculate_defender_pressure_score(defender, defense_call)
                        
                        # logging.warning(f"      Ball handler: {get_name_safe(ball_handler)} (pos: {ball_handler_pos})")
                        # logging.warning(f"      Defender: {get_name_safe(defender)}")
                        # logging.warning(f"      BH score: {bh_score}")
                        # logging.warning(f"      Defender score: {defender_score}")
                        # logging.warning(f"      Comparison: {defender_score} > {bh_score} = {defender_score > bh_score}")
                        
                        if defender_score > bh_score:
                            # logging.warning(f"      ✅ RESULT: DEAD_BALL_TURNOVER (defender {defender_score} > ball handler {bh_score})")
                            # logging.warning("")  # Blank line after dead ball turnover check
                            return ("DEAD_BALL_TURNOVER", None, None)
                        # Else continue
                        # logging.warning(f"      ➡️  No turnover (defender {defender_score} <= ball handler {bh_score})")
    else:
        # logging.warning(f"   ➡️  No turnover check ({turnover_roll} >= {calibrated_dead_ball_to})")
        pass
    # logging.warning("")  # Blank line after dead ball turnover check
    
    return None


def resolve_hco_outcome(game, skeleton):
    """
    Resolve HCO turn outcome using the new Resolution System.
    
    Processes outcomes in the following order:
    1. Get team attributes and settings
    2. Calibrate universal constants
    3-5. Check for events in RANDOMIZED order:
        - Standard fouls (O_FOUL, D_FOUL)
        - Steal attempt (with resolution)
        - Dead ball turnover
    6. Shot attempt (with skeleton variant selection) - if no event occurred
    
    Args:
        game: GameManager object
        skeleton: Skeleton dict (needed for step selection and variant determination)
    
    Returns:
        tuple: (result, variant_result, execution_score)
            - result: "SHOT", "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", or "STEAL"
            - variant_result: For SHOT results, the skeleton variant ("successful", "mid_play_change", "contested", "broken")
                          For non-SHOT results, None
            - execution_score: For SHOT results, execution score (0-100) calculated from result
                          For non-SHOT results, None
    """
    import random
    from BackEnd.constants import (
        STANDARD_D_FOUL, STANDARD_O_FOUL, HARD_STEAL, SOFT_STEAL,
        HARD_FOUL, SOFT_FOUL, SOFT_PROB, STEAL_ATTEMPT, DEAD_BALL_TURNOVER
    )
    from BackEnd.utils.shared import (
        calculate_ball_handling_score, calculate_defender_pressure_score,
        get_player_position, unpack_game_context, get_name_safe
    )
    # get_ball_handler_from_skeleton is defined in this file (phase_resolution.py)
    from BackEnd.utils.defense_utils import is_zone_defense
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    # Step 1: Get Team Attributes and Settings
    off_attrs = off_team.team_attributes
    def_attrs = def_team.team_attributes
    
    offensive_efficiency = off_attrs.get("offensive_efficiency", 0)
    discipline = off_attrs.get("discipline", 0)
    fight_off = off_attrs.get("fight", 0)
    
    defensive_efficiency = def_attrs.get("defensive_efficiency", 0)
    fight_def = def_attrs.get("fight", 0)
    
    # Get aggression setting from strategy_calls (strings: "passive", "normal", "aggressive")
    aggression_level = def_team.strategy_calls.get("aggression_call", "normal")
    
    # 🔍 DEBUG: Step 1 - Team Attributes and Settings
    logging.debug(f"🔍 [HCO RESOLUTION] Step 1 - Team Attributes and Settings:")
    logging.debug(f"   Offense: efficiency={offensive_efficiency}, discipline={discipline}, fight={fight_off}")
    logging.debug(f"   Defense: efficiency={defensive_efficiency}, fight={fight_def}, aggression_level={aggression_level}")
    logging.debug("")  # Blank line after Step 1
    
    # Step 2: Calibrate Universal Constants
    # Standard D Foul calibration
    calibrated_d_foul = STANDARD_D_FOUL + int(fight_def * 0.4)
    calibrated_d_foul = min(98, calibrated_d_foul)  # Max 98
    
    # Standard O Foul calibration
    calibrated_o_foul = STANDARD_O_FOUL - fight_off
    calibrated_o_foul = max(2, calibrated_o_foul)  # Min 2
    
    # Steal thresholds calibration
    calibrated_hard_steal = HARD_STEAL - discipline
    calibrated_soft_steal = SOFT_STEAL - discipline
    
    # Foul thresholds calibration (on steal attempts)
    calibrated_hard_foul = HARD_FOUL - int(fight_def * 0.6)
    calibrated_soft_foul = SOFT_FOUL - int(fight_def * 0.6)
    
    # Dead Ball Turnover calibration
    calibrated_dead_ball_to = DEAD_BALL_TURNOVER - int(0.5 * discipline)
    calibrated_dead_ball_to = max(2, calibrated_dead_ball_to)  # Min 2
    
    # 🔥 DEBUG: Step 2 - Calibrated Constants
    logging.debug(f"🔥 [HCO RESOLUTION] Step 2 - Calibrated Constants:")
    logging.debug(f"   STANDARD_D_FOUL: {STANDARD_D_FOUL} + int({fight_def} * 0.4) = {calibrated_d_foul} (max 98)")
    logging.debug(f"   STANDARD_O_FOUL: {STANDARD_O_FOUL} - {fight_off} = {calibrated_o_foul} (min 2)")
    logging.debug(f"   HARD_STEAL: {HARD_STEAL} - {discipline} = {calibrated_hard_steal}")
    logging.debug(f"   SOFT_STEAL: {SOFT_STEAL} - {discipline} = {calibrated_soft_steal}")
    logging.debug(f"   HARD_FOUL: {HARD_FOUL} - int({fight_def} * 0.6) = {calibrated_hard_foul}")
    logging.debug(f"   SOFT_FOUL: {SOFT_FOUL} - int({fight_def} * 0.6) = {calibrated_soft_foul}")
    logging.debug(f"   DEAD_BALL_TURNOVER: {DEAD_BALL_TURNOVER} - int(0.5 * {discipline}) = {calibrated_dead_ball_to} (min 2)")
    logging.debug("")  # Blank line after Step 2
    
    # Calculate steal attempt rate (needed for steal check)
    # ✅ FIX: Use strategy_calls (strings) not strategy_settings (integers)
    steal_attempt_rate = STEAL_ATTEMPT
    original_rate = steal_attempt_rate
    if aggression_level == "aggressive":
        steal_attempt_rate += 10
    elif aggression_level == "passive":
        steal_attempt_rate -= 10
    # "normal" or any other value: no change
    steal_attempt_rate = max(10, min(30, steal_attempt_rate))  # Clamp between 10-30
    
    # 🔍 DEBUG: Log aggression setting and threshold adjustment
    if steal_attempt_rate != original_rate:
        logging.debug(f"🔍 [HCO RESOLUTION] Steal Attempt Rate Adjustment:")
        logging.debug(f"   Defense team aggression: {aggression_level}")
        logging.debug(f"   Base STEAL_ATTEMPT: {original_rate}%")
        logging.debug(f"   Adjusted rate: {steal_attempt_rate}% ({'+10' if aggression_level == 'aggressive' else '-10'} from aggression)")
    else:
        logging.debug(f"🔍 [HCO RESOLUTION] Steal Attempt Rate:")
        logging.debug(f"   Defense team aggression: {aggression_level}")
        logging.debug(f"   Base STEAL_ATTEMPT: {steal_attempt_rate}% (no adjustment)")
    
    # ✅ EXECUTION SCORE CALCULATION: Calculate once for all outcomes
    # Calculate play effectiveness scores (same calculation used for all HCO results)
    o_random = random.randint(1, 100)
    d_random = random.randint(1, 100)
    o_score = offensive_efficiency + o_random
    d_score = defensive_efficiency + d_random
    
    result_value = o_score - d_score
    
    # Cap result at -100 to +100 for execution score calculation
    capped_result = result_value
    if capped_result > 100:
        capped_result = 100
    elif capped_result < -100:
        capped_result = -100
    
    # Scale from -100 to +100 range to 0-100 Execution Score
    # Formula: execution_score = (capped_result + 100) / 2
    execution_score = (capped_result + 100) / 2
    
    # Store execution_score in game_state for later storage in scouting data
    game_state["execution_score"] = execution_score
    # ✅ STORE RAW RESULT VALUE: Store capped_result (-100 to +100) for lean meter display
    game_state["lean_result_value"] = capped_result
    
    logging.debug(f"📊 [HCO RESOLUTION] Execution Score Calculation (for all outcomes):")
    logging.debug(f"   Offense effectiveness: {offensive_efficiency} + {o_random} (random) = {o_score}")
    logging.debug(f"   Defense effectiveness: {defensive_efficiency} + {d_random} (random) = {d_score}")
    logging.debug(f"   Result (o_score - d_score): {o_score} - {d_score} = {result_value}")
    logging.debug(f"   Execution Score: {result_value} → {capped_result} (capped) → {execution_score:.1f}% (scaled 0-100)")
    logging.debug(f"   Lean Meter Value: {capped_result} (raw -100 to +100)")
    logging.debug("")  # Blank line after execution score calculation
    
    # Steps 3-5: Randomize order of event checks
    # Create list of check functions with their parameters
    check_functions = [
        ("Standard Fouls", lambda: _check_standard_fouls(calibrated_o_foul, calibrated_d_foul)),
        ("Steal Attempt", lambda: _check_steal_attempt(game, skeleton, calibrated_hard_steal, calibrated_soft_steal, 
                                                         calibrated_hard_foul, calibrated_soft_foul, steal_attempt_rate)),
        ("Dead Ball Turnover", lambda: _check_dead_ball_turnover(game, skeleton, calibrated_dead_ball_to))
    ]
    
    # Randomize the order
    random.shuffle(check_functions)

    logging.debug(f"🔍 [HCO RESOLUTION] Randomized check order: {[name for name, _ in check_functions]}")
    logging.debug("")  # Blank line after randomized order

    # Dynamic HCO migration: motion turns resolve foul/steal/turnover PER STEP (the attribute-
    # driven moment walk in resolve_half_court_offense_logic), so skip these up-front percentile
    # tables for motion when the flag is on. Set plays do the same under their OWN flag (overlay
    # model — variant selection STAYS, but events come from the per-step moment). The flag-off
    # path keeps the up-front tables. See Z-Completed/Dynamic_HCO_Motion_Brief.md / Dynamic_HCO_SP_Brief.md.
    _opt = game_state.get("offense_play_type", "")
    skip_upfront_events = (
        (_opt == "motion" and _dynamic_hco_motion_enabled())
        or (_opt in ("set", "set_play") and _dynamic_hco_setplay_enabled())
    )

    # Execute checks in randomized order
    for check_name, check_func in ([] if skip_upfront_events else check_functions):
        result = check_func()
        if result is not None:
            # Event occurred, return immediately with execution_score
            logging.debug(f"🔍 [HCO RESOLUTION] {check_name} returned result: {result[0]}")
            logging.debug(f"   📊 Execution Score: {execution_score:.1f}% (calculated for all outcomes)")
            logging.debug("")  # Blank line after event result
            # For non-SHOT results, return execution_score but None for variant_result
            if len(result) == 2:
                return (result[0], result[1], execution_score)
            elif len(result) == 3:
                # If result already has 3 elements, replace the third with execution_score
                return (result[0], result[1], execution_score)
            else:
                return (result[0], None, execution_score)
    
    # No event occurred in Steps 3-5, continue to Step 6
    logging.debug("")  # Blank line after Steps 3-5 (no event)
    
    # Step 6: Shot Attempt
    # Execution score already calculated above (used for all outcomes)
    # Use the same result_value for variant selection
    logging.debug(f"🔥 [HCO RESOLUTION] Step 6 - Shot Attempt:")
    logging.debug(f"   Using execution score already calculated: {execution_score:.1f}%")
    
    # Select skeleton variant based on result_value (using original uncapped result)
    if result_value > 50:
        variant_result = "successful"
        logging.debug(f"   ✅ Variant: {variant_result} (result {result_value} > 50)")
    elif result_value > 0:
        variant_result = "mid_play_change"
        logging.debug(f"   ✅ Variant: {variant_result} (0 < result {result_value} <= 50)")
    elif result_value > -50:
        variant_result = "contested"
        logging.debug(f"   ✅ Variant: {variant_result} (-50 < result {result_value} <= 0)")
    else:
        variant_result = "broken"
        logging.debug(f"   ✅ Variant: {variant_result} (result {result_value} <= -50)")
    
    logging.debug(f"🔍 [HCO RESOLUTION] Final Result: SHOT with variant '{variant_result}', execution_score={execution_score:.1f}%")
    return ("SHOT", variant_result, execution_score)


def generate_logic(off_call, def_call, off_team, def_team, off_lineup, def_lineup, game=None):
    """
    Calculate lean score based on offensive/defensive matchup.
    
    This function evaluates the effectiveness of the offensive play vs defensive setup
    by considering team attributes, player attributes, and tactical matchups.
    
    Args:
        off_call (str): Offensive playcall (e.g., "Motion - Inside Focus")
        def_call (str): Defensive playcall (e.g., "Man Defense")
        off_team: Offensive team object with attributes
        def_team: Defensive team object with attributes
        off_lineup (dict): Offensive lineup {pos: player}
        def_lineup (dict): Defensive lineup {pos: player}
        game: Game context object (optional, needed to retrieve skeleton)
    
    Returns:
        float: Lean score from -1 to 1
            >= 0.5: successful - play works perfectly
            0 to 0.49: mid_play_change - play adjusts mid-execution
            -0.01 to -0.5: contested - defense engaged, tougher execution
            < -0.5: broken - defense disrupts, offense forced to react
    
    TODO: Implement full logic based on:
        - Team attributes (team speed, execution, discipline, etc.)
        - Player attributes (relevant to play type/focus)
        - Defensive matchup effectiveness
        - Game situation (score, time, quarter)
    """
    import random
    from BackEnd.constants import ACTIONS
    
    result = random.choices(
        ["SHOT", "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL"],
        weights=[6, 1, 1, 1, 1],
        k=1
    )[0]
    
    # Analyze skeleton to count screen attempts
    screen_attempts_by_pos = {}
    if game:
        try:
            # Get the successful variant skeleton to analyze screen usage
            skeleton = get_hco_skeleton(None, game, lean_score=1.0)
            if skeleton and "steps" in skeleton:
                steps = skeleton.get("steps", [])
                for step in steps:
                    # Check pos_actions for SCREEN actions
                    pos_actions = step.get("pos_actions", {})
                    for pos, action_info in pos_actions.items():
                        action = action_info.get("action", "")
                        if action == ACTIONS["SCREEN"] or action == "screen":
                            screen_attempts_by_pos[pos] = screen_attempts_by_pos.get(pos, 0) + 1
                    
                    # Check events for screen events
                    events = step.get("events", [])
                    for event in events:
                        if event.get("type") == "screen":
                            screener_pos = event.get("by")
                            if screener_pos:
                                screen_attempts_by_pos[screener_pos] = screen_attempts_by_pos.get(screener_pos, 0) + 1
                
                # Record screen stats for each player
                if screen_attempts_by_pos:
                    for pos, count in sorted(screen_attempts_by_pos.items()):
                        player = off_lineup.get(pos)
                        if player:
                            # Increment SCR_A for each screen attempt
                            for _ in range(count):
                                player.record_stat("SCR_A")
                                
                                # 50% chance to increment SCR_S for each attempt
                                success = random.randint(1, 2)
                                if success == 1:
                                    player.record_stat("SCR_S")
        except Exception as e:
            pass  # Silently handle skeleton analysis errors
    
    # PLACEHOLDER: Return random lean score for now
    # This allows the system to work while full logic is implemented
    lean_score = random.uniform(-1, 1)
    
    return result, lean_score


def _store_lean_score_internal(lean_score, game, offense_team, defense_team):
    """
    Internal function to store lean_score in offense and defense scouting data.
    
    Args:
        lean_score (float): Lean score from -1.0 to 1.0
        game: Game context object
        offense_team: Offensive team object
        defense_team: Defensive team object
    """
    try:
        # Get play type and focus from game_state
        offense_play_type = game.game_state.get("offense_play_type", "").lower()
        offense_focus = game.game_state.get("offense_play_focus", "")
        defense_playcall = game.game_state.get("defense_playcall", "")
        
        # Normalize play type
        if offense_play_type == "set_play":
            offense_play_type = "set"
        
        # Store in offense scouting data
        if offense_play_type in ["motion", "set"] and offense_focus in ["inside", "attack", "outside"]:
            play_type_label = "Motion" if offense_play_type == "motion" else "Set"
            pc = offense_team.scouting_data["offense"]["Playcalls"]
            
            vs_key = offense_vs_key_from_defense_input(defense_playcall)
            
            # Store lean_score in overall and focus buckets
            if "lean_scores" not in pc[play_type_label]["overall"]:
                pc[play_type_label]["overall"]["lean_scores"] = []
            if "lean_scores" not in pc[play_type_label][offense_focus]:
                pc[play_type_label][offense_focus]["lean_scores"] = []
            
            pc[play_type_label]["overall"]["lean_scores"].append(lean_score)
            pc[play_type_label][offense_focus]["lean_scores"].append(lean_score)
            
            # Store lean_score in vs_* buckets
            if vs_key and vs_key in pc[play_type_label]["overall"]:
                if "lean_scores" not in pc[play_type_label]["overall"][vs_key]:
                    pc[play_type_label]["overall"][vs_key]["lean_scores"] = []
                pc[play_type_label]["overall"][vs_key]["lean_scores"].append(lean_score)
            
            if vs_key and vs_key in pc[play_type_label][offense_focus]:
                if "lean_scores" not in pc[play_type_label][offense_focus][vs_key]:
                    pc[play_type_label][offense_focus][vs_key]["lean_scores"] = []
                pc[play_type_label][offense_focus][vs_key]["lean_scores"].append(lean_score)
            
            # Store in vs_zone aggregate if zone defense
            from BackEnd.utils.defense_utils import is_zone_defense
            if is_zone_defense(defense_playcall) and "vs_zone" in pc[play_type_label]["overall"]:
                if "lean_scores" not in pc[play_type_label]["overall"]["vs_zone"]:
                    pc[play_type_label]["overall"]["vs_zone"]["lean_scores"] = []
                if "lean_scores" not in pc[play_type_label][offense_focus]["vs_zone"]:
                    pc[play_type_label][offense_focus]["vs_zone"]["lean_scores"] = []
                pc[play_type_label]["overall"]["vs_zone"]["lean_scores"].append(lean_score)
                pc[play_type_label][offense_focus]["vs_zone"]["lean_scores"].append(lean_score)
            
            # Store in Cumulative
            if "lean_scores" not in pc["Cumulative"][offense_focus]:
                pc["Cumulative"][offense_focus]["lean_scores"] = []
            pc["Cumulative"][offense_focus]["lean_scores"].append(lean_score)
        
        # Store lean_score in defense scouting data
        def_row = defense_scouting_row_key(defense_playcall)
        if def_row in defense_team.scouting_data["defense"]:
            def_data = defense_team.scouting_data["defense"][def_row]
            game_stats = def_data.get("game_stats", {})
            
            # Store lean_score in top-level game_stats
            if "lean_scores" not in game_stats:
                game_stats["lean_scores"] = []
            game_stats["lean_scores"].append(lean_score)
            
            # Store lean_score in vs_* buckets
            if offense_play_type == "motion":
                if "lean_scores" not in game_stats.get("vs_motion", {}):
                    game_stats.setdefault("vs_motion", {})["lean_scores"] = []
                game_stats["vs_motion"]["lean_scores"].append(lean_score)
            elif offense_play_type == "set":
                if "lean_scores" not in game_stats.get("vs_set", {}):
                    game_stats.setdefault("vs_set", {})["lean_scores"] = []
                game_stats["vs_set"]["lean_scores"].append(lean_score)
            
            if offense_focus in ["inside", "attack", "outside"]:
                vs_focus_key = f"vs_{offense_focus}"
                if "lean_scores" not in game_stats.get(vs_focus_key, {}):
                    game_stats.setdefault(vs_focus_key, {})["lean_scores"] = []
                game_stats[vs_focus_key]["lean_scores"].append(lean_score)
                
                # Store in combination buckets
                if offense_play_type == "motion":
                    combo_key = f"vs_motion_{offense_focus}"
                    if "lean_scores" not in game_stats.get(combo_key, {}):
                        game_stats.setdefault(combo_key, {})["lean_scores"] = []
                    game_stats[combo_key]["lean_scores"].append(lean_score)
                elif offense_play_type == "set":
                    combo_key = f"vs_set_{offense_focus}"
                    if "lean_scores" not in game_stats.get(combo_key, {}):
                        game_stats.setdefault(combo_key, {})["lean_scores"] = []
                    game_stats[combo_key]["lean_scores"].append(lean_score)
    except Exception as e:
        # Silently handle errors to avoid disrupting gameplay
        pass

def _store_execution_score(execution_score, game, offense_team, defense_team):
    """
    Store execution_score in offense and defense scouting data as lean_scores.
    
    Converts execution_score (0-100) to lean_score format (-1.0 to 1.0) for storage.
    Formula: lean_score = (execution_score - 50) / 50
    
    Args:
        execution_score (float): Execution score from 0.0 to 100.0
        game: Game context object
        offense_team: Offensive team object
        defense_team: Defensive team object
    """
    # Convert execution_score (0-100) to lean_score (-1.0 to 1.0) for storage
    # Formula: lean_score = (execution_score - 50) / 50
    # This maps: 0 → -1.0, 50 → 0.0, 100 → 1.0
    lean_score = (execution_score - 50) / 50
    _store_lean_score_internal(lean_score, game, offense_team, defense_team)


# ✅ ALIAS: Keep _store_lean_score for backward compatibility (accepts execution_score or lean_score)
def _store_lean_score(score, game, offense_team, defense_team):
    """
    Store execution score or lean score in scouting data.
    
    If score is 0-100, treats it as execution_score and converts to lean_score.
    If score is -1.0 to 1.0, treats it as lean_score directly.
    
    Args:
        score (float): Execution score (0-100) or lean score (-1.0 to 1.0)
        game: Game context object
        offense_team: Offensive team object
        defense_team: Defensive team object
    """
    # If score is in execution_score range (0-100), convert to lean_score
    if 0 <= score <= 100:
        lean_score = (score - 50) / 50
    else:
        # Assume it's already a lean_score
        lean_score = score
    
    _store_lean_score_internal(lean_score, game, offense_team, defense_team)


def apply_balancing_system(game, game_state, off_team, def_team):
    """
    Apply balancing system to prevent games from getting too out of hand.
    
    If a team is leading or trailing by the adjusted threshold amount or more,
    temporarily override shot_threshold for that HCO turn:
    - Trailing team: shot_threshold = BALANCING_TRAILING (easier shots)
    - Leading team: shot_threshold = BALANCING_LEADING (harder shots)
    
    Args:
        game: GameManager object
        game_state: Game state dict
        off_team: Offensive team object
        def_team: Defensive team object
    
    Returns:
        None (modifies game_state with balancing_shot_threshold_override if applicable)
    """
    from BackEnd.constants.shot_threshold_scale import BALANCING_LEADING, BALANCING_TRAILING

    # Get current quarter
    quarter = game_state.get("quarter", 1)
    
    # Base thresholds by quarter - separate for trailing and leading teams
    trailing_thresholds = {
        1: 6,
        2: 6,
        3: 8,
        4: 10,
    }

    leading_thresholds = {
        1: 6,
        2: 6,
        3: 8,
        4: 10,
    }
    
    # Get team attributes
    off_attrs = off_team.team_attributes
    fight = off_attrs.get("fight", 0)
    discipline = off_attrs.get("discipline", 0)
    
    # Get current scores from game.score dict
    offense_score = game.score.get(off_team.name, 0)
    defense_score = game.score.get(def_team.name, 0)
    score_diff = offense_score - defense_score
    
    # Determine if offense is leading or trailing
    is_trailing = score_diff < 0
    is_leading = score_diff > 0
    abs_score_diff = abs(score_diff)
    
    # Calculate adjusted threshold based on whether trailing or leading
    if is_trailing:
        # Trailing: use trailing thresholds, subtract fight from threshold
        base_threshold = trailing_thresholds.get(quarter, 10)  # Default to Q4 for OT
        adjusted_threshold = base_threshold - fight
    elif is_leading:
        # Leading: use leading thresholds, add discipline to threshold
        base_threshold = leading_thresholds.get(quarter, 10)  # Default to Q4 for OT
        adjusted_threshold = base_threshold + discipline
    else:
        # Tied game, no balancing needed
        return
    
    # Clamp minimum threshold to 1
    adjusted_threshold = max(1, adjusted_threshold)
    
    # Check if threshold is met
    if abs_score_diff >= adjusted_threshold:
        # Apply balancing override
        if is_trailing:
            # Trailing team gets easier shots
            game_state["balancing_shot_threshold_override"] = BALANCING_TRAILING
            # logging.warning(f"⚖️ [BALANCING] Q{quarter}: {off_team.name} trailing by {abs_score_diff} (threshold: {adjusted_threshold}, fight: {fight}) → shot_threshold = {BALANCING_TRAILING}")
        else:  # is_leading
            # Leading team gets harder shots
            game_state["balancing_shot_threshold_override"] = BALANCING_LEADING
            # logging.warning(f"⚖️ [BALANCING] Q{quarter}: {off_team.name} leading by {abs_score_diff} (threshold: {adjusted_threshold}, discipline: {discipline}) → shot_threshold = {BALANCING_LEADING}")
    else:
        # Clear any previous override if threshold not met
        game_state.pop("balancing_shot_threshold_override", None)


def apply_stopper_system_to_skeleton(skeleton, result, game_state):
    """
    Apply stopper system to skeleton: truncate and add stopper step for non-shot results.
    
    Args:
        skeleton: Skeleton dict with "steps" array
        result: Result type ("O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", or "HCO")
        game_state: Game state dict (for storing steal position data)
    
    Returns:
        Modified skeleton (truncated + stopper step, or full skeleton if result == "HCO")
    """
    import copy
    
    # If result is HCO, return full skeleton (no truncation)
    if result == "HCO":
        return skeleton
    
    # If result is SHOT, return full skeleton (no truncation)
    if result == "SHOT":
        return skeleton
    
    # Deep copy skeleton to avoid mutating original
    skeleton = copy.deepcopy(skeleton)
    
    if not skeleton or "steps" not in skeleton:
        logging.warning(f"⚠️ [STOPPER] Cannot apply stopper - skeleton or steps missing (result: {result})")
        return skeleton
    
    steps = skeleton.get("steps", [])
    if len(steps) <= 1:
        logging.warning(f"⚠️ [STOPPER] Cannot apply stopper - skeleton has {len(steps)} steps (need at least 2)")
        return skeleton
    
    # Moment-walk pin: the per-step HCO moment (foul/steal/turnover) fired at a KNOWN step and stashed
    # it here. Pin the stopper there so the outcome lands where it happened instead of a random
    # blast-radius step (the "ball snap-back on a non-shot outcome" teleport). Consumed once (pop) so
    # it can never leak into a later turn's stopper.
    _moment_pin = game_state.pop("_hco_moment_stop_index", None)
    if not (isinstance(_moment_pin, int) and 1 <= _moment_pin <= len(steps) - 1):
        _moment_pin = None

    # Determine which step to stop at based on result type
    if result == "SHOT_CLOCK_VIOLATION":
        # Use precomputed step where shot clock hits 0 (set by HCO shot-clock check)
        stop_step_index = game_state.get("shot_clock_violation_step_index")
        if stop_step_index is None or stop_step_index < 0 or stop_step_index >= len(steps) - 1:
            stop_step_index = max(1, len(steps) - 2)
    elif result in ["O_FOUL", "D_FOUL"]:
        # Pin to the moment step when a moment fired the foul; else a random step before final
        # (exclude step 0 and final step). If skeleton has 7 steps (0-6), choose from steps 1-5.
        if _moment_pin is not None:
            stop_step_index = _moment_pin
        else:
            stop_step_index = random.randint(1, len(steps) - 2) if len(steps) > 2 else 1
    elif result in ["DEAD_BALL_TURNOVER", "STEAL"]:
        # Dynamic HCO pass interception: pin the stop to the ACTUAL pass step (set by the finalizer)
        # so the steal lands at the interception, not a random mid step. Then the moment pin (per-step
        # steal/turnover). Falls through to the legacy random blast-radius when neither is present.
        _pin = game_state.get("_hco_pass_intercept_stop_index")
        if isinstance(_pin, int) and 1 <= _pin <= len(steps) - 1:
            stop_step_index = _pin
        elif _moment_pin is not None:
            stop_step_index = _moment_pin
        # Middle step with blast radius (±2 steps from middle)
        # Calculate middle of steps 1 through len(steps)-1 (excluding step 0 and final step)
        elif len(steps) > 2:
            # Calculate middle step
            middle_step = 1 + (len(steps) - 2 - 1) // 2
            
            # Create blast radius: middle ± 2, clamped to valid range (step 1 to second-to-last)
            min_step = max(1, middle_step - 2)
            max_step = min(len(steps) - 2, middle_step + 2)
            
            # Randomly select from blast radius
            stop_step_index = random.randint(min_step, max_step)
        else:
            stop_step_index = 1
    else:
        # Default: stop at step before final
        stop_step_index = len(steps) - 2
    
    # Truncate skeleton to stop_step_index
    truncated_steps = steps[:stop_step_index + 1]  # Include the stop step
    
    # Get the ball handler at the stop step for the stopper action
    stop_step = truncated_steps[-1]
    ball_handler_pos = None
    ball_handler_location = "key"  # Default location
    ball_handler_action_info = None  # Store full action_info to preserve opp, coords, etc.
    
    # Find ball handler in the stop step (include "shoot" so violation-on-shot credits the shooter, not PG fallback)
    pos_actions = stop_step.get("pos_actions", {})
    for pos, action_info in pos_actions.items():
        action = action_info.get("action", "").lower()
        if action in ["handle_ball", "receive", "pass", "shoot"]:
            ball_handler_pos = pos
            ball_handler_location = action_info.get("location", "key")
            ball_handler_action_info = action_info  # Store full action_info
            break
    
    # If no ball handler found in stop step, check previous step
    if not ball_handler_pos and len(truncated_steps) > 1:
        prev_step = truncated_steps[-2]
        prev_pos_actions = prev_step.get("pos_actions", {})
        for pos, action_info in prev_pos_actions.items():
            action = action_info.get("action", "").lower()
            if action in ["handle_ball", "receive", "shoot"]:
                ball_handler_pos = pos
                ball_handler_location = action_info.get("location", "key")
                ball_handler_action_info = action_info  # Store full action_info
                break
    
    # Create stopper step as final step
    stopper_timestamp = stop_step.get("timestamp", 0) + 300  # 300ms after stop step
    
    # Map result to stopper action
    stopper_action_map = {
        "O_FOUL": "o_foul",
        "D_FOUL": "d_foul",
        "DEAD_BALL_TURNOVER": "dead_ball_turnover",
        "SHOT_CLOCK_VIOLATION": "dead_ball_turnover",
        "STEAL": "steal"
    }
    stopper_action = stopper_action_map.get(result, "turnover")
    
    # Create stopper step
    stopper_step = {
        "timestamp": stopper_timestamp,
        "pos_actions": {},
        "events": [{"type": stopper_action}]
    }
    
    # Add ball handler position (if found) - ball remains with them until stopper
    # ✅ FIX: Preserve opp, coords, and other fields from original action_info
    if ball_handler_pos:
        stopper_action_info = {
            "location": ball_handler_location,
            "action": "handle_ball"  # Ball still with them
        }
        
        # Preserve opp field if it exists (critical for FCP/HCT press breaks)
        if ball_handler_action_info and "opp" in ball_handler_action_info:
            stopper_action_info["opp"] = ball_handler_action_info["opp"]
        
        # Preserve coords if they exist
        if ball_handler_action_info and "coords" in ball_handler_action_info:
            stopper_action_info["coords"] = ball_handler_action_info["coords"]
        
        stopper_step["pos_actions"][ball_handler_pos] = stopper_action_info
    
    # ✅ FIX: Store stop_step_index for later use in determining ball handler and defender
    # This ensures we use the actual ball handler at the step where the steal/foul/turnover occurred
    # Store for all non-shot results (steals, fouls, turnovers, shot clock violation) so defender determination uses correct ball handler
    if result in ["STEAL", "DEAD_BALL_TURNOVER", "SHOT_CLOCK_VIOLATION", "O_FOUL", "D_FOUL"]:
        game_state["steal_stop_step_index"] = stop_step_index
        # Also store a reference to the original skeleton steps before truncation
        # (we'll use this to extract position from the correct step)
        if result == "STEAL":
            game_state["steal_original_skeleton_steps"] = steps.copy()
    
    # Replace skeleton steps with truncated steps + stopper step
    skeleton["steps"] = truncated_steps + [stopper_step]
    
    return skeleton


# ==================== MOTION OFFENSE SHOT RESOLUTION ====================

def _is_inside_location(location):
    """Check if a location is an inside shot location."""
    inside_locations = ["lower lowPost", "lower midPost", "midLane", "basketSpot", "upper lowPost", "upper midPost"]
    return location in inside_locations


def _is_deep_location(location):
    """Check if a location has 'deep' in the name."""
    return "deep" in location.lower()


def _is_outside_location(location):
    """Check if a location is an outside shot location (not inside, not deep)."""
    return not _is_inside_location(location) and not _is_deep_location(location)


def _is_upper_location(location):
    """Check if a location is in the upper half of the court."""
    upper_keywords = ["upper", "top"]
    return any(keyword in location.lower() for keyword in upper_keywords)


def _is_lower_location(location):
    """Check if a location is in the lower half of the court."""
    lower_keywords = ["lower"]
    return any(keyword in location.lower() for keyword in lower_keywords)


def _is_central_location(location):
    """Check if a location is central (key, topLane, deep key)."""
    central_locations = ["key", "topLane", "deep key"]
    return location in central_locations


def _get_upper_inside_locations():
    """Get list of upper half inside shot locations."""
    return ["upper lowPost", "upper midPost", "midLane", "basketSpot"]


def _get_lower_inside_locations():
    """Get list of lower half inside shot locations."""
    return ["lower lowPost", "lower midPost", "midLane", "basketSpot"]


def _check_inside_shot_possibility(selected_step, ball_handler_location, off_lineup):
    """
    Check if an inside shot is possible based on conducive pass logic.
    
    Returns:
        tuple: (is_possible, list of viable receivers with their positions)
    """
    inside_locations = ["lower lowPost", "lower midPost", "midLane", "basketSpot", "upper lowPost", "upper midPost"]
    viable_receivers = []
    
    # Determine which inside locations are viable based on ball handler location
    if _is_upper_location(ball_handler_location):
        viable_inside_locations = _get_upper_inside_locations()
    elif _is_lower_location(ball_handler_location):
        viable_inside_locations = _get_lower_inside_locations()
    elif _is_central_location(ball_handler_location):
        # Central locations can pass to all inside spots
        viable_inside_locations = inside_locations
    else:
        # Default: use all inside locations
        viable_inside_locations = inside_locations
    
    # Find players at viable inside locations
    pos_actions = selected_step.get("pos_actions", {})
    logging.debug(f"🔍 [INSIDE CHECK] Ball handler at: {ball_handler_location}, Viable inside locations: {viable_inside_locations}")
    logging.debug(f"🔍 [INSIDE CHECK] All players in step: {[(pos, action_info.get('location', '')) for pos, action_info in pos_actions.items()]}")
    
    for pos, action_info in pos_actions.items():
        location = action_info.get("location", "")
        if location in viable_inside_locations:
            player = off_lineup.get(pos)
            if player:
                logging.debug(f"🔍 [INSIDE CHECK] Found viable receiver: {pos} at {location}")
                viable_receivers.append({
                    "position": pos,
                    "player": player,
                    "location": location
                })
    
    logging.debug(f"🔍 [INSIDE CHECK] Total viable receivers: {len(viable_receivers)}")
    return len(viable_receivers) > 0, viable_receivers


def _check_attack_shot_possibility(ball_handler_location):
    """
    Check if an attack shot is possible.
    Attack shots are not possible if ball handler is at an inside location.
    """
    return not _is_inside_location(ball_handler_location)


def _check_outside_shot_possibility(selected_step, off_lineup):
    """
    Check if an outside shot is possible (any player at outside location).
    
    Returns:
        tuple: (is_possible, list of players at outside locations)
    """
    outside_players = []
    pos_actions = selected_step.get("pos_actions", {})
    
    for pos, action_info in pos_actions.items():
        location = action_info.get("location", "")
        if _is_outside_location(location):
            player = off_lineup.get(pos)
            if player:
                outside_players.append({
                    "position": pos,
                    "player": player,
                    "location": location
                })
    
    return len(outside_players) > 0, outside_players


def _build_shot_type_weighted_list(strategy_settings, inside_possible, attack_possible, outside_possible, ball_handler_at_inside):
    """
    Build weighted list for shot type selection based on strategy settings and possibilities.
    
    Returns:
        list: Weighted list of shot types (e.g., ["inside", "inside", "attack", "outside"])
    """
    inside_weight = strategy_settings.get("inside", 2)
    attack_weight = strategy_settings.get("attack", 2)
    outside_weight = strategy_settings.get("outside", 2)
    
    # Special case: ball handler at inside location
    if ball_handler_at_inside:
        # No attack possible, weighted: 4 inside, 2 outside
        weighted_list = ["inside"] * 4 + ["outside"] * 2
        if not outside_possible:
            # Only inside possible
            return ["inside"] * 4
        return weighted_list
    
    # Build initial weighted list
    weighted_list = []
    if inside_possible:
        weighted_list.extend(["inside"] * inside_weight)
    if attack_possible:
        weighted_list.extend(["attack"] * attack_weight)
    if outside_possible:
        weighted_list.extend(["outside"] * outside_weight)
    
    # Handle edge cases where list is empty or only one type possible
    if not weighted_list:
        # All three not possible (shouldn't happen, but handle gracefully)
        if inside_possible:
            return ["inside"]
        elif attack_possible:
            return ["attack"]
        elif outside_possible:
            return ["outside"]
        else:
            # Fallback: default to outside
            return ["outside"]
    
    # Handle cases where chosen type has 0 weight
    if inside_possible and attack_possible and not outside_possible:
        if inside_weight == 0 and attack_weight == 0:
            return ["inside", "attack"]  # Random between available
    elif inside_possible and outside_possible and not attack_possible:
        if inside_weight == 0 and outside_weight == 0:
            return ["inside", "outside"]  # Random between available
    elif attack_possible and outside_possible and not inside_possible:
        if attack_weight == 0 and outside_weight == 0:
            return ["attack", "outside"]  # Random between available
    
    return weighted_list


def _find_closest_receiver(ball_handler_location, receivers, off_lineup):
    """
    Find closest receiver to ball handler (75% chance) or random other (25% chance).
    
    Args:
        ball_handler_location: Location string of ball handler
        receivers: List of receiver dicts with "position", "player", "location"
        off_lineup: Offensive lineup dict
    
    Returns:
        dict: Selected receiver
    """
    from BackEnd.constants import HCO_STRING_SPOTS
    
    if len(receivers) == 1:
        return receivers[0]
    
    # Get ball handler coordinates
    bh_coords = HCO_STRING_SPOTS.get(ball_handler_location, {"x": 50, "y": 25})
    
    # Calculate distances
    receiver_distances = []
    for receiver in receivers:
        receiver_location = receiver["location"]
        receiver_coords = HCO_STRING_SPOTS.get(receiver_location, {"x": 50, "y": 25})
        
        # Euclidean distance
        distance = ((bh_coords["x"] - receiver_coords["x"]) ** 2 + 
                   (bh_coords["y"] - receiver_coords["y"]) ** 2) ** 0.5
        
        receiver_distances.append({
            "receiver": receiver,
            "distance": distance
        })
    
    # Sort by distance
    receiver_distances.sort(key=lambda x: x["distance"])
    closest = receiver_distances[0]
    others = receiver_distances[1:]
    
    # 75% chance closest, 25% chance random other
    if random.random() < 0.75 or len(others) == 0:
        return closest["receiver"]
    else:
        return random.choice(others)["receiver"]


def _determine_attack_drive_destination(ball_handler_location):
    """
    Determine valid drive destinations based on starting location.
    
    Returns:
        list: Valid destination locations
    """
    if _is_upper_location(ball_handler_location):
        return ["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot"]
    elif _is_lower_location(ball_handler_location):
        return ["lower lowPost", "lower midPost", "lower bird", "midLane", "basketSpot"]
    elif _is_central_location(ball_handler_location):
        # Central: all destinations
        return ["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot",
                "lower lowPost", "lower midPost", "lower bird"]
    else:
        # Default: all destinations
        return ["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot",
                "lower lowPost", "lower midPost", "lower bird"]


def _create_pass_receive_step(passer_pos, receiver_pos, passer_location, receiver_location, timestamp):
    """
    Create a step for pass and receive.
    
    Returns:
        dict: Step with pass and receive actions
    """
    return {
        "timestamp": timestamp,
        "pos_actions": {
            passer_pos: {
                "location": passer_location,
                "action": "pass"
            },
            receiver_pos: {
                "location": receiver_location,
                "action": "receive"
            }
        },
        "events": []
    }


def _create_shoot_step(shooter_pos, shooter_location, timestamp):
    """
    Create a step for shooting.
    
    Returns:
        dict: Step with shoot action
    """
    return {
        "timestamp": timestamp,
        "pos_actions": {
            shooter_pos: {
                "location": shooter_location,
                "action": "shoot"
            }
        },
        "events": [{"type": "shot"}]
    }


def _create_attack_drive_shoot_steps(
    ball_handler_pos,
    start_location,
    destination_location,
    timestamp,
    is_away_offense=False,
    selected_step=None,
    off_lineup=None,
    def_lineup=None,
    game=None,
):
    """
    Create motion attack drive steps: drive (+ clearance/perimeter/contest), then
    shoot or pass/receive + shoot based on driver decision.
    """
    if (
        selected_step
        and off_lineup
        and def_lineup
        and game is not None
    ):
        from BackEnd.engine.attack_drive_clearance import build_attack_drive_sequence

        result = build_attack_drive_sequence(
            selected_step=selected_step,
            ball_handler_pos=ball_handler_pos,
            start_location=start_location,
            destination_location=destination_location,
            timestamp=timestamp,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            game=game,
            is_away_offense=is_away_offense,
        )
        return result

    final_location = destination_location
    drive_step = {
        "timestamp": timestamp,
        "pos_actions": {
            ball_handler_pos: {
                "location": final_location,
                "action": "drive",
            }
        },
        "events": [],
        "_attack_drive": {
            "driver_gate": True,
            "gate_driver_pos": ball_handler_pos,
            "start_location": start_location,
            "intended_destination": destination_location,
            "final_location": final_location,
            "stopped_short": False,
            "defender_overrides": {},
        },
    }
    shoot_step = {
        "timestamp": timestamp + 300,
        "pos_actions": {
            ball_handler_pos: {
                "location": final_location,
                "action": "shoot",
            }
        },
        "events": [{"type": "shot"}],
        "_attack_drive": {
            "start_location": start_location,
            "intended_destination": destination_location,
            "final_location": final_location,
            "stopped_short": False,
        },
    }
    return {
        "steps": [drive_step, shoot_step],
        "shooter": off_lineup.get(ball_handler_pos) if off_lineup else None,
        "shooter_pos": ball_handler_pos,
        "shooter_location": final_location,
        "resolved_shot_type": "attack",
        "playcall": "Attack",
        "motion_attack_uncontested": False,
        "motion_attack_geometry_contest": False,
        "motion_attack_defense_bonus": 0,
    }


def _apply_attack_penalty(shot_location, is_away_offense):
    """
    Calculate attack shot penalty if player was stopped short.
    
    Args:
        shot_location: Final location where shot was taken
        is_away_offense: Whether away team is on offense
    
    Returns:
        float: Penalty value (0 if no penalty)
    """
    from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS, AWAY_RIM_COORDS
    
    # No penalty for ideal spots
    ideal_spots = ["basketSpot", "upper lowPost", "lower lowPost"]
    if shot_location in ideal_spots:
        return 0.0
    
    # Get shot location coordinates
    shot_coords = HCO_STRING_SPOTS.get(shot_location, {"x": 50, "y": 25})
    
    # Get basket spot coordinates
    if is_away_offense:
        basket_coords = AWAY_RIM_COORDS  # x=10
    else:
        basket_coords = HOME_RIM_COORDS  # x=90
    
    # Calculate penalty
    penalty = abs(shot_coords["x"] - basket_coords["x"])
    
    return penalty


def _uess_sync_emitted_shot_coords(game, skeleton, animations, roles, turn_type="HCO"):
    """UESS single-coord-source: sync EVERY player's ``player.coords`` to the
    emitter's shoot-step render coord, and return the shooter's coord (for
    ``roles["shot_spot"]``). All coords are display-oriented — the same frame
    ``player.coords`` already stores (``apply_coords`` is a pass-through), so no
    re-mirror is needed.

    Why: shot resolution decides from ``player.coords``. `apply_coords_from_
    animations_list` sets those to the ANIMATOR row-end (all players fully
    arrived), but the emitter renders non-gate players INTERRUPTED mid-move
    (§9.5) — a ~58% divergence. So the shot logic saw a different geometry than
    the FE: it mis-scored 2PT/3PT classification (~25%, shooter) AND over-
    contested shots (~6%, defenders fully-arrived in logic but mid-move on
    screen). Stamping the emitted shoot-step coords onto every player makes the
    contest loop, defender selection, and classification all read the rendered
    geometry. See ``Coord_Consumer_UESS_Audit.md`` (hole #1).

    Runs the real emitter on a throwaway turn_result to guarantee parity with
    the later render (the emitter is side-effect-free w.r.t. game/player state;
    ``result_type`` omitted → post-shot sub-steps are a no-op). RNG-neutral
    (save/restore) so it never perturbs resolve_shot's make/miss or downstream
    outcomes. Returns None on any failure → caller falls back to
    ``set_shooter_coords_from_skeleton_last_step`` (shooter-spot only).
    """
    try:
        shooter = roles.get("shooter")
        shooter_id = getattr(shooter, "player_id", None) if shooter else None
        if not shooter_id or not skeleton or not animations:
            return None
        from BackEnd.engine.skeleton_step_emitter import build_skeleton_animation_steps
        probe_tr = {"skeleton": skeleton, "animations": animations, "roles": roles}
        # RNG-NEUTRAL: the emitter draws from the global random stream (shot
        # micro-movements). This is a throwaway pre-pass — save/restore the RNG
        # state so it does NOT advance the stream and perturb resolve_shot's
        # make/miss or any downstream outcome. The fix changes the coords the
        # logic reads, never game results directly.
        import random as _random
        _rng_state = _random.getstate()
        try:
            steps = build_skeleton_animation_steps(probe_tr, game, turn_type=turn_type)
        finally:
            _random.setstate(_rng_state)
        if not steps:
            return None
        sid = str(shooter_id)
        # The shoot step marks the shooter via start.action[shooter_id] == "shoot".
        shoot_step = None
        for st in steps:
            act = (st.get("start") or {}).get("action") or {}
            v = act.get(shooter_id) or act.get(sid)
            if isinstance(v, str) and v.lower().strip() == "shoot":
                shoot_step = st
                break
        if shoot_step is None:
            shoot_step = steps[-1]
        coords = (shoot_step.get("end") or {}).get("coords") or {}
        if not coords:
            return None
        # Sync ALL active players to the emitted shoot-step coord (matches
        # apply_coords_from_animations_list's iteration; adds only where the
        # emitter has a coord for that player — never clobbers with None).
        norm = {str(k): v for k, v in coords.items()}
        for team in (game.home_team, game.away_team):
            for player in (getattr(team, "lineup", None) or {}).values():
                if player is None:
                    continue
                pid = getattr(player, "player_id", None)
                c = coords.get(pid) or norm.get(str(pid))
                if isinstance(c, dict) and c.get("x") is not None and c.get("y") is not None:
                    player.coords = {"x": float(c["x"]), "y": float(c["y"])}
        c = coords.get(shooter_id) or norm.get(sid)
        if isinstance(c, dict) and c.get("x") is not None and c.get("y") is not None:
            return {"x": float(c["x"]), "y": float(c["y"])}
        return None
    except Exception:
        return None


def set_shooter_coords_from_skeleton_last_step(game, skeleton, roles):
    """
    Set roles["shooter"].coords from the last step of the skeleton when that step
    has a shoot action for the shooter. Used for HCO, FCP, HCT, and Final Turn
    so block reconciliation uses the correct shot location. Fast Break does not
    use this.

    NOTE: this is now the FALLBACK path (shooter-spot only). The primary path
    syncs ALL players to the emitter's rendered shoot-step coords via
    ``_uess_sync_emitted_shot_coords`` (UESS single-coord-source). This runs only
    when that resolver returns None.
    """
    _ensure_skeleton_shot_role_positions(game, roles)
    if not skeleton or not roles:
        return
    steps = skeleton.get("steps") or []
    if not steps:
        return
    shooter = roles.get("shooter")
    shooter_pos = roles.get("shooter_pos")
    if shooter is None or shooter_pos is None:
        return
    last_step = steps[-1]
    last_step_pos_actions = last_step.get("pos_actions") or {}
    last_step_keys = list(last_step_pos_actions.keys())
    final_step_shooter_pos = None
    final_step_shooter_action = None
    final_step_shot_event_by = None
    final_step_has_location = False
    final_step_has_spot = False
    for pos, action_info in last_step_pos_actions.items():
        action = (action_info.get("action") or "").lower().strip()
        if action == "shoot":
            final_step_shooter_pos = pos
            final_step_shooter_action = action_info.get("action")
            final_step_has_location = action_info.get("location") is not None
            final_step_has_spot = action_info.get("spot") is not None
            break
    for event in last_step.get("events", []):
        if event.get("type") == "shot":
            final_step_shot_event_by = event.get("by")
            break

    shoot_step = None
    shoot_pos_actions = None
    pa = None
    matched_shoot_step_index = None
    for step_index in range(len(steps) - 1, -1, -1):
        candidate_step = steps[step_index]
        candidate_pos_actions = candidate_step.get("pos_actions") or {}
        candidate_action = candidate_pos_actions.get(shooter_pos)
        if candidate_action and (candidate_action.get("action") or "").lower().strip() == "shoot":
            shoot_step = candidate_step
            shoot_pos_actions = candidate_pos_actions
            pa = candidate_action
            matched_shoot_step_index = step_index
            break

    if not pa:
        return
    from BackEnd.constants import HCO_STRING_SPOTS
    from BackEnd.utils.shared import get_away_player_coords

    explicit_coords = pa.get("coords")
    if (
        isinstance(explicit_coords, dict)
        and explicit_coords.get("x") is not None
        and explicit_coords.get("y") is not None
    ):
        # Dynamic HCO coord-based shoot step (e.g. Freelance, or an attack-drive step that
        # carries an explicit final coord). These coords are already DISPLAY-oriented — they
        # are produced by _spot_display_coords / _basket_display_coords, the same frame the
        # named path lands in after its away mirror, and exactly what
        # is_three_point_shot_from_coords expects. Use them VERBATIM (no re-mirror) and prefer
        # them over the named-spot lookup so the exact procedural shot position drives 2PT/3PT
        # classification rather than a defaulted "key".
        coords = {"x": float(explicit_coords["x"]), "y": float(explicit_coords["y"])}
    else:
        # Legacy named-spot fallback: HCO_STRING_SPOTS is home-oriented → mirror for away.
        location = (pa.get("location") or pa.get("spot") or "key").strip()
        # Case-insensitive lookup (skeleton may use "upper midwing" vs constant "upper midWing")
        coords = HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
        if coords == {"x": 50, "y": 25} and location.lower() != "key":
            for k, v in HCO_STRING_SPOTS.items():
                if k.lower() == location.lower():
                    coords = v
                    break
        if game.offense_team.team_id == game.away_team.team_id:
            coords = get_away_player_coords(coords)
    shooter.coords = coords
    roles["shot_spot"] = coords  # Same data for block reconciliation (explicit shot location = animation location)


def _ensure_skeleton_shot_role_positions(game, roles):
    """
    Normalize positional role fields for skeleton-driven shot turns.

    HCO, FCP, and HCT all use player-object roles plus skeleton steps. This helper
    backfills the matching *_pos fields so shared shot-spot logic, snapshots, and
    downstream debugging operate on one consistent contract.
    """
    if not isinstance(roles, dict):
        return roles

    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup

    if roles.get("shooter_pos") is None and roles.get("shooter") is not None:
        roles["shooter_pos"] = get_player_position(off_lineup, roles.get("shooter"))
    if roles.get("passer_pos") is None and roles.get("passer") is not None:
        roles["passer_pos"] = get_player_position(off_lineup, roles.get("passer"))
    if roles.get("screener_pos") is None and roles.get("screener") is not None:
        roles["screener_pos"] = get_player_position(off_lineup, roles.get("screener"))
    if roles.get("defender_pos") is None and roles.get("defender") is not None:
        roles["defender_pos"] = get_player_position(def_lineup, roles.get("defender"))
    if roles.get("second_defender_pos") is None and roles.get("second_defender") is not None:
        roles["second_defender_pos"] = get_player_position(def_lineup, roles.get("second_defender"))

    ball_handler = roles.get("ball_handler")
    if roles.get("ball_handler_pos") is None:
        if ball_handler is not None:
            roles["ball_handler_pos"] = get_player_position(off_lineup, ball_handler)
        elif roles.get("passer_pos") is not None:
            roles["ball_handler_pos"] = roles.get("passer_pos")
        else:
            roles["ball_handler_pos"] = roles.get("shooter_pos")

    return roles


def resolve_motion_offense_shot(skeleton, game, off_lineup, def_lineup, forced_shot_step_index=None):
    """
    Resolve Motion offense shot attempt.
    
    This function:
    1. Selects a random step (excluding step 0) for shot attempt, or uses forced_shot_step_index if provided
    2. Determines shot type (inside/outside/attack) based on possibilities and strategy
    3. Truncates skeleton at selected step
    4. Appends necessary steps (pass/receive, drive, shoot)
    5. Returns modified skeleton and shot information
    
    Args:
        skeleton: Motion play skeleton with base_loop steps
        game: GameManager instance
        off_lineup: Offensive lineup dict
        def_lineup: Defensive lineup dict
        forced_shot_step_index: Optional int. If provided, use this step index instead of random (for recalibration).
    
    Returns:
        dict: {
            "skeleton": modified skeleton with shot steps appended,
            "shooter": Player object,
            "shooter_location": location string,
            "shot_type": "inside" | "outside" | "attack",
            "playcall": "Inside" | "Outside" | "Attack",
            "attack_penalty": float (0 if not attack or no penalty)
        }
    """
    import copy
    from BackEnd.constants import HCO_STRING_SPOTS
    from BackEnd.utils.shared import get_away_player_coords
    
    game_state = game.game_state
    off_team = game.offense_team
    is_away_offense = off_team.team_id == game.away_team.team_id
    
    # Deep copy skeleton to avoid mutating original
    skeleton = copy.deepcopy(skeleton)
    steps = skeleton.get("steps", [])
    
    if len(steps) < 2:
        logging.warning(f"⚠️ [MOTION SHOT] Skeleton has insufficient steps ({len(steps)}), cannot select shot step")
        return None

    # ── Dynamic HCO Motion (gated, experimental) ──────────────────────────────
    # Attribute-based per-step decision loop (brief Steps 1–2) replaces the random
    # step + random shot-type selection below. Off by default; enable with the
    # GOB_DYNAMIC_HCO_MOTION env var. Recalibration (forced_shot_step_index) and any
    # error fall back to the legacy path so live games are never broken.
    if forced_shot_step_index is None and _dynamic_hco_motion_enabled():
        logging.warning("🟢 [DYNAMIC MOTION] flag ON — running dynamic resolver for this Motion shot")
        try:
            dynamic_result = _resolve_hco_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup, is_setplay=False)
            if dynamic_result is not None:
                return dynamic_result
            logging.info("ℹ️ [DYNAMIC MOTION] Resolver returned None; using legacy random selection")
        except Exception as e:
            logging.warning(f"⚠️ [DYNAMIC MOTION] Error in dynamic resolver, falling back to legacy: {e}")

    # Phase 1: Select step (forced for recalibration, else random excluding step 0)
    if forced_shot_step_index is not None:
        shot_step_index = max(1, min(forced_shot_step_index, len(steps) - 1))
    else:
        shot_step_index = random.randint(1, len(steps) - 1)
    selected_step = steps[shot_step_index]
    
    # Truncate skeleton at selected step
    truncated_steps = steps[:shot_step_index + 1]
    last_timestamp = truncated_steps[-1].get("timestamp", 0)
    
    # Phase 2: Identify ball handler at selected step
    ball_handler_pos = None
    ball_handler_location = "key"
    pos_actions = selected_step.get("pos_actions", {})
    
    for pos, action_info in pos_actions.items():
        action = action_info.get("action", "").lower()
        if action in ["handle_ball", "receive", "pass"]:
            ball_handler_pos = pos
            ball_handler_location = action_info.get("location", "key")
            break
    
    if not ball_handler_pos:
        logging.warning(f"⚠️ [MOTION SHOT] No ball handler found at selected step {shot_step_index}")
        return None
    
    ball_handler = off_lineup.get(ball_handler_pos)
    if not ball_handler:
        logging.warning(f"⚠️ [MOTION SHOT] Ball handler position {ball_handler_pos} not found in lineup")
        return None
    
    # Phase 3: Check shot possibilities
    inside_possible, inside_receivers = _check_inside_shot_possibility(selected_step, ball_handler_location, off_lineup)
    attack_possible = _check_attack_shot_possibility(ball_handler_location)
    outside_possible, outside_players = _check_outside_shot_possibility(selected_step, off_lineup)
    
    ball_handler_at_inside = _is_inside_location(ball_handler_location)
    
    # 🔍 DEBUG: Log shot possibilities
    logging.debug(f"🎯 [MOTION SHOT] Step {shot_step_index}, Ball handler: {ball_handler_pos} at {ball_handler_location}")
    logging.debug(f"🎯 [MOTION SHOT] Inside possible: {inside_possible}, Receivers: {len(inside_receivers)}")
    if inside_receivers:
        logging.debug(f"🎯 [MOTION SHOT] Inside receivers: {[(r['position'], r['location']) for r in inside_receivers]}")
    logging.debug(f"🎯 [MOTION SHOT] Attack possible: {attack_possible}, Outside possible: {outside_possible}")
    logging.debug(f"🎯 [MOTION SHOT] Ball handler at inside: {ball_handler_at_inside}")
    
    # Phase 4: Get strategy settings and build weighted list
    strategy_settings = off_team.strategy_settings
    weighted_list = _build_shot_type_weighted_list(
        strategy_settings, inside_possible, attack_possible, outside_possible, ball_handler_at_inside
    )
    
    logging.debug(f"🎯 [MOTION SHOT] Weighted list: {weighted_list} (inside_weight={strategy_settings.get('inside', 2)}, attack_weight={strategy_settings.get('attack', 2)}, outside_weight={strategy_settings.get('outside', 2)})")
    
    # Phase 5: Select shot type
    selected_shot_type = random.choice(weighted_list)
    logging.debug(f"🎯 [MOTION SHOT] Selected shot type: {selected_shot_type}")
    
    # Phase 6: Execute shot - build additional steps
    new_steps = []
    shooter = ball_handler
    shooter_pos = ball_handler_pos
    shooter_location = ball_handler_location
    attack_penalty = 0.0
    
    if selected_shot_type == "inside":
        if ball_handler_at_inside:
            # Ball handler shoots from current location
            shoot_step = _create_shoot_step(ball_handler_pos, ball_handler_location, last_timestamp + 300)
            new_steps.append(shoot_step)
        else:
            # Pass to inside receiver
            receiver = _find_closest_receiver(ball_handler_location, inside_receivers, off_lineup)
            receiver_pos = receiver["position"]
            receiver_location = receiver["location"]
            
            # Step 1: Pass and receive
            pass_step = _create_pass_receive_step(
                ball_handler_pos, receiver_pos, ball_handler_location, receiver_location, last_timestamp + 300
            )
            new_steps.append(pass_step)
            
            # Step 2: Receiver shoots
            shoot_step = _create_shoot_step(receiver_pos, receiver_location, last_timestamp + 600)
            new_steps.append(shoot_step)
            
            shooter = receiver["player"]
            shooter_pos = receiver_pos
            shooter_location = receiver_location
    
    elif selected_shot_type == "outside":
        if _is_outside_location(ball_handler_location):
            # Ball handler shoots from current location
            shoot_step = _create_shoot_step(ball_handler_pos, ball_handler_location, last_timestamp + 300)
            new_steps.append(shoot_step)
        else:
            # Pass to outside receiver
            receiver = _find_closest_receiver(ball_handler_location, outside_players, off_lineup)
            receiver_pos = receiver["position"]
            receiver_location = receiver["location"]
            
            # Step 1: Pass and receive
            pass_step = _create_pass_receive_step(
                ball_handler_pos, receiver_pos, ball_handler_location, receiver_location, last_timestamp + 300
            )
            new_steps.append(pass_step)
            
            # Step 2: Receiver shoots
            shoot_step = _create_shoot_step(receiver_pos, receiver_location, last_timestamp + 600)
            new_steps.append(shoot_step)
            
            shooter = receiver["player"]
            shooter_pos = receiver_pos
            shooter_location = receiver_location
    
    elif selected_shot_type == "attack":
        # Determine drive destination
        valid_destinations = _determine_attack_drive_destination(ball_handler_location)
        destination = random.choice(valid_destinations)
        
        drive_result = _create_attack_drive_shoot_steps(
            ball_handler_pos,
            ball_handler_location,
            destination,
            last_timestamp + 300,
            is_away_offense,
            selected_step=selected_step,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            game=game,
        )
        new_steps.extend(drive_result["steps"])
        
        shooter = drive_result.get("shooter") or ball_handler
        shooter_pos = drive_result.get("shooter_pos") or ball_handler_pos
        shooter_location = drive_result.get("shooter_location") or destination
        selected_shot_type = drive_result.get("resolved_shot_type") or "attack"
        playcall_override = drive_result.get("playcall")
        
        attack_penalty = _apply_attack_penalty(shooter_location, is_away_offense)
        _playcall_map = {"inside": "Inside", "outside": "Outside", "attack": "Attack"}
        skeleton["steps"] = truncated_steps + new_steps
        
        return {
            "skeleton": skeleton,
            "shooter": shooter,
            "shooter_pos": shooter_pos,
            "shooter_location": shooter_location,
            "shot_type": selected_shot_type,
            "playcall": playcall_override or _playcall_map.get(selected_shot_type, "Attack"),
            "attack_penalty": attack_penalty,
            "motion_attack_uncontested": drive_result.get("motion_attack_uncontested", False),
            "motion_attack_geometry_contest": drive_result.get("motion_attack_geometry_contest", False),
            "motion_attack_defense_bonus": drive_result.get("motion_attack_defense_bonus", 0),
            "motion_attack_driver_shoots": drive_result.get("motion_attack_driver_shoots"),
        }
    
    # Phase 7: Append new steps to truncated skeleton
    skeleton["steps"] = truncated_steps + new_steps
    
    # Phase 8: Map shot type to playcall for shot calculation
    playcall_map = {
        "inside": "Inside",
        "outside": "Outside",
        "attack": "Attack"
    }
    playcall = playcall_map.get(selected_shot_type, "Inside")
    
    return {
        "skeleton": skeleton,
        "shooter": shooter,
        "shooter_pos": shooter_pos,
        "shooter_location": shooter_location,
        "shot_type": selected_shot_type,
        "playcall": playcall,
        "attack_penalty": attack_penalty
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic HCO Motion (gated) — attribute-based shot selection.
# See _documentation_master/projects/Z-Completed/Dynamic_HCO_Motion_Brief.md and
# Z-Completed/Dynamic_HCO_Motion_Implementation_Plan.md (archived). Phase 3: walk the skeleton making
# per-step decisions (Step 2) and hand a shot decision off to the existing shot
# builders / attack-drive sequence. Subtle-movement / freelance EMISSION is Phase
# 4–5 — here those decisions simply advance to the next skeleton step.
# ─────────────────────────────────────────────────────────────────────────────
def _dynamic_hco_motion_enabled():
    """Dynamic HCO Motion is ON by default — the up-front team-attribute event tables are sunset in
    favor of the per-step attribute-driven moment walk. Kill switch: set GOB_DYNAMIC_HCO_MOTION to a
    falsy value (``0``/``false``/``off``) to fall back to the legacy up-front tables."""
    import os
    return os.environ.get("GOB_DYNAMIC_HCO_MOTION", "1").strip().lower() in ("1", "true", "yes", "on")


def _dynamic_hco_defense_enabled():
    """Dynamic HCO Defense (Dynamic_MM_Brief) — ON by default. Gates the per-turn defender posture
    (tight/normal/loose) + the two-gate intercept model. Kill switch: set GOB_DYNAMIC_HCO_DEFENSE to
    a falsy value (``0``/``false``/``off``) to fall back to legacy defender placement.
    NOTE: in-development (P1 = man-defense posture placement only); enabled in prod per owner request."""
    import os
    return os.environ.get("GOB_DYNAMIC_HCO_DEFENSE", "1").strip().lower() in ("1", "true", "yes", "on")


# Interim posture pick — a team-wide loose/normal/tight per turn (Dynamic_MM_Brief §5A). Later
# replaced by the chosen tight/loose playcall variant (P6).
_HCO_DEFENSE_POSTURES = ("loose", "normal", "tight")


def _roll_defense_posture(game, rng=None):
    """Pick this HCO turn's team defense posture and stash it on game_state for the animator
    (render) + the future intercept read. None when the flag is off → legacy placement. Rolled
    fresh each HCO turn so it never goes stale across possessions. See Dynamic_MM_Brief §5A."""
    import random as _r
    game_state = getattr(game, "game_state", {})
    if game_state is None:
        return None
    if not _dynamic_hco_defense_enabled():
        game_state["_hco_defense_posture"] = None
        return None
    posture = (rng or _r).choice(_HCO_DEFENSE_POSTURES)
    game_state["_hco_defense_posture"] = posture
    logging.warning(f"🛡️ [DYNAMIC DEFENSE] turn posture = {posture}")
    return posture


def _dynamic_hco_setplay_enabled():
    """Dynamic HCO **Set Plays** ON by default (overlay model — separate from motion). Variant
    selection stays, but the up-front event tables are skipped in favor of the per-step moment, and
    the per-step dynamic layer (hot read / defense-forced subtle / freelance) overlays the chosen
    variant skeleton. Kill switch: set GOB_DYNAMIC_HCO_SETPLAY to a falsy value (``0``/``false``/
    ``off``). See Z-Completed/Dynamic_HCO_SP_Brief.md."""
    import os
    return os.environ.get("GOB_DYNAMIC_HCO_SETPLAY", "1").strip().lower() in ("1", "true", "yes", "on")


def _setplay_recovery_roll(game, rng=None):
    """Set-play forced-subtle recovery (Z-Completed/Dynamic_HCO_SP_Brief): after the defense knocks the BH off
    the play and he chooses to hold rather than shoot/dish, he either re-enters the set-play
    skeleton or is forced into freelance. `offense_score = (team_chemistry + offensive_efficiency)
    × d6` vs `defense_score = (team_chemistry + defensive_efficiency) × d6` (each team's own
    chemistry). Returns True → re-enter the skeleton at the next defined step; False → freelance."""
    import random as _r
    rng = rng or _r
    oa = (getattr(game.offense_team, "team_attributes", {}) or {})
    da = (getattr(game.defense_team, "team_attributes", {}) or {})
    offense_score = (float(oa.get("team_chemistry", 7) or 7) + float(oa.get("offensive_efficiency", 0) or 0)) * rng.randint(1, 6)
    defense_score = (float(da.get("team_chemistry", 7) or 7) + float(da.get("defensive_efficiency", 0) or 0)) * rng.randint(1, 6)
    return offense_score > defense_score


# Coach VO clips fired when the offense consciously breaks pattern on a hot read. One is
# chosen at random on the BACKEND (logic + SS&S-reproducible) and stamped on the turn result;
# the FE shows the "Hot Read!" call and plays the chosen clip (pure renderer). See SFX_System.md.
HOT_READ_VO_FILES = ("braddock-greatread.wav", "sammy-niceread.mp3")
# TEMPORARILY DISABLED (2026-06-23): the nice-read/great-read hot-read VO clutters more than it
# helps. Flip back to True to re-enable — the full pipeline (clip stamp → emitter
# sfx_on_step_start → FE playback) is left intact, this flag just gates the stamping.
HOT_READ_VO_ENABLED = False


def _motion_bh_at_step(step):
    """
    Ball-handler position + location at a skeleton step = whoever HOLDS the ball at step END.

    On a pass/receive step the ball ends with the receiver (it just arrived), so prefer
    ``receive`` > ``handle_ball`` > ``pass``. Picking the passer — who is giving the ball up —
    would make an appended dish (e.g. a teammate hot read) pass a SECOND time from the same
    player, producing the doubled pass animation. The dynamic walk evaluates every step, so it
    lands on pass steps and must resolve the actual holder (the legacy resolver only sampled one
    random step, so it rarely hit this).
    """
    pos_actions = step.get("pos_actions") or {}
    for wanted in ("receive", "handle_ball", "pass"):
        for pos, info in pos_actions.items():
            if ((info or {}).get("action") or "").lower() == wanted:
                return pos, info.get("location", "key")
    return None, None


def _estimate_step_game_seconds(prev_step, step, off_lineup, is_away_offense):
    """Approximate the game-seconds a skeleton step consumes = the slowest offensive mover's
    grid travel at HCO cruise pace, floored at HCO_STEP_T_FLOOR. Used only by the dynamic
    resolver to track a running shot-clock estimate for the subtle forced-shot backstop (the
    emitter remains the authoritative timer); subtle beats use their explicit tempo floor."""
    import math as _math
    from BackEnd.engine.motion_subtle import _coords_for
    from BackEnd.constants import CRUISE_GRID_PER_GAME_SEC, HCO_STEP_T_FLOOR_GAME_SECONDS
    prev_pa = prev_step.get("pos_actions") or {}
    cur_pa = step.get("pos_actions") or {}
    max_t = 0.0
    for pos in off_lineup:
        if not off_lineup.get(pos):
            continue
        p, c = prev_pa.get(pos), cur_pa.get(pos)
        if not p or not c:
            continue
        pc, cc = _coords_for(p, is_away_offense), _coords_for(c, is_away_offense)
        t = _math.hypot(cc["x"] - pc["x"], cc["y"] - pc["y"]) / float(CRUISE_GRID_PER_GAME_SEC)
        max_t = max(max_t, t)
    return max(float(HCO_STEP_T_FLOOR_GAME_SECONDS), max_t)


def _roll_subtle_defender_reads(def_lineup, def_eff, rng):
    """Per-defender subtle read (incl. the BH defender): ``(player_read_raw + def_eff) * d6``.
    Returns {def_pos: follows_bool} — True = the defender made the read to move with his man;
    False = he freezes (the animator applies this against the beat, creating space). The
    geometric "did my man actually move?" gate is applied in the animator, not here."""
    from BackEnd.utils.shared import player_read_raw
    from BackEnd.engine.motion_step_decision import MOTION_READ_THRESHOLD
    reads = {}
    for def_pos, defender in (def_lineup or {}).items():
        if not defender:
            continue
        score = (player_read_raw(defender) + def_eff) * rng.randint(1, 6)
        reads[def_pos] = bool(score > MOTION_READ_THRESHOLD)
    return reads


def _roll_subtle_idle_motion(
    beat, off_lineup, def_lineup, bh_pos, bh_location, off_to_def, locations, is_away_offense, rng
):
    """Seeded, geography-based render-space idle motion for a subtle beat (COSMETIC; UESS-safe).

    Assigns each player a role-based motion STYLE by where they're standing (inside spot vs
    perimeter, `INSIDE_SPOTS`) + role (offense / defense / ball handler), plus a unit direction
    the FE renders it along. Purely cosmetic — never affects the sim — but rolled here (seeded
    RNG) so the payload fully determines the render (FE stays a pure renderer). v1 styles:
    jockey (inside), jab (perimeter off-ball), shuffle (perimeter D), survey_rock (perimeter BH;
    else still = omitted → heartbeat only). Defender role uses the man matchup's guarded player;
    zone defenders default to shuffle (paired post-D physics is v1.1). Returns
    ``{str(pid): {"kind","style","seed","dir_x","dir_y","amplitude_grid"}}``."""
    from BackEnd.engine.motion_read_map import is_inside_location
    from BackEnd.engine.motion_step_decision import (
        SUBTLE_IDLE_STYLE_AMPLITUDE_GRID,
        BH_SURVEY_PROBABILITY,
    )
    pos_actions = (beat or {}).get("pos_actions") or {}
    bh_player = (off_lineup or {}).get(bh_pos)
    bh_id = getattr(bh_player, "player_id", None)
    # Display-x sign toward the offense's basket (matches basket_x = 9 away / 91 home).
    basket_sign_x = -1.0 if is_away_offense else 1.0
    _bh_c = (pos_actions.get(bh_pos) or {}).get("coords") or {}
    bh_x, bh_y = float(_bh_c.get("x", 50.0)), float(_bh_c.get("y", 25.0))

    def _unit(dx, dy):
        d = (dx * dx + dy * dy) ** 0.5
        return (0.0, 1.0) if d < 1e-6 else (dx / d, dy / d)

    def _entry(style, direction):
        return {
            "kind": "idle_wander",
            "style": style,
            "seed": rng.randint(0, 2**31 - 1),
            "dir_x": round(direction[0], 3),
            "dir_y": round(direction[1], 3),
            "amplitude_grid": SUBTLE_IDLE_STYLE_AMPLITUDE_GRID.get(style, 0.8),
        }

    motion = {}
    # Offense — style by the player's own location.
    for off_pos, player in (off_lineup or {}).items():
        pid = getattr(player, "player_id", None)
        if pid is None:
            continue
        inside = is_inside_location(locations.get(off_pos))
        is_bh = pid == bh_id
        if inside:
            motion[str(pid)] = _entry("jockey", (basket_sign_x, 0.0))
        elif is_bh:
            if rng.random() >= BH_SURVEY_PROBABILITY:
                continue  # perimeter BH stands still (heartbeat only)
            motion[str(pid)] = _entry("survey_rock", (0.0, 1.0))
        else:
            _c = (pos_actions.get(off_pos) or {}).get("coords") or {}
            motion[str(pid)] = _entry(
                "jab", _unit(bh_x - float(_c.get("x", 50.0)), bh_y - float(_c.get("y", 25.0)))
            )

    # Defense — role from the offensive player each defender guards (man matchup). Zone has no
    # matchup here → perimeter shuffle (paired post-D physics lands in v1.1).
    for def_pos, player in (def_lineup or {}).items():
        pid = getattr(player, "player_id", None)
        if pid is None:
            continue
        guarded_off_pos = next((o for o, d in (off_to_def or {}).items() if d == def_pos), None)
        if guarded_off_pos and is_inside_location(locations.get(guarded_off_pos)):
            motion[str(pid)] = _entry("jockey", (basket_sign_x, 0.0))
        else:
            motion[str(pid)] = _entry("shuffle", (0.0, 1.0))

    return motion


def _stamp_final_turn_idle_motion(
    skeleton, off_lineup, def_lineup, bh_pos, position_to_spot, is_away_offense, rng
):
    """Stamp cosmetic ``idle_wander`` idle motion on the two stationary Final Turn
    beats — step 0 (alignment hold) and step 1 (off-ball players stand while the
    BH passes / the shooter receives). Reuses ``_roll_subtle_idle_motion``,
    resolving each player's coords from that beat's spot locations
    (``HCO_STRING_SPOTS``, away-flipped) into a throwaway beat copy so the
    direction math reads correctly WITHOUT mutating the skeleton's ``pos_actions``.
    Final Turn defense is zone → no man matchup passed (defenders shuffle).
    Render-only + UESS-safe; call AFTER ``resolve_shot`` so the idle RNG never
    perturbs the shot outcome."""
    from BackEnd.constants import HCO_STRING_SPOTS
    from BackEnd.utils.shared import get_away_player_coords

    steps = (skeleton or {}).get("steps") or []
    for beat in steps[:2]:
        pos_actions = beat.get("pos_actions") or {}
        locations, temp_pa = {}, {}
        for pos, info in pos_actions.items():
            loc = (info or {}).get("location", "key")
            locations[pos] = loc
            coords = HCO_STRING_SPOTS.get(loc, {"x": 64, "y": 25})
            temp_pa[pos] = {
                **(info or {}),
                "coords": get_away_player_coords(coords) if is_away_offense else dict(coords),
            }
        idle = _roll_subtle_idle_motion(
            {"pos_actions": temp_pa},
            off_lineup,
            def_lineup,
            bh_pos,
            position_to_spot.get(bh_pos, "key"),
            {},  # zone defense → no man matchup
            locations,
            is_away_offense,
            rng,
        )
        if idle:
            beat.setdefault("_subtle_movement", {})["idle_motion"] = idle


# HCO-specific moment frequency dial: scales the HCT contest's p_event + p_dfoul for HCO ONLY
# (HCT/FCP keep event_scalar=1.0). Lower = fewer HCO fouls/steals/turnovers. The HCT contest is
# calibrated for traps (2 defenders); HCO is a single on-ball defender, so we scale it back.
HCO_MOMENT_SCALAR = 0.5        # man-defense per-moment event-frequency dial (HCO-only)
HCO_ZONE_MOMENT_SCALAR = 0.5   # zone-defense dial (defaults equal to man; tune zone independently)

# Per-turn moment ENGAGEMENT by defense aggression (0-4) → % of possessions the defense attempts
# any steal/foul/TO contest. HCO man + zone only (HCT/FCP contest every step). Lower = fewer
# possessions with any moment. Distinct from conversion (HCO_*_MOMENT_SCALAR) and from the
# subtle-movement/defense-pressure gates (those keep the flat randint(0,4) <= slider form).
MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION = {0: 5, 1: 20, 2: 35, 3: 50, 4: 75}

# HCO passing-lane perpendicular distance by defense aggression_call (Dynamic_HCO_System §4).
# Tighter than HCT/FCP (8.0) — closer half-court spacing + faster passes. Normal tempo is rolled
# once per game (randint 5-6) and cached in game_state (stable all game; no per-pass roll).
HCO_PASS_LANE_DIST_BY_AGGRESSION = {"passive": 6.0, "aggressive": 5.0}

# Dynamic HCO Defense — Gate 2 (Dynamic_MM_Brief §5C). When a defender is geometrically in a pass
# lane (Gate 1), his chance to ATTEMPT the interception is set by defense aggression_call. Applied
# only when the dynamic-defense flag is on (posture set); passive never gambles. Gate 3 (the
# attribute contest in resolve_pass_contest) then decides if an attempt actually picks it.
INTERCEPT_ATTEMPT_PCT_BY_CALL = {"aggressive": 80, "normal": 40, "passive": 0}

# Dynamic HCO Defense — HCO-specific pass-contest calibration (owner spec 2026-07-10). Shared
# resolve_pass_contest defaults (HCT/FCP) are BASE=200 / HI=250 / MID=200, left untouched. HCO folds
# team efficiency into BOTH the composite and the bar/tiers (efficiency_in_composite=True):
#   3a pass_score  = ((PS·0.6 + CH·0.2 + IQ·0.2) + offensive_efficiency) × rand(1,6)
#      bar         = HCO_PASS_SAFETY_BASE − offensive_efficiency
#   3b intercept   = ((OD·0.6 + CH·0.2 + IQ·0.2) + defensive_efficiency) × rand(1,6)
#      tier_hi/mid = (HCO_PASS_INTERCEPT_TIER_HI/MID) − defensive_efficiency
HCO_PASS_SAFETY_BASE = 175.0
HCO_PASS_INTERCEPT_TIER_HI = 200.0
HCO_PASS_INTERCEPT_TIER_MID = 170.0


def _hco_pass_lane_dist(game):
    """HCO hot-read/kickout passing-lane distance: passive→6, aggressive→5, normal→randint(5,6)
    rolled ONCE per game and cached in game_state['_hco_pass_lane_dist_normal']."""
    import random
    game_state = game.game_state
    def_call = (getattr(game.defense_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    fixed = HCO_PASS_LANE_DIST_BY_AGGRESSION.get(def_call)
    if fixed is not None:
        return fixed
    cached = game_state.get("_hco_pass_lane_dist_normal")
    if cached is None:
        cached = float(random.randint(5, 6))
        game_state["_hco_pass_lane_dist_normal"] = cached
    return cached


def _hco_step_def_xy(step, bh_pos, off_lineup, def_lineup, off_to_def,
                     is_away_offense, def_aggr, zone, defense_playcall, posture=None):
    """Reconstruct on-court defender coords for a step (def_pos → {x,y}) the same way the animator
    renders them, plus readers + a point transform for lane geometry. MAN → get_defender_coords
    (returns input orientation → display); ZONE → assign_all_zone_defenders (always HOME), so the
    transform flips offensive points to home to match. Returns (def_xy, _coord, _loc, _pt).

    ``posture`` (Dynamic HCO Defense) shades the MAN reconstruction to MATCH the animator's rendered
    placement (emitter-as-god) — so the intercept geometry sees deny defenders in the lane and loose
    defenders out of it. None → legacy placement. (Zone posture is a future zone-parity item.)"""
    from BackEnd.engine.attack_drive_clearance import _spot_display_coords
    pos_actions = step.get("pos_actions") or {}

    def _coord(pos):
        info = pos_actions.get(pos) or {}
        if info.get("coords"):
            return {"x": float(info["coords"]["x"]), "y": float(info["coords"]["y"])}
        return _spot_display_coords(info.get("location") or "key", is_away_offense)

    def _loc(pos):
        return (pos_actions.get(pos) or {}).get("location") or "key"

    bh_xy = _coord(bh_pos)
    bh_location = _loc(bh_pos)

    # Stage 1 (man) + Stage 2 (zone): prefer the render's ACTUAL defender placement, stamped on the
    # step pre-contest (compute_defender_grid = the animator's code). It's in the DISPLAY frame for
    # BOTH man and zone, and the offense coords (`_coord`) are already display frame, so the point
    # transform is identity — one unified frame, no HOME flip. This is what fixes the zone+away
    # contact_point mirror (the contest used to emit HOME-frame points that the render drew flipped).
    # Falls back to the legacy per-mode reconstruction (with its native frame) when no grid is stamped
    # (walk-time contest, or dynamic HCO disabled).
    stamped = ((step.get("_step_state") or {}).get("defense")) or {}
    stamped_xy = {dp: {"x": float(v["x"]), "y": float(v["y"])}
                  for dp, v in stamped.items()
                  if isinstance(v, dict) and "x" in v and def_lineup.get(dp)}
    if stamped_xy:
        def _pt(xy):
            return xy
        return stamped_xy, _coord, _loc, _pt

    if zone:
        # Legacy fallback: assign_all_zone_defenders returns HOME frame → flip offense to HOME.
        from BackEnd.utils.shared_defense import assign_all_zone_defenders
        from BackEnd.utils.shared import get_away_player_coords
        from BackEnd.engine.attack_drive_clearance import _zone_boundaries_for_spot
        offensive_players = [
            {"player_id": getattr(off_lineup[p], "player_id", None), "coords": _coord(p),
             "is_ball_handler": p == bh_pos, "spot": _loc(p)}
            for p in off_lineup if p in pos_actions and off_lineup.get(p)
        ]
        zb = _zone_boundaries_for_spot(defense_playcall, bh_location, is_away_offense)
        def_xy, _guard = assign_all_zone_defenders(
            zb, offensive_players, bh_xy, bh_location, def_aggr, is_away_offense)
        def_xy = def_xy or {}

        def _pt(xy):
            return get_away_player_coords(xy) if is_away_offense else xy
    else:
        # Legacy fallback: per-step man reconstruction (display frame → identity transform).
        from BackEnd.utils.shared_defense import get_defender_coords
        def_xy = {}
        for off_pos in off_lineup:
            if off_pos not in pos_actions:
                continue
            dpos = off_to_def.get(off_pos, off_pos)
            if not def_lineup.get(dpos):
                continue
            def_xy[dpos] = get_defender_coords(
                _coord(off_pos), is_away_offense, def_aggr, _loc(off_pos),
                ball_handler_coords=bh_xy, is_ball_handler=(off_pos == bh_pos), ball_spot=bh_location,
                posture=posture,
            )

        def _pt(xy):
            return xy

    return def_xy, _coord, _loc, _pt


def _hco_blocked_dish_targets(step, bh_pos, off_lineup, def_lineup, off_to_def,
                              is_away_offense, def_aggr, lane_dist, zone=False, defense_playcall=None,
                              posture=None):
    """Hot-read "truly open" gate (§4): positions whose BH→teammate passing lane is covered by a
    help defender — excluded as dish candidates so the offense won't dish into a covered lane.
    Each non-BH lane is tested with defenders_in_lane; the t-band (0.1–0.9) excludes the BH's and
    receiver's own covering defenders, so only a true lane-sitting help defender blocks.
    ``posture`` shades the defender reconstruction (Dynamic HCO Defense) so the offense's read
    matches the rendered placement."""
    from BackEnd.engine.pass_contest import defenders_in_lane

    pos_actions = step.get("pos_actions") or {}
    if bh_pos not in pos_actions:
        return set()
    def_xy, _coord, _loc, _pt = _hco_step_def_xy(
        step, bh_pos, off_lineup, def_lineup, off_to_def, is_away_offense, def_aggr, zone,
        defense_playcall, posture=posture)
    bh_pt = _pt(_coord(bh_pos))

    blocked = set()
    for recv_pos in off_lineup:
        if recv_pos == bh_pos or not off_lineup.get(recv_pos) or recv_pos not in pos_actions:
            continue
        exclude = set() if zone else {off_to_def.get(bh_pos, bh_pos), off_to_def.get(recv_pos, recv_pos)}
        if defenders_in_lane(bh_pt, _pt(_coord(recv_pos)), def_xy, lane_dist, exclude=exclude):
            blocked.add(recv_pos)
    return blocked


def _track_hco_intercept_gates(game_state, in_lane, attempted, stage, pass_type="?"):
    """Diagnostic: accumulate the interception FUNNEL and log running per-game rates so we can see
    where passes are filtered — Gate 1 (defender in lane) → Gate 2 (aggression attempt) → Gate 3a
    (passer-safety evade) → Gate 3b (interceptor band: INTERCEPT / BAT_OOB / miss). Also breaks the
    funnel down by ``pass_type`` (motion / setplay / hot_read / dish / freelance) so we can spot
    per-type patterns. Pure observability; wrapped so a tracking error can never break a turn."""
    if game_state is None:
        return
    try:
        def _bump(d):
            d["passes"] += 1
            if in_lane:
                d["g1"] += 1
            if attempted:
                d["g2"] += 1
            if stage == "passer_safe":
                d["g3a_safe"] += 1
            elif stage == "intercept":
                d["g3b_int"] += 1
            elif stage == "bat_oob":
                d["g3b_bat"] += 1
            elif stage in ("band_complete", "no_contester"):
                d["g3b_miss"] += 1
        _new = lambda: {"passes": 0, "g1": 0, "g2": 0, "g3a_safe": 0,
                        "g3b_int": 0, "g3b_bat": 0, "g3b_miss": 0}
        g = game_state.setdefault("_hco_intercept_gates", _new())
        by_type = game_state.setdefault("_hco_intercept_gates_by_type", {})
        _bump(g)
        _bump(by_type.setdefault(pass_type, _new()))
        n, g1, g2 = g["passes"], g["g1"], g["g2"]
        _r = lambda a, b: f"{100.0 * a / b:.0f}%" if b else "—"
        # compact per-type tail: type=passes·g1·g2·INT·BAT
        types_s = " ".join(
            f"{k}={d['passes']}·{d['g1']}·{d['g2']}·{d['g3b_int']}·{d['g3b_bat']}"
            for k, d in sorted(by_type.items()))
        logging.warning(
            "🚪 [INTERCEPT GATES] passes=%d | G1 in-lane %d (%s) | G2 attempt %d (%s of in-lane) | "
            "G3a passer-safe %d (%s of attempts) | G3b: INT=%d BAT=%d miss=%d | "
            "by-type[p·g1·g2·INT·BAT]: %s [is_full_sim=%s]",
            n, g1, _r(g1, n), g2, _r(g2, g1), g["g3a_safe"], _r(g["g3a_safe"], g2),
            g["g3b_int"], g["g3b_bat"], g["g3b_miss"], types_s, game_state.get("_is_full_simulation"))
    except Exception:
        pass


def _hco_resolve_dish_contest(step, bh_pos, recv_pos, off_lineup, def_lineup, off_to_def,
                              is_away_offense, def_aggr, lane_dist, zone, defense_playcall, off_team, rng,
                              posture=None, game_state=None, pass_type="?"):
    """Stage 2 (§4): resolve a THROWN hot-read dish / kickout through the passing lane. Reuses the
    shared HCT pass model (resolve_pass_contest) with the tighter HCO ``lane_dist``. Eligible
    interceptors = lane-sitting help defenders + the receiver's own man (t-band 0.1..1.0; the
    passer's on-ball man at t≈0 is excluded). Since the decision gate already cleared the 0.1–0.9
    band, the contest mostly catches the receiver's man gambling on the catch + marginal/temporal
    cases. Returns {outcome, deflector, contact_point} — COMPLETE / INTERCEPT / BAT_OOB."""
    from BackEnd.engine.pass_contest import (
        defenders_in_lane, resolve_pass_contest, resolve_offense_pass_modifier, COMPLETE,
    )
    from BackEnd.engine.dynamic_hct import PASS_GRID_PER_GAME_SEC
    from BackEnd.utils.shared import ag_to_grid_per_game_sec

    def_xy, _coord, _loc, _pt = _hco_step_def_xy(
        step, bh_pos, off_lineup, def_lineup, off_to_def, is_away_offense, def_aggr, zone,
        defense_playcall, posture=posture)
    passer_xy = _pt(_coord(bh_pos))
    receiver_xy = _pt(_coord(recv_pos))
    # Gate 1 — eligible interceptors: in-lane (perp <= lane_dist) with projection past the passer
    # (t > 0.1), including the receiver end (<= 1.0). The passer's OWN defender is never eligible —
    # exclude him by POSITION (not just t≈0) so posture sag can't drift him into the outgoing lane
    # and "pick"/bat his own man's pass. MAN → the matchup defender. ZONE → the on-ball zone defender
    # (`_zone_bh_defender`: whose zone polygon covers the passer's spot), mapped back to its lineup key.
    if zone:
        _zbd = _zone_bh_defender(defense_playcall, _loc(bh_pos), is_away_offense, def_lineup, bh_pos)
        _zbd_pos = next((dp for dp, p in def_lineup.items() if p is _zbd), None)
        _passer_def = {_zbd_pos} if _zbd_pos else set()
    else:
        _passer_def = {off_to_def.get(bh_pos, bh_pos)}
    eligible_g1 = defenders_in_lane(passer_xy, receiver_xy, def_xy, lane_dist, t_min=0.1, t_max=1.0,
                                    exclude=_passer_def)
    # Gate 2 — Dynamic HCO Defense (posture set): each in-lane defender only ATTEMPTS the pick per
    # defense aggression_call (aggressive 80 / normal 40 / passive 0). Non-attempters drop out;
    # if none commit, the pass completes. Legacy path (posture None) contests every eligible.
    eligible = eligible_g1
    if posture:
        pct = INTERCEPT_ATTEMPT_PCT_BY_CALL.get(def_aggr, 40)
        eligible = [dpos for dpos in eligible_g1 if rng.randint(1, 100) <= pct]
    if not eligible:
        _track_hco_intercept_gates(game_state, bool(eligible_g1), False, None, pass_type)
        return {"outcome": COMPLETE, "deflector": None, "contact_point": None}

    defenders = []
    for dpos in eligible:
        d = def_lineup.get(dpos)
        if d is None:
            continue
        da = getattr(d, "attributes", None) or {}
        defenders.append({
            "id": dpos, "xy": def_xy[dpos], "rate": ag_to_grid_per_game_sec(da.get("AG", 50)),
            "OD": da.get("OD", 50), "CH": da.get("CH", 50), "IQ": da.get("IQ", 50),
        })
    passer = off_lineup.get(bh_pos)
    pa = getattr(passer, "attributes", None) or {}
    passer_desc = {"xy": passer_xy, "PS": pa.get("PS", 50), "CH": pa.get("CH", 50), "IQ": pa.get("IQ", 50)}
    offense_modifier = resolve_offense_pass_modifier("HCO", getattr(off_team, "team_attributes", None))
    # Defense modifier = defending team's defensive_efficiency (stashed at HCO entry). Folded into
    # the interceptor composite AND subtracted from the tiers (see HCO_PASS_* constants).
    defense_modifier = float((game_state or {}).get("_hco_def_efficiency", 0.0) or 0.0)
    result = resolve_pass_contest(
        passer_desc, receiver_xy, PASS_GRID_PER_GAME_SEC, defenders,
        offense_modifier=offense_modifier, defense_modifier=defense_modifier,
        lane_dist=lane_dist, rng=rng, safety_base=HCO_PASS_SAFETY_BASE,
        tier_hi=HCO_PASS_INTERCEPT_TIER_HI, tier_mid=HCO_PASS_INTERCEPT_TIER_MID,
        efficiency_in_composite=True)
    _track_hco_intercept_gates(game_state, True, True, result.get("stage"), pass_type)
    return result


def _hco_contest_skeleton_pass(step, output_steps, skeleton, off_lineup, def_lineup, off_to_def,
                               is_away_offense, def_aggr, lane_dist, zone, game_state, off_team, rng,
                               pass_type="motion"):
    """Dynamic HCO Defense (P2b): contest a SKELETON ball-movement / reversal pass via the two-gate
    model (reuses `_hco_resolve_dish_contest` — skeleton steps carry named locations, so the posture
    reconstruction is accurate). Returns a STEAL turnover result (``pass_intercepted``) if the pass is
    picked, else None (pass proceeds). Flag-gated: no-op unless a defense posture is set."""
    posture = game_state.get("_hco_defense_posture")
    if not posture:
        return None
    pa = step.get("pos_actions") or {}
    passer = next((p for p, a in pa.items() if ((a or {}).get("action") or "").lower() == "pass"), None)
    receiver = next((p for p, a in pa.items() if ((a or {}).get("action") or "").lower() == "receive"), None)
    # Walk census (diagnostic): does the walk even SEE this pass step? Distinguishes "passes not in
    # the walked steps" (pass_same ≪ census passes → added downstream) from "split encoding at walk
    # time" (pass_seen ≫ pass_same). Pure observability.
    try:
        w = game_state.setdefault("_hco_walk_census", {"steps": 0, "pass_seen": 0, "pass_same": 0})
        w["steps"] += 1
        if passer:
            w["pass_seen"] += 1
            if receiver:
                w["pass_same"] += 1
    except Exception:
        pass
    if not passer or not receiver or not off_lineup.get(passer):
        return None
    step["_hco_contested"] = True  # tag so the final-skeleton coverage pass skips this step
    contest = _hco_resolve_dish_contest(
        step, passer, receiver, off_lineup, def_lineup, off_to_def, is_away_offense,
        def_aggr, lane_dist, zone, game_state.get("defense_playcall"), off_team, rng,
        posture=posture, game_state=game_state, pass_type=pass_type)
    if contest.get("outcome") not in ("INTERCEPT", "BAT_OOB"):
        return None
    logging.warning(
        f"🪡 [HCO PASS] {contest['outcome']} on SKELETON pass {passer}→{receiver} "
        f"by {contest.get('deflector')}")
    skeleton["steps"] = list(output_steps)
    return {
        "skeleton": skeleton,
        "pass_intercepted": True,
        "interceptor_pos": contest.get("deflector"),
        "pass_bat_oob": contest["outcome"] == "BAT_OOB",
        "pass_contact_point": contest.get("contact_point"),
        "passer_pos": passer,
        "shooter": off_lineup[passer],
        "shooter_pos": passer,
    }


def _stamp_contest_defender_grid(skeleton, game, off_lineup, def_lineup):
    """Stamp the render's ACTUAL defender placement (``compute_defender_grid`` = the animator's code)
    on each skeleton step as ``step["_step_state"]["defense"]``, so the interception contest
    (`_hco_step_def_xy`) judges against what gets DRAWN — man and zone — instead of the drifting
    per-step hand reconstruction. Pure + sim-safe, so it runs pre-emit (the emit's exact stash isn't
    available yet — the contest still truncates the skeleton the emit draws; ~2px RNG from the literal
    draw, immaterial against the lane band). Idempotent (re-stamping refreshes). Called BEFORE the
    offense walk (so the walk-time contest reads it too) AND before the coverage pass (final skeleton,
    which may carry recalibrated/expanded steps the pre-walk stamp didn't cover). Wrapped so a stamping
    error can never break a turn."""
    try:
        steps = (skeleton or {}).get("steps") or []
        if not steps:
            return
        from BackEnd.models.animator import Animator
        grid = Animator(game).compute_defender_grid(skeleton, off_lineup, def_lineup)
        for i, step in enumerate(steps):
            ss = step.get("_step_state") or {"index": i}
            ss["defense"] = grid.get(i) or {}
            step["_step_state"] = ss
    except Exception:
        pass


def _hco_contest_final_skeleton(motion_shot_info, game, off_lineup, def_lineup, game_state):
    """Coverage (Dynamic HCO Defense): contest every pass step in the FINAL resolved skeleton that the
    per-step resolver DIDN'T already contest (untagged) — catching passes built outside the walk
    (legacy resolver, shot-clock recalibration, intra-resolution expansion). Reuses the same two-gate
    contest via `_hco_contest_skeleton_pass`; on the FIRST pick (step order) it mutates
    ``motion_shot_info`` with the interception flags + truncated skeleton so the caller's existing
    ``pass_intercepted`` routing finalizes it identically to a walk pick. Flag-gated; no-op if the
    possession was already intercepted or has no posture set."""
    if not _dynamic_hco_defense_enabled():
        return
    if not motion_shot_info or motion_shot_info.get("pass_intercepted"):
        return
    posture = game_state.get("_hco_defense_posture")
    if not posture:
        return
    skeleton = motion_shot_info.get("skeleton") or {}
    steps = skeleton.get("steps") or []
    if not steps:
        return
    _stamp_contest_defender_grid(skeleton, game, off_lineup, def_lineup)
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
    import random as _rng
    off_team = game.offense_team
    is_away_offense = off_team.team_id == game.away_team.team_id
    zone = is_zone_defense(game_state.get("defense_playcall"))
    def_aggr = (getattr(game.defense_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    lane_dist = _hco_pass_lane_dist(game)
    off_to_def = {}
    if not zone:
        matchups = get_matchups_for_defending_team(
            game_state, getattr(game.defense_team, "is_user_team", False))
        off_to_def = {o: d for d, o in matchups.items()}
    ptype = "setplay" if (game_state.get("offense_play_type") or "") == "set_play" else "motion"
    # Snapshot the step list — a pick truncates skeleton["steps"], so iterate a stable copy.
    for i, step in enumerate(list(steps)):
        if step.get("_hco_contested"):
            continue
        pick = _hco_contest_skeleton_pass(
            step, steps[:i + 1], skeleton, off_lineup, def_lineup, off_to_def, is_away_offense,
            def_aggr, lane_dist, zone, game_state, off_team, _rng, pass_type=ptype)
        if pick is not None:
            motion_shot_info["pass_intercepted"] = True
            motion_shot_info["interceptor_pos"] = pick["interceptor_pos"]
            motion_shot_info["pass_bat_oob"] = pick["pass_bat_oob"]
            motion_shot_info["pass_contact_point"] = pick["pass_contact_point"]
            motion_shot_info["passer_pos"] = pick["passer_pos"]
            motion_shot_info["skeleton"] = pick["skeleton"]
            return


def _hco_last_pass_step_index(steps):
    """Index of the last skeleton step carrying a ``pass`` action (the interception point). None if
    no pass step is found. Used to pin the steal/bat-OOB stopper to the actual pass, not a mid step."""
    for i in range(len(steps) - 1, -1, -1):
        pa = (steps[i] or {}).get("pos_actions") or {}
        if any(((a or {}).get("action") or "").lower() == "pass" for a in pa.values()):
            return i
    return None


def _hco_uncatch_receiver_on_pass(steps, pass_idx):
    """On an INTERCEPTED / batted pass the ball must NEVER complete to the offensive receiver — it's
    picked off in flight. Downgrade the receiver's ``receive`` to ``cut`` at the pass step so the
    ball-owner walk keeps the ball with the passer (the steal / OOB step then routes it directly to
    the interceptor). Without this the ball briefly attaches to the receiver, then jumps to the
    defender — the "attached to the receiver first" bug."""
    if pass_idx is None or not (0 <= pass_idx < len(steps)):
        return
    for info in ((steps[pass_idx] or {}).get("pos_actions") or {}).values():
        if ((info or {}).get("action") or "").lower() == "receive":
            info["action"] = "cut"


def _finalize_hco_pass_interception(motion_shot_info, game, roles, off_lineup, def_lineup, game_state):
    """§4 Stage 2: convert an intercepted HCO dish/kickout into a STEAL turnover. ``is_interception``
    drives the FE's INTERCEPTION! headline + SFX. Reuses resolve_turnover_logic + the shared stopper
    system (same tools as the per-step Moment / FCP / rim-runner) so the turnover contract matches."""
    interceptor = def_lineup.get(motion_shot_info.get("interceptor_pos"))
    # The victim = the actual passer. For a freelance pass the ball may have changed hands mid-cycle,
    # so prefer the result's passer_pos; dishes fall back to the turn's ball handler.
    _passer_pos = motion_shot_info.get("passer_pos")
    ball_handler = off_lineup.get(_passer_pos) if _passer_pos else roles.get("ball_handler")
    # Pin the steal to the ACTUAL pass step (where the ball was picked), not a random mid step.
    _src = motion_shot_info.get("skeleton") or {}
    _steps = (_src or {}).get("steps") or []
    _pi = _hco_last_pass_step_index(_steps)
    if _pi is not None:
        game_state["_hco_pass_intercept_stop_index"] = _pi
        _hco_uncatch_receiver_on_pass(_steps, _pi)  # ball goes passer→interceptor, never the receiver
    try:
        skel = apply_stopper_system_to_skeleton(_src, "STEAL", game_state)
    finally:
        game_state.pop("_hco_pass_intercept_stop_index", None)
    # B1 — make the pick READ as an interception (all backend, UESS): the deflector STEPS to the
    # contact point on the stop step (per-step defender override — the animator tweens him there from
    # his posture spot), and the ball ATTACHES to him there by seeding last_stealer_coords (the steal
    # path renders the ball moving to the stealer's coords). Man defense only; falls back gracefully.
    _contact = motion_shot_info.get("pass_contact_point")
    _dpos = motion_shot_info.get("interceptor_pos")
    if _contact and _dpos and isinstance(skel, dict) and skel.get("steps"):
        _cc = {"x": float(_contact["x"]), "y": float(_contact["y"])}
        game_state["last_stealer_coords"] = _cc
        _stop = skel["steps"][-1]
        _stop.setdefault("_attack_drive", {}).setdefault("defender_overrides", {})[_dpos] = {
            "coords": _cc, "action": "steal_reach",
        }
        # Ball animation: make the interceptor OWN the ball on the stop step so it TWEENS from the
        # passer to the contact point (was teleporting — the ball stayed with the offense the whole
        # skeleton and only jumped to the stealer at the next possession via last_stealer_coords).
        # The passer gives it up ("pass", not the stopper's "handle_ball") so the animator's
        # ball-owner walk falls through to the steal event, which now carries the stealer's id.
        if _passer_pos and _passer_pos in (_stop.get("pos_actions") or {}):
            _stop["pos_actions"][_passer_pos]["action"] = "pass"
        _iid = getattr(interceptor, "player_id", None)
        if _iid:
            _evs = _stop.setdefault("events", [])
            _steal_ev = next((_ev for _ev in _evs if _ev.get("type") == "steal"), None)
            if _steal_ev is None:
                _steal_ev = {"type": "steal"}
                _evs.append(_steal_ev)
            _steal_ev["stealer_id"] = _iid
    to_roles = dict(roles)
    to_roles["ball_handler"] = ball_handler
    to_roles["defender"] = interceptor
    if isinstance(skel, dict) and skel.get("steps"):
        to_roles["steps"] = skel["steps"]
    turn_result = resolve_turnover_logic(to_roles, game, turnover_type="STEAL", from_resolution_system=True)
    turn_result["is_interception"] = True
    turn_result["current_turn"] = "HCO"
    turn_result["skeleton"] = skel or {}
    steps = (skel or {}).get("steps") or []
    if steps:
        timing = calc_skeleton_step_timing_contract(
            steps, resolution_step_index=max(0, len(steps) - 1),
            include_hco_step1_bringup=True, phase_type="HCO", off_lineup=game.offense_team.lineup,
        )
        turn_result["time_elapsed"] = timing["time_elapsed"]
        turn_result["step_clock_seconds"] = timing["step_clock_seconds"]
        turn_result["resolution_step_index"] = timing["resolution_step_index"]
        turn_result["executed_step_count"] = timing["executed_step_count"]
    logging.warning(
        f"🪡 [HCO INTERCEPTION] {getattr(ball_handler, 'player_id', None)} dish picked off by "
        f"{getattr(interceptor, 'player_id', None)} → STEAL "
        f"[game={game_state.get('game_id')} is_full_sim={game_state.get('_is_full_simulation')}]")
    return turn_result


def _finalize_hco_pass_bat_oob(motion_shot_info, game, roles, off_lineup, def_lineup, game_state):
    """§14 (HCO) — a batted-out-of-bounds pass is NOT a turnover: the defender is the last to touch,
    so the OFFENSE RETAINS. Transition to a side inbound (SIP; clocks pinned → no shot-clock reset),
    with NO steal/TO stats and no secondary announce. Deflector + contact carried for the (Layer B)
    UESS batted-OOB animation. Distinct from _finalize_hco_pass_interception (INTERCEPT → STEAL)."""
    deflector = def_lineup.get(motion_shot_info.get("interceptor_pos"))
    _passer_pos = motion_shot_info.get("passer_pos")
    ball_handler = off_lineup.get(_passer_pos) if _passer_pos else roles.get("ball_handler")
    off_team = game.offense_team
    # Stop the skeleton at the actual pass step (offense retains — dead ball, not a steal).
    _src = motion_shot_info.get("skeleton") or {}
    _steps = (_src or {}).get("steps") or []
    _pi = _hco_last_pass_step_index(_steps)
    if _pi is not None:
        game_state["_hco_pass_intercept_stop_index"] = _pi
        _hco_uncatch_receiver_on_pass(_steps, _pi)  # ball is batted away, never completes to receiver
    try:
        skel = apply_stopper_system_to_skeleton(_src, "DEAD_BALL_TURNOVER", game_state)
    finally:
        game_state.pop("_hco_pass_intercept_stop_index", None)
    to_roles = dict(roles)
    to_roles["ball_handler"] = ball_handler
    to_roles["defender"] = deflector
    # `action_timeline` / `touch_counts` are internal tallies keyed by Player OBJECTS. convert_players
    # only converts dict VALUES, not keys, so these survive to JSONResponse and crash it ("keys must
    # be str… not Player"). The FE needs the serializable role/step fields, not these — strip them.
    to_roles.pop("action_timeline", None)
    to_roles.pop("touch_counts", None)
    game_state["offensive_state"] = "HCO"  # resume in HCO after the side inbound
    turn_result = {
        "result_type": "DEAD BALL",
        "turnover_type": "",               # NOT a turnover
        "current_turn": "HCO",
        "text": "The pass is batted out of bounds — offense keeps it.",
        "possession_flips": False,         # offense retains (defender last to touch)
        "next_play_type": "SIDE_INBOUND",
        "next_turn": "SIDE_INBOUND",
        "offense_team_id": off_team.team_id,
        # Layer A ships the correct OUTCOME only. bat_oob stays False so the existing (broken-timing,
        # non-UESS) FE ball-send + secondary announce do NOT fire. Layer B flips this on and emits the
        # UESS batted-OOB animation. Contact + deflector are carried now so Layer B can use them.
        "bat_oob": False,
        "bat_oob_contact": motion_shot_info.get("pass_contact_point"),
        "bat_oob_deflector_id": getattr(deflector, "player_id", None),
        "victim_id": None,                 # no TO credited
        "defender_id": getattr(deflector, "player_id", None),
        "is_interception": False,
        "events": [],
        "roles": to_roles,
        "skeleton": skel or {},
    }
    steps = (skel or {}).get("steps") or []
    if steps:
        timing = calc_skeleton_step_timing_contract(
            steps, resolution_step_index=max(0, len(steps) - 1),
            include_hco_step1_bringup=True, phase_type="HCO", off_lineup=off_team.lineup,
        )
        turn_result["time_elapsed"] = timing["time_elapsed"]
        turn_result["step_clock_seconds"] = timing["step_clock_seconds"]
        turn_result["resolution_step_index"] = timing["resolution_step_index"]
        turn_result["executed_step_count"] = timing["executed_step_count"]
    logging.warning(
        f"🪣 [HCO BAT-OOB] pass by {getattr(ball_handler, 'player_id', None)} batted OOB by "
        f"{getattr(deflector, 'player_id', None)} → offense retains (side inbound, no reset, no stats)")
    return turn_result


def _track_hco_pass_census(result, game):
    """Diagnostic: census of EVERY HCO turn's passes vs how many were contestable, to explain the
    gap between total HCO passes and the `🚪 [INTERCEPT GATES]` funnel. Runs for ALL HCO turns
    (motion / set / iso / non-shot), unlike `📏` (motion-only). Per turn counts pass steps in the
    FINAL result skeleton, splits them into `same` (pass+receive in ONE step → the contest hook can
    see it) vs `split` (pass action but no same-step receive → hook skips), and tags the play type +
    whether a dynamic walk even ran (event=SHOT, posture set). Accumulates a running game total, tags
    is_full_sim. Pure observability; wrapped by the caller so it can never break a turn."""
    gs = game.game_state
    steps = ((result or {}).get("skeleton") or {}).get("steps") or []
    play_type = (gs.get("offense_play_type") or "?").lower()
    event_type = (result or {}).get("event_type") or (result or {}).get("result") or "?"
    posture = gs.get("_hco_defense_posture")
    same = split = 0
    for step in steps:
        pa = step.get("pos_actions") or {}
        has_pass = any(((a or {}).get("action") or "").lower() == "pass" for a in pa.values())
        if not has_pass:
            continue
        has_recv = any(((a or {}).get("action") or "").lower() == "receive" for a in pa.values())
        if has_recv:
            same += 1
        else:
            split += 1
    c = gs.setdefault("_hco_pass_census",
                      {"turns": 0, "passes": 0, "same": 0, "split": 0, "by_type": {}})
    c["turns"] += 1
    c["passes"] += same + split
    c["same"] += same
    c["split"] += split
    bt = c["by_type"]
    bt[play_type] = bt.get(play_type, 0) + same + split
    by_type_s = " ".join(f"{k}={v}" for k, v in sorted(bt.items()))
    w = gs.get("_hco_walk_census") or {}
    logging.warning(
        "🧮 [HCO PASS CENSUS] game: turns=%d passes=%d (same=%d split=%d) | by-type: %s | "
        "walk-saw: steps=%d pass_seen=%d pass_same=%d | "
        "this-turn: type=%s passes=%d event=%s posture=%s [is_full_sim=%s]",
        c["turns"], c["passes"], c["same"], c["split"], by_type_s,
        w.get("steps", 0), w.get("pass_seen", 0), w.get("pass_same", 0),
        play_type, same + split, event_type, posture, gs.get("_is_full_simulation"))


def _track_hco_pass_lanes(result, game):
    """Diagnostic (§4 calibration): for every pass step in a resolved HCO motion turn, log the
    closest non-BH defender's perpendicular distance to the pass lane — **mid-lane help** (t 0.1–0.9,
    the "truly open" gate band) AND **full-eligible** (t 0.1–1.0, the contest band incl. the
    receiver's man). Accumulates in game_state and logs the running GAME totals each turn, so the
    last HCO turn's line is the game summary (total passes + overall averages). Pure observability;
    behind GOB_DYNAMIC_HCO_MOTION; wrapped by the caller so it can never break a turn."""
    if not _dynamic_hco_motion_enabled():
        return
    game_state = game.game_state
    if (game_state.get("offense_play_type") or "") != "motion":
        return
    steps = ((result or {}).get("skeleton") or {}).get("steps") or []
    if not steps:
        return
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
    from BackEnd.engine.pass_contest import min_perp_in_lane

    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    defense_playcall = game_state.get("defense_playcall")
    zone = is_zone_defense(defense_playcall)
    def_aggr = (getattr(game.defense_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    off_to_def = {}
    if not zone:
        matchups = get_matchups_for_defending_team(game_state, getattr(game.defense_team, "is_user_team", False))
        off_to_def = {o: d for d, o in matchups.items()}

    turn_samples = []
    for step in steps:
        pa = step.get("pos_actions") or {}
        passer_pos = next((p for p, a in pa.items() if ((a or {}).get("action") or "").lower() == "pass"), None)
        receiver_pos = next((p for p, a in pa.items() if ((a or {}).get("action") or "").lower() == "receive"), None)
        if not passer_pos or not receiver_pos:
            continue
        try:
            def_xy, _coord, _loc, _pt = _hco_step_def_xy(
                step, passer_pos, off_lineup, def_lineup, off_to_def, is_away_offense, def_aggr, zone,
                defense_playcall, posture=game_state.get("_hco_defense_posture"))
            passer_xy, receiver_xy = _pt(_coord(passer_pos)), _pt(_coord(receiver_pos))
            mid = min_perp_in_lane(passer_xy, receiver_xy, def_xy, 0.1, 0.9)
            full = min_perp_in_lane(passer_xy, receiver_xy, def_xy, 0.1, 1.0)
            turn_samples.append((round(mid, 1) if mid is not None else None,
                                 round(full, 1) if full is not None else None))
        except Exception:
            continue

    if not turn_samples:
        return
    t = game_state.setdefault("_hco_pass_lane_tracking",
                              {"count": 0, "mid_sum": 0.0, "mid_n": 0, "full_sum": 0.0, "full_n": 0})
    for mid, full in turn_samples:
        t["count"] += 1
        if mid is not None:
            t["mid_sum"] += mid
            t["mid_n"] += 1
        if full is not None:
            t["full_sum"] += full
            t["full_n"] += 1
    mid_s = f"{t['mid_sum'] / t['mid_n']:.2f}" if t["mid_n"] else "n/a"
    full_s = f"{t['full_sum'] / t['full_n']:.2f}" if t["full_n"] else "n/a"
    logging.warning(
        f"📏 [HCO PASS LANES] this turn (mid/full)={turn_samples} | GAME: passes={t['count']} "
        f"mid_avg={mid_s} (n={t['mid_n']}) full_avg={full_s} (n={t['full_n']}) "
        f"[is_full_sim={game_state.get('_is_full_simulation')}]")


def _resolve_hco_moment(game, ball_handler, bh_defender, event_scalar=None):
    """HCO per-step foul/steal/turnover moment — reuses the HCT attribute contest
    (`_resolve_moment`, same HCT_D8_* levels) but feeds HCO's team modifiers (offensive /
    defensive efficiency) in place of the HCT pressure ratings, and scales event frequency by
    ``event_scalar`` (defaults to HCO_MOMENT_SCALAR; the walk passes HCO_ZONE_MOMENT_SCALAR for
    zone). Returns the raw HCT outcome tuple ``(outcome, score_ratio, credited_player)`` — outcome
    ∈ {STEAL, DEAD BALL, O_FOUL, D_FOUL, POS_O, NEUTRAL}; the caller maps hard outcomes to HCO
    result types and truncates the walk. All logic + RNG stays backend-side (SS&S); FE only renders."""
    from BackEnd.engine.dynamic_hct import _resolve_moment
    off_team = game.offense_team
    def_team = game.defense_team
    off_eff = (getattr(off_team, "team_attributes", {}) or {}).get("offensive_efficiency", 0)
    def_eff = (getattr(def_team, "team_attributes", {}) or {}).get("defensive_efficiency", 0)
    if event_scalar is None:
        event_scalar = HCO_MOMENT_SCALAR
    return _resolve_moment(off_team, def_team, ball_handler, bh_defender,
                           def_mod=def_eff, off_mod=off_eff, event_scalar=event_scalar)


def _zone_bh_defender(defense_playcall, bh_location, is_away_offense, def_lineup, bh_pos):
    """On-ball ZONE defender at a step: the defender whose zone polygon contains the ball-handler's
    spot (mirrors attack_drive's ``bh_zone_def``). Falls back to the nearest zone (by polygon
    centroid, compared in the polygons' home space) and finally to the position-on-position
    defender. Used by the per-step moment when the defense is in a zone (no 1:1 man matchup)."""
    from BackEnd.engine.attack_drive_clearance import (
        _zone_boundaries_for_spot, _defender_for_zone_point, _closest_defender_to_point,
        _spot_display_coords,
    )
    loc = bh_location or "key"
    zb = _zone_boundaries_for_spot(defense_playcall, loc, is_away_offense)
    bh_coord = _spot_display_coords(loc, is_away_offense)
    dpos = _defender_for_zone_point(zb, bh_coord, is_away_offense)
    if dpos is None and zb:
        # Nearest-zone fallback: polygons live in home space, so flip the point to match.
        from BackEnd.utils.shared import get_away_player_coords
        pt = get_away_player_coords(bh_coord) if is_away_offense else bh_coord
        centroids = {}
        for p, poly in zb.items():
            if poly:
                xs = [c[0] for c in poly]
                ys = [c[1] for c in poly]
                centroids[p] = {"x": sum(xs) / len(xs), "y": sum(ys) / len(ys)}
        dpos = _closest_defender_to_point(centroids, pt)
    return def_lineup.get(dpos) if dpos else def_lineup.get(bh_pos)


def _resolve_hco_moment_walk(skeleton, game, off_lineup, def_lineup, reach_in_tags=None):
    """Dynamic HCO per-step foul / steal / turnover moment — the HCT step-by-step moment migrated
    to HCO. Rolls the defense's per-turn moment engagement (aggression 0-4 → % via
    MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION), then walks the skeleton steps firing the attribute-driven moment (`_resolve_hco_moment`) for
    the ball handler vs his MAN defender. Returns the HCO ``result_type`` of the FIRST hard
    outcome (``O_FOUL`` / ``D_FOUL`` / ``STEAL`` / ``DEAD_BALL_TURNOVER``) or None (no moment →
    normal shot resolution). The caller sets ``result`` to this so the existing non-shot
    resolution + stopper system render and route it (no new emission path needed).

    Reach-in micro-movement (option B — every contested step of an engaged turn): when
    ``reach_in_tags`` (a list) is passed, each NON-terminal contest (NEUTRAL near-miss / POS_O
    blow-by) appends ``(step_index, on_ball_defender_id)`` so the caller stamps a render-space
    ``reach_in`` flourish there — the defender's failed steal attempt. Terminal outcomes get
    their reach-in via the stopper step instead. The walk only READS the skeleton (never mutates
    it — tags are applied by the caller post-deepcopy), so the cached skeleton is untouched.

    Defense: MAN → ball-handler's matchup defender; ZONE → the defender whose zone polygon covers
    the BH's spot (`_zone_bh_defender`), scaled by HCO_ZONE_MOMENT_SCALAR. On a hard outcome the
    credited defender is stashed in ``game_state["_hco_moment_defender_id"]`` so the non-shot block
    credits / lunges the ACTUAL contesting defender (man position-match ≠ zone defender). The walk
    runs BEFORE shot resolution, so a moment pre-empts the would-be shot (true per-step interleaving
    is a later refinement). All logic + RNG backend-side (SS&S); FE only renders."""
    import random
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team

    game_state = game.game_state
    # Clear any stale moment-stop pin from a prior turn before we (maybe) set a fresh one below.
    # The pin tells apply_stopper WHICH step this moment fired at, so the foul/steal/turnover renders
    # where it happened instead of a random blast-radius step (the "ball snap-back" teleport).
    game_state.pop("_hco_moment_stop_index", None)
    steps = (skeleton or {}).get("steps") or []
    if len(steps) < 2:
        return None
    # Per-turn moment engagement: aggression (0-4) → % of possessions with any contest
    # (MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION). No engagement → no moment this turn.
    aggression = (getattr(game.defense_team, "strategy_settings", {}) or {}).get("aggression", 2)
    engage_pct = MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION.get(int(aggression), 35)
    if random.randint(1, 100) > engage_pct:
        return None

    defense_playcall = game_state.get("defense_playcall")
    zone = is_zone_defense(defense_playcall)
    is_away_offense = getattr(game.offense_team, "team_id", None) == getattr(
        getattr(game, "away_team", None), "team_id", None)
    event_scalar = HCO_ZONE_MOMENT_SCALAR if zone else HCO_MOMENT_SCALAR
    off_to_def = {}
    if not zone:
        defending_is_user = getattr(game.defense_team, "is_user_team", False)
        matchups = get_matchups_for_defending_team(game_state, defending_is_user)
        off_to_def = {off_pos: def_pos for def_pos, off_pos in matchups.items()}
    rt_map = {"STEAL": "STEAL", "DEAD BALL": "DEAD_BALL_TURNOVER",
              "O_FOUL": "O_FOUL", "D_FOUL": "D_FOUL"}
    for i in range(1, len(steps)):
        bh_pos, bh_loc = _motion_bh_at_step(steps[i])
        if not bh_pos or not off_lineup.get(bh_pos):
            continue
        if zone:
            bh_defender = _zone_bh_defender(defense_playcall, bh_loc, is_away_offense, def_lineup, bh_pos)
        else:
            bh_defender = def_lineup.get(off_to_def.get(bh_pos, bh_pos))
        if bh_defender is None:
            continue
        outcome, _ratio, _credited = _resolve_hco_moment(
            game, off_lineup[bh_pos], bh_defender, event_scalar=event_scalar)
        result_type = rt_map.get(outcome)
        if result_type:
            logging.warning(
                f"⚔️ [HCO MOMENT] {result_type} at step {i} ({bh_pos}, {'zone' if zone else 'man'})")
            # Stash the contesting defender so the non-shot block credits / lunges the actual one.
            game_state["_hco_moment_defender_id"] = getattr(_credited or bh_defender, "player_id", None)
            # Pin the stopper to THIS step so the outcome lands where the moment fired (not a random
            # blast-radius step). Mirrors the interception finalizer's _hco_pass_intercept_stop_index;
            # apply_stopper consumes it once. Covers steal/turnover AND foul moments.
            game_state["_hco_moment_stop_index"] = i
            return result_type
        # Option B: no hard outcome (NEUTRAL near-miss / POS_O blow-by), but the on-ball defender
        # still lunged — record him so the caller stamps a render-space reach_in flourish here.
        if reach_in_tags is not None:
            _rid = getattr(bh_defender, "player_id", None)
            if _rid:
                reach_in_tags.append((i, _rid))
    return None


def _resolve_hco_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup, is_setplay=False):
    """Dynamic HCO per-step offense resolver — ONE implementation for Motion AND Set Play (unified
    2026-07-11; the two were ~255-line near-duplicates differing in a single behavioral fork).

    Walk the skeleton making per-step decisions: build the read map, then at each step run the
    universal ``should_shoot`` (shoot / hot-read dish), SM-precedence (defer the shot to work the
    ball), and the movement matrix (subtle / disruption / freelance). A shot decision terminates and
    appends its shot steps; non-shot decisions advance to the next skeleton step. If no shot fires by
    the end, force one at the last step. Same result contract as ``resolve_motion_offense_shot``, or
    ``None`` to defer to the legacy path.

    ``is_setplay`` gates the ONE behavioral difference: after a forced subtle where the BH then
    doesn't shoot/dish, a set play runs ``_setplay_recovery_roll`` (WON → resume the skeleton; LOST →
    forced ``_resolve_freelance``), modeling a broken-down set. Motion always resumes. Log labels use
    ``_kind`` accordingly."""
    import random
    from BackEnd.engine.motion_read_map import build_motion_read_map
    from BackEnd.engine.motion_step_decision import (
        decide_step_action, should_shoot, _choose_attack_or_outside, _step_locations,
        SHOOT, KICKOUT_SHOOT, HOT_READ_SHOOT, SUBTLE_MOVEMENT, FREELANCE_FORCED,
        SUBTLE_STEP_ELAPSED_BY_TEMPO, SUBTLE_FORCED_SHOT_PENALTY, sm_takes_precedence,
    )
    from BackEnd.engine.motion_subtle import build_subtle_beat
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team

    game_state = game.game_state
    off_team = game.offense_team
    is_away_offense = off_team.team_id == game.away_team.team_id
    _kind = "SETPLAY" if is_setplay else "MOTION"  # log labels only
    steps = skeleton.get("steps", [])
    if len(steps) < 2:
        return None

    # Option B: stamp the render's defender grid BEFORE the walk so the walk-time interception contest
    # (`_hco_contest_skeleton_pass` below) reads the SAME grid the coverage pass does — no reconstruction
    # seam. Coverage re-stamps the final skeleton afterward (idempotent).
    _stamp_contest_defender_grid(skeleton, game, off_lineup, def_lineup)

    read_map = build_motion_read_map(game, off_lineup, def_lineup)

    # Ball-handler defender: man → matchup defender; zone → None (no 1:1 assignment — the zone
    # mismatch already lives in the Step-1 read map; the zone defense_score model is a known
    # follow-up, see brief). decide_step_action handles None (team-fight-only defense_score).
    zone = is_zone_defense(game_state.get("defense_playcall"))
    off_to_def = {}
    if not zone:
        defending_is_user = getattr(game.defense_team, "is_user_team", False)
        matchups = get_matchups_for_defending_team(game_state, defending_is_user)
        off_to_def = {off_pos: def_pos for def_pos, off_pos in matchups.items()}

    shot_actions = {SHOOT, KICKOUT_SHOOT, HOT_READ_SHOOT}

    off_eff = (getattr(off_team, "team_attributes", {}) or {}).get("offensive_efficiency", 0)
    def_team = game.defense_team
    def_eff = (getattr(def_team, "team_attributes", {}) or {}).get("defensive_efficiency", 0)
    tempo = (getattr(off_team, "strategy_calls", {}) or {}).get("tempo_call", "normal")
    shot_clock_est = float(game_state.get("shot_clock_remaining", 30) or 30)
    # §4 hot-read "truly open" gate (man only for now): per-game lane distance + defense aggression.
    _hco_lane_dist = _hco_pass_lane_dist(game)
    _def_aggr_call = (getattr(def_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")

    # Turn-level read gating (brief: rolled ONCE per HCO turn). roll <= setting (both 0-4):
    #  - offense executes reads (subtle MOVEMENT) if its alterations roll clears;
    #  - defense executes pressure if its aggression roll clears.
    # NOTE: the shoot decision (should_shoot) is UNIVERSAL — it runs every step regardless of
    # these rolls (brief: decoupled from alterations). The rolls only gate the MOVEMENT matrix
    # (subtle / disruption). (For now this only gates Motion plays; Set Play reads are a follow-up.)
    alterations = (getattr(off_team, "strategy_settings", {}) or {}).get("alterations", 2)
    aggression = (getattr(def_team, "strategy_settings", {}) or {}).get("aggression", 2)
    offense_reads = random.randint(0, 4) <= alterations
    defense_pressure = random.randint(0, 4) <= aggression
    logging.warning(
        f"🎲 [DYNAMIC {_kind}] turn gate: offense_reads={offense_reads} "
        f"(alterations={alterations}) defense_pressure={defense_pressure} (aggression={aggression})"
    )

    def _apply_dish_contest(decision, result, step, passer_pos):
        """§4 Stage 2: if the executed decision threw a pass (dish/kickout), contest it. On an
        INTERCEPT/BAT_OOB flag the result so the caller converts it to a STEAL turnover. Self-shots
        (shooter == passer) are a no-op."""
        if not isinstance(result, dict):
            return result
        recv = decision.get("shooter_pos")
        if not recv or recv == passer_pos:
            return result
        _ptype = "hot_read" if decision.get("hot_read") else "dish"
        contest = _hco_resolve_dish_contest(
            step, passer_pos, recv, off_lineup, def_lineup, off_to_def, is_away_offense,
            _def_aggr_call, _hco_lane_dist, zone, game_state.get("defense_playcall"), off_team, random,
            posture=game_state.get("_hco_defense_posture"), game_state=game_state, pass_type=_ptype)
        if contest.get("outcome") in ("INTERCEPT", "BAT_OOB"):
            result["pass_intercepted"] = True
            result["interceptor_pos"] = contest.get("deflector")
            result["pass_bat_oob"] = contest["outcome"] == "BAT_OOB"
            result["pass_contact_point"] = contest.get("contact_point")
            logging.warning(
                f"🪡 [HCO PASS] {contest['outcome']} on dish {passer_pos}→{recv} "
                f"by {contest.get('deflector')}")
        # Tag the appended dish pass step so the final-skeleton coverage pass skips it.
        for _st in reversed((result.get("skeleton") or {}).get("steps") or []):
            if (((_st.get("pos_actions") or {}).get(passer_pos) or {}).get("action") or "").lower() == "pass":
                _st["_hco_contested"] = True
                break
        return result

    _skel_pass_type = "setplay" if (game_state.get("offense_play_type") or "") == "set_play" else "motion"
    output_steps = [steps[0]]  # always start at the skeleton's step 0
    for i in range(1, len(steps)):
        shot_clock_est -= _estimate_step_game_seconds(steps[i - 1], steps[i], off_lineup, is_away_offense)
        game_state["_hco_shot_clock_est"] = shot_clock_est  # at-attempt clock for the HCO shot-tier tally
        output_steps.append(steps[i])  # players arrive at skeleton step i
        # P2b: a skeleton ball-movement / reversal pass is interceptable (two-gate contest). A pick
        # returns a STEAL turnover (routed by the outer pass_intercepted check). Flag-gated inside.
        _skel_pass_to = _hco_contest_skeleton_pass(
            steps[i], output_steps, skeleton, off_lineup, def_lineup, off_to_def, is_away_offense,
            _def_aggr_call, _hco_lane_dist, zone, game_state, off_team, random, pass_type=_skel_pass_type)
        if _skel_pass_to is not None:
            return _skel_pass_to
        bh_pos, bh_location = _motion_bh_at_step(steps[i])
        if not bh_pos or not off_lineup.get(bh_pos):
            continue

        # 1. Universal shoot decision — runs BEFORE the movement matrix, every step, all
        # conditions. shoot/dish → execute (terminate); else fall through to movement.
        locations = _step_locations(steps[i])
        # §4 hot-read "truly open" gate: drop dish targets whose passing lane is covered (man + zone).
        blocked_dish = _hco_blocked_dish_targets(
            steps[i], bh_pos, off_lineup, def_lineup, off_to_def,
            is_away_offense, _def_aggr_call, _hco_lane_dist,
            zone=zone, defense_playcall=game_state.get("defense_playcall"),
            posture=game_state.get("_hco_defense_posture"))
        # SM-precedence: when the offense is reading this turn (offense_reads — the
        # per-turn alterations roll, reused, NOT a second roll) and the shot-clock
        # tier/tempo says "work the ball", subtle movement takes precedence over the
        # shoot decision — the BH defers his shot/hot-read and keeps the offense
        # moving. Precedence retreats as the clock drains / tempo speeds up.
        sm_precede = offense_reads and sm_takes_precedence(shot_clock_est, tempo)

        if not sm_precede:
            shoot = should_shoot(bh_pos, off_lineup, locations, read_map, off_team,
                                 shot_clock_est, tempo, random, openness=0.0, allow_dish=True,
                                 blocked_dish_targets=blocked_dish)
            if shoot:
                logging.warning(
                    f"🎯 [DYNAMIC {_kind}] step {i}: SHOOT {shoot['shooter_pos']} "
                    f"{shoot['shot_type']} (hot_read={shoot.get('hot_read')})"
                )
                _dec = {"action": SHOOT, "shooter_pos": shoot["shooter_pos"], "shot_type": shoot["shot_type"]}
                return _apply_dish_contest(_dec, _execute_motion_decision(
                    skeleton, output_steps, steps[i], bh_pos, bh_location, _dec,
                    game, off_lineup, def_lineup, is_away_offense,
                ), steps[i], bh_pos)

        # 2. Movement matrix. Under SM-precedence we force a subtle-movement beat
        # (reusing the branch below, incl. its <1s forced-shot backstop). Otherwise
        # the matrix runs only when the offense alters and/or the defense pressures;
        # neither engaged → static skeleton: just progress to the next step.
        if sm_precede:
            logging.warning(f"🟡 [DYNAMIC {_kind}] step {i}: SM-precedence → subtle movement")
            decision = {"action": SUBTLE_MOVEMENT}
        elif not offense_reads and not defense_pressure:
            continue
        else:
            bh_defender = None if zone else def_lineup.get(off_to_def.get(bh_pos, bh_pos))
            decision = decide_step_action(game, steps[i], bh_pos, bh_defender, off_lineup, read_map, rng=random,
                                          offense_reads=offense_reads, defense_pressure=defense_pressure)
        action = decision.get("action")
        logging.warning(f"🔹 [DYNAMIC {_kind}] step {i} ({bh_pos}@{bh_location}): {action}")
        if action in shot_actions:
            return _apply_dish_contest(decision, _execute_motion_decision(
                skeleton, output_steps, steps[i], bh_pos, bh_location, decision,
                game, off_lineup, def_lineup, is_away_offense,
            ), steps[i], bh_pos)
        if action == SUBTLE_MOVEMENT:
            beat = build_subtle_beat(steps[i], off_lineup, bh_pos, is_away_offense, random, off_eff)
            if beat is None:
                continue
            # Per-defender reads (man + zone, applied in the animator) ride on the beat.
            beat["_subtle_movement"]["defender_reads"] = _roll_subtle_defender_reads(
                def_lineup, def_eff, random
            )
            # Cosmetic render-space idle motion (role-based; fills the frozen tail; UESS-safe).
            beat["_subtle_movement"]["idle_motion"] = _roll_subtle_idle_motion(
                beat, off_lineup, def_lineup, bh_pos, bh_location,
                off_to_def, locations, is_away_offense, random,
            )
            lo, hi = SUBTLE_STEP_ELAPSED_BY_TEMPO.get(tempo, (3, 5))
            elapsed = float(random.randint(lo, hi))
            # Shot-clock expiry backstop: if finishing this beat would leave < 1s, the BH (still
            # holding) is forced to shoot at the 1-second mark with a hard shot_score penalty.
            # Inside if he's at an inside location, else Outside (no time for an attack drive).
            if shot_clock_est - elapsed < 1.0:
                beat["_step_t_floor_game_seconds"] = max(0.0, shot_clock_est - 1.0)
                output_steps.append(beat)
                shot_type = "inside" if _is_inside_location(bh_location) else "outside"
                forced = {"action": SHOOT, "shooter_pos": bh_pos, "shot_type": shot_type}
                logging.warning(
                    f"⏱️ [{_kind} SUBTLE FORCED SHOT] shot clock expiring → {bh_pos} forced {shot_type} "
                    f"shot (-{SUBTLE_FORCED_SHOT_PENALTY})"
                )
                return _execute_motion_decision(
                    skeleton, output_steps, steps[i], bh_pos, bh_location, forced,
                    game, off_lineup, def_lineup, is_away_offense,
                    forced_shot_penalty=SUBTLE_FORCED_SHOT_PENALTY,
                )
            beat["_step_t_floor_game_seconds"] = elapsed
            shot_clock_est -= elapsed
            game_state["_hco_shot_clock_est"] = shot_clock_est  # at-attempt clock (post-subtle)
            output_steps.append(beat)

            # Post-subtle shoot decision (brief: subtle movement can lead to a shot). The BH is
            # now off-pattern; if his man defender FROZE (failed his read) he's open → openness
            # bonus. A yes terminates with a shot; a no resumes the skeleton next iteration.
            bh_def_pos = off_to_def.get(bh_pos) if not zone else None
            froze = (bh_def_pos is not None
                     and beat["_subtle_movement"].get("defender_reads", {}).get(bh_def_pos) is False)
            post_shoot = should_shoot(bh_pos, off_lineup, locations, read_map, off_team,
                                      shot_clock_est, tempo, random,
                                      openness=(20.0 if froze else 0.0), allow_dish=True,
                                      blocked_dish_targets=blocked_dish)
            if post_shoot:
                logging.warning(
                    f"🎯 [DYNAMIC {_kind}] post-subtle SHOOT {post_shoot['shooter_pos']} "
                    f"{post_shoot['shot_type']} (froze={froze})"
                )
                _pdec = {"action": SHOOT, "shooter_pos": post_shoot["shooter_pos"], "shot_type": post_shoot["shot_type"]}
                return _apply_dish_contest(_pdec, _execute_motion_decision(
                    skeleton, output_steps, steps[i], bh_pos, bh_location, _pdec,
                    game, off_lineup, def_lineup, is_away_offense,
                ), steps[i], bh_pos)
            if is_setplay:
                # SET PLAY ONLY (the sole motion/setplay behavioral fork): held instead of
                # shooting/dishing after a forced subtle → recover into the play or get forced into
                # freelance (Z-Completed/Dynamic_HCO_SP_Brief: chemistry+efficiency × d6, each team).
                # Motion always resumes the skeleton (falls through to the next step).
                if _setplay_recovery_roll(game):
                    logging.warning(f"↩️ [DYNAMIC {_kind}] recovery WON → re-enter skeleton at step {i + 1}")
                    continue  # next iteration appends the next defined step (players pop back to spots)
                logging.warning(f"🌀 [DYNAMIC {_kind}] recovery LOST → forced freelance")
                return _resolve_freelance(
                    skeleton, output_steps, steps[i], bh_pos,
                    game, off_lineup, def_lineup, is_away_offense, random,
                )
        elif action == FREELANCE_FORCED:
            # Leave the skeleton and run the freelance progression to a shot.
            return _resolve_freelance(
                skeleton, output_steps, steps[i], bh_pos,
                game, off_lineup, def_lineup, is_away_offense, random,
            )
        # ADVANCE / PASS_IMMEDIATE advance to the next skeleton step.

    # No shot across the walk → force one at the last step, weaving with what we accumulated.
    bh_pos, bh_location = _motion_bh_at_step(steps[-1])
    if not bh_pos or not off_lineup.get(bh_pos):
        return None  # malformed skeleton → defer to legacy
    bh = off_lineup[bh_pos]
    shot_type = "inside" if _is_inside_location(bh_location) else _choose_attack_or_outside(bh, random)
    decision = {"action": SHOOT, "shooter_pos": bh_pos, "shot_type": shot_type}
    return _execute_motion_decision(
        skeleton, output_steps, steps[-1], bh_pos, bh_location, decision,
        game, off_lineup, def_lineup, is_away_offense,
    )


# Backward-compatible named entry points → the unified resolver. The two play types were unified
# 2026-07-11 (they differed only in the set-play recovery roll); these thin delegates keep the
# named API stable for callers/tests. ONE implementation lives in _resolve_hco_offense_shot_dynamic.
def _resolve_motion_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup):
    return _resolve_hco_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup, is_setplay=False)


def _resolve_setplay_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup):
    return _resolve_hco_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup, is_setplay=True)


def _execute_motion_decision(skeleton, base_steps, shot_step, bh_pos, bh_location, decision,
                             game, off_lineup, def_lineup, is_away_offense,
                             forced_shot_penalty=0.0):
    """
    Map a shot Decision onto base_steps + appended shot steps, reusing the existing builders.

    base_steps is the accumulated output stream (skeleton steps + any inserted subtle beats,
    including the shot step itself). shot_step is the original skeleton step the shot fires
    from (used as the attack-drive selected_step and for the receiver's location).
    """
    import random

    last_timestamp = base_steps[-1].get("timestamp", 0)
    shooter_pos = decision["shooter_pos"]
    shot_type = decision["shot_type"]
    via_pass = shooter_pos != bh_pos  # KICKOUT_SHOOT / teammate HOT_READ_SHOOT
    new_steps = []
    attack_penalty = 0.0
    drive_result = None
    playcall_override = None

    if not via_pass:
        # Ball handler shoots himself. Attack → full drive (existing machinery); else shoot in place.
        if shot_type == "attack":
            destination = random.choice(_determine_attack_drive_destination(bh_location))
            drive_result = _create_attack_drive_shoot_steps(
                bh_pos, bh_location, destination, last_timestamp + 300, is_away_offense,
                selected_step=shot_step, off_lineup=off_lineup,
                def_lineup=def_lineup, game=game,
            )
            new_steps.extend(drive_result["steps"])
            shooter_pos = drive_result.get("shooter_pos") or bh_pos
            shooter = drive_result.get("shooter") or off_lineup[bh_pos]
            shooter_location = drive_result.get("shooter_location") or destination
            shot_type = drive_result.get("resolved_shot_type") or "attack"
            playcall_override = drive_result.get("playcall")
            attack_penalty = _apply_attack_penalty(shooter_location, is_away_offense)
        else:
            new_steps.append(_create_shoot_step(bh_pos, bh_location, last_timestamp + 300))
            shooter = off_lineup[bh_pos]
            shooter_location = bh_location
    else:
        # Pass to a specific receiver (kick-out / teammate hot read) → catch-and-shoot.
        receiver = off_lineup.get(shooter_pos)
        receiver_location = ((shot_step.get("pos_actions") or {}).get(shooter_pos) or {}).get("location") or bh_location
        new_steps.append(_create_pass_receive_step(bh_pos, shooter_pos, bh_location, receiver_location, last_timestamp + 300))
        new_steps.append(_create_shoot_step(shooter_pos, receiver_location, last_timestamp + 600))
        shooter = receiver
        shooter_location = receiver_location
        if shot_type == "attack":
            attack_penalty = _apply_attack_penalty(shooter_location, is_away_offense)

    skeleton["steps"] = list(base_steps) + new_steps
    _playcall_map = {"inside": "Inside", "outside": "Outside", "attack": "Attack"}
    result = {
        "skeleton": skeleton,
        "shooter": shooter,
        "shooter_pos": shooter_pos,
        "shooter_location": shooter_location,
        "shot_type": shot_type,
        "playcall": playcall_override or _playcall_map.get(shot_type, "Inside"),
        "attack_penalty": attack_penalty,
        "forced_shot_penalty": float(forced_shot_penalty or 0.0),
    }
    if drive_result is not None:
        result.update({
            "motion_attack_uncontested": drive_result.get("motion_attack_uncontested", False),
            "motion_attack_geometry_contest": drive_result.get("motion_attack_geometry_contest", False),
            "motion_attack_defense_bonus": drive_result.get("motion_attack_defense_bonus", 0),
            "motion_attack_driver_shoots": drive_result.get("motion_attack_driver_shoots"),
        })

    # Hot read = conscious break from pattern → fire a coach VO. Backend picks the clip and
    # flags it on the INITIATION step (first appended step: the dish/drive/shot break). The
    # emitter carries it to step.start.sfx_on_step_start; the FE plays it at step-processing
    # start (before tweens) — no ribbon, no shot/pass-sound collision. See SFX_System.md.
    if HOT_READ_VO_ENABLED and decision.get("action") == "HOT_READ_SHOOT" and new_steps:
        clip = random.choice(HOT_READ_VO_FILES)
        new_steps[0]["_hot_read_sfx"] = clip
        logging.warning(
            f"🔥🔥🔥 [HOT READ EXECUTED] shooter={result['shooter_pos']} "
            f"shot_type={result['shot_type']} vo={clip}"
        )

    return result


def _resolve_freelance(skeleton, base_steps, entry_step, bh_pos,
                       game, off_lineup, def_lineup, is_away_offense, rng):
    """
    Freelance Forced progression (brief: Freelance Behavior). The offense has left the
    skeleton; run cycles of [movement beat → BH shoot/pass/hold] until a shot, capped at
    FREELANCE_MAX_CYCLES (forced shot on the last cycle — option A, shoot-probability ramp).

    Per cycle: emit a freelance movement beat (all five relocate/nudge), then decide —
      - shoot via the shot-clock pressure roll, threshold tightening each cycle
        (roll = randint(1,100)+tempo > 4*shot_clock/cycle);
      - else 80% pass to a teammate within 20 grid (receiver becomes BH, continue) / 20% hold;
      - no teammate within 20 → shoot.
    Returns the resolve_motion_offense_shot result contract.
    """
    from BackEnd.engine.motion_freelance import (
        build_freelance_beat, freelance_shoot_step, freelance_pass_step,
        nearest_named_spot, dist_xy,
        FREELANCE_MAX_CYCLES, FREELANCE_PASS_PROB, FREELANCE_PASS_RADIUS,
    )
    from BackEnd.engine.motion_step_decision import _choose_attack_or_outside, TEMPO_MOD
    from BackEnd.utils.defense_utils import is_zone_defense
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team

    off_team = game.offense_team
    game_state = game.game_state
    off_eff = (getattr(off_team, "team_attributes", {}) or {}).get("offensive_efficiency", 0)
    team_chem = (getattr(off_team, "team_attributes", {}) or {}).get("team_chemistry", 7)
    shot_clock = game_state.get("shot_clock_remaining", 30)
    tempo = (getattr(off_team, "strategy_calls", {}) or {}).get("tempo_call", "normal")
    tempo_mod = TEMPO_MOD.get(tempo, 0)

    # Dynamic HCO Defense (P2): freelance passes are interceptable when the flag is on (posture set).
    # Derive the two-gate contest context once; the freelance beat carries full coords so the
    # dish-contest pipeline (_hco_resolve_dish_contest) works directly on it.
    posture = game_state.get("_hco_defense_posture")
    defense_playcall = game_state.get("defense_playcall")
    zone = is_zone_defense(defense_playcall)
    def_aggr = (getattr(game.defense_team, "strategy_calls", {}) or {}).get("aggression_call", "normal")
    fl_off_to_def = {}
    if not zone:
        _mu = get_matchups_for_defending_team(game_state, getattr(game.defense_team, "is_user_team", False))
        fl_off_to_def = {o: d for d, o in _mu.items()}
    fl_lane_dist = _hco_pass_lane_dist(game)

    output = list(base_steps)
    cur_bh = bh_pos
    current_step = entry_step
    last_ts = output[-1].get("timestamp", 0) if output else 0
    _playcall_map = {"inside": "Inside", "outside": "Outside", "attack": "Attack"}

    def _finish_shot(bh_coords):
        nearest = nearest_named_spot(bh_coords, is_away_offense)
        shot_type = "inside" if _is_inside_location(nearest) else _choose_attack_or_outside(off_lineup[cur_bh], rng)
        output.append(freelance_shoot_step(cur_bh, bh_coords, last_ts + 300))
        skeleton["steps"] = output
        return {
            "skeleton": skeleton,
            "shooter": off_lineup[cur_bh],
            "shooter_pos": cur_bh,
            "shooter_location": nearest,
            "shot_type": shot_type,
            "playcall": _playcall_map.get(shot_type, "Inside"),
            "attack_penalty": _apply_attack_penalty(nearest, is_away_offense) if shot_type == "attack" else 0.0,
        }

    for cycle in range(1, FREELANCE_MAX_CYCLES + 1):
        beat = build_freelance_beat(current_step, off_lineup, cur_bh, off_eff, team_chem, is_away_offense, rng)
        if beat is None:
            break
        output.append(beat)
        last_ts = beat["timestamp"]
        current_step = beat  # next cycle starts from these positions
        bh_coords = beat["pos_actions"][cur_bh]["coords"]

        roll = rng.randint(1, 100) + tempo_mod
        forced = cycle == FREELANCE_MAX_CYCLES
        if not forced and roll <= (4 * shot_clock) / cycle:
            # didn't shoot → pass (to a teammate within 20) or hold
            teammates = [
                (p, beat["pos_actions"][p]["coords"]) for p in beat["pos_actions"]
                if p != cur_bh and dist_xy(bh_coords, beat["pos_actions"][p]["coords"]) <= FREELANCE_PASS_RADIUS
            ]
            if teammates and rng.random() < FREELANCE_PASS_PROB:
                rp, rc = rng.choice(teammates)
                # Dynamic HCO Defense (P2): contest the freelance pass (two gates + posture). On an
                # INTERCEPT/BAT_OOB, show the pass being thrown then return a STEAL turnover (routed
                # by the outer resolver's pass_intercepted check, same path as a dish).
                if posture:
                    contest = _hco_resolve_dish_contest(
                        beat, cur_bh, rp, off_lineup, def_lineup, fl_off_to_def, is_away_offense,
                        def_aggr, fl_lane_dist, zone, defense_playcall, off_team, rng,
                        posture=posture, game_state=game_state, pass_type="freelance")
                    if contest.get("outcome") in ("INTERCEPT", "BAT_OOB"):
                        output.append(freelance_pass_step(cur_bh, rp, bh_coords, rc, last_ts + 300))
                        skeleton["steps"] = output
                        logging.warning(
                            f"🪡 [HCO PASS] {contest['outcome']} on FREELANCE pass {cur_bh}→{rp} "
                            f"by {contest.get('deflector')}")
                        return {
                            "skeleton": skeleton,
                            "pass_intercepted": True,
                            "interceptor_pos": contest.get("deflector"),
                            "pass_bat_oob": contest["outcome"] == "BAT_OOB",
                            "pass_contact_point": contest.get("contact_point"),
                            "passer_pos": cur_bh,
                            "shooter": off_lineup[cur_bh],
                            "shooter_pos": cur_bh,
                        }
                _fp = freelance_pass_step(cur_bh, rp, bh_coords, rc, last_ts + 300)
                if posture:
                    _fp["_hco_contested"] = True  # contested above (survived) → coverage pass skips it
                output.append(_fp)
                last_ts += 300
                cur_bh = rp
                continue
            if teammates:
                continue  # hold → next cycle
            # no teammate within 20 → shoot
        return _finish_shot(bh_coords)

    # Defensive: loop ended without a shot (e.g. beat was None) → force one from the BH's last spot.
    last_coords = ((current_step.get("pos_actions") or {}).get(cur_bh) or {}).get("coords")
    if last_coords is None:
        return None
    return _finish_shot(last_coords)


def resolve_final_turn_shot_logic(game, o_destinations, d_destinations, position_to_spot, bh_pos):
    """
    Final Turn shot: build minimal skeleton (alignment -> pass/receive -> shoot), pick shooter by
    SH (outside) or SC+AG (attack) with weights 50/30/20/9/1, then resolve_shot. Attach alignment
    and time_elapsed = time_remaining to result. Clock runs to 0 on this turn, so quarter/game end
    triggers after the shot (or after FTs if shooting foul); blocking foul on attack awards 2 FTs only.
    """
    import random
    from BackEnd.constants import ACTIONS
    from BackEnd.engine.eoq_debug_log import log_eoq_step
    from BackEnd.utils import situational_logic as sl
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    log_eoq_step(game, "FINAL_SHOT", "pick_shooter", "START", extra={"bh_pos": bh_pos})
    # Shot type: 50% outside, 50% attack, except in Q4/OT when trailing by exactly 3:
    # Final Shot must be an outside three-point attempt (no drive/attack branch).
    delta = sl.get_score_delta(game)
    if getattr(game, "quarter", None) is not None and int(getattr(game, "quarter", 0)) >= 4 and delta == -3:
        shot_type = "Outside"
    else:
        shot_type = "Outside" if random.random() < 0.5 else "Attack"
    game_state["current_playcall"] = shot_type
    # Shooter: rank by SH (outside) or SC+AG (attack), weighted random 50/30/20/9/1
    weights = [0.50, 0.30, 0.20, 0.09, 0.01]
    candidates = []
    for pos, player in off_lineup.items():
        if not player:
            continue
        attrs = getattr(player, "attributes", {}) or {}
        if shot_type == "Outside":
            score = attrs.get("SH", 0)
        else:
            score = attrs.get("SC", 0) + attrs.get("AG", 0)
        candidates.append((player, pos, score))
    candidates.sort(key=lambda t: (t[2], random.random()), reverse=True)
    if not candidates:
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            if off_lineup.get(pos):
                shooter, shooter_pos = off_lineup[pos], pos
                break
        else:
            shooter, shooter_pos = None, "PG"
    else:
        r = random.random()
        cum = 0
        shooter, shooter_pos = candidates[0][0], candidates[0][1]
        for i, (player, pos, _) in enumerate(candidates):
            w = weights[i] if i < len(weights) else (1.0 - cum)
            cum += w
            if r <= cum:
                shooter, shooter_pos = player, pos
                break
    shot_wing = random.choice(["upper wing", "lower wing"])
    bh_is_shooter = bh_pos == shooter_pos
    log_eoq_step(
        game,
        "FINAL_SHOT",
        "pick_shooter",
        "END",
        shooter=shooter,
        shooter_pos=shooter_pos,
        extra={"shot_type": shot_type, "shot_wing": shot_wing, "bh_is_shooter": bh_is_shooter},
    )
    # Opposite vertical half spots for the other 3 or 4 players (doc: midWing, wing, midCorner, corner, deep wing, deep baseline)
    if shot_wing == "upper wing":
        opposite_half_spots = [
            "lower midWing", "lower wing", "lower midCorner", "lower corner",
            "deep lower wing", "deep lower baseline",
        ]
    else:
        opposite_half_spots = [
            "upper midWing", "upper wing", "upper midCorner", "upper corner",
            "deep upper wing", "deep upper baseline",
        ]
    random.shuffle(opposite_half_spots)
    is_away_offense = off_team.team_id == game.away_team.team_id
    # Attack drive destination — rolled ONCE (RNG) up front so the skip-handoff
    # rebuild below stays SS&S-stable (the drive tail is bh-independent anyway).
    attack_destination = None
    if shot_type == "Attack":
        _valid_dests = _determine_attack_drive_destination(shot_wing)
        attack_destination = random.choice(_valid_dests) if _valid_dests else "basketSpot"

    def _assemble_final_shot_skeleton(active_bh_pos, spot_map):
        """Build the Final Shot skeleton for a given ball-handler position + spot map.
        Pure/deterministic (NO RNG) so it can be re-assembled if the skip-handoff
        fallback swaps the acting BH. step0 = alignment, step1 = pass/receive (or
        BH→wing when BH shoots), tail = shoot (Outside) or drive+shoot (Attack)."""
        bh_shoots = active_bh_pos == shooter_pos
        others = [p for p in ["PG", "SG", "SF", "PF", "C"] if p != active_bh_pos and p != shooter_pos]
        other_spot = {}
        for idx, pos in enumerate(others):
            other_spot[pos] = opposite_half_spots[idx % len(opposite_half_spots)]
        s0 = {"timestamp": 0, "pos_actions": {}}
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            s0["pos_actions"][pos] = {
                "action": ACTIONS["HANDLE"] if pos == active_bh_pos else "stand",
                "location": spot_map.get(pos, "key"),
            }
        s1 = {"timestamp": 300, "pos_actions": {}}
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            if bh_shoots and pos == active_bh_pos:
                s1["pos_actions"][pos] = {"action": ACTIONS["HANDLE"], "location": shot_wing}
            elif not bh_shoots and pos == active_bh_pos:
                s1["pos_actions"][pos] = {"action": ACTIONS["PASS"], "location": "deep key"}
            elif pos == shooter_pos:
                s1["pos_actions"][pos] = {"action": ACTIONS["RECEIVE"], "location": shot_wing}
            else:
                s1["pos_actions"][pos] = {
                    "action": "stand",
                    "location": other_spot.get(pos, spot_map.get(pos, "key")),
                }
        if shot_type == "Attack":
            drive_result = _create_attack_drive_shoot_steps(
                shooter_pos, shot_wing, attack_destination, timestamp=600, is_away_offense=is_away_offense
            )
            tail = drive_result.get("steps", []) if isinstance(drive_result, dict) else drive_result
            return {"steps": [s0, s1] + list(tail)}
        s2 = {"timestamp": 600, "pos_actions": {}}
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            if pos == shooter_pos:
                s2["pos_actions"][pos] = {"action": ACTIONS["SHOOT"], "location": shot_wing}
            else:
                loc = "deep key" if pos == active_bh_pos else other_spot.get(pos, spot_map.get(pos, "key"))
                s2["pos_actions"][pos] = {"action": "stand", "location": loc}
        return {"steps": [s0, s1, s2]}

    # Baseline skeleton with the PG as BH — the geometry basis pacing evaluates.
    skeleton = _assemble_final_shot_skeleton(bh_pos, position_to_spot)
    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    from BackEnd.engine.final_turn_pacing import (
        apply_step0_hold_floor,
        evaluate_final_turn_pacing,
    )

    pacing = evaluate_final_turn_pacing(
        game,
        skeleton=skeleton,
        o_destinations=o_destinations,
        position_to_spot=position_to_spot,
        bh_pos=bh_pos,
        shooter_pos=shooter_pos,
        shot_type=shot_type,
        bh_is_shooter=bh_is_shooter,
        prior_turn=prior_turn if isinstance(prior_turn, dict) else None,
    )
    log_eoq_step(
        game,
        "FINAL_SHOT",
        "pacing_preflight",
        "END",
        shooter=shooter,
        shooter_pos=shooter_pos,
        extra={
            "can_meet_anchor": pacing.can_meet_anchor,
            "reason": pacing.reason,
            "step0_hold_floor": pacing.step0_hold_floor,
            "include_entry_pass": pacing.include_entry_pass,
            "handoff_fits": pacing.handoff_fits,
            "include_walkup": pacing.include_walkup,
            "anchor_clock": pacing.anchor_clock,
            "micro_reserve_seconds": pacing.micro_reserve_seconds,
        },
    )
    from BackEnd.utils.eoq_clock_progression import should_route_final_turn_to_flss

    time_remaining_now = int(game_state.get("time_remaining") or 0)
    # Final Shot mode cascade (see EOQ_System.md):
    #   base doesn't fit          → FLSS (late clock) / best-effort (bh=PG, handoff still fires)
    #   PG had the ball           → pg_direct (no handoff)
    #   handoff fits              → handoff (bh=PG, delivered handoff-first)
    #   base fits, handoff doesn't→ skip_handoff (live handler runs it from the PG spot; no FLSS)
    handoff_mode = "pg_direct"
    if not pacing.can_meet_anchor:
        if should_route_final_turn_to_flss(time_remaining_now):
            return {"route_flss": True, "flss_reason": pacing.reason}
        handoff_mode = "best_effort"
        log_eoq_step(
            game, "FINAL_SHOT", "pacing_best_effort", "END",
            extra={"reason": pacing.reason, "time_remaining": time_remaining_now},
        )
        apply_step0_hold_floor(skeleton, 0.0)
    elif pacing.include_entry_pass and not pacing.handoff_fits:
        # Base Final Shot fits but the handoff doesn't → skip it. The live handler
        # runs the shot from the PG's ball-handler spot (BH↔PG spot swap); making him
        # the skeleton BH means the emitter naturally emits no handoff (its
        # prior_owner == skeleton_bh check) and the ball ownership stays consistent.
        from BackEnd.engine.skeleton_step_emitter import _resolve_prior_ball_handler_id
        from BackEnd.utils.shared import get_player_position

        live_bh_id = _resolve_prior_ball_handler_id(
            prior_turn if isinstance(prior_turn, dict) else {}, {}
        )
        live_bh_pos = get_player_position(off_lineup, live_bh_id) if live_bh_id else None
        if live_bh_pos and live_bh_pos != "PG" and off_lineup.get(live_bh_pos):
            position_to_spot = dict(position_to_spot)
            position_to_spot["PG"], position_to_spot[live_bh_pos] = (
                position_to_spot.get(live_bh_pos, "key"),
                position_to_spot.get("PG", "key"),
            )
            o_destinations = dict(o_destinations)
            o_destinations["PG"], o_destinations[live_bh_pos] = (
                o_destinations.get(live_bh_pos),
                o_destinations.get("PG"),
            )
            bh_pos = live_bh_pos
            skeleton = _assemble_final_shot_skeleton(bh_pos, position_to_spot)
            handoff_mode = "skip_handoff"
        else:
            handoff_mode = "handoff"  # couldn't resolve a swap target → fall back to handoff
        apply_step0_hold_floor(skeleton, pacing.step0_hold_floor)
    elif pacing.include_entry_pass:
        handoff_mode = "handoff"
        apply_step0_hold_floor(skeleton, pacing.step0_hold_floor_with_handoff)
    else:
        apply_step0_hold_floor(skeleton, pacing.step0_hold_floor)
    log_eoq_step(
        game,
        "FINAL_SHOT",
        "skeleton_built",
        "END",
        shooter=shooter,
        shooter_pos=shooter_pos,
        extra={
            "skeleton_step_count": len(skeleton.get("steps") or []),
            "shot_type": shot_type,
            "handoff_mode": handoff_mode,
            "bh_pos": bh_pos,
        },
    )
    roles = game.turn_manager.assign_roles(
        off_call=shot_type, def_call=game_state.get("defense_playcall", "2-3-zone"), skeleton=skeleton
    )
    # Set final_turn so shot_manager can apply Final Turn rules (e.g. blocking foul = 2 FTs only on attack)
    game_state["final_turn"] = True
    from BackEnd.engine.final_turn_pacing import final_turn_attack_drive_reserve_seconds

    micro_budget = float(pacing.anchor_clock)
    if shot_type == "Attack":
        micro_budget -= final_turn_attack_drive_reserve_seconds(is_away_offense=is_away_offense)
    game_state["_final_turn_micro_budget_seconds"] = max(0.05, micro_budget)
    try:
        log_eoq_step(game, "FINAL_SHOT", "resolve_shot", "START", shooter=shooter, shooter_pos=shooter_pos)
        # UESS single-coord-source (Final_Turn_UESS_Audit.md FT-Task 1, mirrors HCO
        # Task 1): build the animator ONCE from the finalized skeleton and sync
        # def_lineup coords + zone_defender_assignments_by_step BEFORE resolve_shot,
        # then stamp shot_result["animations"] (below) so the emitter reuses the
        # same build. Without this the resolver never ran the animator, so
        # resolve_shot read a STALE/empty zone map + prior-turn defender coords →
        # Final Turn shots resolved as uncontested while the FE rendered real
        # defenders. Idle motion (_subtle_movement) is stamped separately on the
        # skeleton and read independently by the emitter, so it is unaffected.
        # Defensive: mirror the emitter's own guarded animator build — if the
        # build or coord-sync fails, fall back to the prior behavior (emitter
        # rebuilds later) rather than crashing the final-turn resolution.
        final_turn_animations = None
        try:
            final_turn_animations = Animator(game).skeleton_to_animations(
                skeleton, off_lineup, def_lineup, add_defenders=True
            )
            apply_coords_from_animations_list(game, final_turn_animations)
        except Exception as _ft_sync_err:
            import logging as _ft_sync_log
            _ft_sync_log.warning(
                "FT-Task 1: pre-resolve defender sync failed (%s); falling back "
                "to emitter rebuild for this turn", _ft_sync_err,
            )
            final_turn_animations = None
        # UESS single-coord-source: sync ALL players to the emitter's rendered
        # shoot-step coords (classification + contest read on-screen geometry).
        # Falls back to the skeleton shot location if the build is unavailable.
        _ft_terminal = (
            _uess_sync_emitted_shot_coords(game, skeleton, final_turn_animations, roles, "HCO")
            if final_turn_animations else None
        )
        if _ft_terminal is not None:
            roles["shot_spot"] = dict(_ft_terminal)
        else:
            set_shooter_coords_from_skeleton_last_step(game, skeleton, roles)  # fallback: skeleton shot location
        final_snap = build_skeleton_pre_resolve_shot_snapshot(
            game, off_lineup, def_lineup, skeleton, roles, "FINAL_TURN", "final_turn_pre_resolve_shot"
        )
        shot_result = game.shot_manager.resolve_shot(roles)
        attach_position_snapshots(shot_result, [final_snap])
        log_eoq_step(
            game,
            "FINAL_SHOT",
            "resolve_shot",
            "END",
            shooter=shooter,
            shooter_pos=shooter_pos,
            extra={
                "result_type": shot_result.get("result_type"),
                "quarter_ends_after": shot_result.get("quarter_ends_after"),
                "shot_spot": roles.get("shot_spot"),
            },
        )
    finally:
        game_state.pop("final_turn", None)
        game_state.pop("_final_turn_micro_budget_seconds", None)
    # Cosmetic idle motion on the two stationary beats (step 0 hold, step 1 stand).
    # Rolled here — after resolve_shot — so the idle RNG can't shift the shot.
    _stamp_final_turn_idle_motion(
        skeleton, off_lineup, def_lineup, bh_pos, position_to_spot, is_away_offense, random
    )
    shot_result["oDestinations"] = o_destinations
    shot_result["dDestinations"] = d_destinations
    shot_result["skeleton"] = skeleton
    # UESS single build (FT-Task 1): reuse the finalized single build in the
    # emitter instead of letting build_skeleton_animation_steps rebuild with a
    # fresh RNG draw — so the coords the FE renders == the coords resolve_shot
    # used. Idle motion lives on the skeleton (_subtle_movement) and the emitter
    # reads it independently, so reusing `animations` does not drop it.
    if final_turn_animations:
        shot_result["animations"] = final_turn_animations
    shot_result["final_turn"] = True
    # A handoff is emitted only in handoff / best-effort modes (bh stays PG, ball
    # delivered to him). In skip_handoff the live handler IS the skeleton BH → no
    # handoff; pg_direct never needed one.
    shot_result["final_turn_include_entry_pass"] = handoff_mode in ("handoff", "best_effort")
    shot_result["final_turn_handoff_mode"] = handoff_mode
    shot_result["final_turn_include_walkup"] = pacing.include_walkup
    shot_result["final_turn_anchor_clock"] = pacing.anchor_clock
    from BackEnd.utils.eoq_clock_progression import mark_late_clock_eoq_turn

    mark_late_clock_eoq_turn(shot_result)
    # Player Momentum: flag a made Final Shot so the next break reset adds the
    # Final-Shot bonus on top of the reset (Player_Momentum_System.md).
    if shot_result.get("result_type") == "MAKE":
        _fs_shooter = roles.get("shooter") if isinstance(roles, dict) else None
        _fs_id = getattr(_fs_shooter, "player_id", None)
        if _fs_id is not None:
            game_state["mo_final_shot_maker_id"] = _fs_id
    shot_result["current_turn"] = shot_result.get("current_turn", "HCO")
    shot_result["offense_team_id"] = off_team.team_id
    return shot_result


def resolve_half_court_offense_logic(game):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    # Dynamic HCO Defense (P1): roll this turn's team defense posture (tight/normal/loose) and
    # stash it on game_state; the animator reads it to shade defender placement. No-op (None) when
    # the GOB_DYNAMIC_HCO_DEFENSE flag is off. Rolled fresh each turn → never stale.
    _roll_defense_posture(game)

    # Stash the defending team's defensive_efficiency for the pass-contest Gate 3b modifier
    # (read in _hco_resolve_dish_contest → resolve_pass_contest). Offense uses offensive_efficiency
    # via resolve_offense_pass_modifier at contest time.
    game_state["_hco_def_efficiency"] = float(
        (getattr(def_team, "team_attributes", None) or {}).get("defensive_efficiency", 0) or 0)

    # ✅ BALANCING SYSTEM: Apply balancing system at start of HCO turn
    apply_balancing_system(game, game_state, off_team, def_team)

    # 1. Tactical Setup
    off_call = game_state.get("current_playcall", "Inside")
    def_call = game_state.get("defense_playcall", "man")
    
    # 🔍 DEBUG: Log playcall being used
    logging.debug(f"🔍 [HCO RESOLVE] Using playcall: '{off_call}' (from game_state['current_playcall'])")
    if not off_call or off_call == "Inside":
        logging.debug(f"⚠️ [HCO RESOLVE] WARNING: playcall is '{off_call}' - may fall back to old skeleton system")

    # ✅ NEW RESOLUTION SYSTEM: Get skeleton first (needed for step selection in resolution)
    # For Motion plays, get base_loop skeleton
    # For Set Plays, get a temporary skeleton to use for resolution (will get correct variant after)
    offense_play_type = game_state.get("offense_play_type", "")
    is_motion_play = offense_play_type == "motion"
    
    # 🔍 DEBUG: Log offense_play_type read (FIRST READ - skeleton selection)
    # logging.warning(f"🔍 [HCO RESOLVE DEBUG] FIRST READ - offense_play_type from game_state: '{offense_play_type}' (type: {type(offense_play_type)})")
    # logging.warning(f"🔍 [HCO RESOLVE DEBUG] FIRST READ - is_motion_play: {is_motion_play}")
    # logging.warning(f"🔍 [HCO RESOLVE DEBUG] FIRST READ - current_playcall: '{game_state.get('current_playcall', 'N/A')}'")
    
    if is_motion_play:
        # Motion plays use base_loop skeleton
        skeleton = get_hco_skeleton(None, game, lean_score=None)
    else:
        # Set Plays: Get successful variant skeleton for resolution (will get correct variant after)
        skeleton = get_hco_skeleton(None, game, lean_score=1.0)
    
    # ✅ NEW RESOLUTION SYSTEM: Use new sequential resolution system
    result, variant_result, execution_score = resolve_hco_outcome(game, skeleton)

    # Dynamic HCO migration: per-step foul/steal/turnover MOMENT (from HCT). When the up-front
    # tables are skipped for motion (resolve_hco_outcome → SHOT) and the flag is on, walk the
    # steps with the attribute-driven moment; a hard outcome overrides `result` and routes through
    # the EXISTING non-shot resolution + stopper system below. (v1: man defense, pre-shot.)
    _hco_reach_in_tags = []  # option B: (step_index, defender_id) per non-terminal contest
    if is_motion_play and result == "SHOT" and _dynamic_hco_motion_enabled():
        _moment_result = _resolve_hco_moment_walk(
            skeleton, game, off_lineup, def_lineup, reach_in_tags=_hco_reach_in_tags,
        )
        if _moment_result:
            result = _moment_result

    # ✅ REMOVED: Old generate_logic() call and lean_score storage
    # Store variant_result for skeleton selection (replaces lean_score)
    if variant_result:
        game_state["_skeleton_variant"] = variant_result
    
    # ✅ EXECUTION SCORE: Store execution_score in game_state for stat tracking
    # Note: execution_score is now calculated for ALL HCO results (SHOT, O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER)
    if execution_score is not None:
        game_state["execution_score"] = execution_score
        # ✅ STORE EXECUTION SCORE: Persist to scouting data for stat tracking (all HCO results)
        _store_execution_score(execution_score, game, off_team, def_team)
    
    # 🔍 DEBUG: Log skeleton retrieval result
    if skeleton:
        logging.debug(f"✅ [HCO RESOLVE] Skeleton retrieved successfully: {len(skeleton.get('steps', []))} steps")
    else:
        logging.debug(f"⚠️ [HCO RESOLVE] WARNING: No skeleton retrieved! Will fall back to old system")
    
    # CRITICAL: Always create a deep copy to avoid mutating cached skeleton
    # This prevents any modifications (from stopper system or elsewhere) from affecting future turns
    if skeleton:
        skeleton = copy.deepcopy(skeleton)
    
    # ✅ NEW RESOLUTION SYSTEM: Get correct skeleton variant based on resolution result
    # For Motion plays, use base_loop (no variants)
    # For Set Plays, use variant_result from resolution system
    if is_motion_play:
        # Motion plays use base_loop skeleton (already retrieved)
        final_skeleton = skeleton
        # Dynamic HCO option B: stamp the (failed) steal-attempt reach-in on every non-terminal
        # contested step of an engaged moment-walk turn (terminal outcomes get theirs via the
        # stopper step). Applied here, post-deepcopy, so the cached skeleton is never mutated;
        # step indices align with the walked skeleton. The emitter turns reach_in_def_id into a
        # render-space reach_in flourish (FE lunge + click-steal SFX) — UESS-safe, no coord change.
        if _hco_reach_in_tags and final_skeleton and final_skeleton.get("steps"):
            _fsteps = final_skeleton["steps"]
            for _idx, _rid in _hco_reach_in_tags:
                if 0 <= _idx < len(_fsteps):
                    _fsteps[_idx]["reach_in_def_id"] = _rid
    else:
        # Set Plays: Get skeleton with correct variant based on resolution result
        if variant_result:
            # Map variant_result to lean_score for get_hco_skeleton
            variant_to_lean = {
                "successful": 1.0,
                "mid_play_change": 0.3,
                "contested": -0.3,
                "broken": -1.0
            }
            lean_score = variant_to_lean.get(variant_result, 0.0)
            final_skeleton = get_hco_skeleton(None, game, lean_score=lean_score)
        else:
            # Fallback: use successful variant
            final_skeleton = get_hco_skeleton(None, game, lean_score=1.0)
    
    # CRITICAL: Always create a deep copy to avoid mutating cached skeleton
    if final_skeleton:
        final_skeleton = copy.deepcopy(final_skeleton)

    # Dynamic HCO Set Plays (Stage C): per-step foul/steal/turnover MOMENT on the EXECUTED variant
    # skeleton, replacing the up-front event tables (already skipped via skip_upfront_events under
    # the flag). Man + zone — _resolve_hco_moment_walk handles both. Runs here, AFTER the variant
    # skeleton is chosen + deep-copied, so the walk reads the actual play and the reach-in step
    # indices align with the emitted skeleton; runs BEFORE the shot-clock block so a hard outcome
    # (which clears result != "SHOT") correctly pre-empts the would-be shot. Mirrors the motion
    # moment walk above. (variant selection unaffected — Z-Completed/Dynamic_HCO_SP_Brief, Stage C.)
    if (offense_play_type in ("set", "set_play") and result == "SHOT"
            and _dynamic_hco_setplay_enabled() and final_skeleton):
        _sp_reach_in_tags = []  # option B: (step_index, defender_id) per non-terminal contest
        _sp_moment_result = _resolve_hco_moment_walk(
            final_skeleton, game, off_lineup, def_lineup, reach_in_tags=_sp_reach_in_tags,
        )
        if _sp_moment_result:
            result = _sp_moment_result
        # Stamp the (failed) steal-attempt reach-in on every non-terminal contested step (terminal
        # outcomes get theirs via the stopper step). final_skeleton is already deep-copied, so the
        # cached skeleton is never mutated and indices align with the walked skeleton.
        if _sp_reach_in_tags and final_skeleton.get("steps"):
            _fsteps = final_skeleton["steps"]
            for _idx, _rid in _sp_reach_in_tags:
                if 0 <= _idx < len(_fsteps):
                    _fsteps[_idx]["reach_in_def_id"] = _rid

    # Shot clock violation: if result is SHOT but shot clock would hit 0 during this turn, either violation or shot-at-1 (Shot_Clock_System.md).
    # Motion only: optional recalibration — chance to take a shot from an earlier step to avoid violation (Shot_Clock_System.md — Second Chance System).
    if result == "SHOT" and final_skeleton and "steps" in final_skeleton:
        steps = final_skeleton["steps"]
        if steps:
            timing = calc_skeleton_step_timing_contract(
                steps,
                resolution_step_index=len(steps) - 1,
                include_hco_step1_bringup=True,
                prev_offense_positions=game_state.get("_prev_offense_positions_for_hco"),
                phase_type="HCO",
                off_lineup=game.offense_team.lineup,
            )
            step_clock_seconds = timing.get("step_clock_seconds") or []
            shot_remaining = game_state.get("shot_clock_remaining", 30)
            cumulative = 0
            for i, sec in enumerate(step_clock_seconds):
                cumulative += sec
                if cumulative >= shot_remaining:
                    chemistry = int(off_team.team_attributes.get("team_chemistry", 7))
                    discipline = int(off_team.team_attributes.get("discipline", 0))

                    # Motion recalibration: chance to shoot from step index 2..(i-1) to avoid violation (Shot_Clock_System.md)
                    if is_motion_play and i >= 3:
                        recalibration_score = (chemistry * 5) + (discipline * 3)
                        die_roll = random.randint(1, 100)
                        if die_roll < recalibration_score:
                            chosen_step = random.randint(2, i - 1)
                            motion_shot_info = resolve_motion_offense_shot(
                                final_skeleton, game, off_lineup, def_lineup,
                                forced_shot_step_index=chosen_step,
                            )
                            if motion_shot_info:
                                final_skeleton = motion_shot_info["skeleton"]
                                game_state["_motion_shot_recalibrated"] = motion_shot_info
                                break

                    # No recalibration (or failed recalibration): violation vs shot-at-1
                    from BackEnd.utils.shot_clock_policy import can_commit_shot_clock_violation

                    ball_handler_at_step = get_ball_handler_from_skeleton(final_skeleton, off_lineup, step_index=i)
                    iq = int(getattr(ball_handler_at_step, "attributes", {}).get("IQ", 0) or 0)
                    intelligence = min(25, iq // 4)  # int(IQ/4), cap 0-25 (Shot_Clock_System.md)
                    violation_threshold = 60 + chemistry + discipline + intelligence
                    x = random.randint(1, 100)
                    if (
                        can_commit_shot_clock_violation(game_state)
                        and x > violation_threshold
                    ):
                        # Path A: shot clock violation (current behavior)
                        game_state["shot_clock_violation_step_index"] = i
                        result = "SHOT_CLOCK_VIOLATION"
                    else:
                        # Path B: shot attempt at 1 second remaining — truncate skeleton, keep result SHOT
                        movement_target = shot_remaining - 1
                        cum = 0
                        j = -1
                        for idx, s in enumerate(step_clock_seconds):
                            cum += s
                            if cum <= movement_target:
                                j = idx
                            else:
                                break
                        if j < 0:
                            j = 0
                        truncated_steps = steps[: j + 1] + [steps[-1]]
                        final_skeleton["steps"] = truncated_steps
                        game_state["shot_at_one_second"] = True
                        game_state["_shot_at_one_second_time_elapsed"] = shot_remaining - 1
                    break
    
    # ✅ STOPER SYSTEM: Apply stopper system to skeleton (truncate and add stopper step if needed)
    skeleton = apply_stopper_system_to_skeleton(final_skeleton, result, game_state)
    game_state.pop("shot_clock_violation_step_index", None)  # Don't leak to next turn
    
    # Get the successful variant to determine intended shooter (only for Set Plays)
    # Motion plays don't have variants, so we'll use the base_loop skeleton
    if is_motion_play:
        # For Motion plays, use the same skeleton (base_loop)
        successful_skeleton = skeleton
    else:
        # For Set Plays, get the successful variant
        successful_skeleton = get_hco_skeleton(None, game, lean_score=1.0)  # Force successful variant
    
    roles = game.turn_manager.assign_roles(off_call, def_call, skeleton=skeleton)

    # ✅ FIX: For non-shot outcomes (steals, turnovers, fouls), override defender
    # to be based on ball handler's position, not shooter's position
    # assign_roles() assigns defender based on shooter, but for steals we need
    # whoever is guarding the ball handler at the time of the steal
    if result in ["STEAL", "DEAD_BALL_TURNOVER", "SHOT_CLOCK_VIOLATION", "O_FOUL", "D_FOUL"]:
        # ✅ FIX: Get ball handler from the stop step where the steal/foul/turnover occurs,
        # not from roles (which may be the shooter from a different step)
        # This is critical for Motion plays where the ball handler changes throughout the motion
        # Check for both steal and turnover stop step indices
        # Also check the generic stop_step_index that apply_stopper_system_to_skeleton sets
        stop_step_index = (
            game_state.get("steal_stop_step_index") or 
            game_state.get("turnover_stop_step_index") or
            game_state.get("stop_step_index")
        )
        if stop_step_index is not None and skeleton and "steps" in skeleton:
            # Use the actual ball handler at the stop step
            ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=stop_step_index)
        else:
            # Fallback: use ball handler from roles (for backwards compatibility or if stop step not available)
            ball_handler = roles.get("ball_handler")
        
        if ball_handler:
            ball_handler_pos = get_player_position(off_lineup, ball_handler)
            
            from BackEnd.utils.defense_utils import is_zone_defense
            is_zone = is_zone_defense(def_call)
            if is_zone:
                # Zone defense: use actual zone assignment logic to find which defender(s) are guarding the ball handler
                from BackEnd.utils.shared_defense import (
                    _get_23_zone_boundaries, _get_32_zone_boundaries, _get_131_zone_boundaries,
                    assign_all_zone_defenders
                )
                from BackEnd.constants import HCO_STRING_SPOTS
                from BackEnd.utils.shared import get_away_player_coords
                
                # Get ball handler's location from the skeleton step where steal occurs
                ball_handler_spot = "key"  # Default fallback
                if skeleton and "steps" in skeleton:
                    # For steals, use the stop step (where steal occurs)
                    # For other outcomes, use the last step before stopper
                    steps = skeleton.get("steps", [])
                    if steps:
                        # Find the step where the ball handler has the ball
                        for step in reversed(steps):
                            pos_actions = step.get("pos_actions", {})
                            for pos, action_info in pos_actions.items():
                                action = action_info.get("action", "").lower()
                                if action in ["handle_ball", "receive", "pass"] and pos == ball_handler_pos:
                                    ball_handler_spot = action_info.get("location") or action_info.get("spot") or "key"
                                    break
                            if ball_handler_spot != "key":
                                break
                
                # Get ball handler's coordinates
                ball_handler_coords = HCO_STRING_SPOTS.get(ball_handler_spot, {"x": 50, "y": 25})
                
                # Determine court orientation
                is_away_offense = off_team.team_id == game.away_team.team_id
                if is_away_offense:
                    ball_handler_coords = get_away_player_coords(ball_handler_coords)
                
                # Get zone boundaries based on ball location (applies shifts)
                if def_call == "3-2 Zone":
                    zone_boundaries = _get_32_zone_boundaries(ball_handler_spot, is_away_offense)
                elif def_call == "1-3-1 Zone":
                    zone_boundaries = _get_131_zone_boundaries(ball_handler_spot, is_away_offense)
                else:
                    zone_boundaries = _get_23_zone_boundaries(ball_handler_spot, is_away_offense)
                
                # Build offensive players list for zone assignment
                ball_handler_id = getattr(ball_handler, "player_id", None)
                offensive_players = []
                for pos, player in off_lineup.items():
                    player_id = getattr(player, "player_id", None)
                    player_coords = getattr(player, "coords", {})
                    # Get player's spot from skeleton if available
                    player_spot = "key"
                    if skeleton and "steps" in skeleton:
                        steps = skeleton.get("steps", [])
                        if steps:
                            for step in reversed(steps):
                                pos_actions = step.get("pos_actions", {})
                                if pos in pos_actions:
                                    action_info = pos_actions[pos]
                                    player_spot = action_info.get("location") or action_info.get("spot") or "key"
                                    break
                    
                    # Convert spot to coordinates
                    spot_coords = HCO_STRING_SPOTS.get(player_spot, {"x": 50, "y": 25})
                    if is_away_offense:
                        spot_coords = get_away_player_coords(spot_coords)
                    
                    # Use player's coords if available, otherwise use spot coords
                    final_coords = player_coords if player_coords.get("x") and player_coords.get("y") else spot_coords
                    
                    offensive_players.append({
                        "player_id": player_id,
                        "coords": final_coords,
                        "spot": player_spot,
                        "is_ball_handler": (player_id == ball_handler_id)
                    })
                
                # Get aggression level
                aggression_level = slow_it_down_defense_setting(
                    game.game_state, def_team, "aggression",
                    def_team.strategy_settings.get("aggression", "normal"),
                )
                aggression_map = {0: "passive", 1: "passive", 2: "normal", 3: "aggressive", 4: "aggressive"}
                aggression = aggression_map.get(aggression_level, "normal")
                
                # Call zone assignment logic to get actual defender assignments
                _, defender_to_offensive_player = assign_all_zone_defenders(
                    zone_boundaries,
                    offensive_players,
                    ball_handler_coords,
                    ball_handler_spot,
                    aggression,
                    is_away_offense
                )
                
                # Find which defender(s) are actually guarding the ball handler
                defenders_guarding_ball_handler = []
                for def_pos, guarded_player_id in defender_to_offensive_player.items():
                    if guarded_player_id == ball_handler_id:
                        defenders_guarding_ball_handler.append(def_pos)
                
                # Handle overlapping zones per user requirements:
                # 1. If only one defender is guarding the ball handler, use that one
                # 2. If two defenders are guarding the ball handler, randomly pick one
                if len(defenders_guarding_ball_handler) == 1:
                    defender_pos = defenders_guarding_ball_handler[0]
                elif len(defenders_guarding_ball_handler) >= 2:
                    # Two or more defenders guarding ball handler - randomly pick one
                    defender_pos = random.choice(defenders_guarding_ball_handler)
                else:
                    # No defender assigned to guard ball handler (shouldn't happen, but fallback)
                    # Fallback: use position match
                    defender_pos = ball_handler_pos
                
                defender = (
                    def_lineup.get(defender_pos)
                    if defender_pos
                    else defender_player_from_random_slot_fallback(def_lineup)
                )
            else:
                # Man-to-man: use matchups for the defending team (user vs computer)
                from BackEnd.utils.man_defense_matchups import get_defender_position_for_man_defense
                defending_team_is_user = getattr(game.defense_team, "is_user_team", False)
                defender_pos = get_defender_position_for_man_defense(
                    ball_handler_pos, game.game_state, defending_team_is_user=defending_team_is_user
                ) if ball_handler_pos else random_defender_fallback_position()
                defender = (
                    def_lineup.get(defender_pos)
                    if defender_pos
                    else defender_player_from_random_slot_fallback(def_lineup)
                )
            
            if defender:
                roles["defender"] = defender
    
    # Extract intended shooter from successful variant
    intended_shooter_pos = None
    if successful_skeleton and "steps" in successful_skeleton and successful_skeleton["steps"]:
        final_step = successful_skeleton["steps"][-1]
        for pos, action_info in final_step.get("pos_actions", {}).items():
            action = action_info.get("action", "").lower()
            if action == "shoot":
                intended_shooter_pos = pos
                break
    
    # Store intended shooter in roles for later comparison
    roles["intended_shooter_pos"] = intended_shooter_pos

    # ============================================================================
    # STEAL HCO SETUP: Check if this HCO turn comes from a steal
    # ============================================================================
    # ✅ FIX: Only check for Steal HCO Setup if this is NOT a steal turn itself
    # For HCO steals, this function is called during the steal turn, but last_stealer
    # isn't set until resolve_turnover_logic() runs later. We should only run this
    # check in the NEXT HCO turn (after last_stealer has been set).
    last_stealer = game_state.get("last_stealer")
    is_steal_hco_setup = False
    hco_setup_move_x = 0
    hco_setup_move_y = 0
    hco_setup_final_x = None
    hco_setup_final_y = None
    
    # ✅ FIX: Run HCO Setup if last_stealer exists and next turn is HCO
    # This runs regardless of the current turn's result (even if it's another steal)
    # Once a steal happens and transitions to HCO, the HCO Setup Step should always run in the next HCO turn
    if last_stealer:
        # Check if the previous turn was a steal that transitioned to HCO
        # This happens when last_stealer is set and offensive_state is HCO (not FAST_BREAK)
        offensive_state = game_state.get("offensive_state")
        if offensive_state == "HCO":
            is_steal_hco_setup = True
            ball_handler = last_stealer
            
            # ✅ FIX: Use stored stealer position from skeleton step (if available)
            # This ensures we use the position at the exact moment of the steal, not stale coords
            if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
                stealer_coords = game_state["last_stealer_coords"]
                ball_handler_start_x = stealer_coords.get("x", 50)
                ball_handler_start_y = stealer_coords.get("y", 25)
            else:
                ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
                ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)
            
            # Determine direction away from basket (opposite of steal entry)
            # Home offense: basket at x=90, so away = -1 (left, toward x=10)
            # Away offense: basket at x=10, so away = +1 (right, toward x=90)
            is_away_offense = off_team.team_id == game.away_team.team_id
            if is_away_offense:
                direction = 1  # Away from x=10 (toward x=90)
            else:
                direction = -1  # Away from x=90 (toward x=10)
            
            # Calculate steal HCO setup movement (away from basket)
            hco_setup_move_x = random.randint(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX)
            hco_setup_move_y = random.randint(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE)
            
            # Apply movement away from basket
            hco_setup_final_x = ball_handler_start_x + (direction * hco_setup_move_x)
            hco_setup_final_y = max(STEAL_HCO_SETUP_Y_MIN, min(STEAL_HCO_SETUP_Y_MAX, ball_handler_start_y + hco_setup_move_y))
            
            # Calculate movement for all 9 other players (toward the new offense basket)
            # x_direction: +1 for home offense (toward x=90), -1 for away offense (toward x=10)
            x_direction = 1 if not is_away_offense else -1
            
            # Get ball handler position to check if they're the PG
            ball_handler_pos = get_player_position(off_lineup, ball_handler)
            ball_handler_id = getattr(ball_handler, "player_id", None)
            is_ball_handler_pg = (ball_handler_pos == "PG")
            
            # Calculate target positions for offensive players (excluding ball handler and PG)
            other_players_movements = []
            pg_movement = None
            
            # First, handle PG positioning if ball handler is not the PG
            if not is_ball_handler_pg and "PG" in off_lineup:
                pg_player = off_lineup["PG"]
                pg_id = getattr(pg_player, "player_id", None)
                pg_coords = getattr(pg_player, "coords", {})
                pg_start_x = pg_coords.get("x", 50)
                pg_start_y = pg_coords.get("y", 25)
                
                # PG moves to a spot relative to ball handler
                # Y: ±6 coords from ball handler
                pg_move_y = random.randint(-6, 6)
                pg_final_y = max(4, min(46, ball_handler_start_y + pg_move_y))
                
                # X: 3-9 coords from ball handler in direction of offense basket
                # Away team: -9 to -3 (toward x=10), Home team: 3 to 9 (toward x=90)
                pg_move_x_distance = random.randint(3, 9)
                pg_move_x = x_direction * pg_move_x_distance  # x_direction: -1 for away, +1 for home
                pg_final_x = ball_handler_start_x + pg_move_x
                # Clamp x to court bounds (4-97)
                pg_final_x = max(4, min(97, pg_final_x))
                
                pg_movement = {
                    "player_id": pg_id,
                    "start_x": pg_start_x,
                    "start_y": pg_start_y,
                    "final_x": pg_final_x,
                    "final_y": pg_final_y,
                    "move_x": pg_move_x,  # Already signed (x_direction * distance)
                    "move_y": pg_move_y
                }
            
            # Now handle all other players from both teams (excluding ball handler and offensive PG)
            # Get offensive PG ID to exclude it
            offensive_pg_id = None
            if "PG" in off_lineup:
                offensive_pg_id = getattr(off_lineup["PG"], "player_id", None)
            
            # Helper function to calculate and add player movement
            def add_player_movement(player, player_id):
                # Get player's current position
                player_coords = getattr(player, "coords", {})
                player_start_x = player_coords.get("x", 50)
                player_start_y = player_coords.get("y", 25)
                
                # Calculate movement toward new offense basket
                other_move_x = random.randint(
                    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN,
                    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX
                )
                other_move_y = random.randint(
                    -STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE,
                    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE
                )
                
                # Apply movement toward basket
                other_final_x = player_start_x + (x_direction * other_move_x)
                # Clamp x to court bounds (4-97)
                other_final_x = max(4, min(97, other_final_x))
                # Apply y movement and clamp
                other_final_y = max(
                    STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN,
                    min(STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MAX, player_start_y + other_move_y)
                )
                
                other_players_movements.append({
                    "player_id": player_id,
                    "start_x": player_start_x,
                    "start_y": player_start_y,
                    "final_x": other_final_x,
                    "final_y": other_final_y,
                    "move_x": other_move_x,
                    "move_y": other_move_y
                })
            
            # Iterate through offensive players (excluding ball handler and PG)
            for pos, player in off_lineup.items():
                player_id = getattr(player, "player_id", None)
                if player_id == ball_handler_id:
                    continue  # Skip ball handler
                if player_id == offensive_pg_id:
                    continue  # Skip offensive PG (handled separately above)
                
                add_player_movement(player, player_id)
            
            # Iterate through defensive players (all defensive players move, none can be ball handler or offensive PG)
            for pos, player in def_lineup.items():
                player_id = getattr(player, "player_id", None)
                add_player_movement(player, player_id)
            
            # Add PG movement to the list if it exists
            if pg_movement:
                other_players_movements.append(pg_movement)
            
            # Store in roles for frontend
            roles["is_steal_hco_setup"] = True
            roles["ball_handler_hco_setup_x"] = hco_setup_final_x
            roles["ball_handler_hco_setup_y"] = hco_setup_final_y
            roles["ball_handler_hco_setup_move_x"] = hco_setup_move_x
            roles["ball_handler_hco_setup_move_y"] = hco_setup_move_y
            roles["ball_handler_id"] = ball_handler_id
            roles["other_players_hco_setup_movements"] = other_players_movements
            roles["hco_setup_x_direction"] = x_direction
            
            # Clear last_stealer and stored skeleton data after using it (so it doesn't persist to subsequent turns)
            game_state["last_stealer"] = None
            game_state.pop("steal_stop_step_index", None)
            game_state.pop("steal_original_skeleton_steps", None)
            game_state.pop("last_stealer_coords", None)
    
    # print("inside resolve_half_court_offense_logic")
    # print("[DEBUG] roles:", roles.keys())
    # print("[DEBUG] event_step:", roles.get("event_step"))
    # print("[DEBUG] steps:", roles.get("steps"))
    # print("[DEBUG] shooter:", roles.get("shooter"))

    # ✅ SS&S FIX: Apply energy decay for ALL HCO turns (both SHOT and non-SHOT)
    # Energy decay was previously inside determine_event_type(), but we bypass that
    # for SHOT results in the stopper system. Extract energy decay to ensure it
    # always runs regardless of event type.
    apply_energy_decay(off_lineup, def_lineup)
    
    # ✅ SS&S: Recharge energy for bench players (50% chance to add 0.01 per turn)
    apply_bench_energy_recharge(game)

    # 2. Event Determination
    # Use result from generate_logic() for stopper results, otherwise determine from skeleton
    if result != "SHOT":
        # Map stopper result to event_type
        if result == "O_FOUL":
            event_type = "O_FOUL"
        elif result == "D_FOUL":
            event_type = "D_FOUL"
        elif result == "DEAD_BALL_TURNOVER":
            event_type = "TURNOVER"
        elif result == "SHOT_CLOCK_VIOLATION":
            event_type = "TURNOVER"
        elif result == "STEAL":
            event_type = "TURNOVER"
        else:
            # Fallback: determine from skeleton analysis
            event_type = game.turn_manager.determine_event_type(roles)
    else:
        # Normal flow: result == "SHOT", proceed to shot resolution
        # ✅ SS&S FIX: Commented out determine_event_type() call to avoid conflicts
        # When result == "SHOT" from generate_logic(), we should proceed directly to shot resolution
        # determine_event_type() can return non-SHOT values (e.g., "D_FOUL") which conflicts with stopper system
        # TODO: Revisit determine_event_type() usage if needed for future enhancements
        # event_type = game.turn_manager.determine_event_type(roles)
        # if event_type == "SHOT" or event_type is None:
        #     event_type = "SHOT"
        event_type = "SHOT"

    if event_type != "SHOT":
        # ✅ STOPER SYSTEM: Populate roles for stopper results using SS&S helper functions
        # Use same player determination logic as FCP/HCT for consistency
        
        # Determine ball handler from skeleton (from stopper step or last step)
        # ✅ FIX: Use ball_handler from roles if already set (from defender override logic)
        # Otherwise, determine from skeleton (for cases where override didn't run)
        if "ball_handler" in roles and roles["ball_handler"]:
            ball_handler = roles["ball_handler"]
        else:
            ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
            roles["ball_handler"] = ball_handler
        
        ball_handler_pos = getattr(ball_handler, 'position', None) or "PG"
        
        # Dynamic HCO: the per-step moment stashed the ACTUAL contesting defender (the man matchup
        # OR the resolved zone defender). Prefer it so the steal credit + reach-in lunge land on the
        # right player — for a zone, the position-on-position fallback below would pick the wrong one.
        _moment_def_id = game_state.pop("_hco_moment_defender_id", None)
        if _moment_def_id and not roles.get("defender"):
            for _dp in def_lineup.values():
                if getattr(_dp, "player_id", None) == _moment_def_id:
                    roles["defender"] = _dp
                    break

        # ✅ FIX: Only set defender if not already set by override logic
        # The defender override logic (for steals/turnovers/fouls) should have already set
        # the correct defender based on ball handler position and zone/man defense
        if "defender" not in roles or not roles["defender"]:
            # Determine defender based on ball handler position (same as FCP/HCT)
            _fb = defender_player_from_random_slot_fallback(def_lineup)
            defender = def_lineup.get(ball_handler_pos) or _fb
            roles["defender"] = defender
        else:
            # Use the defender that was already set by override logic
            defender = roles["defender"]

        # Dynamic HCO steal / reach-in micro-movement: for a defender-reach outcome (steal,
        # dead-ball forced by pressure, or reach-in D_FOUL), tag the stopper step (the last,
        # event-bearing step) with the on-ball defender's id. The schema emitter turns this into
        # a render-space ``reach_in`` flourish (defender lunges at the ball + click-steal SFX) —
        # FE-render only, never mutates gameplay coords (UESS-safe). O_FOUL (offensive) is excluded.
        if (result in ("STEAL", "DEAD_BALL_TURNOVER", "D_FOUL")
                and defender is not None and (skeleton or {}).get("steps")):
            _rid = getattr(defender, "player_id", None)
            if _rid:
                skeleton["steps"][-1]["reach_in_def_id"] = _rid

        # Set foul_player using SS&S helper function (same as FCP/HCT)
        if event_type in ["O_FOUL", "D_FOUL"]:
            foul_team_type = "OFFENSE" if event_type == "O_FOUL" else "DEFENSE"
            foul_player = select_foul_player(foul_team_type, ball_handler, off_lineup, def_lineup)
            roles["foul_player"] = foul_player
            # Ensure shooter is set (needed by resolve_non_shooting_foul)
            if "shooter" not in roles or not roles["shooter"]:
                roles["shooter"] = ball_handler
        
        # Convert truncated skeleton to animations
        animator = Animator(game)
        animations = []
        if skeleton and "steps" in skeleton:
            animations = animator.skeleton_to_animations(
                skeleton,
                off_lineup,
                def_lineup,
                add_defenders=True
            )
        if animations:
            apply_coords_from_animations_list(game, animations)

        # ✅ FIX: Extract stealer position from generated animations (SS&S approach)
        # This uses the actual calculated defensive position from the animation system,
        # avoiding coordinate orientation issues and reusing existing calculations
        # Always extract for new steals - coordinates will be cleared after use in followup turn
        # For stopper results (steal, foul, turnover), the stopper step is always the final step,
        # so we can simply use animation["end"] to get the final coordinates
        if event_type == "TURNOVER" and result == "STEAL" and animations and defender:
            # ✅ SS&S: Clear old steal data before setting new steal data (prevents stale data from previous steals)
            game_state.pop("last_stealer_coords", None)
            game_state["last_stealer"] = None
            
            stealer_id = getattr(defender, "player_id", None)
            
            if stealer_id:
                # Find the defensive animation for the stealer
                stealer_animation = None
                for anim in animations:
                    if anim.get("playerId") == stealer_id:
                        stealer_animation = anim
                        break
                
                if stealer_animation and "end" in stealer_animation:
                    # Use the final coordinates from the animation (stopper step is always final)
                    stealer_coords = stealer_animation["end"]
                    game_state["last_stealer_coords"] = stealer_coords.copy()
                    logging.warning(f"🏀 [STEAL POSITION] Extracted final coords from animation end: x={stealer_coords['x']}, y={stealer_coords['y']}")
                else:
                    logging.warning(f"⚠️ [STEAL POSITION] Could not find stealer animation or 'end' field (stealer_id={stealer_id}, has_animation={stealer_animation is not None}, has_end={stealer_animation and 'end' in stealer_animation if stealer_animation else False})")
            else:
                logging.warning(f"⚠️ [STEAL POSITION] Missing stealer_id")
        
        #need to add animations to each of these
        if event_type == "TURNOVER":
            # Use result to determine turnover type (STEAL vs DEAD BALL vs SHOT_CLOCK)
            if result == "DEAD_BALL_TURNOVER":
                turnover_type = "DEAD BALL"
            elif result == "SHOT_CLOCK_VIOLATION":
                turnover_type = "SHOT_CLOCK"
            elif result == "STEAL":
                turnover_type = "STEAL"
            else:
                turnover_type = "DEAD BALL"
            # Pass from_resolution_system=True to respect the resolution system's determination
            turn_result = resolve_turnover_logic(roles, game, turnover_type=turnover_type, from_resolution_system=True)
            timing_contract = calc_skeleton_step_timing_contract(
                roles.get("steps", []),
                resolution_step_index=roles.get("event_step"),
                include_hco_step1_bringup=True,
                phase_type="HCO",
                off_lineup=game.offense_team.lineup,
            )
            turn_result["time_elapsed"] = timing_contract["time_elapsed"]
            turn_result["step_clock_seconds"] = timing_contract["step_clock_seconds"]
            turn_result["resolution_step_index"] = timing_contract["resolution_step_index"]
            turn_result["executed_step_count"] = timing_contract["executed_step_count"]
            turn_result["bringup_per_player_seconds"] = timing_contract.get("bringup_per_player_seconds") or {}
            # Add skeleton to result. Legacy ``animations[]`` is no longer
            # stamped on HCO turn results (Phase 2 of HCO UESS migration);
            # the schema emitter builds them internally from the skeleton.
            turn_result["skeleton"] = skeleton or {}
            # ✅ ADD LEAN METER VALUE: Add raw result value (-100 to +100) to text for frontend parsing
            lean_value = game_state.get("lean_result_value", 0)
            if "lean:" not in turn_result.get("text", ""):
                turn_result["text"] = turn_result.get("text", "") + f" lean:{lean_value:.1f}"
            # ✅ FIX: Add serializable roles data (only include fields needed for frontend, not Player objects)
            # Include steps if they exist (needed for capture_halfcourt_animation fallback)
            # Note: action_timeline uses Player objects as keys, so it can't be serialized - it will be empty dict in fallback
            serializable_roles = {}
            if roles.get("is_steal_hco_setup"):
                serializable_roles["is_steal_hco_setup"] = True
                serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
                serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
                serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
                serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
                serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
                serializable_roles["other_players_hco_setup_movements"] = roles.get("other_players_hco_setup_movements", [])
                serializable_roles["hco_setup_x_direction"] = roles.get("hco_setup_x_direction")
            # ✅ FIX: Include steps if they exist (needed for animation fallback)
            # action_timeline is NOT included because it uses Player objects as keys (not JSON-serializable)
            if "steps" in roles:
                serializable_roles["steps"] = roles["steps"]
            if serializable_roles:
                turn_result["roles"] = serializable_roles
            attach_position_snapshots(
                turn_result,
                [
                    build_phase_post_stopper_snapshot(
                        game,
                        off_lineup,
                        def_lineup,
                        skeleton,
                        roles,
                        "HCO",
                        "turnover",
                        "hco_turnover_post_stopper",
                    )
                ],
            )
            return turn_result

        elif event_type == "O_FOUL":
            game_state["foul_team"] = "OFFENSE"
            foul_result = resolve_non_shooting_foul(roles, game)
            timing_contract = calc_skeleton_step_timing_contract(
                roles.get("steps", []),
                resolution_step_index=roles.get("event_step"),
                include_hco_step1_bringup=True,
                phase_type="HCO",
                off_lineup=game.offense_team.lineup,
            )
            foul_result["time_elapsed"] = timing_contract["time_elapsed"]
            foul_result["step_clock_seconds"] = timing_contract["step_clock_seconds"]
            foul_result["resolution_step_index"] = timing_contract["resolution_step_index"]
            foul_result["executed_step_count"] = timing_contract["executed_step_count"]
            foul_result["bringup_per_player_seconds"] = timing_contract.get("bringup_per_player_seconds") or {}
            # Add skeleton to result. Legacy ``animations[]`` no longer stamped
            # on HCO results (Phase 2 of UESS migration); schema emitter builds
            # them internally.
            foul_result["skeleton"] = skeleton or {}
            # ✅ ADD LEAN METER VALUE: Add raw result value (-100 to +100) to text for frontend parsing
            lean_value = game_state.get("lean_result_value", 0)
            if "lean:" not in foul_result.get("text", ""):
                foul_result["text"] = foul_result.get("text", "") + f" lean:{lean_value:.1f}"
            # ✅ FIX: Add serializable roles data (only include fields needed for frontend, not Player objects)
            # Include steps if they exist (needed for capture_halfcourt_animation fallback)
            # Note: action_timeline uses Player objects as keys, so it can't be serialized - it will be empty dict in fallback
            serializable_roles = {}
            if roles.get("is_steal_hco_setup"):
                serializable_roles["is_steal_hco_setup"] = True
                serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
                serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
                serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
                serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
                serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
                serializable_roles["other_players_hco_setup_movements"] = roles.get("other_players_hco_setup_movements", [])
                serializable_roles["hco_setup_x_direction"] = roles.get("hco_setup_x_direction")
            # ✅ FIX: Include steps if they exist (needed for animation fallback)
            # action_timeline is NOT included because it uses Player objects as keys (not JSON-serializable)
            if "steps" in roles:
                serializable_roles["steps"] = roles["steps"]
            if serializable_roles:
                foul_result["roles"] = serializable_roles
            attach_position_snapshots(
                foul_result,
                [
                    build_phase_post_stopper_snapshot(
                        game,
                        off_lineup,
                        def_lineup,
                        skeleton,
                        roles,
                        "HCO",
                        "non_shooting_foul",
                        "hco_o_foul_post_stopper",
                    )
                ],
            )
            return foul_result

        elif event_type == "D_FOUL":
            game_state["foul_team"] = "DEFENSE"
            foul_result = resolve_non_shooting_foul(roles, game)
            timing_contract = calc_skeleton_step_timing_contract(
                roles.get("steps", []),
                resolution_step_index=roles.get("event_step"),
                include_hco_step1_bringup=True,
                phase_type="HCO",
                off_lineup=game.offense_team.lineup,
            )
            foul_result["time_elapsed"] = timing_contract["time_elapsed"]
            foul_result["step_clock_seconds"] = timing_contract["step_clock_seconds"]
            foul_result["resolution_step_index"] = timing_contract["resolution_step_index"]
            foul_result["executed_step_count"] = timing_contract["executed_step_count"]
            foul_result["bringup_per_player_seconds"] = timing_contract.get("bringup_per_player_seconds") or {}
            # Add skeleton to result. Legacy ``animations[]`` no longer stamped
            # on HCO results (Phase 2 of UESS migration); schema emitter builds
            # them internally.
            foul_result["skeleton"] = skeleton or {}
            # ✅ ADD LEAN METER VALUE: Add raw result value (-100 to +100) to text for frontend parsing
            lean_value = game_state.get("lean_result_value", 0)
            if "lean:" not in foul_result.get("text", ""):
                foul_result["text"] = foul_result.get("text", "") + f" lean:{lean_value:.1f}"
            # ✅ FIX: Add serializable roles data (only include fields needed for frontend, not Player objects)
            # Include steps and action_timeline if they exist (needed for capture_halfcourt_animation fallback)
            serializable_roles = {}
            if roles.get("is_steal_hco_setup"):
                serializable_roles["is_steal_hco_setup"] = True
                serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
                serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
                serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
                serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
                serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
                serializable_roles["other_players_hco_setup_movements"] = roles.get("other_players_hco_setup_movements", [])
                serializable_roles["hco_setup_x_direction"] = roles.get("hco_setup_x_direction")
            # ✅ FIX: Include steps if it exists (needed for animation fallback)
            # Note: action_timeline is NOT included because it uses Player objects as keys (not JSON-serializable)
            # capture_halfcourt_animation will handle missing action_timeline gracefully
            if "steps" in roles:
                serializable_roles["steps"] = roles["steps"]
            if serializable_roles:
                foul_result["roles"] = serializable_roles
            attach_position_snapshots(
                foul_result,
                [
                    build_phase_post_stopper_snapshot(
                        game,
                        off_lineup,
                        def_lineup,
                        skeleton,
                        roles,
                        "HCO",
                        "non_shooting_foul",
                        "hco_d_foul_post_stopper",
                    )
                ],
            )
            return foul_result

    # 3. Shot Result
    # UESS single-coord-source (§1/§7, HCO_UESS_Audit.md Task 1): DEFER the animator
    # build until the skeleton is finalized. Motion / dynamic set-play rewrite the
    # skeleton below (adding pass/receive steps, changing the shooter), so building
    # here — before those edits — made resolve_shot read one build while the FE
    # rendered another (a different RNG draw and, for Motion, a different skeleton).
    # We now build ONCE from the finalized skeleton just before apply_coords, and
    # stamp it onto shot_result so the step emitter reuses the exact build
    # resolve_shot's coords came from.
    animations = []

    # ✅ MOTION OFFENSE: Check if this is a Motion play and route to Motion shot logic
    offense_play_type = game_state.get("offense_play_type", "")
    is_motion_play = offense_play_type == "motion"
    
    # 🔍 DEBUG: Log offense_play_type read (SECOND READ - shot routing)
    # logging.warning(f"🔍 [HCO RESOLVE DEBUG] SECOND READ - offense_play_type from game_state: '{offense_play_type}' (type: {type(offense_play_type)})")
    # logging.warning(f"🔍 [HCO RESOLVE DEBUG] SECOND READ - is_motion_play: {is_motion_play}")
    # logging.warning(f"🔍 [HCO RESOLVE DEBUG] SECOND READ - event_type: '{event_type}'")
    # logging.warning(f"🔍 [HCO RESOLVE DEBUG] SECOND READ - Will call resolve_motion_offense_shot: {is_motion_play and event_type == 'SHOT'}")
    
    # Dynamic HCO Set Plays (Stage B, flagged): a set play whose SHOT runs the per-step dynamic
    # overlay produces the SAME shot-info contract as a Motion shot, so it reuses the roles-update
    # path below verbatim. Off by default; on None/error it falls through to the standard set-play
    # shot path (no behavior change).
    is_setplay_dynamic = (
        not is_motion_play
        and offense_play_type == "set_play"
        and event_type == "SHOT"
        and _dynamic_hco_setplay_enabled()
    )

    if (is_motion_play or is_setplay_dynamic) and event_type == "SHOT":
        if is_setplay_dynamic:
            logging.warning("🟢 [DYNAMIC SETPLAY] flag ON — running dynamic resolver for this Set Play shot")
            try:
                motion_shot_info = _resolve_hco_offense_shot_dynamic(skeleton, game, off_lineup, def_lineup, is_setplay=True)
                if motion_shot_info is None:
                    logging.info("ℹ️ [DYNAMIC SETPLAY] Resolver returned None; using standard set-play shot path")
            except Exception as e:
                logging.warning(f"⚠️ [DYNAMIC SETPLAY] Error in dynamic resolver, falling back to standard path: {e}")
                motion_shot_info = None
        else:
            # Motion play shot resolution (or use precomputed recalibration from shot-clock path)
            motion_shot_info = game_state.pop("_motion_shot_recalibrated", None)
            if not motion_shot_info:
                motion_shot_info = resolve_motion_offense_shot(skeleton, game, off_lineup, def_lineup)

        # Coverage: contest any pass in the FINAL skeleton the per-step resolver didn't already
        # contest (legacy resolve / recalibration / expansion). Mutates motion_shot_info in place →
        # routes through the same interception finalize below.
        _hco_contest_final_skeleton(motion_shot_info, game, off_lineup, def_lineup, game_state)

        # §4 Stage 2: a dish/kickout picked off in the lane → STEAL (interception), not a shot.
        if motion_shot_info and motion_shot_info.get("pass_intercepted"):
            # BAT_OOB → offense retains (side inbound, no stats); INTERCEPT → STEAL turnover.
            if motion_shot_info.get("pass_bat_oob"):
                return _finalize_hco_pass_bat_oob(
                    motion_shot_info, game, roles, off_lineup, def_lineup, game_state)
            return _finalize_hco_pass_interception(
                motion_shot_info, game, roles, off_lineup, def_lineup, game_state)

        if motion_shot_info:
            # Update skeleton with Motion shot modifications
            skeleton = motion_shot_info["skeleton"]
            
            # ✅ FIX 1: Update roles["steps"] with modified skeleton steps for 3-point detection
            # The shot detection logic looks in roles["steps"], so we need to update it
            if "steps" in skeleton:
                roles["steps"] = skeleton["steps"]
            
            # Update roles with Motion shot information
            roles["shooter"] = motion_shot_info["shooter"]
            roles["shooter_pos"] = motion_shot_info["shooter_pos"]
            roles["shooter_location"] = motion_shot_info["shooter_location"]
            roles["motion_shot_type"] = motion_shot_info["shot_type"]
            roles["motion_playcall"] = motion_shot_info["playcall"]
            # attack_penalty (attack drives) + forced_shot_penalty (subtle shot-clock-expiry
            # forced shot) both subtract from shot_score via shot_manager's motion penalty path.
            roles["motion_attack_penalty"] = (
                motion_shot_info["attack_penalty"] + motion_shot_info.get("forced_shot_penalty", 0)
            )
            if motion_shot_info.get("motion_attack_geometry_contest"):
                roles["motion_attack_geometry_contest"] = True
            if motion_shot_info.get("motion_attack_uncontested"):
                roles["motion_attack_uncontested"] = True
            if motion_shot_info.get("motion_attack_defense_bonus"):
                roles["motion_attack_defense_bonus"] = motion_shot_info["motion_attack_defense_bonus"]
            if motion_shot_info.get("motion_attack_driver_shoots") is not None:
                roles["motion_attack_driver_shoots"] = motion_shot_info["motion_attack_driver_shoots"]
            
            # ✅ FIX: Re-derive passer from modified skeleton (Motion plays add pass/receive steps)
            # Use the same criteria as Set Plays: last pass to shooter within 5 steps, pass/receive in same step
            # This ensures assists are tracked correctly for Motion plays, matching Set Play behavior
            if "steps" in skeleton and roles.get("shooter_pos"):
                passer_pos = game.turn_manager.derive_passer_from_steps(skeleton["steps"], roles["shooter_pos"])
                
                if passer_pos:
                    # Convert passer_pos to Player object
                    passer = off_lineup.get(passer_pos)
                    if passer:
                        roles["passer"] = passer
                        roles["passer_pos"] = passer_pos
                    else:
                        # Fallback: passer_pos not found in lineup (shouldn't happen, but safety check)
                        roles["passer"] = None
                        roles["passer_pos"] = None
                else:
                    # No valid passer found (pass too far or no pass to shooter)
                    roles["passer"] = None
                    roles["passer_pos"] = None
            
            # Store attack penalty in game_state for shot calculation
            if motion_shot_info["attack_penalty"] > 0:
                game_state["motion_attack_penalty"] = motion_shot_info["attack_penalty"]
    
    # Resolve shot (standard logic for Set Plays, Motion-specific logic applied above)
    # UESS single build: the skeleton is now finalized (Motion / dynamic set-play
    # edits applied above). Build the animation ONCE and reuse it for coord-sync,
    # resolve_shot, and (stamped below) the step emitter.
    if skeleton and "steps" in skeleton:
        animations = Animator(game).skeleton_to_animations(
            skeleton,
            off_lineup,
            def_lineup,
            add_defenders=True,
        )
    apply_coords_from_animations_list(game, animations)
    # UESS single-coord-source: sync ALL players (shooter + defenders) to the
    # emitter's rendered shoot-step coords so classification (2PT/3PT) AND the
    # contest loop read the on-screen geometry, not the animator row-end.
    _terminal_shoot = _uess_sync_emitted_shot_coords(game, skeleton, animations, roles, "HCO")
    if _terminal_shoot is not None:
        roles["shot_spot"] = dict(_terminal_shoot)
    else:
        set_shooter_coords_from_skeleton_last_step(game, skeleton, roles)  # fallback: skeleton shot location
    hco_snap = build_hco_pre_resolve_shot_snapshot(game, off_lineup, def_lineup, skeleton, roles)
    shot_result = game.shot_manager.resolve_shot(roles)
    attach_position_snapshots(shot_result, [hco_snap])
    # UESS single-coord-source: reuse the finalized single build for the step
    # emitter (mirrors the FCP shot path at ~L7855). build_skeleton_animation_steps
    # consumes shot_result["animations"] instead of rebuilding from the skeleton
    # with a fresh RNG draw, so the coords the FE renders == the coords
    # resolve_shot decided the shot from.
    if animations:
        shot_result["animations"] = animations

    # Player Momentum: a SET PLAY whose EXECUTED skeleton is the "successful"
    # variant routes the ball to the target_shooter by design, so a make here is
    # the target_shooter scoring on the set play → +MO_SET_PLAY_DELTA to the
    # shooter (Player_Momentum_System.md). Motion plays have no target shooter.
    # NOTE: key on the executed skeleton's `_variant` (set in get_hco_skeleton),
    # NOT `variant_result` from resolve_hco_outcome — get_skeleton_by_lean falls
    # back to the successful skeleton when the resolved variant has none, so the
    # successful skeleton can run even when variant_result is something else.
    if (not is_motion_play
            and skeleton
            and skeleton.get("_variant") == "successful"
            and shot_result.get("result_type") == "MAKE"):
        _sp_shooter = roles.get("shooter")
        if _sp_shooter is not None:
            _sp_shooter.add_momentum(MO_SET_PLAY_DELTA)

    # Shot-at-1 path: set time_elapsed so shot clock ends at 1 (Shot_Clock_System.md)
    if "_shot_at_one_second_time_elapsed" in game_state:
        shot_result["time_elapsed"] = game_state.pop("_shot_at_one_second_time_elapsed")
    
    # Add playcall and variant debug info to the text
    variant = skeleton.get("_variant", "unknown") if skeleton else "unknown"
    variant_modifiers = {
        "successful": -50,
        "mid_play_change": 0,
        "contested": 25,
        "broken": 100
    }
    modifier = variant_modifiers.get(variant, 0)
    
    # Use variant_result from resolution system (replaces lean_score)
    variant_display = variant_result if variant_result else variant
    debug_info = f"[{off_call}] {variant_display}, modifier:{modifier:+d} | "
    shot_result["text"] = debug_info + shot_result.get("text", "")
    
    # ✅ ADD LEAN METER VALUE: Add raw result value (-100 to +100) to text for frontend parsing
    lean_value = game_state.get("lean_result_value", 0)
    if "lean:" not in shot_result.get("text", ""):
        shot_result["text"] = shot_result.get("text", "") + f" lean:{lean_value:.1f}"
    
    # Pass next_defensive_setup to animator via roles
    if "next_defensive_setup" in shot_result:
        roles["next_defensive_setup"] = shot_result["next_defensive_setup"]
    
    animator = Animator(game)
    # OLD ANIMATION SYSTEM - REMOVED (conflicts with skeleton-based system)
    # shot_result["animations"] = animator.capture_halfcourt_animation(roles)
    
    # Add skeleton data for unified animation system (reuse skeleton from line 556)
    shot_result["skeleton"] = skeleton or {}
    # Add skeleton variant for debugging (temporary - will be removed after debugging)
    if skeleton and "_variant" in skeleton:
        shot_result["skeleton_variant"] = skeleton["_variant"]
    
    # ✅ FIX 2: Add playcall name to result for Playcall Center display (Motion plays)
    if is_motion_play:
        shot_result["offensive_playcall"] = game_state["current_playcall"]
        shot_result["current_playcall"] = game_state["current_playcall"]  # Also set current_playcall for compatibility
    
    # ✅ Add serializable roles data to result (includes steal HCO setup data if applicable)
    # Only include serializable fields, not player objects
    # Note: turn_manager.convert_players() will handle player objects in other result fields,
    # but we only store the specific fields we need here to avoid serialization issues
    # ✅ FIX: Include steps if it exists (needed for animation fallback)
    # Note: action_timeline is NOT included because it uses Player objects as keys (not JSON-serializable)
    # capture_halfcourt_animation will handle missing action_timeline gracefully
    serializable_roles = {}
    if roles.get("is_steal_hco_setup"):
        serializable_roles["is_steal_hco_setup"] = True
        serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
        serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
        serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
        serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
        serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
    if roles.get("next_defensive_setup"):
        serializable_roles["next_defensive_setup"] = roles.get("next_defensive_setup")
    if roles.get("intended_shooter_pos"):
        serializable_roles["intended_shooter_pos"] = roles.get("intended_shooter_pos")
    # ✅ FIX: Include steps if it exists (needed for animation fallback)
    if "steps" in roles:
        serializable_roles["steps"] = roles["steps"]
    if serializable_roles:  # Only add roles if we have something to add
        shot_result["roles"] = serializable_roles
    
    # Phase 2 of HCO UESS migration: legacy ``animations[]`` is no longer
    # stamped on HCO shot results. The schema emitter (skeleton_step_emitter)
    # builds them internally from the skeleton when assembling
    # ``animation_steps[]``. The animator call previously here is dropped.

    # 4. scouting report update (new buckets)
    try:
        play_type = game.game_state.get("offense_play_type")  # 'motion' or 'set_play'
        # ✅ MOTION OFFENSE: Use actual shot type for Motion plays, intended focus for Set Plays
        if play_type == "motion":
            # For Motion plays, use the actual shot type that was attempted
            motion_shot_type = roles.get("motion_shot_type")  # 'inside', 'attack', or 'outside'
            focus = motion_shot_type if motion_shot_type in ["inside", "attack", "outside"] else game.game_state.get("offense_play_focus", "")
            # Set offense_play_focus to motion_shot_type for execution score storage
            if motion_shot_type in ["inside", "attack", "outside"]:
                game.game_state["offense_play_focus"] = motion_shot_type
        else:
            # For Set Plays, use the intended focus from strategy settings
            focus = game.game_state.get("offense_play_focus")     # 'inside' | 'attack' | 'outside'
        type_label = "Motion" if play_type == "motion" else ("Set" if play_type == "set_play" else None)
        if type_label and focus in ["inside", "attack", "outside"]:
            pc = off_team.scouting_data["offense"]["Playcalls"]
            
            # ✅ MOTION OFFENSE: Track attempts using actual shot type (after shot resolution)
            # Set Plays: Attempts already tracked in turn_manager.py using intended focus
            if play_type == "motion":
                # Track attempts for Motion plays using actual shot type
                pc[type_label]["overall"]["attempts"] += 1
                pc[type_label][focus]["attempts"] += 1
                pc["Cumulative"][focus]["attempts"] += 1
                
                # Track granular attempts against defensive playcall
                from BackEnd.utils.defense_utils import is_zone_defense
                defense_playcall = game.game_state.get("defense_playcall", "man")
                vs_key = offense_vs_key_from_defense_input(defense_playcall)
                
                if vs_key:
                    # Overall attempts vs defense
                    if vs_key in pc[type_label]["overall"]:
                        pc[type_label]["overall"][vs_key]["attempts"] += 1
                    # Focus attempts vs defense
                    if vs_key in pc[type_label][focus]:
                        pc[type_label][focus][vs_key]["attempts"] += 1
                    
                    # Track aggregate vs_zone for any zone type
                    if is_zone_defense(defense_playcall) and "vs_zone" in pc[type_label]["overall"]:
                        pc[type_label]["overall"]["vs_zone"]["attempts"] += 1
                        pc[type_label][focus]["vs_zone"]["attempts"] += 1
            
            rt = shot_result.get("result_type")
            foul_team = game.game_state.get("foul_team")
            # print(f"🎯 SUCCESS DEBUG: rt={rt}, foul_team={foul_team}")
            # Offense success conditions: made shot OR any defensive foul (shooting or non-shooting)
            # Note: When defensive foul occurs on a missed shot, rt is still "MISS" but foul_team is "DEFENSE"
            offense_success = (rt == "MAKE") or (foul_team == "DEFENSE")
            # print(f"🎯 SUCCESS DEBUG: offense_success={offense_success}, rt=='MAKE'={rt == 'MAKE'}, foul_team=='DEFENSE'={foul_team == 'DEFENSE'}")
            # if rt == "MAKE":
            #     print(f"🎯 MADE SHOT SUCCESS: Play type={type_label}, focus={focus} - should increment success")
            # Defense success conditions
            offense_failure = (rt == "MISS" and not (foul_team == "DEFENSE")) or (rt == "TURNOVER") or (rt == "O_FOUL")
            # print(f"🎯 SUCCESS DEBUG: offense_failure={offense_failure}")
            if offense_success:
                # print(f"🎯 SUCCESS DEBUG: Incrementing success for {type_label}/{focus}")
                # print(f"🎯 SUCCESS DEBUG: Before - overall: {pc[type_label]['overall']['success']}, {focus}: {pc[type_label][focus]['success']}, Cumulative: {pc['Cumulative'][focus]['success']}")
                pc[type_label]["overall"]["success"] += 1
                pc[type_label][focus]["success"] += 1
                pc["Cumulative"][focus]["success"] += 1
                
                # Track granular success against defensive playcall
                from BackEnd.utils.defense_utils import is_zone_defense
                defense_playcall = game.game_state.get("defense_playcall", "man")
                vs_key = offense_vs_key_from_defense_input(defense_playcall)
                
                if vs_key:
                    # Overall success vs defense
                    if vs_key in pc[type_label]["overall"]:
                        pc[type_label]["overall"][vs_key]["success"] += 1
                    # Focus success vs defense
                    if vs_key in pc[type_label][focus]:
                        pc[type_label][focus][vs_key]["success"] += 1
                    
                    # Track aggregate vs_zone for any zone type
                    if is_zone_defense(defense_playcall) and "vs_zone" in pc[type_label]["overall"]:
                        pc[type_label]["overall"]["vs_zone"]["success"] += 1
                        pc[type_label][focus]["vs_zone"]["success"] += 1
                
                # print(f"🎯 SUCCESS DEBUG: After - overall: {pc[type_label]['overall']['success']}, {focus}: {pc[type_label][focus]['success']}, Cumulative: {pc['Cumulative'][focus]['success']}")
            elif offense_failure:
                # We don't increment offense success; defensive success can be tracked separately if needed
                pass
            
            # ✅ Track offensive play stats (times_run, successes, player_points)
            # Get current playcall name and offensive team's plays dict
            current_playcall = game.game_state.get("current_playcall")
            if current_playcall and hasattr(off_team, 'plays') and off_team.plays:
                from BackEnd.utils.team_play_utils import resolve_team_play
                play_obj = resolve_team_play(off_team.plays, current_playcall)
                if play_obj:
                    # Always increment times_run
                    if "game_stats" in play_obj:
                        play_obj["game_stats"]["times_run"] = play_obj["game_stats"].get("times_run", 0) + 1
                    
                    # Track success if offense succeeded
                    if offense_success:
                        if "game_stats" in play_obj:
                            play_obj["game_stats"]["successes"] = play_obj["game_stats"].get("successes", 0) + 1
                    
                    # Track player points if shot was made (rt == "MAKE")
                    if rt == "MAKE":
                        shooter = roles.get("shooter")
                        if shooter:
                            shooter_id = getattr(shooter, "player_id", None)
                            if shooter_id:
                                # Get points from shot_result (2 or 3)
                                points = shot_result.get("points", 0)
                                if points > 0:
                                    # Initialize player_points dict if needed
                                    if "game_stats" not in play_obj:
                                        play_obj["game_stats"] = {}
                                    if "player_points" not in play_obj["game_stats"]:
                                        play_obj["game_stats"]["player_points"] = {}
                                    
                                    # Increment player's points for this play
                                    player_points = play_obj["game_stats"]["player_points"]
                                    old_points = player_points.get(shooter_id, 0)
                                    player_points[shooter_id] = old_points + points
            
            # Track defensive playcall success with granular tracking
            defense_playcall = game.game_state.get("defense_playcall", "man")
            tracking_name = defense_scouting_row_key(defense_playcall)
            if tracking_name in def_team.scouting_data["defense"]:
                # Defense success = MISS (without defensive foul) OR TURNOVER OR O_FOUL
                # Defense failure = MAKE OR DEFENSIVE FOUL
                defense_success = (rt == "MISS" and not (foul_team == "DEFENSE")) or (rt == "TURNOVER") or (rt == "O_FOUL")
                defense_failure = (rt == "MAKE") or (foul_team == "DEFENSE")
                
                # Get offensive play type and focus for granular tracking
                offense_play_type = game.game_state.get("offense_play_type", "").lower()  # "motion" or "set_play"
                offense_focus = game.game_state.get("offense_play_focus", "")  # "inside", "attack", "outside"
                
                # Normalize play type (set_play -> set)
                if offense_play_type == "set_play":
                    offense_play_type = "set"
                
                if defense_success:
                    def_team.scouting_data["defense"][tracking_name]["success"] += 1
                    def_team.scouting_data["defense"][tracking_name]["game_stats"]["success"] += 1
                    
                    # Track granular success by play type
                    if offense_play_type == "motion":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_motion"]["success"] += 1
                    elif offense_play_type == "set":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_set"]["success"] += 1
                    
                    # Track granular success by focus type
                    if offense_focus in ["inside", "attack", "outside"]:
                        def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_{offense_focus}"]["success"] += 1
                        
                        # Track combination of play type + focus
                        if offense_play_type == "motion":
                            def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_motion_{offense_focus}"]["success"] += 1
                        elif offense_play_type == "set":
                            def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_set_{offense_focus}"]["success"] += 1
                elif defense_failure:
                    # Defense failed (offense scored or committed defensive foul)
                    pass  # Don't increment success (already at current count)
            
            # Clear foul_team after success tracking to prevent it from affecting subsequent actions (like putbacks)
            # Note: Only clear if this is the original HCO play, not a putback (putbacks have result_type PUTBACK_MAKE/PUTBACK_MISS)
            if rt in ["MAKE", "MISS"]:
                game.game_state["foul_team"] = None
                # print(f"🎯 SUCCESS DEBUG: Cleared foul_team after HCO play (rt={rt})")
        else:
            pass
            # print(f"🎯 SUCCESS DEBUG: Skipping - type_label={type_label}, focus={focus}")
    except Exception as e:
        # Error logging kept - important for debugging actual errors
        logging.error(f"🎯 SUCCESS DEBUG ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    return shot_result


def calculate_foul_turnover(game, positions, roles):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    roles["foul_player"] = None
    ball_handler = roles["ball_handler"]
    defense_call = game_state["defense_playcall"]

    # === Defensive Foul ===
    d_pos = positions["d_foul"]
    d_foul_player = def_lineup[d_pos]
    d_attr = d_foul_player.attributes

    d_movement = (
        d_attr["OD"] * 0.2 + d_attr["AG"] * 0.2 if d_pos in ["PG", "SG"] else
        d_attr["OD"] * 0.1 + d_attr["ID"] * 0.1 + d_attr["AG"] * 0.1 + d_attr["ST"] * 0.1 if d_pos == "SF" else
        d_attr["ID"] * 0.2 + d_attr["ST"] * 0.2 if d_pos in ["PF", "C"] else
        0
    )

    d_foul_score = (d_attr["IQ"] * 0.3 + d_attr["CH"] * 0.3 + d_movement) * random.randint(1, 6)
    from BackEnd.utils.defense_utils import is_zone_defense
    if is_zone_defense(defense_call):
        d_foul_score *= 1.1
    is_d_foul = d_foul_score < def_team.team_attributes["fight"] * 1.2

    # === Offensive Foul ===
    o_pos = positions["o_foul"]
    o_foul_player = off_lineup[o_pos]
    o_attr = o_foul_player.attributes

    o_movement = (
        o_attr["AG"] * 0.4 if o_pos in ["PG", "SG"] else
        o_attr["AG"] * 0.2 + o_attr["ST"] * 0.2 if o_pos == "SF" else
        o_attr["ST"] * 0.4 if o_pos in ["PF", "C"] else
        0
    )

    o_foul_score = (o_attr["IQ"] * 0.3 + o_attr["CH"] * 0.3 + o_movement) * random.randint(1, 6)
    is_o_foul = o_foul_score < off_team.team_attributes["fight"] * 0.8

    # === Turnover ===
    t_pos = positions["turnover"]
    turnover_player = off_lineup[t_pos]
    t_attr = turnover_player.attributes

    bh_score = (
        t_attr["BH"] * 0.5 +
        t_attr["AG"] * 0.2 +
        t_attr["IQ"] * 0.2 +
        t_attr["CH"] * 0.1
    ) * random.randint(1, 6)

    def_mod_player = def_lineup[t_pos]
    def_mod_attr = def_mod_player.attributes

    pressure = (
        def_mod_attr["OD"] * 0.3 +
        def_mod_attr["AG"] * 0.3 +
        def_mod_attr["IQ"] * 0.2 +
        def_mod_attr["CH"] * 0.2
    ) * random.randint(1, 6)
    from BackEnd.utils.defense_utils import is_zone_defense
    if is_zone_defense(defense_call):
        pressure *= 0.9

    turnover_score = bh_score - pressure
    is_turnover = turnover_score < off_team.team_attributes["discipline"]

    # === Decide event type
    decisions = {
        "TURNOVER": (is_turnover, turnover_score),
        "D_FOUL": (is_d_foul, d_foul_score),
        "O_FOUL": (is_o_foul, o_foul_score),
    }

    active = [(k, v[1]) for k, v in decisions.items() if v[0]]
    if not active:
        return "SHOT"

    # Prioritize by score, then priority: TURNOVER > D_FOUL > O_FOUL
    active.sort(key=lambda x: (x[1], ["TURNOVER", "D_FOUL", "O_FOUL"].index(x[0])))

    event_type = active[0][0]
    if event_type == "TURNOVER":
        roles["turnover_player"] = turnover_player
        roles["turnover_defender"] = def_mod_player
        roles["ball_handler"] = turnover_player
    elif event_type == "D_FOUL":
        roles["foul_player"] = d_foul_player
    elif event_type == "O_FOUL":
        roles["foul_player"] = o_foul_player

    return event_type


def resolve_full_court_press_logic(game: "GameManager"):
    """
    Resolve full court press defensive pressure.
    Returns turn data with FCP result and potential progression to HCO.
    """
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    # ✅ Apply energy decay for active players during FCP
    # ✅ FCP DEFENSIVE PLAYERS: Omit zeros from depletion list for defensive players (they always lose some energy)
    apply_energy_decay(off_lineup, def_lineup, omit_zeros_for_defense=True)
    
    # Track FCP attempt (defensive team)
    def_scouting = def_team.scouting_data
    def_scouting["defense"]["FCP"]["used"] += 1

    text = "PRESS!"

    if USE_DYNAMIC_FCP:
        return _resolve_full_court_press_dynamic_first_cut(
            game, def_scouting, text=text
        )

    offenseScore = 0
    defenseScore = 0

    for pos, player in off_lineup.items():
        if pos == "PG":
            offenseScore += 3 * (player.attributes["BH"] * 0.6 + player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2)
        elif pos in ["SG", "SF"]:
            offenseScore += (player.attributes["BH"] * 0.6 + player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2)
    for pos, player in def_lineup.items():
        if pos == "PG":
            defenseScore += 3 * (player.attributes["OD"] * 0.4 + player.attributes["AG"] * 0.4 + player.attributes["IQ"] * 0.2)
        elif pos in ["SG", "SF"]:
            defenseScore += (player.attributes["OD"] * 0.4 + player.attributes["AG"] * 0.4 + player.attributes["IQ"] * 0.2)
    
    offenseScore *= random.randint(1, 6)
    defenseScore *= random.randint(1, 6)
    turnover_type = random.choices(["TRAVEL", "DOUBLE DRIBBLE", "BAD PASS"], weights=[0.6, 0.3, 0.1])[0]
    
    # Get team attributes for BSM and DST calculations
    off_attrs = off_team.team_attributes
    def_attrs = def_team.team_attributes
    
    off_chemistry = off_attrs.get("team_chemistry", 10)
    def_chemistry = def_attrs.get("team_chemistry", 10)
    off_pt_opp_modifier = off_attrs.get("pt_opp_modifier", 0)
    def_pt_efficiency = def_attrs.get("pt_efficiency", 0)
    def_discipline = def_attrs.get("discipline", 0)
    off_fight = int(off_attrs.get("fight", 0))
    
    # Calculate BSM (Base Success Modifier): 400 + (10 * offense fight), then chemistry adjustments (FCP_HCT_System.md)
    BSM = 400 + (10 * off_fight)
    
    # Offense contribution to BSM (using pt_opp_modifier)
    if off_pt_opp_modifier > 0:
        BSM += random.randint(1, off_chemistry) * off_pt_opp_modifier
    else:
        BSM += random.randint(1, off_chemistry)
    
    # Defense reduction to BSM (using pt_efficiency)
    if def_pt_efficiency > 0:
        BSM -= random.randint(1, def_chemistry) * def_pt_efficiency
    else:
        BSM -= random.randint(1, def_chemistry)
    
    # Calculate DST (Defense Safety Threshold) = 600 for FCP
    DST = 600
    
    # Defense contribution to DST
    if def_discipline > 0:
        DST += random.randint(1, def_chemistry) * def_discipline
    else:
        DST += random.randint(1, def_chemistry)
    
    # Real FCP result calculation using BSM and DST
    if (offenseScore + BSM) > defenseScore:
        # Success
        if offenseScore - defenseScore > DST:
            # Dominant success - weighted random (FCP_HCT_System.md: D_FOUL 30%, HCO 40%, SHOT 30%)
            result_type = random.choices(["D_FOUL", "HCO", "SHOT"], weights=[0.3, 0.4, 0.3])[0]
        else:
            # Regular success - just break through
            result_type = "HCO"
    else:
        # Failure - weighted random
        result_type = random.choices(["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"], weights=[0.2, 0.5, 0.3])[0]
    
    result_text_dict = {
        "HCO": "they break the press & establish their half court offense",
        "D_FOUL": "defensive foul!",
        "O_FOUL": "offensive foul!",
        "DEAD_BALL_TURNOVER": f"they force a {turnover_type}!",
        "STEAL": "steal!",
        "SHOT": "they break the press & attempt a shot!"
    }
    
    text += "\n" + result_text_dict[result_type]

    # Initialize shot_result for all cases
    shot_result = {}
    
    # Initialize animator for all cases
    from BackEnd.models.animator import Animator
    animator = Animator(game)
    animations = []
    
    # Handle SHOT result - execute actual shot resolution
    if result_type == "SHOT":
        # ✅ Get skeleton first (needed to determine shooter and passer dynamically)
        skeleton = get_fcp_skeleton("SHOT", game) or {}
        if skeleton and "steps" in skeleton and skeleton.get("steps"):
            skeleton = copy.deepcopy(skeleton)
            start_index = _get_fcp_hct_post_inbound_start_index(skeleton, game)
            skeleton["steps"] = skeleton["steps"][start_index:]
        
        # ✅ Dynamically determine shooter and passer from skeleton
        shooter = None
        shooter_pos = None
        passer = None
        passer_pos = None
        
        if skeleton and "steps" in skeleton and skeleton["steps"]:
            steps = skeleton["steps"]
            # Find shooter from final step (player with "shoot" action)
            final_step = steps[-1]
            pos_actions = final_step.get("pos_actions", {})
            
            for pos, action_info in pos_actions.items():
                action = action_info.get("action", "").lower()
                if action == "shoot":
                    shooter_pos = pos
                    shooter = off_lineup.get(pos)
                    break
            
            # Fallback: use last ball handler if no shooter found
            if not shooter:
                ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
                shooter = ball_handler
                shooter_pos = getattr(ball_handler, 'position', None) or "PG"
            
            # Find passer using derive_passer_from_steps (same logic as HCO)
            if shooter_pos:
                passer_pos = game.turn_manager.derive_passer_from_steps(steps, shooter_pos)
                if passer_pos:
                    passer = off_lineup.get(passer_pos)
        
        # Fallback: use hardcoded values if skeleton doesn't have shooter/passer
        if not shooter:
            shooter = random.choice([off_lineup.get("PF"), off_lineup.get("C")])
            shooter_pos = getattr(shooter, 'position', None) or "PF"
        if not passer:
            passer = off_lineup.get("PG", list(off_lineup.values())[0])
            passer_pos = getattr(passer, 'position', None) or "PG"
        
        # ✅ Find shooter's coordinates at the time of the shot
        shooter_coords = None
        if skeleton and "steps" in skeleton and skeleton["steps"]:
            final_step = skeleton["steps"][-1]
            pos_actions = final_step.get("pos_actions", {})
            if shooter_pos and shooter_pos in pos_actions:
                shooter_action_info = pos_actions[shooter_pos]
                shooter_coords = shooter_action_info.get("coords")
                if not shooter_coords:
                    # Fallback: use shooter's current coords
                    shooter_coords = getattr(shooter, "coords", {"x": 50, "y": 25})
        else:
            # Fallback: use shooter's current coords
            shooter_coords = getattr(shooter, "coords", {"x": 50, "y": 25})
        
        # ✅ Find closest defensive player to shooter's location
        defender = None
        closest_distance = float('inf')
        for pos, def_player in def_lineup.items():
            if def_player is None:
                continue
            def_coords = getattr(def_player, "coords", {"x": 50, "y": 25})
            distance = ((shooter_coords["x"] - def_coords["x"]) ** 2 + 
                       (shooter_coords["y"] - def_coords["y"]) ** 2) ** 0.5
            if distance < closest_distance:
                closest_distance = distance
                defender = def_player
        
        # Fallback: random defensive lineup slot if no defender found
        if not defender:
            defender = defender_player_from_random_slot_fallback(def_lineup)
        
        shot_roles = {
            "ball_handler": passer,
            "ball_handler_pos": passer_pos,
            "shooter": shooter,
            "shooter_pos": shooter_pos,
            "passer": passer,
            "passer_pos": passer_pos,
            "screener": None,
            "screener_pos": None,
            "defender": defender,
        }
        _ensure_skeleton_shot_role_positions(game, shot_roles)
        
        # Use shot manager to resolve the shot
        apply_coords_from_animations_list(game, animations)
        # UESS single-coord-source: sync ALL players to the emitter's rendered
        # shoot-step coords (classification + contest read on-screen geometry).
        _fcp_terminal = _uess_sync_emitted_shot_coords(game, skeleton, animations, shot_roles, "FCP")
        if _fcp_terminal is not None:
            shot_roles["shot_spot"] = dict(_fcp_terminal)
        else:
            set_shooter_coords_from_skeleton_last_step(game, skeleton, shot_roles)  # fallback: skeleton shot location
        fcp_snap = build_skeleton_pre_resolve_shot_snapshot(
            game, off_lineup, def_lineup, skeleton, shot_roles, "FCP", "fcp_pre_resolve_shot"
        )
        shot_result = game.shot_manager.resolve_shot(shot_roles)
        attach_position_snapshots(shot_result, [fcp_snap])
        
        # ✅ Handle AND-1 situations (MAKE with shooting foul)
        # Check for shooting foul on both MAKE and MISS
        free_throws_remaining = shot_result.get("free_throws_remaining") or game_state.get("free_throws_remaining", 0)
        has_and_one = shot_result.get("has_and_one", False)
        
        if shot_result.get("result_type") == "MAKE":
            if has_and_one or free_throws_remaining > 0:
                # AND-1 situation: Made shot with shooting foul
                game_state["offensive_state"] = "FREE_THROW"
                shot_result["next_play_type"] = "FREE_THROW"
                shot_result["next_turn"] = "FREE_THROW"
                shot_result["free_throws_remaining"] = free_throws_remaining
            else:
                # Regular make → route to BASELINE_INBOUND (pressure may apply again)
                game_state["offensive_state"] = "HCO"  # Will be set to BASELINE_INBOUND by transition system
        elif shot_result.get("result_type") in ["MISS", "BLOCK"]:
            if free_throws_remaining > 0:
                # Shooting foul on miss → preserve FREE_THROW state
                game_state["offensive_state"] = "FREE_THROW"
                shot_result["next_play_type"] = "FREE_THROW"
                shot_result["next_turn"] = "FREE_THROW"
                shot_result["free_throws_remaining"] = free_throws_remaining
            else:
                # Regular miss or block → reset to HCO
                game_state["offensive_state"] = "HCO"
                # Track MISS/BLOCK as defensive success for team
                def_scouting["defense"]["FCP"]["success"] += 1
        
        # Track FCP player stats for SHOT results
        fcp_roles = {
            "ball_handler": passer,
            "shooter": shooter,
            "defender": defender,
        }
        _record_fcp_stats(fcp_roles, shot_result, game, off_lineup, def_lineup)
        
        # Add FCP-specific data
        shot_result["fcp_shot"] = True
        shot_result["text"] = "PRESS! " + shot_result.get("text", "")
        shot_result["current_turn"] = "FCP"  # ✅ SS&S: Explicit turn type for transition system
        
        if skeleton and "steps" in skeleton:
            animations = animator.skeleton_to_animations(
                skeleton, 
                off_lineup, 
                def_lineup, 
                add_defenders=True,
                is_fcp=True
            )
            if animations:
                shot_result["animations"] = animations
        
        shot_result["skeleton"] = skeleton
        shot_result["roles"] = shot_roles
        
        return shot_result
    
    # ✅ FCP NON-SHOT: Get FCP "base" variant skeleton and apply stopper system
    # For non-shot results (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO), use FCP "base" variant
    # Apply stopper system if result is not HCO (truncate and add stopper step)
    # logging.warning(f"🔍 [FCP NON-SHOT] Getting FCP base skeleton for result_type={result_type}")
    skeleton = get_fcp_skeleton(result_type, game)  # Get FCP "base" variant (has step 0 with press break positions)
    
    # Deep copy skeleton to avoid mutating cached skeleton
    if skeleton:
        skeleton = copy.deepcopy(skeleton)
    
    # BIP already runs the inbound pass. Skip all leading inbound-left SF steps.
    if skeleton and "steps" in skeleton and skeleton.get("steps"):
        start_index = _get_fcp_hct_post_inbound_start_index(skeleton, game)
        skeleton["steps"] = skeleton["steps"][start_index:]
    
    # ✅ DEBUG: Log step 0 positions from HCO skeleton
    # if skeleton and "steps" in skeleton and len(skeleton.get("steps", [])) > 0:
    #     step_0 = skeleton["steps"][0]
    #     step_0_positions = step_0.get("pos_actions", {})
    #     logging.warning(f"🔍 [FCP NON-SHOT] HCO skeleton step 0 has {len(step_0_positions)} positions: {list(step_0_positions.keys())}")
    #     for pos, pos_action in step_0_positions.items():
    #         location = pos_action.get("location", "N/A")
    #         coords = pos_action.get("coords", "N/A")
    #         logging.warning(f"🔍 [FCP NON-SHOT] Step 0 {pos}: location={location}, coords={coords}")
    
    # Apply stopper system (truncates if needed, or returns full skeleton if result == "HCO")
    skeleton = apply_stopper_system_to_skeleton(skeleton, result_type, game_state)
    # logging.warning(f"🔍 [FCP NON-SHOT] Retrieved skeleton: has_steps={bool(skeleton.get('steps'))}, step_count={len(skeleton.get('steps', []))}")
    
    # ✅ DEBUG: Log step 0 positions AFTER stopper system (should still be there)
    # if skeleton and "steps" in skeleton and len(skeleton.get("steps", [])) > 0:
    #     step_0_after = skeleton["steps"][0]
    #     step_0_positions_after = step_0_after.get("pos_actions", {})
    #     logging.warning(f"🔍 [FCP NON-SHOT] After stopper, step 0 has {len(step_0_positions_after)} positions: {list(step_0_positions_after.keys())}")
    
    # ✅ Determine ball handler from skeleton (who actually has the ball)
    ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
    ball_handler_pos = getattr(ball_handler, 'position', None) or "PG"
    
    # ✅ Determine defender based on ball handler position (position matching for now)
    _fb = defender_player_from_random_slot_fallback(def_lineup)
    defender = def_lineup.get(ball_handler_pos) or _fb
    
    # Build roles dict for animation generation
    roles = {
        "ball_handler": ball_handler,
        "defender": defender,
        "shooter": ball_handler,
        "passer": None,
        "screener": None,
        "steps": skeleton.get("steps", []) if skeleton else [],
    }
    
    # Handle foul results - use standard foul types for frontend
    # ✅ FOUL OUT FIX: Initialize so result always has foul_out fields; capture when D_FOUL/O_FOUL
    foul_out_info = {"fouled_out": False, "foul_count": 0}
    if result_type == "D_FOUL":
        game_state["foul_team"] = "DEFENSE"
        # ✅ Use dynamically determined ball handler and defender
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("DEFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        def_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out and capture for result (so game_manager creates timeout + frontend shows popup)
        foul_out_info = check_and_handle_foul_out(foul_player, game_state, def_team, perform_removal=False)
        result_type = "FOUL"
        # ✅ FIX: Check bonus status for defensive fouls in FCP (per game_flows.md)
        # Defensive fouls should route to FREE_THROW if in bonus, otherwise HCO
        if def_team.team_fouls >= 10:
            # Double bonus (10+ fouls): 2 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2
            game_state["free_throws_remaining"] = 2
            game_state["one_and_one"] = False
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        elif def_team.team_fouls >= 5:
            # Bonus (5-9 fouls): 1 & 1 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2  # Maximum possible (if front end is made)
            game_state["free_throws_remaining"] = 1  # Start with 1 (front end)
            game_state["one_and_one"] = True
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        else:
            # Less than 5 fouls: possession change, side inbound
            game_state["offensive_state"] = "HCO"
            game_state["free_throws"] = 0
            game_state["free_throws_remaining"] = 0
        # text = "PRESS! Defensive foul"
    elif result_type == "O_FOUL":
        game_state["foul_team"] = "OFFENSE"
        # ✅ Use dynamically determined ball handler
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("OFFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        off_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out and capture for result (so game_manager creates timeout + frontend shows popup)
        foul_out_info = check_and_handle_foul_out(foul_player, game_state, off_team, perform_removal=False)
        result_type = "FOUL"
        # text = "PRESS! Offensive foul"
        # Track FCP success: offensive foul = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
    elif result_type == "DEAD_BALL_TURNOVER":
        result_type = "DEAD BALL"
        # text = "PRESS! Turnover"
        # ✅ Use dynamically determined ball handler
        # Record TO stat for the ball handler
        ball_handler.record_stat("TO")
        # Track FCP success: turnover = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
    elif result_type == "STEAL":
        # ✅ Use dynamically determined ball handler and defender
        # Record TO stat for the ball handler (victim of steal)
        ball_handler.record_stat("TO")
        # Record STL stat for the defender (guarding ball handler)
        if defender:
            defender.record_stat("STL")
            # Player Momentum: steal → stealer +, victim − (Player_Momentum_System.md).
            defender.add_momentum(MO_STEAL_DELTA)
            if ball_handler:
                ball_handler.add_momentum(-MO_STEAL_DELTA)
        # Track FCP success: steal = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
        
        # ✅ FIX: Set last_stealer for FCP steals (so Steal HCO Setup runs in next turn)
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""
    
    if skeleton and "steps" in skeleton:
        # logging.warning(f"🔍 [FCP] Converting skeleton to animations (result_type={result_type})...")
        animations = animator.skeleton_to_animations(
            skeleton, 
            off_lineup, 
            def_lineup, 
            add_defenders=True,
            is_fcp=True
        )
        # logging.warning(f"🔍 [FCP] Generated {len(animations)} animations")
        
        # ✅ DEBUG: Log step 0 positions from generated animations
        # for anim in animations[:5]:  # Log first 5 animations
        #     player_id = anim.get("playerId", "UNKNOWN")
        #     movement = anim.get("movement", [])
        #     if movement and len(movement) > 0:
        #         step_0_coords = movement[0].get("coords", "N/A")
        #         logging.warning(f"🔍 [FCP] Animation {player_id[:8]}: step 0 coords={step_0_coords}")
        #     else:
        #         logging.warning(f"⚠️ [FCP] Animation {player_id[:8]}: NO MOVEMENT ARRAY or EMPTY!")
        
        # ✅ FIX: Extract stealer position from generated animations (SS&S approach)
        # This uses the actual calculated defensive position from the animation system
        # For stopper results (steal, foul, turnover), the stopper step is always the final step,
        # so we can simply use animation["end"] to get the final coordinates
        if result_type == "STEAL" and animations and defender:
            stealer_id = getattr(defender, "player_id", None)
            
            if stealer_id:
                # Find the defensive animation for the stealer
                stealer_animation = None
                for anim in animations:
                    if anim.get("playerId") == stealer_id:
                        stealer_animation = anim
                        break
                
                if stealer_animation and "end" in stealer_animation:
                    # Use the final coordinates from the animation (stopper step is always final)
                    stealer_coords = stealer_animation["end"]
                    game_state["last_stealer_coords"] = stealer_coords.copy()
                    defender.coords = stealer_coords.copy()
                    logging.warning(f"🏀 [STEAL POSITION] FCP: Extracted final coords from animation end: x={stealer_coords['x']}, y={stealer_coords['y']}")
                else:
                    logging.warning(f"⚠️ [STEAL POSITION] FCP: Could not find stealer animation or 'end' field (stealer_id={stealer_id}, has_animation={stealer_animation is not None}, has_end={stealer_animation and 'end' in stealer_animation if stealer_animation else False})")
            else:
                logging.warning(f"⚠️ [STEAL POSITION] FCP: Missing stealer_id")
        
        if animations:
            shot_result["animations"] = animations
            logging.warning(f"✅ [FCP] Added {len(animations)} animations to shot_result")
        else:
            logging.warning(f"⚠️ [FCP] No animations generated from skeleton!")
    else:
        animations = []

    if animations:
        apply_coords_from_animations_list(game, animations)
    
    # Determine possession flip
    possession_flips = False
    if result_type == "FOUL" and game_state.get("foul_team") == "OFFENSE":
        possession_flips = True
    elif result_type in ["DEAD BALL", "STEAL"]:
        possession_flips = True
    
    # Handle STEAL: Check for fast break opportunity (STEAL only, not DEAD BALL)
    next_play_type = None
    if result_type == "STEAL":
        p_steal = fast_break_probability_from_slider(
            slow_it_down_defense_setting(
                game_state, def_team, "aggression",
                def_team.strategy_settings.get("aggression", 2),
            )
        )
        if random.random() < p_steal:
            next_play_type = "FAST_BREAK"
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            next_play_type = "HCO"
            game_state["offensive_state"] = "HCO"
    elif result_type == "HCO":
        # ✅ SS&S: Match Fast Break pattern - set offensive_state when transitioning to HCO
        # This prevents duplicate FCP turns (offensive_state must change from "FCP" to "HCO")
        next_play_type = "HCO"
        game_state["offensive_state"] = "HCO"
    elif result_type in ["FOUL", "DEAD BALL"]:
        # ✅ FIX: Set next_play_type to SIDE_INBOUND for O_FOUL, D_FOUL (non-bonus), and DEAD_BALL_TURNOVER
        # This ensures frontend knows to transition to side inbound pass, not loop back to FCP
        # Note: result_type is "FOUL" for both O_FOUL and D_FOUL (converted earlier)
        # For defensive fouls in bonus, offensive_state is already set to FREE_THROW above
        if game_state.get("offensive_state") != "FREE_THROW":
            next_play_type = "SIDE_INBOUND"
            # ✅ FIX: Clear offensive_state to prevent FCP loop
            # SIDE_INBOUND always transitions to HCO, so clear pressure state immediately
            # This prevents the frontend from seeing "FCP" and routing to FCP again
            if game_state.get("offensive_state") in ["FCP", "HCT"]:
                game_state["offensive_state"] = "HCO"
    # For DEAD BALL, O_FOUL, D_FOUL: next_play_type is now set to SIDE_INBOUND (unless FREE_THROW)
    
    # Calculate skeleton-aligned time for FCP phase
    fcp_timing_contract = calc_skeleton_step_timing_contract(
        roles.get("steps", []),
        resolution_step_index=(len(roles.get("steps", [])) - 1 if roles.get("steps") else None),
        include_hco_step1_bringup=False,
        phase_type="FCP",
        off_lineup=game.offense_team.lineup,
    )
    fcp_time_elapsed = fcp_timing_contract["time_elapsed"]
    
    # Track FCP player stats for non-SHOT results
    fcp_roles = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,  # For non-shot results, ball handler is the "shooter"
        "defender": defender,
    }
    turn_result = {"result_type": result_type}
    _record_fcp_stats(fcp_roles, turn_result, game, off_lineup, def_lineup)
    
    # ✅ SS&S: Set offense_team_id (team on offense DURING this turn)
    # Backend calls switch_possession() after turn if needed, so next turn has correct offense_team
    result = {
        "result_type": result_type,
        "text": text,
        "current_turn": "FCP",  # ✅ SS&S: Explicit turn type
        "next_play_type": next_play_type,
        "next_turn": next_play_type,  # ✅ SS&S: Explicit next turn (HCO, FAST_BREAK, or None)
        "ball_handler": roles["ball_handler"],
        "defender": roles["defender"],
        "shooter": roles["shooter"],
        "passer": "",
        "screener": "",
        "offense_team_id": off_team.team_id,  # ✅ SS&S: Team on offense DURING this turn
        "possession_flips": possession_flips,  # ✅ Backend internal flag (tells backend when to call switch_possession)
        "time_elapsed": fcp_time_elapsed,  # Time spent in FCP phase
        "step_clock_seconds": fcp_timing_contract["step_clock_seconds"],
        "resolution_step_index": fcp_timing_contract["resolution_step_index"],
        "executed_step_count": fcp_timing_contract["executed_step_count"],
        "events": [],
        "skeleton": skeleton,
        "animations": animations,
        "roles": roles,
        "foul_team": game_state.get("foul_team"),  # Include foul_team for frontend announcement
        "foul_player_id": getattr(roles.get("foul_player"), "player_id", None) if roles.get("foul_player") else None,  # For foul announcements
        "victim_id": getattr(roles["ball_handler"], "player_id", None),  # For turnover announcements
        "defender_id": getattr(roles["defender"], "player_id", None) if roles["defender"] else None,  # For steal announcements
        "fouled_out": foul_out_info["fouled_out"],
        "foul_count": foul_out_info["foul_count"],
    }
    # ✅ FOUL OUT FIX: Add foul_out_player and context so game_manager creates timeout + frontend shows popup
    if foul_out_info["fouled_out"]:
        result["foul_out_player"] = {
            "player_id": foul_out_info["foul_player_id"],
            "name": foul_out_info["foul_player_name"],
            "photo": foul_out_info["foul_player_photo"],
            "team": foul_out_info["foul_player_team"],
        }
        is_bonus = def_team.team_fouls >= 5 if game_state.get("foul_team") == "DEFENSE" else False
        next_pt = "FREE_THROW" if game_state.get("offensive_state") == "FREE_THROW" else "SIDE_INBOUND"
        game_state["foul_out_context"] = {
            "foul_type": "OFFENSIVE" if game_state.get("foul_team") == "OFFENSE" else "DEFENSIVE",
            "is_shooting_foul": False,
            "is_bonus": is_bonus,
            "next_play_type": next_pt,
            "shooter": ball_handler if game_state.get("offensive_state") == "FREE_THROW" else None,
        }
        logging.info(f"✅ FOUL OUT (FCP): Stored foul context - type={game_state['foul_out_context']['foul_type']}, next={next_pt}")

    if result_type in ("DEAD BALL", "STEAL"):
        attach_position_snapshots(
            result,
            [
                build_phase_post_stopper_snapshot(
                    game,
                    off_lineup,
                    def_lineup,
                    skeleton,
                    roles,
                    "FCP",
                    "turnover",
                    "fcp_turnover_post_stopper",
                )
            ],
        )
    elif result_type == "FOUL":
        attach_position_snapshots(
            result,
            [
                build_phase_post_stopper_snapshot(
                    game,
                    off_lineup,
                    def_lineup,
                    skeleton,
                    roles,
                    "FCP",
                    "non_shooting_foul",
                    "fcp_non_shooting_foul_post_stopper",
                )
            ],
        )

    return result


def get_skeleton_for_turn(result_type, turn_type, game_context=None):
    """
    Universal skeleton getter for all turn types.
    Returns filtered skeleton data based on result_type and turn_type.
    """
    if turn_type == "FCP":
        return get_fcp_skeleton(result_type, game_context)
    elif turn_type == "HCT":
        return get_hct_skeleton(result_type, game_context)
    elif turn_type == "HCO":
        return get_hco_skeleton(result_type, game_context)
    # Future: Add FAST_BREAK, FREE_THROW, etc.
    return None


def get_fcp_skeleton(result_type, game_context=None):
    """
    Get FCP skeleton from MongoDB based on result_type.
    Maps result_type to variant name and randomly selects from available versions.
    
    Args:
        result_type: One of "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", "SHOT", "HCO"
        game_context: Game context object for opposite side logic
    
    Returns:
        dict: Skeleton with steps, or fallback to old hardcoded system
    """
    # ✅ PERFORMANCE: Skip skeleton loading for full simulations
    if game_context and hasattr(game_context, 'game_state'):
        if game_context.game_state.get("_is_full_simulation", False):
            return None
    
    import random
    from BackEnd.db import fcp_skeletons_collection
    
    # Map result_type to variant name
    # All non-shot results use "base" variant (has step 0 with press break positions)
    variant_map = {
        "O_FOUL": "base",
        "D_FOUL": "base",
        "DEAD_BALL_TURNOVER": "base",
        "STEAL": "base",
        "SHOT": "shot",
        "HCO": "base"  # Press break → HCO transition uses base variant
    }
    
    variant_name = variant_map.get(result_type, "base")  # Default to base
    
    # Try to get skeleton from MongoDB
    try:
        # Get all FCP skeletons (for now, we'll use the first one - can be enhanced later)
        skeleton_doc = fcp_skeletons_collection.find_one({})
        
        if skeleton_doc and "variants" in skeleton_doc:
            variants = skeleton_doc.get("variants", {})
            variant_data = variants.get(variant_name)
            
            if variant_data and "versions" in variant_data:
                versions = variant_data["versions"]
                
                # Ensure versions is a list
                if not isinstance(versions, list):
                    logging.warning(f"⚠️ FCP {variant_name} versions is not a list, falling back to hardcoded")
                else:
                    # Filter to only non-empty versions with valid skeleton data
                    non_empty_versions = []
                    for idx, v in enumerate(versions):
                        steps = v.get("steps") if v else None
                        # Check that steps exists, is a list, and has at least one step
                        if steps and isinstance(steps, list) and len(steps) > 0:
                            non_empty_versions.append(v)
                        # Version validation (spam removed)
                
                if non_empty_versions:
                    # Randomly select one non-empty version
                    selected_version = random.choice(non_empty_versions)
                    selected_steps = selected_version.get("steps", [])
                    selected_version_name = selected_version.get("version", "v1")
                    skeleton_data = {
                        "steps": selected_steps,
                        "version": selected_version_name
                    }
                    
                    logging.debug(f"Selected FCP {variant_name} {selected_version_name} (from {len(non_empty_versions)} available)")
                    
                    # Apply opposite side logic if game context is provided
                    if game_context:
                        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
                        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
                    
                    return skeleton_data
                else:
                    logging.warning(f"⚠️ No non-empty versions for FCP {variant_name} (checked {len(versions)} versions), falling back to hardcoded")
            else:
                logging.warning(f"⚠️ Variant {variant_name} not found in FCP skeleton, falling back to hardcoded")
        else:
            logging.warning("⚠️ No FCP skeletons in MongoDB, falling back to hardcoded")
    except Exception as e:
        logging.warning(f"⚠️ Error loading FCP skeleton from MongoDB: {e}, falling back to hardcoded")
    
    # Fallback to old hardcoded system
    from BackEnd.playcall_skeletons.fcp_skeletons import FCP_SKELETONS_DICT, FCP_1
    end_timestamp = FCP_SKELETONS_DICT.get(result_type, 1200)  # Default to HCO timestamp
    
    skeleton_data = {
        "steps": [step for step in FCP_1["steps"] if step["timestamp"] <= end_timestamp]
    }
    
    # Apply opposite side logic if game context is provided
    if game_context:
        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
    
    return skeleton_data


def get_hct_skeleton(result_type, game_context=None):
    """
    Get HCT skeleton from MongoDB based on result_type.
    Maps result_type to variant name and randomly selects from available versions.
    
    Args:
        result_type: One of "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", "SHOT", "HCO"
        game_context: Game context object for opposite side logic
    
    Returns:
        dict: Skeleton with steps, or fallback to old hardcoded system
    """
    # ✅ PERFORMANCE: Skip skeleton loading for full simulations
    if game_context and hasattr(game_context, 'game_state'):
        if game_context.game_state.get("_is_full_simulation", False):
            return None
    
    import random
    from BackEnd.db import hct_skeletons_collection
    
    # Map result_type to variant name
    # All non-shot results use "base" variant (has step 0 with trap break positions)
    variant_map = {
        "O_FOUL": "base",
        "D_FOUL": "base",
        "DEAD_BALL_TURNOVER": "base",
        "STEAL": "base",
        "SHOT": "shot",
        "HCO": "base"  # Trap break → HCO transition uses base variant
    }
    
    variant_name = variant_map.get(result_type, "base")  # Default to base
    
    # Try to get skeleton from MongoDB
    try:
        # Get all HCT skeletons (for now, we'll use the first one - can be enhanced later)
        skeleton_doc = hct_skeletons_collection.find_one({})
        
        if skeleton_doc and "variants" in skeleton_doc:
            variants = skeleton_doc.get("variants", {})
            variant_data = variants.get(variant_name)
            
            if variant_data and "versions" in variant_data:
                versions = variant_data["versions"]
                
                # Ensure versions is a list
                if not isinstance(versions, list):
                    logging.warning(f"⚠️ HCT {variant_name} versions is not a list, falling back to hardcoded")
                else:
                    # Filter to only non-empty versions with valid skeleton data
                    non_empty_versions = []
                    for idx, v in enumerate(versions):
                        steps = v.get("steps") if v else None
                        # Check that steps exists, is a list, and has at least one step
                        if steps and isinstance(steps, list) and len(steps) > 0:
                            non_empty_versions.append(v)
                        # Version validation (spam removed)
                
                if non_empty_versions:
                    # Randomly select one non-empty version
                    selected_version = random.choice(non_empty_versions)
                    selected_steps = selected_version.get("steps", [])
                    selected_version_name = selected_version.get("version", "v1")
                    skeleton_data = {
                        "steps": selected_steps,
                        "version": selected_version_name
                    }
                    
                    logging.debug(f"Selected HCT {variant_name} {selected_version_name} (from {len(non_empty_versions)} available)")
                    
                    # Apply opposite side logic if game context is provided
                    if game_context:
                        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
                        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
                    
                    return skeleton_data
                else:
                    logging.warning(f"⚠️ No non-empty versions for HCT {variant_name} (checked {len(versions)} versions), falling back to hardcoded")
            else:
                logging.warning(f"⚠️ Variant {variant_name} not found in HCT skeleton, falling back to hardcoded")
        else:
            logging.warning("⚠️ No HCT skeletons in MongoDB, falling back to hardcoded")
    except Exception as e:
        logging.warning(f"⚠️ Error loading HCT skeleton from MongoDB: {e}, falling back to hardcoded")
    
    # Fallback to old hardcoded system
    from BackEnd.playcall_skeletons.hct_skeletons import HCT_SCENES, HCT_SKELETONS_DICT
    
    # Get the appropriate end timestamp for this result type
    end_timestamp = HCT_SKELETONS_DICT.get(result_type, 1200)
    
    # Randomly select an HCT scene
    selected_scene = random.choice(HCT_SCENES)
    
    # Filter steps by timestamp
    skeleton_data = {
        "steps": [step for step in selected_scene["steps"] if step["timestamp"] <= end_timestamp]
    }
    
    # Apply opposite side logic if game context is provided (same as FCP - HCT also uses opp field)
    if game_context:
        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
    
    return skeleton_data


def get_skeleton_by_lean(play_doc, lean_score):
    """
    Map lean score to the appropriate skeleton variant.
    
    Args:
        play_doc (dict): Play document from MongoDB with skeletons
        lean_score (float): Lean score from generate_logic() function
            >= 0.5: successful - play works perfectly
            0 to 0.49: mid_play_change - play adjusts mid-execution
            -0.01 to -0.5: contested - defense engaged, tougher execution
            < -0.5: broken - defense disrupts, offense forced to react
    
    Returns:
        tuple: (skeleton dict, variant name string)
    """
    skeletons = play_doc.get("skeletons", {})
    
    # Map lean score to skeleton variant
    if lean_score >= 0.5:
        variant = "successful"
    elif lean_score >= 0:
        variant = "mid_play_change"
    elif lean_score >= -0.5:
        variant = "contested"
    else:
        variant = "broken"
    
    # Get the skeleton, fallback to successful if variant doesn't exist
    skeleton = skeletons.get(variant)
    
    # Handle multi-version variants (v1-v6 for all variants including successful)
    if skeleton:
        # Check if this variant has multiple versions
        if "versions" in skeleton and isinstance(skeleton["versions"], list):
            # Filter to only non-empty versions
            versions_list = skeleton["versions"]
            non_empty_versions = [v for v in versions_list if v.get("steps") and len(v.get("steps", [])) > 0]
            
            if non_empty_versions:
                # Randomly select one non-empty version
                selected_version = random.choice(non_empty_versions)
                # Create skeleton dict with the selected version's steps
                skeleton = {
                    "steps": selected_version.get("steps", []),
                    "version": selected_version.get("version", "v1")
                }
                logging.debug(f"Selected {selected_version.get('version')} for {variant} (from {len(non_empty_versions)} available)")
            else:
                # No non-empty versions available
                if variant == "successful":
                    # Can't fallback to successful if we're already processing successful
                    logging.warning(f"No non-empty versions for {variant}, skeleton will be None")
                    skeleton = None
                else:
                    # Fallback to successful for non-successful variants
                    logging.debug(f"No non-empty versions for {variant}, falling back to successful")
                    skeleton = skeletons.get("successful")
                    variant = "successful"
        # Old format (single steps array) - maintain backwards compatibility
        elif not skeleton.get("steps"):
            # Empty skeleton
            if variant == "successful":
                # Can't fallback to successful if we're already processing successful
                logging.warning(f"Empty skeleton for {variant}, skeleton will be None")
                skeleton = None
            else:
                # Fallback to successful for non-successful variants
                skeleton = skeletons.get("successful")
                variant = "successful"
    
    # If selected variant is empty or None, fallback to successful (only if not already successful)
    if not skeleton or not skeleton.get("steps"):
        if variant != "successful":
            skeleton = skeletons.get("successful")
            variant = "successful"  # Update variant to match fallback
    
    return skeleton, variant


def _canonical_offensive_playcall_name(game_context, playcall: str) -> str:
    """
    Resolve a possibly stale ``current_playcall`` string to the current ``plays.name``
    using the team's ``play_id`` when the name no longer exists in the universal collection.
    """
    if not game_context or not playcall or not isinstance(playcall, str):
        return playcall

    from bson import ObjectId

    from BackEnd.db import games_collection, plays_collection
    from BackEnd.utils.team_play_utils import resolve_team_play

    try:
        if plays_collection.find_one({"name": playcall}, {"_id": 1}):
            return playcall
    except Exception:
        logging.debug("canonical playcall: universal name lookup failed for %r", playcall, exc_info=True)

    offense_team = getattr(game_context, "offense_team", None)
    play_obj = None
    if offense_team and getattr(offense_team, "plays", None):
        play_obj = resolve_team_play(offense_team.plays, playcall)

    if not play_obj:
        game_id = getattr(game_context, "game_id", None)
        if game_id and offense_team is not None:
            team_id = getattr(offense_team, "team_id", None)
            try:
                game_doc = games_collection.find_one({"_id": game_id})
                if game_doc and isinstance(game_doc.get("teams"), dict) and team_id is not None:
                    team_obj = game_doc["teams"].get(team_id) or game_doc["teams"].get(str(team_id))
                    if isinstance(team_obj, dict):
                        play_obj = resolve_team_play(team_obj.get("plays") or {}, playcall)
            except Exception:
                logging.debug("canonical playcall: game doc team plays lookup failed", exc_info=True)

    if play_obj:
        pid = play_obj.get("play_id")
        if pid:
            try:
                doc = plays_collection.find_one({"_id": ObjectId(str(pid))}, {"name": 1})
                if doc and isinstance(doc.get("name"), str) and doc["name"]:
                    return doc["name"]
            except Exception:
                pass
        embedded = play_obj.get("name")
        if isinstance(embedded, str) and embedded:
            try:
                if plays_collection.find_one({"name": embedded}, {"_id": 1}):
                    return embedded
            except Exception:
                pass

    return playcall


def _sync_current_playcall_to_canonical_name(game_context) -> None:
    """Update ``game_state['current_playcall']`` when it still holds a pre-rename display name."""
    if not game_context or not hasattr(game_context, "game_state"):
        return
    raw = game_context.game_state.get("current_playcall")
    if not raw or not isinstance(raw, str):
        return
    canonical = _canonical_offensive_playcall_name(game_context, raw)
    if canonical and canonical != raw:
        game_context.game_state["current_playcall"] = canonical
        logging.debug("Synced current_playcall %r -> %r", raw, canonical)


def get_hco_skeleton(result_type, game_context, lean_score=None):
    """
    Get HCO skeleton based on the current playcall from team-specific play objects.
    
    Args:
        result_type: Legacy parameter (kept for backward compatibility)
        game_context: Game context object
        lean_score (float, optional): Lean score to select skeleton variant
            If provided, selects from: successful, mid_play_change, contested, broken
            If None, defaults to successful
    
    Returns:
        dict: Selected skeleton with steps
    """
    from BackEnd.db import plays_collection, games_collection, tournaments_collection, franchises_collection

    if game_context:
        _sync_current_playcall_to_canonical_name(game_context)
    
    # Get the current playcall from game context
    playcall = game_context.game_state.get("current_playcall", "Inside") if game_context else "Inside"
    
    # Get the offensive team
    offense_team = game_context.offense_team
    offense_team_id = offense_team.team_id
    
    # Try to get skeleton from team-specific play objects first
    skeleton = _get_skeleton_from_team_plays(playcall, offense_team_id, game_context, lean_score=lean_score)
    if skeleton:
        return skeleton
    
    # Fallback to universal plays collection
    play_doc = plays_collection.find_one({"name": playcall})
    
    if play_doc and "skeletons" in play_doc:
        # Check if this is a Motion play
        play_type = play_doc.get("play_type", "set_play")
        
        if play_type == "motion":
            # Motion plays: use base_loop skeleton with random version selection
            skeletons = play_doc.get("skeletons", {})
            if "base_loop" in skeletons:
                base_loop = skeletons["base_loop"]
                
                # Check if base_loop has versions array (new format)
                if "versions" in base_loop and isinstance(base_loop["versions"], list):
                    # Filter to only non-empty versions
                    versions_list = base_loop["versions"]
                    non_empty_versions = [v for v in versions_list if v.get("steps") and len(v.get("steps", [])) > 0]
                    
                    if non_empty_versions:
                        # Randomly select one non-empty version
                        selected_version = random.choice(non_empty_versions)
                        # Create skeleton dict with the selected version's steps
                        skeleton = {
                            "steps": selected_version.get("steps", []),
                            "version": selected_version.get("version", "v0")
                        }
                        logging.debug(f"Selected {selected_version.get('version')} for motion play base_loop (from {len(non_empty_versions)} available)")
                        return skeleton
                # Old format (direct steps array) - maintain backwards compatibility
                elif base_loop.get("steps"):
                    return base_loop
        
        # Set Play: Use lean score to select skeleton variant if provided
        if lean_score is not None:
            skeleton, variant = get_skeleton_by_lean(play_doc, lean_score)
            if skeleton:
                # Add variant name to skeleton metadata for shot modifier
                skeleton["_variant"] = variant
                return _apply_set_play_runtime_position_mapping(
                    skeleton, play_doc.get("target_shooter")
                )
        
        # Default to successful skeleton (Set Play only)
        skeleton = _select_default_set_play_skeleton(play_doc)
        if skeleton:
            return _apply_set_play_runtime_position_mapping(
                skeleton, play_doc.get("target_shooter")
            )
    
    # Final fallback to old skeleton system
    from BackEnd.playcall_skeletons.inside_skeletons import INSIDE_SCENES
    from BackEnd.playcall_skeletons.outside_skeletons import OUTSIDE_SCENES
    from BackEnd.playcall_skeletons.attack_skeletons import ATTACK_SCENES
    from BackEnd.playcall_skeletons.set_play_skeletons import SET_PLAY_SCENES
    from BackEnd.playcall_skeletons.freelance_skeletons import FREELANCE_SCENES
    from BackEnd.playcall_skeletons.base_skeletons import BASE_SCENES
    
    # Map playcall to skeleton scenes (old system)
    playcall_map = {
        "Inside": INSIDE_SCENES,
        "Outside": OUTSIDE_SCENES,
        "Attack": ATTACK_SCENES,
        "Set": SET_PLAY_SCENES,
        "Freelance": FREELANCE_SCENES,
        "Base": BASE_SCENES
    }
    
    scenes = playcall_map.get(playcall, INSIDE_SCENES)
    
    # Randomly select one scene from the available scenes
    if scenes and len(scenes) > 0:
        selected_scene = random.choice(scenes)
        # Debug logging removed - was cluttering logs
        # logging.debug(f"📋 Using fallback skeleton with {len(selected_scene.get('steps', []))} steps")
        return selected_scene


def _get_skeleton_from_team_plays(playcall, team_id, game_context, lean_score=None):
    """
    Get skeleton using reference-based architecture.
    Looks up play_id from team plays, then fetches skeleton from universal plays collection.
    Uses in-memory cache to avoid repeated DB queries.
    
    Args:
        playcall (str): Name of the play to find
        team_id (str): Team ID
        game_context: Game context object
        lean_score (float, optional): Lean score to select skeleton variant
    
    Returns:
        dict: Selected skeleton, or None if not found
    """
    from BackEnd.db import games_collection, tournaments_collection, franchises_collection, plays_collection
    from bson import ObjectId
    from BackEnd.utils.team_play_utils import resolve_team_play
    
    # Initialize skeleton cache on game_context if it doesn't exist
    if not hasattr(game_context, '_skeleton_cache'):
        game_context._skeleton_cache = {}
    
    play_id = None
    team_target_shooter = None
    
    # STEP 1: Get play_id from team plays (in-memory or database)
    offense_team = game_context.offense_team
    if hasattr(offense_team, 'plays') and offense_team.plays:
        play_obj = resolve_team_play(offense_team.plays, playcall)
        if play_obj:
            play_id = play_obj.get("play_id")
            team_target_shooter = play_obj.get("target_shooter")
    
    # If not found in memory, check database
    if not play_id:
        game_id = getattr(game_context, 'game_id', None)
        if game_id:
            game_doc = games_collection.find_one({"_id": game_id})
            if game_doc and "teams" in game_doc:
                team_obj = game_doc["teams"].get(team_id, {})
                plays = team_obj.get("plays", {})
                play_obj = resolve_team_play(plays, playcall)
                if play_obj:
                    play_id = play_obj.get("play_id")
                    team_target_shooter = play_obj.get("target_shooter")
    
    if not play_id:
        # print(f"🔍 NOT FOUND: No play_id for '{playcall}'")
        return None
    
    # STEP 2: Check cache first (avoid repeated DB queries)
    cache_key = f"{play_id}"
    if cache_key in game_context._skeleton_cache:
        play_doc = game_context._skeleton_cache[cache_key]
        # print(f"🔍 CACHE HIT: '{playcall}' (play_id: {play_id})")
    else:
        # STEP 3: Fetch full play document from universal collection
        try:
            play_doc = plays_collection.find_one({"_id": ObjectId(play_id)})
            if not play_doc:
                # print(f"🔍 NOT FOUND: No play document for play_id '{play_id}'")
                return None
            
            # Cache it for future use
            game_context._skeleton_cache[cache_key] = play_doc
            # print(f"🔍 FETCHED from universal: '{playcall}' (play_id: {play_id})")
        except Exception as e:
            print(f"🚨 Error fetching play from universal collection: {e}")
            return None
    
    # STEP 4: Select skeleton variant based on play type
    if "skeletons" not in play_doc:
        return None
    
    # Check if this is a Motion play
    play_type = play_doc.get("play_type", "set_play")
    
    if play_type == "motion":
        # Motion plays: use base_loop skeleton with random version selection
        skeletons = play_doc.get("skeletons", {})
        if "base_loop" in skeletons:
            base_loop = skeletons["base_loop"]
            
            # Check if base_loop has versions array (new format)
            if "versions" in base_loop and isinstance(base_loop["versions"], list):
                # Filter to only non-empty versions
                versions_list = base_loop["versions"]
                non_empty_versions = [v for v in versions_list if v.get("steps") and len(v.get("steps", [])) > 0]
                
                if non_empty_versions:
                    # Randomly select one non-empty version
                    selected_version = random.choice(non_empty_versions)
                    # Create skeleton dict with the selected version's steps
                    skeleton = {
                        "steps": selected_version.get("steps", []),
                        "version": selected_version.get("version", "v0")
                    }
                    logging.debug(f"Selected {selected_version.get('version')} for motion play base_loop (from {len(non_empty_versions)} available)")
                    return skeleton
            # Old format (direct steps array) - maintain backwards compatibility
            elif base_loop.get("steps"):
                return base_loop
        return None
    
    # Set Play: Select skeleton variant based on lean score
    if lean_score is not None:
        skeleton, variant = get_skeleton_by_lean(play_doc, lean_score)
        if skeleton and skeleton.get("steps"):
            skeleton["_variant"] = variant
            target_shooter = team_target_shooter or play_doc.get("target_shooter")
            return _apply_set_play_runtime_position_mapping(skeleton, target_shooter)

    # Default to successful variant (Set Play only)
    skeleton = _select_default_set_play_skeleton(play_doc)
    if skeleton and skeleton.get("steps"):
        target_shooter = team_target_shooter or play_doc.get("target_shooter")
        return _apply_set_play_runtime_position_mapping(skeleton, target_shooter)

    return None


def apply_opposite_side_logic(skeleton_data, is_away_offense):
    """
    Apply opposite side logic to skeleton data based on 'opp' field.
    
    For FCP scenarios:
    - Offensive players with 'opp': True should be positioned on the opposite side 
      of the court (defensive side) - these are ball handlers trying to break the press
    - Offensive players without 'opp' field stay on the same side as normal offense
      (offensive side) - these are outlet options
    
    All players in skeleton are offensive players. Defensive players are positioned 
    separately based on how they guard the offensive players.
    """
    if not skeleton_data or "steps" not in skeleton_data:
        return skeleton_data
    
    # Opp field handling (debug logs removed for cleaner output)
    
    from BackEnd.utils.shared import get_away_player_coords
    from BackEnd.constants import HCO_STRING_SPOTS
    
    steps = skeleton_data.get("steps", [])
    if not steps or len(steps) == 0:
        return skeleton_data
    
    modified_skeleton = {"steps": []}
    total_steps = len(steps)
    
    for step_idx, step in enumerate(steps):
        modified_step = {
            "timestamp": step["timestamp"],
            "pos_actions": {},
            "events": step.get("events", [])
        }
        
        # ✅ FIX: Determine ball handler position (usually PG, or first position with ball)
        # For FCP/HCT, ball handler should be on opposite side
        ball_handler_pos = None
        for pos, action in step.get("pos_actions", {}).items():
            if action.get("has_ball") or pos == "PG":  # PG is usually ball handler
                ball_handler_pos = pos
                break
        if not ball_handler_pos:
            ball_handler_pos = "PG"  # Default to PG if no ball handler found
        
        # ✅ DEBUG: Check if this is final step
        step_is_final = step_idx == total_steps - 1
        
        pos_actions = step.get("pos_actions", {})
        if not pos_actions:
            # Skip steps with no pos_actions
            modified_skeleton["steps"].append(modified_step)
            continue
        
        for position, action_data in pos_actions.items():
            if not isinstance(action_data, dict):
                # Skip invalid action_data
                continue
                
            modified_action = action_data.copy()
            
            # Get the spot coordinates (MongoDB skeletons use "location", old skeletons use "spot")
            location_key = action_data.get("location") or action_data.get("spot", "key")
            spot_coords = HCO_STRING_SPOTS.get(location_key, {"x": 64, "y": 25})
            
            # ✅ FIX: Always default to opp=False unless explicitly set to True
            # If opp key doesn't exist → assume False
            # If opp key exists → use its explicit value (True or False)
            has_opp = action_data.get("opp", False)  # Defaults to False if key doesn't exist
            
            # Check if this offensive player should be on opposite side
            if has_opp:
                # Offensive player with opp=True should be on opposite side (defensive side)
                if is_away_offense:
                    # Away team offense - ball handlers go to home side (defensive side)
                    # No coordinate flip needed - they stay on home side
                    pass
                else:
                    # Home team offense - ball handlers go to away side (defensive side)
                    # Flip coordinates to away side
                    spot_coords = get_away_player_coords(spot_coords)
            else:
                # Offensive player without opp field stays on same side as normal offense
                if is_away_offense:
                    # Away team offense - outlet players go to away side (offensive side)
                    # Flip coordinates to away side
                    spot_coords = get_away_player_coords(spot_coords)
                else:
                    # Home team offense - outlet players stay on home side (offensive side)
                    # No coordinate flip needed
                    pass
            
            # Update the spot coordinates in the action data
            modified_action["coords"] = spot_coords
            modified_step["pos_actions"][position] = modified_action
        
        modified_skeleton["steps"].append(modified_step)
    
    return modified_skeleton


# Dynamic HCT feature flag (Dynamic_HCT_Turns.md). First-cut implementation
# replaces the skeleton-driven offense path with step-by-step movement and
# emergent outcomes (DEAD BALL or HCO). Flip to False to revert to skeleton.
USE_DYNAMIC_HCT = True

# Dynamic FCP feature flag (Z-Completed/Dynamic_FCP_Brief.md). Mirrors USE_DYNAMIC_HCT.
USE_DYNAMIC_FCP = True


def _assemble_hct_fb_shot_result(
    game, dyn, shot, def_scouting, text, off_lineup, def_lineup
):
    """Merge a resolved broken-HCT fast-break shot (§7 / D18) with the HCT loop
    intermediate data into a downstream-ready turn_result.

    ``shot`` is the ``resolve_hct_fast_break_shot`` output (MAKE/MISS shot turn
    fields + ``hct_fb_*`` drive seed). We add the pre-shot loop animation data
    (walk-up targets + ``loop_segments``) so ``build_dynamic_hct_animation_steps``
    can render entry → loop → drive → post-shot in one turn.
    """
    off_team = game.offense_team
    result_type = shot["result_type"]
    ball_handler = shot.get("shooter")
    defender = shot.get("defender")

    text = text + shot.get("text_suffix", "")

    # HCT scouting parity (HCT_A/_S offense, HCT_A_D/_S_D defense) — the same
    # helper the HCO/skeleton path uses; MAKE → offense success, MISS → defense.
    _record_hct_stats(
        {"ball_handler": ball_handler, "shooter": ball_handler, "defender": defender},
        {"result_type": result_type},
        game,
        off_lineup,
        def_lineup,
    )

    loop_segments = dyn.get("loop_segments") or []
    shot["text"] = text
    shot["passer"] = ""
    shot["screener"] = ""
    shot.setdefault("foul_team", shot.get("foul_team"))
    shot.setdefault("foul_player_id", shot.get("foul_player_id"))
    shot.setdefault("fouled_out", shot.get("fouled_out", False))
    shot.setdefault("foul_count", shot.get("foul_count", 0))
    shot["victim_id"] = getattr(defender, "player_id", None) if defender else None
    shot["defender_id"] = getattr(defender, "player_id", None) if defender else None
    shot["events"] = []
    shot["skeleton"] = {}
    shot["roles"] = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,
        "defender": defender,
        "passer": "",
        "screener": "",
    }

    # Emitter intermediate data (same keys as the non-shot path).
    shot["hct_bh_pos"] = dyn["bh_pos"]
    shot["hct_bh_target"] = dyn["bh_target"]
    shot["hct_other_offense_targets"] = dyn["other_offense_targets"]
    shot["hct_def_initial_targets"] = dyn["def_initial_targets"]
    shot["hct_loop_segments"] = loop_segments

    # Engine-portion time totals; the emitter overwrites these once it appends
    # the drive + post-shot sub-steps.
    shot["time_elapsed"] = round(
        sum(s["seconds"] for s in loop_segments) + float(shot.get("hct_fb_t_shooter", 0) or 0),
        2,
    )
    shot["step_clock_seconds"] = [s["seconds"] for s in loop_segments]
    shot["resolution_step_index"] = max(0, len(loop_segments) - 1)
    shot["executed_step_count"] = len(loop_segments)
    shot.setdefault("offense_team_id", off_team.team_id)
    return shot


def _assemble_hct_ab_shot_result(
    game, dyn, shot, def_scouting, text, off_lineup, def_lineup
):
    """Merge a resolved in-Attack-Basket shot (§7 / 2D-2a) with the HCT loop
    intermediate data into a downstream-ready turn_result.

    Mirrors ``_assemble_hct_fb_shot_result``; the only difference is the shot
    step's duration source (``hct_ab_t_shot`` vs. the FB drive's
    ``hct_fb_t_shooter``).
    """
    off_team = game.offense_team
    result_type = shot["result_type"]
    ball_handler = shot.get("shooter")
    defender = shot.get("defender")

    text = text + shot.get("text_suffix", "")

    _record_hct_stats(
        {"ball_handler": ball_handler, "shooter": ball_handler, "defender": defender},
        {"result_type": result_type},
        game,
        off_lineup,
        def_lineup,
    )

    loop_segments = dyn.get("loop_segments") or []
    shot["text"] = text
    shot["passer"] = ""
    shot["screener"] = ""
    shot.setdefault("foul_team", shot.get("foul_team"))
    shot.setdefault("foul_player_id", shot.get("foul_player_id"))
    shot.setdefault("fouled_out", shot.get("fouled_out", False))
    shot.setdefault("foul_count", shot.get("foul_count", 0))
    shot["victim_id"] = getattr(defender, "player_id", None) if defender else None
    shot["defender_id"] = getattr(defender, "player_id", None) if defender else None
    shot["events"] = []
    shot["skeleton"] = {}
    shot["roles"] = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,
        "defender": defender,
        "passer": "",
        "screener": "",
    }

    # Emitter intermediate data (same keys as the non-shot path).
    shot["hct_bh_pos"] = dyn["bh_pos"]
    shot["hct_bh_target"] = dyn["bh_target"]
    shot["hct_other_offense_targets"] = dyn["other_offense_targets"]
    shot["hct_def_initial_targets"] = dyn["def_initial_targets"]
    shot["hct_loop_segments"] = loop_segments

    # Engine-portion time totals; the emitter overwrites these once it appends
    # the shot + post-shot sub-steps.
    shot["time_elapsed"] = round(
        sum(s["seconds"] for s in loop_segments) + float(shot.get("hct_ab_t_shot", 0) or 0),
        2,
    )
    shot["step_clock_seconds"] = [s["seconds"] for s in loop_segments]
    shot["resolution_step_index"] = max(0, len(loop_segments) - 1)
    shot["executed_step_count"] = len(loop_segments)
    shot.setdefault("offense_team_id", off_team.team_id)
    return shot


def _assemble_fcp_fb_shot_result(
    game, dyn, shot, def_scouting, text, off_lineup, def_lineup
):
    """Merge a resolved press-break fast-break shot with FCP loop intermediate data."""
    off_team = game.offense_team
    result_type = shot["result_type"]
    ball_handler = shot.get("shooter")
    defender = shot.get("defender")

    text = text + shot.get("text_suffix", "")

    _record_fcp_stats(
        {"ball_handler": ball_handler, "shooter": ball_handler, "defender": defender},
        {"result_type": result_type},
        game,
        off_lineup,
        def_lineup,
    )

    loop_segments = dyn.get("loop_segments") or []
    shot["text"] = text
    shot["current_turn"] = "FCP"
    shot["passer"] = ""
    shot["screener"] = ""
    shot.setdefault("foul_team", shot.get("foul_team"))
    shot.setdefault("foul_player_id", shot.get("foul_player_id"))
    shot.setdefault("fouled_out", shot.get("fouled_out", False))
    shot.setdefault("foul_count", shot.get("foul_count", 0))
    shot["victim_id"] = getattr(defender, "player_id", None) if defender else None
    shot["defender_id"] = getattr(defender, "player_id", None) if defender else None
    shot["events"] = []
    shot["skeleton"] = {}
    shot["roles"] = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,
        "defender": defender,
        "passer": "",
        "screener": "",
    }
    shot["fcp_press_play"] = game.game_state.get("fcp_press_play")
    shot["fcp_bh_pos"] = dyn["bh_pos"]
    shot["fcp_bh_target"] = dyn["bh_target"]
    shot["fcp_other_offense_targets"] = dyn["other_offense_targets"]
    shot["fcp_def_initial_targets"] = dyn["def_initial_targets"]
    shot["fcp_loop_segments"] = loop_segments
    shot["fcp_skip_walk_up"] = bool(dyn.get("skip_walk_up"))

    shot["time_elapsed"] = round(
        sum(s["seconds"] for s in loop_segments) + float(shot.get("hct_fb_t_shooter", 0) or 0),
        2,
    )
    shot["step_clock_seconds"] = [s["seconds"] for s in loop_segments]
    shot["resolution_step_index"] = max(0, len(loop_segments) - 1)
    shot["executed_step_count"] = len(loop_segments)
    shot.setdefault("offense_team_id", off_team.team_id)
    return shot


def _assemble_fcp_ab_shot_result(
    game, dyn, shot, def_scouting, text, off_lineup, def_lineup
):
    """Merge an in-Attack-Basket press-break shot with FCP loop intermediate data."""
    off_team = game.offense_team
    result_type = shot["result_type"]
    ball_handler = shot.get("shooter")
    defender = shot.get("defender")

    text = text + shot.get("text_suffix", "")

    _record_fcp_stats(
        {"ball_handler": ball_handler, "shooter": ball_handler, "defender": defender},
        {"result_type": result_type},
        game,
        off_lineup,
        def_lineup,
    )

    loop_segments = dyn.get("loop_segments") or []
    shot["text"] = text
    shot["current_turn"] = "FCP"
    shot["passer"] = ""
    shot["screener"] = ""
    shot.setdefault("foul_team", shot.get("foul_team"))
    shot.setdefault("foul_player_id", shot.get("foul_player_id"))
    shot.setdefault("fouled_out", shot.get("fouled_out", False))
    shot.setdefault("foul_count", shot.get("foul_count", 0))
    shot["victim_id"] = getattr(defender, "player_id", None) if defender else None
    shot["defender_id"] = getattr(defender, "player_id", None) if defender else None
    shot["events"] = []
    shot["skeleton"] = {}
    shot["roles"] = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,
        "defender": defender,
        "passer": "",
        "screener": "",
    }
    shot["fcp_press_play"] = game.game_state.get("fcp_press_play")
    shot["fcp_bh_pos"] = dyn["bh_pos"]
    shot["fcp_bh_target"] = dyn["bh_target"]
    shot["fcp_other_offense_targets"] = dyn["other_offense_targets"]
    shot["fcp_def_initial_targets"] = dyn["def_initial_targets"]
    shot["fcp_loop_segments"] = loop_segments
    shot["fcp_skip_walk_up"] = bool(dyn.get("skip_walk_up"))

    shot["time_elapsed"] = round(
        sum(s["seconds"] for s in loop_segments) + float(shot.get("hct_ab_t_shot", 0) or 0),
        2,
    )
    shot["step_clock_seconds"] = [s["seconds"] for s in loop_segments]
    shot["resolution_step_index"] = max(0, len(loop_segments) - 1)
    shot["executed_step_count"] = len(loop_segments)
    shot.setdefault("offense_team_id", off_team.team_id)
    return shot


def _resolve_full_court_press_dynamic_first_cut(game, def_scouting, text):
    """
    Dynamic FCP entry point (PR1). Runs ``compute_dynamic_fcp_turn`` and assembles
    the same return dict shape as the legacy skeleton path for downstream consumers.
    """
    from BackEnd.constants.fcp_press_play_types import play_key_for_fcp_press
    from BackEnd.engine.fcp_press_plays import get_fcp_press_play

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup

    play_key = game_state.get("fcp_press_play") or play_key_for_fcp_press(
        getattr(def_team, "playbook_settings", None)
    )
    game_state["fcp_press_play"] = play_key
    dyn = get_fcp_press_play(play_key).run(game)

    if dyn.get("bail"):
        return {
            "result_type": "HCO",
            "turnover_type": "",
            "text": text,
            "current_turn": "FCP",
            "next_play_type": "HCO",
            "next_turn": "HCO",
            "ball_handler": dyn.get("ball_handler"),
            "defender": dyn.get("defender"),
            "shooter": dyn.get("ball_handler"),
            "passer": "",
            "screener": "",
            "offense_team_id": off_team.team_id,
            "possession_flips": False,
            "time_elapsed": 0.0,
            "step_clock_seconds": [0.0],
            "resolution_step_index": 0,
            "executed_step_count": 0,
            "events": [],
            "skeleton": {},
            "roles": {},
            "fcp_press_play": play_key,
            "fouled_out": False,
            "foul_count": 0,
        }

    if dyn.get("result_type") == "FAST_BREAK_SHOT":
        from BackEnd.engine.dynamic_hct_shot import resolve_hct_fast_break_shot

        shot = resolve_hct_fast_break_shot(game, dyn)
        if not shot.get("_hct_fb_bail"):
            return _assemble_fcp_fb_shot_result(
                game, dyn, shot, def_scouting, text, off_lineup, def_lineup
            )
        dyn["result_type"] = "HCO"
        dyn["fb_seed"] = {}

    if dyn.get("result_type") in ("ATTACK_BASKET_SHOT", "ATTACK_BASKET_DRIVE"):
        from BackEnd.engine.dynamic_hct_shot import (
            resolve_hct_attack_basket_drive,
            resolve_hct_attack_basket_shot,
        )

        resolver = (
            resolve_hct_attack_basket_drive
            if dyn["result_type"] == "ATTACK_BASKET_DRIVE"
            else resolve_hct_attack_basket_shot
        )
        shot = resolver(game, dyn)
        if not shot.get("_hct_ab_bail"):
            return _assemble_fcp_ab_shot_result(
                game, dyn, shot, def_scouting, text, off_lineup, def_lineup
            )
        dyn["result_type"] = "HCO"
        dyn["ab_seed"] = {}

    result_type = dyn["result_type"]
    ball_handler = dyn["ball_handler"]
    defender = dyn["defender"]
    text = text + dyn.get("text_suffix", "")

    turnover_type = dyn.get("turnover_type", "")
    foul_team = dyn.get("foul_team") or None
    foul_player = dyn.get("foul_player")
    stealer = dyn.get("stealer") or defender
    foul_out_info = {"fouled_out": False, "foul_count": 0}
    bat_oob = bool(dyn.get("bat_oob"))

    if result_type == "DEAD BALL" and not bat_oob:
        if ball_handler is not None:
            ball_handler.record_stat("TO")
        def_scouting["defense"]["FCP"]["success"] += 1
    elif result_type == "STEAL":
        if ball_handler is not None:
            ball_handler.record_stat("TO")
        if stealer is not None:
            stealer.record_stat("STL")
            stealer.add_momentum(MO_STEAL_DELTA)
            if ball_handler is not None:
                ball_handler.add_momentum(-MO_STEAL_DELTA)
        def_scouting["defense"]["FCP"]["success"] += 1
        game_state["last_stealer"] = stealer
        game_state["last_rebound"] = ""
        steal_coords = dyn.get("steal_coords") or {}
        if steal_coords:
            game_state["last_stealer_coords"] = dict(steal_coords)
    elif result_type == "FOUL":
        if foul_player is None:
            foul_player = select_foul_player(
                foul_team or "DEFENSE", ball_handler, off_lineup, def_lineup
            )
        game_state["foul_team"] = foul_team
        foul_player.record_stat("F")
        foul_charged_team = off_team if foul_team == "OFFENSE" else def_team
        foul_charged_team.team_fouls += 1
        foul_out_info = check_and_handle_foul_out(
            foul_player, game_state, foul_charged_team, perform_removal=False
        )
        if foul_team == "OFFENSE":
            def_scouting["defense"]["FCP"]["success"] += 1
        else:
            if def_team.team_fouls >= 10:
                game_state["offensive_state"] = "FREE_THROW"
                game_state["free_throws"] = 2
                game_state["free_throws_remaining"] = 2
                game_state["one_and_one"] = False
                game_state["last_ball_handler"] = ball_handler
                game_state["shooter"] = ball_handler
            elif def_team.team_fouls >= 5:
                game_state["offensive_state"] = "FREE_THROW"
                game_state["free_throws"] = 2
                game_state["free_throws_remaining"] = 1
                game_state["one_and_one"] = True
                game_state["last_ball_handler"] = ball_handler
                game_state["shooter"] = ball_handler
            else:
                game_state["offensive_state"] = "HCO"
                game_state["free_throws"] = 0
                game_state["free_throws_remaining"] = 0

    possession_flips = (
        (result_type in ("DEAD BALL", "STEAL") and not bat_oob)
        or (result_type == "FOUL" and foul_team == "OFFENSE")
    )
    if result_type == "HCO":
        next_play_type = "HCO"
        game_state["offensive_state"] = "HCO"
    elif result_type == "DEAD BALL":
        next_play_type = "SIDE_INBOUND"
        if game_state.get("offensive_state") in ("FCP", "HCT"):
            game_state["offensive_state"] = "HCO"
    elif result_type == "STEAL":
        p_steal = fast_break_probability_from_slider(
            slow_it_down_defense_setting(
                game_state, def_team, "aggression",
                def_team.strategy_settings.get("aggression", 2),
            )
        )
        if random.random() < p_steal:
            next_play_type = "FAST_BREAK"
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            next_play_type = "HCO"
            game_state["offensive_state"] = "HCO"
    elif result_type == "FOUL":
        if game_state.get("offensive_state") != "FREE_THROW":
            next_play_type = "SIDE_INBOUND"
            if game_state.get("offensive_state") in ("FCP", "HCT"):
                game_state["offensive_state"] = "HCO"
        else:
            next_play_type = "FREE_THROW"
    else:
        next_play_type = None

    roles = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,
        "defender": defender,
        "passer": "",
        "screener": "",
    }
    if result_type == "FOUL" and foul_player is not None:
        roles["foul_player"] = foul_player

    _record_fcp_stats(
        {
            "ball_handler": ball_handler,
            "shooter": ball_handler,
            "defender": defender,
        },
        {"result_type": result_type},
        game,
        off_lineup,
        def_lineup,
    )

    loop_segments = dyn.get("loop_segments") or []
    return {
        "result_type": result_type,
        "turnover_type": turnover_type,
        "text": text,
        "current_turn": "FCP",
        "next_play_type": next_play_type,
        "next_turn": next_play_type,
        "ball_handler": ball_handler,
        "defender": defender,
        "shooter": ball_handler,
        "passer": "",
        "screener": "",
        "offense_team_id": off_team.team_id,
        "possession_flips": possession_flips,
        "time_elapsed": round(sum(s["seconds"] for s in loop_segments), 2),
        "step_clock_seconds": [s["seconds"] for s in loop_segments],
        "resolution_step_index": max(0, len(loop_segments) - 1),
        "executed_step_count": len(loop_segments),
        "events": [],
        "skeleton": {},
        "roles": roles,
        "foul_team": foul_team,
        "foul_player_id": getattr(foul_player, "player_id", None) if foul_player else None,
        "stealer_id": getattr(stealer, "player_id", None) if (result_type == "STEAL" and stealer) else None,
        "is_interception": bool(dyn.get("is_interception")) if result_type == "STEAL" else False,
        "reach_in_foul": bool(dyn.get("reach_in_foul"))
        if (result_type == "FOUL" and foul_team == "DEFENSE")
        else False,
        "bat_oob": bat_oob,
        "bat_oob_contact": dict(dyn.get("bat_oob_contact") or {}) if bat_oob else None,
        "bat_oob_deflector_id": (
            getattr(def_lineup.get(dyn.get("bat_oob_deflector_pos")), "player_id", None)
            if bat_oob and dyn.get("bat_oob_deflector_pos")
            else None
        ),
        "victim_id": getattr(ball_handler, "player_id", None) if ball_handler else None,
        "defender_id": getattr(defender, "player_id", None) if defender else None,
        "fouled_out": foul_out_info.get("fouled_out", False),
        "foul_count": foul_out_info.get("foul_count", 0),
        "fcp_press_play": play_key,
        "fcp_bh_pos": dyn["bh_pos"],
        "fcp_bh_target": dyn["bh_target"],
        "fcp_other_offense_targets": dyn["other_offense_targets"],
        "fcp_def_initial_targets": dyn["def_initial_targets"],
        "fcp_loop_segments": loop_segments,
        "fcp_skip_walk_up": bool(dyn.get("skip_walk_up")),
    }


def _resolve_half_court_trap_dynamic_first_cut(game, def_scouting, text):
    """
    Dynamic HCT entry point — first cut. Calls into ``dynamic_hct`` to compute
    step 1 → 2 → 3 (attack branch only) animations and outcome, then assembles
    the same return dict shape as the skeleton-driven path so downstream
    consumers (frontend animator, turn manager, stat tracker) stay unchanged.

    Deferred (post-first-cut): pass-to-side branch, x=64 transition / shoot,
    foul / steal outcomes, 10-second-violation gate, post-stopper snapshots.
    """
    from BackEnd.constants.hct_trap_play_types import play_key_for_hct_trap
    from BackEnd.engine.hct_trap_plays import get_hct_trap_play

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup

    # Resolve which trap play runs. Normally stashed at the SS&S choke point
    # (TurnManager.determine_defensive_pressure_type); fall back to a fresh pick
    # from the defending team's playbook for any path that bypassed it. Re-sync
    # the resolved key so the stats sink (_record_hct_stats) attributes A/S to it.
    play_key = game_state.get("hct_trap_play") or play_key_for_hct_trap(
        getattr(def_team, "playbook_settings", None)
    )
    game_state["hct_trap_play"] = play_key
    dyn = get_hct_trap_play(play_key).run(game)

    # §7 / D18 — broken-HCT fast break: the engine reached the topLane spot and
    # hands off to the shot resolver, which produces a real MAKE/MISS shot turn
    # (scoring / rebound / foul / possession). The HCT loop segments remain for
    # the pre-shot animation; the emitter appends the drive + post-shot steps.
    if dyn.get("result_type") == "FAST_BREAK_SHOT":
        from BackEnd.engine.dynamic_hct_shot import resolve_hct_fast_break_shot

        shot = resolve_hct_fast_break_shot(game, dyn)
        if not shot.get("_hct_fb_bail"):
            return _assemble_hct_fb_shot_result(
                game, dyn, shot, def_scouting, text, off_lineup, def_lineup
            )
        # Resolver bailed (missing seed) — settle into a plain HCO break.
        dyn["result_type"] = "HCO"
        dyn["fb_seed"] = {}

    # §7 / 2D-2a — in-Attack-Basket shot: the BH reached the Attack Basket Area
    # and chose a shot. The resolver applies the D5 rim collapse + D6 shot
    # defender and produces a real MAKE/MISS turn; the emitter appends the shot
    # + post-shot steps after the loop segments.
    if dyn.get("result_type") in ("ATTACK_BASKET_SHOT", "ATTACK_BASKET_DRIVE"):
        from BackEnd.engine.dynamic_hct_shot import (
            resolve_hct_attack_basket_shot,
            resolve_hct_attack_basket_drive,
        )

        resolver = (
            resolve_hct_attack_basket_drive
            if dyn["result_type"] == "ATTACK_BASKET_DRIVE"
            else resolve_hct_attack_basket_shot
        )
        shot = resolver(game, dyn)
        if not shot.get("_hct_ab_bail"):
            return _assemble_hct_ab_shot_result(
                game, dyn, shot, def_scouting, text, off_lineup, def_lineup
            )
        dyn["result_type"] = "HCO"
        dyn["ab_seed"] = {}

    result_type = dyn["result_type"]
    ball_handler = dyn["ball_handler"]
    defender = dyn["defender"]
    text = text + dyn.get("text_suffix", "")

    # D9 — §8 violation subtype for a DEAD BALL terminal ("SHOT_CLOCK" /
    # "TEN_SECOND", "OVER_BACK"); empty for a defense-forced dead ball. Drives
    # the FE turnover announcement (gameAnnouncements/announcements typeMap) and
    # carries through turnoverAdapter. Clock/backcourt violations → no steal,
    # SIDE_INBOUND, possession flips.
    turnover_type = dyn.get("turnover_type", "")

    # D8 — emergent foul/steal attribution (literal: the engine names the
    # involved defender / ball handler; see Dynamic_HCT_Turns.md §5).
    foul_team = dyn.get("foul_team") or None
    foul_player = dyn.get("foul_player")
    stealer = dyn.get("stealer") or defender
    foul_out_info = {"fouled_out": False, "foul_count": 0}

    # §14 — a batted-out-of-bounds pass is a DEAD BALL where the OFFENSE RETAINS
    # (side inbound, no flip, no TO) — distinct from a forced-turnover DEAD BALL.
    bat_oob = bool(dyn.get("bat_oob"))

    # Stat tracking parity with the skeleton path.
    if result_type == "DEAD BALL" and not bat_oob:
        if ball_handler is not None:
            ball_handler.record_stat("TO")
        def_scouting["defense"]["HCT"]["success"] += 1
    elif result_type == "STEAL":
        if ball_handler is not None:
            ball_handler.record_stat("TO")
        if stealer is not None:
            stealer.record_stat("STL")
            # Player Momentum: steal → stealer +, victim − (Player_Momentum_System.md).
            stealer.add_momentum(MO_STEAL_DELTA)
            if ball_handler is not None:
                ball_handler.add_momentum(-MO_STEAL_DELTA)
        def_scouting["defense"]["HCT"]["success"] += 1
        # Steal aftermath continuity (mirrors the skeleton path). The steal
        # location (where the ball changed hands) seeds the stealer's start
        # coords for the next possession's Steal HCO / fast-break setup.
        game_state["last_stealer"] = stealer
        game_state["last_rebound"] = ""
        steal_coords = dyn.get("steal_coords") or {}
        if steal_coords:
            game_state["last_stealer_coords"] = dict(steal_coords)
    elif result_type == "FOUL":
        # foul_player is literal from the engine; fall back to skeleton selection
        # only if the engine couldn't name one.
        if foul_player is None:
            foul_player = select_foul_player(
                foul_team or "DEFENSE", ball_handler, off_lineup, def_lineup
            )
        game_state["foul_team"] = foul_team
        foul_player.record_stat("F")
        foul_charged_team = off_team if foul_team == "OFFENSE" else def_team
        foul_charged_team.team_fouls += 1
        foul_out_info = check_and_handle_foul_out(
            foul_player, game_state, foul_charged_team, perform_removal=False
        )
        if foul_team == "OFFENSE":
            # Charge — defensive success, possession flips to a side inbound.
            def_scouting["defense"]["HCT"]["success"] += 1
        else:
            # Reach-in — offense keeps it; bonus routing decides FT vs inbound.
            if def_team.team_fouls >= 10:
                game_state["offensive_state"] = "FREE_THROW"
                game_state["free_throws"] = 2
                game_state["free_throws_remaining"] = 2
                game_state["one_and_one"] = False
                game_state["last_ball_handler"] = ball_handler
                game_state["shooter"] = ball_handler
            elif def_team.team_fouls >= 5:
                game_state["offensive_state"] = "FREE_THROW"
                game_state["free_throws"] = 2
                game_state["free_throws_remaining"] = 1
                game_state["one_and_one"] = True
                game_state["last_ball_handler"] = ball_handler
                game_state["shooter"] = ball_handler
            else:
                game_state["offensive_state"] = "HCO"
                game_state["free_throws"] = 0
                game_state["free_throws_remaining"] = 0

    # Possession flip + next play type per existing HCT conventions. A batted-OOB
    # DEAD BALL is the exception — the offense keeps it (side inbound, no flip).
    possession_flips = (
        (result_type in ("DEAD BALL", "STEAL") and not bat_oob)
        or (result_type == "FOUL" and foul_team == "OFFENSE")
    )
    if result_type == "HCO":
        next_play_type = "HCO"
        game_state["offensive_state"] = "HCO"
    elif result_type == "DEAD BALL":
        next_play_type = "SIDE_INBOUND"
        if game_state.get("offensive_state") in ("FCP", "HCT"):
            game_state["offensive_state"] = "HCO"
    elif result_type == "STEAL":
        # Steal → fast break chance off the takeaway, else settle into HCO.
        p_steal = fast_break_probability_from_slider(
            slow_it_down_defense_setting(
                game_state, def_team, "aggression",
                def_team.strategy_settings.get("aggression", 2),
            )
        )
        if random.random() < p_steal:
            next_play_type = "FAST_BREAK"
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            next_play_type = "HCO"
            game_state["offensive_state"] = "HCO"
    elif result_type == "FOUL":
        # Defensive foul in bonus already set FREE_THROW above; otherwise the
        # whistle resumes from a side inbound.
        if game_state.get("offensive_state") != "FREE_THROW":
            next_play_type = "SIDE_INBOUND"
            if game_state.get("offensive_state") in ("FCP", "HCT"):
                game_state["offensive_state"] = "HCO"
        else:
            next_play_type = "FREE_THROW"
    else:
        next_play_type = None

    roles = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,
        "defender": defender,
        "passer": "",
        "screener": "",
    }
    if result_type == "FOUL" and foul_player is not None:
        roles["foul_player"] = foul_player
    hct_roles = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,
        "defender": defender,
    }
    _record_hct_stats(hct_roles, {"result_type": result_type}, game, off_lineup, def_lineup)

    # Engine returned a defensive bail (missing PG/PG-defender). Return a
    # minimal payload — emitter will skip and frontend falls back to whatever
    # placeholder is available.
    if dyn.get("bail"):
        return {
            "result_type": result_type,
            "turnover_type": turnover_type,
            "text": text,
            "current_turn": "HCT",
            "next_play_type": next_play_type,
            "next_turn": next_play_type,
            "ball_handler": ball_handler,
            "defender": defender,
            "shooter": ball_handler,
            "passer": "",
            "screener": "",
            "offense_team_id": off_team.team_id,
            "possession_flips": possession_flips,
            "time_elapsed": 0.0,
            "step_clock_seconds": [0.0],
            "resolution_step_index": 0,
            "executed_step_count": 0,
            "events": [],
            "skeleton": {},
            "roles": roles,
            "foul_team": None,
            "foul_player_id": None,
            "victim_id": getattr(ball_handler, "player_id", None) if ball_handler else None,
            "defender_id": getattr(defender, "player_id", None) if defender else None,
            "fouled_out": False,
            "foul_count": 0,
        }

    # Intermediate data for the emitter. ``turn_manager`` calls
    # ``build_dynamic_hct_animation_steps`` (which reads these fields +
    # ``prior_turn.final_coords`` + ``prior_turn.final_ball_handler_id``) to
    # assemble three schema steps: entry walk-up, converge, attack. The
    # emitter overwrites ``animation_steps``, ``time_elapsed``, and
    # ``step_clock_seconds`` with the full 3-step totals.
    return {
        "result_type": result_type,
        "turnover_type": turnover_type,
        "text": text,
        "current_turn": "HCT",
        "next_play_type": next_play_type,
        "next_turn": next_play_type,
        "ball_handler": ball_handler,
        "defender": defender,
        "shooter": ball_handler,
        "passer": "",
        "screener": "",
        "offense_team_id": off_team.team_id,
        "possession_flips": possession_flips,
        # Engine-portion totals only; the emitter overwrites time_elapsed /
        # step_clock_seconds / resolution_step_index / executed_step_count with
        # the full walk-up + N-segment totals once steps are assembled.
        "time_elapsed": round(sum(s["seconds"] for s in dyn["loop_segments"]), 2),
        "step_clock_seconds": [s["seconds"] for s in dyn["loop_segments"]],
        "resolution_step_index": max(0, len(dyn["loop_segments"]) - 1),
        "executed_step_count": len(dyn["loop_segments"]),
        "events": [],
        "skeleton": {},
        "roles": roles,
        "foul_team": foul_team,
        "foul_player_id": getattr(foul_player, "player_id", None) if foul_player else None,
        "stealer_id": getattr(stealer, "player_id", None) if (result_type == "STEAL" and stealer) else None,
        # §14 — STEAL that is a pass interception → FE shows "INTERCEPTION!" + SFX.
        "is_interception": bool(dyn.get("is_interception")) if result_type == "STEAL" else False,
        # §5 — D_FOUL credited to the on-ball defender (a true reach-in) → FE
        # announces "Reaching In!"; off-ball help fouls keep the generic language.
        "reach_in_foul": bool(dyn.get("reach_in_foul")) if (result_type == "FOUL" and foul_team == "DEFENSE") else False,
        # §14 — DEAD BALL that is a batted-OOB pass → FE shows "Batted Ball Out Of
        # Bounds!" (not a turnover) and the offense retains.
        "bat_oob": bat_oob,
        # §14.7 — geometry for the FE imperative ball-send (AnimationEngine.
        # _runHctBatOobBallSend): the grid contact point + deflecting defender id.
        "bat_oob_contact": dict(dyn.get("bat_oob_contact") or {}) if bat_oob else None,
        "bat_oob_deflector_id": (
            getattr(def_lineup.get(dyn.get("bat_oob_deflector_pos")), "player_id", None)
            if bat_oob and dyn.get("bat_oob_deflector_pos")
            else None
        ),
        "victim_id": getattr(ball_handler, "player_id", None) if ball_handler else None,
        "defender_id": getattr(defender, "player_id", None) if defender else None,
        "fouled_out": foul_out_info.get("fouled_out", False),
        "foul_count": foul_out_info.get("foul_count", 0),
        # Intermediate data for the emitter.
        "hct_bh_pos": dyn["bh_pos"],
        "hct_bh_target": dyn["bh_target"],
        "hct_other_offense_targets": dyn["other_offense_targets"],
        "hct_def_initial_targets": dyn["def_initial_targets"],
        "hct_loop_segments": dyn["loop_segments"],
    }


def resolve_half_court_trap_logic(game: "GameManager"):
    """
    Resolve half court trap defensive pressure.
    Returns turn data with HCT result and potential progression to HCO.
    """
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    # ✅ Apply energy decay for active players during HCT
    # ✅ HCT DEFENSIVE PLAYERS: Omit zeros from depletion list for defensive players (they always lose some energy)
    apply_energy_decay(off_lineup, def_lineup, omit_zeros_for_defense=True)

    # Track HCT attempt (defensive team)
    def_scouting = def_team.scouting_data
    def_scouting["defense"]["HCT"]["used"] += 1

    if USE_DYNAMIC_HCT:
        return _resolve_half_court_trap_dynamic_first_cut(
            game, def_scouting, text="TRAP!"
        )

    # Initialize variables to prevent UnboundLocalError
    shot_result = {}
    animator = None
    skeleton = {}
    animations = []

    text = "TRAP!"
    offenseScore = 0
    defenseScore = 0

    for pos, player in off_lineup.items():
        if pos == "PG":
            offenseScore += 3 * (player.attributes["BH"] * 0.6 + player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2)
        elif pos in ["SG", "SF"]:
            offenseScore += (player.attributes["BH"] * 0.6 + player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2)
    for pos, player in def_lineup.items():
        if pos == "PG":
            defenseScore += 3 * (player.attributes["OD"] * 0.4 + player.attributes["AG"] * 0.4 + player.attributes["IQ"] * 0.2)
        elif pos in ["SG", "SF"]:
            defenseScore += (player.attributes["OD"] * 0.4 + player.attributes["AG"] * 0.4 + player.attributes["IQ"] * 0.2)
    
    offenseScore *= random.randint(1, 6)
    defenseScore *= random.randint(1, 6)
    
    # Get team attributes for BSM and DST calculations
    off_attrs = off_team.team_attributes
    def_attrs = def_team.team_attributes
    
    off_chemistry = off_attrs.get("team_chemistry", 10)
    def_chemistry = def_attrs.get("team_chemistry", 10)
    off_pt_opp_modifier = off_attrs.get("pt_opp_modifier", 0)
    def_pt_efficiency = def_attrs.get("pt_efficiency", 0)
    def_discipline = def_attrs.get("discipline", 0)
    off_fight = int(off_attrs.get("fight", 0))
    
    # Calculate BSM (Base Success Modifier): 200 + (10 * offense fight), then chemistry adjustments (FCP_HCT_System.md)
    BSM = 200 + (10 * off_fight)
    
    # Offense contribution to BSM (using pt_opp_modifier)
    if off_pt_opp_modifier > 0:
        BSM += random.randint(1, off_chemistry) * off_pt_opp_modifier
    else:
        BSM += random.randint(1, off_chemistry)
    
    # Defense reduction to BSM (using pt_efficiency)
    if def_pt_efficiency > 0:
        BSM -= random.randint(1, def_chemistry) * def_pt_efficiency
    else:
        BSM -= random.randint(1, def_chemistry)
    
    # Calculate DST (Defense Safety Threshold) = 800 for HCT
    DST = 800
    
    # Defense contribution to DST
    if def_discipline > 0:
        DST += random.randint(1, def_chemistry) * def_discipline
    else:
        DST += random.randint(1, def_chemistry)
    
    # Real HCT result calculation using BSM and DST
    if (offenseScore + BSM) > defenseScore:
        # Success
        if offenseScore - defenseScore > DST:
            # Dominant success - weighted random (FCP_HCT_System.md: D_FOUL 30%, HCO 40%, SHOT 30%)
            result_type = random.choices(["D_FOUL", "HCO", "SHOT"], weights=[0.3, 0.4, 0.3])[0]
        else:
            # Regular success - just break through
            result_type = "HCO"
    else:
        # Failure - weighted random
        result_type = random.choices(["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"], weights=[0.2, 0.5, 0.3])[0]
    
    # ✅ REMOVED: Test code that forced all HCT turns to be steals
    
    result_text_dict = {
        "HCO": "they break the trap & establish their half court offense",
        "D_FOUL": "defensive foul!",
        "O_FOUL": "offensive foul!",
        "DEAD_BALL_TURNOVER": f"they force a turnover!",
        "STEAL": "steal!",
        "SHOT": "they break the trap & attempt a shot!"
    }
    
    text += " " + result_text_dict.get(result_type, result_type)

    # Handle SHOT result - execute actual shot resolution (same as FCP)
    if result_type == "SHOT":
        # ✅ Get skeleton first (needed to determine shooter and passer dynamically)
        skeleton = get_hct_skeleton("SHOT", game) or {}
        if skeleton and "steps" in skeleton and skeleton.get("steps"):
            skeleton = copy.deepcopy(skeleton)
            start_index = _get_fcp_hct_post_inbound_start_index(skeleton, game)
            skeleton["steps"] = skeleton["steps"][start_index:]
        
        # ✅ Dynamically determine shooter and passer from skeleton
        shooter = None
        shooter_pos = None
        passer = None
        passer_pos = None
        
        if skeleton and "steps" in skeleton and skeleton["steps"]:
            steps = skeleton["steps"]
            # Find shooter from final step (player with "shoot" action)
            final_step = steps[-1]
            pos_actions = final_step.get("pos_actions", {})
            
            for pos, action_info in pos_actions.items():
                action = action_info.get("action", "").lower()
                if action == "shoot":
                    shooter_pos = pos
                    shooter = off_lineup.get(pos)
                    break
            
            # Fallback: use last ball handler if no shooter found
            if not shooter:
                ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
                shooter = ball_handler
                shooter_pos = getattr(ball_handler, 'position', None) or "PG"
            
            # Find passer using derive_passer_from_steps (same logic as HCO)
            if shooter_pos:
                passer_pos = game.turn_manager.derive_passer_from_steps(steps, shooter_pos)
                if passer_pos:
                    passer = off_lineup.get(passer_pos)
        
        # Fallback: use hardcoded values if skeleton doesn't have shooter/passer
        if not shooter:
            shooter = random.choice([off_lineup.get("PF"), off_lineup.get("C")])
            shooter_pos = getattr(shooter, 'position', None) or "PF"
        if not passer:
            passer = off_lineup.get("PG", list(off_lineup.values())[0])
            passer_pos = getattr(passer, 'position', None) or "PG"
        
        # ✅ Find shooter's coordinates at the time of the shot
        shooter_coords = None
        if skeleton and "steps" in skeleton and skeleton["steps"]:
            final_step = skeleton["steps"][-1]
            pos_actions = final_step.get("pos_actions", {})
            if shooter_pos and shooter_pos in pos_actions:
                shooter_action_info = pos_actions[shooter_pos]
                shooter_coords = shooter_action_info.get("coords")
                if not shooter_coords:
                    # Fallback: use shooter's current coords
                    shooter_coords = getattr(shooter, "coords", {"x": 50, "y": 25})
        else:
            # Fallback: use shooter's current coords
            shooter_coords = getattr(shooter, "coords", {"x": 50, "y": 25})
        
        # ✅ Find closest defensive player to shooter's location
        defender = None
        closest_distance = float('inf')
        for pos, def_player in def_lineup.items():
            if def_player is None:
                continue
            def_coords = getattr(def_player, "coords", {"x": 50, "y": 25})
            distance = ((shooter_coords["x"] - def_coords["x"]) ** 2 + 
                       (shooter_coords["y"] - def_coords["y"]) ** 2) ** 0.5
            if distance < closest_distance:
                closest_distance = distance
                defender = def_player
        
        # Fallback: random defensive lineup slot if no defender found
        if not defender:
            defender = defender_player_from_random_slot_fallback(def_lineup)
        
        shot_roles = {
            "ball_handler": passer,
            "ball_handler_pos": passer_pos,
            "shooter": shooter,
            "shooter_pos": shooter_pos,
            "passer": passer,
            "passer_pos": passer_pos,
            "screener": None,
            "screener_pos": None,
            "defender": defender,
        }
        _ensure_skeleton_shot_role_positions(game, shot_roles)
        
        # Use shot manager to resolve the shot
        apply_coords_from_animations_list(game, animations)
        set_shooter_coords_from_skeleton_last_step(game, skeleton, shot_roles)  # After so block spot uses shot location
        hct_snap = build_skeleton_pre_resolve_shot_snapshot(
            game, off_lineup, def_lineup, skeleton, shot_roles, "HCT", "hct_pre_resolve_shot"
        )
        shot_result = game.shot_manager.resolve_shot(shot_roles)
        attach_position_snapshots(shot_result, [hct_snap])
        
        # ✅ Handle AND-1 situations (MAKE with shooting foul)
        # Check for shooting foul on both MAKE and MISS
        free_throws_remaining = shot_result.get("free_throws_remaining") or game_state.get("free_throws_remaining", 0)
        has_and_one = shot_result.get("has_and_one", False)
        
        if shot_result.get("result_type") == "MAKE":
            if has_and_one or free_throws_remaining > 0:
                # AND-1 situation: Made shot with shooting foul
                game_state["offensive_state"] = "FREE_THROW"
                shot_result["next_play_type"] = "FREE_THROW"
                shot_result["next_turn"] = "FREE_THROW"
                shot_result["free_throws_remaining"] = free_throws_remaining
            else:
                # Regular make → route to BASELINE_INBOUND (pressure may apply again)
                game_state["offensive_state"] = "HCO"  # Will be set to BASELINE_INBOUND by transition system
        elif shot_result.get("result_type") in ["MISS", "BLOCK"]:
            if free_throws_remaining > 0:
                # Shooting foul on miss → preserve FREE_THROW state
                game_state["offensive_state"] = "FREE_THROW"
                shot_result["next_play_type"] = "FREE_THROW"
                shot_result["next_turn"] = "FREE_THROW"
                shot_result["free_throws_remaining"] = free_throws_remaining
            else:
                # Regular miss or block → reset to HCO
                game_state["offensive_state"] = "HCO"
                # Track MISS/BLOCK as defensive success for team
                def_scouting["defense"]["HCT"]["success"] += 1
        
        # Track HCT player stats for SHOT results
        hct_roles = {
            "ball_handler": passer,
            "shooter": shooter,
            "defender": defender,
        }
        _record_hct_stats(hct_roles, shot_result, game, off_lineup, def_lineup)
        
        # Add HCT-specific data
        shot_result["hct_shot"] = True
        shot_result["text"] = "TRAP! " + shot_result.get("text", "")
        shot_result["current_turn"] = "HCT"  # ✅ SS&S: Explicit turn type for transition system
        
        from BackEnd.models.animator import Animator
        animator = Animator(game)
        
        if skeleton and "steps" in skeleton:
            animations = animator.skeleton_to_animations(
                skeleton, 
                off_lineup, 
                def_lineup, 
                add_defenders=True,
                is_fcp=False,
                is_hct=True
            )
            if animations:
                shot_result["animations"] = animations

        shot_result["skeleton"] = skeleton
        shot_result["roles"] = shot_roles

        # Parallel-build: emit unified AnimationStep[] alongside legacy
        # animations[]. See _documentation_master/05_UESS_System/UESS_System.md §3.
        # Defensive: emitter failure must not block the existing payload.
        try:
            from BackEnd.engine.hct_step_emitter import build_hct_animation_steps
            anim_steps = build_hct_animation_steps(shot_result, game)
            if anim_steps is not None:
                shot_result["animation_steps"] = anim_steps
        except Exception as e:
            logging.warning("build_hct_animation_steps (shot path) failed: %s", e)

        return shot_result
    
    # ✅ HCT NON-SHOT: Get HCT "base" variant skeleton and apply stopper system
    # For non-shot results (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO), use HCT "base" variant
    # Apply stopper system if result is not HCO (truncate and add stopper step)
    # logging.warning(f"🔍 [HCT NON-SHOT] Getting HCT base skeleton for result_type={result_type}")
    skeleton = get_hct_skeleton(result_type, game)  # Get HCT "base" variant (has step 0 with trap break positions)
    
    # Deep copy skeleton to avoid mutating cached skeleton
    if skeleton:
        skeleton = copy.deepcopy(skeleton)
    
    # BIP already runs the inbound pass. Skip all leading inbound-left SF steps.
    if skeleton and "steps" in skeleton and skeleton.get("steps"):
        start_index = _get_fcp_hct_post_inbound_start_index(skeleton, game)
        skeleton["steps"] = skeleton["steps"][start_index:]
    
    # Apply stopper system (truncates if needed, or returns full skeleton if result == "HCO")
    skeleton = apply_stopper_system_to_skeleton(skeleton, result_type, game_state)
    # logging.warning(f"🔍 [HCT NON-SHOT] Retrieved skeleton: has_steps={bool(skeleton.get('steps'))}, step_count={len(skeleton.get('steps', []))}")
    
    # ✅ Determine ball handler from skeleton (who actually has the ball)
    ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
    ball_handler_pos = getattr(ball_handler, 'position', None) or "PG"
    
    # ✅ Determine defender based on ball handler position (position matching for now)
    _fb = defender_player_from_random_slot_fallback(def_lineup)
    defender = def_lineup.get(ball_handler_pos) or _fb
    
    # Build roles dict for animation generation
    roles = {
        "ball_handler": ball_handler,
        "defender": defender,
        "shooter": ball_handler,
        "passer": None,
        "screener": None,
        "steps": skeleton.get("steps", []) if skeleton else [],
    }
    
    # Initialize animator if not already initialized
    from BackEnd.models.animator import Animator
    if animator is None:
        animator = Animator(game)
    
    # Handle foul results - use standard foul types for frontend (same as FCP)
    # ✅ FOUL OUT FIX: Initialize so result always has foul_out fields; capture when D_FOUL/O_FOUL
    foul_out_info = {"fouled_out": False, "foul_count": 0}
    if result_type == "D_FOUL":
        game_state["foul_team"] = "DEFENSE"
        # ✅ Use dynamically determined ball handler and defender
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("DEFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        def_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out and capture for result (so game_manager creates timeout + frontend shows popup)
        foul_out_info = check_and_handle_foul_out(foul_player, game_state, def_team, perform_removal=False)
        result_type = "FOUL"
        # ✅ FIX: Check bonus status for defensive fouls in HCT (per game_flows.md)
        # Defensive fouls should route to FREE_THROW if in bonus, otherwise HCO
        if def_team.team_fouls >= 10:
            # Double bonus (10+ fouls): 2 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2
            game_state["free_throws_remaining"] = 2
            game_state["one_and_one"] = False
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        elif def_team.team_fouls >= 5:
            # Bonus (5-9 fouls): 1 & 1 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2  # Maximum possible (if front end is made)
            game_state["free_throws_remaining"] = 1  # Start with 1 (front end)
            game_state["one_and_one"] = True
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        else:
            # Less than 5 fouls: possession change, side inbound
            game_state["offensive_state"] = "HCO"
            game_state["free_throws"] = 0
            game_state["free_throws_remaining"] = 0
    elif result_type == "O_FOUL":
        game_state["foul_team"] = "OFFENSE"
        # ✅ Use dynamically determined ball handler
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("OFFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        off_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out and capture for result (so game_manager creates timeout + frontend shows popup)
        foul_out_info = check_and_handle_foul_out(foul_player, game_state, off_team, perform_removal=False)
        result_type = "FOUL"
        # Track HCT success: offensive foul = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
    elif result_type == "DEAD_BALL_TURNOVER":
        result_type = "DEAD BALL"
        # ✅ Use dynamically determined ball handler
        # Record TO stat for the ball handler
        ball_handler.record_stat("TO")
        # Track HCT success: turnover = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
    elif result_type == "STEAL":
        # ✅ Use dynamically determined ball handler and defender
        # Record TO stat for the ball handler (victim of steal)
        ball_handler.record_stat("TO")
        # Record STL stat for the defender (guarding ball handler)
        if defender:
            defender.record_stat("STL")
            # Player Momentum: steal → stealer +, victim − (Player_Momentum_System.md).
            defender.add_momentum(MO_STEAL_DELTA)
            if ball_handler:
                ball_handler.add_momentum(-MO_STEAL_DELTA)
        # Track HCT success: steal = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
        
        # ✅ FIX: Set last_stealer for HCT steals (so Steal HCO Setup runs in next turn)
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""
    
    if skeleton and "steps" in skeleton:
        # logging.warning(f"🔍 [HCT] Converting skeleton to animations (result_type={result_type})...")
        animations = animator.skeleton_to_animations(
            skeleton, 
            off_lineup, 
            def_lineup, 
            add_defenders=True,
            is_fcp=False,
            is_hct=True
        )
        # logging.warning(f"🔍 [HCT] Generated {len(animations)} animations")
        
        # ✅ FIX: Extract stealer position from generated animations (SS&S approach)
        # This uses the actual calculated defensive position from the animation system
        # For stopper results (steal, foul, turnover), the stopper step is always the final step,
        # so we can simply use animation["end"] to get the final coordinates
        if result_type == "STEAL" and animations and defender:
            stealer_id = getattr(defender, "player_id", None)
            
            if stealer_id:
                # Find the defensive animation for the stealer
                stealer_animation = None
                for anim in animations:
                    if anim.get("playerId") == stealer_id:
                        stealer_animation = anim
                        break
                
                if stealer_animation and "end" in stealer_animation:
                    # Use the final coordinates from the animation (stopper step is always final)
                    stealer_coords = stealer_animation["end"]
                    game_state["last_stealer_coords"] = stealer_coords.copy()
                    defender.coords = stealer_coords.copy()
                    logging.warning(f"🏀 [STEAL POSITION] HCT: Extracted final coords from animation end: x={stealer_coords['x']}, y={stealer_coords['y']}")
                else:
                    logging.warning(f"⚠️ [STEAL POSITION] HCT: Could not find stealer animation or 'end' field (stealer_id={stealer_id}, has_animation={stealer_animation is not None}, has_end={stealer_animation and 'end' in stealer_animation if stealer_animation else False})")
            else:
                logging.warning(f"⚠️ [STEAL POSITION] HCT: Missing stealer_id")
        
        if animations:
            shot_result["animations"] = animations
            # logging.warning(f"✅ [HCT] Added {len(animations)} animations to shot_result")
        else:
            logging.warning(f"⚠️ [HCT] No animations generated from skeleton!")
    else:
        logging.warning(f"⚠️ [HCT] Skeleton has no steps! skeleton={bool(skeleton)}, has_steps={skeleton.get('steps') if skeleton else False}")
        animations = []

    if animations:
        apply_coords_from_animations_list(game, animations)
    
    # Determine possession flip (same logic as FCP)
    possession_flips = False
    if result_type == "FOUL" and game_state.get("foul_team") == "OFFENSE":
        possession_flips = True
    elif result_type in ["DEAD BALL", "STEAL"]:
        possession_flips = True
    
    # Handle STEAL: Check for fast break opportunity (STEAL only, not DEAD BALL)
    next_play_type = None
    if result_type == "STEAL":
        p_steal = fast_break_probability_from_slider(
            slow_it_down_defense_setting(
                game_state, def_team, "aggression",
                def_team.strategy_settings.get("aggression", 2),
            )
        )
        if random.random() < p_steal:
            next_play_type = "FAST_BREAK"
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            next_play_type = "HCO"
            game_state["offensive_state"] = "HCO"
    elif result_type == "HCO":
        # ✅ SS&S: Match Fast Break pattern - set offensive_state when transitioning to HCO
        # This prevents duplicate HCT turns (offensive_state must change from "HCT" to "HCO")
        next_play_type = "HCO"
        game_state["offensive_state"] = "HCO"
    elif result_type in ["FOUL", "DEAD BALL"]:
        # ✅ FIX: Set next_play_type to SIDE_INBOUND for O_FOUL, D_FOUL (non-bonus), and DEAD_BALL_TURNOVER
        # This ensures frontend knows to transition to side inbound pass, not loop back to HCT
        # Note: result_type is "FOUL" for both O_FOUL and D_FOUL (converted earlier)
        # For defensive fouls in bonus, offensive_state is already set to FREE_THROW above
        if game_state.get("offensive_state") != "FREE_THROW":
            next_play_type = "SIDE_INBOUND"
            # ✅ FIX: Clear offensive_state to prevent HCT loop
            # SIDE_INBOUND always transitions to HCO, so clear pressure state immediately
            # This prevents the frontend from seeing "HCT" and routing to HCT again
            if game_state.get("offensive_state") in ["FCP", "HCT"]:
                game_state["offensive_state"] = "HCO"
    # For DEAD BALL, O_FOUL, D_FOUL: next_play_type is now set to SIDE_INBOUND (unless FREE_THROW)
    
    # Calculate skeleton-aligned time for HCT phase
    hct_timing_contract = calc_skeleton_step_timing_contract(
        roles.get("steps", []),
        resolution_step_index=(len(roles.get("steps", [])) - 1 if roles.get("steps") else None),
        include_hco_step1_bringup=False,
        phase_type="HCT",
        off_lineup=game.offense_team.lineup,
    )
    hct_time_elapsed = hct_timing_contract["time_elapsed"]
    
    # Track HCT player stats for non-SHOT results
    hct_roles = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,  # For non-shot results, ball handler is the "shooter"
        "defender": defender,
    }
    turn_result = {"result_type": result_type}
    _record_hct_stats(hct_roles, turn_result, game, off_lineup, def_lineup)
    
    # ✅ SS&S: Set offense_team_id (team on offense DURING this turn)
    # Backend calls switch_possession() after turn if needed, so next turn has correct offense_team
    result = {
        "result_type": result_type,
        "text": text,
        "current_turn": "HCT",  # ✅ SS&S: Explicit turn type
        "next_play_type": next_play_type,
        "next_turn": next_play_type,  # ✅ SS&S: Explicit next turn (HCO, FAST_BREAK, or None)
        "ball_handler": roles["ball_handler"],
        "defender": roles["defender"],
        "shooter": roles["shooter"],
        "passer": "",
        "screener": "",
        "offense_team_id": off_team.team_id,  # ✅ SS&S: Team on offense DURING this turn
        "possession_flips": possession_flips,  # ✅ Backend internal flag (tells backend when to call switch_possession)
        "time_elapsed": hct_time_elapsed,  # Time spent in HCT phase
        "step_clock_seconds": hct_timing_contract["step_clock_seconds"],
        "resolution_step_index": hct_timing_contract["resolution_step_index"],
        "executed_step_count": hct_timing_contract["executed_step_count"],
        "events": [],
        "skeleton": skeleton,
        "animations": animations,
        "roles": roles,
        "foul_team": game_state.get("foul_team"),  # Include foul_team for frontend announcement
        "foul_player_id": getattr(roles.get("foul_player"), "player_id", None) if roles.get("foul_player") else None,  # For foul announcements
        "victim_id": getattr(roles["ball_handler"], "player_id", None),  # For turnover announcements
        "defender_id": getattr(roles["defender"], "player_id", None) if roles["defender"] else None,  # For steal announcements
        "fouled_out": foul_out_info["fouled_out"],
        "foul_count": foul_out_info["foul_count"],
    }
    # ✅ FOUL OUT FIX: Add foul_out_player and context so game_manager creates timeout + frontend shows popup
    if foul_out_info["fouled_out"]:
        result["foul_out_player"] = {
            "player_id": foul_out_info["foul_player_id"],
            "name": foul_out_info["foul_player_name"],
            "photo": foul_out_info["foul_player_photo"],
            "team": foul_out_info["foul_player_team"],
        }
        is_bonus = def_team.team_fouls >= 5 if game_state.get("foul_team") == "DEFENSE" else False
        next_pt = "FREE_THROW" if game_state.get("offensive_state") == "FREE_THROW" else "SIDE_INBOUND"
        game_state["foul_out_context"] = {
            "foul_type": "OFFENSIVE" if game_state.get("foul_team") == "OFFENSE" else "DEFENSIVE",
            "is_shooting_foul": False,
            "is_bonus": is_bonus,
            "next_play_type": next_pt,
            "shooter": ball_handler if game_state.get("offensive_state") == "FREE_THROW" else None,
        }
        logging.info(f"✅ FOUL OUT (HCT): Stored foul context - type={game_state['foul_out_context']['foul_type']}, next={next_pt}")

    if result_type in ("DEAD BALL", "STEAL"):
        attach_position_snapshots(
            result,
            [
                build_phase_post_stopper_snapshot(
                    game,
                    off_lineup,
                    def_lineup,
                    skeleton,
                    roles,
                    "HCT",
                    "turnover",
                    "hct_turnover_post_stopper",
                )
            ],
        )
    elif result_type == "FOUL":
        attach_position_snapshots(
            result,
            [
                build_phase_post_stopper_snapshot(
                    game,
                    off_lineup,
                    def_lineup,
                    skeleton,
                    roles,
                    "HCT",
                    "non_shooting_foul",
                    "hct_non_shooting_foul_post_stopper",
                )
            ],
        )

    # logging.warning(f"✅ [HCT] Returning result with {len(animations)} animations, result_type={result_type}")

    # Parallel-build: emit unified AnimationStep[] alongside legacy
    # animations[]. See _documentation_master/05_UESS_System/UESS_System.md §3.
    # Defensive: emitter failure must not block the existing payload.
    try:
        from BackEnd.engine.hct_step_emitter import build_hct_animation_steps
        anim_steps = build_hct_animation_steps(result, game)
        if anim_steps is not None:
            result["animation_steps"] = anim_steps
    except Exception as e:
        logging.warning("build_hct_animation_steps (non-shot path) failed: %s", e)

    return result
