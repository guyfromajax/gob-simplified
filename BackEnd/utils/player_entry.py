from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from BackEnd.utils.opening_tip import OPENING_TIP_ENTRANCE_POSITIONS


def _copy_coords(coords: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    if not isinstance(coords, dict):
        return None
    x = coords.get("x")
    y = coords.get("y")
    if x is None or y is None:
        return None
    return {"x": float(x), "y": float(y)}


def _iter_active_lineup(game) -> Iterable[tuple[str, Any, str]]:
    for team_key, team in (("home", game.home_team), ("away", game.away_team)):
        for pos, player in (team.lineup or {}).items():
            if player is not None:
                yield team_key, player, pos


def _destinations_from_turn(game, turn: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    result_type = str(turn.get("result_type") or "").upper()
    targets: Dict[str, Dict[str, float]] = {}

    if result_type in {"BASELINE_INBOUND", "SIDE_INBOUND"}:
        offense_team_id = str(turn.get("offense_team_id") or turn.get("possession_team_id") or "")
        offense_dest = turn.get("oDestinations") or {}
        defense_dest = turn.get("dDestinations") or {}
        for team in (game.home_team, game.away_team):
            is_offense = str(team.team_id) == offense_team_id
            source = offense_dest if is_offense else defense_dest
            for pos, player in (team.lineup or {}).items():
                coords = _copy_coords(source.get(pos))
                player_id = getattr(player, "player_id", None)
                if coords and player_id is not None:
                    targets[str(player_id)] = coords
        return targets

    if result_type == "FREE_THROW":
        for animation in turn.get("animations") or []:
            player_id = animation.get("playerId") or animation.get("player_id")
            movement = animation.get("movement") or []
            end_coords = None
            if len(movement) > 1:
                end_coords = _copy_coords((movement[1] or {}).get("coords"))
            if player_id is not None and end_coords:
                targets[str(player_id)] = end_coords
        return targets

    return targets


def build_bench_entry_payload(game, turn: Optional[Dict[str, Any]], *, context: str) -> Optional[Dict[str, Any]]:
    if not isinstance(turn, dict):
        return None

    targets = _destinations_from_turn(game, turn)
    if not targets:
        return None

    animations = []
    for team_key, player, pos in _iter_active_lineup(game):
        player_id = getattr(player, "player_id", None)
        target = targets.get(str(player_id)) if player_id is not None else None
        if target is None:
            target = _copy_coords(getattr(player, "coords", None))
        entrance = _copy_coords(OPENING_TIP_ENTRANCE_POSITIONS.get(team_key, {}).get(pos))
        if player_id is None or entrance is None or target is None:
            continue
        animations.append(
            {
                "playerId": player_id,
                "entrance": entrance,
                "end": target,
            }
        )

    if not animations:
        return None

    return {
        "kind": "BENCH_ENTRY",
        "context": context,
        "target_result_type": turn.get("result_type"),
        "animations": animations,
    }
