"""Distant franchise game sim win-probability helpers.

Used by franchise_routes, calibration scripts, and tests.
"""

from __future__ import annotations

from typing import Any

from BackEnd.constants.distant_sim import (
    DISTANT_CHEMISTRY_MAX,
    DISTANT_CHEMISTRY_MIN,
    DISTANT_MO_LOSS_DECAY,
    DISTANT_MO_MULT_BANDS,
    DISTANT_MO_SCORE_WEIGHT,
    DISTANT_MO_STREAK_LOSS_RESET,
    DISTANT_MO_STREAK_WIN_BONUS,
    DISTANT_MO_WIN_GAIN,
    DISTANT_MOMENTUM_SCORE_MAX,
    DISTANT_MOMENTUM_SCORE_MIN,
    DISTANT_STREAK_BONUS,
    DISTANT_STREAK_MIN,
    DISTANT_STREAK_PENALTY,
    DISTANT_TIER_BANDS,
    DISTANT_TIER_WEEK_GATE,
    DISTANT_TALENT_ATTR_MULT,
    DISTANT_RANKED_FULLSIM_MAX_RANK,
)

_DISTANT_CORE_PLAYER_ATTRS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")


def _core_total_player_attrs(attrs: dict[str, Any] | None) -> int:
    if not attrs:
        return 0
    return sum(int(attrs.get(attr, 0) or 0) for attr in _DISTANT_CORE_PLAYER_ATTRS)


def clamp_distant_team_chemistry(team_chemistry_raw: Any) -> int:
    try:
        tc_raw = int(team_chemistry_raw)
    except (TypeError, ValueError):
        tc_raw = DISTANT_CHEMISTRY_MIN
    return max(DISTANT_CHEMISTRY_MIN, min(DISTANT_CHEMISTRY_MAX, tc_raw))


def clamp_distant_momentum_score(value: Any) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        raw = 0.0
    return max(DISTANT_MOMENTUM_SCORE_MIN, min(DISTANT_MOMENTUM_SCORE_MAX, raw))


def distant_sim_chemistry_scale(team_chemistry_raw: Any) -> float:
    return max(1.0, clamp_distant_team_chemistry(team_chemistry_raw) / 10.0)


def distant_sim_momentum_multiplier(team_chemistry_raw: Any) -> int:
    """Record-momentum multiplier from team chemistry (Distant_Game_Sim_System.md)."""
    tc = clamp_distant_team_chemistry(team_chemistry_raw)
    for upper, mult in DISTANT_MO_MULT_BANDS:
        if tc < upper:
            return mult
    return DISTANT_MO_MULT_BANDS[-1][1]


def _streak_int(team_attributes: dict | None, key: str) -> int:
    if not team_attributes:
        return 0
    try:
        return max(0, int(team_attributes.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def distant_sim_record_momentum(
    team_chemistry_raw: Any,
    *,
    season_wins: int,
    season_losses: int,
    team_attributes: dict | None = None,
) -> int:
    """DISTANT_MO_MULT × (wins − losses) + streak bonus/penalty."""
    mult = distant_sim_momentum_multiplier(team_chemistry_raw)
    wins = max(0, int(season_wins))
    losses = max(0, int(season_losses))
    out = mult * (wins - losses)
    out += distant_sim_record_streak_bonus(team_attributes)
    return out


def distant_sim_record_streak_bonus(team_attributes: dict | None) -> int:
    """Additive streak bonus on record momentum (distant_win/loss_streak FTD fields)."""
    win_streak = _streak_int(team_attributes, "distant_win_streak")
    loss_streak = _streak_int(team_attributes, "distant_loss_streak")
    bonus = 0
    if win_streak >= DISTANT_STREAK_MIN:
        bonus += DISTANT_STREAK_BONUS * (win_streak - (DISTANT_STREAK_MIN - 1))
    if loss_streak >= DISTANT_STREAK_MIN:
        bonus -= DISTANT_STREAK_PENALTY * (loss_streak - (DISTANT_STREAK_MIN - 1))
    return bonus


def distant_sim_tier_multiplier(win_pct: float) -> float:
    for threshold, mult in DISTANT_TIER_BANDS:
        if win_pct >= threshold:
            return mult
    return DISTANT_TIER_BANDS[-1][1]


def distant_sim_tier_adjustment(
    *,
    season_wins: int,
    season_losses: int,
    record_momentum: int,
    season_momentum: int,
    current_week: int,
) -> int:
    """Late-season amplification of momentum layers for hot/cold teams."""
    if int(current_week) < DISTANT_TIER_WEEK_GATE:
        return 0
    gp = max(0, int(season_wins)) + max(0, int(season_losses))
    if gp <= 0:
        return 0
    win_pct = int(season_wins) / gp
    tier_mult = distant_sim_tier_multiplier(win_pct)
    momentum_sum = record_momentum + season_momentum
    return int(momentum_sum * (tier_mult - 1.0))


def distant_sim_season_momentum(momentum_score_raw: Any) -> int:
    """FTD momentum_score × weight → combined-score points."""
    return int(round(clamp_distant_momentum_score(momentum_score_raw) * DISTANT_MO_SCORE_WEIGHT))


def distant_sim_home_chemistry_bonus(team_chemistry_raw: Any) -> int:
    """Home win-roll bonus: 2 × team_chemistry."""
    return 2 * clamp_distant_team_chemistry(team_chemistry_raw)


def distant_sim_team_attr_composite(team_attributes: dict | None) -> int:
    """Fallback talent bump from trained team attributes (distant sim only)."""
    if not team_attributes:
        return 0
    try:
        offensive = int(team_attributes.get("offensive_efficiency") or 0)
        defensive = int(team_attributes.get("defensive_efficiency") or 0)
        st_raw = team_attributes.get("shot_threshold")
        shot_penalty = int(int(st_raw) / 20) if st_raw is not None else 0
    except (TypeError, ValueError):
        return 0
    return offensive + defensive - shot_penalty


def distant_sim_live_roster_player_attrs(
    ftd_doc: dict,
    fpd_by_player_id: dict[str, dict] | None,
) -> int | None:
    """Sum live FPD core attrs for active roster; None when FPD path unavailable."""
    if not fpd_by_player_id:
        return None
    player_ids = [str(pid) for pid in (ftd_doc.get("players") or []) if pid]
    if not player_ids:
        return None
    return sum(
        _core_total_player_attrs((fpd_by_player_id.get(pid) or {}).get("attributes") or {})
        for pid in player_ids
    )


def distant_sim_talent_signal(
    ftd_doc: dict,
    fpd_by_player_id: dict[str, dict] | None = None,
) -> int:
    """
    Distant-only talent input for base score (not written to FTD for ranking).

    Option A: live sum from FPD roster attrs at sim time.
    Option B: frozen total_player_attrs + team-attribute composite fallback.
    """
    live = distant_sim_live_roster_player_attrs(ftd_doc, fpd_by_player_id)
    if live is not None:
        return live
    frozen = int(ftd_doc.get("total_player_attrs") or 0)
    team_attributes = ftd_doc.get("team_attributes") or {}
    return frozen + distant_sim_team_attr_composite(team_attributes)


def distant_sim_base_score(*, prestige: Any, talent_signal: Any) -> int:
    return int(prestige or 0) + int(DISTANT_TALENT_ATTR_MULT * (talent_signal or 0))


def distant_sim_should_promote_ranked_fullsim(
    away_ftd: dict | None,
    home_ftd: dict | None,
    *,
    max_rank: int | None = None,
) -> bool:
    """Phase 5: both teams nationally ranked ≤ cap → full CPU sim instead of distant."""
    cap = DISTANT_RANKED_FULLSIM_MAX_RANK if max_rank is None else int(max_rank)
    if cap <= 0:
        return False
    away_rank = int((away_ftd or {}).get("natl_rank", 999) or 999)
    home_rank = int((home_ftd or {}).get("natl_rank", 999) or 999)
    return away_rank <= cap and home_rank <= cap


def distant_sim_apply_result_to_standings_cache(
    rs_standings: dict[str, dict[str, int]],
    away_id: Any,
    home_id: Any,
    away_score: int,
    home_score: int,
) -> None:
    """Increment in-memory RS W/L so later same-week distant sims see updated records."""
    away_key = str(away_id)
    home_key = str(home_id)
    for key in (away_key, home_key):
        rs_standings.setdefault(key, {"W": 0, "L": 0, "PF": 0, "PA": 0})
    if home_score > away_score:
        rs_standings[home_key]["W"] = int(rs_standings[home_key].get("W", 0) or 0) + 1
        rs_standings[away_key]["L"] = int(rs_standings[away_key].get("L", 0) or 0) + 1
    else:
        rs_standings[away_key]["W"] = int(rs_standings[away_key].get("W", 0) or 0) + 1
        rs_standings[home_key]["L"] = int(rs_standings[home_key].get("L", 0) or 0) + 1
    rs_standings[home_key]["PF"] = int(rs_standings[home_key].get("PF", 0) or 0) + int(home_score)
    rs_standings[home_key]["PA"] = int(rs_standings[home_key].get("PA", 0) or 0) + int(away_score)
    rs_standings[away_key]["PF"] = int(rs_standings[away_key].get("PF", 0) or 0) + int(away_score)
    rs_standings[away_key]["PA"] = int(rs_standings[away_key].get("PA", 0) or 0) + int(home_score)


def compute_distant_momentum_score_updates(
    winner_team_attributes: dict | None,
    loser_team_attributes: dict | None,
) -> tuple[dict[str, float | int], dict[str, float | int]]:
    """
    Apply distant-sim win/loss momentum_score deltas and streak counters.
    Returns partial team_attributes updates for winner and loser FTDs.
    """
    w_attrs = winner_team_attributes or {}
    l_attrs = loser_team_attributes or {}

    w_chem = w_attrs.get("team_chemistry")
    l_chem = l_attrs.get("team_chemistry")
    w_mo = clamp_distant_momentum_score(w_attrs.get("momentum_score", 0))
    l_mo = clamp_distant_momentum_score(l_attrs.get("momentum_score", 0))
    w_old_win_streak = _streak_int(w_attrs, "distant_win_streak")
    l_old_win_streak = _streak_int(l_attrs, "distant_win_streak")
    l_old_loss_streak = _streak_int(l_attrs, "distant_loss_streak")

    w_gain = DISTANT_MO_WIN_GAIN * distant_sim_chemistry_scale(w_chem)
    new_w_win_streak = w_old_win_streak + 1
    if new_w_win_streak >= 3:
        w_gain += DISTANT_MO_STREAK_WIN_BONUS * (new_w_win_streak - 2)
    w_mo_new = clamp_distant_momentum_score(w_mo + w_gain)

    l_decay = DISTANT_MO_LOSS_DECAY * distant_sim_chemistry_scale(l_chem)
    l_mo_new = l_mo - l_decay
    if l_old_win_streak >= 3:
        l_mo_new -= DISTANT_MO_STREAK_LOSS_RESET
    l_mo_new = clamp_distant_momentum_score(l_mo_new)

    return (
        {
            "momentum_score": w_mo_new,
            "distant_win_streak": new_w_win_streak,
            "distant_loss_streak": 0,
        },
        {
            "momentum_score": l_mo_new,
            "distant_win_streak": 0,
            "distant_loss_streak": l_old_loss_streak + 1,
        },
    )


def distant_sim_team_combined(
    ftd_doc: dict,
    *,
    season_wins: int,
    season_losses: int,
    is_home: bool,
    fpd_by_player_id: dict[str, dict] | None = None,
    current_week: int = 0,
) -> int:
    """Base + record momentum + season momentum + tier adj + home-only 2×chemistry bonus."""
    team_attributes = ftd_doc.get("team_attributes") or {}
    raw_chem = team_attributes.get("team_chemistry")
    out = distant_sim_base_score(
        prestige=ftd_doc.get("prestige"),
        talent_signal=distant_sim_talent_signal(ftd_doc, fpd_by_player_id),
    )
    record_mo = distant_sim_record_momentum(
        raw_chem,
        season_wins=season_wins,
        season_losses=season_losses,
        team_attributes=team_attributes,
    )
    season_mo = distant_sim_season_momentum(team_attributes.get("momentum_score", 0))
    out += record_mo
    out += season_mo
    out += distant_sim_tier_adjustment(
        season_wins=season_wins,
        season_losses=season_losses,
        record_momentum=record_mo,
        season_momentum=season_mo,
        current_week=current_week,
    )
    if is_home:
        out += distant_sim_home_chemistry_bonus(raw_chem)
    return out
