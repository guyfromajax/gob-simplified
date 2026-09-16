"""Shot-clock IQ uses the pinned driver, not the fabricated PG.

Post-draw: keep x, recompute the threshold from the pin step's drive
action. get_ball_handler_from_skeleton still omits drive.
"""

from types import SimpleNamespace

from BackEnd.engine.phase_resolution import (
    _driver_on_skeleton_step,
    _shot_clock_iq_threshold,
    get_ball_handler_from_skeleton,
    recompute_shot_clock_threshold_from_pin_driver,
)


class _P:
    def __init__(self, pid, iq, pos="PG"):
        self.player_id = pid
        self.name = pid
        self.position = pos
        self.attributes = {"IQ": iq}

    def get_name(self):
        return self.name


def _lineup(pg_iq=92, sg_iq=40):
    return {
        "PG": _P("pg", pg_iq, "PG"),
        "SG": _P("sg", sg_iq, "SG"),
        "SF": _P("sf", 50, "SF"),
        "PF": _P("pf", 50, "PF"),
        "C": _P("c", 50, "C"),
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


def test_shared_resolver_still_omits_drive():
    off = _lineup()
    assert get_ball_handler_from_skeleton(_drive_skeleton(), off, step_index=1) is off["PG"]


def test_driver_on_pin_step_is_the_drive_not_the_pg():
    off = _lineup()
    assert _driver_on_skeleton_step(_drive_skeleton(), off, 1) is off["SG"]
    assert _driver_on_skeleton_step(_drive_skeleton(), off, 0) is None
    assert _driver_on_skeleton_step(_drive_skeleton(), off, 99) is None


def test_no_drive_pin_is_a_noop():
    off = _lineup()
    fab_thr = _shot_clock_iq_threshold(off["PG"], chemistry=10, discipline=5)
    got = recompute_shot_clock_threshold_from_pin_driver(
        fab_thr, 50, _drive_skeleton(), off, 0, off["PG"], 10, 5,
    )
    assert got == fab_thr


def test_drive_pin_recomputes_threshold_from_driver_iq():
    off = _lineup(pg_iq=92, sg_iq=40)
    fab_thr = _shot_clock_iq_threshold(off["PG"], chemistry=10, discipline=5)
    drv_thr = _shot_clock_iq_threshold(off["SG"], chemistry=10, discipline=5)
    assert fab_thr != drv_thr
    got = recompute_shot_clock_threshold_from_pin_driver(
        fab_thr, 50, _drive_skeleton(), off, 1, off["PG"], 10, 5,
    )
    assert got == drv_thr


def test_poison_forces_a_branch_flip():
    """PG IQ keeps x under the threshold; driver IQ puts the same x over it."""
    off = _lineup(pg_iq=92, sg_iq=0)
    chem, disc = 10, 5
    fab_thr = _shot_clock_iq_threshold(off["PG"], chem, disc)
    drv_thr = _shot_clock_iq_threshold(off["SG"], chem, disc)
    assert fab_thr > drv_thr
    x = drv_thr + 1
    assert not (x > fab_thr)
    assert x > drv_thr
    got = recompute_shot_clock_threshold_from_pin_driver(
        fab_thr, x, _drive_skeleton(), off, 1, off["PG"], chem, disc,
    )
    assert got == drv_thr
    assert (x > fab_thr) != (x > got)
