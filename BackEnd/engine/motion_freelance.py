"""
Dynamic HCO Motion — freelance movement emission (brief: Freelance Behavior).

Builds one freelance "beat": every offensive player independently either makes a
small subtle nudge (50%) or relocates to a nearby predefined spot within 9 grid
spots (50%). When the offense is sharp (off_efficiency + team_chemistry > 15) no
two players may land on the same spot; otherwise a collision is allowed and is
tagged for the front-end rattle effect (Phase 6).

This module emits the MOVEMENT only. The freelance shot loop (when the BH shoots
vs passes/holds) and its shot-clock termination are intentionally NOT wired yet —
that model is still open in the brief. See Dynamic_HCO_Motion_Implementation_Plan.md.

Coord-based skeleton step → existing UESS emitter stamps all required fields; the
BH keeps the ball via his ``handle_ball`` action.
"""
import math

from BackEnd.engine.motion_subtle import _coords_for, _radial_nudge, _X_MIN, _X_MAX, _Y_MIN, _Y_MAX

FREELANCE_RELOCATE_RADIUS = 9.0          # brief: "within 9 euclidean grid spots"
UNIQUE_LOCATION_THRESHOLD = 15           # off_eff + team_chem > this → no shared targets
FREELANCE_SUBTLE_PROB = 0.5              # else relocate
FREELANCE_MAX_CYCLES = 6                 # safety cap; forced shot on the last cycle (option A)
FREELANCE_PASS_PROB = 0.80               # else hold, when the BH doesn't shoot
FREELANCE_PASS_RADIUS = 20.0             # brief: pass to a teammate within 20 grid


def dist_xy(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def nearest_named_spot(coords, is_away_offense):
    """Nearest predefined spot to arbitrary freelance coords — used as shooter_location for shot resolution."""
    from BackEnd.constants import HCO_STRING_SPOTS
    from BackEnd.engine.attack_drive_clearance import _spot_display_coords
    best, best_d = "key", float("inf")
    for name in HCO_STRING_SPOTS:
        c = _spot_display_coords(name, is_away_offense)
        d = math.hypot(c["x"] - coords["x"], c["y"] - coords["y"])
        if d < best_d:
            best_d, best = d, name
    return best


def freelance_shoot_step(pos, coords, timestamp):
    """Coord-based shoot step (shoots from the freelance position → no teleport)."""
    return {"timestamp": timestamp,
            "pos_actions": {pos: {"coords": dict(coords), "action": "shoot"}},
            "events": [{"type": "shot"}]}


def _resolve_collisions(pos_actions, enforce_unique):
    """Offset any coincident players 2 grid apart in opposite directions (backend positional logic).

    Returns the list of collided position groups (for the FE rattle effect) — only populated when
    the team isn't sharp (enforce_unique False); sharp-team coincidences are separated silently.
    """
    from collections import defaultdict
    from BackEnd.engine.motion_subtle import _clamp, _X_MIN, _X_MAX

    groups = defaultdict(list)
    for pos, pa in pos_actions.items():
        c = pa["coords"]
        groups[(c["x"], c["y"])].append(pos)

    collisions = []
    for (cx, cy), group in groups.items():
        if len(group) < 2:
            continue
        if not enforce_unique:
            collisions.append(sorted(group))
        n = len(group)
        for idx, pos in enumerate(sorted(group)):
            off = round((idx - (n - 1) / 2.0) * 4.0, 1)   # 2 players → ±2 grid (opposite); symmetric for more
            nx = round(_clamp(cx + off, _X_MIN, _X_MAX), 1)
            pos_actions[pos]["coords"] = {"x": nx, "y": cy}
    return collisions


def freelance_pass_step(passer_pos, receiver_pos, passer_coords, receiver_coords, timestamp):
    """Coord-based pass/receive step — transfers the ball to the receiver via the emitter walk."""
    return {"timestamp": timestamp,
            "pos_actions": {
                passer_pos: {"coords": dict(passer_coords), "action": "pass"},
                receiver_pos: {"coords": dict(receiver_coords), "action": "receive"},
            },
            "events": []}


def _predefined_spots_within(xy, is_away_offense, radius=FREELANCE_RELOCATE_RADIUS):
    """Predefined (constants) spots whose display coords are within `radius` of xy, excluding xy's own spot."""
    from BackEnd.constants import HCO_STRING_SPOTS
    from BackEnd.engine.attack_drive_clearance import _spot_display_coords
    here = (round(xy["x"], 1), round(xy["y"], 1))
    out = []
    for name in HCO_STRING_SPOTS:
        c = _spot_display_coords(name, is_away_offense)
        cx, cy = round(c["x"], 1), round(c["y"], 1)
        if (cx, cy) == here:
            continue
        if math.hypot(cx - xy["x"], cy - xy["y"]) <= radius:
            out.append({"x": cx, "y": cy})
    return out


def build_freelance_beat(step, off_lineup, bh_pos, off_efficiency, team_chemistry, is_away_offense, rng):
    """
    One freelance movement beat (all five offensive players relocate/nudge), or None if the
    step can't support one. The BH keeps the ball (``handle_ball``); others ``cut``.
    Returns the step plus ``_freelance`` metadata (incl. any collision pairs for the FE).
    """
    from BackEnd.engine.attack_drive_clearance import _basket_display_coords

    pos_actions = step.get("pos_actions") or {}
    coords_by_pos = {}
    for pos in off_lineup:
        if not off_lineup.get(pos):
            continue
        info = pos_actions.get(pos)
        if info is None:
            continue
        coords_by_pos[pos] = _coords_for(info, is_away_offense)

    if bh_pos not in coords_by_pos:
        return None

    enforce_unique = (off_efficiency + team_chemistry) > UNIQUE_LOCATION_THRESHOLD
    basket = _basket_display_coords(is_away_offense)
    taken = set()
    new_pos_actions = {}

    for pos, xy in coords_by_pos.items():
        if rng.random() < FREELANCE_SUBTLE_PROB:
            target = _radial_nudge(xy, basket, toward=bool(rng.choice((0, 1))), amt=rng.randint(2, 5))
        else:
            cands = _predefined_spots_within(xy, is_away_offense)
            if enforce_unique:
                cands = [c for c in cands if (c["x"], c["y"]) not in taken]
            target = rng.choice(cands) if cands else {"x": round(xy["x"], 1), "y": round(xy["y"], 1)}
        taken.add((target["x"], target["y"]))
        new_pos_actions[pos] = {"coords": target, "action": "handle_ball" if pos == bh_pos else "cut"}

    # Backend collision resolution: two sprites must never share a coord (rendering requirement).
    # Coincident players are offset 2 grid apart in opposite directions HERE (positional logic stays
    # on the backend). The front end only plays the rattle animation for the tagged (non-sharp)
    # collisions — it computes no positions.
    collisions = _resolve_collisions(new_pos_actions, enforce_unique)

    return {
        "timestamp": step.get("timestamp", 0) + 150,
        "pos_actions": new_pos_actions,
        "events": [],
        "_freelance": {"bh_pos": bh_pos, "enforce_unique": enforce_unique, "collisions": collisions},
    }
