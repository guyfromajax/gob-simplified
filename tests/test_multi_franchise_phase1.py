"""Multi-franchise Phase 1: cap constant (no DB import)."""

from BackEnd.constants.multi_franchise import MAX_FRANCHISES_PER_USER


def test_max_franchises_per_user_is_two():
    assert MAX_FRANCHISES_PER_USER == 2
