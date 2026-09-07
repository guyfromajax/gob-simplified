"""equiv-v3 WORKER — runs exactly ONE arm for exactly ONE seed, then exits.

Why a worker at all: two arms run back-to-back in one process are not independent. Player
and team state persists in the mongomock DB across games, so an arm's result depends on its
POSITION in the process (proven: three identical passes gave three different games, draw
counts 137,106 / 136,832 / 134,387). Re-seeding the RNGs does not reset the DB.

The fix is process isolation at the GAME level, not the arm level. mongomock.MongoClient()
lives in process memory (db.py:222), so a fresh process IS a fresh database -- one game per
process satisfies "one arm per process" and "fresh DB per game" with the same mechanism, and
startup measures at 0.64s so it costs almost nothing.

Invoked as:  ARM=sim|played SEED=8000 OUT=path python scratch_harness_run.py
Writes one JSON blob. Prints nothing to stdout that the driver does not parse.
"""
import os, sys, json, math, hashlib, statistics as st, random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")

ARM = os.environ["ARM"]
SEED = int(os.environ["SEED"])
OUT = os.environ["OUT"]

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
import BackEnd.utils.sim_random as SR
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
import BackEnd.models.shot_manager as SM
import BackEnd.engine.phase_resolution as PR

GATED_METHODS = ("capture_fast_break_animation", "capture_free_throw_animation",
                 "capture_halfcourt_animation", "skeleton_to_animations")
DEPTH = [0]
_FLAG = {}
DRAWS = Counter()
OBS = {"dists": [], "factors": [], "scores": [], "entries": 0, "fouls": 0,
       "tight": 0, "floor": 0, "shots": 0, "prox_calls": 0}
SRC = Counter()


def _install_draw_counter():
    """Modules alias the sim_rng OBJECT (`from ...sim_random import sim_rng as random`), so
    patching bound methods on the instance is visible everywhere. Adds no draws."""
    for m in ("random", "randint", "choice", "uniform", "randrange", "shuffle",
              "sample", "gauss", "triangular", "betavariate", "expovariate"):
        if not hasattr(SR.sim_rng, m):
            continue
        orig = getattr(SR.sim_rng, m)

        def mk(orig=orig, m=m):
            def counted(*a, **k):
                DRAWS[m] += 1
                return orig(*a, **k)
            return counted
        setattr(SR.sim_rng, m, mk())


def _install_instruments():
    """Identical in BOTH arms, so any asymmetry in the output is the arms, not the probe."""
    orig_prox = SM._proximity_contest_factor
    floor_val = orig_prox(99.0)

    def prox(dist):
        f = orig_prox(dist)
        OBS["prox_calls"] += 1
        if dist is not None:
            d = float(dist)
            OBS["dists"].append(d)
            OBS["factors"].append(f)
            if d <= 3.0:
                OBS["tight"] += 1
            if f <= floor_val:
                OBS["floor"] += 1
        return f
    SM._proximity_contest_factor = prox

    orig_score = SM.ShotManager.calculate_shot_score

    def score(self, *a, **k):
        OBS["shots"] += 1
        return orig_score(self, *a, **k)
    SM.ShotManager.calculate_shot_score = score

    orig_foul = SM.ShotManager.check_defensive_foul_on_shot

    def foul(self, defender, defense_score, shot_type, shooter=None, shooter_location=None):
        out = orig_foul(self, defender, defense_score, shot_type, shooter, shooter_location)
        if defender:
            OBS["entries"] += 1
            OBS["scores"].append(float(defense_score or 0))
            if out[0]:
                OBS["fouls"] += 1
        return out
    SM.ShotManager.check_defensive_foul_on_shot = foul

    # provenance of the coordinate the shot contest actually uses
    orig_freeze = PR._freeze_hco_shot_attempt_geometry

    def freeze(*a, **k):
        out = orig_freeze(*a, **k)
        SRC[str(getattr(out, "source", "<none>"))] += 1
        return out
    PR._freeze_hco_shot_attempt_geometry = freeze


def _install_played_arm():
    """Flip _is_full_simulation IN PLACE on the live dict for the duration of each gated
    Animator call. Never replace the dict: shot_manager.py:286 captured it by reference at
    GameManager construction, and swapping it orphans every shooting-foul award."""
    import BackEnd.models.animator as AN
    for meth in GATED_METHODS:
        orig = getattr(AN.Animator, meth)

        def mk(orig=orig):
            def wrapped(self, *a, **k):
                gs = self.game.game_state
                if DEPTH[0] == 0:
                    _FLAG["had"] = "_is_full_simulation" in gs
                    _FLAG["prev"] = gs.get("_is_full_simulation")
                gs["_is_full_simulation"] = False
                DEPTH[0] += 1
                try:
                    return orig(self, *a, **k)
                finally:
                    DEPTH[0] -= 1
                    if DEPTH[0] == 0:
                        if _FLAG["had"]:
                            gs["_is_full_simulation"] = _FLAG["prev"]
                        else:
                            gs.pop("_is_full_simulation", None)
            return wrapped
        setattr(AN.Animator, meth, mk())


def ft_invariant(turns, window=3):
    """Awards honoured. STRICT requires the free throw on the very next turn, which has a
    known false negative when a TIMEOUT legitimately interposes; WINDOWED allows it within a
    few turns. Both reported so the choice of metric stays visible."""
    awards = strict = windowed = 0
    reasons = Counter()
    for i, t in enumerate(turns):
        if str(t.get("next_turn") or "").upper() != "FREE_THROW":
            continue
        awards += 1
        nxts = [str(turns[j].get("result_type") or "").upper()
                for j in range(i + 1, min(i + 1 + window, len(turns)))]
        if nxts and nxts[0] == "FREE_THROW":
            strict += 1
        if "FREE_THROW" in nxts:
            windowed += 1
        else:
            reasons[f"{str(t.get('result_type') or '').upper()} -> "
                    f"{nxts[0] if nxts else '<END>'}"] += 1
    return awards, strict, windowed, reasons


if __name__ == "__main__":
    _install_draw_counter()
    _install_instruments()
    if ARM == "played":
        _install_played_arm()

    sim_random.seed(SEED)
    training_random.seed(SEED)
    _stdlib.seed(SEED)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
         "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy()
    gm.away_team.strategy_settings = d.copy()
    err = None
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id="%024x" % (0xD0000 + SEED))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            break

    turns = gm.turns or []
    rt = Counter(str(t["result_type"]).upper() for t in turns if t.get("result_type"))
    rows = [(str(t.get("result_type") or ""), str(t.get("turnover_type") or ""),
             str(t.get("next_turn") or "")) for t in turns]
    fp = hashlib.sha256(json.dumps(rows, sort_keys=False).encode()).hexdigest()[:16]
    aw, strict, wind, reasons = ft_invariant(turns)

    json.dump({
        "arm": ARM, "seed": SEED, "error": err,
        "fingerprint": fp, "turns": len(turns),
        "draws": sum(DRAWS.values()),
        # GameManager keeps the live scoreboard on ``gm.score`` (mirrored into game_state
        # as "score"); there is no home_score/away_score key.
        "score": (dict(gm.score) if isinstance(getattr(gm, "score", None), dict)
                  else getattr(gm, "score", None)),
        "result_types": dict(rt),
        "ft_awards": aw, "ft_strict": strict, "ft_windowed": wind,
        "ft_drop_reasons": dict(reasons),
        "src": dict(SRC),
        "shots": OBS["shots"], "entries": OBS["entries"], "fouls": OBS["fouls"],
        "prox_calls": OBS["prox_calls"],
        "score_mean": st.mean(OBS["scores"]) if OBS["scores"] else None,
        "score_median": st.median(OBS["scores"]) if OBS["scores"] else None,
        "dist_mean": st.mean(OBS["dists"]) if OBS["dists"] else None,
        "dist_median": st.median(OBS["dists"]) if OBS["dists"] else None,
        "factor_mean": st.mean(OBS["factors"]) if OBS["factors"] else None,
        "n_graded": len(OBS["dists"]), "tight": OBS["tight"], "floor": OBS["floor"],
    }, open(OUT, "w"))
