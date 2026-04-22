"""
Structured Training Report notes per Training_Notes_System.md.

Produces a list of {title, body} sections. Player Energy Levels reuses legacy
conditioning/scrimmage strings from apply_training_points.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import random

from BackEnd.constants import ALL_ATTRS

TRAINABLE_ATTRS_FOR_NOTES = tuple(a for a in ALL_ATTRS if a not in ["EM", "MO", "NG", "CH"])

NSS = "No Significant Updates"


def _player_name(p: Dict) -> str:
    n = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    return n or str(p.get("_id", ""))


def _player_id(p: Dict) -> str:
    return str(p.get("_id", "") or "")


def _anchor_val(attrs: Dict, code: str) -> int:
    v = attrs.get(f"anchor_{code}", attrs.get(code, 0))
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _ch_post(p: Dict) -> int:
    return _anchor_val(p.get("attributes") or {}, "CH")


def _cumulative_delta(p: Dict, baselines_by_id: Dict[Any, Dict[str, int]]) -> int:
    pid = p.get("_id")
    base = baselines_by_id.get(pid) or {}
    attrs = p.get("attributes") or {}
    total = 0
    for attr in TRAINABLE_ATTRS_FOR_NOTES:
        old_v = base.get(attr, 0)
        try:
            old_v = int(old_v)
        except (TypeError, ValueError):
            old_v = 0
        total += _anchor_val(attrs, attr) - old_v
    return total


def _team_attr_delta_sums(players: List[dict], baselines_by_id: Dict[Any, Dict[str, int]]) -> Dict[str, int]:
    sums: Dict[str, int] = {}
    for attr in TRAINABLE_ATTRS_FOR_NOTES:
        s = 0
        for p in players:
            pid = p.get("_id")
            base = baselines_by_id.get(pid) or {}
            try:
                old_v = int(base.get(attr, 0) or 0)
            except (TypeError, ValueError):
                old_v = 0
            s += _anchor_val(p.get("attributes") or {}, attr) - old_v
        sums[attr] = s
    return sums


def _mvp_discounted_total(player: Dict, baselines_by_id: Dict[Any, Dict[str, int]]) -> float:
    total = float(_cumulative_delta(player, baselines_by_id))
    year = str(player.get("year", "") or "").strip().lower()
    if year == "freshman":
        return total * 0.7
    if year == "sophomore":
        return total * 0.9
    return total


def _readiness_label(s: float) -> str:
    if s > 11:
        return "Very Strong"
    if 4 <= s <= 11:
        return "Strong"
    if -3 <= s <= 3:
        return "Neutral"
    if -11 <= s <= -4:
        return "Weak"
    if s < -11:
        return "Very Weak"
    # Float edge gaps (e.g. between 3 and 4)
    if s > 3:
        return "Strong"
    if s < -3:
        return "Weak"
    return "Neutral"


def _offensive_play_selection(plays_data: Dict) -> List[str]:
    rows: List[Tuple[str, float]] = []
    for name, pdata in (plays_data or {}).items():
        if not isinstance(pdata, dict):
            continue
        eff = pdata.get("effectiveness", 0)
        try:
            eff = float(eff)
        except (TypeError, ValueError):
            eff = 0.0
        rows.append((name, eff))
    if not rows:
        return []
    rows.sort(key=lambda x: (-x[1], x[0]))
    tiers: List[List[str]] = []
    cur_eff: float | None = None
    tier: List[str] = []
    for name, eff in rows:
        if cur_eff is None or eff != cur_eff:
            if tier:
                tiers.append(tier)
            tier = [name]
            cur_eff = eff
        else:
            tier.append(name)
    if tier:
        tiers.append(tier)
    listed: List[str] = []
    for names in tiers:
        if len(listed) + len(names) > 3:
            continue
        listed.extend(names)
    return listed


def _top_defense_names(scouting_data: Dict) -> List[str]:
    defense = (scouting_data or {}).get("defense") or {}
    if not defense:
        return []
    best: float | None = None
    out: List[str] = []
    for dname, ddata in defense.items():
        if not isinstance(ddata, dict):
            continue
        eff = ddata.get("effectiveness", 0)
        try:
            eff = float(eff)
        except (TypeError, ValueError):
            eff = 0.0
        if best is None or eff > best:
            best = eff
            out = [dname]
        elif best is not None and eff == best:
            out.append(dname)
    return sorted(out)


def _locker_room_body(players: List[dict]) -> str:
    eligible = [p for p in players if _ch_post(p) > 59]
    if not eligible:
        return "None"
    weights = [2 if _ch_post(p) > 79 else 1 for p in eligible]
    picked = random.choices(eligible, weights=weights, k=1)[0]
    return _player_name(picked)


def _locker_room_note(players: List[dict]) -> Dict[str, Any]:
    eligible = [p for p in players if _ch_post(p) > 59]
    if not eligible:
        return {"title": "Most Positive Locker Room Influence", "body": "None"}
    weights = [2 if _ch_post(p) > 79 else 1 for p in eligible]
    picked = random.choices(eligible, weights=weights, k=1)[0]
    player_id = _player_id(picked)
    note: Dict[str, Any] = {
        "title": "Most Positive Locker Room Influence",
        "body": _player_name(picked),
    }
    if player_id:
        note["player_id"] = player_id
        note["player_ids"] = [player_id]
    return note


def _note_with_player_ids(title: str, names: List[str], players_by_name: Dict[str, Dict[str, Any]], empty_body: str) -> Dict[str, Any]:
    note: Dict[str, Any] = {"title": title}
    if not names:
        note["body"] = empty_body
        return note
    note["body"] = ", ".join(names)
    player_ids = [_player_id(players_by_name[name]) for name in names if name in players_by_name and _player_id(players_by_name[name])]
    if player_ids:
        note["player_ids"] = player_ids
        if len(player_ids) == 1:
            note["player_id"] = player_ids[0]
    return note


def build_structured_training_report_notes(
    *,
    is_training_camp: bool,
    players: List[dict],
    original_player_baselines: Dict[Any, Dict[str, int]],
    team: dict,
    plays_data: dict,
    scouting_data: dict,
    legacy_energy_notes: List[str],
) -> List[Dict[str, Any]]:
    sections: List[Dict[str, str]] = []
    players_by_name = {_player_name(p): p for p in players}
    by_name = { _player_name(p): _cumulative_delta(p, original_player_baselines) for p in players }
    discounted_by_name = { _player_name(p): _mvp_discounted_total(p, original_player_baselines) for p in players }
    sums = _team_attr_delta_sums(players, original_player_baselines)

    if is_training_camp:
        pos = [(n, t) for n, t in discounted_by_name.items() if t > 0]
        if pos:
            top = max(t for _, t in pos)
            names = sorted(n for n, t in pos if t == top)
            title = "Training Camp Co-MVPs" if len(names) > 1 else "Training Camp MVP"
            sections.append({"title": title, "body": ", ".join(names)})
        else:
            sections.append({"title": "Training Camp MVP", "body": NSS})

        under = [(n, t) for n, t in by_name.items() if t < 10]
        if not under:
            sections.append({"title": "Biggest Concern", "body": "None"})
        else:
            worst = min(t for _, t in under)
            names = sorted(n for n, t in under if t == worst)
            title = "Biggest Concerns" if len(names) > 1 else "Biggest Concern"
            sections.append({"title": title, "body": ", ".join(names)})

        sections.append(_locker_room_note(players))

        hi = sorted(a for a, s in sums.items() if s > 49)
        sections.append({"title": "Strong Cumulative Increase", "body": ", ".join(hi) if hi else NSS})

        lo = sorted(a for a, s in sums.items() if s < 21)
        sections.append({"title": "Concerning Progression", "body": ", ".join(lo) if lo else NSS})
    else:
        pos = [(n, t) for n, t in discounted_by_name.items() if t > 0]
        if pos:
            top = max(t for _, t in pos)
            names = sorted(n for n, t in pos if t == top)
            title = "Practice Players Of The Week" if len(names) > 1 else "Practice Player Of The Week"
            sections.append(_note_with_player_ids(title, names, players_by_name, NSS))
        else:
            sections.append({"title": "Practice Player Of The Week", "body": NSS})

        neg = [(n, t) for n, t in by_name.items() if t < 0]
        if not neg:
            sections.append({"title": "Biggest Regression", "body": "None"})
        else:
            worst = min(t for _, t in neg)
            names = sorted(n for n, t in neg if t == worst)
            sections.append(_note_with_player_ids("Biggest Regression", names, players_by_name, "None"))

        sections.append(_locker_room_note(players))

        hi = sorted(a for a, s in sums.items() if s >= 10)
        sections.append({"title": "Strong Cumulative Increase", "body": ", ".join(hi) if hi else NSS})

        lo = sorted(a for a, s in sums.items() if s <= -10)
        sections.append({"title": "Concerning Regression", "body": ", ".join(lo) if lo else NSS})

    plays_pick = _offensive_play_selection(plays_data)
    sections.append({
        "title": "Strongest Offensive Plays",
        "body": ", ".join(plays_pick) if plays_pick else NSS,
    })

    defs = _top_defense_names(scouting_data)
    sections.append({
        "title": "Strongest Defensive Set",
        "body": ", ".join(defs) if defs else NSS,
    })

    fb = float(team.get("fb_efficiency", 0) or 0) + float(team.get("fb_opp_modifier", 0) or 0)
    sections.append({"title": "Fast Break Readiness", "body": _readiness_label(fb)})

    pt = float(team.get("pt_efficiency", 0) or 0) + float(team.get("pt_opp_modifier", 0) or 0)
    sections.append({"title": "Press/Trap Readiness", "body": _readiness_label(pt)})

    if legacy_energy_notes:
        energy_body = "\n\n".join(legacy_energy_notes)
    else:
        energy_body = NSS
    sections.append({"title": "Player Energy Levels", "body": energy_body})

    return sections
