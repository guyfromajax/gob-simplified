"""Player Development grid: shared by the training page and the FCC Training tab.

These are the only two places development is editable, so they render from one module.
A coach who learns one has learned the other, and neither can drift.

Covers: RT follows the TRAINING position (not the best one), the hover card carries year /
height / weight / the core 12, row order never changes under an edit, and the Inbox tab's
retirement left nothing dangling.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
S = ROOT / "FrontEnd" / "static"
GRID = S / "js" / "shared" / "playerDevelopmentGrid.js"
GRID_JS = GRID.read_text()
FCC_JS = (S / "franchise-command-center.js").read_text()
FCC_HTML = (S / "franchise-command-center.html").read_text()
FCC_CSS = (S / "franchise-command-center.css").read_text()
TRAIN_JS = (S / "training.js").read_text()
TRAIN_HTML = (S / "training.html").read_text()
REPORT_JS = (S / "training-report.js").read_text()


# ── one implementation, two hosts ───────────────────────────────────────────

def test_both_editors_render_from_the_one_module():
    for src in (TRAIN_JS, FCC_JS):
        assert "GOBPlayerDevelopmentGrid" in src
    for page in (TRAIN_HTML, FCC_HTML):
        assert "/js/shared/playerDevelopmentGrid.js" in page
        assert "/css/player-development-grid.css" in page


def test_neither_host_builds_its_own_cards():
    """Card markup lives in the module. A second copy is how two screens start disagreeing."""
    for src in (TRAIN_JS, FCC_JS):
        assert "pdg-card" not in src
        assert "positionSelectHtml" not in src


def test_the_summaries_sit_above_the_roster():
    """A summary belongs before the detail it summarises, and twelve rows would push it
    below the fold if it sat underneath."""
    for page in (TRAIN_HTML, FCC_HTML):
        assert page.index("pdg-tally") < page.index('class="pdg-grid"')


def test_the_fcc_tab_does_not_depend_on_the_training_endpoint():
    """/franchise/training-points 400s after week 26 and is the training page's own
    dependency. Using it here would rebuild the gap this tab exists to close."""
    fn = FCC_JS[FCC_JS.index("function renderFccTrainingTab"):]
    fn = fn[:fn.index("\nfunction fccMaxPositionRating")]
    assert "training-points" not in fn
    assert "userRosterDataCache" in fn


# ── behaviour, executed ─────────────────────────────────────────────────────

pytestmark_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")

HARNESS = """
'use strict';
global.window = {};
global.CSS = { escape: (s) => s };
require(__DEVFOCUS__);
require(__GRID__);
const g = global.window.GOBPlayerDevelopmentGrid;
const player = {
  id: 'p1', name: 'Brice Monroe Jr', year: 'JR', height: 76, weight: 198,
  attributes: { SC: 5, SH: 5, PS: 2, BH: 3, ID: 6, OD: 7, RB: 3, ST: 2, AG: 8, FT: 3, IQ: 3, ND: 3 },
  position_ratings: { PG: 40, SG: 55, SF: 73, PF: 61, C: 48 },
  resolved_training_position: __POS__,
  resolved_training_focus: 'standard',
};
process.stdout.write(JSON.stringify({
  rt: g.rtAtTrainingPosition(player),
  height: g.formatHeight(76),
  attrs: g.ATTR_ORDER,
  anchorPreferred: g.attrValue({ anchor_SC: 9, SC: 5 }, 'SC'),
}));
"""


def _run(pos: str) -> dict:
    script = (textwrap.dedent(HARNESS)
              .replace("__GRID__", json.dumps(str(GRID)))
              .replace("__DEVFOCUS__", json.dumps(str(S / "js" / "shared" / "developmentFocus.js")))
              .replace("__POS__", json.dumps(pos)))
    return json.loads(subprocess.check_output(["node", "-e", script], text=True, timeout=30))


@pytestmark_node
def test_rt_follows_the_training_position_not_the_best_one():
    """The headline behaviour: a natural SF coached at C shows his C rating, not his SF one."""
    assert _run("SF")["rt"] == 73
    assert _run("C")["rt"] == 48
    assert _run("PG")["rt"] == 40


@pytestmark_node
def test_the_hover_card_shows_all_twelve_core_attributes():
    assert _run("SF")["attrs"] == ["SC", "SH", "PS", "BH", "ID", "OD", "RB", "ST", "AG", "FT", "IQ", "ND"]


@pytestmark_node
def test_height_renders_from_inches_and_anchors_win():
    r = _run("SF")
    assert r["height"] == '6\'4"'
    assert r["anchorPreferred"] == 9, "anchor_ is the trained value; the bare key is stale"


# ── order is stable while editing ───────────────────────────────────────────

def test_a_position_change_repaints_the_number_not_the_order():
    """Re-sorting on change would pull the row out from under the coach the instant he
    used it. Only the RT cell is rewritten."""
    fn = GRID_JS[GRID_JS.index("function render(host"):]
    fn = fn[:fn.index("\n  function paintTallies")]
    assert "[data-pdg-rt]" in fn
    assert ".sort(" not in fn


def test_both_editors_link_to_the_training_by_position_chart():
    """Same affordance in both places. The training page saves its draft first because
    leaving mid-allocation would lose points; the FCC tab has nothing to protect, since
    every change there is already saved."""
    assert 'id="fcc-training-tutorial-btn"' in FCC_HTML
    assert 'id="player-dev-tutorial-btn"' in TRAIN_HTML
    for src in (FCC_JS, TRAIN_JS):
        assert "tutorial-advanced-training-by-position.html" in src
        assert "setTrainingPageContext" in src, "the chart needs a way back"
    train_fn = TRAIN_JS[TRAIN_JS.index("function wirePlayerDevelopmentTutorialButton"):]
    assert "saveTrainingFormDraft();" in train_fn[:train_fn.index("window.location.href")]


# ── the Inbox is retired cleanly ────────────────────────────────────────────

def test_the_inbox_tab_is_gone_with_nothing_dangling():
    assert 'data-tab="tutorials-tab"' not in FCC_HTML
    assert "fcc-inbox" not in FCC_HTML
    assert "renderFccInbox" not in FCC_JS
    assert "fcc-inbox" not in FCC_CSS, "orphaned styles for a tab that no longer exists"
    assert "tutorials-tab" not in FCC_CSS


def test_tab_order_is_training_then_recruiting_then_news():
    bar = FCC_HTML[FCC_HTML.index('data-tab="standings-tab"'):FCC_HTML.index("</div>", FCC_HTML.index('data-tab="standings-tab"'))]
    order = [bar.index(t) for t in ('data-tab="awards-tab"', 'data-tab="training-tab"',
                                    'data-tab="recruits-tab"', 'data-tab="press-tab"')]
    assert order == sorted(order)


def test_everything_the_inbox_published_now_runs_in_news():
    """Training report, Practice Squad development report, and game results/box scores."""
    fn = FCC_JS[FCC_JS.index("function fccTeamDispatches"):]
    fn = fn[:fn.index("\nfunction renderNewsTab") if "\nfunction renderNewsTab" in fn else len(fn)]
    assert "training report" in fn
    assert "training_squad_report" in fn
    assert "game_result" in fn
    assert "box score" in fn


def test_dispatches_interleave_into_the_week_cards():
    fn = FCC_JS[FCC_JS.index("async function renderNewsTab"):]
    fn = fn[:fn.index("\nasync function renderHomeTab")]
    assert "fccTeamDispatches(" in fn
    assert "b.mine.join('')" in fn, "your items render inside the week card, not beside it"


def test_a_shared_report_link_still_has_its_back_button():
    """Links already out in the wild carry from=inbox; the tab they named is gone, but the
    Back button must still work and must now return to News."""
    assert "_reportFromRaw === 'news' || _reportFromRaw === 'inbox'" in REPORT_JS
    assert "tab: 'press-tab'" in REPORT_JS
    assert "tutorials-tab" not in REPORT_JS
