"""PART A driver: one process per (arm, seed), fresh DB per game. Aggregates and reports."""
import json, os, subprocess, tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

SEEDS = list(range(8000, 8012))
ARMS = tuple((os.environ.get("ARMS") or "played,sim").split(","))
PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python")


def run(job):
    arm, seed = job
    out = tempfile.mktemp(suffix=f".{arm}.{seed}.json")
    env = dict(os.environ, PYTHONHASHSEED="0", ARM=arm, SEED=str(seed), OUT=out,
               MONGO_DB_NAME=f"gob-else-{arm}-{seed}-{os.environ.get('SPOT_FIX','0')}")
    p = subprocess.run([PY, "scratch_elsebranch_run.py"], env=env, capture_output=True, text=True)
    if not os.path.exists(out):
        return {"arm": arm, "seed": seed, "error": (p.stderr or "")[-500:]}
    d = json.load(open(out)); os.unlink(out)
    return d


def merge_summ(rows, key, branch):
    """Pool the per-game distributions rather than averaging medians."""
    ns, tot, mx, p95s = 0, 0.0, 0.0, []
    for r in rows:
        s = (r.get(key) or {}).get(branch)
        if not s:
            continue
        ns += s["n"]; tot += s["mean"] * s["n"]; mx = max(mx, s["max"]); p95s.append(s["p95"])
    if not ns:
        return None
    return {"n": ns, "mean": round(tot / ns, 1), "max": round(mx, 1),
            "p95_of_game_p95s": round(sorted(p95s)[len(p95s) // 2], 1)}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(run, [(a, s) for a in ARMS for s in SEEDS]))
    for r in res:
        if r.get("error"):
            print(f"  !! {r['arm']}/{r['seed']}: {r['error']}")

    for arm in ARMS:
        rows = [r for r in res if r["arm"] == arm and not r.get("error")]
        if not rows:
            continue
        g = len(rows)
        br, pos, act, trn, nb, vf, cp, ts, pay = (Counter() for _ in range(9))
        CB = ("ELSE_SPOT_IGNORED", "ELSE_NOTHING_AUTHORED", "LOCATION_MISS", "SPOT_MISS")
        for r in rows:
            br.update(r["branch"]); pos.update(r["by_pos"]); act.update(r["by_action"])
            trn.update(r["by_turn"]); nb.update(r["neighbour"]); vf.update(r["verify"])
            cp.update(r["centre_players"]); ts.update(r["turns_seen"])
            pay.update(r.get("payload", {}))
        total = sum(v for k, v in br.items() if not k.startswith("probe-error"))

        print(f"\n{'='*78}\n{arm.upper()}  —  {g} games, {sum(ts.values())} animation builds, "
              f"{total} pos_actions resolved\n{'='*78}")
        if any(k.startswith("probe-error") for k in br):
            print("  PROBE ERRORS:", {k: v for k, v in br.items() if k.startswith("probe-error")})
        print("  classifier self-check vs produced coords:",
              {k: v for k, v in vf.items() if not k.startswith("disagree->")} or "no overlap")

        print("\n  BRANCH SPLIT (all offensive pos_actions)")
        for b in ("COORDS", "LOCATION_OK", "SPOT_OK", "LOCATION_MISS", "SPOT_MISS", "ELSE_SPOT_IGNORED", "ELSE_NOTHING_AUTHORED"):
            n = br.get(b, 0)
            print(f"     {b:14s} {n:7d}  {100.0*n/max(total,1):5.1f}%   {n/g:8.1f} per game")

        CB = ("ELSE_SPOT_IGNORED", "ELSE_NOTHING_AUTHORED", "LOCATION_MISS", "SPOT_MISS")
        centre = sum(br.get(b, 0) for b in CB)
        print(f"     {'-> CENTRE':14s} {centre:7d}  {100.0*centre/max(total,1):5.1f}%   "
              f"{centre/g:8.1f} per game")

        print("\n  (a) SHOOTER vs OFF-BALL — the question that gates Part B")
        for b in CB:
            for role in ("SHOOTER", "offball"):
                n = sum(v for k, v in pos.items() if k.startswith(f"{b}|{role}|"))
                den = sum(v for k, v in pos.items() if f"|{role}|" in k)
                print(f"     {b:14s} {role:8s} {n:6d} of {den:6d} "
                      f"({100.0*n/max(den,1):5.1f}%)  {n/g:7.1f} per game")

        print("\n  (b) POSITIONS")
        for b in CB:
            items = sorted(((k.split("|")[2], v) for k, v in pos.items() if k.startswith(f"{b}|")),
                           key=lambda kv: -kv[1])
            agg = Counter()
            for p, v in items:
                agg[p] += v
            if agg:
                print(f"     {b}: " + ", ".join(f"{p}={v}" for p, v in agg.most_common()))

        print("\n  (b) ACTION TYPES")
        for b in CB:
            agg = Counter()
            for k, v in act.items():
                if k.startswith(f"{b}|"):
                    agg[k.split("|")[2]] += v
            if agg:
                print(f"     {b}: " + ", ".join(f"{a}={v}" for a, v in agg.most_common(10)))

        print("\n  (c) DISPLACEMENT from the previous authored spot (grid units; court is 100x50)")
        for b in CB:
            print(f"     {b:14s} jump IN  {merge_summ(rows, 'displace_in', b)}")
            print(f"     {b:14s} jump OUT {merge_summ(rows, 'displace_out', b)}")
        print("     neighbours authored (is it a HOLE mid-journey or a leading/trailing gap?)")
        for k, v in sorted(nb.items()):
            print(f"        {k}  n={v}")

        print("\n  DOES IT REACH THE CLIENT? (the question that decides whether Part B is blocked)")
        for k in sorted(pay):
            print(f"     {k:42s} {pay[k]:7d}   {pay[k]/g:8.1f} per game")

        print("\n  (d) CONCENTRATION BY TURN TYPE")
        print(f"     builds per turn type: {dict(ts.most_common())}")
        for b in CB:
            agg = Counter()
            for k, v in trn.items():
                if k.startswith(f"{b}|"):
                    agg[k.split("|")[2]] += v
            if agg:
                print(f"     {b}: " + ", ".join(f"{t}={v}" for t, v in agg.most_common()))

    print(f"\n{'='*78}\nEXAMPLES (played)\n{'='*78}")
    for r in res:
        if r["arm"] != "played" or r.get("error"):
            continue
        for e in r.get("examples", [])[:6]:
            print(f"  {e['branch']:13s} {e['turn_type']:12s} {e['position']:3s} {e['role']:8s} "
                  f"step {e['step']}/{e['of']} action={e['action']:10s} "
                  f"loc={e['location']} keys={e['keys']} jump_in={e['jump_in']}")
        break
