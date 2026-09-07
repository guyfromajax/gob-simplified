"""Trace the (50,25) centreline coordinate to its source, and price it.

Hypothesis under test: HCO_STRING_SPOTS holds 15 camelCase keys out of 38 ('upper lowPost',
'topLane', 'basketSpot', ...). Skeletons author spot names in lowercase ('upper lowpost'), so
a plain .get(name, {"x": 50, "y": 25}) MISSES and silently yields court centre. Court centre
is x=50 on y=25, and the 3PT arc is at its deepest there (boundary x=64.0), so the sentinel
always reads as BEHIND THE ARC -- a low-post shot becomes a three.

phase_resolution.py:4408-4414 already carries a case-insensitive retry with the comment
'skeleton may use "upper midwing" vs constant "upper midWing"', so this was a known defect
fixed in ONE path. This probe finds the paths that were not fixed.

Two instruments:
  1. HCO_STRING_SPOTS replaced (in every module that imported it) by a dict subclass that
     records every MISSING-key lookup with its caller file:line. That gives the call sites.
  2. resolve_shot wrapped to capture, per shot: the authored spot name, the value AWARDED,
     and whether the shot was made -- so the sentinel can be priced in points, and so the
     "genuinely wrong" vs "merely inconsistent" distinction is settled per shot rather than
     assumed.
"""
import os, sys, json, math, random as _stdlib
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
import BackEnd.constants as CONST
import BackEnd.models.shot_manager as SM

MISSES = Counter()
SHOTS = []
TRUE = dict(CONST.HCO_STRING_SPOTS)
LOWER = {k.lower(): v for k, v in TRUE.items()}
SENTINEL = {"x": 50, "y": 25}


class RecordingSpots(dict):
    """Records lookups whose key is ABSENT and which therefore fall back to the default."""

    def get(self, key, default=None):
        if key not in self:
            try:
                f = sys._getframe(1)
                site = f"{os.path.basename(f.f_code.co_filename)}:{f.f_lineno}"
            except Exception:
                site = "?"
            # only interesting when the miss is recoverable by case -- i.e. a real spot the
            # caller failed to find purely because of casing
            recoverable = str(key).lower() in LOWER
            MISSES[(site, str(key), "RECOVERABLE-BY-CASE" if recoverable else "unknown-spot")] += 1
        return super().get(key, default)


def _patch_spots():
    """HCO_STRING_SPOTS is imported by value in many modules, so patch every module object
    that holds a reference, not just BackEnd.constants."""
    rec = RecordingSpots(TRUE)
    n = 0
    CONST.HCO_STRING_SPOTS = rec
    for name, mod in list(sys.modules.items()):
        if not name.startswith("BackEnd") or mod is None:
            continue
        if getattr(mod, "HCO_STRING_SPOTS", None) is not None:
            try:
                setattr(mod, "HCO_STRING_SPOTS", rec)
                n += 1
            except Exception:
                pass
    return n


def _true_is3(spot_name, away):
    """The classification the authored spot SHOULD have produced (case-insensitive)."""
    c = LOWER.get(str(spot_name).lower())
    if not c:
        return None
    c = get_away_player_coords(dict(c)) if away else dict(c)
    return is_three_point_shot_from_coords(c, is_away_offense=away), c


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


def _install_shot_capture():
    orig = SM.ShotManager.resolve_shot

    def resolve_shot(self, roles, *a, **k):
        away = self.game.offense_team.team_id == self.game.away_team.team_id
        try:
            _pos, spot = self._get_shooter_position_and_spot(roles.get("shooter"), roles)
        except Exception:
            spot = None
        pre = roles.get("shot_spot") if isinstance(roles, dict) else None
        pre = dict(pre) if isinstance(pre, dict) else None
        out = orig(self, roles, *a, **k)
        try:
            post = roles.get("shot_spot") if isinstance(roles, dict) else None
            rec = {
                "spot": str(spot) if spot else None, "away": away,
                "pre": pre, "post": dict(post) if isinstance(post, dict) else None,
                "awarded_is3": bool(out.get("is_three_point_shot")) if isinstance(out, dict) else None,
                "awarded_value": (out.get("shot_value") if isinstance(out, dict) else None),
                "result": str((out or {}).get("result_type") or "").upper() if isinstance(out, dict) else "",
                "made": bool((out or {}).get("made")) if isinstance(out, dict) else None,
            }
            SHOTS.append(rec)
        except Exception:
            pass
        return out
    SM.ShotManager.resolve_shot = resolve_shot


if __name__ == "__main__":
    _install_played()
    npatched = _patch_spots()
    _install_shot_capture()
    sim_random.seed(SEED); training_random.seed(SEED); _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy(); gm.away_team.strategy_settings = d.copy()
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0xB0000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"; break

    # Price it: for every shot whose authored spot resolves case-insensitively to a REAL
    # spot, compare the value awarded against the value that spot should have produced.
    verdict = Counter()
    wrong_pts = 0
    wrong_ex = []
    for s in SHOTS:
        t = _true_is3(s["spot"], s["away"]) if s["spot"] else None
        if not t:
            verdict["no-resolvable-authored-spot"] += 1
            continue
        true3, truec = t
        if s["awarded_is3"] is None:
            verdict["no-award-recorded"] += 1
            continue
        agree = bool(true3) == bool(s["awarded_is3"])
        made = s["result"] == "MAKE" or s["made"]
        verdict[("agree" if agree else "AWARDED-WRONG") + ("|made" if made else "|missed")] += 1
        if not agree and made:
            wrong_pts += (3 - 2) if s["awarded_is3"] else (2 - 3)
            if len(wrong_ex) < 8:
                wrong_ex.append({"spot": s["spot"], "true_coord": truec, "true_is3": true3,
                                 "awarded_value": s["awarded_value"],
                                 "classified_from": s["post"], "away": s["away"]})

    json.dump({
        "seed": SEED, "error": err, "turns": len(gm.turns or []),
        "score": dict(gm.score) if isinstance(getattr(gm, "score", None), dict) else None,
        "modules_patched": npatched, "n_shots": len(SHOTS),
        "misses": {f"{k[0]} | {k[1]} | {k[2]}": v for k, v in MISSES.most_common(30)},
        "miss_total": sum(MISSES.values()),
        "miss_recoverable": sum(v for k, v in MISSES.items() if k[2] == "RECOVERABLE-BY-CASE"),
        "verdict": dict(verdict), "wrong_points": wrong_pts, "wrong_examples": wrong_ex,
    }, open(OUT, "w"))
