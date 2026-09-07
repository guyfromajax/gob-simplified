"""Guard: a pos_action's position-key vocabulary is coords / location / spot.

WHY THIS EXISTS
---------------
`build_all_animations` decided which key to read off a `pos_action` and tested
only "coords" then "location", falling through to a hardcoded
``{"x": 50, "y": 25}``. The skeletons author the spot name under "spot" a
quarter of the time. Measured over 12 seeded games (192,393 offense pos_actions):

    ELSE_NOTHING_AUTHORED        0
    LOCATION_MISS                0
    ELSE_SPOT_IGNORED      123,890   (100% of the fallthrough)

Every fallthrough was a `spot` the converter refused to read, and every one put
a player on the centre logo: 644.5 five-player stacks per game in the schema
render path, 4,787.6 exact-logo coord instances per game. Two years unnoticed,
because the converter answered instead of failing.

Eleven readers in that same module already wrote
``x.get("location") or x.get("spot")``. The offense build was the ONLY site in
BackEnd/ that decided the key for itself, and the only one that did not speak
its own module's vocabulary. That asymmetry is what this guard pins.

TWO GUARDS
----------
**A. No location-only key dispatch.** Any expression testing membership of
"location" must test "spot" in the same expression. Scoped to all of BackEnd/,
because there is exactly ONE such expression in the tree — the registry below
pins that, so a second one anywhere fails whether or not it is compliant, and a
human has to look at it.

**B. The converter does not invent a position.** The key-dispatch fallthrough in
`build_all_animations` must raise rather than substitute a coordinate. The branch
is unreachable by construction: all 36 pos_action write sites in BackEnd/ emit
one of the three keys (`_pos_action_for_target` is total; the eoq dicts carry
both `location` and `coords`; the three remap sites are position-key passthroughs
or set `coords` on the line before the write), and all 1,800 statically authored
offense entries carry a name.

WHAT THIS GUARD DOES NOT COVER — read before trusting it
--------------------------------------------------------
This checks **membership dispatch**, because that is the shape the defect took
and the shape that is statically decidable. It does not check:

- **`.get("location")` reads.** There are hundreds, and the overwhelming
  majority read a dict the module built for itself, not a skeleton pos_action —
  attack_drive_clearance.py alone has 20 reads of its own
  ``{"location", "coords"}`` target dicts. Separating those requires taint
  tracking, which I tried: inside 700-line functions the closure taints
  everything and the guard flags 30+ non-violations. A guard that cries wolf gets
  deleted, which is strictly worse than a narrow one. Reviewing a new
  ``.get("location")`` belongs to review, not to this file.
- A key **laundered through a variable**: ``k = "location"`` then ``k in pa``.
- `HCO_STRING_SPOTS.get(name, {"x": 50, "y": 25})` — the *sibling* silent
  default at defender_placement.py:191,194. LOCATION_MISS measures 0, so it
  never fires today, but it is the same invent-an-answer shape and is queued
  separately rather than bundled into this increment.

The residual is accepted and deliberate.
"""
from __future__ import annotations

import ast
import os
import pathlib
import types
from unittest import mock

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]


def _fake_game():
    """Minimum a build needs: which side is on offense, and the zone-map attribute."""
    team = lambda tid: types.SimpleNamespace(team_id=tid)  # noqa: E731
    return types.SimpleNamespace(
        offense_team=team("home"),
        away_team=team("away"),
        home_team=team("home"),
        game_state={},
    )


def _fake_lineup():
    return {"PG": types.SimpleNamespace(player_id="pg-1", name="Test PG")}

# The two keys under which a skeleton may author a spot NAME. "coords" is the
# already-resolved form and is not a name.
_NAME_KEYS = ("location", "spot")

# ---------------------------------------------------------------------------
# Guard A registry: every expression in BackEnd/ that dispatches on membership
# of a name key, keyed by (file, enclosing function) -> (count, reason).
#
# Counts are exact ON PURPOSE, following test_uess_coord_contract.py: a second
# dispatch added INSIDE an already-registered function fails too, not just one
# in a new file. There is currently exactly one dispatch in the tree.
# ---------------------------------------------------------------------------
_MEMBERSHIP_SITES: dict[tuple[str, str], tuple[int, str]] = {
    ("BackEnd/engine/defender_placement.py", "build_all_animations"): (
        1,
        "CANONICAL. The offense key dispatch — coords, else location-or-spot, "
        "else raise. This is the site that carried the bug; it now speaks the "
        "same vocabulary as the eleven defender readers below it.",
    ),
}

# Sites that dispatch on "location" WITHOUT "spot" and are known-correct. Empty
# on purpose: there is no legitimate location-only dispatch. Adding one should
# require writing down why.
_LOCATION_ONLY_ALLOWLIST: dict[tuple[str, str], str] = {}

# Guard B target.
_CONVERTER_FILE = "BackEnd/engine/defender_placement.py"
_CONVERTER_FUNC = "build_all_animations"

# Anti-vacuity: the compliant `location or spot` readers the fix was modelled on.
_MUST_SEE_MIN_NAME_READS = 11


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _parse(rel: str) -> ast.Module:
    return ast.parse((_REPO / rel).read_text())


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


def _membership_keys(node: ast.AST) -> set[str]:
    """String keys this expression tests membership of (`"k" in x`)."""
    keys: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Compare):
            continue
        if not any(isinstance(op, (ast.In, ast.NotIn)) for op in sub.ops):
            continue
        if isinstance(sub.left, ast.Constant) and isinstance(sub.left.value, str):
            keys.add(sub.left.value)
    return keys


def _dispatch_sites() -> list[tuple[str, int, str, set[str]]]:
    """Every statement in BackEnd/ whose own test/value dispatches on a name key.

    Returns (file, lineno, function, keys tested). Judged per statement, so
    `elif "location" in pa or "spot" in pa:` is one compliant site.
    """
    out: list[tuple[str, int, str, set[str]]] = []
    for rel in _backend_files():
        try:
            tree = _parse(rel)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            parts: list[ast.AST] = []
            if isinstance(node, (ast.If, ast.While, ast.IfExp)):
                parts = [node.test]
            elif isinstance(node, (ast.Assign, ast.Return)) and node.value is not None:
                parts = [node.value]
            if not parts:
                continue
            keys: set[str] = set()
            for part in parts:
                keys |= _membership_keys(part)
            if keys & set(_NAME_KEYS):
                out.append((rel, node.lineno, _enclosing_function(tree, node.lineno), keys))
    return out


def _converter_function() -> ast.FunctionDef:
    for node in ast.walk(_parse(_CONVERTER_FILE)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == _CONVERTER_FUNC:
                return node
    raise AssertionError(f"{_CONVERTER_FUNC} not found in {_CONVERTER_FILE}")


def _all_keys_touched(node: ast.AST) -> set[str]:
    """Every string key tested for membership, .get() or subscripted."""
    keys = _membership_keys(node)
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr == "get" and sub.args:
                first = sub.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    keys.add(first.value)
        if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
            if isinstance(sub.slice.value, str):
                keys.add(sub.slice.value)
    return keys


# --------------------------------------------------------------------------- #
# Guard A
# --------------------------------------------------------------------------- #
def test_no_location_dispatch_without_spot():
    """Every membership dispatch on a spot name accepts both name keys."""
    offenders = []
    for rel, lineno, func, keys in _dispatch_sites():
        if "location" in keys and "spot" not in keys:
            if (rel, func) in _LOCATION_ONLY_ALLOWLIST:
                continue
            offenders.append(f"  {rel}:{lineno} in {func}() tests {sorted(keys)}")
    assert not offenders, (
        'pos_action key contract violated — these sites test membership of "location" '
        'without also accepting "spot":\n'
        + "\n".join(offenders)
        + "\n\nSkeletons author the spot name under EITHER key: 75% \"location\", 25% "
        '"spot" across the 1,800 statically authored offense pos_actions. A '
        "location-only dispatch silently drops the spot key — when "
        "build_all_animations did exactly this it sent 123,890 pos_actions per 12 "
        "games to the centre logo, undetected for two years.\n"
        'Fix: test `"location" in pa or "spot" in pa` and read '
        '`pa.get("location") or pa.get("spot") or "key"`, matching the eleven readers '
        "in defender_placement.py."
    )


def test_membership_registry_is_exact():
    """Anti-rot: exactly the registered dispatches exist, at the registered counts."""
    seen: dict[tuple[str, str], int] = {}
    for rel, _lineno, func, _keys in _dispatch_sites():
        seen[(rel, func)] = seen.get((rel, func), 0) + 1

    unregistered = sorted(set(seen) - set(_MEMBERSHIP_SITES))
    assert not unregistered, (
        "new name-key dispatch site(s) not in _MEMBERSHIP_SITES: "
        f"{unregistered}. A second converter is how one fix becomes two bugs — "
        "register it with a reason, or route it through the existing dispatch."
    )

    stale = sorted(set(_MEMBERSHIP_SITES) - set(seen))
    assert not stale, (
        f"_MEMBERSHIP_SITES has entries for dispatches that no longer exist: {stale}"
    )

    wrong = {
        key: (seen[key], expected)
        for key, (expected, _reason) in _MEMBERSHIP_SITES.items()
        if seen[key] != expected
    }
    assert not wrong, (
        "dispatch counts moved (site -> (found, registered)): "
        f"{wrong}. An extra dispatch inside an already-registered function is "
        "still a second place the vocabulary can drift."
    )


def test_guard_a_is_not_vacuous():
    """The detector sees the one real dispatch, and sees it as compliant."""
    sites = _dispatch_sites()
    assert sites, "detector found no name-key dispatch anywhere in BackEnd/ — it is blind"
    canonical = [
        (rel, lineno, keys)
        for rel, lineno, func, keys in sites
        if (rel, func) == (_CONVERTER_FILE, _CONVERTER_FUNC)
    ]
    assert canonical, (
        f"detector cannot see the dispatch in {_CONVERTER_FILE}::{_CONVERTER_FUNC} — "
        "Guard A proves nothing"
    )
    for rel, lineno, keys in canonical:
        assert set(_NAME_KEYS) <= keys, (
            f"{rel}:{lineno} tests {sorted(keys)}, expected both {list(_NAME_KEYS)}"
        )


def test_compliant_name_readers_still_present():
    """Anti-vacuity: the eleven `location or spot` readers the fix matches."""
    src = (_REPO / _CONVERTER_FILE).read_text()
    n = src.count('.get("location") or ') 
    assert n >= _MUST_SEE_MIN_NAME_READS, (
        f"expected at least {_MUST_SEE_MIN_NAME_READS} `location or spot` readers in "
        f"{_CONVERTER_FILE}, found {n}. Either they were removed or the module moved; "
        "the fix at the dispatch was defined as matching them, so that claim no longer holds."
    )


# --------------------------------------------------------------------------- #
# Guard B
# --------------------------------------------------------------------------- #
def _key_dispatch_chain() -> ast.If:
    """The if/elif chain in the converter that dispatches on the position keys."""
    for node in ast.walk(_converter_function()):
        if not isinstance(node, ast.If):
            continue
        keys, cur = set(), node
        while True:
            keys |= _all_keys_touched(cur.test)
            if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
                cur = cur.orelse[0]
            else:
                break
        if {"coords", *_NAME_KEYS} <= keys:
            return node
    raise AssertionError(
        f"no coords/location/spot dispatch chain found in {_CONVERTER_FUNC} — "
        "Guard B is vacuous, the code moved"
    )


def test_key_dispatch_accepts_the_whole_vocabulary():
    """All three keys are dispatched on — nobody narrowed it back."""
    chain, keys, cur = _key_dispatch_chain(), set(), None
    cur = chain
    while True:
        keys |= _all_keys_touched(cur.test)
        if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
        else:
            break
    missing = sorted({"coords", *_NAME_KEYS} - keys)
    assert not missing, (
        f"{_CONVERTER_FUNC} key dispatch no longer tests {missing}. All three are "
        "load-bearing: coords is the pre-resolved form, location and spot are the two "
        "names the skeletons actually author."
    )


def test_key_dispatch_fallthrough_raises_in_strict_mode():
    """The final else must still contain a raise, even though it is now gated."""
    tail = _key_dispatch_chain()
    while len(tail.orelse) == 1 and isinstance(tail.orelse[0], ast.If):
        tail = tail.orelse[0]
    assert tail.orelse, (
        f"{_CONVERTER_FUNC} key dispatch has no fallthrough at all — if the chain was "
        "restructured, re-establish where an unresolvable pos_action lands."
    )
    body = ast.Module(body=tail.orelse, type_ignores=[])
    assert any(isinstance(n, ast.Raise) for n in ast.walk(body)), (
        f"{_CONVERTER_FILE} line {tail.orelse[0].lineno}: the key-dispatch else branch "
        "contains no raise. Strict mode must fail loudly on an unresolvable pos_action; "
        "only the PRODUCTION path is allowed to degrade, and only by declining to place "
        "the player, never by substituting a coordinate."
    )


def test_key_dispatch_fallthrough_invents_no_coordinate():
    """The load-bearing invariant, and the one that survives the strict/soft gating.

    Whatever the branch does, it must not produce a coordinate. Asserting "it raises"
    stopped being sufficient once the raise was gated for production safety, so this
    asserts the thing that actually matters: no assignment to ``coords``.
    """
    tail = _key_dispatch_chain()
    while len(tail.orelse) == 1 and isinstance(tail.orelse[0], ast.If):
        tail = tail.orelse[0]
    body = ast.Module(body=tail.orelse, type_ignores=[])
    for node in ast.walk(body):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        for t in targets:
            name = getattr(t, "id", None) or getattr(t, "attr", None)
            assert name != "coords", (
                f"{_CONVERTER_FILE} line {node.lineno}: the key-dispatch fallthrough "
                "assigns `coords`. It must not invent a position — that is the defect "
                "this whole contract exists to prevent. Decline to place the player "
                "instead; an absent pos_action already takes that path and the emitter "
                "backfills from his live coords."
            )


def test_strict_mode_is_on_under_pytest_and_off_by_default():
    """The gate itself. Production must not get the raise; tests must."""
    from BackEnd.engine.defender_placement import _strict_pos_action_keys

    assert _strict_pos_action_keys(), (
        "strict mode is OFF under pytest — an unresolvable pos_action would be silently "
        "skipped in the test suite, which is where we most need it to shout"
    )
    for value, expected in (("true", True), ("1", True), ("false", False), ("0", False)):
        with mock.patch.dict(os.environ, {"GOB_STRICT_POS_ACTION_KEYS": value}):
            assert _strict_pos_action_keys() is expected, f"override {value!r} ignored"
    # With the override absent AND no pytest marker, production default is soft.
    env = {k: v for k, v in os.environ.items()
           if k not in ("GOB_STRICT_POS_ACTION_KEYS", "PYTEST_CURRENT_TEST")}
    with mock.patch.dict(os.environ, env, clear=True):
        assert _strict_pos_action_keys() is False, (
            "production default is strict — a builder-authored skeleton with an "
            "unrecognised shape would crash a live game"
        )


def test_unresolvable_pos_action_raises_in_strict_mode():
    """Behavioural: strict mode refuses to guess, loudly."""
    from BackEnd.engine import defender_placement as dp

    game, off, deff = _fake_game(), _fake_lineup(), {}
    skeleton = {"steps": [{"timestamp": 0, "pos_actions": {"PG": {"action": "drift"}}}]}
    with mock.patch.dict(os.environ, {"GOB_STRICT_POS_ACTION_KEYS": "true"}):
        with pytest.raises(ValueError) as ei:
            dp.build_all_animations(game, skeleton, off, deff, add_defenders=False)
    assert "no position key" in str(ei.value)
    assert "PG" in str(ei.value)


def test_unresolvable_pos_action_is_skipped_not_invented_in_soft_mode():
    """Behavioural: production declines to place him rather than answering (50,25).

    This is the case the raise was gated for. The player must simply be absent from
    the step — NOT present at court centre.
    """
    from BackEnd.engine import defender_placement as dp

    game, off, deff = _fake_game(), _fake_lineup(), {}
    skeleton = {"steps": [
        {"timestamp": 0, "pos_actions": {"PG": {"action": "handle_ball", "spot": "key"}}},
        {"timestamp": 300, "pos_actions": {"PG": {"action": "drift"}}},
    ]}
    with mock.patch.dict(os.environ, {"GOB_STRICT_POS_ACTION_KEYS": "false"}):
        animations, _zones = dp.build_all_animations(
            game, skeleton, off, deff, add_defenders=False)
    pg = [a for a in animations if str(a.get("playerId")) == "pg-1"]
    assert pg, "the resolvable first step should still have produced an animation"
    waypoints = pg[0].get("movement") or []
    assert len(waypoints) == 1, (
        f"expected the unresolvable step to be skipped, got {len(waypoints)} waypoints"
    )
    for wp in waypoints:
        c = wp.get("coords") or {}
        assert not (c.get("x") == 50 and c.get("y") == 25), (
            "soft mode produced court centre — it must decline to place the player, "
            "not substitute the logo"
        )


def test_fallthrough_carries_no_centre_court_literal():
    """The specific regression: no bare (50, 25) on the fallthrough."""
    tail = _key_dispatch_chain()
    while len(tail.orelse) == 1 and isinstance(tail.orelse[0], ast.If):
        tail = tail.orelse[0]
    body = ast.Module(body=tail.orelse, type_ignores=[])
    for node in ast.walk(body):
        if not isinstance(node, ast.Dict):
            continue
        pairs = {
            k.value: v.value
            for k, v in zip(node.keys, node.values)
            if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
        }
        assert not (pairs.get("x") == 50 and pairs.get("y") == 25), (
            f"{_CONVERTER_FILE} line {node.lineno}: court centre reintroduced on the "
            "key-dispatch fallthrough. This is the exact literal that hid the bug."
        )
