import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_node(loader, script):
    cmd = ["node", "--loader", str(ROOT / loader), str(ROOT / script)]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_play_turn_animation_passes_starting_team():
    source = Path("FrontEnd/static/js/phaser/animation/turnAnimation.js").read_text()
    params_start = source.index("const shootParams = {")
    params_end = source.index("};", params_start)
    shoot_params = source[params_start:params_end]

    # shootBall needs both IDs to select the attacking rim. The player sprite
    # supplies the shooter ID; simData supplies the authoritative home ID.
    assert "shooterTeamId," in shoot_params
    assert "homeTeamId," in shoot_params


def test_shoot_ball_rim_selection():
    result = run_node("tests/js/httpsLoaderNoStubBall.mjs", "tests/js/runShootBall.mjs")
    # Made shots settle just inside the raw rim centers (91/9), matching the
    # backend made-shot sweet-spot contract.
    assert result["home"] == {"x": 90, "y": 25}
    assert result["away"] == {"x": 10, "y": 25}
