"""
Pool scaling benchmark. For each worker count: run the full CPU week through the
process pool, timing from BEFORE pool creation (so cold spawn + imports are
included, which production pays per advance-week), and sample peak per-worker RSS.

usage: PYTHONHASHSEED=0 python3 bench_pool.py <worker_counts csv> <repeats>
"""
import os
import pathlib
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from bson import ObjectId
from BackEnd.db import franchises_collection, db
from BackEnd.utils.cpu_week_pool import simulate_cpu_week_pooled

WORKERS = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "1,4,8,12").split(",")]
REPEATS = int(sys.argv[2]) if len(sys.argv) > 2 else 1


def build_jobs():
    fid = ObjectId("6a28436c98dbd04e902eee09")
    f = franchises_collection.find_one({"_id": fid})
    user_tid = f.get("team_id")
    jobs = []
    for i, g in enumerate(f["schedule"][6]):
        aid, hid = (g["away"], g["home"]) if isinstance(g, dict) else (g[0], g[1])
        if user_tid is not None and user_tid in (aid, hid):
            continue
        an = (db.teams.find_one({"_id": aid}, {"name": 1}) or {}).get("name", "")
        hn = (db.teams.find_one({"_id": hid}, {"name": 1}) or {}).get("name", "")
        jobs.append((len(jobs), fid, hid, aid, hn, an))
    return jobs


def sample_rss(parent_pid, stop, peaks):
    """Peak RSS (MB) per child pid, sampled while the pool runs."""
    while not stop.is_set():
        try:
            kids = os.popen(f"pgrep -P {parent_pid}").read().split()
            for pid in kids:
                out = os.popen(f"ps -o rss= -p {pid}").read().strip()
                if out:
                    mb = int(out) / 1024.0
                    peaks[pid] = max(peaks.get(pid, 0.0), mb)
        except Exception:
            pass
        time.sleep(0.5)


def main():
    jobs = build_jobs()
    print(f"jobs={len(jobs)}  workers={WORKERS}  repeats={REPEATS}  "
          f"cores={os.cpu_count()}  PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED')}",
          file=sys.stderr)
    print(f"\n{'workers':>8}{'wall_s':>10}{'games/s':>10}{'speedup':>9}"
          f"{'peak_rss_mb':>13}{'n_children':>11}", file=sys.stderr)
    print("-" * 61, file=sys.stderr)

    base = None
    for w in WORKERS:
        walls, rss_peaks_all = [], []
        for _ in range(REPEATS):
            peaks = {}
            stop = threading.Event()
            t = threading.Thread(target=sample_rss, args=(os.getpid(), stop, peaks), daemon=True)
            t.start()
            t0 = time.perf_counter()  # includes cold pool creation
            results, errors, _ = simulate_cpu_week_pooled(
                jobs, seed_base=None, max_workers=w)
            dt = time.perf_counter() - t0
            stop.set(); t.join(timeout=2)
            walls.append(dt)
            if peaks:
                rss_peaks_all.append(max(peaks.values()))
            if errors:
                print(f"  ⚠️ {len(errors)} errors at workers={w}", file=sys.stderr)
        wall = sorted(walls)[len(walls) // 2]  # median
        peak_rss = max(rss_peaks_all) if rss_peaks_all else 0.0
        if base is None:
            base = wall
        print(f"{w:>8}{wall:>10.1f}{len(jobs)/wall:>10.2f}{base/wall:>8.2f}x"
              f"{peak_rss:>13.0f}{'':>11}", file=sys.stderr)


if __name__ == "__main__":
    main()
