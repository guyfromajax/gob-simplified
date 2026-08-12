"""
Franchise Championship Announce Moments — server-side persistence + detection.

A "pending moment" is a one-shot UI overlay queued on the franchise document and
consumed by the FCC on next mount, OR replayed in place of the standard EOG modal
on a live championship game completion.

Five moment types:
    conference_championship  — Variation A (Classic), winner's color
    region_championship      — Variation A (Classic), winner's color
    national_championship    — Variation B (Cinematic), winner's color
    trophy_spotlight         — Variation C (Trophy), regular-season champ of user's
                               conference, queued at week 26 -> 27
    banner_raise             — Variation D (Banner Raise), USER team only, queued
                               by finish_season when user won the prior national title

The list lives at ``franchise_doc["pending_championship_moments"]``. Each entry
carries everything the frontend needs to render with no follow-up fetches.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Iterable

from bson import ObjectId

from BackEnd.db import db, franchise_team_data_collection
from BackEnd.utils.franchise_standings import calculate_franchise_standings

logger = logging.getLogger(__name__)

PENDING_MOMENTS_FIELD = "pending_championship_moments"

MOMENT_CONFERENCE = "conference_championship"
MOMENT_REGION = "region_championship"
MOMENT_NATIONAL = "national_championship"
MOMENT_TROPHY_SPOTLIGHT = "trophy_spotlight"
MOMENT_BANNER_RAISE = "banner_raise"

CHAMPIONSHIP_MOMENT_TYPES = frozenset(
    [
        MOMENT_CONFERENCE,
        MOMENT_REGION,
        MOMENT_NATIONAL,
        MOMENT_TROPHY_SPOTLIGHT,
        MOMENT_BANNER_RAISE,
    ]
)


def _team_view(team_id: Any, franchise: Any = None) -> dict[str, Any] | None:
    """
    Look up minimal display data for a team identifier. Accepts either an
    ObjectId / 24-hex string OR a canonical team_id key (e.g. "HARVEST"); the
    latter is what saved game documents store on ``home_team_id``/``away_team_id``.

    When ``franchise`` is provided, name/primary_color come from
    ``resolve_team_display`` (Team Builder overlay chrome).
    """
    if team_id is None:
        return None
    proj = {
        "name": 1,
        "primary_color": 1,
        "secondary_color": 1,
        "conference": 1,
        "region": 1,
        "team_id": 1,
        "mascot": 1,
    }
    team_doc = None
    # Try ObjectId path first (used by EOS bracket meta + franchise docs).
    try:
        oid = team_id if isinstance(team_id, ObjectId) else ObjectId(str(team_id))
        team_doc = db.teams.find_one({"_id": oid}, proj)
    except Exception:
        team_doc = None
    # Fall back to canonical team_id key (used by saved game docs / unified
    # ``teams`` object). Required for the live-game championship branch.
    if not team_doc:
        team_doc = db.teams.find_one({"team_id": str(team_id)}, proj)
    if not team_doc:
        return None
    name = team_doc.get("name") or ""
    primary = team_doc.get("primary_color") or "#27408E"
    if franchise is not None:
        try:
            from BackEnd.utils.franchise_team_display import resolve_team_display

            disp = resolve_team_display(franchise, team_doc.get("_id"), core_doc=team_doc)
            name = disp.get("name") or name
            primary = disp.get("primary_color") or primary
        except Exception:
            pass
    return {
        "team_id": str(team_doc.get("_id")),
        "team_id_string": team_doc.get("team_id"),
        "name": name,
        "primary_color": primary,
        "conference": team_doc.get("conference"),
        "region": team_doc.get("region") or "",
    }


def _natl_rank_for_team(franchise_id: ObjectId, team_id_str: str) -> int | None:
    if not team_id_str:
        return None
    try:
        oid = ObjectId(team_id_str)
    except Exception:
        return None
    ftd = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": oid},
        {"natl_rank": 1},
    )
    if not ftd:
        return None
    rank = ftd.get("natl_rank")
    try:
        return int(rank) if rank is not None else None
    except (TypeError, ValueError):
        return None


def _record_for_team(franchise_doc: dict, team_id_str: str) -> dict[str, int]:
    """Compute season W-L record for a team from franchise.results."""
    if not team_id_str:
        return {"W": 0, "L": 0}
    try:
        franchise_id = franchise_doc.get("_id")
        # calculate_franchise_standings expects ``team_ids_map`` to be a dict
        # whose keys are str(team_id) — only ``.keys()`` is used to seed the
        # standings dict for teams with zero rows in ``franchise.results``.
        team_ids_map = {
            str(d["team_id"]): {}
            for d in franchise_team_data_collection.find(
                {"franchise_id": franchise_id}, {"team_id": 1}
            )
            if d.get("team_id") is not None
        }
        standings = calculate_franchise_standings(
            franchise_doc.get("results", {}) or {},
            team_ids_map,
        )
        row = standings.get(str(team_id_str)) or {}
        return {"W": int(row.get("W", 0) or 0), "L": int(row.get("L", 0) or 0)}
    except Exception as exc:
        logger.warning("[CHAMP-MOMENT] record lookup failed team=%s err=%s", team_id_str, exc)
        return {"W": 0, "L": 0}


def _conference_seed_for_team(
    franchise_doc: dict, conference: int, team_id_str: str
) -> int | None:
    if not team_id_str:
        return None
    conf_tournaments = franchise_doc.get("conference_tournaments") or {}
    ct = conf_tournaments.get(str(int(conference))) or conf_tournaments.get(conference) or {}
    seeds = ct.get("seeds") or {}
    seed = seeds.get(team_id_str) or seeds.get(str(team_id_str))
    if seed is None:
        for k, v in seeds.items():
            if str(k) == str(team_id_str):
                seed = v
                break
    try:
        return int(seed) if seed is not None else None
    except (TypeError, ValueError):
        return None


def _user_team_conference_region(franchise_doc: dict) -> tuple[int | None, str | None, str | None]:
    """Return (conference_int, region_letter, user_team_id_str) for the franchise's user team."""
    from BackEnd.api.franchise_routes import get_user_team_from_franchise  # late import; circular safe

    _name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    if not user_team_id_str:
        return (None, None, None)
    view = _team_view(user_team_id_str, franchise_doc)
    if not view:
        return (None, None, str(user_team_id_str))
    conf = view.get("conference")
    try:
        conf_int = int(conf) if conf is not None else None
    except (TypeError, ValueError):
        conf_int = None
    region = (view.get("region") or "").upper() or None
    return (conf_int, region, str(user_team_id_str))


def _moment_id() -> str:
    return uuid.uuid4().hex


def _existing_moment_signature(moment: dict) -> tuple:
    """Stable key for de-dup. (type, conference|region|None, season, game_id|None)."""
    return (
        moment.get("type"),
        moment.get("conference") or moment.get("region"),
        moment.get("season"),
        moment.get("game_id"),
    )


def enqueue_moment(franchise_id: ObjectId, moment: dict) -> bool:
    """
    Append a moment to the franchise doc's pending list. Idempotent on
    (type, conf|region, season, game_id).

    Returns True if newly added.
    """
    if moment.get("type") not in CHAMPIONSHIP_MOMENT_TYPES:
        logger.warning("[CHAMP-MOMENT] enqueue rejected unknown type=%s", moment.get("type"))
        return False
    moment.setdefault("id", _moment_id())
    fresh = db.franchises.find_one(
        {"_id": franchise_id}, {PENDING_MOMENTS_FIELD: 1}
    ) or {}
    existing = fresh.get(PENDING_MOMENTS_FIELD) or []
    sig = _existing_moment_signature(moment)
    for m in existing:
        if _existing_moment_signature(m) == sig:
            return False
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$push": {PENDING_MOMENTS_FIELD: moment}},
    )
    logger.warning(
        "[CHAMP-MOMENT] enqueued type=%s franchise_id=%s conf=%s region=%s game=%s id=%s",
        moment.get("type"),
        str(franchise_id),
        moment.get("conference"),
        moment.get("region"),
        (moment.get("game_id") or "")[:10],
        moment.get("id", "")[:8],
    )
    return True


def list_moments(franchise_doc: dict) -> list[dict]:
    moments = franchise_doc.get(PENDING_MOMENTS_FIELD) or []
    if not isinstance(moments, list):
        return []
    return [m for m in moments if isinstance(m, dict) and m.get("type") in CHAMPIONSHIP_MOMENT_TYPES]


def consume_moment(franchise_id: ObjectId, moment_id: str) -> bool:
    """Remove a moment from the queue by id. Returns True on removal."""
    if not moment_id:
        return False
    res = db.franchises.update_one(
        {"_id": franchise_id},
        {"$pull": {PENDING_MOMENTS_FIELD: {"id": moment_id}}},
    )
    return bool(res.modified_count)


def build_championship_game_moment(
    franchise_doc: dict,
    *,
    game_meta: dict,
    away_id: Any,
    home_id: Any,
    away_score: int,
    home_score: int,
    game_id: str | None,
) -> dict | None:
    """
    Map a freshly-recorded EOS championship game to its moment payload.

    Returns None if the game is not the user's championship (different conf/region,
    or not a final-round phase game).
    """
    phase = (game_meta or {}).get("phase")
    rnd = int((game_meta or {}).get("round") or 0)

    user_conf, user_region, user_team_id_str = _user_team_conference_region(franchise_doc)
    moment_type: str | None = None
    conference: int | None = None
    region: str | None = None

    if phase == "conference" and rnd == 3:
        try:
            game_conf = int(game_meta.get("conference"))
        except (TypeError, ValueError):
            return None
        if user_conf is None or game_conf != user_conf:
            return None
        moment_type = MOMENT_CONFERENCE
        conference = game_conf
    elif phase == "region" and rnd == 2:
        game_region = (game_meta.get("region") or "").upper()
        if not game_region or user_region is None or game_region != user_region:
            return None
        moment_type = MOMENT_REGION
        region = game_region
    elif phase == "national" and rnd == 3:
        moment_type = MOMENT_NATIONAL
    else:
        return None

    winner_id = home_id if int(home_score) > int(away_score) else away_id
    loser_id = away_id if int(home_score) > int(away_score) else home_id
    winner_score = max(int(home_score), int(away_score))
    loser_score = min(int(home_score), int(away_score))

    winner_view = _team_view(winner_id, franchise_doc) or {}
    loser_view = _team_view(loser_id, franchise_doc) or {}

    franchise_id = franchise_doc.get("_id")
    natl_rank = _natl_rank_for_team(franchise_id, winner_view.get("team_id", ""))
    record = _record_for_team(franchise_doc, winner_view.get("team_id", ""))

    return {
        "id": _moment_id(),
        "type": moment_type,
        "season": int(franchise_doc.get("current_season", 1) or 1),
        "conference": conference,
        "region": region,
        "winner_team_id": winner_view.get("team_id"),
        "winner_team_name": winner_view.get("name"),
        "winner_primary_color": winner_view.get("primary_color"),
        "winner_natl_rank": natl_rank,
        "winner_record": record,
        "loser_team_id": loser_view.get("team_id"),
        "loser_team_name": loser_view.get("name"),
        "score": {"winner": winner_score, "loser": loser_score},
        "game_id": str(game_id) if game_id else None,
        "user_is_winner": bool(
            user_team_id_str
            and winner_view.get("team_id")
            and str(user_team_id_str) == str(winner_view.get("team_id"))
        ),
    }


def championship_moment_from_game_doc(
    franchise_doc: dict,
    game_doc: dict,
) -> dict | None:
    """
    Build a Variation A/B moment payload from a finalized game doc when it
    represents the user's conference / region / national championship.

    Used by ``GET /franchise/championship-context`` to power the live-game branch
    in the EOG modal — the game doc may not yet carry a stamped ``eos_meta`` at
    EOG time, so we re-derive the bracket slot here.
    """
    if not isinstance(game_doc, dict) or not isinstance(franchise_doc, dict):
        return None

    eos_meta = game_doc.get("eos_meta") or {}
    phase = eos_meta.get("phase") if isinstance(eos_meta, dict) else None
    rnd = eos_meta.get("round") if isinstance(eos_meta, dict) else None
    conference = eos_meta.get("conference") if isinstance(eos_meta, dict) else None
    region = eos_meta.get("region") if isinstance(eos_meta, dict) else None

    # Fallback: derive phase/round from the franchise's own bracket state.
    if phase is None or rnd is None:
        try:
            from BackEnd.tournament import franchise_tournament as ft

            game_id_str = str(game_doc.get("_id") or "")
            week = int(game_doc.get("week") or 0)
            week_meta = ft.get_eos_week_games(franchise_doc, week, include_completed=True) if week in ft.EOS_WEEKS else []
            for g in week_meta:
                if str(g.get("game_id") or "") == game_id_str:
                    phase = g.get("phase")
                    rnd = g.get("round")
                    conference = g.get("conference")
                    region = g.get("region")
                    break
        except Exception:
            logger.exception("[CHAMP-MOMENT] derive_meta_from_franchise failed")

    is_final = (
        (phase == "conference" and int(rnd or 0) == 3)
        or (phase == "region" and int(rnd or 0) == 2)
        or (phase == "national" and int(rnd or 0) == 3)
    )
    if not is_final:
        return None

    # Saved franchise game docs store team identifiers as canonical team_id
    # keys (e.g. "HARVEST"), not ObjectId hex strings. The unified ``teams``
    # object is keyed by those same identifiers and carries name + score.
    home_id = game_doc.get("home_team_id") or game_doc.get("homeTeamId")
    away_id = game_doc.get("away_team_id") or game_doc.get("awayTeamId")
    teams_obj = game_doc.get("teams") or {}
    home_team_obj = teams_obj.get(home_id) or teams_obj.get(str(home_id)) if home_id is not None else None
    away_team_obj = teams_obj.get(away_id) or teams_obj.get(str(away_id)) if away_id is not None else None
    score_map = game_doc.get("score") or game_doc.get("final_score") or {}

    def _score_from(team_obj: Any, fallback_name: str | None) -> int:
        if isinstance(team_obj, dict) and team_obj.get("score") is not None:
            try:
                return int(team_obj.get("score"))
            except (TypeError, ValueError):
                pass
        if fallback_name and isinstance(score_map, dict):
            try:
                return int(score_map.get(fallback_name, 0) or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    home_name = home_team_obj.get("name") if isinstance(home_team_obj, dict) else None
    away_name = away_team_obj.get("name") if isinstance(away_team_obj, dict) else None
    home_score = _score_from(home_team_obj, home_name)
    away_score = _score_from(away_team_obj, away_name)

    synthetic_meta = {
        "phase": phase,
        "round": rnd,
        "conference": conference,
        "region": region,
    }
    return build_championship_game_moment(
        franchise_doc,
        game_meta=synthetic_meta,
        away_id=away_id,
        home_id=home_id,
        away_score=away_score,
        home_score=home_score,
        game_id=str(game_doc.get("_id") or ""),
    )


def maybe_enqueue_championship_game_moment(
    franchise_doc: dict,
    *,
    game_meta: dict,
    away_id: Any,
    home_id: Any,
    away_score: int,
    home_score: int,
    game_id: str | None,
) -> dict | None:
    """Build + enqueue (idempotent) a championship game moment. Returns the moment or None."""
    moment = build_championship_game_moment(
        franchise_doc,
        game_meta=game_meta,
        away_id=away_id,
        home_id=home_id,
        away_score=away_score,
        home_score=home_score,
        game_id=game_id,
    )
    if not moment:
        return None
    franchise_id = franchise_doc.get("_id")
    if not isinstance(franchise_id, ObjectId):
        return None
    enqueue_moment(franchise_id, moment)
    return moment


def enqueue_trophy_spotlight_for_user_conference(franchise_doc: dict) -> dict | None:
    """
    Queue Variation C for the regular-season champion (1-seed) of the USER's
    conference. Called once at week 26 -> 27 (after conference_tournaments
    initialized so seeds are available).
    """
    franchise_id = franchise_doc.get("_id")
    if not isinstance(franchise_id, ObjectId):
        return None
    user_conf, _user_region, user_team_id_str = _user_team_conference_region(franchise_doc)
    if user_conf is None:
        logger.warning(
            "[CHAMP-MOMENT] trophy_spotlight skipped: user conference unknown franchise_id=%s",
            str(franchise_id),
        )
        return None
    conf_tournaments = franchise_doc.get("conference_tournaments") or {}
    ct = conf_tournaments.get(str(user_conf)) or conf_tournaments.get(user_conf) or {}
    seeds = ct.get("seeds") or {}
    one_seed_id_str: str | None = None
    for tid, seed in seeds.items():
        try:
            seed_int = int(seed)
        except (TypeError, ValueError):
            continue
        if seed_int == 1:
            one_seed_id_str = str(tid)
            break
    if not one_seed_id_str:
        logger.warning(
            "[CHAMP-MOMENT] trophy_spotlight skipped: no 1-seed found conf=%s franchise_id=%s",
            user_conf,
            str(franchise_id),
        )
        return None
    winner_view = _team_view(one_seed_id_str, franchise_doc) or {}
    record = _record_for_team(franchise_doc, one_seed_id_str)
    natl_rank = _natl_rank_for_team(franchise_id, one_seed_id_str)

    moment = {
        "id": _moment_id(),
        "type": MOMENT_TROPHY_SPOTLIGHT,
        "season": int(franchise_doc.get("current_season", 1) or 1),
        "conference": user_conf,
        "winner_team_id": winner_view.get("team_id"),
        "winner_team_name": winner_view.get("name"),
        "winner_primary_color": winner_view.get("primary_color"),
        "winner_natl_rank": natl_rank,
        "winner_record": record,
        "winner_seed": 1,
        "user_is_winner": bool(
            user_team_id_str and str(user_team_id_str) == one_seed_id_str
        ),
    }
    enqueue_moment(franchise_id, moment)
    return moment


def enqueue_banner_raise_if_user_won_national(franchise_doc: dict) -> dict | None:
    """
    Called from finish_season (during week 36 -> next-season transition) BEFORE
    the franchise rollover wipes the prior season's tournaments. If the user's
    team was the national champion, queue Variation D for first FCC mount of the
    new season.
    """
    franchise_id = franchise_doc.get("_id")
    if not isinstance(franchise_id, ObjectId):
        return None
    _user_conf, _user_region, user_team_id_str = _user_team_conference_region(franchise_doc)
    if not user_team_id_str:
        return None
    national_tournament = franchise_doc.get("national_tournament") or {}
    bracket = national_tournament.get("bracket") or {}
    final = bracket.get("final") or []
    if not final:
        return None
    final_match = final[0] if isinstance(final, list) and final else {}
    winner_str = str(final_match.get("winner") or "")
    if not winner_str or winner_str != str(user_team_id_str):
        return None

    winner_view = _team_view(user_team_id_str, franchise_doc) or {}
    record = _record_for_team(franchise_doc, user_team_id_str)
    natl_rank = _natl_rank_for_team(franchise_id, str(user_team_id_str))
    score = final_match.get("score") or {}

    moment = {
        "id": _moment_id(),
        "type": MOMENT_BANNER_RAISE,
        "season": int(franchise_doc.get("current_season", 1) or 1),
        "winner_team_id": winner_view.get("team_id"),
        "winner_team_name": winner_view.get("name"),
        "winner_primary_color": winner_view.get("primary_color"),
        "winner_natl_rank": natl_rank,
        "winner_record": record,
        "score": {
            "home": int(score.get("home", 0) or 0),
            "away": int(score.get("away", 0) or 0),
        }
        if score
        else None,
        "game_id": str(final_match.get("game_id")) if final_match.get("game_id") else None,
        "user_is_winner": True,
    }
    enqueue_moment(franchise_id, moment)
    return moment
