"""
PGPC franchise context builder (lightweight module — avoid importing via BackEnd.utils).

Consumer code may also use `BackEnd.utils.shared.build_franchise_context_for_pgpc` (re-export).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from BackEnd.models.pgpc_snapshot import FranchiseContextForPGPC

_REGULAR_SEASON_WEEKS = 26


def _team_blob_from_game_doc(game_doc: Dict[str, Any], team_id: str) -> Optional[Dict[str, Any]]:
    """Resolve `teams[key]` where key or nested `team_id` matches `team_id`."""
    if not isinstance(game_doc, dict):
        return None
    teams = game_doc.get("teams")
    if not isinstance(teams, dict):
        return None
    tid = str(team_id)
    for key, blob in teams.items():
        if not isinstance(blob, dict):
            continue
        nested = blob.get("team_id")
        if nested is not None and str(nested) == tid:
            return blob
        if str(key) == tid:
            return blob
    return None


def _outcome_for_user(result: Dict[str, Any], user_tid: str) -> Optional[bool]:
    """True if user won, False if lost; None if not involved or tie."""
    away_id = str(result.get("away_id") or "")
    home_id = str(result.get("home_id") or "")
    ut = str(user_tid)
    if ut not in {away_id, home_id}:
        return None
    a_s = int(result.get("away_score", 0) or 0)
    h_s = int(result.get("home_score", 0) or 0)
    if a_s == h_s:
        return None
    if ut == away_id:
        return a_s > h_s
    return h_s > a_s


def _user_game_for_week(
    results_root: Dict[str, Any], week: int, user_tid: str
) -> Optional[Dict[str, Any]]:
    for r in list(results_root.get(str(week), []) or []):
        if not isinstance(r, dict):
            continue
        away_id = str(r.get("away_id") or "")
        home_id = str(r.get("home_id") or "")
        if str(user_tid) in {away_id, home_id}:
            return r
    return None


def _series_vs_opponent_before_week(
    results_root: Dict[str, Any],
    user_tid: str,
    opp_tid: str,
    before_week: int,
) -> Tuple[int, int]:
    w, l = 0, 0
    for week in range(1, before_week):
        r = _user_game_for_week(results_root, week, user_tid)
        if not r:
            continue
        away_id = str(r.get("away_id") or "")
        home_id = str(r.get("home_id") or "")
        if str(opp_tid) not in {away_id, home_id}:
            continue
        o = _outcome_for_user(r, user_tid)
        if o is True:
            w += 1
        elif o is False:
            l += 1
    return w, l


def _streaks_after_sequence(outcomes: List[bool]) -> Tuple[int, int]:
    if not outcomes:
        return 0, 0
    last = outcomes[-1]
    run = 1
    for i in range(len(outcomes) - 2, -1, -1):
        if outcomes[i] == last:
            run += 1
        else:
            break
    if last:
        return run, 0
    return 0, run


def _record_through_weeks(
    results_root: Dict[str, Any], user_tid: str, before_week: int
) -> Tuple[int, int]:
    w, l = 0, 0
    for week in range(1, before_week):
        r = _user_game_for_week(results_root, week, user_tid)
        if not r:
            continue
        o = _outcome_for_user(r, user_tid)
        if o is True:
            w += 1
        elif o is False:
            l += 1
    return w, l


def _best_position_rating(position_ratings: Any) -> float:
    best = 0.0
    if not isinstance(position_ratings, dict):
        return best
    for value in position_ratings.values():
        try:
            rating = int(value)
        except (TypeError, ValueError):
            continue
        best = max(best, float(rating))
    return best


def attach_pgpc_rank_and_player_rt(
    ctx: Dict[str, Any],
    franchise_id: Any,
    game_doc: Dict[str, Any],
) -> None:
    """Mutate ``ctx`` with ``user_natl_rank``, ``opponent_natl_rank``, ``player_overall_rt`` from Mongo."""
    try:
        from BackEnd.db import franchise_players_data_collection, franchise_team_data_collection
    except Exception:
        return

    try:
        fid = ObjectId(str(franchise_id))
    except Exception:
        return

    ut = str(ctx.get("user_team_id") or "")
    ot = str(ctx.get("opponent_team_id") or "")
    if not ut or not ot:
        return

    ftd = list(
        franchise_team_data_collection.find(
            {"franchise_id": fid},
            {"team_id": 1, "natl_rank": 1},
        )
    )
    rank_by: Dict[str, int] = {}
    for doc in ftd:
        tid = str(doc.get("team_id") or "")
        if tid:
            rank_by[tid] = int(doc.get("natl_rank", 999) or 999)
    ctx["user_natl_rank"] = rank_by.get(ut)
    ctx["opponent_natl_rank"] = rank_by.get(ot)

    pids: List[str] = []
    for row in game_doc.get("players") or []:
        if not isinstance(row, dict):
            continue
        pid = row.get("playerId")
        if pid is not None:
            pids.append(str(pid))
    if not pids:
        return

    fpd_docs = franchise_players_data_collection.find(
        {"franchise_id": str(fid), "player_id": {"$in": pids}},
        {"player_id": 1, "position_ratings": 1},
    )
    rt_map: Dict[str, float] = {}
    for doc in fpd_docs:
        pid = str(doc.get("player_id") or "")
        if not pid:
            continue
        rt = _best_position_rating(doc.get("position_ratings"))
        if rt > 0:
            rt_map[pid] = rt
    if rt_map:
        existing = ctx.get("player_overall_rt")
        if isinstance(existing, dict):
            merged = {str(k): float(v) for k, v in existing.items()}
            merged.update(rt_map)
            ctx["player_overall_rt"] = merged
        else:
            ctx["player_overall_rt"] = rt_map


def build_franchise_context_for_pgpc(
    game_doc: Dict[str, Any],
    franchise_doc: Optional[Dict[str, Any]] = None,
    *,
    user_team_id: str,
    opponent_team_id: str,
    user_id: str = "",
    franchise_id: str = "",
    week: int = 0,
    attach_db_fields: bool = True,
) -> FranchiseContextForPGPC:
    """
    Build PGPC franchise context from a finalized game document plus franchise state.

    Fills W/L, margin, OT from ``game_doc``. When ``franchise_doc`` is provided, computes
    streaks, season series vs opponent, and season-phase flags from ``franchise_doc["results"]``.

    When ``attach_db_fields`` is True and ``franchise_doc`` has ``_id``, loads national ranks
    and player overall RT from franchise team/player collections.
    """
    user_blob = _team_blob_from_game_doc(game_doc, user_team_id)
    opp_blob = _team_blob_from_game_doc(game_doc, opponent_team_id)
    user_score = int(user_blob.get("score", 0)) if user_blob else 0
    opp_score = int(opp_blob.get("score", 0)) if opp_blob else 0
    user_won = user_score > opp_score
    margin = user_score - opp_score

    q = game_doc.get("quarter")
    try:
        quarter_int = int(q) if q is not None else 0
    except (TypeError, ValueError):
        quarter_int = 0
    overtime = quarter_int > 4
    if not overtime and user_blob:
        pbq = user_blob.get("points_by_quarter")
        if isinstance(pbq, list) and len(pbq) > 4:
            overtime = True

    ctx: Dict[str, Any] = {
        "franchise_id": str(franchise_id or ""),
        "user_id": str(user_id or ""),
        "week": int(week),
        "user_team_id": str(user_team_id),
        "opponent_team_id": str(opponent_team_id),
        "user_won": user_won,
        "margin_user_minus_opp": margin,
        "overtime": overtime,
        "winning_streak_after_game": 0,
        "losing_streak_after_game": 0,
        "opponent_is_conference_leader": False,
    }

    results_root: Dict[str, Any] = {}
    if isinstance(franchise_doc, dict):
        raw = franchise_doc.get("results")
        if isinstance(raw, dict):
            results_root = raw

    ut = str(user_team_id)
    ot = str(opponent_team_id)
    outcomes: List[bool] = []
    for wk in range(1, max(int(week), 1)):
        r = _user_game_for_week(results_root, wk, ut)
        if not r:
            continue
        o = _outcome_for_user(r, ut)
        if o is not None:
            outcomes.append(o)
    if user_won:
        outcomes.append(True)
    else:
        outcomes.append(False)

    win_streak, loss_streak = _streaks_after_sequence(outcomes)
    ctx["winning_streak_after_game"] = win_streak
    ctx["losing_streak_after_game"] = loss_streak

    sw, sl = _series_vs_opponent_before_week(results_root, ut, ot, int(week))
    if user_won:
        sw += 1
    else:
        sl += 1
    ctx["season_series_vs_opponent"] = {"w": sw, "l": sl}

    wk = int(week)
    ctx["first_game_of_season"] = wk == 1
    ctx["last_regular_season_game"] = wk == _REGULAR_SEASON_WEEKS

    w_before, l_before = _record_through_weeks(results_root, ut, wk)
    w_after, l_after = w_before, l_before
    if user_won:
        w_after += 1
    else:
        l_after += 1
    ctx["above_500_first_time_season"] = (w_after > l_after) and (w_before <= l_before) and (
        w_after + l_after
    ) > 0
    ctx["fell_below_500"] = (w_after < l_after) and (w_before >= l_before) and (w_before + l_before) > 0

    fid_for_db = franchise_id
    if isinstance(franchise_doc, dict) and franchise_doc.get("_id") is not None:
        fid_for_db = str(franchise_doc["_id"])
    ctx["franchise_id"] = str(fid_for_db or ctx.get("franchise_id") or "")

    if attach_db_fields and fid_for_db:
        attach_pgpc_rank_and_player_rt(ctx, fid_for_db, game_doc)

    return ctx  # type: ignore[return-value]


__all__ = [
    "attach_pgpc_rank_and_player_rt",
    "build_franchise_context_for_pgpc",
    "_team_blob_from_game_doc",
]
