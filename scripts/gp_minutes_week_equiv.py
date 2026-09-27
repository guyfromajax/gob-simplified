#!/usr/bin/env python3
"""Seeded one-week advance on a COPY of a SQLite save. MEASUREMENT ONLY.

Runs the user game + finalize_game + complete_week exactly like
scripts/season_advance_harness.py::advance_regular_week (training skipped), with
every CPU game seeded from its matchup and the thread engine pinned to one worker
so two code trees can be exact-diffed. The source save is never opened for write.

Run from the repo root you want to measure (PYTHONHASHSEED=0 required):

  PYTHONHASHSEED=0 python scripts/gp_minutes_week_equiv.py \
      --src "$HOME/Library/Application Support/GOB/local.sqlite" \
      --franchise 6ab284847ab3853ae89a1184 --work tmp/gpmin/after.sqlite \
      --out tmp/gpmin/after.json

  python scripts/gp_minutes_week_equiv.py --diff tmp/gpmin/before.json tmp/gpmin/after.json

``--weeks`` (default 2) advances that many weeks; a week whose CPU games were
pre-simmed in the save only rolls up the user game. ``--engine desktop`` keeps
the shipped spawn pool and skips seeding, for timing only (set
FRANCHISE_CPU_SIM_POOL_WORKERS when sysctl is unavailable).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import zlib
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

ALLOWED = {"GP", "MIN"}
BLOCKS = ("season", "career", "ps_season_stats")


def _configure(work: Path, engine: str) -> None:
    os.environ["GOB_SQLITE_PATH"] = str(work)
    from BackEnd.loopback_env import apply_loopback_env

    apply_loopback_env()
    if engine == "seeded":
        os.environ["FRANCHISE_CPU_SIM_USE_POOL"] = "0"
        os.environ["FRANCHISE_CPU_SIM_MAX_WORKERS"] = "1"
        os.environ["PS_SIM_USE_POOL"] = "0"


def _matchup_seed(base: int, week: int, a, b) -> int:
    key = f"{week}:{':'.join(sorted((str(a), str(b))))}"
    return base + zlib.crc32(key.encode())


def run(args) -> int:
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("set PYTHONHASHSEED=0")
    work = Path(args.work).resolve()
    work.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(str(work) + suffix).unlink(missing_ok=True)
    shutil.copy2(args.src, work)
    _configure(work, args.engine)

    import random

    from bson import ObjectId

    from BackEnd.db import db
    from BackEnd.api import franchise_routes as fr
    from BackEnd.utils import stat_updater, training_random

    random.seed(args.seed)
    training_random.seed(args.seed)

    fid = ObjectId(args.franchise)
    fdoc = db.franchises.find_one({"_id": fid})
    first_week = int(fdoc["week"])
    user_oid = ObjectId(fdoc["user_team_object_id"])
    current = {"week": first_week}

    core = fr._run_franchise_cpu_full_simulation_core

    def seeded_core(franchise_id, home_id, away_id, home_name, away_name, seed=None):
        return core(franchise_id, home_id, away_id, home_name, away_name,
                    seed=_matchup_seed(args.seed, current["week"], home_id, away_id))

    if args.engine == "seeded":
        fr._run_franchise_cpu_full_simulation_core = seeded_core

    fin = {"t": 0.0, "n": 0}
    orig_finalize = stat_updater.finalize_game

    def timed_finalize(*a, **k):
        t0 = time.perf_counter()
        try:
            return orig_finalize(*a, **k)
        finally:
            fin["t"] += time.perf_counter() - t0
            fin["n"] += 1

    stat_updater.finalize_game = timed_finalize

    preexisting = {str(g["_id"]) for g in db.games.find({"franchise_id": str(fid)}, {"_id": 1})}
    weeks = []
    for _ in range(args.weeks):
        fdoc = db.franchises.find_one({"_id": fid})
        week = int(fdoc["week"])
        current["week"] = week
        away_id = home_id = None
        for g in fdoc["schedule"][week - 1]:
            a, h = (g.get("away"), g.get("home")) if isinstance(g, dict) else (g[0], g[1])
            if str(a) == str(user_oid) or str(h) == str(user_oid):
                away_id, home_id = a, h
        names = {t["_id"]: t.get("name", "") for t in db.teams.find({"_id": {"$in": [away_id, home_id]}}, {"name": 1})}
        pre_simmed = db.games.count_documents({"franchise_id": str(fid), "week": week, "mode": None})

        fin["t"], fin["n"] = 0.0, 0
        t0 = time.perf_counter()
        away_s, home_s, summary = seeded_core(fid, home_id, away_id, names.get(home_id, ""), names.get(away_id, ""))
        gid = fr.generate_game_id()
        summary["_id"] = gid
        summary["franchise_id"] = str(fid)
        summary["week"] = week
        db.games.update_one({"_id": gid}, {"$set": summary}, upsert=True)
        timed_finalize(gid, mode="franchise", franchise_id=str(fid))
        fr.complete_week(fr.CompleteWeekRequest(
            franchise_id=str(fid), week=week,
            result=fr.GameResult(team1_id=str(away_id), team2_id=str(home_id),
                                 team1_score=away_s, team2_score=home_s),
            game_id=gid))
        weeks.append({
            "week": week,
            "pre_simmed_cpu_games": pre_simmed,
            "elapsed_s": time.perf_counter() - t0,
            "finalize_s": fin["t"],
            "finalize_n": fin["n"],
        })

    lines = {}
    for coll, key in (("franchise_players_data", "player_id"), ("franchise_recruits_data", "recruit_id")):
        for d in db[coll].find({"franchise_id": str(fid)}):
            lines[f"{coll}:{d.get(key)}"] = {b: d.get(b) or {} for b in BLOCKS}

    box_rows = []
    run_weeks = [w["week"] for w in weeks]
    for g in db.games.find({"franchise_id": str(fid), "week": {"$in": run_weeks}}):
        if str(g["_id"]) in preexisting:
            continue
        sources = [g.get("box_score") or {}]
        sources += [(t or {}).get("box_score") or {} for t in (g.get("teams") or {}).values()]
        seen = set()
        for team_box in sources:
            for team_rows in ([team_box] if any(isinstance(v, dict) and v.get("playerId") for v in team_box.values()) else team_box.values()):
                if not isinstance(team_rows, dict):
                    continue
                for row in team_rows.values():
                    if isinstance(row, dict) and row.get("playerId"):
                        k = (str(g["_id"]), str(row["playerId"]))
                        if k not in seen:
                            seen.add(k)
                            box_rows.append({"game": k[0], "mode": g.get("mode"), "pid": k[1], "sec": row.get("MIN", 0)})

    out = {
        "weeks": weeks,
        "new_week": int(db.franchises.find_one({"_id": fid}, {"week": 1})["week"]),
        "lines": lines,
        "box_rows": box_rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, default=str))
    print(json.dumps({"weeks": weeks, "new_week": out["new_week"]}))
    return 0


def diff(before_path: str, after_path: str) -> int:
    before = json.loads(Path(before_path).read_text())
    after = json.loads(Path(after_path).read_text())
    rows = after["box_rows"]
    zero_games: dict[str, int] = {}
    remainder: dict[str, float] = {}
    for r in rows:
        if r.get("mode") == "practice_squad":
            continue
        sec = r["sec"] or 0
        if sec <= 0:
            zero_games[r["pid"]] = zero_games.get(r["pid"], 0) + 1
        remainder[r["pid"]] = remainder.get(r["pid"], 0.0) + (sec / 60 - sec // 60)

    other_changes = []
    gp_drops = 0
    gp_mismatch = []
    min_mismatch = []
    changed_players = set()
    max_min_delta = 0.0
    keys = set(before["lines"]) | set(after["lines"])
    for key in sorted(keys):
        b = before["lines"].get(key, {})
        a = after["lines"].get(key, {})
        pid = key.split(":", 1)[1]
        for block in BLOCKS:
            bb, ab = b.get(block) or {}, a.get(block) or {}
            for stat in sorted(set(bb) | set(ab)):
                bv, av = bb.get(stat, 0), ab.get(stat, 0)
                if bv == av:
                    continue
                if stat not in ALLOWED:
                    other_changes.append((key, block, stat, bv, av))
                    continue
                changed_players.add(key)
                if block == "ps_season_stats":
                    continue
                if stat == "GP":
                    drop = bv - av
                    if block == "season":
                        gp_drops += drop
                    if drop != zero_games.get(pid, 0):
                        gp_mismatch.append((key, block, bv, av, zero_games.get(pid, 0)))
                else:
                    delta = av - bv
                    max_min_delta = max(max_min_delta, abs(delta))
                    if abs(delta - remainder.get(pid, 0.0)) > 1e-6:
                        min_mismatch.append((key, block, bv, av, remainder.get(pid, 0.0)))
        for stat in ("GP",):
            if (b.get("season") or {}).get(stat, 0) == (a.get("season") or {}).get(stat, 0) and zero_games.get(pid):
                gp_mismatch.append((key, "season", "unchanged", "", zero_games[pid]))

    summary = {
        "weeks": [w["week"] for w in after["weeks"]],
        "players_compared": len(keys),
        "players_changed": len(changed_players),
        "season_gp_drops": gp_drops,
        "zero_second_box_rows": sum(zero_games.values()),
        "max_min_delta": round(max_min_delta, 6),
        "other_stat_changes": len(other_changes),
        "gp_mismatches": len(gp_mismatch),
        "min_mismatches": len(min_mismatch),
    }
    print(json.dumps(summary, indent=2))
    for item in (other_changes + gp_mismatch + min_mismatch)[:20]:
        print("  ", item)
    return 0 if not (other_changes or gp_mismatch or min_mismatch) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--franchise")
    ap.add_argument("--work")
    ap.add_argument("--out")
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--weeks", type=int, default=2)
    ap.add_argument("--engine", choices=("seeded", "desktop"), default="seeded",
                    help="seeded: one thread, every game seeded (exact diffs). "
                         "desktop: shipped spawn pool, unseeded (timing).")
    ap.add_argument("--diff", nargs=2)
    args = ap.parse_args()
    if args.diff:
        return diff(*args.diff)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
