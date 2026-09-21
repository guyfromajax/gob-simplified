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


# ── every re-render rebinds ─────────────────────────────────────────────────

@pytest.mark.parametrize("marker", [
    "fccBindDevelopmentFocus(tbody);",
])
def test_fcc_rebinds_after_each_render_path(marker):
    """First paint, the sort re-render and the scope switch all replace the rows, so a
    single bind at load would leave the dropdowns dead after the first sort."""
    assert FCC_JS.count(marker) >= 3


def test_roster_view_rebinds_after_render():
    assert "GOBDevelopmentFocus.bind(body," in TRV_JS


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


def test_a_failed_save_reverts_the_control():
    """A silent revert-less failure would tell a coach a change stuck when it did not."""
    assert "if (previous) select.value = previous;" in SHARED_JS


def test_auth_headers_come_from_the_app_config():
    assert "API_CONFIG.getAuthHeaders" in SHARED_JS
    assert "localStorage" not in _strip_js_comments(SHARED_JS), \
        "one token source, not a second guess at the key"
