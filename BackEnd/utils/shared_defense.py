import random

def assign_ball_handler_defender_coords(ball_coords, aggression_level: str) -> dict:
    """
    Returns defensive positioning for the ball handler's man-to-man defender.
    Assumes basket is to the right (home team attacking right).
    """
    # Define spacing (1 = tight, 3 = loose)
    spacing_map = {"aggressive": 1, "normal": 2, "passive": 3}
    d_spacing = spacing_map.get(aggression_level.lower(), 2)

    x = ball_coords["x"]
    y = ball_coords["y"]

    # Edge case: ball on baseline
    if y <= 4 or y >= 46:
        y_def = y + d_spacing if y < 25 else y - d_spacing
        x_def = x

    # Edge case: top of key (center court)
    elif 62 <= x <= 66 and 22 <= y <= 28:
        x_def = x - d_spacing
        y_def = y

    # General case
    else:
        x_def = x - d_spacing
        y_def = y + random.randint(1, 3) if y < 25 else y - random.randint(1, 3)

    return {"x": x_def, "y": y_def}

def assign_non_bh_defender_coords(o_coords, ball_coords, aggression_level):
    """
    Assigns defensive positioning for a non-ball-handler defender in man defense.
    Returns {"x": int, "y": int}
    """

    d_spacing_map = {"aggressive": 1, "normal": 2, "passive": 3}
    d_spacing = d_spacing_map.get(aggression_level.lower(), 2)

    ox, oy = o_coords["x"], o_coords["y"]
    bx, by = ball_coords["x"], ball_coords["y"]

    # Edge case: defending someone on the block or in the lane (score threat)
    if 74 <= ox <= 88 and 15 <= oy <= 33:
        return {
            "x": ox - d_spacing,
            "y": oy + random.choice([-1, 1, 0])
        }

    # Edge case: defending someone on the baseline
    elif oy <= 6 or oy >= 44:
        return {
            "x": ox - random.randint(1, 3),
            "y": oy + d_spacing if oy < 25 else oy - d_spacing
        }

    # Edge case: defending someone near the top or wings and ball is on the key
    elif 62 <= bx <= 66 and 22 <= by <= 28:
        return {
            "x": ox - random.randint(2, 4),
            "y": oy + (1 if oy < 25 else -1)
        }

    # General rule: mirror ball spacing, maintain triangle
    else:
        delta_x = bx - ox
        delta_y = by - oy

        x = ox + int(delta_x * 0.3) - d_spacing
        y = oy + int(delta_y * 0.3) + random.choice([-1, 0, 1])

        return {"x": x, "y": y}

