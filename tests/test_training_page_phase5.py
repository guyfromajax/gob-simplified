"""Training page, phase 5: the three-column rebuild and the 6-pip steppers.

The rebuild moved every drill in the page and swapped the control, but the submit payload
is still assembled from twenty hard-coded element ids (`collectTrainingData`). Losing or
renaming one of those would not break the page — it would silently submit a zero for that
drill. These tests pin the ids, the control contract, and the pieces the rebuild is easy
to get half-right on.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "FrontEnd" / "static" / "training.html").read_text()
JS = (ROOT / "FrontEnd" / "static" / "training.js").read_text()
CSS = (ROOT / "FrontEnd" / "static" / "training.css").read_text()

# The twenty drills the backend is fed, exactly as collectTrainingData names them.
DRILL_IDS = [
    "offense-inside", "offense-outside",
    "defense-inside", "defense-outside",
    "technical-passing", "technical-ball-handling", "technical-rebounding",
    "weight-strength", "weight-agility",
    "team-offense-install", "team-defense-install",
    "fast-break-offense-install", "fast-break-defense-install",
    "press-offense-install", "press-defense-install",
    "team-scrimmages",
    "general-conditioning", "general-free-throws", "general-film-study", "general-breaks",
]


# ── the payload contract survived the rebuild ───────────────────────────────

@pytest.mark.parametrize("drill_id", DRILL_IDS)
def test_every_drill_id_is_still_on_the_page(drill_id):
    assert f'id="{drill_id}"' in HTML


@pytest.mark.parametrize("drill_id", DRILL_IDS)
def test_collect_training_data_still_reads_it(drill_id):
    assert f"getElementById('{drill_id}')" in JS


def test_there_are_exactly_twenty_drills():
    assert HTML.count('type="range"') == len(DRILL_IDS)


def test_weight_room_drills_kept_their_ids_when_the_group_retired():
    """Weight Room became Strength/Agility Training in General. The LABELS moved; the ids
    did not, because the payload still posts them under weight_room."""
    assert "Weight Room" not in HTML
    assert "Strength Training" in HTML and "Agility Training" in HTML
    assert "weight_room" in JS


# ── the 6-pip stepper ───────────────────────────────────────────────────────

def test_the_range_input_is_still_the_model():
    """The pips are a skin plus a click target. Every reader — points counter, draft
    save/restore, Auto-Train, collectTrainingData — still reads slider.value."""
    assert 'class="slider"' in HTML
    assert "function setSliderValueFromPip" in JS
    assert "slider.dispatchEvent(new Event('input'" in JS


def test_a_pip_click_routes_through_the_inputs_own_guard():
    """Setting .value directly would bypass the one over-allocation rule."""
    body = JS[JS.index("function setSliderValueFromPip"):JS.index("function updateTrainingSliderVisual")]
    assert "dispatchEvent" in body
    assert "updatePointsRemaining" not in body, "the input handler owns the accounting"


def test_the_hidden_range_stays_focusable():
    """clip, not display:none — the range is still the keyboard control."""
    block = CSS[CSS.index("body.training-page .slider-container .slider {"):]
    block = block[:block.index("}")]
    assert "clip-path" in block
    assert "display: none" not in block


def test_no_trailing_tally_on_a_pip_row():
    """The last lit pip already says the value; a number after it restated it twenty times."""
    assert "pipstep-readout" not in JS
    assert "pipstep-readout" not in CSS


def test_every_drill_row_has_the_same_shape():
    """Name left, pips hard right — the layout the General column's solo drills already
    used. The labelled rows in Player Drills and Scheme Installs stacked label over pips."""
    block = CSS[CSS.index("body.training-page .slider-label {\n  flex-direction: row;"):]
    block = block[:block.index("}")]
    assert "justify-content: space-between" in block
    container = CSS[CSS.index("body.training-page .slider-container {\n  flex: 0 0 auto;"):]
    container = container[:container.index("}")]
    assert "width: auto" in container


def test_solo_drills_still_get_their_attribute_chip():
    """Strength/Agility/Conditioning/Free Throws carry codes (ST/AG/ND/FT). Making them
    solo rows removed their .label-text, and the chip silently stopped rendering."""
    fn = JS[JS.index("function injectAttributeChip"):]
    fn = fn[:fn.index("\n}")]
    assert "drill-group--solo" in fn and "drill-title" in fn


def test_six_pips_per_stepper():
    build = JS[JS.index("function ensureTrainingSliderVisual"):JS.index("function setSliderValueFromPip")]
    assert "i <= 5" in build


def test_unreachable_pips_are_disabled_everywhere_not_just_locally():
    """Spending on one drill shrinks every other drill's reach; a stale pip that looks
    clickable but does nothing is the failure this prevents."""
    assert "function refreshAllTrainingSliderVisuals" in JS
    remaining = JS[JS.index("function updatePointsRemaining"):]
    remaining = remaining[:remaining.index("\n}\n")]
    assert "refreshAllTrainingSliderVisuals()" in remaining


# ── layout ──────────────────────────────────────────────────────────────────

def test_three_columns_not_two_plus_a_strip():
    assert 'class="content-section player-drills-section"' in HTML
    assert 'class="content-section scheme-installs-section"' in HTML
    assert 'class="content-section general-section"' in HTML
    grid = CSS[CSS.index(".main-content-grid {"):]
    assert "repeat(3, 1fr)" in grid[:grid.index("}")]


def test_general_is_a_column_not_a_full_width_row():
    block = CSS[CSS.index("body.training-page") if False else CSS.index(".general-section {"):]
    assert "grid-column: 1 / -1" not in block[:block.index("}")]


def test_the_three_columns_are_declared_at_the_overriding_specificity():
    """training.css carries a whole `body.training-page` block that outranks the plain
    `.main-content-grid` rules above it. The rebuild edited only the plain rules, so on
    the deployed page General still spanned the grid, dropped to a second row and left the
    third column empty. Declare the columns where the cascade actually lands."""
    block = CSS[CSS.index("body.training-page .main-content-grid {"):]
    block = block[:block.index("}")]
    assert "repeat(3, 1fr)" in block


def test_general_does_not_span_the_page_grid():
    spanning = CSS[CSS.index("body.training-page .main-content-grid,"):]
    spanning = spanning[:spanning.index("}")]
    assert "general-section" not in spanning, "General is a column, not a full-width strip"


def test_the_sliders_old_height_floor_is_gone():
    """74px fitted the range track, the node row and the 0-5 scale. With a 20px pip row it
    left ~50px of dead space under every one of the twenty labels."""
    block = CSS[CSS.index("body.training-page .slider-container {\n  position: relative;"):]
    block = block[:block.index("}")]
    assert "min-height: 0" in block


def test_all_three_panels_are_equal_height():
    assert "body.training-page .scheme-installs-section .section-container" in CSS
    assert "body.training-page .team-drills-section" not in CSS


def test_the_pill_stays_on_one_line():
    block = CSS[CSS.index("body.training-page .req-pill {"):]
    block = block[:block.index("}")]
    assert "flex-wrap: nowrap" in block


def test_team_drills_renamed_to_scheme_installs():
    assert "Scheme Installs" in HTML
    assert ">Team Drills<" not in HTML


def test_playbook_toggle_sits_under_the_installs_it_governs():
    installs = HTML.index('scheme-installs-section')
    toggle = HTML.index('playbook-mode-toggle')
    general = HTML.index('content-section general-section')
    assert installs < toggle < general


def test_the_coaching_focus_nag_line_stays_out():
    """Removed once before and reintroduced by a later rebuild. The requirements pill in
    the header already says a focus is needed; the subtitle explains what a focus IS."""
    assert "Required to submit" not in HTML
    assert "Sets what you emphasize across drills" in HTML


def test_scrimmages_moved_to_the_general_column():
    """It is a whole-team activity, not a scheme install, and it reads as a General row."""
    general = HTML.index('content-section general-section')
    assert HTML.index('id="team-scrimmages"') > general
    assert HTML.index('id="general-breaks"') < HTML.index('id="team-scrimmages"')


def test_no_column_reserves_height_it_is_not_using():
    """The grid stretches all three to the tallest; a fixed floor on top of that reserved
    space nothing filled."""
    block = CSS[CSS.index(".main-content-grid .section-container {"):]
    block = block[:block.index("}")]
    assert "min-height: 0" in block
    body_rule = CSS[CSS.index("body.training-page .section-container {"):]
    body_rule = body_rule[:body_rule.index("}")]
    assert "min-height: 0" in body_rule


def test_the_before_you_submit_bar_became_a_pill():
    assert 'class="req-bar"' not in HTML
    assert 'class="req-pill"' in HTML
    # Same ids, so the same updateRequirementsBar drives it.
    for el_id in ("requirements-bar", "req-points", "req-focus", "req-points-used",
                  "req-points-total", "req-points-meter", "req-focus-value",
                  "req-focus-nudge", "req-readout", "points-remaining"):
        assert f'id="{el_id}"' in HTML, el_id


def test_the_pill_sits_under_the_page_title():
    title = HTML.index('class="page-title"')
    pill = HTML.index('class="req-pill"')
    actions = HTML.index('class="header-actions"')
    assert title < pill < actions


# ── Player Development ──────────────────────────────────────────────────────

def test_player_development_reuses_the_shared_module():
    assert "/js/shared/developmentFocus.js" in HTML
    assert "/css/development-focus.css" in HTML
    assert "window.GOBDevelopmentFocus" in JS
    assert "development-focus" not in re.sub(r"//[^\n]*", "", JS), \
        "the training page must not save through its own route"


def test_it_costs_no_extra_request():
    """custom_focus_roster is already fetched, already RT-descending, and already carries
    both development fields through training_position_projection."""
    assert "renderPlayerDevelopment();" in JS
    load = JS[JS.index("data.custom_focus_roster"):]
    assert "renderPlayerDevelopment" in load[:400]


def test_the_grid_is_four_rows_of_three_filled_column_first():
    block = CSS[CSS.index("body.training-page .player-dev-grid {"):]
    block = block[:block.index("}")]
    assert "repeat(3, 1fr)" in block
    assert "repeat(4, auto)" in block
    assert "grid-auto-flow: column" in block


def test_positions_tally_left_focuses_tally_right():
    pos = HTML.index('player-dev-tally-positions')
    foc = HTML.index('player-dev-tally-focuses')
    assert pos < foc
    assert "player-dev-tally--focuses { justify-content: flex-end; }" in CSS


def test_leaving_for_the_chart_saves_the_draft_first():
    """A coach who opens Training by Position mid-allocation must come back to his points."""
    fn = JS[JS.index("function wirePlayerDevelopmentTutorialButton"):]
    fn = fn[:fn.index("wirePlayerDevelopmentTutorialButton();")]
    assert "saveTrainingFormDraft();" in fn
    assert "tutorial-advanced-training-by-position.html" in fn
    assert fn.index("saveTrainingFormDraft();") < fn.index("window.location.href")


def test_tally_recounts_after_a_save():
    saved = JS[JS.index("dev.bind(playerDevGrid"):]
    assert "renderPlayerDevelopmentTally();" in saved[:900]
