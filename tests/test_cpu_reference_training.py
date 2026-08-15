"""Locks the CPU-reference-training coupling: the tuned per-position bases
(_CPU_REFERENCE_BASE_BY_POS) and the frozen coaching-quality reference are two
constants that MUST agree, so CPU scores ~1.0 per position and the league sits
on the ladder once quality is live. Bases must also fit the flat player-point
share after the shared team/breaks footprint. A change to either the reference or a
base, without re-fitting, breaks a test here instead of silently drifting the
league. Models the effective allocation as base × mean-focus-amplifier on each
player's reference top-3 (what player-maximizer-custom produces at CPU scale).

⚠️ **THIS NO LONGER DESCRIBES WHAT CPU TEAMS TRAIN (2026-08-12).** CPU auto-train now
submits ONE team-wide plan (`_cpu_team_allocation`), the same shape a user does, rather
than a per-position plan per group. `_CPU_REFERENCE_BASE_BY_POS` and
`_coaching_quality_reference_allocation` survive as the coaching-quality YARDSTICK and are
still worth locking — but a green run here says nothing about CPU training behaviour, and
this file kept passing straight through the change that decoupled them. If you are looking
for what CPU teams actually train, see `projects/cpu_identity_training_design.md`."""
from BackEnd.utils import player_development as dev

POS = ("PG", "SG", "SF", "PF", "C")
_TEAM_RAW = 8  # breaks 1 + team drills 7
_PLAYER_BUDGET = 24 - _TEAM_RAW


def _cpu_qualities():
    from BackEnd.api.franchise_routes import (
        _CPU_REFERENCE_BASE_BY_POS, _CPU_FOCUS_AMP_MEAN, _cpu_reference_top3,
    )
    out = {}
    for p in POS:
        top3 = set(_cpu_reference_top3(p))
        assert len(top3) == 3, f"{p}: reference top-3 must be exactly 3 (custom focus requires it)"
        base = _CPU_REFERENCE_BASE_BY_POS[p]
        eff = {a: base.get(a, 0) * (_CPU_FOCUS_AMP_MEAN if a in top3 else 1.0)
               for a in dev.GROWTH_ATTRS}
        out[p] = dev.season_coaching_quality(eff, p)
    return out


def test_cpu_reference_training_scores_one_per_position():
    """CPU trains the reference → every position scores ~1.0 with a small residual."""
    qs = _cpu_qualities()
    for p, q in qs.items():
        assert abs(q - 1.0) < 0.03, (
            f"{p}: CPU coaching quality {q:.3f} drifted from 1.0 — the tuned base and the "
            f"frozen reference no longer agree; re-fit _CPU_REFERENCE_BASE_BY_POS.")
    spread = max(qs.values()) - min(qs.values())
    assert spread < 0.08, f"per-position CPU quality spread {spread:.3f} too wide"


def test_cpu_reference_bases_fit_flat_player_budget():
    from BackEnd.api.franchise_routes import _CPU_REFERENCE_BASE_BY_POS
    for p in POS:
        spend = sum(int(v or 0) for v in _CPU_REFERENCE_BASE_BY_POS[p].values())
        assert spend <= _PLAYER_BUDGET, (
            f"{p}: player-attr points {spend} exceed budget {_PLAYER_BUDGET}"
        )


def test_cpu_focus_targets_are_the_frozen_reference_top3():
    """The CPU custom-focus attrs ARE the reference's emphasised (primary) attrs —
    read from reference_allocation, never hardcoded."""
    from BackEnd.api.franchise_routes import _cpu_reference_top3
    for p in POS:
        ref = dev.reference_allocation(p)
        primary = {a for a, pts in ref.items() if pts == dev.COACHING_REFERENCE_PRIMARY_PTS}
        assert set(_cpu_reference_top3(p)) == primary, p


def test_cpu_custom_focus_valid_for_every_player():
    """Every roster player gets exactly 3 distinct valid attrs (custom-focus contract),
    keyed by player id."""
    from BackEnd.api.franchise_routes import _cpu_reference_custom_focus
    from BackEnd.models.training_execution_v2 import PLAYER_MAXIMIZER_RANKING_ATTRS
    allowed = set(PLAYER_MAXIMIZER_RANKING_ATTRS)
    players = [{"_id": "p1"}, {"_id": "p2"}, {"_id": "p3"}]
    fpd = {"p1": {"position_intent": "PG"}, "p2": {"position_intent": "C"},
           "p3": {"position_ratings": {"SF": 60, "PG": 30}}}  # position_intent absent → RT fallback
    cf = _cpu_reference_custom_focus(players, fpd)
    assert set(cf.keys()) == {"p1", "p2", "p3"}
    for pid, attrs in cf.items():
        assert len(attrs) == 3 and len(set(attrs)) == 3, pid
        assert all(a in allowed for a in attrs), pid
