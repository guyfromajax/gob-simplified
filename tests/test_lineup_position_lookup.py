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
import textwrap
import logging
import os

import pytest

import BackEnd.engine.phase_resolution as PR


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
    PR._POS_LOOKUP_WARNED.clear()
    yield
    PR._POS_LOOKUP_WARNED.clear()


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


# ── source guard ────────────────────────────────────────────────────────────────────────

POSITIONS = {"PG", "SG", "SF", "PF", "C"}
GUARDED = ("resolve_half_court_offense_logic",
           "resolve_full_court_press_logic",
           "resolve_half_court_trap_logic")


def _constant_position_fallbacks(source):
    """``getattr(x, 'position', ...) or "<POSITION>"`` occurrences in a function body."""
    found = []
    for node in ast.walk(ast.parse(textwrap.dedent(source))):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        right = node.values[-1]
        if not (isinstance(right, ast.Constant) and right.value in POSITIONS):
            continue
        left = node.values[0]
        if (isinstance(left, ast.Call) and isinstance(left.func, ast.Name)
                and left.func.id == "getattr"
                and any(isinstance(a, ast.Constant) and a.value == "position"
                        for a in left.args)):
            found.append(right.value)
    return found


@pytest.mark.parametrize("fname", GUARDED)
def test_no_constant_position_fallback_remains(fname):
    src = inspect.getsource(getattr(PR, fname))
    assert _constant_position_fallbacks(src) == [], fname
    assert "_resolve_lineup_position(" in src, fname


def test_guard_detects_a_reinstated_constant_fallback():
    poisoned = 'def f(p):\n    pos = getattr(p, "position", None) or "PG"\n    return pos\n'
    assert _constant_position_fallbacks(poisoned) == ["PG"]


def test_flag_defaults_on(monkeypatch):
    monkeypatch.delenv("GOB_LINEUP_POSITION_LOOKUP", raising=False)
    assert PR._lineup_position_lookup_enabled() is True
    monkeypatch.setenv("GOB_LINEUP_POSITION_LOOKUP", "0")
    assert PR._lineup_position_lookup_enabled() is False
