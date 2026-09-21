"""Read-only bundled catalog sidecar for desktop SQLite.

``plays``, ``defenses``, ``fcp_skeletons``, and ``hct_skeletons`` are the
universal rulebook. They live in Atlas on hosted and in ``catalog.sqlite``
next to the binary on desktop. The user save never holds those rows.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

from BackEnd.persistence.guards import CatalogWriteBlocked, _MUTATORS
from BackEnd.persistence.sqlite_collection import (
    SqliteCollection,
    encode_doc,
    encode_id,
)
from BackEnd.persistence.sqlite_schema import create_table_sql, ensure_generated_schema
from BackEnd.runtime_paths import bundle_path


def assert_export_is_read_only() -> None:
    """Refuse to start an Atlas catalog export unless the process is read-only."""
    if os.environ.get("GOB_DB_ACCESS") != "read":
        raise RuntimeError(
            "Catalog export is read-only. Set GOB_DB_ACCESS=read. "
            "This process will not open a write connection to staging or production."
        )


CATALOG_COLLECTIONS: tuple[str, ...] = (
    "plays",
    "defenses",
    "fcp_skeletons",
    "hct_skeletons",
)

# Application id "GOBC" so `file` / `sqlite3` can identify a catalog sidecar.
_CATALOG_APPLICATION_ID = 0x474F4243


def _json_default(obj: Any) -> Any:
    if isinstance(obj, ObjectId):
        return {"$oid": str(obj)}
    if isinstance(obj, datetime):
        return {"$date": obj.isoformat()}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_doc_json(doc: dict[str, Any]) -> str:
    return json.dumps(doc, default=_json_default, sort_keys=True, separators=(",", ":"))


def sort_catalog_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(docs, key=lambda doc: str(doc.get("_id", "")))


def catalog_version(docs_by_collection: dict[str, list[dict[str, Any]]]) -> str:
    digest = hashlib.sha256()
    for name in CATALOG_COLLECTIONS:
        for doc in sort_catalog_docs(list(docs_by_collection.get(name) or [])):
            digest.update(name.encode())
            digest.update(b"\n")
            digest.update(canonical_doc_json(doc).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def resolve_catalog_sqlite_path(process_environment: dict[str, str] | None = None) -> Path | None:
    env = process_environment if process_environment is not None else os.environ
    raw = str(env.get("GOB_CATALOG_SQLITE") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    bundled = bundle_path("catalog.sqlite")
    return bundled if bundled.is_file() else None


def open_catalog_connection(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")
    return conn


def read_catalog_meta(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT doc FROM catalog_meta WHERE id = ?", ('raw:"catalog"',)).fetchone()
    if not row:
        return {"version": "unknown", "source": "unknown", "counts": {}}
    from BackEnd.persistence.sqlite_collection import decode_doc

    return decode_doc(row[0])


def write_catalog_sqlite(
    docs_by_collection: dict[str, list[dict[str, Any]]],
    path: Path,
    *,
    source: str,
) -> dict[str, Any]:
    """Write a deterministic catalog sidecar. Two runs of the same docs match."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    version = catalog_version(docs_by_collection)
    counts = {name: len(docs_by_collection.get(name) or []) for name in CATALOG_COLLECTIONS}
    meta = {
        "_id": "catalog",
        "version": version,
        "source": source,
        "counts": counts,
        "exported_at": "1970-01-01T00:00:00+00:00",
    }
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA page_size = 4096")
        conn.execute(f"PRAGMA application_id = {_CATALOG_APPLICATION_ID}")
        for name in (*CATALOG_COLLECTIONS, "catalog_meta"):
            conn.execute(create_table_sql(name))
        ensure_generated_schema(conn, [*CATALOG_COLLECTIONS, "catalog_meta"])
        conn.execute(
            'INSERT INTO catalog_meta (id, doc) VALUES (?, ?)',
            (encode_id("catalog"), encode_doc(meta)),
        )
        for name in CATALOG_COLLECTIONS:
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


def write_catalog_json(
    docs_by_collection: dict[str, list[dict[str, Any]]],
    path: Path,
    *,
    source: str,
) -> dict[str, Any]:
    """Canonical JSON dump — release-to-release diffs, not the runtime sidecar."""
    meta = {
        "version": catalog_version(docs_by_collection),
        "source": source,
        "counts": {name: len(docs_by_collection.get(name) or []) for name in CATALOG_COLLECTIONS},
        "collections": {
            name: sort_catalog_docs(list(docs_by_collection.get(name) or []))
            for name in CATALOG_COLLECTIONS
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, default=_json_default, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return meta


def load_repo_fixture_docs() -> dict[str, list[dict[str, Any]]]:
    """The 7-play / 6-defense repo export plus in-repo FCP/HCT fallbacks."""
    import copy

    from tests.roster_fixtures import canonical_defense_rows, canonical_play_rows
    from BackEnd.playcall_skeletons.fcp_skeletons import GOB_FCP_SKELETON_DOCS
    from BackEnd.playcall_skeletons.hct_skeletons import GOB_HCT_SKELETON_DOCS

    plays = []
    for raw in canonical_play_rows():
        doc = copy.deepcopy(raw)
        doc["_id"] = doc.get("play_id") or doc.get("_id")
        plays.append(doc)
    defenses = [copy.deepcopy(doc) for doc in canonical_defense_rows()]
    fcp = []
    for index, raw in enumerate(GOB_FCP_SKELETON_DOCS):
        doc = copy.deepcopy(raw)
        doc.setdefault("_id", f"fcp-fallback-{index}")
        fcp.append(doc)
    hct = []
    for index, raw in enumerate(GOB_HCT_SKELETON_DOCS):
        doc = copy.deepcopy(raw)
        doc.setdefault("_id", f"hct-fallback-{index}")
        hct.append(doc)
    return {
        "plays": plays,
        "defenses": defenses,
        "fcp_skeletons": fcp,
        "hct_skeletons": hct,
    }


def empty_memory_catalog() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    for name in (*CATALOG_COLLECTIONS, "catalog_meta"):
        conn.execute(create_table_sql(name))
    ensure_generated_schema(conn, [*CATALOG_COLLECTIONS, "catalog_meta"])
    meta = {
        "_id": "catalog",
        "version": "empty-test",
        "source": "test",
        "counts": {name: 0 for name in CATALOG_COLLECTIONS},
        "exported_at": "1970-01-01T00:00:00+00:00",
    }
    conn.execute(
        'INSERT INTO catalog_meta (id, doc) VALUES (?, ?)',
        (encode_id("catalog"), encode_doc(meta)),
    )
    conn.commit()
    return conn


class CatalogCollection:
    """Read-only wrapper. Writes fail with CatalogWriteBlocked, not a silent no-op."""

    def __init__(self, coll: SqliteCollection):
        object.__setattr__(self, "_coll", coll)
        object.__setattr__(self, "name", coll.name)

    def __getattr__(self, name: str):
        if name in _MUTATORS:
            raise CatalogWriteBlocked(
                f"Write '{name}' refused on bundled catalog collection '{self.name}'. "
                "Catalog patches ship as an app update, not a save write."
            )
        return getattr(self._coll, name)

    @property
    def database(self):
        return self._coll.database

    @database.setter
    def database(self, value: Any) -> None:
        self._coll.database = value

    def aggregate(self, pipeline, *args, **kwargs):
        stages = list(pipeline)
        if any(isinstance(stage, dict) and ({"$out", "$merge"} & set(stage)) for stage in stages):
            raise CatalogWriteBlocked(
                f"Write 'aggregate($out/$merge)' refused on bundled catalog collection '{self.name}'."
            )
        return self._coll.aggregate(stages, *args, **kwargs)

    def __repr__(self) -> str:
        return f"<catalog-ro {self.name!r}>"


def bind_catalog_collections(
    conn: sqlite3.Connection,
    lock: threading.RLock,
) -> dict[str, CatalogCollection]:
    bound: dict[str, CatalogCollection] = {}
    for name in CATALOG_COLLECTIONS:
        raw = SqliteCollection(
            conn, name, writable=False, lock=lock, ensure_schema=False
        )
        bound[name] = CatalogCollection(raw)
    return bound
