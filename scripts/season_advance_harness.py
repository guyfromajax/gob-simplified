#!/usr/bin/env python3
"""Headless season-advance harness — drives a franchise through the FULL season
(regular 1-26 → postseason 27-34 → recruiting 35 → rollover 36) for N seasons,
in-process (no HTTP server, no auth), landing at season+1 week 1.

Parameterised for N seasons (``--seasons N``). RESUMABLE: it reads the franchise's
current (season, week) from the DB every step and continues from there, and records
the target end-season on first run — so a crash at week 24 of a 5-hour run costs
minutes, not the whole run. Re-invoke with the same args to resume.

Week map (BackEnd/tournament/franchise_tournament.py):
  1-26  regular season  → complete_week (auto-seeds conference brackets after wk26)
  27-34 EOS tournament   → sim_rest_of_tournament (NOT complete_week: it 409s once the
                           user team is eliminated; the bracket driver sims all 128)
  35    recruiting       → _run_week_35_signings + set week=36 (auth-bypass impl path)
  36    rollover         → finish_season (develop_rollover per returning + signed)

With ``--measure-dir DIR`` it captures validation snapshots (pre/post FPD, weekly
CPU attribute movement, season box-score stats, offseason report, bracket state) and
the week-1 timing split (sim / persistence / CPU-training). Idempotent + resume-safe.

⚠️  MUTATES the target franchise. Guarded to gob-staging only. Postseason weeks 27-34
have never been driven headless outside this harness.

⚠️  LOCAL RUNS (laptop → remote Atlas): export FRANCHISE_CPU_SIM_USE_POOL=0 first.
    This harness setdefault's POOL=1, which selects the spawn ProcessPool in
    BackEnd/utils/cpu_week_pool.py — 8 workers, each a fresh interpreter that builds its
    OWN MongoClient to Atlas. That pool is tuned for the 32-vCPU Railway service sitting
    next to Atlas; from a laptop over the public internet the 8 concurrent connections +
    a per-week spawn re-import STALL the run on season 1 week 1 (workers idle at ~3% CPU
    waiting on the network). The default thread engine (POOL=0) uses one shared connection
    and completes — a 4-season run is ~148 min. On Railway, leave the pool on. Because the
    harness uses os.environ.setdefault, you MUST set POOL=0 in the shell BEFORE running:
        FRANCHISE_CPU_SIM_USE_POOL=0 python scripts/season_advance_harness.py --franchise ...
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

REGULAR_SEASON_LAST_WEEK = 26
EOS_LAST_WEEK = 34
_HARNESS_END_SEASON_FIELD = "_harness_end_season"

# finalize_game timing accumulator (installed by _instrument_finalize)
_FINALIZE = {"t": 0.0, "n": 0}


def _abort(msg: str):
    print(f"❌ ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def _lazy_imports():
    from bson import ObjectId
    from BackEnd.db import db, franchise_players_data_collection as FPD
    from BackEnd.utils import stat_updater
    from BackEnd.api import franchise_routes as fr
    return ObjectId, db, FPD, stat_updater, fr


def _instrument_finalize(stat_updater):
    """Wrap stat_updater.finalize_game to accumulate total time — the EOG-persistence
    (DB-round-trip) cost, the part co-location would cut."""
    orig = stat_updater.finalize_game
    if getattr(orig, "_instrumented", False):
        return
    def wrapped(*a, **k):
        t0 = time.time()
        try:
            return orig(*a, **k)
        finally:
            _FINALIZE["t"] += time.time() - t0
            _FINALIZE["n"] += 1
    wrapped._instrumented = True
    stat_updater.finalize_game = wrapped


# ── measurement snapshots (all idempotent / resume-safe) ──────────────────────
def _jwrite(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def _snapshot_fpd(FPD, fid, path: Path):
    if path.exists():
        return
    docs = []
    for d in FPD.find({"franchise_id": str(fid)}):
        meta = d.get("meta") or {}
        docs.append({
            "player_id": d.get("player_id"), "year": meta.get("year"),
            "entry_tier": d.get("entry_tier"), "position_intent": d.get("position_intent"),
            "position_ratings": d.get("position_ratings") or {},
            "has_dev": bool(d.get("development")),
            # height/weight for the LONGITUDINAL height check (§16.3 grow-into-frame): the same
            # player_id tracked across boundaries must show real HT growth, not just a static
            # class-year cross-section (a cross-section can look right while nobody grows).
            "height": meta.get("height"), "weight": meta.get("weight"),
            "attributes": {a: (d.get("attributes") or {}).get(a)
                           for a in (d.get("attributes") or {}) if str(a).startswith("anchor_")},
            "team_id": str(meta.get("team_id") or ""),
        })
    _jwrite(path, docs)
    print(f"    [measure] snapshot {path.name}: {len(docs)} players")


def _snapshot_boxscore(FPD, fid, path: Path):
    if path.exists():
        return
    rows = []
    for d in FPD.find({"franchise_id": str(fid)}):
        s = d.get("season") or {}
        if not s:
            continue
        rows.append({"player_id": d.get("player_id"), "team_id": str((d.get("meta") or {}).get("team_id") or ""),
                     "season": {k: s.get(k) for k in s if isinstance(s.get(k), (int, float))}})
    _jwrite(path, rows)
    print(f"    [measure] boxscore stats {path.name}: {len(rows)} players")


def _capture_attr_delta(FPD, fid, user_team_oid, season_no, week, apply_training_fn, path: Path):
    """Snapshot CPU-roster anchor attrs before/after this week's training, append the
    per-attribute movement aggregate. Idempotent by (season, week)."""
    key = f"{season_no}:{week}"
    if path.exists():
        for line in path.read_text().splitlines():
            if line and json.loads(line).get("key") == key:
                return apply_training_fn()  # already recorded; still run training
    def snap():
        out = {}
        for d in FPD.find({"franchise_id": str(fid)}, {"player_id": 1, "attributes": 1, "meta.team_id": 1}):
            if str((d.get("meta") or {}).get("team_id") or "") == str(user_team_oid):
                continue  # exclude the user team; CPU rosters only
            out[d["player_id"]] = {a: v for a, v in (d.get("attributes") or {}).items() if str(a).startswith("anchor_")}
        return out
    before = snap()
    result = apply_training_fn()
    after = snap()
    n = 0; s_signed = 0.0; s_abs = 0.0; per = {}
    for pid, ba in before.items():
        aa = after.get(pid, {})
        for a, bv in ba.items():
            av = aa.get(a)
            if av is None or bv is None:
                continue
            dv = av - bv; n += 1; s_signed += dv; s_abs += abs(dv)
            attr = a.replace("anchor_", "")
            pd = per.setdefault(attr, [0, 0.0]); pd[0] += 1; pd[1] += dv
    rec = {"key": key, "season": season_no, "week": week, "n": n,
           "mean_signed": (s_signed / n if n else 0.0), "mean_abs": (s_abs / n if n else 0.0),
           "per_attr_mean": {a: (v[1] / v[0] if v[0] else 0.0) for a, v in per.items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return result


# ── drive steps ───────────────────────────────────────────────────────────────
def _resolve_user_matchup(fdoc, week, user_team_oid):
    schedule = fdoc.get("schedule", [])
    if week - 1 >= len(schedule):
        return None
    for g in schedule[week - 1]:
        away_id, home_id = (g.get("away"), g.get("home")) if isinstance(g, dict) else (g[0], g[1])
        if away_id == user_team_oid or home_id == user_team_oid:
            return away_id, home_id
    return None


def advance_regular_week(fr, db, stat_updater, fid, week, user_team_oid, fdoc,
                         FPD=None, measure_dir: Path = None, season_no=1):
    """One regular-season week: train (user + CPU autotrain) → user game → complete_week.
    Returns (new_week, phase_timings)."""
    matchup = _resolve_user_matchup(fdoc, week, user_team_oid)
    if matchup is None:
        _abort(f"no user matchup in schedule for week {week}")
    away_id, home_id = matchup
    away_name = (db.teams.find_one({"_id": away_id}, {"name": 1}) or {}).get("name", "")
    home_name = (db.teams.find_one({"_id": home_id}, {"name": 1}) or {}).get("name", "")

    def _do_training():
        try:
            alloc = fr.generate_random_training_allocations(30 if week == 1 else 24)
            alloc["coaching_focus"] = fr.generate_random_coaching_focus()
            fr.run_franchise_training(fr.FranchiseTrainingRequest(
                franchise_id=str(fid), team_id=str(user_team_oid), training_data=alloc))
        except Exception as e:  # noqa: BLE001
            print(f"    week {week}: training skipped ({type(e).__name__}: {e})")

    # 1. training (user + CPU autotrain-reference); capture CPU attr movement if measuring
    t_train0 = time.time()
    if measure_dir is not None and FPD is not None:
        _capture_attr_delta(FPD, fid, user_team_oid, season_no, week, _do_training,
                            measure_dir / "attr_movement.jsonl")
    else:
        _do_training()
    t_train = time.time() - t_train0

    # 2. user game with a finalized box score
    t_sim0 = time.time()
    away_s, home_s, summary = fr._run_franchise_cpu_full_simulation_core(
        fid, home_id, away_id, home_name, away_name)
    gid = fr.generate_game_id()
    summary["_id"] = gid; summary["franchise_id"] = str(fid); summary["week"] = week
    db.games.update_one({"_id": gid}, {"$set": summary}, upsert=True)
    stat_updater.finalize_game(gid, mode="franchise", franchise_id=str(fid))
    t_user = time.time() - t_sim0

    # 3. complete the week (CPU slate + EOG + advance)
    t_cw0 = time.time()
    fr.complete_week(fr.CompleteWeekRequest(
        franchise_id=str(fid), week=week,
        result=fr.GameResult(team1_id=str(away_id), team2_id=str(home_id),
                             team1_score=away_s, team2_score=home_s),
        game_id=gid))
    t_cw = time.time() - t_cw0

    new_week = int((db.franchises.find_one({"_id": fid}, {"week": 1}) or {}).get("week", week))
    return new_week, {"training": t_train, "user_game": t_user, "complete_week": t_cw}


def advance_postseason_week(fr, db, fid):
    fr.sim_rest_of_tournament(fr.SimRestOfTournamentRequest(franchise_id=str(fid)))
    return int((db.franchises.find_one({"_id": fid}, {"week": 1}) or {}).get("week", 0))


def run_week_35(fr, db, fid, fdoc, user_team_oid):
    from BackEnd.db import (franchise_team_data_collection as _FTD,
                            franchise_recruits_data_collection as _FRD)
    # Seed CPU recruiting orders — the real run_week_35_recruiting route builds these per
    # team via _build_cpu_week_35_orders before signing; the auth-bypass signings path skips
    # it, so without this CPU teams sign NO recruits and fill rosters with Poor walk-ons,
    # draining the league ~-5 RT/attr/season (a harness artifact, not a real dropoff).
    ftd_docs = list(_FTD.find({"franchise_id": fid}, {"team_id": 1, fr.RECRUITING_ORDERS_WEEK_35_FIELD: 1}))
    team_ids = [d["team_id"] for d in ftd_docs if d.get("team_id")]
    team_docs = {str(t["_id"]): t for t in db.teams.find({"_id": {"$in": team_ids}})}
    recruits = list(_FRD.find({"franchise_id": str(fid)}))
    for d in ftd_docs:
        tid = d["team_id"]
        if str(tid) == str(user_team_oid) or d.get(fr.RECRUITING_ORDERS_WEEK_35_FIELD):
            continue
        td = team_docs.get(str(tid))
        if td is None:
            continue
        _FTD.update_one({"franchise_id": fid, "team_id": tid},
                        {"$set": {fr.RECRUITING_ORDERS_WEEK_35_FIELD: fr._build_cpu_week_35_orders(td, recruits)}})
    try:
        fr._apply_cpu_week_35_cuts(fid, excluded_team_id=str(user_team_oid))
    except Exception as e:  # noqa: BLE001
        print(f"    week 35: cpu cuts skipped ({type(e).__name__}: {e})")
    fdoc = db.franchises.find_one({"_id": fid})  # re-read after order writes
    results = fr._run_week_35_signings(fdoc)
    token = fr._mint_season_transition_token()
    db.franchises.update_one({"_id": fid}, {"$set": {
        "week": 36, "week_35_recruiting_ran": True,
        fr.WEEK_35_RECRUITING_RESULTS_FIELD: results,
        fr.SEASON_TRANSITION_TOKEN_FIELD: token}})
    return len((results or {}).get("signed_players", []))


def rollover(fr, fid):
    return fr.finish_season(fr.FinishSeasonRequest(franchise_id=str(fid)))


def advance_one_season(fr, db, stat_updater, FPD, fid, user_team_oid, season_no,
                       measure_dir: Path = None):
    fdoc = db.franchises.find_one({"_id": fid})
    week = int(fdoc.get("week", 1))

    if measure_dir is not None:
        _snapshot_fpd(FPD, fid, measure_dir / f"s{season_no}_pre_fpd.json")

    # regular season
    while week <= REGULAR_SEASON_LAST_WEEK:
        t0 = time.time()
        fdoc = db.franchises.find_one({"_id": fid})
        fin_before = _FINALIZE["t"], _FINALIZE["n"]
        new_week, phases = advance_regular_week(
            fr, db, stat_updater, fid, week, user_team_oid, fdoc,
            FPD=FPD, measure_dir=measure_dir, season_no=season_no)
        wall = time.time() - t0
        print(f"  reg wk {week:>2} → {new_week:<2}  ({wall:.0f}s)")
        if week == 1 and measure_dir is not None:
            fin_dt = _FINALIZE["t"] - fin_before[0]
            split = {"season": season_no, "week_total_s": round(wall, 1),
                     "cpu+user_training_s": round(phases["training"], 1),
                     "finalize_game_persist_s": round(fin_dt, 1),
                     "finalize_game_calls": _FINALIZE["n"] - fin_before[1],
                     "sim_and_rest_s": round(wall - phases["training"] - fin_dt, 1)}
            _jwrite(measure_dir / f"s{season_no}_week1_timing.json", split)
            print(f"    [timing] {split}")
        if new_week <= week:
            _abort(f"regular week {week} did not advance (still {new_week})")
        week = new_week

    if measure_dir is not None:
        _snapshot_boxscore(FPD, fid, measure_dir / f"s{season_no}_boxscore.json")

    # postseason
    while REGULAR_SEASON_LAST_WEEK < week <= EOS_LAST_WEEK:
        t0 = time.time()
        new_week = advance_postseason_week(fr, db, fid)
        print(f"  eos wk {week:>2} → {new_week:<2}  ({time.time()-t0:.0f}s)")
        if new_week <= week:
            _abort(f"postseason week {week} did not advance (still {new_week})")
        week = new_week

    if measure_dir is not None:
        fdoc = db.franchises.find_one({"_id": fid})
        _jwrite(measure_dir / f"s{season_no}_brackets.json", {
            "conference_tournaments": fdoc.get("conference_tournaments"),
            "region_tournaments": fdoc.get("region_tournaments"),
            "national_tournament": fdoc.get("national_tournament"),
        })

    # week 35 recruiting
    fdoc = db.franchises.find_one({"_id": fid})
    if int(fdoc.get("week", 0)) == 35:
        n_signed = run_week_35(fr, db, fid, fdoc, user_team_oid)
        print(f"  wk 35 recruiting: {n_signed} signed → week 36")

    # week 36 rollover
    resp = rollover(fr, fid)
    rep = (resp or {}).get("offseason_development", [])
    print(f"  rollover done: {len(rep)} offseason report lines")
    if measure_dir is not None:
        _jwrite(measure_dir / f"s{season_no}_offseason_report.json", rep)
        _snapshot_fpd(FPD, fid, measure_dir / f"s{season_no+1}_pre_fpd.json")
    return resp


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--franchise", required=True)
    ap.add_argument("--seasons", type=int, default=1)
    ap.add_argument("--measure-dir", default=None)
    args = ap.parse_args()

    # Load .env.local so MONGO_URI is populated before the guard (BackEnd.db does this
    # on import, but the guard runs first / before the DB is imported).
    try:
        from dotenv import load_dotenv
        env_local = _REPO / ".env.local"
        load_dotenv(str(env_local)) if env_local.exists() else load_dotenv()
    except Exception:
        pass
    if "gob-staging" not in os.environ.get("MONGO_URI", "").lower():
        _abort("MONGO_URI does not point at gob-staging. Refusing.")
    os.environ.setdefault("FRANCHISE_CPU_SIM_USE_POOL", "1")

    ObjectId, db, FPD, stat_updater, fr = _lazy_imports()
    _instrument_finalize(stat_updater)
    fid = ObjectId(args.franchise)
    fdoc = db.franchises.find_one({"_id": fid})
    if not fdoc:
        _abort(f"franchise {args.franchise} not found")
    user_team_oid = ObjectId(fdoc["user_team_object_id"])
    measure_dir = Path(args.measure_dir) if args.measure_dir else None

    # resume-safe target: record end-season once, then advance until reached
    end_season = fdoc.get(_HARNESS_END_SEASON_FIELD)
    if end_season is None:
        end_season = int(fdoc.get("current_season", 1)) + args.seasons
        db.franchises.update_one({"_id": fid}, {"$set": {_HARNESS_END_SEASON_FIELD: end_season}})
    print(f"✅ target={args.franchise} team={fdoc.get('user_team_id')!r} "
          f"start=(season {fdoc.get('current_season')}, week {fdoc.get('week')}) "
          f"end_season={end_season} measure_dir={measure_dir}")

    while True:
        cur = int((db.franchises.find_one({"_id": fid}, {"current_season": 1}) or {}).get("current_season", 1))
        if cur >= end_season:
            break
        print(f"\n=== season {cur} → {cur+1} (target end {end_season}) ===")
        t0 = time.time()
        advance_one_season(fr, db, stat_updater, FPD, fid, user_team_oid, cur, measure_dir=measure_dir)
        print(f"  season {cur} complete ({(time.time()-t0)/60:.1f} min)")
    print("\n✅ harness complete")


if __name__ == "__main__":
    raise SystemExit(main())
