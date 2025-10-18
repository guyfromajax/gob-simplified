import random

# Starting positions for opening tip
OPENING_TIP_POSITIONS = {
    "home": {
        "PG": {"x": 37, "y": 25},
        "SG": {"x": 43, "y": 15},
        "SF": {"x": 45, "y": 38},
        "PF": {"x": 46, "y": 19},
        "C": {"x": 48, "y": 25},
    },
    "away": {
        "PG": {"x": 64, "y": 25},
        "SG": {"x": 58, "y": 13},
        "SF": {"x": 55, "y": 38},
        "PF": {"x": 56, "y": 20},
        "C": {"x": 52, "y": 25},
    }
}

def get_height_scale_value(height):
    """Convert player height to tip-off scale value"""
    if height > 83:
        return 10
    elif height >= 81:
        return 9
    elif height >= 79:
        return 8
    elif height == 78:
        return 7
    elif height == 77:
        return 6
    elif height == 76:
        return 5
    elif height == 75:
        return 4
    elif height == 74:
        return 3
    elif height == 73:
        return 2
    else:  # < 73
        return 1

def execute_opening_tip(game):
    """
    Execute opening tip logic and return turn data with animations.
    Returns a turn dict suitable for the turns array.
    """
    from BackEnd.utils.shared import get_name_safe
    
    home_tipper = game.home_team.lineup["C"]
    away_tipper = game.away_team.lineup["C"]
    home_lineup = game.home_team.lineup
    away_lineup = game.away_team.lineup

    # Calculate tip scores
    home_scale = get_height_scale_value(home_tipper.height)
    away_scale = get_height_scale_value(away_tipper.height)
    
    home_value = home_scale * random.randint(1, 6)
    away_value = away_scale * random.randint(1, 6)
    
    # Determine winner (ties go to home team)
    home_wins = home_value >= away_value
    
    if home_wins:
        offense_team = game.home_team
        defense_team = game.away_team
        winner_name = get_name_safe(home_tipper)
        winner_team_name = game.home_team.name
    else:
        offense_team = game.away_team
        defense_team = game.home_team
        winner_name = get_name_safe(away_tipper)
        winner_team_name = game.away_team.name
    
    # Store the winner in game state for quarter possession logic
    game.game_state["opening_tip_winner"] = "home" if home_wins else "away"
    
    # Set possession
    game.offense_team = offense_team
    game.defense_team = defense_team
    game.game_state["offensive_state"] = "HCO"
    
    # Determine ball landing spot (tighter range around center court)
    # Home team attacks left (away basket), so ball goes left (x < 50) when home wins
    # Away team attacks right (home basket), so ball goes right (x > 50) when away wins
    ball_spot_y = random.randint(20, 30)  # More centered vertically
    if home_wins:
        ball_spot_x = random.randint(42, 48)  # Home wins -> ball bounces left (toward home teammates)
    else:
        ball_spot_x = random.randint(52, 58)  # Away wins -> ball bounces right (toward away teammates)
    
    ball_landing_coords = {"x": ball_spot_x, "y": ball_spot_y}
    print(f"🏀 Opening tip ball landing at: x={ball_spot_x}, y={ball_spot_y} ({'home' if home_wins else 'away'} wins)")
    
    # Build animations for all players
    animations = []
    
    # Add home team players
    for pos, player in home_lineup.items():
        start_coords = OPENING_TIP_POSITIONS["home"][pos].copy()
        
        if pos == "C":
            # Center jumps up
            animations.append({
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "jumpCoords": {"x": start_coords["x"], "y": start_coords["y"] + 4},
                "end": start_coords,  # Returns to starting position after jump
                "action": "TIP_JUMP"
            })
        else:
            # Other players move toward ball spot
            animations.append({
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "end": ball_landing_coords if home_wins and is_closest_to_ball(pos, ball_landing_coords, home_lineup, "home") else get_nearby_spot(ball_landing_coords),
                "action": "CONVERGE_ON_BALL"
            })
    
    # Add away team players
    for pos, player in away_lineup.items():
        start_coords = OPENING_TIP_POSITIONS["away"][pos].copy()
        
        if pos == "C":
            # Center jumps up
            animations.append({
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "jumpCoords": {"x": start_coords["x"], "y": start_coords["y"] + 4},
                "end": start_coords,  # Returns to starting position after jump
                "action": "TIP_JUMP"
            })
        else:
            # Other players move toward ball spot
            animations.append({
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "end": ball_landing_coords if not home_wins and is_closest_to_ball(pos, ball_landing_coords, away_lineup, "away") else get_nearby_spot(ball_landing_coords),
                "action": "CONVERGE_ON_BALL"
            })
    
    # Random time elapsed (2-5 seconds)
    time_elapsed = random.randint(2, 5)
    
    text = f"{winner_name} wins the tip!"
    
    turn_result = {
        "result_type": "OPENING_TIP",
        "text": text,
        "time_elapsed": time_elapsed,
        "possession_flips": False,
        "animations": animations,
        "ball_landing_coords": ball_landing_coords,
        "home_wins": home_wins,
        "winner": winner_name,
        "next_play_type": "HCO",
        "quarter": game.quarter,  # Add quarter field for frontend filtering
    }
    
    return turn_result

def is_closest_to_ball(pos, ball_coords, lineup, team):
    """Determine if this position is closest to the ball landing spot (excluding C)"""
    positions = OPENING_TIP_POSITIONS[team]
    min_distance = float('inf')
    closest_pos = None
    
    for p in positions:
        if p == "C":  # Skip center
            continue
        coords = positions[p]
        distance = ((coords["x"] - ball_coords["x"]) ** 2 + (coords["y"] - ball_coords["y"]) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            closest_pos = p
    
    return pos == closest_pos

def get_nearby_spot(ball_coords):
    """Get a spot near the ball for players converging"""
    return {
        "x": ball_coords["x"] + random.randint(-3, 3),
        "y": ball_coords["y"] + random.randint(-3, 3)
    }

def player_tip_score(player):
    """Legacy function - kept for compatibility"""
    tip_score = 0
    height_score_dict = {
        82: 11,
        81: 10,
        80: 9,
        79: 8,
        78: 7,
        77: 6,
        76: 5,
        75: 4,
        74: 3,
        73: 2,
    }

    if player.height in height_score_dict:
        tip_score += height_score_dict[player.height] * random.randint(1, 6)
    else:
        tip_score += random.randint(1, 5)

    return tip_score