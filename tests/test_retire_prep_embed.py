"""Chapter 8 cleanup: the Prep embed bridge is gone."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATIC = ROOT / "FrontEnd" / "static"
VIEWS = STATIC / "js" / "shared" / "views"
LOADER = (VIEWS / "viewLoader.js").read_text()
SCOUT = (VIEWS / "scoutingView.js").read_text()


def test_prep_embed_file_is_gone():
    assert not (VIEWS / "prepEmbed.js").exists()
    assert (VIEWS / "viewLoader.js").exists()


def test_view_loader_has_no_embed_or_url_search():
    assert "export function ensureCss" in LOADER
    assert "export function loadScript" in LOADER
    assert "export function ensureFranchiseMode" in LOADER
    assert "export function embed" not in LOADER
    assert "loadIsolated" not in LOADER
    assert "URLSearchParams" not in LOADER
    assert "location.search" not in LOADER
    assert "ctx.get('franchise_id')" in LOADER


def test_no_prep_embed_imports_under_static():
    hits = []
    for path in STATIC.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".js", ".html", ".css"}:
            continue
        text = path.read_text(errors="ignore")
        if "prepEmbed" in text:
            hits.append(str(path.relative_to(ROOT)))
        if "loadIsolated(" in text:
            hits.append(str(path.relative_to(ROOT)) + ":loadIsolated(")
        if "embed(" in text and path.name.endswith("View.js"):
            hits.append(str(path.relative_to(ROOT)) + ":embed(")
    assert hits == []


def test_scouting_reads_franchise_context():
    assert "function contextValue(key)" in SCOUT
    assert "fc.get(key)" in SCOUT
    assert "URLSearchParams" not in SCOUT
    assert "location.search" not in SCOUT
    assert "from './viewLoader.js'" in SCOUT
    assert "prepEmbed" not in SCOUT
