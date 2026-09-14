"""Shot-at-1 discarded receive → within-step transfer on the glued shoot.

Animation only. pos_actions / derive_passer stay untouched. Poison: drop the
stamp and the §8.4 seam guard must fire again.
"""

from BackEnd.engine.phase_resolution import stamp_sa1_within_step_pass
from BackEnd.engine.shot_micro_movements import carry_sa1_pass_onto_first_micro
from BackEnd.engine.skeleton_step_emitter import _walk_ball_owners
from BackEnd.utils.animation_step_helpers import announce_ball_owner_seam


def _step(pa, **extra):
    out = {"pos_actions": pa, "events": []}
    out.update(extra)
    return out


def _recv(passer, receiver):
    return _step({
        passer: {"location": "slot", "action": "pass"},
        receiver: {"location": "wing", "action": "receive"},
    })


def _shoot(pos):
    return _step({pos: {"location": "wing", "action": "shoot"}})


def _handle(pos):
    return _step({pos: {"location": "slot", "action": "handle_ball"}})


class TestStamp:
    def test_stamps_last_receive_to_the_shooter(self):
        pre = [
            _handle("PG"),
            _recv("PG", "SF"),
            _step({"SF": {"location": "elbow", "action": "drive"}}),
            _recv("SF", "C"),
            _shoot("C"),
        ]
        # j=0 keeps handle; discarded = recv, drive, recv; glue shoot
        truncated = [pre[0], pre[-1]]
        stamp = stamp_sa1_within_step_pass(pre, 0, truncated)
        assert stamp == {"passer_pos": "SF", "receiver_pos": "C"}
        assert truncated[-1]["_sa1_within_step_pass"] == stamp
        assert len(truncated) == 2
        assert "receive" not in {
            ((inf or {}).get("action") or "")
            for st in truncated
            for inf in (st.get("pos_actions") or {}).values()
        }

    def test_no_receive_in_discard_is_noop(self):
        pre = [_handle("PG"), _step({"PG": {"location": "lane", "action": "drive"}}), _shoot("PG")]
        truncated = [pre[0], pre[-1]]
        assert stamp_sa1_within_step_pass(pre, 0, truncated) is None
        assert "_sa1_within_step_pass" not in truncated[-1]

    def test_does_not_change_shooter_or_pos_actions(self):
        shoot = _shoot("SG")
        pre = [_handle("PG"), _recv("PG", "SG"), shoot]
        truncated = [pre[0], shoot]
        pa_before = dict(shoot["pos_actions"])
        stamp_sa1_within_step_pass(pre, 0, truncated)
        assert shoot["pos_actions"] == pa_before
        assert list(shoot["pos_actions"]) == ["SG"]


class TestWalkHonorsStamp:
    def test_walk_flips_on_stamped_shoot_without_pos_actions_receive(self):
        shoot = _shoot("SG")
        shoot["_sa1_within_step_pass"] = {"passer_pos": "PG", "receiver_pos": "SG"}
        steps = [_handle("PG"), shoot]
        walks = _walk_ball_owners(steps)
        assert walks[0] == ("PG", "PG")
        assert walks[1] == ("PG", "SG")

    def test_walk_without_stamp_leaves_passer(self):
        steps = [_handle("PG"), _shoot("SG")]
        walks = _walk_ball_owners(steps)
        assert walks[1][0] == walks[1][1] == "PG"


class TestSeamGuard:
    def _chain(self, prev_end, micro_start, micro_end="SG"):
        return [
            {
                "start": {"ball": {"owner_player_id": prev_end}},
                "end": {
                    "ball": {"owner_player_id": prev_end},
                    "next": {"kind": "next_step", "index": 1},
                },
            },
            {
                "start": {
                    "ball": {"owner_player_id": micro_start},
                    "ball_motion_style": "pass" if micro_start != micro_end else None,
                    "action": {micro_end: "shoot"},
                },
                "end": {
                    "ball": {"owner_player_id": micro_end},
                    "next": {"kind": "turn_stop", "event": "SHOT_ATTEMPT"},
                },
            },
        ]

    def test_carried_transfer_is_silent(self, caplog):
        steps = self._chain("PG", "PG", "SG")
        assert announce_ball_owner_seam(steps, family="HCO/MAKE") == 0
        assert "[UESS 8.4]" not in caplog.text

    def test_poison_truncate_without_carry_fires(self, caplog):
        """Reintroduce the hop: first micro starts on the shooter."""
        steps = self._chain("PG", "SG", "SG")
        assert announce_ball_owner_seam(steps, context="HCO/MAKE", family="HCO/MAKE") == 1
        assert "[UESS 8.4] unaccounted owner change HCO/MAKE" in caplog.text


class TestMicroCarry:
    def test_carry_copies_emit_transfer_onto_first_beat(self):
        shoot = {
            "start": {
                "ball": {"owner_player_id": "passer-1"},
                "ball_motion_style": "pass",
                "ball_arrival_coord": {"x": 10.0, "y": 20.0},
            },
            "end": {"ball": {"owner_player_id": "shooter-1"}},
        }
        micros = [
            {
                "start": {"ball": {"owner_player_id": "shooter-1"}},
                "end": {"ball": {"owner_player_id": "shooter-1"}},
            }
        ]
        assert carry_sa1_pass_onto_first_micro(shoot, micros, "shooter-1") is True
        assert micros[0]["start"]["ball"]["owner_player_id"] == "passer-1"
        assert micros[0]["start"]["ball_motion_style"] == "pass"
        assert micros[0]["start"]["ball_arrival_coord"] == {"x": 10.0, "y": 20.0}
        assert micros[0]["end"]["ball"]["owner_player_id"] == "shooter-1"

    def test_carry_noop_when_emit_already_on_shooter(self):
        shoot = {"start": {"ball": {"owner_player_id": "shooter-1"}}, "end": {}}
        micros = [{"start": {"ball": {"owner_player_id": "shooter-1"}}, "end": {}}]
        assert carry_sa1_pass_onto_first_micro(shoot, micros, "shooter-1") is False

    def test_carry_noop_when_shoot_never_transferred(self):
        """Poison shape: truncate dropped the receive, emit still passer→passer."""
        shoot = {
            "start": {"ball": {"owner_player_id": "passer-1"}},
            "end": {"ball": {"owner_player_id": "passer-1"}},
        }
        micros = [
            {
                "start": {"ball": {"owner_player_id": "shooter-1"}},
                "end": {"ball": {"owner_player_id": "shooter-1"}},
            }
        ]
        assert carry_sa1_pass_onto_first_micro(shoot, micros, "shooter-1") is False
        assert micros[0]["start"]["ball"]["owner_player_id"] == "shooter-1"
