"""Lean-movement event log — reporting only.

Recruiting mechanics are unchanged by this module. Lean movement already happens at
two sites in ``franchise_routes.py`` (``_apply_team_to_recruit_performance_lean`` and
``_update_recruit_lean_after_visit``); both hold ``old_lean`` and ``new_lean`` in the
same scope and previously discarded everything except one additions-only boolean.
``diff_lean`` recovers the rest with no extra DB reads.

A lean ladder is ``{"1": team_id|None, "2": ..., "3": ...}``. Slot "1" additionally
uses the sentinel ``"open"`` (see ``_lean_has_open_slot``), which means *vacant* — it
is normalized away here so a vacancy is never mistaken for a rival team.

Events are emitted **relative to the user's team**, which is the write-time filter the
build plan calls for: a mutation on a recruit the user has no relationship with
returns ``[]`` and therefore persists nothing.
"""

from __future__ import annotations

from typing import Any, Iterable

# Slot "1" carries an "open" sentinel meaning vacant; "" appears in legacy docs.
_EMPTY_SLOT_VALUES = (None, "", "open")

RANKS = ("1", "2", "3")

# Event kinds. All are stated from the user's point of view.
GAINED_YOU = "gained_you"
DROPPED_YOU = "dropped_you"
MOVED_UP = "moved_up"
MOVED_DOWN = "moved_down"
RIVAL_TOOK_YOUR_TOP = "rival_took_your_top"
DISPLACED = "displaced"

EVENT_KINDS = (
    GAINED_YOU,
    DROPPED_YOU,
    MOVED_UP,
    MOVED_DOWN,
    RIVAL_TOOK_YOUR_TOP,
    DISPLACED,
)


def normalize_lean(lean_doc: dict | None) -> dict[str, str | None]:
    """Ladder with vacancies as None. ``"open"`` is a vacancy, not a team."""
    normalized: dict[str, str | None] = {"1": None, "2": None, "3": None}
    for rank in RANKS:
        value = (lean_doc or {}).get(rank)
        normalized[rank] = None if value in _EMPTY_SLOT_VALUES else str(value)
    return normalized


def rank_of(lean: dict[str, str | None], team_id: str) -> int | None:
    """1-based ladder position of team_id, or None when absent."""
    if not team_id:
        return None
    target = str(team_id)
    for rank in RANKS:
        if lean.get(rank) == target:
            return int(rank)
    return None


def _teams_on(lean: dict[str, str | None]) -> set[str]:
    return {value for value in lean.values() if value}


def diff_lean(
    old_lean: dict | None,
    new_lean: dict | None,
    *,
    user_team_id: str | None,
    actor_team_id: str | None = None,
    cause: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Movement between two ladders, expressed as user-relevant events.

    Pure — no I/O, no mutation of its arguments.

    ``user_team_id`` is required for the kind names to mean anything (the build plan's
    ``diff_lean(old, new)`` shorthand omits it). ``actor_team_id`` is the team whose
    action produced ``new_lean``; ``cause`` is opaque here and passed through for the
    copy layer.

    At most one event describes the user's own movement, plus one ``displaced`` per
    third-party team knocked off a ladder the user is on. Returns ``[]`` when nothing
    changed or when the user has no relationship with this recruit.
    """
    old = normalize_lean(old_lean)
    new = normalize_lean(new_lean)
    if old == new:
        return []

    user = str(user_team_id) if user_team_id else ""
    if not user:
        return []

    old_rank = rank_of(old, user)
    new_rank = rank_of(new, user)

    # Not on the ladder before or after -> not user-relevant, regardless of churn.
    if old_rank is None and new_rank is None:
        return []

    def _event(kind: str, **extra: Any) -> dict[str, Any]:
        event: dict[str, Any] = {
            "kind": kind,
            "prev_rank": old_rank,
            "rank": new_rank,
            "actor_team_id": str(actor_team_id) if actor_team_id else None,
            "top_team_id": new.get("1"),
            "prev_top_team_id": old.get("1"),
        }
        if cause:
            event["cause"] = dict(cause)
        event.update(extra)
        return event

    events: list[dict[str, Any]] = []

    if old_rank is None and new_rank is not None:
        events.append(_event(GAINED_YOU))
    elif old_rank is not None and new_rank is None:
        events.append(_event(DROPPED_YOU))
    elif old_rank is not None and new_rank is not None and new_rank != old_rank:
        if new_rank < old_rank:
            events.append(_event(MOVED_UP))
        elif old_rank == 1:
            # More specific than moved_down: the user held #1 and a rival took it.
            events.append(_event(RIVAL_TOOK_YOUR_TOP, rival_team_id=new.get("1")))
        else:
            events.append(_event(MOVED_DOWN))
    elif old_rank == 1 and new_rank == 1 and old.get("1") != new.get("1"):
        # Defensive: same rank, different occupant should be impossible.
        events.append(_event(RIVAL_TOOK_YOUR_TOP, rival_team_id=new.get("1")))

    # Third parties knocked off a ladder the user is on — the field changed even when
    # the user's own rank did not.
    #
    # SUPPRESSED whenever this same diff also moved the user. One lean recalc has one
    # cause, so a team falling off alongside any user movement did so as part of that
    # same change — it isn't independent news. It also makes the copy lie: the sentence
    # is "dropped Lancaster — you're still #3", and "still" is only true when the user
    # held #3 through the change. Paired with a gain, a slide, a takeover or a drop it
    # claims continuity the player never had:
    #
    #     moved Crickstown to #1 — you're now #2
    #     dropped Appalachia — you're still #2      <- they were #1 a moment ago
    #
    # Because the block above emits at most one event, and only for the user's own
    # standing, "the user did not move" is exactly "nothing has been emitted yet".
    # displaced is the bystander kind: it fires only when the user held position.
    user_moved = bool(events)
    if not user_moved:
        for gone in sorted(_teams_on(old) - _teams_on(new)):
            if gone != user:
                events.append(_event(DISPLACED, displaced_team_id=gone))

    return events


# ---------------------------------------------------------------------------
# Copy — events read as sentences with causes, not as data.
# ---------------------------------------------------------------------------

def _cause_clause(cause: dict[str, Any] | None, name_of) -> str:
    """Trailing clause explaining *why*, or "" when the cause is unknown."""
    if not cause:
        return ""
    kind = cause.get("type")
    opponent = name_of(cause.get("opponent_team_id")) if cause.get("opponent_team_id") else ""
    if kind == "win" and opponent:
        return f"after the {opponent} win"
    if kind == "quality_loss" and opponent:
        return f"after the close {opponent} loss"
    if kind == "visit":
        return "after your visit" if cause.get("by_user") else "after a rival visit"
    return ""


def render_lean_event(
    event: dict[str, Any],
    recruit_name: str,
    name_of,
) -> str:
    """One sentence for a single event.

    ``name_of(team_id) -> str`` resolves display names; it may return "" for unknown
    teams, in which case the clause that needed the name is dropped rather than
    rendering a blank.
    """
    kind = event.get("kind")
    rank = event.get("rank")
    prev_rank = event.get("prev_rank")
    recruit = recruit_name or "A recruit"
    cause = _cause_clause(event.get("cause"), name_of)

    if kind == GAINED_YOU:
        head = f"{recruit} added you at #{rank}"
    elif kind == DROPPED_YOU:
        head = f"{recruit} dropped you"
        top = name_of(event.get("top_team_id"))
        if top:
            # The rival cause is more informative than the game cause on a drop.
            return f"{head} — {top} moved to #1"
    elif kind == MOVED_UP:
        head = f"{recruit} moved you to #{rank}"
    elif kind == MOVED_DOWN:
        head = f"{recruit} moved you down to #{rank}"
    elif kind == RIVAL_TOOK_YOUR_TOP:
        rival = name_of(event.get("rival_team_id") or event.get("top_team_id"))
        head = (
            f"{recruit} moved {rival} to #1 — you're now #{rank}"
            if rival
            else f"{recruit} moved you down to #{rank}"
        )
        return head
    elif kind == DISPLACED:
        other = name_of(event.get("displaced_team_id"))
        if not other:
            return ""
        head = f"{recruit} dropped {other}"
        if rank:
            return f"{head} — you're still #{rank}"
    else:
        return ""

    return f"{head} — {cause}" if cause else head


def summarize_kinds(events: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Per-kind counts, for the write-time diagnostic log."""
    counts: dict[str, int] = {}
    for event in events:
        kind = str(event.get("kind") or "")
        if kind:
            counts[kind] = counts.get(kind, 0) + 1
    return counts


# Kinds that changed the user's own standing, as opposed to the surrounding field.
_MOVED_KINDS = frozenset({GAINED_YOU, MOVED_UP, MOVED_DOWN, RIVAL_TOOK_YOUR_TOP})


def wire_counts(events: Iterable[dict[str, Any]]) -> dict[str, int]:
    """``{"moved": n, "dropped": m}`` for the secondary button's count line.

    ``displaced`` is deliberately excluded from both totals: a rival falling off a
    ladder is context for the card, not a change to the user's own standing, and
    counting it would inflate "moved" with events the player didn't experience as
    movement.
    """
    moved = 0
    dropped = 0
    for event in events:
        kind = str(event.get("kind") or "")
        if kind == DROPPED_YOU:
            dropped += 1
        elif kind in _MOVED_KINDS:
            moved += 1
    return {"moved": moved, "dropped": dropped}


# How far back a displacement is remembered before the same one is news again.
# The performance rule ("team already at 1 -> remove the lowest other occupied lean")
# fires on every successful roll, so a rival can be dropped, re-added into the freed
# slot, and dropped again within a couple of weeks. Raising this quietens the feed
# further; lowering it lets near-identical lines back in.
DISPLACED_REPEAT_LOOKBACK_WEEKS = 4


def filter_repeat_displacements(
    events: list[dict[str, Any]],
    events_by_week: dict[str, Any] | None,
    week: int,
    lookback_weeks: int = DISPLACED_REPEAT_LOOKBACK_WEEKS,
) -> list[dict[str, Any]]:
    """Drop ``displaced`` events already reported for the same recruit + team recently.

    A team at #1 removes the lowest lean every time it rolls (Recruiting_System.md §5),
    and the freed slot is refilled by the next team that rolls in — so the same rival is
    dropped from the same recruit over and over. Only the removals are user-relevant, so
    the arrivals between them are silent and the feed shows the identical sentence twice
    with nothing in between, which reads as a duplicated message rather than churn.

    Suppressing the repeat is preferred over reporting the arrival: the arrival is not
    news to the player, and emitting it would roughly double the feed's volume to say
    nothing about their own standing.

    Only ``displaced`` is filtered. Events about the user's own standing are always kept
    — a repeated drop or gain is real news every time it happens.
    """
    if not events:
        return events
    try:
        current_week = int(week)
    except (TypeError, ValueError):
        return events

    floor = current_week - max(0, int(lookback_weeks or 0))
    seen: set[tuple[str, str]] = set()
    for raw_week, raw_events in (events_by_week or {}).items():
        try:
            past_week = int(raw_week)
        except (TypeError, ValueError):
            continue
        # `< current_week` so a re-run of THIS week cannot suppress against itself.
        if past_week < floor or past_week >= current_week:
            continue
        for event in raw_events if isinstance(raw_events, list) else []:
            if event.get("kind") != DISPLACED:
                continue
            key = (str(event.get("recruit_id") or ""), str(event.get("displaced_team_id") or ""))
            if all(key):
                seen.add(key)

    kept: list[dict[str, Any]] = []
    for event in events:
        if event.get("kind") == DISPLACED:
            key = (str(event.get("recruit_id") or ""), str(event.get("displaced_team_id") or ""))
            if all(key) and key in seen:
                continue
            if all(key):
                seen.add(key)   # also collapses repeats WITHIN this week's batch
        kept.append(event)
    return kept


def unseen_events(
    events_by_week: dict[str, Any] | None,
    seen_week: int,
) -> list[dict[str, Any]]:
    """Events from weeks after ``seen_week``, newest week first.

    The marker is a week number, not a boolean, precisely so "seen week 12" and
    "seen week 13" are distinguishable within one season.
    """
    return _flatten_weeks(events_by_week, minimum_week=int(seen_week or 0) + 1)


def recent_events(
    events_by_week: dict[str, Any] | None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """All recorded events, newest week first — the Wire card's feed."""
    flat = _flatten_weeks(events_by_week, minimum_week=None)
    return flat[:limit] if limit else flat


def _flatten_weeks(
    events_by_week: dict[str, Any] | None,
    minimum_week: int | None,
) -> list[dict[str, Any]]:
    weeks: list[tuple[int, list[dict[str, Any]]]] = []
    for raw_week, raw_events in (events_by_week or {}).items():
        try:
            week = int(raw_week)
        except (TypeError, ValueError):
            continue
        if minimum_week is not None and week < minimum_week:
            continue
        if isinstance(raw_events, list):
            weeks.append((week, raw_events))
    weeks.sort(key=lambda pair: pair[0], reverse=True)
    flat: list[dict[str, Any]] = []
    for week, week_events in weeks:
        for event in week_events:
            entry = dict(event)
            entry.setdefault("week", week)
            flat.append(entry)
    return flat
