"""Training Report is a real module — no embed-bridge path."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEW = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "views" / "trainingReportView.js").read_text()
JS = (ROOT / "FrontEnd" / "static" / "training-report.js").read_text()
HTML = (ROOT / "FrontEnd" / "static" / "training-report.html").read_text()


def test_view_does_not_embed_the_old_page():
    assert "from './viewLoader.js'" in VIEW
    assert "prepEmbed" not in VIEW
    assert "embed('/training-report.html" not in VIEW
    assert "DOMParser" not in VIEW
    assert "loadIsolated" not in VIEW
    assert "init as initReport" in VIEW


def test_page_script_exports_init():
    assert "function init(" in JS
    assert "function teardown(" in JS
    assert "function shellHtml(" in JS
    assert "export { init, teardown, revalidate, shellHtml };" in JS


def test_html_is_the_focus_host():
    assert "import { init } from '/training-report.js'" in HTML
    assert "location.replace('/franchise-command-center.html?" not in HTML
    assert "URLSearchParams" not in HTML
    assert "embed') === '1'" not in HTML


def test_page_class_is_on_the_view_root_not_document_body():
    assert "root.classList.add('training-report-page')" in JS
    assert "document.body.classList.add('training-report-page')" not in VIEW
    assert "document.body.classList.toggle('training-report-page'" not in VIEW
