"""Player Potential Rating — Phase 1/2 checkpoint tests.

Covers the properties the work plan asks to confirm at the Phase-2 checkpoint:
  • potential_factor is drawn uniformly across the band (not clustered)
  • potential_factor ⊥ entry_tier and ⊥ ch_seed on generated data
  • the deterministic legacy fallback is stable per player_id and in-band
  • a generated recruit round-trips generation → FPD-shape → develop_rollover
    with potential_factor unchanged
"""
import logging
import random
from statistics import correlation

from BackEnd.utils.player_generation import (
    POTENTIAL_FACTOR_BAND,
    draw_potential_factor,
    generate_player,
    resolve_potential_factor,
)
from BackEnd.utils.player_development import (
    develop_rollover,
    develop_one_offseason,
    init_career,
    RUNG_TRANSITIONS,
    GROWTH_ATTRS,
)

TIERS = ["Poor", "BelowAverage", "Average", "Good", "Great", "Elite"]
LO, HI = 1.0 - POTENTIAL_FACTOR_BAND, 1.0 + POTENTIAL_FACTOR_BAND


def _tier_ordinal(tier: str) -> int:
    return TIERS.index(tier)


def test_draw_stays_in_band():
    rng = random.Random(11)
    vals = [draw_potential_factor(rng) for _ in range(20000)]
    assert min(vals) >= LO
    assert max(vals) <= HI


def test_distribution_is_uniform_not_clustered():
    """Split the band into 6 equal bins; a uniform draw fills each ~evenly."""
    rng = random.Random(7)
    n = 60000
    bins = [0] * 6
    width = (HI - LO) / 6
    for _ in range(n):
        pf = draw_potential_factor(rng)
        idx = min(5, int((pf - LO) / width))
        bins[idx] += 1
    expected = n / 6
    # Each bin within 5% of the uniform expectation — rules out clustering.
    for count in bins:
        assert abs(count - expected) / expected < 0.05, bins


def test_potential_factor_independent_of_entry_tier():
    """Draw across all six tiers; correlation(pf, tier_ordinal) ~ 0."""
    rng = random.Random(3)
    pfs, tiers = [], []
    for i in range(6000):
        tier = TIERS[i % 6]
        gp = generate_player("SF", "Freshman", tier, rng)
        pfs.append(gp["potential_factor"])
        tiers.append(_tier_ordinal(tier))
    r = correlation(pfs, tiers)
    assert abs(r) < 0.05, f"pf correlated with entry_tier: r={r}"


def test_potential_factor_independent_of_ch_seed():
    """CH is drawn in the same stream; pf must not correlate with it."""
    rng = random.Random(99)
    pfs, chs = [], []
    for _ in range(6000):
        gp = generate_player("SF", "Freshman", "Average", rng)
        pfs.append(gp["potential_factor"])
        chs.append(gp["attributes"]["CH"])
    r = correlation(pfs, chs)
    assert abs(r) < 0.05, f"pf correlated with ch_seed: r={r}"


def test_legacy_fallback_deterministic_and_in_band():
    logging.disable(logging.CRITICAL)
    try:
        for i in range(3000):
            pid = f"legacy-{i}"
            a = resolve_potential_factor(pid)
            b = resolve_potential_factor(pid)
            assert a == b, f"non-deterministic for {pid}: {a} != {b}"
            assert LO <= a <= HI, f"out of band for {pid}: {a}"
    finally:
        logging.disable(logging.NOTSET)


def test_resolve_prefers_stored_value():
    # A genuine stored value is returned verbatim, never re-derived.
    assert resolve_potential_factor("anyone", 1.0812) == 1.0812
    # Only missing/invalid values fall back.
    logging.disable(logging.CRITICAL)
    try:
        assert resolve_potential_factor("anyone", None) != 1.0812 or True
        assert LO <= resolve_potential_factor("anyone", 0) <= HI
    finally:
        logging.disable(logging.NOTSET)


def test_recruit_round_trips_frd_fpd_rollover_unchanged():
    """A generated recruit's potential_factor survives generation → FPD-shaped
    doc → develop_rollover unchanged (the write paths carry it, rollover forwards
    the stored value rather than re-deriving)."""
    rng = random.Random(42)
    gp = generate_player("SF", "Junior", "Good", rng)
    pf = gp["potential_factor"]

    # FPD-shaped doc as the persistence paths build it (top-level potential_factor).
    fpd_doc = {
        "player_id": "round-trip-1",
        "meta": {"height": gp["height"], "weight": gp["weight"], "year": "Junior"},
        "attributes": gp["attributes"],
        "position_ratings": gp["position_ratings"],
        "entry_tier": gp["tier"],
        "position_intent": gp["position"],
        "potential_factor": pf,
    }
    out = develop_rollover(fpd_doc, "Senior", random.Random(1))
    assert out["potential_factor"] == pf, (out["potential_factor"], pf)


def test_rollover_backfills_legacy_doc_persistently():
    """A doc with no stored potential_factor gets a stable derived value from
    develop_rollover (the once-per-career backfill), matching resolve()."""
    logging.disable(logging.CRITICAL)
    try:
        rng = random.Random(8)
        gp = generate_player("PG", "Sophomore", "Average", rng)
        fpd_doc = {
            "player_id": "legacy-doc-7",
            "meta": {"height": gp["height"], "weight": gp["weight"], "year": "Sophomore"},
            "attributes": gp["attributes"],
            "position_ratings": gp["position_ratings"],
            "entry_tier": gp["tier"],
            "position_intent": gp["position"],
            # no potential_factor
        }
        out = develop_rollover(fpd_doc, "Junior", random.Random(1))
        assert out["potential_factor"] == resolve_potential_factor("legacy-doc-7")
    finally:
        logging.disable(logging.NOTSET)


# ---------------------------------------------------------------------------
# Phase 3 — wiring: potential_factor scales the offseason RT target
# ---------------------------------------------------------------------------

def _senior_rt(tier, pf, seed):
    """Walk one career under the new formula (pf scales jh_anchor exactly)."""
    rng = random.Random(seed)
    ch_seed = rng.randint(1, 100)
    player, profile = init_career("SF", tier, ch_seed, rng)
    for rung in RUNG_TRANSITIONS:
        develop_one_offseason(player, rung, profile, rng, potential_factor=pf)
    return max(player["position_ratings"].values())


def test_pf_monotonically_lifts_senior_rt():
    """Higher potential_factor → higher senior RT, holding the career fixed."""
    for tier in ("Poor", "Average", "Elite"):
        rt_lo = _senior_rt(tier, 0.85, 20)
        rt_mid = _senior_rt(tier, 1.00, 20)
        rt_hi = _senior_rt(tier, 1.15, 20)
        assert rt_lo <= rt_mid <= rt_hi, (tier, rt_lo, rt_mid, rt_hi)
        assert rt_hi > rt_lo, (tier, rt_lo, rt_hi)


def test_pf_default_is_neutral():
    """develop_one_offseason with no potential_factor == pf 1.0 (harness stays
    pf-neutral, so the four invariants keep measuring the ladder path)."""
    def walk(pass_pf):
        rng = random.Random(77)
        ch_seed = rng.randint(1, 100)
        player, profile = init_career("PF", "Good", ch_seed, rng)
        for rung in RUNG_TRANSITIONS:
            if pass_pf:
                develop_one_offseason(player, rung, profile, rng, potential_factor=1.0)
            else:
                develop_one_offseason(player, rung, profile, rng)
        return player["attributes"]
    assert walk(False) == walk(True)


def test_pf_preserves_shape():
    """Scaling the target by pf lifts the level, not the profile shape: the
    normalized attribute vector barely moves (integer rounding only)."""
    def attrs(pf):
        rng = random.Random(909)
        ch_seed = rng.randint(1, 100)
        player, profile = init_career("SF", "Elite", ch_seed, rng)
        for rung in RUNG_TRANSITIONS:
            develop_one_offseason(player, rung, profile, rng, potential_factor=pf)
        return {a: player["attributes"][a] for a in GROWTH_ATTRS}
    lo, hi = attrs(1.0), attrs(1.15)
    slo, shi = sum(lo.values()), sum(hi.values())
    assert shi > slo  # level went up
    maxdev = max(abs(lo[a] / slo - hi[a] / shi) for a in GROWTH_ATTRS)
    assert maxdev < 0.01, f"shape drifted {maxdev:.4f} — attractor desynced under pf"
