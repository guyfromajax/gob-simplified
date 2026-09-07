"""Are two arms run in ONE process independent?

Suspicion, from the ordering probe: the poisoned arm's outcome fingerprint tracked its
POSITION in the process rather than what it did. Run 1 (sim, played, poison) and run 3
(sim, played, poison-values) both gave seed 8000 -> fadb4132258776c3 for the third arm,
despite entirely different poison mechanisms; run 2, where poison was the FOURTH arm,
gave c3fb1ed17fbf7d3b. Two different interventions producing byte-identical games, and
one identical intervention producing different games, is only possible if the arm's
result depends on something carried over between arms.

Likely carrier: the mongomock database. GameManager persists team/player state, and every
arm in these probes runs against the same DB.

TEST: run the IDENTICAL arm three times in one process, changing nothing. If the three
fingerprints differ, arms are not independent and every multi-arm figure measured this way
-- including the equiv-v2 divergence numbers and the FT attribution -- is contaminated.
"""
import os, sys, json, hashlib, random as _stdlib

os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get("PYTHONHASHSEED") != "0":
    raise SystemExit("run with PYTHONHASHSEED=0")

from BackEnd.db import players_collection, teams_collection
from tests.roster_fixtures import seed_universal_rosters
seed_universal_rosters(teams_collection, players_collection)

from BackEnd.utils import sim_random, training_random
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
import BackEnd.utils.sim_random as SR

DRAWS = [0]
for _m in ("random", "randint", "choice", "uniform", "randrange", "shuffle", "sample"):
    if hasattr(SR.sim_rng, _m):
        _o = getattr(SR.sim_rng, _m)

        def _mk(o=_o):
            def c(*a, **k):
                DRAWS[0] += 1
                return o(*a, **k)
            return c
        setattr(SR.sim_rng, _m, _mk())


def fp(turns, gm):
    rows = [(str(t.get("result_type") or ""), str(t.get("next_turn") or "")) for t in turns]
    blob = json.dumps({"n": len(rows), "rows": rows}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16], len(rows)


def run(label, games=2):
    DRAWS[0] = 0
    out = []
    for g in range(games):
        sim_random.seed(8000 + g)
        training_random.seed(8000 + g)
        _stdlib.seed(8000 + g)
        gm = GameManager("Lancaster", "Bentley-Truman")
        d = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2,
             "hc_trap": 5, "fc_press": 5}
        gm.home_team.strategy_settings = d.copy()
        gm.away_team.strategy_settings = d.copy()
        for _q in range(4):
            try:
                simulate_quarter(gm, game_id="%024x" % (0xC0000 + g))
            except Exception as e:
                print(f"   {label} seed {8000+g}: {type(e).__name__}: {e}")
                break
        out.append(fp(gm.turns or [], gm))
    print(f"  {label:<12} draws={DRAWS[0]:>9,}  " +
          "  ".join(f"seed{8000+i}={h}({n})" for i, (h, n) in enumerate(out)))
    return out, DRAWS[0]


if __name__ == "__main__":
    print("Running the IDENTICAL arm three times in one process. Nothing differs.\n")
    a, da = run("pass-1")
    b, db_ = run("pass-2")
    c, dc = run("pass-3")
    print("\n" + "=" * 74)
    ok = (a == b == c) and (da == db_ == dc)
    if ok:
        print("✅ ARMS ARE INDEPENDENT — identical fingerprints and draw counts.")
        print("   Multi-arm-in-one-process measurement is sound.")
    else:
        print("❌ ARMS ARE NOT INDEPENDENT.")
        print(f"   fingerprints equal: 1v2={a==b}  1v3={a==c}  2v3={b==c}")
        print(f"   draw counts: {da:,} / {db_:,} / {dc:,}")
        print("   State carries over between arms, so an arm's result depends on its")
        print("   POSITION in the process. Every multi-arm figure measured this way is")
        print("   contaminated and must be re-measured with one arm per process.")
