from __future__ import annotations

import copy
import logging
import random
from dataclasses import dataclass
from typing import Any, Iterable

from bson import ObjectId


CORE_MOTION_PLAY_NAMES = ("5-0 Motion", "4-1 Motion", "3-2 Motion")
PF_POST_MOTION_PLAY_NAME = "PF Post Motion"
FOCUSES = ("inside", "attack", "outside")
POSITIONS = ("PG", "SG", "SF", "PF", "C")

GROUP_BUILD_UPDATE_WEEKS = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    11: 1,
    12: 2,
    13: 3,
    14: 4,
    15: 5,
    21: 1,
    22: 2,
    23: 3,
    24: 4,
    25: 5,
}

MOTION_NAME_BY_FOCUS = {
    "attack": "5-0 Motion",
    "outside": "4-1 Motion",
    "inside": "3-2 Motion",
}


@dataclass(frozen=True)
class CpuPlaybookBuildResult:
    playbook_settings: dict[str, Any]
    plays: dict[str, Any]


def build_user_schedule_cpu_playbook_groups(
    schedule: list,
    user_team_id: Any,
) -> dict[str, Any]:
    """Build ordered unique user opponents and stagger them into groups of four."""
    if not user_team_id:
        return {"ordered_opponents": [], "groups": {}}

    uid = str(user_team_id)
    ordered: list[str] = []
    seen: set[str] = set()

    for week_games in schedule or []:
        for pair in week_games or []:
            if not pair or len(pair) < 2:
                continue
            away_id, home_id = str(pair[0]), str(pair[1])
            opponent_id = None
            if away_id == uid:
                opponent_id = home_id
            elif home_id == uid:
                opponent_id = away_id
            if opponent_id and opponent_id not in seen:
                seen.add(opponent_id)
                ordered.append(opponent_id)

    groups = {
        str(idx + 1): ordered[idx * 4 : (idx + 1) * 4]
        for idx in range(5)
        if ordered[idx * 4 : (idx + 1) * 4]
    }
    return {"ordered_opponents": ordered, "groups": groups}


def group_for_cpu_playbook_week(week: int) -> int | None:
    try:
        return GROUP_BUILD_UPDATE_WEEKS.get(int(week))
    except (TypeError, ValueError):
        return None


def _attrs(player: Any) -> dict:
    attrs = getattr(player, "attributes", None)
    if isinstance(attrs, dict):
        return attrs
    if isinstance(player, dict):
        return player.get("attributes") or {}
    return {}


def _attr(player: Any, key: str) -> float:
    attrs = _attrs(player)
    try:
        return float(attrs.get(f"anchor_{key}", attrs.get(key, 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


def _position_rating(player: Any, pos: str) -> float:
    ratings = getattr(player, "position_ratings", None)
    if not isinstance(ratings, dict) and isinstance(player, dict):
        ratings = player.get("position_ratings") or {}
    try:
        return float((ratings or {}).get(pos) or 0)
    except (TypeError, ValueError):
        return 0.0


def _position_players_from_team(team: Any) -> dict[str, Any]:
    lineup = getattr(team, "lineup", None) or {}
    players = {pos: lineup.get(pos) for pos in POSITIONS if lineup.get(pos) is not None}
    if len(players) == 5:
        return players

    candidates = list((getattr(team, "players", None) or {}).values())
    assigned: set[str] = set()
    for pos in POSITIONS:
        if pos in players:
            pid = str(getattr(players[pos], "player_id", "") or "")
            if pid:
                assigned.add(pid)
            continue
        best = None
        for player in candidates:
            pid = str(getattr(player, "player_id", "") or "")
            if pid and pid in assigned:
                continue
            rating = _position_rating(player, pos)
            if best is None or rating > best[0]:
                best = (rating, player, pid)
        if best:
            players[pos] = best[1]
            if best[2]:
                assigned.add(best[2])
    return players


def _classify_focus_strengths(position_players: dict[str, Any]) -> dict[str, str]:
    five = [position_players.get(pos) for pos in POSITIONS if position_players.get(pos) is not None]
    if len(five) < 5:
        return {focus: "neutral" for focus in FOCUSES}

    scores = {
        "inside": sum(_attr(player, "SC") for player in five),
        "outside": sum(_attr(player, "SH") for player in five),
        "attack": (sum(_attr(player, "SC") for player in five) + sum(_attr(player, "AG") for player in five)) / 2.0,
    }
    ranked = sorted(scores, key=lambda k: scores[k])
    lowest_k, middle_k, highest_k = ranked[0], ranked[1], ranked[2]
    middle_v = scores[middle_k]
    strong_k = highest_k if (scores[highest_k] - 70 > middle_v) else None
    weak_k = lowest_k if (scores[lowest_k] + 70 < middle_v) else None

    out = {focus: "neutral" for focus in FOCUSES}
    if strong_k:
        out[strong_k] = "strong"
    if weak_k:
        out[weak_k] = "weak"
    return out


def _motion_focus_weights(focus_strengths: dict[str, str]) -> dict[str, int]:
    weights = {focus: 2 for focus in FOCUSES}
    for focus, state in focus_strengths.items():
        if state == "strong":
            weights[focus] = 5
        elif state == "weak":
            weights[focus] = 1
    weights["balanced"] = 4
    return weights


def _weighted_choice_from_dict(weights: dict[str, int]) -> str:
    keys = list(weights.keys())
    return random.choices(keys, weights=[max(0, int(weights[k])) for k in keys], k=1)[0]


def _scoring_ability(player: Any, focus: str) -> float:
    if focus == "outside":
        return 2 * _attr(player, "SH")
    if focus == "attack":
        return _attr(player, "AG") + _attr(player, "SC")
    return _attr(player, "ST") + _attr(player, "SC")


def _target_position_weights(position_players: dict[str, Any], focus: str) -> dict[str, int]:
    weights: dict[str, int] = {}
    for pos in POSITIONS:
        ability = _scoring_ability(position_players.get(pos), focus)
        if ability > 160:
            weight = 5
        elif ability > 130:
            weight = 3
        elif ability > 100:
            weight = 2
        else:
            weight = 1
        weights[pos] = weight
    return weights


def _split_100_even(keys: Iterable[str]) -> dict[str, int]:
    keys = list(keys)
    if not keys:
        return {}
    base = 100 // len(keys)
    remainder = 100 - (base * len(keys))
    return {key: base + (1 if idx < remainder else 0) for idx, key in enumerate(keys)}


def _random_capped_three(keys: tuple[str, str, str], max_pct: int = 50) -> dict[str, int]:
    while True:
        a = random.randint(1, max_pct)
        b = random.randint(1, max_pct)
        c = 100 - a - b
        if 1 <= c <= max_pct:
            vals = [a, b, c]
            random.shuffle(vals)
            return {key: vals[idx] for idx, key in enumerate(keys)}


def _rebalance_percentages(values: dict[str, int], *, min_pct: int = 1) -> dict[str, int]:
    if not values:
        return {}
    vals = {k: max(min_pct, int(round(v))) for k, v in values.items()}
    diff = 100 - sum(vals.values())
    keys = list(vals.keys())
    idx = 0
    while diff != 0 and keys:
        key = keys[idx % len(keys)]
        if diff > 0:
            vals[key] += 1
            diff -= 1
        elif vals[key] > min_pct:
            vals[key] -= 1
            diff += 1
        idx += 1
        if idx > 1000:
            break
    return vals


def _adjust_motion_percentages(play_ids_by_name: dict[str, str], focus_strengths: dict[str, str]) -> dict[str, int]:
    percentages = _split_100_even(play_ids_by_name.values())
    for focus, motion_name in MOTION_NAME_BY_FOCUS.items():
        play_id = play_ids_by_name.get(motion_name)
        if not play_id:
            continue
        state = focus_strengths.get(focus)
        if state not in {"strong", "weak"}:
            continue
        delta = 15 if state == "strong" else -15
        others = [pid for pid in percentages if pid != play_id]
        if not others:
            continue
        percentages[play_id] = percentages.get(play_id, 0) + delta
        per_other = -delta / len(others)
        raw = {pid: pct + (per_other if pid in others else 0) for pid, pct in percentages.items()}
        percentages = _rebalance_percentages(raw, min_pct=1)
    return _rebalance_percentages(percentages, min_pct=1)


def _set_play_target_count(focus_state: str) -> int:
    if focus_state == "strong":
        return 4
    if focus_state == "weak":
        return 2
    return 3


def _selected_set_play_ids(
    existing_ids: list[str],
    set_play_ids_by_focus: dict[str, list[str]],
    focus_strengths: dict[str, str],
    *,
    update_week: bool,
) -> list[str]:
    selected = list(dict.fromkeys(existing_ids))
    if update_week:
        for focus, state in focus_strengths.items():
            if state != "strong":
                continue
            candidates = [pid for pid in set_play_ids_by_focus.get(focus, []) if pid not in selected]
            if candidates:
                selected.append(random.choice(candidates))
        return selected

    selected = []
    for focus in FOCUSES:
        candidates = list(set_play_ids_by_focus.get(focus, []))
        random.shuffle(candidates)
        selected.extend(candidates[: _set_play_target_count(focus_strengths.get(focus, "neutral"))])
    return list(dict.fromkeys(selected))


def _set_play_percentages(play_ids: list[str]) -> dict[str, int]:
    ordered = list(play_ids)
    random.shuffle(ordered)
    if not ordered:
        return {}
    if len(ordered) == 1:
        return {ordered[0]: 100}
    if len(ordered) == 2:
        return {ordered[0]: 55, ordered[1]: 45}
    if len(ordered) == 3:
        return {ordered[0]: 45, ordered[1]: 35, ordered[2]: 20}
    out = {ordered[0]: 20, ordered[1]: 15, ordered[2]: 10}
    remaining = _split_100_even(ordered[3:])
    for key, pct in remaining.items():
        out[key] = pct * 55 / 100
    return _rebalance_percentages(out, min_pct=1)


def _play_id(play_data: dict[str, Any]) -> str:
    return str(play_data.get("play_id") or play_data.get("_id") or "")


def _iter_play_items(plays: dict[str, Any]):
    for key, play in (plays or {}).items():
        if isinstance(play, dict):
            yield key, play


def build_cpu_playbook_for_team(
    team: Any,
    base_playbook_settings: dict[str, Any] | None,
    plays: dict[str, Any] | None,
    *,
    update_week: bool,
) -> CpuPlaybookBuildResult:
    """Return customized CPU playbook settings plus updated team play copies."""
    next_settings = copy.deepcopy(base_playbook_settings or {})
    next_plays = copy.deepcopy(plays or {})

    position_players = _position_players_from_team(team)
    focus_strengths = _classify_focus_strengths(position_players)
    motion_focus_weights = _motion_focus_weights(focus_strengths)

    motion_ids_by_name: dict[str, str] = {}
    set_play_ids_by_focus: dict[str, list[str]] = {focus: [] for focus in FOCUSES}
    play_key_by_id: dict[str, str] = {}

    for key, play in _iter_play_items(next_plays):
        pid = _play_id(play)
        if not pid:
            continue
        play_key_by_id[pid] = key
        if play.get("play_type") == "motion":
            if play.get("name") in CORE_MOTION_PLAY_NAMES or play.get("name") == PF_POST_MOTION_PLAY_NAME:
                motion_ids_by_name[play.get("name")] = pid
        elif play.get("play_type") == "set_play" and play.get("play_focus") in FOCUSES:
            set_play_ids_by_focus[play.get("play_focus")].append(pid)

    selected_motion_names = list(CORE_MOTION_PLAY_NAMES)
    pf = position_players.get("PF")
    if pf is not None and _position_rating(pf, "PF") > 49:
        selected_motion_names.append(PF_POST_MOTION_PLAY_NAME)
    selected_motion_ids_by_name = {
        name: motion_ids_by_name[name]
        for name in selected_motion_names
        if name in motion_ids_by_name
    }

    next_settings["motion"] = _adjust_motion_percentages(selected_motion_ids_by_name, focus_strengths)

    existing_set_ids = [
        str(pid)
        for pid in (next_settings.get("set_plays") or {}).keys()
        if str(pid) in play_key_by_id
    ]
    selected_set_ids = _selected_set_play_ids(
        existing_set_ids,
        set_play_ids_by_focus,
        focus_strengths,
        update_week=update_week,
    )
    next_settings["set_plays"] = _set_play_percentages(selected_set_ids)
    next_settings["fast_breaks"] = _random_capped_three(("covert_release", "rim_runner", "triangle"))
    next_settings["zone_defense"] = _random_capped_three(("zone_23", "zone_32", "zone_131"))
    next_settings["man_defense"] = {"man_normal": 100, "man_pressure": 0, "man_loose": 0}

    meta = next_settings.get("_meta") if isinstance(next_settings.get("_meta"), dict) else {}
    next_settings["_meta"] = {**meta, "schema_version": 2, "cpu_customized": True}

    for key, play in _iter_play_items(next_plays):
        if play.get("play_type") == "motion" and _play_id(play) in set(next_settings["motion"].keys()):
            chosen = _weighted_choice_from_dict(motion_focus_weights)
            play["motion_focus"] = None if chosen == "balanced" else chosen
        elif play.get("play_type") == "set_play" and _play_id(play) in set(selected_set_ids):
            focus = play.get("play_focus")
            if focus in FOCUSES:
                play["target_shooter"] = _weighted_choice_from_dict(
                    _target_position_weights(position_players, focus)
                )

    return CpuPlaybookBuildResult(playbook_settings=next_settings, plays=next_plays)


def refresh_cpu_playbook_group_for_game_init(
    *,
    franchise_id: ObjectId,
    franchise_doc: dict[str, Any],
    week: int,
    user_team_id: Any,
    teams_by_id: dict[str, Any],
    franchise_team_data_collection: Any,
) -> list[str]:
    """Refresh every CPU team in this week's configured group, idempotently."""
    group_num = group_for_cpu_playbook_week(week)
    if group_num is None:
        return []

    schedule_meta = franchise_doc.get("cpu_playbook_schedule") or {}
    groups = schedule_meta.get("groups") or build_user_schedule_cpu_playbook_groups(
        franchise_doc.get("schedule") or [],
        user_team_id,
    ).get("groups", {})
    team_ids = [str(tid) for tid in groups.get(str(group_num), [])]
    if not team_ids:
        return []

    refreshed: list[str] = []
    for team_id in team_ids:
        if str(team_id) == str(user_team_id):
            continue
        try:
            team_oid = ObjectId(str(team_id))
        except Exception:
            logging.warning("⚠️ [CPU PLAYBOOK] Invalid team id in group: %s", team_id)
            continue
        ftd = franchise_team_data_collection.find_one(
            {"franchise_id": franchise_id, "team_id": team_oid}
        )
        if not ftd:
            continue
        if int(ftd.get("cpu_playbook_last_refresh_week") or 0) == int(week):
            continue
        team = teams_by_id.get(str(team_id))
        if team is None:
            continue
        built = build_cpu_playbook_for_team(
            team,
            ftd.get("playbook_settings") or {},
            ftd.get("plays") or {},
            update_week=week > 5,
        )
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": team_oid},
            {
                "$set": {
                    "playbook_settings": built.playbook_settings,
                    "plays": built.plays,
                    "cpu_playbook_last_refresh_week": int(week),
                    "cpu_playbook_last_refresh_group": int(group_num),
                }
            },
        )
        refreshed.append(str(team_id))
    return refreshed
