"""Tests for unified lineup autoset (chemistry pool sizes + payload API path)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from BackEnd.constants import ALL_ATTRS
from BackEnd.models.player import Player
from BackEnd.utils import db_utils
from BackEnd.utils.db_utils import (
    _team_chemistry_pool_sizes,
    autoset_lineup_player_ids_from_payload,
    fill_unified_lineup_gaps,
)


def _attrs(ng: float = 1.0) -> dict:
    d = {k: 50 for k in ALL_ATTRS}
    d["NG"] = ng
    return d


def _five_distinct_payload() -> list[dict]:
    """Five players, each dominant at one position (position_ratings)."""
    def row(pid: int, pos: str, rating: int = 100) -> dict:
        pr = {"PG": 1, "SG": 1, "SF": 1, "PF": 1, "C": 1}
        pr[pos] = rating
        return {
            "_id": str(pid),
            "first_name": f"First{pid}",
            "last_name": f"Last{pid}",
            "attributes": _attrs(1.0),
            "position_ratings": pr,
            "stats": {"game": {"F": 0}},
        }

    return [
        row(1, "PG"),
        row(2, "SG"),
        row(3, "SF"),
        row(4, "PF"),
        row(5, "C"),
    ]


@pytest.mark.parametrize(
    "tc,expected",
    [
        (26, [1, 1, 1, 1, 2]),  # >25 clamped
        (21, [1, 1, 1, 1, 2]),
        (20.5, [1, 1, 1, 1, 2]),
        (16, [1, 1, 1, 1, 2]),
        (15.1, [1, 1, 1, 1, 2]),
        (15, [1, 1, 1, 1, 3]),
        (11, [1, 1, 1, 1, 3]),
        (10, [1, 1, 1, 1, 3]),
        (7, [1, 1, 1, 1, 3]),
        (6, [1, 1, 1, 1, 3]),
        (0, [1, 1, 1, 1, 3]),
    ],
)
def test_team_chemistry_pool_sizes_bands(tc, expected):
    assert _team_chemistry_pool_sizes(tc) == expected


def test_team_chemistry_pool_sizes_invalid_uses_default_mid_band():
    assert _team_chemistry_pool_sizes("bogus") == [1, 1, 1, 1, 3]


def test_autoset_payload_assigns_five_deterministic_with_patched_random():
    payload = _five_distinct_payload()
    gs = {"quarter": 1, "time_remaining": 480}

    def noop_shuffle(x):
        return None

    def first_choice(seq):
        return seq[0]

    with patch.object(db_utils.random, "shuffle", noop_shuffle), patch.object(
        db_utils.random, "choice", first_choice
    ):
        lineup = autoset_lineup_player_ids_from_payload(payload, gs, team_chemistry=21.0)

    assert lineup == {"PG": "1", "SG": "2", "SF": "3", "PF": "4", "C": "5"}


def test_autoset_payload_raises_when_fewer_than_five_eligible():
    payload = []
    for i in range(5):
        payload.append(
            {
                "_id": str(i + 1),
                "first_name": f"F{i}",
                "last_name": f"L{i}",
                "attributes": _attrs(1.0),
                "position_ratings": {"PG": 50, "SG": 50, "SF": 50, "PF": 50, "C": 50},
                "stats": {"game": {"F": 5}},
            }
        )
    with pytest.raises(ValueError, match=r"(?i)fewer than 5 eligible"):
        autoset_lineup_player_ids_from_payload(
            payload, {"quarter": 1, "time_remaining": 480}, 15.0
        )


def test_autoset_uses_waterfall_when_default_ng_too_strict():
    """Four players at NG 0.9, one specialist at NG 0.5 — default Q1 threshold 0.8 drops the 0.5."""
    payload = _five_distinct_payload()
    for row in payload[:-1]:
        row["attributes"] = _attrs(0.9)
    payload[-1]["attributes"] = _attrs(0.5)

    gs = {"quarter": 1, "time_remaining": 480}

    def noop_shuffle(x):
        return None

    def first_choice(seq):
        return seq[0]

    with patch.object(db_utils.random, "shuffle", noop_shuffle), patch.object(
        db_utils.random, "choice", first_choice
    ):
        lineup = autoset_lineup_player_ids_from_payload(payload, gs, team_chemistry=15.0)

    # Without waterfall, only 4 players pass NG>=0.8; relaxed steps include 0.6 then 0.4, etc.
    assert set(lineup.values()) == {"1", "2", "3", "4", "5"}
    assert len(lineup) == 5


def test_fill_unified_lineup_gaps_respects_existing_slots():
    """One open slot (C); only the C specialist should fill it."""
    payload = _five_distinct_payload()
    players = [Player(dict(row)) for row in payload]
    existing = {
        "PG": players[0],
        "SG": players[1],
        "SF": players[2],
        "PF": players[3],
    }

    def noop_shuffle(x):
        return None

    def first_choice(seq):
        return seq[0]

    with patch.object(db_utils.random, "shuffle", noop_shuffle), patch.object(
        db_utils.random, "choice", first_choice
    ):
        filled = fill_unified_lineup_gaps(
            players,
            21.0,
            ["C"],
            existing_assignments=existing,
        )

    assert filled["C"].player_id == "5"
    assert filled["PG"] is players[0]
