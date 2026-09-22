"""`assign_all_zone_defenders` must not crash when no zone slot has boundaries.

`ball_handler_id` used to be bound ONLY inside the `for defender_pos in [PG..C]` loop,
whose first statement is `if defender_pos not in zone_boundaries: continue`. It is READ
again by the ball-handler assignment block AFTER that loop. With every slot missing from
`zone_boundaries`, all five iterations hit the `continue`, the name was never bound, and
the later read raised `UnboundLocalError` - killing the game mid-quarter. Seed 8093 hit
this live with GOB_BOXOUT_CONTEST=1 on both arms.

The fix hoists the binding above the loop, where it is always executed. That is the same
value the loop computed (the scan reads only `offensive_players`, which the function never
mutates), so it is a no-op wherever the code did not already raise.

See reports/zone-crash-and-arrival-cap-2026-09-20.md and the empty-zone branch already
flagged as suspect in reports/zone-empty-branch-2026-09-18.md.
"""
import ast
import inspect

import pytest

from BackEnd.utils.shared_defense import assign_all_zone_defenders


def _players(with_ball_handler=True):
    out = []
    for i, pos in enumerate(("PG", "SG", "SF", "PF", "C")):
        out.append({
            "player_id": f"o{i}",
            "coords": {"x": 60.0 + i, "y": 20.0 + i},
            "spot": "key",
            "is_ball_handler": with_ball_handler and i == 0,
        })
    return out


def _call(zone_boundaries, players):
    return assign_all_zone_defenders(
        zone_boundaries, players, {"x": 60.0, "y": 25.0}, "key", "normal", False,
    )


# ── the crash ───────────────────────────────────────────────────────────────────────────

def test_empty_zone_boundaries_returns_rather_than_raising():
    """The exact shape that killed seed 8093."""
    assignments, credit = _call({}, _players())
    assert isinstance(assignments, dict)
    assert isinstance(credit, dict)


def test_zone_boundaries_missing_every_lineup_slot_returns():
    """Non-empty, but no slot the loop iterates - the same all-five-continue path."""
    assignments, credit = _call({"ROVER": [(60.0, 20.0), (70.0, 30.0)]}, _players())
    assert isinstance(assignments, dict) and isinstance(credit, dict)


def test_it_also_survives_with_no_flagged_ball_handler():
    assignments, credit = _call({}, _players(with_ball_handler=False))
    assert isinstance(assignments, dict) and isinstance(credit, dict)


@pytest.mark.parametrize("players", [[], _players()])
def test_empty_boundaries_with_any_player_list(players):
    assignments, credit = _call({}, players)
    assert isinstance(assignments, dict) and isinstance(credit, dict)


# ── the ACTUAL live path: every present slot taken by an overlap assignment ─────────────

def test_all_five_slots_overlap_assigned_with_an_unguarded_ball_handler(monkeypatch):
    """The state seed 8093 was actually in, captured from the live crash.

    All five slots present WITH coords; two overlap players between them claiming every
    defender (SG+SF and PG+PF+C); one ball handler flagged, and not either overlap player.

    The per-defender loop has a SECOND `continue`: a defender with an overlap assignment
    guards that player and skips the rest of the body. With all five claimed, the loop
    never reached the binding - while the ball-handler fallback block below still found a
    `closest_defender`, because ITS loop has no such skip. That is what raised.
    """
    import BackEnd.utils.shared_defense as SD

    players = _players()                       # o0 is the ball handler
    box = [(55.0, 15.0), (75.0, 15.0), (75.0, 35.0), (55.0, 35.0)]
    zone_boundaries = {pos: list(box) for pos in ("PG", "SG", "SF", "PF", "C")}

    # exactly the captured shape: two overlap players covering all five defenders,
    # neither of them the ball handler
    monkeypatch.setattr(SD, "_detect_overlapping_zones",
                        lambda *a, **k: {"o1": ["SG", "SF"], "o2": ["PG", "PF", "C"]})
    monkeypatch.setattr(SD, "_resolve_overlap_assignments",
                        lambda pid, defs, *a, **k: {d: pid for d in defs})

    # The ball handler must be OUTSIDE every zone, or the first fallback check marks him
    # guarded at line "Is ball handler in any defender's zone?" and the block below - the
    # one that reads ball_handler_id - never runs.
    assignments, credit = SD.assign_all_zone_defenders(
        zone_boundaries, players, {"x": 20.0, "y": 5.0}, "key", "normal", True,
    )
    assert isinstance(assignments, dict) and isinstance(credit, dict)


# ── the structural guard that keeps it fixed ────────────────────────────────────────────

def _bh_lines():
    src = inspect.getsource(assign_all_zone_defenders)
    tree = ast.parse(src)
    fn = tree.body[0]
    loop = next(s for s in fn.body
                if isinstance(s, ast.For) and isinstance(s.iter, ast.List))
    loop_end = max(n.lineno for n in ast.walk(loop) if hasattr(n, "lineno"))
    binds = {n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Name) and n.id == "ball_handler_id"
             and isinstance(n.ctx, ast.Store)}
    reads = {n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Name) and n.id == "ball_handler_id"
             and isinstance(n.ctx, ast.Load)}
    return loop.lineno, loop_end, sorted(binds), sorted(reads)


def test_the_binding_stays_outside_the_skippable_loop():
    """Poison-resistant: move the binding back inside the loop and this fails."""
    loop_start, loop_end, binds, reads = _bh_lines()
    assert binds, "ball_handler_id must be bound somewhere"
    assert max(binds) < loop_start, (
        "ball_handler_id is bound inside a loop whose body can be skipped entirely; "
        f"binds at {binds}, loop starts at line {loop_start} of the function"
    )
    assert not any(loop_start <= b <= loop_end for b in binds)
    assert min(reads) > max(binds), "every read must follow the binding"
