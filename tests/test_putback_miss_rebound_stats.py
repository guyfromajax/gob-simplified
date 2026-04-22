"""
Regression tests for OREB putback-miss rebound stats fix.

Bug (fixed): When a shot missed -> OREB -> putback attempt -> miss -> someone grabs
the rebound, that rebounder's OREB or DREB was never recorded. The fix records the
stat on the canonical roster player in shared.resolve_offensive_rebound so deltas
and persistence see it.
"""

import pytest
from unittest.mock import patch

from tests.test_utils import build_mock_game

POSITION_LIST = ["PG", "SG", "SF", "PF", "C"]


def _sync_lineup_to_roster(game):
    """Set each team's lineup to first 5 roster players so lineup and roster share refs."""
    for team in (game.home_team, game.away_team):
        roster = list(team.get_all_players())
        if len(roster) >= 5:
            team.lineup = {pos: roster[i] for i, pos in enumerate(POSITION_LIST)}


@pytest.mark.integration
class TestPutbackMissReboundStats:
    """Test that OREB/DREB are recorded and appear in deltas when rebound follows putback miss."""

    def test_putback_miss_oreb_recorded_in_deltas(self):
        """After putback miss -> OREB, the offensive rebounder's OREB appears in deltas."""
        game = build_mock_game()
        _sync_lineup_to_roster(game)
        # Pick the roster player who will get the OREB (use offense team's PF)
        off_roster = list(game.offense_team.get_all_players())
        def_roster = list(game.defense_team.get_all_players())
        assert len(off_roster) >= 5 and len(def_roster) >= 5
        rebounder_player = game.offense_team.lineup["PF"]
        rebounder_id = rebounder_player.player_id
        assert rebounder_id is not None

        game.game_state["pending_oreb"] = {
            "rebounder": rebounder_player,
            "rebounder_id": rebounder_id,
        }

        # Force putback miss (threshold 1000 so shot_score >= 1000 is False)
        game.offense_team.team_attributes["shot_threshold"] = 1000

        def fake_determine_rebounder(game_param, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None):
            return rebounder_player, game.offense_team, "OREB"

        # Skip OTB randints; uncontested putback miss via randint(1,100) → 100; bounce uses 3 randints.
        randint_returns = [1, 100, 2, 2, 0] + [5] * 40
        with patch("BackEnd.utils.shared.resolve_over_the_back_foul", return_value=None):
            with patch(
                "BackEnd.utils.shared._resolve_oreb_putback_defender",
                return_value=(None, False),
            ):
                with patch("BackEnd.utils.shared.determine_rebounder", side_effect=fake_determine_rebounder):
                    with patch("BackEnd.utils.shared.random.random", return_value=0.05):
                        with patch("BackEnd.utils.shared.random.randint", side_effect=randint_returns):
                            result = game.turn_manager.resolve_offensive_rebound_turn()

        assert result is not None, "OREB turn should return a result"
        assert result.get("result_type") == "PUTBACK_MISS", f"Expected PUTBACK_MISS, got {result.get('result_type')}"
        assert "rebound" in str(result.get("rebound_type", "")).upper() or result.get("rebound_type") in ("OREB", "DREB")
        deltas = result.get("deltas", {})
        assert rebounder_id in deltas, f"Rebounder {rebounder_id} should be in deltas: {list(deltas.keys())}"
        stats_diff = deltas[rebounder_id].get("stats", {})
        assert "OREB" in stats_diff, f"OREB should be in rebounder deltas: {stats_diff}"
        assert stats_diff["OREB"] == 1, f"OREB delta should be 1, got {stats_diff['OREB']}"

    def test_putback_miss_dreb_recorded_in_deltas(self):
        """After putback miss -> DREB, the defensive rebounder's DREB appears in deltas."""
        game = build_mock_game()
        _sync_lineup_to_roster(game)
        rebounder_player = game.defense_team.lineup["C"]
        rebounder_id = rebounder_player.player_id
        assert rebounder_id is not None

        game.game_state["pending_oreb"] = {
            "rebounder": game.offense_team.lineup["C"],
            "rebounder_id": game.offense_team.lineup["C"].player_id,
        }
        game.offense_team.team_attributes["shot_threshold"] = 1000

        def fake_determine_rebounder(game_param, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None):
            return rebounder_player, game.defense_team, "DREB"

        randint_returns = [1, 100, 2, 2, 0] + [5] * 40
        with patch("BackEnd.utils.shared.resolve_over_the_back_foul", return_value=None):
            with patch(
                "BackEnd.utils.shared._resolve_oreb_putback_defender",
                return_value=(None, False),
            ):
                with patch("BackEnd.utils.shared.determine_rebounder", side_effect=fake_determine_rebounder):
                    with patch("BackEnd.utils.shared.random.random", return_value=0.05):
                        with patch("BackEnd.utils.shared.random.randint", side_effect=randint_returns):
                            result = game.turn_manager.resolve_offensive_rebound_turn()

        assert result is not None
        assert result.get("result_type") == "PUTBACK_MISS"
        assert result.get("rebound_type") == "DREB"
        deltas = result.get("deltas", {})
        assert rebounder_id in deltas, f"Defensive rebounder {rebounder_id} should be in deltas"
        stats_diff = deltas[rebounder_id].get("stats", {})
        assert "DREB" in stats_diff, f"DREB should be in rebounder deltas: {stats_diff}"
        assert stats_diff["DREB"] == 1, f"DREB delta should be 1, got {stats_diff['DREB']}"

    def test_putback_miss_rebound_canonical_player_has_stat(self):
        """Stat is recorded on the roster player (canonical); direct check on player.stats."""
        game = build_mock_game()
        _sync_lineup_to_roster(game)
        rebounder_player = game.offense_team.lineup["SF"]
        rebounder_id = rebounder_player.player_id
        game.game_state["pending_oreb"] = {"rebounder": rebounder_player, "rebounder_id": rebounder_id}
        game.offense_team.team_attributes["shot_threshold"] = 1000

        def fake_determine_rebounder(game_param, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None):
            return rebounder_player, game.offense_team, "OREB"

        oreb_before = rebounder_player.stats["game"].get("OREB", 0)
        randint_returns = [1, 100, 2, 2, 0] + [5] * 40
        with patch("BackEnd.utils.shared.resolve_over_the_back_foul", return_value=None):
            with patch(
                "BackEnd.utils.shared._resolve_oreb_putback_defender",
                return_value=(None, False),
            ):
                with patch("BackEnd.utils.shared.determine_rebounder", side_effect=fake_determine_rebounder):
                    with patch("BackEnd.utils.shared.random.random", return_value=0.1):  # 0.1 < 0.90 => putback branch
                        with patch("BackEnd.utils.shared.random.randint", side_effect=randint_returns):
                            result = game.turn_manager.resolve_offensive_rebound_turn()
        oreb_after = rebounder_player.stats["game"].get("OREB", 0)
        assert result is not None, "resolve_offensive_rebound_turn should return a result"
        assert result.get("result_type") == "PUTBACK_MISS", f"Expected PUTBACK_MISS, got {result.get('result_type')}"
        assert oreb_after == oreb_before + 1, f"Canonical player OREB should increase by 1: {oreb_before} -> {oreb_after}"
