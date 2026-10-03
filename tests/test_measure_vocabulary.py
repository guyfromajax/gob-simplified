"""Display labels for the eight ±20 measures use one vocabulary.

Data keys (`pt_efficiency`, `fb_efficiency`, …) stay as they are. This is a source
scan of in-app display strings, not of docs, gameplay event names, or Playcall
Center 'Press/Trap' (that is the Press / Trap / None setter, not a team measure).
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATIC = ROOT / "FrontEnd" / "static"

# Surfaces that show team-measure names to the player.
DISPLAY_FILES = [
    STATIC / "box-score.js",
    STATIC / "court.html",
    STATIC / "training-report.js",
    STATIC / "training.html",
    STATIC / "js" / "shared" / "views" / "scoutingView.js",
    STATIC / "js" / "shared" / "views" / "teamAttributesView.js",
    STATIC / "js" / "shared" / "officeHome.js",
    STATIC / "tutorial-scouting.html",
    STATIC / "tutorial-team-attributes.html",
    STATIC / "tutorial-training.html",
    STATIC / "tutorial-advanced-press-trap.html",
]

# Lookups that must stay as the server wrote them into stored reports.
KEY_ALLOW = (
    "'Press/Trap Readiness'",
    '"Press/Trap Readiness"',
)

OLD = (
    "Press/Trap Efficiency",
    "Press/Trap Defense",
    "Press/Trap Breaks",
    "Press Break",
    "Fast Break Offense",
)


def test_no_old_measure_display_names():
    for path in DISPLAY_FILES:
        text = path.read_text()
        for phrase in OLD:
            leftover = text
            for allowed in KEY_ALLOW:
                leftover = leftover.replace(allowed, "")
            assert phrase not in leftover, f"{path.name} still shows {phrase!r}"


def test_shared_labels_are_present():
    scout = (STATIC / "js" / "shared" / "views" / "scoutingView.js").read_text()
    for label in ("P/T Offense", "P/T Defense", "Fast Break", "Fast Break Defense"):
        assert label in scout
