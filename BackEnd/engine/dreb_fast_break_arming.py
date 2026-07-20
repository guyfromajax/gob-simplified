"""
Shared DREB → Fast Break arming (HCO / FT / putback / FB-miss).

Mirrors the HCO shot-attempt contract: one ``fast_breaks`` roll + play key on the
miss that produces DREB, stash ``pending_dreb_fb_play_key`` / ``last_release_player``,
and stamp Covert Release getback/release fields on the miss turn when needed.

See Fast_Break_System.md § Fast break initiation + DREB sources beyond HCO.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from BackEnd.constants.fast_break_play_types import (
    COVERT_RELEASE,
    RIM_RUNNER,
    TRIANGLE,
    play_key_for_fast_break_entry,
)
from BackEnd.utils.shared import fast_break_probability_from_slider

# FT Covert: v1 one getback; geo-ranked so a future setting can raise this to 2.
FT_DREB_FB_GETBACK_COUNT = 1
# FB-miss Covert: up to two getbacks that already beat the outlet toward the new rim.
FB_MISS_DREB_FB_GETBACK_COUNT = 2

CENTER_COURT = {"x": 50.0, "y": 25.0}

SOURCE_HCO = "hco"
SOURCE_FT = "ft"
SOURCE_OREB_PUTBACK = "oreb_putback"
SOURCE_FB_MISS = "fb_miss"


def _pid(player: Any) -> Optional[str]:
    if player is None:
        return None
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


def _coords_of(player: Any) -> Dict[str, float]:
    c = getattr(player, "coords", None) or {}
    try:
        return {"x": float(c.get("x", 50)), "y": float(c.get("y", 25))}
    except (TypeError, ValueError):
        return {"x": 50.0, "y": 25.0}


def _dist(a: Dict[str, float], b: Dict[str, float]) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def _lineup_players(lineup: Optional[Dict[str, Any]]) -> List[Any]:
    out: List[Any] = []
    for p in (lineup or {}).values():
        if p is not None:
            out.append(p)
    return out


def _rank_nearest_center(
    players: Sequence[Any],
    *,
    exclude_ids: Optional[set] = None,
) -> List[Any]:
    exclude = {str(x) for x in (exclude_ids or set()) if x is not None}
    scored: List[Tuple[float, Any]] = []
    for p in players:
        pid = _pid(p)
        if pid is None or pid in exclude:
            continue
        scored.append((_dist(_coords_of(p), CENTER_COURT), p))
    scored.sort(key=lambda t: t[0])
    return [p for _, p in scored]


def _clear_pending_fb(game_state: Dict[str, Any]) -> None:
    game_state.pop("_shot_dreb_fb_play_key", None)
    game_state.pop("pending_dreb_fb_play_key", None)
    game_state["last_release_player"] = None


def _stamp_empty_cr_fields(result: Optional[Dict[str, Any]]) -> None:
    if not isinstance(result, dict):
        return
    result["offense_getback"] = []
    result["defense_release"] = []
    result["offense_getback_coords"] = {}
    result["defense_release_coords"] = {}


def _stamp_cr_fields(
    result: Optional[Dict[str, Any]],
    *,
    release_player: Optional[Any],
    getback_players: Sequence[Any],
) -> None:
    if not isinstance(result, dict):
        return
    release_ids: List[str] = []
    release_coords: Dict[str, Dict[str, float]] = {}
    if release_player is not None:
        rid = _pid(release_player)
        if rid:
            release_ids.append(rid)
            release_coords[rid] = _coords_of(release_player)

    getback_ids: List[str] = []
    getback_coords: Dict[str, Dict[str, float]] = {}
    for p in getback_players:
        gid = _pid(p)
        if not gid:
            continue
        getback_ids.append(gid)
        getback_coords[gid] = _coords_of(p)

    result["defense_release"] = release_ids
    result["defense_release_coords"] = release_coords
    result["offense_getback"] = getback_ids
    result["offense_getback_coords"] = getback_coords


def _find_prior_hco_cr_fields(game: Any, max_turns: int = 12) -> Optional[Dict[str, Any]]:
    """Original HCO miss (or any prior turn) that already stamped Covert release/getback."""
    turns = getattr(game, "turns", None) or []
    for turn in reversed(turns[-max_turns:]):
        if not isinstance(turn, dict):
            continue
        if turn.get("result_type") not in ("MISS", "BLOCK", "MAKE"):
            continue
        # Prefer turns that actually authored CR lists (HCO shot path).
        if turn.get("defense_release") or turn.get("offense_getback"):
            return turn
        if turn.get("defense_release_coords") or turn.get("offense_getback_coords"):
            return turn
    return None


def _player_from_id(game: Any, player_id: Optional[str]) -> Optional[Any]:
    if player_id is None:
        return None
    pid = str(player_id)
    for team in (game.home_team, game.away_team):
        p = team.get_player_by_id(pid)
        if p is not None:
            return p
        for cand in (team.lineup or {}).values():
            if cand is not None and str(getattr(cand, "player_id", None)) == pid:
                return cand
    return None


def prepare_covert_oreb_carry(
    game: Any,
    result: Optional[Dict[str, Any]],
) -> Optional[Any]:
    """
    Carry original HCO miss release/getback IDs + coords onto the putback miss turn.
    Returns the release player (or None if Covert cannot be armed from carry).
    """
    prior = _find_prior_hco_cr_fields(game)
    if prior is None:
        _stamp_empty_cr_fields(result)
        return None

    release_ids = list(prior.get("defense_release") or [])
    getback_ids = list(prior.get("offense_getback") or [])
    release_coords = dict(prior.get("defense_release_coords") or {})
    getback_coords = dict(prior.get("offense_getback_coords") or {})

    if isinstance(result, dict):
        result["defense_release"] = release_ids
        result["offense_getback"] = getback_ids
        result["defense_release_coords"] = release_coords
        result["offense_getback_coords"] = getback_coords

    if not release_ids:
        return None
    return _player_from_id(game, release_ids[0])


def prepare_covert_ft_geo(
    game: Any,
    *,
    ft_offense_lineup: Dict[str, Any],
    ft_defense_lineup: Dict[str, Any],
    result: Optional[Dict[str, Any]],
    getback_count: int = FT_DREB_FB_GETBACK_COUNT,
) -> Optional[Any]:
    """
    FT lane: release = FT-defense nearest center; getbacks = FT-offense nearest center.
    Uses live coords (post FT lane animation).
    """
    release_ranked = _rank_nearest_center(_lineup_players(ft_defense_lineup))
    getback_ranked = _rank_nearest_center(_lineup_players(ft_offense_lineup))
    release_player = release_ranked[0] if release_ranked else None
    getbacks = getback_ranked[: max(0, int(getback_count))]
    _stamp_cr_fields(result, release_player=release_player, getback_players=getbacks)
    return release_player


def prepare_covert_fb_miss_geo(
    game: Any,
    *,
    shooting_lineup: Dict[str, Any],
    rebounding_lineup: Dict[str, Any],
    rebounder: Any,
    is_away_shooting: bool,
    result: Optional[Dict[str, Any]],
    getback_count: int = FB_MISS_DREB_FB_GETBACK_COUNT,
) -> Tuple[Optional[Any], bool]:
    """
    FB miss Covert:
      - outlet/release = rebounding-team player nearest center
      - if that player is the rebounder → skip outlet (dribble), same as RR
      - getbacks = up to N from the team that just missed who are closer to the
        **new** FB attack basket than the outlet receiver; else zero getbacks

    Returns ``(release_player, skip_outlet_pass)``.
    """
    # After DREB the rebounding team attacks the opposite rim from the miss.
    # Miss: home shoots → rim x=91; new FB offense (was defense) attacks x=9.
    new_fb_rim = {"x": 9.0, "y": 25.0} if not is_away_shooting else {"x": 91.0, "y": 25.0}

    outlet_ranked = _rank_nearest_center(_lineup_players(rebounding_lineup))
    release_player = outlet_ranked[0] if outlet_ranked else None
    skip_outlet = bool(
        release_player is not None
        and rebounder is not None
        and _pid(release_player) == _pid(rebounder)
    )

    getbacks: List[Any] = []
    if release_player is not None:
        outlet_xy = _coords_of(release_player)
        outlet_to_rim = _dist(outlet_xy, new_fb_rim)
        candidates: List[Tuple[float, Any]] = []
        for p in _lineup_players(shooting_lineup):
            d = _dist(_coords_of(p), new_fb_rim)
            if d < outlet_to_rim:
                candidates.append((d, p))
        candidates.sort(key=lambda t: t[0])
        getbacks = [p for _, p in candidates[: max(0, int(getback_count))]]

    _stamp_cr_fields(result, release_player=release_player, getback_players=getbacks)
    if isinstance(result, dict) and skip_outlet:
        result["skip_outlet_pass"] = True
    return release_player, skip_outlet


def arm_dreb_fast_break(
    game: Any,
    *,
    source: str,
    rebounder: Any,
    rebounding_team: Any,
    result: Optional[Dict[str, Any]] = None,
    # FT
    ft_offense_lineup: Optional[Dict[str, Any]] = None,
    ft_defense_lineup: Optional[Dict[str, Any]] = None,
    # FB miss
    shooting_lineup: Optional[Dict[str, Any]] = None,
    rebounding_lineup: Optional[Dict[str, Any]] = None,
    is_away_shooting: Optional[bool] = None,
    # Optional override (tests)
    force_play_key: Optional[str] = None,
) -> str:
    """
    Arm DREB → FAST_BREAK or fall through to HCO.

    Returns ``"FAST_BREAK"`` or ``"HCO"``. Mutates ``game.game_state`` and optionally
    stamps Covert fields onto ``result``. Honors situational Force Foul (forgo FB).
    """
    from BackEnd.utils.sim_random import sim_rng as random

    from BackEnd.utils import situational_logic as sl

    game_state = game.game_state
    time_remaining_sec = game_state.get("time_remaining")

    # Situational Force Foul after DREB — same forgo as HCO shot_manager path.
    if (
        sl.is_situational_active(getattr(game, "quarter", None))
        and sl.is_slow_it_down(game, time_remaining_sec)
        and sl.should_force_foul(game, time_remaining_sec)
    ):
        _clear_pending_fb(game_state)
        if isinstance(result, dict):
            result["force_foul_after_dreb"] = True
            _stamp_empty_cr_fields(result)
        game_state["offensive_state"] = "HCO"
        game_state["last_rebounder"] = rebounder
        game_state["last_rebound"] = "DREB"
        if isinstance(result, dict):
            result["next_play_type"] = "HCO"
        return "HCO"

    fb_slider = sl.slow_it_down_defense_setting(
        game_state,
        rebounding_team,
        "fast_breaks",
        (getattr(rebounding_team, "strategy_settings", None) or {}).get("fast_breaks", 2),
    )
    p_fb = fast_break_probability_from_slider(fb_slider)
    if random.random() >= p_fb:
        _clear_pending_fb(game_state)
        _stamp_empty_cr_fields(result)
        game_state["offensive_state"] = "HCO"
        game_state["last_rebounder"] = rebounder
        game_state["last_rebound"] = "DREB"
        if isinstance(result, dict):
            result["next_play_type"] = "HCO"
        return "HCO"

    play_key = force_play_key or play_key_for_fast_break_entry(
        True,
        getattr(rebounding_team, "playbook_settings", None),
    )

    release_player: Optional[Any] = None
    if play_key == COVERT_RELEASE:
        if source == SOURCE_OREB_PUTBACK:
            release_player = prepare_covert_oreb_carry(game, result)
            if release_player is None:
                # Cannot run Covert without a carried release — fall back to RR.
                play_key = RIM_RUNNER
        elif source == SOURCE_FT:
            release_player = prepare_covert_ft_geo(
                game,
                ft_offense_lineup=ft_offense_lineup or {},
                ft_defense_lineup=ft_defense_lineup or {},
                result=result,
            )
            if release_player is None:
                play_key = RIM_RUNNER
        elif source == SOURCE_FB_MISS:
            release_player, _skip = prepare_covert_fb_miss_geo(
                game,
                shooting_lineup=shooting_lineup or {},
                rebounding_lineup=rebounding_lineup or {},
                rebounder=rebounder,
                is_away_shooting=bool(is_away_shooting),
                result=result,
            )
            if release_player is None:
                play_key = RIM_RUNNER
        else:
            # HCO uses shot_manager's own Covert prep; helper only finalizes pending.
            pass
    else:
        # RR / Triangle: all crash — no release list required.
        if source in (SOURCE_FT, SOURCE_FB_MISS, SOURCE_OREB_PUTBACK):
            _stamp_empty_cr_fields(result)

    if play_key not in (COVERT_RELEASE, RIM_RUNNER, TRIANGLE):
        play_key = RIM_RUNNER

    game_state["pending_dreb_fb_play_key"] = play_key
    game_state.pop("_shot_dreb_fb_play_key", None)
    game_state["last_rebounder"] = rebounder
    game_state["last_rebound"] = "DREB"
    game_state["offensive_state"] = "FAST_BREAK"

    if play_key == COVERT_RELEASE and release_player is not None:
        game_state["last_release_player"] = release_player
    else:
        game_state["last_release_player"] = None

    if isinstance(result, dict):
        result["next_play_type"] = "FAST_BREAK"
        result["pending_dreb_fb_play_key"] = play_key

    return "FAST_BREAK"


def consume_fb_miss_dreb_arm_stamp(
    game: Any,
    turn_result: Dict[str, Any],
    *,
    rebound_type: Optional[str],
) -> None:
    """Apply ``_fb_miss_dreb_fb_arm_stamp`` (or OREB/HCO default) onto an FB-miss turn."""
    arm_stamp = (getattr(game, "game_state", None) or {}).pop(
        "_fb_miss_dreb_fb_arm_stamp", None
    )
    if rebound_type == "OREB":
        turn_result["next_play_type"] = "OREB"
        return
    if isinstance(arm_stamp, dict) and arm_stamp:
        for k, v in arm_stamp.items():
            turn_result[k] = v
        turn_result["next_play_type"] = (getattr(game, "game_state", None) or {}).get(
            "offensive_state", turn_result.get("next_play_type", "HCO")
        )
    else:
        turn_result["next_play_type"] = "HCO"
