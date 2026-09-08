#!/usr/bin/env python3
"""Populate the shared uniform archive; dry-run by default.

Clears the accumulated paint debt: every rostered player carrying a ``meta.image_id``
but no painted portrait. Writes to ``uniforms/<image_id>__<color_key>.png`` — one
object per (portrait x team look), shared by every franchise — and stamps
``meta.uniform_key`` so the client addresses it directly instead of missing and
waiting on a paint.

See _documentation_master/projects/Uniform_Archive_Brief.md.

WHY THIS RUNS BEFORE THE PER-GAME WARM: with the debt cleared the warm paints
nothing in the steady state, so no user ever waits on a paint. Run it lazily instead
and the warm becomes the primary mechanism, which grows past its window (~2.3
unpainted/team after one class, ~7/team by season 4).

Paints are ~1s CPU and 10.5 MB each, so this is minutes of work per franchise. It is
resumable: every step is idempotent, an interrupted run just re-checks exists().

    python3 scripts/backfill_uniform_archive.py --db gob-staging
    python3 scripts/backfill_uniform_archive.py --db gob-staging --apply --limit 50
"""

import argparse
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target  # noqa: E402


def _find_team(teams, team_id):
    """teams._id is an ObjectId; meta.team_id arrives as a string. Try both."""
    if team_id is None:
        return None
    try:
        from bson import ObjectId
        doc = teams.find_one({"_id": ObjectId(str(team_id))})
        if doc:
            return doc
    except Exception:
        pass
    return teams.find_one({"_id": str(team_id)}) or teams.find_one({"team_id": str(team_id)})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true", help="actually paint and write")
    parser.add_argument("--limit", type=int, default=0, help="stop after N paints (0 = all)")
    parser.add_argument("--franchise", default=None, help="restrict to one franchise_id")
    parser.add_argument("--mirror", action="store_true",
                        help="also copy to the legacy players/master/<player_id>.png key")
    args = parser.parse_args()

    from BackEnd.services import r2_images
    if args.apply and not r2_images.is_configured():
        print("[ABORT] R2 is not configured — painting is impossible. Set R2_* env vars.")
        return 2

    from BackEnd.utils import uniform_archive
    from BackEnd.utils.franchise_team_display import resolve_team_display

    connection = connect_migration_target(args.db, write=args.apply)
    dbh = connection.database
    fpd = dbh["franchise_players_data"]
    ftd = dbh["franchise_team_data"]
    teams = dbh["teams"]

    # Only players actually ON a roster. FPD also holds practice squad and prior
    # seasons; painting those is work nobody will ever see.
    #
    # FTD keys franchise_id as ObjectId while FPD keys it as a string, so a filter
    # has to carry both forms or it silently matches nothing.
    roster_q: dict = {}
    if args.franchise:
        forms: list = [args.franchise]
        try:
            from bson import ObjectId
            forms.append(ObjectId(args.franchise))
        except Exception:
            pass
        roster_q = {"franchise_id": {"$in": forms}}
    active: set[str] = set()
    for t in ftd.find(roster_q, {"players": 1, "franchise_id": 1}):
        for pid in (t.get("players") or []):
            active.add(str(pid))
    print(f"[PLAN] active roster player_ids: {len(active)}")

    q = {"meta.image_id": {"$nin": [None, ""]}, "player_id": {"$in": list(active)}}
    if args.franchise:
        q["franchise_id"] = args.franchise
    candidates = list(fpd.find(q, {"player_id": 1, "franchise_id": 1, "meta": 1}))
    print(f"[PLAN] candidates with image_id on a roster: {len(candidates)}")

    stats = Counter()
    display_cache: dict[tuple, dict] = {}
    t0 = time.perf_counter()
    painted = 0

    for doc in candidates:
        meta = doc.get("meta") or {}
        fid, pid = doc.get("franchise_id"), str(doc.get("player_id"))
        team_id = meta.get("team_id")
        if not team_id:
            stats["skip_no_team_id"] += 1
            continue

        ck = (str(fid), str(team_id))
        if ck not in display_cache:
            core = _find_team(teams, team_id)
            if not core:
                display_cache[ck] = {}
            else:
                try:
                    display_cache[ck] = resolve_team_display(fid, team_id, core_doc=core) or {}
                except Exception:
                    display_cache[ck] = {
                        "primary_color": core.get("primary_color"),
                        "secondary_color": core.get("secondary_color"),
                        "mascot": core.get("mascot"),
                    }
        disp = display_cache[ck]
        if not disp:
            stats["skip_no_team"] += 1
            continue

        ukey = uniform_archive.uniform_key(
            meta.get("image_id"), disp.get("primary_color"),
            disp.get("secondary_color"), disp.get("mascot"),
        )
        if not ukey:
            stats["skip_unkeyable"] += 1
            continue

        if not args.apply:
            stats["would_process"] += 1
            continue

        res = uniform_archive.ensure_uniform(
            image_id=meta.get("image_id"),
            primary=disp.get("primary_color"),
            secondary=disp.get("secondary_color"),
            mascot=disp.get("mascot"),
        )
        stats[res["status"]] += 1
        if res["status"] in ("exists", "painted"):
            fpd.update_one(
                {"franchise_id": str(fid), "player_id": pid},
                {"$set": {"meta.uniform_key": res["uniform_key"], "meta.image_painted": True}},
            )
            stats["stamped"] += 1
            if args.mirror:
                legacy = f"players/master/{pid}.png"
                if not r2_images.exists(legacy):
                    if r2_images.copy(res["object_key"], legacy):
                        stats["mirrored"] += 1
        if res["status"] == "painted":
            painted += 1
            if painted % 25 == 0:
                rate = painted / max(time.perf_counter() - t0, 1e-6)
                print(f"  ... painted {painted}  ({rate:.2f}/s)")
            if args.limit and painted >= args.limit:
                print(f"[STOP] --limit {args.limit} reached")
                break

    elapsed = time.perf_counter() - t0
    print(f"\n[{'DONE' if args.apply else 'DRY RUN'}] {args.db}  elapsed={elapsed:.1f}s")
    for k, v in sorted(stats.items()):
        print(f"   {k:20} {v}")
    if not args.apply:
        print("\nNo data changed. Re-run with --apply to paint.")
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
