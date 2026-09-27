"""Display fields the roster view reads. No new stored data."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from BackEnd.utils.leaders_snapshot import _roster_position
from BackEnd.utils.player_em import roster_rt


def stamp_roster_player(row: dict, *, on_user_team: bool, stored_position: Any = None) -> dict:
    """Position uses the roster rule. RT is the max position rating. Lineup starts unset."""
    row["position"] = _roster_position(
        stored_position if stored_position is not None else row.get("position"),
        row.get("position_ratings"),
        row.get("training_position"),
        row.get("resolved_training_position"),
        on_user_team=on_user_team,
    )
    row["rt"] = roster_rt(row)
    row["starter"] = False
    row["lineup_order"] = None
    return row


def apply_lineup_roles(players: Iterable[Mapping[str, Any]], projected: Optional[Iterable[Mapping[str, Any]]]) -> None:
    """Mark starters from the projected lineup the roster route already builds."""
    order: dict[str, int] = {}
    for row in projected or []:
        if not isinstance(row, Mapping):
            continue
        pid = str(row.get("player_id") or row.get("_id") or "")
        if pid and pid not in order:
            order[pid] = len(order)
    for player in players:
        if not isinstance(player, dict):
            continue
        pid = str(player.get("_id") or player.get("player_id") or "")
        if pid in order:
            player["starter"] = True
            player["lineup_order"] = order[pid]
        else:
            player["starter"] = False
            player["lineup_order"] = None
