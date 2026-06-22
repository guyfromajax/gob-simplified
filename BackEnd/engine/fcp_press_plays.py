"""
Pluggable FCP (Full Court Press) defensive plays.

Behavior-dispatch layer for the press play family. Each play is an ``FCPPlay``
implementation; a registry maps the canonical key (see
``constants/fcp_press_play_types.py``) → instance. The dynamic FCP wrapper
resolves the play stashed in ``game_state["fcp_press_play"]`` and calls
``play.run(game)``.

PR1 registers ``fcp_straight_pressure`` only (mirrors HCT Straight Pressure at
full-court scale). Play-agnostic plumbing — time terminals, FCP stat parity,
schema emission, possession flips — stays outside the play in ``dynamic_fcp`` /
``phase_resolution``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants.fcp_press_play_types import (
    FCP_PRESS_PLAY_LABELS,
    FCP_STRAIGHT_PRESSURE,
)

CoordMap = Dict[str, Dict[str, int]]


class FCPPlay:
    """Base interface for a selectable FCP defensive play."""

    key: str = ""

    @property
    def label(self) -> str:
        return FCP_PRESS_PLAY_LABELS.get(self.key, self.key)

    def begin_possession(
        self,
        bh_xy,
        def_coords: CoordMap,
        off_coords: Optional[CoordMap],
        is_away_offense: bool,
    ) -> "FCPPlay":
        return self

    def detect_moment(
        self, bh_xy, def_coords: CoordMap, is_away_offense: bool
    ) -> Tuple[str, List[str]]:
        from BackEnd.engine.dynamic_hct import _detect_moment

        return _detect_moment(bh_xy, def_coords, is_away_offense)

    def defense_targets(
        self,
        bh_xy,
        def_coords: CoordMap,
        is_away_offense: bool,
        off_coords: Optional[CoordMap] = None,
    ) -> CoordMap:
        from BackEnd.engine.dynamic_hct import _defense_targets

        return _defense_targets(bh_xy, def_coords, is_away_offense, off_coords)

    def select_trappers(
        self,
        in_range: List[str],
        bh_xy,
        def_coords: CoordMap,
        is_away_offense: bool,
    ) -> Tuple[str, str]:
        from BackEnd.engine.dynamic_hct import _select_trappers

        return _select_trappers(in_range, bh_xy, def_coords)

    def run(self, game) -> Dict[str, Any]:
        from BackEnd.engine.dynamic_fcp import compute_dynamic_fcp_turn

        return compute_dynamic_fcp_turn(game, self)


class StraightPressureFCP(FCPPlay):
    """PR1 play: HCT Straight Pressure (§13.6) at full-court / FCP scale."""

    key = FCP_STRAIGHT_PRESSURE

    def __init__(self) -> None:
        self.state: Optional[Dict[str, Any]] = None

    def begin_possession(
        self,
        bh_xy,
        def_coords: CoordMap,
        off_coords: Optional[CoordMap],
        is_away_offense: bool,
    ) -> "StraightPressureFCP":
        from BackEnd.engine.dynamic_hct import _straight_pressure_begin

        inst = StraightPressureFCP()
        inst.state = _straight_pressure_begin(
            bh_xy, def_coords, off_coords, is_away_offense
        )
        return inst

    def detect_moment(
        self, bh_xy, def_coords: CoordMap, is_away_offense: bool
    ) -> Tuple[str, List[str]]:
        from BackEnd.engine.dynamic_hct import _detect_moment

        kind, in_range = _detect_moment(bh_xy, def_coords, is_away_offense)
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


FCP_PRESS_PLAYS: Dict[str, FCPPlay] = {
    FCP_STRAIGHT_PRESSURE: StraightPressureFCP(),
}


def get_fcp_press_play(key: str | None) -> FCPPlay:
    """Resolve a play key to its implementation; default Straight Pressure."""
    return FCP_PRESS_PLAYS.get(key or "", FCP_PRESS_PLAYS[FCP_STRAIGHT_PRESSURE])
