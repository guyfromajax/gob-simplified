from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FCC_JS = ROOT / "FrontEnd" / "static" / "franchise-command-center.js"
TEAM_ATTRS_VIEW = ROOT / "FrontEnd" / "static" / "js" / "shared" / "views" / "teamAttributesView.js"


def test_team_measures_and_scouting_share_plus_minus_twenty_radar_scale():
    source = FCC_JS.read_text(encoding="utf-8")
    view = TEAM_ATTRS_VIEW.read_text(encoding="utf-8")

    assert "const TEAM_MEASURES_RADAR_MIN = -20;" in source
    assert "const TEAM_MEASURES_RADAR_MAX = 20;" in source
    assert "const TEAM_MEASURES_RADAR_DOMINANT_MIN = 14;" in source
    assert "const ringValues = [20, 13.3, 6.7, 0, -6.7, -13.3, -20];" in source
    assert "TEAM_MEASURES_RADAR_MAX - TEAM_MEASURES_RADAR_MIN" in source

    # Leftover #team-stats-tab host is gone; Team Attributes is the sole caller.
    assert "radarHost.innerHTML = buildTeamMeasuresRadarMarkup" not in source
    assert "buildTeamMeasuresLinearCardMarkup" not in source
    assert "window.buildTeamMeasuresRadarMarkup(attrs)" in view

    radar_source = source[
        source.index("function buildTeamMeasuresRadarMarkup") :
        source.index("function upcomingOpponentCacheKey")
    ]
    assert "Math.max(-10" not in radar_source
    assert "Math.min(10" not in radar_source
