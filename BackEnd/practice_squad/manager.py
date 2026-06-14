"""Practice Squad orchestration — init, weekly sims, standings, news."""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any
from urllib.parse import quote

from bson import ObjectId

from BackEnd.db import (
    db,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
    franchise_team_data_collection,
)
from BackEnd.practice_squad.constants import (
    PS_ACTIVE_WEEKS,
    PS_CHAMPIONSHIP_WEEK,
    PS_REGULAR_WEEKS,
    PS_TOURNAMENT_WEEKS,
    REGION_LETTERS,
    SCRUBS_MIN_PLAYERS_TO_COMPETE,
    TIER_NAMES,
)
from BackEnd.practice_squad.roster import (
    build_all_region_rosters,
    build_scrubs_week_roster,
    ps_display_name,
    ps_team_id,
)
from BackEnd.practice_squad.schedule import (
    build_regular_season_schedule,
    championship_game_slot,
    init_tier_tournaments,
    tournament_games_for_week,
)
from BackEnd.practice_squad.sim import run_ps_full_simulation
from BackEnd.practice_squad.stats import apply_ps_game_stats, ensure_ps_season_stats_backfilled
from BackEnd.tournament import bracket_engine
from BackEnd.utils.game_id_utils import generate_game_id

logger = logging.getLogger(__name__)


def _empty_standings() -> dict[str, dict[str, dict[str, int]]]:
    standings: dict[str, dict[str, dict[str, int]]] = {}
    for tier in range(1, 7):
        standings[str(tier)] = {}
        for region in REGION_LETTERS:
            tid = ps_team_id(region, tier)
            standings[str(tier)][tid] = {"w": 0, "l": 0}
    return standings


def _format_team_name_map() -> dict[str, str]:
    return {
        str(team["_id"]): team.get("name", str(team["_id"]))
        for team in db.teams.find({}, {"name": 1})
    }


def _build_region_team_map() -> dict[str, list[str]]:
    region_map = {r: [] for r in REGION_LETTERS}
    for team in db.teams.find({}, {"region": 1}):
        region = str(team.get("region") or "").upper()
        if region in region_map:
            region_map[region].append(str(team["_id"]))
    return region_map


def _player_sources_from_ps_state(ps_state: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for team in (ps_state.get("teams") or {}).values():
        for slot in team.get("roster") or []:
            pid = str(slot.get("player_id") or "")
            src = slot.get("source")
            if pid and src:
                out[pid] = str(src)
    for week_rosters in (ps_state.get("scrubs_rosters") or {}).values():
        for slot in week_rosters or []:
            pid = str(slot.get("player_id") or "")
            src = slot.get("source")
            if pid and src:
                out[pid] = str(src)
    return out


def initialize_practice_squad(
    franchise_id: ObjectId,
    franchise_doc: dict,
) -> dict[str, Any]:
    """Build rosters + schedule after week 1 training camp."""
    fid = str(franchise_id)
    team_name_map = _format_team_name_map()
    region_team_map = _build_region_team_map()

    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id}))
    ftd_by_team = {str(d["team_id"]): d for d in ftd_docs if d.get("team_id") is not None}

    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": fid}))
    fpd_by_player = {str(d["player_id"]): d for d in fpd_docs}

    recruits = list(franchise_recruits_data_collection.find({"franchise_id": fid}))
    recruits_by_region: dict[str, list[dict]] = {r: [] for r in REGION_LETTERS}
    for rec in recruits:
        hr = str(rec.get("Home Region") or "").upper()
        if hr in recruits_by_region:
            recruits_by_region[hr].append(rec)

    teams, scrubs_pools, scrubs_forfeit = build_all_region_rosters(
        region_team_map=region_team_map,
        ftd_by_team=ftd_by_team,
        fpd_by_player=fpd_by_player,
        recruits_by_region=recruits_by_region,
        team_name_map=team_name_map,
    )

    schedule = build_regular_season_schedule(scrubs_forfeit=scrubs_forfeit)

    ps_state: dict[str, Any] = {
        "version": 1,
        "initialized": True,
        "initialized_week": 1,
        "trained_week": None,
        "teams": teams,
        "scrubs_pools": {k: [_roster_slot_ref(p) for p in v] for k, v in scrubs_pools.items()},
        "scrubs_forfeit": scrubs_forfeit,
        "scrubs_rosters": {},
        "schedule": schedule,
        "standings": _empty_standings(),
        "tournaments": {},
        "championship": {},
        "applied_games": [],
        "head_to_head": {},
    }
    return ps_state


def _roster_slot_ref(player: dict) -> dict:
    return {
        "source": player.get("source"),
        "player_id": player.get("player_id"),
        "name": player.get("name"),
        "parent_team_name": player.get("parent_team_name"),
        "best_rt": player.get("best_rt"),
    }


def _resolve_team_roster(ps_state: dict, team_id: str, week: int) -> list[dict]:
    team = (ps_state.get("teams") or {}).get(team_id) or {}
    tier = int(team.get("tier") or 0)
    if tier == 6:
        week_key = str(week)
        return list((ps_state.get("scrubs_rosters") or {}).get(week_key) or [])
    return list(team.get("roster") or [])


def _record_h2h(ps_state: dict, winner_id: str, loser_id: str) -> None:
    h2h = ps_state.setdefault("head_to_head", {})
    key = "|".join(sorted([winner_id, loser_id]))
    rec = h2h.setdefault(key, {})
    rec[winner_id] = int(rec.get(winner_id) or 0) + 1


def _apply_standings(ps_state: dict, winner_id: str, loser_id: str, tier: int) -> None:
    standings = ps_state.setdefault("standings", {})
    tier_key = str(tier if tier else 1)
    tier_standings = standings.setdefault(tier_key, {})
    for tid, delta in ((winner_id, "w"), (loser_id, "l")):
        row = tier_standings.setdefault(tid, {"w": 0, "l": 0})
        row[delta] = int(row.get(delta) or 0) + 1


def _seed_tier_teams(ps_state: dict, tier: int) -> list[str]:
    """Seed 8 regional teams for a tier by W/L, H2H, random."""
    standings = (ps_state.get("standings") or {}).get(str(tier)) or {}
    team_ids = [ps_team_id(r, tier) for r in REGION_LETTERS]
    h2h = ps_state.get("head_to_head") or {}

    def h2h_wins(a: str, b: str) -> int:
        key = "|".join(sorted([a, b]))
        rec = h2h.get(key) or {}
        return int(rec.get(a) or 0)

    def sort_key(tid: str) -> tuple:
        row = standings.get(tid) or {"w": 0, "l": 0}
        w, l = int(row.get("w") or 0), int(row.get("l") or 0)
        return (-w, l, random.random())

    ranked = sorted(team_ids, key=sort_key)
    # Tiebreak pairwise H2H among tied W/L groups
    i = 0
    while i < len(ranked):
        j = i + 1
        wi = standings.get(ranked[i]) or {"w": 0, "l": 0}
        while j < len(ranked):
            wj = standings.get(ranked[j]) or {"w": 0, "l": 0}
            if (wi.get("w"), wi.get("l")) != (wj.get("w"), wj.get("l")):
                break
            j += 1
        if j - i > 1:
            block = ranked[i:j]
            block.sort(key=lambda a: (-sum(h2h_wins(a, b) for b in block if b != a), random.random()))
            ranked[i:j] = block
        i = j
    return ranked


def _maybe_init_tournaments(ps_state: dict, week: int) -> None:
    if week != PS_TOURNAMENT_WEEKS[0]:
        return
    if ps_state.get("tournaments"):
        return
    seed_orders = {tier: _seed_tier_teams(ps_state, tier) for tier in range(1, 6)}
    ps_state["tournaments"] = init_tier_tournaments(seed_orders)


def _games_for_week(ps_state: dict, week: int) -> list[dict]:
    games: list[dict] = []
    if week in PS_REGULAR_WEEKS:
        games.extend(list((ps_state.get("schedule") or {}).get(str(week)) or []))
    if week in PS_TOURNAMENT_WEEKS:
        _maybe_init_tournaments(ps_state, week)
        games.extend(tournament_games_for_week(week, ps_state.get("tournaments") or {}))
    if week == PS_CHAMPIONSHIP_WEEK:
        tourn = ps_state.get("tournaments") or {}
        aa = (tourn.get("1") or {}).get("champion")
        ast = (tourn.get("2") or {}).get("champion")
        slot = championship_game_slot(all_americans_champ=aa, all_stars_champ=ast)
        champ = ps_state.get("championship") or {}
        if slot and not champ.get("game_id"):
            candidates = slot["candidates"]
            home = random.choice(candidates)
            away = candidates[1] if candidates[0] == home else candidates[0]
            slot["home_team_id"] = home
            slot["away_team_id"] = away
            ps_state["championship"] = slot
            games.append(slot)
    return games


def _update_scrubs_rosters(ps_state: dict, week: int) -> None:
    if week not in PS_ACTIVE_WEEKS:
        return
    scrubs_rosters = ps_state.setdefault("scrubs_rosters", {})
    for region in REGION_LETTERS:
        if (ps_state.get("scrubs_forfeit") or {}).get(region):
            continue
        pool = list((ps_state.get("scrubs_pools") or {}).get(region) or [])
        roster = build_scrubs_week_roster(pool)
        tid = ps_team_id(region, 6)
        team = (ps_state.get("teams") or {}).get(tid)
        if team is not None:
            team["roster"] = roster
    # Store combined scrubs snapshot keyed by week (all regions use same week key)
    combined: list[dict] = []
    for region in REGION_LETTERS:
        tid = ps_team_id(region, 6)
        combined.extend(_resolve_team_roster(ps_state, tid, week))
    scrubs_rosters[str(week)] = combined


def _sim_one_game(
    game: dict,
    ps_state: dict,
    week: int,
    franchise_id_str: str,
    fpd_by_id: dict,
    frd_by_id: dict,
) -> dict | None:
    home_id = game.get("home_team_id")
    away_id = game.get("away_team_id")
    if not home_id or not away_id:
        return None

    status = game.get("status")
    if status in ("completed", "forfeit", "skipped"):
        return game

    home_roster = _resolve_team_roster(ps_state, str(home_id), week)
    away_roster = _resolve_team_roster(ps_state, str(away_id), week)

    tier = int(game.get("tier") or (ps_state.get("teams") or {}).get(str(home_id), {}).get("tier") or 1)

    # Scrubs forfeit checks
    home_team = (ps_state.get("teams") or {}).get(str(home_id)) or {}
    away_team = (ps_state.get("teams") or {}).get(str(away_id)) or {}
    if int(home_team.get("tier") or 0) == 6 and len(home_roster) < SCRUBS_MIN_PLAYERS_TO_COMPETE:
        _apply_standings(ps_state, str(away_id), str(home_id), 6)
        game.update({"status": "forfeit", "home_score": 0, "away_score": 0, "winner": str(away_id)})
        return game
    if int(away_team.get("tier") or 0) == 6 and len(away_roster) < SCRUBS_MIN_PLAYERS_TO_COMPETE:
        _apply_standings(ps_state, str(home_id), str(away_id), 6)
        game.update({"status": "forfeit", "home_score": 0, "away_score": 0, "winner": str(home_id)})
        return game

    if len(home_roster) < 5 or len(away_roster) < 5:
        game["status"] = "skipped"
        return game

    home_name = home_team.get("display_name") or str(home_id)
    away_name = away_team.get("display_name") or str(away_id)

    summary: dict[str, Any] = {}
    try:
        away_score, home_score, summary = run_ps_full_simulation(
            home_display_name=home_name,
            away_display_name=away_name,
            home_team_id=str(home_id),
            away_team_id=str(away_id),
            home_roster=home_roster,
            away_roster=away_roster,
            fpd_by_id=fpd_by_id,
            frd_by_id=frd_by_id,
        )
    except Exception as ex:
        logger.error("PS sim failed %s vs %s: %s", home_id, away_id, ex, exc_info=True)
        away_score = random.randint(50, 80)
        home_score = random.randint(50, 80)
        summary = {}

    game_id = generate_game_id()
    summary = dict(summary)
    summary["_id"] = game_id
    summary["franchise_id"] = franchise_id_str
    summary["week"] = week
    summary["mode"] = "practice_squad"
    db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)

    winner = str(home_id) if home_score > away_score else str(away_id)
    loser = str(away_id) if winner == str(home_id) else str(home_id)
    _apply_standings(ps_state, winner, loser, tier)
    _record_h2h(ps_state, winner, loser)

    game.update(
        {
            "status": "completed",
            "game_id": str(game_id),
            "home_score": home_score,
            "away_score": away_score,
            "winner": winner,
        }
    )

    sources = _player_sources_from_ps_state(ps_state)
    apply_ps_game_stats(str(game_id), franchise_id_str, player_sources=sources)
    applied = ps_state.setdefault("applied_games", [])
    if str(game_id) not in applied:
        applied.append(str(game_id))

    # Tournament bracket updates
    phase = game.get("phase")
    if phase == "tournament":
        tier_key = str(game.get("tier"))
        tstate = (ps_state.get("tournaments") or {}).get(tier_key)
        if tstate:
            round_num = int(game.get("round") or 1)
            idx = int(game.get("match_index") or 0)
            bracket = tstate.get("bracket") or {}
            bracket_engine.save_game_result(
                bracket,
                round_num,
                idx,
                str(game_id),
                winner,
                score={str(home_id): home_score, str(away_id): away_score},
            )
            _, next_round, completed, champion = bracket_engine.advance_bracket(
                bracket, round_num
            )
            tstate["bracket"] = bracket
            tstate["current_round"] = next_round
            if completed and champion:
                tstate["champion"] = champion
    elif phase == "championship":
        ps_state["championship"] = {
            **game,
            "status": "completed",
            "game_id": str(game_id),
            "winner": winner,
        }

    return game


def run_practice_squad_week(
    franchise_id: ObjectId,
    franchise_doc: dict,
    week: int,
) -> dict[str, Any]:
    """Sim all PS games for the given week; mutates and returns practice_squad state."""
    ps_state = dict(franchise_doc.get("practice_squad") or {})
    if not ps_state.get("initialized"):
        return ps_state

    if week not in PS_ACTIVE_WEEKS:
        return ps_state

    ps_state = ensure_ps_season_stats_backfilled(str(franchise_id), ps_state)

    if int(ps_state.get("trained_week") or 0) == week:
        return ps_state

    fid = str(franchise_id)
    fpd_by_id = {
        str(d["player_id"]): d
        for d in franchise_players_data_collection.find({"franchise_id": fid})
    }
    frd_by_id = {
        str(d["recruit_id"]): d
        for d in franchise_recruits_data_collection.find({"franchise_id": fid})
    }

    _update_scrubs_rosters(ps_state, week)
    games = _games_for_week(ps_state, week)

    for g in games:
        if g.get("status") != "forfeit" or g.get("winner"):
            continue
        home_id = str(g.get("home_team_id") or "")
        away_id = str(g.get("away_team_id") or "")
        home_team = (ps_state.get("teams") or {}).get(home_id) or {}
        away_team = (ps_state.get("teams") or {}).get(away_id) or {}
        scrubs_forfeit = ps_state.get("scrubs_forfeit") or {}
        home_ff = int(home_team.get("tier") or 0) == 6 and scrubs_forfeit.get(home_team.get("region"))
        away_ff = int(away_team.get("tier") or 0) == 6 and scrubs_forfeit.get(away_team.get("region"))
        tier = int(g.get("tier") or home_team.get("tier") or 6)
        if home_ff and not away_ff:
            _apply_standings(ps_state, away_id, home_id, tier)
            g.update({"winner": away_id, "home_score": 0, "away_score": 0})
        elif away_ff and not home_ff:
            _apply_standings(ps_state, home_id, away_id, tier)
            g.update({"winner": home_id, "home_score": 0, "away_score": 0})

    pending = [g for g in games if g.get("status") not in ("completed", "forfeit", "skipped")]

    for g in pending:
        try:
            _sim_one_game(g, ps_state, week, fid, fpd_by_id, frd_by_id)
        except Exception as ex:
            logger.error("PS sim error: %s", ex, exc_info=True)

    ps_state["trained_week"] = week
    return ps_state


def build_roster_announcement_story(
    ps_state: dict,
    *,
    franchise_id: str,
    team_id: str | None = None,
) -> dict[str, Any]:
    rich_lines: list[dict[str, Any]] = []
    q = f"franchise_id={franchise_id}"
    if team_id:
        q += f"&team_id={team_id}"

    for region in REGION_LETTERS:
        rich_lines.append({"type": "heading", "text": f"Region {region}"})
        for tier in range(1, 6):
            tid = ps_team_id(region, tier)
            team = (ps_state.get("teams") or {}).get(tid) or {}
            display = team.get("display_name") or ps_display_name(region, tier)
            roster = team.get("roster") or []
            parts = [f"{p.get('name')} ({int(p.get('best_rt') or 0)})" for p in roster]
            rich_lines.append(
                {
                    "type": "team_roster",
                    "label": display,
                    "href": f"/team-roster-view.html?mode=practice_squad&ps_team_id={tid}&{q}",
                    "players_line": ", ".join(parts) if parts else "No players assigned.",
                }
            )

    return {
        "story_id": "w1-ps-rosters",
        "week": 1,
        "type": "ps_rosters_announced",
        "headline": "Practice Squad Rosters Announced",
        "rich_lines": rich_lines,
        "created_at": datetime.utcnow(),
    }


def _completed_games_for_week(ps_state: dict, week: int) -> list[dict]:
    games: list[dict] = []
    teams_map = ps_state.get("teams") or {}

    if week in PS_REGULAR_WEEKS:
        for g in (ps_state.get("schedule") or {}).get(str(week)) or []:
            if g.get("status") == "completed" and g.get("game_id"):
                games.append(g)
        return games

    if week in PS_TOURNAMENT_WEEKS:
        round_num = week - PS_TOURNAMENT_WEEKS[0] + 1
        round_key = bracket_engine.get_round_name(round_num)
        for _tier_key, tstate in (ps_state.get("tournaments") or {}).items():
            for m in (tstate.get("bracket") or {}).get(round_key) or []:
                if not m.get("game_id"):
                    continue
                score = m.get("score") or {}
                home_id = str(m.get("home_team") or "")
                away_id = str(m.get("away_team") or "")
                games.append(
                    {
                        "home_team_id": home_id,
                        "away_team_id": away_id,
                        "home_score": score.get(home_id),
                        "away_score": score.get(away_id),
                        "game_id": str(m.get("game_id")),
                        "status": "completed",
                    }
                )
        return games

    if week == PS_CHAMPIONSHIP_WEEK:
        champ = ps_state.get("championship") or {}
        if champ.get("game_id") and champ.get("status") == "completed":
            games.append(champ)
    return games


def build_game_results_story(
    ps_state: dict,
    week: int,
    *,
    franchise_id: str,
    team_id: str | None = None,
) -> dict[str, Any] | None:
    completed = _completed_games_for_week(ps_state, week)
    if not completed:
        return None

    q = f"franchise_id={franchise_id}"
    if team_id:
        q += f"&team_id={team_id}"

    story_id = f"w{week}-ps-game-results"
    news_return = f"/news.html?{q}&story={story_id}"
    return_url = quote(news_return, safe="")

    rich_lines: list[dict[str, Any]] = [
        {
            "type": "link",
            "label": "Practice Squad Standings",
            "href": f"/practice-squad-standings.html?{q}",
        },
        {"type": "gap"},
    ]

    teams_map = ps_state.get("teams") or {}
    for g in completed:
        home_id = str(g.get("home_team_id") or "")
        away_id = str(g.get("away_team_id") or "")
        home_name = (teams_map.get(home_id) or {}).get("display_name") or home_id
        away_name = (teams_map.get(away_id) or {}).get("display_name") or away_id
        hs = g.get("home_score")
        aw = g.get("away_score")
        gid = g.get("game_id")
        rich_lines.append(
            {
                "type": "game_result",
                "text": f"{home_name} {hs}, {away_name} {aw}",
                "box_score_href": f"/box-score.html?game_id={gid}&mode=practice_squad&{q}&return_url={return_url}",
            }
        )

    return {
        "story_id": story_id,
        "week": week,
        "type": "ps_game_results",
        "headline": f"Week {week} Practice Squad Game Results",
        "rich_lines": rich_lines,
        "created_at": datetime.utcnow(),
    }
