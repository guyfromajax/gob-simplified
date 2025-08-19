import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_node(loader, script):
    cmd = ["node", "--loader", str(ROOT / loader), str(ROOT / script)]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_rebound_in_progress_blocks_non_rebounder():
    result = run_node("tests/js/httpsLoaderNoStubBall.mjs", "tests/js/runReboundInProgress.mjs")
    assert result["first"] is None
    assert result["afterRebound"] == "a"
    assert result["flagAfterRebound"] is False
    assert result["final"] == "b"
