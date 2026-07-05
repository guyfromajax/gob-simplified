"""Integration: made-dunk MO aligns with stamped micro_movement_family."""

from BackEnd.constants.momentum import MO_DUNK_DELTA
from BackEnd.engine.shot_micro_movements import select_and_stamp_shot_micro
from BackEnd.utils.player_momentum import apply_made_dunk_momentum


class _StubPlayer:
    def __init__(self):
        self.attributes = {"MO": 0}
        self.momentum_calls = []

    def add_momentum(self, delta):
        self.momentum_calls.append(delta)
        self.attributes["MO"] += int(delta)


class TestMadeDunkMomentumIntegration:
    def test_apply_after_select_matches_stamped_family(self):
        player = _StubPlayer()
        turn = {}
        select_and_stamp_shot_micro(
            turn,
            shot_type="inside",
            shooter_id="s1",
            shooter_x=85.0,
            shooter_y=25.0,
            off_lineup={},
            def_lineup={},
            has_contest=False,
            contest_result=None,
            contest_margin=None,
            shot_defense_score_raw=0.0,
            dunk_stamp={"family_id": "dunk", "dunk_miss": False, "force_miss": False},
            dunk_resolved=True,
        )
        apply_made_dunk_momentum(
            player,
            made=True,
            family_id=turn.get("micro_movement_family"),
        )
        assert turn["micro_movement_family"] == "dunk"
        assert player.momentum_calls == [MO_DUNK_DELTA]

    def test_apply_after_select_skips_non_dunk_family(self):
        player = _StubPlayer()
        turn = {}
        select_and_stamp_shot_micro(
            turn,
            shot_type="inside",
            shooter_id="s1",
            shooter_x=85.0,
            shooter_y=25.0,
            off_lineup={},
            def_lineup={},
            has_contest=False,
            contest_result=None,
            contest_margin=None,
            shot_defense_score_raw=0.0,
            dunk_stamp=None,
            dunk_resolved=True,
        )
        apply_made_dunk_momentum(
            player,
            made=True,
            family_id=turn.get("micro_movement_family"),
        )
        assert player.momentum_calls == []
