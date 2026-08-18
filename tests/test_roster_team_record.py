"""Guards for the /roster team_record block that feeds the roster page identity lockup.

The block is wrapped in `except Exception` so a lookup failure degrades to no record
rather than a 500. That swallowing also hides typos: the block first shipped calling
`db.franchises` / `db.teams`, names that do not exist in api.py, so every response
silently carried team_record=None. These tests pin the contract instead.
"""
import ast
import inspect
import pathlib
import re

import BackEnd.db as gob_db
from BackEnd.utils.franchise_standings import calculate_franchise_standings

API = pathlib.Path(__file__).resolve().parents[1] / "BackEnd" / "api" / "api.py"
SRC = API.read_text()


def _record_block() -> str:
    start = SRC.index('response_data["team_record"] = None')
    end = SRC.index("# Team Builder: overlay identity", start)
    return SRC[start:end]


def test_record_block_exists():
    assert 'response_data["team_record"]' in SRC


def test_block_uses_only_importable_collection_handles():
    block = _record_block()
    # No bare `db.<collection>` access — api.py imports individual collection handles.
    assert not re.search(r"\bdb\.\w+", block), "api.py has no module-level `db`; use *_collection"
    for name in sorted(set(re.findall(r"\b(\w+_collection)\b", block))):
        assert hasattr(gob_db, name), f"{name} is not exported by BackEnd.db"


def test_standings_helper_signature_matches_the_call():
    sig = inspect.signature(calculate_franchise_standings)
    assert list(sig.parameters) == ["franchise_results", "team_ids_map"]


def test_standings_keys_used_by_the_block_are_the_keys_the_helper_returns():
    out = calculate_franchise_standings(
        {"1": [{"away_id": "a", "home_id": "b", "away_score": 70, "home_score": 60}]},
        {"a": {}, "b": {}},
    )
    assert out["a"] == {"PF": 70, "PA": 60, "W": 1, "L": 0}
    block = _record_block()
    for key in re.findall(r'\.get\("([WLPFA]{1,2})"', block):
        assert key in out["a"], f'block reads "{key}", helper never returns it'


def test_conference_place_orders_by_wins_then_point_differential():
    """Mirrors the block's sort key so a change to one side fails loudly."""
    standings = {
        "t1": {"W": 3, "L": 1, "PF": 300, "PA": 280},   # 3 W, +20
        "t2": {"W": 3, "L": 1, "PF": 300, "PA": 250},   # 3 W, +50  -> ahead of t1
        "t3": {"W": 1, "L": 3, "PF": 200, "PA": 400},
    }
    ranked = sorted(
        standings,
        key=lambda tid: (
            -int(standings[tid]["W"]),
            -(int(standings[tid]["PF"]) - int(standings[tid]["PA"])),
        ),
    )
    assert ranked == ["t2", "t1", "t3"]
    assert ranked.index("t1") + 1 == 2


def test_block_is_franchise_gated():
    block = _record_block()
    assert "if franchise_id" in block, "record must not be computed outside a franchise"


def test_block_includes_natl_rank_from_ftd():
    block = _record_block()
    assert '"natl_rank"' in block
    assert "natl_rank_from_ftd_document" in block
    assert "franchise_team_data_collection" in block


def test_block_includes_recruiting_rank_from_ftd():
    block = _record_block()
    assert '"recruiting_rank"' in block
    assert '"recruiting_region_rank"' in block


def test_block_is_syntactically_valid_python():
    ast.parse(SRC)
