"""SPC principle 7 worker — before/after profile of the HCO build path.

Call counts are the primary instrument (standing rule 5). The fix moves 112k
pos_actions per 12 games off a dict-literal fallthrough and onto an
HCO_STRING_SPOTS lookup, so the build should get slightly SLOWER per call; the
point is to know by how much rather than to assume it is free.
"""
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ARM = os.environ.get("ARM", "played")
SEED = int(os.environ["SEED"])
OUT = os.environ["OUT"]

import scratch_harness_run as HR
from BackEnd.utils import sim_random, training_random
import random as _stdlib
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

import BackEnd.engine.defender_placement as DP
import BackEnd.models.animator as AN

STATS = Counter()
TIMES = []


def _install():
    orig = DP.build_all_animations

    def wrapped(game, skeleton, off_lineup, def_lineup, *a, **k):
        t0 = time.perf_counter()
        try:
            return orig(game, skeleton, off_lineup, def_lineup, *a, **k)
        finally:
            TIMES.append(time.perf_counter() - t0)
            STATS["builds"] += 1
            for st in (skeleton.get("steps") or []):
                STATS["step_pos_actions"] += len(st.get("pos_actions") or {})
            STATS["steps"] += len(skeleton.get("steps") or [])

    DP.build_all_animations = wrapped
    if hasattr(AN, "build_all_animations"):
        AN.build_all_animations = wrapped


_install()

if ARM == "played":
    HR._install_played_arm()

sim_random.seed(SEED)
training_random.seed(SEED)
_stdlib.seed(SEED)
gm = GameManager("Lancaster", "Bentley-Truman")
_d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
      "hc_trap": 5, "fc_press": 5}
gm.home_team.strategy_settings = _d.copy()
gm.away_team.strategy_settings = _d.copy()
t_game = time.perf_counter()
err = None
for _q in range(4):
    try:
        simulate_quarter(gm, game_id="%024x" % (0xD0000 + SEED))
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        break
wall = time.perf_counter() - t_game

TIMES.sort()
n = len(TIMES) or 1
json.dump({
    "arm": ARM, "seed": SEED, "error": err,
    "game_wall_s": round(wall, 3),
    "turns": len(gm.turns or []),
    "builds": STATS["builds"],
    "steps": STATS["steps"],
    "step_pos_actions": STATS["step_pos_actions"],
    "build_total_s": round(sum(TIMES), 4),
    "build_mean_ms": round(1000.0 * sum(TIMES) / n, 4),
    "build_p50_ms": round(1000.0 * TIMES[n // 2], 4),
    "build_p95_ms": round(1000.0 * TIMES[int(n * 0.95)], 4),
    "build_share_of_game_pct": round(100.0 * sum(TIMES) / wall, 2) if wall else None,
}, open(OUT, "w"))
