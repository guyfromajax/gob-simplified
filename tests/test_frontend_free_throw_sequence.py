import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_node(loader, script):
    cmd = ["node", "--loader", str(ROOT / loader), str(ROOT / script)]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_free_throw_sequence_defaults_to_rim():
    result = run_node("tests/js/httpsLoaderNoStubBall.mjs", "tests/js/runFreeThrowSequence.mjs")
    assert result["fallback"]["reboundCalled"] is True
    assert result["fallback"]["ballSpot"] == {"x": 91, "y": 25}
    assert result["fallback"]["ballPos"] == {"x": 91, "y": 25}
