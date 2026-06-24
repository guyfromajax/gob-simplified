"""Dynamic HCO subtle-movement Defense Behavior + step-time/forced-shot wiring (brief:
Updated Subtle Movement Logic). The per-defender read is rolled in the resolver and applied
geometrically in the animator's freeze helper; here we unit-test those pieces directly."""
import types

from BackEnd.models.animator import _subtle_defender_should_freeze
from BackEnd.engine.phase_resolution import _roll_subtle_defender_reads
from BackEnd.engine.motion_step_decision import (
    MOTION_READ_THRESHOLD, SUBTLE_STEP_ELAPSED_BY_TEMPO, SUBTLE_FORCED_SHOT_PENALTY,
)


class _FakePlayer:
    def __init__(self, pid, attrs=None):
        self.player_id = pid
        self.attributes = attrs or {}


def _subtle_step(movers, defender_reads):
    return {"pos_actions": {}, "_subtle_movement": {"movers": movers, "defender_reads": defender_reads}}


class _SeqRng:
    """randint returns successive values from a list (cycled)."""
    def __init__(self, seq):
        self.seq = seq
        self.i = 0

    def randint(self, a, b):
        v = self.seq[self.i % len(self.seq)]
        self.i += 1
        return v


# --------------------------------------------------------- _subtle_defender_should_freeze

def test_non_subtle_step_never_freezes():
    assert _subtle_defender_should_freeze({"pos_actions": {}}, "SG", "PG") is False


def test_follows_when_man_moved_and_read_passed():
    step = _subtle_step(movers=["PG", "SG"], defender_reads={"SG": True})
    assert _subtle_defender_should_freeze(step, "SG", "SG") is False  # anchor SG moved, read follows


def test_freezes_when_read_failed_even_if_man_moved():
    step = _subtle_step(movers=["PG", "SG"], defender_reads={"SG": False})
    assert _subtle_defender_should_freeze(step, "SG", "SG") is True


def test_freezes_when_man_did_not_move_regardless_of_read():
    # Anchor SF is not among the movers → defender holds even though his read passed.
    step = _subtle_step(movers=["PG"], defender_reads={"SF_def": True})
    assert _subtle_defender_should_freeze(step, "SF_def", "SF") is True


def test_missing_read_defaults_to_follow():
    step = _subtle_step(movers=["PG", "SG"], defender_reads={})
    assert _subtle_defender_should_freeze(step, "SG", "SG") is False


# --------------------------------------------------------- _roll_subtle_defender_reads

def test_defender_read_smart_follows_dumb_freezes():
    smart = _FakePlayer("d1", {"IQ": 95, "CH": 95})   # read 95
    dumb = _FakePlayer("d2", {"IQ": 5, "CH": 0})       # read 4
    def_lineup = {"PG": smart, "SG": dumb}
    # d6 fixed at 2: smart (95+0)*2=190 > 110 → follows; dumb (4+0)*2=8 → freezes.
    reads = _roll_subtle_defender_reads(def_lineup, def_eff=0, rng=_SeqRng([2]))
    assert reads["PG"] is True
    assert reads["SG"] is False


def test_def_eff_lifts_defender_read():
    weak = _FakePlayer("d", {"IQ": 10, "CH": 0})  # read 8
    # (8 + 50) * 2 = 116 > 110 → follows thanks to team def_eff.
    reads = _roll_subtle_defender_reads({"PG": weak}, def_eff=50, rng=_SeqRng([2]))
    assert reads["PG"] is True


# --------------------------------------------------------- constants / forced-shot plumbing

def test_tempo_elapsed_ranges():
    assert SUBTLE_STEP_ELAPSED_BY_TEMPO == {"slow": (3, 4), "normal": (2, 4), "fast": (2, 3)}
    assert MOTION_READ_THRESHOLD == 110
    assert SUBTLE_FORCED_SHOT_PENALTY == 50


def test_execute_motion_decision_carries_forced_shot_penalty():
    # _execute_motion_decision must surface forced_shot_penalty so resolve_hco_outcome can
    # subtract it from shot_score (alongside attack_penalty).
    from BackEnd.engine.phase_resolution import _execute_motion_decision

    class _G:
        pass

    game = _G()
    bh = _FakePlayer("bh")
    off = {"PG": bh}
    steps = [
        {"pos_actions": {"PG": {"location": "key", "action": "handle_ball"}}},
        {"pos_actions": {"PG": {"location": "key", "action": "handle_ball"}}},
    ]
    decision = {"action": "SHOOT", "shooter_pos": "PG", "shot_type": "outside"}
    res = _execute_motion_decision({"steps": steps}, steps[:2], steps[1], "PG", "key", decision,
                                   game, off, {}, is_away_offense=False, forced_shot_penalty=50)
    assert res["forced_shot_penalty"] == 50
    assert res["attack_penalty"] == 0.0
