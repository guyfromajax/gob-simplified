#!/usr/bin/env python3
"""
Generate a markdown summary of set plays from the MongoDB `plays` collection.

The output contains one row per play with:
- Play Name
- Target Shooter
- Play Focus

Target Shooter is inferred from the final step of each successful skeleton
version. Current data is expected to have two successful versions (`v0` and
`v1`), and both should end with the same shooter position.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from BackEnd.db import plays_collection


OUTPUT_PATH = ROOT / "docs" / "Playbooks_Rework" / "playbooks_summary.md"
VALID_POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _iter_successful_versions(play: dict) -> Iterable[dict]:
    skeletons = play.get("skeletons", {})
    successful = skeletons.get("successful") or {}

    versions = successful.get("versions")
    if isinstance(versions, list):
        for version in versions:
            if isinstance(version, dict) and version.get("steps"):
                yield version
        return

    if successful.get("steps"):
        yield successful


def _extract_final_shooter_position(steps: list[dict]) -> str:
    if not steps:
        raise ValueError("skeleton has no steps")

    final_step = steps[-1]
    pos_actions = final_step.get("pos_actions") or {}

    shooters = [
        position
        for position in VALID_POSITIONS
        if (pos_actions.get(position) or {}).get("action") == "shoot"
    ]

    if len(shooters) != 1:
        raise ValueError(
            f"expected exactly one shooter in final step, found {shooters or 'none'}"
        )

    return shooters[0]


def _resolve_target_shooter(play: dict) -> str:
    successful_versions = list(_iter_successful_versions(play))
    if not successful_versions:
        raise ValueError("play has no successful skeleton versions")

    shooters = []
    for version in successful_versions:
        steps = version.get("steps") or []
        shooters.append(_extract_final_shooter_position(steps))

    unique_shooters = sorted(set(shooters))
    if len(unique_shooters) != 1:
        raise ValueError(
            f"successful versions disagree on target shooter: {', '.join(unique_shooters)}"
        )

    return unique_shooters[0]


def build_summary_rows() -> list[tuple[str, str, str]]:
    query = {
        "play_type": "set_play",
    }
    projection = {
        "_id": 0,
        "name": 1,
        "play_type": 1,
        "play_focus": 1,
        "skeletons.successful": 1,
    }

    plays = list(plays_collection.find(query, projection))
    rows = []

    for play in plays:
        if play.get("play_type") == "motion":
            continue

        play_name = (play.get("name") or "").strip()
        play_focus = (play.get("play_focus") or "").strip()
        if not play_name:
            raise ValueError("encountered play with missing name")

        target_shooter = _resolve_target_shooter(play)
        rows.append((play_name, target_shooter, play_focus))

    rows.sort(key=lambda row: row[0].lower())
    return rows


def render_markdown(rows: list[tuple[str, str, str]]) -> str:
    lines = [
        "# Playbooks Summary",
        "",
        "Play Name | Target Shooter | Play Focus",
        "--- | --- | ---",
    ]

    for play_name, target_shooter, play_focus in rows:
        lines.append(f"{play_name} | {target_shooter} | {play_focus}")

    lines.extend(["", f"Total set plays: {len(rows)}", ""])
    return "\n".join(lines)


def main() -> int:
    rows = build_summary_rows()
    OUTPUT_PATH.write_text(render_markdown(rows), encoding="utf-8")
    print(f"Wrote {len(rows)} set plays to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
