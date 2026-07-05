"""Made-dunk momentum (MO_DUNK_DELTA) wiring."""

from BackEnd.constants.momentum import MO_DUNK_DELTA
from BackEnd.utils.player_momentum import apply_made_dunk_momentum


class _StubPlayer:
    def __init__(self):
        self.attributes = {"MO": 0}
        self.momentum_calls = []

    def add_momentum(self, delta):
        self.momentum_calls.append(delta)
        self.attributes["MO"] += int(delta)


class TestApplyMadeDunkMomentum:
    def test_made_dunk_applies_delta(self):
        player = _StubPlayer()
        apply_made_dunk_momentum(
            player,
            made=True,
            dunk_stamp={"family_id": "dunk"},
        )
        assert player.momentum_calls == [MO_DUNK_DELTA]

    def test_made_drive_dunk_applies_delta(self):
        player = _StubPlayer()
        apply_made_dunk_momentum(
            player,
            made=True,
            dunk_stamp={"family_id": "drive_dunk"},
        )
        assert player.momentum_calls == [MO_DUNK_DELTA]

    def test_miss_does_not_apply(self):
        player = _StubPlayer()
        apply_made_dunk_momentum(
            player,
            made=False,
            dunk_stamp={"family_id": "dunk"},
        )
        assert player.momentum_calls == []

    def test_dunk_miss_stamp_does_not_apply(self):
        player = _StubPlayer()
        apply_made_dunk_momentum(
            player,
            made=True,
            dunk_stamp={"family_id": "dunk", "dunk_miss": True},
        )
        assert player.momentum_calls == []

    def test_non_dunk_family_does_not_apply(self):
        player = _StubPlayer()
        apply_made_dunk_momentum(
            player,
            made=True,
            dunk_stamp={"family_id": "strong"},
        )
        assert player.momentum_calls == []

    def test_family_id_kwarg(self):
        player = _StubPlayer()
        apply_made_dunk_momentum(player, made=True, family_id="dunk")
        assert player.momentum_calls == [MO_DUNK_DELTA]
