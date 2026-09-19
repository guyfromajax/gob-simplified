"""WS-3 slice 1: FranchiseContext door (Url + Session providers)."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_franchise_context_providers():
    completed = subprocess.run(
        ["node", str(ROOT / "tests/js/testFranchiseContext.mjs")],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "franchise context test failed:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["ok"] is True
    assert result["resumeKeys"] >= 12
