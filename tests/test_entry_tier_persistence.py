"""entry_tier must survive the recruit lifecycle, and the derive-from-RT fallback
must be year-aware.

Backstory: the FRD write dropped entry_tier, so signed recruits reached FPD without
it and develop_rollover re-derived it from their undeveloped JH RT via a YEAR-BLIND
formula — down-classifying every recruit ~1.5 tiers, permanently, for four seasons
before anyone noticed (RT held; only shooting attributes fell). These tests pin both
halves so the regression cannot return silently:

  1. a generated recruit round-trips FRD → FPD → rollover with entry_tier UNCHANGED
     (the fallback never fires for a recruit that carries its tier), and
  2. when the fallback DOES fire (legacy docs), it recovers the true tier instead of
     shifting it down.
"""
import logging
import random
import statistics

logging.disable(logging.CRITICAL)

from BackEnd.utils.player_generation import generate_player
from BackEnd.utils.player_development import (
    develop_rollover, _derive_entry_tier_from_rt, JH_ANCHOR_BY_TIER,
)

POSITIONS = ("PG", "SG", "SF", "PF", "C")
TIERS = ("Poor", "BelowAverage", "Average", "Good", "Great", "Elite")


def _fpd_from_recruit(recruit, pos, tier, *, carry_entry_tier: bool):
    """The FPD doc a signed recruit becomes. carry_entry_tier=True models the FIXED
    FRD→FPD path; False models the bug (field dropped) so the fallback fires."""
    doc = {
        "player_id": "r",
        "meta": {"year": recruit["year"], "height": recruit["height"], "weight": recruit["weight"]},
        "attributes": dict(recruit["attributes"]),
        "position_ratings": dict(recruit["position_ratings"]),
        "position_intent": pos,
    }
    if carry_entry_tier:
        doc["entry_tier"] = tier          # generate_recruits_list stamps this; FRD must persist it
    return doc


def test_recruit_entry_tier_round_trips_unchanged():
    """A recruit that carries its entry_tier keeps it through a rollover — the tier is
    NOT silently re-derived. This is the invariant the dropped-field bug violated."""
    rng = random.Random(7)
    for tier in TIERS:
        for pos in POSITIONS:
            recruit = generate_player(pos, "JH", tier, rng)          # recruits enter as JH
            doc = _fpd_from_recruit(recruit, pos, tier, carry_entry_tier=True)
            out = develop_rollover(doc, recruit["year"], random.Random(11))
            assert out["entry_tier"] == tier, (
                f"{pos}/{tier}: entry_tier changed to {out['entry_tier']!r} across a rollover — "
                f"a carried tier must never be re-derived.")


def test_derive_fallback_is_year_aware_no_downclassification():
    """When entry_tier is absent (legacy docs), the year-aware derive recovers the true
    tier rather than shifting it down. Pre-fix this biased the anchor ~-7 to -8 (≈1.5
    tiers); the invariant is near-zero mean bias."""
    rng = random.Random(3)
    true_anchors, derived_anchors = [], []
    for tier in TIERS:
        for _ in range(40):
            for pos in POSITIONS:
                r = generate_player(pos, "JH", tier, rng)
                # a JH recruit rolls onto FR; ratings still reflect JH
                derived = _derive_entry_tier_from_rt(r["position_ratings"], "FR")
                true_anchors.append(JH_ANCHOR_BY_TIER[tier])
                derived_anchors.append(JH_ANCHOR_BY_TIER[derived])
    bias = statistics.mean(derived_anchors) - statistics.mean(true_anchors)
    assert abs(bias) < 2.0, (
        f"derive-from-RT shifts tier by anchor {bias:+.1f} (was ~-8 pre-fix, i.e. ~1.5 "
        f"tiers down) — the year-blind formula has returned.")


def test_dropped_entry_tier_still_recovers_via_year_aware_fallback():
    """Belt and braces: even on the BUGGY path (entry_tier dropped), the fixed fallback
    lands the rolled player near his true tier instead of ~1.5 tiers below."""
    rng = random.Random(5)
    for tier in ("Average", "Good", "Great"):
        deltas = []
        for pos in POSITIONS:
            for _ in range(30):
                recruit = generate_player(pos, "JH", tier, rng)
                doc = _fpd_from_recruit(recruit, pos, tier, carry_entry_tier=False)
                out = develop_rollover(doc, recruit["year"], random.Random(99))
                deltas.append(JH_ANCHOR_BY_TIER[out["entry_tier"]] - JH_ANCHOR_BY_TIER[tier])
        mean_delta = statistics.mean(deltas)
        assert mean_delta > -3.0, (
            f"{tier}: fallback still down-classifies by anchor {mean_delta:+.1f} on the "
            f"dropped-field path.")
