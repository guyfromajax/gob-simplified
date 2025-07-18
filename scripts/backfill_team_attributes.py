from BackEnd.db import teams_collection

DEFAULT_ATTRS = {
    "shot_threshold": 200,
    "ft_shot_threshold": 200,
    "turnover_threshold": -200,
    "foul_threshold": 60,
    "rebound_modifier": 1.0,
    "momentum_score": 10,
    "momentum_delta": 2,
    "offensive_efficiency": 5,
    "offensive_adjust": 5,
    "o_tendency_reads": 5,
    "d_tendency_reads": 5,
    "team_chemistry": 15
}

def backfill_team_attributes():
    for team in teams_collection.find():
        updates = {}
        for attr, default in DEFAULT_ATTRS.items():
            if attr not in team:
                updates[attr] = default
        if updates:
            teams_collection.update_one({"_id": team["_id"]}, {"$set": updates})
            print(f"✅ Added missing attributes to team {team['name']}")
