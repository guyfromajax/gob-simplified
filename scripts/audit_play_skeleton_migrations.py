#!/usr/bin/env python3
"""Read-only structural inventory for historical play/skeleton migrations.

This report deliberately separates structural facts from retirement decisions. It
accepts one explicit database target and uses the enforced read-only script boundary.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target

PLAY_VARIANTS = ("successful", "mid_play_change", "contested", "broken")
SUMMARY_PATH = ROOT / "docs" / "Archive" / "Playbooks_Rework" / "playbooks_summary.md"


def _version_shape(value: Any) -> tuple[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return "not-dict", ()
    versions = value.get("versions")
    if isinstance(versions, list):
        labels = tuple(str(item.get("version")) for item in versions if isinstance(item, dict))
        valid = all(
            isinstance(item, dict)
            and isinstance(item.get("version"), str)
            and isinstance(item.get("steps"), list)
            for item in versions
        )
        unique = len(labels) == len(set(labels))
        return ("versions-valid" if valid and unique else "versions-malformed"), labels
    if isinstance(value.get("steps"), list):
        return "direct-steps", ()
    return "empty-or-unknown", ()


def _rename_map() -> dict[str, str]:
    if not SUMMARY_PATH.exists():
        return {}
    result: dict[str, str] = {}
    for raw in SUMMARY_PATH.read_text(encoding="utf-8").splitlines():
        columns = [part.strip() for part in raw.strip().split("|")]
        if len(columns) != 3 or not columns[0] or columns[0] == "Play Name":
            continue
        match = re.search(r"\(([^()]+)\)\s*$", columns[2])
        if match:
            target = match.group(1).strip()
            if target != columns[0]:
                result[columns[0]] = target
    return result


def audit_database(db) -> dict[str, Any]:
    report: dict[str, Any] = {}
    plays = list(db.plays.find({}))
    play_types = Counter(str(play.get("play_type")) for play in plays)
    root_fields = {
        "game_stats": sum("game_stats" in play for play in plays),
        "season_stats": sum("season_stats" in play for play in plays),
        "play_id": sum(bool(play.get("play_id")) for play in plays),
    }
    legacy_standard = 0
    motion_shapes: Counter[str] = Counter()
    variant_shapes: dict[str, Counter[str]] = {name: Counter() for name in PLAY_VARIANTS}
    variant_labels: dict[str, Counter[tuple[str, ...]]] = {name: Counter() for name in PLAY_VARIANTS}
    missing_variants: Counter[str] = Counter()
    for play in plays:
        skeletons = play.get("skeletons") or {}
        legacy_standard += int("standard" in skeletons)
        if play.get("play_type") == "motion":
            shape, _ = _version_shape(skeletons.get("base_loop"))
            motion_shapes[shape] += 1
            continue
        for name in PLAY_VARIANTS:
            if name not in skeletons:
                missing_variants[name] += 1
            shape, labels = _version_shape(skeletons.get(name))
            variant_shapes[name][shape] += 1
            if labels:
                variant_labels[name][labels] += 1
    report["plays"] = {
        "total": len(plays),
        "play_types": dict(play_types),
        "root_fields": root_fields,
        "legacy_standard": legacy_standard,
        "motion_base_loop_shapes": dict(motion_shapes),
        "set_variant_shapes": {key: dict(value) for key, value in variant_shapes.items()},
        "set_variant_version_labels": {
            key: {",".join(labels): count for labels, count in value.items()}
            for key, value in variant_labels.items()
        },
        "missing_set_variants": dict(missing_variants),
    }
    names = {str(play.get("name")) for play in plays}
    rename_map = _rename_map()
    report["play_renames"] = {
        "mapping_count": len(rename_map),
        "old_names_still_present": sorted(name for name in rename_map if name in names),
        "target_names_missing": sorted(name for name in rename_map.values() if name not in names),
    }

    for collection_name in ("fcp_skeletons", "hct_skeletons"):
        docs = list(db[collection_name].find({}))
        shapes: Counter[str] = Counter()
        labels: Counter[tuple[str, ...]] = Counter()
        missing_name = legacy_field = 0
        variant_names: Counter[str] = Counter()
        for doc in docs:
            missing_name += int(not bool(doc.get("name")))
            legacy_field += int("field" in doc)
            variants = doc.get("variants")
            if not isinstance(variants, dict):
                shapes["missing-variants"] += 1
                continue
            for name, value in variants.items():
                variant_names[str(name)] += 1
                shape, version_labels = _version_shape(value)
                shapes[shape] += 1
                if version_labels:
                    labels[version_labels] += 1
        report[collection_name] = {
            "total": len(docs),
            "missing_name": missing_name,
            "legacy_field": legacy_field,
            "variant_names": dict(variant_names),
            "variant_shapes": dict(shapes),
            "version_labels": {",".join(key): value for key, value in labels.items()},
        }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        report = audit_database(connection.database)
    finally:
        connection.close()
    print(json.dumps({"database": args.db, **report}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
