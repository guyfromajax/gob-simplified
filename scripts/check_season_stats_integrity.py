#!/usr/bin/env python3
"""Read-only check: season GP vs results, and game docs whose teams disagree with the box.

Does not write. Open a SQLite save or a Mongo connection and print a summary.

Examples:
  GOB_PERSISTENCE=sqlite GOB_SQLITE_PATH=/path/to/save.sqlite \\
    python scripts/check_season_stats_integrity.py

  python scripts/check_season_stats_integrity.py --sqlite /path/to/save.sqlite

  python scripts/check_season_stats_integrity.py --mongo "$MONGO_URI" --franchise-id <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


def _box_team_keys(game: dict) -> set[str]:
    keys: set[str] = set()
    teams = game.get("teams")
    if isinstance(teams, dict):
        for key, row in teams.items():
            box = row.get("box_score") if isinstance(row, dict) else None
            if isinstance(box, dict) and any(
                isinstance(player, dict) and (player.get("playerId") or player.get("player_id"))
                for player in box.values()
            ):
                keys.add(str(key))
    box = game.get("box_score")
    if isinstance(box, dict):
        for key, row in box.items():
            if isinstance(row, dict) and any(
                isinstance(player, dict) and (player.get("playerId") or player.get("player_id"))
                for player in row.values()
            ):
                keys.add(str(key))
    return keys


def database_name_from_uri(uri: str | None) -> str | None:
    """Database name is the URI path. ``mongodb://host:27017/gob`` → ``gob``."""
    if not uri:
        return None
    path = (urlparse(uri).path or "").strip("/")
    name = path.split("/")[0] if path else ""
    return name or None


def resolve_mongo_database(db_arg: str | None, uri: str | None) -> str:
    """``--db`` wins. Otherwise the URI path. Error when neither names a database."""
    if db_arg:
        return db_arg
    name = database_name_from_uri(uri)
    if not name:
        raise SystemExit("Pass --db or a Mongo URI whose path is the database name")
    return name


def _resolved_name(ref, teams_by_key: dict[str, dict]) -> str:
    """Team display name when the ref is an id, code, or name already in the index."""
    text = _ref_text(ref).strip()
    if not text or text == "None":
        return ""
    doc = teams_by_key.get(text)
    if doc and doc.get("name"):
        return str(doc["name"])
    return text


def _name_set(refs, teams_by_key: dict[str, dict]) -> set[str]:
    return {name for name in (_resolved_name(ref, teams_by_key) for ref in refs) if name}


class _Store:
    def franchises(self) -> list[tuple[str, dict]]:
        raise NotImplementedError

    def rows(self, collection: str) -> list[tuple[str, dict]]:
        raise NotImplementedError


class SqliteStore(_Store):
    def __init__(self, path: str):
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def rows(self, collection: str) -> list[tuple[str, dict]]:
        out = []
        try:
            cursor = self.con.execute(f"SELECT id, doc FROM {collection}")
        except sqlite3.OperationalError:
            return []
        for row_id, doc in cursor:
            try:
                parsed = json.loads(doc)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict):
                out.append((str(row_id), parsed))
        return out

    def franchises(self) -> list[tuple[str, dict]]:
        return self.rows("franchises")


class MongoStore(_Store):
    def __init__(self, uri: str, db_name: str):
        from pymongo import MongoClient

        self.client = MongoClient(uri, serverSelectionTimeoutMS=4000)
        self.db = self.client[db_name]

    def rows(self, collection: str) -> list[tuple[str, dict]]:
        out = []
        for doc in self.db[collection].find({}):
            if isinstance(doc, dict):
                out.append((str(doc.get("_id")), doc))
        return out

    def franchises(self) -> list[tuple[str, dict]]:
        return self.rows("franchises")


def _team_index(store: _Store) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row_id, doc in store.rows("teams"):
        doc = dict(doc)
        doc.setdefault("_id", row_id.replace("oid:", ""))
        for key in ("_id", "team_id", "name", "code"):
            if doc.get(key):
                index[str(doc[key])] = doc
        if row_id.startswith("oid:"):
            index[row_id.replace("oid:", "")] = doc
    return index


def _ref_text(ref) -> str:
    if isinstance(ref, dict):
        if ref.get("$oid"):
            return str(ref["$oid"])
        if ref.get("_id"):
            return _ref_text(ref.get("_id"))
    return str(ref)


def _team_label(ref, teams_by_key: dict[str, dict]) -> str:
    text = _ref_text(ref)
    doc = teams_by_key.get(text)
    if doc and doc.get("name"):
        return str(doc["name"])
    return text


def check(store: _Store, franchise_id: str | None, database_name: str) -> int:
    print(f"database {database_name}")
    teams_by_key = _team_index(store)
    fpd_gp: dict[tuple[str, str], int] = defaultdict(int)
    for _row_id, doc in store.rows("franchise_players_data"):
        fid = str(doc.get("franchise_id") or "")
        team_id = str((doc.get("meta") or {}).get("team_id") or "")
        if not fid or not team_id:
            continue
        gp = int((doc.get("season") or {}).get("GP") or 0)
        key = (fid, team_id)
        if gp > fpd_gp[key]:
            fpd_gp[key] = gp

    gp_mismatches = 0
    box_disagreements = 0
    franchise_count = 0
    wanted = franchise_id.replace("oid:", "") if franchise_id else None

    for row_id, franchise in store.franchises():
        fid = row_id.replace("oid:", "")
        if wanted and wanted not in {fid, str(franchise.get("_id") or "")}:
            continue
        franchise_count += 1
        played: dict[str, int] = defaultdict(int)
        for _week, rows in (franchise.get("results") or {}).items():
            if not isinstance(rows, list):
                continue
            for result in rows:
                if not isinstance(result, dict):
                    continue
                for side in ("away_id", "home_id"):
                    team_id = str(result.get(side) or "")
                    if team_id:
                        played[team_id] += 1
        team_ids = set(played) | {team for (ff, team) in fpd_gp if ff == fid}
        franchise_gaps = []
        for team_id in sorted(team_ids):
            games = played.get(team_id, 0)
            max_gp = fpd_gp.get((fid, team_id), 0)
            if games != max_gp:
                franchise_gaps.append((team_id, games, max_gp))
        if franchise_gaps:
            user = franchise.get("user_team_id") or franchise.get("user_team")
            print(f"franchise {fid} week {franchise.get('week')} user {user}")
            for team_id, games, max_gp in franchise_gaps:
                gp_mismatches += 1
                print(
                    f"  GP {_team_label(team_id, teams_by_key)} ({team_id}): "
                    f"results={games} max_season_gp={max_gp}"
                )

    for row_id, game in store.rows("games"):
        gid = row_id.replace("oid:", "")
        game_fid = str(game.get("franchise_id") or "")
        if wanted and wanted not in {game_fid, ""}:
            continue
        home = game.get("home_team_id")
        away = game.get("away_team_id")
        box_keys = _box_team_keys(game)
        canonical = {str(item) for item in (home, away) if item}
        result_refs = [item for item in (game.get("team1_id"), game.get("team2_id")) if item]
        box_refs = list(box_keys or canonical)
        box_names = _name_set(box_refs, teams_by_key)
        stored_names = _name_set(result_refs, teams_by_key)
        if not box_names or not stored_names:
            continue
        if box_names == stored_names:
            continue
        if wanted and game_fid and wanted != game_fid:
            continue
        box_disagreements += 1
        print(
            f"box/matchup game {gid} franchise {game_fid or '-'} week {game.get('week')}: "
            f"box={sorted(box_names)} "
            f"stored_teams={sorted(stored_names)}"
        )

    print(
        f"SUMMARY gp_mismatches={gp_mismatches} "
        f"box_disagreements={box_disagreements} franchises={franchise_count}"
    )
    return 0


def _open_store(args: argparse.Namespace) -> tuple[_Store, str]:
    sqlite_path = args.sqlite or os.environ.get("GOB_SQLITE_PATH")
    persistence = (os.environ.get("GOB_PERSISTENCE") or "").strip().lower()
    mongo_uri = args.mongo or os.environ.get("MONGO_URI")
    if args.sqlite or persistence == "sqlite" or (sqlite_path and not args.mongo):
        if not sqlite_path:
            raise SystemExit("SQLite check needs --sqlite or GOB_SQLITE_PATH")
        if not Path(sqlite_path).is_file():
            raise SystemExit(f"SQLite file not found: {sqlite_path}")
        return SqliteStore(sqlite_path), Path(sqlite_path).name
    if not mongo_uri:
        raise SystemExit("Pass --sqlite PATH or --mongo URI (or set GOB_SQLITE_PATH / MONGO_URI)")
    return MongoStore(mongo_uri, resolve_mongo_database(args.db, mongo_uri)), resolve_mongo_database(args.db, mongo_uri)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only season stats integrity check")
    parser.add_argument("--sqlite", help="Path to a SQLite save. Opened read-only.")
    parser.add_argument("--mongo", help="Mongo connection string. Reads only.")
    parser.add_argument("--db", default=None, help="Mongo database name. Defaults to the URI path.")
    parser.add_argument("--franchise-id", default=None)
    args = parser.parse_args(argv)
    store, database_name = _open_store(args)
    return check(store, args.franchise_id, database_name)


if __name__ == "__main__":
    sys.exit(main())
