"""Game Plan is a real module — no embed-bridge path."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEW = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "views" / "gamePlanView.js").read_text()
JS = (ROOT / "FrontEnd" / "static" / "game-plan.js").read_text()
HTML = (ROOT / "FrontEnd" / "static" / "game-plan.html").read_text()
CSS = (ROOT / "FrontEnd" / "static" / "game-plan.css").read_text()


def test_view_does_not_embed_the_old_page():
    assert "embed('/game-plan.html" not in VIEW
    assert "DOMParser" not in VIEW
    assert "loadIsolated" not in VIEW
    assert "init as initPlan" in VIEW


def test_page_script_exports_init():
    assert "function init(" in JS
    assert "function teardown(" in JS
    assert "function shellHtml(" in JS
    assert "export { init, teardown, revalidate, shellHtml };" in JS
    assert "document.addEventListener('DOMContentLoaded', initGamePlan)" not in JS


def test_html_keeps_focus_paths_and_redirects_browse():
    assert "tab', 'game-plan-view'" in HTML or 'tab", "game-plan-view"' in HTML
    assert "resume_from_timeout" in HTML
    assert "mode') === 'tutorial'" in HTML or 'mode") === "tutorial"' in HTML
    assert "location.replace('/franchise-command-center.html?" in HTML
    assert "import { init } from '/game-plan.js'" in HTML


def test_standalone_page_class_is_not_toggled_from_the_view():
    assert "document.body.classList.add('game-plan-page')" not in VIEW
    assert "root.classList.add('game-plan-page')" not in JS


def test_css_does_not_reset_the_app():
    assert CSS.lstrip().startswith("/*") or "body.game-plan-page" in CSS.split("{", 1)[0]
    assert "\n* {" not in CSS
    assert "\nbody {\n" not in CSS
