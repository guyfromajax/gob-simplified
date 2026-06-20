"""
HCT (Half Court Trap) defensive play identifiers.

Mirrors ``constants/fast_break_play_types.py`` exactly, but for the *defensive*
trap play family (a sibling of zone_defense / man_defense in the playbook):

- Code / persistence: snake_case keys below.
- UI labels: "Standard Trap", "Straight Pressure", "Diamond".

Selection mirrors Fast Breaks: weights live on the *defending* team's
``playbook_settings["hc_traps"]``; the chosen key is picked once at the SS&S choke
point (``TurnManager.determine_defensive_pressure_type``) and stashed in
``game_state["hct_trap_play"]`` for ``compute_dynamic_hct_turn`` to consume.

Per-play attempt/success counters live under ``scouting_data["defense"]
["hct_trap_plays"]`` (defense-side, unlike FB's offense-side counters).

PR1 ships ``standard_trap`` only; ``straight_pressure`` and ``diamond`` are
reserved keys (default weight 0) implemented in later cuts.
"""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, Optional

# Canonical keys (match playbook_settings["hc_traps"] / scouting hct_trap_plays)
STANDARD_TRAP = "standard_trap"
STRAIGHT_PRESSURE = "straight_pressure"
DIAMOND = "diamond"

HCT_TRAP_PLAY_KEYS = (
    STANDARD_TRAP,
    STRAIGHT_PRESSURE,
    DIAMOND,
)

# UI labels (snake_case key → display name), parallel to the FB labels.
HCT_TRAP_PLAY_LABELS = {
    STANDARD_TRAP: "Standard Trap",
    STRAIGHT_PRESSURE: "Straight Pressure",
    DIAMOND: "Diamond",
}

# Name/id aliases for playbook normalization (mirrors FAST_BREAK_ID_ALIASES).
HCT_TRAP_ID_ALIASES = {
    STANDARD_TRAP: STANDARD_TRAP,
    "Standard Trap": STANDARD_TRAP,
    STRAIGHT_PRESSURE: STRAIGHT_PRESSURE,
    "Straight Pressure": STRAIGHT_PRESSURE,
    DIAMOND: DIAMOND,
    "Diamond": DIAMOND,
}

# PR1: only Standard Trap is implemented, so default weighting routes 100% to it
# (selection always resolves to standard_trap → behavior is provably unchanged).
# PR2/PR3 rebalance these once Straight Pressure / Diamond land.
DEFAULT_HCT_TRAP_WEIGHTS = {
    STANDARD_TRAP: 100,
    STRAIGHT_PRESSURE: 0,
    DIAMOND: 0,
}


def default_hct_trap_plays() -> Dict[str, Dict[str, int]]:
    """Fresh A/S counters per play (defense scouting only)."""
    return {k: {"A": 0, "S": 0} for k in HCT_TRAP_PLAY_KEYS}


def ensure_hct_trap_plays(defense_scouting: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """
    Merge missing keys for older saves / partial scouting blobs.
    Mutates defense_scouting in place and returns the hct_trap_plays dict.
    """
    if "hct_trap_plays" not in defense_scouting or not isinstance(
        defense_scouting.get("hct_trap_plays"), dict
    ):
        defense_scouting["hct_trap_plays"] = default_hct_trap_plays()
        return defense_scouting["hct_trap_plays"]

    plays = defense_scouting["hct_trap_plays"]
    template = default_hct_trap_plays()
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


def _resolve_hct_trap_weights(
    playbook_settings: Optional[Dict[str, Any]],
) -> Dict[str, int]:
    raw = None
    if isinstance(playbook_settings, dict):
        raw = playbook_settings.get("hc_traps", playbook_settings.get("hc_trap_plays"))
    if not isinstance(raw, dict):
        return dict(DEFAULT_HCT_TRAP_WEIGHTS)

    resolved = {
        key: _coerce_non_negative_weight(raw.get(key)) for key in HCT_TRAP_PLAY_KEYS
    }
    if sum(resolved.values()) <= 0:
        return dict(DEFAULT_HCT_TRAP_WEIGHTS)
    return resolved


def play_key_for_hct_trap(
    playbook_settings: Optional[Dict[str, Any]] = None,
) -> str:
    """Which trap play this HCT possession runs (weighted by the defending team's
    ``playbook_settings["hc_traps"]``; falls back to the defaults)."""
    weights = _resolve_hct_trap_weights(playbook_settings)
    plays = list(HCT_TRAP_PLAY_KEYS)
    return random.choices(plays, weights=[weights[p] for p in plays], k=1)[0]
