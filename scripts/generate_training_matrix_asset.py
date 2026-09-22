#!/usr/bin/env python3
"""
Generate the Training-by-Position tutorial's matrix asset from Python.

The tutorial page used to carry the percentages as hand-typed table cells. That was
already a liability with 5 position columns — a retune of `TRAINING_GAIN_PERCENTAGES`
silently left the page telling coaches the old numbers — and Development Focus took it
from 60 cells to 360. So the numbers are emitted from the source of truth instead, and
`tests/test_training_matrix_asset.py` fails the build if the committed asset drifts.

Why a .js file and not .json: the page loads it with a plain <script src>, so there is no
fetch, no CORS, and nothing to special-case when the downloadable desktop build serves
these files from disk.

Usage:
  python scripts/generate_training_matrix_asset.py            # write
  python scripts/generate_training_matrix_asset.py --check    # exit 1 if stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.constants.training_shape import (  # noqa: E402
    POSITIONS,
    TRAINING_FOCUSES,
    TRAINING_FOCUS_PERCENTAGES,
)

ASSET = ROOT / "FrontEnd" / "static" / "js" / "generated" / "trainingMatrix.js"

# Row order is the tutorial's, not the dict's: offense, defense, body, mind. It reads as
# a scouting report rather than as whatever order the constants happen to be written in.
ATTR_ROWS = [
    ("SC", "Scoring"),
    ("SH", "Shooting"),
    ("PS", "Passing"),
    ("BH", "Ball Handling"),
    ("ID", "Inside Defense"),
    ("OD", "Outside Defense"),
    ("RB", "Rebounding"),
    ("ST", "Strength"),
    ("AG", "Agility"),
    ("FT", "Free Throws"),
    ("IQ", "Basketball IQ"),
    ("ND", "Endurance"),
]

FOCUS_LABELS = {
    "standard": "Standard",
    "offensive": "Offensive",
    "defensive": "Defensive",
    "athletic": "Athletic",
    "fundamentals": "Fundamentals",
    "rebounding": "Rebounding",
}

# Cell shading. The page reads these rather than re-deriving them, so the swatches in the
# legend and the cells can never disagree. `min` is inclusive.
BANDS = [
    {"key": "full", "min": 80, "label": "Strong Fit"},
    {"key": "high", "min": 60, "label": "Solid Fit"},
    {"key": "mid", "min": 40, "label": "Partial"},
    {"key": "low", "min": 0, "label": "Poor Fit"},
]


def build_payload() -> dict:
    matrix = {
        pos: {
            focus: {attr: TRAINING_FOCUS_PERCENTAGES[pos][focus][attr] for attr, _ in ATTR_ROWS}
            for focus in TRAINING_FOCUSES
        }
        for pos in POSITIONS
    }
    return {
        "positions": list(POSITIONS),
        "focuses": [{"value": f, "label": FOCUS_LABELS[f]} for f in TRAINING_FOCUSES],
        "attributes": [{"code": c, "name": n} for c, n in ATTR_ROWS],
        "bands": BANDS,
        "matrix": matrix,
    }


def render() -> str:
    payload = json.dumps(build_payload(), indent=2, sort_keys=False)
    return (
        "/**\n"
        " * GENERATED FILE — do not edit.\n"
        " *\n"
        " * Written by scripts/generate_training_matrix_asset.py from\n"
        " * BackEnd/constants/training_shape.py. Editing it by hand puts the tutorial back\n"
        " * where it started: showing coaches numbers the engine no longer uses.\n"
        " *\n"
        " * Regenerate:  python scripts/generate_training_matrix_asset.py\n"
        " * Guarded by:  tests/test_training_matrix_asset.py\n"
        " */\n"
        "window.GOB_TRAINING_MATRIX = " + payload + ";\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the tutorial training-matrix asset")
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if the committed asset differs from what Python produces")
    args = parser.parse_args()

    expected = render()
    if args.check:
        actual = ASSET.read_text() if ASSET.exists() else ""
        if actual == expected:
            print(f"up to date: {ASSET.relative_to(ROOT)}")
            return 0
        print(f"STALE: {ASSET.relative_to(ROOT)} does not match training_shape.py")
        print("Regenerate with: python scripts/generate_training_matrix_asset.py")
        return 1

    ASSET.parent.mkdir(parents=True, exist_ok=True)
    ASSET.write_text(expected)
    print(f"wrote {ASSET.relative_to(ROOT)} "
          f"({len(POSITIONS)} positions x {len(TRAINING_FOCUSES)} focuses x {len(ATTR_ROWS)} attributes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
