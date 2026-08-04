from BackEnd.utils.sim_random import sim_rng as random

from BackEnd.opening_lineup_snapshot import snapshot_opening_lineups_to_game_state
from BackEnd.utils.position_snapshot_ledger import (
    attach_position_snapshots,
    build_opening_tip_snapshot_from_animations,
)

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

OPENING_TIP_ENTRANCE_POSITIONS = {
    "home": {
        "PG": {"x": 74, "y": 46},
        "SG": {"x": 71, "y": 48},
        "SF": {"x": 77, "y": 48},
        "PF": {"x": 80, "y": 50},
        "C": {"x": 68, "y": 50},
    },
    "away": {
        "PG": {"x": 26, "y": 46},
        "SG": {"x": 29, "y": 48},
        "SF": {"x": 23, "y": 48},
        "PF": {"x": 20, "y": 50},
        "C": {"x": 32, "y": 50},
    },
}

def get_height_scale_value(height):
    """Convert player height to tip-off scale value (1-10).

    Re-banded +3 in. for the recalibrated height distribution (design §11.2), then −1in
    for the 2026-08 HS height shift. These are ABSOLUTE inch literals anchored to the centre
    median, NOT offsets from LEAGUE_MEDIAN_HEIGHT_IN — so they do NOT ride a uniform height
    shift and must be re-banded by hand alongside one. After the −1: centre median 82→81
    still lands mid-scale (81 → 8), preserving the tip-off contest.
    """
    if height > 85:
        return 10
    elif height >= 83:
        return 9
    elif height >= 81:
        return 8
    elif height == 80:
        return 7
    elif height == 79:
        return 6
    elif height == 78:
        return 5
    elif height == 77:
        return 4
    elif height == 76:
        return 3
    elif height == 75:
        return 2
    else:  # < 75
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

    snapshot_opening_lineups_to_game_state(game)

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
    
    # Determine ball landing spot (more pronounced bounce toward winning team)
    # Home team wins: ball goes left (-7 to -10 x spots)
    # Away team wins: ball goes right (+7 to +10 x spots)
    # Y range: -6 to +6 spots from center
    ball_spot_y = 25 + random.randint(-6, 6)  # Peak height with variation
    
    if home_wins:
        ball_spot_x = 50 + random.randint(-10, -7)  # Home wins -> ball bounces left
    else:
        ball_spot_x = 50 + random.randint(7, 10)   # Away wins -> ball bounces right
    
    ball_landing_coords = {"x": ball_spot_x, "y": ball_spot_y}
    
    # Build animations for all players
    animations = []
    include_entrance = getattr(game, "quarter", 1) == 1
    
    # Add home team players
    for pos, player in home_lineup.items():
        entrance_coords = OPENING_TIP_ENTRANCE_POSITIONS["home"][pos].copy()
        start_coords = OPENING_TIP_POSITIONS["home"][pos].copy()
        
        if pos == "C":
            # Center jumps up - ball bounces at peak, no coming down
            jump_coords = {"x": start_coords["x"], "y": start_coords["y"] + 4}
            animation = {
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "jumpCoords": jump_coords,
                "end": jump_coords,
                "action": "TIP_JUMP"
            }
            if include_entrance:
                animation["entrance"] = entrance_coords
            animations.append(animation)
        else:
            # Other players move slightly toward ball spot (1-3 spots)
            if home_wins and is_closest_to_ball(pos, ball_landing_coords, home_lineup, "home"):
                # Tip winner goes to ball location
                end_coords = ball_landing_coords
            else:
                # Other players move slightly toward ball (1-3 spots)
                end_coords = get_slight_movement_toward_ball(start_coords, ball_landing_coords)
            
            animation = {
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "end": end_coords,
                "action": "CONVERGE_ON_BALL"
            }
            if include_entrance:
                animation["entrance"] = entrance_coords
            animations.append(animation)
    
    # Add away team players
    for pos, player in away_lineup.items():
        entrance_coords = OPENING_TIP_ENTRANCE_POSITIONS["away"][pos].copy()
        start_coords = OPENING_TIP_POSITIONS["away"][pos].copy()
        
        if pos == "C":
            # Center jumps up - ball bounces at peak, no coming down
            jump_coords = {"x": start_coords["x"], "y": start_coords["y"] + 4}
            animation = {
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "jumpCoords": jump_coords,
                "end": jump_coords,
                "action": "TIP_JUMP"
            }
            if include_entrance:
                animation["entrance"] = entrance_coords
            animations.append(animation)
        else:
            # Other players move slightly toward ball spot (1-3 spots)
            if not home_wins and is_closest_to_ball(pos, ball_landing_coords, away_lineup, "away"):
                # Tip winner goes to ball location
                end_coords = ball_landing_coords
            else:
                # Other players move slightly toward ball (1-3 spots)
                end_coords = get_slight_movement_toward_ball(start_coords, ball_landing_coords)
            
            animation = {
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "end": end_coords,
                "action": "CONVERGE_ON_BALL"
            }
            if include_entrance:
                animation["entrance"] = entrance_coords
            animations.append(animation)
    
    # OT-Task 1 (Opening_Tip_UESS_Audit.md #1): the tip burns NO game clock (the
    # clock contract is 480→480 / 240→240 and the ledger authority zeroes this
    # downstream). The old `randint(1,5)+1` stamp was dead — discarded before the
    # commit — but was read first by `_compute_real_time_elapsed_ms`, inflating it
    # by 2-6s (FE clock could visibly tick down then snap back) and firing a
    # spurious `[CLOCK CONTRACT] reconciliation fail` on every tip. Stamp 0 so the
    # intermediate value matches the (correct) committed 0-burn.
    time_elapsed = 0
    
    text = f"{winner_name} wins the tip!"

    # Identify ball handler: the offense (tip-winning) player whose end coord
    # is the ball_landing_coords (the converger). Falls back to PG.
    bh_id = None
    for anim in animations:
        end = anim.get("end") or {}
        if end.get("x") == ball_landing_coords["x"] and end.get("y") == ball_landing_coords["y"]:
            bh_id = anim.get("playerId")
            break
    if bh_id is None:
        pg = offense_team.lineup.get("PG")
        bh_id = getattr(pg, "player_id", None) if pg else None

    turn_result = {
        "result_type": "OPENING_TIP",
        "text": text,
        "time_elapsed": time_elapsed,
        "possession_flips": False,
        "offense_team_id": offense_team.team_id,  # ✅ SS&S: Add offense_team_id (critical for game start!)
        "current_turn": "OPENING_TIP",  # ✅ SS&S: Explicit turn type
        "animations": animations,
        "ball_landing_coords": ball_landing_coords,
        "ball_handler_id": bh_id,  # Tip winner who ran to the ball; consumed by OT→HCO bridge.
        "home_wins": home_wins,
        "winner": winner_name,
        "next_play_type": "HCO",
        "next_turn": "HCO",  # ✅ SS&S: Explicit next turn type
        "quarter": game.quarter,  # Add quarter field for frontend filtering
    }

    attach_position_snapshots(
        turn_result,
        [build_opening_tip_snapshot_from_animations(game, animations)],
    )

    return offense_team, defense_team, turn_result

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

def get_slight_movement_toward_ball(start_coords, ball_coords):
    """Get a spot 1-3 positions toward the ball from starting position"""
    # Calculate direction toward ball
    dx = ball_coords["x"] - start_coords["x"]
    dy = ball_coords["y"] - start_coords["y"]
    
    # Normalize direction (but don't go all the way to ball)
    distance = (dx**2 + dy**2)**0.5
    if distance > 0:
        # Move 1-3 spots toward ball
        move_distance = random.randint(1, 3)
        ratio = min(move_distance / distance, 1.0)  # Don't overshoot
        
        return {
            "x": start_coords["x"] + int(dx * ratio),
            "y": start_coords["y"] + int(dy * ratio)
        }
    else:
        # Already at ball spot, move slightly randomly
        return {
            "x": start_coords["x"] + random.randint(-1, 1),
            "y": start_coords["y"] + random.randint(-1, 1)
        }
