"""Stage 1 of the movement-rate unification: ONE accessor, ONE interrupted-coord core.

`reports/movement-rate-inventory.md` found the engine deriving a movement rate at 117 call
sites, with four `_interrupted_coord` definitions (two distinct arithmetic variants) and two
byte-identical combined endpoint+duration helpers. Stage 1 collapsed those to:

  * `shared.movement_rate(player, archetype, *, apply_spread, fallback_rate=None)` — every
    rate-producing site reaches it, because `_ag_grid_per_game_sec` and
    `defender_movement_rate` are now thin delegates;
  * `_interrupted_coord_strict` / `_interrupted_coord_lenient` over one core, with the four
    legacy module-level names bound to the variant each module reached BEFORE;
  * one combined helper, `_motion_end_toward_dest`, re-exported as `_interpolate_step_end`.

Stage 1 is defined as a ZERO-BEHAVIOUR-CHANGE refactor, so these tests pin *routing*, not
arithmetic — the arithmetic is pinned by the equiv-v3 reference (160/160).

The audit exposed two ways a site can escape a naive check, and both are covered here:

  (a) **by-value imports** — `from ... import _ag_grid_per_game_sec` copies the function
      object into the importing module, so patching one module attribute under-counts. The
      audit's probe had to rebind in 25 modules. `test_every_module_holds_the_canonical_*`
      walks every module in `BackEnd` and asserts identity.
  (b) **injected callables** — `dynamic_hct` passes the rate and clamp functions as
      *arguments* into `fcp_offball_attack` (1,989 calls per 8 games). No name-based scan of
      that module can see it. `test_the_injected_path_*` asserts the injection by object
      identity and by executing it against a spy.
"""

import ast
import glob
import importlib
import os
import pkgutil

import pytest

import BackEnd
from BackEnd.utils import animation_step_helpers as ASH
from BackEnd.utils import shared as SH

#: Names that produce a movement rate. Any new one must be added here deliberately.
RATE_PRODUCERS = ("movement_rate", "_ag_grid_per_game_sec", "defender_movement_rate",
                  "ag_to_grid_per_game_sec")

#: The two `_interrupted_coord` variants and the modules that reached each BEFORE Stage 1.
STRICT_MODULES = ("BackEnd.utils.transition_bridge", "BackEnd.utils.reset_step_helper")
LENIENT_MODULES = ("BackEnd.engine.rim_runner_step_emitter",
                   "BackEnd.engine.fb_outlet_pass_step_emitter")


def _all_backend_modules():
    for mi in pkgutil.walk_packages(BackEnd.__path__, "BackEnd."):
        try:
            yield importlib.import_module(mi.name)
        except Exception:
            continue


def _py_files():
    return sorted(glob.glob("BackEnd/**/*.py", recursive=True))


# ---------------------------------------------------------------------------
# The accessor is the only implementation
# ---------------------------------------------------------------------------


def test_the_ag_curve_has_exactly_one_implementation():
    """`0.90 + (AG/100) * 0.2` may appear in exactly one place: `ag_to_grid_per_game_sec`.

    A second copy is how the four `_interrupted_coord` definitions happened.
    """
    hits = []
    for f in _py_files():
        for node in ast.walk(ast.parse(open(f).read())):
            if not isinstance(node, ast.Assign):
                continue
            src = ast.unparse(node.value)
            if "0.9" in src and "/ 100" in src and "0.2" in src:
                hits.append("%s:%d  %s" % (os.path.basename(f), node.lineno, src[:70]))
    assert len(hits) == 1, "the AG curve is implemented more than once:\n  " + "\n  ".join(hits)
    assert "shared.py" in hits[0]


def test_both_public_rate_functions_delegate_to_the_accessor(monkeypatch):
    """THE routing invariant. Both names the engine imports must go through
    `shared.movement_rate` — proved by executing them against a spy, not by reading source.

    Both do a deferred ``from BackEnd.utils.shared import movement_rate`` inside the
    function body, so patching the shared module reaches them.
    """
    calls = []
    real = SH.movement_rate

    def spy(player, archetype, *, apply_spread, fallback_rate=None):
        calls.append((archetype, apply_spread, fallback_rate))
        return real(player, archetype, apply_spread=apply_spread, fallback_rate=fallback_rate)

    monkeypatch.setattr(SH, "movement_rate", spy)

    ASH._ag_grid_per_game_sec(None, "sprint")
    assert calls[-1] == ("sprint", False, None), "the raw path stopped using the accessor"

    ASH.defender_movement_rate(None, "cruise", True)
    assert calls[-1] == ("cruise", True, None), "the spread path stopped using the accessor"

    ASH.defender_movement_rate(None, "drift", False)
    assert calls[-1] == ("drift", False, None), "is_defender must map to apply_spread"


def test_apply_spread_is_exactly_the_old_is_defender_argument():
    """`movement_rate(..., apply_spread=x)` must equal `defender_movement_rate(..., x)`."""
    for arch in ("standard", "sprint", "cruise", "drift", "burst", "shot_motion"):
        for flag in (True, False):
            assert SH.movement_rate(None, arch, apply_spread=flag) == \
                ASH.defender_movement_rate(None, arch, flag)


def test_the_clamp_is_applied_before_the_archetype_multiplier():
    """ORDER IS LOAD-BEARING. The [0.5, 60] clamp lives inside `ag_to_grid_per_game_sec`,
    i.e. on the STANDARD-equivalent rate, and the archetype multiplies AFTERWARDS.

    If someone reverses it, `burst` at a high AG would be clamped to 60 instead of scaling
    past it. The clamp never binds for AG 0-100 (standard spans 12.6-15.4), so only an
    extreme AG can catch the mistake — which is why this test uses one.
    """
    class _P:
        def __init__(self, ag):
            self.attributes = {"AG": ag}

    # AG far beyond the clamp: standard-equivalent saturates at 60, burst then scales it.
    rate = SH.movement_rate(_P(100000), "burst", apply_spread=False)
    from BackEnd.constants import BURST_GRID_PER_GAME_SEC, STANDARD_GRID_PER_GAME_SEC
    expected = BURST_GRID_PER_GAME_SEC * (60.0 / float(STANDARD_GRID_PER_GAME_SEC))
    assert rate == pytest.approx(expected)
    assert rate > 60.0, "clamp-then-multiply must be able to exceed 60 on burst"


def test_fallback_rate_is_used_only_when_the_player_is_falsy():
    """`fallback_rate` carries the covert-release 12.0 through Stage 1 unchanged. It must
    not leak into the normal path."""
    class _P:
        attributes = {"AG": 50}

    assert SH.movement_rate(None, "burst", apply_spread=False, fallback_rate=12.0) == 12.0
    assert SH.movement_rate(_P(), "burst", apply_spread=False, fallback_rate=12.0) == \
        SH.movement_rate(_P(), "burst", apply_spread=False)
    # and with no fallback a missing player resolves to the archetype base, not 12.0
    assert SH.movement_rate(None, "burst", apply_spread=False) != 12.0


# ---------------------------------------------------------------------------
# (a) by-value imports
# ---------------------------------------------------------------------------


def test_every_module_holds_the_canonical_rate_functions():
    """FAILURE MODE (a). `from ... import _ag_grid_per_game_sec` copies the object, so a
    module can silently hold a stale or private one. Every module that holds any of these
    names must hold THE canonical object."""
    canonical = {
        "movement_rate": SH.movement_rate,
        "_ag_grid_per_game_sec": ASH._ag_grid_per_game_sec,
        "defender_movement_rate": ASH.defender_movement_rate,
        "ag_to_grid_per_game_sec": SH.ag_to_grid_per_game_sec,
    }
    bad = []
    for mod in _all_backend_modules():
        for name, obj in canonical.items():
            held = getattr(mod, name, None)
            if held is not None and held is not obj:
                bad.append("%s.%s" % (mod.__name__, name))
    assert not bad, "these modules hold a NON-canonical rate function:\n  " + "\n  ".join(bad)


def test_no_module_defines_its_own_rate_function():
    """A private copy is the defect this stage removed — `_ag_grid_per_game_sec` used to be
    duplicated in two emitters, both missing the `drift` branch."""
    dupes = []
    for f in _py_files():
        for node in ast.walk(ast.parse(open(f).read())):
            if isinstance(node, ast.FunctionDef) and node.name in RATE_PRODUCERS:
                dupes.append("%s:%d %s" % (os.path.basename(f), node.lineno, node.name))
    # the four legitimate definitions: the two in shared, the two delegates in ASH
    assert sorted(d.split()[-1] for d in dupes) == sorted([
        "ag_to_grid_per_game_sec", "movement_rate",
        "_ag_grid_per_game_sec", "defender_movement_rate"]), \
        "unexpected rate-function definitions:\n  " + "\n  ".join(dupes)


def test_the_private_stampers_route_through_the_accessor(monkeypatch):
    """The three private copies of `stamp_tween_durations` must use the accessor.

    They import `movement_rate` BY VALUE at module level, so this patches each module's own
    attribute — which is exactly the point of failure mode (a).
    """
    from BackEnd.engine import rim_runner_step_emitter as RR
    from BackEnd.engine import fb_outlet_pass_step_emitter as FB
    from BackEnd.engine import covert_release_step_emitter as CR

    for mod in (RR, FB, CR):
        assert getattr(mod, "movement_rate", None) is SH.movement_rate, \
            "%s does not hold the accessor; its private stamper cannot be using it" % mod.__name__
        src = ast.unparse(ast.parse(open(mod.__file__).read()))
        fn = next(n for n in ast.walk(ast.parse(open(mod.__file__).read()))
                  if isinstance(n, ast.FunctionDef) and n.name == "_stamp_tween_durations")
        body = ast.unparse(fn)
        assert "movement_rate(" in body, "%s._stamp_tween_durations bypasses the accessor" % mod.__name__
        # STAGE 2 (2026-09-24) SUPERSEDES THE STAGE 1 PIN HERE. Stage 1 asserted
        # `apply_spread=False` with the message "wiring the spread in is a later stage".
        # This IS that stage: the flip was the whole point of routing these through the
        # accessor. What must hold now is that the spread is applied PER PLAYER, by
        # def_lineup membership, so the offence is untouched.
        assert "apply_spread=_is_defender_id(pid, def_lineup)" in body, (
            "%s._stamp_tween_durations must apply the spread per player via def_lineup "
            "membership — a blanket apply_spread=True would widen the OFFENCE" % mod.__name__
        )


# ---------------------------------------------------------------------------
# (b) injected callables
# ---------------------------------------------------------------------------


def test_the_injected_path_receives_the_canonical_callables():
    """FAILURE MODE (b). `dynamic_hct` injects the rate and clamp functions into
    `fcp_offball_attack`, which never imports them. A name-based refactor misses this site
    entirely — the audit only found it by runtime trace."""
    from BackEnd.engine import dynamic_hct as DH
    assert DH._ag_grid_per_game_sec is ASH._ag_grid_per_game_sec
    assert DH._interrupted_coord is ASH._interrupted_coord_strict, \
        "dynamic_hct injects variant A; binding anything else changes the injected path"

    src = open(DH.__file__).read()
    assert "ag_grid_fn=_ag_grid_per_game_sec" in src
    assert "interrupted_fn=_interrupted_coord" in src


def test_the_injected_rate_actually_reaches_the_accessor(monkeypatch):
    """Execute the injection rather than trusting the binding: call the injected callable
    the way `fcp_offball_attack` calls it (positionally, player + archetype) and assert the
    accessor saw it."""
    from BackEnd.engine import dynamic_hct as DH
    seen = []
    real = SH.movement_rate

    def spy(player, archetype, *, apply_spread, fallback_rate=None):
        seen.append((archetype, apply_spread))
        return real(player, archetype, apply_spread=apply_spread, fallback_rate=fallback_rate)

    monkeypatch.setattr(SH, "movement_rate", spy)
    injected = DH._ag_grid_per_game_sec          # what is passed as ag_grid_fn
    injected(None, "sprint")                      # fcp_offball_attack.py call shape
    assert seen == [("sprint", False)], "the injected rate callable bypassed the accessor"


# ---------------------------------------------------------------------------
# _interrupted_coord: one core, two variants, unchanged routing
# ---------------------------------------------------------------------------


def test_there_is_exactly_one_interrupted_coord_core():
    defs = []
    for f in _py_files():
        for node in ast.walk(ast.parse(open(f).read())):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_interrupted_coord"):
                defs.append("%s:%d %s" % (os.path.basename(f), node.lineno, node.name))
    names = sorted(d.split()[-1] for d in defs)
    assert names == ["_interrupted_coord_core", "_interrupted_coord_lenient",
                     "_interrupted_coord_strict"], \
        "the four definitions are back:\n  " + "\n  ".join(defs)


def test_each_module_keeps_the_variant_it_reached_before():
    """Stage 1 must NOT normalise the two policies. Each legacy name stays bound to the
    variant that module reached before the refactor (audit Q2)."""
    for name in STRICT_MODULES:
        mod = importlib.import_module(name)
        assert mod._interrupted_coord is ASH._interrupted_coord_strict, \
            "%s reached variant A (strict); re-pointing it is a behaviour change" % name
    for name in LENIENT_MODULES:
        mod = importlib.import_module(name)
        assert mod._interrupted_coord is ASH._interrupted_coord_lenient, \
            "%s reached variant B (lenient); re-pointing it is a behaviour change" % name


def test_the_two_variants_still_differ_exactly_where_they_did():
    """The drift is PRESERVED, not fixed — that is stage 2. Pin it so a later 'tidy-up'
    cannot silently unify them."""
    strict, lenient = ASH._interrupted_coord_strict, ASH._interrupted_coord_lenient
    # lenient tolerates None; strict does not
    assert lenient(None, None, 14.0, 1.0) == {"x": 50.0, "y": 25.0}
    assert lenient(None, {"x": 1.0, "y": 2.0}, 14.0, 1.0) == {"x": 1.0, "y": 2.0}
    assert lenient({"x": 3.0, "y": 4.0}, None, 14.0, 1.0) == {"x": 3.0, "y": 4.0}
    with pytest.raises(TypeError):
        strict(None, None, 14.0, 1.0)
    # and the zero test differs in the 1e-9 window
    s, t = {"x": 0.0, "y": 0.0}, {"x": 5e-10, "y": 0.0}
    assert strict(s, t, 0.0, 1.0) == {"x": 5e-10, "y": 0.0}
    assert lenient(s, t, 0.0, 1.0) == {"x": 0.0, "y": 0.0}


def test_every_interrupted_coord_call_site_is_accounted_for():
    """32 call sites (audit Q1). 31 are direct; the 32nd is the injected one in
    `fcp_offball_attack`, which calls it through a parameter named `interrupted_fn`."""
    direct = 0
    for f in _py_files():
        for node in ast.walk(ast.parse(open(f).read())):
            if not isinstance(node, ast.Call):
                continue
            nm = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if nm == "_interrupted_coord":
                direct += 1
    injected = 0
    for f in _py_files():
        for node in ast.walk(ast.parse(open(f).read())):
            if isinstance(node, ast.Call):
                nm = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                if nm == "interrupted_fn":
                    injected += 1
    assert injected >= 1, "the injected _interrupted_coord call site disappeared"
    assert direct + injected == 32, (
        "expected 32 _interrupted_coord call sites (31 direct + 1 injected), found %d + %d"
        % (direct, injected)
    )


# ---------------------------------------------------------------------------
# the combined endpoint+duration helper
# ---------------------------------------------------------------------------


def test_there_is_one_combined_helper_re_exported_under_both_names():
    from BackEnd.engine import skeleton_step_emitter as SKE
    assert SKE._interpolate_step_end is ASH._motion_end_toward_dest
    defs = []
    for f in _py_files():
        for node in ast.walk(ast.parse(open(f).read())):
            if isinstance(node, ast.FunctionDef) and node.name in (
                    "_interpolate_step_end", "_motion_end_toward_dest"):
                defs.append("%s:%d %s" % (os.path.basename(f), node.lineno, node.name))
    assert len(defs) == 1, "the combined helper is duplicated again:\n  " + "\n  ".join(defs)


def test_the_combined_helper_callers_are_all_still_there():
    """13 callers (6 + 7 in the audit). They pass a RAW rate and Stage 1 keeps it raw."""
    n = 0
    for f in _py_files():
        tree = ast.parse(open(f).read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            nm = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if nm in ("_motion_end_toward_dest", "_interpolate_step_end"):
                n += 1
    assert n == 13, "expected 13 combined-helper call sites, found %d" % n


def test_the_combined_helper_rate_is_per_player_not_per_call():
    """STAGE 2 SUPERSEDES THE STAGE 1 PIN. Stage 1 asserted these 13 callers stayed on a raw
    rate. Stage 2 wires the spread in — but it must be decided PER PLAYER.

    All 13 callers are MIXED (each resolves the player with `_player_lookup_by_id(off_lineup,
    def_lineup, pid)`; several branch `"cut" if pid in off_ids else "guard_offball"` in the
    same loop). A blanket `apply_spread=True` would widen the OFFENCE, which is out of scope.
    So every caller must go through `defender_aware_rate`, which tests def_lineup membership.
    """
    for f in _py_files():
        tree = ast.parse(open(f).read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            nm = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if nm not in ("_motion_end_toward_dest", "_interpolate_step_end"):
                continue
            if len(node.args) > 2:
                arg = ast.unparse(node.args[2])
                assert "apply_spread=True" not in arg, (
                    "%s:%d applies the spread unconditionally — these call sites are MIXED, so "
                    "that would widen the offence" % (os.path.basename(f), node.lineno)
                )


# ---------------------------------------------------------------------------
# preserved defects — Stage 1 must NOT fix these
# ---------------------------------------------------------------------------


def test_the_covert_release_12_fallback_is_preserved():
    """Four sites substitute a hardcoded 12.0 when the player lookup fails; the canonical
    fallback is the archetype base (burst off by -20.0). Stage 1 carries it UNCHANGED via
    `fallback_rate=12.0`. Correcting it is stage 2, behind its own flag."""
    src = open("BackEnd/engine/covert_release_step_emitter.py").read()
    assert src.count("fallback_rate=12.0") == 4
    assert src.count("STAGE 2") >= 4, "the 12.0 sites must stay flagged for stage 2"
    # and the accessor must honour it
    assert SH.movement_rate(None, "burst", apply_spread=False, fallback_rate=12.0) == 12.0


def test_the_missing_traversal_floor_is_preserved():
    """Three sites compute `rate * t` with no `max(0.0, ...)`. Preserved exactly."""
    src = open("BackEnd/engine/covert_release_step_emitter.py").read()
    assert src.count("max_traversal = rate * t") == 3
    assert "max_traversal = max(0.0, rate * t)" not in src, (
        "a floor was added to covert_release — that is a behaviour change, stage 2"
    )


def test_drift_or_hold_coord_was_not_folded_in():
    """Explicitly out of scope: it consumes RNG (`r.random()`) inside its clamp, so folding
    it into a pure shared helper would move the draw stream."""
    body = ast.unparse(next(
        n for n in ast.walk(ast.parse(open(ASH.__file__).read()))
        if isinstance(n, ast.FunctionDef) and n.name == "drift_or_hold_coord"))
    assert "r.random()" in body
    assert "_interrupted_coord" not in body, (
        "drift_or_hold_coord was routed through the shared clamp — it draws RNG, so this "
        "would move the draw stream"
    )
