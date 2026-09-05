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


def _signatures(module="BackEnd.engine.rim_runner_step_emitter", builders=_SHARED_BUILDERS):
    mod = importlib.import_module(module)
    return {
        name: inspect.signature(getattr(mod, name))
        for name in builders
        if hasattr(mod, name)
    }


def _call_sites(files=_EMITTERS, builders=_SHARED_BUILDERS):
    for rel in files:
        path = _REPO / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None)
            if name in builders:
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


# ---------------------------------------------------------------------------
# Second family: the universal pass builder.
#
# `build_pass_step` lives in transition_bridge and is called from four modules.
# Its `continuing_targets` parameter decides whether the other eight players
# keep moving or stand still, and it is the single highest-leverage knob in the
# animation cleanup (see projects/animation_cleanup_findings.md §2). Any change
# to its signature has exactly the cross-module blast radius that produced the
# §17 production failure guarded above.
# ---------------------------------------------------------------------------

_PASS_BUILDER_MODULE = "BackEnd.utils.transition_bridge"
_PASS_BUILDERS = ("build_pass_step",)

_PASS_CALLERS = (
    "BackEnd/utils/transition_bridge.py",
    "BackEnd/engine/after_steal_fast_break_step_emitter.py",
    "BackEnd/engine/dynamic_hct_step_emitter.py",
    "BackEnd/engine/fb_drive_step_emitter.py",
)


def _pass_signatures():
    return _signatures(_PASS_BUILDER_MODULE, _PASS_BUILDERS)


def _pass_call_sites():
    return _call_sites(_PASS_CALLERS, _PASS_BUILDERS)


def test_every_pass_builder_call_site_binds():
    sigs = _pass_signatures()
    failures = []

    for rel, lineno, name, kwargs in _pass_call_sites():
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

        unknown = sorted(kwargs - {p.name for p in sig.parameters.values()})
        if unknown:
            failures.append(f"{rel}:{lineno} {name}() unexpected {unknown}")

    assert not failures, "pass-builder call sites do not bind:\n  " + "\n  ".join(failures)


def test_pass_builder_is_called_cross_module():
    """Sanity: the binding test above is only meaningful if callers exist elsewhere."""
    cross = {
        (rel, name)
        for rel, _lineno, name, _kw in _pass_call_sites()
        if not rel.endswith("transition_bridge.py")
    }
    assert cross, "expected at least one cross-module build_pass_step call site to guard"


def test_pass_builder_previous_step_is_optional():
    """`previous_step` must exist and must have a default.

    Deriving continuing movement requires knowing where each player was still
    heading, which lives on the prior step. But making the parameter REQUIRED is
    the exact §17 defect: a caller that cannot supply it raises TypeError on a
    rare branch, the emitter's try/except swallows it, and the turn silently
    degrades to legacy rendering.
    """
    sig = _pass_signatures()["build_pass_step"]
    param = sig.parameters.get("previous_step")
    assert param is not None, (
        "build_pass_step lost its previous_step parameter; continuing movement "
        "cannot be derived without the prior step's start.destination"
    )
    assert param.default is not inspect.Parameter.empty, (
        "build_pass_step(previous_step=...) must have a default so a caller "
        "that cannot supply one degrades to a freeze instead of raising."
    )


def test_freezing_everyone_must_be_explicit():
    """The default must NOT be the freeze.

    Root cause #1 of the animation cleanup: `continuing_targets=None` froze
    everyone but passer and receiver, and most builders never opted in — so the
    default silently decided. Callers that genuinely want a freeze pass None
    explicitly and keep it; callers that never decided must get movement.
    """
    sig = _pass_signatures()["build_pass_step"]
    default = sig.parameters["continuing_targets"].default
    assert default is not None, (
        "build_pass_step(continuing_targets=None) as the DEFAULT means every "
        "call site that omits the argument freezes eight players without anyone "
        "choosing that. Use a sentinel default meaning 'derive from previous_step' "
        "and keep an explicit None as the opt-in freeze."
    )
