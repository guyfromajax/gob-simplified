import logging
import random
from typing import List, Dict, Union, Optional

from BackEnd.db import players_collection
from BackEnd.models.player import Player
from BackEnd.models.team_manager import TeamManager

# Trait groups per position
POSITION_TRAITS = {
    "PG": ["BH", "PS", "IQ", "OD"],
    "SG": ["SH", "PS", "OD", "AG"],
    "SF": ["AG", "ST", "ID", "OD"],
    "PF": ["ID", "ST", "RB", "IQ"],
    "C":  ["SC", "ID", "ST", "RB"]
}

# Default max fouls allowed by quarter for lineup eligibility (5 fouls = fouled out, never eligible)
# Q4: applied only when time_remaining > 240 (late Q4 / OT have no extra foul limit).
DEFAULT_FOUL_LIMITS_BY_QUARTER = {1: 1, 2: 2, 3: 3, 4: 3}

def get_player_rating(player, traits: List[str]) -> float:
    total = 0
    for trait in traits:
        total += player.attributes.get(trait, 0)
    return total / len(traits)

def is_player_eligible_for_lineup(
    player,
    game_state=None,
    ineligible_player_ids=None,
    *,
    ng_min: Optional[float] = None,
    foul_limits_by_quarter: Optional[Dict[int, int]] = None,
) -> bool:
    """
    Check if a player is eligible for lineup based on energy and foul restrictions.
    Fouled-out (5+ fouls) is derived from player.get_stat("F", "game"), not a persisted list.

    Args:
        player: Player object to check
        game_state: Optional game state dict with quarter, time_remaining (for energy/foul restrictions)
        ineligible_player_ids: Deprecated, ignored. Kept for backward compatibility.
        ng_min: If set, use this as the minimum NG (energy) threshold; 0 or None (when game_state
                is set) means no NG check. If None and game_state is set, use default (0.8 or 0.64).
        foul_limits_by_quarter: If set, dict quarter (1-4) -> max fouls allowed. Used for waterfall
                relaxation. OT always uses only 5-foul check.

    Returns:
        True if player is eligible, False otherwise
    """
    foul_count = player.get_stat("F", "game")
    if foul_count is not None and foul_count >= 5:
        return False

    if not game_state:
        return True

    quarter = game_state.get("quarter", 1)
    time_remaining = game_state.get("time_remaining", 480)

    # Energy (NG) filtering
    if ng_min is not None:
        if ng_min > 0:
            ng = player.attributes.get("NG", 1.0)
            if ng < ng_min:
                return False
    else:
        ng = player.attributes.get("NG", 1.0)
        is_late_q4_or_ot = (quarter == 4 and time_remaining < 240) or quarter > 4
        energy_threshold = 0.64 if is_late_q4_or_ot else 0.8
        if ng < energy_threshold:
            return False

    # Foul filtering by quarter (OT has no extra limit; late Q4 has no per-quarter limit)
    if quarter > 4:
        return True
    if quarter == 4 and time_remaining <= 240:
        return True
    limits = foul_limits_by_quarter if foul_limits_by_quarter is not None else DEFAULT_FOUL_LIMITS_BY_QUARTER
    max_fouls = limits.get(quarter, 99)
    if (foul_count or 0) > max_fouls:
        return False
    return True


def _get_eligible_players(
    team: Union[str, TeamManager],
    game_state=None,
    *,
    ng_min: Optional[float] = None,
    foul_limits_by_quarter: Optional[Dict[int, int]] = None,
    exclude_player_ids: Optional[set] = None,
) -> List[Player]:
    """Return list of players eligible for lineup under given rules. Exclude fouled-out and optional IDs."""
    if isinstance(team, TeamManager):
        players = list(team.get_all_players())
    else:
        players_cursor = players_collection.find({"team": team})
        players = [Player(p) for p in players_cursor]
    exclude = set(exclude_player_ids) if exclude_player_ids else set()
    return [
        p for p in players
        if p.player_id not in exclude
        and is_player_eligible_for_lineup(
            p, game_state, ng_min=ng_min, foul_limits_by_quarter=foul_limits_by_quarter
        )
    ]


def _waterfall_eligibility(game_state=None):
    """
    Yield (ng_min, foul_limits_by_quarter) in waterfall order: first relax NG by 0.2 each step,
    then relax foul limits by 1 per quarter each step. Used to find a legal lineup when default
    rules leave too few eligible players.
    """
    quarter = game_state.get("quarter", 1) if game_state else 1
    time_remaining = game_state.get("time_remaining", 480) if game_state else 480
    is_late_q4_or_ot = (quarter == 4 and time_remaining < 240) or quarter > 4
    default_ng = 0.64 if is_late_q4_or_ot else 0.8

    # NG waterfall: default, then drop by 0.2 until 0 (no NG check)
    ng = default_ng
    while True:
        yield (ng, None)
        if ng <= 0:
            break
        ng = round(ng - 0.2, 2)
        if ng < 0:
            ng = 0

    # Foul waterfall: allow one more foul per quarter each step, cap at 4 (5 = fouled out)
    base = dict(DEFAULT_FOUL_LIMITS_BY_QUARTER)
    for step in range(1, 5):
        relaxed = {q: min(base[q] + step, 4) for q in (1, 2, 3, 4)}
        yield (0, relaxed)


def _team_chemistry_pool_sizes(team_chemistry: float) -> List[int]:
    """
    Pool sizes for fill order 1–5 after role order shuffle (Lineup_Selection_Screen.md).
    """
    try:
        tc = float(team_chemistry)
    except (TypeError, ValueError):
        tc = 12.0
    if tc > 25:
        tc = 25.0
    if tc > 20:
        return [1, 1, 1, 1, 2]
    if tc >= 16:
        return [1, 1, 1, 1, 3]
    if tc >= 11:
        return [1, 1, 1, 2, 3]
    if tc >= 7:
        return [1, 1, 1, 3, 3]
    return [1, 1, 1, 3, 3]


def _player_slot_rating(player: Player, pos: str) -> float:
    """Prefer position_ratings[pos], else attribute-trait average for POSITION_TRAITS[pos]."""
    pr = getattr(player, "position_ratings", None) or {}
    if isinstance(pr, dict) and pos in pr and pr.get(pos) is not None:
        try:
            return float(pr[pos])
        except (TypeError, ValueError):
            pass
    return get_player_rating(player, POSITION_TRAITS[pos])


def build_unified_autoset_lineup_from_eligible(
    eligible_players: List[Player],
    team_chemistry: float,
) -> Dict[str, Player]:
    """
    Canonical autoset selection after eligibility + waterfall: shuffle role order,
    then for each fill slot use team-chemistry pool size N: top N by slot rating,
    random if N > 1 else top player.
    """
    pool_sizes = _team_chemistry_pool_sizes(team_chemistry)
    position_order = ["PG", "SG", "SF", "PF", "C"]
    random.shuffle(position_order)
    assigned_ids = set()
    lineup: Dict[str, Player] = {}
    for fill_idx, pos in enumerate(position_order):
        n = pool_sizes[fill_idx] if fill_idx < len(pool_sizes) else 2
        available = [p for p in eligible_players if p.player_id not in assigned_ids]
        rated = [(p, _player_slot_rating(p, pos)) for p in available]
        rated.sort(key=lambda t: (-t[1], t[0].player_id))
        if not rated:
            raise ValueError(f"No available players left for autoset at fill index {fill_idx}")
        take = min(max(1, n), len(rated))
        candidates = rated[:take]
        chosen = candidates[0][0] if len(candidates) == 1 else random.choice(candidates)[0]
        lineup[pos] = chosen
        assigned_ids.add(chosen.player_id)
    return lineup


def fill_unified_lineup_gaps(
    eligible_players: List[Player],
    team_chemistry: float,
    missing_positions: List[str],
    *,
    existing_assignments: Dict[str, Player],
) -> Dict[str, Player]:
    """
    Fill only ``missing_positions`` using the same pool-size bands as full autoset,
    but with pool_sizes[0..] applied to the shuffled *missing* slots (not all five).
    Used when a partial lineup already has valid players (e.g. foul-out cleared one slot).
    """
    pool_sizes = _team_chemistry_pool_sizes(team_chemistry)
    order = list(missing_positions)
    random.shuffle(order)
    assigned_ids = {p.player_id for p in existing_assignments.values() if p is not None}
    result: Dict[str, Player] = dict(existing_assignments)
    for fill_idx, pos in enumerate(order):
        n = pool_sizes[fill_idx] if fill_idx < len(pool_sizes) else 2
        available = [p for p in eligible_players if p.player_id not in assigned_ids]
        rated = [(p, _player_slot_rating(p, pos)) for p in available]
        rated.sort(key=lambda t: (-t[1], t[0].player_id))
        if not rated:
            raise ValueError(
                f"No eligible players left to fill lineup gap at position {pos} (fill index {fill_idx})"
            )
        take = min(max(1, n), len(rated))
        candidates = rated[:take]
        chosen = candidates[0][0] if len(candidates) == 1 else random.choice(candidates)[0]
        result[pos] = chosen
        assigned_ids.add(chosen.player_id)
    return result


def autoset_lineup_player_ids_from_payload(
    players_payload: List[dict],
    game_state: Optional[dict],
    team_chemistry: float,
) -> Dict[str, str]:
    """
    Server-side autoset for lineup UI: JSON roster rows -> { PG/SG/...: player_id }.
    Uses is_player_eligible_for_lineup + waterfall + unified chemistry pools.
    """
    players: List[Player] = []
    for raw in players_payload:
        data = dict(raw)
        if data.get("_id") is not None and not data.get("player_id"):
            data["player_id"] = str(data["_id"])
        players.append(Player(data))

    gs = game_state if game_state else {"quarter": 1, "time_remaining": 480}
    eligible: Optional[List[Player]] = None
    for ng_min, foul_limits_by_quarter in _waterfall_eligibility(gs):
        eligible = [
            p
            for p in players
            if is_player_eligible_for_lineup(
                p, gs, ng_min=ng_min, foul_limits_by_quarter=foul_limits_by_quarter
            )
        ]
        if len(eligible) >= 5:
            break

    if not eligible or len(eligible) < 5:
        raise ValueError(
            "Fewer than 5 eligible players for autoset after waterfall (check NG/fouls/quarter)."
        )

    lineup_players = build_unified_autoset_lineup_from_eligible(eligible, team_chemistry)
    return {pos: pl.player_id for pos, pl in lineup_players.items()}


def build_lineup_from_mongo(team: Union[str, TeamManager], game_state=None) -> Dict[str, Player]:
    """Build a starting lineup using existing player objects when available.

    Uses a waterfall of relaxed eligibility rules if needed: first relax NG (energy)
    threshold by 0.2 each step, then relax foul limits by quarter, until at least 5
    eligible players are found (or raise if still impossible).
    
    ``team`` may be either a team name or an actual :class:`TeamManager`
    instance.  When a ``TeamManager`` is supplied the players from its roster
    are reused so their in-memory ``stats['game']`` containers are preserved.
    Passing a string falls back to the original behaviour of constructing new
    :class:`Player` objects from the database.
    
    Args:
        team: Team name or TeamManager instance
        game_state: Optional game state dict with quarter, time_remaining
                   Used to filter players based on energy and foul restrictions (fouled-out from F >= 5)
    """
    if isinstance(team, TeamManager):
        team_name = team.name
    else:
        team_name = team

    eligible_players = None
    used_ng_min = None
    used_foul_limits = None
    step = 0
    for ng_min, foul_limits_by_quarter in _waterfall_eligibility(game_state):
        eligible_players = _get_eligible_players(
            team, game_state, ng_min=ng_min, foul_limits_by_quarter=foul_limits_by_quarter
        )
        if len(eligible_players) >= 5:
            used_ng_min = ng_min
            used_foul_limits = foul_limits_by_quarter
            break
        step += 1

    if eligible_players is None or len(eligible_players) < 5:
        total = len(list(team.get_all_players())) if isinstance(team, TeamManager) else players_collection.count_documents({"team": team_name})
        raise ValueError(
            f"Team '{team_name}' has fewer than 5 eligible players even after relaxing NG and foul limits. "
            f"Total roster: {total}, last eligible: {len(eligible_players) if eligible_players else 0}"
        )

    if step > 0:
        logging.info(
            "Lineup waterfall: built lineup for %s with relaxed eligibility (step %s) ng_min=%s foul_limits=%s",
            team_name, step, used_ng_min, used_foul_limits,
        )

    tc = 15.0
    if isinstance(team, TeamManager) and getattr(team, "team_attributes", None):
        try:
            tc = float(team.team_attributes.get("team_chemistry", 15))
        except (TypeError, ValueError):
            tc = 15.0
    return build_unified_autoset_lineup_from_eligible(eligible_players, tc)


def assign_lineup_from_ids(team: TeamManager, lineup_ids: Dict[str, str]) -> Dict[str, Player]:
    """Assign lineup from player IDs, skipping None/empty values.
    
    This function will only assign positions that have valid player IDs.
    Positions with None or missing values will remain unassigned and should
    be filled by _ensure_complete_lineup().
    """
    for pos, pid in lineup_ids.items():
        # Skip None, empty string, or invalid player IDs
        if not pid:
            continue
            
        existing = team.lineup.get(pos)
        if existing and existing.player_id == pid:
            continue

        player = team.get_player_by_id(pid)
        if player and team.lineup.get(pos) is not player:
            team.lineup[pos] = player

    return team.lineup


def autoset_strategy_settings(team: TeamManager):
    """
    Automatically set strategy settings for a computer team using the same
    weighted randomization logic as initial strategy settings.
    
    This function regenerates strategy settings using _init_strategy_settings()
    to allow computer teams to adjust their strategy during timeouts, quarter
    breaks, and foul out instances.
    
    Args:
        team: TeamManager instance (must be a computer team, not user team)
    
    Returns:
        dict: New strategy settings
    """
    # ✅ DEBUG: Log if this is being called on a user team (this would be a bug!)
    if team.is_user_team:
        # logging.warning(f"⚠️ [AUTOSET STRATEGY] ERROR: autoset_strategy_settings() called on USER team: {team.name} (is_user_team={team.is_user_team}). This should NOT happen!")
        # Don't autoset strategy for user teams
        return team.strategy_settings
    
    # ✅ DEBUG: Log when autoset is called on computer teams
    old_inside = team.strategy_settings.get('inside', 'MISSING') if hasattr(team, 'strategy_settings') and team.strategy_settings else 'MISSING'
    # logging.warning(f"🔍 [AUTOSET STRATEGY] Autosetting strategy for COMPUTER team: {team.name}, old inside: {old_inside}")
    
    # Regenerate strategy settings using the same logic as initialization
    new_strategy_settings = team._init_strategy_settings()
    team.strategy_settings = new_strategy_settings
    
    new_inside = new_strategy_settings.get('inside', 'MISSING')
    # logging.warning(f"🔍 [AUTOSET STRATEGY] New inside: {new_inside}")
    
    return new_strategy_settings
