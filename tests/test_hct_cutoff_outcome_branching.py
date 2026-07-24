"""Broken HCT/FCP cutoff: POS_O continues; NEUTRAL/D_STOP → HCO stop."""

from BackEnd.engine.cutoff_resolution import (
    map_cutoff_outcome_to_fb,
    map_cutoff_outcome_to_hct_transition,
)


def test_hct_transition_pos_o_continues_attack():
    assert map_cutoff_outcome_to_hct_transition("POS_O") == "CONTINUE_ATTACK"


def test_hct_transition_neutral_and_d_stop_to_stop_hco():
    assert map_cutoff_outcome_to_hct_transition("NEUTRAL") == "STOP_HCO"
    assert map_cutoff_outcome_to_hct_transition("D_STOP") == "STOP_HCO"


def test_hct_transition_unknown_defaults_to_stop_hco():
    assert map_cutoff_outcome_to_hct_transition("WEIRD") == "STOP_HCO"


def test_fb_map_d_stop_is_defensive_stop():
    event, flags = map_cutoff_outcome_to_fb("D_STOP")
    assert event == "DEFENSIVE_STOP"
    assert flags == {}


def test_fb_map_neutral_still_defensive_stop():
    event, _ = map_cutoff_outcome_to_fb("NEUTRAL")
    assert event == "DEFENSIVE_STOP"


def test_fb_map_pos_o_still_shot():
    event, flags = map_cutoff_outcome_to_fb("POS_O")
    assert event == "SHOT"
    assert flags.get("ball_handler_beats_defender") is True
