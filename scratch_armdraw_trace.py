"""Arm-asymmetric RNG census. One (arm, seed) per process.

Records every sim_rng primitive draw (random / getrandbits — every Random method
funnels through these two) with its in-repo call path and the turn index it fell in.
Also installs the global-draw guard so BackEnd draws that escape to stdlib `random`
are counted per arm. Observation only: wrappers pass values through untouched.
"""
import os, sys, pickle
os.environ.setdefault("OUT", "/dev/null")
REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
import scratch_equiv3_fbdedupe as W
from BackEnd.utils import sim_random
from BackEnd.models.game_manager import GameManager

sim_random.install_global_draw_guard()
PREFIX = REPO + "/"
GM = [None]
_init = GameManager.__init__
def _gm_init(self, *a, **k):
    _init(self, *a, **k)
    GM[0] = self
GameManager.__init__ = _gm_init

PATHS = {}
DRAWS = []   # (turn_idx, path_id, kind, value)

def _path():
    f = sys._getframe(2)
    out = []
    while f is not None:
        fn = f.f_code.co_filename
        if fn.startswith(PREFIX) and "/BackEnd/" in fn:
            out.append((fn[len(PREFIX):], f.f_code.co_name, f.f_lineno))
        f = f.f_back
    return tuple(reversed(out))

def _record(kind, v):
    p = _path()
    pid = PATHS.get(p)
    if pid is None:
        pid = PATHS[p] = len(PATHS)
    g = GM[0]
    if W.SIDE["depth"]:
        kind = "S" + kind
    DRAWS.append((len(g.turns or []) if g is not None else -1, pid, kind, v))

rng = sim_random.sim_rng
_gb, _rnd = rng.getrandbits, rng.random
def gb(k):
    v = _gb(k); _record("b%d" % k, v); return v
def rnd():
    v = _rnd(); _record("r", v); return v
rng.getrandbits = gb
rng.random = rnd

if __name__ == "__main__":
    W._install_defense_census()
    if W.ALIGN_RNG:
        W._install_align_regions()
    rows = W.run_arm(os.environ["ARM"] == "played")
    g = GM[0]
    import copy
    turns = [copy.deepcopy({k: v for k, v in t.items() if k not in ("animation_steps", "animations", "skeleton")})
             for t in (g.turns or [])]
    pickle.dump({"rows": rows, "paths": {v: k for k, v in PATHS.items()}, "draws": DRAWS,
                 "turns": turns, "global": sim_random.global_draw_report()},
                open(os.environ["TRACE_OUT"], "wb"))
    print(os.environ["ARM"], rows[0]["seed"], rows[0]["points_per_team"], rows[0]["draws"], len(DRAWS))
