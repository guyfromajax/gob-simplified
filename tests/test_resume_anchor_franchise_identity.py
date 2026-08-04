"""Resume-anchor identity: merge + stamp + fail-closed roster guard."""

import unittest

from BackEnd.utils.resume_anchor_identity import (
    merge_resume_anchor_snapshot,
    resolve_franchise_id_for_roster,
    stamp_resume_identity_on_snapshot,
)


class ResumeAnchorFranchiseIdentityTests(unittest.TestCase):
    def test_merge_preserves_root_franchise_identity_over_empty_snapshot(self):
        """Historical anchors omit franchise_id/mode; merge must recover them from root."""
        root = {
            "_id": "game-1",
            "mode": "franchise",
            "franchise_id": "fid-abc",
            "tournament_id": None,
            "user_team_side": "home",
            "quarter": 99,
        }
        snapshot = {
            "quarter": 3,
            "clock": "0:00",
            "time_remaining": 0,
            "players": [{"playerId": "minted-1", "team": "home"}],
            "score": {"Concord": 40, "Morristown": 38},
        }
        merged = merge_resume_anchor_snapshot(root, snapshot)
        self.assertEqual(merged["mode"], "franchise")
        self.assertEqual(merged["franchise_id"], "fid-abc")
        self.assertEqual(merged["user_team_side"], "home")
        self.assertEqual(merged["_id"], "game-1")
        self.assertEqual(merged["quarter"], 3)
        self.assertEqual(merged["players"][0]["playerId"], "minted-1")

    def test_old_wholesale_replace_would_drop_identity(self):
        snapshot = {"quarter": 3, "players": [{"playerId": "x"}]}
        saved = dict(snapshot)
        with self.assertRaisesRegex(ValueError, "Refusing to load core rosters"):
            resolve_franchise_id_for_roster(saved, body={"mode": "franchise"})

    def test_merge_then_resolve_loads_franchise_roster_id(self):
        root = {"mode": "franchise", "franchise_id": "fid-abc"}
        snapshot = {"quarter": 2}
        merged = merge_resume_anchor_snapshot(root, snapshot)
        mode, fid = resolve_franchise_id_for_roster(merged, body={})
        self.assertEqual(mode, "franchise")
        self.assertEqual(fid, "fid-abc")

    def test_stamp_writes_identity_into_new_snapshots(self):
        snap = {"quarter": 2, "players": []}
        stamp_resume_identity_on_snapshot(
            snap,
            body={"mode": "franchise", "franchise_id": "fid-new"},
        )
        self.assertEqual(snap["mode"], "franchise")
        self.assertEqual(snap["franchise_id"], "fid-new")

    def test_stamp_prefers_identity_source_over_body(self):
        snap = {}
        stamp_resume_identity_on_snapshot(
            snap,
            body={"mode": "single", "franchise_id": "from-body"},
            identity_source={"mode": "franchise", "franchise_id": "from-root"},
        )
        self.assertEqual(snap["mode"], "franchise")
        self.assertEqual(snap["franchise_id"], "from-root")

    def test_guard_fails_when_franchise_mode_without_id(self):
        with self.assertRaisesRegex(ValueError, "Refusing to load core rosters"):
            resolve_franchise_id_for_roster({"mode": "franchise"}, body={})

    def test_non_franchise_mode_allows_none_roster_id(self):
        mode, fid = resolve_franchise_id_for_roster({"mode": "single"}, body={})
        self.assertEqual(mode, "single")
        self.assertIsNone(fid)

    def test_body_franchise_id_rescues_merged_doc_missing_id(self):
        mode, fid = resolve_franchise_id_for_roster(
            {"mode": "franchise"},
            body={"mode": "franchise", "franchise_id": "from-body"},
        )
        self.assertEqual(mode, "franchise")
        self.assertEqual(fid, "from-body")


if __name__ == "__main__":
    unittest.main()
