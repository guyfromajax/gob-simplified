"""Development Focus, phase 4: the roster surfaces and the ownership gate behind them.

Phase 4 renders live controls on the FCC roster tab and the roster page, and a read-only
block on the player page. All three hang off ONE question — "is this the user's own
team?" — and the first revision answered it by comparing ``meta.team_id`` (an ObjectId
string) against ``user_team_id`` (a team NAME). That comparison matches nothing, so the
block never rendered and every save came back 403. The franchise document really does
carry both identifiers, and FPD ``meta`` mirrors both, so these tests pin the pairing.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
API_SRC = (ROOT / "BackEnd" / "api" / "api.py").read_text()
FRANCHISE_SRC = (ROOT / "BackEnd" / "api" / "franchise_routes.py").read_text()
SHARED_JS = (ROOT / "FrontEnd" / "static" / "js" / "shared" / "developmentFocus.js").read_text()
FCC_JS = (ROOT / "FrontEnd" / "static" / "franchise-command-center.js").read_text()
TRV_JS = (ROOT / "FrontEnd" / "static" / "team-roster-view.js").read_text()
FCC_HTML = (ROOT / "FrontEnd" / "static" / "franchise-command-center.html").read_text()


def _strip_js_comments(source: str) -> str:
    """Comments describe the rule; these guards must read the code that enforces it."""
    without_blocks = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(line for line in without_blocks.splitlines()
                      if not line.lstrip().startswith("//"))


def _load_function(source: str, name: str):
    """Exec one module-level function in isolation — api.py itself builds the whole app."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            namespace: dict = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<extracted>", "exec"), namespace)
            return namespace[name]
    raise AssertionError(f"{name} not found")


on_user_team = _load_function(API_SRC, "_player_on_user_team")

# Shapes taken from real gob-staging documents, not invented:
#   franchises: {user_team_id: 'Bentley-Truman', user_team_object_id: '69a6...a52'}
#   FPD meta:   {team: 'Hollywood Prep', team_id: '69a6...ac6'}
FRANCHISE = {"user_team_id": "Bentley-Truman", "user_team_object_id": "69a6fcb68d2c56aa82e48a52"}


# ── the ownership gate ───────────────────────────────────────────────────────

def test_matches_on_the_team_object_id():
    assert on_user_team(FRANCHISE, {"team": "Bentley-Truman", "team_id": "69a6fcb68d2c56aa82e48a52"})


def test_matches_on_the_team_name_when_the_id_is_absent():
    """Older FPD docs carry meta.team without meta.team_id."""
    assert on_user_team(FRANCHISE, {"team": "Bentley-Truman"})


def test_rejects_another_teams_player():
    assert not on_user_team(FRANCHISE, {"team": "Hollywood Prep", "team_id": "69a6fcb68d2c56aa82e48ac6"})


def test_does_not_compare_an_id_against_a_name():
    """The regression: meta.team_id vs user_team_id (a name) matched nothing, everywhere."""
    assert not on_user_team({"user_team_id": "Bentley-Truman"},
                            {"team_id": "69a6fcb68d2c56aa82e48a52"})


@pytest.mark.parametrize("franchise,meta", [
    (None, {"team_id": "x"}),
    ({}, {"team_id": "x"}),
    (FRANCHISE, None),
    (FRANCHISE, {}),
    ({"user_team_object_id": ""}, {"team_id": ""}),
    ({"user_team_id": ""}, {"team": ""}),
])
def test_missing_data_is_never_ownership(franchise, meta):
    """An empty identifier on either side must not read as a match — that would hand a
    coach another team's controls, and the write route uses the same rule."""
    assert not on_user_team(franchise, meta)


# ── the write route applies the same rule ───────────────────────────────────

def _write_route_body() -> str:
    start = FRANCHISE_SRC.index('@router.post("/franchise/player/development-focus")')
    end = FRANCHISE_SRC.index("@router.", start + 10)
    return FRANCHISE_SRC[start:end]


def test_write_route_projects_both_identifiers():
    body = _write_route_body()
    assert "user_team_object_id" in body, "projecting only the name reintroduces the 403"
    assert "user_team_id" in body


def test_write_route_still_rejects_a_foreign_player():
    assert "Player is not on your team" in _write_route_body()


def test_write_route_reuses_the_shared_team_resolver():
    assert "get_user_team_from_franchise(franchise)" in _write_route_body()


# ── the roster payload decides, the views do not guess ──────────────────────

def test_roster_payload_carries_the_ownership_flag():
    assert '"is_user_team": is_user_team' in API_SRC


def test_roster_development_keys_ride_on_ownership_not_on_franchise_mode():
    """Gating on `franchise_id` alone would ship the keys with every opponent roster."""
    tail = API_SRC.split('"training_position": p.get')[1][:400]
    assert "} if is_user_team else {})" in tail
    assert "} if franchise_id else {})" not in tail


def test_roster_view_reads_the_flag_rather_than_the_url():
    assert "trIsUserTeam = !!data.is_user_team" in TRV_JS
    assert "function trShowDevelopment()" in TRV_JS


# ── one POS column, not a derived one plus a training one ───────────────────

def test_fcc_has_a_single_position_column_titled_pos():
    head = FCC_HTML[FCC_HTML.index('<th class="c-ident" data-sort-col="Name">'):]
    head = head[:head.index("</thead>")]
    assert head.count('data-sort-col="POS"') == 1
    assert 'data-sort-col="TrainPos"' not in head, "the duplicate training column is gone"
    assert ">POS<" in head and ">TRAIN<" not in head


def test_pos_keeps_its_slot_and_dev_focus_trails_the_attributes():
    """POS stays in the third column it has always occupied — the edit moved to the
    training page, so the column is a plain value again. DEV FOCUS sits past the attribute
    tiles: read the evidence, then the coaching call."""
    head = FCC_HTML[FCC_HTML.index('<th class="c-ident" data-sort-col="Name">'):]
    head = head[:head.index("</thead>")]
    order = [head.index(m) for m in ('data-sort-col="RT"', 'data-sort-col="POS"',
                                     'data-sort-col="Year"', 'attr-tiles-head',
                                     'data-sort-col="Focus"')]
    assert order == sorted(order)


def test_the_row_builders_emit_the_same_order_as_the_header():
    """Header and row are built in different places; a mismatch shifts every cell."""
    row = FCC_JS[FCC_JS.index("function fccRosterRowHtml"):]
    row = row[:row.index("\n}")]
    order = [row.index(m) for m in ("fccRtLockupHtml", "fccPositionCellHtml",
                                    "p.weight", "attr-tiles-cell", "fccFocusCellHtml")]
    assert order == sorted(order)

    trow = TRV_JS[TRV_JS.index("function trAttrRowHtml"):]
    trow = trow[:trow.index("\n}")]
    torder = [trow.index(m) for m in ("trPositionCellHtml", "p.weight",
                                      "attr-tiles-cell", "trFocusCellHtml")]
    assert torder == sorted(torder)


def test_the_pos_cell_falls_back_to_the_chip_where_development_does_not_apply():
    """Practice-squad rows must still show a position, just not a development one."""
    fn = FCC_JS[FCC_JS.index("function fccPositionCellHtml"):]
    fn = fn[:fn.index("\n}")]
    assert "fccPosChipHtml(p.pos)" in fn
    assert "FCC_ROSTER_STATE.scope === 'practice'" in fn


def test_roster_view_pos_cell_does_the_same():
    fn = TRV_JS[TRV_JS.index("function trPositionCellHtml"):]
    fn = fn[:fn.index("\n}")]
    assert "trPosChipHtml(p.pos)" in fn
    assert "positionTextHtml(p)" in fn


# ── one editor: the training page ───────────────────────────────────────────

TRAINING_JS = (ROOT / "FrontEnd" / "static" / "training.js").read_text()


def test_the_roster_surfaces_are_read_only():
    """The rosters are for scanning and comparing. A live control in a twelve-tile-wide
    row also invites a stray click that writes to the database with no undo."""
    for src in (FCC_JS, TRV_JS):
        assert "positionSelectHtml" not in src
        assert "focusSelectHtml" not in src
        assert "GOBDevelopmentFocus.bind" not in src


def test_the_training_page_is_the_editor():
    assert "dev.positionSelectHtml(player)" in TRAINING_JS
    assert "dev.focusSelectHtml(player)" in TRAINING_JS
    assert "dev.bind(playerDevGrid" in TRAINING_JS


def test_the_rosters_carry_no_route_to_the_editor_yet():
    """Deliberate, pending testing: the rosters display the two values and nothing else.
    A "Set development" link was built and pulled back out — revisit once the one-editor
    flow has been used in anger. Discoverability is the open question, not a settled one."""
    for html_name in ("franchise-command-center.html", "team-roster-view.html"):
        html = (ROOT / "FrontEnd" / "static" / html_name).read_text()
        assert "devfocus-goto" not in html, html_name
    for src in (FCC_JS, TRV_JS):
        assert "devfocus-goto-training" not in src
    # (The FCC's own Run Training button links to training.html; that is unrelated.)


def test_the_shared_module_still_owns_both_renderings():
    """Read-only and editable are two renderings of one contract, not two features."""
    for name in ("positionTextHtml", "focusTextHtml", "positionSelectHtml", "focusSelectHtml"):
        assert name + ":" in SHARED_JS, name


def test_a_converted_player_still_says_where_his_rt_came_from():
    """RT is the rating at the NATURAL best position. Since POS shows the training
    position, a divergence would leave RT labelled by a position the row no longer names."""
    assert "function fccNaturalPositionHintHtml" in FCC_JS
    for src in (FCC_JS, TRV_JS):
        assert "devfocus-natural" in src
        assert "positionOf(p)" in src


def test_the_hint_is_silent_when_the_two_agree():
    fn = FCC_JS[FCC_JS.index("function fccNaturalPositionHintHtml"):]
    fn = fn[:fn.index("\n}")]
    assert "natural === api.positionOf(p)) return ''" in fn


def test_pos_sorting_was_broken_and_is_now_wired():
    """'POS' mapped to 'pos', fell through to the attribute branch, read a non-existent
    anchor_pos and scored every row 0 — clicking the header did nothing."""
    assert "dataKey === 'pos' || dataKey === 'Focus'" in FCC_JS
    assert "if (key === 'pos')" in TRV_JS


# ── every re-render rebinds ─────────────────────────────────────────────────

def test_the_training_grid_binds_its_controls():
    assert "dev.bind(playerDevGrid" in (ROOT / "FrontEnd" / "static" / "training.js").read_text()


def test_fcc_mappers_carry_the_development_fields():
    """The projection trap, front-end edition: both FCC mappers cherry-pick fields."""
    assert FCC_JS.count("resolved_training_focus: p.resolved_training_focus") == 2


def test_practice_scope_renders_no_controls():
    assert "FCC_ROSTER_STATE.scope === 'practice'" in FCC_JS
    assert "TR_STATE.scope !== 'practice'" in TRV_JS


# ── the shared module is the only implementation ────────────────────────────

def test_focus_values_match_the_backend():
    from BackEnd.constants.training_shape import TRAINING_FOCUSES

    js_values = re.findall(r"\{ value: '([a-z]+)', label: '[A-Za-z]+' \}", SHARED_JS)
    assert js_values == list(TRAINING_FOCUSES)


def test_positions_match_the_backend():
    from BackEnd.constants.training_shape import POSITIONS

    listed = re.search(r"var POSITIONS = \[([^\]]+)\]", SHARED_JS).group(1)
    assert [p.strip().strip("'") for p in listed.split(",")] == list(POSITIONS)


def test_every_save_goes_to_the_one_route():
    assert _strip_js_comments(SHARED_JS).count("/franchise/player/development-focus") == 1
    for src in (FCC_JS, TRV_JS):
        assert "development-focus" not in _strip_js_comments(src), \
            "surfaces must save through the shared module"


# ── the control saves itself; nothing else does ────────────────────────────

def test_changing_a_dropdown_is_the_whole_interaction():
    """No confirm step, no apply button, no row ticks. Bulk set was built and then removed:
    an unlabelled checkbox beside a control that already saves read as a save confirmation,
    and the toolbar explaining it only appeared after the first tick."""
    for src in (SHARED_JS, FCC_JS, TRV_JS, (ROOT / "FrontEnd" / "static" / "training.js").read_text()):
        assert "devfocus-check" not in src
        assert "bulkSetFocus" not in src
    html = (ROOT / "FrontEnd" / "static" / "franchise-command-center.html").read_text()
    assert "devfocus-bulk" not in html
    assert "devfocus-bulk" not in (ROOT / "FrontEnd" / "static" / "css" / "development-focus.css").read_text()


def test_the_save_is_bound_to_the_change_event():
    assert "select.addEventListener('change'" in SHARED_JS


def test_a_failed_save_reverts_the_control():
    """A silent revert-less failure would tell a coach a change stuck when it did not."""
    assert "if (previous) select.value = previous;" in SHARED_JS


def test_auth_headers_come_from_the_app_config():
    assert "API_CONFIG.getAuthHeaders" in SHARED_JS
    assert "localStorage" not in _strip_js_comments(SHARED_JS), \
        "one token source, not a second guess at the key"
