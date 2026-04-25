"""
Resolve ``{player_name}`` for PGPC questions from ``player_slot`` + box score (+ optional RT context).

Substitution rules (see ``press_conference_routes``):
  * Questions use the player's **full** display name (first + last when available).
  * Answers use **first name** only when the question text included ``{player_name}``
    and the full name has multiple words; otherwise answers also use the full name.

Rules align loosely with question-bank intent so effect-tag resolution can reuse the same player later.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence


def _int(stats: Mapping[str, Any], key: str) -> int:
    try:
        return int(stats.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _user_team_players(game_doc: Mapping[str, Any], user_team_id: str) -> List[Dict[str, Any]]:
    tid = str(user_team_id)
    return [
        p
        for p in (game_doc.get("players") or [])
        if isinstance(p, dict) and str(p.get("team_id") or "") == tid
    ]


def _starter_ids(game_doc: Mapping[str, Any], user_team_id: str) -> set[str]:
    ol = game_doc.get("opening_lineup")
    if not isinstance(ol, dict):
        return set()
    raw = ol.get(str(user_team_id)) or ol.get(user_team_id)
    if not isinstance(raw, (list, tuple)):
        return set()
    return {str(x) for x in raw if x is not None}


def _pid(p: Mapping[str, Any]) -> str:
    return str(p.get("playerId") or "")


def _stats(p: Mapping[str, Any]) -> Dict[str, Any]:
    s = p.get("stats")
    return dict(s) if isinstance(s, dict) else {}


def _em(p: Mapping[str, Any]) -> int:
    attrs = p.get("attributes")
    if not isinstance(attrs, dict):
        return 0
    try:
        return int(attrs.get("EM", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _rt(pid: str, context: Mapping[str, Any] | None) -> Optional[float]:
    if not context:
        return None
    m = context.get("player_overall_rt")
    if not isinstance(m, dict):
        return None
    v = m.get(pid) if pid in m else m.get(str(pid))
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pick(
    players: Sequence[Dict[str, Any]],
    key: Callable[[Dict[str, Any]], Any],
    *,
    reverse: bool = True,
) -> Optional[Dict[str, Any]]:
    if not players:
        return None
    return sorted(players, key=key, reverse=reverse)[0]


def _player_full_and_first(p: Mapping[str, Any]) -> tuple[str, str]:
    """Display (full_name, first_name) for press copy."""
    fn = str(p.get("first_name") or "").strip()
    ln = str(p.get("last_name") or "").strip()
    raw = str(p.get("name") or "").strip()
    if fn or ln:
        full = f"{fn} {ln}".strip()
        if not full:
            full = raw or "your player"
        first = fn or (raw.split()[0] if raw else full)
    elif raw:
        full = raw
        parts = raw.split()
        first = parts[0] if parts else raw
    else:
        return "your player", "your player"
    return full, first


def _finalize_player_names(p: Optional[Dict[str, Any]]) -> tuple[str, str]:
    if not p:
        return "your player", "your player"
    return _player_full_and_first(p)


def answer_name_for_pgpc_answers(
    *,
    question_included_player_placeholder: bool,
    full_name: str,
    first_name: str,
) -> str:
    """
    Answers use first name only when the question used ``{player_name}`` and the
    resolved full name is multi-word (first + last). Otherwise keep the full name.
    """
    if not question_included_player_placeholder:
        return full_name
    if not full_name or full_name == "your player":
        return full_name
    if len(full_name.split()) >= 2:
        return first_name
    return full_name


def _pick_player_record_for_slot(
    player_slot: str,
    players: List[Dict[str, Any]],
    bench: List[Dict[str, Any]],
    context: Mapping[str, Any] | None,
) -> Optional[Dict[str, Any]]:
    slot = str(player_slot)

    if slot == "high_scorer":
        return _pick(players, lambda x: (_int(_stats(x), "PTS"),))

    if slot == "hot_shooter":
        return _pick(
            players,
            lambda x: (_int(_stats(x), "3PTM"), _int(_stats(x), "PTS")),
        )

    if slot == "top_rebounder":
        return _pick(players, lambda x: (_int(_stats(x), "REB"), _int(_stats(x), "PTS")))

    if slot == "surprise_rebounder":
        pool = bench if bench else players
        return _pick(pool, lambda x: (_int(_stats(x), "REB"),))

    if slot == "surprise_scorer":
        low_rt = [
            x
            for x in players
            if (r := _rt(_pid(x), context)) is not None and r <= 50
        ]
        pool = low_rt if low_rt else (bench if bench else players)
        return _pick(pool, lambda x: (_int(_stats(x), "PTS"),))

    if slot in ("lockdown_defender",):
        qualified = [x for x in players if _int(_stats(x), "DEF_A") >= 4]
        pool = qualified if qualified else players
        return _pick(pool, lambda x: (_int(_stats(x), "DEF_S"), _int(_stats(x), "DEF_A")))

    if slot == "defensive_liability":
        qualified = [x for x in players if _int(_stats(x), "DEF_A") >= 3]
        pool = qualified if qualified else players

        def liability_key(x: Dict[str, Any]) -> tuple[int, int]:
            st = _stats(x)
            da = max(_int(st, "DEF_A"), 1)
            ds = _int(st, "DEF_S")
            return (ds * 100 // da, -_int(st, "PTS"))

        return sorted(pool, key=liability_key)[0] if pool else None

    if slot in ("foul_trouble", "foul_out"):
        return _pick(players, lambda x: (_int(_stats(x), "F"), _int(_stats(x), "PTS")))

    if slot == "ft_struggles":
        pool = [x for x in players if _int(_stats(x), "FTA") >= 4]
        if not pool:
            pool = [x for x in players if _int(_stats(x), "FTA") >= 1]
        if not pool:
            return _pick(players, lambda x: (_int(_stats(x), "PTS"),))

        def ft_pct(x: Dict[str, Any]) -> tuple[int, int]:
            st = _stats(x)
            fta = max(_int(st, "FTA"), 1)
            ftm = _int(st, "FTM")
            return (ftm * 100 // fta, fta)

        return sorted(pool, key=ft_pct)[0]

    if slot == "confident_player":
        return _pick(players, lambda x: (_em(x), _int(_stats(x), "PTS")))

    if slot == "frustrated_player":
        return sorted(
            players,
            key=lambda x: (_em(x), _int(_stats(x), "PTS")),
        )[0]

    if slot in ("bench_outperformer",):
        pool = bench if bench else players
        return _pick(pool, lambda x: (_int(_stats(x), "PTS"),))

    if slot == "benched_star":
        pool = bench if bench else players
        rated: List[Dict[str, Any]] = []
        for x in pool:
            r = _rt(_pid(x), context)
            if r is not None and r >= 75:
                rated.append(x)
        pool2 = rated if rated else pool

        return sorted(
            pool2,
            key=lambda x: (
                _int(_stats(x), "MIN"),
                -(_rt(_pid(x), context) or 0.0),
            ),
        )[0] if pool2 else None

    if slot == "dominant_star":
        rated = []
        for x in players:
            r = _rt(_pid(x), context)
            if r is not None and r >= 80:
                rated.append(x)
        pool = rated if rated else players
        return _pick(pool, lambda x: (_int(_stats(x), "PTS"),))

    if slot == "struggling_star":
        rated = []
        for x in players:
            r = _rt(_pid(x), context)
            if r is not None and r >= 80:
                rated.append(x)
        pool = rated if rated else players
        band = [x for x in pool if 1 <= _int(_stats(x), "PTS") <= 6]
        pool2 = band if band else pool
        return sorted(pool2, key=lambda x: _int(_stats(x), "PTS"))[0] if pool2 else None

    if slot == "zero_star":
        rated = []
        for x in players:
            r = _rt(_pid(x), context)
            if r is not None and r >= 80:
                rated.append(x)
        zeros = [x for x in rated if _int(_stats(x), "PTS") == 0]
        pool = zeros if zeros else rated if rated else players
        return sorted(pool, key=lambda x: (-(_rt(_pid(x), context) or 0),))[0] if pool else None

    if slot == "game_winner":
        return _pick(players, lambda x: (_int(_stats(x), "PTS"), _int(_stats(x), "REB")))

    return _pick(players, lambda x: (_int(_stats(x), "PTS"),))


def resolve_player_display_names_for_slot(
    player_slot: str | None,
    game_doc: Mapping[str, Any],
    user_team_id: str,
    context: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Returns (full_display_name, first_name) for PGPC substitution.
    Falls back to ``(\"your player\", \"your player\")`` when unresolved.
    """
    if not player_slot:
        return "", ""

    players = _user_team_players(game_doc, user_team_id)
    if not players:
        return "your player", "your player"

    starters = _starter_ids(game_doc, user_team_id)
    bench = [p for p in players if _pid(p) not in starters] if starters else list(players)

    p = _pick_player_record_for_slot(str(player_slot), players, bench, context)
    return _finalize_player_names(p)


def resolve_player_name_for_slot(
    player_slot: str | None,
    game_doc: Mapping[str, Any],
    user_team_id: str,
    context: Mapping[str, Any] | None = None,
) -> str:
    """Resolved **full** display name (backward-compatible API)."""
    full, _ = resolve_player_display_names_for_slot(player_slot, game_doc, user_team_id, context)
    return full


__all__ = [
    "answer_name_for_pgpc_answers",
    "resolve_player_display_names_for_slot",
    "resolve_player_name_for_slot",
]
