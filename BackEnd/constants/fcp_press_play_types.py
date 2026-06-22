"""
FCP (Full Court Press) defensive play identifiers.

Mirrors ``constants/hct_trap_play_types.py`` for the full-court press family:

- Code / persistence: ``fcp_*`` snake_case keys below.
- UI labels: same display names as HCT ("Straight Pressure", etc.).

Selection mirrors HCT traps: weights live on the defending team's
``playbook_settings["fc_presses"]``; the chosen key is picked once at the SS&S
choke point (``TurnManager.determine_defensive_pressure_type``) and stashed in
``game_state["fcp_press_play"]`` for ``compute_dynamic_fcp_turn`` to consume.

PR1 registers ``fcp_straight_pressure`` only; PR3 adds the other two plays.
"""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, Optional

FCP_STANDARD_TRAP = "fcp_standard_trap"
FCP_STRAIGHT_PRESSURE = "fcp_straight_pressure"
FCP_STANDARD_DIAMOND = "fcp_standard_diamond"

FCP_PRESS_PLAY_KEYS = (
    FCP_STANDARD_TRAP,
    FCP_STRAIGHT_PRESSURE,
    FCP_STANDARD_DIAMOND,
)

FCP_PRESS_PLAY_LABELS = {
    FCP_STANDARD_TRAP: "Standard Trap",
    FCP_STRAIGHT_PRESSURE: "Straight Pressure",
    FCP_STANDARD_DIAMOND: "Standard Diamond",
}

FCP_PRESS_ID_ALIASES = {
    FCP_STANDARD_TRAP: FCP_STANDARD_TRAP,
    "Standard Trap": FCP_STANDARD_TRAP,
    "fcp_standard_trap": FCP_STANDARD_TRAP,
    FCP_STRAIGHT_PRESSURE: FCP_STRAIGHT_PRESSURE,
    "Straight Pressure": FCP_STRAIGHT_PRESSURE,
    "fcp_straight_pressure": FCP_STRAIGHT_PRESSURE,
    FCP_STANDARD_DIAMOND: FCP_STANDARD_DIAMOND,
    "Standard Diamond": FCP_STANDARD_DIAMOND,
    "fcp_standard_diamond": FCP_STANDARD_DIAMOND,
}

# PR3 target default (34/33/33). PR1 ignores weights — always straight pressure.
DEFAULT_FCP_PRESS_WEIGHTS = {
    FCP_STANDARD_TRAP: 34,
    FCP_STRAIGHT_PRESSURE: 33,
    FCP_STANDARD_DIAMOND: 33,
}

# PR1: only straight pressure is implemented.
PR1_FCP_PRESS_PLAY_KEYS = (FCP_STRAIGHT_PRESSURE,)


def default_fcp_press_plays() -> Dict[str, Dict[str, int]]:
    """Fresh A/S counters per play (defense scouting only)."""
    return {k: {"A": 0, "S": 0} for k in FCP_PRESS_PLAY_KEYS}


def ensure_fcp_press_plays(defense_scouting: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """
    Merge missing keys for older saves / partial scouting blobs.
    Mutates defense_scouting in place and returns the fcp_press_plays dict.
    """
    if "fcp_press_plays" not in defense_scouting or not isinstance(
        defense_scouting.get("fcp_press_plays"), dict
    ):
        defense_scouting["fcp_press_plays"] = default_fcp_press_plays()
        return defense_scouting["fcp_press_plays"]

    plays = defense_scouting["fcp_press_plays"]
    template = default_fcp_press_plays()
    for key, val in template.items():
        if key not in plays or not isinstance(plays.get(key), dict):
            plays[key] = copy.deepcopy(val)
        else:
            plays[key].setdefault("A", 0)
            plays[key].setdefault("S", 0)
    return plays


def _coerce_non_negative_weight(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, numeric)


def _resolve_fcp_press_weights(
    playbook_settings: Optional[Dict[str, Any]],
) -> Dict[str, int]:
    raw = None
    if isinstance(playbook_settings, dict):
        raw = playbook_settings.get("fc_presses", playbook_settings.get("fc_press"))
    if not isinstance(raw, dict):
        return {FCP_STRAIGHT_PRESSURE: 100}

    # PR1: only straight pressure runs; ignore unimplemented keys until PR3.
    weight = _coerce_non_negative_weight(raw.get(FCP_STRAIGHT_PRESSURE))
    if weight <= 0:
        return {FCP_STRAIGHT_PRESSURE: 100}
    return {FCP_STRAIGHT_PRESSURE: weight}


def play_key_for_fcp_press(
    playbook_settings: Optional[Dict[str, Any]] = None,
) -> str:
    """Which press play this FCP possession runs.

    PR1: always ``fcp_straight_pressure`` (only implemented play). PR3 will
    weighted-select across ``fc_presses`` like ``play_key_for_hct_trap``.
    """
    weights = _resolve_fcp_press_weights(playbook_settings)
    plays = list(weights.keys())
    return random.choices(plays, weights=[weights[p] for p in plays], k=1)[0]
