"""
Quarter start inbound pass for Q2, Q3, Q4
Uses BASELINE_INBOUND format for frontend compatibility
"""
import random
from BackEnd.utils.shared import getAwayTeamCoords
from BackEnd.utils.shared_defense import assign_bh_defender_coords, assign_non_bh_defender_coords


def create_quarter_start_inbound(game):
    """
    Create an inbound pass turn for Q2/Q3/Q4 start.
    Returns a turn in BASELINE_INBOUND format so frontend can reuse existing logic.
    
    Positions players at half court and shows PG inbounding to a teammate.
    """
    offense_team = game.offense_team
    defense_team = game.defense_team
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
    
    # SF inbounds from sideline, PG receives
    # SF at inbound spot, PG at receive spot
    inbound_spot = inbound_spot_home.copy()
    pg_receive_spot_home = {"x": 50, "y": 25}  # PG receives at center
    
    o_dest_home["SF"] = inbound_spot  # SF inbounds
    o_dest_home["PG"] = pg_receive_spot_home  # PG receives
    
    # Flip if away team has possession
    o_dest = getAwayTeamCoords(o_dest_home.copy()) if is_away_offense else o_dest_home
    bh_coords = o_dest["PG"]  # Ball ends with PG
    
    # Defensive positioning
    aggression = defense_team.strategy_calls.get("aggression_call", "normal")
    d_dest = {}
    
    for pos in defense_team.lineup.keys():
        if pos == "PG":
            d_coords = assign_bh_defender_coords(bh_coords, aggression, is_away_offense)
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
    
    # Get passer (SF) and receiver (PG) player objects
    sf_player = offense_team.lineup.get("SF")
    pg_player = offense_team.lineup.get("PG")
    
    passer_id = getattr(sf_player, "player_id", None)
    receiver_id = getattr(pg_player, "player_id", None)
    passer_name = getattr(sf_player, "name", "SF")
    receiver_name = getattr(pg_player, "name", "PG")
    
    # Text
    quarter_num = game.quarter
    text = f"Start of Q{quarter_num}: {passer_name} inbounds to {receiver_name}."
    
    # Return with animations array and pass data
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
        # Pass data for animation
        "passerId": passer_id,
        "receiverId": receiver_id,
        "passer": passer_name,
        "receiver": receiver_name,
        "pass_origin": o_dest["SF"],  # SF inbound location
        "pass_target": o_dest["PG"],  # PG receive location
    }
    
    return turn_result

