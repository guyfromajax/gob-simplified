"""Screen census — read-only, consumes NO RNG.

Wraps ``defender_placement.build_all_animations`` and measures, at the point AFTER the
full offense+defence build, everything Stage A would need to retarget a screener:

  * can the RECEIVER be derived at all (another offensive pos_action in the same step
    carrying the same ``location``)?
  * does a DEFENDER resolve for that receiver (man matchup / zone)?
  * where is the receiver HEADING (his next authored location after the screen step)?
  * how far is today's ``OFFSET_SPOTS`` screener coordinate from the receiver's defender,
    and is it on the defender's path or behind it?

The wrapper calls the original FIRST and only reads its inputs and its return value, so
the draw stream is untouched. Proved, not asserted: with SCREEN_CENSUS=1 the worker must
still reproduce the reference on fp AND draws.
"""
import math
from collections import Counter, defaultdict

_orig = None
S = {
    "calls": 0,
    "screens": 0,
    "receiver": Counter(),        # derivation outcome
    "defender": Counter(),        # defender resolution outcome
    "heading": Counter(),         # could we read where the receiver goes next
    "def_scheme": Counter(),
    "dist_screener_to_recv_def": Counter(),   # 0.5 buckets
    "dist_screener_to_recv": Counter(),
    "on_path": Counter(),
    "dist_screener_to_own_def": Counter(),   # staleness of the screener's OWN defender         # is today's screener coord between def and recv dest
    "samples": [],
    "no_recv_samples": [],
    # Stage A applier stats, accumulated from apply_screen_targeting's return value
    "stageA": {"screens": 0, "applied": 0,
               "fallback": Counter(), "displacement": Counter(), "calls": 0},
}


def _d(a, b):
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def _b(v, w=0.5):
    return round(round(float(v) / w) * w, 2)


def install():
    global _orig
    from BackEnd.engine import defender_placement as DP
    if _orig is not None:
        return
    _orig = DP.build_all_animations

    def wrapped(game, skeleton, off_lineup, def_lineup, add_defenders=True,
                is_fcp=False, is_hct=False):
        out = _orig(game, skeleton, off_lineup, def_lineup, add_defenders=add_defenders,
                    is_fcp=is_fcp, is_hct=is_hct)
        try:
            _measure(game, skeleton, off_lineup, def_lineup, out)
        except Exception as e:                       # census must never break a game
            S["receiver"]["CENSUS_ERROR:%s" % type(e).__name__] += 1
        return out

    DP.build_all_animations = wrapped
    _install_stage_a()
    # rebind the module-attribute copies: `from X import build_all_animations` takes a
    # reference, so patching DP alone under-counts (the import trap, 25-module census).
    import sys
    for mod in list(sys.modules.values()):
        if mod is None or mod is DP:
            continue
        if getattr(mod, "build_all_animations", None) is _orig:
            mod.build_all_animations = wrapped


def _install_stage_a():
    """Wrap the Stage A applier to accumulate its own returned stats. Read-only: the
    original is called first and only its return value is recorded."""
    import sys
    from BackEnd.utils import screen_targeting as ST
    if getattr(ST.apply_screen_targeting, "_census", False):
        return
    orig = ST.apply_screen_targeting

    def wrapped(*a, **kw):
        st = orig(*a, **kw)
        try:
            if st and st.get("enabled"):
                A = S["stageA"]
                A["calls"] += 1
                A["screens"] += st.get("screens", 0)
                A["applied"] += st.get("applied", 0)
                A["fallback"].update(st.get("fallback") or {})
                A["displacement"].update(st.get("displacement") or {})
        except Exception:
            pass
        return st

    wrapped._census = True
    ST.apply_screen_targeting = wrapped
    for mod in list(sys.modules.values()):
        if mod is None or mod is ST:
            continue
        if getattr(mod, "apply_screen_targeting", None) is orig:
            mod.apply_screen_targeting = wrapped


def _measure(game, skeleton, off_lineup, def_lineup, out):
    from BackEnd.engine.defender_placement import (
        defender_grid_from_animations, offense_grid_from_animations)
    from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
    from BackEnd.utils.defense_utils import is_zone_defense

    anims = (out[0] if isinstance(out, tuple) else out) or []
    zassign = (out[1] if isinstance(out, tuple) and len(out) > 1 else None) or {}
    steps = (skeleton or {}).get("steps") or []
    if not steps:
        return
    S["calls"] += 1

    n = len(steps)
    dgrid = defender_grid_from_animations(anims, def_lineup, n)
    ogrid = offense_grid_from_animations(anims, off_lineup, steps)

    gs = getattr(game, "game_state", {}) or {}
    call = gs.get("defense_playcall", "man")
    zone = bool(is_zone_defense(call))
    S["def_scheme"][("zone" if zone else "man")] += 1
    try:
        user_def = game.defense_team.team_id == game.user_team.team_id
    except Exception:
        user_def = False
    matchups = get_matchups_for_defending_team(gs, user_def)   # {def_pos: off_pos}
    guard_of = {v: k for k, v in (matchups or {}).items()}     # {off_pos: def_pos}

    for si, step in enumerate(steps):
        pas = step.get("pos_actions") or {}
        for spos, info in sorted(pas.items(), key=lambda kv: str(kv[0])):
            act = (info.get("action") or "").lower().strip()
            if act != "screen":
                continue
            S["screens"] += 1
            loc = info.get("location") or info.get("spot")
            if not loc:
                S["receiver"]["no_location_on_screener"] += 1
                continue

            # --- receiver derivation: same step, same authored location ---
            same = [p for p, i2 in sorted(pas.items(), key=lambda kv: str(kv[0]))
                    if p != spos and (i2.get("location") or i2.get("spot")) == loc]
            if len(same) == 1:
                recv, how = same[0], "unique_same_location"
            elif len(same) > 1:
                recv, how = same[0], "ambiguous_same_location(%d)" % len(same)
            else:
                recv, how = None, "none_same_location"
            S["receiver"][how] += 1
            if recv is None:
                if len(S["no_recv_samples"]) < 120:
                    S["no_recv_samples"].append({
                        "loc": loc, "screener": spos, "step": si,
                        "others": {p: (i2.get("location") or i2.get("spot"))
                                   for p, i2 in sorted(pas.items()) if p != spos},
                        "actions": {p: i2.get("action") for p, i2 in sorted(pas.items())},
                    })
                continue

            # --- where is the receiver heading (next authored location) ---
            dest = None
            for s2 in steps[si + 1:]:
                i2 = (s2.get("pos_actions") or {}).get(recv)
                if not i2:
                    continue
                l2 = i2.get("location") or i2.get("spot")
                if l2 and l2 != loc:
                    dest = l2
                    break
            S["heading"]["has_next_dest" if dest else "no_next_dest"] += 1

            # --- defender for the receiver ---
            # ZONE: the real guard map is zone_defender_assignments_by_step
            # ({step: {def_pos: off_player_id}}), NOT the man matchup dict.
            if zone:
                rpid = getattr(off_lineup.get(recv), "player_id", None)
                row = zassign.get(si) or zassign.get(str(si)) or {}
                dpos = next((dp for dp, opid in sorted(row.items(), key=lambda kv: str(kv[0]))
                             if opid and rpid and str(opid) == str(rpid)), None)
            else:
                dpos = guard_of.get(recv)
            dcoord = (dgrid.get(si) or {}).get(dpos) if dpos else None
            tag = "zone" if zone else "man"
            if dcoord:
                S["defender"][tag + "_resolved"] += 1
            elif not dpos:
                S["defender"][tag + "_unresolved_no_guard"] += 1
            else:
                S["defender"][tag + "_unresolved_no_coord"] += 1
            if not dcoord:
                continue

            scr_c = (ogrid.get(si) or {}).get(spos)
            recv_c = (ogrid.get(si) or {}).get(recv)
            if not scr_c or not recv_c:
                S["defender"]["offense_coord_missing"] += 1
                continue

            S["dist_screener_to_recv_def"][_b(_d(scr_c, dcoord))] += 1
            own = guard_of.get(spos) if not zone else None
            own_c = (dgrid.get(si) or {}).get(own) if own else None
            if own_c:
                S["dist_screener_to_own_def"][_b(_d(scr_c, own_c))] += 1
            S["dist_screener_to_recv"][_b(_d(scr_c, recv_c))] += 1

            # is today's screener coord between the defender and where the receiver goes?
            if dest:
                from BackEnd.constants import HCO_STRING_SPOTS
                dc = HCO_STRING_SPOTS.get(dest)
                if dc:
                    # projection of (screener-def) onto unit(dest-def)
                    vx, vy = dc["x"] - dcoord["x"], dc["y"] - dcoord["y"]
                    L = math.hypot(vx, vy)
                    if L > 1e-6:
                        t = ((scr_c["x"] - dcoord["x"]) * vx +
                             (scr_c["y"] - dcoord["y"]) * vy) / (L * L)
                        S["on_path"]["t" + str(_b(max(-1.0, min(2.0, t)), 0.25))] += 1
            if len(S["samples"]) < 400:
                S["samples"].append({
                    "step": si, "screener": spos, "receiver": recv, "loc": loc,
                    "dest": dest, "def": dpos, "zone": zone,
                    "scr": scr_c, "recv": recv_c, "dcoord": dcoord,
                })


def summary():
    def top(c, k=14):
        return dict(sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))[:k])
    return {
        "calls": S["calls"], "screens": S["screens"],
        "receiver": dict(S["receiver"]), "defender": dict(S["defender"]),
        "heading": dict(S["heading"]), "def_scheme": dict(S["def_scheme"]),
        "dist_screener_to_recv_def": dict(S["dist_screener_to_recv_def"]),
        "dist_screener_to_recv": dict(S["dist_screener_to_recv"]),
        "on_path": top(S["on_path"], 20),
        "dist_screener_to_own_def": dict(S["dist_screener_to_own_def"]),
        "samples": S["samples"][:25],
        "no_recv_samples": S["no_recv_samples"][:40],
        "stageA": {"calls": S["stageA"]["calls"], "screens": S["stageA"]["screens"],
                   "applied": S["stageA"]["applied"],
                   "fallback": dict(S["stageA"]["fallback"]),
                   "displacement": dict(S["stageA"]["displacement"])},
    }
