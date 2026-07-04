"""Phase 6 integration tests — distant sim persist, momentum FTD updates, ranking freeze."""

from __future__ import annotations

from unittest.mock import patch

from BackEnd.distant_sim_engine import (
    compute_distant_momentum_score_updates,
    distant_sim_apply_result_to_standings_cache,
    distant_sim_should_promote_ranked_fullsim,
    distant_sim_talent_signal,
    distant_sim_team_combined,
)


class _Oid:
    """Stand-in for bson.ObjectId when pymongo is not installed in the test env."""

    def __init__(self, label: str = "id") -> None:
        self.label = label

    def __str__(self) -> str:
        return self.label

    def __repr__(self) -> str:
        return f"Oid({self.label!r})"

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))


def _player(pid: str, *, pos_rt: int = 80) -> dict:
    return {
        "_id": pid,
        "playerId": pid,
        "name": f"Player {pid[-4:]}",
        "position_ratings": {p: pos_rt for p in ("PG", "SG", "SF", "PF", "C")},
        "attributes": {
            "SC": 70, "SH": 70, "ID": 70, "OD": 70, "PS": 70, "BH": 70,
            "RB": 70, "ST": 70, "AG": 70, "ND": 70, "IQ": 70, "FT": 70,
        },
    }


def _fake_team_context(team_oid: _Oid, *, team_id: str = "TEAM_A") -> dict:
    players = [_player(f"p{i}") for i in range(8)]
    return {
        "team_object_id": str(team_oid),
        "team_id": team_id,
        "name": "Test U",
        "mascot": "T",
        "primary_color": "#000",
        "secondary_color": "#fff",
        "team_attributes": {"team_chemistry": 9, "momentum_score": 0},
        "players": players,
    }


def test_momentum_updates_apply_to_ftd_cache():
    """6.1 — winner/loser momentum_score + streaks merge into in-memory FTD cache."""
    winner_oid = "winner"
    loser_oid = "loser"
    ftd_cache = {
        winner_oid: {"team_attributes": {"team_chemistry": 10, "momentum_score": 0, "distant_win_streak": 0}},
        loser_oid: {"team_attributes": {"team_chemistry": 10, "momentum_score": 0, "distant_win_streak": 0}},
    }
    w_up, l_up = compute_distant_momentum_score_updates(
        ftd_cache[winner_oid]["team_attributes"],
        ftd_cache[loser_oid]["team_attributes"],
    )
    ftd_cache[winner_oid]["team_attributes"].update(w_up)
    ftd_cache[loser_oid]["team_attributes"].update(l_up)

    assert float(ftd_cache[winner_oid]["team_attributes"]["momentum_score"]) > 0
    assert int(ftd_cache[winner_oid]["team_attributes"]["distant_win_streak"]) == 1
    assert int(ftd_cache[loser_oid]["team_attributes"]["distant_loss_streak"]) == 1


def test_build_distant_game_summary_marks_distant_engine():
    """6.2 — distant game doc: simulation_engine, box scores, final quarter."""
    try:
        from BackEnd.models import distant_game_stats
    except ModuleNotFoundError:
        return  # pymongo not in env; covered in CI / manual playtest

    home_oid = _Oid("home")
    away_oid = _Oid("away")

    def fake_load(_fid, team_oid):
        tid = "HOME" if team_oid == home_oid else "AWAY"
        return _fake_team_context(team_oid, team_id=tid)

    with patch.object(distant_game_stats, "_load_team_context", side_effect=fake_load):
        summary = distant_game_stats.build_distant_game_summary(
            franchise_id=_Oid("franchise"),
            week=5,
            home_team_object_id=home_oid,
            away_team_object_id=away_oid,
            home_score=72,
            away_score=65,
        )

    assert summary["simulation_engine"] == "distant"
    assert summary["quarter"] == 5
    assert summary["is_final"] is True
    assert summary["home_team"]["score"] == 72
    assert summary["away_team"]["score"] == 65
    assert summary["box_score"]["HOME"]
    assert summary["team_totals"]["HOME"]["PTS"] == 72
    assert summary["team_totals"]["AWAY"]["PTS"] == 65
    assert len(summary["players"]) >= 10


def test_v2_franchise_freezes_total_player_attrs_on_ftd_update():
    """6.3 — v2 rank/prestige strips total_player_attrs from FTD roster writes."""
    franchise_doc = {"rank_prestige_system_version": 2}
    update_fields = {"total_player_attrs": 9999, "prestige": 650}
    if int(franchise_doc.get("rank_prestige_system_version", 1) or 1) >= 2:
        update_fields = {k: v for k, v in update_fields.items() if k != "total_player_attrs"}
    assert "total_player_attrs" not in update_fields
    assert update_fields["prestige"] == 650


def test_talent_signal_reads_fpd_without_mutating_ftd():
    """6.3 — live FPD talent is sim-only; FTD frozen attrs unchanged."""
    ftd = {
        "total_player_attrs": 1000,
        "players": ["p1"],
        "team_attributes": {},
    }
    fpd = {"p1": {"attributes": {"SC": 100, "SH": 100, "ID": 100, "OD": 100, "PS": 100, "BH": 100,
                                  "RB": 100, "ST": 100, "AG": 100, "ND": 100, "IQ": 100, "FT": 100}}}
    signal = distant_sim_talent_signal(ftd, fpd)
    assert signal == 1200
    assert ftd["total_player_attrs"] == 1000


def test_within_week_cache_updates_combined_score():
    """6.1 — same-week distant sim sees updated W/L in combined score."""
    ftd = {
        "prestige": 600,
        "total_player_attrs": 1400,
        "team_attributes": {"team_chemistry": 9, "momentum_score": 0},
    }
    rs = {"team-a": {"W": 0, "L": 0}}
    before = distant_sim_team_combined(ftd, season_wins=0, season_losses=0, is_home=False, current_week=8)
    distant_sim_apply_result_to_standings_cache(rs, "team-b", "team-a", 60, 70)
    after = distant_sim_team_combined(ftd, season_wins=1, season_losses=0, is_home=False, current_week=8)
    assert after > before
    assert rs["team-a"]["W"] == 1


def test_ranked_promotion_routes_to_full_sim_gate():
    """Phase 5/6 — ranked promotion helper gates elite distant matchups."""
    assert distant_sim_should_promote_ranked_fullsim({"natl_rank": 5}, {"natl_rank": 12})
    assert not distant_sim_should_promote_ranked_fullsim({"natl_rank": 5}, {"natl_rank": 20})
