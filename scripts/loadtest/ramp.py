#!/usr/bin/env python3
"""Phase 2 ramp (STAGING ONLY). Do not run without Jamie's go-ahead (shared Atlas cluster).

Steps N = 1,5,10,15,20,30,40,60 concurrent franchises (users 1..N, seeded beforehand
with seed.py --n <max>), each running --weeks weeks at --mix sim fraction; 60 s pause
between steps. Stops at the FIRST hit of:
  - p95 week wall time > 3x the N=1 step's p95
  - 5xx rate > 1% of requests in the step
  - any request > 120 s (excluding fire-and-forget start-cpu-sims unless
    --count-cpu-sims-in-slow-rule; it is recorded either way)
  - the deployed commit changes during a step (a deploy restarts the process), or
    /health stops answering
  - a manual stop: touch scripts/loadtest/.state/STOP (e.g. Jamie sees memory > 80%)

    ../gob-simplified/.venv/bin/python scripts/loadtest/ramp.py --steps 1,5,10,15,20,30,40,60
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from datetime import datetime, timezone

import httpx

from common import STAGING_BASE_URL, STATE_DIR, load_users, require_staging_url
from run import REPORTS, run_step

STOP_FILE = STATE_DIR / "STOP"


def deployed_commit() -> str | None:
    try:
        r = httpx.get(require_staging_url(STAGING_BASE_URL) + "/health", timeout=20)
        return r.json().get("commit")
    except Exception:
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--steps", default="1,5,10,15,20,30,40,60")
    p.add_argument("--weeks", type=int, default=2)
    p.add_argument("--mix", type=float, default=0.7)
    p.add_argument("--pause", type=float, default=60.0)
    p.add_argument("--turn-think", type=float, default=0.0)
    p.add_argument("--count-cpu-sims-in-slow-rule", action="store_true")
    args = p.parse_args()

    steps = [int(x) for x in args.steps.split(",") if x.strip()]
    users_all = [u for u in load_users() if u.get("franchise_id")]
    if len(users_all) < max(steps):
        raise SystemExit(f"seed at least {max(steps)} users first (have {len(users_all)})")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ramp_dir = REPORTS / f"{stamp}-ramp"
    ramp_dir.mkdir(parents=True, exist_ok=True)
    table, baseline_p95, stop_reason = [], None, None
    rng = random.Random(7)

    for i, n in enumerate(steps):
        if STOP_FILE.exists():
            stop_reason = "manual STOP file"
            break
        users = users_all[:n]
        plans = {u["n"]: ["sim" if rng.random() < args.mix else "played" for _ in range(args.weeks)] for u in users}
        commit_before = deployed_commit()
        summary = asyncio.run(run_step(users, lambda u: plans[u["n"]], label=f"ramp-n{n}",
                                       turn_think=args.turn_think, out_dir=ramp_dir / f"n{n:03d}"))
        commit_after = deployed_commit()
        eps = summary["endpoints"]
        # slowest single request, with/without the fire-and-forget CPU slate
        req_rows = [json.loads(l) for l in open(ramp_dir / f"n{n:03d}" / "requests.jsonl")]
        considered = [r for r in req_rows if args.count_cpu_sims_in_slow_rule or r["step"] != "start-cpu-sims"]
        max_req = max((r["latency_s"] for r in considered), default=0)
        row = {
            "N": n, "t_start": summary["t_start_iso"], "t_end": summary["t_end_iso"],
            "weeks": summary["weeks"], "weeks_ok": summary["weeks_ok"],
            "week_p50": summary["week_wall_s"]["p50"], "week_p95": summary["week_wall_s"]["p95"],
            "week_max": summary["week_wall_s"]["max"],
            "p95_by_endpoint": {k: v["p95"] for k, v in eps.items()},
            "n429": summary["n429"], "n5xx": summary["n5xx"], "rate_5xx": summary["rate_5xx"],
            "transport_errors": summary["n_transport_errors"],
            "max_request_s_rule": max_req, "max_request_s_all": summary["max_request_s"],
            "commit_before": commit_before, "commit_after": commit_after,
        }
        table.append(row)
        (ramp_dir / "ramp.json").write_text(json.dumps(table, indent=2))
        print(json.dumps({k: row[k] for k in row if k != "p95_by_endpoint"}))

        if i == 0:
            baseline_p95 = row["week_p95"]
        if commit_before is None or commit_after is None or commit_before != commit_after:
            stop_reason = f"deploy/restart during step N={n} ({commit_before} -> {commit_after})"
        elif summary["rate_5xx"] > 0.01:
            stop_reason = f"5xx rate {summary['rate_5xx']:.2%} > 1% at N={n}"
        elif max_req > 120:
            stop_reason = f"request took {max_req:.0f}s (> 120 s) at N={n}"
        elif baseline_p95 and row["week_p95"] and row["week_p95"] > 3 * baseline_p95:
            stop_reason = f"p95 week {row['week_p95']}s > 3x baseline {baseline_p95}s at N={n}"
        elif summary["weeks_ok"] < summary["weeks"]:
            stop_reason = f"{summary['weeks'] - summary['weeks_ok']} week(s) failed at N={n}"
        if stop_reason:
            break
        if i < len(steps) - 1:
            time.sleep(args.pause)

    result = {"baseline_p95": baseline_p95, "stop_reason": stop_reason or "completed all steps", "steps": table}
    (ramp_dir / "ramp.json").write_text(json.dumps(result, indent=2))
    print(f"\nSTOP: {result['stop_reason']}\nresults: {ramp_dir}/ramp.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
