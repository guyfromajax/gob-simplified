"""
Resolve home/away identifiers on a game document to the keys used in ``game["teams"]``.

DB fields ``home_team_id`` / ``away_team_id`` may be legacy slugs or names while
``teams`` is keyed by canonical Mongo team ids. Summarize and enrichment use the
latter; GET /api/game must emit ids that match ``teams`` keys so clients can index
``teams[home_team_id]`` (rank, record, fouls, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _norm_slot(s: Any) -> str:
    if s is None:
        return ""
    return str(s).upper().replace(" ", "_").replace("-", "_")


def _find_teams_dict_key(
    teams_obj: Dict[Any, Any],
    stored_id: Any,
    legacy_blob: Any,
) -> Optional[Any]:
    if not isinstance(teams_obj, dict) or not teams_obj:
        return None

    if stored_id is not None and stored_id != "":
        sid = str(stored_id)
        for k in teams_obj:
            if k == stored_id or str(k) == sid:
                return k
        for k, row in teams_obj.items():
            if not isinstance(row, dict):
                continue
            tid = row.get("team_id")
            if tid is not None and str(tid) == sid:
                return k
            nm = row.get("name")
            if nm:
                if str(nm) == sid or _norm_slot(nm) == _norm_slot(sid):
                    return k

    if isinstance(legacy_blob, dict):
        lname = legacy_blob.get("name")
        if lname:
            for k, row in teams_obj.items():
                if isinstance(row, dict) and row.get("name") == lname:
                    return k
    return None


def resolve_home_away_teams_slot_keys(saved: dict) -> Tuple[Any, Any]:
    """
    Return (home_key, away_key) suitable for indexing ``saved["teams"]``.

    Falls back to stored ``home_team_id`` / ``away_team_id`` when resolution fails.
    """
    hid_orig = saved.get("home_team_id")
    aid_orig = saved.get("away_team_id")
    teams_obj = saved.get("teams") or {}
    if not isinstance(teams_obj, dict) or not teams_obj:
        return hid_orig, aid_orig

    leg_h = saved.get("home_team")
    leg_a = saved.get("away_team")

    home_key = _find_teams_dict_key(teams_obj, hid_orig, leg_h)
    away_key = _find_teams_dict_key(teams_obj, aid_orig, leg_a)

    keys = list(teams_obj.keys())
    if home_key is None and len(keys) == 2 and away_key is not None:
        home_key = next((k for k in keys if k != away_key), None)
    elif away_key is None and len(keys) == 2 and home_key is not None:
        away_key = next((k for k in keys if k != home_key), None)
    elif home_key is None and away_key is None and len(keys) == 2:
        hname = leg_h.get("name") if isinstance(leg_h, dict) else None
        aname = leg_a.get("name") if isinstance(leg_a, dict) else None
        if hname:
            for k, row in teams_obj.items():
                if isinstance(row, dict) and row.get("name") == hname:
                    home_key = k
                    break
        if aname:
            for k, row in teams_obj.items():
                if isinstance(row, dict) and row.get("name") == aname:
                    away_key = k
                    break

    if home_key is not None and away_key is not None and home_key == away_key:
        return hid_orig, aid_orig

    return (
        home_key if home_key is not None else hid_orig,
        away_key if away_key is not None else aid_orig,
    )
