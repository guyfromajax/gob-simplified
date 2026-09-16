"""Dead-ball TO credit: the charged player must have had the ball on that step.

Symptom #3 mechanism C: drive-contact pinned a drive step, get_ball_handler
fell back to PG, and the TO was charged to the wrong man. Credit comes from
the drive-contact payload AFTER the pre-credit RNG — this function must not
grow ``drive`` (shot-clock IQ + zone-defender draws).
"""

import pytest

from BackEnd.engine.phase_resolution import (
    SKELETON_POSSESSION_ACTIONS,
    _apply_drive_contact_dead_ball_credit,
    assert_dead_ball_victim_had_ball,
    get_ball_handler_from_skeleton,
)


class _P:
    def __init__(self, pid):
        self.player_id = pid


def _lineup():
    return {
        "PG": _P("pg"),
        "SG": _P("sg"),
        "SF": _P("sf"),
        "PF": _P("pf"),
        "C": _P("c"),
    }


def _drive_skeleton():
    return {
        "steps": [
            {"pos_actions": {
                "PG": {"action": "handle_ball", "location": "key"},
                "SG": {"action": "stationary", "location": "wing"},
            }},
            {"pos_actions": {
                "PG": {"action": "stationary", "location": "key"},
                "SG": {"action": "drive", "location": "elbow"},
            }},
        ]
    }


def test_credit_contract_treats_drive_as_possession():
    assert "drive" in SKELETON_POSSESSION_ACTIONS


def test_shared_resolver_omits_drive_so_shot_clock_iq_holds():
    # An explicit pin on a drive step still falls back to PG. That is
    # deliberate: this return feeds shot-clock IQ. Credit is the payload path.
    off = _lineup()
    skel = _drive_skeleton()
    bh = get_ball_handler_from_skeleton(skel, off, step_index=1)
    assert bh is off["PG"]


def test_drive_contact_credit_charges_the_driver_not_pg():
    off = _lineup()
    skel = _drive_skeleton()
    roles = {"ball_handler": off["PG"], "ball_handler_id": "pg"}
    gs = {"_hco_drive_contact_driver_id": "sg", "steal_stop_step_index": 1}
    _apply_drive_contact_dead_ball_credit(roles, gs, skel, off)
    assert roles["ball_handler"] is off["SG"]
    assert roles["ball_handler_id"] == "sg"
    assert "_hco_drive_contact_driver_id" not in gs


def test_guard_accepts_the_driver():
    off = _lineup()
    skel = _drive_skeleton()
    assert_dead_ball_victim_had_ball(skel, 1, off["SG"], off)


def test_poison_charging_pg_on_a_drive_step_fails_the_guard():
    off = _lineup()
    skel = _drive_skeleton()
    with pytest.raises(AssertionError, match="did not have the ball"):
        assert_dead_ball_victim_had_ball(skel, 1, off["PG"], off)


def test_poison_credit_without_stash_leaves_pg_and_guard_still_fires():
    # 26c: the helper pops the stash; a missing stash is the pre-fix shape.
    # The guard is a separate literal and still names the lie.
    off = _lineup()
    skel = _drive_skeleton()
    roles = {"ball_handler": off["PG"], "ball_handler_id": "pg"}
    gs = {"steal_stop_step_index": 1}
    _apply_drive_contact_dead_ball_credit(roles, gs, skel, off)
    assert roles["ball_handler"] is off["PG"]
    with pytest.raises(AssertionError, match="did not have the ball"):
        assert_dead_ball_victim_had_ball(skel, 1, roles["ball_handler"], off)
