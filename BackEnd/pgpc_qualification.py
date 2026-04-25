"""
PGPC question qualification: filter `PRESS_CONFERENCE_QUESTIONS` by trigger.condition + filters.

Loads the question bank via importlib (avoids importing `BackEnd.utils`, which pulls Mongo/bson).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from BackEnd.models.pgpc_snapshot import FranchiseContextForPGPC
from BackEnd.pgpc_context import _team_blob_from_game_doc

_PCQ_PATH = Path(__file__).resolve().parent / "utils" / "press_conference_questions.py"
_QUESTION_BANK_CACHE: Optional[List[Dict[str, Any]]] = None

TIER_C_CONDITIONS = frozenset(
    {
        "clutch_time_scoring",
        "unanswered_run",
        "first_blood",
        "lead_changes",
        "game_winner_shot",
        "early_foul_trouble",
    }
)


def _press_conference_questions() -> List[Dict[str, Any]]:
    global _QUESTION_BANK_CACHE
    if _QUESTION_BANK_CACHE is None:
        spec = importlib.util.spec_from_file_location(
            "press_conference_questions_data", _PCQ_PATH
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load question bank from {_PCQ_PATH}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _QUESTION_BANK_CACHE = list(mod.PRESS_CONFERENCE_QUESTIONS)
    return _QUESTION_BANK_CACHE


def _int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _user_team_id(ctx: Mapping[str, Any]) -> str:
    return str(ctx.get("user_team_id") or "")


def _opponent_team_id(ctx: Mapping[str, Any]) -> str:
    return str(ctx.get("opponent_team_id") or "")


def _margin(ctx: Mapping[str, Any], game_doc: Mapping[str, Any]) -> int:
    if "margin_user_minus_opp" in ctx:
        return _int(ctx.get("margin_user_minus_opp"))
    ut = _user_team_id(ctx)
    ot = _opponent_team_id(ctx)
    ub = _team_blob_from_game_doc(game_doc, ut)
    ob = _team_blob_from_game_doc(game_doc, ot)
    return _int(ub.get("score") if ub else 0) - _int(ob.get("score") if ob else 0)


def _user_won(ctx: Mapping[str, Any], game_doc: Mapping[str, Any]) -> bool:
    if "user_won" in ctx:
        return bool(ctx.get("user_won"))
    return _margin(ctx, game_doc) > 0


def _overtime(ctx: Mapping[str, Any], game_doc: Mapping[str, Any]) -> bool:
    if ctx.get("overtime") is True:
        return True
    q = _int(game_doc.get("quarter"))
    if q > 4:
        return True
    ut = _user_team_id(ctx)
    ub = _team_blob_from_game_doc(game_doc, ut)
    if ub:
        pbq = ub.get("points_by_quarter")
        if isinstance(pbq, list) and len(pbq) > 4:
            return True
    return False


def _scores_through_q3(
    game_doc: Mapping[str, Any], team_id: str
) -> Optional[int]:
    blob = _team_blob_from_game_doc(game_doc, team_id)
    if not blob:
        return None
    pbq = blob.get("points_by_quarter")
    if not isinstance(pbq, list) or len(pbq) < 3:
        return None
    return sum(_int(pbq[i]) for i in range(3))


def _opening_starters(
    game_doc: Mapping[str, Any], user_team_id: str
) -> Optional[set[str]]:
    ol = game_doc.get("opening_lineup")
    if not isinstance(ol, dict):
        return None
    raw = ol.get(str(user_team_id))
    if raw is None:
        raw = ol.get(user_team_id)
    if not isinstance(raw, (list, tuple)) or len(raw) != 5:
        return None
    return {str(x) for x in raw if x is not None}


def _players_for_team(
    game_doc: Mapping[str, Any], team_id: str
) -> List[Dict[str, Any]]:
    tid = str(team_id)
    out: List[Dict[str, Any]] = []
    for row in game_doc.get("players") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("team_id") or "") == tid:
            out.append(row)
    return out


def _stat_row(row: Mapping[str, Any], key: str) -> int:
    stats = row.get("stats")
    if not isinstance(stats, dict):
        return 0
    return _int(stats.get(key))


def _team_sum_stat(players: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(_stat_row(p, key) for p in players)


def _team_fg_pct(players: Sequence[Mapping[str, Any]]) -> Optional[float]:
    fgm = _team_sum_stat(players, "FGM")
    fga = _team_sum_stat(players, "FGA")
    if fga <= 0:
        return None
    return 100.0 * fgm / fga


def _team_def_pct(players: Sequence[Mapping[str, Any]]) -> Optional[float]:
    ds = _team_sum_stat(players, "DEF_S")
    da = _team_sum_stat(players, "DEF_A")
    if da <= 0:
        return None
    return 100.0 * ds / da


def _player_def_pct(row: Mapping[str, Any]) -> Optional[float]:
    return _team_def_pct([row])


def _player_rt(
    player_id: str, ctx: Mapping[str, Any]
) -> Optional[float]:
    m = ctx.get("player_overall_rt")
    if not isinstance(m, dict):
        return None
    if player_id not in m and str(player_id) not in m:
        return None
    v = m.get(player_id)
    if v is None:
        v = m.get(str(player_id))
    f = _float(v, -1.0)
    return f if f >= 0 else None


def _series_wins_losses(ctx: Mapping[str, Any]) -> Tuple[int, int]:
    s = ctx.get("season_series_vs_opponent")
    if not isinstance(s, dict):
        return 0, 0
    return _int(s.get("w")), _int(s.get("l"))


def _eval_win_loss_filters(
    *,
    win: bool,
    filters: Mapping[str, Any],
    ctx: Mapping[str, Any],
    game_doc: Mapping[str, Any],
) -> bool:
    margin = _margin(ctx, game_doc)

    if filters.get("specificity") == "generic":
        pass

    if "min_margin" in filters:
        need = _int(filters.get("min_margin"))
        if win:
            if margin < need:
                return False
        else:
            if margin > -need:
                return False

    if "max_margin" in filters:
        cap = _int(filters.get("max_margin"))
        if win:
            if margin > cap:
                return False
        else:
            if margin < -cap:
                return False

    if filters.get("overtime") is True and not _overtime(ctx, game_doc):
        return False

    orank = ctx.get("opponent_natl_rank")
    if orank is not None:
        orank_i = _int(orank, -1)
        if "opponent_max_rank" in filters:
            if orank_i < 0 or orank_i > _int(filters.get("opponent_max_rank")):
                return False
        if "opponent_min_rank" in filters:
            if orank_i < _int(filters.get("opponent_min_rank")):
                return False

    if "opponent_is_conference_leader" in filters:
        if bool(filters.get("opponent_is_conference_leader")) != bool(
            ctx.get("opponent_is_conference_leader")
        ):
            return False

    gap_need = _int(filters.get("opponent_rank_gap_min"), -1)
    if gap_need >= 0:
        ur = ctx.get("user_natl_rank")
        opp_r = ctx.get("opponent_natl_rank")
        if ur is None or opp_r is None:
            return False
        ui, oi = _int(ur, -1), _int(opp_r, -1)
        if ui < 0 or oi < 0:
            return False
        if filters.get("opponent_higher") is True:
            if ui - oi < gap_need:
                return False
        if filters.get("opponent_lower") is True:
            if oi - ui < gap_need:
                return False

    if "wins_vs_opponent_this_season_min" in filters:
        w, _ = _series_wins_losses(ctx)
        if w < _int(filters.get("wins_vs_opponent_this_season_min")):
            return False

    if "losses_vs_opponent_this_season_min" in filters:
        _, ell = _series_wins_losses(ctx)
        if ell < _int(filters.get("losses_vs_opponent_this_season_min")):
            return False

    return True


def _eval_tier_c(
    condition: str,
    filters: Mapping[str, Any],
    game_doc: Mapping[str, Any],
) -> bool:
    tc = game_doc.get("pgpc_tier_c")
    if not isinstance(tc, dict):
        return False

    if condition == "lead_changes":
        n = tc.get("lead_changes")
        if not isinstance(n, (int, float)):
            return False
        return _int(n) >= _int(filters.get("min_changes"))

    if condition == "first_blood":
        fb = tc.get("first_blood")
        if not isinstance(fb, dict):
            return False
        if "user_scored_first_min" in filters:
            return _int(fb.get("user_run_before_opp_score")) >= _int(
                filters.get("user_scored_first_min")
            )
        if "opponent_scored_first_min" in filters:
            return _int(fb.get("opponent_run_before_user_score")) >= _int(
                filters.get("opponent_scored_first_min")
            )
        return False

    if condition == "unanswered_run":
        ur = tc.get("unanswered_run")
        if not isinstance(ur, dict):
            return False
        if "user_run_min" in filters:
            return _int(ur.get("user_longest")) >= _int(filters.get("user_run_min"))
        if "opponent_run_min" in filters:
            return _int(ur.get("opponent_longest")) >= _int(
                filters.get("opponent_run_min")
            )
        return False

    if condition == "clutch_time_scoring":
        cs = tc.get("clutch_time_scoring")
        if not isinstance(cs, dict):
            return False
        if filters.get("user_outscored_q4_final_2min") is True:
            return bool(cs.get("user_outscored_final_2min"))
        return bool(cs)

    if condition == "game_winner_shot":
        gws = tc.get("game_winner_shot")
        return isinstance(gws, dict) and bool(gws.get("occurred"))

    if condition == "early_foul_trouble":
        eft = tc.get("early_foul_trouble")
        need = _int(filters.get("fouls_by_halftime_min"), 3)
        if isinstance(eft, dict):
            byp = eft.get("by_player") or eft.get("players")
            if isinstance(byp, dict):
                return any(_int(v) >= need for v in byp.values())
            if isinstance(byp, list):
                return any(_int(x) >= need for x in byp)
        return False

    return False


def _condition_holds(
    condition: str,
    filters: Mapping[str, Any],
    game_doc: Mapping[str, Any],
    ctx: Mapping[str, Any],
) -> bool:
    ut = _user_team_id(ctx)
    ot = _opponent_team_id(ctx)
    if not ut or not ot:
        return condition == "always"

    user_players = _players_for_team(game_doc, ut)
    opp_players = _players_for_team(game_doc, ot)

    if condition == "always":
        return True

    if condition in TIER_C_CONDITIONS:
        return _eval_tier_c(condition, filters, game_doc)

    if condition == "win":
        if not _user_won(ctx, game_doc):
            return False
        return _eval_win_loss_filters(
            win=True, filters=filters, ctx=ctx, game_doc=game_doc
        )

    if condition == "loss":
        if _user_won(ctx, game_doc):
            return False
        return _eval_win_loss_filters(
            win=False, filters=filters, ctx=ctx, game_doc=game_doc
        )

    if condition == "come_from_behind_win":
        if not _user_won(ctx, game_doc):
            return False
        u3 = _scores_through_q3(game_doc, ut)
        o3 = _scores_through_q3(game_doc, ot)
        if u3 is None or o3 is None:
            return False
        if u3 >= o3:
            return False
        if filters.get("trailing_entering_q4") is True:
            return True
        return False

    if condition == "blown_loss":
        if _user_won(ctx, game_doc):
            return False
        u3 = _scores_through_q3(game_doc, ut)
        o3 = _scores_through_q3(game_doc, ot)
        if u3 is None or o3 is None:
            return False
        if u3 <= o3:
            return False
        return filters.get("leading_entering_q4") is True

    if condition == "bench_pts":
        starters = _opening_starters(game_doc, ut)
        if starters is None:
            return False
        bench_pts = 0
        for row in user_players:
            pid = str(row.get("playerId") or "")
            if not pid or pid in starters:
                continue
            bench_pts += _stat_row(row, "PTS")
        if "user_bench_min" in filters:
            return bench_pts >= _int(filters.get("user_bench_min"))
        if "user_bench_max" in filters:
            return bench_pts <= _int(filters.get("user_bench_max"))
        return False

    if condition == "bench_outscores_starter":
        starters = _opening_starters(game_doc, ut)
        if starters is None:
            return False
        starter_pts: List[int] = []
        bench_pts: List[int] = []
        for row in user_players:
            pid = str(row.get("playerId") or "")
            if not pid:
                continue
            pts = _stat_row(row, "PTS")
            if pid in starters:
                starter_pts.append(pts)
            else:
                bench_pts.append(pts)
        if len(starter_pts) != 5 or not bench_pts:
            return False
        return max(bench_pts) > min(starter_pts)

    if condition == "winning_streak":
        streak = _int(ctx.get("winning_streak_after_game"))
        if "min_streak" in filters:
            if streak < _int(filters.get("min_streak")):
                return False
        if "max_streak" in filters:
            if streak > _int(filters.get("max_streak")):
                return False
        return streak > 0

    if condition == "losing_streak":
        streak = _int(ctx.get("losing_streak_after_game"))
        if "min_streak" in filters:
            if streak < _int(filters.get("min_streak")):
                return False
        if "max_streak" in filters:
            if streak > _int(filters.get("max_streak")):
                return False
        return streak > 0

    if condition == "first_game_of_season":
        return ctx.get("first_game_of_season") is True

    if condition == "last_regular_season_game":
        return ctx.get("last_regular_season_game") is True

    if condition == "must_win_seeding":
        return ctx.get("must_win_seeding") is True

    if condition == "clinched_conference_seed":
        return ctx.get("clinched_conference_seed") is True

    if condition == "prestige_new_high":
        return ctx.get("prestige_new_high") is True

    if condition == "prestige_drop_streak":
        if "min_weeks" not in filters:
            return False
        return _int(ctx.get("prestige_drop_streak")) >= _int(filters["min_weeks"])

    if condition == "entered_top_25_first_time":
        return ctx.get("entered_top_25_first_time") is True

    if condition == "fell_out_top_25":
        return ctx.get("fell_out_top_25") is True

    if condition == "above_500_first_time_season":
        return ctx.get("above_500_first_time_season") is True

    if condition == "fell_below_500":
        return ctx.get("fell_below_500") is True

    if condition == "team_chemistry":
        blob = _team_blob_from_game_doc(game_doc, ut)
        chem = None
        if blob:
            attrs = blob.get("attributes")
            if isinstance(attrs, dict):
                chem = attrs.get("team_chemistry")
        if chem is None:
            band = ctx.get("team_chemistry_band")
            if band is not None:
                chem = band
        c = _float(chem, float("nan"))
        if c != c:
            return False
        if "min_chemistry" in filters:
            return c >= _float(filters.get("min_chemistry"))
        if "max_chemistry" in filters:
            return c <= _float(filters.get("max_chemistry"))
        return False

    if condition == "fg_pct_gap":
        ug = _team_fg_pct(user_players)
        og = _team_fg_pct(opp_players)
        if ug is None or og is None:
            return False
        diff = ug - og
        if "user_advantage_min" in filters:
            return diff >= _float(filters.get("user_advantage_min"))
        if "opponent_advantage_min" in filters:
            return (og - ug) >= _float(filters.get("opponent_advantage_min"))
        return False

    if condition == "fastbreak_pts_gap":
        ufb = _team_sum_stat(user_players, "FB_PTS")
        ofb = _team_sum_stat(opp_players, "FB_PTS")
        if "user_advantage_min" in filters:
            return (ufb - ofb) >= _int(filters.get("user_advantage_min"))
        if "opponent_advantage_min" in filters:
            return (ofb - ufb) >= _int(filters.get("opponent_advantage_min"))
        return False

    if condition == "paint_pts_gap":
        up = _team_sum_stat(user_players, "PIP")
        op = _team_sum_stat(opp_players, "PIP")
        if "user_advantage_min" in filters:
            return (up - op) >= _int(filters.get("user_advantage_min"))
        if "opponent_advantage_min" in filters:
            return (op - up) >= _int(filters.get("opponent_advantage_min"))
        return False

    if condition == "three_pt_pct":
        ua = _team_sum_stat(user_players, "3PTA")
        um = _team_sum_stat(user_players, "3PTM")
        if ua <= 0:
            return False
        upct = 100.0 * um / ua
        if "user_min_pct" in filters:
            if ua < _int(filters.get("user_min_attempts")):
                return False
            return upct >= _float(filters.get("user_min_pct"))
        if "user_max_pct" in filters:
            if ua < _int(filters.get("user_min_attempts")):
                return False
            return upct <= _float(filters.get("user_max_pct"))
        return False

    if condition == "team_def_pct":
        dp = _team_def_pct(user_players)
        if dp is None:
            return False
        if "min_def_pct" in filters:
            if _team_sum_stat(user_players, "DEF_A") < _int(
                filters.get("min_defa")
            ):
                return False
            return dp >= _float(filters.get("min_def_pct"))
        return False

    if condition == "player_def_pct":
        for row in user_players:
            da = _stat_row(row, "DEF_A")
            dp = _player_def_pct(row)
            if dp is None:
                continue
            if "min_def_pct" in filters:
                if da < _int(filters.get("min_defa")):
                    continue
                if dp >= _float(filters.get("min_def_pct")):
                    return True
            if "max_def_pct" in filters:
                if da < _int(filters.get("min_defa")):
                    continue
                if dp <= _float(filters.get("max_def_pct")):
                    return True
        return False

    if condition == "player_pts":
        need = _int(filters.get("min_pts"))
        return any(_stat_row(r, "PTS") >= need for r in user_players)

    if condition == "player_reb":
        need = _int(filters.get("min_reb"))
        return any(_stat_row(r, "REB") >= need for r in user_players)

    if condition == "player_three_pt_made":
        need = _int(filters.get("min_made"))
        return any(_stat_row(r, "3PTM") >= need for r in user_players)

    if condition == "player_fouls":
        need = _int(filters.get("min_fouls"))
        return any(_stat_row(r, "F") >= need for r in user_players)

    if condition == "player_ft":
        max_pct = _float(filters.get("max_ft_pct"))
        min_att = _int(filters.get("min_ft_attempts"))
        for row in user_players:
            fta = _stat_row(row, "FTA")
            if fta < min_att:
                continue
            ftm = _stat_row(row, "FTM")
            pct = 100.0 * ftm / fta
            if pct <= max_pct:
                return True
        return False

    if condition == "player_em":
        for row in user_players:
            attrs = row.get("attributes")
            if not isinstance(attrs, dict):
                continue
            em = _int(attrs.get("EM"))
            if "min_em" in filters and em >= _int(filters.get("min_em")):
                return True
            if "max_em" in filters and em <= _int(filters.get("max_em")):
                return True
        return False

    if condition == "opponent_star_pts":
        if not filters.get("opponent_highest_rt"):
            return False
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
        if best_id is None:
            return False
        for row in opp_players:
            if str(row.get("playerId")) == best_id:
                return _stat_row(row, "PTS") <= _int(filters.get("max_pts"))
        return False

    if condition == "player_pts_vs_rating":
        prt = _int(filters.get("player_rt_max"), 50)
        mpts = _int(filters.get("min_pts"))
        for row in user_players:
            pid = str(row.get("playerId") or "")
            rt = _player_rt(pid, ctx)
            if rt is None or rt > prt:
                continue
            if _stat_row(row, "PTS") >= mpts:
                return True
        return False

    if condition == "player_reb_vs_rating":
        prt = _int(filters.get("player_rt_max"), 50)
        mreb = _int(filters.get("min_reb"))
        for row in user_players:
            pid = str(row.get("playerId") or "")
            rt = _player_rt(pid, ctx)
            if rt is None or rt > prt:
                continue
            if _stat_row(row, "REB") >= mreb:
                return True
        return False

    if condition == "player_pts_rating":
        min_rt = _float(filters.get("min_rt"))
        if "min_pts" in filters and "max_pts" in filters:
            lo, hi = _int(filters.get("min_pts")), _int(filters.get("max_pts"))
            for row in user_players:
                pid = str(row.get("playerId") or "")
                rt = _player_rt(pid, ctx)
                if rt is None or rt < min_rt:
                    continue
                pts = _stat_row(row, "PTS")
                if lo <= pts <= hi:
                    return True
            return False
        if "min_pts" in filters:
            need = _int(filters.get("min_pts"))
            for row in user_players:
                pid = str(row.get("playerId") or "")
                rt = _player_rt(pid, ctx)
                if rt is None or rt < min_rt:
                    continue
                if _stat_row(row, "PTS") >= need:
                    return True
            return False
        if "pts" in filters:
            exact = _int(filters.get("pts"))
            for row in user_players:
                pid = str(row.get("playerId") or "")
                rt = _player_rt(pid, ctx)
                if rt is None or rt < min_rt:
                    continue
                if _stat_row(row, "PTS") == exact:
                    return True
            return False
        return False

    if condition == "limited_minutes_high_rt":
        max_min = _float(filters.get("max_minutes"))
        min_rt = _float(filters.get("min_rt"))
        for row in user_players:
            pid = str(row.get("playerId") or "")
            rt = _player_rt(pid, ctx)
            if rt is None or rt < min_rt:
                continue
            mn = _stat_row(row, "MIN")
            if mn <= max_min:
                return True
        return False

    return False


def get_qualifying_pgpc_questions(
    game_doc: Mapping[str, Any],
    context: FranchiseContextForPGPC | Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """
    Return question dicts from the bank that qualify for this game + franchise context.
    """
    ctx = dict(context)
    out: List[Dict[str, Any]] = []
    for q in _press_conference_questions():
        trig = q.get("trigger")
        if not isinstance(trig, dict):
            continue
        cond = trig.get("condition")
        if not isinstance(cond, str):
            continue
        filters = trig.get("filters") or {}
        if not isinstance(filters, dict):
            filters = {}
        if not _condition_holds(cond, filters, game_doc, ctx):
            continue
        out.append(q)
    return out


__all__ = [
    "TIER_C_CONDITIONS",
    "get_qualifying_pgpc_questions",
]
