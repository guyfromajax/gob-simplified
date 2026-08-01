"""
Guardrail: for the 128 core teams, asset folder, stored team_id, and
FE/BE-derived path slug must agree — except Couer d'Alene.

See team-builder-identity-inventory.md (Known anomaly — Couer d'Alene).
Normalizing any one of the three forms in isolation will fail this test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from BackEnd.utils.team_slug import slug_from_display_name

ROOT = Path(__file__).resolve().parents[1]
TEAMS_TSV = ROOT / "teams" / "128_teams.txt"
ASSETS_DIR = ROOT / "FrontEnd" / "static" / "images" / "teams"

# Documented single exception — do not expand without updating the inventory.
COUER_DISPLAY = "Couer d'Alene"
COUER_STORED_TEAM_ID = "couer_d_alene"
COUER_ASSET_AND_DERIVED = "couer_dalene"


def _load_core_teams() -> list[tuple[str, str]]:
    """Return [(display_name, stored_team_id), ...] — first 128 rows only."""
    text = TEAMS_TSV.read_text(encoding="utf-8")
    rows: list[tuple[str, str]] = []
    for line in text.splitlines()[1:]:
        if not line.strip() or line.startswith("prestige"):
            break
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name = parts[1].strip()
        team_id = parts[3].strip()
        if name and team_id:
            rows.append((name, team_id))
    return rows


@pytest.fixture(scope="module")
def core_teams() -> list[tuple[str, str]]:
    teams = _load_core_teams()
    assert len(teams) == 128, f"expected 128 core teams, got {len(teams)}"
    return teams


def test_couer_dalene_is_documented_three_way_mismatch(core_teams):
    """Couer alone: stored team_id ≠ asset folder / derived slug."""
    matches = [(n, tid) for n, tid in core_teams if n == COUER_DISPLAY]
    assert len(matches) == 1, f"expected one {COUER_DISPLAY!r} row"
    _name, stored = matches[0]
    assert stored == COUER_STORED_TEAM_ID
    derived = slug_from_display_name(COUER_DISPLAY)
    assert derived == COUER_ASSET_AND_DERIVED
    assert stored.lower() != derived
    assert (ASSETS_DIR / COUER_ASSET_AND_DERIVED).is_dir(), (
        f"asset folder missing: {ASSETS_DIR / COUER_ASSET_AND_DERIVED}"
    )
    assert not (ASSETS_DIR / COUER_STORED_TEAM_ID).is_dir(), (
        f"unexpected asset folder for stored id: {ASSETS_DIR / COUER_STORED_TEAM_ID} "
        "(do not rename stored team_id to match assets without a migration plan)"
    )


def test_all_other_core_teams_asset_stored_and_derived_agree(core_teams):
    """
    For every core team except Couer d'Alene:
    asset directory name == stored team_id (lower) == FE/BE-derived slug.
    """
    failures: list[str] = []
    for name, stored_raw in core_teams:
        if name == COUER_DISPLAY:
            continue
        stored = stored_raw.lower()
        derived = slug_from_display_name(name)
        asset_dir = ASSETS_DIR / derived
        if stored != derived:
            failures.append(
                f"{name!r}: stored={stored!r} != derived={derived!r}"
            )
        if not asset_dir.is_dir():
            failures.append(
                f"{name!r}: asset dir missing for derived slug {derived!r} "
                f"({asset_dir})"
            )
        elif asset_dir.name != stored:
            # Directory exists under derived; name must also equal stored.
            failures.append(
                f"{name!r}: asset folder {asset_dir.name!r} != stored {stored!r}"
            )

    assert not failures, (
        "Core team slug forms must agree (asset dir, stored team_id, "
        "FE/BE-derived). Couer d'Alene is the only documented exception.\n"
        + "\n".join(failures)
    )
