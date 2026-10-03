"""Playbooks is a real module — no embed-bridge path."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEW = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "views" / "playbooksView.js").read_text()
JS = (ROOT / "FrontEnd" / "static" / "playbooks.js").read_text()
HTML = (ROOT / "FrontEnd" / "static" / "playbooks.html").read_text()
CSS = (ROOT / "FrontEnd" / "static" / "playbooks.css").read_text()


def test_view_does_not_embed_the_old_page():
    assert "from './viewLoader.js'" in VIEW
    assert "prepEmbed" not in VIEW
    assert "embed('/playbooks.html" not in VIEW
    assert "DOMParser" not in VIEW
    assert "loadIsolated" not in VIEW
    assert "init as initPlaybooks" in VIEW


def test_page_script_exports_init():
    assert "function init(" in JS
    assert "function teardown(" in JS
    assert "function shellHtml(" in JS
    assert "export { init, teardown, revalidate, shellHtml };" in JS
    assert "document.addEventListener('DOMContentLoaded'" not in JS
    assert "window.addEventListener(\"DOMContentLoaded\"" not in JS


def test_html_keeps_tutorial_and_redirects_browse():
    assert "tab', 'playbooks-view'" in HTML or 'tab", "playbooks-view"' in HTML
    assert "mode') === 'tutorial'" in HTML or 'mode") === "tutorial"' in HTML
    assert "location.replace('/franchise-command-center.html?" in HTML
    assert "embed') === '1'" not in HTML
    assert "import { init } from '/playbooks.js'" in HTML


def test_standalone_page_class_is_not_toggled_from_the_view():
    assert "document.body.classList.add('playbooks-page')" not in VIEW
    assert "root.classList.add('playbooks-page')" not in JS


def test_css_does_not_reset_the_app():
    assert "\n* {" not in CSS
    assert "\nbody {\n" not in CSS
    assert "\n:root {" not in CSS
