"""Tests for PGPC session question selection (vanilla cap + count range)."""

import random
from unittest.mock import patch

from BackEnd.pgpc_selection import (
    _weighted_sample_without_replacement,
    select_pgpc_questions_for_session,
    shuffle_answers_for_display,
)


def _q(cond: str, qid: str) -> dict:
    return {"id": qid, "trigger": {"condition": cond, "filters": {}}, "answers": []}


def test_shuffle_answers_shows_at_most_four_after_shuffle():
    q = {
        "id": "q1",
        "text": "Q?",
        "answers": [
            {"letter": "A", "text": "t1", "archetype": "x1"},
            {"letter": "B", "text": "t2", "archetype": "x2"},
            {"letter": "C", "text": "t3", "archetype": "x3"},
            {"letter": "D", "text": "t4", "archetype": "x4"},
            {"letter": "E", "text": "t5", "archetype": "x5"},
        ],
    }
    rng = random.Random(0)
    out = shuffle_answers_for_display(q, rng)
    assert len(out["answers"]) == 4
    assert {a["letter"] for a in out["answers"]} == {"A", "B", "C", "D"}

    q3 = {"id": "q2", "text": "Q2?", "answers": q["answers"][:3]}
    out3 = shuffle_answers_for_display(q3, random.Random(1))
    assert len(out3["answers"]) == 3


def test_weighted_sampling_favors_higher_weight():
    light = _q("win", "light")
    light["weight"] = 1
    heavy = _q("win", "heavy")
    heavy["weight"] = 50
    qualified = [light, heavy]
    rng = random.Random(12345)
    heavy_hits = 0
    for _ in range(500):
        sel = _weighted_sample_without_replacement(qualified, 1, rng)
        if sel and sel[0]["id"] == "heavy":
            heavy_hits += 1
    assert heavy_hits > 400


def test_selection_count_between_6_and_8():
    qualified = [_q("win", f"w{i}") for i in range(40)]
    qualified += [_q("always", f"a{i}") for i in range(20)]
    rng = random.Random(42)
    for _ in range(30):
        sel = select_pgpc_questions_for_session(qualified, rng=rng)
        assert 6 <= len(sel) <= 8


def test_no_vanilla_when_specific_pool_covers_target():
    qualified = [_q("win", f"w{i}") for i in range(30)] + [_q("always", "a0")]
    rng = random.Random(0)
    for _ in range(40):
        sel = select_pgpc_questions_for_session(qualified, rng=rng)
        assert all(q["trigger"]["condition"] != "always" for q in sel)


def test_first_wave_adds_at_most_three_vanilla():
    specifics = [_q("win", f"w{i}") for i in range(5)]
    vanilla = [_q("always", f"a{i}") for i in range(20)]
    qualified = specifics + vanilla
    rng = random.Random(99)
    with patch.object(rng, "randint", return_value=8):
        sel = select_pgpc_questions_for_session(qualified, rng=rng)
    assert len(sel) == 8
    vanilla_ids = {q["id"] for q in sel if q["trigger"]["condition"] == "always"}
    specific_ids = {q["id"] for q in sel if q["trigger"]["condition"] != "always"}
    assert len(specific_ids) == 5
    assert len(vanilla_ids) == 3


def test_session_length_never_exceeds_qualified_pool():
    qualified = [_q("win", f"w{i}") for i in range(5)]
    rng = random.Random(2)
    with patch.object(rng, "randint", return_value=8):
        sel = select_pgpc_questions_for_session(qualified, rng=rng)
    assert len(sel) == 5


def test_padding_adds_extra_vanilla_beyond_three_when_pool_is_tiny():
    specifics = [_q("win", "w1"), _q("win", "w2")]
    vanilla = [_q("always", f"a{i}") for i in range(25)]
    qualified = specifics + vanilla
    rng = random.Random(1)
    with patch.object(rng, "randint", return_value=8):
        sel = select_pgpc_questions_for_session(qualified, rng=rng)
    assert len(sel) == 8
    v_count = sum(1 for q in sel if q["trigger"]["condition"] == "always")
    assert v_count == 6
