"""Harvest the EXISTING [3PT-READ] diagnostic (shot_manager.py:1026-1068) rather than
rebuilding it.

Its gate is double: ``calibration_diagnostics_enabled(game_state)`` -- which is
``not (_is_full_simulation or _headless_simulation)``, so ON in played/interactive games and
OFF in CPU sims -- AND ``logging.getLogger().isEnabledFor(logging.DEBUG)``. Both were added
by d3b11a184e (2026-07-23, "Codex fixed sim slowing issues") purely to keep it out of sims.

To read it WITHOUT redefining the arm, the gate call is forced true only for its own call
site (line 1027), leaving the identical call at line 400 and ``_is_full_simulation`` itself
untouched. Whether the game was perturbed anyway is checked by comparing turns/score against
the uninstrumented played-arm run for the same seed.

Fields are taken from ``record.args``, not by parsing the formatted string.
"""
import os, sys, json, logging, random as _stdlib
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
import BackEnd.models.shot_manager as SM

ROWS = []
GATE_LINE = 1027   # the [3PT-READ] gate's own call to calibration_diagnostics_enabled


class Capture(logging.Handler):
    """Cheap: filters on record.msg (the raw format string), never formatting non-matches."""

    def emit(self, record):
        pass

    def handle(self, record):
        msg = record.msg
        if isinstance(msg, str) and msg.startswith("[3PT-READ]") and record.args:
            ROWS.append(record.args)
        return True


def _install_diag_gate():
    orig = SM.calibration_diagnostics_enabled

    def gate(x):
        # True ONLY for the 3PT-READ site, so shot_manager.py:400's diagnostic bookkeeping
        # and the arm's own _is_full_simulation both behave exactly as they did.
        try:
            if sys._getframe(1).f_lineno == GATE_LINE:
                return True
        except Exception:
            pass
        return orig(x)
    SM.calibration_diagnostics_enabled = gate


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


if __name__ == "__main__":
    _install_played()
    _install_diag_gate()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(Capture())
    root.setLevel(logging.DEBUG)
    logging.disable(logging.NOTSET)

    sim_random.seed(SEED); training_random.seed(SEED); _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy(); gm.away_team.strategy_settings = d.copy()
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0xA0000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"; break

    # args order per the format string at shot_manager.py:1053-1068
    #  0 shot_type, 1 resolved_is_three, 2 coord_is_three, 3 role_spot_is_three,
    #  4 spot_name_is_three, 5 shooter_id, 6 shooter_pos, 7 skeleton_spot,
    #  8 roles_shot_spot, 9 sx, 10 sy
    pairs = {"resolved_vs_coord": Counter(), "resolved_vs_spotname": Counter(),
             "resolved_vs_rolespot": Counter()}
    spot_when_mismatch = Counter()
    xy_when_mismatch = Counter()
    ex = []
    for a in ROWS:
        res, coord, rolesp, spotn = a[1], a[2], a[3], a[4]
        pairs["resolved_vs_coord"][f"resolved={res} coord={coord}"] += 1
        pairs["resolved_vs_spotname"][f"resolved={res} spot_name={spotn}"] += 1
        pairs["resolved_vs_rolespot"][f"resolved={res} role_spot={rolesp}"] += 1
        if bool(res) != bool(spotn):
            spot_when_mismatch[str(a[7])] += 1
            xy_when_mismatch[f"({a[9]:.1f},{a[10]:.1f})"] += 1
            if len(ex) < 8:
                ex.append({"shot_type": a[0], "resolved": res, "coord": coord,
                           "role_spot": rolesp, "spot_name": spotn,
                           "skeleton_spot": str(a[7]), "roles_shot_spot": str(a[8]),
                           "resolved_xy": [round(a[9], 2), round(a[10], 2)]})

    json.dump({
        "seed": SEED, "error": err, "turns": len(gm.turns or []),
        "score": dict(gm.score) if isinstance(getattr(gm, "score", None), dict) else None,
        "n_lines": len(ROWS),
        "pairs": {k: dict(v) for k, v in pairs.items()},
        "skeleton_spot_when_resolved_ne_spotname": dict(spot_when_mismatch.most_common(12)),
        "resolved_xy_when_mismatch": dict(xy_when_mismatch.most_common(12)),
        "examples": ex,
    }, open(OUT, "w"))
