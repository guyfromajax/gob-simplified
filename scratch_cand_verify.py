"""Verify (b) with the REAL fallback, not a replica.

My read-only replica of set_shooter_coords_from_skeleton_last_step produced candidate-pair
distances of ~36 grid, which is exactly the away-mirror distance (68-32). That is the
signature of a mirroring mistake in the replica, so the replica's numbers cannot be trusted.

This calls the real ``set_shooter_coords_from_skeleton_last_step`` -- the exact function the
sim arm uses -- snapshotting and restoring ``shooter.coords`` and ``roles["shot_spot"]`` so
the game is not perturbed. Independence is checked by comparing turns/score against the
uninstrumented played-arm run for the same seed.
"""
import os, sys, json, math, random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")
SEED, OUT = int(os.environ["SEED"]), os.environ["OUT"]

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)
from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
from BackEnd.utils.shot_geometry import is_three_point_shot_from_coords
import BackEnd.engine.phase_resolution as PR

PAIRS = []
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
orig_fb = PR.set_shooter_coords_from_skeleton_last_step


def _real_skel_candidate(game, skeleton, roles):
    """Run the REAL fallback, capture roles['shot_spot'], then undo every write."""
    sh = roles.get("shooter")
    saved_c = dict(sh.coords) if isinstance(getattr(sh, "coords", None), dict) else None
    had = isinstance(roles, dict) and "shot_spot" in roles
    saved_s = roles.get("shot_spot") if isinstance(roles, dict) else None
    try:
        orig_fb(game, skeleton, roles)
        out = roles.get("shot_spot")
        return dict(out) if isinstance(out, dict) else None
    except Exception:
        return None
    finally:
        if saved_c is not None:
            sh.coords = saved_c
        if isinstance(roles, dict):
            if had:
                roles["shot_spot"] = saved_s
            else:
                roles.pop("shot_spot", None)


def sync(game, skeleton, animations, roles, turn_type="HCO"):
    skel = _real_skel_candidate(game, skeleton, roles)
    emit = orig_sync(game, skeleton, animations, roles, turn_type)
    if emit and skel:
        away = game.offense_team.team_id == game.away_team.team_id
        e3 = is_three_point_shot_from_coords(emit, is_away_offense=away)
        s3 = is_three_point_shot_from_coords(skel, is_away_offense=away)
        PAIRS.append({"emit": emit, "skel": skel, "e3": e3, "s3": s3,
                      "dist": math.hypot(emit["x"] - skel["x"], emit["y"] - skel["y"]),
                      "away": away, "ti": len(getattr(game, "turns", None) or [])})
    return emit


PR._uess_sync_emitted_shot_coords = sync

if __name__ == "__main__":
    _install_played()
    sim_random.seed(SEED); training_random.seed(SEED); _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy(); gm.away_team.strategy_settings = d.copy()
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0xF0000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"; break

    # Did the degenerate court-centre coord reach the SCOREBOARD? Resolve each affected
    # shot's turn record and read the value actually awarded.
    tl = gm.turns or []
    awarded = Counter()
    for p in PAIRS:
        if abs(p["emit"]["x"] - 50.0) > 1e-9 or abs(p["emit"]["y"] - 25.0) > 1e-9:
            continue
        t = tl[p["ti"]] if p["ti"] < len(tl) else {}
        awarded[f"{str(t.get('result_type') or '?').upper()}|value={t.get('shot_value')}"] += 1
    diff = [p for p in PAIRS if p["dist"] > 1e-9]
    flips = [p for p in PAIRS if bool(p["e3"]) != bool(p["s3"])]
    json.dump({
        "seed": SEED, "error": err, "turns": len(gm.turns or []),
        "score": dict(gm.score) if isinstance(getattr(gm, "score", None), dict) else None,
        "n": len(PAIRS), "n_differ": len(diff), "n_flip": len(flips),
        "flip_e3_s2": sum(1 for p in flips if p["e3"] and not p["s3"]),
        "flip_s3_e2": sum(1 for p in flips if p["s3"] and not p["e3"]),
        "dist_mean_differ": (sum(p["dist"] for p in diff) / len(diff)) if diff else None,
        "dist_hist": dict(Counter(min(int(p["dist"]), 40) // 5 * 5 for p in diff)),
        "examples": diff[:8],
        "degenerate_n": sum(1 for p in PAIRS if abs(p["emit"]["x"]-50.0) < 1e-9
                            and abs(p["emit"]["y"]-25.0) < 1e-9),
        "degenerate_awarded": dict(awarded),
    }, open(OUT, "w"))
