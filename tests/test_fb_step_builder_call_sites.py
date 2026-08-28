"""Guard: every FB step-builder call site must bind against its signature.

Motivated by a production TypeError (Sentry PYTHON-FASTAPI-9M): a required
keyword-only `previous_step` was added to `_build_outlet_denied_defender_step`
and only the Rim Runner call site was updated. `triangle_step_emitter` calls the
same builder, so every DEFENSIVE_STOP Triangle with a denied outlet raised
TypeError — swallowed by the emitter's try/except, silently degrading the turn to
legacy rendering and cold-starting the following HCO turn (a visible teleport).

These builders are shared across emitters and called only on rare branches, so a
signature change can pass every test and still break in production. This test
binds each call site statically instead of waiting to execute the branch.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]

# Builders defined in rim_runner_step_emitter and reused by other FB emitters.
_SHARED_BUILDERS = (
    "_build_outlet_denied_defender_step",
    "_build_lane_pass_intercepted_step",
    "_build_lane_pass_batted_step",
    "_build_shot_motion_step",
    "_build_hold_up_step",
    "_initialize_continuing_movement",
)

_EMITTERS = (
    "BackEnd/engine/rim_runner_step_emitter.py",
    "BackEnd/engine/triangle_step_emitter.py",
    "BackEnd/engine/covert_release_step_emitter.py",
)


def _signatures():
    mod = importlib.import_module("BackEnd.engine.rim_runner_step_emitter")
    return {
        name: inspect.signature(getattr(mod, name))
        for name in _SHARED_BUILDERS
        if hasattr(mod, name)
    }


def _call_sites():
    for rel in _EMITTERS:
        path = _REPO / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None)
            if name in _SHARED_BUILDERS:
                kwargs = {kw.arg for kw in node.keywords if kw.arg}
                yield rel, node.lineno, name, kwargs


def test_every_shared_builder_call_site_binds():
    sigs = _signatures()
    failures = []

    for rel, lineno, name, kwargs in _call_sites():
        sig = sigs.get(name)
        if sig is None:
            continue

        required = {
            p.name
            for p in sig.parameters.values()
            if p.kind is p.KEYWORD_ONLY and p.default is p.empty
        }
        missing = sorted(required - kwargs)
        if missing:
            failures.append(f"{rel}:{lineno} {name}() missing {missing}")
            continue

        unknown = sorted(
            kwargs - {p.name for p in sig.parameters.values()}
        )
        if unknown:
            failures.append(f"{rel}:{lineno} {name}() unexpected {unknown}")

    assert not failures, "FB step-builder call sites do not bind:\n  " + "\n  ".join(failures)


def test_shared_builders_are_actually_called_cross_module():
    """Sanity: if nothing calls these across modules the test above is vacuous."""
    cross = {
        (rel, name)
        for rel, _lineno, name, _kw in _call_sites()
        if not rel.endswith("rim_runner_step_emitter.py")
    }
    assert cross, "expected at least one cross-module call site to guard"


@pytest.mark.parametrize("name", ["_build_outlet_denied_defender_step"])
def test_cross_module_builders_tolerate_missing_previous_step(name):
    """A caller that cannot supply `previous_step` must degrade, not raise.

    This is the exact production failure: the argument was required, the Triangle
    caller did not pass it, and the whole turn fell back to legacy rendering.
    """
    sig = _signatures()[name]
    param = sig.parameters.get("previous_step")
    assert param is not None, f"{name} lost its previous_step parameter"
    assert param.default is not inspect.Parameter.empty, (
        f"{name}(previous_step=...) must have a default. Making it required "
        "breaks cross-module callers at runtime on a rare branch, where the "
        "emitter's try/except hides it as a silent legacy fallback."
    )
