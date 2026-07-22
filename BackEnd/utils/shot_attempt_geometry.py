"""Immutable coordinate input for game logic at the instant of a shot attempt.

This is intentionally narrower than a universal turn-state contract.  It freezes
the geometry the shot resolver needs today while leaving room to add other
decision-time participants without routing mutable ``Player.coords`` through
gameplay code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


CoordRow = tuple[str, float, float]


def freeze_coord_rows(rows: Iterable[tuple[object, object]]) -> tuple[CoordRow, ...]:
    """Normalize ``(key, {x, y})`` pairs into an immutable tuple."""
    frozen: list[CoordRow] = []
    for key, coord in rows:
        if key is None or not isinstance(coord, dict):
            continue
        if coord.get("x") is None or coord.get("y") is None:
            continue
        frozen.append((str(key), float(coord["x"]), float(coord["y"])))
    return tuple(frozen)


@dataclass(frozen=True)
class ShotAttemptGeometry:
    """Authoritative, decision-time coordinates for one shot attempt."""

    source: str
    shot_step_index: Optional[int]
    shooter_id: str
    shooter_x: float
    shooter_y: float
    defenders_by_id: tuple[CoordRow, ...] = ()
    defenders_by_position: tuple[CoordRow, ...] = ()

    @property
    def shooter_coord(self) -> dict[str, float]:
        return {"x": self.shooter_x, "y": self.shooter_y}

    @staticmethod
    def _lookup(rows: tuple[CoordRow, ...], key: object) -> Optional[dict[str, float]]:
        wanted = str(key)
        for row_key, x, y in rows:
            if row_key == wanted:
                return {"x": x, "y": y}
        return None

    def defender_coord(self, *, player_id=None, position=None) -> Optional[dict[str, float]]:
        if player_id is not None:
            coord = self._lookup(self.defenders_by_id, player_id)
            if coord is not None:
                return coord
        if position is not None:
            return self._lookup(self.defenders_by_position, position)
        return None
