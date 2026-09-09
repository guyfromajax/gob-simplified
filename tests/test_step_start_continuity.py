"""UESS §8.1: within a turn, step N+1 ``start.coords`` must equal step N ``end.coords``.

WHY THIS FILE EXISTS. Nothing in the suite asserted this before 2026-09-09, and a real
teleport shipped behind that gap: the fast-break shooter released his shot and then snapped
4.5 ft BACKWARDS down his own drive path, because the post-shot chain was built twice and the
copy that rendered was seeded from a stale coord (bugs.md item 40).

WHY IT MATTERS ON SCREEN, and why "start coords are only metadata" is wrong. The renderer does
not draw ``start.coords``. It snaps sprites to ``end.coords`` at every step end
(``animationPlayback.js:1526``) and only snaps to start on the turn's ENTRY step (``:1585``) --
the playback docstring says so outright: *"Engine does not snap-to-start; sprite drift between
steps is the caller's bug to fix"* (``:1039``). ``start.coords`` decides one thing: whether a
player is tweened at all (``:1302``, skipped when start == end). So a discontinuity is visible
in one of two ways:

  - player authored STILL in N+1  -> tween skipped, he holds his real position all step, then
    the end-of-step snap JUMPS him. A teleport.
  - player authored MOVING in N+1 -> the tween runs from his real position to the right place.
    No jump, but along a path and at a speed nobody authored.

Neither is acceptable, so the assertion is exact equality rather than a tolerance.
"""

from typing import Any, Dict, List

import pytest

from BackEnd.utils.animation_step_helpers import enforce_step_start_continuity

EPS = 1e-6


def _coord(x: float, y: float) -> Dict[str, float]:
    return {"x": float(x), "y": float(y)}


def _step(start: Dict[str, Any], end: Dict[str, Any]) -> Dict[str, Any]:
    return {"start": {"coords": start}, "end": {"coords": end}}


def assert_within_turn_continuity(steps: List[Dict[str, Any]], label: str = "") -> None:
    """The invariant itself. Shared so emitter tests can call it directly."""
    for i in range(1, len(steps)):
        prev_end = ((steps[i - 1].get("end") or {}).get("coords")) or {}
        cur_start = ((steps[i].get("start") or {}).get("coords")) or {}
        for pid, pe in prev_end.items():
            cs = cur_start.get(pid)
            if not isinstance(pe, dict) or not isinstance(cs, dict):
                continue
            gap = (
                (float(cs["x"]) - float(pe["x"])) ** 2
                + (float(cs["y"]) - float(pe["y"])) ** 2
            ) ** 0.5
            assert gap < EPS, (
                "UESS §8.1 violated%s: step %d player %s starts at (%.4f, %.4f) but step %d "
                "ended him at (%.4f, %.4f) — a %.2f ft discontinuity. The renderer snaps to "
                "end.coords and never to start.coords mid-turn, so this is a teleport if the "
                "player is authored still in step %d, and an unauthored glide if he is not."
                % (
                    (" in " + label) if label else "",
                    i, pid, float(cs["x"]), float(cs["y"]),
                    i - 1, float(pe["x"]), float(pe["y"]), gap, i,
                )
            )


class TestInvariantItself:
    def test_continuous_chain_passes(self):
        steps = [
            _step({"p1": _coord(10, 10)}, {"p1": _coord(20, 15)}),
            _step({"p1": _coord(20, 15)}, {"p1": _coord(30, 20)}),
            _step({"p1": _coord(30, 20)}, {"p1": _coord(30, 20)}),
        ]
        assert_within_turn_continuity(steps, "continuous fixture")

    def test_the_shipped_defect_is_caught(self):
        """POISON — the exact shape measured in bugs.md item 40: shooter releases at
        (93.36, 27.36), next step parks him back at (90.18, 24.18)."""
        steps = [
            _step({"s": _coord(90.18, 24.18)}, {"s": _coord(93.36, 27.36)}),
            _step({"s": _coord(93.36, 27.36)}, {"s": _coord(93.36, 27.36)}),
            # the teleport: authored still, at a coord he left one step ago
            _step({"s": _coord(90.18, 24.18)}, {"s": _coord(90.18, 24.18)}),
        ]
        with pytest.raises(AssertionError, match=r"UESS §8.1 violated"):
            assert_within_turn_continuity(steps, "poisoned fixture")

    def test_reports_the_magnitude(self):
        steps = [
            _step({"p": _coord(0, 0)}, {"p": _coord(0, 0)}),
            _step({"p": _coord(3, 4)}, {"p": _coord(3, 4)}),
        ]
        with pytest.raises(AssertionError, match=r"5\.00 ft discontinuity"):
            assert_within_turn_continuity(steps)

    def test_absorbed_discontinuity_also_fails(self):
        """A discontinuity on a MOVING player does not teleport, but it still means the
        player travels a path nobody authored. It must not be waved through."""
        steps = [
            _step({"p": _coord(0, 0)}, {"p": _coord(10, 0)}),
            _step({"p": _coord(4, 0)}, {"p": _coord(20, 0)}),
        ]
        with pytest.raises(AssertionError, match=r"UESS §8.1 violated"):
            assert_within_turn_continuity(steps)


class TestGuardHelper:
    """``enforce_step_start_continuity`` is the guard wired into the FB emitters."""

    def test_guard_repairs_and_counts(self):
        steps = [
            _step({"s": _coord(90.18, 24.18)}, {"s": _coord(93.36, 27.36)}),
            _step({"s": _coord(90.18, 24.18)}, {"s": _coord(90.18, 24.18)}),
        ]
        assert enforce_step_start_continuity(steps, context="unit") == 1
        assert_within_turn_continuity(steps, "after guard")

    def test_guard_is_a_noop_on_clean_input(self):
        """It must not perturb correct output — that is what makes it safe to leave on."""
        steps = [
            _step({"p": _coord(1, 1)}, {"p": _coord(2, 2)}),
            _step({"p": _coord(2, 2)}, {"p": _coord(3, 3)}),
        ]
        import copy

        before = copy.deepcopy(steps)
        assert enforce_step_start_continuity(steps) == 0
        assert steps == before

    def test_guard_leaves_players_absent_from_prior_end_alone(self):
        """Stationary players can be dropped from end.coords; the guard must not invent
        a position for them (same carve-out as skeleton_step_emitter.py:2132-2135)."""
        steps = [
            _step({"a": _coord(1, 1), "b": _coord(5, 5)}, {"a": _coord(2, 2)}),
            _step({"a": _coord(9, 9), "b": _coord(5, 5)}, {"a": _coord(9, 9)}),
        ]
        assert enforce_step_start_continuity(steps) == 1
        assert steps[1]["start"]["coords"]["a"] == _coord(2, 2)
        assert steps[1]["start"]["coords"]["b"] == _coord(5, 5)
