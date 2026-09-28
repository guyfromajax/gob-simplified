"""Read-only browse shaping for League › Tournament (``GET /franchise/tournament/brackets``).

Does not reconcile region brackets or run any franchise writes. Staleness is
detected by comparing the stored blob to what reconcile would produce, without
persisting.
"""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from BackEnd.tournament import franchise_tournament as ft
from BackEnd.tournament import bracket_engine

TOURNAMENT_FIRST_WEEK = 27

PHASE_DRAW_WEEK = {
    "conference": TOURNAMENT_FIRST_WEEK,
    "region": ft.EOS_REGION_WEEKS[0],
    "national": ft.EOS_NATIONAL_WEEKS[0],
}

WEEK_PHASE = {}
for w in ft.EOS_CONFERENCE_WEEKS:
    WEEK_PHASE[w] = "conference"
for w in ft.EOS_REGION_WEEKS:
    WEEK_PHASE[w] = "region"
for w in ft.EOS_NATIONAL_WEEKS:
    WEEK_PHASE[w] = "national"

WEEK_ROUND_LABEL = {
    27: "Quarterfinal",
    28: "Semifinal",
    29: "Final",
    30: "Semifinal",
    31: "Final",
    32: "Quarterfinal",
    33: "Semifinal",
    34: "Final",
}


def week_round_label(week: int) -> str | None:
    return WEEK_ROUND_LABEL.get(int(week))

ROUND_LABELS = {
    "conference": {"round1": "Quarterfinal", "round2": "Semifinal", "final": "Final"},
    "national": {"round1": "Quarterfinal", "round2": "Semifinal", "final": "Final"},
    "region": {"round1": "Semifinal", "final": "Final"},
}


def current_phase(week: int) -> str | None:
    if week in ft.EOS_CONFERENCE_WEEKS:
        return "conference"
    if week in ft.EOS_REGION_WEEKS:
        return "region"
    if week in ft.EOS_NATIONAL_WEEKS:
        return "national"
    return None


def round_labels_for_phase(phase: str) -> dict[str, str]:
    return dict(ROUND_LABELS.get(phase, ROUND_LABELS["conference"]))


def shape_eos_tournament(
    franchise_doc: dict[str, Any],
    week: int,
    user_conference: Any,
    user_region: str,
    national_tournament: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Same phase pick as ``/franchise/command-center/data`` (FCC bracket tab)."""
    week_val = int(week or 1)
    if week_val in ft.EOS_CONFERENCE_WEEKS:
        if user_conference is None:
            return None
        ct = (franchise_doc.get("conference_tournaments") or {}).get(str(user_conference), {})
        return ct if ct else None
    if week_val in ft.EOS_REGION_WEEKS:
        region = str(user_region or "").upper()
        if len(region) != 1:
            return None
        rt = (franchise_doc.get("region_tournaments") or {}).get(region, {})
        if not rt:
            return None
        final_list = rt.get("final", [])
        champ = final_list[0].get("winner") if final_list and final_list[0].get("winner") else None
        return {
            "bracket": {"round1": rt.get("round1", []), "round2": [], "final": final_list},
            "seeds": rt.get("seeds", {}),
            "current_round": rt.get("current_round", 1),
            "champion": champ,
        }
    if week_val in ft.EOS_NATIONAL_WEEKS:
        return national_tournament if national_tournament else None
    return None


def _is_team_id(value: Any) -> bool:
    if value is None or not isinstance(value, str):
        return False
    if value.startswith("R1_") or len(value) != 24:
        return False
    try:
        from bson import ObjectId

        ObjectId(value)
        return True
    except Exception:
        return False


def collect_bracket_team_ids(franchise_doc: dict[str, Any]) -> set[str]:
    ids: set[str] = set()

    def add_id(raw: Any) -> None:
        if _is_team_id(raw):
            ids.add(str(raw))

    def walk_matchups(matchups: Any) -> None:
        for m in matchups or []:
            if not isinstance(m, dict):
                continue
            add_id(m.get("home_team"))
            add_id(m.get("away_team"))
            add_id(m.get("winner"))

    for ct in (franchise_doc.get("conference_tournaments") or {}).values():
        bracket = (ct or {}).get("bracket") or {}
        for key in ("round1", "round2", "final"):
            walk_matchups(bracket.get(key))

    for rt in (franchise_doc.get("region_tournaments") or {}).values():
        for key in ("round1", "final"):
            walk_matchups((rt or {}).get(key))

    nat = franchise_doc.get("national_tournament") or {}
    bracket = nat.get("bracket") or {}
    for key in ("round1", "round2", "final"):
        walk_matchups(bracket.get(key))

    champ = nat.get("champion")
    add_id(champ)
    return ids


def region_tournaments_stale(
    franchise_doc: dict[str, Any],
    teams_collection,
    eos_team_ids: list[Any],
) -> bool:
    """True when reconcile would change ``region_tournaments`` (read-only check)."""
    if not franchise_doc.get("region_tournaments") or not eos_team_ids:
        return False
    updated = ft.reconcile_region_tournaments_with_canonical(
        franchise_doc, teams_collection, eos_team_ids
    )
    return updated is not None


def _user_lost_in_matchup(m: dict[str, Any], user_team_id: str) -> bool:
    winner = m.get("winner")
    if not winner or not _is_team_id(winner):
        return False
    home = str(m.get("home_team") or "")
    away = str(m.get("away_team") or "")
    uid = str(user_team_id)
    if uid not in {home, away}:
        return False
    return str(winner) != uid


def user_eliminated_round_label(
    franchise_doc: dict[str, Any],
    user_team_id: str,
    week: int,
) -> str | None:
    """Human round name for the user's last loss in the active/post phase."""
    uid = str(user_team_id)
    phase = current_phase(week) or "national"
    labels = round_labels_for_phase(phase if phase != "region" else "region")

    def scan_bracket(bracket: dict[str, Any], phase_name: str) -> str | None:
        phase_labels = round_labels_for_phase(phase_name)
        for key in ("round1", "round2", "final"):
            for m in bracket.get(key) or []:
                if isinstance(m, dict) and _user_lost_in_matchup(m, uid):
                    return phase_labels.get(key, key)
        return None

    if phase == "conference" or week in ft.EOS_CONFERENCE_WEEKS:
        for ct in (franchise_doc.get("conference_tournaments") or {}).values():
            label = scan_bracket((ct or {}).get("bracket") or {}, "conference")
            if label:
                return label
    if phase in {"region", "national"} or week >= ft.EOS_REGION_WEEKS[0]:
        for rt in (franchise_doc.get("region_tournaments") or {}).values():
            label = scan_bracket(
                {
                    "round1": (rt or {}).get("round1") or [],
                    "round2": [],
                    "final": (rt or {}).get("final") or [],
                },
                "region",
            )
            if label:
                return label
    nat = franchise_doc.get("national_tournament") or {}
    return scan_bracket(nat.get("bracket") or {}, "national")


def build_teams_map(
    franchise_doc: dict[str, Any],
    team_ids: set[str],
    *,
    teams_collection,
    franchise_team_data_collection,
    franchise_id: Any,
    calculate_franchise_standings,
) -> dict[str, dict[str, Any]]:
    from BackEnd.utils.franchise_team_display import resolve_team_display

    if not team_ids:
        return {}

    results = franchise_doc.get("results") or {}
    reg_only = {
        k: v
        for k, v in results.items()
        if isinstance(k, str) and k.isdigit() and 1 <= int(k) <= 26
    }
    standings = calculate_franchise_standings(reg_only, {tid: {} for tid in team_ids})

    ftd_rows = list(
        franchise_team_data_collection.find(
            {"franchise_id": franchise_id, "team_id": {"$in": list(team_ids)}},
            {"team_id": 1, "natl_rank": 1},
        )
    )
    rank_by_id = {str(r["team_id"]): r.get("natl_rank") for r in ftd_rows if r.get("team_id")}

    out: dict[str, dict[str, Any]] = {}
    for tid in team_ids:
        core = teams_collection.find_one(
            {"_id": ObjectId(tid)},
            {"name": 1, "mascot": 1, "conference": 1, "region": 1, "team_id": 1},
        )
        if not core:
            continue
        disp = resolve_team_display(franchise_doc, tid, core_doc=core)
        row = standings.get(tid) or {}
        name = disp.get("name") or core.get("name") or tid
        out[tid] = {
            "name": name,
            "mascot": core.get("mascot"),
            "conference": core.get("conference"),
            "region": core.get("region"),
            "natl_rank": rank_by_id.get(tid),
            "W": int(row.get("W") or 0),
            "L": int(row.get("L") or 0),
            "logo": name,
        }
    return out


def _score_pair(score: Any, home_id: str, away_id: str) -> tuple[int | None, int | None]:
    if not isinstance(score, dict):
        return None, None
    hs = score.get("home")
    as_ = score.get("away")
    if hs is None:
        hs = score.get(home_id)
    if as_ is None:
        as_ = score.get(away_id)
    try:
        return (int(hs) if hs is not None else None, int(as_) if as_ is not None else None)
    except (TypeError, ValueError):
        return None, None


def user_tournament_games_by_phase(
    franchise_doc: dict[str, Any],
    user_team_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """User's EOS games grouped for Team › Schedule (weeks 27–34)."""
    uid = str(user_team_id)
    grouped: dict[str, list[dict[str, Any]]] = {
        "conference": [],
        "region": [],
        "national": [],
    }
    for week in ft.EOS_WEEKS:
        games = ft.get_eos_week_games(franchise_doc, week, include_completed=True)
        for g in games:
            away = str(g.get("away_id") or "")
            home = str(g.get("home_id") or "")
            if uid not in {away, home}:
                continue
            phase = str(g.get("phase") or "")
            if phase not in grouped:
                continue
            rnd = int(g.get("round") or 1)
            rkey = bracket_engine.get_round_name(rnd)
            label = round_labels_for_phase(phase).get(rkey, rkey)
            site = "home" if uid == home else "away"
            opponent_id = away if site == "home" else home
            hs, as_ = _score_pair(g.get("score"), home, away)
            row: dict[str, Any] = {
                "week": week,
                "phase": phase,
                "round_label": label,
                "site": site,
                "opponent_id": opponent_id,
                "game_id": g.get("game_id"),
            }
            if hs is not None and as_ is not None:
                if site == "home":
                    row["team_score"], row["opp_score"] = hs, as_
                else:
                    row["team_score"], row["opp_score"] = as_, hs
                row["result"] = "W" if row["team_score"] > row["opp_score"] else "L"
            grouped[phase].append(row)
    for phase in grouped:
        grouped[phase].sort(key=lambda r: r["week"])
    return grouped


def build_tournament_brackets_response(
    franchise_doc: dict[str, Any],
    *,
    user_team_id: str,
    user_team_doc: dict[str, Any] | None,
    teams_collection,
    franchise_team_data_collection,
    get_user_eos_phase_status,
    calculate_franchise_standings,
) -> dict[str, Any]:
    week = int(franchise_doc.get("week") or 1)
    national = franchise_doc.get("national_tournament") or {}
    user_conf = (user_team_doc or {}).get("conference")
    user_region = str((user_team_doc or {}).get("region") or "").upper()

    team_ids = collect_bracket_team_ids(franchise_doc)
    teams = build_teams_map(
        franchise_doc,
        team_ids,
        teams_collection=teams_collection,
        franchise_team_data_collection=franchise_team_data_collection,
        franchise_id=franchise_doc.get("_id"),
        calculate_franchise_standings=calculate_franchise_standings,
    )

    eos_status = get_user_eos_phase_status(franchise_doc, str(user_team_id), week) if week in ft.EOS_WEEKS else {}
    user_eliminated = bool(eos_status.get("eliminated_from_current_phase"))
    champion = national.get("champion")
    tournament_complete = bool(champion)

    eos_team_ids = [
        d["team_id"]
        for d in franchise_team_data_collection.find(
            {"franchise_id": franchise_doc.get("_id")},
            {"team_id": 1},
        )
        if d.get("team_id") is not None
    ]
    region_stale = region_tournaments_stale(franchise_doc, teams_collection, eos_team_ids)
    region_tournaments = franchise_doc.get("region_tournaments") or {}
    if region_stale:
        reconciled = ft.reconcile_region_tournaments_with_canonical(
            franchise_doc, teams_collection, eos_team_ids
        )
        if reconciled is not None:
            region_tournaments = reconciled
            team_ids = collect_bracket_team_ids({
                **franchise_doc,
                "region_tournaments": region_tournaments,
            })
            teams = build_teams_map(
                franchise_doc,
                team_ids,
                teams_collection=teams_collection,
                franchise_team_data_collection=franchise_team_data_collection,
                franchise_id=franchise_doc.get("_id"),
                calculate_franchise_standings=calculate_franchise_standings,
            )

    phase = current_phase(week)
    if tournament_complete and week > max(ft.EOS_NATIONAL_WEEKS):
        phase = phase or "national"

    return {
        "week": week,
        "first_week": TOURNAMENT_FIRST_WEEK,
        "locked": week < TOURNAMENT_FIRST_WEEK,
        "current_phase": phase,
        "round_labels": {
            "conference": round_labels_for_phase("conference"),
            "region": round_labels_for_phase("region"),
            "national": round_labels_for_phase("national"),
        },
        "phase_draw_week": PHASE_DRAW_WEEK,
        "conference_tournaments": franchise_doc.get("conference_tournaments") or {},
        "region_tournaments": region_tournaments,
        "national_tournament": national,
        "eos_tournament": shape_eos_tournament(
            franchise_doc, week, user_conf, user_region, national or None
        ),
        "teams": teams,
        "user_team_id": str(user_team_id),
        "user_conference": user_conf,
        "user_region": user_region,
        "user_eliminated": user_eliminated,
        "eliminated_in_round": user_eliminated_round_label(franchise_doc, user_team_id, week)
        if user_eliminated
        else None,
        "has_eos_game_this_week": bool(eos_status.get("has_game_this_week")),
        "has_bye_this_week": bool(eos_status.get("has_bye_this_week")),
        "region_qualified": bool(eos_status.get("region_qualified")),
        "tournament_complete": tournament_complete,
        "champion": champion,
        "region_tournaments_stale": region_stale,
    }
