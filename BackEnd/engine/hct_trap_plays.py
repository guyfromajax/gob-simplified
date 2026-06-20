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

from typing import List, Optional, Tuple

from BackEnd.constants.hct_trap_play_types import (
    HCT_TRAP_PLAY_LABELS,
    STANDARD_TRAP,
    STRAIGHT_PRESSURE,
)

# Type alias for clarity: a coord map is {position: {"x": int, "y": int}}.
CoordMap = Dict[str, Dict[str, int]]


class HCTPlay:
    """Base interface for a selectable HCT defensive play.

    The base implements the **Standard Trap** behavior at every seam by delegating
    to the shared engine helpers, so a play that overrides nothing == Standard Trap.
    Subclasses override only the seams that differ (Straight Pressure overrides
    ``detect_moment`` + ``defense_targets``). The shared loop
    (``compute_dynamic_hct_turn``) calls these seams; play-agnostic plumbing (time
    terminals, stat parity, emission, possession flips) stays outside the play.
    """

    key: str = ""

    @property
    def label(self) -> str:
        return HCT_TRAP_PLAY_LABELS.get(self.key, self.key)

    # --- Per-possession lifecycle ------------------------------------------
    def begin_possession(
        self,
        bh_xy,
        def_coords: CoordMap,
        off_coords: Optional[CoordMap],
        is_away_offense: bool,
    ) -> "HCTPlay":
        """Return the play handler for this possession. Stateless plays (Standard
        Trap) return ``self``; stateful plays (Straight Pressure) return a fresh
        instance carrying its locked man-assignment / role state so the shared
        registry singleton stays stateless."""
        return self

    # --- Behavior seams (default = Standard Trap) ---------------------------
    def detect_moment(
        self, bh_xy, def_coords: CoordMap, is_away_offense: bool
    ) -> Tuple[str, List[str]]:
        """Classify the moment as 'none' | 'pressure' | 'trap' (+ in-range list)."""
        from BackEnd.engine.dynamic_hct import _detect_moment

        return _detect_moment(bh_xy, def_coords, is_away_offense)

    def defense_targets(
        self,
        bh_xy,
        def_coords: CoordMap,
        is_away_offense: bool,
        off_coords: Optional[CoordMap] = None,
    ) -> CoordMap:
        """Per-possession defensive formation targets around the BH (pure)."""
        from BackEnd.engine.dynamic_hct import _defense_targets

        return _defense_targets(bh_xy, def_coords, is_away_offense, off_coords)

    # --- Entry --------------------------------------------------------------
    def run(self, game) -> Dict[str, Any]:
        """Resolve one HCT possession, returning the engine intermediate dict
        (same shape as ``compute_dynamic_hct_turn``)."""
        # Lazy import avoids a circular dependency (dynamic_hct ↔ this module).
        from BackEnd.engine.dynamic_hct import compute_dynamic_hct_turn

        return compute_dynamic_hct_turn(game, self)


class StandardTrap(HCTPlay):
    """The original trap: today's dynamic HCT loop, verbatim (inherits all seams)."""

    key = STANDARD_TRAP


class StraightPressure(HCTPlay):
    """Play #2 (§13.6): man-to-man backcourt pressure. The three backcourt
    defenders (PG/SG/SF) lock onto a man at the converge and stick until a stop
    event, except a man who enters the ABA is released and the freed defender
    fills the next open role (rover/trapper → key → wings). A real trap re-forms
    only via the rover. Frontcourt PF/C zone coverage, the ABA read, and the
    HCO/FB transition are inherited from Standard.

    State (man assignments + roles) is per-possession: ``begin_possession``
    returns a fresh instance carrying ``self.state`` so the registry singleton
    stays stateless and reentrant.
    """

    key = STRAIGHT_PRESSURE

    def __init__(self) -> None:
        self.state: Optional[Dict[str, Any]] = None

    def begin_possession(
        self,
        bh_xy,
        def_coords: CoordMap,
        off_coords: Optional[CoordMap],
        is_away_offense: bool,
    ) -> "StraightPressure":
        from BackEnd.engine.dynamic_hct import _straight_pressure_begin

        inst = StraightPressure()
        inst.state = _straight_pressure_begin(
            bh_xy, def_coords, off_coords, is_away_offense
        )
        return inst

    def detect_moment(
        self, bh_xy, def_coords: CoordMap, is_away_offense: bool
    ) -> Tuple[str, List[str]]:
        from BackEnd.engine.dynamic_hct import _detect_moment

        kind, in_range = _detect_moment(bh_xy, def_coords, is_away_offense)
        # A trap is allowed only when an active rover has reached the BH (is in
        # range); otherwise cap at single-defender pressure (no double-team).
        if kind == "trap":
            rover = (self.state or {}).get("rover")
            if rover is not None and rover in in_range:
                return "trap", in_range
            return "pressure", in_range
        return kind, in_range

    def defense_targets(
        self,
        bh_xy,
        def_coords: CoordMap,
        is_away_offense: bool,
        off_coords: Optional[CoordMap] = None,
    ) -> CoordMap:
        from BackEnd.engine.dynamic_hct import (
            _straight_pressure_begin,
            _straight_pressure_targets,
        )

        if self.state is None:
            self.state = _straight_pressure_begin(
                bh_xy, def_coords, off_coords, is_away_offense
            )
        return _straight_pressure_targets(
            self.state, bh_xy, def_coords, is_away_offense, off_coords
        )


# Registry: canonical key → play instance. Diamond is added in PR3; until then its
# key resolves to Standard Trap via the fallback.
HCT_TRAP_PLAYS: Dict[str, HCTPlay] = {
    STANDARD_TRAP: StandardTrap(),
    STRAIGHT_PRESSURE: StraightPressure(),
}


def get_hct_trap_play(key: str | None) -> HCTPlay:
    """Resolve a play key to its implementation, falling back to Standard Trap for
    unknown / not-yet-implemented keys (e.g. ``straight_pressure``/``diamond``)."""
    return HCT_TRAP_PLAYS.get(key or "", HCT_TRAP_PLAYS[STANDARD_TRAP])
