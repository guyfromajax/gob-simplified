"""Pinpoint where the ~(50,25) shooter coordinate enters, for the shots that show it.

Prior step ruled OUT the casing hypothesis: a dict subclass recording every missing-key
HCO_STRING_SPOTS lookup saw ZERO misses, so 'upper lowpost' is not falling through
defender_placement.py:190's sentinel -- at least not via a dict the probe could see. So stop
hypothesising and dump the whole chain for affected shots:

    skeleton shoot-step pos_action  ->  animator movement row  ->  emitter shoot-step end

plus an identity check that the patched constant actually reached the build module.
"""
import os, sys, json, random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")
SEED, OUT = int(os.environ.get("SEED", "8000")), os.environ["OUT"]

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)
from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
from BackEnd.utils.shot_geometry import is_three_point_shot_from_coords
from BackEnd.utils.shared import get_away_player_coords
from BackEnd.constants import HCO_STRING_SPOTS
import BackEnd.engine.phase_resolution as PR
import BackEnd.models.shot_manager as SM

LOWER = {k.lower(): v for k, v in HCO_STRING_SPOTS.items()}
PENDING = {}
SHOTS = []

DUMPS = []
BRANCH = Counter()
DEPTH, _FLAG = [0], {}


def _install_played():
    import BackEnd.models.animator as AN
    for m in ("capture_fast_break_animation", "capture_free_throw_animation",
              "capture_halfcourt_animation", "skeleton_to_animations"):
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


orig_sync = PR._uess_sync_emitted_shot_coords


def sync(game, skeleton, animations, roles, turn_type="HCO"):
    out = orig_sync(game, skeleton, animations, roles, turn_type)
    try:
        if not out:
            return out
        near_centre = abs(out["x"] - 50.0) < 3.0 and abs(out["y"] - 25.0) < 3.0
        shooter = roles.get("shooter")
        sid = getattr(shooter, "player_id", None)
        spos = roles.get("shooter_pos")
        steps = (skeleton or {}).get("steps") or []

        # which build branch would the shooter's shoot step take?
        pa = None
        idx = None
        for i in range(len(steps) - 1, -1, -1):
            a = (steps[i].get("pos_actions") or {}).get(spos)
            if a and (a.get("action") or "").lower().strip() == "shoot":
                pa, idx = a, i
                break
        if pa is not None:
            br = ("explicit-coords" if "coords" in pa
                  else "named-location" if "location" in pa
                  else "NEITHER->hardcoded(50,25)")
            BRANCH[f"{br}{' | near-centre' if near_centre else ''}"] += 1
            # Ground truth = the spot the skeleton actually authored. The build reads only
            # "coords"/"location"; set_shooter_coords_from_skeleton_last_step reads
            # "location" OR "spot" (phase_resolution.py:4408), which is the whole divergence.
            name = pa.get("location") or pa.get("spot")
            away = game.offense_team.team_id == game.away_team.team_id
            true3 = None
            if name and str(name).lower() in LOWER:
                c = dict(LOWER[str(name).lower()])
                if away:
                    c = get_away_player_coords(c)
                true3 = is_three_point_shot_from_coords(c, is_away_offense=away)
            PENDING.clear()
            PENDING.update({"branch": br, "near_centre": near_centre, "spot_name": name,
                            "true_is3": true3, "emit": dict(out),
                            "authored_coords": pa.get("coords")})
        if near_centre and len(DUMPS) < 6:
            row = None
            for a in (animations or []):
                if str(a.get("player_id")) == str(sid):
                    mv = a.get("movement") or []
                    row = {"n": len(mv),
                           "first3": [m.get("coords") for m in mv[:3]],
                           "last3": [m.get("coords") for m in mv[-3:]],
                           "actions_tail": [m.get("action") for m in mv[-4:]]}
                    break
            import BackEnd.engine.defender_placement as DP
            DUMPS.append({
                "emit_returned": out,
                "shooter_pos": spos,
                "shoot_step_index": idx, "n_skeleton_steps": len(steps),
                "pos_action_keys": sorted(pa.keys()) if pa else None,
                "pos_action": {k: (str(v)[:60]) for k, v in (pa or {}).items()},
                "animator_row": row,
                "last_step_pos_actions": sorted(((steps[-1].get("pos_actions") or {}).keys())) if steps else [],
                "spots_is_patched": type(getattr(DP, "HCO_STRING_SPOTS", None)).__name__,
            })
    except Exception as e:
        DUMPS.append({"probe_error": f"{type(e).__name__}: {e}"})
    return out


PR._uess_sync_emitted_shot_coords = sync

_orig_resolve = SM.ShotManager.resolve_shot


def _resolve(self, roles, *a, **k):
    """Joins the awarded value to the branch recorded by the sync immediately before it."""
    ctx = dict(PENDING)
    PENDING.clear()
    out = _orig_resolve(self, roles, *a, **k)
    if ctx and isinstance(out, dict):
        ctx["awarded_is3"] = bool(out.get("is_three_point_shot"))
        ctx["awarded_value"] = out.get("shot_value")
        ctx["made"] = str(out.get("result_type") or "").upper() == "MAKE" or bool(out.get("made"))
        SHOTS.append(ctx)
    return out


SM.ShotManager.resolve_shot = _resolve

if __name__ == "__main__":
    _install_played()
    sim_random.seed(SEED); training_random.seed(SEED); _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy(); gm.away_team.strategy_settings = d.copy()
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0xC0000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"; break
    tally, pts = Counter(), Counter()
    for s_ in SHOTS:
        b = s_["branch"]
        tally[b] += 1
        if s_.get("true_is3") is None:
            tally[b + " |no-ground-truth"] += 1
            continue
        wrong = bool(s_["true_is3"]) != bool(s_.get("awarded_is3"))
        tally[f"{b} |{'WRONG' if wrong else 'ok'}{'|made' if s_.get('made') else '|missed'}"] += 1
        if wrong and s_.get("made"):
            pts[b] += (1 if s_.get("awarded_is3") else -1)
    json.dump({"seed": SEED, "error": err, "turns": len(gm.turns or []),
               "score": dict(gm.score) if isinstance(getattr(gm, "score", None), dict) else None,
               "branch": dict(BRANCH), "n_shots": len(SHOTS),
               "tally": dict(tally), "points_error_by_branch": dict(pts),
               "dumps": DUMPS}, open(OUT, "w"), indent=1)
