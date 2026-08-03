"""FPD persistence PRESENCE check — the pool→FPD carry at franchise init.

Why presence, not resolution: the read-side resolvers (resolve_potential_factor, the
entry_tier RT fallback, position_intent-from-ratings) each return the right value whether the
field is STORED on the doc or absent, so a dropped write looks perfect on screen. That masking
let a narrow Mongo projection silently strip potential_factor from the pool read — the third
such loss — and only a manual FPD snapshot caught it. These assert the fields are actually
PRESENT on the persisted doc, through a real mongomock projection, so a future drop fails a test
instead of shipping. Applies to all three fields, which share the fallback-masking property.
"""
import mongomock

from BackEnd.models.franchise_manager import (
    POOL_TO_FPD_CARRY_FIELDS,
    POOL_TO_FPD_PROJECTION,
)

# The trio whose read-side fallback masks a dropped write.
MASKED = ("entry_tier", "position_intent", "potential_factor")


def test_carry_list_includes_the_fallback_masked_trio():
    for f in MASKED:
        assert f in POOL_TO_FPD_CARRY_FIELDS, f"{f} must be carried pool→FPD"


def test_projection_preserves_every_carried_field():
    # Structural guarantee: the projection is built from the carry list, so it cannot drop a
    # field the carry reads. This is the invariant the bug violated.
    for f in POOL_TO_FPD_CARRY_FIELDS:
        assert POOL_TO_FPD_PROJECTION.get(f) == 1, \
            f"projection omits {f} — the carry's p.get('{f}') would silently be None"


def test_projected_pool_doc_carries_the_fields_through_mongomock():
    """A real projection through mongomock: seed a pool player WITH the fields, run the exact
    init projection, build the carry the way init does, and assert every field is present and
    non-None on the resulting FPD doc — the check that would have caught the silent strip."""
    col = mongomock.MongoClient().db.players
    col.insert_one({
        "_id": "pool-1", "first_name": "A", "last_name": "B", "team": "X",
        "attributes": {"SC": 60}, "position_ratings": {"SF": 60},
        "entry_tier": "Average", "position_intent": "SF", "potential_factor": 1.07,
    })
    doc = col.find_one({}, POOL_TO_FPD_PROJECTION)
    fpd_carry = {f: doc.get(f) for f in POOL_TO_FPD_CARRY_FIELDS}  # exactly how init builds it
    for f in MASKED:
        assert f in fpd_carry and fpd_carry[f] is not None, \
            f"{f} absent from the FPD doc — a narrow projection dropped it (the masked bug)"
    assert fpd_carry["potential_factor"] == 1.07
    assert fpd_carry["entry_tier"] == "Average"
    assert fpd_carry["position_intent"] == "SF"


def test_the_old_narrow_projection_would_fail_this_check():
    """Teeth: the pre-fix projection (no potential_factor) strips it silently — proving the
    presence check above actually catches the regression it was written for."""
    buggy = {k: v for k, v in POOL_TO_FPD_PROJECTION.items() if k != "potential_factor"}
    col = mongomock.MongoClient().db.players
    col.insert_one({"_id": "p", "entry_tier": "Good", "position_intent": "PG",
                    "potential_factor": 0.9})
    doc = col.find_one({}, buggy)
    assert doc.get("potential_factor") is None  # silently gone under the narrow projection
