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
    spot = result["fallback"]["ballSpot"]
    assert spot["x"] == 85
    assert 19 <= spot["y"] <= 31
    pos = result["fallback"]["ballPos"]
    assert pos["x"] == spot["x"]
    assert pos["y"] == 50 - spot["y"]


def test_free_throw_possession_change_event():
    result = run_node("tests/js/httpsLoaderNoStubBall.mjs", "tests/js/runFreeThrowSequence.mjs")
    assert result["home"]["posChange"] is True
    assert result["technical"]["posChange"] is False
    assert result["technical"]["inboundCalled"] is False


def test_free_throw_halftime_inbound_orientation():
    result = run_node(
        "tests/js/httpsLoaderNoStubBall.mjs",
        "tests/js/runFreeThrowHalftime.mjs",
    )
    assert result["inboundSide"] == "home"
    assert result["ballSpotX"] == 3
