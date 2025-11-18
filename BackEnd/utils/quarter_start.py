"""
Quarter start inbound pass for Q2, Q3, Q4
Uses BASELINE_INBOUND format for frontend compatibility
"""
import random
from BackEnd.utils.shared import getAwayTeamCoords
from BackEnd.utils.shared_defense import assign_bh_defender_coords, assign_non_bh_defender_coords

# adding a comment for git push
def create_quarter_start_inbound(game):
    """
    Create an inbound pass turn for Q2/Q3/Q4 start.
    Returns a turn in BASELINE_INBOUND format so frontend can reuse existing logic.
    
    Uses the opening tip winner to determine possession for consistent quarter starts.
    """
    # Determine possession based on opening tip winner
    opening_tip_winner = game.game_state.get("opening_tip_winner", "home")
    
    # Alternate possession each quarter (Q1: opening tip winner, Q2: other team, Q3: opening tip winner, Q4: other team)
    if game.quarter == 1:
        # Q1 uses opening tip winner (already set)
        offense_team = game.offense_team
        defense_team = game.defense_team
    elif game.quarter == 2:
        # Q2 goes to the team that didn't win opening tip
        if opening_tip_winner == "home":
            offense_team = game.away_team
            defense_team = game.home_team
        else:
            offense_team = game.home_team
            defense_team = game.away_team
    elif game.quarter == 3:
        # Q3 goes back to opening tip winner
        if opening_tip_winner == "home":
            offense_team = game.home_team
            defense_team = game.away_team
        else:
            offense_team = game.away_team
            defense_team = game.home_team
    else:  # Q4
        # Q4 goes to the team that didn't win opening tip
        if opening_tip_winner == "home":
            offense_team = game.away_team
            defense_team = game.home_team
        else:
            offense_team = game.home_team
            defense_team = game.away_team
    
    # Update game state with new possession
    game.offense_team = offense_team
    game.defense_team = defense_team
    game.game_state["offensive_state"] = "HCO"
    
    is_away_offense = offense_team.team_id == game.away_team.team_id
    
    # Sideline inbound spot at half court (home orientation)
    inbound_spot_home = {"x": 50, "y": 15}
    
    # Offensive player destinations (half court positions, home orientation)
    home_ranges = {
        "SG": {"x": (48, 52), "y": (22, 28)},
        "SF": {"x": (45, 49), "y": (30, 36)},
        "PF": {"x": (51, 55), "y": (30, 36)},
        "C":  {"x": (48, 52), "y": (38, 44)},
    }
    
    o_dest_home = {}
    for pos, ranges in home_ranges.items():
        o_dest_home[pos] = {
            "x": random.randint(*ranges["x"]),
            "y": random.randint(*ranges["y"]),
        }
    
    # PG stays at inbound spot
    o_dest_home["PG"] = inbound_spot_home.copy()
    
    # Flip if away team has possession
    o_dest = getAwayTeamCoords(o_dest_home.copy()) if is_away_offense else o_dest_home
    bh_coords = o_dest["PG"]
    
    # Defensive positioning
    # Ensure strategy_calls is initialized
    if not hasattr(defense_team, 'strategy_calls') or not defense_team.strategy_calls:
        defense_team.strategy_calls = {}
    aggression = defense_team.strategy_calls.get("aggression_call", "normal")
    d_dest = {}
    
    for pos in defense_team.lineup.keys():
        if pos == "PG":
            d_coords = assign_bh_defender_coords(bh_coords, aggression, is_away_offense, "quarter_start_inbound")
            if is_away_offense:
                d_coords = getAwayTeamCoords({"tmp": d_coords})["tmp"]
            d_dest[pos] = d_coords
        elif pos in o_dest:
            o_coords = o_dest[pos]
            o_calc = getAwayTeamCoords({"tmp": o_coords})["tmp"] if is_away_offense else o_coords
            d_coords = assign_non_bh_defender_coords(o_calc, bh_coords, aggression, is_away_offense)
            if is_away_offense:
                d_coords = getAwayTeamCoords({"tmp": d_coords})["tmp"]
            d_dest[pos] = d_coords
    
    # Build animations array for frontend (like opening tip)
    animations = []
    
    # Offensive players
    for pos, player in offense_team.lineup.items():
        player_id = getattr(player, "player_id", None)
        if player_id:
            start = getattr(player, "coords", {"x": 50, "y": 25})
            end = o_dest[pos]
            animations.append({
                "playerId": player_id,
                "movement": [
                    {"timestamp": 0, "coords": start, "action": "STAND"},
                    {"timestamp": 800, "coords": end, "action": "STAND"},
                ],
            })
            # Update player coords
            player.coords = end.copy()
    
    # Defensive players
    for pos, player in defense_team.lineup.items():
        player_id = getattr(player, "player_id", None)
        if player_id:
            start = getattr(player, "coords", {"x": 50, "y": 25})
            end = d_dest[pos]
            animations.append({
                "playerId": player_id,
                "movement": [
                    {"timestamp": 0, "coords": start, "action": "STAND"},
                    {"timestamp": 800, "coords": end, "action": "STAND"},
                ],
            })
            # Update player coords
            player.coords = end.copy()
    
    # Text
    quarter_num = game.quarter
    text = f"Start of Q{quarter_num}: {offense_team.name} inbounds the ball."
    
    # Return with animations array (like opening tip)
    turn_result = {
        "result_type": "BASELINE_INBOUND",
        "text": text,
        "time_elapsed": 4,
        "possession_flips": False,
        "animations": animations,
        "ball_spot": bh_coords,
        "oDestinations": o_dest,
        "dDestinations": d_dest,
        "possession_team_id": offense_team.team_id,
        "quarter": game.quarter,
    }
    
    return turn_result

