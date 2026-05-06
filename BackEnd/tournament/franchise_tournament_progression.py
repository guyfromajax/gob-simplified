"""
Central entry point for franchise EOS tournament result recording and bracket advances.

Routes and services should use this module—not ``franchise_tournament.save_*`` or
``advance_*`` directly (Step 6). Low-level ``save_*`` / ``advance_*`` remain in
``franchise_tournament`` for use only from here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from bson import ObjectId

from BackEnd.db import db
from BackEnd.tournament import franchise_tournament as ft

logger = logging.getLogger(__name__)


def normalize_tournament_team_id(tid: Any) -> str:
    """Canonical 24-hex team id string for comparisons and bracket writes."""
    return ft._eos_team_id_canonical(tid)


def find_user_eos_game_meta(
    franchise_doc: dict,
    week_games_meta: list | None,
    user_team_id_str: Any,
    week: int | None,
) -> dict | None:
    """
    Locate the EOS schedule row (``game_meta``) for the user's matchup this week.

    Mirrors the resolution rules previously embedded in ``_save_user_eos_bracket_result``:
    calendar meta first, optional ObjectId / teams collection resolution for user id,
    then playable meta when calendar misses (stuck R1 / week drift).
    """
    if week_games_meta is None:
        return None
    meta_primary = list(week_games_meta)
    found = ft.find_user_game_in_eos_week(meta_primary, user_team_id_str)
    resolved: str | None = None
    if not found and user_team_id_str:
        raw = str(user_team_id_str).strip()
        try:
            if ObjectId.is_valid(raw):
                resolved = str(ObjectId(raw))
        except Exception:
            resolved = None
        if not resolved:
            try:
                doc = db.teams.find_one(
                    {"$or": [{"team_id": raw}, {"name": raw}, {"code": raw}]},
                    {"_id": 1},
                )
            except Exception:
                doc = None
            if doc and doc.get("_id") is not None:
                resolved = str(doc["_id"])
        if resolved:
            found = ft.find_user_game_in_eos_week(meta_primary, resolved)
            if found:
                logger.warning(
                    "🧭 [EOS-PROGRESSION] Resolved user_team_id for EOS meta: raw=%s resolved=%s",
                    raw,
                    resolved,
                )
    if not found and week is not None and week in ft.EOS_WEEKS:
        playable = ft.get_eos_week_games(franchise_doc, week, include_completed=False)
        found = ft.find_user_game_in_eos_week(playable, user_team_id_str)
        if not found and resolved:
            found = ft.find_user_game_in_eos_week(playable, resolved)
        if found:
            logger.warning(
                "[EOS-BRACKET-DEBUG] user_eos_meta_using_playable_list franchise_id=%s week=%s",
                str(franchise_doc.get("_id")),
                week,
            )
    if not found:
        logger.warning(
            "⚠️ [EOS-PROGRESSION] No user EOS meta row (user_team_id=%s week=%s)",
            user_team_id_str,
            week,
        )
        return None
    return found[1]


def find_eos_game_meta_for_team_pair(
    week_games_meta: list | None,
    team1_id: Any,
    team2_id: Any,
) -> dict[str, Any] | None:
    """
    Resolve EOS schedule meta by the two team ids in the played result.

    Used when ``find_user_eos_game_meta`` misses (e.g. ``user_team_id_str`` not aligned with
    franchise meta) so we still record the bracket slot via ``record_tournament_game_result``.
    """
    if not week_games_meta:
        return None
    a = normalize_tournament_team_id(team1_id)
    b = normalize_tournament_team_id(team2_id)
    if not a or not b:
        return None
    want = frozenset({a, b})
    for g in week_games_meta:
        if not isinstance(g, dict) or not g.get("phase"):
            continue
        ga = normalize_tournament_team_id(g.get("away_id"))
        gh = normalize_tournament_team_id(g.get("home_id"))
        if ga and gh and frozenset({ga, gh}) == want:
            return g
    return None


def _validate_players_match_meta(
    game_meta: dict[str, Any],
    team1_id: Any,
    team2_id: Any,
) -> None:
    a = normalize_tournament_team_id(game_meta.get("away_id"))
    h = normalize_tournament_team_id(game_meta.get("home_id"))
    t1 = normalize_tournament_team_id(team1_id)
    t2 = normalize_tournament_team_id(team2_id)
    if {t1, t2} != {a, h}:
        raise ValueError(
            f"Result teams do not match EOS meta away/home: meta=({a},{h}) request=({t1},{t2})"
        )


def _upsert_franchise_game_document(
    team1_id: Any,
    team2_id: Any,
    team1_score: int,
    team2_score: int,
    week: int,
    franchise_id_str: str,
    game_id: str | None,
) -> None:
    """
    Persist scores to ``games`` (franchise mode). Same rules as ``_save_game_result`` in
    ``franchise_routes`` — kept here to avoid import cycles.
    """
    if game_id:
        try:
            game_id_str = str(game_id)
            existing = db.games.find_one({"_id": game_id_str})
            if existing:
                filter_doc: dict[str, Any] = {"_id": game_id_str}
            else:
                existing_oid = None
                if ObjectId.is_valid(game_id_str):
                    game_oid = ObjectId(game_id_str)
                    existing_oid = db.games.find_one({"_id": game_oid})
                if existing_oid:
                    filter_doc = {"_id": game_oid}
                else:
                    filter_doc = {"_id": game_id_str}
        except Exception as e:
            logger.warning(
                "⚠️ [EOS-PROGRESSION] Invalid game_id=%s (%s); using legacy lookup",
                game_id,
                e,
            )
            game_id = None
            filter_doc = {}
    else:
        filter_doc = {}

    if not game_id:
        lookup_doc: dict[str, Any] = {
            "week": week,
            "$or": [
                {"team1_id": team1_id, "team2_id": team2_id},
                {"team1_id": team2_id, "team2_id": team1_id},
            ],
            "franchise_id": franchise_id_str,
        }
        existing = db.games.find_one(lookup_doc)
        if existing:
            filter_doc = {"_id": existing["_id"]}
        else:
            filter_doc = {"week": week, "team1_id": team1_id, "team2_id": team2_id}

    update_fields = {
        "team1_id": team1_id,
        "team2_id": team2_id,
        "team1_score": team1_score,
        "team2_score": team2_score,
        "week": week,
        "franchise_id": franchise_id_str,
    }
    db.games.update_one(filter_doc, {"$set": update_fields}, upsert=True)


def _write_bracket_slot(
    franchise_doc: dict,
    game_meta: dict[str, Any],
    *,
    game_id_str: str,
    winner_id_str: str,
    score: dict[str, int],
) -> None:
    phase = game_meta.get("phase")
    if phase == "conference":
        ft.save_conference_game_result(
            franchise_doc,
            int(game_meta["conference"]),
            int(game_meta["round"]),
            int(game_meta["matchup_index"]),
            game_id_str,
            winner_id_str,
            score,
        )
    elif phase == "region":
        ft.save_region_game_result(
            franchise_doc,
            str(game_meta["region"]),
            int(game_meta["round"]),
            int(game_meta["matchup_index"]),
            game_id_str,
            winner_id_str,
            score,
        )
    elif phase == "national":
        ft.save_national_game_result(
            franchise_doc,
            int(game_meta["round"]),
            int(game_meta["matchup_index"]),
            game_id_str,
            winner_id_str,
            score,
        )
    else:
        raise ValueError(f"Unknown EOS phase {phase!r}")


def advance_conference_bracket(
    franchise_doc: dict,
    conference: int,
) -> Tuple[bool, Optional[str]]:
    """Advance one conference bracket; delegates to ``franchise_tournament``."""
    return ft.advance_conference_bracket(franchise_doc, conference)


def advance_national_bracket(franchise_doc: dict) -> Tuple[bool, Optional[str]]:
    """Advance the national bracket; delegates to ``franchise_tournament``."""
    return ft.advance_national_bracket(franchise_doc)


def advance_region_bracket(franchise_doc: dict, region: str) -> Optional[str]:
    """Return region champion if the final has a winner; delegates to ``franchise_tournament``."""
    return ft.advance_region_bracket(franchise_doc, region)


def record_tournament_game_result(
    franchise_doc: dict,
    game_meta: dict[str, Any],
    *,
    week: int,
    franchise_id_str: str,
    game_id: str | None,
    team1_id: Any,
    team2_id: Any,
    team1_score: int,
    team2_score: int,
    source: str = "user",
    skip_games_upsert: bool = False,
) -> dict[str, Any]:
    """
    Record one franchise EOS tournament outcome: ``games`` row + bracket slot.

    Callers still merge rows into ``franchise.results[week]`` as today; a later step
    will fold that into this function.

    ``skip_games_upsert``: when True, only update the bracket (caller already wrote
    the full ``games`` document, e.g. full CPU sim summary + finalize).

    ``source`` is for logging/traceability: ``user``, ``cpu_full``, ``distant``,
    ``existing_games`` (sync from a ``games`` row), ``existing_results`` (sync from
    a results row, creating a minimal ``games`` doc).

    Idempotent for repeated calls with the same winner and scores; a later call may
    supply ``game_id`` when it was previously missing (legacy lookup path).

    ``cpu_full`` / ``distant`` never overwrite a slot that already has a different
    winner or scores (prevents double-sim / retry clobber). ``user`` and
    ``existing_*`` may still repair or correct a populated slot.
    """
    _validate_players_match_meta(game_meta, team1_id, team2_id)

    home_id_g = game_meta["home_id"]
    hg = normalize_tournament_team_id(home_id_g)
    t1 = normalize_tournament_team_id(team1_id)
    score = {
        "home": team1_score if t1 == hg else team2_score,
        "away": team2_score if t1 == hg else team1_score,
    }
    winner_raw = team1_id if team1_score > team2_score else team2_id
    winner_id_str = normalize_tournament_team_id(winner_raw) or str(winner_raw)
    bracket_game_id = str(game_id or "")
    incoming_gid = bracket_game_id.strip()

    snap = ft.get_eos_bracket_slot_snapshot(franchise_doc, game_meta)
    if snap is not None:
        ew = (snap.get("winner_id") or "").strip()
        esc = snap.get("score") or {"home": 0, "away": 0}
        egid = (snap.get("game_id") or "").strip()
        same_scores = int(esc.get("home", 0) or 0) == int(score["home"]) and int(
            esc.get("away", 0) or 0
        ) == int(score["away"])

        if ew:
            same_winner = ew == winner_id_str
            if same_winner and same_scores:
                need_gid_write = bool(
                    incoming_gid
                    and incoming_gid != egid
                    and (not egid or source == "user")
                )
                if need_gid_write:
                    _write_bracket_slot(
                        franchise_doc,
                        game_meta,
                        game_id_str=incoming_gid,
                        winner_id_str=winner_id_str,
                        score=score,
                    )
                    if not skip_games_upsert and game_id:
                        _upsert_franchise_game_document(
                            team1_id,
                            team2_id,
                            team1_score,
                            team2_score,
                            week,
                            franchise_id_str,
                            game_id,
                        )
                    logger.warning(
                        "[EOS-BRACKET-DEBUG] record_tournament_game_result_backfill_game_id "
                        "franchise_id=%s phase=%s conf/region=%s round=%s idx=%s source=%s game_id=%s",
                        str(franchise_doc.get("_id")),
                        game_meta.get("phase"),
                        game_meta.get("conference") or game_meta.get("region"),
                        game_meta.get("round"),
                        game_meta.get("matchup_index"),
                        source,
                        incoming_gid[:16],
                    )
                else:
                    logger.warning(
                        "[EOS-BRACKET-DEBUG] record_tournament_game_result_skip_duplicate "
                        "franchise_id=%s phase=%s conf/region=%s round=%s idx=%s source=%s",
                        str(franchise_doc.get("_id")),
                        game_meta.get("phase"),
                        game_meta.get("conference") or game_meta.get("region"),
                        game_meta.get("round"),
                        game_meta.get("matchup_index"),
                        source,
                    )
                loser_id = normalize_tournament_team_id(
                    team2_id if team1_score > team2_score else team1_id
                )
                return {
                    "phase": game_meta.get("phase"),
                    "week": week,
                    "game_id": incoming_gid or egid,
                    "winner_id": winner_id_str,
                    "loser_id": loser_id,
                    "bracket_slot_recorded": True,
                    "results_row_recorded": False,
                    "game_doc_recorded": bool(need_gid_write and not skip_games_upsert),
                    "round_advanced": False,
                    "phase_completed": False,
                    "champion_id": None,
                    "user_eliminated": None,
                    "user_has_next_game": None,
                    "duplicate_eos_record": not need_gid_write,
                }

            if source in ("cpu_full", "distant"):
                logger.warning(
                    "[EOS-BRACKET-DEBUG] record_tournament_game_result_skip_locked_slot "
                    "franchise_id=%s source=%s phase=%s conf/region=%s round=%s idx=%s "
                    "existing_w=%s new_w=%s",
                    str(franchise_doc.get("_id")),
                    source,
                    game_meta.get("phase"),
                    game_meta.get("conference") or game_meta.get("region"),
                    game_meta.get("round"),
                    game_meta.get("matchup_index"),
                    (ew or "")[:16],
                    (winner_id_str or "")[:16],
                )
                loser_id = normalize_tournament_team_id(
                    team2_id if team1_score > team2_score else team1_id
                )
                return {
                    "phase": game_meta.get("phase"),
                    "week": week,
                    "game_id": egid,
                    "winner_id": ew or winner_id_str,
                    "loser_id": loser_id,
                    "bracket_slot_recorded": False,
                    "results_row_recorded": False,
                    "game_doc_recorded": False,
                    "round_advanced": False,
                    "phase_completed": False,
                    "champion_id": None,
                    "user_eliminated": None,
                    "user_has_next_game": None,
                    "skipped_non_idempotent_cpu": True,
                }

    logger.warning(
        "[EOS-BRACKET-DEBUG] record_tournament_game_result franchise_id=%s phase=%s "
        "conf/region=%s round=%s idx=%s source=%s winner=%s game_id=%s",
        str(franchise_doc.get("_id")),
        game_meta.get("phase"),
        game_meta.get("conference") or game_meta.get("region"),
        game_meta.get("round"),
        game_meta.get("matchup_index"),
        source,
        (winner_id_str or "")[:24],
        (bracket_game_id or "")[:16],
    )

    if not skip_games_upsert:
        _upsert_franchise_game_document(
            team1_id,
            team2_id,
            team1_score,
            team2_score,
            week,
            franchise_id_str,
            game_id,
        )
    _write_bracket_slot(
        franchise_doc,
        game_meta,
        game_id_str=bracket_game_id,
        winner_id_str=winner_id_str,
        score=score,
    )

    # Championship Announce Moments: queue Variation A/B for the FCC overlay path
    # (sim-rest, distant sim, sim-championship). The "user" source covers the
    # live-game path; that flow renders the moment in place of the EOG modal,
    # client-side, so we deliberately skip enqueue here to avoid double-show.
    if source in ("cpu_full", "distant"):
        try:
            from BackEnd.utils.franchise_championship_moments import (
                maybe_enqueue_championship_game_moment,
            )

            maybe_enqueue_championship_game_moment(
                franchise_doc,
                game_meta=game_meta,
                away_id=team1_id,
                home_id=team2_id,
                away_score=team1_score,
                home_score=team2_score,
                game_id=bracket_game_id or None,
            )
        except Exception:
            logger.exception(
                "[CHAMP-MOMENT] enqueue failed franchise_id=%s phase=%s round=%s",
                str(franchise_doc.get("_id")),
                game_meta.get("phase"),
                game_meta.get("round"),
            )

    loser_id = normalize_tournament_team_id(team2_id if team1_score > team2_score else team1_id)
    return {
        "phase": game_meta.get("phase"),
        "week": week,
        "game_id": bracket_game_id,
        "winner_id": winner_id_str,
        "loser_id": loser_id,
        "bracket_slot_recorded": True,
        "results_row_recorded": False,
        "game_doc_recorded": not skip_games_upsert,
        "round_advanced": False,
        "phase_completed": False,
        "champion_id": None,
        "user_eliminated": None,
        "user_has_next_game": None,
    }
