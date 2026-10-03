"""Route-level detectors for the three new Office moments (Chapter 7).

Elimination, the end-of-season review and the signing-class summary are all read
off data the game already stores — the tournament brackets, the season snapshot
reader in ``career_data`` and the week-35 signing results. Nothing here writes a
franchise field, hooks the sim or invents a value: a field whose source is absent
is omitted from the payload.

The bracket blobs are passed in by the caller (``_user_eos_bracket_and_seeds``),
so this module stays pure and does no database work of its own.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

# EOS tiers in calendar order. A loss only ends the season when no later tier
# still awaits the team.
TIER_ORDER = ("conference", "region", "national")

# Which calendar week each bracket slot is played on, so the stored round can be
# named with the Advance ladder's existing labels (ROUND_NAME_BY_WEEK). The weeks
# are the same ones BRACKET_REVEAL_WEEKS / BRACKET_UPDATE_WEEKS key off.
ROUND_WEEK = {
    ("conference", "round1"): 27,
    ("conference", "round2"): 28,
    ("conference", "final"): 29,
    ("region", "round1"): 30,
    ("region", "final"): 31,
    ("national", "round1"): 32,
    ("national", "round2"): 33,
    ("national", "final"): 34,
}

_ROUND_KEYS = ("round1", "round2", "final")


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _teams(matchup: Mapping[str, Any]) -> tuple[str, str]:
    return str(matchup.get("home_team") or ""), str(matchup.get("away_team") or "")


def user_in_bracket(bracket: Mapping[str, Any] | None, team_id: Any) -> bool:
    """True when the team holds a slot in any round of this bracket.

    Decides whether a bracket reveal is the coach's own milestone or a weekly note:
    the reveal only pops when the user's team is in the bracket being revealed.
    """
    tid = str(team_id or "")
    if not tid or not isinstance(bracket, Mapping):
        return False
    for round_key in _ROUND_KEYS:
        for matchup in bracket.get(round_key) or []:
            if isinstance(matchup, Mapping) and tid in _teams(matchup):
                return True
    return False


def _user_loss_in_bracket(
    bracket: Mapping[str, Any] | None,
    team_id: str,
) -> Optional[tuple[str, Mapping[str, Any]]]:
    """``(round_key, matchup)`` for the team's decided loss, latest round first."""
    if not isinstance(bracket, Mapping):
        return None
    for round_key in reversed(_ROUND_KEYS):
        for matchup in bracket.get(round_key) or []:
            if not isinstance(matchup, Mapping):
                continue
            if team_id not in _teams(matchup):
                continue
            winner = str(matchup.get("winner") or "")
            if winner and winner != team_id:
                return round_key, matchup
    return None


def _score_for(matchup: Mapping[str, Any], team_id: str) -> Optional[dict[str, int]]:
    """``{user, opponent}`` from the stored ``{home, away}`` score, or None."""
    score = matchup.get("score")
    if not isinstance(score, Mapping):
        return None
    home_id, _away_id = _teams(matchup)
    home = _int(score.get("home"))
    away = _int(score.get("away"))
    if home is None or away is None:
        return None
    user_is_home = home_id == team_id
    return {
        "user": home if user_is_home else away,
        "opponent": away if user_is_home else home,
    }


def _opponent_of(matchup: Mapping[str, Any], team_id: str) -> str:
    home_id, away_id = _teams(matchup)
    return away_id if home_id == team_id else home_id


def elimination_payload(
    *,
    tier_brackets: Sequence[tuple[str, Mapping[str, Any] | None, Mapping[str, Any] | None]],
    team_id: Any,
    season: Any,
    region_qualified: bool,
    seen_season: Any = None,
    round_name_by_week: Mapping[int, str] | None = None,
    team_name_of: Callable[[str], Optional[str]] | None = None,
    record: Mapping[str, Any] | None = None,
    conference_place: Any = None,
    national_rank: Any = None,
) -> Optional[dict[str, Any]]:
    """The season-ending tournament loss, or None.

    The team is eliminated when it lost its latest decided tournament matchup and
    no later tournament still awaits it: a conference loss only ends the season
    for a team that did not qualify for its region, while a region or national
    loss always does. Once per season — the caller stamps ``seen_season``.
    """
    tid = str(team_id or "")
    season_n = _int(season)
    if not tid or season_n is None:
        return None
    if _int(seen_season) == season_n:
        return None

    by_tier = {str(tier): (bracket, seeds) for tier, bracket, seeds in tier_brackets}
    loss: Optional[tuple[str, str, Mapping[str, Any]]] = None
    for tier in TIER_ORDER:
        bracket, _seeds = by_tier.get(tier, (None, None))
        found = _user_loss_in_bracket(bracket, tid)
        if found:
            loss = (tier, found[0], found[1])
    if loss is None:
        return None
    tier, round_key, matchup = loss
    if tier == "conference" and region_qualified:
        # The conference run ended but the region tournament still awaits.
        return None

    payload: dict[str, Any] = {
        "eligible": True,
        "season": season_n,
        "tier": tier,
        "round_key": round_key,
    }
    week = ROUND_WEEK.get((tier, round_key))
    round_name = (round_name_by_week or {}).get(week) if week is not None else None
    if round_name:
        payload["round_name"] = round_name

    opponent_id = _opponent_of(matchup, tid)
    if opponent_id:
        payload["opponent_team_id"] = opponent_id
        name = team_name_of(opponent_id) if team_name_of else None
        if name:
            payload["opponent_team_name"] = str(name)
    score = _score_for(matchup, tid)
    if score:
        payload["score"] = score
    game_id = matchup.get("game_id")
    if game_id:
        payload["game_id"] = str(game_id)

    wins = _int((record or {}).get("wins"))
    losses = _int((record or {}).get("losses"))
    if wins is not None and losses is not None:
        payload["record"] = {"wins": wins, "losses": losses}
    place = _int(conference_place)
    if place is not None:
        payload["conference_place"] = place
    rank = _int(national_rank)
    if rank is not None and rank > 0:
        payload["national_rank"] = rank

    _seeds = (by_tier.get(tier) or (None, None))[1]
    if isinstance(_seeds, Mapping):
        # Conference and national blobs store a seeds map; region brackets do not,
        # so a region elimination simply carries no seeds.
        user_seed = _int(_seeds.get(tid))
        opponent_seed = _int(_seeds.get(opponent_id)) if opponent_id else None
        if user_seed is not None:
            payload["user_seed"] = user_seed
        if opponent_seed is not None:
            payload["opponent_seed"] = opponent_seed
    return payload


def season_review_payload(
    franchise_doc: Mapping[str, Any] | None,
    team_id: Any,
    *,
    season_over: bool,
    seen_season: Any = None,
) -> Optional[dict[str, Any]]:
    """The end-of-season review, once the season's games are all played.

    Reads the same ``season_record_detail`` ``finish_season`` stores on the
    ``season_record`` trophy (wins/losses/conf_finish plus the snapshot), so
    the live review and the stored review always match. Titles come from the
    season's title trophies — the same list the Trophy Case review uses.
    """
    from BackEnd.utils.trophy_log import season_record_detail, title_trophies_for_season

    if not season_over or not isinstance(franchise_doc, Mapping):
        return None
    season_n = _int(franchise_doc.get("current_season")) or 1
    if _int(seen_season) == season_n:
        return None
    try:
        snapshot = season_record_detail(franchise_doc, team_id)
    except Exception:
        logger.exception("[MOMENTS] season review snapshot failed")
        return None
    payload = {"eligible": True, "season": season_n, **snapshot}
    titles = title_trophies_for_season(franchise_doc)
    if titles:
        payload["titles"] = titles
    return payload


def signed_class_payload(
    franchise_doc: Mapping[str, Any] | None,
    team_id: Any,
    *,
    results_modal: Mapping[str, Any] | None,
    hub_reveal_seen: bool,
) -> Optional[dict[str, Any]]:
    """The one-time Office summary of the signing class.

    Gated on the week-35 hub reveal having been seen, so the Office never
    pre-empts the live Signing Day beat (Jamie's decision 24). Eligibility and the
    class size come from the existing recruiting-results modal payload; the recruit
    rows come from the same reader the Trophy Case review uses, so both surfaces
    show one shape.
    """
    from BackEnd.utils.career_data import class_signed

    if not hub_reveal_seen or not isinstance(franchise_doc, Mapping):
        return None
    if not (isinstance(results_modal, Mapping) and results_modal.get("eligible")):
        return None
    recruits = class_signed(franchise_doc, team_id)
    if not recruits:
        return None
    return {
        "eligible": True,
        "recruits": recruits,
        "count": _int(results_modal.get("count")) or len(recruits),
    }


def first_archetype_payload(archetype_signals: Mapping[str, Any] | None) -> Optional[dict[str, Any]]:
    """The first time a coach's lead archetype is established, before its reveal.

    Same gate the existing reveal uses (``archetype_reveal_seen === false &&
    lead_archetype``). An *evolution* is a different, weekly-tier moment, so a
    pending evolution is not a first establish.
    """
    signals = archetype_signals or {}
    lead = str(signals.get("lead_archetype") or "").strip()
    if not lead or signals.get("archetype_reveal_seen"):
        return None
    if str(signals.get("archetype_evolution_pending") or "").strip():
        return None
    return {"eligible": True, "archetype": lead}
