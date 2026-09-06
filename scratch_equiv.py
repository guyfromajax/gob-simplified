"""Sim-vs-played EQUIVALENCE probe, animation isolated.

HARNESS ID: equiv-v1  (pin this; before/after pairs are only comparable
within the same harness id — the arm definition is still moving.)

ARM DEFINITION (the whole point). `_is_full_simulation` stays True in BOTH
arms so every behavioural branch it gates is held constant: timeout policy
(game_manager.py:1926/2056), foul-out lineup rebuild (:1303/:1370), FCP
skeleton loading + its draws (phase_resolution.py:9964/:10065), the
StepState diagnose pass and its third placement (step_state.py:115),
Playcall Center (turn_manager.py:1474), user-team damping (db_utils.py:339/
:1205), and the triangle/FT emitter gates. The ONLY delta between arms is
that the played arm lets the four animator gates fall through
(animator.py:145, 624, 829, 1265), so animation actually runs.

Reports two things per the standing instruction:
  - DRAW ATTRIBUTION (leading indicator, cheap, low noise): sim_rng draws
    whose stack passes through the placement subtree.
  - BOX SCORE (pass condition): turns/points/MAKE/MISS/FT/STEAL/FOUL/BLOCK.
"""
import os, sys, random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0 (SPC determinism contract clause 3)")

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

GAMES = int(os.environ.get("PROBE_GAMES", "20"))

# Modules that constitute defender placement. animator today; the new engine
# module after commit 1 — count BOTH so the probe is valid across the move.
PLACEMENT_MODULES = {
    "BackEnd.models.animator",
    "BackEnd.engine.defender_placement",
}

C = Counter()          # live counters, reset per game
_MAXDEPTH = 40


def _in_placement() -> bool:
    """True when any frame in the current stack belongs to the placement subtree."""
    f = sys._getframe(2)
    d = 0
    while f is not None and d < _MAXDEPTH:
        if f.f_globals.get("__name__") in PLACEMENT_MODULES:
            return True
        f = f.f_back
        d += 1
    return False


def _install_draw_attribution():
    """Wrap sim_rng's draw methods to tally total vs placement-attributable draws."""
    rng = sim_random.sim_rng
    for name in ("random", "randint", "choice", "choices", "shuffle", "uniform",
                 "sample", "gauss", "normalvariate", "betavariate", "triangular",
                 "randrange", "getrandbits", "expovariate", "lognormvariate",
                 "vonmisesvariate", "paretovariate", "weibullvariate", "randbytes"):
        orig = getattr(rng, name, None)
        if orig is None:
            continue

        def make(orig=orig):
            def wrapped(*a, **k):
                C["draws_total"] += 1
                if _in_placement():
                    C["draws_placement"] += 1
                return orig(*a, **k)
            return wrapped
        setattr(rng, name, make())


def _install_call_counters():
    """Count placement computations directly (acceptance B's counter)."""
    from BackEnd.utils import shared_defense as SD
    _gdc = SD.get_defender_coords

    def gdc(*a, **k):
        C["get_defender_coords"] += 1
        return _gdc(*a, **k)
    SD.get_defender_coords = gdc

    from BackEnd.models import animator as AN
    for meth, key in (("_build_all_animations", "build_all_animations"),
                      ("compute_defender_grid", "compute_defender_grid"),
                      ("capture_halfcourt_animation", "capture_halfcourt")):
        orig = getattr(AN.Animator, meth, None)
        if orig is None:
            continue

        def make(orig=orig, key=key):
            def wrapped(self, *a, **k):
                C[key] += 1
                return orig(self, *a, **k)
            return wrapped
        setattr(AN.Animator, meth, make())


class AnimatorBlindGameState(dict):
    """Reports `_is_full_simulation` as False ONLY to animator.py callers.

    Every other consumer still sees True, which is what holds the six known
    non-animation divergence causes constant. See the module docstring.
    """

    def get(self, key, default=None):
        if key == "_is_full_simulation":
            if sys._getframe(1).f_globals.get("__name__") == "BackEnd.models.animator":
                return False
        return super().get(key, default)


def run_arm(label, blind, games):
    rows = []
    for g in range(games):
        C.clear()
        sim_random.seed(8000 + g)
        training_random.seed(8000 + g)
        _stdlib.seed(8000 + g)
        gm = GameManager("Lancaster", "Bentley-Truman")
        if blind:
            gm.game_state = AnimatorBlindGameState(gm.game_state)
        d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
             "hc_trap": 5, "fc_press": 5}
        gm.home_team.strategy_settings = d.copy()
        gm.away_team.strategy_settings = d.copy()
        gid = "%024x" % (0xE0000 + g)          # deterministic, identical across arms
        for _q in range(4):
            try:
                simulate_quarter(gm, game_id=gid)
            except Exception as e:
                print(f"  [{label} seed {8000+g}] quarter aborted: {type(e).__name__}: {e}")
                break
        rt = Counter()
        tt = Counter()
        for t in (gm.turns or []):
            if t.get("result_type"):
                rt[str(t["result_type"]).upper()] += 1
            if t.get("turnover_type"):
                tt[str(t["turnover_type"]).upper()] += 1
        rows.append({
            "seed": 8000 + g,
            "turns": len(gm.turns or []),
            "points": sum((gm.score or {}).values()),
            "rt": rt, "tt": tt,
            "draws_total": C["draws_total"],
            "draws_placement": C["draws_placement"],
            "gdc": C["get_defender_coords"],
            "build_all": C["build_all_animations"],
            "grid": C["compute_defender_grid"],
            "capture_hc": C["capture_halfcourt"],
        })
        print(f"  [{label}] seed {8000+g}: turns={rows[-1]['turns']:>4} "
              f"pts={rows[-1]['points']:>4} draws={rows[-1]['draws_total']:>7} "
              f"placement={rows[-1]['draws_placement']:>7} gdc={rows[-1]['gdc']:>6}")
    return rows


def summarize(rows):
    n = len(rows) or 1
    out = {
        "turns": sum(r["turns"] for r in rows) / n,
        "points": sum(r["points"] for r in rows) / n,
        "draws_total": sum(r["draws_total"] for r in rows) / n,
        "draws_placement": sum(r["draws_placement"] for r in rows) / n,
        "gdc": sum(r["gdc"] for r in rows) / n,
        "build_all": sum(r["build_all"] for r in rows) / n,
        "grid": sum(r["grid"] for r in rows) / n,
        "capture_hc": sum(r["capture_hc"] for r in rows) / n,
    }
    for k in ("MAKE", "MISS", "BLOCK", "FOUL", "FREE_THROW"):
        out[k] = sum(r["rt"].get(k, 0) for r in rows) / n
    for k in ("STEAL", "OVER_BACK", "TEN_SECOND"):
        out[k] = (sum(r["tt"].get(k, 0) for r in rows) / n) + \
                 (sum(r["rt"].get(k, 0) for r in rows) / n if k == "STEAL" else 0)
    return out


if __name__ == "__main__":
    _install_draw_attribution()
    _install_call_counters()
    print(f"\nHARNESS equiv-v1  games={GAMES}  seeds 8000..{8000+GAMES-1}")
    print("\n--- ARM 1: sim (animation skipped, status quo) ---")
    sim = run_arm("sim", blind=False, games=GAMES)
    print("\n--- ARM 2: played (animation runs; every other flag branch held) ---")
    played = run_arm("played", blind=True, games=GAMES)

    s, p = summarize(sim), summarize(played)
    print("\n" + "=" * 78)
    print(f"EQUIVALENCE  harness=equiv-v1  n={GAMES} per arm  seeds 8000-{8000+GAMES-1}")
    print("=" * 78)
    print(f"{'metric':<20}{'sim':>12}{'played':>12}{'delta':>12}{'pct':>10}")
    for k in ("turns", "points", "MAKE", "MISS", "BLOCK", "FOUL", "FREE_THROW",
              "STEAL", "draws_total", "draws_placement", "gdc", "build_all",
              "grid", "capture_hc"):
        a, b = s[k], p[k]
        delta = b - a
        pct = (100.0 * delta / a) if a else float("nan")
        print(f"{k:<20}{a:>12.1f}{b:>12.1f}{delta:>+12.1f}{pct:>+9.1f}%")
    print()
    print("SELF-CHECK (the arm split actually took effect):")
    print(f"  played-arm capture_halfcourt calls: {p['capture_hc']:.1f}/game "
          f"(sim arm {s['capture_hc']:.1f})")
    print(f"  played-arm build_all_animations   : {p['build_all']:.1f}/game "
          f"(sim arm {s['build_all']:.1f})")
    if p["gdc"] <= s["gdc"]:
        print("  ⚠️  played arm did NOT do more placement work — wrapper may have been "
              "lost (game_state reassigned mid-run). Result is INVALID.")
    else:
        print("  ✅ played arm did more placement work than sim arm, as expected.")
