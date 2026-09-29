"""Server-side Office moment queue (Chapter 7).

Reads the eligibility flags and payloads already built for command-center data.
Does not write franchise fields, enqueue finalize work, or change the sim.

Tiers
    EVERYDAY     — no pop-up (none of today's modal flags)
    WEEKLY       — Office card only (`weekly_card_items`)
    MILESTONE    — pop-up candidate
    SEASON PEAK  — pop-up candidate

Priority (lower number first). Documented in UX_System §10.
    10  championship          SEASON PEAK  long
    20  bracket_reveal        MILESTONE    long
    30  walk_on_welcome       MILESTONE    long
    40  conference_rs_region  MILESTONE    short
    50  region_bye            MILESTONE    short
    60  archetype_evolution   MILESTONE    short
    70  bracket_update        WEEKLY
    80  recruit_visit         WEEKLY

Cap
    `moments_for_this_visit` is the first pop-up-tier item.
    A second item is included only when the first is `duration=short` and the
    second is MILESTONE or SEASON PEAK. Remaining pop-up-tier items stay in
    `moments` (still eligible next visit — seen keys are unchanged). WEEKLY
    items go to `weekly_card_items` and never take a pop-up slot.

`recruiting_results_modal` is not queued. Signing celebration is the week-35 hub.
"""

from __future__ import annotations

from typing import Any

TIER_EVERYDAY = "EVERYDAY"
TIER_WEEKLY = "WEEKLY"
TIER_MILESTONE = "MILESTONE"
TIER_SEASON_PEAK = "SEASON_PEAK"

POPUP_TIERS = frozenset({TIER_MILESTONE, TIER_SEASON_PEAK})


WEEKLY_HREF = {
    "bracket_update": "/franchise-command-center.html?tab=tournament-view",
    "recruit_visit": "/recruiting.html",
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
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": kind,
        "kind": kind,
        "tier": tier,
        "priority": priority,
        "payload_ref": payload_ref,
        "seen_key": seen_key,
        "title": title,
        "line": line,
    }
    if duration:
        row["duration"] = duration
    if href:
        row["href"] = href
    return row


def _eligible_payload(payload: Any) -> bool:
    return bool(isinstance(payload, dict) and payload.get("eligible"))


def collect_moments(
    *,
    championship_moments: list[Any] | None = None,
    conference_rs_region_modal: dict[str, Any] | None = None,
    region_bye_modal_eligible: bool = False,
    walk_on_welcome_modal: dict[str, Any] | None = None,
    recruit_visit_modal: dict[str, Any] | None = None,
    bracket_reveal_modal: dict[str, Any] | None = None,
    bracket_update_modal: dict[str, Any] | None = None,
    archetype_evolution_pending: str | None = None,
) -> list[dict[str, Any]]:
    """Eligible moments from existing CC flags. Recruiting-results is omitted."""
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
    if _eligible_payload(bracket_reveal_modal):
        rows.append(
            _item(
                kind="bracket_reveal",
                tier=TIER_MILESTONE,
                priority=20,
                payload_ref="bracket_reveal_modal",
                seen_key=str(bracket_reveal_modal.get("reveal_key") or "bracket_reveal"),
                duration="long",
                title="Bracket reveal",
                line="The tournament bracket is set.",
            )
        )
    if _eligible_payload(walk_on_welcome_modal):
        count = int(walk_on_welcome_modal.get("count") or 0)
        rows.append(
            _item(
                kind="walk_on_welcome",
                tier=TIER_MILESTONE,
                priority=30,
                payload_ref="walk_on_welcome_modal",
                seen_key="walk_on_welcome_modal_seen_season",
                duration="long",
                title="Walk-on welcome",
                line=f"{count} walk-on{'s' if count != 1 else ''} joined the roster."
                if count
                else "Walk-ons joined the roster.",
            )
        )
    if _eligible_payload(conference_rs_region_modal):
        rows.append(
            _item(
                kind="conference_rs_region",
                tier=TIER_MILESTONE,
                priority=40,
                payload_ref="conference_rs_region_modal",
                seen_key="conference_rs_region_modal_seen_season",
                duration="short",
                title="Region tournament qualified",
                line="Regular-season conference title still qualifies you for region.",
            )
        )
    if region_bye_modal_eligible:
        rows.append(
            _item(
                kind="region_bye",
                tier=TIER_MILESTONE,
                priority=50,
                payload_ref="region_bye_modal_eligible",
                seen_key="region_bye_modal_seen_season",
                duration="short",
                title="Region tournament bye",
                line="You have a bye in the region tournament.",
            )
        )
    pending = str(archetype_evolution_pending or "").strip()
    if pending:
        rows.append(
            _item(
                kind="archetype_evolution",
                tier=TIER_MILESTONE,
                priority=60,
                payload_ref="archetype_evolution_pending",
                seen_key="archetype_evolution_pending",
                duration="short",
                title="Coaching archetype",
                line="Your coaching archetype evolved.",
            )
        )
    if _eligible_payload(bracket_update_modal):
        rows.append(
            _item(
                kind="bracket_update",
                tier=TIER_WEEKLY,
                priority=70,
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
                priority=80,
                payload_ref="recruit_visit_modal",
                seen_key="recruit_visit_modal_seen_week",
                title="Recruit visit",
                line=f"{name} is visiting this week.",
                href=WEEKLY_HREF["recruit_visit"],
            )
        )
    rows.sort(key=lambda row: int(row["priority"]))
    return rows


def cap_this_visit(popup_moments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """At most one pop-up; two only when the first is short and the second is a pop-up tier."""
    if not popup_moments:
        return []
    first = popup_moments[0]
    chosen = [first]
    if len(popup_moments) > 1 and first.get("duration") == "short":
        second = popup_moments[1]
        if second.get("tier") in POPUP_TIERS:
            chosen.append(second)
    return chosen


def build_moment_queue(
    *,
    championship_moments: list[Any] | None = None,
    conference_rs_region_modal: dict[str, Any] | None = None,
    region_bye_modal_eligible: bool = False,
    walk_on_welcome_modal: dict[str, Any] | None = None,
    recruit_visit_modal: dict[str, Any] | None = None,
    bracket_reveal_modal: dict[str, Any] | None = None,
    bracket_update_modal: dict[str, Any] | None = None,
    archetype_evolution_pending: str | None = None,
) -> dict[str, Any]:
    moments = collect_moments(
        championship_moments=championship_moments,
        conference_rs_region_modal=conference_rs_region_modal,
        region_bye_modal_eligible=region_bye_modal_eligible,
        walk_on_welcome_modal=walk_on_welcome_modal,
        recruit_visit_modal=recruit_visit_modal,
        bracket_reveal_modal=bracket_reveal_modal,
        bracket_update_modal=bracket_update_modal,
        archetype_evolution_pending=archetype_evolution_pending,
    )
    weekly = [row for row in moments if row["tier"] == TIER_WEEKLY]
    popups = [row for row in moments if row["tier"] in POPUP_TIERS]
    this_visit = cap_this_visit(popups)
    return {
        "moments": moments,
        "moments_for_this_visit": this_visit,
        "weekly_card_items": weekly,
    }
