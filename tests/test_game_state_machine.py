import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_game_state_machine_transitions():
    cmd = ["node", str(ROOT / "tests/js/runGameStateMachine.mjs")]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(completed.stdout.strip().splitlines()[-1])
    assert data["allowedFinal"] == "Rebound"
    assert data["illegalError"] is True
