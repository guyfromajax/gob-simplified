"""Bundled base league for desktop SQLite saves.

``teams`` and ``players`` are the universal 128-program league. Hosted they
live in Atlas and are shared by every franchise. Desktop copies them into
each new save at creation — play mutates those rows, so the bundle is a
template, not a live sidecar.

Canonical source is production (``gob``): that is the league hosted players
already run. Staging can hold unpublished roster or Team Builder work.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

from BackEnd.persistence.catalog import canonical_doc_json, sort_catalog_docs
from BackEnd.persistence.sqlite_collection import SqliteCollection, encode_doc, encode_id
from BackEnd.persistence.sqlite_schema import create_table_sql, ensure_generated_schema
from BackEnd.runtime_paths import bundle_path


def assert_export_is_read_only() -> None:
    """Refuse to start an Atlas league export unless the process is read-only."""
    if os.environ.get("GOB_DB_ACCESS") != "read":
        raise RuntimeError(
            "Base league export is read-only. Set GOB_DB_ACCESS=read. "
            "This process will not open a write connection to staging or production."
        )


LEAGUE_COLLECTIONS: tuple[str, ...] = ("teams", "players")
EXPECTED_TEAM_COUNT = 128

# Application id "GOBL" so `file` / `sqlite3` can identify a league bundle.
_LEAGUE_APPLICATION_ID = 0x474F424C


def league_version(docs_by_collection: dict[str, list[dict[str, Any]]]) -> str:
    digest = hashlib.sha256()
    for name in LEAGUE_COLLECTIONS:
        for doc in sort_catalog_docs(list(docs_by_collection.get(name) or [])):
            digest.update(name.encode())
            digest.update(b"\n")
            digest.update(canonical_doc_json(doc).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def resolve_base_league_sqlite_path(
    process_environment: dict[str, str] | None = None,
) -> Path | None:
    env = process_environment if process_environment is not None else os.environ
    raw = str(env.get("GOB_BASE_LEAGUE_SQLITE") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    bundled = bundle_path("base_league.sqlite")
    return bundled if bundled.is_file() else None


def open_league_connection(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    return conn


def read_league_meta(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        "SELECT doc FROM league_meta WHERE id = ?", ('raw:"league"',)
    ).fetchone()
    if not row:
        return {"version": "unknown", "source": "unknown", "counts": {}}
    from BackEnd.persistence.sqlite_collection import decode_doc

    return decode_doc(row[0])


def _counts(docs_by_collection: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {name: len(docs_by_collection.get(name) or []) for name in LEAGUE_COLLECTIONS}


def write_league_sqlite(
    docs_by_collection: dict[str, list[dict[str, Any]]],
    path: Path,
    *,
    source: str,
) -> dict[str, Any]:
    """Write a deterministic league bundle. Two runs of the same docs match."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    version = league_version(docs_by_collection)
    counts = _counts(docs_by_collection)
    meta = {
        "_id": "league",
        "version": version,
        "source": source,
        "counts": counts,
        "exported_at": "1970-01-01T00:00:00+00:00",
    }
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA page_size = 4096")
        conn.execute(f"PRAGMA application_id = {_LEAGUE_APPLICATION_ID}")
        for name in (*LEAGUE_COLLECTIONS, "league_meta"):
            conn.execute(create_table_sql(name))
        ensure_generated_schema(conn, [*LEAGUE_COLLECTIONS, "league_meta"])
        conn.execute(
            "INSERT INTO league_meta (id, doc) VALUES (?, ?)",
            (encode_id("league"), encode_doc(meta)),
        )
        for name in LEAGUE_COLLECTIONS:
            for doc in sort_catalog_docs(list(docs_by_collection.get(name) or [])):
                stored = dict(doc)
                if "_id" not in stored:
                    stored["_id"] = ObjectId()
                conn.execute(
                    f'INSERT INTO "{name}" (id, doc) VALUES (?, ?)',
                    (encode_id(stored["_id"]), encode_doc(stored)),
                )
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()
    return meta


def write_league_json(
    docs_by_collection: dict[str, list[dict[str, Any]]],
    path: Path,
    *,
    source: str,
) -> dict[str, Any]:
    """Canonical JSON dump — release-to-release diffs, not the runtime bundle."""
    meta = {
        "version": league_version(docs_by_collection),
        "source": source,
        "counts": _counts(docs_by_collection),
        "collections": {
            name: sort_catalog_docs(list(docs_by_collection.get(name) or []))
            for name in LEAGUE_COLLECTIONS
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(meta, default=_json_default, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return meta


def _json_default(obj: Any) -> Any:
    if isinstance(obj, ObjectId):
        return {"$oid": str(obj)}
    if isinstance(obj, datetime):
        return {"$date": obj.isoformat()}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def load_league_docs(path: Path) -> dict[str, list[dict[str, Any]]]:
    conn = open_league_connection(path)
    try:
        lock = threading.RLock()
        docs: dict[str, list[dict[str, Any]]] = {}
        for name in LEAGUE_COLLECTIONS:
            coll = SqliteCollection(
                conn, name, writable=False, lock=lock, ensure_schema=False
            )
            docs[name] = list(coll.find({}))
        return docs
    finally:
        conn.close()


def seed_empty_save(
    *,
    teams_coll: Any,
    players_coll: Any,
    save_meta: Any,
    league_path: Path,
) -> dict[str, Any] | None:
    """Copy the bundled league into an empty save through the collection API.

    Existing saves are left alone — play mutates teams/players, so a re-copy
    would clobber a season. Returns the league meta when a copy ran.
    """
    if teams_coll.count_documents({}) > 0:
        return None
    docs = load_league_docs(league_path)
    teams = [copy.deepcopy(doc) for doc in docs.get("teams") or []]
    players = [copy.deepcopy(doc) for doc in docs.get("players") or []]
    if teams:
        teams_coll.insert_many(teams)
    if players:
        players_coll.insert_many(players)
    conn = open_league_connection(league_path)
    try:
        meta = read_league_meta(conn)
    finally:
        conn.close()
    stamp = {
        "_id": "base_league",
        "league_version": meta.get("version") or "unknown",
        "source": meta.get("source") or "unknown",
        "counts": meta.get("counts") or {
            "teams": len(teams),
            "players": len(players),
        },
    }
    existing = save_meta.find_one({"_id": "base_league"})
    if existing is None:
        save_meta.insert_one(stamp)
    else:
        save_meta.replace_one({"_id": "base_league"}, stamp, upsert=True)
    return stamp


def fixture_league_docs() -> dict[str, list[dict[str, Any]]]:
    """Tiny two-team league for unit tests. Not the shipping 128."""
    home_id = ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")
    away_id = ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")
    home_player = ObjectId("cccccccccccccccccccccccc")
    away_player = ObjectId("dddddddddddddddddddddddd")
    attrs = {k: 70 for k in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]}
    return {
        "teams": [
            {
                "_id": home_id,
                "name": "Test Lancaster",
                "team_id": "TEST_LANCASTER",
                "conference": 1,
                "region": "A",
                "primary_color": "#1a1a5c",
                "secondary_color": "#f5c518",
                "mascot": "Pioneers",
                "prestige": 500,
                "total_player_attrs": 840,
                "player_ids": [home_player],
            },
            {
                "_id": away_id,
                "name": "Test Morristown",
                "team_id": "TEST_MORRISTOWN",
                "conference": 1,
                "region": "A",
                "primary_color": "#7a1f1f",
                "secondary_color": "#e8e8e8",
                "mascot": "Foxes",
                "prestige": 480,
                "total_player_attrs": 820,
                "player_ids": [away_player],
            },
        ],
        "players": [
            {
                "_id": home_player,
                "player_id": str(home_player),
                "first_name": "Test",
                "last_name": "Guard",
                "team": "Test Lancaster",
                "team_id": home_id,
                "year": "Jr",
                "height": 74,
                "weight": 185,
                "attributes": attrs.copy(),
                "position_ratings": {"PG": 80, "SG": 75, "SF": 60, "PF": 40, "C": 30},
            },
            {
                "_id": away_player,
                "player_id": str(away_player),
                "first_name": "Test",
                "last_name": "Wing",
                "team": "Test Morristown",
                "team_id": away_id,
                "year": "So",
                "height": 76,
                "weight": 200,
                "attributes": attrs.copy(),
                "position_ratings": {"PG": 50, "SG": 70, "SF": 80, "PF": 65, "C": 40},
            },
        ],
    }
