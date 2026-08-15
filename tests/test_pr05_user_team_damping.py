"""PR0.5 — the existing margin damping now applies to a leading USER team in full sim.

WHY THIS EXISTS. The blowout systems had never once been applied to the team doing the blowing
out. Matched pair on the prod season (franchise 6a8073d78294292a794bec4c): HA Rushmore (user) and
Couer d'Alene (CPU), talent 563.8 vs 564, both 26-0, identical Run and Gun / Full-Court Press
vision pair. Cumulative margin by quarter:

    Rushmore       Q1 10.7   half 18.2   Q3 27.2   final 33.3
    Couer d'Alene  Q1 10.1   half 17.6   Q3 19.4   final 19.9

Level through halftime (+0.6). Second half: +15.1 vs +2.3. Talent would show in the first half;
it does not. The divergence opens exactly as the lead crosses 20 — the conservative-strategy
threshold — which the CPU team had and the user team was excluded from.

WHAT THESE TESTS PIN
  1. Full sim: a leading user team IS damped.
  2. Turn-by-turn: it is NOT (governor spec A2 — the user owns subs and playcalls there).
  3. The user's PLAN survives: `strategy_settings_base` is byte-identical across damping, and the
     games-doc snapshot persists the plan rather than the damped view.
  4. Regression, pre-dating PR0.5: autoset must not adopt a DAMPED `strategy_settings` as `base`.
     Reachable via timeout-resume, which rehydrates a team from the games-doc snapshot
     (team_settings_manager.extract_team_settings). Before PR0.5 that snapshot held damped values,
     so a resumed leading team promoted its damping to its plan permanently.
"""

import copy

import pytest

from BackEnd.utils import db_utils
from BackEnd.utils.db_utils import (
    _blowout_lineup_active,
    _conservative_strategy_active,
    autoset_strategy_settings,
)


PLAN = {
    "offense": 3, "inside": 2, "attack": 3, "outside": 2, "fast_breaks": 4,
    "play_calling": 2, "defense": 1, "aggression": 4, "hc_trap": 3, "fc_press": 3,
    "rebounding": 3, "tempo": 4, "alterations": 2,
}


class _Team:
    """Minimal TeamManager stand-in. Only what the damping path reads."""

    def __init__(self, is_user_team, name="T"):
        self.name = name
        self.is_user_team = is_user_team
        self.strategy_settings = dict(PLAN)
        self.team_attributes = {}
        self.players = {}
        self.lineup = {}

    def _compute_strategic_strategy_settings(self, game_state):  # pragma: no cover - not reached
        return dict(PLAN)


def _state(margin, quarter=3, full_sim=True, time_remaining=400):
    """game_state with the team leading by `margin`."""
    gs = {
        "quarter": quarter,
        "time_remaining": time_remaining,
        "score": {"T": 80, "OPP": 80 - margin},
    }
    if full_sim:
        gs["_is_full_simulation"] = True
    return gs


@pytest.fixture(autouse=True)
def _patch_teammanager(monkeypatch):
    """_blowout_lineup_active isinstance-checks TeamManager; accept the stand-in."""
    monkeypatch.setattr(db_utils, "TeamManager", _Team)


@pytest.fixture(autouse=True)
def _seeded():
    """The conservative override uses weighted rolls. Seed so the assertions are stable."""
    db_utils.random.seed(20260815)


def _margin_ok():
    """Skip cleanly if the stand-in cannot express a margin to the real helper."""
    return db_utils._team_score_margin(_Team(False), _state(40)) is not None


# ── 1 + 2. the gate ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("is_user", [False, True])
def test_full_sim_damps_a_big_lead_for_either_team(is_user):
    """The whole point of PR0.5: in full sim, user and CPU are treated the same.

    Asserts through autoset_strategy_settings, NOT _conservative_strategy_active — the latter
    never consulted `is_user_team`, so asserting on it passes with or without the fix and pins
    nothing. The gate lives in autoset.
    """
    if not _margin_ok():
        pytest.skip("margin helper needs a richer team stub")
    team = _Team(is_user_team=is_user)
    gs = _state(40)
    assert _conservative_strategy_active(team, gs) is True, "precondition: the lead is damp-worthy"

    effective = autoset_strategy_settings(team, gs)
    damped = [k for k in db_utils._CONSERVATIVE_STRATEGY_ROLLS if effective.get(k) != PLAN[k]]
    assert damped, (
        f"a leading {'user' if is_user else 'CPU'} team was not damped in full sim; "
        f"effective settings still match the plan"
    )
    assert team.strategy_settings_base == PLAN, "the plan must survive"


def test_turn_by_turn_never_damps_a_user_team():
    """Play Quarter: the user owns subs and playcalls (governor spec A2)."""
    if not _margin_ok():
        pytest.skip("margin helper needs a richer team stub")
    user = _Team(is_user_team=True)
    gs = _state(40, full_sim=False)
    assert _blowout_lineup_active(user, gs) is False
    before = dict(user.strategy_settings)
    autoset_strategy_settings(user, gs)
    assert user.strategy_settings == before, "turn-by-turn must not touch the user's settings"


def test_turn_by_turn_still_damps_a_cpu_team():
    """The gate is on the USER, not on the mode — CPU damping is unchanged everywhere."""
    if not _margin_ok():
        pytest.skip("margin helper needs a richer team stub")
    cpu = _Team(is_user_team=False)
    assert _conservative_strategy_active(cpu, _state(40, full_sim=False)) is True


# ── 3. the user's plan survives ──────────────────────────────────────────────────────────

def test_user_plan_is_byte_identical_after_damping():
    """`strategy_settings_base` is the plan and must not move, however hard the view is damped.

    Asserts on base rather than on `strategy_settings`: under this design the live view is
    EXPECTED to change — that is the feature. The plan is what must not.
    """
    if not _margin_ok():
        pytest.skip("margin helper needs a richer team stub")
    user = _Team(is_user_team=True)
    plan_before = copy.deepcopy(user.strategy_settings)

    for quarter, margin in ((3, 40), (3, 5), (4, 60), (4, 0), (3, 35)):
        autoset_strategy_settings(user, _state(margin, quarter=quarter))

    assert user.strategy_settings_base == plan_before, (
        "the user's PLAN moved during a simulated game — this is the corruption PR0.5 must not cause"
    )


def test_snapshot_persists_the_plan_not_the_damped_view():
    """The games-doc snapshot feeds the Gameplan UI and timeout-resume. Both want the plan."""
    if not _margin_ok():
        pytest.skip("margin helper needs a richer team stub")
    from BackEnd.api.api import _persisted_strategy_settings

    user = _Team(is_user_team=True)
    autoset_strategy_settings(user, _state(60, quarter=4, time_remaining=100))
    assert _persisted_strategy_settings(user) == PLAN

    fresh = _Team(is_user_team=True)          # never reached autoset -> no base
    assert _persisted_strategy_settings(fresh) == PLAN


# ── 4. the latent bug, pre-dating PR0.5 ──────────────────────────────────────────────────

def test_autoset_does_not_promote_damped_settings_to_the_plan():
    """REGRESSION, and it predates PR0.5.

    autoset adopts `strategy_settings` as `base` when base is absent. Timeout-resume rehydrates a
    team from the games-doc snapshot, so before this change a team that was leading when the game
    was saved came back with DAMPED settings and no base — and autoset promoted the damping to
    its plan permanently. Persisting `strategy_settings_base` is what closes it; this pins the
    consequence rather than the mechanism, so it still fails if the snapshot regresses.
    """
    if not _margin_ok():
        pytest.skip("margin helper needs a richer team stub")
    from BackEnd.api.api import _persisted_strategy_settings

    leading = _Team(is_user_team=True)
    autoset_strategy_settings(leading, _state(60, quarter=4, time_remaining=100))
    damped_view = dict(leading.strategy_settings)

    snapshot = _persisted_strategy_settings(leading)     # what a save would write

    resumed = _Team(is_user_team=True)                   # fresh object, as on resume
    resumed.strategy_settings = dict(snapshot)           # rehydrated from the games doc
    autoset_strategy_settings(resumed, _state(0, quarter=1))   # no lead -> no damping

    assert resumed.strategy_settings_base == PLAN, (
        "a resumed team adopted a damped view as its plan — the snapshot must carry the plan"
    )
    if damped_view != PLAN:
        assert snapshot != damped_view, "the snapshot captured the damped view, not the plan"
