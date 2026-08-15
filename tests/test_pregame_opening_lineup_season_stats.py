from types import SimpleNamespace

from BackEnd.api.api import _resolve_matchup_display_lineup


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(player_id):
    return SimpleNamespace(player_id=player_id)


class _Team:
    def __init__(self, team_id, prefix):
        self.team_id = team_id
        self.opening_players = [_player(f"{prefix}-open-{pos}") for pos in POSITIONS]
        self.current_pg = _player(f"{prefix}-sub-PG")
        self.lineup = {
            "PG": self.current_pg,
            **{
                pos: self.opening_players[idx]
                for idx, pos in enumerate(POSITIONS)
                if pos != "PG"
            },
        }

    def get_all_players(self):
        return [*self.opening_players, self.current_pg]


def test_prefer_opening_resolves_the_immutable_tipoff_five():
    team = _Team("HOME", "home")
    opening = {
        team.team_id: [player.player_id for player in team.opening_players]
    }

    displayed = _resolve_matchup_display_lineup(team, opening)

    assert [displayed[pos].player_id for pos in POSITIONS] == [
        player.player_id for player in team.opening_players
    ]
    assert team.current_pg not in displayed.values()


def test_default_matchup_payload_still_resolves_the_current_five():
    team = _Team("HOME", "home")

    displayed = _resolve_matchup_display_lineup(team)

    assert displayed == team.lineup


def test_incomplete_opening_snapshot_preserves_existing_slot_fallback():
    team = _Team("HOME", "home")
    opening = {team.team_id: [team.opening_players[0].player_id]}

    displayed = _resolve_matchup_display_lineup(team, opening)

    assert displayed["PG"] is team.opening_players[0]
    for pos in POSITIONS[1:]:
        assert displayed[pos] is team.lineup[pos]
