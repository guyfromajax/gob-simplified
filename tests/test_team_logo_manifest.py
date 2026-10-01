"""The known-logo-art lists in common.js match the files in images/teams/.

getTeamAssetPath('logo_square') serves the square when a team has one, else its
logo_primary, else the generic square, so League tables never request a
missing file. These lists are built once; this test fails when art is added or
removed without updating them.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "FrontEnd" / "static"
COMMON_JS = STATIC / "common.js"
TEAMS = STATIC / "images" / "teams"


def _js_set(name: str) -> set[str]:
    text = COMMON_JS.read_text(encoding="utf-8")
    start = text.index(f"var {name} = {{")
    body = text[start : text.index("};", start)]
    return set(re.findall(r"'([A-Za-z_]+)':\s*1", body))


def _folder(slug: str) -> Path:
    return TEAMS / ("IDA" if slug == "ida" else slug)


def test_logo_lists_match_disk():
    core = _js_set("CORE_TEAM_ASSET_SLUGS")
    square = _js_set("TEAM_LOGO_SQUARE_SLUGS")
    primary = _js_set("TEAM_LOGO_PRIMARY_SLUGS")
    assert square and primary
    assert not (square & primary), "a slug is listed as both square and primary-only"
    assert square <= core and primary <= core

    for slug in sorted(core):
        files = {p.name for p in _folder(slug).glob("*.png")} if _folder(slug).is_dir() else set()
        has_square = f"{slug}_logo_square.png" in files
        has_primary = f"{'IDA' if slug == 'ida' else slug}_logo_primary.png" in files or f"{slug}_logo_primary.png" in files
        assert (slug in square) == has_square, f"{slug}: logo_square on disk={has_square}"
        if not has_square:
            assert (slug in primary) == has_primary, f"{slug}: logo_primary on disk={has_primary}"


def test_every_listed_logo_file_exists():
    for slug in _js_set("TEAM_LOGO_SQUARE_SLUGS"):
        assert (_folder(slug) / f"{slug}_logo_square.png").is_file(), slug
    for slug in _js_set("TEAM_LOGO_PRIMARY_SLUGS"):
        assert (_folder(slug) / f"{slug}_logo_primary.png").is_file(), slug
