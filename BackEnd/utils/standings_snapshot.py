"""Week snapshot for GET /franchise/standings.

The live build reads the franchise document (results and schedule), every
franchise-team row, and the teams collection. This module keeps the already
sorted rows for one franchise week. Scopes filter that list in the route.

Fresh only when meta matches this week and season, is not stale, and the
body was built at that generation. Anything else falls back to the live
build, then stores. A miss does not error.

``note_standings_stale`` bumps ``gen`` on the meta document. The body is a
second document stamped with the generation it was built at. A rebuild
writes the rows, then clears stale only if that generation is still current.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _collection():
    from BackEnd.persistence import get_store

    return get_store().standings_snapshots_collection


def snapshot_id(franchise_id: str) -> str:
    return str(franchise_id)


def meta_id(franchise_id: str) -> str:
    return f"meta:{franchise_id}"


def read_snapshot(franchise_id: str) -> dict[str, Any] | None:
    doc = _collection().find_one({"_id": snapshot_id(franchise_id)})
    return doc if isinstance(doc, dict) else None


def read_meta(franchise_id: str) -> dict[str, Any] | None:
    doc = _collection().find_one({"_id": meta_id(franchise_id)})
    return doc if isinstance(doc, dict) else None


def _meta_matches_week(meta: dict[str, Any] | None, *, week: int, season: int) -> bool:
    if not meta or meta.get("stale"):
        return False
    try:
        return int(meta.get("week")) == int(week) and int(meta.get("season") or 1) == int(season)
    except (TypeError, ValueError):
        return False


def _generation(doc: dict[str, Any] | None) -> int:
    if not doc:
        return 0
    try:
        return int(doc.get("gen") or 0)
    except (TypeError, ValueError):
        return 0


def fresh_rows(franchise_id: str, *, week: int, season: int) -> list[dict[str, Any]] | None:
    meta = read_meta(franchise_id)
    if not _meta_matches_week(meta, week=week, season=season):
        return None
    body = read_snapshot(franchise_id)
    if not body:
        return None
    try:
        built = int(meta.get("built_gen"))
    except (TypeError, ValueError):
        return None
    if _generation(body) != built:
        return None
    rows = body.get("rows")
    if not isinstance(rows, list):
        return None
    return list(rows)


def note_standings_stale(franchise_id: str | None) -> None:
    """Bump meta ``gen`` and mark the rows stale. Creates the counter if needed."""
    if not franchise_id:
        return
    try:
        _collection().update_one(
            {"_id": meta_id(franchise_id)},
            {
                "$inc": {"gen": 1},
                "$set": {"stale": True, "franchise_id": str(franchise_id)},
            },
            upsert=True,
        )
    except Exception:
        logger.exception("[STANDINGS] snapshot invalidate failed franchise_id=%s", franchise_id)


def _as_sqlite(coll):
    from BackEnd.persistence.sqlite_collection import SqliteCollection

    return coll if isinstance(coll, SqliteCollection) else None


def _write_body(doc: dict[str, Any]) -> None:
    coll = _collection()
    sqlite_coll = _as_sqlite(coll)
    if sqlite_coll is not None:
        sqlite_coll.upsert_owned(doc)
    else:
        coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)


def _commit_meta(franchise_id: str, gen: int, week: int, season: int, *, existed: bool) -> bool:
    coll = _collection()
    mid = meta_id(franchise_id)
    fields = {
        "franchise_id": str(franchise_id),
        "stale": False,
        "week": int(week),
        "season": int(season or 1),
        "built_gen": int(gen),
    }
    if not existed:
        result = coll.update_one(
            {"_id": mid},
            {"$setOnInsert": {**fields, "gen": int(gen)}},
            upsert=True,
        )
        return getattr(result, "upserted_id", None) is not None
    result = coll.update_one(
        {"_id": mid, "gen": int(gen)},
        {"$set": fields},
    )
    return getattr(result, "matched_count", 0) > 0


def publish_rows(
    franchise_id: str,
    *,
    week: int,
    season: int,
    rows: list[dict[str, Any]],
    meta: dict[str, Any] | None,
) -> bool:
    existed = meta is not None
    gen = _generation(meta) if existed else 0
    _write_body(
        {
            "_id": snapshot_id(franchise_id),
            "franchise_id": str(franchise_id),
            "gen": gen,
            "rows": rows,
        }
    )
    return _commit_meta(franchise_id, gen, week, season, existed=existed)


def refresh_standings_snapshot(
    franchise_id: str,
    *,
    week: int,
    season: int,
    rows: list[dict[str, Any]],
) -> None:
    """Store rows built from the week that is about to be committed."""
    try:
        meta = read_meta(franchise_id)
        publish_rows(franchise_id, week=week, season=season, rows=rows, meta=meta)
    except Exception:
        logger.exception(
            "[STANDINGS] snapshot rebuild failed franchise_id=%s week=%s",
            franchise_id,
            week,
        )


def rows_for_request(
    franchise_id: str,
    *,
    week: int,
    season: int,
    live_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]] | None, str]:
    """Return cached rows, or None when the caller must build them.

    Pass ``live_rows`` after a miss to store them. The store is skipped when
    ``gen`` moved during the build.
    """
    if live_rows is None:
        cached = fresh_rows(franchise_id, week=week, season=season)
        if cached is not None:
            return cached, "snapshot"
        return None, "live"
    meta = read_meta(franchise_id)
    try:
        publish_rows(franchise_id, week=week, season=season, rows=live_rows, meta=meta)
    except Exception:
        logger.exception("[STANDINGS] snapshot store failed franchise_id=%s", franchise_id)
    return live_rows, "live"
