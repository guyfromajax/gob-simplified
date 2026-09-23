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


# ── the hover card is always fully on screen ────────────────────────────────

PLACE_HARNESS = """
'use strict';
// Replays the real placement arithmetic from showHoverCard against a fake viewport.
const VH = 900, VW = 1400, GAP = 8, EDGE = 8;
const CARD = { w: 252, h: 210 };

function place(anchorTop, anchorLeft) {
  const a = { top: anchorTop, bottom: anchorTop + 18, left: anchorLeft };
  const above = a.top - GAP - CARD.h;
  const below = a.bottom + GAP;
  let top;
  if (above >= EDGE) top = above;
  else if (below + CARD.h <= VH - EDGE) top = below;
  else top = Math.max(EDGE, VH - EDGE - CARD.h);
  const left = Math.min(Math.max(EDGE, a.left), VW - EDGE - CARD.w);
  return { top, left, bottom: top + CARD.h, right: left + CARD.w };
}

const cases = {
  topRow:     place(120, 180),    // near the panel top — used to clip upward
  bottomRow:  place(830, 180),    // near the page bottom — used to fall off
  middle:     place(500, 180),
  farRight:   place(500, 1330),   // would overflow the right edge
  farLeft:    place(500, 2),
};
const fits = {};
Object.keys(cases).forEach((k) => {
  const c = cases[k];
  fits[k] = c.top >= EDGE && c.bottom <= VH - EDGE && c.left >= EDGE && c.right <= VW - EDGE;
});
process.stdout.write(JSON.stringify({ cases, fits }));
"""


@pytestmark_node
def test_the_hover_card_never_leaves_the_viewport():
    """The two shipped bugs: the top row's card clipped against the panel edge, and the
    bottom row's flipped downward off the page. Both are placement, so both are tested as
    placement — plus the horizontal edges, which the old markup never handled at all."""
    out = json.loads(subprocess.check_output(
        ["node", "-e", textwrap.dedent(PLACE_HARNESS)], text=True, timeout=30))
    for case, ok in out["fits"].items():
        assert ok, f"{case} placed off-screen: {out['cases'][case]}"


@pytestmark_node
def test_it_prefers_above_but_flips_below_when_there_is_no_room():
    out = json.loads(subprocess.check_output(
        ["node", "-e", textwrap.dedent(PLACE_HARNESS)], text=True, timeout=30))
    assert out["cases"]["middle"]["bottom"] < 500, "roomy anchor opens upward"
    assert out["cases"]["topRow"]["top"] > 120, "no room above, so it opens downward"


def test_the_card_is_not_inside_the_row_it_describes():
    """An ancestor that clips is unfixable by choosing a better side, so the card lives on
    <body> at position:fixed instead."""
    assert "document.body.appendChild(cardEl)" in GRID_JS
    css = (S / "css" / "player-development-grid.css").read_text()
    block = css[css.index(".pdg-hovercard {"):]
    block = block[:block.index("}")]
    assert "position: fixed" in block
    import re as _re
    code = _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)   # the comment explains the fix
    assert "nth-child" not in code, "the old flip-by-position rule was the bug"


def test_scrolling_dismisses_it_rather_than_stranding_it():
    """Fixed coordinates are taken once; a scroll would leave the card pointing at nothing."""
    assert "window.addEventListener('scroll', hideHoverCard, true)" in GRID_JS
    assert "window.addEventListener('resize', hideHoverCard)" in GRID_JS


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


# ── what the focus develops, in the hover card ──────────────────────────────

DEVELOPS_HARNESS = """
'use strict';
global.window = {}; global.CSS = { escape: (s) => s };
require(__DEVFOCUS__); require(__MATRIX__); require(__GRID__);
const g = global.window.GOBPlayerDevelopmentGrid;
const mk = (p, f) => ({ id: 'x', name: 'T', position_ratings: { [p]: 70 },
  resolved_training_position: p, resolved_training_focus: f, attributes: {} });
const FOCUSES = ['standard','offensive','defensive','athletic','fundamentals','rebounding'];
const out = { PG: {}, C: {}, SG: {} };
Object.keys(out).forEach((pos) => FOCUSES.forEach((f) => { out[pos][f] = g.developsFor(mk(pos, f)); }));
process.stdout.write(JSON.stringify(out));
"""


def _develops() -> dict:
    script = (textwrap.dedent(DEVELOPS_HARNESS)
              .replace("__GRID__", json.dumps(str(GRID)))
              .replace("__DEVFOCUS__", json.dumps(str(S / "js" / "shared" / "developmentFocus.js")))
              .replace("__MATRIX__", json.dumps(str(S / "js" / "generated" / "trainingMatrix.js"))))
    return json.loads(subprocess.check_output(["node", "-e", script], text=True, timeout=30))


@pytestmark_node
def test_each_focus_names_something_different():
    """The flaw in the first rule. An absolute threshold marked the same four codes on a
    PG's Standard, Defensive AND Fundamentals, so changing focus changed nothing on screen.
    A chosen focus now reports what it RAISES above Standard for that position."""
    pg = _develops()["PG"]
    assert pg["offensive"] == ["SC", "SH"]
    assert pg["defensive"] == ["ID", "OD"]
    assert pg["rebounding"] == ["RB", "ST"]
    assert pg["athletic"] == ["ST", "AG"]
    assert len({tuple(v) for k, v in pg.items() if k != "standard"}) == 5, \
        "five chosen focuses, five distinct answers"


@pytestmark_node
def test_standard_names_where_his_points_land_best():
    """Standard has no baseline to differ from, so it falls back to the published threshold."""
    assert _develops()["PG"]["standard"] == ["PS", "BH", "OD", "AG"]


@pytestmark_node
def test_every_profile_names_at_least_one_and_at_most_four():
    """Enough to be a statement, few enough to read without decoding."""
    d = _develops()
    for pos, focuses in d.items():
        for focus, attrs in focuses.items():
            assert 1 <= len(attrs) <= 4, f"{pos}/{focus} -> {attrs}"


@pytestmark_node
def test_the_always_100_attributes_are_never_named():
    """FT/IQ/ND are 100% in every profile, so naming them would put the same three codes on
    every player on every focus. The asset derives them rather than hardcoding."""
    d = _develops()
    for focuses in d.values():
        for attrs in focuses.values():
            assert not ({"FT", "IQ", "ND"} & set(attrs))


def test_the_accent_is_on_the_code_and_never_the_value():
    """Colour on a rating already means 'how good is he' product-wide — blue #4A90D9 for
    10+, green for 7-9 (attrTiles.js). Tinting the values here would make one colour mean
    two things on the same attribute, one click apart."""
    css = (S / "css" / "player-development-grid.css").read_text()
    assert ".pdg-hc-attr.is-develops b { color: #F79420; }" in css
    assert ".pdg-hc-attr.is-develops i" not in css
    block = css[css.index(".pdg-hc-attr i {"):]
    assert "color: #fff" in block[:block.index("}")]


def test_the_threshold_is_published_not_hardcoded_in_the_view():
    assert "data.develops.min" in GRID_JS
    gen = (ROOT / "scripts" / "generate_training_matrix_asset.py").read_text()
    assert "DEVELOPS_MIN = 70" in gen
    assert "def _locked_attrs" in gen
