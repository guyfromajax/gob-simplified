"""
Dynamic HCO Motion — subtle movement emission (brief: Subtle Movement).

Builds a single off-pattern "beat" skeleton step: the ball handler nudges off the
predefined motion pattern and (when he does) zero or more non-ball-handlers make
small category-appropriate relocations; everyone else holds. The dynamic resolver
inserts this beat between skeleton steps, and the next skeleton step pulls players
back to their defined spots (brief: "he'll go to his spot defined in that step").
That skeleton-resume also provides the "pop back" for hard-step-inward moves.

The beat is a normal coord-based skeleton step → the existing UESS emitter stamps
every required field. The ball stays with the BH via his ``handle_ball`` action
(skeleton_step_emitter._walk_ball_owners). Coords are display-space.

Scope: positional micro-moves only. Which non-BH players relocate is gated by a per-teammate
attribute read (see ``build_subtle_beat``); the specific move category is still chosen at
random within what's applicable to each player's location. DEFERRED — the two ball-transfer non-BH
variants ("flash to receive a quick pass and shoot" and "cut to the basket and
receive a pass from the BH"): those transfer possession / can terminate in a shot,
so they belong with the hot-read/decision machinery, not the positional beat.
"""
import math

# Off-pattern coord clamps (display space).
_X_MIN, _X_MAX = 2.0, 98.0
_Y_MIN, _Y_MAX = 2.0, 48.0

# Ball-handler radial moves (side-dribble is added dynamically when eligible).
BH_SUBTLE_MOVES = ("in_place", "back", "in")
# Subtle movers render at the standard HCO skeleton pace (cruise). The emitter reads this
# explicit archetype off the pos_action.
SUBTLE_ARCHETYPE = "cruise"
# Inside "flash" targets (brief: lowPost players flash to midLane / a midPost / a highPost).
_INSIDE_FLASH_BASE = ("midLane",)


def _norm(loc):
    return (loc or "").strip().lower()


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _coords_for(info, is_away_offense):
    from BackEnd.engine.attack_drive_clearance import _spot_display_coords
    if info and info.get("coords"):
        return {"x": float(info["coords"]["x"]), "y": float(info["coords"]["y"])}
    c = _spot_display_coords((info or {}).get("location") or "key", is_away_offense)
    return {"x": float(c["x"]), "y": float(c["y"])}


def _radial_nudge(xy, basket, toward, amt):
    """Move ``amt`` grid spots toward (or away from) the basket along the radial line."""
    dx, dy = xy["x"] - basket["x"], xy["y"] - basket["y"]
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist          # unit vector AWAY from the basket
    if toward:
        ux, uy = -ux, -uy
    return {"x": round(_clamp(xy["x"] + ux * amt, _X_MIN, _X_MAX), 1),
            "y": round(_clamp(xy["y"] + uy * amt, _Y_MIN, _Y_MAX), 1)}


def _bh_radial_target(bh_xy, move, is_away_offense, rng):
    if move == "in_place":
        return {"x": round(bh_xy["x"], 1), "y": round(bh_xy["y"], 1)}
    from BackEnd.engine.attack_drive_clearance import _basket_display_coords
    return _radial_nudge(bh_xy, _basket_display_coords(is_away_offense), toward=(move == "in"), amt=rng.randint(2, 5))


def _bh_subtle(loc, bh_xy, occupied, is_away_offense, rng):
    """Pick the BH's subtle move. Side-dribble only when at a perimeter spot with a free neighbor."""
    from BackEnd.engine.attack_drive_clearance import _is_perimeter_spot, _tangential_targets, _spot_display_coords

    side_cands = []
    if _is_perimeter_spot(loc):
        side_cands = [t for t in _tangential_targets(loc) if _norm(t) not in occupied]

    available = list(BH_SUBTLE_MOVES) + (["side"] if side_cands else [])
    move = rng.choice(available)
    if move == "side":
        # Dribble halfway toward an unoccupied bordering perimeter spot (stays outside).
        tgt = _spot_display_coords(rng.choice(side_cands), is_away_offense)
        return ({"x": round((bh_xy["x"] + tgt["x"]) / 2, 1),
                 "y": round((bh_xy["y"] + tgt["y"]) / 2, 1)}, "side")
    return (_bh_radial_target(bh_xy, move, is_away_offense, rng), move)


def _inside_flash_target(loc, occupied, rng):
    """A free inside target (midLane / midPost / highPost), same vertical half when the player has one."""
    from BackEnd.engine.attack_drive_clearance import _vertical_half
    half = _vertical_half(loc)
    targets = list(_INSIDE_FLASH_BASE)
    halves = [half] if half in ("upper", "lower") else ["upper", "lower"]
    for h in halves:
        targets += [f"{h} midPost", f"{h} highPost"]
    targets = [t for t in targets if _norm(t) not in occupied and _norm(t) != _norm(loc)]
    return rng.choice(targets) if targets else None


def _non_bh_target(loc, xy, occupied, is_away_offense, rng):
    """A category-appropriate positional micro-move target for a non-BH player (display coords)."""
    from BackEnd.engine.attack_drive_clearance import (
        _is_perimeter_spot, _tangential_targets, _spot_display_coords, _basket_display_coords,
    )
    from BackEnd.engine.motion_read_map import is_inside_location

    basket = _basket_display_coords(is_away_offense)

    if is_inside_location(loc):
        # Inside player: flash to an inside target, or slide outward (toward perimeter).
        if rng.choice((0, 1)) == 0:
            tgt = _inside_flash_target(loc, occupied, rng)
            if tgt:
                c = _spot_display_coords(tgt, is_away_offense)
                return {"x": round(c["x"], 1), "y": round(c["y"], 1)}
        return _radial_nudge(xy, basket, toward=False, amt=rng.randint(2, 5))

    if _is_perimeter_spot(loc):
        # Outside player: slide to an adjacent open perimeter spot, or hard-step inward
        # (the skeleton resume "pops" him back to his defined spot next step).
        if rng.choice((0, 1)) == 0:
            cands = [t for t in _tangential_targets(loc) if _norm(t) not in occupied]
            if cands:
                c = _spot_display_coords(rng.choice(cands), is_away_offense)
                return {"x": round(c["x"], 1), "y": round(c["y"], 1)}
        return _radial_nudge(xy, basket, toward=True, amt=rng.randint(2, 5))

    # Anywhere else: a small radial nudge off pattern.
    return _radial_nudge(xy, basket, toward=False, amt=rng.randint(2, 5))


def build_subtle_beat(step, off_lineup, bh_pos, is_away_offense, rng, off_eff=0, altered_moves=None):
    """
    Build a coord-based subtle-movement beat (BH nudges off pattern; some non-BH relocate;
    the rest hold), or None if the step can't support one. Carries explicit display coords
    for all five offensive players; the BH keeps the ball via its ``handle_ball`` action.

    Each non-BH teammate makes his own read — ``(player_read_raw + off_eff) * d6`` — and only
    relocates (when a move is applicable) if it clears ``MOTION_READ_THRESHOLD`` (brief: Updated
    Subtle Movement Logic; replaces the old flat 50% coin flip). The BH always moves (he chose
    the subtle movement). ``off_eff`` = offense team offensive_efficiency.

    ``altered_moves`` (S3 altered actions): ``{pos: {"coords", "location"}}`` — when provided, the
    RANDOM per-teammate relocation is REPLACED: listed non-BH players move to their given target
    (action ``"cut"``), everyone else holds. The caller (the walk) decides the moves via the
    altered-action trigger/selection; the BH still nudges. None → legacy random-relocation behavior.
    """
    from BackEnd.utils.shared import player_read_raw
    from BackEnd.engine.motion_step_decision import MOTION_READ_THRESHOLD

    pos_actions = step.get("pos_actions") or {}
    coords_by_pos, loc_by_pos = {}, {}
    for pos in off_lineup:
        if not off_lineup.get(pos):
            continue
        info = pos_actions.get(pos)
        if info is None:
            continue
        coords_by_pos[pos] = _coords_for(info, is_away_offense)
        loc_by_pos[pos] = info.get("location") or ""

    if bh_pos not in coords_by_pos:
        return None

    bh_occupied = {_norm(l) for p, l in loc_by_pos.items() if p != bh_pos and l}
    bh_target, bh_move = _bh_subtle(loc_by_pos.get(bh_pos, ""), coords_by_pos[bh_pos],
                                    bh_occupied, is_away_offense, rng)

    new_pos_actions = {bh_pos: {"coords": bh_target, "action": "handle_ball", "archetype": SUBTLE_ARCHETYPE}}
    movers = [bh_pos]
    for pos, xy in coords_by_pos.items():
        if pos == bh_pos:
            continue
        moved = False
        if altered_moves is not None:
            # S3: non-BH players do their SELECTED altered action (or hold) — no random relocation.
            mv = altered_moves.get(pos)
            if mv and mv.get("coords"):
                new_pos_actions[pos] = {"coords": mv["coords"], "location": mv.get("location"),
                                        "action": mv.get("action", "cut"), "archetype": SUBTLE_ARCHETYPE}
                movers.append(pos)
                moved = True
        else:
            # Legacy: per-teammate read → random relocation. Smart players almost always make the
            # (correct) read; the d6 makes weaker readers hit-and-miss (brief G2).
            read = (player_read_raw(off_lineup.get(pos)) + off_eff) * rng.randint(1, 6)
            if read > MOTION_READ_THRESHOLD:
                occupied = {_norm(l) for q, l in loc_by_pos.items() if q != pos and l}
                target = _non_bh_target(loc_by_pos.get(pos, ""), xy, occupied, is_away_offense, rng)
                if target:
                    new_pos_actions[pos] = {"coords": target, "action": "cut", "archetype": SUBTLE_ARCHETYPE}
                    movers.append(pos)
                    moved = True
        if not moved:
            new_pos_actions[pos] = {"coords": {"x": round(xy["x"], 1), "y": round(xy["y"], 1)},
                                    "action": "stationary"}

    return {
        "timestamp": step.get("timestamp", 0) + 150,
        "pos_actions": new_pos_actions,
        "events": [],
        "_subtle_movement": {"bh_pos": bh_pos, "bh_move": bh_move, "movers": movers},
    }
