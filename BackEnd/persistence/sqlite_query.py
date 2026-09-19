"""Mongo-shaped query matching and update application. Draws nothing."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId


def oid_key(value: Any) -> str | None:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict) and set(value.keys()) == {"$oid"}:
        return str(value["$oid"])
    return None


def values_equal(left: Any, right: Any) -> bool:
    if left == right:
        return True
    left_oid = oid_key(left)
    right_oid = oid_key(right)
    if left_oid is not None and right_oid is not None:
        return left_oid == right_oid
    if left_oid is not None and str(right) == left_oid:
        return True
    if right_oid is not None and str(left) == right_oid:
        return True
    return False


def get_path(doc: dict[str, Any], path: str) -> Any:
    current: Any = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def has_path(doc: dict[str, Any], path: str) -> bool:
    current: Any = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def set_path(doc: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = doc
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            current[part] = nxt
        current = nxt
    current[parts[-1]] = value


def unset_path(doc: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    current = doc
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            return
        current = nxt
    current.pop(parts[-1], None)


def _compare(value: Any, op: str, expected: Any) -> bool:
    if value is None:
        return False
    try:
        if op == "$gt":
            return value > expected
        if op == "$gte":
            return value >= expected
        if op == "$lt":
            return value < expected
        if op == "$lte":
            return value <= expected
    except TypeError:
        return False
    return False


def resolve_value(doc: dict[str, Any], spec: Any) -> Any:
    if isinstance(spec, str) and spec.startswith("$"):
        path = spec[1:]
        return get_path(doc, path) if has_path(doc, path) else None
    if isinstance(spec, dict) and spec and all(str(key).startswith("$") for key in spec):
        if len(spec) != 1:
            return None
        op, args = next(iter(spec.items()))
        return eval_expr(doc, op, args)
    return spec


def eval_expr(doc: dict[str, Any], op: str, args: Any) -> Any:
    if op == "$ifNull":
        value = resolve_value(doc, args[0])
        return resolve_value(doc, args[1]) if value is None else value
    if op == "$divide":
        left = resolve_value(doc, args[0])
        right = resolve_value(doc, args[1])
        if not right:
            return None
        return left / right
    if op == "$multiply":
        result = 1
        for item in args:
            value = resolve_value(doc, item)
            if value is None:
                return None
            result *= value
        return result
    if op == "$add":
        result = 0
        for item in args:
            value = resolve_value(doc, item)
            result += 0 if value is None else value
        return result
    if op == "$gt":
        return (resolve_value(doc, args[0]) or 0) > (resolve_value(doc, args[1]) or 0)
    if op == "$gte":
        return (resolve_value(doc, args[0]) or 0) >= (resolve_value(doc, args[1]) or 0)
    if op == "$lt":
        return (resolve_value(doc, args[0]) or 0) < (resolve_value(doc, args[1]) or 0)
    if op == "$lte":
        return (resolve_value(doc, args[0]) or 0) <= (resolve_value(doc, args[1]) or 0)
    if op == "$eq":
        return values_equal(resolve_value(doc, args[0]), resolve_value(doc, args[1]))
    if op == "$and":
        return all(bool(resolve_value(doc, item)) for item in args)
    if op == "$or":
        return any(bool(resolve_value(doc, item)) for item in args)
    if op == "$cond":
        if isinstance(args, dict):
            pred, then, els = args.get("if"), args.get("then"), args.get("else")
        else:
            pred, then, els = args[0], args[1], args[2]
        return resolve_value(doc, then) if resolve_value(doc, pred) else resolve_value(doc, els)
    return None


def match_query(doc: dict[str, Any], query: dict[str, Any] | None) -> bool:
    if not query:
        return True
    for key, condition in query.items():
        if key == "$expr":
            if not resolve_value(doc, condition):
                return False
            continue
        if key == "$and":
            if not all(match_query(doc, part) for part in condition):
                return False
            continue
        if key == "$or":
            if not any(match_query(doc, part) for part in condition):
                return False
            continue
        if key == "$nor":
            if any(match_query(doc, part) for part in condition):
                return False
            continue
        if not _match_field(doc, key, condition):
            return False
    return True


def _match_field(doc: dict[str, Any], path: str, condition: Any) -> bool:
    if isinstance(condition, dict) and any(str(k).startswith("$") for k in condition):
        actual = get_path(doc, path) if has_path(doc, path) else None
        present = has_path(doc, path)
        for op, expected in condition.items():
            if op == "$eq":
                if not values_equal(actual, expected):
                    return False
            elif op == "$ne":
                if values_equal(actual, expected):
                    return False
            elif op in {"$gt", "$gte", "$lt", "$lte"}:
                if not _compare(actual, op, expected):
                    return False
            elif op == "$in":
                if not any(values_equal(actual, item) for item in expected):
                    return False
            elif op == "$nin":
                if any(values_equal(actual, item) for item in expected):
                    return False
            elif op == "$exists":
                if bool(present) != bool(expected):
                    return False
            elif op == "$regex":
                import re
                flags = 0
                if isinstance(condition.get("$options"), str) and "i" in condition["$options"]:
                    flags = re.IGNORECASE
                if actual is None or re.search(str(expected), str(actual), flags) is None:
                    return False
            elif op == "$options":
                continue
            elif op == "$not":
                if _match_field(doc, path, expected):
                    return False
            else:
                if not values_equal(actual, expected):
                    return False
        return True
    actual = get_path(doc, path) if has_path(doc, path) else None
    return values_equal(actual, condition)


def apply_update(doc: dict[str, Any], update: dict[str, Any], *, inserting: bool = False) -> dict[str, Any]:
    if not update:
        return doc
    if any(not str(key).startswith("$") for key in update):
        replacement = dict(update)
        if "_id" in doc and "_id" not in replacement:
            replacement["_id"] = doc["_id"]
        return replacement
    for op, spec in update.items():
        if op == "$set":
            for path, value in spec.items():
                set_path(doc, path, value)
        elif op == "$setOnInsert":
            if inserting:
                for path, value in spec.items():
                    set_path(doc, path, value)
        elif op == "$unset":
            for path in spec:
                unset_path(doc, path)
        elif op == "$inc":
            for path, amount in spec.items():
                current = get_path(doc, path) if has_path(doc, path) else 0
                set_path(doc, path, current + amount)
        elif op == "$push":
            for path, value in spec.items():
                current = get_path(doc, path) if has_path(doc, path) else None
                if not isinstance(current, list):
                    current = []
                if isinstance(value, dict) and "$each" in value:
                    current.extend(value["$each"])
                else:
                    current.append(value)
                set_path(doc, path, current)
        elif op == "$addToSet":
            for path, value in spec.items():
                current = get_path(doc, path) if has_path(doc, path) else None
                if not isinstance(current, list):
                    current = []
                items = value["$each"] if isinstance(value, dict) and "$each" in value else [value]
                for item in items:
                    if not any(values_equal(existing, item) for existing in current):
                        current.append(item)
                set_path(doc, path, current)
        elif op == "$pull":
            for path, value in spec.items():
                current = get_path(doc, path) if has_path(doc, path) else None
                if not isinstance(current, list):
                    continue
                set_path(doc, path, [item for item in current if not values_equal(item, value)])
    return doc


def project_doc(doc: dict[str, Any], projection: dict[str, Any] | None) -> dict[str, Any]:
    if not projection:
        return dict(doc)
    include_id = projection.get("_id", 1) not in (0, False)
    non_id = {key: value for key, value in projection.items() if key != "_id"}
    inclusion = any(value not in (0, False) for value in non_id.values())
    out: dict[str, Any] = {}
    if inclusion:
        for key, value in non_id.items():
            if value in (0, False):
                continue
            if value in (1, True):
                if key in doc:
                    out[key] = doc[key]
            elif isinstance(value, (dict, str)):
                out[key] = resolve_value(doc, value)
    else:
        out = dict(doc)
        for key, value in non_id.items():
            if value in (0, False):
                out.pop(key, None)
    if include_id and "_id" in doc:
        out["_id"] = doc["_id"]
    else:
        out.pop("_id", None)
    return out


def sort_docs(docs: list[dict[str, Any]], key_or_spec: Any, direction: int | None = None) -> list[dict[str, Any]]:
    specs: list[tuple[str, int]]
    if isinstance(key_or_spec, list):
        specs = [(str(item[0]), int(item[1])) for item in key_or_spec]
    elif direction is None and isinstance(key_or_spec, list):
        specs = [(str(item[0]), int(item[1])) for item in key_or_spec]
    else:
        specs = [(str(key_or_spec), 1 if direction is None else int(direction))]

    def sort_key(doc: dict[str, Any]) -> tuple:
        keys = []
        for path, _direction in specs:
            value = get_path(doc, path) if has_path(doc, path) else None
            if isinstance(value, ObjectId):
                value = str(value)
            if isinstance(value, datetime):
                value = value.isoformat()
            keys.append(value)
        return tuple(keys)

    result = list(docs)
    for path, direction_value in reversed(specs):
        result.sort(key=lambda doc, p=path: _sortable(get_path(doc, p) if has_path(doc, p) else None), reverse=direction_value < 0)
    return result


def _sortable(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ""
    return value
