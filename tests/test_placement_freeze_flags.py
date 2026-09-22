"""The two placement flags must ship in the state Jamie approved (2026-09-21).

``GOB_PLACEMENT_FREEZE`` is ON: one placement draw per step, written once by whoever
creates the step, never redrawn, and the HCO emit renders that frozen row instead of
its own draw. ``GOB_PLACEMENT_SINGLE_BUILD`` is ON: the stamp builds whose entire
output write-once discards are no longer run.

This is a shipped-defaults guard. If someone flips either one, they should have to edit
this file and say why. It also pins the two properties the flip rests on:

  * **both kill switches still work** — ``equiv_v3_reference_70f7dd021_b1a.json`` is
    only reachable while ``GOB_PLACEMENT_FREEZE=0`` turns the whole thing off;
  * **the conjunction** — Stage 3 is inert unless the freeze is on, because with
    write-once off every build's result is still consumed and skipping one would
    change what a consumer reads.
"""

import pytest

from BackEnd.utils import placement_freeze as PF


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so the helpers return their shipped defaults, not an override."""
    monkeypatch.delenv(PF.FLAG, raising=False)
    monkeypatch.delenv(PF.FLAG_SINGLE_BUILD, raising=False)


def test_freeze_defaults_on(clean_env):
    assert PF.enabled() is True, (
        "GOB_PLACEMENT_FREEZE must default ON. One draw per step, written once, is the "
        "shipped behaviour."
    )


def test_single_build_defaults_on(clean_env):
    assert PF.single_build_enabled() is True, (
        "GOB_PLACEMENT_SINGLE_BUILD must default ON. Builds whose output write-once "
        "discards are not run."
    )


def test_freeze_kill_switch_turns_both_off(clean_env, monkeypatch):
    """The rollback path to equiv_v3_reference_70f7dd021_b1a.json."""
    monkeypatch.setenv(PF.FLAG, "0")
    assert PF.enabled() is False
    assert PF.single_build_enabled() is False


def test_single_build_kill_switch_leaves_the_freeze_on(clean_env, monkeypatch):
    """Dropping back to 2a: freeze without the build skip."""
    monkeypatch.setenv(PF.FLAG_SINGLE_BUILD, "0")
    assert PF.enabled() is True
    assert PF.single_build_enabled() is False


def test_single_build_is_inert_without_the_freeze(clean_env, monkeypatch):
    """The conjunction. Asking for Stage 3 with the freeze off must NOT enable it."""
    monkeypatch.setenv(PF.FLAG, "0")
    monkeypatch.setenv(PF.FLAG_SINGLE_BUILD, "1")
    assert PF.single_build_enabled() is False, (
        "Stage 3 must be inert unless the freeze is on: with write-once off every "
        "build's result is still consumed, so nothing is discardable."
    )


def test_discardable_needs_both_rows(clean_env):
    """A build is only skippable when every step has BOTH a defender and an offense row.

    Defence alone would let a post-subtle beat (phase_resolution.py:7683, pre-seeded
    with `defense` and no `offense`) qualify, and skipping there would strip the offense
    row the SIM arm's coord write scans for at :5030.
    """
    both = {"_step_state": {"defense": {"PG": {"x": 1, "y": 2}},
                            "offense": {"PG": {"x": 3, "y": 4}}}}
    defence_only = {"_step_state": {"defense": {"PG": {"x": 1, "y": 2}}}}
    bare = {}

    assert PF.stamp_build_is_discardable([both, both]) is True
    assert PF.stamp_build_is_discardable([both, defence_only]) is False
    assert PF.stamp_build_is_discardable([both, bare]) is False
    assert PF.stamp_build_is_discardable([]) is False


def test_frozen_defense_never_invents_a_row(clean_env):
    """Rule 26: absent means absent. It abstains, it does not fabricate."""
    assert PF.frozen_defense({}) == {}
    assert PF.frozen_defense({"_step_state": {}}) == {}
    assert PF.frozen_defense(None) == {}


def test_miss_reason_distinguishes_never_stamped_from_stamped_empty(clean_env):
    assert PF.miss_reason({}) == PF.REASON_NEVER_STAMPED
    assert PF.miss_reason({"_step_state": {"defense": {}}}) == PF.REASON_STAMPED_EMPTY
