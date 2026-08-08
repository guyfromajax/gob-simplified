"""Team Builder Apply floors are diff-scoped (§4.5b) — not full-roster."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.constants.team_builder_budget import CORE_12_ATTRS, core12_total
from BackEnd.constants.training_shape import (
    CORE_12,
    authored_floor_violations,
    floor_violations,
)
from BackEnd.utils.player_generation import position_profile
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


def _mk(pos: str, mean: float, **ov) -> dict:
    prof = position_profile(pos) or {}
    raw = {a: float(prof.get(a, 1) or 1) for a in CORE_12}
    tot = sum(raw.values()) or 1.0
    base = {a: max(1, int(round(mean * (raw[a] / tot) * 12))) for a in CORE_12}
    base.update(ov)
    return base


# Framework §10.2 battery shapes (weight-scaled P6 sign-off).
CREATIVE = [
    ("stretch_four", "PF", _mk("PF", 40, SH=55, FT=45, SC=35, RB=28, ST=42, AG=30, ID=28, OD=22, PS=18, BH=16, IQ=28, ND=25)),
    ("shooting_big", "C", _mk("C", 38, SH=48, FT=42, SC=40, RB=35, ST=40, ID=38, AG=18, OD=16, PS=14, BH=12, IQ=22, ND=22)),
    ("undersized_rim_protector", "PF", _mk("PF", 36, ID=55, RB=50, ST=52, SC=22, SH=12, AG=28, OD=20, PS=14, BH=12, FT=18, IQ=24, ND=30)),
    ("point_forward", "SF", _mk("SF", 40, PS=48, BH=45, IQ=42, AG=40, SC=38, SH=32, OD=28, ID=22, ST=28, RB=18, FT=30, ND=28)),
    ("three_and_d", "SG", _mk("SG", 38, SH=52, OD=48, FT=40, AG=36, ID=28, SC=22, BH=20, PS=18, IQ=30, RB=18, ST=28, ND=32)),
    ("traditional_post", "C", _mk("C", 36, SC=48, ID=50, RB=48, ST=52, SH=8, AG=10, OD=12, PS=10, BH=8, FT=20, IQ=22, ND=28)),
    ("pure_distributor", "PG", _mk("PG", 38, PS=55, BH=52, IQ=50, OD=32, SH=22, SC=18, AG=36, ID=20, ST=18, RB=14, FT=28, ND=30)),
    ("small_ball_five", "C", _mk("C", 40, AG=45, SH=40, OD=38, PS=30, BH=28, SC=32, ID=28, ST=30, RB=28, FT=35, IQ=32, ND=28)),
    ("scoring_pg", "PG", _mk("PG", 40, SC=50, SH=45, BH=48, PS=40, AG=38, IQ=35, OD=18, ID=14, ST=22, RB=12, FT=38, ND=25)),
    ("slashing_sf", "SF", _mk("SF", 38, SC=48, AG=45, BH=38, PS=28, ST=35, ID=30, SH=14, FT=18, OD=28, RB=30, IQ=28, ND=30)),
]


def _path_flat(pos: str, sc: int, sh: int, other: int) -> dict:
    a = {x: other for x in CORE_12}
    a["SC"], a["SH"] = sc, sh
    return a


PATHOLOGICAL = (
    [(f"harsh_{p}", p, _path_flat(p, 90, 90, 5)) for p in ("PG", "SG", "SF", "PF", "C")]
    + [(f"mild_{p}", p, _path_flat(p, 70, 70, 8)) for p in ("PG", "SG", "SF", "PF", "C")]
    + [
        (
            "glass_cannon_pg",
            "PG",
            {a: 5 for a in CORE_12} | {"SC": 85, "SH": 80, "BH": 75, "PS": 40, "FT": 60},
        ),
        (
            "statue_c",
            "C",
            {a: 5 for a in CORE_12} | {"ST": 90, "RB": 85, "SC": 70, "ID": 60},
        ),
        (
            "starved_id_c",
            "C",
            _mk("C", 36, ID=8, SC=50, RB=45, ST=50, SH=8, AG=10, OD=10, PS=10, BH=8, FT=20, IQ=22, ND=28),
        ),
        (
            "starved_id_pf",
            "PF",
            _mk("PF", 36, ID=8, SC=50, RB=45, ST=50, SH=8, AG=10, OD=10, PS=10, BH=8, FT=20, IQ=22, ND=28),
        ),
    ]
)


class TestAuthoredFloorViolations(unittest.TestCase):
    def test_zero_edit_ignores_inherited_shortfall(self):
        inherited = {a: 50 for a in CORE_12}
        inherited["ID"] = 8  # below PF floor
        self.assertTrue(floor_violations("PF", inherited))
        self.assertEqual(
            authored_floor_violations("PF", inherited, inherited),
            [],
        )

    def test_editing_unrelated_attr_ignores_untouched_shortfall(self):
        inherited = {a: 50 for a in CORE_12}
        inherited["ID"] = 8
        final = dict(inherited)
        final["BH"] = 55  # legal change; ID still starved but unedited
        viols = authored_floor_violations("PF", final, inherited)
        self.assertEqual(viols, [])
        self.assertTrue(any(a == "ID" for a, _, _ in floor_violations("PF", final)))

    def test_editing_starved_attr_refuses(self):
        inherited = {a: 50 for a in CORE_12}
        final = dict(inherited)
        final["ID"] = 8
        viols = authored_floor_violations("PF", final, inherited)
        self.assertTrue(any(a == "ID" for a, _, _ in viols))

    def test_helper_matches_row_scope_when_final_equals_row(self):
        """Apply uses row≠inherited; helper covers the same set when finals mirror the row."""
        inherited = {a: 50 for a in CORE_12}
        row_final = dict(inherited)
        row_final["ID"] = 8
        self.assertEqual(
            authored_floor_violations("PF", row_final, inherited),
            [
                (a, h, n)
                for a, h, n in floor_violations("PF", row_final)
                if a == "ID"
            ],
        )


class TestBatteryDiffScoped(unittest.TestCase):
    def test_creative_clears_when_fully_authored(self):
        """Authoring a creative shape changes all twelve attrs → full floor gate."""
        legal = {a: 40 for a in CORE_12}
        cleared = 0
        for name, pos, attrs in CREATIVE:
            viols = authored_floor_violations(pos, attrs, legal)
            self.assertEqual(
                viols,
                floor_violations(pos, attrs),
                f"{name}: diff scope should match full check when all attrs change",
            )
            if not viols:
                cleared += 1
        self.assertEqual(cleared, 10, f"creative clear count {cleared}/10")

    def test_pathological_refused_when_fully_authored(self):
        legal = {a: 40 for a in CORE_12}
        refused = 0
        for name, pos, attrs in PATHOLOGICAL:
            viols = authored_floor_violations(pos, attrs, legal)
            self.assertEqual(viols, floor_violations(pos, attrs), name)
            if viols:
                refused += 1
        self.assertEqual(refused, len(PATHOLOGICAL), f"path refuse {refused}/{len(PATHOLOGICAL)}")


class TestReplaceSlotRosterDiffFloors(unittest.TestCase):
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
        # PF with ID below floor — zero-edit restatement must Apply.
        starved = {a: 50 for a in CORE_12}
        starved["ID"] = 8
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
                # Spend within capped total: move 1 from BH→SC leave ID=8.
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

    def test_authoring_starved_id_refuses(self):
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
        with self.assertRaises(ValueError) as ctx:
            self._run_replace(source, rows)
        self.assertIn("shape_floor_violation", str(ctx.exception))
        self.assertIn("ID:", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
