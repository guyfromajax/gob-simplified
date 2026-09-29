"""Training Report is a real module — no embed-bridge path."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEW = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "views" / "trainingReportView.js").read_text()
JS = (ROOT / "FrontEnd" / "static" / "training-report.js").read_text()
HTML = (ROOT / "FrontEnd" / "static" / "training-report.html").read_text()


def test_view_does_not_embed_the_old_page():
    assert "embed('/training-report.html" not in VIEW
    assert "DOMParser" not in VIEW
    assert "loadIsolated" not in VIEW
    assert "init as initReport" in VIEW


def test_page_script_exports_init():
    assert "function init(" in JS
    assert "function teardown(" in JS
    assert "function shellHtml(" in JS
    assert "export { init, teardown, revalidate, shellHtml };" in JS


def test_html_still_redirects_into_the_app():
    assert "tab', 'training-report-view'" in HTML or 'tab", "training-report-view"' in HTML
    assert "location.replace('/franchise-command-center.html?" in HTML
