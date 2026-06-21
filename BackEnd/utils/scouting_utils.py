"""
Shared utilities for scouting report functionality.
Extracts play usage data from game documents for both franchise and tournament modes.
"""
from typing import List, Dict, Any, Optional, Tuple

from bson import ObjectId

from BackEnd.db import teams_collection, players_collection
from BackEnd.utils.roster_builder import build_roster_players, ATTR_KEYS as SCOUTING_CORE_ATTR_KEYS
from BackEnd.utils.team_play_utils import iter_team_plays


def _resolve_game_team_key(
    teams_obj: Dict[str, Any],
    team_name: str,
    team_object_id: str,
    team_id_field: Optional[str],
) -> Optional[str]:
    """Resolve a team's key in a game document's ``teams`` object. Keys may be
    team_id strings (e.g. "LITTLE_YORK"), team names, or ObjectId strings."""
    for key in teams_obj.keys():
        if team_id_field and key == team_id_field:
            return key
        if key == team_name:
            return key
        try:
            if len(key) == 24:  # ObjectId string length
                key_obj_id = ObjectId(key)
                if key_obj_id == ObjectId(team_object_id):
                    return key
                key_team_doc = teams_collection.find_one({"_id": key_obj_id})
                if key_team_doc and key_team_doc.get("name") == team_name:
                    return key
        except Exception:
            pass
    return None


def extract_plays_from_game_document(
    last_game: Dict[str, Any],
    team_name: str,
    team_object_id: str,
    team_id_field: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Extract play usage data from a game document for scouting reports.
    
    This function handles the complex matching logic to find the correct team
    in the game document's teams object, which can be keyed by team_id strings,
    team names, or ObjectId strings.
    
    Args:
        last_game: Game document from games collection
        team_name: Name of the team (e.g., "Little York")
        team_object_id: ObjectId string of the team document
        team_id_field: team_id field value (e.g., "LITTLE_YORK")
    
    Returns:
        List of play dictionaries with name, times_run, successes, and total_playcalls
    """
    plays_data = []
    
    if not last_game:
        return plays_data
    
    # Extract play usage from game document
    teams_obj = last_game.get("teams", {})
    
    if not teams_obj:
        return plays_data
    
    # Game documents key teams by team_id string / name / ObjectId string.
    team_key = _resolve_game_team_key(teams_obj, team_name, team_object_id, team_id_field)
    if not team_key:
        return plays_data
    
    team_plays = teams_obj.get(team_key, {}).get("plays", {})
    
    if not team_plays:
        return plays_data
    
    # Calculate total playcalls for usage %
    total_playcalls = 0
    for _play_key, play_data, _display_name in iter_team_plays(team_plays):
        game_stats = play_data.get("game_stats", {})
        times_run = game_stats.get("times_run", 0)
        total_playcalls += times_run
    
    # Build plays array
    for play_key, play_data, display_name in iter_team_plays(team_plays):
        game_stats = play_data.get("game_stats", {})
        times_run = game_stats.get("times_run", 0)
        successes = game_stats.get("successes", 0)
        
        if times_run > 0:  # Only include plays that were actually run
            plays_data.append({
                "play_id": play_data.get("play_id"),
                "name": display_name,
                "play_key": play_key,
                "times_run": times_run,
                "successes": successes,
                "total_playcalls": total_playcalls
            })
    
    return plays_data


def extract_play_counters_from_game_document(
    last_game: Dict[str, Any],
    team_name: str,
    team_object_id: str,
    team_id_field: Optional[str],
    *,
    side: str,
    subkey: str,
    label_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Per-play A/S counter extractor for the scouting report (Fast Break /
    HCT trap), mirroring ``extract_plays_from_game_document``'s per-game
    semantics. Reads the team's saved per-game ``scouting`` snapshot at
    ``teams[key]["scouting"][side][subkey]`` — e.g. ``offense.fast_break_plays``
    or ``defense.hct_trap_plays``. Returns rows shaped for ``renderPlayUsage``
    (``name`` / ``times_run`` / ``successes``), only for plays actually run
    (A > 0). ``A`` → ``times_run``, ``S`` → ``successes``.
    """
    rows: List[Dict[str, Any]] = []
    if not last_game:
        return rows
    teams_obj = last_game.get("teams", {})
    if not teams_obj:
        return rows
    team_key = _resolve_game_team_key(teams_obj, team_name, team_object_id, team_id_field)
    if not team_key:
        return rows
    scouting = teams_obj.get(team_key, {}).get("scouting", {}) or {}
    counters = (scouting.get(side) or {}).get(subkey) or {}
    if not isinstance(counters, dict):
        return rows
    for play_key, label in label_map.items():
        stats = counters.get(play_key) or {}
        attempts = int(stats.get("A", 0) or 0)
        successes = int(stats.get("S", 0) or 0)
        if attempts > 0:
            rows.append({
                "play_key": play_key,
                "name": label,
                "times_run": attempts,
                "successes": successes,
            })
    return rows


SCOUTING_LINEUP_POSITIONS: Tuple[str, ...] = ("PG", "SG", "SF", "PF", "C")


def _player_sort_key(p: Dict[str, Any]) -> str:
    return str(p.get("_id") or p.get("player_id") or "")


def _parse_rt(pr: Dict[str, Any], pos: str) -> Optional[float]:
    raw = (pr or {}).get(pos)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def compute_projected_starting_five(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Greedy projected lineup: repeatedly pick the best remaining (player, open position)
    pair by highest RT; each player and position used at most once.

    Returns rows in fixed order PG → C for display, omitting unfilled slots.
    """
    assigned_players: set[str] = set()
    lineup_by_pos: Dict[str, Tuple[Dict[str, Any], float]] = {}

    while len(lineup_by_pos) < 5:
        best_key: Optional[Tuple[float, str, int]] = None  # (-rt, pid, pos_index) for min()
        best_player: Optional[Dict[str, Any]] = None
        best_pos: Optional[str] = None

        for p in players:
            pid = _player_sort_key(p)
            if not pid or pid in assigned_players:
                continue
            pr = p.get("position_ratings") or {}
            for pos in SCOUTING_LINEUP_POSITIONS:
                if pos in lineup_by_pos:
                    continue
                rt = _parse_rt(pr, pos)
                if rt is None:
                    continue
                # Minimize (-rt, pid, pos) => max rt, then stable pid, then position order
                cand = (-rt, pid, SCOUTING_LINEUP_POSITIONS.index(pos))
                if best_key is None or cand < best_key:
                    best_key = cand
                    best_player = p
                    best_pos = pos

        if best_player is None or best_pos is None:
            break
        rt_chosen = _parse_rt(best_player.get("position_ratings") or {}, best_pos) or 0.0
        lineup_by_pos[best_pos] = (best_player, float(rt_chosen))
        assigned_players.add(_player_sort_key(best_player))

    rows: List[Dict[str, Any]] = []
    attrs_keys = list(SCOUTING_CORE_ATTR_KEYS)
    for pos in SCOUTING_LINEUP_POSITIONS:
        if pos not in lineup_by_pos:
            continue
        p, rt = lineup_by_pos[pos]
        attrs = p.get("attributes") or {}
        attr_display = {}
        for k in attrs_keys:
            raw = attrs.get(f"anchor_{k}", attrs.get(k, 0))
            try:
                attr_display[k] = int(float(raw)) // 10
            except (TypeError, ValueError):
                attr_display[k] = 0
        try:
            rt_out = round(float(rt), 1)
        except (TypeError, ValueError):
            rt_out = 0.0
        rows.append(
            {
                "position": pos,
                "player_id": _player_sort_key(p),
                "name": (p.get("name") or f"{p.get('first_name', '')} {p.get('last_name', '')}").strip(),
                "jersey": p.get("jersey"),
                "year": p.get("year") or "",
                "height": p.get("height"),
                "weight": p.get("weight"),
                "rt": rt_out,
                "attributes": attr_display,
            }
        )
    return rows


def load_tournament_roster_for_scouting(
    tournament_doc: Dict[str, Any], team_doc: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Same player shape as GET /tournament/roster (for projected lineup)."""
    tournament_players = tournament_doc.get("players", {}) or tournament_doc.get(
        "player_stats", {}
    )
    team_player_ids = team_doc.get("player_ids", [])
    if not team_player_ids:
        return []

    core_players_dict = {
        str(p["_id"]): p
        for p in players_collection.find(
            {"_id": {"$in": team_player_ids}},
            {
                "position_ratings": 1,
                "height": 1,
                "weight": 1,
                "jersey": 1,
                "year": 1,
                "attributes": 1,
                "first_name": 1,
                "last_name": 1,
            },
        )
    }

    team_name = team_doc.get("name", "")
    pids_with_core = [pid for pid in team_player_ids if str(pid) in core_players_dict]
    mode_overrides: Dict[str, Dict[str, Any]] = {}
    for pid in pids_with_core:
        pid_str = str(pid)
        core_player = core_players_dict[pid_str]
        tournament_player_data = tournament_players.get(pid_str, {})
        meta = tournament_player_data.get("meta", {}) if tournament_player_data else {}
        tournament_attributes = (
            tournament_player_data.get("attributes", {}) if tournament_player_data else {}
        )
        core_attributes = core_player.get("attributes", {}) or {}
        merged_attributes = {**core_attributes, **tournament_attributes}
        position_ratings = (
            tournament_player_data.get("position_ratings") if tournament_player_data else None
        )
        if not position_ratings:
            position_ratings = core_player.get("position_ratings", {})
        first = (
            meta.get("first_name")
            or (tournament_player_data.get("first_name") if tournament_player_data else None)
            or core_player.get("first_name", "")
        )
        last = (
            meta.get("last_name")
            or (tournament_player_data.get("last_name") if tournament_player_data else None)
            or core_player.get("last_name", "")
        )
        mode_overrides[pid_str] = {
            "first_name": first,
            "last_name": last,
            "attributes": merged_attributes,
            "position_ratings": position_ratings,
        }

    return build_roster_players(pids_with_core, mode_overrides, core_players_dict, team_name)
