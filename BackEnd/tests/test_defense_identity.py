"""Tests for BackEnd.utils.defense_identity (Phase 1 resolver)."""

import pytest

from BackEnd.utils.defense_identity import (
    SYNTHETIC_DEFENSE_IDS,
    canonical_scouting_defense_key,
    clear_defense_identity_cache,
    defense_display_name,
    is_zone_defense_id,
    offense_vs_key_from_defense_input,
    refresh_defense_identity_cache,
    resolve_to_defense_id,
)
from BackEnd.db import defenses_collection


@pytest.fixture(autouse=True)
def _clean_defenses_and_cache():
    defenses_collection.delete_many({})
    clear_defense_identity_cache()
    yield
    defenses_collection.delete_many({})
    clear_defense_identity_cache()


def test_synthetic_ids_round_trip():
    for sid in SYNTHETIC_DEFENSE_IDS:
        assert resolve_to_defense_id(sid) == sid
    assert is_zone_defense_id("vs_Fast_Break") is False


def test_resolve_defense_id_and_name_and_oid():
    ins = defenses_collection.insert_one(
        {
            "defense_id": "2-3-zone",
            "defense_type": "Zone",
            "name": "2-3 Zone",
            "effectiveness": 0.0,
        }
    )
    refresh_defense_identity_cache()

    assert resolve_to_defense_id("2-3-zone") == "2-3-zone"
    assert resolve_to_defense_id("2-3 Zone") == "2-3-zone"
    assert resolve_to_defense_id(str(ins.inserted_id)) == "2-3-zone"
    assert defense_display_name("2-3-zone") == "2-3 Zone"
    assert is_zone_defense_id("2-3-zone") is True


def test_playbook_keys():
    defenses_collection.insert_one(
        {
            "defense_id": "man",
            "defense_type": "Man",
            "name": "Man-to-Man",
            "effectiveness": 0.0,
        }
    )
    defenses_collection.insert_one(
        {
            "defense_id": "3-2-zone",
            "defense_type": "Zone",
            "name": "3-2 Zone",
            "effectiveness": 0.0,
        }
    )
    refresh_defense_identity_cache()

    assert resolve_to_defense_id("zone_32") == "3-2-zone"
    assert resolve_to_defense_id("man_normal") == "man"


def test_legacy_man_alias_prefers_man_then_base_man():
    defenses_collection.insert_one(
        {
            "defense_id": "base-man",
            "defense_type": "Man",
            "name": "Base Man",
            "effectiveness": 0.0,
        }
    )
    refresh_defense_identity_cache()
    assert resolve_to_defense_id("Man") == "base-man"

    defenses_collection.insert_one(
        {
            "defense_id": "man",
            "defense_type": "Man",
            "name": "Man-to-Man",
            "effectiveness": 0.0,
        }
    )
    refresh_defense_identity_cache()
    assert resolve_to_defense_id("Man") == "man"


def test_zone_generic_maps_to_2_3_zone_doc():
    defenses_collection.insert_one(
        {
            "defense_id": "2-3-zone",
            "defense_type": "Zone",
            "name": "2-3 Zone",
            "effectiveness": 0.0,
        }
    )
    refresh_defense_identity_cache()
    assert resolve_to_defense_id("Zone") == "2-3-zone"


def test_unknown_returns_none():
    refresh_defense_identity_cache()
    assert resolve_to_defense_id("not-a-defense") is None
    assert resolve_to_defense_id("") is None


def test_canonical_scouting_row_key_and_vs_bucket():
    defenses_collection.insert_one(
        {
            "defense_id": "base-man",
            "defense_type": "Man",
            "name": "Base Man",
            "effectiveness": 0.0,
        }
    )
    defenses_collection.insert_one(
        {
            "defense_id": "2-3-zone",
            "defense_type": "Zone",
            "name": "2-3 Zone",
            "effectiveness": 0.0,
        }
    )
    refresh_defense_identity_cache()

    assert canonical_scouting_defense_key("base-man") == "man"
    assert canonical_scouting_defense_key("2-3-zone") == "2-3-zone"
    assert offense_vs_key_from_defense_input("Man") == "vs_man"
    assert offense_vs_key_from_defense_input("2-3 Zone") == "vs_2-3_zone"
