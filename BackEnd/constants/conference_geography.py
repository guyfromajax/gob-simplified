"""Conference → state-level geography map (Team Builder v2 §5.1).

Sits alongside region A–H. Does not replace or overload region.
Texas appears in 11 and 12; California in 15 and 16 — intentional.
"""
from __future__ import annotations

# Verbatim from team-builder-v2-plan.md §5.1
CONFERENCE_GEOGRAPHY: dict[int, tuple[str, ...]] = {
    1: ("Pennsylvania", "New Jersey", "Delaware"),
    2: ("West Virginia", "North Carolina", "Virginia", "Maryland"),
    3: (
        "Massachusetts",
        "Rhode Island",
        "Vermont",
        "Maine",
        "New Hampshire",
        "Connecticut",
    ),
    4: ("New York", "East Canada", "Europe"),
    5: ("Michigan", "Ohio", "Indiana"),
    6: ("Illinois", "Minnesota", "Wisconsin"),
    7: ("Mississippi", "Tennessee", "Kentucky", "South Carolina", "Alabama"),
    8: ("Florida", "Georgia"),
    9: ("Iowa", "Kansas", "Missouri"),
    10: (
        "Nebraska",
        "South Dakota",
        "North Dakota",
        "Wyoming",
        "Montana",
        "Central Canada",
    ),
    11: ("Oklahoma", "Texas", "Arkansas"),
    12: ("Texas", "Louisiana"),
    13: ("Arizona", "New Mexico", "Nevada", "Colorado", "Utah"),
    14: ("Idaho", "Washington", "Oregon", "West Canada"),
    15: ("California",),
    16: ("California", "Hawaii", "Alaska", "Asia", "Australia"),
}

NON_US_GEOGRAPHIES = frozenset(
    {
        "East Canada",
        "Central Canada",
        "West Canada",
        "Europe",
        "Asia",
        "Australia",
    }
)


def geography_for_conference(conference: int | None) -> tuple[str, ...]:
    try:
        n = int(conference)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ()
    return CONFERENCE_GEOGRAPHY.get(n, ())


def distinct_geographies() -> list[str]:
    """Sorted unique geography labels from the §5.1 map (must be exactly 56)."""
    found: set[str] = set()
    for entries in CONFERENCE_GEOGRAPHY.values():
        found.update(entries)
    return sorted(found)


def conferences_for_geography(geography: str) -> list[int]:
    label = str(geography or "").strip()
    if not label:
        return []
    return sorted(
        conf
        for conf, entries in CONFERENCE_GEOGRAPHY.items()
        if label in entries
    )


__all__ = [
    "CONFERENCE_GEOGRAPHY",
    "NON_US_GEOGRAPHIES",
    "geography_for_conference",
    "distinct_geographies",
    "conferences_for_geography",
]
