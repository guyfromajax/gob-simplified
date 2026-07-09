"""
FLSS coach VO and Final Shot SFX exclusion contract.

Single source of truth for which audio files may play on FLSS shot attempts.
Final Turn uses the separate Final Shot stinger / headline path; FLSS uses
launch/heave coach VO only (see SFX_System.md, EOQ_System.md §8).
"""

from __future__ import annotations

import random
from typing import FrozenSet, Tuple

FLSS_COACH_VO_LAUNCH_FILE = "sammy-launch.mp3"
FLSS_COACH_VO_HEAVE_FILE = "duke-heave.mp3"

# Court stingers + Final Shot coach clip — never valid on FLSS turns.
FINAL_SHOT_SFX_FILES: FrozenSet[str] = frozenset(
    {
        "sammy-final-shot.mp3",
        "final-shot-braddock.mp3",
        "braddock-finalshot.mp3",
    }
)


def flss_coach_vo_pool(*, flss_heave_sfx: bool) -> Tuple[str, ...]:
    """Allowed coach VO filenames for one FLSS shot (launch-only or launch+heave)."""
    pool: list[str] = [FLSS_COACH_VO_LAUNCH_FILE]
    if flss_heave_sfx:
        pool.append(FLSS_COACH_VO_HEAVE_FILE)
    return tuple(pool)


def resolve_flss_coach_vo_filename(*, flss_heave_sfx: bool) -> str:
    return random.choice(flss_coach_vo_pool(flss_heave_sfx=flss_heave_sfx))


def resolve_flss_coach_sfx_stamp(*, flss_heave_sfx: bool) -> dict:
    """Schema ``sfx_on_step_start`` payload for FLSS coach VO at the terminal shoot step."""
    return {
        "file": resolve_flss_coach_vo_filename(flss_heave_sfx=flss_heave_sfx),
        "event": "flss_vo",
        "volume": 0.7,
    }


def is_final_shot_sfx_excluded_on_flss(filename: str) -> bool:
    return str(filename or "") in FINAL_SHOT_SFX_FILES
