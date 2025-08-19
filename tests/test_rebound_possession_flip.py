import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run_node(loader, script):
    cmd = ["node", "--loader", str(ROOT / loader), str(ROOT / script)]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout.strip().splitlines()[-1])

def test_defensive_rebound_flips_possession():
    result = run_node("tests/js/httpsLoaderNoStubBall.mjs", "tests/js/runDefensiveReboundFlip.mjs")
    assert result["attached"] == "pgA"
    assert result["newOffense"] == "AWAY"
    assert result["eventOffense"] == "AWAY"
