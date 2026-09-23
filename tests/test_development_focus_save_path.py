"""The Development Focus save path: a saved change must never look like a failed one.

Shipped bug (fixed here). `toast()` read an undeclared `toastTimer` — the declaration was
deleted by an unrelated edit — and the file is 'use strict', so it threw. Because `toast()`
was called inside the promise's SUCCESS handler and the failure handler was a trailing
`.catch()`, that throw was caught by the failure path, which reverted the control. The
write had already succeeded, so:

  * every FIRST change to a player showed the old value while the database held the new one;
  * a SECOND change to a DIFFERENT value left the control showing the FIRST value, matching
    neither what the coach picked nor what was stored.

The declaration is restored, but that alone would leave the design fragile: any future
throw after a successful save reproduces the symptom exactly. So the failure handler is now
`.then(onSuccess, onFailure)` — passed as the second argument, it structurally cannot see
anything thrown by the success handler beside it. These tests exercise that, they do not
just grep for it.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / "FrontEnd" / "static" / "js" / "shared" / "developmentFocus.js"
SRC = MODULE.read_text()

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")


HARNESS = """
'use strict';
// Minimal DOM: only what the module actually touches.
const el = () => ({ id: '', className: '', textContent: '', classList: {
  _s: new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
  toggle(c,on){on?this._s.add(c):this._s.delete(c);}, contains(c){return this._s.has(c);} },
  setAttribute(){}, appendChild(){} });
const body = { appendChild() {} };
global.document = { getElementById: () => null, createElement: () => el(), body: body };
global.window = { API_CONFIG: { getAuthHeaders: () => ({}) } };
global.API_CONFIG = { buildUrl: (p) => 'http://x' + p, getAuthHeaders: () => ({}) };
global.console = { error() {}, log() {}, warn() {} };

const MODE = __MODE__;   // 'ok' | 'fail' | 'ok_but_onsaved_throws'

global.fetch = () => MODE === 'fail'
  ? Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ detail: 'nope' }) })
  : Promise.resolve({ ok: true, json: () => Promise.resolve({ updated: true }) });

require(__PATH__);
const api = global.window.GOBDevelopmentFocus;

const select = {
  value: 'standard',
  disabled: false,
  dataset: { devfocusField: 'training_focus', playerId: 'p1', devfocusPrev: 'standard' },
  _h: null,
  addEventListener(_t, h) { this._h = h; },
};
const root = { querySelectorAll: () => [select] };

const onSaved = MODE === 'ok_but_onsaved_throws'
  ? () => { throw new Error('boom in onSaved'); }
  : () => {};

api.bind(root, () => 'fid', onSaved);

// The browser sets .value before firing 'change'.
select.value = 'rebounding';
select._h();

setTimeout(() => {
  console.log = undefined;
  process.stdout.write(JSON.stringify({
    shown: select.value,
    prev: select.dataset.devfocusPrev,
    disabled: select.disabled,
  }));
}, 30);
"""


def _run(mode: str) -> dict:
    script = (textwrap.dedent(HARNESS)
              .replace("__PATH__", json.dumps(str(MODULE)))
              .replace("__MODE__", json.dumps(mode)))
    out = subprocess.check_output(["node", "-e", script], text=True, timeout=30)
    return json.loads(out.strip())


# ── behaviour ───────────────────────────────────────────────────────────────

def test_a_successful_save_keeps_the_new_value():
    """The shipped bug: this showed 'standard' while the database held 'rebounding'."""
    r = _run("ok")
    assert r["shown"] == "rebounding"
    assert r["prev"] == "rebounding"
    assert r["disabled"] is False, "the control must be re-enabled either way"


def test_a_failed_save_reverts_the_control():
    """Still true, and the point of having a failure path at all: a coach must never be
    left looking at a value that was not stored."""
    r = _run("fail")
    assert r["shown"] == "standard"
    assert r["prev"] == "standard"
    assert r["disabled"] is False


def test_a_throw_after_a_successful_save_does_not_revert():
    """The structural guarantee. `onSaved` blows up here; the save still succeeded, so the
    control must keep the new value. Under the old .then().catch() shape this reverted."""
    r = _run("ok_but_onsaved_throws")
    assert r["shown"] == "rebounding", "a post-save error was misreported as a failed save"
    assert r["prev"] == "rebounding"


# ── the shape that makes the above structural ───────────────────────────────

def test_the_failure_handler_is_thens_second_argument():
    """A trailing .catch() would see throws from the success handler; a second argument
    to .then() cannot. That distinction is the whole fix."""
    bind = SRC[SRC.index("function bind(root"):]
    bind = bind[:bind.index("\n  }")]
    assert ".catch(" not in bind, "a trailing .catch would swallow post-save errors again"
    assert "save(getFranchiseId(), playerId, field, value).then(" in bind


def test_toast_timer_is_declared():
    """The specific regression: an unrelated edit deleted this line, and 'use strict' turned
    the read into a ReferenceError on every single successful save."""
    assert "var toastTimer = null;" in SRC
    assert SRC.index("var toastTimer") < SRC.index("if (toastTimer)")


def test_post_save_side_effects_are_individually_guarded():
    assert "function runSafely(fn)" in SRC
    bind = SRC[SRC.index("function bind(root"):SRC.index("function runSafely")]
    assert bind.count("runSafely(") == 3, "onSaved and both toasts"
