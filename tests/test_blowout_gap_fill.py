"""The foul-out gap-filler honours the blowout lineup.

`fill_unified_lineup_gaps` had no blowout parameter, so a foul-out in garbage time seated the
BEST available player — undoing, one slot at a time, the thing the blowout lineup exists to do.

Scope is narrower than it looks and these tests pin that too: the primary full-sim foul-out
path never reaches the gap-filler (game_manager.py:692 skips it and defers to
`_rebuild_both_lineups_for_full_sim_break`, which was already blowout-aware). The live
exposures were turn-by-turn CPU foul-outs and the `_check_lineups_for_foul_out` safety-net
sweep — the only call site in the codebase letting `perform_removal` default to True.
"""

import pytest

from BackEnd.utils import db_utils
from BackEnd.utils.db_utils import fill_unified_lineup_gaps, _player_rt_max


POSITIONS = ["PG", "SG", "SF", "PF", "C"]


class _P:
    """Player stand-in. Only what the selector reads: id, and a per-position rating."""

    def __init__(self, pid, rating):
        self.player_id = pid
        self._rating = rating

    def __repr__(self):
        return f"<{self.player_id} rt={self._rating}>"


@pytest.fixture(autouse=True)
def _flat_ratings(monkeypatch):
    """Every player rates the same at every position, so RT ordering is unambiguous.

    Position fit is a separate concern; mixing it in here would make a failure ambiguous
    between "picked the wrong five" and "seated them wrong".
    """
    monkeypatch.setattr(db_utils, "_player_slot_rating", lambda p, pos: p._rating)


def _bench(n=8):
    """Ratings 10, 20, ... — index 0 is the worst player, index -1 the best."""
    return [_P(f"p{i}", (i + 1) * 10) for i in range(n)]


def test_normal_fill_takes_the_best_available():
    """Unchanged behaviour when no blowout is active — this is the baseline."""
    pool = _bench()
    seated = {p: _P(f"seated{p}", 5) for p in POSITIONS[:4]}
    out = fill_unified_lineup_gaps(pool, 15.0, ["C"], existing_assignments=seated)
    assert out["C"] is pool[-1], "without a blowout the gap must take the BEST available"


def test_blowout_fill_takes_the_worst_available():
    """The fix: in garbage time the walk-on is the lowest-RT player, not the best."""
    pool = _bench()
    seated = {p: _P(f"seated{p}", 5) for p in POSITIONS[:4]}
    out = fill_unified_lineup_gaps(
        pool, 15.0, ["C"], existing_assignments=seated, prefer_lowest_rt=True
    )
    assert out["C"] is pool[0], "in a blowout the gap must take the LOWEST-RT available"


def test_surviving_slots_are_never_disturbed():
    """The whole point of the gap-filler: the four who did not foul out stay put."""
    pool = _bench()
    seated = {p: _P(f"seated{p}", 5) for p in POSITIONS[:4]}
    before = dict(seated)
    out = fill_unified_lineup_gaps(
        pool, 15.0, ["C"], existing_assignments=seated, prefer_lowest_rt=True
    )
    for pos, player in before.items():
        assert out[pos] is player, f"{pos} was reseated; only the missing slot may change"


def test_multi_slot_blowout_fill_takes_the_n_worst():
    """Two slots open -> the two lowest-RT players, not two arbitrary low ones."""
    pool = _bench()
    seated = {p: _P(f"seated{p}", 5) for p in POSITIONS[:3]}
    out = fill_unified_lineup_gaps(
        pool, 15.0, ["PF", "C"], existing_assignments=seated, prefer_lowest_rt=True
    )
    assert {out["PF"], out["C"]} == {pool[0], pool[1]}


def test_already_seated_players_are_not_reused():
    """A player holding a surviving slot must not also be picked for the open one."""
    pool = _bench()
    dupe = pool[0]
    seated = {"PG": dupe, "SG": pool[5], "SF": pool[6], "PF": pool[7]}
    out = fill_unified_lineup_gaps(
        pool, 15.0, ["C"], existing_assignments=seated, prefer_lowest_rt=True
    )
    assert out["C"] is not dupe, "the lowest-RT player was already on the floor"
    assert out["C"] is pool[1], "should fall through to the next-lowest available"


def test_insufficient_players_still_raises():
    """The blowout path must not paper over an unfillable lineup."""
    with pytest.raises(ValueError):
        fill_unified_lineup_gaps(
            [], 15.0, ["C"], existing_assignments={}, prefer_lowest_rt=True
        )


def test_selection_is_deterministic_on_rt_ties():
    """Ties break on player_id, so the same foul-out never produces two different walk-ons."""
    tied = [_P(f"z{i}", 50) for i in range(5)] + [_P("a_low", 10)]
    seated = {p: _P(f"seated{p}", 5) for p in POSITIONS[:4]}
    first = fill_unified_lineup_gaps(
        list(tied), 15.0, ["C"], existing_assignments=dict(seated), prefer_lowest_rt=True
    )["C"]
    for _ in range(5):
        again = fill_unified_lineup_gaps(
            list(reversed(tied)), 15.0, ["C"],
            existing_assignments=dict(seated), prefer_lowest_rt=True,
        )["C"]
        assert again.player_id == first.player_id


def test_rt_is_max_across_positions_not_the_open_slot():
    """Blowout selection ranks on `_player_rt_max`, matching the full-autoset inversion.

    A player who is poor at the open position but excellent elsewhere is still a STARTER and
    must not be the garbage-time pick. Ranking on the open slot's rating alone would seat him.
    """
    import BackEnd.utils.db_utils as du

    star_bad_at_c = _P("star", 0)
    scrub = _P("scrub", 0)
    ratings = {("star", "C"): 5, ("scrub", "C"): 40}
    for pos in POSITIONS:
        ratings.setdefault(("star", pos), 95)
        ratings.setdefault(("scrub", pos), 40)

    import pytest as _pytest
    mp = _pytest.MonkeyPatch()
    mp.setattr(du, "_player_slot_rating", lambda p, pos: ratings[(p.player_id, pos)])
    try:
        assert _player_rt_max(star_bad_at_c) > _player_rt_max(scrub)
        seated = {p: _P(f"seated{p}", 5) for p in POSITIONS[:4]}
        out = fill_unified_lineup_gaps(
            [star_bad_at_c, scrub], 15.0, ["C"],
            existing_assignments=seated, prefer_lowest_rt=True,
        )
        assert out["C"] is scrub, "ranked on the open slot instead of RT-max — star benched wrongly"
    finally:
        mp.undo()
