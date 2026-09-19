"""The two rebound flags must ship in the state Jamie approved.

``GOB_REBOUND_FROM_ARRIVAL`` is ON: the rebounder is selected from where crashers
actually arrive. ``GOB_REBOUND_RACE`` is OFF: the race term and its derived
``REBOUND_RACE_TIME_SCALE`` stay in the tree as a dormant lever for the tuning pass,
but nothing scores on time to the ball yet.

This is a shipped-defaults guard. If someone flips either one, they should have to
edit this file and say why.
"""

import os

import pytest

from BackEnd.utils import rebound_arrival as RA


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so ``enabled()`` returns its shipped default, not an override."""
    monkeypatch.delenv("GOB_REBOUND_FROM_ARRIVAL", raising=False)
    monkeypatch.delenv("GOB_REBOUND_RACE", raising=False)


def test_arrival_defaults_on(clean_env):
    assert RA.enabled() is True, (
        "GOB_REBOUND_FROM_ARRIVAL must default ON. Selecting the rebounder from "
        "arrival positions is the shipped behaviour."
    )


def test_race_defaults_off(clean_env):
    assert RA.race_enabled() is False, (
        "GOB_REBOUND_RACE must default OFF. The race term is a dormant lever for the "
        "tuning pass; turning it on is a balance decision, not a default."
    )


def test_arrival_kill_switch(monkeypatch):
    """``=0`` restores legacy selection. This is the rollback path."""
    monkeypatch.setenv("GOB_REBOUND_FROM_ARRIVAL", "0")
    assert RA.enabled() is False


def test_race_requires_arrival(monkeypatch):
    """The race term is meaningless without arrival coords to race from, so it stays
    gated on the arrival flag even when explicitly enabled."""
    monkeypatch.setenv("GOB_REBOUND_RACE", "1")
    monkeypatch.setenv("GOB_REBOUND_FROM_ARRIVAL", "0")
    assert RA.race_enabled() is False

    monkeypatch.setenv("GOB_REBOUND_FROM_ARRIVAL", "1")
    assert RA.race_enabled() is True


def test_race_time_scale_is_the_derived_value():
    """0.5792 is derived, not chosen: T_bar * REBOUND_DISTANCE_SCALE / D_bar over
    6,555 candidate evaluations (D_bar = 10.7069 grid units, T_bar = 0.7752 s), so
    both terms evaluate to 0.427651 at the league average. Changing it is a retune."""
    from BackEnd.constants import REBOUND_DISTANCE_SCALE, REBOUND_RACE_TIME_SCALE

    assert REBOUND_RACE_TIME_SCALE == pytest.approx(0.5792)

    d_bar, t_bar = 10.7069, 0.7752
    distance_term = 1.0 / (1.0 + d_bar / REBOUND_DISTANCE_SCALE)
    race_term = 1.0 / (1.0 + t_bar / REBOUND_RACE_TIME_SCALE)
    assert race_term == pytest.approx(distance_term, abs=1e-5), (
        "the race term must be mean-neutral against the distance term at the league "
        "average - that is what makes it a unit conversion rather than a retune"
    )
