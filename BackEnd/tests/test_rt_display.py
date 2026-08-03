import json
import subprocess
from pathlib import Path

from BackEnd.utils import rt_display


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_RT_HELPER = REPO_ROOT / "FrontEnd/static/js/shared/rtBucket.js"


def test_rt_letter_grade_boundaries():
    expected = {
        -1: "F",
        29: "F",
        30: "D",
        39: "D",
        40: "C",
        49: "C",
        50: "C+",
        59: "C+",
        60: "B",
        69: "B",
        70: "B+",
        79: "B+",
        80: "A",
        89: "A",
        90: "A+",
        99: "A+",
        100: "A++",
        115: "A++",
    }
    assert {value: rt_display.rt_letter_grade(value) for value in expected} == expected


def test_rt_letter_grade_handles_missing_and_decimal_values():
    assert rt_display.rt_letter_grade(None) == "--"
    assert rt_display.rt_letter_grade("") == "--"
    assert rt_display.rt_letter_grade("not-a-rating") == "--"
    assert rt_display.rt_letter_grade(79.9) == "B+"


def test_numeric_rollback_mode(monkeypatch):
    monkeypatch.setattr(rt_display, "RT_DISPLAY_MODE", "number")
    assert rt_display.format_rt_display(84) == "84"
    assert rt_display.format_rt_display(84.5) == "84.5"
    assert rt_display.format_rt_display(None) == "--"


def test_frontend_and_backend_letters_match_for_full_rt_range():
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const grades = Array.from({ length: 131 }, (_, rt) => context.window.getRtLetterGrade(rt));
process.stdout.write(JSON.stringify(grades));
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(FRONTEND_RT_HELPER)],
        check=True,
        capture_output=True,
        text=True,
    )
    frontend_grades = json.loads(result.stdout)
    backend_grades = [rt_display.rt_letter_grade(rt) for rt in range(131)]

    mismatches = [
        (rt, frontend, backend)
        for rt, (frontend, backend) in enumerate(zip(frontend_grades, backend_grades))
        if frontend != backend
    ]
    assert not mismatches, f"Frontend/backend RT grade drift: {mismatches}"
