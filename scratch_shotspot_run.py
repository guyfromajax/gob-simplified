"""shot_spot / 2PT-3PT classification probe. ONE arm, ONE seed, ONE process.

Process isolation is mandatory (see bugs.md arm-independence entry): arms run back-to-back
in one process are not independent. Everything here that matters is measured WITHIN a single
arm and within a single turn, so it is immune to that contamination anyway, but the harness
keeps the isolation so the cross-arm rates are also usable.

Four questions:
  (a) per arm, shot_spot provenance and the resulting 2PT/3PT classification
  (b) how often the two CANDIDATE spots classify a shot DIFFERENTLY (arc-side flip), not
      merely how often their coordinates differ
  (c) the classification channel's contribution to the MAKE gap, vs defender placement
  (d) whether the PLAYED arm ALONE can misclassify -- i.e. whether the coord the shot was
      SCORED from lands on a different side of the arc than the coord the client is finally
      RENDERED. That is a live scoreboard error, not an equivalence problem.

Invoked as: ARM=sim|played SEED=8000 OUT=path python scratch_shotspot_run.py
"""
import os, sys, json, math, random as _stdlib
from collections import Counter, defaultdict

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")

ARM, SEED, OUT = os.environ["ARM"], int(os.environ["SEED"]), os.environ["OUT"]

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
from BackEnd.utils.shot_geometry import is_three_point_shot_from_coords
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.shared import get_away_player_coords
import BackEnd.engine.phase_resolution as PR
import BackEnd.engine.skeleton_step_emitter as EMIT
import BackEnd.models.shot_manager as SM

GATED = ("capture_fast_break_animation", "capture_free_throw_animation",
         "capture_halfcourt_animation", "skeleton_to_animations")
DEPTH, _FLAG = [0], {}

CAND = []          # (b): both candidate spots per shot
SCORED = {}        # (d): turn_idx -> coord the shot was scored from
RENDER = defaultdict(list)   # (d): turn_idx -> [emitter shoot-step coords, in call order]
SYNC = Counter()   # (a): provenance


def _away(game):
    return game.offense_team.team_id == game.away_team.team_id


def _is3(game, c):
    return is_three_point_shot_from_coords(c, is_away_offense=_away(game)) if c else None


def _skeleton_candidate(game, skeleton, roles):
    """READ-ONLY replica of set_shooter_coords_from_skeleton_last_step's coord choice
    (phase_resolution.py:4327-4418). Mirrors it exactly -- scan backwards for the shooter's
    'shoot' pos_action, prefer explicit display-oriented coords, else the named-spot lookup
    with the away mirror -- but writes nothing."""
    try:
        steps = (skeleton or {}).get("steps") or []
        shooter_pos = roles.get("shooter_pos")
        if not steps or shooter_pos is None:
            return None
        pa = None
        for i in range(len(steps) - 1, -1, -1):
            a = (steps[i].get("pos_actions") or {}).get(shooter_pos)
            if a and (a.get("action") or "").lower().strip() == "shoot":
                pa = a
                break
        if not pa:
            return None
        ec = pa.get("coords")
        if isinstance(ec, dict) and ec.get("x") is not None and ec.get("y") is not None:
            return {"x": float(ec["x"]), "y": float(ec["y"])}
        loc = (pa.get("location") or pa.get("spot") or "key").strip()
        c = HCO_STRING_SPOTS.get(loc, {"x": 50, "y": 25})
        if c == {"x": 50, "y": 25} and loc.lower() != "key":
            for k, v in HCO_STRING_SPOTS.items():
                if k.lower() == loc.lower():
                    c = v
                    break
        return get_away_player_coords(c) if _away(game) else dict(c)
    except Exception:
        return None


def _shoot_coord(steps, shooter_id):
    """Same extraction the sync uses: the step whose start.action marks the shooter
    'shoot', else the last step; take that step's END coord for the shooter."""
    if not steps:
        return None
    sid = str(shooter_id)
    step = None
    for st in steps:
        act = (st.get("start") or {}).get("action") or {}
        v = act.get(shooter_id) or act.get(sid)
        if isinstance(v, str) and v.lower().strip() == "shoot":
            step = st
            break
    if step is None:
        step = steps[-1]
    coords = (step.get("end") or {}).get("coords") or {}
    c = coords.get(shooter_id) or {str(k): v for k, v in coords.items()}.get(sid)
    if isinstance(c, dict) and c.get("x") is not None and c.get("y") is not None:
        return {"x": float(c["x"]), "y": float(c["y"])}
    return None


def _install(game_ref):
    orig_sync = PR._uess_sync_emitted_shot_coords

    def sync(game, skeleton, animations, roles, turn_type="HCO"):
        emit = orig_sync(game, skeleton, animations, roles, turn_type)
        SYNC["emitter" if emit is not None else "skeleton_fallback"] += 1
        skel = _skeleton_candidate(game, skeleton, roles)
        if emit and skel:
            e3, s3 = _is3(game, emit), _is3(game, skel)
            CAND.append({"emit": emit, "skel": skel, "emit_is3": e3, "skel_is3": s3,
                         "flip": bool(e3 != s3),
                         "dist": math.hypot(emit["x"] - skel["x"], emit["y"] - skel["y"])})
        return emit
    PR._uess_sync_emitted_shot_coords = sync

    # (d) the coord the shot was actually SCORED from
    orig_resolve = SM.ShotManager.resolve_shot

    def resolve_shot(self, roles, *a, **k):
        g = self.game
        ti = len(getattr(g, "turns", None) or [])
        sp = roles.get("shot_spot") if isinstance(roles, dict) else None
        sh = roles.get("shooter") if isinstance(roles, dict) else None
        if isinstance(sp, dict) and sp.get("x") is not None:
            SCORED[ti] = {"coord": dict(sp), "is3": _is3(g, sp),
                          "shooter": getattr(sh, "player_id", None),
                          "state": g.game_state.get("offensive_state")}
        return orig_resolve(self, roles, *a, **k)
    SM.ShotManager.resolve_shot = resolve_shot

    # (d) every emitter build, in call order, per turn. Patching the emitter MODULE attr
    # catches both call sites: phase_resolution:4279 and turn_manager:3981 both import the
    # name INSIDE the function, so they resolve the patched attribute at call time.
    orig_build = EMIT.build_skeleton_animation_steps

    def build(turn_result, game, *a, **k):
        steps = orig_build(turn_result, game, *a, **k)
        try:
            # Identify the shooter FROM THE STEPS, not from turn_result["roles"] -- the
            # client-facing call at turn_manager.py:3983 passes ``result``, which carries no
            # roles, so keying off roles silently dropped every final render.
            hit = None
            for st in (steps or []):
                act = (st.get("start") or {}).get("action") or {}
                for pid, v in act.items():
                    if isinstance(v, str) and v.lower().strip() == "shoot":
                        c = ((st.get("end") or {}).get("coords") or {}).get(pid)
                        if isinstance(c, dict) and c.get("x") is not None:
                            hit = (str(pid), {"x": float(c["x"]), "y": float(c["y"])})
                        break
                if hit:
                    break
            if hit:
                sid, c = hit
                RENDER[len(getattr(game, "turns", None) or [])].append(
                    {"coord": c, "is3": _is3(game, c), "shooter": sid,
                     "has_result_type": bool((turn_result or {}).get("result_type")),
                     "n_steps": len(steps or [])})
        except Exception:
            pass
        return steps
    EMIT.build_skeleton_animation_steps = build


def _install_played():
    import BackEnd.models.animator as AN
    for m in GATED:
        o = getattr(AN.Animator, m)

        def mk(o=o):
            def w(self, *a, **k):
                gs = self.game.game_state
                if DEPTH[0] == 0:
                    _FLAG["had"] = "_is_full_simulation" in gs
                    _FLAG["prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                DEPTH[0] += 1
                try:
                    return o(self, *a, **k)
                finally:
                    DEPTH[0] -= 1
                    if DEPTH[0] == 0:
                        if _FLAG["had"]:
                            gs["_is_full_simulation"] = _FLAG["prev"]
                        else:
                            gs.pop("_is_full_simulation", None)
            return w
        setattr(AN.Animator, m, mk())


if __name__ == "__main__":
    if ARM == "played":
        _install_played()
    sim_random.seed(SEED); training_random.seed(SEED); _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy(); gm.away_team.strategy_settings = d.copy()
    _install(gm)
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0xE0000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            break

    # (a)+(c) straight off the turn records -- _stamp_shot_classification wrote these.
    cls = Counter()
    src = Counter()
    for t in (gm.turns or []):
        rtv = str(t.get("result_type") or "").upper()
        if rtv not in ("MAKE", "MISS", "BLOCK"):
            continue
        if "is_three_point_shot" not in t:
            cls[(rtv, "unstamped")] += 1
            continue
        cls[(rtv, "3PT" if t.get("is_three_point_shot") else "2PT")] += 1
        src[str(t.get("shot_classification_source"))] += 1

    # (d) scored-vs-rendered, same turn. The FINAL render is the last emitter build for the
    # turn that carries a result_type (that is the one handed to the client); the earlier
    # result_type-less build is the classification probe.
    d_tot = d_flip = d_nofinal = 0
    d_ex = []
    d_award_cmp, d_award_flip, d_award_ex = Counter(), Counter(), []
    d_by_rt = Counter()      # flips split by outcome: a MAKE flip misawards POINTS,
    d_rt_all = Counter()     # a MISS/BLOCK flip corrupts only 3PA/3PM stat lines
    d_points_err = 0
    turns_list = gm.turns or []
    for ti, sc in SCORED.items():
        want = str(sc["shooter"])
        finals = [r for r in (RENDER.get(ti, []) + RENDER.get(ti + 1, []))
                  if r["has_result_type"] and r["shooter"] == want]
        if not finals:
            d_nofinal += 1
            continue
        fin = finals[-1]
        d_tot += 1
        # The turn resolved at index ti lands at gm.turns[ti]; used only to split flips by
        # outcome, and cross-checked on shooter id where the turn record carries one.
        trec = turns_list[ti] if ti < len(turns_list) else {}
        rtv = str(trec.get("result_type") or "?").upper()
        d_rt_all[rtv] += 1
        if "is_three_point_shot" in trec:
            awarded = bool(trec.get("is_three_point_shot"))
            d_award_cmp[rtv] += 1
            if awarded != bool(fin["is3"]):
                d_award_flip[rtv] += 1
                if len(d_award_ex) < 10:
                    d_award_ex.append({"turn": ti, "result": rtv,
                                       "awarded_is3": awarded, "awarded_value": trec.get("shot_value"),
                                       "rendered": fin["coord"], "rendered_is3": fin["is3"],
                                       "premicro": sc["coord"], "premicro_is3": sc["is3"]})
        if bool(fin["is3"]) != bool(sc["is3"]):
            d_flip += 1
            d_by_rt[rtv] += 1
            if rtv == "MAKE":
                d_points_err += 1
            if len(d_ex) < 10:
                d_ex.append({"turn": ti, "result": rtv,
                             "scored": sc["coord"], "scored_is3": sc["is3"],
                             "rendered": fin["coord"], "rendered_is3": fin["is3"],
                             "stamped_value": trec.get("shot_value"),
                             "state": sc["state"]})

    json.dump({
        "arm": ARM, "seed": SEED, "error": err, "turns": len(gm.turns or []),
        "score": dict(gm.score) if isinstance(getattr(gm, "score", None), dict) else None,
        "sync": dict(SYNC),
        "cls": {f"{k[0]}|{k[1]}": v for k, v in cls.items()},
        "cls_src": dict(src),
        "cand_n": len(CAND),
        "cand_flips": sum(1 for c in CAND if c["flip"]),
        "cand_3to2": sum(1 for c in CAND if c["skel_is3"] and not c["emit_is3"]),
        "cand_2to3": sum(1 for c in CAND if c["emit_is3"] and not c["skel_is3"]),
        "cand_coord_differ": sum(1 for c in CAND if c["dist"] > 1e-9),
        "cand_dist_mean": (sum(c["dist"] for c in CAND) / len(CAND)) if CAND else None,
        "d_total": d_tot, "d_flips": d_flip, "d_nofinal": d_nofinal, "d_examples": d_ex,
        "d_award_cmp": dict(d_award_cmp), "d_award_flip": dict(d_award_flip),
        "d_award_ex": d_award_ex,
        "d_by_rt": dict(d_by_rt), "d_rt_all": dict(d_rt_all), "d_points_err": d_points_err,
        "render_turns": len(RENDER), "scored_turns": len(SCORED),
        "dbg_scored": [[ti, str(v["shooter"])[:8], v["is3"]] for ti, v in sorted(SCORED.items())[:12]],
        "dbg_render": [[ti, str(r["shooter"])[:8], r["is3"], r["has_result_type"]]
                       for ti in sorted(RENDER)[:12] for r in RENDER[ti]],
    }, open(OUT, "w"))
