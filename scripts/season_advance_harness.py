#!/usr/bin/env python3
"""Headless season-advance harness — drives ONE franchise through the FULL season
(regular 1-26 → postseason 27-34 → recruiting 35 → rollover 36) for N seasons,
in-process (no HTTP server, no auth), then lands at season+1 week 1.

Parameterised for N seasons (``--seasons N``); N=1 is just the loop run once.

Week map (BackEnd/tournament/franchise_tournament.py):
  1-26  regular season   → complete_week (auto-seeds conference brackets after wk26)
  27-34 EOS tournament    → sim_rest_of_tournament (NOT complete_week: it 409s once the
                            user team is eliminated; the bracket driver sims all 128)
  35    recruiting        → _run_week_35_signings + set week=36 (auth-bypass impl path)
  36    rollover          → finish_season (develop_rollover per returning + signed)

⚠️  MUTATES the target franchise (advances its season). Guarded to gob-staging only.
Postseason weeks 27-34 have NEVER been driven headless before this harness.
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

REGULAR_SEASON_LAST_WEEK = 26
EOS_LAST_WEEK = 34


def _abort(msg: str):
    print(f"❌ ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def _lazy_imports():
    from bson import ObjectId
    from BackEnd.db import db, franchises_collection
    from BackEnd.utils import stat_updater
    from BackEnd.api import franchise_routes as fr
    return ObjectId, db, franchises_collection, stat_updater, fr


def _resolve_user_matchup(fdoc, week, user_team_oid):
    """Find the user team's matchup in schedule[week-1]; return (away_id, home_id)."""
    schedule = fdoc.get("schedule", [])
    if week - 1 >= len(schedule):
        return None
    for g in schedule[week - 1]:
        away_id, home_id = (g.get("away"), g.get("home")) if isinstance(g, dict) else (g[0], g[1])
        if away_id == user_team_oid or home_id == user_team_oid:
            return away_id, home_id
    return None


def advance_regular_week(fr, db, stat_updater, fid, week, user_team_oid, fdoc):
    """One regular-season week: train (user + CPU autotrain) → user game → complete_week.
    Returns the new week. Mirrors scripts/eog_measurement_season.py."""
    from bson import ObjectId
    matchup = _resolve_user_matchup(fdoc, week, user_team_oid)
    if matchup is None:
        _abort(f"no user matchup in schedule for week {week}")
    away_id, home_id = matchup
    away_name = (db.teams.find_one({"_id": away_id}, {"name": 1}) or {}).get("name", "")
    home_name = (db.teams.find_one({"_id": home_id}, {"name": 1}) or {}).get("name", "")

    # 1. training (best-effort). run_franchise_training(phase=full) also fires CPU
    #    auto-train for all 128 teams — now the reference allocation.
    try:
        alloc = fr.generate_random_training_allocations(30 if week == 1 else 24)
        alloc["coaching_focus"] = fr.generate_random_coaching_focus()
        fr.run_franchise_training(fr.FranchiseTrainingRequest(
            franchise_id=str(fid), team_id=str(user_team_oid), training_data=alloc))
    except Exception as e:  # noqa: BLE001
        print(f"    week {week}: training skipped ({type(e).__name__}: {e})")

    # 2. user game with a finalized box score
    away_s, home_s, summary = fr._run_franchise_cpu_full_simulation_core(
        fid, home_id, away_id, home_name, away_name)
    gid = fr.generate_game_id()
    summary["_id"] = gid; summary["franchise_id"] = str(fid); summary["week"] = week
    db.games.update_one({"_id": gid}, {"$set": summary}, upsert=True)
    stat_updater.finalize_game(gid, mode="franchise", franchise_id=str(fid))

    # 3. complete the week (CPU slate + EOG + advance; wk26 seeds conference brackets)
    fr.complete_week(fr.CompleteWeekRequest(
        franchise_id=str(fid), week=week,
        result=fr.GameResult(team1_id=str(away_id), team2_id=str(home_id),
                             team1_score=away_s, team2_score=home_s),
        game_id=gid))
    return int((db.franchises.find_one({"_id": fid}, {"week": 1}) or {}).get("week", week))


def advance_postseason_week(fr, db, fid):
    """One EOS week (27-34) via the bracket driver. Sims all 128 teams' bracket games,
    advances exactly one EOS week; the wk34 call closes the championship → week 35."""
    fr.sim_rest_of_tournament(fr.SimRestOfTournamentRequest(franchise_id=str(fid)))
    return int((db.franchises.find_one({"_id": fid}, {"week": 1}) or {}).get("week", 0))


def run_week_35(fr, db, fid, fdoc, user_team_oid):
    """Week 35 recruiting via the auth-bypass impl path (Option B): run signings and
    set week=36 + token, which finish_season consumes."""
    try:
        fr._apply_cpu_week_35_cuts(fid, excluded_team_id=str(user_team_oid))
    except Exception as e:  # noqa: BLE001
        print(f"    week 35: cpu cuts skipped ({type(e).__name__}: {e})")
    results = fr._run_week_35_signings(fdoc)
    token = fr._mint_season_transition_token()
    db.franchises.update_one({"_id": fid}, {"$set": {
        "week": 36, "week_35_recruiting_ran": True,
        fr.WEEK_35_RECRUITING_RESULTS_FIELD: results,
        fr.SEASON_TRANSITION_TOKEN_FIELD: token}})
    return len((results or {}).get("signed_players", []))


def rollover(fr, fid):
    """finish_season: develop_rollover per returning + signed player; persists the
    next-season FPD (incl. development). Returns the response (with offseason report)."""
    return fr.finish_season(fr.FinishSeasonRequest(franchise_id=str(fid)))


def advance_one_season(fr, db, stat_updater, fid, user_team_oid, *, verbose=True):
    fdoc = db.franchises.find_one({"_id": fid})
    week = int(fdoc.get("week", 1))
    # regular season
    while week <= REGULAR_SEASON_LAST_WEEK:
        t0 = time.time()
        fdoc = db.franchises.find_one({"_id": fid})
        new_week = advance_regular_week(fr, db, stat_updater, fid, week, user_team_oid, fdoc)
        if verbose:
            print(f"  reg wk {week:>2} → {new_week:<2}  ({time.time()-t0:.0f}s)")
        if new_week <= week:
            _abort(f"regular week {week} did not advance (still {new_week})")
        week = new_week
    # postseason
    while REGULAR_SEASON_LAST_WEEK < week <= EOS_LAST_WEEK:
        t0 = time.time()
        new_week = advance_postseason_week(fr, db, fid)
        if verbose:
            print(f"  eos wk {week:>2} → {new_week:<2}  ({time.time()-t0:.0f}s)")
        if new_week <= week:
            _abort(f"postseason week {week} did not advance (still {new_week})")
        week = new_week
    # week 35 recruiting
    fdoc = db.franchises.find_one({"_id": fid})
    if int(fdoc.get("week", 0)) == 35:
        n_signed = run_week_35(fr, db, fid, fdoc, user_team_oid)
        if verbose:
            print(f"  wk 35 recruiting: {n_signed} signed → week 36")
    # week 36 rollover
    resp = rollover(fr, fid)
    return resp


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--franchise", required=True)
    ap.add_argument("--seasons", type=int, default=1)
    args = ap.parse_args()

    if "gob-staging" not in os.environ.get("MONGO_URI", "").lower():
        _abort("MONGO_URI does not point at gob-staging. Refusing.")
    os.environ.setdefault("FRANCHISE_CPU_SIM_USE_POOL", "1")  # fast pooled CPU slate

    ObjectId, db, franchises_collection, stat_updater, fr = _lazy_imports()
    fid = ObjectId(args.franchise)
    fdoc = db.franchises.find_one({"_id": fid})
    if not fdoc:
        _abort(f"franchise {args.franchise} not found")
    user_team_oid = ObjectId(fdoc["user_team_object_id"])
    print(f"✅ target={args.franchise} team={fdoc.get('user_team_id')!r} "
          f"start_week={fdoc.get('week')} seasons={args.seasons}")

    for s in range(args.seasons):
        cur = int((db.franchises.find_one({"_id": fid}, {"current_season": 1}) or {}).get("current_season", 1))
        print(f"\n=== season {cur} (advance {s+1}/{args.seasons}) ===")
        t0 = time.time()
        resp = advance_one_season(fr, db, stat_updater, fid, user_team_oid)
        rep = (resp or {}).get("offseason_development", [])
        print(f"  rollover done ({time.time()-t0:.0f}s): {len(rep)} offseason report lines")
    print("\n✅ harness complete")


if __name__ == "__main__":
    raise SystemExit(main())
