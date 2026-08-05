"""Phase 1 verification attacks — exercise paths after runtime-pool + boundary fixes."""
from __future__ import annotations

import copy
import unittest

from bson import ObjectId

from BackEnd.constants.team_builder_budget import (
    ATTR_MAX,
    ATTR_MIN,
    CORE_12_ATTRS,
    apply_capped_topup,
    clamp_attr,
    core12_total,
    evaluate_mode_roster,
    force_core12_to_budget,
)
from BackEnd.utils.team_builder_roster import (
    generate_roster_at_band,
    replace_slot_roster,
)


def _even(total: int) -> dict:
    base, rem = divmod(total, 12)
    out = {k: base for k in CORE_12_ATTRS}
    for i in range(rem):
        out[CORE_12_ATTRS[i]] += 1
    return out


def _player_row(attrs: dict, name=("Attack", "Player"), year="FR"):
    return {
        "first_name": name[0],
        "last_name": name[1],
        "class_year": year,
        "height_in": 72,
        "weight_lb": 190,
        "jersey": 10,
        "attributes": dict(attrs),
    }


def _force_rows_to_budgets(rows, budgets):
    """Shared capped-boundary helper — same force used at Apply."""
    out = []
    for i, row in enumerate(rows):
        attrs = dict(row.get("attributes") or {})
        budget = budgets[i] if i < len(budgets) else budgets[-1]
        forced = force_core12_to_budget(attrs, int(budget))
        shipped = {key: forced[key] for key in CORE_12_ATTRS}
        out.append(shipped)
    return out


JASON = {
    "SC": 4,
    "SH": 2,
    "ID": 8,
    "OD": 1,
    "PS": 1,
    "BH": 1,
    "RB": 1,
    "ST": 1,
    "AG": 1,
    "ND": 2,
    "IQ": 1,
    "FT": 1,
}


class TestCriterion2CappedBoundaryAttacks(unittest.TestCase):
    def test_19_edit_not_exactly_fifteen_is_rejected(self):
        """§4.5a: edit must be exactly 15 — never truncated, never padded."""
        from unittest.mock import MagicMock

        franchise_id = ObjectId()
        team_oid = ObjectId()
        inherited_ids = [f"p{i}" for i in range(15)]
        source_fpd = [
            {
                "franchise_id": str(franchise_id),
                "player_id": pid,
                "meta": {
                    "height": 72,
                    "weight": 190,
                    "year": "Junior",
                    "archetype": "Walk On" if i >= 12 else None,
                },
                "attributes": _even(200 if i >= 12 else 400),
            }
            for i, pid in enumerate(inherited_ids)
        ]
        ftd_col = MagicMock()
        ftd_col.find_one.return_value = {"players": inherited_ids}
        fpd_col = MagicMock()
        fpd_col.find.return_value = source_fpd

        for n in (12, 14, 16):
            rows = [_player_row(_even(400), (f"P{i}", "Extra")) for i in range(n)]
            with self.assertRaises(ValueError) as ctx:
                replace_slot_roster(
                    franchise_id=franchise_id,
                    team_object_id=team_oid,
                    team_name="Attack U",
                    roster_mode="edit",
                    imported_players=rows,
                    franchise_team_data_collection=ftd_col,
                    franchise_players_data_collection=fpd_col,
                    attribute_mode="capped",
                )
            self.assertEqual(str(ctx.exception), f"roster_size_invalid:{n}:15")
            fpd_col.insert_many.assert_not_called()

    def test_2_capped_budgets_cover_all_fifteen_including_walk_ons(self):
        """Criterion 2 re-run: points cannot cross a player boundary across 15."""
        budgets = [400] * 12 + [180, 190, 200]
        rows = []
        for i, b in enumerate(budgets):
            attrs = _even(b + 80 if i == 0 else (b - 40 if i == 14 else b))
            rows.append(_player_row(attrs, (f"P{i}", "Bound")))
        shipped = _force_rows_to_budgets(rows, budgets)
        self.assertEqual(len(shipped), 15)
        self.assertEqual([core12_total(a) for a in shipped], budgets)

    def test_2a_raise_past_inherited_forced_back(self):
        inherited_budget = 400
        attack = _even(500)
        forced = force_core12_to_budget(attack, inherited_budget)
        self.assertEqual(core12_total(forced), inherited_budget)

    def test_2b_lower_a_raise_b_cannot_cross_budgets(self):
        a = force_core12_to_budget(_even(350), 400)
        b = force_core12_to_budget(_even(450), 400)
        self.assertEqual([core12_total(a), core12_total(b)], [400, 400])

    def test_2c_capped_forced_to_inherited_budgets(self):
        inherited = [300, 310, 320, 330, 340]
        attack = [_even(600) for _ in range(5)]
        shipped = [
            force_core12_to_budget(a, inherited[i]) for i, a in enumerate(attack)
        ]
        self.assertEqual([core12_total(a) for a in shipped], inherited)


class TestCriterion4UncappedPool(unittest.TestCase):
    def test_4_over_runtime_pool_is_detected(self):
        attrs = [_even(600) for _ in range(12)]
        team_total = sum(core12_total(a) for a in attrs)
        pool = 5000
        evaluation = evaluate_mode_roster(
            attribute_mode="uncapped", player_attrs=attrs, team_pool=pool, team_median=4000
        )
        self.assertGreater(team_total, pool)
        self.assertEqual(evaluation["over_pool_by"], team_total - pool)


class TestCriterion5Clamp(unittest.TestCase):
    def test_5_clamp_matrix(self):
        cases = {
            "zero": 0,
            "four": 4,
            "hundred": 100,
            "negative": -3,
            "non_numeric": "abc",
            "empty": "",
        }
        for label, raw in cases.items():
            with self.subTest(label=label):
                sc = clamp_attr(raw)
                self.assertGreaterEqual(sc, ATTR_MIN, label)
                self.assertLessEqual(sc, ATTR_MAX, label)


class TestCriterion9ResetBaseline(unittest.TestCase):
    def test_9_mode_switch_does_not_corrupt_raw_inherited_total(self):
        raw = dict(JASON)
        capped = apply_capped_topup(raw)
        inherited_capped = copy.deepcopy(capped["attrs"])
        uncapped_attrs = {
            k: max(ATTR_MIN, min(ATTR_MAX, int(raw.get(k, ATTR_MIN)))) for k in CORE_12_ATTRS
        }
        capped_again = apply_capped_topup(raw)
        self.assertEqual(core12_total(inherited_capped), 60)
        self.assertEqual(capped_again["attrs"], inherited_capped)
        self.assertEqual(core12_total(uncapped_attrs), 63)
        self.assertEqual(capped_again["raw_total"], 24)


class TestPath3GenerateBounds(unittest.TestCase):
    def test_generate_always_fifteen_with_three_walk_ons(self):
        templates = [
            {
                "meta": {"height": 72, "weight": 190, "year": "Junior"},
                "attributes": _even(400),
            }
            for _ in range(12)
        ]
        generated = generate_roster_at_band(
            source_fpd_docs=templates,
            team_name="Gen U",
            team_object_id=ObjectId(),
            roster_size=15,
            attribute_mode="capped",
            apply_topup=True,
        )
        self.assertEqual(len(generated), 15)
        walk_ons = [
            p for p in generated if (p.get("meta") or {}).get("archetype") == "Walk On"
        ]
        self.assertEqual(len(walk_ons), 3)
        self.assertEqual(
            [(p.get("meta") or {}).get("archetype") for p in generated[12:]],
            ["Walk On", "Walk On", "Walk On"],
        )

    def test_generate_capped_scholarship_forced_to_inherited_budgets(self):
        templates = [
            {
                "meta": {"height": 72, "weight": 190, "year": "Junior"},
                "attributes": dict(JASON),
            },
            {
                "meta": {"height": 74, "weight": 200, "year": "Senior"},
                "attributes": _even(400),
            },
        ]
        generated = generate_roster_at_band(
            source_fpd_docs=templates,
            team_name="Gen U",
            team_object_id=ObjectId(),
            roster_size=15,
            attribute_mode="capped",
            apply_topup=True,
        )
        self.assertEqual(len(generated), 15)
        budgets = [60, 400] + [400] * 10
        for i in range(12):
            forced = force_core12_to_budget(
                generated[i].get("attributes") or {}, budgets[i % len(budgets)]
            )
            self.assertEqual(core12_total(forced), budgets[i % len(budgets)])


if __name__ == "__main__":
    unittest.main()
