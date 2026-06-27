"""Dynamic HCO Set Plays — Stage A: feature gate + up-front-event skip wiring."""
import os
import importlib
import BackEnd.engine.phase_resolution as PR


def _set_env(monkeypatch, **kv):
    for k, v in kv.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_setplay_gate_off_by_default(monkeypatch):
    monkeypatch.delenv("GOB_DYNAMIC_HCO_SETPLAY", raising=False)
    assert PR._dynamic_hco_setplay_enabled() is False


def test_setplay_gate_on(monkeypatch):
    for v in ("1", "true", "YES", "on"):
        monkeypatch.setenv("GOB_DYNAMIC_HCO_SETPLAY", v)
        assert PR._dynamic_hco_setplay_enabled() is True


def test_setplay_gate_independent_of_motion(monkeypatch):
    # The two flags are independent — motion ON must not enable set plays.
    monkeypatch.setenv("GOB_DYNAMIC_HCO_MOTION", "1")
    monkeypatch.delenv("GOB_DYNAMIC_HCO_SETPLAY", raising=False)
    assert PR._dynamic_hco_motion_enabled() is True
    assert PR._dynamic_hco_setplay_enabled() is False


# --------------------------------------------------------- recovery roll (re-enter vs freelance)

class _Team:
    def __init__(self, chem, eff):
        self.team_attributes = {"team_chemistry": chem, "offensive_efficiency": eff, "defensive_efficiency": eff}


class _Game:
    def __init__(self, off, deff):
        self.offense_team = off
        self.defense_team = deff


class _Rng:
    def __init__(self, seq):
        self.seq = list(seq); self.i = 0
    def randint(self, a, b):
        v = self.seq[self.i % len(self.seq)]; self.i += 1; return v


def test_recovery_reenters_when_offense_wins():
    # offense (10+5)*6=90 vs defense (7+0)*1=7 → re-enter
    g = _Game(_Team(10, 5), _Team(7, 0))
    assert PR._setplay_recovery_roll(g, rng=_Rng([6, 1])) is True


def test_recovery_freelance_when_defense_wins():
    # offense (7+0)*1=7 vs defense (10+5)*6=90 → freelance
    g = _Game(_Team(7, 0), _Team(10, 5))
    assert PR._setplay_recovery_roll(g, rng=_Rng([1, 6])) is False
