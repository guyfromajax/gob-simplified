from datetime import datetime

def build_game_summary(game_manager):
    """
    Create a clean dictionary for MongoDB insertion from a GameManager instance.
    """
    gm = game_manager
    return {
        "home_team": gm.home_team,
        "away_team": gm.away_team,
        "score": gm.score,
        "winner": gm.home_team if gm.score[gm.home_team] > gm.score[gm.away_team] else gm.away_team,
        "quarters": gm.quarter,
        "points_by_quarter": gm.points_by_quarter,
        "box_score": gm.get_box_score(),
        "timestamp": datetime.utcnow().isoformat()
    }
