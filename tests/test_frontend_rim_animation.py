import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_node(loader, script):
    cmd = ["node", "--loader", str(ROOT / loader), str(ROOT / script)]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_play_turn_animation_passes_starting_team():
    result = run_node("tests/js/httpsLoader.mjs", "tests/js/runPlayTurnAnimation.mjs")
    assert result["homeResult"] is True
    assert result["awayResult"] is False


def test_shoot_ball_rim_selection():
    result = run_node("tests/js/httpsLoaderNoStubBall.mjs", "tests/js/runShootBall.mjs")
    assert result["home"] == {"x": 89, "y": 25}
    assert result["away"] == {"x": 11, "y": 25}
