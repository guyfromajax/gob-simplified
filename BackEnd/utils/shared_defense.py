import math
import random
import logging
from BackEnd.utils.shared import get_away_player_coords
from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS, AWAY_RIM_COORDS

# PHASE 6: Old functions removed - use get_defender_coords() instead
# assign_bh_defender_coords() and assign_non_bh_defender_coords() have been removed
# All call sites now use the unified get_defender_coords() system


# ==================== ZONE DEFENSE LOGIC ====================

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


# ==================== HCT (Half Court Trap) Zone Defense ====================
# Stored in home-defending orientation (right-half, x > 50). _get_zone_coords
# flips when away team is on offense, mirroring the HCO zone constants above.
# Two trap defenders per shift sit on the ball handler via trap formation; their
# zone entry is None to signal "compute via trap rules, not polygon".

HCT_STANDARD_NORMAL = {
    "PG": ["center court", "deep key", "deep upper wing", "deep lower wing", "key"],
    "SG": ["deep upper baseline", "deep upper wing", "upper wing"],
    "SF": ["deep lower baseline", "deep lower wing", "lower wing"],
    "PF": ["topLane", "upper apex", "lower apex", "upper highPost", "lower highPost"],
    "C": ["midLane", "upper midPost", "lower midPost", "basketSpot", "upper lowPost", "lower lowPost"],
}

# Upper shift (ball handler y > 30): PG and SG trap the ball handler.
HCT_STANDARD_UPPER_SHIFT = {
    "PG": None,  # ball-handler trapper (trap formation)
    "SG": None,  # ball-handler trapper (trap formation)
    "SF": ["deep key", "key"],
    "PF": ["upper apex", "upper highPost"],
    "C": ["midLane", "upper midPost", "upper lowPost", "basketSpot", "lower lowPost", "lower midPost"],
}

# Lower shift (ball handler y < 20): PG and SF trap the ball handler.
HCT_STANDARD_LOWER_SHIFT = {
    "PG": None,  # ball-handler trapper (trap formation)
    "SG": ["deep key", "key"],
    "SF": None,  # ball-handler trapper (trap formation)
    "PF": ["upper apex", "upper highPost"],
    "C": ["midLane", "upper midPost", "upper lowPost", "basketSpot", "lower lowPost", "lower midPost"],
}

# BH-guarder rectangular clamp box (home-defending orientation; x flips when away offense).
HCT_BH_GUARD_CLAMP_X = (54, 73)
HCT_BH_GUARD_CLAMP_Y_UPPER = (31, 50)
HCT_BH_GUARD_CLAMP_Y_LOWER = (1, 19)

# Trap formation: each trapper at BH_x + (1..4 toward basket), one at BH_y+2, the other at BH_y-2.
HCT_TRAP_X_OFFSET_MIN = 1
HCT_TRAP_X_OFFSET_MAX = 4
HCT_TRAP_Y_OFFSET = 2

# Which trapper takes the +y vs -y slot in each shift.
# +1 = sit at BH_y + offset (above), -1 = sit at BH_y - offset (below).
HCT_BH_GUARDER_Y_OFFSET_SIGN = {
    "upper": {"PG": -1, "SG": +1},
    "lower": {"PG": +1, "SF": -1},
}


def _get_hct_standard_zone_boundaries(ball_y, is_away_offense=False):
    """
    HCT Standard: pick zone variant via ball-handler y, return per-position polygons.

    Shift rules:
        ball_y < 20 → lower shift
        ball_y > 30 → upper shift
        else        → normal (no trap formation)

    Returns ``(zone_boundaries, shift_name)``. ``zone_boundaries`` maps position →
    list of (x, y) tuples for non-trapping defenders, OR ``None`` for the trap
    defenders in upper / lower shifts (caller must run the trap-formation rules
    for those positions).
    """
    try:
        by = float(ball_y)
    except (TypeError, ValueError):
        by = 25.0
    if by < 20:
        zone_def = HCT_STANDARD_LOWER_SHIFT
        shift = "lower"
    elif by > 30:
        zone_def = HCT_STANDARD_UPPER_SHIFT
        shift = "upper"
    else:
        zone_def = HCT_STANDARD_NORMAL
        shift = "normal"

    zone_boundaries = {}
    for position, spot_list in zone_def.items():
        if spot_list is None:
            zone_boundaries[position] = None
        else:
            zone_boundaries[position] = _get_zone_coords(spot_list, is_away_offense)

    return zone_boundaries, shift


def _get_hct_bh_guarders_for_shift(shift):
    """List of defender positions that play trap formation for the given shift."""
    if shift == "upper":
        return ["PG", "SG"]
    if shift == "lower":
        return ["PG", "SF"]
    return []


def _get_hct_bh_guard_clamp_box(shift, is_away_offense=False):
    """
    Return ``(x_min, x_max, y_min, y_max)`` clamp rectangle for trap defenders.

    Stored in home-defending orientation (x ∈ [54, 73]); flipped to x ∈ [27, 46]
    when away team is on offense. Y bands are absolute (no flip): upper shift
    → 31–50, lower shift → 1–19.
    """
    if shift == "upper":
        y_min, y_max = HCT_BH_GUARD_CLAMP_Y_UPPER
    elif shift == "lower":
        y_min, y_max = HCT_BH_GUARD_CLAMP_Y_LOWER
    else:
        return None
    x_min, x_max = HCT_BH_GUARD_CLAMP_X
    if is_away_offense:
        return (100 - x_max, 100 - x_min, y_min, y_max)
    return (x_min, x_max, y_min, y_max)


def resolve_hct_defender_collisions(per_def_coords, bh_coords, rng=None):
    """
    HCT collision avoidance.

    After all defenders have been placed for a single step, prevent any two from
    occupying the **exact same** (x, y). When a collision is detected:

    - If the ball handler is past either baseline (``bh_x < 9`` or ``bh_x > 91``):
      use an X-offset around the ball handler — one mover at ``BH_x + 2``, the
      other at ``BH_x - 2``, both at ``BH_y``.
    - Otherwise: use a Y-offset — one mover at ``BH_y + 2``, the other at
      ``BH_y - 2``, both at ``BH_x``.

    Random pick of which mover takes +2 vs −2.

    For a 3-defender pileup: pick one mover to keep its current spot at random;
    the other two get the pair-resolution above. (4+ pileups: one stays, two are
    repositioned, any remainder stays — extremely rare; not worth special-casing.)

    HCT-specific because it forces both colliding defenders to converge on the
    ball handler — that's fine in HCT (trap intent) but wrong for HCO.
    """
    if rng is None:
        rng = random
    if not per_def_coords or not bh_coords:
        return per_def_coords

    coord_to_positions = {}
    for pos, coords in per_def_coords.items():
        if not coords:
            continue
        key = (int(coords["x"]), int(coords["y"]))
        coord_to_positions.setdefault(key, []).append(pos)

    bh_x = int(round(bh_coords.get("x", 50)))
    bh_y = int(round(bh_coords.get("y", 25)))
    use_x_offset = bh_x < 9 or bh_x > 91

    for _coord_key, positions in coord_to_positions.items():
        if len(positions) < 2:
            continue
        shuffled = list(positions)
        rng.shuffle(shuffled)
        if len(positions) == 2:
            mover_a, mover_b = shuffled[0], shuffled[1]
        else:
            # 3+: keep one at random, resolve the next two as a pair.
            mover_a, mover_b = shuffled[1], shuffled[2]

        if use_x_offset:
            per_def_coords[mover_a] = {"x": bh_x + 2, "y": bh_y}
            per_def_coords[mover_b] = {"x": bh_x - 2, "y": bh_y}
        else:
            per_def_coords[mover_a] = {"x": bh_x, "y": bh_y + 2}
            per_def_coords[mover_b] = {"x": bh_x, "y": bh_y - 2}

    return per_def_coords


def compute_hct_trap_formation(
    bh_coords,
    shift,
    is_away_offense=False,
    rng=None,
):
    """
    Compute (x, y) for the two trap defenders given the ball handler's coords.

    Each trapper sits at ``BH_x + offset * direction`` where ``offset`` is a random
    integer in [1, 4] (the two trappers must use different offsets), and
    ``direction`` is +1 toward the right basket (home offense) or -1 toward the
    left basket (away offense).

    One trapper takes y = BH_y + 2, the other y = BH_y - 2 — see
    ``HCT_BH_GUARDER_Y_OFFSET_SIGN`` for which position takes which slot. If the
    pair would push one defender past the y-clamp, the whole pair shifts as a
    unit so both stay in bounds and the 4-unit y-spacing is preserved.

    Returns ``{position: {"x": int, "y": int}}`` for the two trapper positions
    of the shift, or ``{}`` for normal shift.
    """
    if rng is None:
        rng = random
    clamp = _get_hct_bh_guard_clamp_box(shift, is_away_offense)
    if clamp is None:
        return {}
    x_min, x_max, y_min, y_max = clamp
    direction = -1 if is_away_offense else 1

    trappers = _get_hct_bh_guarders_for_shift(shift)
    if len(trappers) != 2:
        return {}

    sign_map = HCT_BH_GUARDER_Y_OFFSET_SIGN.get(shift, {})

    # Pick two distinct x-offsets in [HCT_TRAP_X_OFFSET_MIN, HCT_TRAP_X_OFFSET_MAX].
    offsets = list(range(HCT_TRAP_X_OFFSET_MIN, HCT_TRAP_X_OFFSET_MAX + 1))
    rng.shuffle(offsets)
    offset_a, offset_b = offsets[0], offsets[1]

    pos_a, pos_b = trappers[0], trappers[1]
    sign_a = sign_map.get(pos_a, +1)
    sign_b = sign_map.get(pos_b, -1)

    bh_x = int(round(bh_coords.get("x", 50)))
    bh_y = int(round(bh_coords.get("y", 25)))

    a_y = bh_y + sign_a * HCT_TRAP_Y_OFFSET
    b_y = bh_y + sign_b * HCT_TRAP_Y_OFFSET

    # Pair-shift if either is outside the y-clamp; preserves the 4-unit spacing.
    over_high = max(a_y, b_y) - y_max
    if over_high > 0:
        a_y -= over_high
        b_y -= over_high
    under_low = y_min - min(a_y, b_y)
    if under_low > 0:
        a_y += under_low
        b_y += under_low
    a_y = max(y_min, min(y_max, a_y))
    b_y = max(y_min, min(y_max, b_y))

    a_x = max(x_min, min(x_max, bh_x + offset_a * direction))
    b_x = max(x_min, min(x_max, bh_x + offset_b * direction))

    return {
        pos_a: {"x": int(a_x), "y": int(a_y)},
        pos_b: {"x": int(b_x), "y": int(b_y)},
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
        # PHASE 5: Use new unified defender coordinate system
        # get_defender_coords handles coordinate orientation automatically
        # ball_handler_coords are already in the correct orientation (away if away offense)
        result = get_defender_coords(
            ball_handler_coords,
            is_away_offense,
            aggression_level,
            ball_spot,
            None,
            is_ball_handler=True
        )
        # get_defender_coords returns coords in same orientation as input (away if away offense)
        # But zone defense expects HOME orientation for consistency with other functions
        # So we need to convert to HOME orientation if away offense
        if is_away_offense:
            # Result is in away orientation, convert to home orientation
            return get_away_player_coords(result)
        else:
            # Result is already in home orientation
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
                # PHASE 5: Use new unified defender coordinate system
                # HCO_STRING_SPOTS are in home orientation, but get_defender_coords handles orientation automatically
                result = get_defender_coords(
                    mapped_coords,
                    is_away_offense,
                    aggression_level,
                    mapped_zone_location,
                    None,
                    is_ball_handler=True
                )
                # get_defender_coords returns in same orientation as input (home orientation here)
                # Zone defense expects HOME orientation, so no conversion needed
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
        # PHASE 5: Use new unified defender coordinate system
        result = get_defender_coords(
            target_coords,
            is_away_offense,
            aggression_level,
            players_in_zone[0].get("spot", "key"),
            ball_handler_coords,
            is_ball_handler=False
        )
        # get_defender_coords returns in same orientation as input (away if away offense)
        # Convert to HOME orientation for consistency with zone defense
        if is_away_offense:
            return get_away_player_coords(result)
        else:
            return result
    elif len(players_in_zone) > 1:
        # Multiple players - guard the one closest to basket
        closest_to_basket = min(
            players_in_zone,
            key=lambda p: _manhattan_distance_to_basket(p["coords"], is_away_offense)
        )
        # PHASE 5: Use new unified defender coordinate system
        result = get_defender_coords(
            closest_to_basket["coords"],
            is_away_offense,
            aggression_level,
            closest_to_basket.get("spot", "key"),
            ball_handler_coords,
            is_ball_handler=False
        )
        # get_defender_coords returns in same orientation as input (away if away offense)
        # Convert to HOME orientation for consistency with zone defense
        if is_away_offense:
            return get_away_player_coords(result)
        else:
            return result
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
            # Ball handler IS the overlap player
            # ✅ NEW LOGIC: Check if defenders have other players in their zones
            # Priority: Ensure at least one defender stays on ball handler
            # If one defender has other players → that defender guards other player, other stays on BH
            # If both have other players → randomly choose one to guard other player, other stays on BH
            # If neither has other players → both guard ball handler (double-team with offsets)
            
            if len(defenders_with_other_players) == 1:
                # One defender has other players → that defender guards other player
                def_with_others = list(defenders_with_other_players.keys())[0]
                other_players = defenders_with_other_players[def_with_others]
                # Guard the closest other player to basket (or first one if multiple)
                closest_other = min(
                    other_players,
                    key=lambda p: _manhattan_distance_to_basket(p["coords"], is_away_offense)
                )
                assignments[def_with_others] = closest_other.get("player_id")
                # Other defender stays on ball handler
                def_without_others = defenders_without_other_players[0]
                assignments[def_without_others] = overlap_player_id
                
            elif len(defenders_with_other_players) == 2:
                # Both defenders have other players → randomly choose one to guard other player
                # The other stays on ball handler (ensuring at least one guards BH)
                def_list = list(defenders_with_other_players.keys())
                chosen_defender = random.choice(def_list)
                other_defender = def_list[0] if def_list[1] == chosen_defender else def_list[1]
                
                # Chosen defender guards closest other player in their zone
                other_players = defenders_with_other_players[chosen_defender]
                closest_other = min(
                    other_players,
                    key=lambda p: _manhattan_distance_to_basket(p["coords"], is_away_offense)
                )
                assignments[chosen_defender] = closest_other.get("player_id")
                # Other defender stays on ball handler
                assignments[other_defender] = overlap_player_id
                
            else:
                # Neither has other players → both guard ball handler (double-team with offsets)
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
                    # PHASE 5: Use new unified defender coordinate system
                    # assigned_player["coords"] are in current orientation (away if away offense)
                    # get_defender_coords handles coordinate orientation automatically
                    coords = get_defender_coords(
                        assigned_player["coords"],
                        is_away_offense,
                        aggression_level,
                        ball_spot,
                        None,
                        is_ball_handler=True
                    )
                    # get_defender_coords returns in same orientation as input (away if away offense)
                    # Zone defense expects HOME orientation, so convert if away offense
                    if is_away_offense:
                        coords = get_away_player_coords(coords)
                else:
                    # PHASE 5: Use new unified defender coordinate system
                    coords = get_defender_coords(
                        assigned_player["coords"],
                        is_away_offense,
                        aggression_level,
                        assigned_player.get("spot", "key"),
                        ball_handler_coords,
                        is_ball_handler=False
                    )
                    # get_defender_coords returns in same orientation as input (away if away offense)
                    # Zone defense expects HOME orientation, so convert if away offense
                    if is_away_offense:
                        coords = get_away_player_coords(coords)
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
            # PHASE 6: Use new unified defender coordinate system
            # get_defender_coords handles coordinate orientation automatically
            if ball_spot in ["deep key", "deep lower wing", "deep lower baseline", "deep upper wing", "deep upper baseline"]:
                mapped_zone_location = _map_deep_location_to_zone_location(ball_spot)
                mapped_coords = HCO_STRING_SPOTS.get(mapped_zone_location, ball_handler_coords)
                # get_defender_coords handles orientation automatically
                coords = get_defender_coords(
                    mapped_coords,
                    is_away_offense,
                    aggression_level,
                    mapped_zone_location,
                    None,
                    is_ball_handler=True
                )
            else:
                # get_defender_coords handles orientation automatically
                coords = get_defender_coords(
                    ball_handler_coords,
                    is_away_offense,
                    aggression_level,
                    ball_spot,
                    None,
                    is_ball_handler=True
                )
            # get_defender_coords returns in same orientation as input (away if away offense)
            # Zone defense expects HOME orientation, so convert if away offense
            if is_away_offense:
                coords = get_away_player_coords(coords)
            assignments[closest_defender] = coords
            # Track that this defender is guarding the ball handler
            if ball_handler_id:
                defender_to_offensive_player[closest_defender] = ball_handler_id
    
    # ✅ Apply offsets when multiple defenders guard the same offensive player
    assignments = _apply_multi_defender_offsets(
        assignments,
        defender_to_offensive_player,
        offensive_players,
        zone_boundaries,
        is_away_offense
    )
    
    return assignments, defender_to_offensive_player


def _apply_multi_defender_offsets(
    assignments,
    defender_to_offensive_player,
    offensive_players,
    zone_boundaries,
    is_away_offense
):
    """
    Apply offsets to defenders when multiple defenders guard the same offensive player.
    Prevents perfect stacking by offsetting defenders based on the spot of the player they're guarding.
    
    Args:
        assignments: Dict mapping defender_pos → {"x": int, "y": int} coordinates
        defender_to_offensive_player: Dict mapping defender_pos → offensive_player_id
        offensive_players: List of offensive player dicts with "player_id", "coords", "spot" keys
        zone_boundaries: Dict mapping defender_pos → list of (x, y) tuples for that zone
        is_away_offense: Whether away team is on offense
    
    Returns:
        Updated assignments dict with offsets applied
    """
    # Determine x direction: 1 if home team is on offense, -1 if away team is on offense
    x_direction = -1 if is_away_offense else 1
    
    # Group defenders by the offensive player they're guarding
    offensive_player_to_defenders = {}
    for defender_pos, offensive_player_id in defender_to_offensive_player.items():
        if offensive_player_id not in offensive_player_to_defenders:
            offensive_player_to_defenders[offensive_player_id] = []
        offensive_player_to_defenders[offensive_player_id].append(defender_pos)
    
    # Apply offsets for each group with multiple defenders
    for offensive_player_id, defender_list in offensive_player_to_defenders.items():
        if len(defender_list) < 2:
            continue  # Only one defender, no offset needed
        
        # Get the offensive player's spot
        offensive_player = next((p for p in offensive_players if p.get("player_id") == offensive_player_id), None)
        if not offensive_player:
            continue
        
        spot = offensive_player.get("spot", "key")
        
        # Sort defenders for consistent ordering (defender 1 vs defender 2)
        defender_list_sorted = sorted(defender_list)
        
        # Determine offset based on spot category
        # ✅ FIX: Use consistent offset patterns for all spots (no zone-area-based logic)
        # This prevents defenders from converging when spots change between steps
        if spot in ["key", "topLane", "upper highPost", "lower highPost", "midLane"]:
            # Use consistent y-axis offset (same as wings) - no zone area logic
            # Defender 1: y += 2, Defender 2: y -= 2
            if len(defender_list_sorted) >= 1:
                assignments[defender_list_sorted[0]]["y"] += 2
            if len(defender_list_sorted) >= 2:
                assignments[defender_list_sorted[1]]["y"] -= 2
        
        elif spot in ["upper wing", "upper midWing", "lower wing", "lower midWing", 
                      "upper apex", "upper bird", "lower apex", "lower bird"]:
            # Defender 1: y += 2, Defender 2: y -= 2
            if len(defender_list_sorted) >= 1:
                assignments[defender_list_sorted[0]]["y"] += 2
            if len(defender_list_sorted) >= 2:
                assignments[defender_list_sorted[1]]["y"] -= 2
        
        elif spot in ["upper midCorner", "upper corner", "lower midCorner", "lower corner",
                      "upper midBaseline", "lower midBaseline", "upper midPost", "upper lowPost",
                      "lower midPost", "lower lowPost"]:
            # Defender 1: x += x_direction * 2, Defender 2: x -= x_direction * 2
            if len(defender_list_sorted) >= 1:
                assignments[defender_list_sorted[0]]["x"] += x_direction * 2
            if len(defender_list_sorted) >= 2:
                assignments[defender_list_sorted[1]]["x"] -= x_direction * 2
    
    return assignments


# ============================================================================
# PHASE 1: UNIFIED DEFENDER COORDINATE SYSTEM
# ============================================================================

def get_spacing(aggression_level: str, is_ball_handler: bool = False) -> int:
    """
    Get defender spacing based on aggression level and defender type.
    
    Args:
        aggression_level: Defense aggression setting ("aggressive", "normal", "passive")
        is_ball_handler: Whether this is the ball handler's defender
    
    Returns:
        Spacing value (grid units)
    """
    if is_ball_handler:
        # BH defenders: tighter spacing
        spacing_map = {"aggressive": 2, "normal": 3, "passive": 4}
    else:
        # Non-BH defenders: looser spacing
        spacing_map = {"aggressive": 1, "normal": 2, "passive": 3}
    
    default_spacing = 3 if is_ball_handler else 2
    return spacing_map.get(aggression_level.lower(), default_spacing)


def verify_defender_closer_to_basket(
    def_x: float, def_y: float,
    off_x: float, off_y: float,
    basket_x: float, basket_y: float
) -> bool:
    """
    Verify that defender is closer to basket than offensive player.
    Used for BH defenders only.
    
    Args:
        def_x, def_y: Defender coordinates
        off_x, off_y: Offensive player coordinates
        basket_x, basket_y: Basket coordinates
    
    Returns:
        True if defender is closer to basket, False otherwise
    """
    defender_to_basket = abs(def_x - basket_x) + abs(def_y - basket_y)
    off_to_basket = abs(off_x - basket_x) + abs(off_y - basket_y)
    return defender_to_basket < off_to_basket


def apply_spot_adjustments(
    def_x: float, def_y: float,
    spot: str,
    unit_x: float, unit_y: float,
    spacing: int,
    is_ball_handler: bool = False
) -> tuple:
    """
    Apply spot-specific adjustments to defender positioning.
    
    Args:
        def_x, def_y: Initial defender coordinates
        spot: Court spot string
        x_direction: X direction (-1 for left, +1 for right)
        y_direction: Y direction (-1 for up, +1 for down)
        spacing: Base spacing value
        is_ball_handler: Whether this is ball handler's defender
    
    Returns:
        Tuple of (adjusted_x, adjusted_y)
    """
    # For most spots, the base calculation is sufficient
    # This function can be extended for specialized positioning if needed
    # Currently, spot-specific logic is handled in calculate_defender_coords()
    return def_x, def_y


def calculate_defender_coords(
    offensive_coords: dict,
    target_basket: dict,
    aggression_level: str,
    spot: str = "key",
    ball_handler_coords: dict = None,
    is_ball_handler: bool = False,
    ball_spot: str = None  # For non-BH defenders: ball handler's spot
) -> dict:
    """
    Calculate defender coordinates for any defensive scenario.
    
    CORE RULES:
    - For BH defenders: Defender is always positioned closer to the basket than the ball handler.
    - For non-BH defenders: Defender is positioned relative to their assignment and ball handler,
      maintaining proper spacing, but may not always be closer to basket.
      Non-BH defenders require ball_spot parameter for complex positioning logic.
    
    Args:
        offensive_coords: Offensive player coordinates in HOME orientation
        target_basket: Basket coordinates being defended (HOME_RIM_COORDS or AWAY_RIM_COORDS)
        aggression_level: Defense aggression ("aggressive", "normal", "passive")
        spot: Court spot string ("key", "lower wing", etc.)
        ball_handler_coords: Optional ball handler coordinates (for non-BH defenders)
        is_ball_handler: Whether this is the ball handler's defender
    
    Returns:
        Defender coordinates in HOME orientation
    """
    ox = offensive_coords["x"]
    oy = offensive_coords["y"]
    basket_x = target_basket["x"]
    basket_y = target_basket["y"]
    
    if is_ball_handler:
        # BH DEFENDER: Always closer to basket than ball handler
        # Pure geometric calculation - no flags, no special cases
        # Calculate direction vector from offensive player to basket
        dx = basket_x - ox  # Positive = toward basket (right), Negative = away from basket (left)
        dy = basket_y - oy  # Positive = toward basket (down), Negative = away from basket (up)
        
        # Normalize direction (unit vector)
        distance_to_basket = ((dx ** 2) + (dy ** 2)) ** 0.5
        if distance_to_basket == 0:
            # Offensive player is at basket (edge case)
            unit_x = 0
            unit_y = 0
        else:
            unit_x = dx / distance_to_basket
            unit_y = dy / distance_to_basket
        
        # Get spacing based on aggression
        spacing = get_spacing(aggression_level, is_ball_handler=True)
        
        # Calculate base defender position: move toward basket by spacing amount
        def_x = ox + (unit_x * spacing)
        def_y = oy + (unit_y * spacing)
        
        # Apply spot-specific positioning
        if spot == "key":
            # Keep geometric calculation, just add small Y variation
            def_y = oy + random.randint(-1, 1)
        elif spot in ["lower wing", "upper wing", "lower midwing", "upper midwing"]:
            # Keep geometric X, adjust Y toward basket
            def_x = ox + (unit_x * spacing)
            def_y = oy + random.randint(2, 4) * (1 if unit_y > 0 else -1)
        elif spot in ["lower corner", "upper corner", "lower midBaseline", "upper midBaseline", 
                      "lower midcorner", "upper midcorner"]:
            # X position: Defender's x should equal ball handler's x
            def_x = ox  # Defender x equals ball handler x
            
            # Y position: Follow corner y-position rules
            # Upper corner: defender's y must be LOWER (defender below ball handler)
            if "upper" in spot:
                def_y = oy - random.randint(2, 4)  # Defender below (lower y value)
            # Lower corner: defender's y must be HIGHER (defender above ball handler)
            elif "lower" in spot:
                def_y = oy + random.randint(2, 4)  # Defender above (higher y value)
        
        # Verify defender is closer to basket (BH defender requirement)
        if not verify_defender_closer_to_basket(def_x, def_y, ox, oy, basket_x, basket_y):
            logging.warning(f"⚠️ [CALCULATE_DEFENDER_COORDS] BH defender not closer to basket! "
                           f"Defender: ({def_x}, {def_y}), BH: ({ox}, {oy}), Basket: ({basket_x}, {basket_y})")
        
    else:
        # NON-BH DEFENDER: Position relative to assignment and ball handler
        # Use the full complex logic from assign_non_bh_defender_coords
        # This requires both ball_spot and o_spot (spot parameter)
        bx = ball_handler_coords["x"] if ball_handler_coords else ox
        by = ball_handler_coords["y"] if ball_handler_coords else oy
        
        # Determine is_away_offense from target_basket
        # If target_basket is HOME_RIM_COORDS, away team is on offense (defending home basket)
        # If target_basket is AWAY_RIM_COORDS, home team is on offense (defending away basket)
        is_away_offense_calc = (target_basket == HOME_RIM_COORDS)
        
        # Calculate directions (matching old function logic)
        y_direction = -1 if oy > 25 else 1
        x_direction = 1 if bx > ox else -1
        basket_direction = -1 if is_away_offense_calc else 1
        
        # Use ball_spot if provided, otherwise default to "key"
        ball_spot_used = ball_spot if ball_spot else "key"
        o_spot_used = spot
        
        # PHASE 4: Implement full non-BH defender logic from assign_non_bh_defender_coords
        # This is the complex logic based on ball_spot and o_spot combinations
        if ball_spot_used == "key":
            if o_spot_used in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
                def_x = ox + 0.1 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.4 * (abs(by - oy) * y_direction)
            elif o_spot_used in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
                def_x = ox + (random.randint(1, 4) * x_direction)
                def_y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * y_direction)
            elif o_spot_used in ["lower midcorner", "upper midcorner"]:
                def_x = ox
                def_y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * y_direction)
            elif o_spot_used in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
                def_x = ox - 2 if is_away_offense_calc else ox + 2
                def_y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * y_direction)
            else:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif ball_spot_used in ["lower wing", "lower midWing", "lower midCorner"]:
            if o_spot_used in ["lower corner", "lower midCorner", "lower wing", "lower midWing", "lower baseline"]:
                if is_away_offense_calc:
                    if bx < ox:
                        def_x = ox - (abs(bx - ox) * 0.5)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                    else:
                        def_x = ox + random.randint(0, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                else:
                    if bx > ox:
                        def_x = bx + random.randint(-1, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                    else:
                        def_x = ox + random.randint(-1, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
            elif o_spot_used in ["upper corner", "upper midCorner", "upper wing", "upper midWing", "upper baseline"]:
                if is_away_offense_calc:
                    if bx < ox:
                        def_x = ox - (abs(bx - ox) * 0.5)
                        def_y = oy + ((abs(by - oy) * 0.5) * y_direction)
                    else:
                        def_x = ox + (abs(bx - ox) * 0.5)
                        def_y = oy + ((abs(by - oy) * 0.5) * y_direction)
                else:
                    if bx > ox:
                        def_x = ox + (abs(bx - ox) * 0.5)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                    else:
                        def_x = ox + random.randint(-1, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
            elif o_spot_used in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
                def_x = ox - 2 if is_away_offense_calc else ox + 2
                def_y = oy
            elif o_spot_used in ["key"]:
                if ball_spot_used in ["lower wing", "lower midWing"]:
                    def_x = bx
                    def_y = oy + 0.5 * (abs(by - oy) * y_direction)
                else:
                    def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                    def_y = oy + 0.5 * (abs(by - oy) * y_direction)
            else:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif ball_spot_used in ["upper wing", "upper midWing", "upper midCorner"]:
            if o_spot_used in ["lower corner", "lower midCorner", "lower wing", "lower midWing", "lower baseline"]:
                if is_away_offense_calc:
                    if bx < ox:
                        def_x = ox - (abs(bx - ox) * 0.5)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                    else:
                        def_x = ox + (abs(bx - ox) * 0.5)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                else:
                    if bx > ox:
                        def_x = bx + random.randint(-1, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                    else:
                        def_x = ox + random.randint(-1, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
            elif o_spot_used in ["upper corner", "upper midCorner", "upper wing", "upper midWing", "upper baseline"]:
                if is_away_offense_calc:
                    if bx < ox:
                        def_x = ox - (abs(bx - ox) * 0.5)
                        def_y = oy + ((abs(by - oy) * 0.5) * y_direction)
                    else:
                        def_x = ox + random.randint(0, 1)
                        def_y = oy + ((abs(by - oy) * 0.5) * y_direction)
                else:
                    if bx > ox:
                        def_x = ox + random.randint(0, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
                    else:
                        def_x = ox + random.randint(-1, 1)
                        def_y = oy + (random.randint(3, 5) * y_direction)
            elif o_spot_used in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
                def_x = ox - 2 if is_away_offense_calc else ox + 2
                def_y = oy
            elif o_spot_used in ["key"]:
                if ball_spot_used in ["upper wing", "upper midWing"]:
                    def_x = bx
                    def_y = oy + 0.5 * (abs(by - oy) * y_direction)
                else:
                    def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                    def_y = oy + 0.5 * (abs(by - oy) * y_direction)
            else:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif ball_spot_used in ["lower corner", "upper corner", "lower midBaseline", "upper midBaseline"]:
            if o_spot_used in ["upper corner", "lower baseline", "upper baseline"]:
                def_x = ox + 0.1 * (abs(bx - ox) * x_direction)
                def_y = oy + (5 * y_direction)
            elif o_spot_used in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + (4 * y_direction)
            elif o_spot_used in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
                def_x = ox - 2 if is_away_offense_calc else ox + 2
                def_y = oy
            else:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif ball_spot_used in ["lower lowpost", "upper lowpost", "lower midpost", "upper midpost", "midLane"]:
            if o_spot_used in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
            elif o_spot_used in ["key", "lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
            elif o_spot_used in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
                def_x = ox - 2 if is_away_offense_calc else ox + 2
                def_y = oy
            else:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
        elif ball_spot_used in ["lower highPost", "upper highPost"]:
            if o_spot_used in ["lower corner", "upper corner", "lower baseline", "upper baseline"]:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
            elif o_spot_used in ["lower wing", "upper wing", "lower midwing", "upper midwing", "lower midCorner", "upper midCorner"]:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
            elif o_spot_used in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
                def_x = ox - 2 if is_away_offense_calc else ox + 2
                def_y = oy
            else:
                def_x = ox + 0.5 * (abs(bx - ox) * x_direction)
                def_y = oy + 0.5 * (abs(by - oy) * y_direction)
        else:
            # Default fallback
            spacing = get_spacing(aggression_level, is_ball_handler=False)
            def_x = ox + (spacing * x_direction)
            def_y = oy + (spacing * y_direction)
    
    return {"x": int(def_x), "y": int(def_y)}


# ── Dynamic HCO Defense — per-turn posture shade (Dynamic_MM_Brief §5; P1) ──────────────────
# Layered on top of the baseline (normal) man position by get_defender_coords ONLY when a posture
# is passed (the HCO dynamic-defense path). posture None/"normal" → no change, so every other turn
# type (fast break, HCT, quarter-start, attack-drives) is untouched. Knobs ported from the visual
# proof scripts/defense_posture_proof.py. Inside-man matchups are locked to normal post D.
#
# The shade runs in the caller's (input) orientation. The attacked rim in that orientation is
# HOME_RIM (x≈91) for home offense and AWAY_RIM (x≈9) for away offense — used AS-IS (both baskets
# sit at fixed court x; away orientation mirrors only the players). The tight-deny uses the ball
# direction instead, so it is orientation-agnostic.
# On-ball cushion delta along the man→basket axis (+ = toward basket = more cushion / sag).
# Dynamic MM S3 — POSTURE-driven placement (retires aggression for the HCO path). All tunable.
# On-ball: sit this many grid off the BH toward the rim, by posture (was aggression's get_spacing 2/3/4).
ONBALL_POSTURE_DIST = {"tight": 2.5, "normal": 3.5, "loose": 4.5}
# Off-ball tight = DENY: sit this many grid off the man, on the ball side (in his passing lane).
POSTURE_DENY_DISTANCE = 2.0
# Off-ball normal/loose = HELP: sit `sag` of the way from the man toward the ball, + a shade toward the
# basket (fraction of man→basket), then anchor per dimension (see _apply_defender_posture).
HELP_SAG = {"normal": 0.30, "loose": 0.55}
HELP_SAG_JITTER = 0.10          # ±0–10% human jitter on the sag fraction (resolved once + frozen → UESS-safe)
HELP_BASKET_SHADE = 0.20        # shade toward the basket, as a fraction of the man→basket distance
HELP_ANCHOR_FLOOR = 0.30        # min follow in the man's basket-aligned dimension ("comes off it some")
# Canonical inside spots (matches motion_read_map.INSIDE_SPOTS; duplicated to avoid an engine
# import cycle in this low-level util). Defenders on these men ignore posture (normal post D).
_POSTURE_INSIDE_SPOTS = frozenset({
    "lower lowpost", "upper lowpost", "lower midpost", "upper midpost", "midlane", "basketspot",
})


def _posture_nudge(px, py, tx, ty, amt):
    """Move point (px,py) `amt` grid toward (tx,ty). Negative amt moves away."""
    dx, dy = tx - px, ty - py
    d = math.hypot(dx, dy) or 1.0
    return (px + dx / d * amt, py + dy / d * amt)


def _apply_defender_posture(def_coords, off_coords, ball_coords, is_ball_handler, o_spot,
                            posture, is_away_offense):
    """Dynamic MM S3 — POSTURE-DRIVEN defender placement (aggression retired for the HCO path). Computes
    the FULL position from man/ball/basket + posture, in the caller's orientation; the aggression base
    (`def_coords`) is used ONLY for inside-man matchups (locked to normal post-D — post-up defense is a
    separate altered-action reaction). posture None → legacy base (FB / tip-off / non-HCO, untouched).

      • On-ball → `ONBALL_POSTURE_DIST[posture]` grid off the BH toward the rim.
      • Off-ball tight → DENY: `POSTURE_DENY_DISTANCE` grid off the man on the ball side (passing lane).
      • Off-ball normal/loose → HELP: sit `HELP_SAG[posture]` (± jitter) of the way from the man toward the
        ball, + `HELP_BASKET_SHADE`·(basket−man) toward the rim, then ANCHOR per dimension by the man's
        basket-offset — `w_d = max(FLOOR, off_d / max(off_x,off_y))` — so the defender follows the help
        spot fully in the far-from-basket dimension but stays near his man (with a floor) in the aligned
        one (key man → anchored in y, corner man → anchored in x; the whole arc, continuously)."""
    if not posture:
        return def_coords
    if (o_spot or "").strip().lower() in _POSTURE_INSIDE_SPOTS:
        return def_coords  # inside-man lock → base post-D
    basket = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    ox, oy = float(off_coords["x"]), float(off_coords["y"])
    bkx, bky = float(basket["x"]), float(basket["y"])

    if is_ball_handler:
        nx, ny = _posture_nudge(ox, oy, bkx, bky, ONBALL_POSTURE_DIST.get(posture, 3.5))
        return {"x": int(round(nx)), "y": int(round(ny))}

    bx, by = (float(ball_coords["x"]), float(ball_coords["y"])) if ball_coords else (bkx, bky)
    if posture == "tight":
        nx, ny = _posture_nudge(ox, oy, bx, by, POSTURE_DENY_DISTANCE)  # DENY: ball-side, in the lane
        return {"x": int(round(nx)), "y": int(round(ny))}

    # normal / loose HELP
    sag = HELP_SAG.get(posture, 0.30) * (1.0 + random.uniform(-HELP_SAG_JITTER, HELP_SAG_JITTER))
    hx = ox + sag * (bx - ox) + HELP_BASKET_SHADE * (bkx - ox)   # ideal help spot (between ball & man, + shade)
    hy = oy + sag * (by - oy) + HELP_BASKET_SHADE * (bky - oy)
    off_x, off_y = abs(ox - bkx), abs(oy - bky)                  # man's basket-offset per axis
    m = max(off_x, off_y) or 1.0
    wx = max(HELP_ANCHOR_FLOOR, off_x / m)
    wy = max(HELP_ANCHOR_FLOOR, off_y / m)
    return {"x": int(round(ox + (hx - ox) * wx)), "y": int(round(oy + (hy - oy) * wy))}


def get_defender_coords(
    offensive_coords: dict,
    is_away_offense: bool,
    aggression_level: str,
    spot: str = "key",
    ball_handler_coords: dict = None,
    is_ball_handler: bool = False,
    ball_spot: str = None,  # For non-BH defenders: ball handler's spot
    posture: str = None     # Dynamic HCO Defense (P1): "tight"/"normal"/"loose"; None = legacy placement
) -> dict:
    """
    Public API for getting defender coordinates.
    Handles coordinate orientation transformation automatically.
    
    This is the main entry point for calculating defender positions. It automatically
    handles coordinate orientation (home/away) so callers don't need to worry about
    flipping coordinates manually.
    
    COORDINATE CONTRACT:
    - Input: Coordinates can be in any orientation (home or away)
    - Internal: All calculations happen in HOME orientation
    - Output: Coordinates returned in same orientation as input
    
    Args:
        offensive_coords: Offensive player coordinates (in current orientation - home or away)
        is_away_offense: Whether away team is on offense
        aggression_level: Defense aggression setting ("aggressive", "normal", "passive")
        spot: Court spot string ("key", "lower wing", etc.)
        ball_handler_coords: Optional ball handler coordinates (for non-BH defenders, in current orientation)
        is_ball_handler: Whether this is the ball handler's defender
    
    Returns:
        Defender coordinates (in same orientation as input)
    
    Example:
        # Home team offense - coordinates already in home orientation
        def_coords = get_defender_coords(
            {"x": 64, "y": 25},  # Offensive player coords (home orientation)
            is_away_offense=False,
            aggression_level="normal",
            spot="key",
            is_ball_handler=True
        )
        # Returns coords in home orientation
        
        # Away team offense - coordinates in away orientation
        def_coords = get_defender_coords(
            {"x": 36, "y": 25},  # Offensive player coords (away orientation)
            is_away_offense=True,
            aggression_level="normal",
            spot="key",
            is_ball_handler=True
        )
        # Returns coords in away orientation (automatically flipped)
    """
    # Determine target basket based on which team is on offense
    # User clarification:
    # - Home team on offense: basket at x=90 (HOME basket)
    # - Away team on offense: basket at x=10 (AWAY basket)
    if is_away_offense:
        # Away team attacking AWAY basket (x=10 in home orientation)
        target_basket = AWAY_RIM_COORDS
    else:
        # Home team attacking HOME basket (x=90 in home orientation)
        target_basket = HOME_RIM_COORDS
    
    # Convert offensive coords to HOME orientation for calculation
    if is_away_offense:
        # Input coords are in away orientation, flip to home orientation
        offensive_coords_home = get_away_player_coords(offensive_coords)
    else:
        # Input coords already in home orientation
        offensive_coords_home = offensive_coords
    
    # Convert ball handler coords if provided
    if ball_handler_coords:
        if is_away_offense:
            # Input coords are in away orientation, flip to home orientation
            ball_handler_coords_home = get_away_player_coords(ball_handler_coords)
        else:
            # Input coords already in home orientation
            ball_handler_coords_home = ball_handler_coords
    else:
        ball_handler_coords_home = None
    
    # Calculate defender position in HOME orientation
    # Core function uses pure geometric calculation
    defender_coords_home = calculate_defender_coords(
        offensive_coords_home,
        target_basket,
        aggression_level,
        spot,
        ball_handler_coords_home,
        is_ball_handler
    )
    
    # Convert result back to original orientation
    if is_away_offense:
        # For away offense: coordinate flip inverts relative positioning
        # Geometric calculation gives correct position in home orientation,
        # but after flipping, defender ends up on wrong side.
        # Solution: Check if defender is on correct side in away orientation,
        # and if not, invert the x position in home orientation before flipping.
        defender_coords_away = get_away_player_coords(defender_coords_home)
        offensive_coords_away = get_away_player_coords(offensive_coords_home)
        
        # For away offense, defender should be LEFT (x < offensive x) in away orientation
        if defender_coords_away["x"] > offensive_coords_away["x"]:
            # Defender is on wrong side - invert x position in home orientation
            distance_from_bh = abs(defender_coords_home["x"] - offensive_coords_home["x"])
            if defender_coords_home["x"] < offensive_coords_home["x"]:
                # Currently left, move to right
                defender_coords_home["x"] = offensive_coords_home["x"] + distance_from_bh
            else:
                # Currently right, move to left
                defender_coords_home["x"] = offensive_coords_home["x"] - distance_from_bh
            # Re-flip to get correct away orientation result
            result = get_away_player_coords(defender_coords_home)
        else:
            # Defender is on correct side
            result = defender_coords_away
    else:
        # Return coords in home orientation (no flip needed)
        result = defender_coords_home

    # Dynamic MM S3: POSTURE-DRIVEN placement (tight/normal/loose), computed from man/ball/basket in the
    # SAME (input) orientation — aggression retired for the HCO path. posture None → the aggression base
    # above (every non-HCO caller: FB, rim-runner, tip-off — untouched). "normal" now ALSO routes here.
    if posture:
        result = _apply_defender_posture(
            result, offensive_coords, ball_handler_coords, is_ball_handler, spot, posture,
            is_away_offense)
    return result
