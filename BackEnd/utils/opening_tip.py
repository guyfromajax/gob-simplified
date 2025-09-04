import random

def execute_opening_tip(game):
    home_tipper = game.home_team.lineup["C"]
    away_tipper = game.away_team.lineup["C"]

    home_tip_score = player_tip_score(home_tipper)
    away_tip_score = player_tip_score(away_tipper)

    if home_tip_score > away_tip_score:
        offense_team = game.home_team
        defense_team = game.away_team
    else:
        offense_team = game.away_team
        defense_team = game.home_team

    return offense_team, defense_team

def player_tip_score(player):
    tip_score = 0
    height_score_dict = {
        82: 11,
        81: 10,
        80: 9,
        79: 8,
        78: 7,
        77: 6,
        76: 5,
        75: 4,
        74: 3,
        73: 2,
    }

    if player.height in height_score_dict:
        tip_score += height_score_dict[player.height] * random.randint(1, 6)
    else:
        tip_score += random.randint(1, 5)

    return tip_score