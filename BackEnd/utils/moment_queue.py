"""Server-side Office moment queue (Chapter 7).

Reads the eligibility flags and payloads already built for command-center data.
Does not write franchise fields, enqueue finalize work, or change the sim.

Tiers
    EVERYDAY     — no pop-up (none of today's modal flags)
    WEEKLY       — Office card only (`weekly_card_items`, and one `also` row)
    MILESTONE    — pop-up candidate
    SEASON PEAK  — pop-up candidate

Priority (lower number first). Documented in UX_System §10.
    10  championship          SEASON PEAK  long   gold   STING_SEASON_PEAK
    15  season_review         SEASON PEAK  long   gold   STING_SEASON_PEAK
    20  elimination           MILESTONE    short  quiet  —
    30  bracket_reveal        MILESTONE    long   gold   STING_MILESTONE
    40  signed_class          MILESTONE    long   gold   STING_MILESTONE
    50  walk_on_welcome       MILESTONE    long   gold   STING_MILESTONE
    60  region_bye            MILESTONE    short  gold   STING_MILESTONE
    65  conference_rs_region  MILESTONE    short  gold   STING_MILESTONE
    70  first_archetype       MILESTONE    short  gold   STING_MILESTONE
    80  bracket_update        WEEKLY
    90  recruit_visit         WEEKLY
   100  archetype_evolution   WEEKLY
   110  bracket_reveal        WEEKLY  (the user's team is not in the revealed bracket)

Cap
    A season peak shows alone: when one is eligible, this visit is the season-peak
    items only — a championship and a review together are exactly
    [championship, season_review], shown as "1 of 2 / 2 of 2".
    Otherwise `moments_for_this_visit` is the first pop-up-tier item, plus a second
    only when the first is `duration=short` and the second is a pop-up tier.
    Remaining pop-up-tier items stay in `moments` (still eligible next visit — seen
    keys are unchanged). WEEKLY items go to `weekly_card_items` and never take a
    pop-up slot; the highest-priority one is also offered as `also`.

`recruiting_results_modal` is not queued as itself. The signing class is the
`signed_class` milestone, eligible only after the week-35 hub reveal has been
seen, so the Office summarises a beat the hub already played.
"""

from __future__ import annotations

from typing import Any

TIER_EVERYDAY = "EVERYDAY"
TIER_WEEKLY = "WEEKLY"
TIER_MILESTONE = "MILESTONE"
TIER_SEASON_PEAK = "SEASON_PEAK"

POPUP_TIERS = frozenset({TIER_MILESTONE, TIER_SEASON_PEAK})

STYLE_GOLD = "gold"
STYLE_QUIET = "quiet"

# Sound cue slots. The client owns playback (and the files do not exist yet);
# the server only says which cue a moment carries.
STING_SEASON_PEAK = "STING_SEASON_PEAK"
STING_MILESTONE = "STING_MILESTONE"

ARCHETYPES_HREF = "/coaching-archetypes.html"

WEEKLY_HREF = {
    "bracket_update": "/franchise-command-center.html?tab=tournament-view",
    "recruit_visit": "/recruiting.html",
    "bracket_reveal": "/franchise-command-center.html?tab=tournament-view",
    # Online only: the coaching-archetypes page is a community surface.
    "archetype_evolution": ARCHETYPES_HREF,
}


def _item(
    *,
    kind: str,
    tier: str,
    priority: int,
    payload_ref: str,
    seen_key: str,
    duration: str | None = None,
    title: str,
    line: str,
    href: str | None = None,
    style: str | None = None,
    sting: str | None = None,
) -> dict[str, Any]:
    """One queue row. ``style`` and ``sting`` are decided here, never by the client."""
    if style is None and tier in POPUP_TIERS:
        style = STYLE_GOLD
    if sting is None and style == STYLE_GOLD:
        sting = STING_SEASON_PEAK if tier == TIER_SEASON_PEAK else STING_MILESTONE
    row: dict[str, Any] = {
        "id": kind,
        "kind": kind,
        "tier": tier,
        "priority": priority,
        "payload_ref": payload_ref,
        "seen_key": seen_key,
        "title": title,
        "line": line,
        "style": style,
        "sting": sting,
    }
    if duration:
        row["duration"] = duration
    if href:
        row["href"] = href
    return row


def _eligible_payload(payload: Any) -> bool:
    return bool(isinstance(payload, dict) and payload.get("eligible"))


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def collect_moments(
    *,
    championship_moments: list[Any] | None = None,
    season_review: dict[str, Any] | None = None,
    elimination: dict[str, Any] | None = None,
    conference_rs_region_modal: dict[str, Any] | None = None,
    region_bye_modal_eligible: bool = False,
    walk_on_welcome_modal: dict[str, Any] | None = None,
    recruit_visit_modal: dict[str, Any] | None = None,
    bracket_reveal_modal: dict[str, Any] | None = None,
    bracket_update_modal: dict[str, Any] | None = None,
    signed_class: dict[str, Any] | None = None,
    first_archetype: dict[str, Any] | None = None,
    archetype_evolution_pending: str | None = None,
    user_in_revealed_bracket: bool = False,
    archetype_href: str | None = ARCHETYPES_HREF,
) -> list[dict[str, Any]]:
    """Eligible moments from existing CC flags, ordered by priority."""
    rows: list[dict[str, Any]] = []
    champs = [m for m in (championship_moments or []) if m]
    if champs:
        rows.append(
            _item(
                kind="championship",
                tier=TIER_SEASON_PEAK,
                priority=10,
                payload_ref="pending_championship_moments",
                seen_key="pending_championship_moments",
                duration="long",
                title="Championship moment",
                line="A title moment is waiting.",
            )
        )
    if _eligible_payload(season_review):
        rows.append(
            _item(
                kind="season_review",
                tier=TIER_SEASON_PEAK,
                priority=15,
                payload_ref="season_review",
                seen_key="season_review_seen_season",
                duration="long",
                title="Season review",
                line="Your season, start to finish.",
            )
        )
    if _eligible_payload(elimination):
        round_name = str((elimination or {}).get("round_name") or "").strip()
        rows.append(
            _item(
                kind="elimination",
                tier=TIER_MILESTONE,
                priority=20,
                payload_ref="elimination",
                seen_key="elimination_seen_season",
                duration="short",
                title="Season over",
                line=f"Your season ended in the {round_name}." if round_name
                else "Your season is over.",
                # Dignified, per decision 21: no gold, no sound, fade only.
                style=STYLE_QUIET,
            )
        )
    if _eligible_payload(bracket_reveal_modal):
        reveal_key = str(bracket_reveal_modal.get("reveal_key") or "bracket_reveal")
        if user_in_revealed_bracket:
            rows.append(
                _item(
                    kind="bracket_reveal",
                    tier=TIER_MILESTONE,
                    priority=30,
                    payload_ref="bracket_reveal_modal",
                    seen_key=reveal_key,
                    duration="long",
                    title="Bracket reveal",
                    line="The tournament bracket is set, and you are in it.",
                )
            )
        else:
            # Not the coach's own moment: it folds to the weekly card.
            rows.append(
                _item(
                    kind="bracket_reveal",
                    tier=TIER_WEEKLY,
                    priority=110,
                    payload_ref="bracket_reveal_modal",
                    seen_key=reveal_key,
                    title="Bracket reveal",
                    line="The tournament bracket is set.",
                    href=WEEKLY_HREF["bracket_reveal"],
                )
            )
    if _eligible_payload(signed_class):
        count = int((signed_class or {}).get("count") or 0)
        rows.append(
            _item(
                kind="signed_class",
                tier=TIER_MILESTONE,
                priority=40,
                payload_ref="signed_class",
                seen_key="recruiting_results_modal_seen_season",
                duration="long",
                title="Signing class",
                line=f"{_plural(count, 'recruit')} signed with your program."
                if count
                else "Your signing class is in.",
            )
        )
    if _eligible_payload(walk_on_welcome_modal):
        count = int(walk_on_welcome_modal.get("count") or 0)
        rows.append(
            _item(
                kind="walk_on_welcome",
                tier=TIER_MILESTONE,
                priority=50,
                payload_ref="walk_on_welcome_modal",
                seen_key="walk_on_welcome_modal_seen_season",
                duration="long",
                title="Walk-on welcome",
                line=f"{_plural(count, 'walk-on')} joined the roster."
                if count
                else "Walk-ons joined the roster.",
            )
        )
    if region_bye_modal_eligible:
        rows.append(
            _item(
                kind="region_bye",
                tier=TIER_MILESTONE,
                priority=60,
                payload_ref="region_bye_modal_eligible",
                seen_key="region_bye_modal_seen_season",
                duration="short",
                title="Region tournament bye",
                line="You have a bye in the region tournament.",
            )
        )
    if _eligible_payload(conference_rs_region_modal):
        rows.append(
            _item(
                kind="conference_rs_region",
                tier=TIER_MILESTONE,
                priority=65,
                payload_ref="conference_rs_region_modal",
                seen_key="conference_rs_region_modal_seen_season",
                duration="short",
                title="Region tournament qualified",
                line="Regular-season conference title still qualifies you for region.",
            )
        )
    if _eligible_payload(first_archetype):
        rows.append(
            _item(
                kind="first_archetype",
                tier=TIER_MILESTONE,
                priority=70,
                payload_ref="first_archetype",
                seen_key="archetype_reveal_seen",
                duration="short",
                title="Coaching archetype",
                line="Your coaching archetype is established.",
            )
        )
    if _eligible_payload(bracket_update_modal):
        rows.append(
            _item(
                kind="bracket_update",
                tier=TIER_WEEKLY,
                priority=80,
                payload_ref="bracket_update_modal",
                seen_key=str(bracket_update_modal.get("update_key") or "bracket_update"),
                title="Tournament update",
                line="The tournament bracket moved this week.",
                href=WEEKLY_HREF["bracket_update"],
            )
        )
    if _eligible_payload(recruit_visit_modal):
        recruit = recruit_visit_modal.get("recruit") or {}
        name = str(recruit.get("name") or "A recruit")
        rows.append(
            _item(
                kind="recruit_visit",
                tier=TIER_WEEKLY,
                priority=90,
                payload_ref="recruit_visit_modal",
                seen_key="recruit_visit_modal_seen_week",
                title="Recruit visit",
                line=f"{name} is visiting this week.",
                href=WEEKLY_HREF["recruit_visit"],
            )
        )
    pending = str(archetype_evolution_pending or "").strip()
    if pending:
        rows.append(
            _item(
                kind="archetype_evolution",
                tier=TIER_WEEKLY,
                priority=100,
                payload_ref="archetype_evolution_pending",
                seen_key="archetype_evolution_pending",
                title="Coaching archetype",
                line="Your coaching archetype evolved.",
                # Omitted on desktop, where the coaching-archetypes page is not served.
                href=archetype_href or None,
            )
        )
    rows.sort(key=lambda row: int(row["priority"]))
    return rows


def cap_this_visit(popup_moments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The pop-ups this visit: a season peak alone, else one, or two when the first is short."""
    if not popup_moments:
        return []
    peaks = [row for row in popup_moments if row.get("tier") == TIER_SEASON_PEAK]
    if peaks:
        # A season peak takes the whole visit. A title and its review are the one
        # pair that shows together: the title first, the review as "2 of 2".
        return peaks[:2]
    first = popup_moments[0]
    chosen = [first]
    if len(popup_moments) > 1 and first.get("duration") == "short":
        second = popup_moments[1]
        if second.get("tier") in POPUP_TIERS:
            chosen.append(second)
    return chosen


def also_row(weekly_moments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The one folded weekly item the Office card offers, highest priority first."""
    for row in weekly_moments:
        also: dict[str, Any] = {
            "kind": row["kind"],
            "title": row["title"],
            "line": row["line"],
            "href": row.get("href"),
        }
        return also
    return None


def build_moment_queue(**kwargs: Any) -> dict[str, Any]:
    moments = collect_moments(**kwargs)
    weekly = [row for row in moments if row["tier"] == TIER_WEEKLY]
    popups = [row for row in moments if row["tier"] in POPUP_TIERS]
    return {
        "moments": moments,
        "moments_for_this_visit": cap_this_visit(popups),
        "weekly_card_items": weekly,
        "also": also_row(weekly),
    }
