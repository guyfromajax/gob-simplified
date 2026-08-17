import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "FrontEnd" / "static" / "js" / "shared" / "maintenanceBanner.js"
CONFIG = ROOT / "FrontEnd" / "static" / "config" / "maintenance.json"


def _node_time_contract() -> dict:
    source = f"""
const m = require({json.dumps(str(SCRIPT))});
const winter = m.safeParseTimeMs('2026-01-15T15:00:00', 'America/New_York');
const summer = m.safeParseTimeMs('2026-08-15T15:00:00', 'America/New_York');
const winterWindow = m.getWarningWindowStartMs({{
  starts_at_iso: '2026-01-15T15:00:00',
  starts_at_timezone: 'America/New_York',
  show_minutes_before: 60
}});
const summerWindow = m.getWarningWindowStartMs({{
  starts_at_iso: '2026-08-15T15:00:00',
  starts_at_timezone: 'America/New_York',
  show_minutes_before: 60
}});
console.log(JSON.stringify({{
  zone: m.defaultWallClockTimeZone,
  winter: new Date(winter).toISOString(),
  summer: new Date(summer).toISOString(),
  winterWindow: new Date(winterWindow).toISOString(),
  summerWindow: new Date(summerWindow).toISOString()
}}));
"""
    result = subprocess.run(
        ["node", "-e", source],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_new_york_wall_clock_handles_est_and_edt_with_sixty_minute_window():
    result = _node_time_contract()

    assert result == {
        "zone": "America/New_York",
        "winter": "2026-01-15T20:00:00.000Z",  # 3 PM EST (UTC-5)
        "summer": "2026-08-15T19:00:00.000Z",  # 3 PM EDT (UTC-4)
        "winterWindow": "2026-01-15T19:00:00.000Z",
        "summerWindow": "2026-08-15T18:00:00.000Z",
    }


def test_maintenance_config_uses_new_york_wall_clock_and_sixty_minute_warning():
    config = json.loads(CONFIG.read_text())

    assert config["starts_at_timezone"] == "America/New_York"
    assert config["show_minutes_before"] == 60
    assert not config["starts_at_iso"].endswith("Z")
