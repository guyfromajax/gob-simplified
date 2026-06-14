"""Canonical player class year labels for API + UI display."""

from __future__ import annotations

from typing import Any

_YEAR_ALIASES: dict[str, str] = {
    "jh": "JH",
    "freshman": "Freshman",
    "fr": "Freshman",
    "sophomore": "Sophomore",
    "so": "Sophomore",
    "junior": "Junior",
    "jr": "Junior",
    "senior": "Senior",
    "sr": "Senior",
    "graduate": "Graduate",
    "grad": "Graduate",
}

_YEAR_ABBREV: dict[str, str] = {
    "JH": "JH",
    "Freshman": "FR",
    "Sophomore": "SO",
    "Junior": "JR",
    "Senior": "SR",
    "Graduate": "GR",
}


def normalize_player_year(year: Any) -> str | None:
    """Return canonical class year (e.g. ``Senior``) or ``None`` when empty."""
    if year is None:
        return None
    raw = str(year).strip()
    if not raw or raw == "--":
        return None
    canonical = _YEAR_ALIASES.get(raw.lower())
    if canonical:
        return canonical
    if raw.isalpha():
        return raw[0].upper() + raw[1:].lower()
    return raw


def format_player_year_abbrev(year: Any) -> str:
    """User-facing class year abbreviation (JH/FR/SO/JR/SR/GR); ``--`` when unknown/empty."""
    normalized = normalize_player_year(year)
    if not normalized:
        return "--"
    return _YEAR_ABBREV.get(normalized, normalized)


def format_player_year_display(year: Any) -> str:
    """Alias for :func:`format_player_year_abbrev` — UI always shows abbreviations."""
    return format_player_year_abbrev(year)
