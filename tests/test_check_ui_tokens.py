"""Fixture checks for scripts/check_ui_tokens.py. The real tree is not scanned."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import scripts.check_ui_tokens as tokens

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_ui_tokens.py"

TOKENS_CSS = """
.gob {
  --green:#34EC27;
  --orange:#F79420;
  --navy:#27408E;
  --navy-hi:#4A6ED2;
  --blue:#4A90D9;
  --red:#ff6d6d;
  --yellow:#FFD700;
  --white:#ffffff;
  --black:#000000;
  --text-60:rgba(255,255,255,.60);
  --white-10:rgba(255,255,255,.1);
  --fs-13:13px;
  --fw-bold:700;
  --tracking-4:.04em;
  --font-body:'Inter',sans-serif;
  --font-display:'Bebas Neue Pro',sans-serif;
  --delta-up:var(--green);
  --tier-green:var(--green);
}
"""

NEW_CSS = """
.advance { background: var(--green); }
.play-now { color: #34EC27; }
.wl.win { color: #34EC27; }
.chip.up { color: var(--delta-up); }
.t-green { color: var(--tier-green); }
.card { color: var(--green); background: #2AD01E; }
.save { background: var(--orange); }
.note { color: #F79420; }
.prize { border-color: var(--reward-gold); }
.navy-row { background: #27408E; }
.mist { background: rgba(255,255,255,.10); }
.raw {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .04em;
  font-family: Inter, sans-serif;
}
.tok {
  font-size: var(--fs-13);
  font-weight: var(--fw-bold);
  letter-spacing: var(--tracking-4);
  font-family: var(--font-body);
}
.alias { --green: #34ec27; }
"""

LEGACY_CSS = """
.banner { color: rgb(255, 109, 109); background: green; }
.old-type { font-size: 15px; letter-spacing: 0.08em; }
"""

SHELL_JS = """
  var PAGES = {
    '/shell-page.html': { kind: 'browse' }
  };
"""

SHELL_HTML = """<!DOCTYPE html>
<html>
<head><style>
.hero { color: hsl(110, 90%, 54%); }
</style></head>
<body><div class="card" style="color: var(--green); font-size: 12px"></div></body>
</html>
"""

CLASS_HTML = """<!DOCTYPE html>
<html class="gob gob-shell">
<style>.panel { background: navy; }</style>
</html>
"""

OLD_HTML = """<!DOCTYPE html>
<html>
<style>.x { color: white; }</style>
<div style="background: orange"></div>
</html>
"""

NEW_JS = """
el.innerHTML = '<div class="card" style="background:#34ec27"></div>';
node.style.fontWeight = '700';
"""

LEGACY_JS = """
node.style.color = '#ff6d6d';
label.style.fontFamily = 'Inter, sans-serif';
"""

CLEAN_CSS = """
.advance { background: var(--green); }
.save { color: var(--orange); }
.ok { font-size: var(--fs-13); font-weight: var(--fw-bold); letter-spacing: var(--tracking-4); font-family: var(--font-display); }
"""


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(root: Path) -> Path:
    _write(root, "css/gob-tokens.css", TOKENS_CSS)
    _write(root, "css/gob-components.css", NEW_CSS)
    _write(root, "css/old-page.css", LEGACY_CSS)
    _write(root, "js/shared/gobShell.js", SHELL_JS)
    _write(root, "shell-page.html", SHELL_HTML)
    _write(root, "classed.html", CLASS_HTML)
    _write(root, "old.html", OLD_HTML)
    _write(root, "js/shared/views/card.js", NEW_JS)
    _write(root, "legacy.js", LEGACY_JS)
    return root


def _audit(root: Path) -> tokens.Audit:
    return tokens.audit_tree(root, root / "css" / "gob-tokens.css")


def _by(hits, **want):
    found = []
    for hit in hits:
        if all(getattr(hit, key) == value for key, value in want.items()):
            found.append(hit)
    return found


def test_literal_detection_and_near_duplicate_groups(tmp_path):
    audit = _audit(_fixture(tmp_path))
    colours = {(hit.path, hit.text, hit.kind) for hit in audit.colours}

    assert ("css/gob-components.css", "#34EC27", "green") in colours
    assert ("css/gob-components.css", "#2AD01E", "green") in colours
    assert ("css/gob-components.css", "#27408E", "navy") in colours
    assert ("css/gob-components.css", "#F79420", "orange") in colours
    assert any(hit.kind == "white/grey" and "255" in hit.text for hit in audit.colours)
    assert ("css/old-page.css", "rgb(255, 109, 109)", "red") in colours
    assert ("css/old-page.css", "green", "green") in colours
    assert any(hit.kind == "green" and hit.text.lower().startswith("hsl(") for hit in audit.colours)
    assert ("old.html", "white", "white/grey") in colours
    assert ("old.html", "orange", "orange") in colours
    assert ("classed.html", "navy", "navy") in colours
    # The token file is the source, not a finding.
    assert not any(hit.path.endswith("gob-tokens.css") for hit in audit.colours)

    exact = _by(audit.colours, path="css/gob-components.css", text="#34EC27")
    nearby = _by(audit.colours, path="css/gob-components.css", text="#2AD01E")
    assert exact and nearby
    assert exact[0].kind == nearby[0].kind == "green"
    assert "from --green" in exact[0].detail
    assert "from --green" in nearby[0].detail
    exact_de = float(exact[0].detail.split()[1])
    nearby_de = float(nearby[0].detail.split()[1])
    assert exact_de < 1
    assert nearby_de > exact_de

    mist = _by(audit.colours, path="css/gob-components.css", kind="white/grey")
    assert mist
    assert any("--white" in hit.detail for hit in mist)


def test_colour_law_hits_and_allowed_uses(tmp_path):
    audit = _audit(_fixture(tmp_path))
    laws = {(hit.surface, hit.kind, hit.path, hit.text) for hit in audit.laws}

    assert ("new", "green", "css/gob-components.css", "var(--green)") in laws
    assert ("new", "green", "css/gob-components.css", "#2AD01E") in laws
    assert ("new", "orange", "css/gob-components.css", "#F79420") in laws
    assert ("new", "reward-gold", "css/gob-components.css", "--reward-gold") in laws
    assert ("new", "green", "shell-page.html", "var(--green)") in laws
    assert ("new", "green", "js/shared/views/card.js", "#34ec27") in laws

    # Advance, W badge, delta-up / tier-green, and save are not hits.
    blocked_text = {hit.text for hit in audit.laws}
    assert "var(--delta-up)" not in blocked_text
    assert "var(--tier-green)" not in blocked_text
    assert "var(--orange)" not in blocked_text
    advance_greens = [
        hit for hit in audit.laws
        if hit.path == "css/gob-components.css" and hit.text == "#34EC27"
    ]
    assert advance_greens == []
    # Redefining --green is a near-duplicate literal, not a law hit.
    # The same hex in js/shared/views/card.js is a use, and is a hit.
    alias_laws = [
        hit for hit in audit.laws
        if hit.path == "css/gob-components.css" and hit.text == "#34ec27"
    ]
    assert alias_laws == []
    alias = _by(audit.colours, path="css/gob-components.css", text="#34ec27")
    assert alias and alias[0].kind == "green"


def test_type_literals_skip_token_references(tmp_path):
    audit = _audit(_fixture(tmp_path))
    raw = {(hit.kind, hit.path) for hit in audit.types if hit.path == "css/gob-components.css"}
    assert ("font-size", "css/gob-components.css") in raw
    assert ("font-weight", "css/gob-components.css") in raw
    assert ("letter-spacing", "css/gob-components.css") in raw
    assert ("font-family", "css/gob-components.css") in raw
    tok_values = [hit.text for hit in audit.types if "var(--fs-13)" in hit.text or "var(--fw-bold)" in hit.text]
    assert tok_values == []
    assert any(hit.kind == "font-size" and hit.path == "shell-page.html" for hit in audit.types)
    assert any(hit.kind == "font-weight" and hit.path == "js/shared/views/card.js" for hit in audit.types)
    assert any(hit.kind == "font-family" and hit.path == "legacy.js" for hit in audit.types)
    assert any(hit.kind == "font-size" and hit.path == "css/old-page.css" for hit in audit.types)


def test_legacy_and_new_are_split(tmp_path):
    audit = _audit(_fixture(tmp_path))
    surfaces = {(hit.path, hit.surface) for hit in (*audit.colours, *audit.types, *audit.laws)}
    assert ("css/gob-components.css", "new") in surfaces
    assert ("shell-page.html", "new") in surfaces
    assert ("classed.html", "new") in surfaces
    assert ("js/shared/views/card.js", "new") in surfaces
    assert ("css/old-page.css", "legacy") in surfaces
    assert ("old.html", "legacy") in surfaces
    assert ("legacy.js", "legacy") in surfaces
    law = audit.law_counts()
    assert law["new"]["green"] >= 1
    assert law["legacy"]["orange"] >= 1  # old.html style="background: orange"
    assert sum(law["new"].values()) != sum(law["legacy"].values()) or law["new"]["reward-gold"]


def test_strict_exit_code(tmp_path):
    root = _fixture(tmp_path / "dirty")
    report = tmp_path / "dirty.md"
    base = [sys.executable, str(SCRIPT), "--root", str(root), "--report", str(report)]
    plain = subprocess.run(base, check=False, capture_output=True, text=True)
    assert plain.returncode == 0, plain.stderr
    assert "Colour-law hits" in plain.stdout
    assert report.is_file()
    assert "colour-law new" in report.read_text(encoding="utf-8")

    strict = subprocess.run([*base, "--strict"], check=False, capture_output=True, text=True)
    assert strict.returncode == 1

    clean = tmp_path / "clean"
    _write(clean, "css/gob-tokens.css", TOKENS_CSS)
    _write(clean, "css/gob-components.css", CLEAN_CSS)
    clean_report = tmp_path / "clean.md"
    clean_run = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(clean), "--report", str(clean_report), "--strict"],
        check=False, capture_output=True, text=True,
    )
    assert clean_run.returncode == 0, clean_run.stdout + clean_run.stderr


def test_strict_ignores_legacy_law_hits(tmp_path):
    root = tmp_path / "legacy_only"
    _write(root, "css/gob-tokens.css", TOKENS_CSS)
    _write(root, "old.html", OLD_HTML)
    report = tmp_path / "legacy.md"
    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--report", str(report), "--strict"],
        check=False, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    text = report.read_text(encoding="utf-8")
    assert "colour-law new" in text
    assert "| colour-law legacy |" in text or "colour-law legacy" in text


def test_allow_list_selectors_and_comments(tmp_path):
    root = tmp_path / "allowed"
    _write(root, "css/gob-tokens.css", TOKENS_CSS)
    _write(
        root,
        "css/gob-components.css",
        """
.col-card.is-pos { color: var(--green); }
.meter.chem.is-green { color: var(--green); }
.att-col .att-bar { color: var(--green); background: var(--orange); }
.gob-btn--gate { background: #34EC27; }
.gob-btn--action { background: #F79420; }
.todo.gated { color: var(--orange); }
.tsr-up { color: #34ec27; } /* colour-law: positive-data */
.toggle-btn.active { background: #f79420; } /* colour-law: committed */
""",
    )
    _write(root, "css/gob-tutorial.css", ".x { color: var(--orange); background: #34EC27; }")
    audit = _audit(root)
    assert audit.law_counts()["new"]["green"] == 0
    assert audit.law_counts()["new"]["orange"] == 0
    tutorial_new = [
        hit for hit in audit.laws
        if hit.path.endswith("gob-tutorial.css") and hit.surface == "new"
    ]
    assert tutorial_new == []
