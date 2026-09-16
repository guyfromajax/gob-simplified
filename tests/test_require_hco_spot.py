"""Centre-court fallbacks raise instead of inventing (bugs.md item 26 / Phase 4)."""

import ast
from pathlib import Path

import pytest

from BackEnd.constants import require_hco_spot

_BACKEND = Path(__file__).resolve().parents[1] / "BackEnd"


def test_require_hco_spot_returns_named_spot():
    assert require_hco_spot("key") == {"x": 64.0, "y": 25.0}
    assert require_hco_spot("center court") == {"x": 50.0, "y": 25.0}


def test_require_hco_spot_raises_on_unknown_name():
    with pytest.raises(KeyError, match="NOT_A_REAL_SPOT"):
        require_hco_spot("NOT_A_REAL_SPOT")
    with pytest.raises(KeyError):
        require_hco_spot(None)


def _is_centre_court_dict(node):
    if not isinstance(node, ast.Dict):
        return False
    keys = []
    for k in node.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.append(k.value)
        else:
            return False
    if set(keys) != {"x", "y"}:
        return False
    vals = {}
    for k, v in zip(node.keys, node.values):
        if not isinstance(v, ast.Constant) or not isinstance(v.value, (int, float)):
            return False
        vals[k.value] = float(v.value)
    return vals == {"x": 50.0, "y": 25.0}


def test_hco_string_spots_get_never_defaults_to_centre_court():
    """Poison: reinstating HCO_STRING_SPOTS.get(name, {50,25}) fails here."""
    offenders = []
    for path in _BACKEND.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        if "HCO_STRING_SPOTS.get" not in src:
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or len(node.args) < 2:
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Name)
                and func.value.id == "HCO_STRING_SPOTS"
            ):
                continue
            if _is_centre_court_dict(node.args[1]):
                offenders.append("%s:%d" % (path.relative_to(_BACKEND.parent), node.lineno))
    assert not offenders, "centre-court HCO_STRING_SPOTS.get defaults: %s" % offenders
