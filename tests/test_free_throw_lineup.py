import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_case(offense_team: str, shooter_pos: str):
    cmd = [
        "node",
        "--loader",
        str(ROOT / "tests/js/httpsLoaderNoStubBall.mjs"),
        str(ROOT / "tests/js/getFreeThrowLineupDestinations.mjs"),
        offense_team,
        shooter_pos,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_home_offense_sg_shooter():
    result = run_case("home", "SG")
    expected_o = {
        "SG": {"x": 74, "y": 25},
        "PG": {"x": 56, "y": 44},
        "SF": {"x": 80, "y": 32},
        "PF": {"x": 86, "y": 19},
        "C": {"x": 86, "y": 32},
    }
    expected_d = {
        "PG": {"x": 54, "y": 37},
        "SG": {"x": 83, "y": 32},
        "SF": {"x": 83, "y": 19},
        "PF": {"x": 89, "y": 32},
        "C": {"x": 89, "y": 19},
    }
    assert result["oDestinations"] == expected_o, result
    assert result["dDestinations"] == expected_d, result
    print("✅ home SG mapping")


def test_away_offense_pg_shooter():
    result = run_case("away", "PG")
    expected_o = {
        "PG": {"x": 27, "y": 25},
        "SG": {"x": 45, "y": 44},
        "SF": {"x": 20, "y": 32},
        "PF": {"x": 14, "y": 19},
        "C": {"x": 14, "y": 32},
    }
    expected_d = {
        "PG": {"x": 47, "y": 37},
        "SG": {"x": 17, "y": 32},
        "SF": {"x": 17, "y": 19},
        "PF": {"x": 11, "y": 32},
        "C": {"x": 11, "y": 19},
    }
    assert result["oDestinations"] == expected_o, result
    assert result["dDestinations"] == expected_d, result
    print("✅ away PG mapping")
