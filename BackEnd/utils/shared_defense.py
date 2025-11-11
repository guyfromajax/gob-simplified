import random
from BackEnd.utils.shared import get_away_player_coords

def assign_bh_defender_coords(ball_coords, aggression_level: str, is_away_offense: bool, bh_spot: str = "key") -> dict:
    """
    Returns defensive positioning for the ball handler's man-to-man defender.
    Adjusts based on court orientation: if away team is on offense, direction is reversed.
    
    Args:
        ball_coords: Ball handler's coordinates
        aggression_level: Defense aggression setting
        is_away_offense: Whether away team has the ball
        bh_spot: Ball handler's spot string ("key", "lower wing", etc.) - NEW
    """
    
    print(f"🏀 BH-defender positioning: bh_spot='{bh_spot}'")
    
    spacing_map = {"aggressive": 1, "normal": 2, "passive": 3}
    d_spacing = spacing_map.get(aggression_level.lower(), 2)

    x = ball_coords["x"]
    y = ball_coords["y"]

    # Convert ball handler coords back to home orientation so the spacing logic
    # is consistent regardless of which team has possession.
    if is_away_offense:
        flipped = get_away_player_coords(ball_coords)
        x_bh, y_bh = flipped["x"], flipped["y"]

    y_direction = -1 if y > 25 else 1  # direction toward basket
    x_direction = -1 if is_away_offense else 1
    

    if bh_spot == "key":
        x = x_bh + (x_direction * d_spacing)
        y = y_bh + random.randint(-1,1)
    elif bh_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing"]:
        x = x_bh + (x_direction * d_spacing)
        y = y_bh + random.randint(2,4) * y_direction
    elif bh_spot in ["lower corner", "upper corner", "lower midcorner", "upper midcorner", "lower midBaseline", "upper midBaseline"]:
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
    
    # Edge case: ball on baseline
    # if y <= 4 or y >= 46:
    #     # Vertical positioning doesn't depend on court orientation
    #     y_def = y + (y_direction * d_spacing)
    #     x_def = x  # No X spacing on baseline - defender matches ball handler's X

    # # Edge case: top of key
    # elif (62 <= x <= 66 or 35 <= x <= 39) and 22 <= y <= 28:
    #     x_def = x + (x_direction * d_spacing)
    #     y_def = y

    # # General case
    # else:
    #     # y_shift = y_direction * random.randint(1, 3)
    #     y_def = y + (y_direction * d_spacing)
    #     # y_def = y + y_shift if y < 25 else y - y_shift
    #     x_def = x + (x_direction * d_spacing)


    return {"x": x, "y": y}


def assign_non_bh_defender_coords(o_coords, ball_coords, aggression_level, is_away_offense, ball_spot="key", o_spot="key"):
    """
    Assigns defensive positioning for a non-ball-handler defender in man defense.
    Returns {"x": int, "y": int}
    """
    
    print(f"🏀 D-positioning: ball_spot='{ball_spot}', o_spot='{o_spot}'")

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
            x = ox #+ 0.5 * (abs(bx - ox) * x_direction)
            y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * y_direction)
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    elif ball_spot in ["lower wing", "upper wing", "lower midwing", "upper midwing"]:
        if o_spot in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
            x = ox + 0.1 * (abs(bx - ox) * x_direction)
            y = oy + 4 * y_direction
        elif o_spot == "key":
            x = bx + (3 * basket_direction)
            y = oy + 0.3 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower wing","upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
            x = bx + (3 * basket_direction)
            y = oy + 0.3 * (abs(by - oy) * y_direction)
        elif o_spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            x = ox - 2 if is_away_offense else ox + 2
            y = oy
        else:
            x = ox + 0.5 * (abs(bx - ox) * x_direction)
            y = oy + 0.5 * (abs(by - oy) * y_direction)
    elif ball_spot in ["lower corner", "upper corner", "lower midcorner", "upper midcorner", "lower midBaseline", "upper midBaseline"]:
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
