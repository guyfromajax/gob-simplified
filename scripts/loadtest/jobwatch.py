#!/usr/bin/env python3
"""Poll a tagged franchise's CPU-sim job doc during a run. READ-ONLY (STAGING ONLY).

phase-b overwrites each matchup's completed_at, so the final job doc can't show
where start-cpu-sims' time went. The job IS persisted at known points, though:
  - all matchups -> "running" just before the pool starts (pool start)
  - every 10 completed games during the sequential persist loop (after the pool)
  - job completed_at at the end of start-cpu-sims
Sampling it once a second recovers the pre-pool / pool / persist / post split
without touching app code.

    ../gob-simplified/.venv/bin/python scripts/loadtest/jobwatch.py --franchise <id> --minutes 12 --out <dir>
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from bson import ObjectId

from common import FRANCHISE_PREFIX, connect_staging


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--franchise", required=True)
    p.add_argument("--minutes", type=float, default=12)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    conn = connect_staging("read")
    db = conn.database
    fid = ObjectId(a.franchise)
    end = time.time() + a.minutes * 60
    last = None
    with open(out / "jobwatch.jsonl", "a", buffering=1) as f:
        while time.time() < end:
            t = time.time()
            doc = db["franchises"].find_one({"_id": fid, "loadtest_name": {"$regex": f"^{FRANCHISE_PREFIX}"}},
                                            {"week": 1, "cpu_sim_jobs": 1}) or {}
            jobs = doc.get("cpu_sim_jobs") or {}
            wk = str(doc.get("week"))
            job = jobs.get(wk) or {}
            m = job.get("matchups") or {}
            rows = list(m.values()) if isinstance(m, dict) else list(m)
            snap = {
                "week": doc.get("week"),
                "status": job.get("status"), "phase": job.get("phase"),
                "running": sum(1 for r in rows if r.get("status") == "running"),
                "complete": sum(1 for r in rows if r.get("status") == "complete"),
                "completed_matchups": job.get("completed_matchups"),
                "job_started_at": job.get("started_at"), "job_completed_at": job.get("completed_at"),
                "claim_active": (job.get("claim") or {}).get("active"),
            }
            if snap != last:
                f.write(json.dumps({"t": round(t, 3), **snap}) + "\n")
                last = snap
            time.sleep(max(0.0, a.interval - (time.time() - t)))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
