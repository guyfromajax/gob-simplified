"""Structural guard for the identity/development carry.

PLAYER_DEV_CARRY_FIELDS is the single source of truth for the fields that must survive
every player-doc hop (recruit → signed_player → FPD, and FPD → FPD at rollover). A field
added to that tuple must be carried at each hop; a hop that reverts to a hand-maintained
per-field cherry-pick — the failure mode that dropped entry_tier / position_intent /
potential_factor at signing and re-derived them (argmax intent, uuid-hashed potential) —
must fail CI here rather than ship silent.
"""
import re
from pathlib import Path

from BackEnd.models.franchise_manager import (
    carry_dev_fields,
    PLAYER_DEV_CARRY_FIELDS,
    POOL_TO_FPD_CARRY_FIELDS,
)

ROOT = Path(__file__).resolve().parents[1]


def test_carry_dev_fields_carries_present_and_omits_absent():
    src = {f: f"v_{f}" for f in PLAYER_DEV_CARRY_FIELDS}
    src["unrelated"] = "x"
    out = carry_dev_fields(src)
    assert set(out) == set(PLAYER_DEV_CARRY_FIELDS)  # every declared field carried
    assert "unrelated" not in out                    # nothing else leaks through
    assert carry_dev_fields({}) == {}                # absent → omitted (backfilled downstream)
    assert carry_dev_fields({"entry_tier": None}) == {}  # None → omitted


def test_pool_carry_is_a_subset_of_player_dev_carry():
    # POOL_TO_FPD_CARRY_FIELDS is the pool-sourced subset; the module asserts this too.
    assert set(POOL_TO_FPD_CARRY_FIELDS) <= set(PLAYER_DEV_CARRY_FIELDS)


def test_signing_hop_carries_every_declared_field():
    """_week_35_result_entry_from_recruit is the hop that used to DROP these. A recruit
    carrying the full declared set must emerge with the full set — so a field added to
    PLAYER_DEV_CARRY_FIELDS is enforced at the signing boundary, not silently dropped."""
    from BackEnd.api.franchise_routes import _week_35_result_entry_from_recruit

    recruit = {
        "recruit_id": "r1", "name": "Test Player", "height": 72, "weight": 175,
        "year": "JH", "archetype": "Classic SF", "position_ratings": {"SF": 40},
        "attributes": {"SC": 40}, "Home Region": "H",
        **{f: f"v_{f}" for f in PLAYER_DEV_CARRY_FIELDS},
    }
    entry = _week_35_result_entry_from_recruit(recruit, {"_id": "T", "name": "T"}, False, False, False)
    for f in PLAYER_DEV_CARRY_FIELDS:
        assert entry.get(f) == f"v_{f}", f"signing hop dropped {f}"


def test_no_hop_hand_lists_dev_fields_instead_of_the_helper():
    """Regression guard: the FPD/FRD write hops must carry via carry_dev_fields, not a
    hand-written per-field cherry-pick keyed off the hop's source dict."""
    src = (ROOT / "BackEnd/api/franchise_routes.py").read_text(encoding="utf-8")
    bad = re.findall(
        r'"(?:entry_tier|position_intent|potential_factor|development)":\s*'
        r'(?:signed_player|fpd_doc|recruit)(?:\.get\(|\[)',
        src,
    )
    assert not bad, f"hand-listed dev-field carry found — use carry_dev_fields: {bad}"
    assert src.count("carry_dev_fields(") >= 4, "expected carry_dev_fields at each FPD/FRD hop"
