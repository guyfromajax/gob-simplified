"""Player Training is a real module — weekly focus on training.html, player-dev in Prep."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEW = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "views" / "trainingView.js").read_text()
JS = (ROOT / "FrontEnd" / "static" / "training.js").read_text()
HTML = (ROOT / "FrontEnd" / "static" / "training.html").read_text()
CSS = (ROOT / "FrontEnd" / "static" / "training.css").read_text()
ADVANCE = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "gobAdvance.js").read_text()
SHELL = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "gobShell.js").read_text()


def test_view_does_not_embed_the_old_page():
    assert "from './viewLoader.js'" in VIEW
    assert "prepEmbed" not in VIEW
    assert "embed('/training.html" not in VIEW
    assert "DOMParser" not in VIEW
    assert "loadIsolated" not in VIEW
    assert "init as initTraining" in VIEW
    assert "sections: 'player-dev'" in VIEW


def test_page_script_exports_init():
    assert "function init(" in JS
    assert "function teardown(" in JS
    assert "function shellHtml(" in JS
    assert "export { init, teardown, revalidate, shellHtml };" in JS
    assert "document.addEventListener('DOMContentLoaded'" not in JS
    assert 'window.addEventListener("DOMContentLoaded"' not in JS
    assert "sections: 'weekly'" in JS or "options.sections" in JS


def test_html_is_weekly_focus_host():
    assert "location.replace('/franchise-command-center.html?" not in HTML
    assert "sections: 'weekly'" in HTML
    assert "import { init } from '/training.js'" in HTML
    assert "gobLeaveConfirm.js" in HTML
    assert "embed') === '1'" not in HTML


def test_advance_opens_training_html_focus():
    assert "'/training.html?'" in ADVANCE or '"/training.html?"' in ADVANCE
    assert "tab', 'training-view'" not in ADVANCE
    assert "'/training.html': { kind: 'focus' }" in SHELL


def test_view_toggles_the_page_class():
    assert "document.body.classList.toggle('training-page'" in VIEW
    assert "root.classList.add('training-page')" not in JS


def test_css_does_not_reset_the_app():
    assert "\n* {" not in CSS
    assert "\nbody {\n" not in CSS
    assert "\n:root {" not in CSS
