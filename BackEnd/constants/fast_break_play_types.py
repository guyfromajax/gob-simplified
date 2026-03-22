"""
Fast break play identifiers (DREB → outlet) and steal bucket.

- Code / persistence: snake_case keys below.
- UI label for ``THIRTY_TWO`` is "32" (see Fast_Break_System / FB_Update_Brief).

``rim_runner`` and ``thirty_two`` are reserved for future logic; only
``covert_release`` (DREB outlet) and ``after_steal`` (steal entry) increment today.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

# Canonical keys (match scouting_data["offense"]["fast_break_plays"])
COVERT_RELEASE = "covert_release"
RIM_RUNNER = "rim_runner"
THIRTY_TWO = "thirty_two"
AFTER_STEAL = "after_steal"

FAST_BREAK_PLAY_KEYS = (
    COVERT_RELEASE,
    RIM_RUNNER,
    THIRTY_TWO,
    AFTER_STEAL,
)


def default_fast_break_plays() -> Dict[str, Dict[str, int]]:
    """Fresh A/S counters per play (offense scouting only)."""
    return {k: {"A": 0, "S": 0} for k in FAST_BREAK_PLAY_KEYS}


def ensure_fast_break_plays(offense_scouting: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """
    Merge missing keys for older saves / partial scouting blobs.
    Mutates offense_scouting in place and returns fast_break_plays dict.
    """
    if "fast_break_plays" not in offense_scouting or not isinstance(
        offense_scouting.get("fast_break_plays"), dict
    ):
        offense_scouting["fast_break_plays"] = default_fast_break_plays()
        return offense_scouting["fast_break_plays"]

    fb = offense_scouting["fast_break_plays"]
    template = default_fast_break_plays()
    for key, val in template.items():
        if key not in fb or not isinstance(fb.get(key), dict):
            fb[key] = copy.deepcopy(val)
        else:
            fb[key].setdefault("A", 0)
            fb[key].setdefault("S", 0)
    return fb


def play_key_for_fast_break_entry(is_dreb_outlet: bool) -> str:
    """Which scouting bucket gets an attempt for this FB possession."""
    return COVERT_RELEASE if is_dreb_outlet else AFTER_STEAL
