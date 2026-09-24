"""Phase 1 EXTENDED measurement probe — READ-ONLY, consumes no RNG.

Wraps ``collision_separation.apply_separation_to_animations``, snapshots every player's
coordinates BEFORE the pass and diffs them AFTER, so "who actually moved" is measured rather
than taken from the pass's own bookkeeping.

THE ITEM 22 INVARIANT is checked here directly: the shooter's coordinates must be byte-identical
before and after, at every step. A violation is counted and an example kept.
"""
import collections

S = {
    "calls": 0, "enabled_calls": 0, "all_calls": 0,
    "moved_players": collections.Counter(),      # role-class -> n placements moved
    "moved_amount": collections.Counter(),       # 0.1-grid buckets of actual displacement
    "shooter_violations": 0,
    "shooter_violation_examples": [],
    "ball_violations": 0,
    "stats": collections.Counter(),              # summed pass stats
    "moves": collections.Counter(),              # reported push magnitudes, 0.1 buckets
    "residual_by_class": collections.Counter(),
    "moved_by_class": collections.Counter(),
    "errors": 0,
}


def _snap(animations):
    out = {}
    for a in animations or []:
        pid = a.get("playerId")
        if pid is None:
            continue
        out[pid] = [dict(e.get("coords") or {}) for e in (a.get("movement") or [])
                    if isinstance(e, dict)]
    return out


def install():
    import sys
    from BackEnd.utils import collision_separation as CS
    if getattr(CS.apply_separation_to_animations, "_probe", False):
        return
    orig = CS.apply_separation_to_animations

    def wrapped(animations, game, def_lineup, off_lineup=None, skeleton=None):
        before = _snap(animations)
        st = orig(animations, game, def_lineup, off_lineup=off_lineup, skeleton=skeleton)
        try:
            _measure(before, animations, st, off_lineup, def_lineup, skeleton)
        except Exception:
            S["errors"] += 1
        return st

    wrapped._probe = True
    CS.apply_separation_to_animations = wrapped
    for mod in list(sys.modules.values()):
        if mod is None or mod is CS:
            continue
        if getattr(mod, "apply_separation_to_animations", None) is orig:
            mod.apply_separation_to_animations = wrapped


def _measure(before, animations, st, off_lineup, def_lineup, skeleton):
    import math
    from BackEnd.utils.collision_separation import shooter_positions
    S["calls"] += 1
    if not st or not st.get("enabled"):
        return
    S["enabled_calls"] += 1
    if st.get("all_enabled"):
        S["all_calls"] += 1
    for k, v in st.items():
        if isinstance(v, int):
            S["stats"][k] += v
    for m in st.get("moves") or []:
        S["moves"][round(round(float(m) / 0.1) * 0.1, 2)] += 1
    for k, v in (st.get("residual_by_class") or {}).items():
        S["residual_by_class"][k] += v
    for k, v in (st.get("moved_by_class") or {}).items():
        S["moved_by_class"][k] += v

    off_pid = {getattr(p, "player_id", None): pos for pos, p in (off_lineup or {}).items()}
    def_pid = {getattr(p, "player_id", None): pos for pos, p in (def_lineup or {}).items()}
    shooters = shooter_positions(skeleton)

    after = _snap(animations)
    for pid, rows in after.items():
        prev = before.get(pid) or []
        for i, c in enumerate(rows):
            if i >= len(prev) or not c or not prev[i]:
                continue
            d = math.hypot(float(c.get("x", 0)) - float(prev[i].get("x", 0)),
                           float(c.get("y", 0)) - float(prev[i].get("y", 0)))
            if d < 1e-9:
                continue
            if pid in off_pid:
                pos = off_pid[pid]
                S["moved_players"]["offence"] += 1
                if pos in shooters:
                    S["shooter_violations"] += 1
                    if len(S["shooter_violation_examples"]) < 5:
                        S["shooter_violation_examples"].append(
                            {"pos": pos, "step": i, "before": prev[i], "after": c})
            elif pid in def_pid:
                S["moved_players"]["defence"] += 1
            else:
                S["moved_players"]["unknown"] += 1
            S["moved_amount"][round(round(d / 0.1) * 0.1, 2)] += 1


def summary():
    return {
        "calls": S["calls"], "enabled_calls": S["enabled_calls"], "all_calls": S["all_calls"],
        "errors": S["errors"],
        "moved_players": dict(S["moved_players"]),
        "moved_amount": dict(S["moved_amount"]),
        "SHOOTER_VIOLATIONS": S["shooter_violations"],
        "shooter_violation_examples": S["shooter_violation_examples"],
        "stats": dict(S["stats"]),
        "moves": dict(S["moves"]),
        "residual_by_class": dict(S["residual_by_class"]),
        "moved_by_class": dict(S["moved_by_class"]),
    }
