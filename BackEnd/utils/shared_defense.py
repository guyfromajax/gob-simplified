import random
from BackEnd.utils.shared import get_away_player_coords

def assign_bh_defender_coords(ball_coords, aggression_level: str, is_away_offense: bool) -> dict:
    """
    Returns defensive positioning for the ball handler's man-to-man defender.
    Adjusts based on court orientation: if away team is on offense, direction is reversed.
    """
    spacing_map = {"aggressive": 1, "normal": 2, "passive": 3}
    d_spacing = spacing_map.get(aggression_level.lower(), 2)

    x = ball_coords["x"]
    y = ball_coords["y"]

    # Convert ball handler coords back to home orientation so the spacing logic
    # is consistent regardless of which team has possession.
    if is_away_offense:
        flipped = get_away_player_coords(ball_coords)
        x, y = flipped["x"], flipped["y"]

    direction = -1 if is_away_offense else 1  # direction toward basket
    
    # X-offset direction based on which basket the offense is attacking
    # Home offense (attacking X=90): defender moves toward X=90 (add)
    # Away offense (attacking X=10): defender moves toward X=10 (subtract)
    # Working in home orientation coords, then caller flips result
    # In home coords: home offense goes right (+), away offense goes left (-)
    # But away coords get flipped, so we want: home=+1, away=-1
    x_direction = -1 if is_away_offense else 1

    # Edge case: ball on baseline
    if y <= 4 or y >= 46:
        # Vertical positioning doesn't depend on court orientation
        y_def = y + (d_spacing if y < 25 else -d_spacing)
        x_def = x  # No X spacing on baseline - defender matches ball handler's X

    # Edge case: top of key
    elif 62 <= x <= 66 and 22 <= y <= 28:
        x_def = x + (x_direction * d_spacing)
        y_def = y

    # General case
    else:
        y_shift = direction * random.randint(1, 3)
        y_def = y + y_shift if y < 25 else y - y_shift
        x_def = x + (x_direction * d_spacing)

    return {"x": x_def, "y": y_def}


def assign_non_bh_defender_coords(o_coords, ball_coords, aggression_level, is_away_offense):
    """
    Assigns defensive positioning for a non-ball-handler defender in man defense.
    Returns {"x": int, "y": int}
    """

    d_spacing_map = {"aggressive": 1, "normal": 2, "passive": 3}
    d_spacing = d_spacing_map.get(aggression_level.lower(), 2)

    direction = -1 if is_away_offense else 1  # Determines whether we add or subtract spacing in y

    ox, oy = o_coords["x"], o_coords["y"]
    bx, by = ball_coords["x"], ball_coords["y"]

    # When the away team has the ball the offensive coordinates are flipped
    # horizontally. Convert the ball handler's coordinates back to the home
    # orientation so the logic below can remain consistent.
    if is_away_offense:
        flipped = get_away_player_coords(ball_coords)
        bx, by = flipped["x"], flipped["y"]

    # Determine X-offset direction based on which team is on offense
    # Home offense (attacking X=90): defenders closer to X=90 (x + spacing)
    # Away offense (attacking X=10): defenders closer to X=10 (x - spacing)
    x_direction = -1 if is_away_offense else 1
    
    # Edge case: defending someone on the block or in the lane (score threat)
    if 74 <= ox <= 88 and 15 <= oy <= 33:
        return {
            "x": ox + (x_direction * d_spacing),
            "y": oy + random.choice([-1, 1, 0])
        }

    # Edge case: defending someone on the baseline
    elif oy <= 6 or oy >= 44:
        return {
            "x": ox,  # No X spacing on baseline - defender matches offensive player's X
            # Vertical offset shouldn't flip when court orientation changes
            "y": oy + (d_spacing if oy < 25 else -d_spacing)
        }

    # Edge case: defending someone near the top or wings and ball is on the key
    elif 62 <= bx <= 66 and 22 <= by <= 28:
        return {
            "x": ox + (x_direction * random.randint(2, 4)),
            "y": oy + direction * (1 if oy < 25 else -1)
        }

    # General rule: mirror ball spacing, maintain triangle
    else:
        delta_x = bx - ox
        delta_y = by - oy

        x = ox + int(delta_x * 0.3) + (x_direction * d_spacing)
        y = oy + int(delta_y * 0.3) + direction * random.choice([-1, 0, 1])

        return {"x": x, "y": y}
