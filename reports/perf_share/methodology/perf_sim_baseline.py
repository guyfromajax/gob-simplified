"""
⏱️ SIM PERF BASELINE HARNESS — MEASUREMENT ONLY. Safe to delete.

Runs a full 63-game CPU week (and optionally Practice Squad games) headlessly by
calling the SAME functions the game calls:

  CPU : BackEnd.api.franchise_routes._run_franchise_cpu_full_simulation_core
  PS  : BackEnd.practice_squad.sim.run_ps_full_simulation

Neither of those writes to Mongo, and this harness adds no writes of its own, so
a run is read-only against the configured database.

Outputs (reports/perf/):
  phase_breakdown_<ts>.json   phase timings + per-game wall times
  refstats_<ts>.csv / .json   per-team reference stat set (the regression anchor)
  cprofile_<ts>.prof/.txt     function-level profile of a single game

Usage:
  python3 scripts/perf_sim_baseline.py --franchise <id> --week 7 --games 63
  python3 scripts/perf_sim_baseline.py --franchise <id> --games 2 --mode both
  python3 scripts/perf_sim_baseline.py --franchise <id> --games 63 --workers 4
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_DIR = REPO / "reports" / "perf"

# Team-total keys as the engine emits them (game.team_totals -> teams[tid]["totals"]).
_STAT_KEYS = [
    "PTS", "FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F",
]


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    try:
        return bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO, text=True
        ).strip())
    except Exception:
        return True


def _team_totals(tinfo: dict) -> dict:
    """
    Pull the engine's own team totals. Falls back to summing the box score if
    `totals` is ever absent, so the reference set never silently reads as zeros.
    """
    src = tinfo.get("totals") or {}
    if src:
        return {k: src.get(k, 0) or 0 for k in _STAT_KEYS}
    totals = {k: 0 for k in _STAT_KEYS}
    for _pos, row in (tinfo.get("box_score") or {}).items():
        if not isinstance(row, dict):
            continue
        for k in _STAT_KEYS:
            v = row.get(k)
            if isinstance(v, (int, float)):
                totals[k] += v
    if not totals.get("REB"):
        totals["REB"] = totals.get("OREB", 0) + totals.get("DREB", 0)
    return totals


def _possessions(t: dict) -> float:
    """Standard possessions estimate: FGA - OREB + TO + 0.44*FTA."""
    return round(
        t.get("FGA", 0) - t.get("OREB", 0) + t.get("TO", 0) + 0.44 * t.get("FTA", 0), 2
    )


def _pct(made, att):
    return round(100.0 * made / att, 2) if att else 0.0


def _row_from_summary(summary: dict, side: str, meta: dict) -> dict:
    """
    `summary["teams"]` is keyed by canonical team_id, not "home"/"away" — the
    side mapping comes from summary["home_team_id"] / ["away_team_id"].
    """
    summary = summary or {}
    teams = summary.get("teams") or {}
    tid = summary.get(f"{side}_team_id")
    tinfo = teams.get(tid) or {}
    if not tinfo:  # defensive: fall back to positional order
        vals = list(teams.values())
        idx = 0 if side == "home" else 1
        tinfo = vals[idx] if len(vals) > idx else {}
    t = _team_totals(tinfo)
    return {
        **meta,
        "side": side,
        "team": tinfo.get("name") or "",
        "team_id": tinfo.get("team_id") or tid or "",
        "final_score": tinfo.get("score", t.get("PTS", 0)),
        "possessions": _possessions(t),
        "FGM": t["FGM"], "FGA": t["FGA"], "FG_pct": _pct(t["FGM"], t["FGA"]),
        "TPM": t["3PTM"], "TPA": t["3PTA"], "TP_pct": _pct(t["3PTM"], t["3PTA"]),
        "FTM": t["FTM"], "FTA": t["FTA"], "FT_pct": _pct(t["FTM"], t["FTA"]),
        "TO": t["TO"], "OREB": t["OREB"], "DREB": t["DREB"], "REB": t["REB"],
        "AST": t["AST"], "STL": t["STL"], "BLK": t["BLK"], "PF": t["F"],
    }


# ---------------------------------------------------------------------------
# matchup resolution (mirrors _resolve_complete_week_week_games)
# ---------------------------------------------------------------------------

def resolve_matchups(franchise_id_str: str, week: int, limit: int):
    from bson import ObjectId
    from BackEnd.db import db, franchises_collection

    try:
        fid = ObjectId(franchise_id_str)
    except Exception:
        fid = franchise_id_str
    fdoc = franchises_collection.find_one({"_id": fid})
    if not fdoc:
        raise SystemExit(f"franchise {franchise_id_str} not found")

    schedule = fdoc.get("schedule") or []
    if week < 1 or week > len(schedule):
        raise SystemExit(f"week {week} out of range (schedule has {len(schedule)} weeks)")
    week_games = schedule[week - 1]

    user_team_id = fdoc.get("team_id") or fdoc.get("user_team_id")

    name_cache: dict = {}

    def name_of(tid):
        if tid not in name_cache:
            doc = db.teams.find_one({"_id": tid}, {"name": 1}) or {}
            name_cache[tid] = doc.get("name", "")
        return name_cache[tid]

    matchups = []
    for idx, g in enumerate(week_games):
        if isinstance(g, dict):
            away_id, home_id = g.get("away"), g.get("home")
        else:
            away_id, home_id = g[0], g[1]
        # production skips the user's own matchup (that game is played, not simmed)
        if user_team_id is not None and user_team_id in (away_id, home_id):
            continue
        matchups.append({
            "idx": idx,
            "away_id": away_id, "home_id": home_id,
            "away_name": name_of(away_id), "home_name": name_of(home_id),
        })
    return fid, matchups[:limit]


# ---------------------------------------------------------------------------
# runners
# ---------------------------------------------------------------------------

def run_cpu_game(fid, m):
    from BackEnd.api.franchise_routes import _run_franchise_cpu_full_simulation_core
    t0 = time.perf_counter()
    away_score, home_score, summary = _run_franchise_cpu_full_simulation_core(
        fid, m["home_id"], m["away_id"], m["home_name"], m["away_name"]
    )
    return time.perf_counter() - t0, away_score, home_score, summary


def resolve_ps_games(franchise_id_str: str, week: int, limit: int):
    """
    Replicate run_practice_squad_week's input prep, but WITHOUT its DB writes /
    standings mutation. Returns kwargs ready for run_ps_full_simulation.
    """
    from bson import ObjectId
    from BackEnd.db import (
        franchises_collection,
        franchise_players_data_collection,
        franchise_recruits_data_collection,
    )
    from BackEnd.practice_squad.manager import (
        _games_for_week, _resolve_team_roster, _update_scrubs_rosters,
    )

    try:
        fid = ObjectId(franchise_id_str)
    except Exception:
        fid = franchise_id_str
    fdoc = franchises_collection.find_one({"_id": fid}) or {}
    ps_state = dict(fdoc.get("practice_squad") or {})
    if not ps_state.get("initialized"):
        return []

    sfid = str(fid)
    fpd_by_id = {str(d["player_id"]): d
                 for d in franchise_players_data_collection.find({"franchise_id": sfid})}
    frd_by_id = {str(d["recruit_id"]): d
                 for d in franchise_recruits_data_collection.find({"franchise_id": sfid})}

    _update_scrubs_rosters(ps_state, week)
    teams = ps_state.get("teams") or {}

    jobs = []
    for g in _games_for_week(ps_state, week):
        home_id, away_id = g.get("home_team_id"), g.get("away_team_id")
        if not home_id or not away_id:
            continue
        home_roster = _resolve_team_roster(ps_state, str(home_id), week)
        away_roster = _resolve_team_roster(ps_state, str(away_id), week)
        if len(home_roster) < 5 or len(away_roster) < 5:
            continue
        ht = teams.get(str(home_id)) or {}
        at = teams.get(str(away_id)) or {}
        jobs.append({
            "home_display_name": ht.get("display_name") or str(home_id),
            "away_display_name": at.get("display_name") or str(away_id),
            "home_team_id": str(home_id), "away_team_id": str(away_id),
            "home_roster": home_roster, "away_roster": away_roster,
            "fpd_by_id": fpd_by_id, "frd_by_id": frd_by_id,
            "game_id": None,  # no persistence from the harness
        })
        if len(jobs) >= limit:
            break
    return jobs


def run_ps_game(job):
    from BackEnd.practice_squad.sim import run_ps_full_simulation
    t0 = time.perf_counter()
    away_score, home_score, summary = run_ps_full_simulation(**job)
    return time.perf_counter() - t0, away_score, home_score, summary


def summarize_phases(total_wall):
    from BackEnd.utils import sim_profiler
    snap = sim_profiler.snapshot()
    return snap, sim_profiler.format_table(snap, total_wall)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--franchise", required=True)
    ap.add_argument("--week", type=int, default=1)
    ap.add_argument("--games", type=int, default=63)
    ap.add_argument("--mode", choices=["cpu", "ps", "both"], default="cpu")
    ap.add_argument("--workers", type=int, default=1,
                    help="1 = sequential (clean phase attribution); >1 mirrors production ThreadPoolExecutor")
    ap.add_argument("--ps-franchise", default="",
                    help="franchise id for PS games (defaults to --franchise)")
    ap.add_argument("--ps-week", type=int, default=0,
                    help="week for PS games (defaults to --week)")
    ap.add_argument("--cprofile", action="store_true", help="also cProfile a single game")
    ap.add_argument("--no-profile", action="store_true", help="skip phase instrumentation")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    if not args.no_profile:
        os.environ["GOB_SIM_PROFILE"] = "1"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    commit = _git_commit()

    # import sim modules FIRST so profiler alias-rebinding sees their namespaces
    import BackEnd.api.franchise_routes  # noqa: F401
    import BackEnd.practice_squad.sim  # noqa: F401
    from BackEnd.utils import sim_profiler

    probes = sim_profiler.install()

    stat_rows: list[dict] = []
    batches: dict[str, dict] = {}

    def run_batch(kind, items, runner, label_of, workers):
        """Run one homogeneous batch of games with its own phase snapshot."""
        game_times: list[dict] = []
        failures: list[dict] = []

        def _record(item, dur, away_score, home_score, summary):
            meta = {
                "kind": kind, "matchup": label_of(item), "wall_s": round(dur, 4),
            }
            game_times.append({**meta, "away_score": away_score, "home_score": home_score})
            for side in ("home", "away"):
                stat_rows.append(_row_from_summary(summary, side, meta))

        sim_profiler.reset()
        wall0 = time.perf_counter()
        if workers <= 1:
            for i, item in enumerate(items, 1):
                try:
                    dur, a, h, s = runner(item)
                    _record(item, dur, a, h, s)
                    print(f"  [{kind} {i:>3}/{len(items)}] {dur:6.2f}s  {label_of(item)}  {a}-{h}",
                          file=sys.stderr)
                except Exception as e:
                    failures.append({"matchup": label_of(item), "err": f"{type(e).__name__}: {e}"})
                    print(f"  [{kind} {i:>3}] FAILED {type(e).__name__}: {e}", file=sys.stderr)
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = {ex.submit(runner, item): item for item in items}
                done = 0
                for fut in as_completed(futs):
                    item = futs[fut]
                    done += 1
                    try:
                        dur, a, h, s = fut.result()
                        _record(item, dur, a, h, s)
                        print(f"  [{kind} {done:>3}/{len(items)}] {dur:6.2f}s  "
                              f"{label_of(item)}  {a}-{h}", file=sys.stderr)
                    except Exception as e:
                        failures.append({"matchup": label_of(item),
                                         "err": f"{type(e).__name__}: {e}"})
                        print(f"  [{kind} {done:>3}] FAILED {type(e).__name__}: {e}",
                              file=sys.stderr)
        total_wall = time.perf_counter() - wall0
        snap = sim_profiler.snapshot()
        durs = sorted(g["wall_s"] for g in game_times)
        timing = {
            "games": len(durs),
            "total_wall_s": round(total_wall, 3),
            "sum_game_s": round(sum(durs), 3),
            "min_s": durs[0] if durs else None,
            "median_s": round(statistics.median(durs), 3) if durs else None,
            "mean_s": round(statistics.mean(durs), 3) if durs else None,
            "p90_s": round(durs[int(len(durs) * 0.9)], 3) if len(durs) > 2 else None,
            "max_s": durs[-1] if durs else None,
        }
        batches[kind] = {
            "workers": workers, "timing": timing, "phases": snap,
            "per_game": game_times, "failures": failures,
            "table": sim_profiler.format_table(snap, total_wall),
        }
        print(f"\n=== {kind} phase breakdown ===\n"
              + batches[kind]["table"], file=sys.stderr)
        return batches[kind]

    if args.mode in ("cpu", "both"):
        fid, matchups = resolve_matchups(args.franchise, args.week, args.games)
        print(f"▶ CPU franchise={args.franchise} week={args.week} "
              f"matchups={len(matchups)} workers={args.workers} commit={commit[:9]}",
              file=sys.stderr)
        run_batch("cpu_full", matchups, lambda m: run_cpu_game(fid, m),
                  lambda m: f"{m['away_name']} @ {m['home_name']}", args.workers)

    if args.mode in ("ps", "both"):
        ps_jobs = resolve_ps_games(args.ps_franchise or args.franchise,
                                   args.ps_week or args.week, args.games)
        print(f"▶ PS jobs={len(ps_jobs)}", file=sys.stderr)
        if ps_jobs:
            run_batch("practice_squad", ps_jobs, run_ps_game,
                      lambda j: f"{j['away_display_name']} @ {j['home_display_name']}",
                      args.workers)

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "git_commit": commit,
        "git_dirty": _git_dirty(),
        "franchise_id": args.franchise, "week": args.week,
        "mode": args.mode, "workers": args.workers,
        "probes_installed": len(probes),
        "python": sys.version.split()[0],
        "host": os.uname().sysname + " " + os.uname().machine,
        "batches": batches,
    }
    suffix = f"{args.tag + '_' if args.tag else ''}{ts}"
    pj = OUT_DIR / f"phase_breakdown_{suffix}.json"
    pj.write_text(json.dumps(payload, indent=2, default=str))

    # reference stat set
    rj = OUT_DIR / f"refstats_{suffix}.json"
    rj.write_text(json.dumps({
        "generated_at": payload["generated_at"], "git_commit": commit,
        "git_dirty": payload["git_dirty"],
        "franchise_id": args.franchise, "week": args.week,
        "rows": stat_rows,
    }, indent=2, default=str))
    rc = OUT_DIR / f"refstats_{suffix}.csv"
    if stat_rows:
        with rc.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(stat_rows[0].keys()))
            w.writeheader()
            w.writerows(stat_rows)

    for kind, b in batches.items():
        print(f"\n{kind} timing: {json.dumps(b['timing'], indent=2)}", file=sys.stderr)
    print(f"\n📄 {pj}\n📄 {rj}\n📄 {rc}", file=sys.stderr)

    # optional cProfile of a single game (CPU path)
    if args.cprofile:
        import cProfile, pstats
        fid2, mm = resolve_matchups(args.franchise, args.week, 1)
        if not mm:
            print("⚠️ no matchup available for cProfile", file=sys.stderr)
            return
        prof_path = OUT_DIR / f"cprofile_{suffix}.prof"
        txt_path = OUT_DIR / f"cprofile_{suffix}.txt"
        pr = cProfile.Profile()
        pr.enable()
        run_cpu_game(fid2, mm[0])
        pr.disable()
        pr.dump_stats(str(prof_path))
        with txt_path.open("w") as fh:
            st = pstats.Stats(pr, stream=fh)
            fh.write("=== BY CUMULATIVE TIME (top 80) ===\n")
            st.sort_stats("cumulative").print_stats(80)
            fh.write("\n\n=== BY TOTAL (SELF) TIME (top 80) ===\n")
            st.sort_stats("tottime").print_stats(80)
        print(f"📄 {prof_path}\n📄 {txt_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
