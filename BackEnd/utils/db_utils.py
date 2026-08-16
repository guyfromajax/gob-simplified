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

# Selector objective blend (Lineup selection):
#     score = w * static_rating + (1 - w) * effective_rating
# w = 1.0 is pure static position_ratings (paper talent, fatigue-blind) — the historical
# behaviour and the current default. w = 0.0 is pure effective rating (who is better RIGHT
# NOW), which makes rotation EMERGENT: a starter tires, his effective rating falls below a
# fresh backup's, the next rebuild seats the backup, he recovers on the bench and returns.
# Intermediate w trades responsiveness against "ride your stars" — a top-heavy roster should
# keep a tired star on when the alternative is worse across the whole game, not just now.
# This single weight is the intended home for archetype influence (via starter_bench_gap).
LINEUP_EFFECTIVE_WEIGHT_DEFAULT = 0.25


def _player_effective_slot_rating(player: Player, pos: str) -> float:
    """Position rating recomputed from NG-RESCALED attributes — what the player is worth right
    now, not on paper.

    Only MALLEABLE_ATTRS rescale with energy; IQ/CH and height do not, so an IQ-heavy player
    degrades more slowly than ``rating * NG`` would suggest. That is why this recomputes the
    rating rather than scaling it.

    Cached on the player object per NG value: NG is the only input that moves within a game.
    """
    attrs = getattr(player, "attributes", None) or {}
    try:
        ng = float(attrs.get("NG", 1.0) or 1.0)
    except (TypeError, ValueError):
        ng = 1.0
    ng = max(0.0, min(1.0, ng))
    cache = getattr(player, "_eff_slot_rating_cache", None)
    if cache is None or cache.get("_ng") != ng:
        from BackEnd.constants import MALLEABLE_ATTRS
        from BackEnd.utils.position_ratings import compute_position_ratings

        scaled = {k: (float(v) * ng if k in MALLEABLE_ATTRS else v)
                  for k, v in attrs.items() if isinstance(v, (int, float))}
        try:
            ratings = compute_position_ratings(
                {"attributes": scaled, "height": getattr(player, "height", None)}
            )
        except Exception:
            ratings = {}
        cache = {"_ng": ng, **{p: float(ratings.get(p, 0.0)) for p in _LINEUP_POSITIONS}}
        try:
            player._eff_slot_rating_cache = cache
        except Exception:
            pass
    val = cache.get(pos)
    if val is None or val <= 0:
        # No usable recompute (missing height/attrs) — degrade to the static rating scaled by
        # NG rather than dropping the player out of contention entirely.
        return _player_slot_rating(player, pos) * ng
    return float(val)


def _blended_slot_rating(player: Player, pos: str, effective_weight: float) -> float:
    """score = w * static + (1 - w) * effective. w == 1.0 skips the recompute entirely."""
    w = LINEUP_EFFECTIVE_WEIGHT_DEFAULT if effective_weight is None else float(effective_weight)
    if w >= 1.0:
        return _player_slot_rating(player, pos)
    static = _player_slot_rating(player, pos)
    if w <= 0.0:
        return _player_effective_slot_rating(player, pos)
    return w * static + (1.0 - w) * _player_effective_slot_rating(player, pos)

# ── Computer-team situational-override tunables (Computer_Team_GamePlan_System.md) ──
# Conservative strategy (sit on the lead): lead thresholds + the late-Q4 time split.
CONSERVATIVE_LEAD_THRESHOLD = 20            # Q1–Q3, and Q4+ when > CONSERVATIVE_LATE_Q4_SECONDS remain
CONSERVATIVE_LATE_Q4_LEAD_THRESHOLD = 15    # Q4+ when ≤ CONSERVATIVE_LATE_Q4_SECONDS remain
CONSERVATIVE_LATE_Q4_SECONDS = 239

# ── SELF-REGULATION OVERRIDE (foul trouble + fatigue) ────────────────────────────────────
# A press team backs off when its guards are in foul trouble or gassed, the way a real one
# does. Sits alongside the sit-on-the-lead override on the same seam (strategy_settings_base
# stays untouched, so this reverts the moment the trouble clears).
#
# COMPLEMENTS the per-quarter foul limits rather than duplicating them: those are a
# PERSONNEL lever evaluated only at rebuild boundaries, this is a TACTICS lever. And the
# limits are switched off entirely in the final 4:00 of Q4 and all OT — where 39% of
# foul-outs occur — so there, this is the only brake that exists.
QUARTER_SECONDS = 480.0
REGULATION_SECONDS = QUARTER_SECONDS * 4

# "On pace to foul out": fouls > 5 x fraction of regulation elapsed. End of Q1 -> 2+,
# half -> 3+, end of Q3 -> 4+. SELF_REG_FOUL_MIN keeps a single early foul from counting,
# since any foul in the first minutes is technically ahead of pace.
SELF_REG_FOUL_PACE_MULT = 5.0
SELF_REG_FOUL_MIN = 2
# ABSOLUTE floor under the pace test, and it is load-bearing. By late Q4 the pace line has
# risen to ~4.7, so a player sitting on 4 fouls scores as NOT ahead of pace — exactly where
# the override matters most (59% of FCP rebuilds in Q4 have a 4-foul player on the floor,
# and the per-quarter limits are switched off there). Pace measures PROJECTED foul-out; one
# foul from disqualification is maximal danger whatever the clock says.
#
# APPLIED TO ON-FLOOR PLAYERS ONLY. The two tests answer different questions: the pace test
# is ASSET MANAGEMENT (roster-wide — a player benched at four fouls is exactly the asset
# being protected, and you want him available in the fourth), while the absolute floor is a
# RIGHT-NOW concern. A benched four-foul player is not at imminent risk of anything; that is
# what benching him accomplished.
SELF_REG_FOUL_ABS = 4
SELF_REG_FOUL_FULL_COUNT = 3      # players in trouble for full foul severity
SELF_REG_NG_FLOOR_FRAC = 0.33     # roster fraction below the NG floor where fatigue starts
SELF_REG_NG_FULL_FRAC = 0.66      # ... and where it saturates

# Per-slider damp weights. `aggression` generates fouls within any defensive turn, so foul
# trouble drives it hardest; hc_trap/fc_press generate the pressure turns that burn NG at
# 1.30x the normal rate (apply_energy_decay omit_zeros_for_defense), so fatigue drives those.
SELF_REG_WEIGHTS_FOUL = {"aggression": 1.00, "hc_trap": 0.50, "fc_press": 0.50}
SELF_REG_WEIGHTS_FATIGUE = {"aggression": 0.40, "hc_trap": 0.80, "fc_press": 0.80}
# League baseline means — the damp TARGET and hard floor. Damping is proportional toward
# these, never to a fixed value and never to zero: a press team backs off to roughly
# average, it does not stop being a press team.
SELF_REG_TARGETS = {"aggression": 2.00, "hc_trap": 0.99, "fc_press": 0.99}

# TRAILING LATE — a team down two possessions in the last five minutes should keep pressing
# despite foul trouble. Suppresses self-regulation entirely rather than inverting it;
# raising sliders ABOVE the identity base is new behaviour belonging to the deferred
# mid-game adjustment layer, not to this override.
SELF_REG_DESPERATION_SECONDS = 300
SELF_REG_DESPERATION_MARGIN = 6
# Blowout lineup (rest starters): margin-of-victory thresholds + Q4 time splits.
BLOWOUT_Q3_MARGIN = 40                      # was 50: out of line with the Q4 ladder below
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
    """True when a comfortably-winning team should rest its starters (garbage time) and build the
    lineup from its LOWEST-RT players. Margin-of-victory thresholds by quarter/time
    (Computer_Team_GamePlan_System.md §Blowout Situation). Never Q1/Q2/OT; re-checked at every
    lineup set, so it reverts automatically once the margin drops back under threshold.

    APPLIES TO USER TEAMS IN FULL SIM ONLY (PR0.5). The user team used to be excluded
    unconditionally, which meant the blowout systems were never applied to the team doing the
    blowing out. Matched pair on the prod season: Rushmore (user) and Couer d'Alene (CPU), talent
    563.8 vs 564, both 26-0, same vision pair — level through halftime (18.2 vs 17.6) and then
    +15.1 vs +2.3 in the second half, diverging exactly as the lead crosses 20.

    Turn-by-turn is still excluded: in Play Quarter the user owns substitutions, and overriding
    them there would take away a decision they are actively making (governor spec A2). The flag
    is set at main.py:902 and cleared at :951/:969.
    """
    if not isinstance(team, TeamManager):
        return False
    if getattr(team, "is_user_team", False) and not (game_state or {}).get("_is_full_simulation"):
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


def solve_best_assignment(
    players: List[Player],
    positions: List[str],
    *,
    required_ids: Optional[set] = None,
    preference_fn=None,
    effective_weight: float = None,
    tie_break: str = "shuffle",
) -> Dict[str, Player]:
    """EXACT max-weight assignment of ``positions`` over ``players``. Returns {pos: Player}.

    Objective = sum of ``_blended_slot_rating(player, pos, effective_weight)`` across the
    filled slots, plus an optional ``preference_fn`` bonus. See
    ``LINEUP_EFFECTIVE_WEIGHT_DEFAULT`` for what the weight means. Solved by DP over position bitmasks: 2^len(positions)
    states x len(players), so microseconds at five slots and a twelve-man pool. This replaces
    a greedy position-by-position fill, which could not find the best five — measured at a mean
    17.5-point shortfall, optimal in only 19% of rebuilds, with a bench player outrating the
    starter at his own slot in 47% of them.

    TIE-BREAKING is random and free: ``players`` is shuffled up front and the DP improves on
    strict ``>``, so among equally-optimal assignments the winner is decided by shuffle order.
    Variation at zero rating cost — unlike the old random fill order, which bought variation by
    giving up rating.

    ``tie_break`` selects HOW that order is produced, and nothing else:

    * ``"shuffle"`` (default, the GAME path) — ``sim_rng.shuffle``. Unchanged, including the
      draw itself, so sim draw counts and repro are untouched.
    * ``"stable"`` (the DISPLAY path) — sort by ``player_id``. Draws NOTHING. Display surfaces
      run on page loads, OUTSIDE the sim; drawing from ``sim_rng`` there would desync the
      stream (see the per-subsystem RNG rule), and a random tie-break would also make the
      projected five flip between page loads for no reason. Equally-optimal assignments have
      identical total rating, so this changes WHICH five is shown on an exact tie, never how
      good it is.

    ``required_ids`` players MUST be seated (the locked FT shooter). Enforced as a hard
    constraint inside the optimisation — the best five CONTAINING them — not by pre-seating
    them and greedily filling around, which is what the old code did.

    ``preference_fn(player, position) -> float`` is the DELIBERATE-DEVIATION HOOK. Not used
    yet. See ``build_unified_autoset_lineup_from_eligible`` for what belongs here.
    """
    n_pos = len(positions)
    if n_pos == 0:
        return {}
    pool = list(players)
    if tie_break == "stable":
        pool.sort(key=lambda p: str(getattr(p, "player_id", "")))   # deterministic, zero draws
    else:
        random.shuffle(pool)                  # random tie-break among equal optima
    required_ids = {str(x) for x in (required_ids or set())}

    def score(p, pos):
        v = _blended_slot_rating(p, pos, effective_weight)
        if preference_fn is not None:
            try:
                v += float(preference_fn(p, pos) or 0.0)
            except Exception:
                pass
        return v

    full = (1 << n_pos) - 1
    NEG = float("-inf")
    n_req = len(required_ids)
    # LAYERED dp: layers[L][mask][k] = best score using the first L players, having filled
    # `mask` and seated k of the required ones. Layering is what makes reconstruction safe —
    # a flat parent table can walk into a predecessor state that a LATER player produced, which
    # silently seats the same player twice.
    layers = [[[NEG] * (n_req + 1) for _ in range(full + 1)]]
    layers[0][0][0] = 0.0
    for p in pool:
        is_req = 1 if str(getattr(p, "player_id", "")) in required_ids else 0
        prev = layers[-1]
        cur = [row[:] for row in prev]          # option: skip this player
        for mask in range(full + 1):
            for k in range(n_req + 1):
                if prev[mask][k] == NEG:
                    continue
                nk = k + is_req
                if nk > n_req:
                    continue
                for i in range(n_pos):
                    if mask & (1 << i):
                        continue
                    nm = mask | (1 << i)
                    v = prev[mask][k] + score(p, positions[i])
                    if v > cur[nm][nk]:
                        cur[nm][nk] = v
        layers.append(cur)

    final = layers[-1]
    # Prefer seating every required player; fall back only if the pool cannot accommodate them.
    want = None
    for w in range(n_req, -1, -1):
        if final[full][w] != NEG:
            want = w
            break
    if want is None:
        raise ValueError("No feasible lineup assignment from the eligible pool")

    out: Dict[str, Player] = {}
    mask, k = full, want
    for L in range(len(pool), 0, -1):
        if mask == 0:
            break
        p = pool[L - 1]
        if layers[L][mask][k] == layers[L - 1][mask][k]:
            continue                            # player L-1 was skipped
        is_req = 1 if str(getattr(p, "player_id", "")) in required_ids else 0
        pk = k - is_req
        placed = False
        for i in range(n_pos):
            if not (mask & (1 << i)):
                continue
            pm = mask ^ (1 << i)
            if pk < 0 or layers[L - 1][pm][pk] == NEG:
                continue
            if abs(layers[L - 1][pm][pk] + score(p, positions[i]) - layers[L][mask][k]) < 1e-9:
                out[positions[i]] = p
                mask, k = pm, pk
                placed = True
                break
        if not placed:                          # value came from the skip edge after all
            continue
    if len(out) != n_pos:
        raise ValueError("No feasible lineup assignment from the eligible pool")
    return out


def build_unified_autoset_lineup_from_eligible(
    eligible_players: List[Player],
    team_chemistry: float,
    force_include_ids: Optional[List[str]] = None,
    *,
    prefer_lowest_rt: bool = False,
    position_fill_order: Optional[List[str]] = None,
    preference_fn=None,
    effective_weight: float = None,
) -> Dict[str, Player]:
    """
    Canonical autoset selection after eligibility + waterfall. Seats the EXACT best five by
    max-weight assignment over the eligible pool (see ``solve_best_assignment``).

    Eligibility (NG threshold, foul limits) and the waterfall relaxation happen UPSTREAM in
    ``build_lineup_from_mongo`` and are unchanged — this optimises over the eligible pool it is
    handed, never the whole roster.

    ``prefer_lowest_rt`` (blowout / garbage time) INVERTS THE SELECTION, not the seating: take
    the five LOWEST-RT eligible players (RT = best slot rating across positions, as before),
    then seat those five optimally. Resting the starters is the intent; fielding them in
    nonsense positions was not. Forced-include players are retained.

    ``team_chemistry`` is ACCEPTED AND IGNORED. It used to size a random candidate pool for the
    last fill slot; measured, that cost a mean 4.39 rating points per rebuild and bought nothing
    — the variation it produced was indistinguishable from noise. Tie-breaking now supplies
    variation at zero cost. The parameter stays because callers pass it positionally.

    ``position_fill_order`` is ACCEPTED AND UNUSED — fill order cannot affect an exact
    assignment. It is NOT dead code: it is the DEVIATION HOOK'S FIRST INTENDED CONSUMER.
    Shot-weight ordering optimises a genuinely different objective (seat scorers where the
    playbook shoots most), which can CONFLICT with max-sum-of-position-ratings — a team may
    rationally field a slightly lower-rated five to get its shooters into high-attempt spots.
    That tension is exactly what ``preference_fn`` exists to express, and where this parameter
    should move when the identity work lands.

    ``preference_fn(player, position) -> float`` — deliberate-deviation hook, currently always
    ``None``. The principle: optimal is the BASELINE, and any deviation must MEAN something
    (a vision preference, resting a star in a decided game, developing a freshman). The old
    behaviour deviated via ``random.shuffle``, which meant nothing.

    ``force_include_ids`` players must appear in the five (the pending FT shooter — see
    Timeout_System.md § Designated Free Throw Shooter Lock). Enforced inside the solve.
    """
    positions = list(_LINEUP_POSITIONS)
    force_set = {str(x) for x in (force_include_ids or [])}

    if prefer_lowest_rt:
        forced = [p for p in eligible_players if str(p.player_id) in force_set]
        rest = [p for p in eligible_players if str(p.player_id) not in force_set]
        rest.sort(key=lambda p: (_player_rt_max(p), str(p.player_id)))
        chosen = forced + rest[: max(0, len(positions) - len(forced))]
        if len(chosen) < len(positions):
            chosen = (chosen + [p for p in eligible_players if p not in chosen])[: len(positions)]
        return solve_best_assignment(chosen, positions, preference_fn=preference_fn,
                                     effective_weight=effective_weight)

    return solve_best_assignment(
        eligible_players, positions, required_ids=force_set, preference_fn=preference_fn,
        effective_weight=effective_weight,
    )


def fill_unified_lineup_gaps(
    eligible_players: List[Player],
    team_chemistry: float,
    missing_positions: List[str],
    *,
    existing_assignments: Dict[str, Player],
    preference_fn=None,
    effective_weight: float = None,
    prefer_lowest_rt: bool = False,
) -> Dict[str, Player]:
    """
    Fill only ``missing_positions`` with the EXACT best available players, holding the already-
    seated slots fixed. Used when a partial lineup survives (e.g. a foul-out cleared one slot).

    This is the FOUL-OUT PATH, and it is the most-watched selection decision in a game: a
    starter fouls out and the user watches who walks on. It previously used the same greedy
    fill + chemistry random pool as full autoset, so the worst selector was running at the most
    visible moment. It now shares ``solve_best_assignment`` with full autoset — over the missing
    slots only, so the surviving four are never disturbed.

    ``prefer_lowest_rt`` (blowout / garbage time) mirrors
    ``build_unified_autoset_lineup_from_eligible``: narrow the candidate pool to the LOWEST-RT
    available players, then seat those optimally. Without it this function had no notion of a
    blowout at all, so a foul-out in garbage time seated the BEST available player — undoing,
    one slot at a time, the exact thing the blowout lineup exists to do.

    Note where that actually bit, because it is narrower than it looks: the primary full-sim
    foul-out path never reaches here (game_manager.py:692 skips it and defers to
    ``_rebuild_both_lineups_for_full_sim_break``, which is blowout-aware). The live exposures
    were turn-by-turn CPU foul-outs and the ``_check_lineups_for_foul_out`` safety-net sweep —
    the only call site in the codebase that lets ``perform_removal`` default to True, and not
    gated on sim mode. Self-correcting at the next lineup rebuild either way, so the old
    exposure was one starter for part of one stint, not a whole garbage-time lineup.

    ``team_chemistry`` is accepted and ignored (see
    ``build_unified_autoset_lineup_from_eligible``).
    """
    order = [p for p in missing_positions if p]
    if not order:
        return dict(existing_assignments)
    assigned_ids = {str(p.player_id) for p in existing_assignments.values() if p is not None}
    available = [p for p in eligible_players if str(p.player_id) not in assigned_ids]
    if len(available) < len(order):
        raise ValueError(
            f"No eligible players left to fill lineup gaps {order} "
            f"(available={len(available)}, needed={len(order)})"
        )
    if prefer_lowest_rt:
        # Same shape as the full-autoset inversion: pick WHO plays by lowest RT, then seat
        # them optimally. Resting the starters is the intent; fielding the scrubs in nonsense
        # positions was not. Tie-break on player_id so the choice is deterministic.
        available = sorted(available, key=lambda p: (_player_rt_max(p), str(p.player_id)))[: len(order)]
    result: Dict[str, Player] = dict(existing_assignments)
    result.update(solve_best_assignment(available, order, preference_fn=preference_fn,
                                        effective_weight=effective_weight))
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


# Tip-off game state: what ``build_lineup_from_mongo`` is handed when a game starts. Q1 with a
# full clock is not late-Q4/OT, so the waterfall opens at the 0.80 NG gate and no per-quarter
# foul limit binds (nobody has fouled yet).
PREGAME_STATE = {"quarter": 1, "time_remaining": 480}


def projected_starting_five_from_payload(players_payload: List[dict]) -> Dict[str, str]:
    """The five that AUTOSET WOULD FIELD AT TIP -> { PG/SG/...: player_id }.

    This is the display counterpart of ``autoset_lineup_player_ids_from_payload``, and the
    single source of truth for every "projected starting five" surface (FCC Scouting Report
    tab, team roster pages, training report, practice-squad team, tournament). It exists so
    those surfaces stop disagreeing with the floor.

    PARITY IS STRUCTURAL, not a reimplementation. It runs the same eligibility waterfall, the
    same ``solve_best_assignment`` DP and the same ``LINEUP_EFFECTIVE_WEIGHT_DEFAULT``
    objective as the game, over the same full-roster pool. The previous display selector was a
    separate GREEDY fill on raw ``position_ratings`` — the selector the sim measured and
    rejected (optimal in 19% of rebuilds, mean 17.5-point shortfall).

    ENERGY-AWARE ON PURPOSE. The objective is 25% paper talent / 75% NG-rescaled effective
    rating, and NG persists to FPD and is written by the training paths — so a player the
    week's training left tired legitimately drops out of the projection, because he is also
    worth less at tip. Showing paper talent here would diverge from the floor for exactly the
    players the user most needs to see.

    TWO DIFFERENCES REMAIN, both correct:
      * exact ties resolve deterministically here and randomly in the sim (see
        ``solve_best_assignment``'s ``tie_break``) — same total rating either way;
      * a user who sets a lineup manually overrides autoset entirely, so this is what autoset
        WOULD have picked. CPU teams never override, so for them it is exact.

    Blowout inversion, the FT-shooter force-include and foul-out gap fills are all mid-game
    mechanics and cannot apply at tip, so none of them are modelled here.

    Degrades to a PARTIAL five (fewer than five slots) on a short or fully-ineligible roster
    rather than raising — a display surface must still render.
    """
    players: List[Player] = []
    for raw in players_payload or []:
        data = dict(raw)
        # ``_id`` FIRST, matching how the display rows key themselves
        # (``scouting_utils._player_sort_key``). A row carrying both keys under different
        # values would otherwise seat an id the caller cannot map back, silently dropping a
        # slot from the rendered five.
        pid = data.get("_id") if data.get("_id") is not None else data.get("player_id")
        if pid is not None:
            pid_s = str(pid)
            data["player_id"] = pid_s
            # ``Player`` only reads ``_id`` (else uuid4). Without this, payloads that
            # carry ``player_id`` only (e.g. training report) seat unmappable ids and
            # the display five renders empty.
            data["_id"] = pid_s
        players.append(Player(data))

    if not players:
        return {}

    eligible: List[Player] = []
    for ng_min, foul_limits_by_quarter in _waterfall_eligibility(PREGAME_STATE):
        eligible = [
            p
            for p in players
            if is_player_eligible_for_lineup(
                p, PREGAME_STATE, ng_min=ng_min, foul_limits_by_quarter=foul_limits_by_quarter
            )
        ]
        if len(eligible) >= 5:
            break

    # Short roster: the waterfall cannot manufacture bodies. Seat what exists over as many
    # slots as it can fill, in the canonical position order.
    if not eligible:
        eligible = players
    positions = list(_LINEUP_POSITIONS)[: min(5, len(eligible))]
    if not positions:
        return {}

    seated = solve_best_assignment(eligible, positions, tie_break="stable")
    return {pos: pl.player_id for pos, pl in seated.items()}


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


def _self_reg_elapsed_fraction(game_state) -> float:
    """Fraction of REGULATION elapsed. OT counts as fully elapsed (1.0), so the
    on-pace-to-foul-out test stays at its strictest there rather than resetting."""
    quarter = int(game_state.get("quarter") or 1)
    if quarter > 4:
        return 1.0
    time_remaining = float(game_state.get("time_remaining") or 0)
    elapsed = (quarter - 1) * QUARTER_SECONDS + (QUARTER_SECONDS - time_remaining)
    return max(0.0, min(1.0, elapsed / REGULATION_SECONDS))


def _self_reg_desperation_active(team, game_state) -> bool:
    """True when the team is trailing by SELF_REG_DESPERATION_MARGIN+ in the final
    SELF_REG_DESPERATION_SECONDS of Q4, or at any point in OT. Keep pressing."""
    quarter = int(game_state.get("quarter") or 1)
    if quarter < 4:
        return False
    if quarter == 4:
        time_remaining = float(game_state.get("time_remaining") or 0)
        if time_remaining > SELF_REG_DESPERATION_SECONDS:
            return False
    margin = _team_score_margin(team, game_state)
    if margin is None:
        return False
    return margin <= -SELF_REG_DESPERATION_MARGIN


def _self_reg_severities(team, game_state):
    """(foul_severity, fatigue_severity), each 0.0-1.0."""
    try:
        players = list(team.get_all_players())
    except Exception:
        return 0.0, 0.0
    if not players:
        return 0.0, 0.0

    elapsed = _self_reg_elapsed_fraction(game_state)
    pace_line = SELF_REG_FOUL_PACE_MULT * elapsed
    lineup = getattr(team, "lineup", None) or {}
    on_floor_ids = {
        str(getattr(p, "player_id", "")) for p in lineup.values() if p is not None
    }
    trouble = 0
    for p in players:
        fouls = p.get_stat("F", "game") or 0
        if fouls >= 5:
            continue
        on_floor = str(getattr(p, "player_id", "")) in on_floor_ids
        ahead_of_pace = fouls >= SELF_REG_FOUL_MIN and fouls > pace_line
        one_from_out = on_floor and fouls >= SELF_REG_FOUL_ABS
        if ahead_of_pace or one_from_out:
            trouble += 1
    sev_foul = min(1.0, trouble / float(SELF_REG_FOUL_FULL_COUNT))

    # Same NG floor the lineup gate uses, so both agree about what "tired" means.
    quarter = int(game_state.get("quarter") or 1)
    time_remaining = float(game_state.get("time_remaining") or QUARTER_SECONDS)
    is_late_q4_or_ot = (quarter == 4 and time_remaining < 240) or quarter > 4
    ng_floor = 0.64 if is_late_q4_or_ot else 0.8
    blocked = sum(1 for p in players
                  if float(p.attributes.get("NG", 1.0) or 1.0) < ng_floor)
    frac = blocked / float(len(players))
    span = max(1e-9, SELF_REG_NG_FULL_FRAC - SELF_REG_NG_FLOOR_FRAC)
    sev_fat = max(0.0, min(1.0, (frac - SELF_REG_NG_FLOOR_FRAC) / span))
    return sev_foul, sev_fat


def _apply_self_regulation_override(settings: dict, team, game_state) -> dict:
    """Damp aggression / hc_trap / fc_press toward the league baseline in proportion to how
    much foul trouble and fatigue the team is carrying.

    DETERMINISTIC — no RNG draw, deliberately unlike the conservative override. This is a
    continuous response to a continuous state; a draw would make behaviour jitter between
    stoppages for no reason, and it keeps the sim's draw count unchanged.

    Sliders are only ever lowered, and never below SELF_REG_TARGETS."""
    if not isinstance(game_state, dict) or not isinstance(team, TeamManager):
        return settings
    if getattr(team, "is_user_team", False):
        return settings
    if _self_reg_desperation_active(team, game_state):
        return settings

    sev_foul, sev_fat = _self_reg_severities(team, game_state)
    if sev_foul <= 0.0 and sev_fat <= 0.0:
        return settings

    for slider, target in SELF_REG_TARGETS.items():
        current = settings.get(slider)
        if current is None:
            continue
        try:
            current = float(current)
        except (TypeError, ValueError):
            continue
        if current <= target:
            continue
        move = max(sev_foul * SELF_REG_WEIGHTS_FOUL.get(slider, 0.0),
                   sev_fat * SELF_REG_WEIGHTS_FATIGUE.get(slider, 0.0))
        if move <= 0.0:
            continue
        damped = current - move * (current - target)
        settings[slider] = max(int(round(target)), min(4, int(round(damped))))
    return settings


def autoset_strategy_settings(team: TeamManager, game_state=None):
    """
    Ensure a computer team has strategy settings, and apply the situational
    sit-on-the-lead override (Game_Init_System.md § Computer Team Strategy Logic).

    IDEMPOTENT ON THE DERIVATION. A CPU team's game plan is derived ONCE — normally at
    ``TeamManager.__init__`` from the projected starting five — and then persists as
    ``team.strategy_settings_base`` for the rest of the game. This function no longer
    re-derives it at every lineup rebuild.

    WHY: it used to recompute from the CURRENT five at every quarter break / timeout /
    foul-out, so a team's identity shifted several times a game as players tired, and no
    per-team slider configuration was reachable at all — anything a caller set was
    overwritten by the next rebuild. Measured: 52–84% of team-games had every slider
    changed between tip and final buzzer.

    WHAT STILL HAPPENS EVERY CALL: the sit-on-the-lead override. It is re-evaluated
    against the live ``game_state`` and applied on top of the persisted base, so a
    comfortable lead still dials the eight conservative settings down — and, because the
    base is kept separate, the team reverts to its real game plan if the lead evaporates.

    Args:
        team: TeamManager instance (must be a computer team, not user team)
        game_state: Optional live game state (quarter, time_remaining, score)

    Returns:
        dict: The team's effective strategy settings
    """
    # USER TEAMS: full sim only (PR0.5). Outside full sim the user owns their playcalls and this
    # must not touch them (governor spec A2). Inside full sim the sit-on-the-lead damping applies
    # to them exactly as it does to a CPU team — see _blowout_lineup_active for the evidence.
    #
    # SAFE BY CONSTRUCTION, not by avoidance: `strategy_settings_base` below holds the pristine
    # plan and `strategy_settings` is a per-call damped VIEW recomputed on every lineup rebuild.
    # The user's saved gameplan lives in the FTD document and is never written from here (the only
    # FTD write of strategy_settings is gameplan_routes.py:1186, which writes DEFAULTS when the
    # field is missing). The games-doc snapshot now persists `strategy_settings_base` — see
    # api.py — so both of its consumers (the Gameplan UI at gameplan_routes.py:1625 and
    # timeout-resume via extract_team_settings) read the PLAN rather than a damped view.
    if team.is_user_team and not (game_state or {}).get("_is_full_simulation"):
        return team.strategy_settings

    # Establish the persistent base ONCE. Callers reach here after init, so the settings
    # already present (init-derived, or supplied by a saved game / gameplan) ARE the game
    # plan — adopt them rather than recomputing. The _compute_ fallback covers the case
    # where a caller somehow arrives with no settings at all, preserving the original
    # "ensure settings exist" guarantee these call sites were providing.
    base = getattr(team, "strategy_settings_base", None)
    if not base:
        current = getattr(team, "strategy_settings", None)
        if current and isinstance(current, dict) and len(current) > 0:
            base = dict(current)
        else:
            base = team._compute_strategic_strategy_settings(game_state)
        team.strategy_settings_base = base

    # Sit-on-the-lead override: when comfortably ahead, dial the eight conservative settings
    # down (all others keep their base values). Applied to a COPY of the base every call, so
    # it both fires while the lead holds and reverts cleanly once it doesn't.
    # CONSERVATIVE WINS. Both overrides target aggression / hc_trap / fc_press and the
    # conservative rolls damp strictly harder, so stacking them would double-count.
    if _conservative_strategy_active(team, game_state):
        team.strategy_settings = _apply_conservative_strategy_override(
            dict(base), team, game_state
        )
    else:
        team.strategy_settings = _apply_self_regulation_override(
            dict(base), team, game_state
        )
    return team.strategy_settings
