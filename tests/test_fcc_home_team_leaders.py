from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "FrontEnd" / "static" / "franchise-command-center.html"
JS = ROOT / "FrontEnd" / "static" / "franchise-command-center.js"


def test_coachs_office_team_leaders_categories_and_rates_are_wired():
    html = HTML.read_text()
    script = JS.read_text()

    assert "<h3>Team Leaders</h3>" in html
    for category in ("PTS", "REB", "AST", "DEF"):
        assert f'data-home-leader-category="{category}"' in html

    assert "let homeTeamLeaderCategory = 'PTS';" in script
    assert "getPlayerTotalRebounds(player) / getGamesPlayed(player)" in script
    assert "getPlayerSeasonStats(player).AST || 0) / getGamesPlayed(player)" in script
    assert "Number(getPlayerSeasonStats(player).DEF_A || 0) / gp) >= 4" in script
    assert "Number(stats.DEF_S || 0) / attempts" in script
    assert "display: (value) => value.toFixed(1)" in script
    assert "display: (value) => `${Math.round(value)}%`" in script

