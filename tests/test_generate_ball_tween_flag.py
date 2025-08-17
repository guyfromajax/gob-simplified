import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_case(enable: bool):
    cmd = [
        "node",
        "--loader",
        str(ROOT / "tests/js/httpsLoaderNoStubBall.mjs"),
        str(ROOT / "tests/js/runGenerateBallTween.mjs"),
    ]
    if enable:
        cmd.append("--enable")
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_ball_tween_respects_flag():
    off = run_case(False)
    assert off["tweenCalled"] is False
    on = run_case(True)
    assert on["tweenCalled"] is True
