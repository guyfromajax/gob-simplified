"""STORED generated columns + real indexes for SQLite JSON1 tables.

``json_extract`` in a WHERE clause still walks every row in C. Generated
columns persist franchise_id / player_id / team_id / week as real columns so
the query planner can seek. Filters that cannot be compiled fall back to a
full-table decode and ``match_query``. A fully compiled filter, including
range comparisons on those columns, is applied in SQL.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from bson import ObjectId


def _json_default(obj: Any) -> Any:
    if isinstance(obj, ObjectId):
        return {"$oid": str(obj)}
    if isinstance(obj, datetime):
        return {"$date": obj.isoformat()}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def encode_id(value: Any) -> str:
    """Must match ``sqlite_collection.encode_id`` (oid:/raw: row keys)."""
    if isinstance(value, ObjectId):
        return f"oid:{value}"
    return f"raw:{json.dumps(value, default=_json_default, separators=(',', ':'))}"


INDEXED_FIELDS: tuple[str, ...] = ("franchise_id", "player_id", "team_id", "week")
COLUMN_FOR_FIELD: dict[str, str] = {
    "franchise_id": "g_franchise_id",
    "player_id": "g_player_id",
    "team_id": "g_team_id",
    "week": "g_week",
}

# Prefer $oid (Mongo-shaped), then a bare JSON scalar (string ids on FPD/games).
_GENERATED_EXPR = (
    "COALESCE(json_extract(doc, '$.{field}.$oid'), json_extract(doc, '$.{field}'))"
)


def generated_sql(field: str) -> str:
    if field == "week":
        return "CAST(json_extract(doc, '$.week') AS TEXT)"
    return _GENERATED_EXPR.format(field=field)


def create_table_sql(name: str) -> str:
    cols = ", ".join(
        f"{column} TEXT GENERATED ALWAYS AS ({generated_sql(field)}) STORED"
        for field, column in COLUMN_FOR_FIELD.items()
    )
    return (
        f'CREATE TABLE IF NOT EXISTS "{name}" ('
        f"id TEXT PRIMARY KEY, doc TEXT NOT NULL, {cols})"
    )


def _rewrite_with_generated(conn: sqlite3.Connection, name: str) -> None:
    """SQLite refuses ALTER ADD STORED on a non-empty table. Copy instead."""
    tmp = f"{name}__gnew"
    conn.execute(f'DROP TABLE IF EXISTS "{tmp}"')
    conn.execute(create_table_sql(tmp).replace("IF NOT EXISTS ", ""))
    conn.execute(f'INSERT INTO "{tmp}" (id, doc) SELECT id, doc FROM "{name}"')
    conn.execute(f'DROP TABLE "{name}"')
    conn.execute(f'ALTER TABLE "{tmp}" RENAME TO "{name}"')


def ensure_indexes(conn: sqlite3.Connection, name: str) -> None:
    for field, column in COLUMN_FOR_FIELD.items():
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS "idx_{name}_{column}" '
            f'ON "{name}" ({column})'
        )
    conn.execute(
        f'CREATE INDEX IF NOT EXISTS "idx_{name}_fid_pid" '
        f'ON "{name}" (g_franchise_id, g_player_id)'
    )
    conn.execute(
        f'CREATE INDEX IF NOT EXISTS "idx_{name}_fid_tid" '
        f'ON "{name}" (g_franchise_id, g_team_id)'
    )
    conn.execute(
        f'CREATE INDEX IF NOT EXISTS "idx_{name}_fid_week" '
        f'ON "{name}" (g_franchise_id, g_week)'
    )


def ensure_generated_schema(conn: sqlite3.Connection, table_names: list[str]) -> None:
    """Ensure STORED generated columns + indexes. Rewrites non-empty old tables."""
    for name in table_names:
        existing = {
            row[1]
            for row in conn.execute(f'PRAGMA table_xinfo("{name}")').fetchall()
        }
        if "id" not in existing:
            continue
        needed = set(COLUMN_FOR_FIELD.values())
        if not needed <= existing:
            _rewrite_with_generated(conn, name)
        ensure_indexes(conn, name)


class SqliteConnState:
    """Shared connection + lock + transaction depth for every collection."""

    def __init__(self, conn: sqlite3.Connection, lock) -> None:
        self.conn = conn
        self.lock = lock
        self.tx_depth = 0


@contextmanager
def store_transaction(state: SqliteConnState) -> Iterator[None]:
    """Nestable write transaction. Inner ``_commit`` calls are no-ops.

    SQLite's implicit DML transaction is left open until the outermost
    exit, then committed (or rolled back on error).
    """
    with state.lock:
        outermost = state.tx_depth == 0
        state.tx_depth += 1
    try:
        yield
        with state.lock:
            state.tx_depth -= 1
            if outermost:
                state.conn.commit()
    except Exception:
        with state.lock:
            state.tx_depth -= 1
            if outermost:
                state.conn.rollback()
        raise


def id_sql_values(value: Any) -> list[str]:
    """Encode ``_id`` so both oid: and raw: row keys match a string/ObjectId."""
    out: list[str] = [encode_id(value)]
    if isinstance(value, str):
        try:
            out.append(encode_id(ObjectId(value)))
        except Exception:
            pass
    elif isinstance(value, ObjectId):
        out.append(encode_id(str(value)))
    # Unique, stable order.
    seen: set[str] = set()
    unique: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def index_sql_values(value: Any) -> list[str] | None:
    """Values that may appear in a g_* column, or None if not compilable."""
    if isinstance(value, dict):
        if "$in" in value:
            out: list[str] = []
            for item in value["$in"]:
                compiled = index_sql_values(item)
                if compiled is None:
                    return None
                out.extend(compiled)
            return out
        if "$oid" in value:
            return [str(value["$oid"])]
        return None
    if isinstance(value, ObjectId):
        return [str(value)]
    if value is None:
        return []
    return [str(value)]


# Comparison ops on an extracted column. ``$in`` / ``$eq`` compile alongside
# them when every operator in the dict is one of these.
_CMP_OPS = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<="}
_ADJACENT_OPS = set(_CMP_OPS) | {"$in", "$eq"}


def _is_real_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def compile_indexed_value(column: str, value: Any) -> tuple[str, list[Any]] | None:
    """SQL for one extracted-column predicate, or None if ``match_query`` must run it.

    Equality and ``$in`` stay string matches against the TEXT generated column.
    ``$gt`` / ``$gte`` / ``$lt`` / ``$lte`` compile too. Numeric bounds use
    ``CAST(column AS REAL)`` plus a numeric-text guard, because ``g_week`` is
    TEXT and ``"10" <= "26"`` is false in SQLite. String bounds stay text
    comparisons. A dict that also contains ``$in`` or ``$eq`` compiles when
    every operator is one of those. Anything else (``$ne``, ``$regex``, …)
    returns None so the row is still decoded and checked in Python.
    """
    if isinstance(value, dict) and any(op in _CMP_OPS for op in value):
        return _compile_comparison_value(column, value)
    compiled = index_sql_values(value)
    if compiled is None:
        return None
    if not compiled:
        return f"{column} IS NULL", []
    if len(compiled) == 1:
        return f"{column} = ?", list(compiled)
    placeholders = ",".join("?" * len(compiled))
    return f"{column} IN ({placeholders})", list(compiled)


def _compile_comparison_value(column: str, value: dict[str, Any]) -> tuple[str, list[Any]] | None:
    if not set(value) <= _ADJACENT_OPS:
        return None
    bounds = [(op, value[op]) for op in _CMP_OPS if op in value]
    kinds: list[str] = []
    for _op, bound in bounds:
        if _is_real_number(bound):
            kinds.append("num")
        elif isinstance(bound, str):
            kinds.append("str")
        else:
            return None
    if len(set(kinds)) != 1:
        return None
    numeric = kinds[0] == "num"
    parts: list[str] = []
    params: list[Any] = []
    if "$in" in value:
        compiled = index_sql_values({"$in": value["$in"]})
        if compiled is None:
            return None
        if not compiled:
            parts.append("0")
        else:
            placeholders = ",".join("?" * len(compiled))
            parts.append(f"{column} IN ({placeholders})")
            params.extend(compiled)
    if "$eq" in value:
        compiled = index_sql_values(value["$eq"])
        if compiled is None:
            return None
        if not compiled:
            parts.append(f"{column} IS NULL")
        elif len(compiled) == 1:
            parts.append(f"{column} = ?")
            params.append(compiled[0])
        else:
            placeholders = ",".join("?" * len(compiled))
            parts.append(f"{column} IN ({placeholders})")
            params.extend(compiled)
    for op, bound in bounds:
        sql_op = _CMP_OPS[op]
        if numeric:
            # Reject stored text that is not itself a number. SQLite's CAST
            # turns 'abc' into 0, which would disagree with Python's TypeError
            # (match_query treats that comparison as a non-match).
            parts.append(
                f"(CAST({column} AS REAL) {sql_op} ? AND {column} = CAST({column} AS REAL))"
            )
            params.append(bound)
        else:
            parts.append(f"{column} {sql_op} ?")
            params.append(bound)
    if not parts:
        return None
    return " AND ".join(parts), params


def compile_filter(filt: dict[str, Any] | None) -> tuple[str, list[Any]] | None:
    """Push every compilable clause to SQL; leave the rest to ``match_query``.

    Returns None only when *no* clause can be pushed (full-table decode).
    ``{"_id": gid, "players.playerId": pid}`` therefore seeks the primary key
    and residual-matches the player predicate — the sim write path.
    An empty / None filter is a full scan.
    """
    if not filt:
        return None
    clauses: list[str] = []
    params: list[Any] = []
    for key, value in filt.items():
        if key == "_id":
            if isinstance(value, dict) and "$in" in value:
                ids: list[str] = []
                for item in value["$in"]:
                    ids.extend(id_sql_values(item))
                if not ids:
                    clauses.append("0")
                    continue
                placeholders = ",".join("?" * len(ids))
                clauses.append(f"id IN ({placeholders})")
                params.extend(ids)
                continue
            if isinstance(value, dict):
                continue
            ids = id_sql_values(value)
            placeholders = ",".join("?" * len(ids))
            clauses.append(f"id IN ({placeholders})")
            params.extend(ids)
            continue
        if key not in COLUMN_FOR_FIELD:
            continue
        column = COLUMN_FOR_FIELD[key]
        compiled_sql = compile_indexed_value(column, value)
        if compiled_sql is None:
            continue
        clause, clause_params = compiled_sql
        clauses.append(clause)
        params.extend(clause_params)
    if not clauses:
        return None
    return " AND ".join(clauses), params


def filter_fully_compiled(filt: dict[str, Any] | None) -> bool:
    """True when every clause was pushed to SQL — ``LIMIT 1`` is safe for find_one."""
    if not filt:
        return False
    for key, value in filt.items():
        if key == "_id":
            if isinstance(value, dict) and "$in" not in value:
                return False
            continue
        if key not in COLUMN_FOR_FIELD:
            return False
        if compile_indexed_value(COLUMN_FOR_FIELD[key], value) is None:
            return False
    return True
