"""PART A: how often does build_all_animations fall back to court centre, for NON-shooters?

ONE arm, ONE seed, ONE process (arm-independence rule: a mongomock DB persists across runs
in the same interpreter, so sequential arms are not independent).

defender_placement.build_all_animations resolves each offensive pos_action three ways:

    :176  "coords" in pos_action      -> use them                          COORDS
    :180  "location" in pos_action    -> HCO_STRING_SPOTS[location]        LOCATION_OK
                                        ...or (50,25) if the name is unknown  LOCATION_MISS
    :196  neither                     -> (50,25) hardcoded                 ELSE

LOCATION_MISS and ELSE both land the player on the centre logo, but they are different
defects: one is an unhandled spot NAME, the other is a step that authored no position at
all. Counted separately throughout.

The classifier re-runs the branch conditions against the INPUT skeleton rather than
intercepting the middle of a 225-line function, then verifies itself against the coords the
function actually produced. Exact, because the conditions are plain key membership.
"""
import os, sys, json, math, random as _stdlib
from collections import Counter, defaultdict

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")
ARM, SEED, OUT = os.environ.get("ARM", "played"), int(os.environ["SEED"]), os.environ["OUT"]
# COUNTERFACTUAL (measurement only, never written to disk): when set, hand the build the
# `spot` name under the key it already reads, which is exactly what a real fix at
# defender_placement.py:176-197 would do. If the schema-path logo pile is downstream of this
# build, it must vanish. If it survives, a second independent converter is producing it.
SPOT_FIX = os.environ.get("SPOT_FIX") == "1"

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)
from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
import BackEnd.engine.defender_placement as DP
from BackEnd.constants import HCO_STRING_SPOTS, OFFSET_SPOTS

CENTRE = (50.0, 25.0)
CENTRE_BRANCHES = ("ELSE_SPOT_IGNORED", "ELSE_NOTHING_AUTHORED", "LOCATION_MISS", "SPOT_MISS")

BRANCH = Counter()              # branch -> count
BY_POS = Counter()              # (branch, shooter?, position) -> count
BY_ACTION = Counter()           # (branch, shooter?, action) -> count
BY_TURN = Counter()             # (branch, shooter?, offensive_state) -> count
DISPLACE = defaultdict(list)    # branch -> [jump_in_distance]
DISPLACE_OUT = defaultdict(list)
NEIGHBOUR_AUTHORED = Counter()  # was an adjacent step authored, i.e. is this a hole not a gap?
VERIFY = Counter()              # classifier agreed with produced coords?
TURNS_SEEN = Counter()
CENTRE_PLAYER_STEPS = Counter()  # distinct (turn, position) that hit centre at least once
EXAMPLES = []


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _classify(pos_action, action):
    """Which of the three branches this pos_action takes, and the coords it yields."""
    if "coords" in pos_action:
        c = pos_action.get("coords") or {}
        return "COORDS", (float(c.get("x", 50)), float(c.get("y", 25)))
    if "location" in pos_action or "spot" in pos_action:
        # Mirrors the FIXED dispatch. SPOT_ONLY is broken out so the previously
        # ignored population stays visible and can be verified against produced
        # coords, rather than merely vanishing from the report.
        spot_only = "location" not in pos_action
        location = pos_action.get("location") or pos_action.get("spot") or "key"
        if action in ("screen",):
            coords = OFFSET_SPOTS.get(location) or HCO_STRING_SPOTS.get(location)
        else:
            coords = HCO_STRING_SPOTS.get(location)
        if not coords:
            return ("SPOT_MISS" if spot_only else "LOCATION_MISS"), CENTRE
        xy = (float(coords.get("x", 50)), float(coords.get("y", 25)))
        return ("SPOT_OK" if spot_only else "LOCATION_OK"), xy
    return "ELSE_NOTHING_AUTHORED", CENTRE


def _install():
    orig = DP.build_all_animations

    def wrapped(game, skeleton, off_lineup, def_lineup, *a, **k):
        out = orig(game, skeleton, off_lineup, def_lineup, *a, **k)
        try:
            _measure(game, skeleton, off_lineup, out)
        except Exception as e:  # a probe must never change the run
            BRANCH[f"probe-error:{type(e).__name__}"] += 1
        return out

    DP.build_all_animations = wrapped
    # The Animator adapter imported the name directly, so patch that binding too.
    import BackEnd.models.animator as AN
    if getattr(AN, "build_all_animations", None) is not None:
        AN.build_all_animations = wrapped


def _measure(game, skeleton, off_lineup, out):
    gs = getattr(game, "game_state", {}) or {}
    turn_type = str(gs.get("offensive_state") or "?")
    steps = skeleton.get("steps") or []
    TURNS_SEEN[turn_type] += 1

    positions = sorted({p for s in steps for p in (s.get("pos_actions") or {}).keys()}, key=str)
    positions = [p for p in positions if off_lineup.get(p)]

    # The shooter is the position that shoots somewhere in THIS skeleton.
    shooters = {
        p for p in positions
        for s in steps
        if str(((s.get("pos_actions") or {}).get(p) or {}).get("action") or "") in ("shoot", "dunk")
    }

    # Coords the function actually produced, so the classifier can check itself.
    produced = {}
    anims = out[0] if isinstance(out, tuple) else out
    for row in (anims or []):
        pid = row.get("playerId") or row.get("player_id")
        for i, mv in enumerate(row.get("movement") or []):
            c = mv.get("coords") or {}
            if "x" in c:
                produced[(pid, i)] = (float(c["x"]), float(c["y"]))

    for position in positions:
        player = off_lineup.get(position)
        pid = getattr(player, "player_id", None)
        role = "SHOOTER" if position in shooters else "offball"

        # Per-position sequence of (step_idx, branch, coords, action).
        seq = []
        for step_idx, step in enumerate(steps):
            pa = (step.get("pos_actions") or {}).get(position)
            if not pa:
                continue
            action = str(pa.get("action", "drift"))
            branch, coords = _classify(pa, action)
            seq.append((step_idx, branch, coords, action))

        hit_centre = False
        for i, (step_idx, branch, coords, action) in enumerate(seq):
            BRANCH[branch] += 1
            BY_POS[(branch, role, position)] += 1
            BY_ACTION[(branch, role, action)] += 1
            BY_TURN[(branch, role, turn_type)] += 1

            got = produced.get((pid, i))
            if got is not None:
                # Only the two centre branches are verifiable this cheaply; the location and
                # coords branches get flipped downstream for away offense / opp handling.
                if branch in CENTRE_BRANCHES:
                    VERIFY["agree" if _dist(got, CENTRE) < 0.01 else "disagree"] += 1
                    if _dist(got, CENTRE) >= 0.01:
                        VERIFY[f"disagree-> {got[0]:.0f},{got[1]:.0f}"] += 1
                # POST-FIX acceptance: the previously ignored `spot` population must now
                # produce a REAL coord. The away-offense flip is x -> 100-x with y
                # preserved, so a resolved spot lands on the logo only if the spot IS the
                # logo; any other centre hit means the name did not resolve.
                if branch in ("SPOT_OK", "LOCATION_OK"):
                    spot_is_centre = _dist(coords, CENTRE) < 0.01
                    if _dist(got, CENTRE) < 0.01 and not spot_is_centre:
                        VERIFY[f"{branch}-LANDED-ON-LOGO-ANYWAY"] += 1
                    else:
                        VERIFY[f"{branch}-resolved-to-a-real-spot"] += 1

            if branch not in CENTRE_BRANCHES:
                continue
            hit_centre = True

            # (c) Displacement: the visible jump. Where was he on his previous authored
            # step, and where does he go next?
            prev_real = next((s for s in reversed(seq[:i]) if s[1] in ("COORDS", "LOCATION_OK", "SPOT_OK")), None)
            next_real = next((s for s in seq[i + 1:] if s[1] in ("COORDS", "LOCATION_OK", "SPOT_OK")), None)
            if prev_real:
                DISPLACE[branch].append(_dist(prev_real[2], coords))
            if next_real:
                DISPLACE_OUT[branch].append(_dist(coords, next_real[2]))
            NEIGHBOUR_AUTHORED[
                f"{branch}|prev={'yes' if prev_real else 'no'},next={'yes' if next_real else 'no'}"
            ] += 1

            if len(EXAMPLES) < 25:
                EXAMPLES.append({
                    "turn_type": turn_type, "position": position, "role": role,
                    "step": step_idx, "of": len(steps), "action": action, "branch": branch,
                    "location": (steps[step_idx].get("pos_actions") or {}).get(position, {}).get("location"),
                    "keys": sorted((steps[step_idx].get("pos_actions") or {}).get(position, {}).keys()),
                    "prev": prev_real[2] if prev_real else None,
                    "next": next_real[2] if next_real else None,
                    "jump_in": round(_dist(prev_real[2], coords), 1) if prev_real else None,
                })
        if hit_centre:
            CENTRE_PLAYER_STEPS[role] += 1


def _install_played():
    import BackEnd.models.animator as AN
    depth, flag = [0], {}
    for m in ("capture_fast_break_animation", "capture_free_throw_animation",
              "capture_halfcourt_animation", "skeleton_to_animations"):
        o = getattr(AN.Animator, m, None)
        if o is None:
            continue

        def mk(o=o):
            def w(self, *a, **k):
                gs = self.game.game_state
                if depth[0] == 0:
                    flag["had"] = "_is_full_simulation" in gs
                    flag["prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                depth[0] += 1
                try:
                    return o(self, *a, **k)
                finally:
                    depth[0] -= 1
                    if depth[0] == 0:
                        if flag["had"]:
                            gs["_is_full_simulation"] = flag["prev"]
                        else:
                            gs.pop("_is_full_simulation", None)
            return w
        setattr(AN.Animator, m, mk())


if __name__ == "__main__":
    if ARM == "played":
        _install_played()
    _install()

    sim_random.seed(SEED); training_random.seed(SEED); _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy(); gm.away_team.strategy_settings = d.copy()
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0x50000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"; break

    def summ(vals):
        if not vals:
            return None
        v = sorted(vals)
        return {"n": len(v), "median": round(v[len(v) // 2], 1),
                "p95": round(v[int(len(v) * 0.95) - 1], 1), "max": round(v[-1], 1),
                "mean": round(sum(v) / len(v), 1)}

    # Consumption census. build_all_animations feeding court-centre coords only matters
    # to Part B if those coords reach the renderer. Walk the turn payloads the client
    # actually receives and count centre-clustered offensive players in each.
    payload = Counter()
    for t in (gm.turns or []):
        steps_schema = t.get("animation_steps") or []
        legacy = t.get("animations") or []
        has_schema = bool(steps_schema)
        payload["turn|schema" if has_schema else "turn|legacy-or-none"] += 1
        if legacy:
            payload["turn|has_legacy_animations"] += 1
            centre_players = 0
            for row in legacy:
                if not isinstance(row, dict):
                    continue
                mv = row.get("movement") or []
                if any(isinstance(m, dict) and (m.get("coords") or {}).get("x") == 50
                       and (m.get("coords") or {}).get("y") == 25 for m in mv):
                    centre_players += 1
            if centre_players:
                payload[f"turn|legacy_centre_players>={min(centre_players,5)}"] += 1
                payload["CENTRE_REACHES_CLIENT_via_legacy"] += 1
                # THE decisive cell. The FE prefers animation_steps when present and only
                # falls back to the legacy animations list when it is absent, so a logo pile
                # is visible ONLY on turns with no schema steps.
                if has_schema:
                    payload["  legacy_centre BUT schema present (legacy unused)"] += 1
                else:
                    payload["  legacy_centre AND no schema -> RENDERS"] += 1
                    if centre_players >= 5:
                        payload["  ALL FIVE on the logo AND no schema -> RENDERS"] += 1
        if has_schema:
            # Schema path: how many DISTINCT players sit exactly on the logo in the SAME
            # step? One is ordinary mid-court traffic. Five is a defect pile. This is the
            # discriminator, because the raw instance count cannot tell them apart.
            hits = 0
            for st in steps_schema:
                for bucket in ("start", "end"):
                    coords = ((st.get(bucket) or {}).get("coords") or {})
                    if not isinstance(coords, dict):
                        continue
                    on_logo = {
                        pid for pid, c in coords.items()
                        if isinstance(c, dict) and c.get("x") == 50 and c.get("y") == 25
                    }
                    if on_logo:
                        hits += len(on_logo)
                        payload[f"schema_step|players_on_logo={min(len(on_logo), 6)}"] += 1
                    if coords:
                        payload["schema_step|coord_buckets_seen"] += 1
            if hits:
                payload["CENTRE_REACHES_CLIENT_via_schema"] += 1
                payload["schema_centre_coord_instances"] += hits

    json.dump({
        "arm": ARM, "seed": SEED, "spot_fix": SPOT_FIX, "error": err, "turns": len(gm.turns or []),
        "payload": dict(payload),
        "branch": dict(BRANCH),
        "by_pos": {f"{b}|{r}|{p}": n for (b, r, p), n in BY_POS.items()},
        "by_action": {f"{b}|{r}|{a}": n for (b, r, a), n in BY_ACTION.items()},
        "by_turn": {f"{b}|{r}|{t}": n for (b, r, t), n in BY_TURN.items()},
        "turns_seen": dict(TURNS_SEEN),
        "displace_in": {k: summ(v) for k, v in DISPLACE.items()},
        "displace_out": {k: summ(v) for k, v in DISPLACE_OUT.items()},
        "neighbour": dict(NEIGHBOUR_AUTHORED),
        "verify": dict(VERIFY),
        "centre_players": dict(CENTRE_PLAYER_STEPS),
        "examples": EXAMPLES,
    }, open(OUT, "w"))
