from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYER_DETAIL_JS = ROOT / "FrontEnd" / "static" / "player-detail.js"
PLAYER_DETAIL_CSS = ROOT / "FrontEnd" / "static" / "player-detail.css"


def test_unsigned_recruit_profile_uses_neutral_background_not_team_art():
    source = PLAYER_DETAIL_JS.read_text()
    styles = PLAYER_DETAIL_CSS.read_text()

    assert "!!player?.is_recruit && !player?.is_signed" in source
    assert "pd-portrait-wrap--unsigned-recruit" in source
    assert ".pd-portrait-wrap--unsigned-recruit" in styles
    assert "background: #747474" in styles


def test_signed_recruit_profile_resolves_assigned_team_background():
    source = PLAYER_DETAIL_JS.read_text()

    assert "player?.signed_team_name" in source
    assert "getTeamBackground(teamName, staticPrefix)" in source
