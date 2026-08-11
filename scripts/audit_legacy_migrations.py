#!/usr/bin/env python3
"""Read-only evidence report for retained historical database migrations.

Run once per explicit target. A PASS proves the inspected invariant currently holds;
it does not prove which script established it. UNKNOWN means the old migration is too
procedural or data-specific to retire from a generic schema check alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target

REQUIRED_DEFENSE_IDS = {
    "base-man", "man-tight", "man-loose", "2-3-zone", "3-2-zone", "1-3-1-zone"
}
REQUIRED_STRATEGY_FIELDS = {
    "offense", "inside", "attack", "outside", "play_calling", "defense",
    "aggression", "hc_trap", "fc_press", "rebounding", "fast_breaks",
}
REQUIRED_COACHING_FIELDS = {
    "effectiveness", "training_focus_list", "authoritarian", "systems coach",
    "player maximizer", "culture builder",
}


def _missing_count(collection, query: dict[str, Any]) -> int:
    return collection.count_documents(query)


def audit_database(db) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def record(group: str, invariant: str, passed: bool | None, detail: str) -> None:
        results.append({
            "group": group,
            "invariant": invariant,
            "status": "PASS" if passed is True else "FAIL" if passed is False else "UNKNOWN",
            "detail": detail,
        })

    def obsolete(group: str, invariant: str, detail: str) -> None:
        results.append({"group": group, "invariant": invariant, "status": "OBSOLETE", "detail": detail})

    defense_ids = {str(d.get("defense_id")) for d in db.defenses.find({}, {"defense_id": 1})}
    missing_defenses = sorted(REQUIRED_DEFENSE_IDS - defense_ids)
    record("defense_seeders", "all canonical defense_ids exist", not missing_defenses,
           f"missing={missing_defenses}")

    for collection_name in ("plays", "defenses"):
        collection = db[collection_name]
        total = collection.count_documents({})
        for field in ("effectiveness", "cloaking", "momentum"):
            missing = _missing_count(collection, {field: {"$exists": False}})
            record("play_defense_fields", f"{collection_name}.{field} exists", total > 0 and missing == 0,
                   f"missing={missing}/{total}")

    teams = db.teams
    total_teams = teams.count_documents({})
    missing_coaching = 0
    missing_strategy = 0
    legacy_tempo = 0
    missing_pfpa = 0
    for team in teams.find({}, {"coaching": 1, "strategy_settings": 1, "PF": 1, "PA": 1}):
        if not REQUIRED_COACHING_FIELDS.issubset(set((team.get("coaching") or {}).keys())):
            missing_coaching += 1
        strategy = team.get("strategy_settings") or {}
        if not REQUIRED_STRATEGY_FIELDS.issubset(set(strategy.keys())):
            missing_strategy += 1
        if "tempo" in strategy:
            legacy_tempo += 1
        if "PF" not in team or "PA" not in team:
            missing_pfpa += 1
    obsolete("team_backfills", "universal teams.coaching backfill",
             "no runtime consumer; current coaching state lives on users/FTD")
    obsolete("team_backfills", "universal teams.strategy_settings backfill",
             "current settings live in FTD/tournament/game documents")
    record("team_backfills", "legacy strategy_settings.tempo absent", legacy_tempo == 0,
           f"legacy={legacy_tempo}/{total_teams}")
    obsolete("team_backfills", "universal teams PF/PA zero backfill",
             "standings are recomputed from games; universal fields are optional zero fallback")

    players = db.players
    total_players = players.count_documents({})
    for field in ("player_id", "photo", "position_ratings"):
        missing = players.count_documents({field: {"$exists": False}})
        record("player_catalog", f"players.{field} exists", total_players > 0 and missing == 0,
               f"missing={missing}/{total_players}")
    roster_mismatch = 0
    for team in teams.find({}, {"name": 1, "player_ids": 1}):
        expected = {p["_id"] for p in players.find({"team": team.get("name")}, {"_id": 1})}
        if set(team.get("player_ids") or []) != expected:
            roster_mismatch += 1
    record("player_catalog", "teams.player_ids matches players.team", roster_mismatch == 0,
           f"mismatched_teams={roster_mismatch}/{total_teams}")

    recruit_sets = db.recruit_sets
    recruit_total = recruit_bad_year = recruit_missing_region = 0
    for set_doc in recruit_sets.find({}, {"recruits": 1}):
        for recruit in set_doc.get("recruits") or []:
            recruit_total += 1
            if recruit.get("year") not in {"JH", "Freshman", "Sophomore", "Junior"}:
                recruit_bad_year += 1
            if recruit.get("Home Region") not in set("ABCDEFGH"):
                recruit_missing_region += 1
    record("recruit_sets", "canonical year values", recruit_total > 0 and recruit_bad_year == 0,
           f"bad={recruit_bad_year}/{recruit_total}")
    record("recruit_sets", "frozen Home Region values", recruit_total > 0 and recruit_missing_region == 0,
           f"missing_or_bad={recruit_missing_region}/{recruit_total}")

    for collection_name in ("franchises", "tournaments"):
        collection = db[collection_name]
        total = collection.count_documents({})
        missing = collection.count_documents({"user_id": {"$exists": False}})
        record("ownership_migration", f"{collection_name}.user_id exists", missing == 0,
               f"missing={missing}/{total}")

    ftd = db.franchise_team_data
    total_ftd = ftd.count_documents({})
    malformed_ftd = 0
    malformed_by_franchise: dict[str, int] = {}
    active_franchise_ids = {str(doc["_id"]) for doc in db.franchises.find({}, {"_id": 1})}
    for doc in ftd.find({}, {"franchise_id": 1, "plays": 1, "playbook_settings": 1}):
        doc_malformed = False
        plays = doc.get("plays") or {}
        settings = doc.get("playbook_settings") or {}
        if not isinstance(plays, dict) or not isinstance(settings, dict):
            doc_malformed = True
        else:
            doc_malformed = any(not isinstance(key, str) for key in plays) or not {
                "motion", "set_plays", "fast_breaks", "man_defense", "zone_defense"
            }.issubset(settings)
        if doc_malformed:
            malformed_ftd += 1
            key = str(doc.get("franchise_id"))
            malformed_by_franchise[key] = malformed_by_franchise.get(key, 0) + 1
    record("ftd_schema", "string-keyed plays and canonical playbook shape",
           malformed_ftd == 0,
           f"malformed={malformed_ftd}/{total_ftd}; franchise_groups={len(malformed_by_franchise)}; "
           f"active_groups={sum(1 for key in malformed_by_franchise if key in active_franchise_ids)}; "
           f"orphan_groups={sum(1 for key in malformed_by_franchise if key not in active_franchise_ids)}")

    record("procedural_history", "nested historical game/skeleton rewrites", None,
           "requires migration-specific comparison; generic schema presence is insufficient")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        results = audit_database(connection.database)
    finally:
        connection.close()
    if args.json:
        print(json.dumps({"database": args.db, "results": results}, indent=2))
    else:
        print(f"Legacy migration evidence: {args.db}")
        for result in results:
            print(f"{result['status']:7} {result['group']}: {result['invariant']} — {result['detail']}")
    return 1 if any(result["status"] == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
