"""Box-out contest (Model C): pairing geometry, the ST roll, the push-back, and the
clairvoyance guard that keeps all three blind to the outcome.

The point of the guard: a box-out resolves when the ball leaves the shooter's hand.
If it could see the bounce, every defender would box out the man nearest where the ball
is actually going, and rebounding would collapse the same way crash destinations would.
`crash_destination` has its own allowlist for this; these are the box-out's.
"""
import ast
import inspect
import random

import pytest

from BackEnd.utils import boxout_contest as BO


class _P:
    def __init__(self, pid, x, y, st=50, rb=None, iq=None, ch=None):
        self.player_id = pid
        self.coords = {"x": float(x), "y": float(y)}
        # Stage 2: the contest scores a composite, so a player needs all four. Defaulting
        # RB/IQ/CH to ST keeps the single-argument `_P(pid, x, y, st=N)` calls meaningful -
        # such a player has composite == N, so the ST-gap tests still read as written.
        self.attributes = {"ST": st,
                           "RB": st if rb is None else rb,
                           "IQ": st if iq is None else iq,
                           "CH": st if ch is None else ch}


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setenv("GOB_BOXOUT_CONTEST", "1")


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("GOB_BOXOUT_CONTEST", raising=False)
    assert BO.enabled() is False
    monkeypatch.setenv("GOB_BOXOUT_CONTEST", "1")
    assert BO.enabled() is True


# ── Stage 1: pairing geometry ───────────────────────────────────────────────────────────

def test_pairs_with_the_nearest_offensive_crasher_inside_the_radius():
    d = _P("d", 50, 25)
    near, far = _P("near", 54, 25), _P("far", 59, 25)
    pairs = BO.find_boxout_pairs([d], [far, near])
    assert [(p[0].player_id, p[1].player_id) for p in pairs] == [("d", "near")]


def test_nobody_outside_the_radius_is_paired():
    d = _P("d", 50, 25)
    out = _P("out", 50 + BO.BOXOUT_PAIR_RADIUS + 0.01, 25)
    assert BO.find_boxout_pairs([d], [out]) == []


def test_exactly_on_the_radius_pairs():
    d = _P("d", 50, 25)
    edge = _P("edge", 50 + BO.BOXOUT_PAIR_RADIUS, 25)
    assert len(BO.find_boxout_pairs([d], [edge])) == 1


def test_each_player_is_in_at_most_one_pair():
    d1, d2 = _P("d1", 50, 25), _P("d2", 51, 25)
    only = _P("o", 52, 25)
    pairs = BO.find_boxout_pairs([d1, d2], [only])
    assert len(pairs) == 1
    assert pairs[0][0].player_id == "d1"          # first defender takes him
    assert len({p[1].player_id for p in pairs}) == 1


def test_one_contest_per_pair_and_no_player_twice():
    defs = [_P(f"d{i}", 50 + i, 25) for i in range(5)]
    offs = [_P(f"o{i}", 50 + i, 26) for i in range(5)]
    pairs = BO.find_boxout_pairs(defs, offs)
    assert len({p[0].player_id for p in pairs}) == len(pairs)
    assert len({p[1].player_id for p in pairs}) == len(pairs)


def test_equidistant_tiebreak_is_stable_and_order_based():
    """Two candidates exactly equidistant -> the one earlier in the offense order."""
    d = _P("d", 50, 25)
    a, b = _P("a", 50, 22), _P("b", 50, 28)   # both exactly 3 away
    assert BO.find_boxout_pairs([d], [a, b])[0][1].player_id == "a"
    assert BO.find_boxout_pairs([d], [b, a])[0][1].player_id == "b"


def test_pairing_consumes_no_rng():
    """Stage 1 is pure geometry - the house pattern (find_pass_contester) and the brief."""
    from BackEnd.utils.sim_random import sim_rng
    defs = [_P(f"d{i}", 50 + i, 25) for i in range(5)]
    offs = [_P(f"o{i}", 50 + i, 27) for i in range(5)]
    before = sim_rng.getstate()
    BO.find_boxout_pairs(defs, offs)
    assert sim_rng.getstate() == before


def test_pairing_is_deterministic_across_repeats():
    defs = [_P(f"d{i}", 50 + i, 25) for i in range(5)]
    offs = [_P(f"o{i}", 50 + i * 1.5, 27) for i in range(5)]
    once = [(a.player_id, b.player_id, round(g, 6)) for a, b, g in BO.find_boxout_pairs(defs, offs)]
    for _ in range(20):
        again = [(a.player_id, b.player_id, round(g, 6)) for a, b, g in BO.find_boxout_pairs(defs, offs)]
        assert again == once


def test_players_without_coords_are_skipped_not_guessed():
    d = _P("d", 50, 25)
    blind = _P("blind", 0, 0)
    blind.coords = {}
    assert BO.find_boxout_pairs([d], [blind]) == []
    assert BO.find_boxout_pairs([blind], [d]) == []


# ── Stage 2: the ST roll ────────────────────────────────────────────────────────────────

def test_score_is_the_weighted_composite_times_a_d6():
    """Stage 2: (0.4*RB + 0.4*ST + 0.1*IQ + 0.1*CH) x rand(1,6), not pure ST."""
    p = _P("p", 0, 0, st=40, rb=80, iq=20, ch=60)
    composite = 0.4 * 80 + 0.4 * 40 + 0.1 * 20 + 0.1 * 60   # = 56.0
    seen = {BO.boxout_score(p, rng=random.Random(i)) for i in range(200)}
    assert seen <= {composite * k for k in range(1, 7)}
    assert len(seen) == 6


def test_the_weights_are_named_sum_to_one_and_are_the_only_tuning_surface():
    assert BO.BOXOUT_SCORE_WEIGHTS == {"RB": 0.4, "ST": 0.4, "IQ": 0.1, "CH": 0.1}
    assert sum(BO.BOXOUT_SCORE_WEIGHTS.values()) == pytest.approx(1.0)


def test_rebounding_now_counts_where_it_did_not_before():
    """The point of Stage 2: a better rebounder beats an equally strong man."""
    strong_only = _P("s", 0, 0, st=70, rb=30, iq=50, ch=50)
    rebounder = _P("r", 1, 0, st=70, rb=90, iq=50, ch=50)
    assert BO.boxout_score(rebounder, rng=random.Random(3)) > \
           BO.boxout_score(strong_only, rng=random.Random(3))


def test_a_tie_goes_to_the_defender():
    d, o = _P("d", 0, 0, st=50), _P("o", 1, 0, st=50)

    class _Fixed:
        def randint(self, a, b):
            return 3          # identical rolls -> identical scores

    r = BO.resolve_boxout(d, o, rng=_Fixed())
    assert r["def_score"] == r["off_score"]
    assert r["defender_wins"] is True and r["winner"] is d and r["loser"] is o


def test_the_composite_tilts_but_does_not_dominate():
    """A big composite edge wins clearly more often, and clearly not always.

    `_P(..., st=N)` sets all four attributes to N, so the gap here is a composite gap.
    """
    def rate(st_d, st_o):
        rng = random.Random(7)
        w = sum(BO.resolve_boxout(_P("d", 0, 0, st_d), _P("o", 1, 0, st_o),
                                  rng=rng)["defender_wins"] for _ in range(4000))
        return 100.0 * w / 4000
    even, edge, big = rate(50, 50), rate(65, 50), rate(85, 50)
    assert edge > even, "a composite edge must raise the win rate"
    assert big > edge, "a bigger edge must raise it further"
    assert big < 90.0, "the composite must not dominate - the d6 keeps it human"


def test_the_loser_is_the_other_player():
    for st_d, st_o in ((90, 20), (20, 90)):
        r = BO.resolve_boxout(_P("d", 0, 0, st_d), _P("o", 1, 0, st_o), rng=random.Random(1))
        assert {r["winner"].player_id, r["loser"].player_id} == {"d", "o"}
        assert r["winner"] is not r["loser"]


# ── the push-back ───────────────────────────────────────────────────────────────────────

def _d(a, b):
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def test_push_back_moves_away_from_the_rim():
    rim_x = 91.0
    dest = {"x": 85.0, "y": 25.0}
    out = BO.push_back(dest, (70.0, 25.0), rim_x)
    assert out["x"] < dest["x"], "home rim is at x=91, so away from it is -x"
    assert _d(out, {"x": rim_x, "y": BO.RIM_Y}) > _d(dest, {"x": rim_x, "y": BO.RIM_Y})


def test_push_back_magnitude_is_the_declared_fraction_of_remaining_travel():
    dest, origin = {"x": 85.0, "y": 25.0}, (75.0, 25.0)     # travel = 10
    out = BO.push_back(dest, origin, 91.0)
    assert _d(out, dest) == pytest.approx(BO.BOXOUT_PUSHBACK_FRACTION * 10.0, abs=0.02)


def test_a_player_already_at_his_destination_is_not_moved():
    dest = {"x": 85.0, "y": 25.0}
    assert BO.push_back(dest, (85.0, 25.0), 91.0) == {"x": 85.0, "y": 25.0}


def test_push_back_is_clamped_to_the_court():
    out = BO.push_back({"x": 6.0, "y": 4.0}, (90.0, 45.0), 91.0)
    assert BO.COURT_X_MIN <= out["x"] <= BO.COURT_X_MAX
    assert BO.COURT_Y_MIN <= out["y"] <= BO.COURT_Y_MAX


def test_push_back_returns_a_new_dict_and_never_mutates():
    dest = {"x": 85.0, "y": 25.0}
    before = dict(dest)
    BO.push_back(dest, (70.0, 25.0), 91.0)
    assert dest == before


def test_push_back_consumes_no_rng():
    from BackEnd.utils.sim_random import sim_rng
    state = sim_rng.getstate()
    BO.push_back({"x": 85.0, "y": 25.0}, (70.0, 25.0), 91.0)
    assert sim_rng.getstate() == state


# ── clairvoyance ────────────────────────────────────────────────────────────────────────

#: Anything that could carry the outcome into a box-out.
OUTCOME_NAMES = {
    "bounce_spot", "ball_bounce", "ball_bounce_x", "ball_bounce_y", "result",
    "result_type", "made", "shot_made", "rebounder", "rebound", "turn_result",
    "free_throws", "outcome_known",
}


def _params(fn):
    return set(inspect.signature(fn).parameters)


@pytest.mark.parametrize("fn", [BO.find_boxout_pairs, BO.resolve_boxout,
                                BO.push_back, BO.boxout_score])
def test_no_public_entry_point_accepts_an_outcome_bearing_parameter(fn):
    assert _params(fn) & OUTCOME_NAMES == set(), fn.__name__


def _identifiers(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


def _module_body_without_docstrings(path):
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:]
    return tree


def test_the_module_never_names_the_outcome():
    """Docstrings may DISCUSS the bounce; the code must never touch it."""
    tree = _module_body_without_docstrings(BO.__file__)
    assert _identifiers(tree) & OUTCOME_NAMES == set()


def test_guard_detects_a_reinstated_outcome_read(tmp_path):
    p = tmp_path / "poison.py"
    p.write_text('"""bounce_spot in a docstring is fine."""\n'
                 "def f(dest, bounce_spot):\n    return bounce_spot\n")
    tree = _module_body_without_docstrings(str(p))
    assert _identifiers(tree) & OUTCOME_NAMES == {"bounce_spot"}


def test_the_call_site_does_not_hand_the_box_out_the_bounce():
    """shot_manager has `result` and `bounce_spot` in scope where the contest resolves."""
    import BackEnd.models.shot_manager as SM
    src = inspect.getsource(SM.ShotManager._prepare_crash_arrival)
    block = src.split("BOXOUT.enabled()")[1].split("probe = dict(result or {})")[0]
    assert "bounce_spot" not in block and "result" not in block
    assert "BOXOUT.find_boxout_pairs(" in block and "BOXOUT.push_back(" in block


def test_crash_destination_allowlist_is_untouched():
    """Model C must not have widened Model A's signature."""
    from BackEnd.utils import crash_destination as CD
    assert _params(CD.crash_destination) == {"shooter_x", "shooter_y", "rim_x", "tightness"}
