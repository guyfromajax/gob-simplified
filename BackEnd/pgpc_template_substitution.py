"""
Resolve `{placeholder}` tokens in PGPC question/answer text (except `{player_name}`,
handled in ``press_conference_routes`` with full vs first-name rules).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from BackEnd.pgpc_context import _team_blob_from_game_doc
from BackEnd.pgpc_qualification import (
    _int,
    _opening_starters,
    _player_rt,
    _players_for_team,
    _stat_row,
    _team_def_pct,
    _team_fg_pct,
    _team_sum_stat,
)


def _pct_display(v: Optional[float]) -> str:
    if v is None:
        return "0"
    return str(int(round(v)))


def _opponent_display_name(game_doc: Mapping[str, Any], opp_tid: str) -> str:
    blob = _team_blob_from_game_doc(game_doc, opp_tid)
    if blob:
        n = blob.get("name")
        if n:
            return str(n)
    return "the opponent"


def _opp_star_points(game_doc: Mapping[str, Any], opp_tid: str, ctx: Mapping[str, Any]) -> str:
    opp_players = _players_for_team(game_doc, opp_tid)
    best_id: Optional[str] = None
    best_rt = -1.0
    for row in opp_players:
        pid = str(row.get("playerId") or "")
        if not pid:
            continue
        rt = _player_rt(pid, ctx)
        if rt is None:
            continue
        if rt > best_rt:
            best_rt = rt
            best_id = pid
    if not best_id:
        return "0"
    for row in opp_players:
        if str(row.get("playerId")) == best_id:
            return str(_stat_row(row, "PTS"))
    return "0"


def _user_bench_points(game_doc: Mapping[str, Any], ut: str) -> str:
    starters = _opening_starters(game_doc, ut)
    if starters is None:
        return "0"
    total = 0
    for row in _players_for_team(game_doc, ut):
        pid = str(row.get("playerId") or "")
        if not pid or pid in starters:
            continue
        total += _stat_row(row, "PTS")
    return str(total)


def _halftime_fouls(tier_c: Mapping[str, Any], pid: str) -> Optional[int]:
    eft = tier_c.get("early_foul_trouble")
    if not isinstance(eft, dict):
        return None
    byp = eft.get("by_player") or eft.get("players")
    if isinstance(byp, dict):
        if pid in byp:
            return _int(byp.get(pid))
        for k, v in byp.items():
            if str(k) == pid:
                return _int(v)
    return None


def build_pgpc_substitutions(
    game_doc: Mapping[str, Any],
    ctx: Mapping[str, Any],
    *,
    slot_player: Optional[Mapping[str, Any]] = None,
    player_slot: Optional[str] = None,
) -> Dict[str, str]:
    """
    Flat map of ``"{token}" -> str`` for every placeholder used in the bank
    (values are best-effort from box score + ``pgpc_tier_c`` + franchise ctx).
    """
    ut = str(ctx.get("user_team_id") or "")
    ot = str(ctx.get("opponent_team_id") or "")

    raw_tc = game_doc.get("pgpc_tier_c")
    tc: Dict[str, Any] = dict(raw_tc) if isinstance(raw_tc, dict) else {}

    out: Dict[str, str] = {}

    out["{win_streak}"] = str(_int(ctx.get("winning_streak_after_game")))
    out["{loss_streak}"] = str(_int(ctx.get("losing_streak_after_game")))
    out["{prestige_decline_weeks}"] = str(_int(ctx.get("prestige_drop_streak")))
    out["{opponent_name}"] = _opponent_display_name(game_doc, ot) if ot else "the opponent"

    user_players = _players_for_team(game_doc, ut) if ut else []
    opp_players = _players_for_team(game_doc, ot) if ot else []

    ug = _team_fg_pct(user_players)
    og = _team_fg_pct(opp_players)
    out["{user_fg_pct}"] = _pct_display(ug)
    out["{opp_fg_pct}"] = _pct_display(og)
    if ug is not None and og is not None:
        out["{fg_pct_gap}"] = str(int(round(abs(ug - og))))
    else:
        out["{fg_pct_gap}"] = "0"

    ufb = _team_sum_stat(user_players, "FB_PTS")
    ofb = _team_sum_stat(opp_players, "FB_PTS")
    out["{fb_pts_gap}"] = str(max(0, ofb - ufb))

    upip = _team_sum_stat(user_players, "PIP")
    opip = _team_sum_stat(opp_players, "PIP")
    out["{pip_gap}"] = str(max(0, upip - opip))

    out["{bench_pts}"] = _user_bench_points(game_doc, ut) if ut else "0"

    dp = _team_def_pct(user_players)
    out["{team_def_pct}"] = _pct_display(dp)

    out["{lead_changes}"] = str(_int(tc.get("lead_changes")))

    fb = tc.get("first_blood")
    if isinstance(fb, dict):
        out["{opening_run}"] = str(_int(fb.get("user_run_before_opp_score")))
        out["{opp_opening_run}"] = str(_int(fb.get("opponent_run_before_user_score")))
    else:
        out["{opening_run}"] = "0"
        out["{opp_opening_run}"] = "0"

    ur = tc.get("unanswered_run")
    if isinstance(ur, dict):
        out["{user_run}"] = str(_int(ur.get("user_longest")))
        out["{opp_run}"] = str(_int(ur.get("opponent_longest")))
    else:
        out["{user_run}"] = "0"
        out["{opp_run}"] = "0"

    out["{opp_star_pts}"] = _opp_star_points(game_doc, ot, ctx) if ot else "0"

    slot = str(player_slot) if player_slot else ""
    if slot_player and isinstance(slot_player, dict):
        st = slot_player.get("stats")
        stats: Mapping[str, Any] = st if isinstance(st, dict) else {}
        pid = str(slot_player.get("playerId") or "")

        def gs(key: str) -> int:
            return _int(stats.get(key))

        out["{player_pts}"] = str(gs("PTS"))
        out["{player_reb}"] = str(gs("REB"))
        out["{player_3pm}"] = str(gs("3PTM"))
        fouls = gs("F")
        if fouls == 0:
            fouls = gs("PF")
        if slot == "foul_trouble":
            hf = _halftime_fouls(tc, pid)
            out["{player_fouls}"] = str(hf) if hf is not None else str(fouls)
        else:
            out["{player_fouls}"] = str(fouls)
        out["{player_ftm}"] = str(gs("FTM"))
        out["{player_fta}"] = str(gs("FTA"))
        out["{player_min}"] = str(gs("MIN"))
    else:
        out["{player_pts}"] = "0"
        out["{player_reb}"] = "0"
        out["{player_3pm}"] = "0"
        out["{player_fouls}"] = "0"
        out["{player_ftm}"] = "0"
        out["{player_fta}"] = "0"
        out["{player_min}"] = "0"

    return out


def apply_pgpc_substitutions(text: str, subs: Mapping[str, str]) -> str:
    t = text
    for key, val in subs.items():
        if key == "{player_name}":
            continue
        t = t.replace(key, val)
    return t


__all__ = ["apply_pgpc_substitutions", "build_pgpc_substitutions"]
