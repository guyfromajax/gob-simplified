"""Stage 2: the defender AG spread reaches the unified movement path, PER PLAYER.

Stage 1 gave the engine one rate accessor and one combined endpoint+duration helper, all on
a raw rate. Stage 2 lets `GOB_DEFENDER_AG_SPREAD` reach them — but the 13 callers of the
combined helper are all MIXED (each resolves the player with
`_player_lookup_by_id(off_lineup, def_lineup, pid)`, and several branch
`"cut" if pid in off_ids else "guard_offball"` inside the same loop). The spread is a
DEFENDER spread, so a blanket `apply_spread=True` would widen the OFFENCE, which is out of
scope and a large behaviour change.

So every one of those sites goes through `defender_aware_rate(player, archetype, pid,
def_lineup)`, which tests **def_lineup membership** — never an action label, never a
variable name. These tests pin that, and pin that the offence cannot move.

WARNING FROM HISTORY (reports/rate-unify-stage1.md): a prior commit put `_is_defender_id` /
`defender_movement_rate` imports inside a FUNCTION-LOCAL block in `triangle_step_emitter`
while two other functions in that module referenced the names. It parsed, it imported, and
it passed every test — but both call sites would have raised `NameError` the first time that
path fired, and the sims never fired it. `test_no_module_references_these_names_without_a_*`
and `test_every_function_that_references_*` exist so that cannot recur.
"""

import ast
import glob
import importlib
import os

import pytest

from BackEnd.utils import animation_step_helpers as ASH
from BackEnd.utils import shared as SH

#: The one per-player accessor every mixed call site must use.
PER_PLAYER = "defender_aware_rate"

#: Names whose scope the triangle incident proved must be module-level.
SCOPE_CRITICAL = ("defender_aware_rate", "_is_defender_id", "defender_movement_rate",
                  "movement_rate")


class _P:
    def __init__(self, pid, ag=50):
        self.player_id = pid
        self.attributes = {"AG": ag}


def _py_files():
    return sorted(glob.glob("BackEnd/**/*.py", recursive=True))


def _module_of(path):
    return path[:-3].replace("/", ".")


# ---------------------------------------------------------------------------
# the per-player rule
# ---------------------------------------------------------------------------


def test_defender_aware_rate_spreads_only_defenders(monkeypatch):
    """THE Stage 2 invariant. Same player, same archetype — on the defending lineup the
    spread applies, off it the rate is untouched."""
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")
    def_lineup = {"PG": _P("D1", 10)}
    slow_def = _P("D1", 10)
    slow_off = _P("O1", 10)

    raw = ASH._ag_grid_per_game_sec(slow_off, "standard")
    assert ASH.defender_aware_rate(slow_off, "standard", "O1", def_lineup) == raw, \
        "an OFFENSIVE player's rate moved — the spread is defenders only"
    assert ASH.defender_aware_rate(slow_def, "standard", "D1", def_lineup) != raw, \
        "the spread did not reach the defender"


def test_membership_is_the_test_not_the_action_label(monkeypatch):
    """A pid that is not in `def_lineup` is offence, whatever the step calls him. The audit
    found sites labelled `"cut"` that place defenders and vice versa."""
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")
    lineup = {"PG": _P("D1", 10)}
    for pid in ("O1", "", None, "D2"):
        assert ASH.defender_aware_rate(_P(pid, 10), "standard", pid, lineup) == \
            ASH._ag_grid_per_game_sec(_P(pid, 10), "standard")
    assert ASH.defender_aware_rate(_P("D1", 10), "standard", "D1", {}) == \
        ASH._ag_grid_per_game_sec(_P("D1", 10), "standard"), "an empty lineup must spread nobody"


def test_flag_off_is_identical_for_defenders_and_offence(monkeypatch):
    """The flag governs ALL of Stage 2. Off, every player gets the raw archetype rate."""
    monkeypatch.delenv(ASH.DEFENDER_AG_SPREAD_FLAG, raising=False)
    lineup = {"PG": _P("D1", 10), "C": _P("D2", 90)}
    for pid, ag in (("D1", 10), ("D2", 90), ("O1", 10), ("O2", 90)):
        p = _P(pid, ag)
        for arch in ("standard", "sprint", "cruise", "drift", "burst", "shot_motion"):
            assert ASH.defender_aware_rate(p, arch, pid, lineup) == \
                ASH._ag_grid_per_game_sec(p, arch)


def test_every_combined_helper_caller_uses_the_per_player_accessor():
    """All 13 callers of the combined helper must resolve their rate through
    `defender_aware_rate`. A new caller that computes its own rate fails here."""
    bad, seen = [], 0
    for f in _py_files():
        txt = open(f).read()
        if "_motion_end_toward_dest" not in txt and "_interpolate_step_end" not in txt:
            continue
        tree = ast.parse(txt)
        funcs = [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or len(call.args) < 3:
                continue
            nm = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", None)
            if nm not in ("_motion_end_toward_dest", "_interpolate_step_end"):
                continue
            enc = None
            for fn in funcs:
                if fn.lineno <= call.lineno <= fn.end_lineno and (enc is None or fn.lineno > enc.lineno):
                    enc = fn
            if enc is None or enc.name in ("_motion_end_toward_dest", "_interpolate_step_end"):
                continue
            seen += 1
            rate_expr = ast.unparse(call.args[2])
            assign = None
            for node in ast.walk(enc):
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                        ast.unparse(node.targets[0]) == rate_expr and node.lineno < call.lineno:
                    if assign is None or node.lineno > assign.lineno:
                        assign = node
            src = ast.unparse(assign.value) if assign is not None else rate_expr
            if PER_PLAYER not in src:
                bad.append("%s:%d in %s  rate <- %s" % (os.path.basename(f), call.lineno, enc.name, src[:60]))
    assert seen == 13, "expected 13 combined-helper call sites, found %d" % seen
    assert not bad, (
        "these combined-helper call sites do not use the per-player accessor, so they either "
        "miss the spread or apply it to the offence:\n  " + "\n  ".join(bad)
    )


def test_the_private_stampers_apply_the_spread_per_player():
    """The three private copies of `stamp_tween_durations`. Their ENDPOINTS already used the
    wrapper; Stage 2 closes the split so the rendered duration matches the simulated
    distance — defenders only."""
    for name in ("BackEnd.engine.rim_runner_step_emitter",
                 "BackEnd.engine.fb_outlet_pass_step_emitter",
                 "BackEnd.engine.covert_release_step_emitter"):
        mod = importlib.import_module(name)
        fn = next(n for n in ast.walk(ast.parse(open(mod.__file__).read()))
                  if isinstance(n, ast.FunctionDef) and n.name == "_stamp_tween_durations")
        body = ast.unparse(fn)
        assert "apply_spread=_is_defender_id(pid, def_lineup)" in body, \
            "%s._stamp_tween_durations is not applying the spread per player" % name
        assert "apply_spread=True" not in body, \
            "%s would widen the offence" % name


# ---------------------------------------------------------------------------
# the triangle lesson: scope
# ---------------------------------------------------------------------------


def test_no_module_references_these_names_without_a_module_scope_import():
    """FUNCTION-LOCAL imports of these names are how the triangle NameError happened: the
    import sat in one function's body while two other functions used the name.

    A module-level import (or a module-level definition) is required. A function-local
    import is allowed ONLY if every reference is inside that same function.
    """
    bad = []
    for f in _py_files():
        tree = ast.parse(open(f).read())
        module_level = set()
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_level.update(a.asname or a.name for a in node.names)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                module_level.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        module_level.add(t.id)
        funcs = [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for name in SCOPE_CRITICAL:
            if name in module_level:
                continue
            # every reference must be inside a function that itself imports the name
            for ref in ast.walk(tree):
                if not (isinstance(ref, ast.Name) and ref.id == name and isinstance(ref.ctx, ast.Load)):
                    continue
                owner = None
                for fn in funcs:
                    if fn.lineno <= ref.lineno <= fn.end_lineno and (owner is None or fn.lineno > owner.lineno):
                        owner = fn
                local_import = False
                if owner is not None:
                    for node in ast.walk(owner):
                        if isinstance(node, (ast.Import, ast.ImportFrom)) and \
                                any((a.asname or a.name) == name for a in node.names):
                            local_import = True
                            break
                if not local_import:
                    bad.append("%s:%d  %s referenced in %s with no import it can see"
                               % (os.path.basename(f), ref.lineno, name,
                                  owner.name if owner else "<module>"))
    assert not bad, (
        "a NameError waiting to fire (this is exactly the triangle_step_emitter incident):\n  "
        + "\n  ".join(bad)
    )


def test_every_function_that_references_the_names_can_actually_resolve_them():
    """Stronger than reading imports: import every module that references the names and
    resolve each one through the module's own globals, the way Python will at runtime."""
    unresolved = []
    for f in _py_files():
        txt = open(f).read()
        if not any(n in txt for n in SCOPE_CRITICAL):
            continue
        try:
            mod = importlib.import_module(_module_of(f))
        except Exception:
            continue
        tree = ast.parse(txt)
        funcs = [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for fn in funcs:
            refs = {n.id for n in ast.walk(fn)
                    if isinstance(n, ast.Name) and n.id in SCOPE_CRITICAL and isinstance(n.ctx, ast.Load)}
            if not refs:
                continue
            local = set()
            for node in ast.walk(fn):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    local.update(a.asname or a.name for a in node.names)
            for r in refs - local:
                if not hasattr(mod, r):
                    unresolved.append("%s.%s -> %s" % (mod.__name__, fn.name, r))
    assert not unresolved, (
        "these functions reference a name their module cannot resolve at runtime:\n  "
        + "\n  ".join(unresolved)
    )


def test_the_modules_touched_by_stage_2_hold_the_accessor_at_module_scope():
    """Belt and braces on the four emitters Stage 2 rewired."""
    for name in ("BackEnd.engine.after_steal_fast_break_step_emitter",
                 "BackEnd.engine.fb_drive_resolution",
                 "BackEnd.engine.shot_micro_movements",
                 "BackEnd.engine.skeleton_step_emitter"):
        mod = importlib.import_module(name)
        assert getattr(mod, PER_PLAYER, None) is ASH.defender_aware_rate, \
            "%s does not hold defender_aware_rate at module scope" % name


# ---------------------------------------------------------------------------
# the offence must not move
# ---------------------------------------------------------------------------


def test_the_offence_rate_is_unchanged_at_every_spread_strength(monkeypatch):
    """Whatever `DEFENDER_AG_SPREAD` is set to, a player who is not on the defending lineup
    gets exactly `_ag_grid_per_game_sec`."""
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")
    def_lineup = {"PG": _P("D1", 50)}
    for s in (0.10, 0.25, 0.50, 0.75, 1.00):
        monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", s)
        for ag in (0, 10, 24, 50, 73, 100, 144):
            p = _P("O1", ag)
            for arch in ("standard", "sprint", "cruise", "drift", "burst", "shot_motion"):
                assert ASH.defender_aware_rate(p, arch, "O1", def_lineup) == \
                    ASH._ag_grid_per_game_sec(p, arch), (s, ag, arch)


def test_the_midpoint_defender_is_also_unchanged(monkeypatch):
    """AG=50 is the spread's fixed point, so an average defender must not move either —
    otherwise the flag is a stealth global speed change."""
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")
    lineup = {"PG": _P("D1", 50)}
    for s in (0.10, 0.50, 1.00):
        monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", s)
        for arch in ("standard", "sprint", "cruise", "drift", "burst"):
            assert ASH.defender_aware_rate(_P("D1", 50), arch, "D1", lineup) == \
                ASH._ag_grid_per_game_sec(_P("D1", 50), arch)


def test_the_spread_strength_was_not_tuned():
    """Jamie tunes once at the end. Stage 2 uses the value already in the code."""
    assert ASH.DEFENDER_AG_SPREAD == 0.50
    assert ASH.DEFENDER_AG_SPREAD_FLAG == "GOB_DEFENDER_AG_SPREAD"


def test_there_is_still_only_one_flag():
    """Stage 2 must not introduce a second switch."""
    flags = set()
    for f in _py_files():
        for node in ast.walk(ast.parse(open(f).read())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and node.value.startswith("GOB_") and "SPREAD" in node.value:
                flags.add(node.value)
    assert flags == {"GOB_DEFENDER_AG_SPREAD"}, "a second spread flag appeared: %r" % (flags,)


def test_stage_3_defects_are_still_untouched():
    """Out of scope for Stage 2: the four hardcoded 12.0 fallbacks and the three missing
    `max(0.0, ...)` floors. (The source comments call these STAGE 2; the Stage 2 brief
    defers them to STAGE 3. The numbering moved, the code did not.)"""
    src = open("BackEnd/engine/covert_release_step_emitter.py").read()
    assert src.count("fallback_rate=12.0") == 4
    assert src.count("max_traversal = rate * t") == 3
    assert "max_traversal = max(0.0, rate * t)" not in src


# ---------------------------------------------------------------------------
# the id passed must be the id the player was looked up with
# ---------------------------------------------------------------------------

#: Sites whose player does NOT come from `_player_lookup_by_id`, with the id that is
#: correct there and why. Anything else must be derivable, so a blanket loop variable fails.
ID_EXEMPT = {
    ("fb_drive_resolution.py", "_reachable_defender_ends"):
        "defender = def_lineup.get(pos); pid = _player_id(defender) — pid IS his id",
    ("shot_micro_movements.py", "build_shot_micro_steps"):
        "defender_player / defender_id — `pid` here belongs to earlier loops and is UNBOUND",
    ("shared.py", "apply_sim_crash_destinations"):
        "player = by_id.get(ns) where ns = _norm_player_id(pid) = str(pid)",
}


def _lookup_id(expr):
    try:
        node = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None
    if isinstance(node, ast.Call):
        nm = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
        if nm == "_player_lookup_by_id" and len(node.args) >= 3:
            return ast.unparse(node.args[2])
    return None


def test_the_id_passed_is_the_id_the_player_was_looked_up_with():
    """REGRESSION GUARD — this bug actually happened and the reference caught it.

    A blanket rewrite passed the loop variable `pid` at
    `shot_micro_movements.build_shot_micro_steps`, where the player is `defender_player`
    and `pid` belongs to *earlier* loops in the same function. On the path that reaches the
    defender clamp those loops have not run, so `pid` was UNBOUND — 70 NameErrors in a
    single game, raised while evaluating the argument list and swallowed upstream, which
    silently skipped the clamp and moved the whole game.

    Whenever the player comes from `_player_lookup_by_id(off, def, X)`, the id passed must
    be X. Sites whose player comes from somewhere else are listed in ID_EXEMPT with the
    reason, so a new one cannot be added by accident.
    """
    checked, bad = 0, []
    for f in _py_files():
        txt = open(f).read()
        if PER_PLAYER not in txt:
            continue
        tree = ast.parse(txt)
        funcs = [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or len(call.args) < 4:
                continue
            nm = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", None)
            if nm != PER_PLAYER:
                continue
            enc = None
            for fn in funcs:
                if fn.lineno <= call.lineno <= fn.end_lineno and (enc is None or fn.lineno > enc.lineno):
                    enc = fn
            if enc is None or enc.name == PER_PLAYER:
                continue
            checked += 1
            player_expr = ast.unparse(call.args[0])
            id_expr = ast.unparse(call.args[2])
            derived = _lookup_id(player_expr)
            if derived is None:
                for node in ast.walk(enc):
                    if isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                            ast.unparse(node.targets[0]) == player_expr and node.lineno < call.lineno:
                        d = _lookup_id(ast.unparse(node.value))
                        if d:
                            derived = d
            key = (os.path.basename(f), enc.name)
            if derived is None:
                if key not in ID_EXEMPT:
                    bad.append("%s:%d in %s — player %r is not from _player_lookup_by_id and the "
                               "site is not in ID_EXEMPT" % (key[0], call.lineno, enc.name, player_expr))
                continue
            if derived != id_expr:
                bad.append("%s:%d in %s — player looked up with %r but id passed is %r"
                           % (key[0], call.lineno, enc.name, derived, id_expr))
    assert checked == 13, "expected 13 defender_aware_rate call sites, found %d" % checked
    assert not bad, (
        "the id passed does not name the player whose rate is being computed. This is the "
        "unbound-`pid` bug:\n  " + "\n  ".join(bad)
    )
