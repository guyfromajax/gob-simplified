"""
Worker-kill recovery test (amendment 2).

Runs a seeded pooled week, kills a live worker process mid-run to force a
BrokenProcessPool, and confirms:
  1. the week still completes (no hung gate),
  2. every game has a result (retry ladder recovered the incomplete ones),
  3. results are byte-identical to a clean sequential seeded run — i.e. the
     recovered games are correct, not random fallback.

The kill is driven from a sidecar thread that watches the pool's child PIDs and
SIGKILLs one shortly after the run starts.
"""
import logging
import os
import pathlib
import signal
import sys
import threading
import time

logging.basicConfig(level=logging.WARNING, format="LADDER %(levelname)s %(message)s",
                    stream=sys.stderr)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from bson import ObjectId
from BackEnd.db import franchises_collection, db
from BackEnd.utils.cpu_week_pool import simulate_cpu_week_pooled

SEED = 20260720
N = 8


def build_jobs():
    fid = ObjectId("6a28436c98dbd04e902eee09")
    f = franchises_collection.find_one({"_id": fid})
    jobs = []
    for i, g in enumerate(f["schedule"][6]):
        if len(jobs) >= N:
            break
        aid, hid = (g["away"], g["home"]) if isinstance(g, dict) else (g[0], g[1])
        an = (db.teams.find_one({"_id": aid}, {"name": 1}) or {}).get("name", "")
        hn = (db.teams.find_one({"_id": hid}, {"name": 1}) or {}).get("name", "")
        jobs.append((i, fid, hid, aid, hn, an))
    return fid, jobs


def canon(results):
    return [(i, results[i][0], results[i][1]) for i in sorted(results)]


def _busiest_child(parent_pid):
    """The child burning the most CPU = a worker mid-game (not the idle
    resource_tracker or a spawn helper)."""
    try:
        kids = [int(p) for p in os.popen(f"pgrep -P {parent_pid}").read().split()]
    except Exception:
        return None
    best, best_cpu = None, -1.0
    for pid in kids:
        try:
            cpu = float(os.popen(f"ps -o %cpu= -p {pid}").read().strip() or "0")
        except Exception:
            cpu = 0.0
        if cpu > best_cpu:
            best, best_cpu = pid, cpu
    return best if best_cpu > 5.0 else None  # >5% = actually running a game


def killer(parent_pid, fired):
    """SIGKILL the worker that is actively running a game."""
    deadline = time.time() + 40
    while time.time() < deadline:
        pid = _busiest_child(parent_pid)
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
                fired.append(pid)
                print(f"  💥 SIGKILL busy worker pid={pid}", file=sys.stderr)
            except ProcessLookupError:
                pass
            return
        time.sleep(0.3)


def main():
    fid, jobs = build_jobs()

    # clean sequential reference
    from BackEnd.api.franchise_routes import _run_franchise_cpu_full_simulation_core
    ref = {}
    for (idx, fid_, hid, aid, hn, an) in jobs:
        a, h, _ = _run_franchise_cpu_full_simulation_core(fid_, hid, aid, hn, an, seed=SEED + idx)
        ref[idx] = (a, h, None)
    print(f"reference (sequential, seeded): {len(ref)} games", file=sys.stderr)

    fired = []
    t = threading.Thread(target=killer, args=(os.getpid(), fired), daemon=True)
    t.start()

    t0 = time.time()
    results, errors, leaks = simulate_cpu_week_pooled(
        jobs, seed_base=SEED, max_workers=4, collect_guard=True)
    dt = time.time() - t0

    print(f"\nworker killed: {fired or 'NONE (test inconclusive)'}", file=sys.stderr)
    print(f"completed in {dt:.1f}s  results={len(results)}/{len(jobs)}  errors={len(errors)}",
          file=sys.stderr)

    ok_complete = len(results) == len(jobs) and not errors
    ok_correct = canon(results) == canon(ref)
    worker_leaks = {i: v for i, v in leaks.items() if v}

    print(f"\n[1] week completed, all games present : {'✅' if ok_complete else '❌'}", file=sys.stderr)
    print(f"[2] results == clean sequential ref   : {'✅' if ok_correct else '❌'}", file=sys.stderr)
    print(f"[3] worker RNG leaks                  : {'✅ none' if not worker_leaks else '❌ ' + str(worker_leaks)}",
          file=sys.stderr)
    if not ok_correct:
        for i in sorted(ref):
            if i not in results:
                print(f"    missing game {i}", file=sys.stderr)
            elif results[i][:2] != ref[i][:2]:
                print(f"    game {i}: pool={results[i][:2]} ref={ref[i][:2]}", file=sys.stderr)

    ok = bool(fired) and ok_complete and ok_correct and not worker_leaks
    print(f"\n{'✅ PASS' if ok else '❌ FAIL'}", file=sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
