"""Walk-on jersey + portrait assignment when surviving onto the active 12."""
from __future__ import annotations

import random
import unittest
from unittest.mock import MagicMock

from BackEnd.utils.jersey_assignment import (
    allowed_jersey_numbers,
    jersey_position_for_player,
    pick_jersey_number,
)
from BackEnd.utils.team_builder_portraits import resolve_kit_keys
from BackEnd.utils.walk_on_portraits import (
    FRANCHISE_USED_FIELD,
    pick_walk_on_image_id,
    walk_on_image_ids,
)
from BackEnd.utils.walk_on_roster_identity import assign_walk_ons_making_active_roster


class JerseyHelperTests(unittest.TestCase):
    def test_position_intent_preferred_over_best_rt(self):
        player = {
            "position_intent": "PG",
            "pos": "C",
            "position_ratings": {"PG": 40, "C": 90},
        }
        self.assertEqual(jersey_position_for_player(player), "PG")

    def test_pick_excludes_taken_then_wraps(self):
        rng = random.Random(1)
        pool = allowed_jersey_numbers("PG")
        taken = set(pool)
        # Full pool exhausted → still returns a legal PG number.
        n = pick_jersey_number("PG", taken, rng=rng)
        self.assertIn(n, pool)


class WalkOnPortraitPoolTests(unittest.TestCase):
    def test_manifest_has_71_unique_ids(self):
        ids = walk_on_image_ids()
        self.assertEqual(len(ids), 71)
        self.assertEqual(len(set(ids)), 71)

    def test_resolve_kit_keys_walk_on_prefix(self):
        iid = walk_on_image_ids()[0]
        kit, mask = resolve_kit_keys(iid)
        self.assertTrue(kit.startswith("portrait-kits/walk_on_portraits/"))
        self.assertTrue(mask.endswith(".mask.png"))
        self.assertIn(iid, kit)

    def test_pick_avoids_used_until_exhausted(self):
        rng = random.Random(0)
        ids = list(walk_on_image_ids())
        used = ids[:-1]
        pick = pick_walk_on_image_id(used, rng=rng)
        self.assertEqual(pick, ids[-1])
        # Exhausted → reuse allowed
        pick2 = pick_walk_on_image_id(ids, rng=rng)
        self.assertIn(pick2, ids)


class AssignWalkOnRosterTests(unittest.TestCase):
    def test_assigns_jersey_and_image_skips_when_present(self):
        rng = random.Random(42)
        fpd_col = MagicMock()
        fran_col = MagicMock()
        fran_col.find_one.return_value = {FRANCHISE_USED_FIELD: []}

        walk_need = {
            "meta": {"archetype": "Walk On", "jersey": None},
            "position_intent": "SG",
            "position_ratings": {"SG": 50, "PG": 40},
        }
        walk_has = {
            "meta": {
                "archetype": "Walk On",
                "jersey": 12,
                "image_id": "already-set",
            },
            "position_intent": "PG",
        }
        pool = {
            "meta": {"archetype": "Scorer", "jersey": 5},
            "position_intent": "SF",
        }
        fpd_map = {
            "w1": walk_need,
            "w2": walk_has,
            "p1": pool,
        }
        summary = assign_walk_ons_making_active_roster(
            franchise_id="fid1",
            team_id="tid1",
            active_player_ids=["w1", "w2", "p1"],
            fpd_map=fpd_map,
            franchise_players_data_collection=fpd_col,
            franchises_collection=fran_col,
            warm=False,
            rng=rng,
        )
        self.assertEqual(summary["considered"], 2)
        self.assertEqual(summary["jersey_assigned"], 1)
        self.assertEqual(summary["image_assigned"], 1)
        self.assertEqual(summary["skipped_has_jersey"], 1)
        self.assertEqual(summary["skipped_has_image"], 1)
        self.assertEqual(fpd_col.update_one.call_count, 1)
        args, kwargs = fpd_col.update_one.call_args
        self.assertEqual(args[0]["player_id"], "w1")
        set_doc = args[1]["$set"]
        self.assertIn("meta.jersey", set_doc)
        self.assertIn("meta.image_id", set_doc)
        self.assertIn(set_doc["meta.image_id"], walk_on_image_ids())
        fran_col.update_one.assert_called_once()
        add = fran_col.update_one.call_args[0][1]["$addToSet"][FRANCHISE_USED_FIELD]["$each"]
        self.assertEqual(add, [set_doc["meta.image_id"]])


class TestCollectionTruthiness(unittest.TestCase):
    """Guards a bug class the rest of this suite structurally CANNOT catch.

    `bool(pymongo.Collection)` raises NotImplementedError; `bool(mongomock.Collection)`
    returns True. Every test here runs on mongomock, so a `not some_collection` check
    passes locally and throws only in production. That is exactly how
    `_warm_walk_on_masters` shipped with `not teams_collection` on line 213 — the user
    team's eager portrait warm never painted a master, and the caller's try/except turned
    it into a logged traceback nobody read.

    So do not assert against a mock here. Simulate the REAL pymongo contract.
    """

    class _PymongoLike:
        """Stands in for pymongo.Collection's refusal to be truth-tested."""

        def __bool__(self):
            raise NotImplementedError(
                "Collection objects do not implement truth value testing or bool(). "
                "Please compare with None instead: collection is not None")

    def test_warm_does_not_truth_test_the_collection(self):
        """The guard clause must survive a collection that refuses bool()."""
        from BackEnd.utils.walk_on_roster_identity import _warm_walk_on_masters

        # entries non-empty so the `or` cannot short-circuit before the collection check.
        # If line 213 ever regresses to `not teams_collection`, this raises instead of
        # returning, and the failure names the exact contract that was broken.
        try:
            painted = _warm_walk_on_masters(
                franchise_id="f1",
                franchise_doc=None,
                team_id="not-an-objectid",
                entries=[{"player_id": "w1", "image_id": "i1", "team_id": "t1"}],
                teams_collection=self._PymongoLike(),
            )
        except NotImplementedError as e:
            self.fail(f"truth-tested a Collection instead of comparing to None: {e}")
        self.assertEqual(painted, 0)

    def test_resolver_does_not_truth_test_the_collection(self):
        """team_id_resolver had the same bug twice; keep it fixed."""
        import inspect
        from BackEnd.utils import team_id_resolver

        src = inspect.getsource(team_id_resolver)
        self.assertNotIn(
            "teams_collection_override or teams_collection", src,
            "`or` calls bool() on a Collection — use an explicit `is not None` ternary")
        self.assertNotIn(
            "and collection:", src,
            "truth-testing a Collection — compare with `collection is not None`")


if __name__ == "__main__":
    unittest.main()
