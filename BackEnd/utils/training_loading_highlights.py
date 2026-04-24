"""Archetyped loading-feed copy for franchise training (see Training_System_Live_Feed.md)."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from BackEnd.utils import training_feed_lines as tfl
from BackEnd.utils.franchise_coaching_focus_counts import (
    COACHING_FOCUS_FTD_COUNT_KEYS,
    _COACHING_FOCUS_ARCHETYPE_TO_FTD_SUBKEY,
)

_MAX_LINES = 36
_GENERIC_FRACTION = 0.25
_WEIGHT_SESSION = 0.70
_WEIGHT_LEAD = 0.15
_WEIGHT_COMBO = 0.15

_PLAYER_ATTR_POOLS: Dict[str, Tuple[Mapping[str, Sequence[str]], Mapping[str, Sequence[str]]]] = {
    "SC": (tfl.SC_POSITIVE, tfl.SC_NEGATIVE),
    "SH": (tfl.SH_POSITIVE, tfl.SH_NEGATIVE),
    "ID": (tfl.ID_POSITIVE, tfl.ID_NEGATIVE),
    "OD": (tfl.OD_POSITIVE, tfl.OD_NEGATIVE),
    "PS": (tfl.PS_POSITIVE, tfl.PS_NEGATIVE),
    "BH": (tfl.BH_POSITIVE, tfl.BH_NEGATIVE),
    "RB": (tfl.RB_POSITIVE, tfl.RB_NEGATIVE),
    "ST": (tfl.ST_POSITIVE, tfl.ST_NEGATIVE),
    "AG": (tfl.AG_POSITIVE, tfl.AG_NEGATIVE),
    "ND": (tfl.ND_POSITIVE, tfl.ND_NEGATIVE),
    "IQ": (tfl.IQ_POSITIVE, tfl.IQ_NEGATIVE),
    "FT": (tfl.FT_POSITIVE, tfl.FT_NEGATIVE),
}

_TEAM_ATTR_POOLS: Dict[str, Tuple[Mapping[str, Sequence[str]], Mapping[str, Sequence[str]]]] = {
    "offensive_efficiency": (tfl.TEAM_OFFENSE_INSTALL_POSITIVE, tfl.TEAM_OFFENSE_INSTALL_NEGATIVE),
    "defensive_efficiency": (tfl.TEAM_DEFENSE_INSTALL_POSITIVE, tfl.TEAM_DEFENSE_INSTALL_NEGATIVE),
    "fb_efficiency": (tfl.TEAM_FASTBREAK_INSTALL_POSITIVE, tfl.TEAM_FASTBREAK_INSTALL_NEGATIVE),
    "pt_efficiency": (tfl.TEAM_PRESS_TRAP_INSTALL_POSITIVE, tfl.TEAM_PRESS_TRAP_INSTALL_NEGATIVE),
    "fb_opp_modifier": (tfl.TEAM_FASTBREAK_INSTALL_POSITIVE, tfl.TEAM_FASTBREAK_INSTALL_NEGATIVE),
    "pt_opp_modifier": (tfl.TEAM_PRESS_TRAP_INSTALL_POSITIVE, tfl.TEAM_PRESS_TRAP_INSTALL_NEGATIVE),
}


def _to_int_delta(raw: Any) -> Optional[int]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return None


def _is_freshman_year(year_raw: Any) -> bool:
    return str(year_raw or "").strip().lower() == "freshman"


def _player_attr_delta_qualifies_for_feed(d: int, *, is_freshman: bool) -> bool:
    """Match Training_System_Live_Feed.md: default ±3 band excluded; freshman ±4 band excluded."""
    if is_freshman:
        return d > 4 or d < -4
    return d > 3 or d < -3


def _session_archetype_to_pool_key(archetype: Optional[str]) -> str:
    if not archetype:
        return "generic"
    sub = _COACHING_FOCUS_ARCHETYPE_TO_FTD_SUBKEY.get(str(archetype).strip())
    if sub:
        return sub
    return "generic"


def _lead_archetype_from_ftd(counts: Mapping[str, Any]) -> str:
    vals = {k: int(counts.get(k, 0) or 0) for k in COACHING_FOCUS_FTD_COUNT_KEYS}
    max_v = max(vals.values()) if vals else 0
    leaders = [k for k, v in vals.items() if v == max_v]
    return random.choice(leaders)


def _combo_archetype_from_ftd(counts: Mapping[str, Any]) -> Optional[str]:
    rated = sorted(
        ((k, int(counts.get(k, 0) or 0)) for k in COACHING_FOCUS_FTD_COUNT_KEYS),
        key=lambda t: (-t[1], t[0]),
    )
    if len(rated) < 3:
        return None
    _first, second, third = rated[0], rated[1], rated[2]
    if second[1] > third[1] + 3:
        return second[0]
    return None


def _pick_voice_key(session_key: str, lead_key: str, combo_key: Optional[str]) -> str:
    if random.random() < _GENERIC_FRACTION:
        return "generic"
    if combo_key is None:
        return session_key if random.random() < _WEIGHT_SESSION else lead_key
    r = random.random()
    if r < _WEIGHT_SESSION:
        return session_key
    if r < _WEIGHT_SESSION + _WEIGHT_LEAD:
        return lead_key
    return combo_key


def _choose_line_from_pool(pool: Mapping[str, Sequence[str]], voice: str) -> str:
    lines = list(pool.get(voice) or pool.get("generic") or ())
    if not lines:
        return ""
    return random.choice(lines)


def _finalize_sentence(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    if s[-1] in ".!?":
        return s
    return f"{s}."


def build_training_loading_highlights(
    training_report: Mapping[str, Any] | None,
    *,
    ftd_coaching_focus: Mapping[str, int] | None = None,
) -> List[str]:
    """
    Build loading-screen lines from training report + FTD archetype counters.

    ``training_report`` may include ``ftd_coaching_focus``; ``ftd_coaching_focus`` kwarg overrides.
    ``team_drills`` (breaks / scrimmages points) may be stored on the report for this week.
    """
    if not training_report:
        return []

    counts: MutableMapping[str, int] = {}
    raw_ftd = ftd_coaching_focus if ftd_coaching_focus is not None else training_report.get("ftd_coaching_focus")
    if isinstance(raw_ftd, dict):
        for k in COACHING_FOCUS_FTD_COUNT_KEYS:
            try:
                counts[k] = int(raw_ftd.get(k, 0) or 0)
            except (TypeError, ValueError):
                counts[k] = 0
    else:
        for k in COACHING_FOCUS_FTD_COUNT_KEYS:
            counts[k] = 0

    cf = training_report.get("coaching_focus") or {}
    session_arch = cf.get("archetype") if isinstance(cf, dict) else None
    session_key = _session_archetype_to_pool_key(session_arch if isinstance(session_arch, str) else None)
    lead_key = _lead_archetype_from_ftd(counts)
    combo_key = _combo_archetype_from_ftd(counts)

    flavor_voice = _pick_voice_key(session_key, lead_key, combo_key)
    flavor = _finalize_sentence(_choose_line_from_pool(tfl.COACHING_FOCUS_FLAVOR, flavor_voice))

    body: List[str] = []

    player_logs = training_report.get("player_logs") or training_report.get("player_changes") or {}
    if isinstance(player_logs, dict):
        for player_name in sorted(player_logs.keys(), key=lambda k: str(k).lower()):
            changes = player_logs.get(player_name)
            if not isinstance(changes, dict):
                continue
            name = str(player_name).strip()
            if not name:
                continue
            is_fr = _is_freshman_year(changes.get("year"))
            for attr, pools in _PLAYER_ATTR_POOLS.items():
                d = _to_int_delta(changes.get(attr))
                if d is None:
                    continue
                if not _player_attr_delta_qualifies_for_feed(d, is_freshman=is_fr):
                    continue
                voice = _pick_voice_key(session_key, lead_key, combo_key)
                pos_pool, neg_pool = pools
                pos_cut = 4 if is_fr else 3
                if d > pos_cut:
                    frag = _choose_line_from_pool(pos_pool, voice)
                else:
                    frag = _choose_line_from_pool(neg_pool, voice)
                if not frag:
                    continue
                body.append(_finalize_sentence(f"{name} {frag}".strip()))

    team_log = training_report.get("team_log") or training_report.get("team_changes") or {}
    if isinstance(team_log, dict):
        for attr, pools in _TEAM_ATTR_POOLS.items():
            d = _to_int_delta(team_log.get(attr))
            if d is None:
                continue
            if d <= 3 and d >= -3:
                continue
            voice = _pick_voice_key(session_key, lead_key, combo_key)
            pos_pool, neg_pool = pools
            if d > 3:
                line = _choose_line_from_pool(pos_pool, voice)
            else:
                line = _choose_line_from_pool(neg_pool, voice)
            if line:
                body.append(_finalize_sentence(line))

    team_drills = training_report.get("team_drills") or {}
    if isinstance(team_drills, dict):
        scr = team_drills.get("scrimmages")
        br = team_drills.get("breaks")
        if _to_int_delta(scr) is not None and int(scr) > 0:
            voice = _pick_voice_key(session_key, lead_key, combo_key)
            line = _choose_line_from_pool(tfl.TEAM_SCRIMMAGES_POSITIVE, voice)
            if line:
                body.append(_finalize_sentence(line))
        if _to_int_delta(br) is not None and int(br) > 0:
            voice = _pick_voice_key(session_key, lead_key, combo_key)
            line = _choose_line_from_pool(tfl.TEAM_BREAKS_POSITIVE, voice)
            if line:
                body.append(_finalize_sentence(line))

    random.shuffle(body)

    out: List[str] = []
    if flavor:
        out.append(flavor)
    out.extend(body)

    seen: set[str] = set()
    unique: List[str] = []
    for line in out:
        if not line or line in seen:
            continue
        seen.add(line)
        unique.append(line)
    return unique[:_MAX_LINES]
