"""Avoidance-only opportunity count (amendment 2).

Same instrument and same seeds as the pre-change HCO probe (4000..4000+N), so
the numbers are directly comparable:
    BEFORE: 3039 beats, BH behind line 83 (4.15/game), 58 nudge / 25 spot,
            deepest x=38.0, freelance pass to backcourt receiver 33 (1.65/game)

If the residual is zero, the awareness roll does NOT get written.
"""
import os, sys, random as _stdlib

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
import BackEnd.engine.over_and_back as OAB
import BackEnd.engine.motion_freelance as MF

S = {"beats": 0, "bh_behind": 0, "offball_behind": 0, "any_behind": 0,
     "passes": 0, "pass_rx_behind": 0, "worst": None,
     "bh_arrived_behind": 0, "bh_moved_behind": 0}
_away = {"v": False}

_real_beat = MF.build_freelance_beat
def _probe(step, off_lineup, bh_pos, off_eff, team_chem, is_away_offense, rng):
    # BH's INCOMING coord, before this beat moves anyone
    _in = (step.get("pos_actions") or {}).get(bh_pos) or {}
    _in_xy = MF._coords_for(_in, is_away_offense) if _in else None
    _was_behind = (_in_xy is not None and
                   OAB.in_backcourt(float(_in_xy.get("x", 50)), is_away_offense))
    beat = _real_beat(step, off_lineup, bh_pos, off_eff, team_chem, is_away_offense, rng)
    if beat is None:
        return beat
    _away["v"] = is_away_offense
    S["beats"] += 1
    behind_any = False
    for pos, info in (beat.get("pos_actions") or {}).items():
        x = float((info.get("coords") or {}).get("x", 50))
        if OAB.in_backcourt(x, is_away_offense):
            behind_any = True
            if pos == bh_pos:
                S["bh_behind"] += 1
                S["bh_arrived_behind" if _was_behind else "bh_moved_behind"] += 1
                depth = (50 - x) if not is_away_offense else (x - 50)
                if S["worst"] is None or depth > S["worst"][0]:
                    S["worst"] = (depth, x)
            else:
                S["offball_behind"] += 1
    if behind_any:
        S["any_behind"] += 1
    return beat
MF.build_freelance_beat = _probe

_real_pass = MF.freelance_pass_step
def _probe_pass(passer_pos, receiver_pos, passer_coords, receiver_coords, timestamp):
    S["passes"] += 1
    if OAB.in_backcourt(float((receiver_coords or {}).get("x", 50)), _away["v"]):
        S["pass_rx_behind"] += 1
    return _real_pass(passer_pos, receiver_pos, passer_coords, receiver_coords, timestamp)
MF.freelance_pass_step = _probe_pass

from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

GAMES = int(os.environ.get("PROBE_GAMES", "20"))
for g in range(GAMES):
    sim_random.seed(4000 + g)
    training_random.seed(4000 + g)
    _stdlib.seed(4000 + g)
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

print("\n" + "=" * 70)
print(f"AVOIDANCE-ONLY RESIDUAL   seeds 4000..{4000+GAMES-1}  games={GAMES}")
print("=" * 70)
print(f"  freelance beats                       : {S['beats']}   (before: 3039)")
print(f"  >>> BH behind the line                : {S['bh_behind']}"
      f"   (before: 83 = 4.15/game)")
print(f"  >>> off-ball offenders behind the line: {S['offball_behind']}")
print(f"  beats with someone behind the line    : {S['any_behind']}   (before: 402)")
if S["worst"]:
    print(f"  deepest BH incursion                  : x={S['worst'][1]}")
print(f"  freelance passes                      : {S['passes']}   (before: 1660)")
print(f"  >>> pass to receiver behind the line  : {S['pass_rx_behind']}"
      f"   (before: 33 = 1.65/game)")
print()
print(f"  of the BH residual:")
print(f"    ARRIVED behind the line (entry coords): {S['bh_arrived_behind']}"
      f"   = {S['bh_arrived_behind']/GAMES:.2f}/game")
print(f"    MOVED behind the line this beat        : {S['bh_moved_behind']}"
      f"   = {S['bh_moved_behind']/GAMES:.2f}/game")
print()
print(f"  RESIDUAL BH opportunities per game    : {S['bh_behind']/GAMES:.3f}")
print(f"  RESIDUAL illegal passes per game      : {S['pass_rx_behind']/GAMES:.3f}")
