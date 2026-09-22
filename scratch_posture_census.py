"""Off-ball man-posture census — read-only, consumes NO RNG.

Wraps ``shared_defense._apply_defender_posture`` (the one place every HCO man placement
passes through: shared_defense.py:2218-2221) and records, per posture, the geometry
complaint #3 is about: how far the help defender ends up from his man, from the ball and
from the rim, and how much of the movement is along the man->ball axis vs the man->rim
axis.

The wrapper calls the original FIRST and only measures its inputs and its return value, so
the draw stream is untouched. That is proved, not asserted: with EQUIV_MAN_POSTURE unset
the worker must still reproduce the current reference 40/40 on fp AND draws.

Distributions are kept as Counters of rounded values (0.1 grid) rather than raw lists:
exact enough for p50/p90 at 0.1 resolution, and flat in memory over a 40-game run.
"""
import math
from collections import Counter, defaultdict

from BackEnd.constants import AWAY_RIM_COORDS, HOME_RIM_COORDS

BUCKET = 0.1          # quantile resolution, in grid units
SAMPLE_CAP = 4000     # full records kept per posture, for the pictures


def _new_bucket():
    return {
        "calls": 0,
        "inside_lock": 0,          # o_spot in _POSTURE_INSIDE_SPOTS -> posture ignored
        "anchor_floor_x": 0,       # HELP_ANCHOR_FLOOR is what set wx
        "anchor_floor_y": 0,
        "anchor_floor_either": 0,
        "anchor_floor_both": 0,
        "gap_to_man": Counter(),
        "dist_to_ball": Counter(),
        "dist_to_rim": Counter(),
        "sag_ball_axis": Counter(),   # component of (def-man) along unit(ball-man)
        "sag_rim_axis": Counter(),    # component of (def-man) along unit(rim-man)
        "lane_offset": Counter(),     # distance from the man->ball segment (deny check)
        "man_dist_to_rim": Counter(),  # the MAN's own rim distance (the help defender's yardstick)
        "man_dist_to_ball": Counter(),
        "strongness": Counter(),       # the zone shade's own ramp, reused here as a yardstick
        # gap to man and defender rim distance, split by the SAME strong/weak ramp the zone
        # help shade uses, so "does man read ball side?" is answered on the zone's terms.
        "gap_by_side": {"strong": Counter(), "middle": Counter(), "weak": Counter()},
        "defrim_by_side": {"strong": Counter(), "middle": Counter(), "weak": Counter()},
        "manrim_by_side": {"strong": Counter(), "middle": Counter(), "weak": Counter()},
        "in_lane": 0,                 # lane_offset <= 1.0 AND between man and ball
        "samples": [],
    }


CENSUS = defaultdict(_new_bucket)
STATE = {"seed": None, "errors": 0, "installed": False}


def reset(seed=None):
    CENSUS.clear()
    STATE["seed"] = seed
    STATE["errors"] = 0


def _q(counter, frac):
    """Quantile from a Counter of rounded values. Returns None when empty."""
    n = sum(counter.values())
    if not n:
        return None
    target = frac * n
    seen = 0
    for v in sorted(counter):
        seen += counter[v]
        if seen >= target:
            return v
    return max(counter)


def _mean(counter):
    n = sum(counter.values())
    if not n:
        return None
    return sum(v * c for v, c in counter.items()) / float(n)


def stats(counter):
    return {"n": sum(counter.values()), "mean": _mean(counter),
            "p50": _q(counter, 0.50), "p90": _q(counter, 0.90)}


def _record(out, off_coords, ball_coords, o_spot, posture, is_away_offense, inside_lock):
    import BackEnd.utils.shared_defense as SD

    b = CENSUS[str(posture)]
    b["calls"] += 1
    if inside_lock:
        b["inside_lock"] += 1
        return

    ox, oy = float(off_coords["x"]), float(off_coords["y"])
    dx, dy = float(out["x"]), float(out["y"])
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    rx, ry = float(rim["x"]), float(rim["y"])
    if ball_coords:
        bx, by = float(ball_coords["x"]), float(ball_coords["y"])
    else:
        bx, by = rx, ry

    vx, vy = dx - ox, dy - oy
    b["gap_to_man"][round(math.hypot(vx, vy) / BUCKET) * BUCKET] += 1
    b["dist_to_ball"][round(math.hypot(dx - bx, dy - by) / BUCKET) * BUCKET] += 1
    b["dist_to_rim"][round(math.hypot(dx - rx, dy - ry) / BUCKET) * BUCKET] += 1

    lb = math.hypot(bx - ox, by - oy)
    if lb:
        b["sag_ball_axis"][round((vx * (bx - ox) + vy * (by - oy)) / lb / BUCKET) * BUCKET] += 1
    lr = math.hypot(rx - ox, ry - oy)
    if lr:
        b["sag_rim_axis"][round((vx * (rx - ox) + vy * (ry - oy)) / lr / BUCKET) * BUCKET] += 1

    # deny: is he actually in the passing lane between his man and the ball?
    if lb:
        t = (vx * (bx - ox) + vy * (by - oy)) / (lb * lb)
        px, py = ox + t * (bx - ox), oy + t * (by - oy)
        off_lane = math.hypot(dx - px, dy - py)
        b["lane_offset"][round(off_lane / BUCKET) * BUCKET] += 1
        if off_lane <= 1.0 and 0.0 <= t <= 1.0:
            b["in_lane"] += 1

    # strong/weak side, on the zone help shade's own ramp (zone_sink.SIDE_SPAN +
    # ball_centrality): 1.0 = strong side / central ball, 0.0 = far weak side.
    import BackEnd.utils.zone_sink as _zs
    strongness = 1.0 - min(1.0, abs(by - oy) / _zs.SIDE_SPAN)
    strongness += (1.0 - strongness) * _zs.ball_centrality(by)
    side = "strong" if strongness >= 0.66 else ("weak" if strongness < 0.33 else "middle")
    b["strongness"][round(strongness / 0.05) * 0.05] += 1
    gap = math.hypot(vx, vy)
    man_rim = math.hypot(ox - rx, oy - ry)
    b["man_dist_to_rim"][round(man_rim / BUCKET) * BUCKET] += 1
    b["man_dist_to_ball"][round(math.hypot(ox - bx, oy - by) / BUCKET) * BUCKET] += 1
    b["gap_by_side"][side][round(gap / BUCKET) * BUCKET] += 1
    b["defrim_by_side"][side][round(math.hypot(dx - rx, dy - ry) / BUCKET) * BUCKET] += 1
    b["manrim_by_side"][side][round(man_rim / BUCKET) * BUCKET] += 1

    # which anchor dimension was pinned by HELP_ANCHOR_FLOOR (shared_defense.py:2085-2086)
    if posture in ("normal", "loose"):
        off_x, off_y = abs(ox - rx), abs(oy - ry)
        m = max(off_x, off_y) or 1.0
        fx = (off_x / m) < SD.HELP_ANCHOR_FLOOR
        fy = (off_y / m) < SD.HELP_ANCHOR_FLOOR
        b["anchor_floor_x"] += 1 if fx else 0
        b["anchor_floor_y"] += 1 if fy else 0
        b["anchor_floor_either"] += 1 if (fx or fy) else 0
        b["anchor_floor_both"] += 1 if (fx and fy) else 0

    if len(b["samples"]) < SAMPLE_CAP:
        b["samples"].append({
            "seed": STATE["seed"], "o_spot": o_spot, "away": bool(is_away_offense),
            "man": [ox, oy], "def": [dx, dy], "ball": [bx, by], "rim": [rx, ry],
            "gap": round(math.hypot(vx, vy), 3),
        })


def install():
    """Wrap the posture entry point. Idempotent."""
    if STATE["installed"]:
        return
    import BackEnd.utils.shared_defense as SD

    orig = SD._apply_defender_posture
    inside = SD._POSTURE_INSIDE_SPOTS

    def wrapped(def_coords, off_coords, ball_coords, is_ball_handler, o_spot,
                posture, is_away_offense):
        out = orig(def_coords, off_coords, ball_coords, is_ball_handler, o_spot,
                   posture, is_away_offense)
        if not is_ball_handler:
            try:
                _record(out, off_coords, ball_coords, o_spot, posture, is_away_offense,
                        (o_spot or "").strip().lower() in inside)
            except Exception:       # never let the census break a run
                STATE["errors"] += 1
        return out

    SD._apply_defender_posture = wrapped
    STATE["installed"] = True


def summary():
    out = {"errors": STATE["errors"], "by_posture": {}}
    for posture, b in CENSUS.items():
        out["by_posture"][posture] = {
            "calls": b["calls"],
            "inside_lock": b["inside_lock"],
            "gap_to_man": stats(b["gap_to_man"]),
            "dist_to_ball": stats(b["dist_to_ball"]),
            "dist_to_rim": stats(b["dist_to_rim"]),
            "sag_ball_axis": stats(b["sag_ball_axis"]),
            "sag_rim_axis": stats(b["sag_rim_axis"]),
            "lane_offset": stats(b["lane_offset"]),
            "in_lane": b["in_lane"],
            "anchor_floor_x": b["anchor_floor_x"],
            "anchor_floor_y": b["anchor_floor_y"],
            "anchor_floor_either": b["anchor_floor_either"],
            "anchor_floor_both": b["anchor_floor_both"],
        }
    return out


_DISTS = ("gap_to_man", "dist_to_ball", "dist_to_rim", "sag_ball_axis",
          "sag_rim_axis", "lane_offset", "man_dist_to_rim", "man_dist_to_ball",
          "strongness")
_SPLITS = ("gap_by_side", "defrim_by_side", "manrim_by_side")


def raw():
    """The Counters themselves, so several games can be POOLED before quantiles are
    taken. Per-game p50/p90 averaged across games is not the pooled p50/p90."""
    out = {}
    for posture, b in CENSUS.items():
        out[posture] = {
            "counts": {k: b[k] for k in ("calls", "inside_lock", "in_lane",
                                         "anchor_floor_x", "anchor_floor_y",
                                         "anchor_floor_either", "anchor_floor_both")},
            "dists": {k: {("%.2f" % v): c for v, c in b[k].items()} for k in _DISTS},
            "splits": {k: {side: {("%.2f" % v): c for v, c in cc.items()}
                           for side, cc in b[k].items()} for k in _SPLITS},
        }
    return out


def samples(posture):
    return CENSUS[str(posture)]["samples"]
