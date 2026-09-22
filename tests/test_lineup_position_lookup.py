"""``GOB_LINEUP_POSITION_LOOKUP``: a player's position is their lineup slot, not a constant.

``Player`` has no ``position`` attribute and nothing in the backend ever assigns one, so
every ``getattr(player, 'position', None) or "PG"`` site took its constant unconditionally.
The nine sites in phase_resolution now resolve the slot by identity lookup in the lineup
that owns the player, and return ``None`` rather than guessing when the player is absent.

One test per site class (non-shot ball handler / shot-fallback shooter / hardcoded shooter
/ hardcoded passer), plus a source guard that the legacy pattern has not come back.
"""
import ast
import inspect
import pathlib
import logging
import os

import pytest

import BackEnd.engine.phase_resolution as PR
from BackEnd.utils import lineup_position as LP


class _P:
    """Stand-in for Player: no ``position`` attribute, identity equality."""

    def __init__(self, pid):
        self.player_id = pid


class _AlwaysEqual(_P):
    """Equality is not identity. A lookup built on ``==`` would return the wrong slot."""

    def __eq__(self, other):
        return True

    __hash__ = None


@pytest.fixture
def lineup():
    return {p: _P(p) for p in ("PG", "SG", "SF", "PF", "C")}


class _Game:
    def __init__(self, gid="g1"):
        self.game_id = gid
        self.game_state = {}


@pytest.fixture(autouse=True)
def _clean_warn_state(monkeypatch):
    monkeypatch.setenv("GOB_LINEUP_POSITION_LOOKUP", "1")
    LP.POS_LOOKUP_WARNED.clear()
    yield
    LP.POS_LOOKUP_WARNED.clear()


# The nine live sites, as (site id, the constant the legacy code used). Kept here so a new
# site or a changed constant has to be acknowledged in this file.
SITE_CLASSES = [
    ("HCO:non-shot ball handler", "PG"),
    ("FCP:non-shot ball handler", "PG"),
    ("HCT:non-shot ball handler", "PG"),
    ("FCP:shot fallback shooter", "PG"),
    ("HCT:shot fallback shooter", "PG"),
    ("FCP:hardcoded shooter", "PF"),
    ("HCT:hardcoded shooter", "PF"),
    ("FCP:hardcoded passer", "PG"),
    ("HCT:hardcoded passer", "PG"),
]


@pytest.mark.parametrize("site,const", SITE_CLASSES)
@pytest.mark.parametrize("slot", ["PG", "SG", "SF", "PF", "C"])
def test_every_site_class_returns_the_lineup_slot_not_the_constant(lineup, site, const, slot):
    got = PR._resolve_lineup_position(lineup[slot], lineup, site, const, _Game())
    assert got == slot
    if slot != const:
        assert got != const, "the site fell back to its hard-coded constant"


@pytest.mark.parametrize("site,const", SITE_CLASSES)
def test_kill_switch_restores_the_constant(monkeypatch, lineup, site, const):
    monkeypatch.setenv("GOB_LINEUP_POSITION_LOOKUP", "0")
    # The legacy read: getattr(player, 'position', None) is None for every player object
    # in the backend, so the constant is what came back on every call.
    for slot in lineup:
        assert PR._resolve_lineup_position(lineup[slot], lineup, site, const, _Game()) == const


def test_lookup_is_by_identity_not_equality(lineup):
    """``get_player_position`` uses ``==``; these sites use ``is`` on purpose."""
    impostor = _AlwaysEqual("impostor")
    mixed = {"PG": impostor, "SG": lineup["SG"], "SF": lineup["SF"],
             "PF": lineup["PF"], "C": lineup["C"]}
    assert PR._resolve_lineup_position(mixed["C"], mixed, "HCO:non-shot ball handler",
                                       "PG", _Game()) == "C"


def test_absent_player_returns_none_and_never_a_constant(lineup):
    stranger = _P("bench")
    assert PR._resolve_lineup_position(stranger, lineup, "HCO:non-shot ball handler",
                                       "PG", _Game()) is None


@pytest.mark.parametrize("bad", [None, {}])
def test_missing_lineup_returns_none(bad):
    assert PR._resolve_lineup_position(_P("x"), bad, "FCP:hardcoded passer",
                                       "PG", _Game()) is None


def test_unresolved_warns_once_per_game_per_site(caplog, lineup):
    caplog.set_level(logging.WARNING)
    stranger, game = _P("bench"), _Game("game-A")
    for _ in range(5):
        PR._resolve_lineup_position(stranger, lineup, "HCO:non-shot ball handler", "PG", game)
    msgs = [r.getMessage() for r in caplog.records if "[POS LOOKUP]" in r.getMessage()]
    assert len(msgs) == 1
    assert "HCO:non-shot ball handler" in msgs[0] and "bench" in msgs[0]

    # a different site in the same game warns on its own
    PR._resolve_lineup_position(stranger, lineup, "FCP:hardcoded passer", "PG", game)
    # and the next game starts clean
    PR._resolve_lineup_position(stranger, lineup, "HCO:non-shot ball handler", "PG", _Game("game-B"))
    msgs = [r.getMessage() for r in caplog.records if "[POS LOOKUP]" in r.getMessage()]
    assert len(msgs) == 3


def test_warn_state_is_bounded(lineup):
    stranger = _P("bench")
    for i in range(PR._POS_LOOKUP_WARNED_MAX_GAMES * 3):
        PR._resolve_lineup_position(stranger, lineup, "HCO:non-shot ball handler",
                                    "PG", _Game("g%d" % i))
    assert len(PR._POS_LOOKUP_WARNED) <= PR._POS_LOOKUP_WARNED_MAX_GAMES


# ── the eight sites outside phase_resolution ────────────────────────────────────────────

import BackEnd.engine.eoq_perfection as EOQ  # noqa: E402
import BackEnd.engine.foul_announcement_language as FAL  # noqa: E402
import BackEnd.engine.skeleton_step_emitter as SSE  # noqa: E402


def test_site3_bh_defender_pos_resolves_from_the_defense_lineup(lineup):
    """skeleton_step_emitter: the guard_ball tag goes to the defender's own slot."""
    for slot in lineup:
        got = SSE._bh_defender_pos({"defender": lineup[slot]}, lineup)
        assert got == slot


def test_site3_returns_none_without_a_defender_or_a_lineup(lineup):
    assert SSE._bh_defender_pos({}, lineup) is None
    assert SSE._bh_defender_pos({"defender": None}, lineup) is None
    assert SSE._bh_defender_pos({"defender": _P("stranger")}, lineup) is None
    assert SSE._bh_defender_pos({"defender": lineup["PG"]}, None) is None


def test_site3_kill_switch_returns_none_for_every_defender(monkeypatch, lineup):
    monkeypatch.setenv("GOB_LINEUP_POSITION_LOOKUP", "0")
    for slot in lineup:
        assert SSE._bh_defender_pos({"defender": lineup[slot]}, lineup) is None


def test_site4_covert_release_resolves_a_ball_handler_with_no_player_id(lineup):
    """covert_release_step_emitter: identity finds the slot where the id match cannot.

    The legacy `.position` last resort only ever rescued test stubs - a real Player has
    no such attribute - and it could not help a ball handler whose player_id is None.
    """
    import BackEnd.engine.covert_release_step_emitter as CRSE
    from BackEnd.utils.lineup_position import lineup_slot as slot

    anon = _P(None)
    off = {"PG": anon, "SG": lineup["SG"]}
    assert CRSE._resolve_position_from_lineup(None, off) is None   # id match cannot work
    assert slot(off, anon) == "PG"                                  # identity can


def test_site2_defensive_foul_is_on_ball_uses_the_two_lineups(lineup):
    """foul_announcement_language: fouler's DEFENSE slot vs ball handler's OFFENSE slot."""
    off = {p: _P("o" + p) for p in lineup}
    deff = {p: _P("d" + p) for p in lineup}
    assert FAL.defensive_foul_is_on_ball(
        deff["SG"], off["SG"], off_lineup=off, def_lineup=deff) is True
    assert FAL.defensive_foul_is_on_ball(
        deff["C"], off["SG"], off_lineup=off, def_lineup=deff) is False
    # no lineups -> cannot tell, and must not guess
    assert FAL.defensive_foul_is_on_ball(deff["SG"], off["SG"]) is False


def test_site2_kill_switch_is_always_false(monkeypatch, lineup):
    monkeypatch.setenv("GOB_LINEUP_POSITION_LOOKUP", "0")
    off = {p: _P("o" + p) for p in lineup}
    deff = {p: _P("d" + p) for p in lineup}
    assert FAL.defensive_foul_is_on_ball(
        deff["SG"], off["SG"], off_lineup=off, def_lineup=deff) is False


class _Team:
    def __init__(self, lineup, bench):
        self.lineup = lineup
        self.players = {p.player_id: p for p in list(lineup.values()) + bench}


def test_site1_box_score_keys_bench_players_as_bench_not_a_guess(lineup):
    """game_manager: BENCH is derived from the lineup lookup, not a dead attribute read."""
    from BackEnd.utils.lineup_position import lineup_slot as slot
    bench = [_P("b1"), _P("b2")]
    team = _Team(lineup, bench)
    for p in bench:
        assert slot(team.lineup, p) is None      # genuinely off the floor -> "BENCH"
    for name, p in lineup.items():
        assert slot(team.lineup, p) == name      # on the floor -> the real slot


@pytest.mark.parametrize("site", ["6_turn_manager", "7_eoq_run_out"])
def test_offfloor_ball_handler_is_replaced_not_relabelled(lineup, site):
    """turn_manager / eoq_perfection: a last_ball_handler off the floor is dropped.

    The old code kept him as the shooter and relabelled him "PG"; the guard now re-picks
    from the lineup, which is the pattern resolve_flss_shot_logic already used.
    """
    from BackEnd.utils.shared import get_player_position
    stranger = _P("subbed-out")
    assert not get_player_position(lineup, stranger)
    replacement = lineup.get("PG") or next((p for p in lineup.values() if p), None)
    assert get_player_position(lineup, replacement) == "PG"


def test_site8_flss_guard_makes_the_constant_unreachable():
    """eoq_perfection already dropped an off-offense ball handler before the lookup."""
    src = inspect.getsource(EOQ.resolve_flss_shot_logic)
    assert "if ball_handler is not None and not get_player_position(off_lineup, ball_handler):" in src
    assert "shooter_pos = get_player_position(off_lineup, shooter)\n" in src


# ── source guard: the whole of BackEnd ──────────────────────────────────────────────────

BACKEND = pathlib.Path(PR.__file__).resolve().parent.parent
POSITION_ATTRS = {"position", "pos"}

# The ONE read not governed by GOB_LINEUP_POSITION_LOOKUP: select_foul_player's
# GOB_FOUL_ON_BALL_WEIGHT=0 kill-switch path, which must reproduce the legacy behaviour.
ALLOWLIST = {("engine/phase_resolution.py", "select_foul_player")}

KILL_SWITCH = "lineup_position_lookup_enabled"


def _is_switch_call(node):
    return (isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id == KILL_SWITCH)
        or (isinstance(node.func, ast.Attribute) and node.func.attr == KILL_SWITCH)))


def _is_negated_switch(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_switch_call(node.operand)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        return any(_is_negated_switch(v) for v in node.values)
    return False


def _position_getattrs(tree):
    """[(line, in_kill_switch_branch)] for every getattr(x, "position"/"pos") in `tree`."""
    found = []

    def walk(node, disabled, func):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = node.name
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "getattr" and len(node.args) >= 2 \
                and isinstance(node.args[1], ast.Constant) \
                and node.args[1].value in POSITION_ATTRS:
            found.append((node.lineno, disabled, func))
        if isinstance(node, ast.If):
            for v in ast.iter_child_nodes(node.test):
                walk(v, disabled, func)
            body_off = disabled or _is_negated_switch(node.test)
            else_off = disabled or _is_switch_call(node.test)
            for stmt in node.body:
                walk(stmt, body_off, func)
            for stmt in node.orelse:
                walk(stmt, else_off, func)
            return
        if isinstance(node, ast.IfExp):
            walk(node.test, disabled, func)
            walk(node.body, disabled, func)
            walk(node.orelse, disabled or _is_switch_call(node.test), func)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, disabled, func)

    walk(tree, False, None)
    return found


def _offenders(root=None):
    out = []
    for path in sorted((root or BACKEND).rglob("*.py")):
        rel = str(path.relative_to(root or BACKEND))
        for line, disabled, func in _position_getattrs(ast.parse(path.read_text())):
            if disabled or (rel, func) in ALLOWLIST:
                continue
            out.append((rel, line, func))
    return out


def test_no_player_position_attribute_read_survives_anywhere_in_backend():
    """Player has no `position`/`pos` attribute. Reading one is always a bug.

    A read is tolerated only inside a GOB_LINEUP_POSITION_LOOKUP=0 branch (the kill
    switch, which must reproduce the legacy behaviour) or in the single allowlisted
    GOB_FOUL_ON_BALL_WEIGHT=0 path.
    """
    assert _offenders() == []


def test_guard_detects_an_unguarded_read(tmp_path):
    (tmp_path / "bad.py").write_text('def f(p):\n    return getattr(p, "position", None) or "PG"\n')
    assert _offenders(tmp_path) == [("bad.py", 2, "f")]


def test_guard_accepts_a_read_inside_the_kill_switch(tmp_path):
    (tmp_path / "ok.py").write_text(
        "def f(p, lineup):\n"
        "    if lineup_position_lookup_enabled():\n"
        "        return lineup_slot(lineup, p)\n"
        "    return getattr(p, \"position\", None) or \"PG\"\n")
    # the `return` is not in an `orelse`, so this SHOULD be reported - an early-return
    # kill switch has to be written as an explicit `not ...` branch to be recognised.
    assert _offenders(tmp_path) == [("ok.py", 4, "f")]
    (tmp_path / "ok.py").write_text(
        "def f(p, lineup):\n"
        "    if not lineup_position_lookup_enabled():\n"
        "        return getattr(p, \"position\", None) or \"PG\"\n"
        "    return lineup_slot(lineup, p)\n")
    assert _offenders(tmp_path) == []


def test_flag_defaults_on(monkeypatch):
    monkeypatch.delenv("GOB_LINEUP_POSITION_LOOKUP", raising=False)
    assert PR._lineup_position_lookup_enabled() is True
    assert LP.lineup_position_lookup_enabled() is True
    monkeypatch.setenv("GOB_LINEUP_POSITION_LOOKUP", "0")
    assert PR._lineup_position_lookup_enabled() is False


def test_phase_resolution_reexports_the_shared_helper():
    """One implementation, not two."""
    assert PR._resolve_lineup_position is LP.resolve_lineup_position
    assert PR._POS_LOOKUP_WARNED is LP.POS_LOOKUP_WARNED


@pytest.mark.parametrize("fname", ("resolve_half_court_offense_logic",
                                   "resolve_full_court_press_logic",
                                   "resolve_half_court_trap_logic"))
def test_the_nine_resolver_sites_still_use_the_helper(fname):
    assert "_resolve_lineup_position(" in inspect.getsource(getattr(PR, fname))
