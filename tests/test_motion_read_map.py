"""Phase 1 tests — Dynamic HCO Motion read map (brief Steps 0 & 1)."""
from BackEnd.engine.motion_read_map import (
    build_motion_read_map,
    _man_read_map,
    _zone_read_map,
    READ_THRESHOLD,
    ZONE_AREA_COVERAGE,
)

POSITIONS = ["PG", "SG", "SF", "PF", "C"]
_ATTR_KEYS = ["SC", "ST", "AG", "SH", "ID", "OD", "IQ", "CH"]


class _FakePlayer:
    def __init__(self, pid, **overrides):
        self.player_id = pid
        self.attributes = {k: 50 for k in _ATTR_KEYS}
        self.attributes.update(overrides)


def _uniform_lineup(prefix):
    """Five position-keyed players, all attributes 50."""
    return {pos: _FakePlayer(f"{prefix}_{pos}") for pos in POSITIONS}


class _FakeTeam:
    def __init__(self, is_user_team=False):
        self.is_user_team = is_user_team


class _FakeGame:
    def __init__(self, defense_playcall):
        self.game_state = {"defense_playcall": defense_playcall}
        self.defense_team = _FakeTeam(is_user_team=False)


# ----- man -----

def test_man_attack_edge_flags_only_attack():
    off = _uniform_lineup("off")
    # PG gets a big AG edge; SC/ST/SH balanced vs a uniform defender → only attack clears 15.
    off["PG"] = _FakePlayer("off_PG", AG=90)
    deff = _uniform_lineup("def")
    flags = _man_read_map(off, deff, game_state={}, defending_is_user=False)
    assert flags["off_PG"] == {"inside": False, "attack": True, "outside": False}
    for pos in ["SG", "SF", "PF", "C"]:
        assert flags[f"off_{pos}"] == {"inside": False, "attack": False, "outside": False}


def test_man_even_matchup_all_false():
    off, deff = _uniform_lineup("off"), _uniform_lineup("def")
    flags = _man_read_map(off, deff, game_state={}, defending_is_user=False)
    assert all(f == {"inside": False, "attack": False, "outside": False} for f in flags.values())


def test_man_outside_edge_flags_only_outside():
    off = _uniform_lineup("off")
    off["SG"] = _FakePlayer("off_SG", SH=90)  # SH - OD = 40 > 15
    deff = _uniform_lineup("def")
    flags = _man_read_map(off, deff, game_state={}, defending_is_user=False)
    assert flags["off_SG"] == {"inside": False, "attack": False, "outside": True}


def test_man_missing_defender_yields_all_false():
    off = _uniform_lineup("off")
    off["PG"] = _FakePlayer("off_PG", SC=99, AG=99, SH=99)
    deff = _uniform_lineup("def")
    deff["PG"] = None  # no matched defender
    flags = _man_read_map(off, deff, game_state={}, defending_is_user=False)
    assert flags["off_PG"] == {"inside": False, "attack": False, "outside": False}


# ----- zone -----

def test_zone_attack_edge_flags_only_attack():
    off = _uniform_lineup("off")
    off["PG"] = _FakePlayer("off_PG", AG=90)  # attack D ~ 50 (uniform) → (50+90)/2 - 50 = 20 > 15
    deff = _uniform_lineup("def")
    flags = _zone_read_map(off, deff, variant="23")
    assert flags["off_PG"] == {"inside": False, "attack": True, "outside": False}
    for pos in ["SG", "SF", "PF", "C"]:
        assert flags[f"off_{pos}"] == {"inside": False, "attack": False, "outside": False}


def test_zone_uniform_all_false_every_variant():
    for variant in ZONE_AREA_COVERAGE:
        off, deff = _uniform_lineup("off"), _uniform_lineup("def")
        flags = _zone_read_map(off, deff, variant=variant)
        assert all(f == {"inside": False, "attack": False, "outside": False} for f in flags.values()), variant


def test_zone_23_center_excluded_from_outside_dscore():
    # In 2-3, C touches inside only. Give C a huge OD; it must NOT raise the Outside D-score
    # (C is excluded from outside), so a modest-SH offender still reads outside.
    off = _uniform_lineup("off")
    off["SG"] = _FakePlayer("off_SG", SH=70)  # 70 - outside_d
    deff = _uniform_lineup("def")
    deff["C"] = _FakePlayer("def_C", OD=100)  # would tank outside reads IF counted
    flags = _zone_read_map(off, deff, variant="23")
    # outside_d averages OD over PG/SG/SF/PF (all 50), C excluded → outside_d = 50 → 70-50 = 20 > 15
    assert flags["off_SG"]["outside"] is True


# ----- routing -----

def test_build_routes_man_when_not_zone(monkeypatch):
    import BackEnd.engine.motion_read_map as mod
    calls = {}
    monkeypatch.setattr(mod, "_man_read_map", lambda *a, **k: calls.setdefault("man", True) or {})
    monkeypatch.setattr(mod, "_zone_read_map", lambda *a, **k: calls.setdefault("zone", True) or {})
    build_motion_read_map(_FakeGame(defense_playcall="Man"), _uniform_lineup("off"), _uniform_lineup("def"))
    assert calls == {"man": True}


def test_build_routes_zone_for_zone_playcall(monkeypatch):
    import BackEnd.engine.motion_read_map as mod
    calls = {}
    monkeypatch.setattr(mod, "_man_read_map", lambda *a, **k: calls.setdefault("man", True) or {})
    monkeypatch.setattr(mod, "_zone_read_map", lambda *a, **k: calls.setdefault("zone", True) or {})
    # "2-3 Zone" display name is recognized by is_zone_defense's no-DB legacy fallback.
    build_motion_read_map(_FakeGame(defense_playcall="2-3 Zone"), _uniform_lineup("off"), _uniform_lineup("def"))
    assert calls == {"zone": True}


def test_build_zone_full_map_smoke():
    # End-to-end zone path (no monkeypatch): full 5-player map, well-formed flags.
    off, deff = _uniform_lineup("off"), _uniform_lineup("def")
    flags = build_motion_read_map(_FakeGame(defense_playcall="2-3 Zone"), off, deff)
    assert set(flags.keys()) == {f"off_{p}" for p in POSITIONS}
    assert all(set(v) == {"inside", "attack", "outside"} for v in flags.values())
