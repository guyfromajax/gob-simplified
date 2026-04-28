"""Normalize franchise_team_data (FTD) for a new in-memory game (Q1 / init-game).

Keeps parity with the franchise greenfield path in simulate_quarter_endpoint:
per-game play/defense tracking is reset while effectiveness / cloaking / momentum
carry over from FTD.
"""

from __future__ import annotations

import copy
from typing import Any


def prepare_ftd_for_new_game(ftd: dict | None) -> dict[str, Any]:
    """
    Convert an FTD document payload (or None) into pieces for GameManager/TeamManager.

    Returns:
        team_attributes: copy of FTD team_attributes, or None if missing/empty
        strategy_settings: copy of strategy_settings, or None if missing/empty
        playbook_settings: dict (may be empty)
        plays_data: None if no ftd; otherwise normalized dict (may be empty)
        scouting_data: None if no ftd; otherwise deep copy with fresh defense game_stats
    """
    empty: dict[str, Any] = {
        "team_attributes": None,
        "strategy_settings": None,
        "playbook_settings": {},
        "plays_data": None,
        "scouting_data": None,
    }
    if not ftd:
        return empty

    raw_attrs = ftd.get("team_attributes") or {}
    team_attributes: dict[str, Any] | None = dict(raw_attrs) if raw_attrs else None

    raw_strategy = ftd.get("strategy_settings") or {}
    strategy_settings: dict[str, Any] | None = dict(raw_strategy) if raw_strategy else None

    playbook_settings = dict(ftd.get("playbook_settings") or {})

    plays_raw = ftd.get("plays") or {}
    plays_data: dict[str, Any] | None = None
    if plays_raw:
        plays_data = {}
        for play_name, play_data in plays_raw.items():
            if play_name is None:
                continue
            plays_data[play_name] = {
                "play_id": play_data.get("play_id", ""),
                "name": play_data.get("name", play_name),
                "play_type": play_data.get("play_type", ""),
                "play_focus": play_data.get("play_focus", ""),
                "target_shooter": play_data.get("target_shooter"),
                "motion_focus": play_data.get("motion_focus"),
                "effectiveness": play_data.get("effectiveness", 0),
                "cloaking": play_data.get("cloaking", 0),
                "momentum": play_data.get("momentum", 0),
                "game_stats": {
                    "times_run": 0,
                    "successes": 0,
                    "player_points": {},
                    "effectiveness": 0.0,
                },
            }
    else:
        plays_data = {}

    scouting_raw = ftd.get("scouting_data")
    scouting_data: dict[str, Any] | None = None
    if scouting_raw and isinstance(scouting_raw, dict):
        from BackEnd.models.team_manager import TeamManager, normalize_scouting_data_for_gameplay

        scouting_data = normalize_scouting_data_for_gameplay(scouting_raw)
        defense = scouting_data.get("defense") or {}
        fresh_gs = copy.deepcopy(TeamManager._create_defense_structure_template()["game_stats"])
        for defense_name, defense_data in list(defense.items()):
            if defense_name is None or not isinstance(defense_data, dict):
                continue
            if "game_stats" in defense_data:
                defense_data["game_stats"] = copy.deepcopy(fresh_gs)
            if "used" in defense_data:
                defense_data["used"] = 0
            if "success" in defense_data:
                defense_data["success"] = 0
    else:
        scouting_data = {}

    return {
        "team_attributes": team_attributes,
        "strategy_settings": strategy_settings,
        "playbook_settings": playbook_settings,
        "plays_data": plays_data,
        "scouting_data": scouting_data,
    }
