"""Team Builder Apply does not enforce per-attribute shape floors.

Capped mode still binds each player to their inherited core-12 total; redistribution
within that total (including below position floors) must Apply successfully.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.constants.team_builder_budget import CORE_12_ATTRS, core12_total
from BackEnd.constants.training_shape import CORE_12, floor_violations
from BackEnd.utils.team_builder_roster import replace_slot_roster


def _even(total: int) -> dict:
    base, rem = divmod(total, 12)
    out = {k: base for k in CORE_12_ATTRS}
    for i in range(rem):
        out[CORE_12_ATTRS[i]] += 1
    return out


def _fpd(i: int, *, attrs: dict | None = None, intent: str = "SF") -> dict:
    core = attrs or _even(420)
    full = dict(core)
    for key in CORE_12_ATTRS:
        full[f"anchor_{key}"] = full[key]
    full["CH"] = 55
    full["EM"] = 40
    full["MO"] = 0
    full["anchor_CH"] = 55
    full["anchor_EM"] = 40
    full["anchor_MO"] = 0
    return {
        "franchise_id": "fid",
        "player_id": f"old-{i}",
        "meta": {
            "first_name": f"P{i}",
            "last_name": "Floor",
            "team": "Source U",
            "team_id": "deadbeefdeadbeefdeadbeef",
            "height": 76,
            "weight": 200,
            "year": ["freshman", "sophomore", "junior", "senior"][i % 4],
            "jersey": i + 1,
            "Home Region": "A",
            "archetype": "Walk On" if i >= 12 else f"Arch{i}",
        },
        "attributes": full,
        "position_ratings": {"PG": 20, "SG": 30, "SF": 50, "PF": 40, "C": 25},
        "entry_tier": "Average",
        "position_intent": intent,
        "development": None,
    }


class TestReplaceSlotRosterNoShapeFloors(unittest.TestCase):
    def _run_replace(self, source: list[dict], rows: list[dict]):
        franchise_id = ObjectId()
        team_oid = ObjectId("deadbeefdeadbeefdeadbeef")
        old_ids = [d["player_id"] for d in source]
        for doc in source:
            doc["franchise_id"] = str(franchise_id)
        ftd_coll = MagicMock()
        ftd_coll.find_one.return_value = {"players": old_ids}
        fpd_coll = MagicMock()
        fpd_coll.find.return_value = source
        players_coll = MagicMock()
        players_coll.find_one.return_value = None
        wizard = []
        for i in range(3):
            wo = source[12 + i]
            wizard.append(
                {
                    "first_name": wo["meta"]["first_name"],
                    "last_name": wo["meta"]["last_name"],
                    "year": wo["meta"]["year"],
                    "height": wo["meta"]["height"],
                    "weight": wo["meta"]["weight"],
                    "jersey": wo["meta"]["jersey"],
                    "attributes": copy.deepcopy(wo["attributes"]),
                    "position_ratings": copy.deepcopy(wo["position_ratings"]),
                    "entry_tier": "Poor",
                    "position_intent": wo["position_intent"],
                    "development": None,
                    "Home Region": "A",
                    "archetype": "Walk On",
                }
            )
        return replace_slot_roster(
            franchise_id=franchise_id,
            team_object_id=team_oid,
            team_name="Custom U",
            roster_mode="edit",
            imported_players=rows,
            franchise_team_data_collection=ftd_coll,
            franchise_players_data_collection=fpd_coll,
            attribute_mode="capped",
            team_pool=99999,
            players_collection=players_coll,
            wizard_walk_ons=wizard,
        )

    def test_zero_edit_below_floor_inherited_passes(self):
        starved = {a: 50 for a in CORE_12}
        starved["ID"] = 8
        self.assertTrue(floor_violations("PF", starved))
        source = [_fpd(i, intent="PF" if i == 0 else "SF") for i in range(15)]
        source[0] = _fpd(0, attrs=starved, intent="PF")
        rows = []
        for i, doc in enumerate(source):
            row = {
                "first_name": doc["meta"]["first_name"],
                "last_name": doc["meta"]["last_name"],
                "class_year": ["FR", "SO", "JR", "SR"][i % 4],
                "height_in": doc["meta"]["height"],
                "jersey": doc["meta"]["jersey"],
                "attributes": {k: doc["attributes"][k] for k in CORE_12_ATTRS},
                "position_intent": doc["position_intent"],
            }
            if i >= 12:
                row["walk_on"] = True
            rows.append(row)
        _ids, docs = self._run_replace(source, rows)
        self.assertEqual(len(docs), 15)
        self.assertEqual(docs[0]["attributes"]["ID"], 8)

    def test_edit_other_attr_with_untouched_shortfall_passes(self):
        starved = {a: 50 for a in CORE_12}
        starved["ID"] = 8
        source = [_fpd(i, intent="PF" if i == 0 else "SF") for i in range(15)]
        source[0] = _fpd(0, attrs=starved, intent="PF")
        rows = []
        for i, doc in enumerate(source):
            attrs = {k: doc["attributes"][k] for k in CORE_12_ATTRS}
            if i == 0:
                attrs["SC"] = attrs["SC"] + 1
                attrs["BH"] = attrs["BH"] - 1
            row = {
                "first_name": doc["meta"]["first_name"],
                "last_name": doc["meta"]["last_name"],
                "class_year": ["FR", "SO", "JR", "SR"][i % 4],
                "height_in": doc["meta"]["height"],
                "jersey": doc["meta"]["jersey"],
                "attributes": attrs,
                "position_intent": doc["position_intent"],
            }
            if i >= 12:
                row["walk_on"] = True
            rows.append(row)
        self.assertEqual(core12_total(rows[0]["attributes"]), core12_total(starved))
        _ids, docs = self._run_replace(source, rows)
        self.assertEqual(docs[0]["attributes"]["ID"], 8)
        self.assertEqual(docs[0]["attributes"]["SC"], starved["SC"] + 1)

    def test_authoring_starved_attr_within_budget_passes(self):
        """Path that previously raised shape_floor_violation must now Apply."""
        legal = {a: 50 for a in CORE_12}
        source = [_fpd(i, attrs=dict(legal), intent="PF" if i == 0 else "SF") for i in range(15)]
        rows = []
        for i, doc in enumerate(source):
            attrs = {k: doc["attributes"][k] for k in CORE_12_ATTRS}
            if i == 0:
                # Keep core-12 total so capped force-to-budget does not rewrite ID up.
                attrs["ID"] = 8
                attrs["SC"] = 50 + 42
            row = {
                "first_name": doc["meta"]["first_name"],
                "last_name": doc["meta"]["last_name"],
                "class_year": ["FR", "SO", "JR", "SR"][i % 4],
                "height_in": doc["meta"]["height"],
                "jersey": doc["meta"]["jersey"],
                "attributes": attrs,
                "position_intent": doc["position_intent"],
            }
            if i >= 12:
                row["walk_on"] = True
            rows.append(row)
        self.assertTrue(floor_violations("PF", rows[0]["attributes"]))
        self.assertEqual(core12_total(rows[0]["attributes"]), core12_total(legal))
        _ids, docs = self._run_replace(source, rows)
        self.assertEqual(docs[0]["attributes"]["ID"], 8)
        self.assertEqual(docs[0]["attributes"]["SC"], 92)


if __name__ == "__main__":
    unittest.main()
