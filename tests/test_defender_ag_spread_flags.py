"""The defender AG spread ships behind ``GOB_DEFENDER_AG_SPREAD``, **default ON** (2026-09-24).

Flipped on 2026-09-24. ``GOB_DEFENDER_AG_SPREAD=0`` is the rollback and reproduces
``equiv_v3_reference_1f4af0ede_loosesag_nogate.json`` (160/160, fp AND draws) plus
``equiv_v3_loose_baseline_1f4af0ede_loosesag.json`` (80/80). Because an unset flag now means
ON, any test that intends the spread OFF must use the ``spread_off`` fixture and say so.

The shipped AG curve is nearly flat — across the real league a p90-AG defender is only 1.103×
a p10-AG one — so defenders all move alike. This widens the player multiplier for **defenders
only**, at the **endpoint only**, keeping AG=50 fixed:

    scale(AG) = (1 - s) + (AG / 100) * 2s,   s = DEFENDER_AG_SPREAD = 0.50

This is a shipped-defaults guard. It also pins the properties the build rests on:

  * at ``s = 0.10`` the wrapper is **byte-identical** to the shipped formula, so the kill
    switch is exact rather than merely equivalent;
  * **AG=50 is unchanged at every s** — the midpoint is preserved, so the average player never
    moves and the flag cannot be a stealth global speed change;
  * **offence is untouched** at any s;
  * **step duration T is untouched** at any s — this is the whole reason the spread lives at
    the endpoint and not in ``_ag_grid_per_game_sec``. Widening the shared function costs
    +11.2% game length at s=0.50 (reports/ag-spread-sweep-2026-09-24.md §5);
  * **the endpoint and the tween read the SAME wrapper.** If one is changed and not the other,
    the rendered motion stops matching the distance covered — so both call sites are pinned.
"""

import inspect
import os

import pytest

from BackEnd.utils import animation_step_helpers as ASH
from BackEnd.utils import transition_bridge as TB


class _P:
    def __init__(self, ag, pid="p"):
        self.player_id = pid
        self.attributes = {"AG": ag}


ARCHES = ("standard", "sprint", "cruise", "drift", "burst", "shot_motion", "compressed_hco")


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so the helper returns its shipped default (ON since 2026-09-24)."""
    monkeypatch.delenv(ASH.DEFENDER_AG_SPREAD_FLAG, raising=False)


@pytest.fixture
def spread_off(monkeypatch):
    """Explicitly DISABLED. Since the 2026-09-24 flip an unset flag means ON, so a test that
    intends the spread off must say so rather than relying on the default."""
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "0")


@pytest.fixture
def spread_on(monkeypatch):
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")


def test_spread_defaults_on(clean_env):
    """FLIPPED 2026-09-24. Was `test_spread_defaults_off`; the assertion is inverted because
    the default itself moved, which is the whole content of the flip. Kept (not deleted) so a
    future change cannot silently flip it back without editing this line and saying why."""
    assert ASH.defender_ag_spread_enabled() is True, (
        "GOB_DEFENDER_AG_SPREAD must default ON. The defender spread at s=0.50 is the shipped "
        "behaviour; reports/ag-spread-default-flip.md."
    )


def test_spread_kill_switch(clean_env, monkeypatch):
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "0")
    assert ASH.defender_ag_spread_enabled() is False
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")
    assert ASH.defender_ag_spread_enabled() is True


def test_flag_off_is_the_shipped_function_itself(spread_off):
    """OFF must return `_ag_grid_per_game_sec`'s own value for defenders too.

    Takes `spread_off` rather than `clean_env` since the 2026-09-24 flip: unset now means ON,
    so this test has to ask for the off state explicitly. The assertion is unchanged."""
    for arch in ARCHES:
        for ag in (0, 24, 39, 50, 73, 100, 144):
            assert ASH.defender_movement_rate(_P(ag), arch, True) == \
                ASH._ag_grid_per_game_sec(_P(ag), arch)


def test_s_010_is_byte_identical_to_the_shipped_formula(spread_on, monkeypatch):
    """The kill switch is exact, not approximate: (1-0.10) + (AG/100)*0.20 IS the shipped
    0.90 + (AG/100)*0.2. Checked across every archetype and the full AG range in play."""
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.10)
    for arch in ARCHES:
        for ag in range(0, 145):
            assert ASH.defender_movement_rate(_P(ag), arch, True) == \
                ASH._ag_grid_per_game_sec(_P(ag), arch), (arch, ag)


def test_midpoint_is_preserved_at_every_s(spread_on, monkeypatch):
    """AG=50 must never move, or the flag is a global speed change in disguise."""
    for s in (0.10, 0.25, 0.50, 0.75, 1.00):
        monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", s)
        for arch in ARCHES:
            assert ASH.defender_movement_rate(_P(50), arch, True) == \
                ASH._ag_grid_per_game_sec(_P(50), arch), (s, arch)


def test_spread_constant_is_reused_not_copied(spread_on, monkeypatch):
    """Doubling DEFENDER_AG_SPREAD must double the deviation from the midpoint."""
    mid = ASH._ag_grid_per_game_sec(_P(50), "standard")
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.25)
    d1 = ASH.defender_movement_rate(_P(100), "standard", True) - mid
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.50)
    d2 = ASH.defender_movement_rate(_P(100), "standard", True) - mid
    assert d1 > 0
    assert d2 == pytest.approx(2 * d1)


def test_it_actually_widens(spread_on):
    """The point of the build: the p10->p90 league rate ratio must grow."""
    lo, hi = _P(24), _P(73)          # real-league p10 / p90
    today = ASH._ag_grid_per_game_sec(hi, "standard") / ASH._ag_grid_per_game_sec(lo, "standard")
    wide = (ASH.defender_movement_rate(hi, "standard", True)
            / ASH.defender_movement_rate(lo, "standard", True))
    assert today == pytest.approx(1.1034, abs=1e-3)
    assert wide > 1.6


def test_offence_is_untouched_at_any_s(spread_on, monkeypatch):
    for s in (0.10, 0.25, 0.50, 0.75, 1.00):
        monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", s)
        for arch in ARCHES:
            for ag in (0, 24, 50, 73, 144):
                assert ASH.defender_movement_rate(_P(ag), arch, False) == \
                    ASH._ag_grid_per_game_sec(_P(ag), arch), (s, arch, ag)


def test_the_shared_rate_function_is_not_touched():
    """The spread must NOT live in `_ag_grid_per_game_sec` or `ag_to_grid_per_game_sec`:
    those feed natural_t -> the gate -> step duration T, which is the +11.2% pacing trap."""
    from BackEnd.utils import shared as SH
    for fn in (ASH._ag_grid_per_game_sec, SH.ag_to_grid_per_game_sec):
        src = inspect.getsource(fn)
        assert "DEFENDER_AG_SPREAD" not in src
        assert "defender_ag_spread_enabled" not in src


def test_step_duration_is_computed_before_the_spread_is_applied():
    """The ordering constraint, pinned in source: in `build_walk_up_step`, `t` is frozen and
    `natural_t` consumed by the gate BEFORE `defender_movement_rate` is ever called. If someone
    moves the call earlier, a slow defender would start stretching T and the offence would wait
    for him instead of beating him."""
    src = inspect.getsource(TB.build_walk_up_step)
    i_rates = src.index("rate = _ag_grid_per_game_sec(player, arch)")
    i_t = src.index("t = max(float(min_t_game_sec), slowest_t)")
    i_spread = src.index("defender_movement_rate(")
    assert i_rates < i_t < i_spread, "the spread must be applied after T is frozen"


def test_natural_t_is_built_from_the_unwidened_rate():
    """natural_t feeds the gate. It must use `_ag_grid_per_game_sec`, never the wrapper."""
    src = inspect.getsource(TB.build_walk_up_step)
    head = src[:src.index("t = max(float(min_t_game_sec), slowest_t)")]
    assert "defender_movement_rate" not in head
    assert "natural_t[pid] = dist / rate" in head


def test_the_endpoint_and_the_tween_read_the_same_wrapper():
    """THE central invariant. If either call site stops using `defender_movement_rate`, the
    rendered motion and the simulated endpoint diverge — the animation stops matching the game.
    Both are pinned here so that change cannot pass silently."""
    endpoint_src = inspect.getsource(TB.build_walk_up_step)
    tween_src = inspect.getsource(ASH.stamp_tween_durations)
    assert "defender_movement_rate(" in endpoint_src, "endpoint stopped using the wrapper"
    assert "defender_movement_rate(" in tween_src, "tween stopped using the wrapper"
    # and the tween must not have reverted to the raw function
    assert "_ag_grid_per_game_sec(" not in tween_src, (
        "stamp_tween_durations must go through defender_movement_rate, not the raw rate"
    )


def test_the_tween_matches_the_endpoint_for_a_slow_defender(spread_on, monkeypatch):
    """End to end on the two functions that must agree: at the same rate, the duration the
    stamper writes covers exactly the distance the endpoint helper says was travelled."""
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.50)
    slow = _P(10, "D")
    rate = ASH.defender_movement_rate(slow, "standard", True)
    T = 1.0
    start = {"x": 0.0, "y": 0.0}
    target = {"x": 40.0, "y": 0.0}                    # far beyond rate*T
    end = TB._interrupted_coord(start, target, rate, T)
    covered = ((end["x"] - start["x"]) ** 2 + (end["y"] - start["y"]) ** 2) ** 0.5
    assert covered == pytest.approx(rate * T)
    start_blk = {"coords": {"D": start}, "archetype": {"D": "standard"}}
    ASH.stamp_tween_durations(start_blk, {"D": end}, T, {}, {"PG": slow})
    dur = start_blk["tween_durations"]["D"]
    assert dur * rate == pytest.approx(covered, abs=1e-6)


def test_no_new_rng(spread_on):
    """A spread is arithmetic. The wrapper must not draw."""
    from BackEnd.utils import sim_random
    st = sim_random.sim_rng.getstate()
    for ag in range(0, 101, 5):
        ASH.defender_movement_rate(_P(ag), "standard", True)
    assert sim_random.sim_rng.getstate() == st


def test_constants_unchanged():
    """Nothing retuned to build this."""
    from BackEnd.constants import (STANDARD_GRID_PER_GAME_SEC, SPRINT_GRID_PER_GAME_SEC,
                                   CRUISE_GRID_PER_GAME_SEC, DRIFT_GRID_PER_GAME_SEC,
                                   BURST_GRID_PER_GAME_SEC, SHOT_MOTION_GRID_PER_GAME_SEC)
    assert (STANDARD_GRID_PER_GAME_SEC, SPRINT_GRID_PER_GAME_SEC, CRUISE_GRID_PER_GAME_SEC,
            DRIFT_GRID_PER_GAME_SEC, BURST_GRID_PER_GAME_SEC,
            SHOT_MOTION_GRID_PER_GAME_SEC) == (14, 18, 13, 8, 32, 14)
    assert ASH.DEFENDER_AG_SPREAD == 0.50
    from BackEnd.utils.shared import ag_to_grid_per_game_sec
    assert ag_to_grid_per_game_sec(50) == 14.0
    assert ag_to_grid_per_game_sec(0) == pytest.approx(12.6)
    assert ag_to_grid_per_game_sec(100) == pytest.approx(15.4)


# ---------------------------------------------------------------------------
# Call-site closure (2026-09-24)
# ---------------------------------------------------------------------------
#
# `_interrupted_coord` is not one function - there are FOUR copies of it
# (transition_bridge, reset_step_helper, fb_outlet_pass_step_emitter,
# rim_runner_step_emitter). So "the wrapper is used" cannot be checked by reading one
# function; it has to be checked at every call site, structurally.
#
# The tests below parse the engine and resolve the RATE argument of every
# `_interrupted_coord(...)` call back to its assignment. Every site must resolve to
# `defender_movement_rate` EXCEPT the five offence placements listed in OFFENCE_SITES --
# and that list is frozen, so adding a new unwired defender site fails the suite rather
# than silently costing a defender his spread.

import ast
import glob
import re

#: Sites that place an OFFENSIVE player and must keep using the raw shipped rate.
#: Wiring any of these would change offence, which this build must not do.
OFFENCE_SITES = {
    ("dynamic_hct.py", "bh_rate"): "the ball handler's own drive rate",
    ("dynamic_hct.py", "bh_drive_rate"): "the ball handler breaking down his man",
    ("dynamic_hct.py", "rate"): "the off-ball OFFENCE walk (two sites, off_lineup/off_coords)",
    ("rim_runner_step_emitter.py", "rate"): "an unconditional offence `cut`",
}


def _interrupted_coord_sites():
    """(file, lineno, rate_expr, kind) for every `_interrupted_coord` call in BackEnd."""
    out = []
    for fn in sorted(glob.glob("BackEnd/**/*.py", recursive=True)):
        text = open(fn).read()
        if "_interrupted_coord" not in text:
            continue
        src = text.splitlines()
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            nm = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
            if nm != "_interrupted_coord" or len(node.args) < 3:
                continue
            expr = ast.unparse(node.args[2])
            if expr.startswith("defender_movement_rate"):
                out.append((os.path.basename(fn), node.lineno, expr, "WRAPPER"))
                continue
            kind = "UNRESOLVED"
            for i in range(node.lineno - 2, -1, -1):
                m = re.match(r"\s*%s\s*=\s*(.*)" % re.escape(expr), src[i])
                if not m:
                    continue
                v, j = m.group(1), i
                while v.count("(") > v.count(")") and j + 1 < len(src):
                    j += 1
                    v += " " + src[j].strip()
                kind = "WRAPPER" if "defender_movement_rate" in v else "RAW"
                break
            out.append((os.path.basename(fn), node.lineno, expr, kind))
    return out


def test_every_interrupted_coord_site_resolves_to_a_rate_we_recognise():
    """No site may be left unresolvable - that would hide an unwired defender."""
    sites = _interrupted_coord_sites()
    assert len(sites) >= 31, "call sites disappeared; re-derive the inventory (found %d)" % len(sites)
    unresolved = [s for s in sites if s[3] == "UNRESOLVED"]
    assert not unresolved, "cannot tell which rate these sites use: %r" % (unresolved,)


def test_every_defender_interrupted_coord_site_reads_the_wrapper():
    """THE closure invariant. Every `_interrupted_coord` call places its player at
    `start + rate x T`; if that rate is not the wrapper's, the endpoint and the tween are
    computed at different speeds and the animation stops matching the game.

    Only the documented OFFENCE placements may use the raw rate.
    """
    raw = [(f, ln, e) for f, ln, e, k in _interrupted_coord_sites() if k == "RAW"]
    unexpected = [s for s in raw if (s[0], s[2]) not in OFFENCE_SITES]
    assert not unexpected, (
        "these `_interrupted_coord` sites still use the raw shipped rate. If the placed "
        "player is a DEFENDER, route it through defender_movement_rate. If he is on "
        "OFFENCE, add him to OFFENCE_SITES with a reason:\n  %s"
        % "\n  ".join("%s:%d  rate=%s" % s for s in unexpected)
    )
    assert len(raw) == 5, (
        "the offence exemption list is frozen at 5 sites; it is now %d. A new raw site is "
        "either a defender that needs wiring or an offence placement that needs a reason "
        "in OFFENCE_SITES." % len(raw)
    )


def test_the_wrapper_reaches_every_emitter_that_places_defenders():
    """The module-level import trap, from the other side.

    `from ... import defender_movement_rate` copies the function object into the importing
    module, so a module that places defenders must actually hold it. Two bindings are
    legitimate and this accepts both:

      * a MODULE-level import, which must be the wrapper object itself;
      * a FUNCTION-level import (``dynamic_hct_shot`` does this), which resolves from the
        source module at call time and is therefore immune to the trap outright.

    What must not happen is a module placing defenders with neither.
    """
    import importlib
    for m in ("BackEnd.utils.transition_bridge", "BackEnd.utils.reset_step_helper",
              "BackEnd.engine.dynamic_hct", "BackEnd.engine.dynamic_hct_step_emitter",
              "BackEnd.engine.dynamic_hct_shot", "BackEnd.engine.rim_runner_step_emitter",
              "BackEnd.engine.fb_outlet_pass_step_emitter",
              "BackEnd.engine.triangle_step_emitter"):
        mod = importlib.import_module(m)
        bound = getattr(mod, "defender_movement_rate", None)
        if bound is not None:
            assert bound is ASH.defender_movement_rate, (
                "%s holds something OTHER than the wrapper under that name" % m
            )
            continue
        src = inspect.getsource(mod)
        assert re.search(r"^\s+from BackEnd\.utils\.animation_step_helpers import "
                         r"[^\n]*defender_movement_rate", src, re.M), (
            "%s places defenders but imports the wrapper neither at module nor function "
            "level - its sites cannot be using it" % m
        )


def test_step_duration_is_frozen_before_the_spread_at_every_new_site():
    """The pacing trap, re-checked per module rather than only in `build_walk_up_step`.

    Where a builder derives its step duration `t` from a player's rate, that derivation
    must use the RAW `_ag_grid_per_game_sec` and must come BEFORE the widened rate is
    used for an endpoint. If the widened rate ever feeds `t`, a slow defender starts
    stretching the step and the offence waits for him instead of beating him.
    """
    from BackEnd.engine import triangle_step_emitter as TRI
    src = inspect.getsource(TRI._build_parallel_move_step)
    i_t = src.index("t = max(t, _traversal_seconds(step_start_coords[pid], mover[1], recv_rate))")
    i_spread = src.index("defender_movement_rate(")
    assert i_t < i_spread, "the triangle step must freeze t before applying the spread"
    assert "recv_rate = _ag_grid_per_game_sec(" in src, (
        "the duration-forming rate must stay RAW; widening it is the +11.2% pacing trap"
    )


def test_no_new_site_forms_a_duration_from_the_widened_rate():
    """Structural: `defender_movement_rate(...)` must never be divided into a distance to
    make a time, in any module. That is the shape that turns the spread into pacing."""
    bad = []
    for fn in sorted(glob.glob("BackEnd/**/*.py", recursive=True)):
        text = open(fn).read()
        if "defender_movement_rate" not in text:
            continue
        src = text.splitlines()
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Assign):
                continue
            tgt = ast.unparse(node.targets[0])
            if not re.search(r"(^|_)t$|_t\b|seconds|duration", tgt):
                continue
            if "defender_movement_rate" in ast.unparse(node.value):
                bad.append("%s:%d  %s" % (os.path.basename(fn), node.lineno, src[node.lineno - 1].strip()))
    assert not bad, "a step duration is being formed from the WIDENED rate:\n  " + "\n  ".join(bad)
