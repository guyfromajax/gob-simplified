from types import SimpleNamespace

from BackEnd.engine.phase_resolution import _get_fcp_hct_post_inbound_start_index


def _step(sf_action, sf_spot, pg_action=None):
    pos_actions = {
        "SF": {"action": sf_action, "spot": sf_spot},
        "PG": {"action": pg_action or "stationary"},
    }
    return {"pos_actions": pos_actions}


def _game_with_prev_turn(prev_turn):
    return SimpleNamespace(turns=[prev_turn])


def test_defaults_to_legacy_skip_when_not_post_bip():
    skeleton = {"steps": [_step("pass", "inbound_left", "receive"), _step("cut", "wing")]}
    game = _game_with_prev_turn({"result_type": "HCO"})
    assert _get_fcp_hct_post_inbound_start_index(skeleton, game) == 1


def test_post_bip_skips_single_inbound_pass_step():
    skeleton = {"steps": [_step("pass", "inbound_left", "receive"), _step("handle_ball", "key")]}
    game = _game_with_prev_turn({"current_turn": "BASELINE_INBOUND"})
    assert _get_fcp_hct_post_inbound_start_index(skeleton, game) == 1


def test_post_bip_skips_staging_and_pass_steps():
    skeleton = {
        "steps": [
            _step("handle_ball", "inbound_left", "get_open"),
            _step("pass", "inbound_left", "receive"),
            _step("handle_ball", "key"),
        ]
    }
    game = _game_with_prev_turn({"result_type": "BASELINE_INBOUND"})
    assert _get_fcp_hct_post_inbound_start_index(skeleton, game) == 2


def test_post_bip_recognizes_inbound_right_for_away_orientation():
    skeleton = {"steps": [_step("pass", "inbound_right", "receive"), _step("cut", "backcourt")]}
    game = _game_with_prev_turn({"turn_type": "BASELINE_INBOUND"})
    assert _get_fcp_hct_post_inbound_start_index(skeleton, game) == 1


def test_never_trims_entire_skeleton_when_all_steps_look_inbound():
    skeleton = {
        "steps": [
            _step("handle_ball", "inbound_left"),
            _step("pass", "inbound_left", "receive"),
        ]
    }
    game = _game_with_prev_turn({"result_type": "BASELINE_INBOUND"})
    assert _get_fcp_hct_post_inbound_start_index(skeleton, game) == 1
