#!/usr/bin/env python3
"""Explicit-target maintenance for universal player and team catalog data.

This consolidates the retained photo, rating, roster-reference, measurement,
attribute-profile, legacy-color, and destructive JSON-replacement utilities. Dry-run
is the default. Destructive replacement additionally requires exact target confirmation
and an external backup directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.constants import ALL_ATTRS
from BackEnd.models.player import Player
from BackEnd.script_db import ScriptDatabaseError, connect_script_database
from BackEnd.utils.position_ratings import compute_position_ratings
from scripts.publish_universal_data import _validate_backup_root, _write_backup

TEAMS_DIR = ROOT / "teams"
IMAGES_DIR = ROOT / "FrontEnd" / "static" / "images" / "players"
ATTRIBUTE_KEYS = ALL_ATTRS + ["NG"]
NO_ANCHOR = frozenset({"NG", "CH", "EM", "MO"})
UUID_PNG = re.compile(
    r"^([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\.png$",
    re.IGNORECASE,
)

ATTRIBUTE_PROFILES = {
    "production": (
        ("South Lancaster", "south_lancaster_production.json"),
        ("Four Corners", "four_corners_production.json"),
    ),
    "staging": (
        ("Bentley-Truman", "bentley_truman_staging.json"),
        ("Lancaster", "lancaster_staging.json"),
        ("Four Corners", "four_corners_staging.json"),
        ("Morristown", "morristown_staging.json"),
        ("Ocean City", "ocean_city_staging.json"),
        ("South Lancaster", "south_lancaster_staging.json"),
        ("Little York", "little_york_staging.json"),
        ("Xavien", "xavien_staging.json"),
    ),
}

LEGACY_TEAM_COLORS = {
    "BENTLEY-TRUMAN": ("#4066b2", "#ffffff"),
    "LANCASTER": ("#d24a1b", "#000000"),
    "FOUR_CORNERS": ("#c0976a", "#00954b"),
    "OCEAN_CITY": ("#2a2168", "#00a89d"),
    "MORRISTOWN": ("#ec1d28", "#cccccc"),
    "LITTLE_YORK": ("#65308e", "#f6af38"),
    "XAVIEN": ("#016837", "#999999"),
    "SOUTH_LANCASTER": ("#7c2b24", "#e39649"),
}


def _team_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_player(players, team: str, raw: dict[str, Any]):
    base = {
        "team": team,
        "first_name": str(raw.get("first_name") or "").strip(),
        "last_name": str(raw.get("last_name") or "").strip(),
    }
    jersey = raw.get("jersey")
    with_jersey = {**base, "jersey": jersey} if jersey is not None else base
    return players.find_one(with_jersey) or (players.find_one(base) if jersey is not None else None)


def sync_photos(players, images_dir: Path, *, apply: bool) -> dict[str, int]:
    counts = {"changed": 0, "unchanged": 0, "missing": 0}
    for path in sorted(images_dir.iterdir() if images_dir.is_dir() else []):
        match = UUID_PNG.match(path.name)
        if not match:
            continue
        player = players.find_one({"player_id": match.group(1)})
        if not player:
            counts["missing"] += 1
            continue
        photo = f"/static/images/players/{path.name}"
        if player.get("photo") == photo:
            counts["unchanged"] += 1
            continue
        if apply:
            players.update_one({"_id": player["_id"]}, {"$set": {"photo": photo}})
        counts["changed"] += 1
    return counts


def recalculate_ratings(players, *, apply: bool) -> dict[str, int]:
    counts = {"scanned": 0, "changed": 0}
    projection = {"team": 1, "first_name": 1, "last_name": 1, "attributes": 1, "height": 1,
                  "position_ratings": 1}
    for player in players.find({}, projection):
        counts["scanned"] += 1
        ratings = compute_position_ratings(player)
        if player.get("position_ratings") == ratings:
            continue
        if apply:
            players.update_one({"_id": player["_id"]}, {"$set": {"position_ratings": ratings}})
        counts["changed"] += 1
    return counts


def rebuild_roster_ids(players, teams, *, apply: bool) -> dict[str, int]:
    counts = {"scanned": 0, "changed": 0}
    for team in teams.find({}, {"name": 1, "player_ids": 1}):
        counts["scanned"] += 1
        player_ids = [p["_id"] for p in players.find({"team": team.get("name")}, {"_id": 1})]
        if team.get("player_ids") == player_ids:
            continue
        if apply:
            teams.update_one({"_id": team["_id"]}, {"$set": {"player_ids": player_ids}})
        counts["changed"] += 1
    return counts


def sync_measurements(players, paths: Iterable[Path], *, apply: bool) -> dict[str, int]:
    counts = {"matched": 0, "changed": 0, "missed": 0}
    for path in paths:
        data = _team_json(path)
        team = data.get("name")
        for raw in data.get("players", []):
            player = _find_player(players, team, raw)
            if not player:
                counts["missed"] += 1
                continue
            counts["matched"] += 1
            changes = {key: raw.get(key) for key in ("height", "weight")
                       if raw.get(key) is not None and player.get(key) != raw.get(key)}
            if not changes:
                continue
            if apply:
                players.update_one({"_id": player["_id"]}, {"$set": changes})
            counts["changed"] += 1
    return counts


def sync_attribute_profile(players, profile: str, teams_dir: Path, *, apply: bool) -> dict[str, int]:
    counts = {"matched": 0, "changed": 0, "missed": 0}
    include_year = profile == "staging"
    for team, filename in ATTRIBUTE_PROFILES[profile]:
        path = teams_dir / filename
        if not path.is_file():
            raise ScriptDatabaseError(f"Missing profile source {path}")
        for raw in _team_json(path).get("players", []):
            player = _find_player(players, team, raw)
            if not player:
                counts["missed"] += 1
                continue
            counts["matched"] += 1
            current = player.get("attributes") or {}
            changes: dict[str, Any] = {}
            if include_year and raw.get("year") is not None and player.get("year") != raw["year"]:
                changes["year"] = raw["year"]
            for attr in ATTRIBUTE_KEYS:
                value = raw.get(attr)
                if value is None:
                    continue
                if current.get(attr) != value:
                    changes[f"attributes.{attr}"] = value
                if attr not in NO_ANCHOR and current.get(f"anchor_{attr}") != value:
                    changes[f"attributes.anchor_{attr}"] = value
            if not changes:
                continue
            if apply:
                players.update_one({"_id": player["_id"]}, {"$set": changes})
            counts["changed"] += 1
    return counts


def sync_legacy_colors(teams, *, apply: bool) -> dict[str, int]:
    counts = {"matched": 0, "changed": 0, "missing": 0}
    for team_id, (primary, secondary) in LEGACY_TEAM_COLORS.items():
        team = teams.find_one({"team_id": team_id})
        if not team:
            counts["missing"] += 1
            continue
        counts["matched"] += 1
        values = {"primary_color": primary, "secondary_color": secondary}
        if all(team.get(key) == value for key, value in values.items()):
            continue
        if apply:
            teams.update_one({"_id": team["_id"]}, {"$set": values})
        counts["changed"] += 1
    return counts


def build_replacement_docs(paths: Iterable[Path]) -> list[dict[str, Any]]:
    docs = []
    seen_players = set()
    for path in paths:
        data = _team_json(path)
        team_name = data.get("name")
        for raw_original in data.get("players", []):
            raw = dict(raw_original)
            key = (team_name, raw.get("first_name"), raw.get("last_name"), raw.get("jersey"))
            if key in seen_players:
                raise ScriptDatabaseError(f"Duplicate player across replacement files: {key}")
            seen_players.add(key)
            if "attributes" not in raw:
                raw["attributes"] = {name: raw.get(name, 0) for name in ALL_ATTRS}
            player = Player(raw)
            player_id = str(uuid4())
            doc = {
                "_id": player_id, "player_id": player_id,
                "first_name": player.first_name, "last_name": player.last_name,
                "team": player.team, "attributes": player.attributes,
                "stats": player.stats, "metadata": player.metadata,
                "jersey": player.jersey, "year": player.year,
                "height": raw.get("height"), "weight": raw.get("weight"),
            }
            doc["position_ratings"] = compute_position_ratings(doc)
            docs.append(doc)
    return docs


def replace_players(players, teams, paths: Iterable[Path], *, apply: bool) -> dict[str, int]:
    docs = build_replacement_docs(paths)
    if apply:
        players.delete_many({})
        if docs:
            players.insert_many(docs)
        rebuild_roster_ids(players, teams, apply=True)
    return {"replacement_players": len(docs)}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-db")
    parser.add_argument("--backup-dir", type=Path)
    sub = parser.add_subparsers(dest="operation", required=True)
    photos = sub.add_parser("photos"); photos.add_argument("--images-dir", type=Path, default=IMAGES_DIR)
    sub.add_parser("ratings")
    sub.add_parser("roster-ids")
    measurements = sub.add_parser("measurements"); measurements.add_argument("--file", action="append", type=Path, required=True)
    attributes = sub.add_parser("attributes"); attributes.add_argument("--profile", choices=sorted(ATTRIBUTE_PROFILES), required=True); attributes.add_argument("--teams-dir", type=Path, default=TEAMS_DIR)
    sub.add_parser("legacy-colors")
    replace = sub.add_parser("replace-from-json"); replace.add_argument("--file", action="append", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    destructive = args.operation == "replace-from-json" and args.apply
    connection = connect_script_database(
        target=args.db, access="write" if args.apply else "read",
        destructive=destructive, confirm_db=args.confirm_db,
        pristine_env=dict(os.environ), repo_root=ROOT,
    )
    players = connection.database["players"]
    teams = connection.database["teams"]
    try:
        if destructive:
            backup_root = _validate_backup_root(args.backup_dir)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_dir = backup_root / f"{args.db}-before-player-replacement-{stamp}"
            run_dir.mkdir(mode=0o700)
            backup = _write_backup(run_dir, "players", list(players.find({})))
            print(f"[BACKUP] {backup}")
        if args.operation == "photos":
            counts = sync_photos(players, args.images_dir, apply=args.apply)
        elif args.operation == "ratings":
            counts = recalculate_ratings(players, apply=args.apply)
        elif args.operation == "roster-ids":
            counts = rebuild_roster_ids(players, teams, apply=args.apply)
        elif args.operation == "measurements":
            counts = sync_measurements(players, args.file, apply=args.apply)
        elif args.operation == "attributes":
            counts = sync_attribute_profile(players, args.profile, args.teams_dir, apply=args.apply)
        elif args.operation == "legacy-colors":
            counts = sync_legacy_colors(teams, apply=args.apply)
        else:
            counts = replace_players(players, teams, args.file, apply=args.apply)
        print(f"[{'APPLIED' if args.apply else 'DRY RUN'}] {args.operation}: {counts}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
