from BackEnd.engine.motion_step_decision import (
    OUTSIDE_SHOT_MIN_GAP_BY_TIER,
    RANDOM_TIER_SHOOT_PCT,
    _outside_shot_is_eligible,
)


def test_random_tier_tunables_match_hco_balance_grid():
    assert RANDOM_TIER_SHOOT_PCT["early"] == {"slow": 10, "normal": 20, "fast": 30}
    assert RANDOM_TIER_SHOOT_PCT["mid"] == {"slow": 20, "normal": 35, "fast": 50}
    assert RANDOM_TIER_SHOOT_PCT["late"] == {"slow": 95, "normal": 95, "fast": 95}


def test_outside_gap_gate_relaxes_by_clock_tier():
    assert OUTSIDE_SHOT_MIN_GAP_BY_TIER == {
        "early": 11.0,
        "mid": 7.0,
        "late": 3.0,
        "very_late": 0.0,
        "forced": 0.0,
    }
    assert not _outside_shot_is_eligible("PG", "outside", 25, {"PG": 10.99})
    assert _outside_shot_is_eligible("PG", "outside", 25, {"PG": 11.0})
    assert not _outside_shot_is_eligible("PG", "outside", 18, {"PG": 6.99})
    assert _outside_shot_is_eligible("PG", "outside", 18, {"PG": 7.0})
    assert not _outside_shot_is_eligible("PG", "outside", 10, {"PG": 2.99})
    assert _outside_shot_is_eligible("PG", "outside", 10, {"PG": 3.0})
    assert _outside_shot_is_eligible("PG", "outside", 4, {"PG": 0.0})


def test_gap_gate_does_not_restrict_inside_or_attack_candidates():
    assert _outside_shot_is_eligible("PG", "inside", 30, {"PG": 0.0})
    assert _outside_shot_is_eligible("PG", "attack", 30, {"PG": 0.0})


def test_authoritative_map_missing_candidate_rejects_early_outside():
    assert not _outside_shot_is_eligible("PG", "outside", 30, {})
    # Specialized callers without a geometry contract retain legacy behavior.
    assert _outside_shot_is_eligible("PG", "outside", 30, None)
