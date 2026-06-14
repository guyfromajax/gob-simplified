"""Full-engine Practice Squad game simulation."""

from __future__ import annotations

import logging
from typing import Any

from BackEnd.main import simulate_quarter
from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player
from BackEnd.models.team_manager import TeamManager
from BackEnd.utils.shared import summarize_game_state

logger = logging.getLogger(__name__)

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player_payload_from_roster_slot(slot: dict, fpd_by_id: dict, frd_by_id: dict) -> dict[str, Any]:
    pid = str(slot.get("player_id") or "")
    source = slot.get("source")
    if source == "fpd":
        fpd = fpd_by_id.get(pid) or {}
        meta = fpd.get("meta") or {}
        return {
            "_id": pid,
            "first_name": str(meta.get("first_name") or ""),
            "last_name": str(meta.get("last_name") or ""),
            "team": slot.get("parent_team_name") or "",
            "attributes": dict(fpd.get("attributes") or {}),
            "position_ratings": dict(fpd.get("position_ratings") or {}),
            "height": meta.get("height"),
            "weight": meta.get("weight"),
            "year": meta.get("year") or "",
            "jersey": None,
        }
    frd = frd_by_id.get(pid) or {}
    name = str(slot.get("name") or frd.get("name") or "Recruit")
    parts = name.split(None, 1)
    first = parts[0] if parts else "Recruit"
    last = parts[1] if len(parts) > 1 else ""
    return {
        "_id": pid,
        "first_name": first,
        "last_name": last,
        "team": "",
        "attributes": dict(frd.get("attributes") or {}),
        "position_ratings": dict(frd.get("position_ratings") or {}),
        "height": frd.get("height"),
        "weight": frd.get("weight"),
        "year": frd.get("year") or "",
        "jersey": None,
    }


def build_ps_lineup(team: TeamManager) -> dict[str, Player]:
    """Top RT at each position, then best remaining for bench if needed."""
    players = list(team.get_all_players())

    def rt_at(player: Player, pos: str) -> int:
        pr = getattr(player, "position_ratings", None) or {}
        try:
            return int(float(pr.get(pos) or 0))
        except (TypeError, ValueError):
            return 0

    def best_rt(player: Player) -> int:
        pr = getattr(player, "position_ratings", None) or {}
        vals = []
        for v in pr.values():
            try:
                vals.append(int(float(v)))
            except (TypeError, ValueError):
                pass
        return max(vals) if vals else 0

    lineup: dict[str, Player] = {}
    used: set[str] = set()

    for pos in POSITIONS:
        candidates = [p for p in players if str(p.player_id) not in used]
        if not candidates:
            break
        candidates.sort(key=lambda p: (-rt_at(p, pos), -best_rt(p), p.name))
        pick = candidates[0]
        lineup[pos] = pick
        used.add(str(pick.player_id))

    return lineup


def run_ps_full_simulation(
    *,
    home_display_name: str,
    away_display_name: str,
    home_team_id: str,
    away_team_id: str,
    home_roster: list[dict],
    away_roster: list[dict],
    fpd_by_id: dict[str, dict],
    frd_by_id: dict[str, dict],
) -> tuple[int, int, dict]:
    """Run a full turn-based sim; no DB writes."""
    home_payloads = [_player_payload_from_roster_slot(s, fpd_by_id, frd_by_id) for s in home_roster]
    away_payloads = [_player_payload_from_roster_slot(s, fpd_by_id, frd_by_id) for s in away_roster]

    gm = GameManager(
        home_display_name,
        away_display_name,
        mode="single",
        franchise_id=None,
        home_team_attributes=TeamManager.init_team_attributes(mode="franchise"),
        away_team_attributes=TeamManager.init_team_attributes(mode="franchise"),
        home_roster_override=home_payloads,
        away_roster_override=away_payloads,
        home_synthetic_team_id=home_team_id,
        away_synthetic_team_id=away_team_id,
    )
    gm.home_team.lineup = build_ps_lineup(gm.home_team)
    gm.away_team.lineup = build_ps_lineup(gm.away_team)
    gm.game_state["allow_fouled_out_lineup_reentry"] = True

    gm.setup_opening_tip()
    gm.quarter = 1
    while True:
        simulate_quarter(gm)
        current_q = gm.quarter - 1
        if current_q >= 4:
            h_pts = gm.game_state["score"][gm.home_team.name]
            a_pts = gm.game_state["score"][gm.away_team.name]
            if h_pts != a_pts:
                gm.quarter = current_q
                gm.game_state["quarter"] = current_q
                break
            gm.home_team.points_by_quarter.append(0)
            gm.away_team.points_by_quarter.append(0)

    away_score = int(gm.score.get(away_display_name, 0) or 0)
    home_score = int(gm.score.get(home_display_name, 0) or 0)
    summary = summarize_game_state(gm)
    if not isinstance(summary, dict):
        summary = {}
    summary["mode"] = "practice_squad"
    summary["simulation_engine"] = "practice_squad_full"
    summary["home_team_id"] = home_team_id
    summary["away_team_id"] = away_team_id
    return away_score, home_score, summary
