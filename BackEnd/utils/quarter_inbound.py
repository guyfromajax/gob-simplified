"""
Quarter start inbound pass logic for Q2, Q3, Q4
Similar to baseline inbound but at center court
"""
import random
from BackEnd.utils.shared import getAwayTeamCoords
from BackEnd.utils.shared_defense import assign_bh_defender_coords, assign_non_bh_defender_coords


def execute_quarter_start_inbound(game):
    """
    Create an inbound pass turn for the start of Q2, Q3, or Q4.
    The team with possession starts at center court (sideline inbound).
    
    Returns a turn result dict with animations for all players.
    """
    offense_team = game.offense_team
    defense_team = game.defense_team
    is_away_offense = offense_team.team_id == game.away_team.team_id
    
    # Center court sideline inbound spot (home orientation)
    inbound_spot_home = {"x": 50, "y": 10}  # Sideline at center court
    
    # Destination ranges for offensive players receiving the inbound (home orientation)
    home_ranges = {
        "SG": {"x": (48, 52), "y": (20, 26)},
        "SF": {"x": (46, 50), "y": (28, 34)},
        "PF": {"x": (52, 56), "y": (28, 34)},
        "C":  {"x": (48, 52), "y": (36, 42)},
    }
    
    o_dest_home = {}
    for pos, ranges in home_ranges.items():
        o_dest_home[pos] = {
            "x": random.randint(*ranges["x"]),
            "y": random.randint(*ranges["y"]),
        }
    
    # Inbounder (PG) stays at the inbound spot
    o_dest_home["PG"] = inbound_spot_home.copy()
    
    # Flip coordinates if away team has possession
    o_dest = getAwayTeamCoords(o_dest_home.copy()) if is_away_offense else o_dest_home
    bh_coords = o_dest["PG"]
    
    # Defensive positioning
    aggression = defense_team.strategy_calls.get("aggression_call", "normal")
    d_dest = {}
    for pos, defender in defense_team.lineup.items():
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
    
    # Build animations for all players
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
    
    # Update player positions
    for pos, player in offense_team.lineup.items():
        player.coords = o_dest[pos].copy()
    for pos, player in defense_team.lineup.items():
        player.coords = d_dest[pos].copy()
    
    # Determine receiver (randomly choose from SG, SF, PF, C)
    receiver_pos = random.choice(["SG", "SF", "PF", "C"])
    receiver = offense_team.lineup.get(receiver_pos)
    receiver_name = getattr(receiver, "name", None) or f"{getattr(receiver, 'first_name', '')} {getattr(receiver, 'last_name', '')}".strip()
    
    text = f"Quarter start: {offense_team.name} inbounds the ball to {receiver_name}."
    
    turn_result = {
        "result_type": "QUARTER_START_INBOUND",
        "text": text,
        "time_elapsed": 4,
        "possession_flips": False,
        "animations": animations,
        "ball_spot": bh_coords,
        "receiver": receiver_pos,
        "receiverId": getattr(receiver, "player_id", None),
        "inbounderId": getattr(offense_team.lineup.get("PG"), "player_id", None),
        "next_play_type": game.game_state.get("offensive_state", "HCO"),
        "quarter": game.quarter,
    }
    
    return turn_result

