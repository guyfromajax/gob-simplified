"""JSON1-backed collection with a pymongo-shaped surface. Draws nothing."""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.results import (
    BulkWriteResult,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)

from BackEnd.persistence.sqlite_query import (
    apply_update,
    match_query,
    project_doc,
    sort_docs,
)
from BackEnd.persistence.sqlite_schema import (
    COLUMN_FOR_FIELD,
    SqliteConnState,
    compile_filter,
    create_table_sql,
    ensure_generated_schema,
    filter_fully_compiled,
    store_transaction,
)


def _default(obj: Any) -> Any:
    if isinstance(obj, ObjectId):
        return {"$oid": str(obj)}
    if isinstance(obj, datetime):
        return {"$date": obj.isoformat()}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _hook(obj: dict[str, Any]) -> Any:
    if set(obj.keys()) == {"$oid"}:
        return ObjectId(obj["$oid"])
    if set(obj.keys()) == {"$date"}:
        return datetime.fromisoformat(obj["$date"])
    return obj


def encode_doc(doc: dict[str, Any]) -> str:
    return json.dumps(doc, default=_default, separators=(",", ":"))


def decode_doc(raw: str) -> dict[str, Any]:
    return json.loads(raw, object_hook=_hook)


def encode_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return f"oid:{value}"
    return f"raw:{json.dumps(value, default=_default, separators=(',', ':'))}"


class SqliteCursor:
    def __init__(self, docs: list[dict[str, Any]]):
        self._docs = docs

    def sort(self, key_or_spec: Any, direction: int | None = None) -> SqliteCursor:
        self._docs = sort_docs(self._docs, key_or_spec, direction)
        return self

    def limit(self, count: int) -> SqliteCursor:
        self._docs = self._docs[: int(count)]
        return self

    def skip(self, count: int) -> SqliteCursor:
        self._docs = self._docs[int(count) :]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __len__(self) -> int:
        return len(self._docs)


class SqliteCollection:
    """One JSON1 table with generated-column indexes for hot equality filters.

    Queries that compile to ``id`` / ``g_franchise_id`` / ``g_player_id`` /
    ``g_team_id`` are index seeks. Everything else still full-scans. Python
    ``match_query`` always re-checks decoded rows so a SQL miss is never a
    correctness miss.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        name: str,
        *,
        writable: bool = True,
        lock: threading.RLock | None = None,
        state: SqliteConnState | None = None,
    ):
        self.name = name
        self.database = None
        self._conn = conn
        self._writable = writable
        self._state = state
        self._lock = (state.lock if state is not None else lock) or threading.RLock()
        self._indexes: list[dict[str, Any]] = []
        with self._lock:
            self._conn.execute(create_table_sql(name))
            self._commit()

    def _require_write(self) -> None:
        if not self._writable:
            from BackEnd.persistence.guards import ProdWriteBlocked
            raise ProdWriteBlocked(
                f"Write blocked on local SQLite collection '{self.name}' "
                f"(GOB_DB_ACCESS=read)."
            )

    def _select(
        self,
        filt: dict[str, Any] | None = None,
        *,
        one: bool = False,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Decode only the rows SQL can narrow to; residual-match in Python.

        ``one=True`` stops at the first residual match. When every filter
        clause compiled, that is a ``LIMIT 1`` index seek — Mongo ``find_one``
        semantics. Without the limit, ``find_one({franchise_id})`` would still
        decode every game in the franchise.
        """
        compiled = compile_filter(filt)
        limit_sql = one and filter_fully_compiled(filt)
        with self._lock:
            if compiled is None:
                sql = f'SELECT id, doc FROM "{self.name}"'
                params: list[Any] = []
            else:
                where, params = compiled
                sql = f'SELECT id, doc FROM "{self.name}" WHERE {where}'
            if limit_sql:
                sql += " LIMIT 1"
            cur = self._conn.execute(sql, params)
            matched: list[tuple[str, dict[str, Any]]] = []
            for row_id, raw in cur:
                doc = decode_doc(raw)
                if match_query(doc, filt):
                    matched.append((row_id, doc))
                    if one:
                        break
        return matched

    def _rows(self) -> list[tuple[str, dict[str, Any]]]:
        with self._lock:
            cur = self._conn.execute(f'SELECT id, doc FROM "{self.name}"')
            return [(row_id, decode_doc(raw)) for row_id, raw in cur.fetchall()]

    def _put(self, doc: dict[str, Any]) -> None:
        stored = copy.deepcopy(doc)
        if "_id" not in stored:
            stored["_id"] = ObjectId()
        row_id = encode_id(stored["_id"])
        with self._lock:
            self._conn.execute(
                f'INSERT OR REPLACE INTO "{self.name}" (id, doc) VALUES (?, ?)',
                (row_id, encode_doc(stored)),
            )

    def _delete_id(self, row_id: str) -> None:
        with self._lock:
            self._conn.execute(f'DELETE FROM "{self.name}" WHERE id = ?', (row_id,))

    def _commit(self) -> None:
        if self._state is not None and self._state.tx_depth > 0:
            return
        with self._lock:
            self._conn.commit()

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None):
        matched = [copy.deepcopy(doc) for _row_id, doc in self._select(filter)]
        if projection:
            matched = [project_doc(doc, projection) for doc in matched]
        return SqliteCursor(matched)

    def find_one(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None):
        for _row_id, doc in self._select(filter, one=True):
            out = copy.deepcopy(doc)
            if projection:
                out = project_doc(out, projection)
            return out
        return None

    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        return sum(1 for _row_id, _doc in self._select(filter))

    def estimated_document_count(self) -> int:
        with self._lock:
            cur = self._conn.execute(f'SELECT COUNT(*) FROM "{self.name}"')
            return int(cur.fetchone()[0])

    def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        self._require_write()
        stored = copy.deepcopy(document)
        if "_id" not in stored:
            stored["_id"] = ObjectId()
        self._put(stored)
        self._commit()
        return InsertOneResult(stored["_id"], acknowledged=True)

    def insert_many(self, documents, ordered: bool = True) -> InsertManyResult:
        self._require_write()
        ids = []
        for document in documents:
            stored = copy.deepcopy(document)
            if "_id" not in stored:
                stored["_id"] = ObjectId()
            self._put(stored)
            ids.append(stored["_id"])
        self._commit()
        return InsertManyResult(ids, acknowledged=True)

    def replace_one(self, filter: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> UpdateResult:
        self._require_write()
        for row_id, doc in self._select(filter, one=True):
            if match_query(doc, filter):
                stored = copy.deepcopy(replacement)
                if "_id" not in stored:
                    stored["_id"] = doc.get("_id")
                self._delete_id(row_id)
                self._put(stored)
                self._commit()
                return UpdateResult({"n": 1, "nModified": 1, "ok": 1.0}, acknowledged=True)
        if upsert:
            stored = copy.deepcopy(replacement)
            if "_id" not in stored:
                stored["_id"] = ObjectId()
            self._put(stored)
            self._commit()
            return UpdateResult(
                {"n": 1, "nModified": 0, "ok": 1.0, "upserted": stored["_id"]},
                acknowledged=True,
            )
        return UpdateResult({"n": 0, "nModified": 0, "ok": 1.0}, acknowledged=True)

    def _update_matches(self, filter, update, upsert, many) -> UpdateResult:
        self._require_write()
        matched = 0
        modified = 0
        upserted = None
        for row_id, doc in self._select(filter, one=not many):
            if not match_query(doc, filter):
                continue
            matched += 1
            before = encode_doc(doc)
            updated = apply_update(copy.deepcopy(doc), update, inserting=False)
            if encode_doc(updated) != before:
                modified += 1
            self._delete_id(row_id)
            self._put(updated)
            if not many:
                break
        if matched == 0 and upsert:
            seed: dict[str, Any] = {}
            # Mongo copies equality predicates from the filter onto the new document.
            for key, value in (filter or {}).items():
                if str(key).startswith("$") or isinstance(value, dict):
                    continue
                seed[key] = value
            inserted = apply_update(seed, update, inserting=True)
            if "_id" not in inserted:
                inserted["_id"] = ObjectId()
            self._put(inserted)
            upserted = inserted["_id"]
            matched = 1
        self._commit()
        raw = {"n": matched, "nModified": modified, "ok": 1.0}
        if upserted is not None:
            raw["upserted"] = upserted
        return UpdateResult(raw, acknowledged=True)

    def update_one(self, filter, update, upsert: bool = False) -> UpdateResult:
        return self._update_matches(filter, update, upsert, many=False)

    def update_many(self, filter, update, upsert: bool = False) -> UpdateResult:
        return self._update_matches(filter, update, upsert, many=True)

    def delete_one(self, filter: dict[str, Any] | None = None) -> DeleteResult:
        self._require_write()
        deleted = 0
        for row_id, doc in self._select(filter, one=True):
            if match_query(doc, filter):
                self._delete_id(row_id)
                deleted = 1
                break
        self._commit()
        return DeleteResult({"n": deleted, "ok": 1.0}, acknowledged=True)

    def delete_many(self, filter: dict[str, Any] | None = None) -> DeleteResult:
        self._require_write()
        deleted = 0
        for row_id, doc in self._select(filter):
            if match_query(doc, filter):
                self._delete_id(row_id)
                deleted += 1
        self._commit()
        return DeleteResult({"n": deleted, "ok": 1.0}, acknowledged=True)

    def find_one_and_update(self, filter, update, **kwargs):
        doc = self.find_one(filter)
        result = self.update_one(filter, update, upsert=bool(kwargs.get("upsert")))
        if result.matched_count == 0 and result.upserted_id is None:
            return None
        if kwargs.get("return_document") and str(kwargs.get("return_document")).endswith("AFTER"):
            return self.find_one(filter) or self.find_one({"_id": result.upserted_id})
        return doc

    def find_one_and_replace(self, filter, replacement, **kwargs):
        doc = self.find_one(filter)
        self.replace_one(filter, replacement, upsert=bool(kwargs.get("upsert")))
        return doc

    def find_one_and_delete(self, filter, **kwargs):
        doc = self.find_one(filter)
        if doc is not None:
            self.delete_one(filter)
        return doc

    def bulk_write(self, operations, ordered: bool = True):
        self._require_write()
        if self._state is not None:
            with store_transaction(self._state):
                return self._bulk_write_ops(operations)
        return self._bulk_write_ops(operations)

    def _bulk_write_ops(self, operations):
        inserted = 0
        matched = 0
        modified = 0
        deleted = 0
        upserted = 0
        for op in operations:
            name = type(op).__name__
            if name == "InsertOne":
                self.insert_one(op._doc)
                inserted += 1
            elif name == "UpdateOne":
                result = self.update_one(op._filter, op._doc, upsert=bool(getattr(op, "_upsert", False)))
                matched += result.matched_count
                modified += result.modified_count
                if result.upserted_id is not None:
                    upserted += 1
            elif name == "UpdateMany":
                result = self.update_many(op._filter, op._doc, upsert=bool(getattr(op, "_upsert", False)))
                matched += result.matched_count
                modified += result.modified_count
            elif name == "ReplaceOne":
                result = self.replace_one(op._filter, op._doc, upsert=bool(getattr(op, "_upsert", False)))
                matched += result.matched_count
                modified += result.modified_count
                if result.upserted_id is not None:
                    upserted += 1
            elif name == "DeleteOne":
                result = self.delete_one(op._filter)
                deleted += result.deleted_count
            elif name == "DeleteMany":
                result = self.delete_many(op._filter)
                deleted += result.deleted_count
            else:
                raise TypeError(f"Unsupported bulk op {name}")
        return BulkWriteResult(
            {
                "nInserted": inserted,
                "nMatched": matched,
                "nModified": modified,
                "nRemoved": deleted,
                "nUpserted": upserted,
                "ok": 1.0,
            },
            acknowledged=True,
        )

    def create_index(self, keys, **kwargs) -> str:
        name = kwargs.get("name") or "idx"
        key_spec = keys if isinstance(keys, list) else [(keys, 1)]
        self._indexes.append({"key": dict(key_spec), "name": name})
        columns: list[str] = []
        for field, _direction in key_spec:
            if field not in COLUMN_FOR_FIELD:
                return name
            columns.append(COLUMN_FOR_FIELD[field])
        unique = "UNIQUE " if kwargs.get("unique") else ""
        safe_name = str(name).replace('"', "")
        with self._lock:
            self._conn.execute(
                f'CREATE {unique}INDEX IF NOT EXISTS "{safe_name}" '
                f'ON "{self.name}" ({", ".join(columns)})'
            )
            self._commit()
        return name

    def create_indexes(self, indexes, **kwargs):
        for index in indexes:
            keys = getattr(index, "document", {}).get("keys") or getattr(index, "_keys", [])
            name = getattr(index, "document", {}).get("name") or "idx"
            self.create_index(list(keys), name=name)

    def list_indexes(self):
        return list(self._indexes)

    def drop_index(self, name) -> None:
        self._indexes = [idx for idx in self._indexes if idx.get("name") != name]

    def drop_indexes(self) -> None:
        self._indexes = []

    def drop(self) -> None:
        self._require_write()
        with self._lock:
            self._conn.execute(f'DROP TABLE IF EXISTS "{self.name}"')
            self._conn.execute(create_table_sql(self.name))
            ensure_generated_schema(self._conn, [self.name])
            self._conn.commit()

    def distinct(self, key: str, filter: dict[str, Any] | None = None):
        from BackEnd.persistence.sqlite_query import get_path, has_path
        seen = []
        for _row_id, doc in self._select(filter):
            if not match_query(doc, filter):
                continue
            if not has_path(doc, key):
                continue
            value = get_path(doc, key)
            if value not in seen:
                seen.append(value)
        return seen

    def aggregate(self, pipeline, *args, **kwargs):
        docs = [copy.deepcopy(doc) for _row_id, doc in self._rows()]
        for stage in pipeline or []:
            if not isinstance(stage, dict) or len(stage) != 1:
                continue
            op, spec = next(iter(stage.items()))
            if op == "$match":
                docs = [doc for doc in docs if match_query(doc, spec)]
            elif op == "$project":
                docs = [project_doc(doc, spec) for doc in docs]
            elif op == "$limit":
                docs = docs[: int(spec)]
            elif op == "$skip":
                docs = docs[int(spec) :]
            elif op == "$sort":
                docs = sort_docs(docs, list(spec.items()))
        return docs

    def __repr__(self) -> str:
        return f"<SqliteCollection {self.name!r}>"


class NullCollection:
    """Disabled collection: reads empty, writes vanish. Used for eog_band_log."""

    def __init__(self, name: str):
        self.name = name
        self.database = None

    def find(self, *args, **kwargs):
        return SqliteCursor([])

    def find_one(self, *args, **kwargs):
        return None

    def count_documents(self, *args, **kwargs) -> int:
        return 0

    def estimated_document_count(self) -> int:
        return 0

    def insert_one(self, document):
        return InsertOneResult(document.get("_id") if isinstance(document, dict) else None, acknowledged=True)

    def insert_many(self, documents, ordered: bool = True):
        return InsertManyResult([], acknowledged=True)

    def update_one(self, *args, **kwargs):
        return UpdateResult({"n": 0, "nModified": 0, "ok": 1.0}, acknowledged=True)

    def update_many(self, *args, **kwargs):
        return UpdateResult({"n": 0, "nModified": 0, "ok": 1.0}, acknowledged=True)

    def replace_one(self, *args, **kwargs):
        return UpdateResult({"n": 0, "nModified": 0, "ok": 1.0}, acknowledged=True)

    def delete_one(self, *args, **kwargs):
        return DeleteResult({"n": 0, "ok": 1.0}, acknowledged=True)

    def delete_many(self, *args, **kwargs):
        return DeleteResult({"n": 0, "ok": 1.0}, acknowledged=True)

    def bulk_write(self, operations, ordered: bool = True):
        return BulkWriteResult(
            {"nInserted": 0, "nMatched": 0, "nModified": 0, "nRemoved": 0, "nUpserted": 0, "ok": 1.0},
            acknowledged=True,
        )

    def find_one_and_update(self, *args, **kwargs):
        return None

    def find_one_and_replace(self, *args, **kwargs):
        return None

    def find_one_and_delete(self, *args, **kwargs):
        return None

    def create_index(self, *args, **kwargs) -> str:
        return "noop"

    def create_indexes(self, *args, **kwargs):
        return []

    def list_indexes(self):
        return []

    def drop(self) -> None:
        return None

    def distinct(self, *args, **kwargs):
        return []

    def aggregate(self, *args, **kwargs):
        return []

    def __repr__(self) -> str:
        return f"<NullCollection {self.name!r}>"


class RemoteUnavailable:
    """Refuse remote collections outside the test profile.

    Desktop/loopback must not answer auth, billing, community, or user-record
    reads from an empty in-memory store. Tests keep mongomock remotes.
    """

    def __init__(self, name: str):
        self.name = name
        self.database = None

    def _refuse(self, *_args, **_kwargs):
        raise RuntimeError(
            f"SQLite profile refuses remote collection {self.name!r}. "
            "Auth, billing, community, and user records are served by the remote "
            "backend. This process must not answer from an empty in-memory store."
        )

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._refuse

    def __repr__(self) -> str:
        return f"<RemoteUnavailable {self.name!r}>"
