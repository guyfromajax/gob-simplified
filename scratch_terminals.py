"""Terminal-type counts per game on a FIXED seed set (8000..8000+N).

Reused verbatim before and after the universal-establishment change so the
TEN_SECOND and OVER_BACK deltas are measured over the same games, per the
standing requirement that before/after comparisons share their seeds.
"""
import os, sys, random as _stdlib
from collections import Counter

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0 (SPC standing rule 4)")

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
from bson import ObjectId
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

GAMES = int(os.environ.get("PROBE_GAMES", "20"))
TO = Counter()
turns_total = 0

for g in range(GAMES):
    sim_random.seed(8000 + g)
    training_random.seed(8000 + g)
    _stdlib.seed(8000 + g)
    gm = GameManager("Lancaster", "Bentley-Truman")
    d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
         "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = d.copy()
    gm.away_team.strategy_settings = d.copy()
    gid = str(ObjectId())
    for _q in range(4):
        try:
            simulate_quarter(gm, game_id=gid)
        except Exception:
            break
    for t in (gm.turns or []):
        turns_total += 1
        tt = t.get("turnover_type")
        if tt:
            TO[str(tt)] += 1

print("\n" + "=" * 66)
print(f"TERMINAL COUNTS  seeds 8000..{8000+GAMES-1}  games={GAMES}")
print("=" * 66)
print(f"  turns total: {turns_total}")
for k in sorted(TO):
    print(f"  {k:<16} {TO[k]:>6}   {TO[k]/GAMES:>7.2f}/game")
print()
print(f"  TEN_SECOND per game : {TO['TEN_SECOND']/GAMES:.3f}")
print(f"  OVER_BACK  per game : {TO['OVER_BACK']/GAMES:.3f}")
