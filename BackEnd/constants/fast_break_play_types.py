"""
Fast break play identifiers (DREB → outlet) and steal bucket.

- Code / persistence: snake_case keys below.
- UI label for ``TRIANGLE`` is "Triangle" (see Fast_Break_System.md).

``triangle`` reuses the Rim Runner entry/denied-outlet family, then branches into
its own setup / decision / finish payload once the RR lane-pass read is declined.
DREB play key is chosen on the shot attempt (``shot_manager``) and passed via
``pending_dreb_fb_play_key``; ``play_key_for_fast_break_entry`` is only a fallback when pending is missing.
``after_steal`` is used for steal entry.
"""

from __future__ import annotations

import copy
from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, Optional

# Canonical keys (match scouting_data["offense"]["fast_break_plays"])
COVERT_RELEASE = "covert_release"
RIM_RUNNER = "rim_runner"
TRIANGLE = "triangle"
AFTER_STEAL = "after_steal"

FAST_BREAK_PLAY_KEYS = (
    COVERT_RELEASE,
    RIM_RUNNER,
    TRIANGLE,
    AFTER_STEAL,
)

# UI labels (snake_case key → display name), parallel to HCT_TRAP_PLAY_LABELS.
# Used by the FCC Scouting Report "Play Usage: Fast Breaks" panel.
FAST_BREAK_PLAY_LABELS = {
    COVERT_RELEASE: "Covert Release",
    RIM_RUNNER: "Rim Runner",
    TRIANGLE: "Triangle",
    AFTER_STEAL: "After Steal",
}
DEFAULT_DREB_FAST_BREAK_WEIGHTS = {
    COVERT_RELEASE: 33,
    RIM_RUNNER: 33,
    TRIANGLE: 34,
}

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


def _coerce_non_negative_weight(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, numeric)


def _resolve_dreb_fast_break_weights(
    playbook_settings: Optional[Dict[str, Any]],
) -> Dict[str, int]:
    raw = None
    if isinstance(playbook_settings, dict):
        raw = playbook_settings.get("fast_breaks", playbook_settings.get("fast_break"))
    if not isinstance(raw, dict):
        return dict(DEFAULT_DREB_FAST_BREAK_WEIGHTS)

    resolved = {
        COVERT_RELEASE: _coerce_non_negative_weight(raw.get(COVERT_RELEASE)),
        RIM_RUNNER: _coerce_non_negative_weight(raw.get(RIM_RUNNER)),
        TRIANGLE: _coerce_non_negative_weight(raw.get(TRIANGLE)),
    }
    if sum(resolved.values()) <= 0:
        return dict(DEFAULT_DREB_FAST_BREAK_WEIGHTS)
    return resolved


def play_key_for_fast_break_entry(
    is_dreb_outlet: bool,
    playbook_settings: Optional[Dict[str, Any]] = None,
) -> str:
    """Which scouting bucket gets an attempt for this FB possession."""
    if not is_dreb_outlet:
        return AFTER_STEAL
    weights = _resolve_dreb_fast_break_weights(playbook_settings)
    plays = [COVERT_RELEASE, RIM_RUNNER, TRIANGLE]
    return random.choices(plays, weights=[weights[p] for p in plays], k=1)[0]
