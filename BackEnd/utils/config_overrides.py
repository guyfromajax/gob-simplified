"""
Runtime config overrides persisted to a JSON file.
Used by the God mode (jamies-cc) page. Values here override constants when present.
"""

import json
import os
from pathlib import Path
from typing import Any

# Store alongside project root; avoid __file__ under BackEnd/utils
_ROOT = Path(__file__).resolve().parents[2]
OVERRIDES_PATH = Path(os.environ.get("CONFIG_OVERRIDES_PATH", str(_ROOT / "config_overrides.json")))

# Defaults (match BackEnd/constants/__init__.py and shared.py)
DEFAULTS = {
    # Turn Results
    "STANDARD_D_FOUL": 95,
    "STANDARD_O_FOUL": 5,
    "HARD_STEAL": -200,
    "SOFT_STEAL": -100,
    "HARD_FOUL": 200,
    "SOFT_FOUL": 100,
    "STEAL_ATTEMPT": 25,
    "DEAD_BALL_TURNOVER": 7,
    # Charges
    "CHARGE_THRESHOLD": -240,
    "BLOCKING_FOUL_THRESHOLD": 220,
    # Blocks
    "BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD": 200,
    "BLOCK_RECONCILIATION_BLOCK_THRESHOLD": 200,
    "BLOCK_Y_ROLL_MIN": 1,
    "BLOCK_Y_ROLL_MAX": 6,
    # Aggression Foul Multiplier (1–5 map to indices 0–4)
    "aggression_foul_1": 0.8,
    "aggression_foul_2": 0.9,
    "aggression_foul_3": 1.0,
    "aggression_foul_4": 1.1,
    "aggression_foul_5": 1.2,
    # Shooting Thresholds
    "HARD_SHOOTING_FOUL_THRESHOLD": 50,
    "SOFT_SHOOTING_FOUL_THRESHOLD": 110,
    "SOFT_PROB": 0.16,
    "THREE_POINTER_FOUL_MISS_CHANCE": 0.4,
    "TWO_POINTER_FOUL_MISS_CHANCE": 0.2,
    "THREE_POINT_SHOT_THRESHOLD_INCREASE": 40,
    # Team Attribute Ranges
    "shot_threshold_min": -10,
    "shot_threshold_max": 190,
    "rebound_modifier_min": 0.0,
    "rebound_modifier_max": 0.4,
    # Tempo Time Elapsed (get_time_elapsed)
    "tempo_slow_mean": 24,
    "tempo_slow_std": 6,
    "tempo_slow_min": 5,
    "tempo_slow_max": 35,
    "tempo_normal_mean": 18,
    "tempo_normal_std": 6,
    "tempo_normal_min": 5,
    "tempo_normal_max": 35,
    "tempo_fast_mean": 12,
    "tempo_fast_std": 4,
    "tempo_fast_min": 4,
    "tempo_fast_max": 15,
}


def _load_raw() -> dict[str, Any]:
    if not OVERRIDES_PATH.is_file():
        return {}
    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def get_overrides() -> dict[str, Any]:
    """Return merged config: defaults + file overrides (file wins)."""
    out = dict(DEFAULTS)
    raw = _load_raw()
    for k, v in raw.items():
        if k in DEFAULTS:
            out[k] = v
    return out


def set_overrides(updates: dict[str, Any]) -> None:
    """Write updates to file (merge with existing). Creates file if missing."""
    current = _load_raw()
    for k, v in updates.items():
        if k in DEFAULTS:
            current[k] = v
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)


def get_value(key: str) -> Any:
    """Return effective value for one key (default or override)."""
    overrides = _load_raw()
    return overrides.get(key, DEFAULTS.get(key))


def get_team_attr_range(attr_name: str) -> tuple[float, float]:
    """Return (min, max) for shot_threshold or rebound_modifier (for TEAM_ATTR_CLAMPS)."""
    if attr_name == "shot_threshold":
        return (
            get_value("shot_threshold_min"),
            get_value("shot_threshold_max"),
        )
    if attr_name == "rebound_modifier":
        return (
            get_value("rebound_modifier_min"),
            get_value("rebound_modifier_max"),
        )
    return (0, 0)  # Only shot_threshold and rebound_modifier are overridable here


def get_tempo_params(tempo_call: str) -> dict[str, float]:
    """Return mean, std, min, max for a tempo (slow, normal, fast)."""
    prefix = f"tempo_{tempo_call}_"
    return {
        "mean": get_value(prefix + "mean"),
        "std": get_value(prefix + "std"),
        "min": get_value(prefix + "min"),
        "max": get_value(prefix + "max"),
    }
