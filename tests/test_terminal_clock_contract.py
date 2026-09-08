"""Guard: a turn that ends its period reports ONE clock through FIVE fields.

THE DEFECT THIS EXISTS TO PREVENT (measured 2026-09-08, bugs.md item 10)
-----------------------------------------------------------------------
A turn carries a single fact — "how much clock is left after me" — spread across
``clock_start``, ``time_elapsed``, ``clock_end``, ``time_remaining`` and ``clock``.
Both quarter-end authors set ``clock_end = 0`` and left ``time_remaining`` and
``clock`` holding their pre-turn values. Nothing objected, because every field was
individually plausible and no test looks at more than one at a time.

The renderer then picked the stale one. ``gameScene.js:2671-2677`` resolves the game
clock as ``time_remaining`` -> ``clock``/``game_clock`` -> ``clock_end``, so it read
the pre-turn value and displayed 0:01 at the buzzer while the authoritative clock was
0. 8 of 32 measured quarter boundaries ended showing time that did not exist.

This is the clock dimension of the same class as the pos_action coordinate contract
and the free-throw count contract: one fact, several fields, and a consumer free to
pick a stale one. The structural answer is the same — a single author, and a guard
that fails the build when a second one appears.

WHAT IS GUARDED
---------------
A. Declaring a turn terminal (``["clock_end"] = 0``) happens in exactly ONE function.
   A new site is the defect reappearing, and it is caught statically.
B. That function writes EVERY field it claims to own. Deleting one is caught.
C. Both public terminal authors emit a mutually consistent field-set, checked by
   running them.
D. The consistency predicate is not vacuous — it is shown rejecting each field in turn.

NOT GUARDED, DELIBERATELY: the mid-quarter case. ``time_remaining`` disagrees with
``clock_end`` on 497 of 2,864 non-boundary turns (17.4%), which is larger than what
is fixed here and invisible only because the next turn overwrites it. That is its own
item in bugs.md and its own increment; widening this guard would fail the tree today.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from BackEnd.utils.eoq_clock_progression import (
    ensure_quarter_end_clock_drain,
    normalize_quarter_end_after_clock_update,
    stamp_terminal_clock,
)

_REPO = pathlib.Path(__file__).resolve().parents[1]

_AUTHOR_FILE = "BackEnd/utils/eoq_clock_progression.py"
_AUTHOR_FUNC = "stamp_terminal_clock"

# Fields stamp_terminal_clock owns. `clock_start` / `time_elapsed` are excluded on
# purpose: they describe HOW the turn resolved and each caller owns them.
_OWNED_FIELDS = ("clock_end", "time_remaining", "clock")

# Exact, so a new terminal author trips this rather than sliding in. Raise it only
# together with an entry in _ALLOWED_ZERO_WRITERS and a reason.
_EXPECTED_ZERO_WRITE_COUNT = 1

_ALLOWED_ZERO_WRITERS = {
    (_AUTHOR_FILE, _AUTHOR_FUNC): "the single terminal clock author; the whole point of the contract",
}

# The renderer's resolution order, pinned so the reason this matters stays visible.
_FE_PRECEDENCE = ("time_remaining", "clock", "clock_end")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _backend_files() -> list[str]:
    return sorted(
        p.relative_to(_REPO).as_posix()
        for p in (_REPO / "BackEnd").rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _enclosing_function(tree: ast.Module, lineno: int) -> str:
    best, best_start = "<module>", -1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= getattr(node, "end_lineno", node.lineno):
                if node.lineno > best_start:
                    best, best_start = node.name, node.lineno
    return best


def _terminal_zero_writes() -> list[tuple[str, int, str]]:
    """Every ``<expr>["clock_end"] = 0`` in BackEnd/ — i.e. every declaration of terminal.

    Only the literal zero counts. ``_attach_clock_contract`` assigns a computed
    ``clock_end`` on every turn; that is the general clock contract, not a terminal
    declaration, and it is not this guard's business.
    """
    out: list[tuple[str, int, str]] = []
    for rel in _backend_files():
        try:
            tree = ast.parse((_REPO / rel).read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not (isinstance(node.value, ast.Constant) and node.value.value == 0):
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "clock_end"
                ):
                    out.append((rel, node.lineno, _enclosing_function(tree, node.lineno)))
    return out


def _fields_written_by(rel: str, func: str) -> set[str]:
    """String subscript keys assigned inside a named function."""
    tree = ast.parse((_REPO / rel).read_text())
    written: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != func:
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Assign):
                continue
            for target in sub.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and isinstance(target.slice.value, str)
                ):
                    written.add(target.slice.value)
    return written


def _clock_to_seconds(text: str) -> int:
    minutes, seconds = str(text).split(":")
    return int(minutes) * 60 + int(seconds)


def terminal_clock_inconsistencies(turn: dict) -> list[str]:
    """Every way `turn` fails the terminal clock contract. Empty list == consistent.

    Fields absent from the turn are not invented; only what is present is checked,
    because not every terminal author owns clock_start/time_elapsed.
    """
    problems: list[str] = []
    end = turn.get("clock_end")
    if end != 0:
        problems.append(f"clock_end is {end!r}, a terminal turn ends at 0")
        return problems

    remaining = turn.get("time_remaining")
    if remaining is not None and int(remaining) != end:
        problems.append(
            f"time_remaining={remaining!r} disagrees with clock_end={end!r} "
            f"(the renderer reads time_remaining FIRST, so this is the field it shows)"
        )

    for key in ("clock", "game_clock"):
        shown = turn.get(key)
        if shown is None:
            continue
        try:
            value = _clock_to_seconds(shown)
        except (ValueError, AttributeError):
            problems.append(f"{key}={shown!r} is not a M:SS clock string")
            continue
        if value != end:
            problems.append(f"{key}={shown!r} disagrees with clock_end={end!r}")

    start, elapsed = turn.get("clock_start"), turn.get("time_elapsed")
    if isinstance(start, (int, float)) and isinstance(elapsed, (int, float)):
        if int(elapsed) != int(start) - int(end):
            problems.append(
                f"time_elapsed={elapsed!r} != clock_start={start!r} - clock_end={end!r}"
            )
    return problems


class _StubGame:
    def __init__(self, time_remaining: int):
        self.game_state = {"time_remaining": time_remaining}


# --------------------------------------------------------------------------- #
# A. terminal is declared in exactly one place
# --------------------------------------------------------------------------- #
def test_terminal_clock_is_authored_in_exactly_one_function():
    writes = _terminal_zero_writes()
    offenders = [w for w in writes if (w[0], w[2]) not in _ALLOWED_ZERO_WRITERS]
    assert not offenders, (
        "A new site declares a turn terminal by writing clock_end = 0 directly:\n"
        + "\n".join(f"  {rel}:{line} in {func}()" for rel, line, func in offenders)
        + f"\n\nCall {_AUTHOR_FUNC}() instead. Writing clock_end alone is exactly the "
        "defect this guard exists for: the renderer reads time_remaining first and "
        "will show the stale pre-turn clock at the buzzer."
    )


def test_terminal_write_count_is_exact():
    """Anti-rot. A bare allowlist rots; a count makes any new author visible."""
    writes = _terminal_zero_writes()
    assert len(writes) == _EXPECTED_ZERO_WRITE_COUNT, (
        f"expected exactly {_EXPECTED_ZERO_WRITE_COUNT} terminal clock declaration, "
        f"found {len(writes)}: {writes}. If this is intended, update "
        "_EXPECTED_ZERO_WRITE_COUNT and _ALLOWED_ZERO_WRITERS together, with a reason."
    )


def test_guard_is_not_vacuous():
    """The detector must actually see the real author, or it guards nothing."""
    writes = _terminal_zero_writes()
    assert (_AUTHOR_FILE, _AUTHOR_FUNC) in {(rel, func) for rel, _, func in writes}, (
        f"the detector cannot find the known clock_end = 0 write in "
        f"{_AUTHOR_FILE}::{_AUTHOR_FUNC}. The AST match is broken and every other "
        "test in section A is passing for free."
    )


# --------------------------------------------------------------------------- #
# B. the author writes every field it owns
# --------------------------------------------------------------------------- #
def test_author_writes_every_field_it_owns():
    written = _fields_written_by(_AUTHOR_FILE, _AUTHOR_FUNC)
    missing = [f for f in _OWNED_FIELDS if f not in written]
    assert not missing, (
        f"{_AUTHOR_FUNC}() no longer writes {missing}. Dropping a field re-creates the "
        "original defect: the remaining fields stay plausible and the renderer picks "
        "whichever one is stale."
    )


def test_renderer_precedence_is_covered_by_the_author():
    """Whatever the FE reads first must be a field we author. That is the whole bug."""
    written = _fields_written_by(_AUTHOR_FILE, _AUTHOR_FUNC)
    assert _FE_PRECEDENCE[0] in written, (
        f"the renderer resolves the clock as {' -> '.join(_FE_PRECEDENCE)} "
        f"(gameScene.js:2671-2677) but {_AUTHOR_FUNC}() does not write "
        f"{_FE_PRECEDENCE[0]!r}, so the value on screen is not the value we set."
    )


# --------------------------------------------------------------------------- #
# C. both public authors emit a consistent set, checked by running them
# --------------------------------------------------------------------------- #
def test_stamp_terminal_clock_is_self_consistent():
    turn = {"clock_start": 7, "time_elapsed": 7, "time_remaining": 7, "clock": "0:07"}
    stamp_terminal_clock(turn)
    assert terminal_clock_inconsistencies(turn) == []


def test_drain_emits_a_consistent_terminal_clock():
    """The pre-fix payload: clock_end 0 with time_remaining and clock left at 2."""
    turn = {
        "result_type": "PUTBACK_MISS",
        "next_play_type": None,
        "next_turn": None,
        "time_remaining": 2,
        "clock": "0:02",
    }
    ensure_quarter_end_clock_drain(_StubGame(2), turn)
    assert turn["quarter_ends_after"] is True
    assert terminal_clock_inconsistencies(turn) == []
    assert turn["time_elapsed"] == 2 and turn["clock_start"] == 2


def test_drain_is_consistent_when_the_clock_is_already_zero():
    turn = {
        "result_type": "MISS",
        "next_play_type": None,
        "next_turn": None,
        "time_remaining": 0,
        "clock": "0:00",
    }
    ensure_quarter_end_clock_drain(_StubGame(0), turn)
    assert terminal_clock_inconsistencies(turn) == []


def test_drain_leaves_non_terminal_turns_alone():
    """Scope: this contract applies to terminal turns only, not the general path."""
    turn = {"result_type": "MISS", "next_play_type": "HCO", "time_remaining": 300, "clock": "5:00"}
    ensure_quarter_end_clock_drain(_StubGame(300), turn)
    assert turn == {
        "result_type": "MISS",
        "next_play_type": "HCO",
        "time_remaining": 300,
        "clock": "5:00",
    }


def test_normalize_emits_a_consistent_terminal_clock():
    """The exact measured case: a DREB that burned its last second.

    Pre-fix this produced clock_end=0 with time_remaining=1 and clock='0:01',
    and the renderer showed 0:01 at the buzzer.
    """
    turn = {
        "result_type": "DREB",
        "next_play_type": "HCO",
        "next_turn": "HCO",
        "clock_start": 1,
        "time_elapsed": 1,
        "time_remaining": 1,
        "clock": "0:01",
    }
    normalize_quarter_end_after_clock_update(_StubGame(0), turn)
    assert turn["quarter_ends_after"] is True
    assert turn["next_play_type"] is None
    assert terminal_clock_inconsistencies(turn) == []


def test_normalize_still_defers_to_pending_free_throws():
    """The documented exception survives: FTs finish at 0:00 before the quarter ends."""
    turn = {"result_type": "FOUL", "next_play_type": "FREE_THROW", "time_remaining": 3, "clock": "0:03"}
    normalize_quarter_end_after_clock_update(_StubGame(0), turn)
    assert "quarter_ends_after" not in turn
    assert turn["next_play_type"] == "FREE_THROW"


def test_normalize_returns_early_while_the_clock_still_runs():
    """The `time_remaining > 0` guard is correct and stays. Pinned so nobody 'fixes' it."""
    turn = {"result_type": "DREB", "next_play_type": "HCO", "time_remaining": 12, "clock": "0:12"}
    normalize_quarter_end_after_clock_update(_StubGame(12), turn)
    assert "quarter_ends_after" not in turn, (
        "normalize must not declare a quarter over while the clock still has time. "
        "Inverting this guard would strip continuations from every mid-quarter turn."
    )


# --------------------------------------------------------------------------- #
# D. the predicate rejects each field in turn (anti-vacuity)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "field, value",
    [
        ("clock_end", 1),
        ("time_remaining", 1),
        ("clock", "0:01"),
        ("game_clock", "0:01"),
        ("time_elapsed", 99),
    ],
)
def test_predicate_catches_a_single_disagreeing_field(field, value):
    """One field out of step must be enough to fail. That was the whole defect."""
    turn = {
        "clock_start": 1,
        "time_elapsed": 1,
        "clock_end": 0,
        "time_remaining": 0,
        "clock": "0:00",
        "game_clock": "0:00",
    }
    assert terminal_clock_inconsistencies(turn) == [], "baseline must be consistent"
    turn[field] = value
    assert terminal_clock_inconsistencies(turn), (
        f"a terminal turn with {field}={value!r} was accepted as consistent; "
        "the predicate is not actually comparing that field"
    )
