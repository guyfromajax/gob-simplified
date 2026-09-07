"""Driver for the fouled-3PT misaward probe. One process per (arm, seed), fresh DB per game.

Aggregates the acceptance evidence: misaward rate per arm, the per-shot branch join, the
and-one rows, the per-site award audit, and the prior-one_and_one no-op check.
"""
import json, os, subprocess, sys, tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

# shot_manager BLOCKING_FOUL branch: penalised under the team-foul bonus, not as a shot.
BLOCKING_FOUL_SITE = "shot_manager.py:1509"

SEEDS = list(range(8000, 8012))          # 12 games per arm, same seeds as the 16.9%/23.8% run
ARMS = ("played", "sim")
PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python")


def run(job):
    arm, seed = job
    out = tempfile.mktemp(suffix=f".{arm}.{seed}.json")
    env = dict(os.environ, PYTHONHASHSEED="0", ARM=arm, SEED=str(seed), OUT=out,
               MONGO_DB_NAME=f"gob-ft3-{arm}-{seed}")
    p = subprocess.run([PY, "scratch_ft3_run.py"], env=env, capture_output=True, text=True)
    if not os.path.exists(out):
        return {"arm": arm, "seed": seed, "error": (p.stderr or "")[-400:], "tally": {}}
    d = json.load(open(out))
    os.unlink(out)
    return d


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(run, [(a, s) for a in ARMS for s in SEEDS]))

    for r in res:
        if r.get("error"):
            print(f"  !! {r['arm']}/{r['seed']}: {r['error']}")

    for arm in ARMS:
        rows = [r for r in res if r["arm"] == arm and not r.get("error")]
        tally, join, award, oao = Counter(), Counter(), Counter(), Counter()
        for r in rows:
            tally.update(r.get("tally", {})); join.update(r.get("join", {}))
            award.update(r.get("award", {})); oao.update(r.get("oao_prior", {}))
        fa = sum(r.get("ft_att", 0) for r in rows); fm = sum(r.get("ft_made", 0) for r in rows)
        ok3, bad3 = tally.get("OK|3PT", 0), tally.get("MISAWARD|3PT", 0)
        ok2, bad2 = tally.get("OK|2PT", 0), tally.get("MISAWARD|2PT", 0)
        n3, n2 = ok3 + bad3, ok2 + bad2
        print(f"\n===== {arm.upper()}  ({len(rows)} games) =====")
        print(f"  fouled 3PT attempts : {n3:4d}   misawarded {bad3:3d}  = "
              f"{(100.0*bad3/n3 if n3 else 0):.1f}%")
        print(f"  fouled 2PT attempts : {n2:4d}   misawarded {bad2:3d}  = "
              f"{(100.0*bad2/n2 if n2 else 0):.1f}%")
        print(f"  free throws         : {fa} attempted, {fm} made = "
              f"{(100.0*fm/fa if fa else 0):.1f}%   ({fa/max(len(rows),1):.2f} FTA/game)")
        print("  -- rows (awarded vs expected) --")
        for k in sorted(k for k in tally if "|awarded=" in k):
            a = int(k.split("awarded=")[1].split("|")[0]); e = int(k.split("expected=")[1])
            print(f"     {'WRONG' if a != e else '  ok '}  {k}  n={tally[k]}")
        print("  -- per-shot branch join (shooting fouls) --")
        for k in sorted(join):
            got = k.split("free_throws=")[1].strip()
            if BLOCKING_FOUL_SITE in k:
                # bonus-penalised, not a shooting foul: 0 (below bonus) or 2 (1-and-1 / double)
                verdict = "  ok " if got in ("0", "2") else "WRONG"
                print(f"     {verdict}  [BONUS] {k}  n={join[k]}")
                continue
            exp = 1 if "made" in k.split("|")[2] else (3 if "3PT" in k else 2)
            print(f"     {'WRONG' if got != str(exp) else '  ok '}  {k}  n={join[k]}")
        print("  -- residual misaward examples --")
        for r in rows:
            for m in r.get("misaward_examples", []):
                print(f"     seed={r['seed']} turn={m['turn']} {m['result']} is3={m['is3']} "
                      f"awarded={m['awarded']} expected={m['expected']} "
                      f"near_quarter_end={m['near_quarter_end']} cur={m['current_turn']}")
        print("  -- award sites --")
        for k in sorted(award):
            print(f"     {k}  n={award[k]}")
        print("  -- prior one_and_one at each site (False/None => writing False is a no-op) --")
        for k in sorted(oao):
            print(f"     {k}  n={oao[k]}")
