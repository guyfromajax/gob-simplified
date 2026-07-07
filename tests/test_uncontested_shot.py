"""Universal uncontested inside/attack make helper."""

import pytest

from BackEnd.utils.uncontested_shot import (
    UNCONTESTED_INSIDE_ATTACK_MAX_DIST,
    UNCONTESTED_MAKE_THRESHOLD_BASE,
    apply_uncontested_inside_attack_make,
    compute_uncontested_inside_attack_make_threshold,
    resolve_uncontested_inside_attack_make,
    uncontested_inside_attack_helper_eligible,
)


class _Team:
    def __init__(self, discipline=0, fight=0):
        self.team_attributes = {"discipline": discipline, "fight": fight}


class TestUncontestedInsideAttackHelper:
    BASKET = (87.0, 25.0)

    def test_outside_shot_excluded(self):
        assert uncontested_inside_attack_helper_eligible(
            shot_type="outside",
            shooter_x=85.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
        ) is False

    def test_geo_gate_distance_11(self):
        # ~11 grid from (87,25) toward home: (76, 25) is dist 11
        assert uncontested_inside_attack_helper_eligible(
            shot_type="inside",
            shooter_x=76.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
        ) is True
        assert uncontested_inside_attack_helper_eligible(
            shot_type="attack",
            shooter_x=75.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
        ) is False

    def test_threshold_formula(self):
        off = _Team(discipline=5, fight=0)
        deff = _Team(fight=3)
        threshold = compute_uncontested_inside_attack_make_threshold(
            shooter_x=85.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
            off_team=off,
            def_team=deff,
        )
        assert threshold == 100.0  # clamped from 99 + 5 - 3

    def test_distance_penalty_beyond_11_lowers_threshold(self, monkeypatch):
        """At dist 12+ threshold drops by 2*(d-11) → harder to make (need lower roll)."""
        off = _Team()
        deff = _Team()
        # Bypass geo gate in compute by calling with dist 12 — helper returns None at dist>11
        # Test the penalty math directly by temporarily allowing dist 12 in compute only.
        from BackEnd.utils import uncontested_shot as mod

        monkeypatch.setattr(mod, "UNCONTESTED_INSIDE_ATTACK_MAX_DIST", 15.0)
        t11 = compute_uncontested_inside_attack_make_threshold(
            shooter_x=76.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
            off_team=off,
            def_team=deff,
        )
        t12 = compute_uncontested_inside_attack_make_threshold(
            shooter_x=75.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
            off_team=off,
            def_team=deff,
        )
        assert t11 == pytest.approx(99.0)
        assert t12 == pytest.approx(97.0)

    def test_roll_make_when_below_threshold(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.utils.uncontested_shot.random.randint",
            lambda _a, _b: 50,
        )
        assert resolve_uncontested_inside_attack_make(
            shot_type="inside",
            shooter_x=85.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
            off_team=_Team(),
            def_team=_Team(),
        ) is True

    def test_roll_miss_when_at_or_above_threshold(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.utils.uncontested_shot.random.randint",
            lambda _a, _b: 99,
        )
        assert resolve_uncontested_inside_attack_make(
            shot_type="attack",
            shooter_x=85.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
            off_team=_Team(),
            def_team=_Team(),
        ) is False

    def test_apply_falls_back_to_threshold_compare(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.utils.uncontested_shot.random.randint",
            lambda _a, _b: 1,
        )
        # dist > 11 → helper None → fallback
        assert apply_uncontested_inside_attack_make(
            shot_type="inside",
            shooter_x=70.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
            off_team=_Team(),
            def_team=_Team(),
            shot_score=150.0,
            shot_threshold=100.0,
        ) is True
        assert apply_uncontested_inside_attack_make(
            shot_type="inside",
            shooter_x=70.0,
            shooter_y=25.0,
            basket_x=self.BASKET[0],
            basket_y=self.BASKET[1],
            off_team=_Team(),
            def_team=_Team(),
            shot_score=80.0,
            shot_threshold=100.0,
        ) is False
