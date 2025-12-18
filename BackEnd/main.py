import random
import json
import logging
from BackEnd.db import players_collection, teams_collection, games_collection
from BackEnd.utils.db_utils import build_lineup_from_mongo, assign_lineup_from_ids
from BackEnd.models.player import Player
from BackEnd.models.game_manager import GameManager
from BackEnd.models.turn_manager import TurnManager
from BackEnd.constants import (
    ALL_ATTRS,
    BOX_SCORE_KEYS,
    PLAYCALL_ATTRIBUTE_WEIGHTS,
    THREE_POINT_PROBABILITY,
    BLOCK_PROBABILITY,
    MALLEABLE_ATTRS,
    STRATEGY_CALL_DICTS,
    TEMPO_PASS_DICT,
    TURNOVER_CALC_DICT,
    POSITION_LIST,
)
from BackEnd.utils.shared import (
    calculate_screen_score,
    choose_rebounder,
    calculate_rebound_score,
    get_fast_break_chance,
    get_time_elapsed,
    apply_help_defense_if_triggered,
    resolve_offensive_rebound,
    weighted_random_from_dict,
    generate_pass_chain,
    get_name_safe,
    default_rebounder_dict,
    determine_rebounder,
)
from BackEnd.utils.energy_system import recharge_lineups


def _init_game_stats_dict():
    """Initialize game stats dict with all stats set to 0, except Outlet_Score_List which is an empty array."""
    stats = {k: 0 for k in BOX_SCORE_KEYS}
    stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
    return stats


def _initialize_game_stats(gm: GameManager, game_id: str | None = None) -> None:
    """Reset per-game stats for all players and persist initial state.

    This is invoked once at the start of a game before Q1 begins. It clears
    each player's ``stats['game']`` bucket and records a flag in
    ``gm.game_state`` so subsequent quarters do not reset the numbers again.
    When ``game_id`` is provided the initial player payload is written to the
    ``games`` collection.
    """

    logging.info(f"🔍 initialize_game_stats called for Q{gm.quarter}, game_stats_initialized={gm.game_state.get('game_stats_initialized', False)}")

    if gm.game_state.get("game_stats_initialized"):
        logging.info("✅ Game stats already initialized, skipping reset")
        return

    if game_id:
        doc = games_collection.find_one({"_id": game_id})
        if doc and doc.get("game_stats_initialized"):
            # Build maps for stats and attributes
            stats_map = {
                p.get("playerId"): p.get("stats", {}) for p in doc.get("players", [])
            }
            attrs_map = {
                p.get("playerId"): p.get("attributes", {}) for p in doc.get("players", [])
            }
            for team in (gm.home_team, gm.away_team):
                for player in team.get_all_players():
                    # Restore stats
                    stats = stats_map.get(player.player_id)
                    if stats:
                        player.stats["game"].update(stats)
                    # Restore EM, CH, MO from saved game
                    saved_attrs = attrs_map.get(player.player_id)
                    if saved_attrs:
                        player.attributes["EM"] = saved_attrs.get("EM", player.attributes.get("EM", 0))
                        player.attributes["CH"] = saved_attrs.get("CH", player.attributes.get("CH", 0))
                        player.attributes["MO"] = saved_attrs.get("MO", player.attributes.get("MO", 0))
                        # Update anchors
                        player.attributes["anchor_EM"] = player.attributes["EM"]
                        player.attributes["anchor_CH"] = player.attributes["CH"]
                        player.attributes["anchor_MO"] = player.attributes["MO"]
            gm.game_state["game_stats_initialized"] = True
            return

    logging.info("🚨 RESETTING GAME STATS (should only happen in Q1!)")
    affected: list[str] = []
    for team in (gm.home_team, gm.away_team):
        for player in team.get_all_players():
            player.reset_stats()
            # Randomize EM, CH, MO for new game instance
            player.attributes = Player.randomize_game_attributes(player.attributes)
            affected.append(player.player_id)

    gm.game_state["game_stats_initialized"] = True
    logging.info(f"🚨 Reset {len(affected)} player stats, flag set to True")

    if game_id:
        players_payload = []
        for label, team in (("home", gm.home_team), ("away", gm.away_team)):
            for pos, player in team.lineup.items():
                players_payload.append(
                    {
                        "playerId": player.player_id,
                        "team": label,
                        "team_id": team.team_id,
                        "pos": pos,
                        "stats": _init_game_stats_dict(),
                        "attributes": {
                            "EM": player.attributes.get("EM", 0),
                            "CH": player.attributes.get("CH", 0),
                            "MO": player.attributes.get("MO", 0)
                        }
                    }
                )

        games_collection.update_one(
            {"_id": game_id},
            {"$set": {"players": players_payload, "game_stats_initialized": True}},
            upsert=True,
        )

    # print(f"[DEV] Initialized game stats for players: {affected}")


def _ensure_complete_lineup(team, game_state=None) -> None:
    """Ensure a team has players at all required positions.

    If any position from ``POSITION_LIST`` is missing, attempt to build a
    complete lineup from the team's roster.  Raises ``ValueError`` when the
    roster cannot supply the missing positions.
    
    Args:
        team: TeamManager instance
        game_state: Optional game state dict to check for ineligible players
    """

    # Get ineligible players (fouled-out) if game_state is available
    ineligible_player_ids = set()
    if game_state:
        ineligible_player_ids = set(game_state.get("ineligible_players", []))
    
    # First, remove any ineligible players from the lineup
    for pos, player in list(team.lineup.items()):
        if player and hasattr(player, "player_id") and player.player_id in ineligible_player_ids:
            logging.warning(f"⚠️ Removing ineligible player {player.player_id} from {team.name} {pos} position")
            team.lineup[pos] = None
    
    # Now find missing positions (including those we just cleared)
    missing = [pos for pos in POSITION_LIST if not team.lineup.get(pos)]
    if not missing:
        return
    
    # Get currently assigned player IDs (to avoid duplicates)
    current_player_ids = set()
    for pos, player in team.lineup.items():
        if player and hasattr(player, "player_id"):
            current_player_ids.add(player.player_id)

    # Filter available players: exclude ineligible, already-assigned, and players failing energy/foul restrictions
    from BackEnd.utils.db_utils import is_player_eligible_for_lineup
    available_players = [
        p for p in team.get_all_players()
        if p.player_id not in ineligible_player_ids 
        and p.player_id not in current_player_ids
        and is_player_eligible_for_lineup(p, game_state, ineligible_player_ids)
    ]
    
    if len(available_players) < len(missing):
        raise ValueError(
            f"Team '{team.name}' lineup missing positions {missing}: "
            f"Only {len(available_players)} eligible players available "
            f"(need {len(missing)}, excluding {len(ineligible_player_ids)} ineligible)"
        )
    
    # Fill missing positions with available players
    # Use simple assignment based on position needs
    from BackEnd.utils.db_utils import POSITION_TRAITS, get_player_rating
    import random
    
    position_order = ["PG", "SG", "SF", "PF", "C"]
    random.shuffle(position_order)  # Randomize order for variety
    
    remaining_available = available_players.copy()
    
    for pos in missing:
        if not remaining_available:
            raise ValueError(
                f"Team '{team.name}' lineup incomplete; missing positions: {missing}"
            )
        
        # Rate players for this position
        traits = POSITION_TRAITS.get(pos, [])
        rated = [(p, get_player_rating(p, traits)) for p in remaining_available]
        rated.sort(key=lambda tup: tup[1], reverse=True)
        
        # Pick from top 3 candidates (or all if fewer)
        top_candidates = rated[:3] if len(rated) >= 3 else rated
        chosen_player = random.choice(top_candidates)[0]
        
        team.lineup[pos] = chosen_player
        remaining_available.remove(chosen_player)
    
    # Final validation
    remaining = [pos for pos in POSITION_LIST if not team.lineup.get(pos)]
    if remaining:
        raise ValueError(
            f"Team '{team.name}' lineup incomplete; missing positions: {remaining}"
        )


def simulate_quarter(
    gm: GameManager,
    home_lineup_ids=None,
    away_lineup_ids=None,
    game_id: str | None = None,
    start_with_inbound: bool = False,
    starting_possession: str | None = None,
    turn_by_turn_mode: bool = False,
    resume_from_timeout: bool = False,
):
    """Simulate a single quarter on an existing ``GameManager``.

    Lineups may be optionally supplied as dictionaries mapping positions to
    player ids. When omitted the current lineup on the ``GameManager`` is used
    (or auto-generated if still empty). This function mutates ``gm`` in place
    and advances ``gm.quarter`` when finished.
    
    Args:
        turn_by_turn_mode: If True, only initializes the quarter (opening tip/inbound)
                          but does NOT run the full simulation loop. The frontend
                          will call /api/simulate-turn repeatedly instead.
    """

    if game_id is not None:
        gm.game_id = game_id

    # Apply lineups if provided or build them if not already set
    logging.info(f"🏀 simulate_quarter: home_lineup_ids={home_lineup_ids}, away_lineup_ids={away_lineup_ids}, current_home_lineup_keys={list(gm.home_team.lineup.keys()) if gm.home_team.lineup else 'EMPTY'}, current_away_lineup_keys={list(gm.away_team.lineup.keys()) if gm.away_team.lineup else 'EMPTY'}")
    
    if home_lineup_ids:
        gm.home_team.lineup = assign_lineup_from_ids(gm.home_team, home_lineup_ids)
        logging.info(f"✅ simulate_quarter: Set home lineup from home_lineup_ids: {list(gm.home_team.lineup.keys())}")
    elif not gm.home_team.lineup:
        # Reuse existing player objects so per-game stats persist mid-game.
        gm.home_team.lineup = build_lineup_from_mongo(gm.home_team, gm.game_state)
        logging.info(f"✅ simulate_quarter: Built home lineup from MongoDB: {list(gm.home_team.lineup.keys())}")

    if away_lineup_ids:
        gm.away_team.lineup = assign_lineup_from_ids(gm.away_team, away_lineup_ids)
        logging.info(f"✅ simulate_quarter: Set away lineup from away_lineup_ids: {list(gm.away_team.lineup.keys())}")
    elif not gm.away_team.lineup:
        gm.away_team.lineup = build_lineup_from_mongo(gm.away_team, gm.game_state)
        logging.info(f"✅ simulate_quarter: Built away lineup from MongoDB: {list(gm.away_team.lineup.keys())}")
    
    # ✅ QUARTER BREAK: Rebuild computer team's lineup at start of each new quarter
    # This allows computer team to adjust based on energy/foul restrictions
    computer_team = gm.away_team if not gm.away_team.is_user_team else gm.home_team
    if not computer_team.is_user_team and not (away_lineup_ids if computer_team == gm.away_team else home_lineup_ids):
        # Only rebuild if no explicit lineup was provided and this is the computer team
        try:
            computer_team.lineup = build_lineup_from_mongo(computer_team, gm.game_state)
            logging.info(f"✅ QUARTER BREAK: Rebuilt computer team ({computer_team.name}) lineup for Q{gm.quarter} with energy/foul filtering")
        except Exception as e:
            logging.error(f"⚠️ QUARTER BREAK: Failed to rebuild computer team lineup: {e}")
            # Don't fail quarter start if lineup rebuild fails - use existing lineup
    
    # Final check - log final lineup state
    logging.info(f"🏀 simulate_quarter: FINAL home_lineup_keys={list(gm.home_team.lineup.keys()) if gm.home_team.lineup else 'EMPTY'}, away_lineup_keys={list(gm.away_team.lineup.keys()) if gm.away_team.lineup else 'EMPTY'}")
    
    # Validate that both lineups contain all required positions
    # Pass game_state to filter out ineligible (fouled-out) players
    _ensure_complete_lineup(gm.home_team, gm.game_state)
    _ensure_complete_lineup(gm.away_team, gm.game_state)

    # Zero per-game stats exactly once per game before the opening tip.
    # Only initialize stats if game_stats_initialized flag is not set (prevents resetting stats mid-game)
    if not gm.game_state.get("game_stats_initialized", False):
        _initialize_game_stats(gm, game_id)
        gm.game_state["game_stats_initialized"] = True
    gm.game_state["start_box_score"] = gm.get_box_score()

    # Ensure the turn manager is aware of any lineup changes
    gm.turn_manager = TurnManager(gm)
    
    # In turn-by-turn mode, clear turns from previous quarters to prevent stale data
    # from being included in player lookups (old lineups appearing with pos: null)
    if turn_by_turn_mode and gm.quarter > 1:
        logging.info(f"🧹 Clearing {len(gm.turns)} stale turns from Q{gm.quarter-1} (turn-by-turn mode)")
        gm.turns = []

    q = gm.quarter
    gm.game_state["quarter"] = q

    # ✅ TIMEOUT: If resuming from timeout, skip all quarter initialization
    # Reuse the same pattern as quarter breaks - preserve all game state
    # Create the appropriate initial turn based on timeout_next_play_type
    if resume_from_timeout:
        # ✅ TIMEOUT: Clear old turns from before timeout (same as quarter breaks clear turns)
        # This prevents old turns (like opening tip) from being returned to frontend
        if len(gm.turns) > 0:
            logging.info(f"🧹 TIMEOUT RESUME: Clearing {len(gm.turns)} stale turns from before timeout")
            gm.turns = []
        
        timeout_next_play_type = gm.game_state.get("timeout_next_play_type")
        
        # ✅ QUARTER BREAK: If timeout_next_play_type is missing/None, this is NOT a timeout resume
        # This handles cases where resume_from_timeout flag was incorrectly preserved across quarter boundaries
        # or stale timeout state exists in DB without valid next_play_type
        if not timeout_next_play_type:
            logging.warning(f"⚠️ QUARTER BREAK: resume_from_timeout=True but timeout_next_play_type is None - treating as normal quarter start (quarter {q})")
            # Fall through to normal quarter initialization below
            resume_from_timeout = False  # Clear flag to prevent timeout resume logic
        else:
            logging.info(f"✅ TIMEOUT RESUME: Skipping ALL quarter start logic (opening tip/inbounds) - timeout_next_play_type={timeout_next_play_type}")
        
        # Create the appropriate initial turn based on timeout_next_play_type
        if resume_from_timeout and timeout_next_play_type == "SIDE_INBOUND":
            # ✅ TIMEOUT RESUME: Use game.offense_team as source of truth (SS&S)
            # Possession was already set correctly by foul resolution before timeout was created
            current_offense_team_id = gm.offense_team.team_id
            stored_offense_team_id = gm.game_state.get("timeout_offense_team_id")
            
            if stored_offense_team_id and stored_offense_team_id != current_offense_team_id:
                logging.warning(f"⚠️ TIMEOUT RESUME: Mismatch - stored={stored_offense_team_id}, current={current_offense_team_id}. Using current.")
            
            logging.info(f"✅ TIMEOUT RESUME: Creating SIP turn with offense team: {gm.offense_team.name} (team_id: {current_offense_team_id})")
            # ✅ TIMEOUT: Reset offensive_state to HCO to ensure SIP transitions to HCO (not FCP/HCT)
            # This prevents defensive pressure from before timeout from carrying over
            gm.game_state["offensive_state"] = "HCO"
            logging.info(f"✅ TIMEOUT RESUME: Reset offensive_state to HCO (was: {gm.game_state.get('offensive_state', 'unknown')})")
            gm.turn_manager.set_strategy_calls()  # Ensure strategy calls are set
            sip_turn = gm.turn_manager.setup_side_inbound()
            # ✅ TIMEOUT RESUME: Ensure clock is in turn payload for frontend
            if "clock" not in sip_turn:
                sip_turn["clock"] = gm.game_state.get("clock", "0:00")
            gm.turns.append(sip_turn)
            gm.text_log.append(sip_turn.get("text", "Side inbound"))
            # Update clock (SIP takes 4 seconds)
            if gm.game_state.get("time_remaining", 0) > 4:
                gm.game_state["time_remaining"] -= 4
                minutes = gm.game_state["time_remaining"] // 60
                seconds = gm.game_state["time_remaining"] % 60
                gm.game_state["clock"] = f"{minutes}:{seconds:02d}"
            logging.info(f"✅ TIMEOUT RESUME: SIP turn created with offense team: {gm.offense_team.name} (team_id: {gm.offense_team.team_id}), total turns: {len(gm.turns)}")
        elif resume_from_timeout and timeout_next_play_type == "FREE_THROW":
            # Free throw turn will be created by simulate_macro_turn (first call from frontend)
            logging.info(f"✅ TIMEOUT RESUME: Will create FREE_THROW turn via /api/simulate-turn")
            pass
        elif resume_from_timeout and timeout_next_play_type == "BASELINE_INBOUND":
            # BIP turn will be created by simulate_macro_turn (first call from frontend)
            logging.info(f"✅ TIMEOUT RESUME: Will create BASELINE_INBOUND turn via /api/simulate-turn")
            pass
        elif resume_from_timeout:
            # Fallback: If timeout_next_play_type is unexpected, default to SIP
            logging.warning(f"⚠️ TIMEOUT RESUME: timeout_next_play_type={timeout_next_play_type} is unexpected, defaulting to SIDE_INBOUND")
            gm.turn_manager.set_strategy_calls()
            sip_turn = gm.turn_manager.setup_side_inbound()
            gm.turns.append(sip_turn)
            gm.text_log.append(sip_turn.get("text", "Side inbound"))
            if gm.game_state.get("time_remaining", 0) > 4:
                gm.game_state["time_remaining"] -= 4
                minutes = gm.game_state["time_remaining"] // 60
                seconds = gm.game_state["time_remaining"] % 60
                gm.game_state["clock"] = f"{minutes}:{seconds:02d}"
        
        # ✅ TIMEOUT: Only clear timeout state and return early if we actually handled a timeout resume
        if resume_from_timeout:
            # ✅ TIMEOUT: Clear timeout state from memory
            gm.game_state.pop("timeout_next_play_type", None)
            gm.game_state.pop("timeout_offense_team_id", None)  # Also clear possession team
            
            # ✅ TIMEOUT: Clear timeout state from database after resume (defensive cleanup)
            # This prevents stale timeout state from affecting future games
            if game_id:
                try:
                    from BackEnd.db import games_collection
                    games_collection.update_one(
                        {"_id": game_id},
                        {"$unset": {"timeout_next_play_type": "", "timeout_offense_team_id": ""}}
                    )
                    logging.info(f"🧹 TIMEOUT RESUME: Cleared timeout state from database for game_id={game_id}")
                except Exception as e:
                    logging.warning(f"⚠️ TIMEOUT RESUME: Failed to clear timeout state from DB: {e}")
                    # Non-critical - game continues normally

            return gm  # Early return - skip all quarter initialization

    period_label = f"Q{q}" if q <= 4 else f"OT{q - 4}"
    gm.game_state["period_label"] = period_label

    for team in (gm.home_team, gm.away_team):
        while len(team.points_by_quarter) < q:
            team.points_by_quarter.append(0)
    gm.game_state["points_by_quarter"] = {
        gm.home_team.name: gm.home_team.points_by_quarter,
        gm.away_team.name: gm.away_team.points_by_quarter,
    }

    # Reset clock and fouls for the upcoming quarter
    gm.game_state["time_remaining"] = 480 if q <= 4 else 240
    gm.game_state["clock"] = "8:00" if q <= 4 else "4:00"
    gm.home_team.team_fouls = 0
    gm.away_team.team_fouls = 0
    gm.game_state["team_fouls"] = {gm.home_team.name: 0, gm.away_team.name: 0}
    # Note: timeouts do NOT reset per quarter - they carry over the whole game

    # Recharge energy between quarters
    # After Q1, Q3, Q4: +10% | After Q2 (halftime): +20%
    if q == 3:
        recharge_amount = 0.2  # After Q2 (halftime)
    else:
        recharge_amount = 0.1  # After Q1, Q3, Q4
    recharge_lineups(gm, recharge_amount)

    # Handle quarter start possession
    if start_with_inbound and starting_possession:
        # Use specified starting possession (for sim buttons)
        if starting_possession == "home":
            gm.offense_team = gm.home_team
            gm.defense_team = gm.away_team
        else:
            gm.offense_team = gm.away_team
            gm.defense_team = gm.home_team
        
        # Check for defensive pressure on the inbound
        pressure_type = gm.turn_manager.determine_defensive_pressure_type()
        gm.game_state["offensive_state"] = pressure_type
        print(f"🏀 Q{q} start: {gm.offense_team.name} gets possession (custom) - Defense: {pressure_type}")
    elif q == 1 or (q > 4):  # Q1 or any OT
        # Opening tip for Q1 and all OT periods
        from BackEnd.utils.opening_tip import execute_opening_tip
        _, _, tip_turn = execute_opening_tip(gm)
        gm.turns.append(tip_turn)
        # Update clock for tip time elapsed
        gm.game_state["time_remaining"] -= tip_turn["time_elapsed"]
        minutes = gm.game_state["time_remaining"] // 60
        seconds = gm.game_state["time_remaining"] % 60
        gm.game_state["clock"] = f"{minutes}:{seconds:02d}"
    elif q == 2:
        # Q2: Team that didn't win opening tip gets possession via BASELINE_INBOUND
        opening_tip_winner = gm.game_state.get("opening_tip_winner", "home")
        if opening_tip_winner == "home":
            gm.offense_team = gm.away_team
            gm.defense_team = gm.home_team
        else:
            gm.offense_team = gm.home_team
            gm.defense_team = gm.away_team
        
        # Ensure strategy calls are set before creating inbound turn
        gm.turn_manager.set_strategy_calls()
        
        # Check for defensive pressure on the inbound
        pressure_type = gm.turn_manager.determine_defensive_pressure_type()
        gm.game_state["offensive_state"] = pressure_type
        
        # Determine next defensive setup (FCP/HCT/HCO)
        next_defensive_setup = pressure_type if pressure_type in ["FCP", "HCT"] else None
        
        print(f"🏀 Q{q} start: {gm.offense_team.name} gets possession (lost opening tip) - Defense: {pressure_type}")
        
        # Create proper BASELINE_INBOUND turn using turn_manager
        inbound_payload = gm.turn_manager.setup_baseline_inbound(next_defensive_setup=next_defensive_setup)
        
        # Build complete BASELINE_INBOUND turn
        inbound_turn = {
            **inbound_payload,
            "text": f"Start of Q{q}: {gm.offense_team.name} inbounds the ball.",
            "time_elapsed": 4,
            "possession_flips": False,
            "quarter": q,
        }
        
        gm.turns.append(inbound_turn)
        gm.text_log.append(inbound_turn["text"])
        
        # Update clock
        gm.game_state["time_remaining"] -= inbound_turn["time_elapsed"]
        minutes = gm.game_state["time_remaining"] // 60
        seconds = gm.game_state["time_remaining"] % 60
        gm.game_state["clock"] = f"{minutes}:{seconds:02d}"
    elif q == 3:
        # Q3: Team that did NOT win opening tip gets possession via BASELINE_INBOUND
        opening_tip_winner = gm.game_state.get("opening_tip_winner", "home")
        if opening_tip_winner == "home":
            gm.offense_team = gm.away_team
            gm.defense_team = gm.home_team
        else:
            gm.offense_team = gm.home_team
            gm.defense_team = gm.away_team
        
        # Ensure strategy calls are set before creating inbound turn
        gm.turn_manager.set_strategy_calls()
        
        # Check for defensive pressure on the inbound
        pressure_type = gm.turn_manager.determine_defensive_pressure_type()
        gm.game_state["offensive_state"] = pressure_type
        
        # Determine next defensive setup (FCP/HCT/HCO)
        next_defensive_setup = pressure_type if pressure_type in ["FCP", "HCT"] else None
        
        print(f"🏀 Q{q} start: {gm.offense_team.name} gets possession (lost opening tip) - Defense: {pressure_type}")
        
        # Create proper BASELINE_INBOUND turn using turn_manager
        inbound_payload = gm.turn_manager.setup_baseline_inbound(next_defensive_setup=next_defensive_setup)
        
        # Build complete BASELINE_INBOUND turn
        inbound_turn = {
            **inbound_payload,
            "text": f"Start of Q{q}: {gm.offense_team.name} inbounds the ball.",
            "time_elapsed": 4,
            "possession_flips": False,
            "quarter": q,
        }
        
        gm.turns.append(inbound_turn)
        gm.text_log.append(inbound_turn["text"])
        
        # Update clock
        gm.game_state["time_remaining"] -= inbound_turn["time_elapsed"]
        minutes = gm.game_state["time_remaining"] // 60
        seconds = gm.game_state["time_remaining"] % 60
        gm.game_state["clock"] = f"{minutes}:{seconds:02d}"
    elif q == 4:
        # Q4: Opening tip winner gets possession via BASELINE_INBOUND
        opening_tip_winner = gm.game_state.get("opening_tip_winner", "home")
        if opening_tip_winner == "home":
            gm.offense_team = gm.home_team
            gm.defense_team = gm.away_team
        else:
            gm.offense_team = gm.away_team
            gm.defense_team = gm.home_team
        
        # Ensure strategy calls are set before creating inbound turn
        gm.turn_manager.set_strategy_calls()
        
        # Check for defensive pressure on the inbound
        pressure_type = gm.turn_manager.determine_defensive_pressure_type()
        gm.game_state["offensive_state"] = pressure_type
        
        # Determine next defensive setup (FCP/HCT/HCO)
        next_defensive_setup = pressure_type if pressure_type in ["FCP", "HCT"] else None
        
        print(f"🏀 Q{q} start: {gm.offense_team.name} gets possession (won opening tip) - Defense: {pressure_type}")
        
        # Create proper BASELINE_INBOUND turn using turn_manager
        inbound_payload = gm.turn_manager.setup_baseline_inbound(next_defensive_setup=next_defensive_setup)
        
        # Build complete BASELINE_INBOUND turn
        inbound_turn = {
            **inbound_payload,
            "text": f"Start of Q{q}: {gm.offense_team.name} inbounds the ball.",
            "time_elapsed": 4,
            "possession_flips": False,
            "quarter": q,
        }
        
        gm.turns.append(inbound_turn)
        gm.text_log.append(inbound_turn["text"])
        
        # Update clock
        gm.game_state["time_remaining"] -= inbound_turn["time_elapsed"]
        minutes = gm.game_state["time_remaining"] // 60
        seconds = gm.game_state["time_remaining"] % 60
        gm.game_state["clock"] = f"{minutes}:{seconds:02d}"

    # TURN-BY-TURN MODE: If enabled, skip the full simulation loop
    # Frontend will call /api/simulate-turn repeatedly instead
    if not turn_by_turn_mode:
        # Safety guard: prevent infinite loops
        max_turns = 200  # Reasonable limit for a quarter (480 seconds / ~2-3 seconds per turn)
        turn_count = 0
        
        logging.info(f"🏀 Starting full simulation of Q{gm.quarter}, initial time_remaining={gm.game_state['time_remaining']}")
        
        while gm.game_state["time_remaining"] > 0:
            turn_count += 1
            if turn_count > max_turns:
                logging.error(f"🚨 Infinite loop detected! Exceeded {max_turns} turns. time_remaining={gm.game_state['time_remaining']}, quarter={gm.quarter}")
                raise RuntimeError(f"Simulation exceeded {max_turns} turns. Possible infinite loop. time_remaining={gm.game_state['time_remaining']}")
            
            previous_time = gm.game_state["time_remaining"]
            gm.simulate_macro_turn()
            gm.game_state["team_fouls"] = {
                gm.home_team.name: gm.home_team.team_fouls,
                gm.away_team.name: gm.away_team.team_fouls,
            }
            gm.game_state["team_timeouts"] = {
                gm.home_team.name: getattr(gm.home_team, 'timeouts', 5),
                gm.away_team.name: getattr(gm.away_team, 'timeouts', 5),
            }
            
            # Safety check: ensure time is decreasing
            if gm.game_state["time_remaining"] >= previous_time and turn_count > 10:
                logging.warning(f"⚠️ Time not decreasing! previous={previous_time}, current={gm.game_state['time_remaining']}, turn={turn_count}")
                # Don't break here, might be legitimate (e.g., fouls, timeouts)
        
        logging.info(f"✅ Full simulation complete: Q{gm.quarter} finished after {turn_count} turns, final time_remaining={gm.game_state['time_remaining']}")
        gm.quarter += 1
    else:
        # Turn-by-turn mode: Quarter is initialized, ready for turn-by-turn sim
        pass

    return gm

#minor change for new push

def initialize_team_attributes():
    settings = {}
    for team in ["Lancaster", "Bentley-Truman"]:
        # Initialize dictionary for each team
        team_settings = {
            "shot_threshold": random.randint(150, 250),
            "turnover_modifier": random.randint(-250, -150),
            "foul_modifier": random.randint(40, 90),
            "rebound_modifier": random.choice([0.8, 0.9, 1.0, 1.1, 1.2]),
            "momentum_score": random.randint(0,20),
            "offensive_efficienty": random.randint(1,10),
            "team_chemistry": random.randint(7,25),
            "defensive_efficiency": 0,
            "fb_efficiency": 0,
            "pt_efficiency": 0,
            "fb_opp_modifier": 0,
            "pt_opp_modifier": 0
        }
        settings[team] = team_settings
    return settings

def initialize_strategy_calls():
    calls = ["offense_playcall", "defense_playcall", "tempo_call", "aggression_call"]
    settings = {}
    for team in ["Lancaster", "Bentley-Truman"]:
        settings[team] = {call: "" for call in calls}
    return settings

def initialize_strategy_settings():
    strategies = ["defense","tempo", "aggression", "fast_break"]
    settings = {}

    for team in ["Lancaster", "Bentley-Truman"]:
        team_settings = {s: random.randint(0, 4) for s in strategies}
        team_settings["half_court_trap"] = 0
        team_settings["full_court_press"] = 0
        settings[team] = team_settings

    return settings

def print_initial_settings(game_state):
    print("\n=== GAME INITIALIZATION SETTINGS ===")

    print("\n--- Playcall Weights ---")
    for team, weights in game_state["playcall_weights"].items():
        print(f"{team}:")
        for k, v in weights.items():
            print(f"  {k.ljust(10)}: {v}")
    
    print("\n--- Team Attributes ---")
    for team, attrs in game_state["team_attributes"].items():
        print(f"{team}:")
        for k, v in attrs.items():
            print(f"  {k.ljust(20)}: {v}")

    print("\n--- Strategy Settings ---")
    for team, strat in game_state["strategy_settings"].items():
        print(f"{team}:")
        for k, v in strat.items():
            print(f"  {k.ljust(20)}: {v}")

    print("\n--- Strategy Calls ---")
    for team, calls in game_state["strategy_calls"].items():
        print(f"{team}:")
        for k, v in calls.items():
            print(f"  {k.ljust(20)}: {v}")

# --- Aggregator for simulation results ---
def initialize_aggregates():
    return {
        "team_results": [],
        "player_box_scores": []
    }

def collect_simulation_stats(game_state, aggregates):
    aggregates["team_results"].append({
        "score": dict(game_state["score"]),
        "points_by_quarter": dict(game_state["points_by_quarter"])
    })
    player_stats_snapshot = {
        team: {
            player: dict(stats)
            for player, stats in game_state["box_score"][team].items()
        }
        for team in game_state["box_score"]
    }
    aggregates["player_box_scores"].append(player_stats_snapshot)

#RESOLVE_TURN
def resolve_strategy_calls(game_state):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    tempo_setting = game_state["strategy_settings"][off_team]["tempo"]
    aggression_setting = game_state["strategy_settings"][def_team]["aggression"]
    game_state["strategy_calls"][off_team]["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
    game_state["strategy_calls"][def_team]["aggression_call"] = random.choice(STRATEGY_CALL_DICTS["aggression"][aggression_setting])
    
    return game_state["strategy_calls"] 


def get_shot_weights_for_playcall(team_attrs, playcall_name):
    if playcall_name == "Set":
        playcall_name = "Attack"
    weights = PLAYCALL_ATTRIBUTE_WEIGHTS[playcall_name]
    
    shot_scores = {}
    for player, attr in team_attrs.items():
        score = sum(attr[stat] * wt for stat, wt in weights.items())
        shot_scores[player] = score

    return shot_scores

#POST-TURN
def generate_animation_packet(turn_result):
    """
    Creates the final JSON animation payload to send to the frontend:
    - Player coordinates
    - Action types
    - Time elapsed
    - Narration string
    - Game state deltas
    """
    return {
        "text": turn_result["text"],
        "time_elapsed": turn_result["time_elapsed"],
        "offensive_state": turn_result.get("new_offense_state", "HCO"),
        "foul_type": turn_result.get("foul_type", None),
    }

def recalculate_energy_scaled_attributes(game_state):
    for team in game_state["players"]:
        for pos, player_obj in game_state["players"][team].items():
            attr = game_state["players"][team][pos].attributes
            ng = attr["NG"]
            for key in MALLEABLE_ATTRS:
                anchor_val = attr[f"anchor_{key}"]
                attr[key] = int(anchor_val * ng)


def select_weighted_playcall(user_settings):
    playcall_names = list(user_settings.keys())
    weights = list(user_settings.values())
    return random.choices(playcall_names, weights=weights, k=1)[0]


def calculate_rebound_score(player_attr):
    base_score = (
        player_attr["RB"] * 0.5 +
        player_attr["ST"] * 0.3 +
        player_attr["IQ"] * 0.1 +
        player_attr["CH"] * 0.1
    )
    return base_score * random.randint(1, 6)

#POST-GAME
def calculate_team_stats(game_state):
    team_stats = {}
    stat_keys = ["FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "PTS",
                 "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S"]

    for team, player_dict in game_state["box_score"].items():
        team_totals = {k: 0 for k in stat_keys}
        for player_stats in player_dict.values():
            if isinstance(player_stats, dict):
                for k in stat_keys:
                    team_totals[k] += player_stats.get(k, 0)
        team_stats[team] = team_totals

    return team_stats

def build_box_score_from_player_stats(game_state):
    box_score = {}

    for team in game_state["players"]:
        box_score[team] = {}
        for pos, player in game_state["players"][team].items():
            name = player.get_name()
            box_score[team][name] = dict(player.stats["game"])  # Deep copy
    return box_score


def print_scouting_report(data):
    for team in data:
        print(f"\n=== {team.upper()} SCOUTING REPORT ===")

        print("\nOffensive Playcall Usage & Success:")
        for call, val in data[team]["offense"]["Playcalls"].items():
            print(f"{call.ljust(10)} — Used: {val['used']}, Success: {val['success']}")

        print("\nFast Break:")
        fb_used = data[team]["offense"]["Fast_Break_Entries"]
        fb_success = data[team]["offense"]["Fast_Break_Success"]
        print(f"Entries: {fb_used}, Success: {fb_success}")

        print("\nDefensive Success:")
        for def_type, val in data[team]["defense"].items():
            print(f"{def_type.ljust(14)} — Used: {val['used']}, Success: {val['success']}")

def run_simulation(home_team_name, away_team_name, home_lineup_ids=None, away_lineup_ids=None):
    """Run a full game simulation.

    This now acts as a thin wrapper around :func:`simulate_quarter`, looping
    until the game is complete. Existing callers therefore continue to work
    without modification while enabling quarter-by-quarter control elsewhere.
    """

    gm = GameManager(home_team_name, away_team_name)

    # Ensure default lineups exist before the opening tip so tip-off logic and
    # tests that patch ``build_lineup_from_mongo`` have actual players to work
    # with. ``simulate_quarter`` will reuse these lineups unless explicit ids
    # are provided.
    if not gm.home_team.lineup:
        gm.home_team.lineup = build_lineup_from_mongo(gm.home_team)
    if not gm.away_team.lineup:
        gm.away_team.lineup = build_lineup_from_mongo(gm.away_team)

    # Execute opening tip logic
    gm.setup_opening_tip()

    print("Inside run_simulation")
    print(f"Home team: {home_team_name}, Away team: {away_team_name}")

    gm.quarter = 1
    while True:
        simulate_quarter(gm, home_lineup_ids if gm.quarter == 1 else None,
                         away_lineup_ids if gm.quarter == 1 else None)

        current_q = gm.quarter - 1  # simulate_quarter increments after play

        if current_q >= 4:
            h_pts = gm.game_state["score"][gm.home_team.name]
            a_pts = gm.game_state["score"][gm.away_team.name]
            if h_pts != a_pts:
                gm.quarter = current_q
                gm.game_state["quarter"] = current_q
                break
            gm.home_team.points_by_quarter.append(0)
            gm.away_team.points_by_quarter.append(0)

    # Save teams object to database for skeleton lookup during simulation
    try:
        from BackEnd.api.gameplan_routes import populate_team_plays
        from BackEnd.utils.shared import summarize_game_state
        
        # Get populated plays for team objects
        populated_plays = populate_team_plays()
        
        print(f"🔍 DEBUG: Populated {len(populated_plays)} plays for teams in run_simulation")
        print(f"🔍 DEBUG: Play keys: {list(populated_plays.keys())}")
        
        # Create team objects with plays for skeleton lookup
        teams_obj = {
            gm.home_team.team_id: {
                "playcall_settings": getattr(gm.home_team, 'playcall_settings', {}),
                "strategy_settings": getattr(gm.home_team, 'strategy_settings', {}),
                "plays": populated_plays.copy()
            },
            gm.away_team.team_id: {
                "playcall_settings": getattr(gm.away_team, 'playcall_settings', {}),
                "strategy_settings": getattr(gm.away_team, 'strategy_settings', {}),
                "plays": populated_plays.copy()
            }
        }
        
        print(f"🔍 DEBUG: Created teams object with keys: {list(teams_obj.keys())}")
        print(f"🔍 DEBUG: Home team plays: {len(teams_obj[gm.home_team.team_id]['plays'])}")
        print(f"🔍 DEBUG: Away team plays: {len(teams_obj[gm.away_team.team_id]['plays'])}")
        
        # Generate a game_id for this simulation using standardized format
        from BackEnd.utils.game_id_utils import generate_game_id
        game_id = generate_game_id()
        gm.game_id = game_id
        
        # Create a summary with teams object
        summary = summarize_game_state(gm)
        summary["teams"] = teams_obj
        
        # Save to database
        games_collection.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
        print(f"🔍 DEBUG: Saved teams object to database with game_id: {game_id}")
        
    except Exception as e:
        print(f"🚨 Failed to save teams object in run_simulation: {e}")
        import traceback
        traceback.print_exc()

    # print(f"*********gm:\n{gm}")
    return gm




#MAIN
# def main(return_game_state=False):
#     energy_rng_seed = 1.0  # Default for first turn
    
#     # Get team documents
#     lancaster_team = teams_collection.find_one({"name": "Lancaster"})
#     bt_team = teams_collection.find_one({"name": "Bentley-Truman"})
#     print("🔍 Checking live team names in /simulate:")


#     print("🧠 Inserted teams:")
#     for team in teams_collection.find({}):
#         print("📁", team.get("name"))


#     if not lancaster_team or not bt_team:
#         raise ValueError("One or both teams not found in the database.")

#     # Pull 5 player documents from Mongo based on stored IDs
#     lancaster_roster = [
#         Player(players_collection.find_one({"_id": pid}))
#         for pid in lancaster_team["player_ids"][:5]
#     ]
#     bt_roster = [
#         Player(players_collection.find_one({"_id": pid}))
#         for pid in bt_team["player_ids"][:5]
#     ]

#     print(lancaster_roster)
#     print(bt_roster)


#     game_state = {
#         "offense_team": "Lancaster",
#         "defense_team": "Bentley-Truman",
#         "players": {
#             "Lancaster": {
#                 "PG": lancaster_roster[0],
#                 "SG": lancaster_roster[1],
#                 "SF": lancaster_roster[2],
#                 "PF": lancaster_roster[3],
#                 "C":  lancaster_roster[4]
#             },
#             "Bentley-Truman": {
#                 "PG": bt_roster[0],
#                 "SG": bt_roster[1],
#                 "SF": bt_roster[2],
#                 "PF": bt_roster[3],
#                 "C":  bt_roster[4]
#             }
#         },
#         "score": {"Lancaster": 0, "Bentley-Truman": 0},
#         "time_remaining": 480,
#         "quarter": 1,
#         "offensive_state": "HALF_COURT",
#         "tempo": 2,
#         "playcall": {"offense": "Base", "defense": "Man"},
#         "defense_playcall": "Man",  # Add this line
#         "turn_number": 17,
#         "team_fouls": {
#             "Lancaster": 0,
#             "Bentley-Truman": 0
#         },
#         "free_throws": 0,
#         "free_throws_remaining": 0,
#         "last_ball_handler": None,
#         "bonsu_active": False,
#         "box_score": {
#             "Lancaster": {},
#             "Bentley-Truman": {}
#         }
#     }
    
#     game_state["scouting_data"] = {
#         team: {
#             "offense": {
#                 "Fast_Break_Entries": 0,
#                 "Fast_Break_Success": 0,
#                 "Playcalls": {call: {"used": 0, "success": 0} for call in ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]},
#             },
#             "defense": {
#                 "Man": {"used": 0, "success": 0},
#                 "Zone": {"used": 0, "success": 0},
#                 "vs_Fast_Break": {"used": 0, "success": 0},
#             }
#         }
#         for team in game_state["players"]
#     }
    
#     game_state["playcall_weights"] = initialize_playcall_settings()
#     game_state["team_attributes"] = initialize_team_attributes()
#     game_state["strategy_settings"] = initialize_strategy_settings()
#     game_state["strategy_calls"] = initialize_strategy_calls()

#     game_state["playcall_tracker"] = {
#         team: {call: 0 for call in ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]}
#         for team in game_state["players"]
#     }
#     game_state["defense_playcall_tracker"] = {
#         team: {call: 0 for call in ["Man", "Zone"]}
#         for team in game_state["players"]
#     }

#     game_state["points_by_quarter"] = {
#         team: [0, 0, 0, 0] for team in game_state["players"]
#     }


#     i = 1
#     for q in range(1, 5):  # quarters 1 to 4
#         game_state["quarter"] = q
#         recharge_amount = 0.3 if q == 3 else 0.2
#         # Reset fouls at start of quarter
#         for team in game_state["team_fouls"]:
#             game_state["team_fouls"][team] = 0
#         game_state["time_remaining"] = 480  # 8 minutes per quarter
#         # Recharge NG at quarter break
#         for team in game_state["players"]:
#             for player in game_state["players"][team].values():
#                 player.recharge_energy(recharge_amount)


#         if not return_game_state:
#             print(f"\n=== Start of Q{q} ===")
#         while game_state["time_remaining"] > 0:
#             if not return_game_state:
#                 print(f"--- Turn {i} ---")
#             game_state["last_ball_handler"] = game_state["players"][game_state["offense_team"]]["PG"]
#             # game_state["last_ball_handler"] = "PG"
#             game_state["strategy_calls"] = resolve_strategy_calls(game_state)
#             # for team, calls in game_state["strategy_calls"].items():
#             #     print(f"{team} Tempo = {calls['tempo_call']}, Aggression = {calls['aggression_call']}")
#             turn_result = resolve_turn(game_state)
#             game_state["time_remaining"] = max(0, game_state["time_remaining"] - turn_result["time_elapsed"])
            
#             for player in game_state["players"][game_state["offense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])
#             for player in game_state["players"][game_state["defense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])

#             #Energy System
#             if i % 2 == 0 or i == 1:
#                 energy_rng_seed = random.choices(
#                     [0.9, 0.95, 1.0, 1.05, 1.1],
#                     weights=[1, 2, 5, 2, 1]
#                 )[0]
#             # print(f"Turn {i} | Energy RNG: {energy_rng_seed}")
#             base_decay = 0.025  # Base amount of NG lost per turn
#             fatigue_mod = 1.1 if game_state["defense_playcall"] == "Man" else 0.9
#             def_team = game_state["defense_team"]
#             for team in [game_state["offense_team"], game_state["defense_team"]]:
#                 for pos, player_obj in game_state["players"][team].items():
#                     attr = game_state["players"][team][pos].attributes
#                     endurance = attr["ND"]
#                     decay = max(0.001, base_decay - (endurance / 1000))  # Prevent negative decay
#                     decay = max(0.001, decay * energy_rng_seed)  # Apply seeded RNG
#                      # ✅ Only apply to defenders
#                     if team == def_team:
#                         decay *= fatigue_mod
#                     player_obj.decay_energy(decay) # Floor at 0.1
#             recalculate_energy_scaled_attributes(game_state)

#             minutes = game_state["time_remaining"] // 60
#             seconds = game_state["time_remaining"] % 60
#             clock_display = f"{minutes}:{seconds:02d}"
#             if not return_game_state:
#                 print()
#                 print(turn_result.get("text", "No description"))
#                 print()
#                 print(f"Score: {game_state['score']}")
#                 print(f"Clock: {clock_display} // Q{game_state['quarter']}")
#                 print(f"Team Fouls: {game_state['team_fouls']}")
#                 # if turn_result.get("possession_flips"):
#                 #     print("Possession changes.")
#                 # else:
#                 #     print("Possession retained.")
#                 print()
#             if turn_result.get("possession_flips", False):
#                 game_state["offense_team"], game_state["defense_team"] = (
#                     game_state["defense_team"],
#                     game_state["offense_team"]
#                 )
#             i += 1

#         if not return_game_state:
#             print(f"=== End of Q{q} ===")
    
#     for team in game_state["box_score"]:
#         for player in game_state["box_score"][team]:
#             raw_seconds = game_state["box_score"][team][player]["MIN"]
#             game_state["box_score"][team][player]["MIN"] = int(raw_seconds / 60)

#     # --- Overtime if tied after regulation ---
#     while game_state["score"]["Lancaster"] == game_state["score"]["Bentley-Truman"]:
#         game_state["quarter"] += 1
#         for team in game_state["points_by_quarter"]:
#             game_state["points_by_quarter"][team].append(0)

#         game_state["time_remaining"] = 240  # 4 minutes for OT

#         if not return_game_state:
#             print(f"\n=== Start of Overtime Q{game_state['quarter']} ===")

#         while game_state["time_remaining"] > 0:
#             if not return_game_state:
#                 print(f"--- Turn {i} (OT) ---")
#             turn_result = resolve_turn(game_state)
#             game_state["time_remaining"] = max(0, game_state["time_remaining"] - turn_result["time_elapsed"])

#             for player in game_state["players"][game_state["offense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])
#             for player in game_state["players"][game_state["defense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])

#             # Energy and movement logic remains unchanged
#             if i % 2 == 0 or i == 1:
#                 energy_rng_seed = random.choices([0.9, 0.95, 1.0, 1.05, 1.1], weights=[1, 2, 5, 2, 1])[0]
#             base_decay = 0.025
#             for team in [game_state["offense_team"], game_state["defense_team"]]:
#                 for pos, player_obj in game_state["players"][team].items():
#                     attr = game_state["players"][team][pos].attributes
#                     endurance = attr["ND"]
#                     decay = max(0.001, base_decay - (endurance / 1000))
#                     decay = max(0.001, decay * energy_rng_seed)
#                     attr["NG"] = max(0.1, round(attr["NG"] - decay, 3))
#             recalculate_energy_scaled_attributes(game_state)

#             minutes = game_state["time_remaining"] // 60
#             seconds = game_state["time_remaining"] % 60
#             clock_display = f"{minutes}:{seconds:02d}"
#             if not return_game_state:
#                 print(turn_result.get("text", "No description"))
#                 print(f"Clock: {clock_display}")
#                 print(f"Quarter: Q{game_state['quarter']}")
#                 print(f"Score: {game_state['score']}")
#                 print(f"Team Fouls: {game_state['team_fouls']}")
#                 print("Possession changes." if turn_result.get("possession_flips") else "Possession retained.")
#                 print()

#             if turn_result.get("possession_flips", False):
#                 game_state["offense_team"], game_state["defense_team"] = (
#                     game_state["defense_team"],
#                     game_state["offense_team"]
#                 )
#             i += 1

#         if not return_game_state:
#             print(f"=== End of Overtime Q{game_state['quarter']} ===")

    
#     if not return_game_state:
#         print(f"\n=== Box Score After {i} Turns ===")
#     for team in game_state["box_score"]:
#         team_score = game_state["score"][team]
#         if not return_game_state:
#             print(f"\n{team} {team_score}")
#         for player, stats in game_state["box_score"][team].items():
#             # Recalculate PTS if you're not auto-updating it in record_stat()
#             stats["PTS"] = (2 * stats["FGM"]) + stats["3PTM"] + stats["FTM"]
#             stats["REB"] = stats["OREB"] + stats["DREB"]
#             if not return_game_state:
#                 print(f"{player}: {stats}")

#     if not return_game_state:
#         print(f"\n=== Team Points by Quarter ===")
#         for team, q_points in game_state["points_by_quarter"].items():
#             print(f"{team}: Q1={q_points[0]}  Q2={q_points[1]}  Q3={q_points[2]}  Q4={q_points[3]}  Total={sum(q_points)}")

#     # Reset all player attributes to anchor values after the game
#     for team in game_state["players"]:
#         for pos, player in game_state["players"][team].items():
#             player.reset_energy()

#     if not return_game_state:
#         print(f"\n=== Team Stats Summary ===")
#     team_stats = calculate_team_stats(game_state)
#     stat_keys = ["FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "PTS",
#                     "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S"]

#     # Print header
#     column_width = max(len(k) for k in stat_keys) + 2
#     header = "TEAM".ljust(18) + "".join(k.rjust(column_width) for k in stat_keys)
#     if not return_game_state:
#         print(header)
#         print("-" * len(header))

#         for team, stats in team_stats.items():
#             row = team.ljust(18) + "".join(str(stats.get(k, 0)).rjust(column_width) for k in stat_keys)
#             print(row)

#     # if not return_game_state:
#     #     print_scouting_report(game_state["scouting_data"])



#     if return_game_state:
#         return game_state

# # if __name__ == "__main__":
#     game_state = main(return_game_state=False)

# if __name__ == "__main__":
#     # This starts the FastAPI server when running locally or on Railway
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)


# if __name__ == "__main__":
    # aggregates = initialize_aggregates()

    # for sim in range(100):
    #     game_state = main(return_game_state=True)
    #     collect_simulation_stats(game_state, aggregates)

    # with open("aggregated_stats.json", "w") as f:
    #     json.dump(aggregates, f, indent=2)


