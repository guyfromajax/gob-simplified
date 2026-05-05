"""
Franchise End-of-Season Tournament: Conference → Region → National.

Weeks 27–29: Conference tournaments (16 brackets, 8 teams each).
Weeks 30–31: Region tournaments (8 brackets, 4 teams each, with bye logic). Week 30 includes
region finals when there is no playable R1 (e.g. both conferences double-bye, or round1 only
has placeholders) but final already has two real teams.
Weeks 32–34: National tournament (8 region winners).

Seeding/tiebreaker: W first, then natl_rank (no differential).
Does not affect Tournament mode (standalone) tournaments.
"""
from __future__ import annotations

import logging
from copy import deepcopy
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


def _infer_rs1_team_id_from_conference_tournament(ct: Dict[str, Any]) -> Optional[str]:
    """
    RS#1 for region bye logic = conference #1 seed. Prefer ``seeds`` (lowest seed rank);
    if missing (legacy / partial saves), infer from bracket round1[0] (1v8: home is seed 1).
    """
    seeds = ct.get("seeds") or {}
    if seeds:
        best_tid: Any = None
        best_rank = 999
        for tid, rank in seeds.items():
            try:
                r = int(rank)
            except (TypeError, ValueError):
                continue
            if r < best_rank:
                best_rank = r
                best_tid = tid
        if best_tid is not None:
            return str(best_tid)
    bracket = ct.get("bracket") or {}
    r1 = bracket.get("round1") or []
    if not r1 or not isinstance(r1[0], dict):
        return None
    m0 = r1[0]
    ht = m0.get("home_team")
    if ht:
        return str(ht)
    at = m0.get("away_team")
    if at:
        return str(at)
    return None


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
        if c not in rs1:
            inferred = _infer_rs1_team_id_from_conference_tournament(ct)
            if inferred:
                rs1[c] = inferred
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


def _region_tournament_fully_unplayed(rt: Dict[str, Any]) -> bool:
    for m in rt.get("round1") or []:
        if isinstance(m, dict) and m.get("winner"):
            return False
    for m in rt.get("final") or []:
        if isinstance(m, dict) and m.get("winner"):
            return False
    return True


def _r1_matchup_incomplete(m: Any) -> bool:
    if not isinstance(m, dict) or m.get("winner"):
        return False
    a, h = m.get("away_team"), m.get("home_team")
    return not a or not h


def _final_matchup_incomplete(m: Any) -> bool:
    if not isinstance(m, dict) or m.get("winner"):
        return False
    a, h = m.get("away_team"), m.get("home_team")
    return not a or not h


def _merge_region_slots_from_canonical(existing: Dict[str, Any], canonical: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Fill missing away/home on unplayed slots from freshly computed bracket. Returns (merged, changed)."""
    out = deepcopy(existing)
    changed = False
    r1e = out.setdefault("round1", [])
    r1c = canonical.get("round1") or []
    for i in range(len(r1e)):
        if r1e[i].get("winner"):
            continue
        if i >= len(r1c):
            continue
        for side in ("away_team", "home_team"):
            if not r1e[i].get(side) and r1c[i].get(side):
                r1e[i][side] = r1c[i][side]
                changed = True
    fine = out.get("final") or []
    finc = canonical.get("final") or []
    if fine and finc and not fine[0].get("winner"):
        for side in ("away_team", "home_team"):
            if not fine[0].get(side) and finc[0].get(side):
                fine[0][side] = finc[0][side]
                changed = True
    return out, changed


def reconcile_region_tournaments_with_canonical(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: List[Any],
) -> Optional[Dict[str, Any]]:
    """
    Rebuild region brackets from conference champions + RS#1 and merge into the saved doc.

    - If a region has no decided games and has incomplete slots or wrong round1 length, replace
      that region with the canonical bracket.
    - Otherwise copy missing away/home from canonical onto unplayed slots only.

    Returns a new ``region_tournaments`` dict if anything changed, else ``None``.
    """
    if not team_ids:
        return None
    existing = franchise_doc.get("region_tournaments") or {}
    try:
        fresh = initialize_region_tournaments(franchise_doc, teams_collection, team_ids)
    except Exception as exc:
        logger.warning("reconcile_region_tournaments_with_canonical: init failed: %s", exc)
        return None
    if not existing:
        return fresh

    out: Dict[str, Any] = {}
    changed = False
    for r in REGION_LETTERS:
        ex_orig = existing.get(r)
        fr = fresh.get(r) or {}
        if not ex_orig:
            out[r] = deepcopy(fr)
            changed = True
            continue
        ex = deepcopy(ex_orig)
        if _region_tournament_fully_unplayed(ex):
            r1_inc = any(_r1_matchup_incomplete(m) for m in (ex.get("round1") or []))
            fin_list = ex.get("final") or []
            fin_inc = bool(fin_list) and _final_matchup_incomplete(fin_list[0])
            len_mismatch = len(ex.get("round1") or []) != len(fr.get("round1") or [])
            if r1_inc or fin_inc or len_mismatch:
                out[r] = deepcopy(fr)
                changed = True
                continue
        merged, slot_changed = _merge_region_slots_from_canonical(ex, fr)
        out[r] = merged
        if slot_changed:
            changed = True
    return out if changed else None


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

    include_completed True: bracket round follows the calendar EOS week (e.g. week 28 → conference R2).
    include_completed False: bracket round follows each tournament's current_round so playable lists
    stay in sync when franchise week advances before every bracket has finished the prior round.
    """
    games = []
    if week in EOS_CONFERENCE_WEEKS:
        # Calendar column (schedule / history): round follows franchise week (27→R1, 28→R2, 29→final).
        # Playable list (complete_week, play-next, FCC): each bracket uses its own current_round so
        # global week can advance while a conference still has R1 games (avoids empty week lists).
        round_num_calendar = week - 26  # 27->1, 28->2, 29->3
        conf_tournaments = franchise_doc.get("conference_tournaments", {})
        for c in range(1, 17):
            ct = conf_tournaments.get(str(c), conf_tournaments.get(c)) or {}
            if include_completed:
                round_num = round_num_calendar
            else:
                round_num = int(ct.get("current_round", 1) or 1)
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
                r1_playable_appended = 0
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
                        r1_playable_appended += 1
                # No R1 games to list (empty round1, or only placeholders / skipped rows): if final is
                # already two real teams, expose it here so week 30 meta matches week 31 shape.
                if r1_playable_appended == 0:
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
        round_num_calendar = week - 31  # 32->1, 33->2, 34->3
        national = franchise_doc.get("national_tournament", {}) or {}
        if include_completed:
            round_num = round_num_calendar
        else:
            round_num = int(national.get("current_round", 1) or 1)
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


def _eos_team_id_canonical(tid: Any) -> str:
    """Normalize franchise / bracket team ids for comparisons (ObjectId, 24-hex str, etc.)."""
    if tid is None:
        return ""
    if isinstance(tid, ObjectId):
        return str(tid)
    s = str(tid).strip()
    if not s:
        return ""
    if ObjectId.is_valid(s):
        try:
            return str(ObjectId(s))
        except Exception:
            return s
    return s


def eos_meta_bracket_slot_has_winner(franchise_doc: Dict[str, Any], g: Dict[str, Any]) -> bool:
    """True if the EOS meta row's bracket slot already records a ``winner`` (sync/advance can skip)."""
    phase = g.get("phase")
    if phase == "conference":
        ct = _get_conference_tournament_ct(franchise_doc, int(g["conference"]))
        if not ct:
            return False
        br = ct.get("bracket") or {}
        rn = bracket_engine.get_round_name(int(g["round"]))
        lst = br.get(rn) or []
        i = int(g.get("matchup_index", 0))
        if i < 0 or i >= len(lst):
            return False
        return bool((lst[i] or {}).get("winner"))
    if phase == "region":
        rt = (franchise_doc.get("region_tournaments") or {}).get(g["region"]) or {}
        rnum = int(g["round"])
        if rnum == 1:
            lst = rt.get("round1") or []
            i = int(g.get("matchup_index", 0))
            if 0 <= i < len(lst):
                return bool((lst[i] or {}).get("winner"))
            return False
        if rnum == 2:
            fin = rt.get("final") or []
            if fin:
                return bool((fin[0] or {}).get("winner"))
        return False
    if phase == "national":
        nat = franchise_doc.get("national_tournament") or {}
        br = nat.get("bracket") or {}
        rn = bracket_engine.get_round_name(int(g["round"]))
        lst = br.get(rn) or []
        i = int(g.get("matchup_index", 0))
        if 0 <= i < len(lst):
            return bool((lst[i] or {}).get("winner"))
    return False


def _eos_slot_score_dict(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, dict):
        return {"home": 0, "away": 0}
    return {
        "home": int(raw.get("home", 0) or 0),
        "away": int(raw.get("away", 0) or 0),
    }


def get_eos_bracket_slot_snapshot(
    franchise_doc: Dict[str, Any],
    g: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Read the current EOS bracket cell for meta ``g``.

    Returns ``None`` if structure is missing or index is out of range. Otherwise returns
    ``winner_id`` (canonical hex or empty string if no winner yet), ``score`` ``{home, away}``,
    and ``game_id`` (string, possibly empty).
    """
    phase = g.get("phase")
    if phase == "conference":
        ct = _get_conference_tournament_ct(franchise_doc, int(g["conference"]))
        if not ct:
            return None
        br = ct.get("bracket") or {}
        rn = bracket_engine.get_round_name(int(g["round"]))
        lst = br.get(rn) or []
        i = int(g.get("matchup_index", 0))
        if i < 0 or i >= len(lst):
            return None
        m = lst[i] or {}
        w = m.get("winner")
        wid = _eos_team_id_canonical(w) if w else ""
        return {
            "winner_id": wid,
            "score": _eos_slot_score_dict(m.get("score")),
            "game_id": str(m.get("game_id") or ""),
        }
    if phase == "region":
        rt = (franchise_doc.get("region_tournaments") or {}).get(g["region"]) or {}
        rnum = int(g["round"])
        if rnum == 1:
            lst = rt.get("round1") or []
            i = int(g.get("matchup_index", 0))
            if i < 0 or i >= len(lst):
                return None
            m = lst[i] or {}
            w = m.get("winner")
            wid = _eos_team_id_canonical(w) if w else ""
            return {
                "winner_id": wid,
                "score": _eos_slot_score_dict(m.get("score")),
                "game_id": str(m.get("game_id") or ""),
            }
        if rnum == 2:
            fin = rt.get("final") or []
            if not fin:
                return None
            m = fin[0] or {}
            w = m.get("winner")
            wid = _eos_team_id_canonical(w) if w else ""
            return {
                "winner_id": wid,
                "score": _eos_slot_score_dict(m.get("score")),
                "game_id": str(m.get("game_id") or ""),
            }
        return None
    if phase == "national":
        nat = franchise_doc.get("national_tournament", {}) or {}
        br = nat.get("bracket") or {}
        rn = bracket_engine.get_round_name(int(g["round"]))
        lst = br.get(rn) or []
        i = int(g.get("matchup_index", 0))
        if i < 0 or i >= len(lst):
            return None
        m = lst[i] or {}
        w = m.get("winner")
        wid = _eos_team_id_canonical(w) if w else ""
        return {
            "winner_id": wid,
            "score": _eos_slot_score_dict(m.get("score")),
            "game_id": str(m.get("game_id") or ""),
        }
    return None


def find_user_game_in_eos_week(
    week_games: List[Dict[str, Any]],
    user_team_id_str: Optional[str],
) -> Optional[Tuple[int, Dict[str, Any]]]:
    """Return (index, game) if user's team is in one of the games, else None."""
    if not user_team_id_str:
        return None
    user_key = _eos_team_id_canonical(user_team_id_str)
    if not user_key:
        return None
    for idx, g in enumerate(week_games):
        if _eos_team_id_canonical(g.get("away_id")) == user_key or _eos_team_id_canonical(g.get("home_id")) == user_key:
            return (idx, g)
    previews: list[str] = []
    for i, g in enumerate(week_games[:12]):
        previews.append(
            f"{i}:a={_eos_team_id_canonical(g.get('away_id'))[:10]} h={_eos_team_id_canonical(g.get('home_id'))[:10]}"
        )
    logger.warning(
        "[EOS-BRACKET-DEBUG] find_user_game_miss user_key=%s n_games=%s preview=[%s]",
        user_key,
        len(week_games),
        " | ".join(previews) if previews else "(empty week_games_meta)",
    )
    return None


def _get_conference_tournament_ct(franchise_doc: Dict[str, Any], conference: int) -> Optional[Dict[str, Any]]:
    """Resolve conference tournament state; never return a fresh {} (that would wipe keys on writeback)."""
    conf_tournaments = franchise_doc.get("conference_tournaments") or {}
    key = str(conference)
    ct = conf_tournaments.get(key)
    if ct is None:
        ct = conf_tournaments.get(conference)
    if ct is None and key.isdigit():
        try:
            ct = conf_tournaments.get(int(key))
        except (TypeError, ValueError):
            ct = None
    if not isinstance(ct, dict) or not ct:
        return None
    return ct


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
    ct = _get_conference_tournament_ct(franchise_doc, conference)
    if not ct:
        logger.warning(
            "[EOS-BRACKET-DEBUG] save_conference_missing_ct franchise_id=%s conf=%s key=%s",
            str(franchise_doc.get("_id")),
            conference,
            key,
        )
        return
    bracket = ct.get("bracket")
    if not isinstance(bracket, dict) or not bracket.get("round1"):
        logger.warning(
            "[EOS-BRACKET-DEBUG] save_conference_game_result_empty_bracket franchise_id=%s conf=%s "
            "key_str=%s round=%s idx=%s",
            str(franchise_doc.get("_id")),
            conference,
            key,
            round_num,
            matchup_index,
        )
        return
    rn = bracket_engine.get_round_name(round_num)
    rnd_list = bracket.get(rn) or []
    if matchup_index < 0 or matchup_index >= len(rnd_list):
        logger.warning(
            "[EOS-BRACKET-DEBUG] save_conference_OOB franchise_id=%s conf=%s round=%s rn=%s idx=%s len=%s",
            str(franchise_doc.get("_id")),
            conference,
            round_num,
            rn,
            matchup_index,
            len(rnd_list),
        )
        return
    bracket_engine.save_game_result(bracket, round_num, matchup_index, game_id, winner_id, score)
    if int(conference) <= 4:
        logger.warning(
            "[EOS-BRACKET-DEBUG] save_conference_game_result franchise_id=%s conf=%s round=%s idx=%s "
            "winner_id=%s game_id=%s",
            str(franchise_doc.get("_id")),
            conference,
            round_num,
            matchup_index,
            str(winner_id)[:12] if winner_id else "",
            str(game_id)[:12] if game_id else "",
        )
    ct["bracket"] = bracket
    conf_tournaments[key] = ct


def _eos_matchup_pair_key(m: Any) -> tuple[str, str]:
    if not isinstance(m, dict):
        return ("", "")
    h, a = m.get("home_team"), m.get("away_team")
    return (str(h) if h is not None else "", str(a) if a is not None else "")


def _merge_eos_round_matchup_lists(fresh_list: List[Any], stale_list: List[Any]) -> List[Any]:
    """
    Copy ``fresh_list`` matchup dicts; for any slot with no ``winner``, copy ``winner``,
    ``game_id``, and ``score`` from the stale list slot with the same (home_team, away_team).

    Used when phase A re-reads EOS blobs from Mongo after ``start-cpu-sims`` so CPU-written
    winners are not overwritten by an in-memory franchise doc loaded before those writes.
    """
    stale_by_pair: Dict[tuple[str, str], Dict[str, Any]] = {}
    for sm in stale_list or []:
        if isinstance(sm, dict):
            stale_by_pair.setdefault(_eos_matchup_pair_key(sm), sm)
    out: List[Any] = []
    for fm in fresh_list or []:
        if not isinstance(fm, dict):
            out.append(fm)
            continue
        m = deepcopy(fm)
        if not m.get("winner"):
            sm = stale_by_pair.get(_eos_matchup_pair_key(m))
            if isinstance(sm, dict) and sm.get("winner"):
                m["winner"] = sm.get("winner")
                if "game_id" in sm:
                    m["game_id"] = sm.get("game_id")
                if sm.get("score") is not None:
                    m["score"] = deepcopy(sm.get("score"))
        out.append(m)
    return out


def _merge_bracket_round_dict(fresh_bracket: Dict[str, Any], stale_bracket: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(fresh_bracket) if isinstance(fresh_bracket, dict) else {}
    for rk in bracket_engine.ROUND_KEYS:
        fl = out.get(rk)
        if not isinstance(fl, list):
            continue
        sl = (stale_bracket or {}).get(rk) or []
        out[rk] = _merge_eos_round_matchup_lists(fl, sl)
    return out


def _resolve_region_final_placeholders(rt: Dict[str, Any]) -> Dict[str, Any]:
    """Replace resolved R1_0/R1_1 final placeholders with their known R1 winners."""
    out = deepcopy(rt)
    round1 = out.get("round1") or []
    final = out.get("final") or []
    if not final or not isinstance(final[0], dict):
        return out

    f = final[0]
    for idx, placeholder in ((0, "R1_0"), (1, "R1_1")):
        if idx >= len(round1) or not isinstance(round1[idx], dict):
            continue
        winner = round1[idx].get("winner")
        if not winner:
            continue
        winner_str = str(winner)
        if f.get("away_team") == placeholder:
            f["away_team"] = winner_str
        if f.get("home_team") == placeholder:
            f["home_team"] = winner_str
    out["final"] = final
    return out


def _merge_one_conference_tournament_ct(f_ct: Dict[str, Any], s_ct: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(f_ct)
    fb = out.get("bracket") or {}
    sb = (s_ct or {}).get("bracket") or {}
    out["bracket"] = _merge_bracket_round_dict(fb, sb)
    return out


def merge_conference_tournaments_phase_a(fresh: Any, stale: Any) -> Dict[str, Any]:
    if not isinstance(stale, dict):
        return deepcopy(fresh) if isinstance(fresh, dict) else {}
    if not isinstance(fresh, dict) or not fresh:
        return deepcopy(stale)
    out = deepcopy(fresh)
    for key_raw, s_ct in stale.items():
        if not isinstance(s_ct, dict):
            continue
        try:
            ks = str(int(str(key_raw)))
        except (TypeError, ValueError):
            ks = str(key_raw)
        f_ct = out.get(ks) or out.get(key_raw)
        if not isinstance(f_ct, dict):
            out[ks] = deepcopy(s_ct)
            continue
        out[ks] = _merge_one_conference_tournament_ct(f_ct, s_ct)
    return out


def merge_region_tournaments_phase_a(fresh: Any, stale: Any) -> Dict[str, Any]:
    if not isinstance(stale, dict):
        return deepcopy(fresh) if isinstance(fresh, dict) else {}
    if not isinstance(fresh, dict) or not fresh:
        return deepcopy(stale)
    out = deepcopy(fresh)
    for region_key, s_rt in stale.items():
        if not isinstance(s_rt, dict):
            continue
        f_rt = out.get(region_key)
        if not isinstance(f_rt, dict):
            out[region_key] = deepcopy(s_rt)
            continue
        merged_rt = deepcopy(f_rt)
        for rk in ("round1", "final"):
            if rk in merged_rt and isinstance(merged_rt[rk], list):
                sl = s_rt.get(rk) or []
                merged_rt[rk] = _merge_eos_round_matchup_lists(merged_rt[rk], sl)
        out[region_key] = _resolve_region_final_placeholders(merged_rt)
    return out


def merge_national_tournament_phase_a(fresh: Any, stale: Any) -> Dict[str, Any]:
    if not isinstance(stale, dict):
        return deepcopy(fresh) if isinstance(fresh, dict) else {}
    if not isinstance(fresh, dict) or not fresh:
        return deepcopy(stale)
    out = deepcopy(fresh)
    fb = out.get("bracket") or {}
    sb = stale.get("bracket") or {}
    out["bracket"] = _merge_bracket_round_dict(fb, sb)
    return out


def merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise(
    fresh_projection: Dict[str, Any],
    stale_franchise_doc: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Reconcile EOS tournament blobs for ``complete_week`` phase A ``$set``.

    ``fresh_projection`` should be a recent ``find_one`` on the franchise (CPU sims, etc.);
    ``stale_franchise_doc`` is the in-memory doc after ``_complete_week_process_user_game_block``.
    """
    merged: Dict[str, Any] = {}
    if not isinstance(fresh_projection, dict):
        fresh_projection = {}
    if not isinstance(stale_franchise_doc, dict):
        stale_franchise_doc = {}
    for key in ("conference_tournaments", "region_tournaments", "national_tournament"):
        stale_val = stale_franchise_doc.get(key)
        if stale_val is None:
            continue
        fresh_val = fresh_projection.get(key)
        if key == "conference_tournaments":
            merged[key] = merge_conference_tournaments_phase_a(fresh_val, stale_val)
        elif key == "region_tournaments":
            merged[key] = merge_region_tournaments_phase_a(fresh_val, stale_val)
        else:
            merged[key] = merge_national_tournament_phase_a(fresh_val, stale_val)
    return merged


def log_eos_conference_bracket_snapshot(franchise_doc: Dict[str, Any], label: str) -> None:
    """Temporary debug: log R1 winner counts and round2 size per conference (grep [EOS-BRACKET-DEBUG])."""
    franch_id = franchise_doc.get("_id")
    ct_all = franchise_doc.get("conference_tournaments") or {}
    for c in range(1, 17):
        ct = ct_all.get(str(c)) or ct_all.get(c) or {}
        br = ct.get("bracket") or {}
        r1 = br.get("round1") or []
        r2 = br.get("round2") or []
        nwin = sum(1 for m in r1 if m.get("winner"))
        logger.warning(
            "[EOS-BRACKET-DEBUG] %s franchise_id=%s conf=%s current_round=%s r1_winners=%s/4 r2_len=%s",
            label,
            str(franch_id),
            c,
            ct.get("current_round"),
            nwin,
            len(r2),
        )


def advance_conference_bracket(
    franchise_doc: Dict[str, Any],
    conference: int,
) -> Tuple[bool, Optional[str]]:
    """Advance one conference bracket. Returns (advanced, champion_if_finished)."""
    conf_tournaments = franchise_doc.get("conference_tournaments", {})
    key = str(conference)
    ct = _get_conference_tournament_ct(franchise_doc, conference)
    if not ct:
        logger.warning(
            "[EOS-BRACKET-DEBUG] advance_conference_missing_ct franchise_id=%s conf=%s",
            str(franchise_doc.get("_id")),
            conference,
        )
        return (False, None)
    bracket = ct.get("bracket", {})
    current_round = ct.get("current_round", 1)
    r1 = bracket.get("round1") or []
    r1_winners_before = sum(1 for m in r1 if m.get("winner"))
    updated, next_round, completed, champion = bracket_engine.advance_bracket(
        bracket, current_round, winners_from_matchups=True
    )
    ct["bracket"] = updated
    ct["current_round"] = next_round
    if completed and champion:
        ct["champion"] = champion
    r2_after = len((updated.get("round2") or []))
    logger.warning(
        "[EOS-BRACKET-DEBUG] advance_conference franchise_id=%s conf=%s cr_before=%s cr_after=%s "
        "r1_winners_before=%s/4 advanced=%s r2_len_after=%s champion=%s",
        str(franchise_doc.get("_id")),
        conference,
        current_round,
        next_round,
        r1_winners_before,
        next_round > current_round,
        r2_after,
        champion,
    )
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
