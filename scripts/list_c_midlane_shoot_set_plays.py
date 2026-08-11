#!/usr/bin/env python3
"""
List all set plays that have at least one skeleton variant where the final step
is the "C" (center) with "shoot" action from the "midLane" spot.

Output: Play Name, Skeleton (variant), Version number
"""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target


def final_step_is_c_shoot_midlane(steps):
    """Return True if the final step has C with action 'shoot' from location/spot 'midLane'."""
    if not steps:
        return False
    final_step = steps[-1]
    pos_actions = final_step.get("pos_actions", {})
    c_action = pos_actions.get("C")
    if not c_action or c_action.get("action") != "shoot":
        return False
    location = c_action.get("location") or c_action.get("spot") or ""
    return location.strip().lower() == "midlane"


def iter_set_play_skeletons(play_doc):
    """
    Yield (skeleton_name, version_label, steps) for every variant/version of a set play.
    - successful: one set of steps (no version), yield ("successful", "—", steps)
    - mid_play_change, contested, broken: yield each ("variant", "v1"/"v2"/..., steps)
    """
    skeletons = play_doc.get("skeletons", {})
    for skel_name, skel_data in skeletons.items():
        if not isinstance(skel_data, dict):
            continue
        if "steps" in skel_data:
            steps = skel_data.get("steps", [])
            if steps:
                yield (skel_name, "—", steps)
        if "versions" in skel_data:
            versions = skel_data["versions"]
            if isinstance(versions, list):
                for v in versions:
                    ver_label = v.get("version", "?")
                    steps = v.get("steps", [])
                    if steps:
                        yield (skel_name, ver_label, steps)
            elif isinstance(versions, dict):
                for ver_label, v in versions.items():
                    steps = v.get("steps", []) if isinstance(v, dict) else []
                    if steps:
                        yield (skel_name, ver_label, steps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        plays = list(connection.database.plays.find({"play_type": "set_play"}))
    finally:
        connection.close()
    results = []

    for play in plays:
        play_name = play.get("name", "Unknown")
        for skeleton_name, version_label, steps in iter_set_play_skeletons(play):
            if final_step_is_c_shoot_midlane(steps):
                results.append((play_name, skeleton_name, version_label))

    # Dedupe and sort for consistent output
    seen = set()
    unique = []
    for r in results:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    unique.sort(key=lambda x: (x[0], x[1], x[2]))

    print("Set plays with final step: C — shoot from midLane")
    print("Play Name | Skeleton | Version")
    print("-" * 60)
    for play_name, skeleton, version in unique:
        print(f"{play_name} | {skeleton} | {version}")
    print("-" * 60)
    print(f"Total: {len(unique)} item(s)")


if __name__ == "__main__":
    main()
