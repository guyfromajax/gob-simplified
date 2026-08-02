"""Runtime league context — week-1 as-initialized, not live franchise saves."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from BackEnd.utils.team_builder_league_context import compute_league_attr_context


def _attrs(n):
    base, rem = divmod(n, 12)
    keys = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")
    out = {k: base for k in keys}
    for i in range(rem):
        out[keys[i]] += 1
    return out


class TestLeagueAttrContext(unittest.TestCase):
    def test_week1_as_initialized_uses_core_plus_seeded_walk_ons(self):
        t1, t2 = ObjectId(), ObjectId()
        p1, p2, p3 = ObjectId(), ObjectId(), ObjectId()
        teams = [
            {"_id": t1, "player_ids": [p1, p2], "total_player_attrs": 0},
            {"_id": t2, "player_ids": [p3], "total_player_attrs": 0},
        ]
        players = {
            p1: {"_id": p1, "attributes": _attrs(500)},
            p2: {"_id": p2, "attributes": _attrs(300)},
            p3: {"_id": p3, "attributes": _attrs(400)},
        }

        db = MagicMock()
        db.teams.find.return_value = teams

        def find_players(query, projection=None):
            ids = query.get("_id", {}).get("$in", [])
            return [players[i] for i in ids if i in players]

        db.players.find.side_effect = find_players

        fake_wo = {"attributes": _attrs(60)}
        with patch(
            "BackEnd.models.franchise_manager.generate_walk_on_profile",
            return_value=fake_wo,
        ):
            ctx = compute_league_attr_context(db)
            ctx2 = compute_league_attr_context(db)

        # core 800 / 400 + 3×60 pad → 980 / 580
        self.assertEqual(ctx["source"], "week1_as_initialized")
        self.assertEqual(ctx["team_pool"], 980)
        self.assertEqual(ctx["team_median"], 780)
        self.assertEqual(ctx["scholarship_pool"], 800)
        # Idempotent across calls (seeded walk-ons, same inputs).
        self.assertEqual(ctx["team_pool"], ctx2["team_pool"])
        self.assertEqual(ctx["team_median"], ctx2["team_median"])

    def test_does_not_read_franchise_collections_for_pool(self):
        db = MagicMock()
        db.teams.find.return_value = []
        with patch(
            "BackEnd.models.franchise_manager.generate_walk_on_profile",
            return_value={"attributes": _attrs(60)},
        ):
            ctx = compute_league_attr_context(db)
        self.assertEqual(ctx["source"], "week1_as_initialized")
        db.franchises.find.assert_not_called()
        db.franchise_team_data.find.assert_not_called()
        db.franchise_players_data.find.assert_not_called()


if __name__ == "__main__":
    unittest.main()
