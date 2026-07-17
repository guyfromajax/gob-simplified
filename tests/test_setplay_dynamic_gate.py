"""Dynamic HCO Set Plays — the set-play forced-subtle recovery roll.

Gate tests removed (cleanup 2026-07-13): the GOB_DYNAMIC_HCO_MOTION / GOB_DYNAMIC_HCO_SETPLAY kill
switches + their neutered `_dynamic_hco_*_enabled()` helpers were retired in Stage 3 (dynamic is
always-on, no legacy fallback), so there is nothing left to gate.
"""
import BackEnd.engine.phase_resolution as PR


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
    assert PR._hco_recovery_roll(g, rng=_Rng([6, 1])) is True


def test_recovery_freelance_when_defense_wins():
    # offense (7+0)*1=7 vs defense (10+5)*6=90 → freelance
    g = _Game(_Team(7, 0), _Team(10, 5))
    assert PR._hco_recovery_roll(g, rng=_Rng([1, 6])) is False
