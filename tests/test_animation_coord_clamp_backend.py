from BackEnd.utils.shared import sanitize_turn_animation_payload


def test_sanitize_turn_animation_payload_clamps_standard_turn():
    turn = {
        "result_type": "MISS",
        "oDestinations": {"PG": {"x": 120, "y": -4}},
        "dDestinations": {"PG": {"x": -2, "y": 75}},
        "ball_spot": {"x": 500, "y": -100},
        "animations": [
            {
                "playerId": "p1",
                "end": {"x": 95, "y": 1},
                "movement": [
                    {"coords": {"x": -10, "y": 60}},
                ],
            }
        ],
    }

    out = sanitize_turn_animation_payload(turn)

    assert out["oDestinations"]["PG"] == {"x": 91.0, "y": 2.0}
    assert out["dDestinations"]["PG"] == {"x": 9.0, "y": 49.0}
    assert out["ball_spot"] == {"x": 500, "y": -100}
    assert out["animations"][0]["end"] == {"x": 91.0, "y": 2.0}
    assert out["animations"][0]["movement"][0]["coords"] == {"x": 9.0, "y": 49.0}


def test_sanitize_turn_animation_payload_keeps_exempt_turn_unclamped():
    turn = {
        "result_type": "SIDE_INBOUND",
        "oDestinations": {"PG": {"x": 2, "y": 51}},
        "ball_spot": {"x": 1, "y": 52},
        "animations": [{"movement": [{"coords": {"x": 3, "y": 50}}]}],
    }

    out = sanitize_turn_animation_payload(turn)

    assert out["oDestinations"]["PG"] == {"x": 2, "y": 51}
    assert out["ball_spot"] == {"x": 1, "y": 52}
    assert out["animations"][0]["movement"][0]["coords"] == {"x": 3, "y": 50}


def test_sanitize_turn_animation_payload_handles_batch_turns():
    turn = {
        "result_type": "BATCH",
        "batch_turns": [
            {"result_type": "MISS", "oDestinations": {"PG": {"x": 150, "y": 0}}},
            {"result_type": "TIMEOUT", "oDestinations": {"PG": {"x": 2, "y": 52}}},
        ],
    }

    out = sanitize_turn_animation_payload(turn)

    assert out["batch_turns"][0]["oDestinations"]["PG"] == {"x": 91.0, "y": 2.0}
    assert out["batch_turns"][1]["oDestinations"]["PG"] == {"x": 2, "y": 52}
