"""The tutorial's matrix asset must match Python, byte for byte.

The Training-by-Position page used to carry the percentages as hand-typed table cells, and
`Training_System.md` warned that "any retune of those percentages must be mirrored there."
A warning in a doc is not a guard: the retune ships, the mirror is forgotten, and the page
quietly teaches coaches numbers the engine stopped using. Development Focus took the page
from 60 cells to 360, so hand-authoring stopped being viable at all.

This is the guard. If `training_shape.py` moves and the asset is not regenerated, this
fails and names the command.
"""
from __future__ import annotations

import pathlib

import pytest

from BackEnd.constants.training_shape import (
    POSITIONS,
    TRAINING_FOCUSES,
    TRAINING_FOCUS_PERCENTAGES,
)
from scripts.generate_training_matrix_asset import ASSET, ATTR_ROWS, BANDS, build_payload, render

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = (ROOT / "FrontEnd" / "static" / "tutorial-advanced-training-by-position.html").read_text()


# ── the drift guard ─────────────────────────────────────────────────────────

def test_the_committed_asset_matches_python():
    assert ASSET.exists(), "run: python scripts/generate_training_matrix_asset.py"
    assert ASSET.read_text() == render(), (
        "FrontEnd/static/js/generated/trainingMatrix.js is stale.\n"
        "Regenerate with: python scripts/generate_training_matrix_asset.py"
    )


def test_the_asset_says_it_is_generated():
    """Whoever opens it next needs to know not to edit it in place."""
    head = ASSET.read_text()[:600]
    assert "GENERATED FILE" in head
    assert "generate_training_matrix_asset.py" in head


# ── the payload carries the whole matrix, not a sample ──────────────────────

def test_every_profile_is_published():
    matrix = build_payload()["matrix"]
    assert set(matrix) == set(POSITIONS)
    for pos in POSITIONS:
        assert set(matrix[pos]) == set(TRAINING_FOCUSES), pos
        for focus in TRAINING_FOCUSES:
            assert set(matrix[pos][focus]) == {c for c, _ in ATTR_ROWS}, (pos, focus)


@pytest.mark.parametrize("pos", POSITIONS)
@pytest.mark.parametrize("focus", TRAINING_FOCUSES)
def test_published_values_are_the_engine_values(pos, focus):
    published = build_payload()["matrix"][pos][focus]
    for attr, value in published.items():
        assert value == TRAINING_FOCUS_PERCENTAGES[pos][focus][attr]


def test_no_attribute_is_quietly_dropped_from_the_page():
    """A missing row would read as "this attribute is not trained" rather than as a bug."""
    codes = {c for c, _ in ATTR_ROWS}
    assert codes == set(TRAINING_FOCUS_PERCENTAGES["PG"]["standard"])


def test_the_attribute_order_is_the_reading_order_not_the_dict_order():
    """Standard display order, shared by By Position and By Focus."""
    assert [c for c, _ in ATTR_ROWS] == [
        "SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT",
    ]


# ── bands ───────────────────────────────────────────────────────────────────

def test_bands_are_published_so_cells_and_legend_cannot_disagree():
    assert build_payload()["bands"] == BANDS
    assert [b["min"] for b in BANDS] == sorted((b["min"] for b in BANDS), reverse=True), \
        "the page picks the first band a value clears, so they must descend"
    assert BANDS[-1]["min"] == 0, "every value must land in some band"


def test_no_band_is_called_standard():
    """The page now has a Standard FOCUS. A band with the same name would make "Standard"
    mean two different things in one legend."""
    assert not any(b["label"].lower() == "standard" for b in BANDS)


# ── the page consumes the asset rather than repeating it ────────────────────

def test_the_page_loads_the_generated_asset():
    assert "/js/generated/trainingMatrix.js" in PAGE


def test_the_page_carries_no_hand_typed_percentages():
    """The failure this whole phase exists to prevent."""
    assert 'data-band="full">100%' not in PAGE
    assert PAGE.count("%</span>") == 0


# ── the page renders both orientations from the one asset ───────────────────

GRID_JS = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "trainingMatrixGrid.js").read_text()


def test_both_orientations_exist_and_read_the_same_data():
    """Two views of one dataset. A second copy of the numbers for the second view would
    reintroduce exactly the drift this phase removes."""
    assert 'data-fg-mode="position"' in PAGE
    assert 'data-fg-mode="focus"' in PAGE
    assert GRID_JS.count("DATA.matrix[") == 2, "one lookup per orientation, one source"


def test_it_lands_on_by_focus_standard():
    """Five positions under the default focus — the table this page has always shown, and
    the state every player is actually in. The focus dimension is opted into, not landed in.

    The markup's pressed state and the renderer's initial state are set in two different
    files; a mismatch would show one tab highlighted while the other tab's table rendered."""
    assert "mode: 'focus'" in GRID_JS
    assert "focus: DATA.focuses[0].value" in GRID_JS
    assert TRAINING_FOCUSES[0] == "standard", "focuses[0] is what the page lands on"

    focus_btn = PAGE[PAGE.index('class="fg-mode is-on"'):]
    focus_btn = focus_btn[:focus_btn.index("</button>")]
    assert 'data-fg-mode="focus"' in focus_btn
    assert 'aria-selected="true"' in focus_btn
    assert PAGE.count('class="fg-mode is-on"') == 1, "exactly one tab starts pressed"


def test_the_archetype_subhead_is_gone():
    """Archetype is not a dimension of this matrix and never was — position and focus are."""
    intro = PAGE[PAGE.index('<p class="intro">'):]
    intro = intro[:intro.index("</p>")]
    assert "archetype" not in intro.lower()
    assert "position and development focus" in intro
    # (archetypeBadge.js is an unrelated shared script and legitimately stays.)


def test_the_legend_is_built_from_the_published_bands():
    assert "DATA.bands" in GRID_JS
    assert '<div class="fitgrid-legend" id="fitgrid-legend"></div>' in PAGE
    assert "Strong Fit" not in PAGE, "band labels come from the asset, not the markup"


def test_cells_pick_the_first_band_they_clear():
    fn = GRID_JS[GRID_JS.index("function bandFor"):]
    fn = fn[:fn.index("\n  }")]
    assert "value >= DATA.bands[i].min" in fn
