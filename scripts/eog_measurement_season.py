#!/usr/bin/env python3
"""
Drive the EOG-band measurement franchise through a full regular season (26 weeks)
in-process, so calculate_attr_changes emits real [EOG-BAND] data on live-shaped
games. No UI, no server, no auth — the week-advancing route handlers are called
directly (same in-process pattern as scripts/perf_sim_baseline.py).

Each week, for the ONE hardcoded target franchise:
  1. training       — run_franchise_training (best-effort; non-fatal if it fails)
  2. user game      — sim the user matchup with real FTD hydration + persist a
                      real box score (so EOG reads real stats for the user's game)
  3. complete_week  — sims the entire CPU slate, runs EOG on every game, advances
                      the week N -> N+1

Repeats until the franchise `week` exceeds --stop-after-week (default 26).

⚠️  MUTATES the target franchise (advances its season). Only ever run against a
disposable staging franchise. Hard safety guards below refuse to run otherwise.

Resumable: current week is read from the franchise doc each iteration, so
re-invoking continues from wherever it stopped (run week 1, verify, then the rest).

Env (set by scripts/run_eog_measurement.sh, validated here):
  MONGO_URI                     must contain 'gob-staging'
  GOB_EOG_BAND_LOG=1            band capture on
  GOB_EOG_BAND_LOG_FILE=<abs>   durable local path for the dataset
  FRANCHISE_ALL_GAMES_FULL_SIM=1  REQUIRED — else regular-season games go distant
                                  and the six usage-gated attributes are garbage
  FRANCHISE_ALL_TEAMS_AUTOTRAIN=1 (recommended) real CPU training
  FRANCHISE_CPU_SIM_USE_POOL=1     (recommended) fast CPU slate
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make `BackEnd` importable when run as `python scripts/eog_measurement_season.py`.
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Hardcoded target — do NOT resolve "most recent franchise"; that stops being
# true the moment another franchise exists.
TARGET_FRANCHISE_ID = "6a66449127f0298bd27584c5"
EXPECTED_USER_TEAM = "South Lancaster"
EXPECTED_DB_MARKER = "gob-staging"
REGULAR_SEASON_LAST_WEEK = 26


def _abort(msg: str) -> None:
    print(f"❌ ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stop-after-week", type=int, default=REGULAR_SEASON_LAST_WEEK,
        help="Advance until franchise week exceeds this (default 26). Use 1 for the "
             "week-1 capture gate, then re-run with 26 for the rest.",
    )
    args = parser.parse_args()
    stop_after = min(int(args.stop_after_week), REGULAR_SEASON_LAST_WEEK)

    # ---- Safety gate 1: environment (before importing anything DB-bound) -------
    mongo_uri = os.environ.get("MONGO_URI", "")
    if EXPECTED_DB_MARKER not in mongo_uri.lower():
        _abort(f"MONGO_URI does not point at '{EXPECTED_DB_MARKER}'. Refusing to run "
               f"(guards against prod / an empty local DB). Got: {mongo_uri[:40]}...")

    # Imports are deferred until AFTER the MONGO_URI guard so a misconfigured run
    # can't connect anywhere first.
    from bson import ObjectId
    from BackEnd.db import db, franchises_collection
    from BackEnd.utils import stat_updater
    from BackEnd.api.franchise_routes import (
        _run_franchise_cpu_full_simulation_core,
        complete_week,
        run_franchise_training,
        generate_game_id,
        generate_random_training_allocations,
        generate_random_coaching_focus,
        CompleteWeekRequest,
        GameResult,
        FranchiseTrainingRequest,
        _eog_band_log_enabled,
        _eog_band_log_path,
        _franchise_all_games_full_sim,
    )

    # ---- Safety gate 2: capture + clean-data flags ----------------------------
    if not _eog_band_log_enabled():
        _abort("GOB_EOG_BAND_LOG is not on — nothing would be captured.")
    if not _franchise_all_games_full_sim():
        _abort("FRANCHISE_ALL_GAMES_FULL_SIM is not 1 — regular-season games would go "
               "distant and the six usage-gated attributes would be GARBAGE. Set it.")

    # ---- Safety gate 3: the franchise is who we think it is --------------------
    fid = ObjectId(TARGET_FRANCHISE_ID)
    fdoc = franchises_collection.find_one({"_id": fid})
    if not fdoc:
        _abort(f"Franchise {TARGET_FRANCHISE_ID} not found in this DB.")
    user_team_name = fdoc.get("user_team_id")
    if user_team_name != EXPECTED_USER_TEAM:
        _abort(f"Franchise user team is {user_team_name!r}, expected "
               f"{EXPECTED_USER_TEAM!r} — wrong franchise or wrong DB. Refusing.")
    user_team_oid = ObjectId(fdoc["user_team_object_id"])

    print(f"✅ Guards passed. Target={TARGET_FRANCHISE_ID} team={user_team_name!r} "
          f"db-marker={EXPECTED_DB_MARKER} band_log={_eog_band_log_path()}")
    print(f"   Advancing until week > {stop_after}.\n")

    weeks_done = 0
    while True:
        fdoc = franchises_collection.find_one({"_id": fid})
        week = int(fdoc.get("week", 1))
        if week > stop_after:
            print(f"\n✅ Reached stop condition (current week {week} > {stop_after}).")
            break
        if week > REGULAR_SEASON_LAST_WEEK:
            print(f"\n✅ Regular season complete (week {week} is postseason).")
            break

        # --- resolve the user matchup for this week from the schedule ----------
        schedule = fdoc.get("schedule", [])
        matchup = None
        if week - 1 < len(schedule):
            for away_id, home_id in schedule[week - 1]:
                if away_id == user_team_oid or home_id == user_team_oid:
                    matchup = (away_id, home_id)
                    break
        if matchup is None:
            _abort(f"Could not find user matchup in schedule for week {week}.")
        away_id, home_id = matchup
        away_name = (db.teams.find_one({"_id": away_id}, {"name": 1}) or {}).get("name", "")
        home_name = (db.teams.find_one({"_id": home_id}, {"name": 1}) or {}).get("name", "")

        # --- 1. training (best-effort; complete_week has no training gate) ------
        try:
            alloc = generate_random_training_allocations(30 if week == 1 else 24)
            alloc["coaching_focus"] = generate_random_coaching_focus()
            run_franchise_training(FranchiseTrainingRequest(
                franchise_id=TARGET_FRANCHISE_ID,
                team_id=str(user_team_oid),
                training_data=alloc,
            ))
            trained = "trained"
        except Exception as e:  # noqa: BLE001 — training must never block the week
            trained = f"training SKIPPED ({type(e).__name__}: {e})"

        # --- 2. user game with a real, finalized box score (mirrors EOS Path B)-
        away_score, home_score, summary = _run_franchise_cpu_full_simulation_core(
            fid, home_id, away_id, home_name, away_name
        )
        game_id = generate_game_id()
        summary["_id"] = game_id
        summary["franchise_id"] = str(fid)
        summary["week"] = week
        db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
        stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(fid))

        # --- 3. complete the week (sims CPU slate, EOG on all games, advances) --
        complete_week(CompleteWeekRequest(
            franchise_id=TARGET_FRANCHISE_ID,
            week=week,
            result=GameResult(
                team1_id=str(away_id), team2_id=str(home_id),
                team1_score=away_score, team2_score=home_score,
            ),
            game_id=game_id,
        ))

        new_week = int((franchises_collection.find_one({"_id": fid}, {"week": 1}) or {}).get("week", week))
        if new_week <= week:
            _abort(f"Week {week} did not advance (still {new_week}). Stopping so the "
                   f"franchise isn't driven in a stuck loop.")
        weeks_done += 1
        print(f"  week {week:>2} → {new_week:<2}  user {away_name} {away_score}-{home_score} {home_name}  [{trained}]")

    # --- summary -----------------------------------------------------------------
    path = _eog_band_log_path()
    lines = 0
    if os.path.exists(path):
        with open(path) as fh:
            lines = sum(1 for _ in fh)
    print(f"\nWeeks advanced this run: {weeks_done}. Band-log file: {path} ({lines} lines).")
    print("Next: python scripts/eog_band_report.py --strict "
          f"{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
