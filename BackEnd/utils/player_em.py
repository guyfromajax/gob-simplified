"""Player Emotion (EM) week-to-week rules.

FPD ``attributes.EM`` (1–100) is the franchise source of truth. Training applies
focus + breaks as two independent per-player rolls then clamps. EOG applies one
per-player roll from RT / box minutes / CH and writes FPD. Franchise game init
seeds from FPD EM (see ``Player.randomize_game_attributes(preserve_emotion=True)``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from BackEnd.persistence import get_store
_store = get_store()
db = _store.db
franchise_players_data_collection = _store.franchise_players_data_collection

logger = logging.getLogger(__name__)

EM_MIN = 1
EM_MAX = 100

# Coaching-focus EM bands. None = this leaf does not move EM.
_FOCUS_EM_BANDS: Dict[str, Optional[Tuple[int, int]]] = {
    "culture-builder-inspire": (2, 5),
    "culture-builder-community": (2, 5),
    "culture-builder-confidence": (0, 2),
    "culture-builder-teamwork": None,  # Team Building
    "authoritarian-discipline": (-5, 0),
    "authoritarian-execution": (-3, 0),
    "authoritarian-rebounding": None,
    "authoritarian-teamwork": None,
}

_SYSTEMS_COACH_EM_BAND = (-2, 0)
_PLAYER_MAXIMIZER_EM_BAND = (0, 2)

# RT > 69 / 50–69 / ≤49 × minutes >19 / 15–19 / else × CH >69 / 40–69 / <40
_EOG_EM_BANDS: Dict[str, Dict[str, Dict[str, Tuple[int, int]]]] = {
    "star": {  # RT > 69
        "hi": {"hi": (2, 5), "mid": (2, 4), "lo": (1, 4)},
        "mid": {"hi": (0, 1), "mid": (-1, 1), "lo": (-1, 0)},
        "lo": {"hi": (-5, -2), "mid": (-6, -3), "lo": (-7, -3)},
    },
    "mid": {  # RT 50–69
        "hi": {"hi": (1, 3), "mid": (1, 2), "lo": (0, 2)},
        "mid": {"hi": (0, 1), "mid": (-1, 1), "lo": (-1, 0)},
        "lo": {"hi": (-2, 0), "mid": (-3, -1), "lo": (-4, -1)},
    },
    "low": {  # RT ≤ 49
        "hi": {"hi": (3, 7), "mid": (2, 6), "lo": (2, 5)},
        "mid": {"hi": (2, 5), "mid": (2, 4), "lo": (2, 3)},
        "lo": {"hi": (-1, 0), "mid": (-1, 0), "lo": (-2, 0)},
    },
}


def clamp_em(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = EM_MIN
    return max(EM_MIN, min(EM_MAX, n))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def roster_rt(player_doc: Optional[dict]) -> int:
    """Max position_ratings value on an FPD (or equivalent) player doc."""
    ratings = (player_doc or {}).get("position_ratings") or {}
    best = 0
    for value in ratings.values() if isinstance(ratings, dict) else ():
        rating = _safe_int(value, 0)
        if rating > best:
            best = rating
    return best


def box_minutes(raw_min: Any) -> int:
    """Displayed box-score minutes: floor(seconds / 60). DNP / missing → 0."""
    seconds = _safe_int(raw_min, 0)
    if seconds < 0:
        seconds = 0
    return seconds // 60


def training_focus_em_delta(sub_option: Optional[str], rng) -> int:
    """Independent coaching-focus EM roll for one player. 0 when the leaf has no EM band."""
    band = _focus_em_band(sub_option)
    if band is None:
        return 0
    lo, hi = band
    return int(rng.randint(lo, hi))


def _focus_em_band(sub_option: Optional[str]) -> Optional[Tuple[int, int]]:
    if not sub_option:
        return None
    if sub_option in _FOCUS_EM_BANDS:
        return _FOCUS_EM_BANDS[sub_option]
    if sub_option.startswith("systems-coach-"):
        return _SYSTEMS_COACH_EM_BAND
    if sub_option.startswith("player-maximizer-"):
        return _PLAYER_MAXIMIZER_EM_BAND
    return None


def training_breaks_em_delta(points: Any, rng) -> int:
    """Independent breaks-slider EM roll for one player. Missing points → 0."""
    try:
        n = int(points)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        lo, hi = (-5, -3)
    elif n < 2:
        lo, hi = (-2, 0)
    elif n == 2:
        lo, hi = (0, 2)
    else:
        lo, hi = (2, 5)
    return int(rng.randint(lo, hi))


def apply_training_em(
    players: Iterable[dict],
    sub_option: Optional[str],
    breaks_points: Any,
    rng,
) -> None:
    """Add focus + breaks EM rolls per player, then clamp 1–100. Mutates player dicts.

    Does not write training-report change rows; callers keep EM off TRAINABLE_PLAYER_ATTRS.
    """
    for player in players:
        attrs = player.get("attributes")
        if not isinstance(attrs, dict):
            continue
        current = _safe_int(attrs.get("EM"), EM_MIN)
        focus_delta = training_focus_em_delta(sub_option, rng)
        breaks_delta = training_breaks_em_delta(breaks_points, rng)
        new_em = clamp_em(current + focus_delta + breaks_delta)
        attrs["EM"] = new_em
        attrs["anchor_EM"] = new_em


def _rt_tier(rt: int) -> str:
    if rt > 69:
        return "star"
    if rt > 49:
        return "mid"
    return "low"


def _minutes_tier(minutes: int) -> str:
    if minutes > 19:
        return "hi"
    if minutes > 14:
        return "mid"
    return "lo"


def _ch_tier(ch: int) -> str:
    if ch > 69:
        return "hi"
    if ch >= 40:
        return "mid"
    return "lo"


def eog_em_delta(rt: int, minutes: int, ch: int, rng) -> int:
    """One EOG EM roll for one player from roster RT, displayed minutes, and FPD CH."""
    band = _EOG_EM_BANDS[_rt_tier(_safe_int(rt))][_minutes_tier(_safe_int(minutes))][
        _ch_tier(_safe_int(ch))
    ]
    return int(rng.randint(band[0], band[1]))


def _player_id_from_game_row(row: dict) -> str:
    return str(row.get("playerId") or row.get("player_id") or "")


def _minutes_from_game_row(row: dict) -> int:
    stats = row.get("stats") or {}
    if not isinstance(stats, dict):
        stats = {}
    raw = stats.get("MIN")
    if raw is None:
        raw = row.get("MIN")
    return box_minutes(raw)


def _load_game_candidates(games_col, game_id) -> List[dict]:
    from bson import ObjectId

    seen: set[str] = set()
    out: List[dict] = []

    def _add(doc: Optional[dict]) -> None:
        if not isinstance(doc, dict):
            return
        key = str(doc.get("_id"))
        if key in seen:
            return
        seen.add(key)
        out.append(doc)

    gid_str = str(game_id)
    _add(games_col.find_one({"_id": gid_str}))
    try:
        oid = game_id if isinstance(game_id, ObjectId) else ObjectId(gid_str)
        _add(games_col.find_one({"_id": oid}))
    except Exception:
        pass
    if not isinstance(game_id, str):
        _add(games_col.find_one({"_id": game_id}))
    return out


def _richest_game_doc(candidates: List[dict]) -> Optional[dict]:
    if not candidates:
        return None
    return max(candidates, key=lambda d: len(d.get("players") or []))


def apply_franchise_eog_player_em(
    game_id: Any,
    franchise_id: Any,
    *,
    games_col=None,
    fpd_col=None,
    rng=None,
) -> int:
    """Write FPD EM from this franchise game's box minutes. Idempotent per game doc.

    Returns the number of FPD players updated. Skips practice-squad games and a
    second pass once ``player_em_eog_applied`` is set.
    """
    if rng is None:
        import random as rng  # EOG uses the global stream, same as team-attr EOG.

    if games_col is None or fpd_col is None:

        if games_col is None:
            games_col = db.games
        if fpd_col is None:
            fpd_col = franchise_players_data_collection

    candidates = _load_game_candidates(games_col, game_id)
    if not candidates:
        logger.warning("[PLAYER-EM-EOG] No game doc for game_id=%s", str(game_id))
        return 0
    if any(bool(d.get("player_em_eog_applied")) for d in candidates):
        return 0

    game_doc = _richest_game_doc(candidates) or {}
    if (game_doc.get("mode") or "") == "practice_squad":
        return 0

    rows = game_doc.get("players") or []
    if not isinstance(rows, list) or not rows:
        logger.warning("[PLAYER-EM-EOG] Game %s has no players list", str(game_id))
        _mark_player_em_eog_applied(games_col, candidates)
        return 0

    minutes_by_pid: Dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = _player_id_from_game_row(row)
        if not pid:
            continue
        minutes_by_pid[pid] = _minutes_from_game_row(row)

    pids = list(minutes_by_pid.keys())
    if not pids:
        _mark_player_em_eog_applied(games_col, candidates)
        return 0

    fid_str = str(franchise_id)
    fid_candidates: List[Any] = [fid_str]
    try:
        from bson import ObjectId

        fid_candidates.append(ObjectId(fid_str))
    except Exception:
        pass
    if franchise_id not in fid_candidates:
        fid_candidates.append(franchise_id)

    fpd_docs = list(
        fpd_col.find(
            {"franchise_id": {"$in": fid_candidates}, "player_id": {"$in": pids}},
            {"player_id": 1, "attributes": 1, "position_ratings": 1, "franchise_id": 1},
        )
    )
    fpd_by_pid = {str(d.get("player_id")): d for d in fpd_docs if d.get("player_id")}

    from pymongo import UpdateOne

    ops: List[UpdateOne] = []
    updated = 0
    for pid, minutes in minutes_by_pid.items():
        doc = fpd_by_pid.get(pid)
        if not doc:
            continue
        attrs = doc.get("attributes") if isinstance(doc.get("attributes"), dict) else {}
        current = _safe_int(attrs.get("EM"), EM_MIN)
        ch = _safe_int(attrs.get("CH"), 0)
        rt = roster_rt(doc)
        new_em = clamp_em(current + eog_em_delta(rt, minutes, ch, rng))
        ops.append(
            UpdateOne(
                {"franchise_id": doc.get("franchise_id", fid_str), "player_id": pid},
                {"$set": {"attributes.EM": new_em, "attributes.anchor_EM": new_em}},
            )
        )
        updated += 1

    if ops:
        fpd_col.bulk_write(ops, ordered=False)

    _mark_player_em_eog_applied(games_col, candidates)
    logger.info(
        "[PLAYER-EM-EOG] game_id=%s franchise_id=%s updated=%s",
        str(game_id),
        fid_str,
        updated,
    )
    return updated


def _mark_player_em_eog_applied(games_col, candidates: List[dict]) -> None:
    for doc in candidates:
        gid = doc.get("_id")
        if gid is None:
            continue
        games_col.update_one({"_id": gid}, {"$set": {"player_em_eog_applied": True}})
