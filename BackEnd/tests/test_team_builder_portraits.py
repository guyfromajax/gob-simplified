"""Phase 3d §6.5 — fitted assignment, relaxation order, seed stability."""
from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.constants.team_builder_budget import CORE_12_ATTRS
from BackEnd.utils.team_builder_portraits import (
    assign_fitted_image,
    assign_roster_portraits,
    catalog_for_picker,
    classify_team_builder_player,
    get_or_create_wizard_portraits,
    load_tb_portrait_pool,
    measure_exact_match_rate,
    resolve_kit_keys,
)
from BackEnd.utils.team_builder_roster import replace_slot_roster


def _attrs(total: int = 420) -> dict:
    base, rem = divmod(total, 12)
    out = {k: base for k in CORE_12_ATTRS}
    for i in range(rem):
        out[CORE_12_ATTRS[i]] += 1
    # Force Cut-ish definition via ST/AG/RT path (rt from position ratings).
    out["ST"] = 70
    out["AG"] = 50
    return out


def _player(**kwargs):
    pid = kwargs.get("player_id") or str(uuid.uuid4())
    return {
        "player_id": pid,
        "first_name": kwargs.get("first_name", "Marcus"),
        "last_name": kwargs.get("last_name", "Johnson"),
        "height_in": kwargs.get("height_in", 78),
        "weight_lb": kwargs.get("weight_lb", 250),
        "attributes": kwargs.get("attributes") or _attrs(),
        "class_year": "JR",
    }


class TestTbPortraitPool(unittest.TestCase):
    def test_pool_is_recruit_union_builder(self):
        pool = load_tb_portrait_pool()
        self.assertEqual(len(pool), 450)
        sets = {e["set_id"] for e in pool}
        self.assertIn("recruit_set_0001", sets)
        self.assertIn("builder_set_0001", sets)

    def test_exact_match_rate_near_99_2(self):
        result = measure_exact_match_rate()
        self.assertEqual(result["pool_size"], 450)
        self.assertEqual(result["league_players"], 1536)
        self.assertGreaterEqual(result["exact_match_pct"], 99.0)
        self.assertLessEqual(result["exact_match_pct"], 99.5)

    def test_resolve_kit_keys_builder_prefix(self):
        pool = load_tb_portrait_pool()
        builder = next(e for e in pool if e["set_id"] == "builder_set_0001")
        kit, mask = resolve_kit_keys(builder["image_id"])
        self.assertTrue(kit.startswith("portrait-kits/builder_set_0001/"))
        self.assertTrue(mask.endswith(".mask.png"))

    def test_resolve_kit_keys_recruit_prefix(self):
        pool = load_tb_portrait_pool()
        recruit = next(e for e in pool if e["set_id"] == "recruit_set_0001")
        kit, _mask = resolve_kit_keys(recruit["image_id"])
        self.assertTrue(kit.startswith("recruits/kit/"))


class TestRelaxationOrder(unittest.TestCase):
    def test_hold_frame_relax_skin_family_before_definition(self):
        """Sparse cell: exact missing → family skin at same frame+def before def relax."""
        pool = [
            {
                "image_id": "fam-1",
                "set_id": "t",
                "kit_prefix": "x",
                "frame": "Broad",
                "definition": "Toned",
                "skin": "black-light",
            },
            {
                "image_id": "def-1",
                "set_id": "t",
                "kit_prefix": "x",
                "frame": "Broad",
                "definition": "Cut",
                "skin": "black-normal",
            },
            {
                "image_id": "frame-other",
                "set_id": "t",
                "kit_prefix": "x",
                "frame": "Lean",
                "definition": "Toned",
                "skin": "black-normal",
            },
        ]
        target = {
            "player_id": "seed-1",
            "frame": "Broad",
            "definition": "Toned",
            "skin": "black-normal",
            "race": "black",
        }
        result = assign_fitted_image(target, pool=pool)
        self.assertEqual(result["image_id"], "fam-1")
        self.assertEqual(result["match_stage"], "frame_def_family")

    def test_relax_definition_before_frame(self):
        pool = [
            {
                "image_id": "def-relax",
                "set_id": "t",
                "kit_prefix": "x",
                "frame": "Broad",
                "definition": "Soft",
                "skin": "black-normal",
            },
            {
                "image_id": "frame-relax",
                "set_id": "t",
                "kit_prefix": "x",
                "frame": "Normal",
                "definition": "Toned",
                "skin": "black-normal",
            },
        ]
        target = {
            "player_id": "seed-2",
            "frame": "Broad",
            "definition": "Toned",
            "skin": "black-normal",
            "race": "black",
        }
        result = assign_fitted_image(target, pool=pool)
        self.assertEqual(result["image_id"], "def-relax")
        self.assertEqual(result["match_stage"], "frame_skin")

    def test_quality_beats_uniqueness(self):
        pool = [
            {
                "image_id": "only-exact",
                "set_id": "t",
                "kit_prefix": "x",
                "frame": "Broad",
                "definition": "Toned",
                "skin": "black-normal",
            },
            {
                "image_id": "worse",
                "set_id": "t",
                "kit_prefix": "x",
                "frame": "Lean",
                "definition": "Toned",
                "skin": "black-normal",
            },
        ]
        target = {
            "player_id": "seed-3",
            "frame": "Broad",
            "definition": "Toned",
            "skin": "black-normal",
            "race": "black",
        }
        result = assign_fitted_image(target, used_ids={"only-exact"}, pool=pool)
        self.assertEqual(result["image_id"], "only-exact")
        self.assertTrue(result["duplicate_allowed"])


class TestSeedStability(unittest.TestCase):
    def test_wizard_portraits_idempotent_across_calls(self):
        db = MagicMock()
        stored = {}

        def find_one(query, proj=None):
            key = (query["user_id"], query["draft_id"], query["replaced_object_id"])
            doc = stored.get(key)
            if not doc:
                return None
            if proj and "portraits" in proj:
                return {"portraits": doc["portraits"]}
            return doc

        def update_one(query, update, upsert=False):
            key = (query["user_id"], query["draft_id"], query["replaced_object_id"])
            portraits = update["$set"]["portraits"]
            stored[key] = {"portraits": portraits}

        col = MagicMock()
        col.find_one.side_effect = find_one
        col.update_one.side_effect = update_one
        db.__getitem__.return_value = col

        players = [_player(first_name=f"P{i}", player_id="") for i in range(15)]
        # Distinct heights so classification still runs.
        for i, p in enumerate(players):
            p["height_in"] = 72 + (i % 6)
            p["weight_lb"] = 190 + i * 3
            p["player_id"] = None

        a = get_or_create_wizard_portraits(
            db,
            user_id="u1",
            replaced_object_id="slot1",
            draft_id="draft-abcdef01",
            players=players,
        )
        b = get_or_create_wizard_portraits(
            db,
            user_id="u1",
            replaced_object_id="slot1",
            draft_id="draft-abcdef01",
            players=players,
        )
        self.assertEqual(len(a), 15)
        self.assertEqual(
            [(x["player_id"], x["image_id"]) for x in a],
            [(x["player_id"], x["image_id"]) for x in b],
        )

    def test_apply_reuses_wizard_player_id_and_image_id(self):
        franchise_id = ObjectId()
        team_oid = ObjectId()
        old_ids = [f"old-{i}" for i in range(15)]
        source = []
        for i in range(15):
            attrs = _attrs(400 if i < 12 else 180)
            for key in CORE_12_ATTRS:
                attrs[f"anchor_{key}"] = attrs[key]
            source.append(
                {
                    "franchise_id": str(franchise_id),
                    "player_id": old_ids[i],
                    "meta": {
                        "first_name": f"P{i}",
                        "last_name": "Ship",
                        "team": "Source U",
                        "team_id": str(team_oid),
                        "height": 74,
                        "weight": 200,
                        "year": "junior",
                        "jersey": i + 1,
                        "Home Region": "A",
                        "archetype": "Walk On" if i >= 12 else "Athlete",
                    },
                    "attributes": attrs,
                    "position_ratings": {"SF": 50},
                    "entry_tier": "Great",
                    "position_intent": "SF",
                }
            )
        ftd = MagicMock()
        ftd.find_one.return_value = {"players": old_ids}
        fpd = MagicMock()
        fpd.find.return_value = source
        players_coll = MagicMock()
        players_coll.find_one.return_value = None

        minted = [str(uuid.uuid4()) for _ in range(15)]
        images = [e["image_id"] for e in load_tb_portrait_pool()[:15]]
        rows = []
        for i, doc in enumerate(source):
            rows.append(
                {
                    "first_name": doc["meta"]["first_name"],
                    "last_name": doc["meta"]["last_name"],
                    "class_year": "JR",
                    "height_in": 74,
                    "weight_lb": 200,
                    "jersey": i + 1,
                    "attributes": {k: doc["attributes"][k] for k in CORE_12_ATTRS},
                    "player_id": minted[i],
                    "image_id": images[i],
                    "walk_on": i >= 12,
                }
            )

        new_ids, new_docs = replace_slot_roster(
            franchise_id=franchise_id,
            team_object_id=team_oid,
            team_name="Custom U",
            roster_mode="edit",
            imported_players=rows,
            franchise_team_data_collection=ftd,
            franchise_players_data_collection=fpd,
            attribute_mode="capped",
            team_pool=99999,
            players_collection=players_coll,
            wizard_walk_ons=None,
        )
        self.assertEqual(new_ids, minted)
        for i, doc in enumerate(new_docs):
            self.assertEqual(doc["player_id"], minted[i])
            self.assertEqual(doc["meta"]["image_id"], images[i])
            self.assertNotIn("photo", doc)


class TestPickerCatalog(unittest.TestCase):
    def test_counts_present_before_filter(self):
        catalog = catalog_for_picker()
        self.assertEqual(catalog["total"], 450)
        self.assertTrue(catalog["counts"]["skin"])
        self.assertTrue(catalog["counts"]["frame"])
        self.assertIsNone(catalog["empty_reason"])

    def test_empty_filter_explains(self):
        catalog = catalog_for_picker(skin="not-a-real-skin")
        self.assertEqual(catalog["filtered_count"], 0)
        self.assertIn("No portraits match", catalog["empty_reason"] or "")


class TestClassifierReuse(unittest.TestCase):
    def test_classify_uses_existing_pipeline(self):
        target = classify_team_builder_player(_player())
        self.assertIsNotNone(target)
        self.assertIn(target["frame"], ("Slight", "Lean", "Normal", "Broad", "Doughy"))
        self.assertIn(target["definition"], ("Cut", "Toned", "Soft"))
        self.assertTrue(target["skin"])


if __name__ == "__main__":
    unittest.main()
