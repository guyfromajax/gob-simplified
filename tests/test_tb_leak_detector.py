"""
Team Builder replaced-name leak detector — unit scan + franchise route sweep.

Invariant: replaced core name appears nowhere as *rendered* text in franchise-
scoped JSON except allowlisted metadata / orientation copy. Dict keys and
lookup identifiers (score maps, possession, home_team/away_team) are identity
and are not leaks.

Run (prefer unittest to avoid conftest DB block-list when .env points at gob):
  TB_LEAK_DETECTOR=0 .venv/bin/python -m unittest tests.test_tb_leak_detector -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# Project root on path (unittest does not load conftest).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("TB_LEAK_DETECTOR", "0")
os.environ.setdefault("TB_LEAK_DETECTOR_THROW", "0")

import mongomock
from bson import ObjectId

from BackEnd.utils import team_builder_leak_detector as det
from BackEnd.utils.franchise_team_display import TEAM_BUILDER_FIELD


class TestScanAllowlist(unittest.TestCase):
    def test_allowlists_replaced_name_fields(self):
        payload = {
            "team": "Hanson",
            "team_builder_replaced_name": "Providence",
            "team_builder": {"replaced_name": "Providence", "name": "Hanson"},
            "standings": [{"name": "Hanson", "team_id": "x"}],
        }
        self.assertEqual(det.scan_json_for_replaced_name(payload, "Providence"), [])

    def test_identity_name_is_not_a_leak(self):
        # §3.1a: wire ``name`` is core identity; chrome is display_name.
        hits = det.scan_json_for_replaced_name(
            {
                "standings": [
                    {"name": "Providence", "display_name": "Hanson", "W": 1}
                ],
                "teams": {"home": {"name": "Providence", "display_name": "Hanson"}},
            },
            "Providence",
        )
        self.assertEqual(hits, [])

    def test_catches_chrome_display_fields(self):
        hits = det.scan_json_for_replaced_name(
            {
                "standings": [{"name": "Providence", "display_name": "Providence"}],
                "rankings": [{"team_name": "Providence"}],
            },
            "Providence",
        )
        self.assertIn("standings[0].display_name", hits)
        self.assertIn("rankings[0].team_name", hits)

    def test_score_keys_and_possession_are_not_leaks(self):
        payload = {
            "score": {"Providence": 72, "Concord": 68},
            "points_by_quarter": {"Providence": [10, 0, 0, 0]},
            "possession": "Providence",
            "home_team": "Providence",
            "away_team": "Concord",
            "teams": {"home": {"name": "Providence", "display_name": "Hanson"}},
        }
        hits = det.scan_json_for_replaced_name(payload, "Providence")
        self.assertEqual(hits, [])
        self.assertFalse(any("#key" in h for h in hits))
        self.assertNotIn("possession", hits)

    def test_allowlists_orientation_copy(self):
        payload = {
            "note": "Hanson · Conference 3 · replacing Providence in this franchise"
        }
        self.assertEqual(det.scan_json_for_replaced_name(payload, "Providence"), [])

    def test_path_allowlist_helpers(self):
        self.assertTrue(det.path_is_allowlisted("team_builder.replaced_name"))
        self.assertTrue(det.path_is_allowlisted("team_builder_replaced_name"))
        self.assertTrue(det.path_is_lookup_identifier("possession"))
        self.assertFalse(det.path_is_allowlisted("standings[0].name"))


class TestTbLeakRouteSweep(unittest.TestCase):
    """Seed a TB franchise and walk franchise-scoped JSON producers."""

    def setUp(self):
        self.client = mongomock.MongoClient()
        self.db = self.client.db
        self.prov_oid = ObjectId()
        self.conc_oid = ObjectId()
        self.replaced_name = "Providence"
        self.custom_name = "Hanson"

        self.db.teams.insert_many(
            [
                {
                    "_id": self.prov_oid,
                    "name": self.replaced_name,
                    "team_id": "PROVIDENCE",
                    "conference": 3,
                    "region": "B",
                    "primary_color": "#111111",
                    "mascot": "Friars",
                },
                {
                    "_id": self.conc_oid,
                    "name": "Concord",
                    "team_id": "CONCORD",
                    "conference": 3,
                    "region": "B",
                    "primary_color": "#222222",
                    "mascot": "Owls",
                },
            ]
        )
        self.franchise_id = ObjectId()
        self.db.franchises.insert_one(
            {
                "_id": self.franchise_id,
                "user_id": "test-user-123",
                "user_team_id": self.custom_name,
                "user_team_object_id": str(self.prov_oid),
                "week": 1,
                "current_season": 1,
                "schedule": [[[self.conc_oid, self.prov_oid]]],
                "results": {},
                "training_status": {},
                TEAM_BUILDER_FIELD: {
                    "replaced_object_id": str(self.prov_oid),
                    "replaced_name": self.replaced_name,
                    "name": self.custom_name,
                    "abbreviation": "HAN",
                    "asset_strategy": "generated",
                    "primary_color": "#aabbcc",
                },
            }
        )
        self.db.franchise_team_data.insert_many(
            [
                {
                    "franchise_id": self.franchise_id,
                    "team_id": self.prov_oid,
                    "natl_rank": 40,
                    "team_attributes": {"team_chemistry": 50},
                    "prestige": 70,
                },
                {
                    "franchise_id": self.franchise_id,
                    "team_id": self.conc_oid,
                    "natl_rank": 55,
                    "team_attributes": {},
                    "prestige": 60,
                },
            ]
        )
        self.db.games = self.db.games
        self.db.franchise_state = self.db.franchise_state

        import BackEnd.utils.franchise_team_display as ftd
        import BackEnd.api.franchise_routes as fr
        import BackEnd.utils.ownership as ownership
        import BackEnd.db as dbmod

        self._patches = [
            mock.patch.object(ftd, "franchises_collection", self.db.franchises),
            mock.patch.object(ftd, "teams_collection", self.db.teams),
            mock.patch.object(fr, "db", self.db),
            mock.patch.object(
                fr, "franchise_team_data_collection", self.db.franchise_team_data
            ),
            mock.patch.object(
                fr, "franchise_state_collection", self.db.franchise_state
            ),
            mock.patch.object(ownership, "franchises_collection", self.db.franchises),
            mock.patch.object(dbmod, "franchises_collection", self.db.franchises),
            mock.patch.object(dbmod, "teams_collection", self.db.teams),
            mock.patch.object(
                dbmod, "franchise_team_data_collection", self.db.franchise_team_data
            ),
            mock.patch.object(det, "get_team_builder_overlay", self._overlay_for),
        ]
        for p in self._patches:
            p.start()

        self.walked: list[str] = []
        self.walk_errors: list[str] = []

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def _overlay_for(self, franchise_id):
        doc = self.db.franchises.find_one({"_id": ObjectId(str(franchise_id))})
        if not doc:
            return None
        return doc.get(TEAM_BUILDER_FIELD)

    def _record(self, findings, route, payload, *, scan_for_leaks=True):
        self.walked.append(route)
        if not scan_for_leaks:
            return
        hits = det.scan_json_for_replaced_name(payload, self.replaced_name)
        if hits:
            findings.append({"route": route, "paths": hits})

    def _print_coverage(self):
        print("\n[TB-LEAK] COVERAGE — walked this run:")
        for r in self.walked:
            print(f"  ✓ {r}")
        print("[TB-LEAK] COVERAGE — declared producers:")
        for r in det.FRANCHISE_LEAK_SWEEP_PRODUCERS:
            mark = "✓" if any(r in w or w.startswith(r.split("(")[0]) for w in self.walked) else "✗"
            print(f"  {mark} {r}")
        print("[TB-LEAK] COVERAGE — declared GET routes:")
        for path, _ in det.FRANCHISE_LEAK_SWEEP_GET_ROUTES:
            mark = "✓" if any(path in w for w in self.walked) else "✗"
            print(f"  {mark} GET {path}")
        print("[TB-LEAK] COVERAGE — NOT walked (known gaps):")
        for r in det.FRANCHISE_LEAK_SWEEP_NOT_WALKED:
            print(f"  · {r}")
        if self.walk_errors:
            print("[TB-LEAK] COVERAGE — walk errors:")
            for e in self.walk_errors:
                print(f"  ! {e}")
        print()

    def test_sweep_franchise_routes_report(self):
        from BackEnd.api.franchise_routes import (
            _franchise_summary_for_list,
            standings,
            command_center_data,
        )
        from BackEnd.utils.ownership import verify_franchise_owned_by_user
        from BackEnd.utils.shared import summarize_game_state

        findings: list[dict] = []
        fid = str(self.franchise_id)

        # --- list card ---
        doc = self.db.franchises.find_one({"_id": self.franchise_id})
        self._record(
            findings,
            "producer:_franchise_summary_for_list",
            _franchise_summary_for_list(doc),
        )

        # --- standings ---
        try:
            body = standings(
                franchise_id=fid,
                profile=False,
                scope="user_region",
                team_id=str(self.prov_oid),
                region=None,
            )
            self._record(findings, "producer:standings", body)
        except Exception as e:
            self.walk_errors.append(f"standings: {e}")
            findings.append(
                {"route": "producer:standings", "paths": [f"<error: {e}>"]}
            )

        # --- command-center/data ---
        try:
            user = {"user_id": "test-user-123"}
            verify_franchise_owned_by_user(fid, user["user_id"])
            fn = getattr(command_center_data, "__wrapped__", command_center_data)
            try:
                body = fn(franchise_id=fid, user=user, profile=False)
            except TypeError:
                body = command_center_data(franchise_id=fid, user=user, profile=False)
            if hasattr(body, "body"):
                body = json.loads(body.body)
            self._record(findings, "producer:command_center_data", body)
        except Exception as e:
            self.walk_errors.append(f"command_center_data: {e}")
            findings.append(
                {
                    "route": "producer:command_center_data",
                    "paths": [f"<error: {e}>"],
                }
            )

        # --- summarize_game_state: API chrome vs persist identity ---
        home = mock.Mock()
        home.name = self.replaced_name
        home.display_name = self.custom_name
        home.team_id = "PROVIDENCE"
        home.primary_color = "#111"
        home.secondary_color = "#222"
        home.mascot = "Friars"
        home.team_fouls = 0
        home.timeouts = 4
        home.points_by_quarter = [10, 0, 0, 0]
        home.team_attributes = {}
        home.strategy_settings = {}
        home.strategy_calls = {}
        home.plays = {}
        home.scouting_data = {}
        home.playbook_settings = {}
        home.lineup = {}
        home.get_all_players = mock.Mock(return_value=[])
        home.get_player_by_id = mock.Mock(return_value=None)
        home.franchise_id = None

        away = mock.Mock()
        away.name = "Concord"
        away.display_name = "Concord"
        away.team_id = "CONCORD"
        away.primary_color = "#333"
        away.secondary_color = "#444"
        away.mascot = "Owls"
        away.team_fouls = 0
        away.timeouts = 4
        away.points_by_quarter = [8, 0, 0, 0]
        away.team_attributes = {}
        away.strategy_settings = {}
        away.strategy_calls = {}
        away.plays = {}
        away.scouting_data = {}
        away.playbook_settings = {}
        away.lineup = {}
        away.get_all_players = mock.Mock(return_value=[])
        away.get_player_by_id = mock.Mock(return_value=None)
        away.franchise_id = None

        game = mock.Mock()
        game.home_team = home
        game.away_team = away
        game.score = {self.replaced_name: 10, "Concord": 8}
        game.quarter = 1
        game.game_id = None
        game.turns = []
        game.text_log = []
        game.game_state = {
            "points_by_quarter": {
                self.replaced_name: [10, 0, 0, 0],
                "Concord": [8, 0, 0, 0],
            },
            "clock": "8:00",
            "time_remaining": 480,
        }
        game.team_totals = {self.replaced_name: {}, "Concord": {}}
        game.get_box_score = mock.Mock(return_value={})

        try:
            api_payload = summarize_game_state(game, exclude_animations=False)
            self._record(
                findings,
                "producer:summarize_game_state(exclude_animations=False)",
                api_payload,
            )
            # name = core identity; display_name = overlay; score keys = core.
            home_row = next(iter((api_payload.get("teams") or {}).values()), {})
            self.assertEqual(home_row.get("name"), self.replaced_name)
            self.assertEqual(home_row.get("display_name"), self.custom_name)
            self.assertIn(self.replaced_name, api_payload.get("score") or {})
            self.assertNotIn(self.custom_name, api_payload.get("score") or {})
        except Exception as e:
            self.walk_errors.append(f"summarize_api: {e}")
            findings.append(
                {
                    "route": "producer:summarize_game_state(exclude_animations=False)",
                    "paths": [f"<error: {e}>"],
                }
            )

        try:
            persist_payload = summarize_game_state(game, exclude_animations=True)
            self._record(
                findings,
                "producer:summarize_game_state(exclude_animations=True)",
                persist_payload,
            )
            home_row = next(iter((persist_payload.get("teams") or {}).values()), {})
            self.assertEqual(home_row.get("name"), self.replaced_name)
            self.assertEqual(home_row.get("display_name"), self.custom_name)
            self.assertIn(self.replaced_name, persist_payload.get("score") or {})
        except Exception as e:
            self.walk_errors.append(f"summarize_persist: {e}")
            findings.append(
                {
                    "route": "producer:summarize_game_state(exclude_animations=True)",
                    "paths": [f"<error: {e}>"],
                }
            )

        # --- TestClient walk of FRANCHISE_LEAK_SWEEP_GET_ROUTES ---
        try:
            from fastapi.testclient import TestClient
            from BackEnd.api.api import app
            from BackEnd.utils.auth import get_current_user

            app.dependency_overrides[get_current_user] = lambda: {
                "user_id": "test-user-123",
                "email": "t@t.com",
                "role": "user",
            }
            try:
                with TestClient(app) as client:
                    for path, qtemplate in det.FRANCHISE_LEAK_SWEEP_GET_ROUTES:
                        q = {
                            k: (fid if v == "{fid}" else v)
                            for k, v in qtemplate.items()
                        }
                        if path.endswith("/standings") and "team_id" not in q:
                            q["team_id"] = str(self.prov_oid)
                        try:
                            res = client.get(path, params=q)
                        except Exception as e:
                            self.walk_errors.append(f"GET {path}: {e}")
                            findings.append(
                                {
                                    "route": f"GET {path}",
                                    "paths": [f"<request error: {e}>"],
                                }
                            )
                            continue
                        label = f"GET {path}"
                        if res.status_code >= 400:
                            self.walked.append(f"{label} (status {res.status_code})")
                            if res.status_code == 500:
                                try:
                                    detail = res.json()
                                except Exception:
                                    detail = {"raw": res.text[:200]}
                                findings.append(
                                    {
                                        "route": label,
                                        "paths": [f"<status 500: {detail}>"],
                                    }
                                )
                            continue
                        try:
                            payload = res.json()
                        except Exception:
                            self.walked.append(f"{label} (non-json)")
                            continue
                        if path.endswith("/list") and isinstance(payload, dict):
                            for i, card in enumerate(payload.get("franchises") or []):
                                if str(card.get("franchise_id")) != fid:
                                    continue
                                self._record(findings, f"{label}[{i}]", card)
                            if not any(label in w for w in self.walked):
                                self.walked.append(label)
                            continue
                        self._record(findings, label, payload)
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        except Exception as e:
            self.walk_errors.append(f"TestClient: {e}")
            findings.append(
                {"route": "TestClient", "paths": [f"<client error: {e}>"]}
            )

        # Explicit: box-score data route is NOT walked (no seeded game_id).
        print(
            "\n[TB-LEAK] BOX-SCORE: GET /api/game/{game_id} not walked in this "
            "sweep (needs seeded game). Middleware now resolves franchise_id "
            "from the game doc so live box-score responses are scannable.\n"
        )

        deduped: list[dict] = []
        seen: set[str] = set()
        for item in findings:
            key = f"{item.get('route')}|{','.join(item.get('paths') or [])}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        findings = deduped

        self._print_coverage()
        report = det.format_leak_report(
            franchise_id=fid,
            replaced_name=self.replaced_name,
            findings=findings,
        )
        print(report + "\n")
        if findings:
            print("[TB-LEAK] FINDINGS_JSON_START")
            print(json.dumps(findings, indent=2, default=str))
            print("[TB-LEAK] FINDINGS_JSON_END")

        self.assertEqual(
            findings,
            [],
            msg="Replaced-name leaks found — see report above (fix producers, not this test).",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
