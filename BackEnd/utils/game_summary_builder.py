from datetime import datetime

def build_game_summary(game_manager):
    """
    Create a clean dictionary for MongoDB insertion from a GameManager instance.
    """
    gm = game_manager
    home = gm.home_team.name
    away = gm.away_team.name
    score = gm.score

    home_obj = {
        "name": home,
        "team_id": gm.home_team.team_id,
        "score": score.get(home, 0),
    }

    away_obj = {
        "name": away,
        "team_id": gm.away_team.team_id,
        "score": score.get(away, 0),
    }

    return {
        "home_team": home,
        "away_team": away,
        "score": score,
        "winner": home if score[home] > score[away] else away,
        "quarters": gm.quarter,
        "points_by_quarter": {
            home: list(getattr(gm.home_team, "points_by_quarter", []) or []),
            away: list(getattr(gm.away_team, "points_by_quarter", []) or []),
        },
        "box_score": gm.get_box_score(),
        "timestamp": datetime.utcnow().isoformat(),
        "homeTeam": home_obj,
        "awayTeam": away_obj,
    }
