"""The HCO drive help-cutoff gate removal ships behind ``GOB_HCO_CUTOFF_NO_GATE``,
**default OFF** (2026-09-23).

Today ``HCO_CUTOFF_STOP_ATTEMPT_PROB`` is ``{"passive": 0.0, "normal": 0.5, "aggressive":
1.0}``, so a **passive defense never attempts a help rotation on a blow-by at all**. With the
flag on, every aggression setting attempts it.

This is a shipped-defaults guard. It also pins what must NOT change:

  * only the *attempt* gate goes — the corridor, the arrival race and the contest roll are
    untouched, so a rotation still has to be earned;
  * the constant is **kept**, not deleted, so the rollback is exact and reads by name;
  * the two new flags are independent of each other.
"""

import inspect

import pytest

from BackEnd.engine import attack_drive_clearance as ADC


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so the helper returns its shipped default (OFF)."""
    monkeypatch.delenv(ADC.HCO_CUTOFF_NO_GATE_FLAG, raising=False)


def test_gate_removal_defaults_off(clean_env):
    assert ADC.cutoff_gate_removed() is False, (
        "GOB_HCO_CUTOFF_NO_GATE must default OFF. This is built and measured, not flipped."
    )


def test_gate_kill_switch(clean_env, monkeypatch):
    monkeypatch.setenv(ADC.HCO_CUTOFF_NO_GATE_FLAG, "0")
    assert ADC.cutoff_gate_removed() is False
    monkeypatch.setenv(ADC.HCO_CUTOFF_NO_GATE_FLAG, "1")
    assert ADC.cutoff_gate_removed() is True


def test_passive_never_attempts_with_the_flag_off(clean_env):
    """The behaviour Jamie is removing: passive is a hard 0.0."""
    assert ADC.hco_cutoff_stop_attempt_prob("passive") == 0.0
    assert ADC.hco_cutoff_stop_attempt_prob("normal") == 0.5
    assert ADC.hco_cutoff_stop_attempt_prob("aggressive") == 1.0


def test_every_aggression_attempts_with_the_flag_on(clean_env, monkeypatch):
    monkeypatch.setenv(ADC.HCO_CUTOFF_NO_GATE_FLAG, "1")
    for aggression in ("passive", "normal", "aggressive"):
        assert ADC.hco_cutoff_stop_attempt_prob(aggression) == 1.0
    assert ADC.hco_cutoff_stop_attempt_prob("something_unmapped") == 1.0


def test_the_constant_is_kept_and_reused_not_copied(clean_env, monkeypatch):
    """The table must survive the flag so the rollback is exact, and be read by name."""
    assert ADC.HCO_CUTOFF_STOP_ATTEMPT_PROB == {"passive": 0.0, "normal": 0.5, "aggressive": 1.0}
    monkeypatch.setattr(ADC, "HCO_CUTOFF_STOP_ATTEMPT_PROB",
                        {"passive": 0.2, "normal": 0.6, "aggressive": 0.9})
    assert ADC.hco_cutoff_stop_attempt_prob("passive") == 0.2
    assert ADC.hco_cutoff_stop_attempt_prob("aggressive") == 0.9


def test_the_unmapped_default_is_still_half_with_the_flag_off(clean_env):
    assert ADC.hco_cutoff_stop_attempt_prob("something_unmapped") == 0.5


def test_it_returns_a_probability_not_none(clean_env, monkeypatch):
    """1.0, never None. `best_cutoff_on_drive` rolls once per candidate whenever this is not
    None, so returning None would ALSO change the draw count, not just the admissions."""
    monkeypatch.setenv(ADC.HCO_CUTOFF_NO_GATE_FLAG, "1")
    v = ADC.hco_cutoff_stop_attempt_prob("passive")
    assert v is not None and isinstance(v, float) and v == 1.0


def test_the_race_and_contest_constants_are_untouched():
    """Only the attempt gate goes. A rotation still has to be earned."""
    assert ADC.HCO_CUTOFF_PATH_CORRIDOR == 11.0
    assert ADC.HCO_CUTOFF_DEFENDER_TIME_SLACK == 1.0


def test_the_resolver_reads_the_helper_not_the_table(clean_env):
    """If someone re-inlines HCO_CUTOFF_STOP_ATTEMPT_PROB.get(...) at the call site, the flag
    silently stops working. Pin the call site instead of trusting it."""
    src = inspect.getsource(ADC._resolve_hco_help_cutoff)
    assert "hco_cutoff_stop_attempt_prob(aggression)" in src
    assert "HCO_CUTOFF_STOP_ATTEMPT_PROB.get" not in src


def test_the_comment_states_what_the_table_actually_does():
    """The old comment claimed loose/aggressive defenses "sit deeper in help lanes and cut off
    more", which is the inverse of the table: `passive` is the LOWEST entry, not the highest.

    Asserting the old phrase is absent does not work - the replacement quotes it in order to
    correct it. So pin the correction instead: if someone restores the old claim as fact, this
    sentence goes with it and the test fails.
    """
    # comments wrap, so flatten "# " continuations before matching
    flat = " ".join(l.strip().lstrip("#").strip() for l in inspect.getsource(ADC).splitlines())
    assert "`passive` is the lowest entry, not the highest" in flat
    assert "a PASSIVE defense never attempts a help rotation on a blow-by" in flat
    assert "Only the attempt gate goes" in flat


def test_independent_of_the_loose_sag_axis(clean_env, monkeypatch):
    """Two unrelated changes; neither flag may gate the other."""
    from BackEnd.utils import shared_defense as SD
    monkeypatch.delenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, raising=False)
    monkeypatch.setenv(ADC.HCO_CUTOFF_NO_GATE_FLAG, "1")
    assert ADC.cutoff_gate_removed() is True
    assert SD.loose_sag_axis_enabled() is False
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    monkeypatch.setenv(ADC.HCO_CUTOFF_NO_GATE_FLAG, "0")
    assert ADC.cutoff_gate_removed() is False
    assert SD.loose_sag_axis_enabled() is True
