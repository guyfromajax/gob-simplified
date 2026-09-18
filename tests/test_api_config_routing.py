"""WS-5a: two-axis API routing table (web byte-identical; desktop+local seam)."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_config_routing_table():
    completed = subprocess.run(
        ["node", str(ROOT / "tests/js/testApiConfigRouting.mjs")],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "routing table test failed:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["ok"] is True
    assert result["hostCases"] >= 3
    assert result["categories"] == 14
