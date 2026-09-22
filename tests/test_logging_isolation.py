"""No test module may reconfigure logging for the whole process.

`logging.disable(level)` is a process-wide switch with no owner. Four test modules
called it at MODULE scope and never restored it, so once pytest imported them during
COLLECTION every later test in the run lost its log records. Six UESS seam guards
(test_unrendered_and_ball_seam, test_sa1_within_step_pass) assert on `caplog.text`;
they passed alone and failed in a full run, and were the last uncovered reds in
reports/test-triage-2026-09-19.md. See reports/test-uncovered-2026-09-20.md.

The fix is a scoped autouse fixture that restores the previous value. This guard keeps
the module-scope form from coming back.
"""
import ast
import pathlib

import pytest

TESTS = pathlib.Path(__file__).resolve().parent

#: Calls that change logging for every logger in the process.
GLOBAL_LOGGING_CALLS = {
    ("logging", "disable"),
    ("logging", "basicConfig"),
    ("logging", "shutdown"),
    ("logging.config", "dictConfig"),
    ("logging.config", "fileConfig"),
}


def _dotted(node):
    """`logging.config.dictConfig` -> ('logging.config', 'dictConfig')."""
    if not isinstance(node, ast.Attribute):
        return None
    parts = [node.attr]
    cur = node.value
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    parts.reverse()
    return ".".join(parts[:-1]), parts[-1]


def module_scope_offenders(tree):
    """Global logging calls reachable at import time (module body, incl. if/try/with)."""
    found = []

    def walk(node):
        for child in ast.iter_child_nodes(node):
            # a function or class body only runs when called, so it is not import-time
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Call):
                target = _dotted(child.func)
                if target in GLOBAL_LOGGING_CALLS:
                    found.append((child.lineno, "%s.%s" % target))
            walk(child)

    walk(tree)
    return found


def _test_modules():
    return sorted(p for p in TESTS.rglob("test_*.py") if "e2e" not in p.parts)


def test_no_test_module_reconfigures_logging_at_import():
    offenders = []
    for path in _test_modules():
        for lineno, call in module_scope_offenders(ast.parse(path.read_text())):
            offenders.append("%s:%d %s()" % (path.relative_to(TESTS.parent), lineno, call))
    assert offenders == [], (
        "these run at import and leak into every later test; use an autouse fixture "
        "that restores the previous value instead:\n  " + "\n  ".join(offenders)
    )


def test_guard_detects_the_module_scope_form(tmp_path):
    """Poison: the exact line that caused the six seam failures."""
    p = tmp_path / "test_poison.py"
    p.write_text("import logging\nlogging.disable(logging.CRITICAL)\n\ndef test_x():\n    pass\n")
    assert module_scope_offenders(ast.parse(p.read_text())) == [(2, "logging.disable")]


def test_guard_detects_it_inside_a_try_block(tmp_path):
    p = tmp_path / "test_poison2.py"
    p.write_text("import logging\ntry:\n    logging.basicConfig(level=0)\nexcept Exception:\n    pass\n")
    assert module_scope_offenders(ast.parse(p.read_text())) == [(3, "logging.basicConfig")]


def test_guard_allows_the_scoped_fixture_form(tmp_path):
    p = tmp_path / "test_ok.py"
    p.write_text(
        "import logging\nimport pytest\n\n\n"
        "@pytest.fixture(autouse=True)\ndef quiet():\n"
        "    previous = logging.root.manager.disable\n"
        "    logging.disable(logging.CRITICAL)\n"
        "    try:\n        yield\n    finally:\n        logging.disable(previous)\n"
    )
    assert module_scope_offenders(ast.parse(p.read_text())) == []


# ── the fixture actually restores ───────────────────────────────────────────────────────

def test_caplog_still_works_after_the_quiet_fixture_has_run(caplog):
    """Ordering-independent proof: a module that quiets logs must not leak the silence."""
    import logging as _logging

    from tests import test_in_season_invariants as victim  # imports cleanly, quiets nothing

    assert _logging.root.manager.disable == 0, (
        "importing a quieting test module left logging globally disabled at level "
        f"{_logging.root.manager.disable}"
    )
    _logging.warning("caplog is alive")
    assert "caplog is alive" in caplog.text
    assert victim is not None
