"""
Pluggable HCT (Half Court Trap) defensive plays.

Behavior-dispatch layer for the trap play family. Each play is an ``HCTPlay``
implementation; a registry maps the canonical key (see
``constants/hct_trap_play_types.py``) → instance. ``phase_resolution`` resolves the
play stashed in ``game_state["hct_trap_play"]`` and calls ``play.run(game)``.

This is the formalized version of Fast Break's per-play-module split
(``rim_runner_fast_break.py`` etc.).

PR1 registers only ``StandardTrap``, which carries today's logic verbatim by
delegating to ``compute_dynamic_hct_turn``. The granular per-phase seams
(build_formation / detect_pressure_and_trappers / bh_decision / resolve_moment /
movement) are extracted onto this interface in PR2, when the second play
(``straight_pressure``) first needs to share the loop while diverging in places.
Play-agnostic plumbing — time terminals (shot-clock 0 + the elapsed-based
10-second rule), HCT stat parity, schema/step emission, possession flips — stays
OUTSIDE the play so every play inherits it consistently.
"""

from __future__ import annotations

from typing import Any, Dict

from BackEnd.constants.hct_trap_play_types import (
    HCT_TRAP_PLAY_LABELS,
    STANDARD_TRAP,
)


class HCTPlay:
    """Base interface for a selectable HCT defensive play."""

    key: str = ""

    @property
    def label(self) -> str:
        return HCT_TRAP_PLAY_LABELS.get(self.key, self.key)

    def run(self, game) -> Dict[str, Any]:
        """Resolve one HCT possession, returning the engine intermediate dict
        (same shape as ``compute_dynamic_hct_turn``)."""
        raise NotImplementedError


class StandardTrap(HCTPlay):
    """The original (and PR1's only) trap: today's dynamic HCT loop, verbatim."""

    key = STANDARD_TRAP

    def run(self, game) -> Dict[str, Any]:
        # Lazy import avoids a circular dependency (dynamic_hct ↔ this module).
        from BackEnd.engine.dynamic_hct import compute_dynamic_hct_turn

        return compute_dynamic_hct_turn(game)


# Registry: canonical key → play instance. Straight Pressure / Diamond are added
# in later cuts; until then their keys resolve to Standard Trap via the fallback.
HCT_TRAP_PLAYS: Dict[str, HCTPlay] = {
    STANDARD_TRAP: StandardTrap(),
}


def get_hct_trap_play(key: str | None) -> HCTPlay:
    """Resolve a play key to its implementation, falling back to Standard Trap for
    unknown / not-yet-implemented keys (e.g. ``straight_pressure``/``diamond``)."""
    return HCT_TRAP_PLAYS.get(key or "", HCT_TRAP_PLAYS[STANDARD_TRAP])
