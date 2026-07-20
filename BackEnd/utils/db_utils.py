import logging
from BackEnd.utils.sim_random import sim_rng as random
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
    if tc > 15:
        return [1, 1, 1, 1, 2]
    return [1, 1, 1, 1, 3]


def _player_slot_rating(player: Player, pos: str) -> float:
    """Prefer position_ratings[pos], else attribute-trait average for POSITION_TRAITS[pos]."""
    pr = getattr(player, "position_ratings", None) or {}
    if isinstance(pr, dict) and pos in pr and pr.get(pos) is not None:
        try:
            return float(pr[pos])
        except (TypeError, ValueError):
            pass
    return get_player_rating(player, POSITION_TRAITS[pos])


_LINEUP_POSITIONS = ("PG", "SG", "SF", "PF", "C")

# ── Computer-team situational-override tunables (Computer_Team_GamePlan_System.md) ──
# Conservative strategy (sit on the lead): lead thresholds + the late-Q4 time split.
CONSERVATIVE_LEAD_THRESHOLD = 20            # Q1–Q3, and Q4+ when > CONSERVATIVE_LATE_Q4_SECONDS remain
CONSERVATIVE_LATE_Q4_LEAD_THRESHOLD = 15    # Q4+ when ≤ CONSERVATIVE_LATE_Q4_SECONDS remain
CONSERVATIVE_LATE_Q4_SECONDS = 239
# Blowout lineup (rest starters): margin-of-victory thresholds + Q4 time splits.
BLOWOUT_Q3_MARGIN = 50
BLOWOUT_Q4_MARGIN_EARLY = 35                # Q4, > BLOWOUT_Q4_EARLY_SECONDS remain
BLOWOUT_Q4_MARGIN_MID = 25                  # Q4, > BLOWOUT_Q4_MID_SECONDS remain
BLOWOUT_Q4_MARGIN_LATE = 20                 # Q4, > 0 remain
BLOWOUT_Q4_EARLY_SECONDS = 239
BLOWOUT_Q4_MID_SECONDS = 59


def _player_rt_max(player: Player) -> float:
    """Blowout-selection RT for a player = his HIGHEST slot rating across all five positions."""
    return max(_player_slot_rating(player, pos) for pos in _LINEUP_POSITIONS)


def _team_score_margin(team, game_state) -> Optional[int]:
    """The team's own scoring margin (its score − opponent's) from game_state, or None if it can't
    be resolved. Shared by the conservative-strategy and blowout-lineup situational overrides."""
    if not isinstance(game_state, dict):
        return None
    score_map = game_state.get("score") or {}
    name = getattr(team, "name", None)
    if not isinstance(score_map, dict) or name not in score_map:
        return None
    my_score = int(score_map.get(name, 0) or 0)
    opp_score = None
    for other, val in score_map.items():
        if other != name:
            opp_score = int(val or 0)
            break
    if opp_score is None:
        return None
    return my_score - opp_score


def _blowout_lineup_active(team, game_state) -> bool:
    """True when a comfortably-winning COMPUTER team should rest its starters (garbage time) and
    build the lineup from its LOWEST-RT players. Margin-of-victory thresholds by quarter/time
    (Computer_Team_GamePlan_System.md §Blowout Situation). Never Q1/Q2/OT; re-checked at every
    lineup set, so it reverts automatically once the margin drops back under threshold."""
    if not isinstance(team, TeamManager) or getattr(team, "is_user_team", False):
        return False
    margin = _team_score_margin(team, game_state)
    if margin is None:
        return False
    quarter = int(game_state.get("quarter") or 1)
    if quarter == 3:
        return margin > BLOWOUT_Q3_MARGIN
    if quarter == 4:
        time_remaining = float(game_state.get("time_remaining") or 0)
        if time_remaining > BLOWOUT_Q4_EARLY_SECONDS:
            return margin > BLOWOUT_Q4_MARGIN_EARLY
        if time_remaining > BLOWOUT_Q4_MID_SECONDS:
            return margin > BLOWOUT_Q4_MARGIN_MID
        if time_remaining > 0:
            return margin > BLOWOUT_Q4_MARGIN_LATE
    return False  # Q1, Q2, OT (quarter >= 5) → never


_FILL_ORDER_UNSET = object()


def _shot_weight_fill_order(playbooks_weights) -> Optional[List[str]]:
    """The 5 lineup positions sorted by DESCENDING playbook shot-attempt weight, or ``None``
    when the weights carry no usable signal (not a dict, missing, all-zero, or all-equal) — in
    which case the caller falls back to a random shuffle. Ties among non-equal weights break by
    canonical PG..C order so the result is deterministic.

    ``playbooks_weights`` is the ``["playbooks"]`` map from ``compute_position_shot_weights`` —
    {PG..C: int} summing to 100 (computed from playbook usage only; no playcall center needed).
    """
    if not isinstance(playbooks_weights, dict):
        return None
    try:
        vals = {pos: float(playbooks_weights.get(pos, 0) or 0) for pos in _LINEUP_POSITIONS}
    except (TypeError, ValueError):
        return None
    if not any(vals.values()):
        return None  # missing / all-zero → no signal
    if len(set(vals.values())) == 1:
        return None  # all-equal → no signal
    return sorted(_LINEUP_POSITIONS, key=lambda p: (-vals[p], _LINEUP_POSITIONS.index(p)))


def compute_team_fill_order(team) -> Optional[List[str]]:
    """Shot-weight autoset fill order for a team from its playbook_settings + plays. Returns a
    position list (highest shot-attempt weight first) or ``None`` (→ caller shuffles). Any failure
    (no playbook, compute error, unusable weights) degrades safely to ``None``."""
    playbook_settings = getattr(team, "playbook_settings", None) or {}
    plays = getattr(team, "plays", None) or {}
    if not playbook_settings or not plays:
        return None
    try:
        from BackEnd.utils.playbook_weights_utils import compute_position_shot_weights

        weights = compute_position_shot_weights(playbook_settings, plays)
    except Exception as e:  # never let lineup construction fail on the weights
        logging.warning("Autoset fill-order: shot-weight compute failed (%s); using shuffle", e)
        return None
    return _shot_weight_fill_order((weights or {}).get("playbooks"))


def compute_fill_order_for_franchise_team(franchise_id, team_id) -> Optional[List[str]]:
    """Shot-weight autoset fill order for a franchise team, looked up by (franchise_id, team_id)
    from the persisted franchise_team_data (playbook_settings + plays). Used by the lineup-UI
    autoset endpoint, which has no in-memory TeamManager. Returns a position list or ``None``
    (→ shuffle) when the team, its playbook, or the weights can't be resolved."""
    if not franchise_id or not team_id:
        return None
    try:
        from bson import ObjectId
        from BackEnd.db import franchise_team_data_collection

        def _oid(v):
            try:
                return ObjectId(str(v))
            except Exception:
                return v

        ftd = franchise_team_data_collection.find_one(
            {"franchise_id": _oid(franchise_id), "team_id": _oid(team_id)},
            {"playbook_settings": 1, "plays": 1},
        )
        if not ftd:
            return None
        from BackEnd.utils.playbook_weights_utils import compute_position_shot_weights

        weights = compute_position_shot_weights(
            ftd.get("playbook_settings") or {}, ftd.get("plays") or {}
        )
    except Exception as e:
        logging.warning("Autoset fill-order (franchise team): failed (%s); using shuffle", e)
        return None
    return _shot_weight_fill_order((weights or {}).get("playbooks"))


def _get_or_compute_team_fill_order(team) -> Optional[List[str]]:
    """Lazily compute and cache the shot-weight fill order on a TeamManager. Playbooks are frozen
    during a game, so this is computed on the first lineup build and reused by every in-game
    rebuild (timeouts / quarter breaks / foul-outs). Returns a position list or ``None``."""
    if not isinstance(team, TeamManager):
        return None
    cached = getattr(team, "_position_fill_order", _FILL_ORDER_UNSET)
    if cached is not _FILL_ORDER_UNSET:
        return cached
    order = compute_team_fill_order(team)
    try:
        team._position_fill_order = order
    except Exception:
        pass
    return order


def build_unified_autoset_lineup_from_eligible(
    eligible_players: List[Player],
    team_chemistry: float,
    force_include_ids: Optional[List[str]] = None,
    *,
    prefer_lowest_rt: bool = False,
    position_fill_order: Optional[List[str]] = None,
) -> Dict[str, Player]:
    """
    Canonical autoset selection after eligibility + waterfall: pick the position FILL ORDER,
    then for each fill slot use team-chemistry pool size N: top N by slot rating, random if
    N > 1 else top player. Because the fill is greedy, the position filled first gets first
    pick of the whole eligible pool at that position.

    ``position_fill_order`` (shot-weight autoset): order the fill by descending playbook
    shot-attempt likelihood so the biggest-shooting positions pick their best-fit player first —
    contested talent flows to the spots that shoot most, and the chemistry random pool lands on
    the lowest-shot position (fill slot 5). When ``None`` (or unusable) the order is a random
    shuffle, exactly as before. Ignored under ``prefer_lowest_rt`` (blowout keeps the shuffle).

    ``prefer_lowest_rt`` (blowout / garbage time): seat the team's WORST players instead — rank
    by each player's RT (highest slot rating across positions) and take the LOWEST N. Same
    eligibility waterfall and chemistry pools; only the ranking is inverted. Forced-include
    players (e.g. a locked FT shooter) still play.

    ``force_include_ids`` lists player ids that MUST appear in the returned five
    (e.g. the pending free-throw shooter, who cannot be benched while owed FTs —
    see Timeout_System.md § Designated Free Throw Shooter Lock). Each forced
    player is seated into their best-rated open slot first; the remaining slots
    fill normally.
    """
    pool_sizes = _team_chemistry_pool_sizes(team_chemistry)
    if prefer_lowest_rt or not position_fill_order:
        position_order = ["PG", "SG", "SF", "PF", "C"]
        random.shuffle(position_order)
    else:
        # Shot-weight order: dedupe to the canonical five, appending any missing in PG..C order.
        position_order = []
        for p in position_fill_order:
            if p in _LINEUP_POSITIONS and p not in position_order:
                position_order.append(p)
        for p in _LINEUP_POSITIONS:
            if p not in position_order:
                position_order.append(p)
    assigned_ids = set()
    lineup: Dict[str, Player] = {}

    # Seat forced-include players first (FT shooter safeguard).
    force_set = {str(x) for x in (force_include_ids or [])}
    if force_set:
        for p in eligible_players:
            if str(p.player_id) not in force_set or p.player_id in assigned_ids:
                continue
            open_positions = [pos for pos in position_order if pos not in lineup]
            if not open_positions:
                break
            best_pos = max(open_positions, key=lambda pos: _player_slot_rating(p, pos))
            lineup[best_pos] = p
            assigned_ids.add(p.player_id)

    for fill_idx, pos in enumerate(position_order):
        if pos in lineup:
            continue  # pre-seated by force-include
        n = pool_sizes[fill_idx] if fill_idx < len(pool_sizes) else 2
        available = [p for p in eligible_players if p.player_id not in assigned_ids]
        if prefer_lowest_rt:
            # Blowout: rank by per-player RT (best slot rating across positions), LOWEST first.
            rated = [(p, _player_rt_max(p)) for p in available]
            rated.sort(key=lambda t: (t[1], t[0].player_id))
        else:
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
    position_fill_order: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Server-side autoset for lineup UI: JSON roster rows -> { PG/SG/...: player_id }.
    Uses is_player_eligible_for_lineup + waterfall + unified chemistry pools.

    ``position_fill_order`` (shot-weight autoset): optional pre-computed fill order (highest
    shot-attempt position first) from the team's playbook; ``None`` falls back to a shuffle.
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

    lineup_players = build_unified_autoset_lineup_from_eligible(
        eligible, team_chemistry, position_fill_order=position_fill_order
    )
    return {pos: pl.player_id for pos, pl in lineup_players.items()}


def pending_ft_shooter_id(game_state) -> Optional[str]:
    """Return the designated free-throw shooter's player id when a free throw
    is pending, else None. Used to keep that shooter in the active lineup
    (autoset guard + Set Lineup screen lock). Reads either the live
    ``game_state['shooter']`` object or the persisted ``timeout_shooter_id``.
    """
    if not game_state:
        return None
    is_ft = (
        game_state.get("offensive_state") == "FREE_THROW"
        or game_state.get("timeout_next_play_type") == "FREE_THROW"
    )
    if not is_ft:
        return None
    shooter = game_state.get("shooter")
    sid = getattr(shooter, "player_id", None) or game_state.get("timeout_shooter_id")
    return str(sid) if sid else None


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

    if eligible_players is None:
        eligible_players = []

    if len(eligible_players) < 5:
        allow_fouled_out_reentry = bool(
            game_state
            and (
                game_state.get("allow_fouled_out_lineup_reentry")
                or (
                    isinstance(team, TeamManager)
                    and not getattr(team, "is_user_team", False)
                )
            )
        )
        if allow_fouled_out_reentry and isinstance(team, TeamManager):
            existing_ids = {str(getattr(p, "player_id", "")) for p in eligible_players}
            emergency_ids = {
                str(pid)
                for pid in ((game_state or {}).get("emergency_fouled_out_lineup_player_ids") or [])
            }
            fouled_out_players = [
                p
                for p in team.get_all_players()
                if str(getattr(p, "player_id", "")) not in existing_ids
                and getattr(p, "get_stat", None)
                and (p.get_stat("F", "game") or 0) >= 5
            ]
            previously_readmitted = [
                p
                for p in fouled_out_players
                if str(getattr(p, "player_id", "")) in emergency_ids
            ]
            shortfall = 5 - len(eligible_players)
            emergency_players = previously_readmitted[:shortfall]
            remaining_shortfall = shortfall - len(emergency_players)
            if remaining_shortfall > 0:
                remaining_pool = [
                    p
                    for p in fouled_out_players
                    if str(getattr(p, "player_id", "")) not in {
                        str(getattr(ep, "player_id", "")) for ep in emergency_players
                    }
                ]
                if len(remaining_pool) >= remaining_shortfall:
                    emergency_players.extend(
                        random.sample(remaining_pool, remaining_shortfall)
                    )
            if len(emergency_players) >= shortfall:
                eligible_players.extend(emergency_players)
                game_state["emergency_fouled_out_lineup_player_ids"] = sorted(
                    emergency_ids
                    | {
                        str(getattr(player, "player_id", ""))
                        for player in emergency_players
                        if getattr(player, "player_id", None) is not None
                    }
                )
                logging.warning(
                    "Computer-team lineup exhaustion: Team '%s' randomly re-admitted %s "
                    "fouled-out player(s) to complete the lineup: %s",
                    team_name,
                    shortfall,
                    [getattr(p, "player_id", None) for p in emergency_players],
                )

    if len(eligible_players) < 5:
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

    # FT shooter safeguard: if a free throw is pending and the designated
    # shooter is on THIS team, force-include them so autoset can't bench the
    # player who's about to shoot (Timeout_System.md § Designated FT Shooter Lock).
    force_include = []
    shooter_id = pending_ft_shooter_id(game_state)
    if shooter_id and any(str(p.player_id) == shooter_id for p in eligible_players):
        force_include = [shooter_id]

    # Blowout (garbage time): a comfortably-winning computer team rests its starters and seats
    # its lowest-RT players instead. Re-checked here each lineup set, so it auto-reverts when the
    # margin drops back. See Computer_Team_GamePlan_System.md §Blowout Situation.
    prefer_lowest_rt = _blowout_lineup_active(team, game_state)
    # Shot-weight autoset: seat best-fit players at the highest shot-attempt positions first
    # (computed once from the team's frozen playbook, cached for the game). Ignored in blowout.
    fill_order = _get_or_compute_team_fill_order(team)
    return build_unified_autoset_lineup_from_eligible(
        eligible_players, tc, force_include_ids=force_include,
        prefer_lowest_rt=prefer_lowest_rt, position_fill_order=fill_order,
    )


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


# In-game CONSERVATIVE strategy override (Computer_Team_GamePlan_System.md §In-Game Strategy
# Settings Adjustments). When a computer team is comfortably leading it sits on the lead — these
# eight settings are re-rolled with low-weighted likelihoods. The other settings (inside, attack,
# outside, play_calling, defense) keep their normal computed values. Each entry: (values, weights).
_CONSERVATIVE_STRATEGY_ROLLS = {
    "offense":     ([0, 1, 2], [60, 30, 10]),
    "aggression":  ([0, 1, 2], [60, 30, 10]),
    "hc_trap":     ([0, 1],    [90, 10]),
    "fc_press":    ([0, 1],    [90, 10]),
    "tempo":       ([0, 1],    [90, 10]),
    "alterations": ([0, 1],    [90, 10]),
    "fast_breaks": ([0, 1],    [90, 10]),
    "rebounding":  ([0, 1],    [90, 10]),
}


def _conservative_strategy_active(team: TeamManager, game_state) -> bool:
    """True when the computer team is comfortably leading (sit-on-the-lead conditions):
    Q1–Q3 → lead > 20; Q4+ (incl. OT) → lead > 20 when > 239s remain, else lead > 15.
    Lead is the computer team's own margin (its score − opponent's), read from game_state.
    """
    lead = _team_score_margin(team, game_state)
    if lead is None:
        return False
    quarter = int(game_state.get("quarter") or 1)
    if quarter < 4:
        return lead > CONSERVATIVE_LEAD_THRESHOLD
    time_remaining = float(game_state.get("time_remaining") or 0)
    if time_remaining > CONSERVATIVE_LATE_Q4_SECONDS:
        return lead > CONSERVATIVE_LEAD_THRESHOLD
    return lead > CONSERVATIVE_LATE_Q4_LEAD_THRESHOLD


def _apply_conservative_strategy_override(settings: dict, team: TeamManager, game_state) -> dict:
    """If the team is comfortably leading, override the eight 'sit on the lead' settings with the
    low-weighted conservative rolls; all other settings keep their normal computed values."""
    if not _conservative_strategy_active(team, game_state):
        return settings
    for key, (values, weights) in _CONSERVATIVE_STRATEGY_ROLLS.items():
        settings[key] = random.choices(values, weights=weights, k=1)[0]
    return settings


def autoset_strategy_settings(team: TeamManager, game_state=None):
    """
    Automatically set strategy settings for a computer team from its active five
    (Game_Init_System.md § Computer Team Strategy Logic).

    Regenerates settings during timeouts, quarter breaks, and foul-outs.
    When ``game_state`` is supplied, Q4+ CPU tempo uses score/time logic.

    Args:
        team: TeamManager instance (must be a computer team, not user team)
        game_state: Optional live game state (quarter, time_remaining, score)

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
    
    # Regenerate strategy settings from the team's current five active players
    # (Game_Init_System.md § Computer Team Strategy Logic). Falls back to the
    # legacy random init internally if five players can't be resolved.
    new_strategy_settings = team._compute_strategic_strategy_settings(game_state)
    # Sit-on-the-lead override: when comfortably ahead, dial the eight conservative settings down
    # (other settings keep their computed values). Only fires here — i.e. at the quarter-break /
    # timeout / foul-out instances that call autoset — never at game init (no lead at 0–0).
    new_strategy_settings = _apply_conservative_strategy_override(new_strategy_settings, team, game_state)
    team.strategy_settings = new_strategy_settings
    
    new_inside = new_strategy_settings.get('inside', 'MISSING')
    # logging.warning(f"🔍 [AUTOSET STRATEGY] New inside: {new_inside}")
    
    return new_strategy_settings
