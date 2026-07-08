"""Airball primary announcement payload (schema + legacy contract)."""

from BackEnd.engine.skeleton_step_emitter import _airball_announcement


def test_airball_announcement_payload_home_offense():
    turn = {
        "shot_variant": "AIRBALL",
        "result_type": "MISS",
        "shooter_id": "shooter-abc",
    }
    ann = _airball_announcement(turn, away_offense=False)
    assert ann is not None
    assert ann["text"] == "Airball!"
    assert ann["team"] == "home"
    assert ann["style"] == "primary"
    assert ann["player_data"]["playerId"] == "shooter-abc"
    assert ann.get("meta") is None


def test_airball_announcement_payload_away_offense():
    turn = {
        "shot_variant": "AIRBALL",
        "result_type": "MISS",
        "shooter_id": "shooter-xyz",
    }
    ann = _airball_announcement(turn, away_offense=True)
    assert ann is not None
    assert ann["team"] == "away"


def test_airball_announcement_skips_non_airball_and_makes():
    assert _airball_announcement(
        {"shot_variant": "CLANK", "result_type": "MISS", "shooter_id": "x"},
        away_offense=False,
    ) is None
    assert _airball_announcement(
        {"shot_variant": "AIRBALL", "result_type": "MAKE", "shooter_id": "x"},
        away_offense=False,
    ) is None
    assert _airball_announcement(
        {"shot_variant": "AIRBALL", "result_type": "MISS"},
        away_offense=False,
    ) is None


def test_airball_announcement_skips_flss_heave():
    assert _airball_announcement(
        {
            "shot_variant": "AIRBALL",
            "result_type": "MISS",
            "shooter_id": "x",
            "flss": True,
            "flss_zone": "heave",
        },
        away_offense=False,
    ) is None
