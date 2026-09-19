"""The crash-destination model must never be able to see the shot's outcome.

``bounce_spot`` is computed at ``shot_manager.py:2465``, eighty-five lines before the
HCO crash destinations are authored at ``:2550``, and ``result["ball_bounce_x"]`` is
already populated by then. Nothing structural stops someone passing it in, and a
crasher who knows where the ball lands makes rebounding a deterministic race.

So the guard is on the SIGNATURE: this test fails if ``crash_destination`` grows a
parameter that could carry the outcome. It is deliberately annoying to work around.
"""

import inspect

import pytest

from BackEnd.utils import crash_destination as CD

#: Everything the model is allowed to know: the shot, and how tightly to hedge.
ALLOWED_PARAMS = {"shooter_x", "shooter_y", "rim_x", "shot_type", "tightness"}

#: Anything whose presence would mean the outcome reached the model.
FORBIDDEN_SUBSTRINGS = (
    "bounce", "result", "made", "miss", "outcome", "foul", "frame",
    "locals", "rebounder", "winner", "game",
)


def test_signature_carries_only_the_shot():
    params = inspect.signature(CD.crash_destination).parameters
    names = set(params) - {"self"}

    unexpected = names - ALLOWED_PARAMS
    assert not unexpected, (
        f"crash_destination grew parameter(s) {sorted(unexpected)}. Only the SHOT may "
        f"reach this model ({sorted(ALLOWED_PARAMS)}). If the new input genuinely "
        f"describes the shot rather than its outcome, add it to ALLOWED_PARAMS "
        f"deliberately and say why in the module docstring."
    )

    for name in names:
        low = name.lower()
        for bad in FORBIDDEN_SUBSTRINGS:
            assert bad not in low, (
                f"crash_destination parameter {name!r} looks outcome-bearing "
                f"({bad!r}). A crasher must not know where the ball is going to land."
            )

    # Keyword-only, so nobody can smuggle an extra positional argument past the
    # allowlist by relying on parameter order.
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values()), (
        "crash_destination's parameters must stay keyword-only."
    )


def test_the_guard_rejects_an_outcome_bearing_signature():
    """Poison: the same check must fail on a signature that takes the bounce."""
    def crash_destination_poisoned(*, shooter_x, shooter_y, rim_x, bounce_spot):
        return {"x": 0, "y": 0}

    names = set(inspect.signature(crash_destination_poisoned).parameters)
    unexpected = names - ALLOWED_PARAMS
    assert unexpected == {"bounce_spot"}
    assert any(bad in "bounce_spot" for bad in FORBIDDEN_SUBSTRINGS)


def test_module_body_never_touches_the_bounce():
    """Scan executable code only - the docstrings deliberately NAME the thing they
    forbid, so a plain text search would flag its own warning."""
    import ast

    tree = ast.parse(inspect.getsource(CD))
    # Docstring nodes, by identity - get_docstring() returns a CLEANED string that no
    # longer equals the Constant's raw value, so they have to be excluded by node.
    doc_nodes = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(n, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_nodes.add(id(body[0].value))

    touched = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            touched.add(node.id)
        elif isinstance(node, ast.Attribute):
            touched.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in doc_nodes:
            touched.add(node.value)

    offenders = sorted(
        t for t in touched
        if isinstance(t, str) and ("ball_bounce" in t or t in {"bounce_spot", "result"})
    )
    assert not offenders, (
        f"crash_destination's code touches {offenders}. It must never read the "
        f"bounce or the result payload - that is the one thing this model cannot do."
    )
    # the shared helper it IS allowed to use
    assert "_bounce_variance_for_shot_distance" in touched


@pytest.mark.parametrize("rim_x", [91.0, 9.0])
@pytest.mark.parametrize("dist", [5.0, 14.0, 22.0, 33.0, 48.0])
def test_destinations_stay_on_the_court(rim_x, dist):
    shooter_x = rim_x - dist if rim_x > 50 else rim_x + dist
    for _ in range(200):
        d = CD.crash_destination(shooter_x=shooter_x, shooter_y=CD.RIM_Y, rim_x=rim_x,
                                 tightness=1.0)
        assert CD.COURT_X_MIN <= d["x"] <= CD.COURT_X_MAX
        assert CD.COURT_Y_MIN <= d["y"] <= CD.COURT_Y_MAX
        # and on the correct half - a crasher never ends up at the other basket
        assert (d["x"] > 50.0) == (rim_x > 50.0)


def test_two_draws_exactly():
    """Draw-neutrality: the model must cost the same two randints as the flat box."""
    from BackEnd.utils import sim_random

    box = getattr(sim_random.sim_rng, "_equiv_draws", None)
    if not box:
        pytest.skip("draw counter not installed outside the equiv harness")
    before = box[0]
    CD.crash_destination(shooter_x=73.0, shooter_y=10.0, rim_x=91.0, tightness=1.0)
    assert box[0] - before == 2


def test_tightness_pulls_crashers_toward_the_rim():
    rim_x = 91.0
    shooter_x = 91.0 - 33.0
    far = [CD.crash_destination(shooter_x=shooter_x, shooter_y=25.0, rim_x=rim_x,
                                tightness=1.0)["x"] for _ in range(400)]
    near = [CD.crash_destination(shooter_x=shooter_x, shooter_y=25.0, rim_x=rim_x,
                                 tightness=0.5)["x"] for _ in range(400)]
    # higher x == closer to the home rim
    assert sum(near) / len(near) > sum(far) / len(far)
