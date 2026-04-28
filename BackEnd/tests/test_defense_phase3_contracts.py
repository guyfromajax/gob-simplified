"""
Phase 3 contracts: values shaped like API / game_state → scouting row keys & zone detection.

Guards sim paths (e.g. shot_manager rebound weighting) that rely on defense_playcall slugs
and is_zone_defense() after the defense_id migration.
"""

import pytest

from BackEnd.db import defenses_collection
from BackEnd.utils.defense_identity import (
    clear_defense_identity_cache,
    defense_scouting_row_key,
    refresh_defense_identity_cache,
)
from BackEnd.utils.defense_utils import is_zone_defense


@pytest.fixture(autouse=True)
def _clean_defenses_and_cache():
    defenses_collection.delete_many({})
    clear_defense_identity_cache()
    yield
    defenses_collection.delete_many({})
    clear_defense_identity_cache()


def _seed_hco_catalog():
    for doc in (
        {"defense_id": "man", "defense_type": "Man", "name": "Man-to-Man", "effectiveness": 0.0},
        {"defense_id": "2-3-zone", "defense_type": "Zone", "name": "2-3 Zone", "effectiveness": 0.0},
        {"defense_id": "3-2-zone", "defense_type": "Zone", "name": "3-2 Zone", "effectiveness": 0.0},
        {"defense_id": "1-3-1-zone", "defense_type": "Zone", "name": "1-3-1 Zone", "effectiveness": 0.0},
    ):
        defenses_collection.insert_one(doc)
    refresh_defense_identity_cache()


def test_defense_scouting_row_key_api_and_game_state_shapes():
    _seed_hco_catalog()
    assert defense_scouting_row_key("2-3-zone") == "2-3-zone"
    assert defense_scouting_row_key("2-3 Zone") == "2-3-zone"
    assert defense_scouting_row_key("man") == "man"
    assert defense_scouting_row_key("man_normal") == "man"
    assert defense_scouting_row_key("zone_23") == "2-3-zone"
    assert defense_scouting_row_key("zone_32") == "3-2-zone"


def test_is_zone_defense_slug_and_legacy_for_shot_math():
    _seed_hco_catalog()
    assert is_zone_defense("2-3-zone") is True
    assert is_zone_defense("3-2-zone") is True
    assert is_zone_defense("1-3-1-zone") is True
    assert is_zone_defense("man") is False
    assert is_zone_defense("man_normal") is False
    assert is_zone_defense("2-3 Zone") is True
    assert is_zone_defense("Zone") is True
