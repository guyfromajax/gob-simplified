"""
Franchise End-of-Season Tournament: Conference → Region → National.

Weeks 27–29: Conference tournaments (16 brackets, 8 teams each).
Weeks 30–31: Region tournaments (8 brackets, 4 teams each, with bye logic).
Weeks 32–34: National tournament (8 region winners).

Seeding/tiebreaker: W first, then natl_rank (no differential).
Does not affect Tournament mode (standalone) tournaments.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from BackEnd.tournament import bracket_engine
from BackEnd.tournament.eos_tournament import calculate_standings
from BackEnd.utils.franchise_standings import calculate_franchise_standings
from BackEnd.db import franchise_team_data_collection

logger = logging.getLogger(__name__)

REGULAR_SEASON_WEEKS = 26
EOS_CONFERENCE_WEEKS = (27, 28, 29)
EOS_REGION_WEEKS = (30, 31)
EOS_NATIONAL_WEEKS = (32, 33, 34)
EOS_WEEKS = (*EOS_CONFERENCE_WEEKS, *EOS_REGION_WEEKS, *EOS_NATIONAL_WEEKS)

REGION_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"]


def _conference_to_region(conference: int) -> str:
    """Conference 1-16 -> region letter A-H. Conferences 1,2->A; 3,4->B; ..."""
    if not 1 <= conference <= 16:
        return "A"
    return REGION_LETTERS[(conference - 1) // 2]


def _region_to_conferences(region: str) -> Tuple[int, int]:
    """Region A-H -> (conf1, conf2). e.g. A -> (1, 2)."""
    try:
        idx = REGION_LETTERS.index(region)
        return idx * 2 + 1, idx * 2 + 2
    except ValueError:
        return 1, 2


def get_team_conference_region(teams_collection, team_ids: List[Any]) -> Tuple[Dict[str, int], Dict[str, str]]:
    """Return team_id_str -> conference (1-16), team_id_str -> region (A-H)."""
    docs = list(teams_collection.find(
        {"_id": {"$in": [ObjectId(t) if not isinstance(t, ObjectId) else t for t in team_ids]}},
        {"_id": 1, "conference": 1, "region": 1},
    ))
    by_id = {}
    for d in docs:
        tid = str(d["_id"])
        c = d.get("conference")
        r = d.get("region")
        if c is not None:
            by_id[tid] = (c, r if r is not None else _conference_to_region(c))
    team_to_conference = {tid: c for tid, (c, _) in by_id.items()}
    team_to_region = {tid: r for tid, (_, r) in by_id.items()}
    return team_to_conference, team_to_region


def get_conference_standings(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: List[Any],
    team_to_conference: Dict[str, int],
    conference_number: int,
) -> List[Dict[str, Any]]:
    """Standings for one conference (W, natl_rank). Sorted by W desc, natl_rank asc. Returns 8 teams."""
    all_standings = calculate_standings(franchise_doc, teams_collection, team_ids=team_ids)
    conf_teams = [s for s in all_standings if team_to_conference.get(s["team_id"]) == conference_number]
    conf_teams.sort(key=lambda x: (-x["wins"], x["natl_rank"]))
    return conf_teams[:8]


def initialize_conference_tournaments(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: List[Any],
) -> Dict[str, Dict[str, Any]]:
    """Build 16 conference brackets. Seeds from conference standings (W, natl_rank). Keys are str for BSON."""
    team_to_conference, _ = get_team_conference_region(teams_collection, team_ids)
    out = {}
    for c in range(1, 17):
        conf_standings = get_conference_standings(
            franchise_doc, teams_collection, team_ids, team_to_conference, c
        )
        if len(conf_standings) != 8:
            raise ValueError(
                f"Conference {c} has {len(conf_standings)} teams, expected 8."
            )
        seed_order = [s["team_id"] for s in conf_standings]
        bracket = bracket_engine.generate_bracket(seed_order)
        seeds = {s["team_id"]: i + 1 for i, s in enumerate(conf_standings)}
        # BSON requires string keys; use str(c) so franchise doc serializes to MongoDB.
        out[str(c)] = {
            "bracket": bracket,
            "current_round": 1,
            "seeds": seeds,
            "champion": None,
        }
    return out


def _build_region_bracket(
    conf1: int,
    conf2: int,
    conf_champions: Dict[int, str],
    conf_rs1: Dict[int, str],
) -> Dict[str, Any]:
    """One region: qualifiers from two conferences. Bye logic per spec."""
    c1_tw = conf_champions.get(conf1)
    c1_rs1 = conf_rs1.get(conf1)
    c2_tw = conf_champions.get(conf2)
    c2_rs1 = conf_rs1.get(conf2)
    double1 = c1_tw and c1_rs1 and c1_tw == c1_rs1
    double2 = c2_tw and c2_rs1 and c2_tw == c2_rs1

    def m(away: Any, home: Any) -> Dict[str, Any]:
        return {"away_team": away, "home_team": home, "game_id": None, "winner": None, "score": {}}

    if double1 and double2:
        return {"round1": [], "final": [m(c1_tw, c2_tw)], "current_round": 1}
    if double1 and not double2:
        return {"round1": [m(c2_tw, c2_rs1)], "final": [m("R1_0", c1_tw)], "current_round": 1}
    if double2 and not double1:
        return {"round1": [m(c1_tw, c1_rs1)], "final": [m("R1_0", c2_tw)], "current_round": 1}
    return {
        "round1": [m(c1_tw, c2_rs1), m(c2_tw, c1_rs1)],
        "final": [m("R1_0", "R1_1")],
        "current_round": 1,
    }


def _get_conf_champions_and_rs1(
    franchise_doc: Dict[str, Any],
    team_ids: List[Any],
    team_to_conference: Dict[str, int],
) -> Tuple[Dict[int, str], Dict[int, str]]:
    """After conference tournaments: champion and RS#1 per conference. RS#1 = seed 1 (first in seeds)."""
    conf_tournaments = franchise_doc.get("conference_tournaments", {})
    champions = {}
    rs1 = {}
    for c in range(1, 17):
        ct = conf_tournaments.get(str(c), conf_tournaments.get(c)) or {}
        champ = ct.get("champion")
        if champ:
            champions[c] = str(champ)
        seeds = ct.get("seeds", {})
        if seeds:
            seed_order = [tid for tid, _ in sorted(seeds.items(), key=lambda x: x[1])]
            if seed_order:
                rs1[c] = str(seed_order[0])
    return champions, rs1


def initialize_region_tournaments(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: List[Any],
) -> Dict[str, Dict[str, Any]]:
    """Build 8 region brackets from conference champions and RS#1. Bye logic applied."""
    team_to_conference, _ = get_team_conference_region(teams_collection, team_ids)
    champions, rs1 = _get_conf_champions_and_rs1(franchise_doc, team_ids, team_to_conference)
    out = {}
    for r in REGION_LETTERS:
        conf1, conf2 = _region_to_conferences(r)
        out[r] = _build_region_bracket(conf1, conf2, champions, rs1)
    return out


def initialize_national_tournament(
    franchise_doc: Dict[str, Any],
    teams_collection,
    region_champions: Dict[str, str],
    franchise_results: Dict[str, List],
    team_ids: List[Any],
) -> Dict[str, Any]:
    """8 region winners, seeded by W then natl_rank. Uses only regular-season (weeks 1–26) for W."""
    reg_season_only = {
        k: v for k, v in franchise_results.items()
        if isinstance(k, str) and k.isdigit() and 1 <= int(k) <= REGULAR_SEASON_WEEKS
    }
    team_ids_map = {str(tid): {} for tid in team_ids}
    standings_data = calculate_franchise_standings(reg_season_only, team_ids_map)
    franchise_id = franchise_doc.get("_id")
    natl_rank_by_team_id = {}
    if franchise_id:
        ftd_docs = list(franchise_team_data_collection.find(
            {"franchise_id": franchise_id},
            {"team_id": 1, "natl_rank": 1},
        ))
        natl_rank_by_team_id = {str(d["team_id"]): d.get("natl_rank", 999) for d in ftd_docs if d.get("team_id")}

    rank_list = []
    for tid in region_champions.values():
        tid_str = str(tid)
        w = standings_data.get(tid_str, {}).get("W", 0)
        nr = natl_rank_by_team_id.get(tid_str, 999)
        rank_list.append((tid_str, w, nr))
    rank_list.sort(key=lambda x: (-x[1], x[2]))
    seed_order = [x[0] for x in rank_list]
    if len(seed_order) < 8:
        raise ValueError(f"National tournament needs 8 teams, got {len(seed_order)}")
    bracket = bracket_engine.generate_bracket(seed_order)
    return {
        "bracket": bracket,
        "current_round": 1,
        "seeds": {tid: i + 1 for i, tid in enumerate(seed_order)},
        "champion": None,
    }


def get_eos_week_games(
    franchise_doc: Dict[str, Any],
    week: int,
    include_completed: bool = False,
) -> List[Dict[str, Any]]:
    """
    Return list of games for the given EOS week. Each item: {away_id, home_id, phase, meta}.
    meta: conference/region, round, matchup_index for routing results.
    If include_completed True, also return winner, score, game_id on each item.
    """
    games = []
    if week in EOS_CONFERENCE_WEEKS:
        round_num = week - 26  # 27->1, 28->2, 29->3
        conf_tournaments = franchise_doc.get("conference_tournaments", {})
        for c in range(1, 17):
            ct = conf_tournaments.get(str(c), conf_tournaments.get(c)) or {}
            if not include_completed and ct.get("current_round") != round_num:
                continue
            bracket = ct.get("bracket", {})
            rn = bracket_engine.get_round_name(round_num)
            matchups = bracket.get(rn, [])
            for i, m in enumerate(matchups):
                away = m.get("away_team")
                home = m.get("home_team")
                if not away or not home:
                    continue
                if not include_completed and m.get("winner"):
                    continue
                g = {
                    "away_id": ObjectId(away) if isinstance(away, str) and len(away) == 24 else away,
                    "home_id": ObjectId(home) if isinstance(home, str) and len(home) == 24 else home,
                    "phase": "conference",
                    "conference": c,
                    "round": round_num,
                    "matchup_index": i,
                }
                if include_completed:
                    g["winner"] = m.get("winner")
                    g["score"] = m.get("score", {})
                    g["game_id"] = m.get("game_id")
                games.append(g)
    elif week in EOS_REGION_WEEKS:
        region_tournaments = franchise_doc.get("region_tournaments", {})
        if week == 30:
            for r in REGION_LETTERS:
                rt = region_tournaments.get(r, {})
                round1 = rt.get("round1", [])
                for i, m in enumerate(round1):
                    if not include_completed and m.get("winner"):
                        continue
                    away = m.get("away_team")
                    home = m.get("home_team")
                    if away and home and not (isinstance(away, str) and away.startswith("R1")) and not (isinstance(home, str) and home.startswith("R1")):
                        g = {
                            "away_id": ObjectId(away) if isinstance(away, str) else away,
                            "home_id": ObjectId(home) if isinstance(home, str) else home,
                            "phase": "region",
                            "region": r,
                            "round": 1,
                            "matchup_index": i,
                        }
                        if include_completed:
                            g["winner"] = m.get("winner")
                            g["score"] = m.get("score", {})
                            g["game_id"] = m.get("game_id")
                        games.append(g)
        else:
            for r in REGION_LETTERS:
                rt = region_tournaments.get(r, {})
                final = rt.get("final", [])
                if not final:
                    continue
                m = final[0]
                if not include_completed and m.get("winner"):
                    continue
                away = m.get("away_team")
                home = m.get("home_team")
                if isinstance(away, str) and away.startswith("R1"):
                    continue
                if isinstance(home, str) and home.startswith("R1"):
                    continue
                if away and home:
                    g = {
                        "away_id": ObjectId(away) if isinstance(away, str) else away,
                        "home_id": ObjectId(home) if isinstance(home, str) else home,
                        "phase": "region",
                        "region": r,
                        "round": 2,
                        "matchup_index": 0,
                    }
                    if include_completed:
                        g["winner"] = m.get("winner")
                        g["score"] = m.get("score", {})
                        g["game_id"] = m.get("game_id")
                    games.append(g)
    elif week in EOS_NATIONAL_WEEKS:
        round_num = week - 31  # 32->1, 33->2, 34->3
        national = franchise_doc.get("national_tournament", {})
        if not include_completed and national.get("current_round") != round_num:
            return games
        bracket = national.get("bracket", {})
        rn = bracket_engine.get_round_name(round_num)
        matchups = bracket.get(rn, [])
        for i, m in enumerate(matchups):
            if not include_completed and m.get("winner"):
                continue
            away = m.get("away_team")
            home = m.get("home_team")
            if away and home:
                g = {
                    "away_id": ObjectId(away) if isinstance(away, str) and len(away) == 24 else away,
                    "home_id": ObjectId(home) if isinstance(home, str) and len(home) == 24 else home,
                    "phase": "national",
                    "round": round_num,
                    "matchup_index": i,
                }
                if include_completed:
                    g["winner"] = m.get("winner")
                    g["score"] = m.get("score", {})
                    g["game_id"] = m.get("game_id")
                games.append(g)
    return games


def find_user_game_in_eos_week(
    week_games: List[Dict[str, Any]],
    user_team_id_str: Optional[str],
) -> Optional[Tuple[int, Dict[str, Any]]]:
    """Return (index, game) if user's team is in one of the games, else None."""
    if not user_team_id_str:
        return None
    for idx, g in enumerate(week_games):
        if str(g["away_id"]) == user_team_id_str or str(g["home_id"]) == user_team_id_str:
            return (idx, g)
    return None


def save_conference_game_result(
    franchise_doc: Dict[str, Any],
    conference: int,
    round_num: int,
    matchup_index: int,
    game_id: str,
    winner_id: str,
    score: Dict[str, int],
) -> None:
    """Mutates franchise_doc['conference_tournaments']."""
    conf_tournaments = franchise_doc.setdefault("conference_tournaments", {})
    key = str(conference)
    ct = conf_tournaments.get(key, {})
    bracket = ct.get("bracket", {})
    bracket_engine.save_game_result(bracket, round_num, matchup_index, game_id, winner_id, score)
    ct["bracket"] = bracket
    conf_tournaments[key] = ct


def advance_conference_bracket(
    franchise_doc: Dict[str, Any],
    conference: int,
) -> Tuple[bool, Optional[str]]:
    """Advance one conference bracket. Returns (advanced, champion_if_finished)."""
    conf_tournaments = franchise_doc.get("conference_tournaments", {})
    ct = conf_tournaments.get(str(conference), {})
    bracket = ct.get("bracket", {})
    current_round = ct.get("current_round", 1)
    updated, next_round, completed, champion = bracket_engine.advance_bracket(
        bracket, current_round, winners_from_matchups=True
    )
    ct["bracket"] = updated
    ct["current_round"] = next_round
    if completed and champion:
        ct["champion"] = champion
    conf_tournaments[str(conference)] = ct
    franchise_doc["conference_tournaments"] = conf_tournaments
    return (next_round > current_round, champion if completed else None)


def save_region_game_result(
    franchise_doc: Dict[str, Any],
    region: str,
    round_num: int,
    matchup_index: int,
    game_id: str,
    winner_id: str,
    score: Dict[str, int],
) -> None:
    """Mutates franchise_doc['region_tournaments']. R1_0 = winner round1[0], R1_1 = winner round1[1]."""
    region_tournaments = franchise_doc.setdefault("region_tournaments", {})
    rt = region_tournaments.get(region, {})
    winner_str = str(winner_id)
    if round_num == 1:
        round1 = rt.get("round1", [])
        if matchup_index < len(round1):
            m = round1[matchup_index]
            m["game_id"] = game_id
            m["winner"] = winner_str
            m["score"] = score
            final = rt.get("final", [])
            if final:
                f = final[0]
                placeholder = "R1_0" if matchup_index == 0 else "R1_1"
                if f.get("away_team") == placeholder:
                    f["away_team"] = winner_str
                if f.get("home_team") == placeholder:
                    f["home_team"] = winner_str
        rt["round1"] = round1
        rt["final"] = rt.get("final", [])
    else:
        final = rt.get("final", [])
        if final and matchup_index == 0:
            final[0]["game_id"] = game_id
            final[0]["winner"] = winner_str
            final[0]["score"] = score
        rt["final"] = final
    rt["current_round"] = 2
    region_tournaments[region] = rt
    franchise_doc["region_tournaments"] = region_tournaments


def advance_region_bracket(
    franchise_doc: Dict[str, Any],
    region: str,
) -> Optional[str]:
    """Return region champion if final has winner; no bracket advance (fill done in save_region_game_result)."""
    region_tournaments = franchise_doc.get("region_tournaments", {})
    rt = region_tournaments.get(region, {})
    final = rt.get("final", [])
    if not final:
        return None
    if final[0].get("winner"):
        return final[0]["winner"]
    return None


def save_national_game_result(
    franchise_doc: Dict[str, Any],
    round_num: int,
    matchup_index: int,
    game_id: str,
    winner_id: str,
    score: Dict[str, int],
) -> None:
    """Mutates franchise_doc['national_tournament']."""
    national = franchise_doc.setdefault("national_tournament", {})
    bracket = national.get("bracket", {})
    bracket_engine.save_game_result(bracket, round_num, matchup_index, game_id, str(winner_id), score)
    national["bracket"] = bracket
    franchise_doc["national_tournament"] = national


def advance_national_bracket(franchise_doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Advance national bracket. Returns (advanced, champion_if_finished)."""
    national = franchise_doc.get("national_tournament", {})
    bracket = national.get("bracket", {})
    current_round = national.get("current_round", 1)
    updated, next_round, completed, champion = bracket_engine.advance_bracket(
        bracket, current_round, winners_from_matchups=True
    )
    national["bracket"] = updated
    national["current_round"] = next_round
    if completed and champion:
        national["champion"] = champion
    franchise_doc["national_tournament"] = national
    return (next_round > current_round, champion if completed else None)


def get_region_champions(franchise_doc: Dict[str, Any]) -> Dict[str, str]:
    """After week 31: region -> champion team id string."""
    region_tournaments = franchise_doc.get("region_tournaments", {})
    champs = {}
    for r in REGION_LETTERS:
        rt = region_tournaments.get(r, {})
        final = rt.get("final", [])
        if final and final[0].get("winner"):
            champs[r] = str(final[0]["winner"])
    return champs


def get_eliminated_team_ids(franchise_doc: Dict[str, Any]) -> set:
    """
    Return set of team ID strings that have been eliminated from tournament play
    (lost a game in conference, region, or national bracket). Used to skip
    training for eliminated computer teams during EOS weeks (Franchise_Tournament_System.md).
    """
    eliminated = set()
    # Placeholders in brackets (e.g. region R1_0/R1_1) are not team IDs
    def is_team_id(s):
        if s is None or not isinstance(s, str):
            return False
        if s.startswith("R1_") or len(s) != 24:
            return False
        try:
            ObjectId(s)
            return True
        except Exception:
            return False

    def add_loser(m):
        winner = m.get("winner")
        if not winner or not is_team_id(winner):
            return
        home = m.get("home_team")
        away = m.get("away_team")
        loser = str(away) if str(winner) == str(home) else str(home)
        if is_team_id(loser):
            eliminated.add(loser)

    for c in range(1, 17):
        ct = (franchise_doc.get("conference_tournaments") or {}).get(str(c), {})
        bracket = ct.get("bracket", {})
        for rnd in ("round1", "round2", "final"):
            for m in bracket.get(rnd, []):
                add_loser(m)

    for r in REGION_LETTERS:
        rt = (franchise_doc.get("region_tournaments") or {}).get(r, {})
        for rnd in ("round1", "final"):
            for m in rt.get(rnd, []):
                add_loser(m)

    national = franchise_doc.get("national_tournament") or {}
    bracket = national.get("bracket", {})
    for rnd in ("round1", "round2", "final"):
        for m in bracket.get(rnd, []):
            add_loser(m)

    return eliminated
