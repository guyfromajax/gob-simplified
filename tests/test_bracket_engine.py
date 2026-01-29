"""Unit tests for shared bracket_engine (Tournament / EOS)."""
import pytest

from BackEnd.tournament.bracket_engine import (
    advance_bracket,
    generate_bracket,
    get_round_name,
    save_game_result,
)


def test_get_round_name():
    assert get_round_name(1) == "round1"
    assert get_round_name(2) == "round2"
    assert get_round_name(3) == "final"
    assert get_round_name(0) == "round1"


def test_generate_bracket_requires_8():
    with pytest.raises(ValueError, match="8 teams"):
        generate_bracket(["a", "b", "c"])


def test_generate_bracket_shape():
    ids = [f"tid{i}" for i in range(8)]
    b = generate_bracket(ids)
    assert list(b.keys()) == ["round1", "round2", "final"]
    assert len(b["round1"]) == 4
    assert len(b["round2"]) == 0
    assert len(b["final"]) == 0
    for m in b["round1"]:
        assert "home_team" in m and "away_team" in m and "winner" in m and "game_id" in m


def test_generate_bracket_1v8_4v5_2v7_3v6():
    ids = [f"tid{i}" for i in range(8)]
    b = generate_bracket(ids)
    # 1v8, 4v5, 2v7, 3v6
    expect = [(ids[0], ids[7]), (ids[3], ids[4]), (ids[1], ids[6]), (ids[2], ids[5])]
    for i, (h, a) in enumerate(expect):
        assert b["round1"][i]["home_team"] == h and b["round1"][i]["away_team"] == a


def test_save_game_result():
    ids = [f"tid{i}" for i in range(8)]
    b = generate_bracket(ids)
    save_game_result(b, 1, 0, "g1", "tid0", {"tid0": 80, "tid7": 70})
    assert b["round1"][0]["game_id"] == "g1"
    assert b["round1"][0]["winner"] == "tid0"
    assert b["round1"][0]["score"] == {"tid0": 80, "tid7": 70}


def test_advance_bracket_round1_to_2():
    ids = [f"tid{i}" for i in range(8)]
    b = generate_bracket(ids)
    for i, w in enumerate(["tid0", "tid4", "tid1", "tid2"]):
        save_game_result(b, 1, i, f"g{i}", w)
    bracket, r, done, champ = advance_bracket(b, 1, winners_from_matchups=True)
    assert r == 2
    assert done is False
    assert champ is None
    assert len(bracket["round2"]) == 2
    assert bracket["round2"][0]["home_team"] == "tid0" and bracket["round2"][0]["away_team"] == "tid4"
    assert bracket["round2"][1]["home_team"] == "tid1" and bracket["round2"][1]["away_team"] == "tid2"


def test_advance_bracket_round2_to_3():
    ids = [f"tid{i}" for i in range(8)]
    b = generate_bracket(ids)
    for i, w in enumerate(["tid0", "tid4", "tid1", "tid2"]):
        save_game_result(b, 1, i, f"g{i}", w)
    advance_bracket(b, 1, winners_from_matchups=True)
    save_game_result(b, 2, 0, "s0", "tid0")
    save_game_result(b, 2, 1, "s1", "tid1")
    bracket, r, done, champ = advance_bracket(b, 2, winners_from_matchups=True)
    assert r == 3
    assert done is False
    assert champ is None
    assert len(bracket["final"]) == 1
    assert bracket["final"][0]["home_team"] == "tid0" and bracket["final"][0]["away_team"] == "tid1"


def test_advance_bracket_final_complete():
    ids = [f"tid{i}" for i in range(8)]
    b = generate_bracket(ids)
    for i, w in enumerate(["tid0", "tid4", "tid1", "tid2"]):
        save_game_result(b, 1, i, f"g{i}", w)
    advance_bracket(b, 1, winners_from_matchups=True)
    save_game_result(b, 2, 0, "s0", "tid0")
    save_game_result(b, 2, 1, "s1", "tid1")
    advance_bracket(b, 2, winners_from_matchups=True)
    save_game_result(b, 3, 0, "f0", "tid0")
    bracket, r, done, champ = advance_bracket(b, 3, winners_from_matchups=True)
    assert r == 3
    assert done is True
    assert champ == "tid0"
