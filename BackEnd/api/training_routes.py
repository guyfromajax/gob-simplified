from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from BackEnd.models.training_manager import TrainingManager, save_training_results
from BackEnd.db import players_collection, teams_collection, training_log_collection

router = APIRouter()

class TrainingRequest(BaseModel):
    team_name: str
    session_type: str
    allocations: Dict[str, Any]

@router.post("/api/run_training")
def run_training(request: TrainingRequest):
    try:
        manager = TrainingManager(request.team_name).load_team_and_players()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    session = manager.create_training_session(session_type=request.session_type)
    for category, allocation in request.allocations.items():
        session.assign_points(category, allocation)

    # Snapshot initial anchor values for players
    player_baselines = {
        p["_id"]: {k: v for k, v in p.get("attributes", {}).items() if k.startswith("anchor_")}
        for p in manager.players
    }

    TEAM_FIELDS = [
        "team_chemistry", "offensive_efficiency", "offensive_adjust",
        "defense_threshold", "shot_threshold", "turnover_threshold",
        "foul_threshold", "rebound_modifier", "o_tendency_reads", "d_tendency_reads"
    ]
    team_before = {k: manager.team_doc.get(k, 0) for k in TEAM_FIELDS}

    # Apply training
    updates = session.apply_training(manager.players, manager.team_doc)

    # Compute player deltas
    player_logs: Dict[str, Dict[str, int]] = {}
    for player in manager.players:
        pid = player["_id"]
        name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        deltas = {}
        for anchor_field, new_val in updates.get(pid, {}).items():
            old_val = player_baselines.get(pid, {}).get(anchor_field, 0)
            delta = new_val - old_val
            if delta != 0:
                trait = anchor_field.replace("anchor_", "")
                deltas[trait] = delta
        if deltas:
            player_logs[name] = deltas

    # Compute team deltas
    team_log: Dict[str, int] = {}
    for field, old_val in team_before.items():
        new_val = manager.team_doc.get(field, old_val)
        delta = new_val - old_val
        if delta != 0:
            team_log[field] = delta

    # Persist results
    save_training_results(
        player_updates=updates,
        players_collection=players_collection,
        team_doc=manager.team_doc,
        teams_collection=teams_collection,
        training_session=session,
        training_log_collection=training_log_collection,
    )

    return {"player_logs": player_logs, "team_log": team_log}

