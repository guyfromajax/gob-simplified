#!/usr/bin/env python3
"""
League scoring report — the metrics identity, shot calibration and the EOG bands are
judged against, read straight from persisted games.

WHY THIS EXISTS: these numbers were never logged. They did not need to be — every figure
here is derived from `games.teams.<TEAM>.totals`, which is written for every game and
never expires. The gap was a report, not instrumentation. Hand-rolled queries answered it
three times during the identity investigation and disagreed once, because two of them
silently filtered on `is_final` (set on ~5% of CPU games) and measured a handful of games
while reporting a league.

READ-ONLY. Never writes. Run with GOB_DB_ACCESS=read.

  scripts/league_scoring_report.py --franchise <id>
  scripts/league_scoring_report.py --franchise <id> --weeks 13-14
  scripts/league_scoring_report.py --franchise <id> --weeks 1 --vs <other_id> --vs-weeks 1

COMPARING WEEKS IS NOT COMPARING TREATMENTS. Teams develop, so week 13 outscores week 1
in any league. Compare like-for-like weeks across franchises (--vs), or the same franchise
before and after a change. A week-1-vs-week-13 delta measures player development.
"""

from __future__ import annotations

# Pin PYTHONHASHSEED before anything else. See BackEnd/utils/repro. Loaded BY PATH so this
# does not import the BackEnd.utils package, whose __init__ pulls in stat_updater -> db.
import os as _os, sys as _sys, importlib.util as _ilu
_GOB_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _GOB_ROOT)
_spec = _ilu.spec_from_file_location(
    "_gob_repro", _os.path.join(_GOB_ROOT, "BackEnd", "utils", "repro.py"))
_repro = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_repro)
_repro.pin_hash_seed()

import argparse
import statistics
from typing import Any

# game_manager.py:613 — a player is disqualified at >= 5 personal fouls. Not a named
# constant in the engine; if that ever changes this must follow it.
FOUL_OUT_AT = 5

# Possessions are ESTIMATED, not counted: the engine does not persist a possession count.
# 0.44 is the standard coefficient for converting free-throw attempts into the possessions
# they ended. It is a convention, not a measurement of THIS engine — treat PPP as
# comparable between runs of this report, not as ground truth.
FTA_POSSESSION_COEFF = 0.44


def parse_weeks(spec: str | None) -> list[int] | None:
    """'13-14' | '1,3,5' | '7' -> [ints]. None means every week present."""
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def _team_rows(game: dict) -> list[dict]:
    """One `totals` dict per team, plus its box_score, for a single game."""
    rows = []
    for side in (game.get("teams") or {}).values():
        if not isinstance(side, dict):
            continue
        totals = side.get("totals")
        if isinstance(totals, dict) and totals.get("PTS") is not None:
            rows.append({"totals": totals, "box": side.get("box_score") or {}})
    # A game contributes two team-games or none. A one-sided game means a partial write.
    return rows if len(rows) == 2 else []


def collect(db, franchise_id, weeks: list[int] | None,
            include_practice_squad: bool = False) -> dict[str, Any]:
    from bson import ObjectId
    try:
        fid_variants = [ObjectId(str(franchise_id)), str(franchise_id)]
    except Exception:
        fid_variants = [str(franchise_id)]

    query: dict[str, Any] = {"franchise_id": {"$in": fid_variants}}
    if weeks:
        query["week"] = {"$in": weeks}
    # PRACTICE-SQUAD GAMES SHARE THIS COLLECTION AND THIS franchise_id. They are 24
    # All-American games of low-rated recruits played alongside the 63-game league slate,
    # and including them silently moves every league mean — week 2 read as 84 games when
    # the league played 64. Real league games carry mode None (CPU sim) or "franchise"
    # (the user's own game); only PS sets mode="practice_squad".
    if not include_practice_squad:
        query["mode"] = {"$ne": "practice_squad"}

    # NO is_final FILTER. It is set on a small minority of CPU-simmed games; filtering on
    # it silently drops ~95% of the league and yields a confident, wrong mean.
    per_week: dict[int, list[dict]] = {}
    partial = 0
    for g in db["games"].find(query, {"week": 1, "teams": 1}):
        rows = _team_rows(g)
        if not rows:
            partial += 1
            continue
        per_week.setdefault(g.get("week"), []).extend(rows)
    return {"per_week": per_week, "partial_games": partial}


def _num(d: dict, key: str) -> float:
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def summarize(rows: list[dict]) -> dict[str, Any] | None:
    """Aggregate a list of team-games into the identity/EOG metric set."""
    if not rows:
        return None
    pts, poss, fouls, foul_outs = [], [], [], []
    fgm = fga = tpm = tpa = 0.0
    for r in rows:
        t = r["totals"]
        p = _num(t, "PTS")
        possessions = (_num(t, "FGA") - _num(t, "OREB") + _num(t, "TO")
                       + FTA_POSSESSION_COEFF * _num(t, "FTA"))
        pts.append(p)
        if possessions > 0:
            poss.append(possessions)
        fouls.append(_num(t, "F"))
        fgm += _num(t, "FGM"); fga += _num(t, "FGA")
        tpm += _num(t, "3PTM"); tpa += _num(t, "3PTA")
        box = r["box"]
        players = box.values() if isinstance(box, dict) else (box or [])
        foul_outs.append(sum(
            1 for pl in players
            if isinstance(pl, dict) and _num(pl, "F") >= FOUL_OUT_AT))
    return {
        "team_games": len(rows),
        "pts": statistics.mean(pts),
        "pts_sd": statistics.pstdev(pts) if len(pts) > 1 else 0.0,
        # Standard error of the mean — the number that says whether a delta is real.
        "pts_sem": (statistics.pstdev(pts) / (len(pts) ** 0.5)) if len(pts) > 1 else 0.0,
        "poss": statistics.mean(poss) if poss else 0.0,
        "ppp": (statistics.mean(pts) / statistics.mean(poss)) if poss else 0.0,
        "fg_pct": (fgm / fga * 100) if fga else 0.0,
        "tp_pct": (tpm / tpa * 100) if tpa else 0.0,
        "fouls": statistics.mean(fouls),
        "foul_outs": statistics.mean(foul_outs),
    }


def identity_state(db, franchise_id) -> str:
    """Whether identity is actually live for this franchise — the treatment, not the data."""
    try:
        from BackEnd.utils.franchise_identity import franchise_identity_summary
        from bson import ObjectId
        s = franchise_identity_summary(ObjectId(str(franchise_id)))
    except Exception as e:  # noqa: BLE001
        return f"identity: unknown ({type(e).__name__})"
    teams = s.get("teams") or 0
    with_id = s.get("teams_with_identity") or 0
    var = s.get("slider_variance") or {}
    flat = [k for k in ("aggression", "hc_trap", "fc_press") if not (var.get(k) or 0) > 0]
    if with_id == 0 or flat:
        return (f"identity: ❌ INERT ({with_id}/{teams} teams, "
                f"flat sliders: {flat or 'none'})")
    return f"identity: ✅ LIVE ({with_id}/{teams} teams)"


HEADER = (f"{'week':>6}{'team-gm':>9}{'PTS':>8}{'±sem':>7}{'POSS':>8}"
          f"{'PPP':>7}{'FG%':>7}{'3P%':>7}{'FOUL':>7}{'F-OUT':>7}")


def line(label: str, s: dict) -> str:
    return (f"{label:>6}{s['team_games']:>9}{s['pts']:>8.2f}{s['pts_sem']:>7.2f}"
            f"{s['poss']:>8.1f}{s['ppp']:>7.3f}{s['fg_pct']:>7.1f}{s['tp_pct']:>7.1f}"
            f"{s['fouls']:>7.2f}{s['foul_outs']:>7.2f}")


def report(db, franchise_id, weeks, title: str,
           include_practice_squad: bool = False) -> dict | None:
    data = collect(db, franchise_id, weeks, include_practice_squad)
    per_week = data["per_week"]
    print(f"\n{'=' * 78}\n{title}\n{identity_state(db, franchise_id)}\n{'=' * 78}")
    if not per_week:
        print("  no games found for that franchise/week selection")
        return None
    if data["partial_games"]:
        print(f"  ⚠️  skipped {data['partial_games']} game(s) without two complete team "
              f"totals (partial or in-progress writes)")
    print(HEADER)
    print("-" * 78)
    for wk in sorted(k for k in per_week if k is not None):
        s = summarize(per_week[wk])
        if s:
            print(line(str(wk), s))
    all_rows = [r for rows in per_week.values() for r in rows]
    overall = summarize(all_rows)
    print("-" * 78)
    print(line("ALL", overall))
    return overall


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--franchise", required=True)
    ap.add_argument("--weeks", default=None, help="'13-14' | '1,3,5' | '7' (default: all)")
    ap.add_argument("--vs", default=None, help="second franchise id to compare against")
    ap.add_argument("--vs-weeks", default=None, help="weeks for --vs (default: --weeks)")
    ap.add_argument("--include-practice-squad", action="store_true",
                    help="also count mode=practice_squad games (default: league only)")
    args = ap.parse_args()

    from BackEnd.db import db

    weeks = parse_weeks(args.weeks)
    a = report(db, args.franchise, weeks,
               f"FRANCHISE {args.franchise}  weeks={args.weeks or 'all'}"
               + ("  [+PS games]" if args.include_practice_squad else ""),
               args.include_practice_squad)

    if args.vs:
        vs_weeks = parse_weeks(args.vs_weeks) if args.vs_weeks else weeks
        b = report(db, args.vs, vs_weeks,
                   f"FRANCHISE {args.vs}  weeks={args.vs_weeks or args.weeks or 'all'}",
                   args.include_practice_squad)
        if a and b:
            print(f"\n{'=' * 78}\nDELTA  (second minus first)\n{'=' * 78}")
            d = b["pts"] - a["pts"]
            # Difference of two independent means: SE = sqrt(sem_a^2 + sem_b^2).
            se = (a["pts_sem"] ** 2 + b["pts_sem"] ** 2) ** 0.5
            pct = (d / a["pts"] * 100) if a["pts"] else 0.0
            print(f"  points/team-game  {a['pts']:.2f} -> {b['pts']:.2f}   "
                  f"{d:+.2f} ({pct:+.1f}%)")
            print(f"  PPP               {a['ppp']:.3f} -> {b['ppp']:.3f}")
            print(f"  fouls/team-game   {a['fouls']:.2f} -> {b['fouls']:.2f}")
            print(f"  foul-outs/tm-gm   {a['foul_outs']:.2f} -> {b['foul_outs']:.2f}")
            if se > 0:
                print(f"\n  points delta = {d:+.2f} +/- {se:.2f} (1 SE); "
                      f"|delta|/SE = {abs(d) / se:.1f}")
                if abs(d) < 2 * se:
                    print("  ⚠️  BELOW 2 SE — not distinguishable from zero. More weeks "
                          "needed before calling this a real effect.")
            if args.vs_weeks and args.vs_weeks != (args.weeks or ""):
                print("\n  ⚠️  DIFFERENT WEEK RANGES. Teams develop over a season, so part "
                      "of this delta is development, not treatment.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
