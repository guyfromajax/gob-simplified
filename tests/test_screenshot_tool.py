import json
import os
import struct
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = ROOT / "scripts" / "capture_screenshot.mjs"
SESSION_SCRIPT = ROOT / "scripts" / "save_screenshot_session.mjs"
RECIPE_SCRIPT = ROOT / "scripts" / "screenshot_recipes.mjs"


def run_node_module(source: str, *, check: bool = True):
    return subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def png_dimensions(path: Path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


class ScreenshotFixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler contract
        body = b"""<!doctype html>
<html><head><style>
body { margin: 0; background: #07111f; color: white; font-family: sans-serif; }
#capture-target { width: 320px; height: 180px; background: #ef8b22; }
</style></head><body>
<main id="ready"><div id="capture-target">
<svg width="80" height="80" viewBox="0 0 80 80"><circle cx="40" cy="40" r="30" fill="#fff"/></svg>
<span>Native browser capture</span>
</div></main></body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


@pytest.fixture(scope="module")
def screenshot_fixture_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ScreenshotFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/fixture.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_parsing_defaults_conflicts_and_recipe_overrides():
    result = run_node_module(
        f"""
import {{ parseArguments }} from {json.dumps(CAPTURE_SCRIPT.as_uri())};
const defaults = parseArguments(['--url', 'http://localhost:8000/homepage.html']);
const recipe = parseArguments([
  '--url', 'http://localhost:8000/training.html', '--recipe', 'training',
  '--viewport', '1280x720', '--delay-ms', '0'
]);
let conflict = '';
try {{
  parseArguments(['--url', 'http://localhost:8000/mode-select.html', '--recipe', 'around-league', '--full-page']);
}} catch (error) {{ conflict = error.message; }}
console.log(JSON.stringify({{ defaults, recipe, conflict }}));
"""
    )
    data = json.loads(result.stdout)
    assert data["defaults"]["viewport"] == {"width": 1920, "height": 1080}
    assert data["defaults"]["safeName"] == "homepage"
    assert data["recipe"]["safeName"] == "training"
    assert data["recipe"]["viewport"] == {"width": 1280, "height": 720}
    assert data["recipe"]["delayMs"] == 0
    assert "cannot be combined" in data["conflict"]


def test_safe_names_collision_paths_and_non_http_rejection(tmp_path):
    output_dir = tmp_path / "shots"
    output_dir.mkdir()
    result = run_node_module(
        f"""
import {{ chooseOutputPath, parseArguments, sanitizeName }} from {json.dumps(CAPTURE_SCRIPT.as_uri())};
import fs from 'node:fs';
const first = chooseOutputPath({json.dumps(str(output_dir))}, 'mode-select', new Date('2026-08-12T13:00:00Z'));
fs.writeFileSync(first, 'occupied');
const second = chooseOutputPath({json.dumps(str(output_dir))}, 'mode-select', new Date('2026-08-12T13:00:00Z'));
let protocol = '';
try {{ parseArguments(['--url', 'file:///tmp/page.html']); }} catch (error) {{ protocol = error.message; }}
console.log(JSON.stringify({{ safe: sanitizeName('  Möde Select!  '), first, second, protocol }}));
"""
    )
    data = json.loads(result.stdout)
    assert data["safe"] == "mode-select"
    assert data["first"].endswith("mode-select-20260812-130000.png")
    assert data["second"].endswith("mode-select-20260812-130000-2.png")
    assert "http:// or https://" in data["protocol"]


def test_storage_state_validation_is_private_and_does_not_leak_contents(tmp_path):
    secret = "DO_NOT_PRINT_THIS_SYNTHETIC_TOKEN"
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"cookies": [], "origins": [], "secret": secret}))
    state.chmod(0o644)
    result = subprocess.run(
        [
            "node",
            str(CAPTURE_SCRIPT),
            "--url",
            "http://localhost:8000/homepage.html",
            "--state",
            str(state),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "0600" in result.stderr
    assert secret not in result.stdout + result.stderr

    state.chmod(0o600)
    parsed = run_node_module(
        f"""
import {{ parseArguments }} from {json.dumps(CAPTURE_SCRIPT.as_uri())};
const value = parseArguments(['--url', 'http://localhost:8000/homepage.html', '--state', {json.dumps(str(state))}]);
console.log(JSON.stringify({{ path: value.statePath }}));
"""
    )
    assert json.loads(parsed.stdout)["path"] == str(state)
    assert secret not in parsed.stdout + parsed.stderr


def test_session_helper_rejects_production_and_repo_state():
    result = run_node_module(
        f"""
import {{ parseSessionArguments }} from {json.dumps(SESSION_SCRIPT.as_uri())};
const messages = [];
for (const args of [
  ['--url', 'https://geekedoutbasketball.com/login.html'],
  ['--state', {json.dumps(str(ROOT / 'tmp' / 'state.json'))}]
]) {{
  try {{ parseSessionArguments(args); }} catch (error) {{ messages.push(error.message); }}
}}
console.log(JSON.stringify(messages));
"""
    )
    messages = json.loads(result.stdout)
    assert "production login is not allowed" in messages[0]
    assert "outside the repository" in messages[1]


def test_recipe_catalog_has_only_navigation_readiness_metadata():
    result = run_node_module(
        f"""
import {{ SCREENSHOT_RECIPES, recipeNames }} from {json.dumps(RECIPE_SCRIPT.as_uri())};
console.log(JSON.stringify({{
  names: recipeNames(),
  keys: [...new Set(Object.values(SCREENSHOT_RECIPES).flatMap(Object.keys))].sort()
}}));
"""
    )
    data = json.loads(result.stdout)
    assert data["names"] == [
        "around-league",
        "court",
        "fcc",
        "full-game-sim",
        "game-preview",
        "mode-select",
        "recruiting",
        "set-lineup",
        "training",
    ]
    assert set(data["keys"]) <= {
        "delayMs",
        "description",
        "name",
        "pathPattern",
        "selector",
        "viewport",
        "waitFor",
        "waitForHidden",
    }


def test_native_viewport_and_selector_screenshots(screenshot_fixture_url, tmp_path):
    viewport = subprocess.run(
        [
            "node",
            str(CAPTURE_SCRIPT),
            "--url",
            screenshot_fixture_url,
            "--name",
            "viewport",
            "--viewport",
            "640x480",
            "--wait-for",
            "#ready",
            "--delay-ms",
            "0",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    viewport_path = Path(viewport.stdout.strip())
    assert viewport_path.is_file()
    assert png_dimensions(viewport_path) == (640, 480)

    selector = subprocess.run(
        [
            "node",
            str(CAPTURE_SCRIPT),
            "--url",
            screenshot_fixture_url,
            "--name",
            "selector",
            "--viewport",
            "640x480",
            "--selector",
            "#capture-target",
            "--delay-ms",
            "0",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    selector_path = Path(selector.stdout.strip())
    assert selector_path.is_file()
    assert png_dimensions(selector_path) == (320, 180)


def test_missing_selector_has_specific_bounded_failure(screenshot_fixture_url, tmp_path):
    result = run_node_module(
        f"""
import {{ captureScreenshot, parseArguments }} from {json.dumps(CAPTURE_SCRIPT.as_uri())};
const options = parseArguments([
  '--url', {json.dumps(screenshot_fixture_url)}, '--selector', '#does-not-exist',
  '--delay-ms', '0', '--output-dir', {json.dumps(str(tmp_path))}
]);
options.readinessTimeoutMs = 100;
try {{
  await captureScreenshot(options);
  process.exitCode = 9;
}} catch (error) {{
  console.log(error.message);
}}
""",
        check=False,
    )
    assert result.returncode == 0
    assert "Capture selector failed" in result.stdout
    assert "matched 0" in result.stdout


def test_retired_capture_runtime_cannot_be_reintroduced_silently():
    shipped_roots = [ROOT / "FrontEnd", ROOT / "BackEnd"]
    forbidden = (
        "GOBCapture",
        "GOB_CAPTURE_BOOTSTRAPPED",
        "captureBootstrap",
        "captureControls",
        "captureCourt",
        "captureDom",
        "captureUtils",
        "html2canvas",
        "preserveDrawingBuffer",
    )
    matches = []
    for shipped_root in shipped_roots:
        for path in shipped_root.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for token in forbidden:
                if token in text:
                    matches.append(f"{path.relative_to(ROOT)}: {token}")
    assert not matches, "Retired screenshot runtime references found:\n" + "\n".join(matches)
