import random
import logging
from BackEnd.utils.shared import get_away_player_coords
from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS, AWAY_RIM_COORDS

def assign_bh_defender_coords(ball_coords, aggression_level: str, is_away_offense: bool, bh_spot: str = "key") -> dict:
    """
    Returns defensive positioning for the ball handler's man-to-man defender.
    
    IMPORTANT: This function always expects and returns coordinates in HOME orientation.
    Callers must unflip coords to home orientation before calling (if they're in away orientation).
    The function returns coords in HOME orientation - callers will flip to away orientation for display if needed.
    
    Ball handler defender positioning:
    - When HOME team has the ball: defender to the RIGHT (x_direction = +1)
    - When AWAY team has the ball: defender to the LEFT (x_direction = -1)
    
    Args:
        ball_coords: Ball handler's coordinates in HOME orientation
        aggression_level: Defense aggression setting
        is_away_offense: Whether away team has the ball (used to determine x_direction)
        bh_spot: Ball handler's spot string ("key", "lower wing", etc.)
    """
    
    
    spacing_map = {"aggressive": 2, "normal": 3, "passive": 4}
    d_spacing = spacing_map.get(aggression_level.lower(), 2)

    # IMPORTANT: This function now always expects and works in HOME orientation.
    # Callers must pass coords in home orientation (unflip if needed before calling).
    # The function returns coords in HOME orientation.
    x_bh = ball_coords["x"]
    y_bh = ball_coords["y"]

    # 🐛 DEBUG: Log coordinate flow inside assign_bh_defender_coords
    if is_away_offense:
        logging.warning(f"🔍 [ASSIGN_BH_DEFENDER] Input coords (home orientation): {ball_coords}")

    y_direction = -1 if y_bh > 25 else 1  # direction toward basket
    
    # Ball handler defender positioning:
    # - When HOME team has the ball: defender should be to the RIGHT (toward home basket at x=90) = x_direction = +1
    # - When AWAY team has the ball: defender should be to the LEFT (toward away basket at x=10) = x_direction = -1
    # This ensures the defender is always between the ball handler and the basket they're attacking.
    x_direction = -1 if is_away_offense else 1
    

    if bh_spot == "key":
        x = x_bh + (x_direction * d_spacing)
        y = y_bh + random.randint(-1,1)
    elif bh_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing"]:
        x = x_bh + (x_direction * d_spacing)
        y = y_bh + random.randint(2,4) * y_direction
    elif bh_spot in ["lower corner", "upper corner", "lower midBaseline", "upper midBaseline", "lower midcorner", "upper midcorner"]:
        x = x_bh
        y = y_bh + (y_direction * d_spacing)
    elif bh_spot in ["midLane","lower lowPost", "upper lowPost", "lower midPost", "upper midPost", "lower highPost", "upper highPost"]:
        x = x_bh + (2 * x_direction)
        y = y_bh + (1 * y_direction)
    elif bh_spot in ["upper apex", "lower apex"]:
        x = x_bh + (2 * x_direction)
        y = y_bh + (2 * y_direction)
    elif bh_spot in ["deep key", "deep lower wing", "deep lower baseline", "deep upper wing", "deep upper baseline"]:
        x = x_bh + (random.randint(12,20) * x_direction)
        y = y_bh + (random.randint(4,8) * y_direction)
    else:
        x = x_bh + (x_direction * random.randint(3,6))
        y = y_bh + random.randint(-3,3)

    result = {"x": x, "y": y}
    
    if is_away_offense:
        logging.warning(f"   - Defender position calculated in home orientation: {result}")
        logging.warning(f"   - x_direction used: {x_direction} (LEFT when away offense)")
        logging.warning(f"   - Final result x < 50 (home side)? {result.get('x', 50) < 50}")
    
    # Function always returns coords in HOME orientation
    # Callers (animator) will flip to away orientation for display if needed
    return result


def assign_non_bh_defender_coords(o_coords, ball_coords, aggression_level, is_away_offense, ball_spot="key", o_spot="key"):
    """
    Assigns defensive positioning for a non-ball-handler defender in man defense.
    Returns {"x": int, "y": int}
    """
    
    # Removed verbose D-positioning log

    d_spacing_map = {"aggressive": 1, "normal": 2, "passive": 3}
    d_spacing = d_spacing_map.get(aggression_level.lower(), 2)  

    ox, oy = o_coords["x"], o_coords["y"]
    bx, by = ball_coords["x"], ball_coords["y"]

    # When the away team has the ball, both offensive and ball coordinates are flipped
    # horizontally. Convert both back to the home orientation so the logic below
    # can remain consistent.
    if is_away_offense:
        flipped_ball = get_away_player_coords(ball_coords)
        bx, by = flipped_ball["x"], flipped_ball["y"]
        # flipped_offense = get_away_player_coords(o_coords)
        # ox, oy = flipped_offense["x"], flipped_offense["y"]
        
        flipped_offense = get_away_player_coords(o_coords)
        ox, oy = flipped_offense["x"], flipped_offense["y"]
    
    # Calculate directions AFTER flipping (if applicable)
    # In home orientation, defenders are always to the right (toward home basket at x=90)
    
    y_direction = -1 if oy > 25 else 1
    # x_direction = 1  # Always toward home basket in home orientation
    x_direction = 1 if bx > ox else -1
    basket_direction = -1 if is_away_offense else 1
    
    if ball_spot == "key":
        if o_spot in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
            x = ox + 0.1 * (abs(bx - ox) * x_direction)
            y = oy + 0.4 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
            x = ox + (random.randint(1,4) * x_direction)#+ 0.5 * (abs(bx - ox) * x_direction)
            y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * y_direction)
        elif o_spot in ["lower midcorner", "upper midcorner"]:
            x = ox
            y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * y_direction)
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * y_direction)
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    elif ball_spot in ["lower wing", "lower midWing", "lower midCorner"]:
        if o_spot in ["lower corner", "lower midCorner", "lower wing", "lower midWing", "lower baseline"]:
            if is_away_offense:
                if bx < ox:
                    #ball is closer to basket
                    x = ox - (abs(bx - ox) * 0.5)
                    y = oy + (random.randint(3,5) * y_direction)
                else:
                    x = ox + random.randint(0,1)
                    y = oy + (random.randint(3,5) * y_direction)
            else:
                if bx > ox:
                    x = bx + random.randint(-1,1)
                    y = oy + (random.randint(3,5) * y_direction)
                else:
                    x = ox + random.randint(-1,1)
                    y = oy + (random.randint(3,5) * y_direction)
        elif o_spot in ["upper corner", "upper midCorner", "upper wing", "upper midWing", "upper baseline"]:
            if is_away_offense:
                if bx < ox:
                    #ball is closer to basket
                    x = ox - (abs(bx - ox) * 0.5)
                    y = oy + ((abs(by - oy) * 0.5) * y_direction)
                else:
                    x = ox + (abs(bx - ox) * 0.5)
                    y = oy + ((abs(by - oy) * 0.5) * y_direction)
            else:
                if bx > ox:
                    x = ox + (abs(bx - ox) * 0.5)
                    y = oy + (random.randint(3,5) * y_direction)
                else:
                    x = ox + random.randint(-1,1)
                    y = oy + (random.randint(3,5) * y_direction)

        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    elif ball_spot in ["upper wing", "upper midWing", "upper midCorner"]:
        if o_spot in ["lower corner", "lower midCorner", "lower wing", "lower midWing", "lower baseline"]:
            if is_away_offense:
                if bx < ox:
                    #ball is closer to basket
                    x = ox - (abs(bx - ox) * 0.5)
                    y = oy + (random.randint(3,5) * y_direction)
                else:
                    x = ox + (abs(bx - ox) * 0.5)
                    y = oy + (random.randint(3,5) * y_direction)
            else:
                if bx > ox:
                    x = bx + random.randint(-1,1)
                    y = oy + (random.randint(3,5) * y_direction)
                else:
                    x = ox + random.randint(-1,1)
                    y = oy + (random.randint(3,5) * y_direction)
        elif o_spot in ["upper corner", "upper midCorner", "upper wing", "upper midWing", "upper baseline"]:
            if is_away_offense:
                if bx < ox:
                    #ball is closer to basket
                    x = ox - (abs(bx - ox) * 0.5)
                    y = oy + ((abs(by - oy) * 0.5) * y_direction)
                else:
                    x = ox + random.randint(0,1)
                    y = oy + ((abs(by - oy) * 0.5) * y_direction)
            else:
                if bx > ox:
                    x = ox + random.randint(0,1)
                    y = oy + (random.randint(3,5) * y_direction)
                else:
                    x = ox + random.randint(-1,1)
                    y = oy + (random.randint(3,5) * y_direction)
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    # elif ball_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midcorner", "upper midcorner"]:
    #     if o_spot in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
    #         x = ox + random.randint(0, 2) * x_direction
    #         y = oy + 4 * y_direction
    #     elif o_spot == "key":
    #         x = bx + (3 * basket_direction)
    #         y = oy + 0.3 * (abs(by - oy) * y_direction)
    #     elif o_spot in ["lower wing","upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
    #         x = bx + (3 * basket_direction)
    #         y = oy + 0.3 * (abs(by - oy) * y_direction)
    #     elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
    #         x = ox - 2 if is_away_offense else ox + 2
    #         y = oy
    #     else:
    #         x = ox + 0.5 * (abs(bx - ox) * x_direction)
    #         y = oy + 0.5 * (abs(by - oy) * y_direction)
    
    elif ball_spot in ["lower corner", "upper corner", "lower midBaseline", "upper midBaseline"]:
        if o_spot in ["upper corner", "lower baseline", "upper baseline"]:
            x = ox + 0.1 *(abs(bx - ox) * x_direction)
            y = oy + (5 * y_direction)
        elif o_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + (4 * y_direction)       
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    elif ball_spot in ["lower lowpost", "upper lowpost", "lower midpost", "upper midpost", "midLane"]:
        if o_spot in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif o_spot in ["key", "lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    elif ball_spot in ["lower highPost", "upper highPost"]:
        if o_spot in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    else:
        if o_spot in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    
    # Create result dictionary from calculated x and y
    result = {"x": int(x), "y": int(y)}
    
    # Edge case: defending someone on the block or in the lane (score threat)
    # if 74 <= ox <= 88 and 15 <= oy <= 33:
    #     result = {
    #         "x": ox + (x_direction * d_spacing),
    #         "y": oy + random.choice([-1, 1, 0])
    #     }

    # # Edge case: defending someone on the baseline
    # elif oy <= 6 or oy >= 44:
    #     result = {
    #         "x": ox,  # No X spacing on baseline - defender matches offensive player's X
    #         # Vertical offset shouldn't flip when court orientation changes
    #         "y": oy + d_spacing * y_direction
    #     }

    # # Edge case: defending someone near the top or wings and ball is on the key
    # elif (62 <= bx <= 66 and 22 <= by <= 28) or (35 <= bx <= 39 and 22 <= by <= 28):
    #     result = {
    #         "x": ox + (x_direction * random.randint(2, 4)),
    #         "y": oy + y_direction * random.randint(1, 3)
    #     }

    # # General rule: mirror ball spacing, maintain triangle
    # else:
    #     delta_x = abs(bx - ox)
    #     delta_y = abs(by - oy)

    #     # x = ox + int(delta_x * 0.3) + (x_direction * d_spacing)
    #     # y = oy + int(delta_y * 0.3) + (y_direction * d_spacing)
    #     x = ox + (int(delta_x * 0.3) * x_direction)
    #     y = oy + (int(delta_y * 0.3) * y_direction)

    #     result = {"x": x, "y": y}
    
    
    return result


# ==================== ZONE DEFENSE LOGIC ====================

# 2-3 Zone Defense: Zone definitions (using spot names from HCO_STRING_SPOTS)
# Each zone is defined by border points that form a polygon
ZONE_23_NORMAL = {
    "PG": ["key", "midLane", "topLane", "upper midCorner", "upper wing", "upper midWing"],
    "SG": ["key", "midLane", "topLane", "lower midCorner", "lower wing", "lower midWing"],
    "SF": ["lower midCorner", "lower corner", "lower lowPost", "lower midPost", "lower apex", "lower bird", "lower midBaseline"],
    "PF": ["upper midCorner", "upper corner", "upper lowPost", "upper midPost", "upper apex", "upper bird", "upper midBaseline"],
    "C": ["upper lowPost", "lower lowPost", "lower midPost", "midLane", "upper midPost"],
}

# Lower shift (ball on lower wing, lower midCorner, or lower corner)
ZONE_23_LOWER_SHIFT = {
    "PG": ["lower midWing", "lower highPost", "upper midCorner", "upper wing", "upper midWing", "key"],
    "SG": ["lower corner", "lower midCorner", "lower wing", "lower midPost", "lower highPost", "lower apex", "lower bird", "lower midBaseline"],
    "SF": ["lower midCorner", "lower corner", "lower lowPost", "lower midPost", "lower apex", "lower bird", "lower midBaseline"],
    "PF": ["upper midCorner", "upper corner", "upper lowPost", "upper midPost", "upper apex", "upper bird", "upper midBaseline"],
    "C": ["upper lowPost", "lower lowPost", "lower midPost", "midLane", "upper midPost"],
}

# Upper shift (ball on upper wing, upper midCorner, or upper corner)
ZONE_23_UPPER_SHIFT = {
    "SG": ["upper midWing", "upper highPost", "lower midCorner", "lower wing", "lower midWing", "key"],  # Removed midLane to mirror Lower PG
    "PG": ["upper corner", "upper midCorner", "upper wing", "upper midPost", "upper highPost", "upper apex", "upper bird", "upper midBaseline"],  # Added upper corner, upper midPost, upper apex, upper bird, upper midBaseline to mirror Lower SG
    "SF": ["lower midCorner", "lower corner", "lower lowPost", "lower midPost", "lower apex", "lower bird", "lower midBaseline"],
    "PF": ["upper midCorner", "upper corner", "upper lowPost", "upper midPost", "upper apex", "upper bird", "upper midBaseline"],
    "C": ["upper lowPost", "lower lowPost", "lower midPost", "midLane", "upper midPost"],
}

# 3-2 Zone Defense: Zone definitions (using spot names from HCO_STRING_SPOTS)
# Each zone is defined by border points that form a polygon
ZONE_32_NORMAL = {
    "PG": ["key", "upper midWing", "upper highPost", "midLane", "lower highPost", "lower midWing"],
    "SG": ["upper wing", "upper midWing", "upper highPost", "upper midPost", "upper bird", "upper midCorner"],
    "SF": ["lower wing", "lower midWing", "lower highPost", "lower midPost", "lower bird", "lower midCorner"],
    "PF": ["basketSpot", "midLane", "upper midPost", "upper bird", "upper midCorner", "upper corner", "upper midBaseline", "upper lowPost"],
    "C": ["basketSpot", "midLane", "lower midPost", "lower bird", "lower midCorner", "lower corner", "lower midBaseline", "lower lowPost"],
}

# Lower corner shift (ball on lower corner)
ZONE_32_LOWER_SHIFT = {
    "PG": ["key", "upper midWing", "upper highPost", "midLane", "lower highPost", "lower midWing"],
    "SG": ["upper wing", "upper midWing", "upper highPost", "upper midPost", "upper bird", "upper midCorner"],
    "SF": ["lower wing", "lower midWing", "lower highPost", "lower midPost", "lower bird", "lower midCorner"],
    "PF": ["basketSpot", "midLane", "upper midPost", "upper bird", "upper midCorner", "upper corner", "upper midBaseline", "upper lowPost", "basketSpot", "midLane", "lower corner"],
    "C": ["basketSpot", "midLane", "lower midPost", "lower bird", "lower midCorner", "lower corner", "lower midBaseline", "lower lowPost"],
}

# Upper corner shift (ball on upper corner)
ZONE_32_UPPER_SHIFT = {
    "PG": ["key", "upper midWing", "upper highPost", "midLane", "lower highPost", "lower midWing"],
    "SG": ["upper wing", "upper midWing", "upper highPost", "upper midPost", "upper bird", "upper midCorner"],
    "SF": ["lower wing", "lower midWing", "lower highPost", "lower midPost", "lower bird", "lower midCorner"],
    "PF": ["basketSpot", "midLane", "upper midPost", "upper bird", "upper midCorner", "upper corner", "upper midBaseline", "upper lowPost"],
    "C": ["basketSpot", "midLane", "lower midPost", "lower bird", "lower midCorner", "lower corner", "lower midBaseline", "lower lowPost", "basketSpot", "midLane", "upper corner"],
}

# 1-3-1 Zone Defense: Zone definitions (using spot names from HCO_STRING_SPOTS)
# Each zone is defined by border points that form a polygon
ZONE_131_NORMAL = {
    "PG": ["key", "lower midWing", "lower wing", "lower apex", "lower highPost", "topLane", "upper highPost", "upper apex", "upper wing", "upper midWing"],
    "SG": ["upper apex", "upper wing", "upper midCorner", "upper bird"],
    "SF": ["lower apex", "lower wing", "lower midCorner", "lower bird"],
    "PF": ["midLane", "lower lowPost", "lower midPost", "lower highPost", "topLane", "upper highPost", "upper midPost", "upper lowPost"],
    "C": ["basketSpot", "upper corner", "upper midBaseline", "upper lowPost", "basketSpot", "lower lowPost", "lower midBaseline", "lower corner", "lower midCorner", "lower bird", "lower midPost", "midLane", "basketSpot"],
}

# Lower shift (ball on lower wing, lower midWing, lower midCorner)
ZONE_131_LOWER_SHIFT = {
    "PG": ["key", "lower midWing", "lower wing", "lower apex", "lower highPost", "topLane"],
    "SG": ["upper midWing", "upper wing", "upper midCorner", "upper corner", "upper midBaseline", "upper lowPost", "upper midPost", "upper highPost"],
    "SF": ["lower midWing", "lower wing", "lower midCorner"],
    "PF": ["midLane", "lower lowPost", "lower midPost", "lower highPost", "topLane", "upper highPost", "upper midPost", "upper lowPost"],
    "C": ["basketSpot", "lower lowPost", "lower midBaseline", "lower corner"],
}

# Lower corner shift (ball on lower corner)
ZONE_131_LOWER_CORNER_SHIFT = {
    "PG": ["key", "lower midWing", "lower wing", "lower apex", "lower highPost", "lower midPost", "midLane", "topLane"],
    "SG": ["key", "upper midWing", "upper wing", "upper midCorner", "upper corner", "upper midBaseline", "upper lowPost", "upper midPost", "upper highPost"],
    "SF": ["lower midWing", "lower wing", "lower midCorner"],
    "PF": ["midLane", "lower lowPost", "lower midPost", "lower highPost", "topLane", "upper highPost", "upper midPost", "upper lowPost"],
    "C": ["lower corner"],
}

# Upper shift (ball on upper wing, upper midWing, upper midCorner)
ZONE_131_UPPER_SHIFT = {
    "PG": ["key", "upper midWing", "upper wing", "upper apex", "upper highPost", "topLane"],
    "SG": ["upper midWing", "upper wing", "upper midCorner"],
    "SF": ["lower midWing", "lower wing", "lower midCorner", "lower corner", "lower midBaseline", "lower lowPost", "lower midPost", "lower highPost"],
    "PF": ["midLane", "lower lowPost", "lower midPost", "lower highPost", "topLane", "upper highPost", "upper midPost", "upper lowPost"],
    "C": ["basketSpot", "upper lowPost", "upper midBaseline", "upper corner"],
}

# Upper corner shift (ball on upper corner)
ZONE_131_UPPER_CORNER_SHIFT = {
    "PG": ["key", "upper midWing", "upper wing", "upper apex", "upper highPost", "upper midPost", "midLane", "topLane"],
    "SG": ["upper midWing", "upper wing", "upper midCorner"],
    "SF": ["key", "lower midWing", "lower wing", "lower midCorner", "lower corner", "lower midBaseline", "lower lowPost", "lower midPost", "lower highPost"],
    "PF": ["midLane", "lower lowPost", "lower midPost", "lower highPost", "topLane", "upper highPost", "upper midPost", "upper lowPost"],
    "C": ["upper corner"],
}


def _get_zone_coords(zone_definition, is_away_offense=False):
    """
    Convert zone definition (list of spot names) to list of coordinate tuples.
    Flips coordinates if away team is on offense.
    
    Args:
        zone_definition: List of spot names (e.g., ["key", "midLane", "upper midCorner"])
        is_away_offense: Whether to flip coordinates for away team
    
    Returns:
        List of (x, y) coordinate tuples forming the zone polygon
    """
    coords = []
    for spot in zone_definition:
        spot_coords = HCO_STRING_SPOTS.get(spot, {"x": 50, "y": 25})
        x, y = spot_coords["x"], spot_coords["y"]
        
        # Flip coordinates if away team is on offense
        if is_away_offense:
            flipped = get_away_player_coords({"x": x, "y": y})
            x, y = flipped["x"], flipped["y"]
        
        coords.append((x, y))
    
    return coords


def _point_in_polygon(point_x, point_y, polygon_coords):
    """
    Check if a point is inside a polygon using ray casting algorithm.
    
    Args:
        point_x: X coordinate of the point
        point_y: Y coordinate of the point
        polygon_coords: List of (x, y) tuples forming the polygon
    
    Returns:
        True if point is inside polygon (or on boundary), False otherwise
    """
    if len(polygon_coords) < 3:
        return False
    
    # Check if point is exactly on any vertex or edge
    for i in range(len(polygon_coords)):
        x1, y1 = polygon_coords[i]
        x2, y2 = polygon_coords[(i + 1) % len(polygon_coords)]
        
        # Check if point is on vertex
        if point_x == x1 and point_y == y1:
            return True
        
        # Check if point is on edge (using cross product and distance)
        # Edge is from (x1,y1) to (x2,y2)
        # Point is on edge if cross product is 0 and point is between endpoints
        cross_product = (point_x - x1) * (y2 - y1) - (point_y - y1) * (x2 - x1)
        if abs(cross_product) < 0.01:  # On the line (small tolerance for floating point)
            # Check if point is between endpoints
            if min(x1, x2) <= point_x <= max(x1, x2) and min(y1, y2) <= point_y <= max(y1, y2):
                return True
    
    # Ray casting algorithm
    inside = False
    j = len(polygon_coords) - 1
    
    for i in range(len(polygon_coords)):
        xi, yi = polygon_coords[i]
        xj, yj = polygon_coords[j]
        
        if ((yi > point_y) != (yj > point_y)) and (point_x < (xj - xi) * (point_y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    
    return inside


def _get_23_zone_boundaries(ball_spot, is_away_offense=False):
    """
    Get zone boundaries for 2-3 zone defense, applying shifts based on ball location.
    
    Args:
        ball_spot: String spot name where ball is located
        is_away_offense: Whether away team is on offense
    
    Returns:
        Dict mapping position → list of (x, y) coordinate tuples for that zone
    """
    # Determine which zone definition to use based on ball location
    # Shift is triggered by ball on strong perimeter positions (wing, midCorner, corner)
    # but NOT by midWing positions (weaker perimeter threat)
    if ball_spot in ["lower wing", "lower midCorner", "lower corner"]:
        zone_def = ZONE_23_LOWER_SHIFT
    elif ball_spot in ["upper wing", "upper midCorner", "upper corner"]:
        zone_def = ZONE_23_UPPER_SHIFT
    else:
        zone_def = ZONE_23_NORMAL
    
    # Convert spot names to coordinates
    zone_boundaries = {}
    for position, spot_list in zone_def.items():
        zone_boundaries[position] = _get_zone_coords(spot_list, is_away_offense)
    
    return zone_boundaries


def _get_32_zone_boundaries(ball_spot, is_away_offense=False):
    """
    Get zone boundaries for 3-2 zone defense, applying shifts based on ball location.
    
    Args:
        ball_spot: String spot name where ball is located
        is_away_offense: Whether away team is on offense
    
    Returns:
        Dict mapping position → list of (x, y) coordinate tuples for that zone
    """
    # Determine which zone definition to use based on ball location
    # Shift is triggered only by ball in corner positions (not wing or midCorner)
    if ball_spot == "lower corner":
        zone_def = ZONE_32_LOWER_SHIFT
    elif ball_spot == "upper corner":
        zone_def = ZONE_32_UPPER_SHIFT
    else:
        zone_def = ZONE_32_NORMAL
    
    # Convert spot names to coordinates
    zone_boundaries = {}
    for position, spot_list in zone_def.items():
        zone_boundaries[position] = _get_zone_coords(spot_list, is_away_offense)
    
    return zone_boundaries


def _get_131_zone_boundaries(ball_spot, is_away_offense=False):
    """
    Get zone boundaries for 1-3-1 zone defense, applying shifts based on ball location.
    
    Args:
        ball_spot: String spot name where ball is located
        is_away_offense: Whether away team is on offense
    
    Returns:
        Dict mapping position → list of (x, y) coordinate tuples for that zone
    """
    # Determine which zone definition to use based on ball location
    # Lower shift: ball at lower wing, lower midWing, lower midCorner
    if ball_spot in ["lower wing", "lower midWing", "lower midCorner"]:
        zone_def = ZONE_131_LOWER_SHIFT
    # Lower corner shift: ball at lower corner
    elif ball_spot in ["lower corner"]:
        zone_def = ZONE_131_LOWER_CORNER_SHIFT
    # Upper shift: ball at upper wing, upper midWing, upper midCorner
    elif ball_spot in ["upper wing", "upper midWing", "upper midCorner"]:
        zone_def = ZONE_131_UPPER_SHIFT
    # Upper corner shift: ball at upper corner
    elif ball_spot in ["upper corner"]:
        zone_def = ZONE_131_UPPER_CORNER_SHIFT
    else:
        zone_def = ZONE_131_NORMAL
    
    # Convert spot names to coordinates
    zone_boundaries = {}
    for position, spot_list in zone_def.items():
        zone_boundaries[position] = _get_zone_coords(spot_list, is_away_offense)
    
    return zone_boundaries


def _point_in_zone(point_coords, zone_coords, is_away_offense=False):
    """
    Check if a point is in a zone polygon.
    
    Args:
        point_coords: Dict with "x" and "y" keys, or (x, y) tuple
        zone_coords: List of (x, y) tuples forming the zone polygon
        is_away_offense: Whether to flip point coordinates for away team
    
    Returns:
        True if point is in zone, False otherwise
    """
    if isinstance(point_coords, dict):
        x, y = point_coords["x"], point_coords["y"]
    else:
        x, y = point_coords
    
    # Flip coordinates if away team is on offense
    if is_away_offense:
        flipped = get_away_player_coords({"x": x, "y": y})
        x, y = flipped["x"], flipped["y"]
    
    return _point_in_polygon(x, y, zone_coords)


def _manhattan_distance_to_basket(coords, is_away_offense=False):
    """
    Calculate Manhattan distance from a point to the basket being attacked.
    
    Note: Coords are in flipped state (away orientation) if away offense.
    Basket coords must match the same orientation as the input coords.
    
    Args:
        coords: Dict with "x" and "y" keys, or (x, y) tuple (in flipped state if away offense)
        is_away_offense: Whether away team is on offense
    
    Returns:
        Manhattan distance (|x - basket_x| + |y - basket_y|)
    """
    if isinstance(coords, dict):
        x, y = coords["x"], coords["y"]
    else:
        x, y = coords
    
    # Get basket coordinates - basket being attacked
    # The basket being attacked is always AWAY_RIM_COORDS (x=10):
    # - When away offense: Coords are in away orientation, home basket (x=90 home) = x=10 away = AWAY_RIM_COORDS
    # - When home offense: Coords are in home orientation, away basket (x=10 home) = AWAY_RIM_COORDS
    basket = AWAY_RIM_COORDS
    
    return abs(x - basket["x"]) + abs(y - basket["y"])


def _distance_toward_basket(point_coords, ball_handler_coords, is_away_offense=False):
    """
    Calculate how far a point is "toward the basket" relative to the ball handler's direction.
    This measures progress in the direction of attack.
    
    Args:
        point_coords: Dict with "x" and "y" keys for the point to measure
        ball_handler_coords: Dict with "x" and "y" keys for ball handler position
        is_away_offense: Whether away team is on offense
    
    Returns:
        Distance toward basket (positive means closer to basket than ball handler)
    """
    if isinstance(point_coords, dict):
        px, py = point_coords["x"], point_coords["y"]
    else:
        px, py = point_coords
    
    if isinstance(ball_handler_coords, dict):
        bx, by = ball_handler_coords["x"], ball_handler_coords["y"]
    else:
        bx, by = ball_handler_coords
    
    # Flip coordinates to home orientation for calculation
    if is_away_offense:
        flipped_point = get_away_player_coords({"x": px, "y": py})
        px, py = flipped_point["x"], flipped_point["y"]
        flipped_bh = get_away_player_coords({"x": bx, "y": by})
        bx, by = flipped_bh["x"], flipped_bh["y"]
    
    # Get basket coordinates - basket being attacked
    # After flipping, coords are in home orientation
    # - When away offense (after flip): Coords in home orientation, attacking home basket (x=90) = HOME_RIM_COORDS
    # - When home offense: Coords in home orientation, attacking away basket (x=10) = AWAY_RIM_COORDS
    if is_away_offense:
        basket = HOME_RIM_COORDS  # Away team attacking home basket (in home orientation after flip)
    else:
        basket = AWAY_RIM_COORDS  # Home team attacking away basket (in home orientation)
    
    # Calculate progress toward basket
    # Distance from point to basket vs distance from ball handler to basket
    point_to_basket = abs(px - basket["x"]) + abs(py - basket["y"])
    bh_to_basket = abs(bx - basket["x"]) + abs(by - basket["y"])
    
    # Return difference (negative = further from basket, positive = closer to basket)
    return bh_to_basket - point_to_basket


def _find_closest_spot_in_zone_to_point(zone_coords, target_coords, is_away_offense=False):
    """
    Find the spot in a zone that is closest to a target point.
    
    Args:
        zone_coords: List of (x, y) tuples forming the zone polygon
        target_coords: Dict with "x" and "y" keys for target point
        is_away_offense: Whether to flip coordinates for away team
    
    Returns:
        Dict with "x" and "y" keys for closest spot in zone
    """
    if isinstance(target_coords, dict):
        tx, ty = target_coords["x"], target_coords["y"]
    else:
        tx, ty = target_coords
    
    # Flip target coordinates if away team is on offense
    if is_away_offense:
        flipped = get_away_player_coords({"x": tx, "y": ty})
        tx, ty = flipped["x"], flipped["y"]
    
    # Find closest point in zone (minimum Euclidean distance)
    min_dist = float('inf')
    closest = zone_coords[0]
    
    for zone_point in zone_coords:
        zx, zy = zone_point
        dist = ((tx - zx) ** 2 + (ty - zy) ** 2) ** 0.5
        if dist < min_dist:
            min_dist = dist
            closest = zone_point
    
    # Convert back to dict and flip if needed
    result = {"x": closest[0], "y": closest[1]}
    if is_away_offense:
        result = get_away_player_coords(result)
    
    return result


def _map_deep_location_to_zone_location(ball_spot):
    """
    Map deep court locations to their corresponding zone locations.
    Deep locations are outside zone boundaries but need to be guarded by zone defenders.
    
    Args:
        ball_spot: String spot name (e.g., "deep key", "deep lower wing")
    
    Returns:
        Mapped zone location string, or original spot if not a deep location
    """
    deep_location_map = {
        "deep key": "key",
        "deep lower wing": "lower wing",
        "deep lower baseline": "lower wing",
        "deep upper wing": "upper wing",
        "deep upper baseline": "upper wing",
    }
    return deep_location_map.get(ball_spot, ball_spot)


def assign_zone_defender_coords(
    defender_pos,
    zone_boundaries,
    offensive_players,
    ball_handler_coords,
    ball_spot,
    aggression_level,
    is_away_offense
):
    """
    Assign defensive coordinates for a zone defender based on priorities and zone logic.
    
    Args:
        defender_pos: Position of defender (e.g., "PG", "SG")
        zone_boundaries: Dict mapping position → list of (x, y) tuples for that zone
        offensive_players: List of dicts with "coords" and optionally "is_ball_handler" keys
        ball_handler_coords: Dict with "x" and "y" keys for ball handler
        ball_spot: String spot name where ball is located
        aggression_level: Defense aggression setting
        is_away_offense: Whether away team is on offense
    
    Returns:
        Dict with "x" and "y" keys for defender position, or None if no assignment
    """
    if defender_pos not in zone_boundaries:
        return None
    
    # Get zone coordinates (already converted to tuples in zone_boundaries)
    defender_zone_coords_list = zone_boundaries[defender_pos]
    
    # PRIORITY 1: Check if ball handler is in defender's zone
    # ✅ Zone boundaries are in same orientation as ball_handler_coords (both flipped if away offense)
    # So pass is_away_offense=False to _point_in_zone so it doesn't flip coords (they're already matched)
    ball_handler_in_zone = _point_in_zone(ball_handler_coords, defender_zone_coords_list, False)
    
    if ball_handler_in_zone:
        # Guard ball handler
        # assign_bh_defender_coords now returns HOME orientation when away team has the ball
        # (to keep defender on home side where they should be)
        # So we want HOME orientation for consistency, which we already have
        
        # 🐛 DEBUG: Log coordinate flow for ball handler's defender
        logging.warning(f"🔍 [ZONE DEFENSE DEBUG] assign_zone_defender_coords - Defender {defender_pos}, BH in zone")
        logging.warning(f"   - is_away_offense: {is_away_offense}")
        logging.warning(f"   - BH coords (input, away orientation): {ball_handler_coords}")
        logging.warning(f"   - BH coords x < 50 (away side)? {ball_handler_coords.get('x', 50) < 50}")
        
        # assign_bh_defender_coords expects home-oriented coords, so unflip if away offense
        if is_away_offense:
            ball_handler_coords_home = get_away_player_coords(ball_handler_coords)
            logging.warning(f"   - BH coords unflipped to home orientation: {ball_handler_coords_home}")
        else:
            ball_handler_coords_home = ball_handler_coords
        result = assign_bh_defender_coords(ball_handler_coords_home, aggression_level, is_away_offense, ball_spot)
        
        logging.warning(f"   - Coords from assign_bh_defender_coords (home orientation): {result}")
        logging.warning(f"   - Coords x < 50 (home side)? {result.get('x', 50) < 50}")
        logging.warning(f"   - Expected: x < 50 (home side for defender), Actual: x={result.get('x')}")
        # Don't unflip - assign_bh_defender_coords already returns home orientation when away team has ball
        
        return result
    
    # PRIORITY 1.5: Handle deep locations (ball handler outside zone boundaries)
    # Map deep locations to zone locations and check if mapped location is in this defender's zone
    mapped_zone_location = _map_deep_location_to_zone_location(ball_spot)
    if mapped_zone_location != ball_spot:  # This is a deep location
        # Get coordinates for the mapped zone location (e.g., "key" instead of "deep key")
        mapped_coords = HCO_STRING_SPOTS.get(mapped_zone_location, None)
        if mapped_coords:
            # HCO_STRING_SPOTS are in home orientation
            # Check if mapped location is in this defender's zone (need to flip for zone check if away offense)
            mapped_coords_for_zone_check = get_away_player_coords(mapped_coords) if is_away_offense else mapped_coords
            mapped_location_in_zone = _point_in_zone(mapped_coords_for_zone_check, defender_zone_coords_list, False)
            
            if mapped_location_in_zone:
                # Position defender as if guarding the mapped location (not the deep location)
                # This keeps the defender in their zone area while still guarding the ball handler
                # assign_bh_defender_coords expects home-oriented coords, and HCO_STRING_SPOTS are already in home orientation
                result = assign_bh_defender_coords(mapped_coords, aggression_level, is_away_offense, mapped_zone_location)
                return result
    
    # PRIORITY 2: Ball handler not in zone - check for offensive players in zone
    players_in_zone = []
    for off_player in offensive_players:
        if off_player.get("is_ball_handler"):
            continue  # Already handled above
        
        player_coords = off_player.get("coords")
        # ✅ Zone boundaries are in same orientation as player_coords (both flipped if away offense)
        if player_coords and _point_in_zone(player_coords, defender_zone_coords_list, False):
            players_in_zone.append(off_player)
    
    if len(players_in_zone) == 1:
        # One player in zone - guard them
        target_coords = players_in_zone[0]["coords"]
        return assign_non_bh_defender_coords(
            target_coords, 
            ball_handler_coords, 
            aggression_level, 
            is_away_offense, 
            ball_spot,
            players_in_zone[0].get("spot", "key")
        )
    elif len(players_in_zone) > 1:
        # Multiple players - guard the one closest to basket
        closest_to_basket = min(
            players_in_zone,
            key=lambda p: _manhattan_distance_to_basket(p["coords"], is_away_offense)
        )
        return assign_non_bh_defender_coords(
            closest_to_basket["coords"],
            ball_handler_coords,
            aggression_level,
            is_away_offense,
            ball_spot,
            closest_to_basket.get("spot", "key")
        )
    else:
        # No players in zone - position at spot in zone closest to ball handler
        # ✅ Zone coords are in same orientation as ball_handler_coords (both flipped if away offense)
        # _find_closest_spot_in_zone_to_point assumes zones are in home orientation, so it flips target
        # But our zones are now in away orientation if away offense, so pass False (don't flip target)
        # Result will be in away orientation, then unflip to home orientation for consistency
        closest_spot = _find_closest_spot_in_zone_to_point(
            defender_zone_coords_list,
            ball_handler_coords,
            False  # Don't flip - zones and target are already in same orientation
        )
        # ✅ assign_bh_defender_coords/assign_non_bh_defender_coords unflip internally and return home orientation
        # _find_closest_spot_in_zone_to_point returns in away orientation if zones are in away orientation
        # We need to return in home orientation for consistency with other functions
        if is_away_offense:
            # Result is in away orientation (because zones are in away orientation), unflip to home orientation
            closest_spot = get_away_player_coords(closest_spot)
        return closest_spot


def _detect_overlapping_zones(offensive_players, zone_boundaries, is_away_offense):
    """
    Detect offensive players that are in overlapping zones (belong to multiple defenders).
    
    Args:
        offensive_players: List of dicts with "coords", "player_id", and optionally "is_ball_handler", "spot" keys
        zone_boundaries: Dict mapping position → list of (x, y) tuples for that zone
        is_away_offense: Whether away team is on offense
    
    Returns:
        Dict mapping player_id → list of defender positions whose zones contain this player
    """
    overlap_map = {}  # player_id → [list of defender positions]
    
    for off_player in offensive_players:
        player_id = off_player.get("player_id")
        player_coords = off_player.get("coords")
        
        if not player_id or not player_coords:
            continue
        
        zones_containing_player = []
        # ✅ Zone boundaries are in same orientation as player_coords (both flipped if away offense)
        for defender_pos, zone_coords in zone_boundaries.items():
            if _point_in_zone(player_coords, zone_coords, False):
                zones_containing_player.append(defender_pos)
        
        # Only record if player is in multiple zones (overlap)
        if len(zones_containing_player) > 1:
            overlap_map[player_id] = zones_containing_player
    
    return overlap_map


def _resolve_overlap_assignments(
    overlap_player_id,
    overlap_defenders,
    zone_boundaries,
    offensive_players,
    ball_handler_coords,
    ball_spot,
    aggression_level,
    is_away_offense
):
    """
    Resolve which defender should guard an overlap player based on overlap logic.
    
    Args:
        overlap_player_id: ID of the offensive player in overlap
        overlap_defenders: List of defender positions whose zones contain this player
        zone_boundaries: Dict mapping position → list of (x, y) tuples for that zone
        offensive_players: List of all offensive players
        ball_handler_coords: Dict with "x" and "y" keys for ball handler
        ball_spot: String spot name where ball is located
        aggression_level: Defense aggression setting
        is_away_offense: Whether away team is on offense
    
    Returns:
        Dict mapping defender_pos → player_id to guard (None means defender doesn't guard overlap player)
    """
    overlap_player = next((p for p in offensive_players if p.get("player_id") == overlap_player_id), None)
    if not overlap_player:
        return {def_pos: None for def_pos in overlap_defenders}
    
    overlap_coords = overlap_player.get("coords")
    is_ball_handler = overlap_player.get("is_ball_handler", False)
    
    # Check which defenders have other players in their zones
    defenders_with_other_players = {}
    defenders_without_other_players = []
    
    for def_pos in overlap_defenders:
        zone_coords = zone_boundaries[def_pos]
        other_players_in_zone = []
        
        for off_player in offensive_players:
            if off_player.get("player_id") == overlap_player_id:
                continue  # Skip the overlap player itself
            
            player_coords = off_player.get("coords")
            # ✅ Zone boundaries are in same orientation as player_coords (both flipped if away offense)
            if player_coords and _point_in_zone(player_coords, zone_coords, False):
                other_players_in_zone.append(off_player)
        
        if other_players_in_zone:
            defenders_with_other_players[def_pos] = other_players_in_zone
        else:
            defenders_without_other_players.append(def_pos)
    
    assignments = {}
    
    # Case 1: One defender has other players, one doesn't
    if len(defenders_with_other_players) == 1 and len(defenders_without_other_players) == 1:
        # Defender without other players guards overlap player
        for def_pos in defenders_without_other_players:
            assignments[def_pos] = overlap_player_id
        # Defender with other players guards their zone player
        for def_pos, other_players in defenders_with_other_players.items():
            assignments[def_pos] = None  # Will guard one of their zone players
    
    # Case 2: Neither defender has other players
    elif len(defenders_with_other_players) == 0:
        # Both guard overlap player
        for def_pos in overlap_defenders:
            assignments[def_pos] = overlap_player_id
    
    # Case 3: Both defenders have other players
    elif len(defenders_with_other_players) == len(overlap_defenders):
        # Check if ball handler is the overlap player or one of the other players
        ball_handler_in_one_zone = False
        bh_defender = None
        ball_handler_is_overlap = is_ball_handler  # Ball handler is the overlap player itself
        
        # Check if ball handler is one of the other players (not the overlap player)
        for def_pos, other_players in defenders_with_other_players.items():
            for other_player in other_players:
                if other_player.get("is_ball_handler"):
                    ball_handler_in_one_zone = True
                    bh_defender = def_pos
                    break
            if ball_handler_in_one_zone:
                break
        
        if ball_handler_in_one_zone:
            # BH defender guards ball handler (one of their other zone players)
            assignments[bh_defender] = None  # Will guard ball handler via priority logic
            # Other defender guards closest to ball handler (overlap or their zone player)
            other_defender = next(def_pos for def_pos in overlap_defenders if def_pos != bh_defender)
            other_players = defenders_with_other_players[other_defender]
            
            # Compare overlap player vs other zone players - which is closest to ball handler in their direction?
            # Use distance toward basket (progress toward basket relative to ball handler)
            candidates = [overlap_player] + other_players
            closest_to_bh = min(
                candidates,
                key=lambda p: -_distance_toward_basket(
                    p["coords"],
                    ball_handler_coords,
                    is_away_offense
                )  # Negative because we want most progress toward basket (smallest negative = closest toward basket)
            )
            assignments[other_defender] = closest_to_bh.get("player_id")
        elif ball_handler_is_overlap:
            # Ball handler IS the overlap player - both defenders should guard them
            # But check priority: one defender might have other players that are closer to basket
            # For now, let both defenders guard the overlap player (ball handler)
            # This matches case 2 (neither has other players)
            for def_pos in overlap_defenders:
                assignments[def_pos] = overlap_player_id
        else:
            # Neither has ball handler - both guard their zone players
            for def_pos in overlap_defenders:
                assignments[def_pos] = None  # Will guard one of their zone players
    
    return assignments


def assign_all_zone_defenders(
    zone_boundaries,
    offensive_players,
    ball_handler_coords,
    ball_spot,
    aggression_level,
    is_away_offense
):
    """
    Assign defensive coordinates for all zone defenders, handling overlaps.
    
    Args:
        zone_boundaries: Dict mapping position → list of (x, y) tuples for each zone
        offensive_players: List of dicts with "coords", "player_id", and optionally "is_ball_handler", "spot" keys
        ball_handler_coords: Dict with "x" and "y" keys for ball handler
        ball_spot: String spot name where ball is located
        aggression_level: Defense aggression setting
        is_away_offense: Whether away team is on offense
    
    Returns:
        Tuple of:
        - Dict mapping defender_pos → {"x": int, "y": int} coordinates for that defender
        - Dict mapping defender_pos → offensive_player_id (which offensive player each defender is guarding)
    """
    assignments = {}  # defender_pos → {"x": int, "y": int}
    defender_to_offensive_player = {}  # defender_pos → offensive_player_id (tracking which player each defender is guarding)
    
    # Detect overlapping zones
    overlap_map = _detect_overlapping_zones(offensive_players, zone_boundaries, is_away_offense)
    
    # Create map of which defenders are involved in overlaps
    defenders_in_overlaps = set()
    for overlap_player_id, defender_list in overlap_map.items():
        defenders_in_overlaps.update(defender_list)
    
    # Build map of overlap players (to exclude from standard priority logic)
    overlap_player_ids = set(overlap_map.keys())
    
    # First pass: Handle overlap assignments
    overlap_player_to_guard = {}  # defender_pos → player_id to guard from overlap resolution
    overlap_guarded_by = {}  # overlap_player_id → defender_pos who is guarding them
    for overlap_player_id, overlap_defenders in overlap_map.items():
        overlap_assignments = _resolve_overlap_assignments(
            overlap_player_id,
            overlap_defenders,
            zone_boundaries,
            offensive_players,
            ball_handler_coords,
            ball_spot,
            aggression_level,
            is_away_offense
        )
        
        for def_pos, assigned_player_id in overlap_assignments.items():
            if assigned_player_id:
                overlap_player_to_guard[def_pos] = assigned_player_id
                overlap_guarded_by[assigned_player_id] = def_pos
    
    # Second pass: Assign coordinates for each defender
    for defender_pos in ["PG", "SG", "SF", "PF", "C"]:
        if defender_pos not in zone_boundaries:
            continue
        
        # Check if this defender has an overlap assignment
        if defender_pos in overlap_player_to_guard:
            # Guard the overlap-assigned player
            assigned_player_id = overlap_player_to_guard[defender_pos]
            assigned_player = next((p for p in offensive_players if p.get("player_id") == assigned_player_id), None)
            
            if assigned_player:
                # Track which offensive player this defender is guarding
                defender_to_offensive_player[defender_pos] = assigned_player_id
                
                if assigned_player.get("is_ball_handler"):
                    # assigned_player["coords"] are in away orientation if away offense
                    # assign_bh_defender_coords now returns HOME orientation when away team has the ball
                    # (to keep defender on home side where they should be)
                    # So we want HOME orientation for consistency, which we already have
                    
                    # 🐛 DEBUG: Log coordinate flow for ball handler's defender
                    logging.warning(f"🔍 [ZONE DEFENSE DEBUG] assign_all_zone_defenders - Defender {defender_pos} assigned to BH")
                    logging.warning(f"   - is_away_offense: {is_away_offense}")
                    logging.warning(f"   - BH coords (input, away orientation): {assigned_player['coords']}")
                    logging.warning(f"   - BH coords x < 50 (away side)? {assigned_player['coords'].get('x', 50) < 50}")
                    
                    # assign_bh_defender_coords expects home-oriented coords, so unflip if away offense
                    if is_away_offense:
                        bh_coords_home = get_away_player_coords(assigned_player["coords"])
                        logging.warning(f"   - BH coords unflipped to home orientation: {bh_coords_home}")
                    else:
                        bh_coords_home = assigned_player["coords"]
                    coords = assign_bh_defender_coords(
                        bh_coords_home,
                        aggression_level,
                        is_away_offense,
                        ball_spot
                    )
                    
                    logging.warning(f"   - Coords from assign_bh_defender_coords (home orientation): {coords}")
                    logging.warning(f"   - Coords x < 50 (home side)? {coords.get('x', 50) < 50}")
                    logging.warning(f"   - Expected: x < 50 (home side for defender), Actual: x={coords.get('x')}")
                    # Don't unflip - assign_bh_defender_coords already returns home orientation when away team has ball
                else:
                    coords = assign_non_bh_defender_coords(
                        assigned_player["coords"],
                        ball_handler_coords,
                        aggression_level,
                        is_away_offense,
                        ball_spot,
                        assigned_player.get("spot", "key")
                    )
                assignments[defender_pos] = coords
                continue
        
        # If defender is in an overlap but doesn't have overlap assignment, exclude overlap players
        # from their zone consideration (they guard other players in their zone)
        # BUT: Always include ball handler in consideration (they have priority)
        # If not in overlap, use standard priority logic (excluding overlap players already assigned)
        players_to_consider = offensive_players.copy()
        
        # Find ball handler player_id
        ball_handler_id = None
        for p in offensive_players:
            if p.get("is_ball_handler"):
                ball_handler_id = p.get("player_id")
                break
        
        # If this defender is involved in an overlap but not guarding the overlap player,
        # exclude ALL overlap players from their consideration (except ball handler if not already guarded)
        if defender_pos in defenders_in_overlaps and defender_pos not in overlap_player_to_guard:
            # Exclude overlap players, but include ball handler only if not already assigned to another defender
            players_to_consider = [p for p in players_to_consider 
                                  if p.get("player_id") not in overlap_player_ids or 
                                  (p.get("player_id") == ball_handler_id and 
                                   ball_handler_id not in overlap_guarded_by)]
        else:
            # If not in overlap, still exclude overlap players that are already being guarded
            # (but always include ball handler if not already guarded by someone else)
            players_to_consider = [p for p in players_to_consider 
                                  if p.get("player_id") == ball_handler_id or
                                  (p.get("player_id") not in overlap_guarded_by) or 
                                  overlap_guarded_by.get(p.get("player_id")) == defender_pos]
        
        # Use standard priority logic with filtered players
        coords = assign_zone_defender_coords(
            defender_pos,
            zone_boundaries,
            players_to_consider,
            ball_handler_coords,
            ball_spot,
            aggression_level,
            is_away_offense
        )
        if coords:
            assignments[defender_pos] = coords
            # Determine which offensive player this defender is guarding
            # Check which player in players_to_consider is closest to the defender's assigned position
            # or if ball handler is in zone, they're guarding the ball handler
            ball_handler_in_zone = False
            zone_coords = zone_boundaries.get(defender_pos, [])
            if zone_coords:
                for p in players_to_consider:
                    if p.get("is_ball_handler") and _point_in_zone(p.get("coords"), zone_coords, False):
                        defender_to_offensive_player[defender_pos] = p.get("player_id")
                        ball_handler_in_zone = True
                        break
            
            if not ball_handler_in_zone and players_to_consider:
                # Find closest offensive player to defender's assigned position
                min_dist = float('inf')
                closest_player_id = None
                for p in players_to_consider:
                    player_coords = p.get("coords")
                    if player_coords:
                        dist = ((coords["x"] - player_coords["x"]) ** 2 + 
                               (coords["y"] - player_coords["y"]) ** 2) ** 0.5
                        if dist < min_dist:
                            min_dist = dist
                            closest_player_id = p.get("player_id")
                if closest_player_id:
                    defender_to_offensive_player[defender_pos] = closest_player_id
    
    # FALLBACK: Ensure at least one defender guards the ball handler
    # Check if ball handler is being guarded by any defender
    ball_handler_guarded = False
    
    # First check: Is ball handler in any defender's zone?
    for defender_pos, coords in assignments.items():
        zone_coords = zone_boundaries.get(defender_pos, [])
        if zone_coords and _point_in_zone(ball_handler_coords, zone_coords, False):
            ball_handler_guarded = True
            break
    
    # Second check: Is ball handler at a deep location being handled?
    if not ball_handler_guarded:
        mapped_zone_location = _map_deep_location_to_zone_location(ball_spot)
        if mapped_zone_location != ball_spot:  # This is a deep location
            mapped_coords = HCO_STRING_SPOTS.get(mapped_zone_location, None)
            if mapped_coords:
                # Flip mapped coords if away offense (to match zone boundary orientation)
                if is_away_offense:
                    mapped_coords = get_away_player_coords(mapped_coords)
                
                # Check if any defender has the mapped location in their zone
                for defender_pos, coords in assignments.items():
                    zone_coords = zone_boundaries.get(defender_pos, [])
                    if zone_coords and _point_in_zone(mapped_coords, zone_coords, False):
                        ball_handler_guarded = True
                        break
    
    # Third check: Is ball handler in an overlap that was resolved?
    if not ball_handler_guarded:
        for overlap_player_id, overlap_defenders in overlap_map.items():
            # Find the overlap player to check if it's the ball handler
            overlap_player = next((p for p in offensive_players if p.get("player_id") == overlap_player_id), None)
            if overlap_player and overlap_player.get("is_ball_handler"):
                # Ball handler was in an overlap - check if they're being guarded
                if overlap_player_id in overlap_guarded_by:
                    ball_handler_guarded = True
                    break
    
    # Final fallback: If ball handler is still not guarded, assign defender closest to ball handler
    if not ball_handler_guarded:
        
        # Find defender with zone closest to ball handler
        closest_defender = None
        min_distance = float('inf')
        
        # Handle deep locations: use mapped location coordinates for distance calculation
        if ball_spot in ["deep key", "deep lower wing", "deep lower baseline", "deep upper wing", "deep upper baseline"]:
            mapped_zone_location = _map_deep_location_to_zone_location(ball_spot)
            mapped_coords = HCO_STRING_SPOTS.get(mapped_zone_location, ball_handler_coords)
            if is_away_offense:
                search_coords = get_away_player_coords(mapped_coords)
            else:
                search_coords = mapped_coords
        else:
            search_coords = ball_handler_coords
        
        for defender_pos in ["PG", "SG", "SF", "PF", "C"]:
            if defender_pos not in zone_boundaries:
                continue
            
            zone_coords = zone_boundaries[defender_pos]
            if not zone_coords:
                continue
            
            # Calculate center of zone
            avg_x = sum(c[0] for c in zone_coords) / len(zone_coords)
            avg_y = sum(c[1] for c in zone_coords) / len(zone_coords)
            zone_center = {"x": avg_x, "y": avg_y}
            
            # Calculate distance from ball handler (or mapped location) to zone center
            bh_x, bh_y = search_coords["x"], search_coords["y"]
            distance = ((bh_x - zone_center["x"]) ** 2 + (bh_y - zone_center["y"]) ** 2) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                closest_defender = defender_pos
        
        # Assign closest defender to guard ball handler
        if closest_defender:
            # For deep locations, guard the mapped location, not the deep location
            if ball_spot in ["deep key", "deep lower wing", "deep lower baseline", "deep upper wing", "deep upper baseline"]:
                mapped_zone_location = _map_deep_location_to_zone_location(ball_spot)
                mapped_coords = HCO_STRING_SPOTS.get(mapped_zone_location, ball_handler_coords)
                # HCO_STRING_SPOTS are in home orientation, and assign_bh_defender_coords expects home orientation
                # So don't flip mapped_coords
                coords = assign_bh_defender_coords(mapped_coords, aggression_level, is_away_offense, mapped_zone_location)
            else:
                # assign_bh_defender_coords expects home-oriented coords, so unflip if away offense
                if is_away_offense:
                    ball_handler_coords_home = get_away_player_coords(ball_handler_coords)
                else:
                    ball_handler_coords_home = ball_handler_coords
                coords = assign_bh_defender_coords(ball_handler_coords_home, aggression_level, is_away_offense, ball_spot)
            assignments[closest_defender] = coords
            # Track that this defender is guarding the ball handler
            if ball_handler_id:
                defender_to_offensive_player[closest_defender] = ball_handler_id
    
    return assignments, defender_to_offensive_player
