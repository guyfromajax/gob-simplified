from datetime import datetime

def build_game_summary(game_manager):
    """
    Create a clean dictionary for MongoDB insertion from a GameManager instance.
    """
    gm = game_manager
    home = gm.home_team.name
    away = gm.away_team.name
    score = gm.score

    return {
        "home_team": home,
        "away_team": away,
        "score": score,
        "winner": home if score[home] > score[away] else away,
        "quarters": gm.quarter,
        "points_by_quarter": gm.game_state["points_by_quarter"],
        "box_score": gm.get_box_score(),
        "timestamp": datetime.utcnow().isoformat()
    }

