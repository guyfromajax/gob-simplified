"""§4.5b — editor is a diff, not a form (criteria 21–25)."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.constants.team_builder_budget import (
    CORE_12_ATTRS,
    capped_budget_for_inherited,
    core12_total,
)
from BackEnd.utils.team_builder_roster import (
    _budgets_for_authored_roster,
    _ordered_source_fpd,
    apply_row_diff_to_inherited,
    count_importable_players,
    replace_slot_roster,
)


def _even(total: int) -> dict:
    base, rem = divmod(total, 12)
    out = {k: base for k in CORE_12_ATTRS}
    for i in range(rem):
        out[CORE_12_ATTRS[i]] += 1
    return out


def _fpd(i: int, *, walk_on: bool = False) -> dict:
    attrs = _even(420 if not walk_on else 180)
    attrs["CH"] = 55 + i
    attrs["EM"] = 40 + i
    attrs["MO"] = 0
    attrs["anchor_CH"] = attrs["CH"]
    attrs["anchor_EM"] = attrs["EM"]
    attrs["anchor_MO"] = 0
    for key in CORE_12_ATTRS:
        attrs[f"anchor_{key}"] = attrs[key]
    year = ["freshman", "sophomore", "junior", "senior"][i % 4]
    meta = {
        "first_name": f"P{i}",
        "last_name": "Inherit",
        "team": "Source U",
        "team_id": "deadbeefdeadbeefdeadbeef",
        "height": 72 + (i % 5),
        "weight": 190,
        "year": year,
        "jersey": i + 1,
        "Home Region": ["A", "B", "C", "D", "E", "F", "G", "H"][i % 8],
        "archetype": "Walk On" if walk_on else f"Archetype{i}",
    }
    return {
        "franchise_id": "fid",
        "player_id": f"old-{i}",
        "meta": meta,
        "attributes": attrs,
        "position_ratings": {"PG": 10 + i, "SG": 20, "SF": 30, "PF": 40, "C": 50},
        "entry_tier": "Great" if not walk_on else "Poor",
        "position_intent": "SF",
        "development": {"curve": f"c{i}"} if walk_on else None,
        "photo": f"/static/images/players/p{i}.png",
        "season": {"PTS": 0},
        "career": {"PTS": 0},
    }


class TestEditorIsADiff(unittest.TestCase):
    def test_21_zero_edit_preserves_non_editor_fields(self):
        inherited = _fpd(3)
        row = {
            "first_name": "P3",
            "last_name": "Inherit",
            "class_year": "SR",  # same class as senior
            "height_in": 75,
            "weight_lb": 190,
            "jersey": 4,
            "attributes": {k: inherited["attributes"][k] for k in CORE_12_ATTRS},
        }
        out = apply_row_diff_to_inherited(
            inherited,
            row,
            team_name="Custom U",
            team_object_id=ObjectId("deadbeefdeadbeefdeadbeef"),
            attribute_mode="capped",
            budget=core12_total(inherited["attributes"]),
            apply_topup=True,
        )
        self.assertEqual(out["meta"]["Home Region"], "D")
        self.assertEqual(out["meta"]["archetype"], "Archetype3")
        self.assertEqual(out["meta"]["year"], "senior")  # exact inherited string
        self.assertEqual(out["attributes"]["CH"], inherited["attributes"]["CH"])
        self.assertEqual(out["attributes"]["EM"], inherited["attributes"]["EM"])
        self.assertEqual(out["attributes"]["MO"], 0)
        self.assertEqual(out["position_ratings"], inherited["position_ratings"])
        self.assertEqual(out["entry_tier"], "Great")
        self.assertEqual(out["photo"], inherited["photo"])
        self.assertEqual(out["meta"]["team"], "Custom U")

    def test_22_one_attr_edit_leaves_siblings_and_intangibles(self):
        inherited = _fpd(1)
        row = {
            "first_name": "P1",
            "last_name": "Inherit",
            "class_year": "SO",
            "height_in": inherited["meta"]["height"],
            "weight_lb": 190,
            "jersey": 2,
            "attributes": {k: inherited["attributes"][k] for k in CORE_12_ATTRS},
        }
        row["attributes"]["SC"] = inherited["attributes"]["SC"] + 1
        # Keep budget: drop 1 from SH so force doesn't reshuffle everything.
        row["attributes"]["SH"] = inherited["attributes"]["SH"] - 1
        out = apply_row_diff_to_inherited(
            inherited,
            row,
            team_name="Custom U",
            team_object_id=ObjectId("deadbeefdeadbeefdeadbeef"),
            attribute_mode="capped",
            budget=core12_total(inherited["attributes"]),
            apply_topup=False,
        )
        self.assertEqual(out["attributes"]["SC"], inherited["attributes"]["SC"] + 1)
        self.assertEqual(out["attributes"]["CH"], inherited["attributes"]["CH"])
        self.assertEqual(out["meta"]["Home Region"], "B")
        self.assertEqual(out["meta"]["year"], "sophomore")

    def test_24_blank_optional_csv_inherits(self):
        inherited = _fpd(2)
        row = {
            "first_name": "P2",
            "last_name": "Inherit",
            "class_year": "",  # blank → inherit
            "height_in": "",
            "weight_lb": "",
            "jersey": "",
            "attributes": {},  # blank attrs → inherit
        }
        out = apply_row_diff_to_inherited(
            inherited,
            row,
            team_name="Custom U",
            team_object_id=ObjectId("deadbeefdeadbeefdeadbeef"),
            attribute_mode="capped",
            budget=None,
            apply_topup=False,
        )
        self.assertEqual(out["meta"]["year"], "junior")
        self.assertEqual(out["meta"]["height"], inherited["meta"]["height"])
        self.assertEqual(out["meta"]["Home Region"], "C")
        self.assertEqual(out["attributes"]["SC"], inherited["attributes"]["SC"])
        self.assertEqual(out["attributes"]["CH"], inherited["attributes"]["CH"])

    def test_count_importable_allows_blank_year(self):
        rows = [
            {"first_name": f"A{i}", "last_name": "B", "class_year": "" if i else "FR"}
            for i in range(15)
        ]
        self.assertEqual(count_importable_players(rows), 15)

    def test_replace_slot_roster_edit_clones(self):
        franchise_id = ObjectId()
        team_oid = ObjectId()
        old_ids = [f"old-{i}" for i in range(15)]
        source = [_fpd(i, walk_on=(i >= 12)) for i in range(15)]
        for i, doc in enumerate(source):
            doc["player_id"] = old_ids[i]
            doc["franchise_id"] = str(franchise_id)

        ftd_coll = MagicMock()
        ftd_coll.find_one.return_value = {"players": old_ids}
        fpd_coll = MagicMock()
        fpd_coll.find.return_value = source
        players_coll = MagicMock()
        players_coll.find_one.return_value = None

        wizard = []
        for i in range(3):
            wo = _fpd(12 + i, walk_on=True)
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
                    "position_intent": "SF",
                    "development": wo["development"],
                    "Home Region": wo["meta"]["Home Region"],
                    "archetype": "Walk On",
                }
            )

        rows = []
        for i, doc in enumerate(source):
            row = {
                "first_name": doc["meta"]["first_name"],
                "last_name": doc["meta"]["last_name"],
                "class_year": ["FR", "SO", "JR", "SR"][i % 4],
                "height_in": doc["meta"]["height"],
                "weight_lb": doc["meta"]["weight"],
                "jersey": doc["meta"]["jersey"],
                "attributes": {k: doc["attributes"][k] for k in CORE_12_ATTRS},
            }
            if i >= 12:
                row["walk_on"] = True
            rows.append(row)

        new_ids, new_docs = replace_slot_roster(
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
        self.assertEqual(len(new_docs), 15)
        for i in range(12):
            self.assertEqual(new_docs[i]["meta"]["Home Region"], source[i]["meta"]["Home Region"])
            self.assertEqual(new_docs[i]["meta"]["archetype"], source[i]["meta"]["archetype"])
            self.assertEqual(new_docs[i]["meta"]["year"], source[i]["meta"]["year"])
            self.assertEqual(new_docs[i]["attributes"]["CH"], source[i]["attributes"]["CH"])
            # §4.5c: flat base-league photo paths are stripped (masters unrecolourable).
            self.assertNotIn("photo", new_docs[i])
            self.assertNotIn("photo", new_docs[i].get("meta") or {})
            # Minted ids — never the inherited base-league / init UUID.
            self.assertNotEqual(new_ids[i], old_ids[i])
        for i in range(12, 15):
            self.assertEqual(new_docs[i]["meta"]["archetype"], "Walk On")
            self.assertEqual(new_docs[i]["development"], wizard[i - 12]["development"])
            self.assertEqual(new_docs[i]["meta"]["Home Region"], wizard[i - 12]["Home Region"])
        self.assertEqual(len(new_ids), 15)
        self.assertEqual(len(set(new_ids)), 15)
        self.assertTrue(set(new_ids).isdisjoint(set(old_ids)))

    def test_replace_slot_roster_rejects_non_edit_modes(self):
        franchise_id = ObjectId()
        team_oid = ObjectId()
        ftd_coll = MagicMock()
        ftd_coll.find_one.return_value = {"players": [f"old-{i}" for i in range(15)]}
        fpd_coll = MagicMock()
        fpd_coll.find.return_value = []
        for mode in ("keep", "generate", "KEEP", "Generate", "import", "IMPORT"):
            with self.assertRaises(ValueError) as ctx:
                replace_slot_roster(
                    franchise_id=franchise_id,
                    team_object_id=team_oid,
                    team_name="Custom U",
                    roster_mode=mode,
                    imported_players=None,
                    franchise_team_data_collection=ftd_coll,
                    franchise_players_data_collection=fpd_coll,
                    attribute_mode="capped",
                )
            self.assertTrue(str(ctx.exception).startswith("roster_mode_invalid:"))
            fpd_coll.insert_many.assert_not_called()

    def test_edit_capped_topup_applies_universally(self):
        """§4.5c: capped top-up is not exempted — below-floor attrs rise to 60."""
        franchise_id = ObjectId()
        team_oid = ObjectId()
        old_ids = [f"old-{i}" for i in range(15)]
        source = [_fpd(i, walk_on=(i >= 12)) for i in range(15)]
        for key in CORE_12_ATTRS:
            source[0]["attributes"][key] = 1
            source[0]["attributes"][f"anchor_{key}"] = 1
        for i, doc in enumerate(source):
            doc["player_id"] = old_ids[i]
            doc["franchise_id"] = str(franchise_id)

        ftd_coll = MagicMock()
        ftd_coll.find_one.return_value = {"players": old_ids}
        fpd_coll = MagicMock()
        fpd_coll.find.return_value = source
        players_coll = MagicMock()
        players_coll.find_one.return_value = None

        rows = []
        for i, doc in enumerate(source):
            row = {
                "first_name": doc["meta"]["first_name"],
                "last_name": doc["meta"]["last_name"],
                "class_year": ["FR", "SO", "JR", "SR"][i % 4],
                "height_in": doc["meta"]["height"],
                "weight_lb": doc["meta"]["weight"],
                "jersey": doc["meta"]["jersey"],
                "attributes": {k: doc["attributes"][k] for k in CORE_12_ATTRS},
            }
            if i >= 12:
                row["walk_on"] = True
            rows.append(row)

        _new_ids, new_docs = replace_slot_roster(
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
            wizard_walk_ons=None,
        )
        self.assertGreaterEqual(core12_total(new_docs[0]["attributes"]), 60)

    def test_portrait_ref_image_id_survives_strip(self):
        """meta.image_id is the kit key; flat photo is dropped (§4.5c / Decision #34)."""
        franchise_id = ObjectId()
        team_oid = ObjectId()
        old_ids = [f"old-{i}" for i in range(15)]
        source = [_fpd(i, walk_on=(i >= 12)) for i in range(15)]
        kit_id = "builder_set_0001/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        for i, doc in enumerate(source):
            doc["player_id"] = old_ids[i]
            doc["franchise_id"] = str(franchise_id)
            if i == 0:
                doc["meta"]["image_id"] = kit_id

        ftd_coll = MagicMock()
        ftd_coll.find_one.return_value = {"players": old_ids}
        fpd_coll = MagicMock()
        fpd_coll.find.return_value = source
        players_coll = MagicMock()
        players_coll.find_one.return_value = None

        rows = []
        for i, doc in enumerate(source):
            row = {
                "first_name": doc["meta"]["first_name"],
                "last_name": doc["meta"]["last_name"],
                "class_year": ["FR", "SO", "JR", "SR"][i % 4],
                "height_in": doc["meta"]["height"],
                "weight_lb": doc["meta"]["weight"],
                "jersey": doc["meta"]["jersey"],
                "attributes": {k: doc["attributes"][k] for k in CORE_12_ATTRS},
            }
            if i >= 12:
                row["walk_on"] = True
            rows.append(row)

        _new_ids, new_docs = replace_slot_roster(
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
            wizard_walk_ons=None,
        )
        self.assertEqual(new_docs[0]["meta"].get("image_id"), kit_id)
        self.assertNotIn("photo", new_docs[0])
        self.assertNotIn("photo", new_docs[0].get("meta") or {})


class TestCriterion25ShuffledFindOrder(unittest.TestCase):
    """
    Criterion 25 / Decision #29: budgets bind by player_id identity.

    A fixture whose find() order happens to match FTD order cannot catch this.
    Construct a deliberate mismatch, prove the naive ordinal path fails, then
    prove replace_slot_roster still binds each budget to the right player.
    """

    def _roster_with_distinct_budgets(self):
        # Widely spaced totals so a wrong ordinal cannot accidentally pass.
        # Non-monotonic player_id labels so sorting by player_id != FTD order.
        totals = [300 + i * 25 for i in range(12)] + [160, 185, 210]
        # Intentionally NOT alphabetical / numeric — sorting by player_id
        # must not recreate FTD roster order.
        roster_ids = [f"pid-{n}" for n in (
            "zulu", "yankee", "xray", "whiskey", "victor", "uniform",
            "tango", "sierra", "romeo", "quebec", "papa", "oscar",
            "november", "mike", "lima",
        )]
        docs = []
        for i, (pid, total) in enumerate(zip(roster_ids, totals)):
            attrs = _even(total)
            for key in CORE_12_ATTRS:
                attrs[f"anchor_{key}"] = attrs[key]
            attrs["CH"] = 10 + i
            attrs["EM"] = 20 + i
            attrs["MO"] = 0
            docs.append(
                {
                    "franchise_id": "fid",
                    "player_id": pid,
                    "meta": {
                        "first_name": f"Slot{i}",
                        "last_name": "Bind",
                        "team": "Source U",
                        "team_id": "deadbeefdeadbeefdeadbeef",
                        "height": 72,
                        "weight": 190,
                        "year": "junior",
                        "jersey": 50 - i,  # descending — jersey sort != roster order
                        "archetype": "Walk On" if i >= 12 else f"Arch{i}",
                        "Home Region": "A",
                    },
                    "attributes": attrs,
                    "position_ratings": {"SF": 40},
                    "entry_tier": "Average",
                    "position_intent": "SF",
                }
            )
        return roster_ids, totals, docs

    def test_25_naive_find_order_budgets_are_wrong(self):
        """Without identity map, shuffled find() order mis-assigns budgets."""
        roster_ids, totals, docs = self._roster_with_distinct_budgets()
        shuffled = list(reversed(docs))
        self.assertNotEqual(
            [d["player_id"] for d in shuffled],
            roster_ids,
            "fixture must disagree with FTD order",
        )
        naive = _budgets_for_authored_roster(
            attr_mode="capped",
            source_fpd=shuffled,
            imported_players=None,
            explicit_budgets=None,
            ordered_fpd=None,  # legacy ordinal over find() result
        )
        expected = [capped_budget_for_inherited(t) for t in totals]
        self.assertNotEqual(
            naive,
            expected,
            "naive find()-order budgets must diverge — otherwise the fixture is weak",
        )

    def test_25_identity_map_is_not_a_sort(self):
        roster_ids, _totals, docs = self._roster_with_distinct_budgets()
        shuffled = list(reversed(docs))
        ordered = _ordered_source_fpd(shuffled, roster_ids)
        self.assertEqual([d["player_id"] for d in ordered], roster_ids)
        # Sorting the query result by player_id or jersey is not FTD order.
        self.assertNotEqual(
            [d["player_id"] for d in sorted(shuffled, key=lambda d: d["player_id"])],
            roster_ids,
        )
        self.assertNotEqual(
            [d["player_id"] for d in sorted(shuffled, key=lambda d: d["meta"]["jersey"])],
            roster_ids,
        )

    def test_25_capped_edit_binds_budget_by_player_id_under_shuffled_find(self):
        franchise_id = ObjectId()
        team_oid = ObjectId()
        roster_ids, totals, docs = self._roster_with_distinct_budgets()
        for d in docs:
            d["franchise_id"] = str(franchise_id)

        # Deliberate non-roster find() order.
        find_order = list(reversed(docs[0:15:2] + docs[1:15:2]))
        self.assertNotEqual([d["player_id"] for d in find_order], roster_ids)

        ftd_coll = MagicMock()
        ftd_coll.find_one.return_value = {"players": roster_ids}
        fpd_coll = MagicMock()
        fpd_coll.find.return_value = find_order
        players_coll = MagicMock()
        players_coll.find_one.return_value = None

        expected_budgets = [capped_budget_for_inherited(t) for t in totals]
        rows = []
        for i, doc in enumerate(docs):
            row = {
                "first_name": doc["meta"]["first_name"],
                "last_name": doc["meta"]["last_name"],
                "class_year": "JR",
                "height_in": 72,
                "weight_lb": 190,
                "jersey": doc["meta"]["jersey"],
                "walk_on": i >= 12,
            }
            if i < 12:
                # Restate inherited core-12 (identity still binds budgets).
                row["attributes"] = {k: doc["attributes"][k] for k in CORE_12_ATTRS}
            else:
                # Blank -> inherit walk-on budget from identity-mapped FPD.
                row["attributes"] = {}
            rows.append(row)

        _new_ids, new_docs = replace_slot_roster(
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
            wizard_walk_ons=None,
        )

        shipped = [core12_total(d["attributes"]) for d in new_docs]
        self.assertEqual(shipped, expected_budgets)

        for i, doc in enumerate(new_docs):
            self.assertEqual(doc["meta"]["first_name"], f"Slot{i}")
            self.assertEqual(doc["attributes"]["CH"], 10 + i)


if __name__ == "__main__":
    unittest.main()
