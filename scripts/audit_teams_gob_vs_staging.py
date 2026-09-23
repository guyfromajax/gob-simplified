#!/usr/bin/env python3
"""Read-only audit: compare gob.teams vs gob-staging.teams.

Summarizes field presence and value drift. Does not dump every mismatched doc —
prints per-field mismatch counts (and a few example team names).

Production is read-only and requires process-level ``GOB_DB_ACCESS=read``.
Staging resolves independently from repo-root ``.env.local``. No writes.

Usage:
    GOB_DB_ACCESS=read .venv/bin/python scripts/audit_teams_gob_vs_staging.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import (  # noqa: E402
    PRODUCTION_DB,
    STAGING_DB,
    ScriptDatabaseError,
    connect_script_database,
)


def _norm(value: Any) -> Any:
    """Normalize BSON / nested values for equality comparison."""
    if isinstance(value, dict):
        return {str(k): _norm(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, list):
        return [_norm(v) for v in value]
    try:
        from bson import ObjectId

        if isinstance(value, ObjectId):
            return str(value)
    except Exception:
        pass
    return value


def _team_key(doc: dict[str, Any]) -> str:
    return str(doc.get("_id"))


def main() -> int:
    pristine = dict(os.environ)
    production = connect_script_database(
        target=PRODUCTION_DB, access="read", pristine_env=pristine, repo_root=ROOT
    )
    staging = connect_script_database(
        target=STAGING_DB,
        access="read",
        pristine_env=pristine,
        repo_root=ROOT,
        force_local_staging=True,
    )
    try:
        prod_docs = list(production.database["teams"].find({}))
        stg_docs = list(staging.database["teams"].find({}))

        prod_by_id = {_team_key(d): d for d in prod_docs}
        stg_by_id = {_team_key(d): d for d in stg_docs}
        prod_names = {str(d.get("name")): _team_key(d) for d in prod_docs}
        stg_names = {str(d.get("name")): _team_key(d) for d in stg_docs}

        print("=== teams collection audit (read-only) ===")
        print(f"gob          count={len(prod_docs)}")
        print(f"gob-staging  count={len(stg_docs)}")

        only_prod = sorted(set(prod_by_id) - set(stg_by_id))
        only_stg = sorted(set(stg_by_id) - set(prod_by_id))
        only_prod_names = sorted(set(prod_names) - set(stg_names))
        only_stg_names = sorted(set(stg_names) - set(prod_names))

        print(f"_id only in gob:         {len(only_prod)}")
        print(f"_id only in gob-staging: {len(only_stg)}")
        print(f"name only in gob:         {len(only_prod_names)}")
        print(f"name only in gob-staging: {len(only_stg_names)}")
        if only_prod_names:
            print(f"  examples (gob): {only_prod_names[:5]}")
        if only_stg_names:
            print(f"  examples (staging): {only_stg_names[:5]}")

        shared_ids = sorted(set(prod_by_id) & set(stg_by_id))
        print(f"shared _id pairs: {len(shared_ids)}")

        prod_key_freq: Counter[str] = Counter()
        stg_key_freq: Counter[str] = Counter()
        for d in prod_docs:
            prod_key_freq.update(d.keys())
        for d in stg_docs:
            stg_key_freq.update(d.keys())

        all_keys = sorted(set(prod_key_freq) | set(stg_key_freq))
        print("\n--- field presence (doc counts that have the key) ---")
        presence_diff = False
        for key in all_keys:
            pc, sc = prod_key_freq[key], stg_key_freq[key]
            mark = "" if pc == sc else "  ← DIFF"
            if pc != sc:
                presence_diff = True
            print(f"  {key:28s} gob={pc:3d}  staging={sc:3d}{mark}")
        if not presence_diff:
            print("  (all fields present on the same number of docs)")

        field_mismatch_docs: dict[str, list[str]] = defaultdict(list)
        identical = 0
        for tid in shared_ids:
            a = prod_by_id[tid]
            b = stg_by_id[tid]
            name = str(a.get("name") or b.get("name") or tid)
            keys = set(a.keys()) | set(b.keys())
            diffs = []
            for key in keys:
                in_a = key in a
                in_b = key in b
                if in_a != in_b or _norm(a.get(key)) != _norm(b.get(key)):
                    diffs.append(key)
            if not diffs:
                identical += 1
            else:
                for key in diffs:
                    field_mismatch_docs[key].append(name)

        print("\n--- value compare (matched by _id) ---")
        print(f"identical docs: {identical}/{len(shared_ids)}")
        print(f"docs with ≥1 field difference: {len(shared_ids) - identical}")

        if not field_mismatch_docs:
            print("No field/value differences on shared teams.")
            return 0

        print("\n--- fields that do not match perfectly ---")
        print(f"{'field':28s} {'mismatched_docs':>16}  examples")
        for key in sorted(field_mismatch_docs, key=lambda k: (-len(field_mismatch_docs[k]), k)):
            names = field_mismatch_docs[key]
            examples = ", ".join(names[:3])
            more = f" (+{len(names) - 3} more)" if len(names) > 3 else ""
            print(f"{key:28s} {len(names):16d}  {examples}{more}")

        print("\n--- mismatch shape hints (shared docs only) ---")
        for key in sorted(field_mismatch_docs):
            if key == "player_ids":
                len_diff = content_diff = 0
                for tid in shared_ids:
                    a = prod_by_id[tid].get(key)
                    b = stg_by_id[tid].get(key)
                    if _norm(a) == _norm(b):
                        continue
                    if (a is None) != (b is None) or len(a or []) != len(b or []):
                        len_diff += 1
                    else:
                        content_diff += 1
                print(
                    f"  {key}: length differs on {len_diff} docs; "
                    f"same length / different members on {content_diff} docs"
                )
                continue

            prod_vals = []
            stg_vals = []
            for name in field_mismatch_docs[key]:
                tid = prod_names.get(name) or stg_names.get(name)
                if not tid:
                    continue
                prod_vals.append(_norm(prod_by_id[tid].get(key)))
                stg_vals.append(_norm(stg_by_id[tid].get(key)))

            if prod_vals and all(
                isinstance(v, (int, float, str, type(None), bool)) for v in prod_vals + stg_vals
            ):
                print(
                    f"  {key}: {len(field_mismatch_docs[key])} docs differ; "
                    f"gob unique≈{len(set(map(str, prod_vals)))}, "
                    f"staging unique≈{len(set(map(str, stg_vals)))}"
                )
            else:
                print(f"  {key}: {len(field_mismatch_docs[key])} docs differ (non-scalar / nested)")

        return 0
    finally:
        production.close()
        staging.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
