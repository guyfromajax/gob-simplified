#!/usr/bin/env python3
"""
Script to rename team attributes in MongoDB collections.

RENAMES:
- foul_modifier → fight
- turnover_modifier → discipline

Updates:
- teams collection (8 team documents)
- tournaments collection (all tournament docs → nested teams objects)
- franchises collection (all franchise docs → nested franchise_teams objects)
- games collection (all game docs → nested team objects)
"""

import sys
import os

# Add parent directory to path to import BackEnd modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import teams_collection, tournaments_collection, franchises_collection, games_collection
from bson import ObjectId

def update_teams_collection():
    """Rename attributes in teams collection."""
    print("📋 Processing teams collection...")
    
    teams = teams_collection.find({})
    updated_count = 0
    
    for team in teams:
        update_ops = {}
        
        # Rename foul_modifier to fight if it exists
        if "foul_modifier" in team:
            update_ops["fight"] = team["foul_modifier"]
            update_ops["$unset"] = {"foul_modifier": ""}
        
        # Rename turnover_modifier to discipline if it exists
        if "turnover_modifier" in team:
            if "$unset" not in update_ops:
                update_ops["$unset"] = {}
            update_ops["discipline"] = team["turnover_modifier"]
            update_ops["$unset"]["turnover_modifier"] = ""
        
        if update_ops:
            # Separate $set and $unset operations
            set_ops = {k: v for k, v in update_ops.items() if k != "$unset"}
            unset_ops = update_ops.get("$unset", {})
            
            final_update = {}
            if set_ops:
                final_update["$set"] = set_ops
            if unset_ops:
                final_update["$unset"] = unset_ops
            
            teams_collection.update_one({"_id": team["_id"]}, final_update)
            updated_count += 1
            print(f"   ✅ Updated team: {team.get('name', 'Unknown')}")
    
    print(f"   ✅ Updated {updated_count} team documents")
    return updated_count

def update_tournaments_collection():
    """Rename attributes in tournaments collection (nested in teams objects)."""
    print("📋 Processing tournaments collection...")
    modified_count = 0
    
    tournaments = tournaments_collection.find({})
    
    for tournament in tournaments:
        updated = False
        teams = tournament.get("teams", {})
        
        for team_id, team_data in teams.items():
            if isinstance(team_data, dict) and "team_attributes" in team_data:
                attrs = team_data["team_attributes"]
                update_path = f"teams.{team_id}.team_attributes"
                
                update_ops = {}
                
                # Rename foul_modifier to aggression
                if "foul_modifier" in attrs:
                    update_ops[f"{update_path}.aggression"] = attrs["foul_modifier"]
                    update_ops[f"{update_path}.$unset.foul_modifier"] = ""
                
                # Rename turnover_modifier to discipline
                if "turnover_modifier" in attrs:
                    update_ops[f"{update_path}.discipline"] = attrs["turnover_modifier"]
                    if f"{update_path}.$unset" not in update_ops:
                        update_ops[f"{update_path}.$unset"] = {}
                    update_ops[f"{update_path}.$unset.turnover_modifier"] = ""
                
                if update_ops:
                    # Separate $set and $unset operations
                    set_ops = {k: v for k, v in update_ops.items() if not k.endswith(".$unset")}
                    unset_ops = {}
                    for k, v in update_ops.items():
                        if k.endswith(".$unset"):
                            # Extract the unset key
                            unset_key = k.replace(f"{update_path}.$unset.", "")
                            unset_ops[f"{update_path}.{unset_key}"] = ""
                    
                    final_update = {}
                    if set_ops:
                        final_update["$set"] = set_ops
                    if unset_ops:
                        final_update["$unset"] = unset_ops
                    
                    tournaments_collection.update_one(
                        {"_id": tournament["_id"]},
                        final_update
                    )
                    updated = True
        
        if updated:
            modified_count += 1
    
    print(f"   ✅ Updated {modified_count} tournament documents")
    return modified_count

def update_franchises_collection():
    """Rename attributes in franchises collection (nested in franchise_teams objects)."""
    print("📋 Processing franchises collection...")
    modified_count = 0
    
    franchises = franchises_collection.find({})
    
    for franchise in franchises:
        updated = False
        franchise_teams = franchise.get("franchise_teams", {})
        
        for team_id, team_data in franchise_teams.items():
            if isinstance(team_data, dict) and "team_attributes" in team_data:
                attrs = team_data["team_attributes"]
                update_path = f"franchise_teams.{team_id}.team_attributes"
                
                update_ops = {}
                
                # Rename foul_modifier to aggression
                if "foul_modifier" in attrs:
                    update_ops[f"{update_path}.aggression"] = attrs["foul_modifier"]
                    update_ops[f"{update_path}.$unset.foul_modifier"] = ""
                
                # Rename turnover_modifier to discipline
                if "turnover_modifier" in attrs:
                    update_ops[f"{update_path}.discipline"] = attrs["turnover_modifier"]
                    if f"{update_path}.$unset" not in update_ops:
                        update_ops[f"{update_path}.$unset"] = {}
                    update_ops[f"{update_path}.$unset.turnover_modifier"] = ""
                
                if update_ops:
                    # Separate $set and $unset operations
                    set_ops = {k: v for k, v in update_ops.items() if not k.endswith(".$unset")}
                    unset_ops = {}
                    for k, v in update_ops.items():
                        if k.endswith(".$unset"):
                            # Extract the unset key
                            unset_key = k.replace(f"{update_path}.$unset.", "")
                            unset_ops[f"{update_path}.{unset_key}"] = ""
                    
                    final_update = {}
                    if set_ops:
                        final_update["$set"] = set_ops
                    if unset_ops:
                        final_update["$unset"] = unset_ops
                    
                    franchises_collection.update_one(
                        {"_id": franchise["_id"]},
                        final_update
                    )
                    updated = True
        
        if updated:
            modified_count += 1
    
    print(f"   ✅ Updated {modified_count} franchise documents")
    return modified_count

def update_games_collection():
    """Rename attributes in games collection (nested in team objects)."""
    print("📋 Processing games collection...")
    modified_count = 0
    
    games = games_collection.find({})
    
    for game in games:
        updated = False
        
        # Check home_team
        if "home_team" in game and isinstance(game["home_team"], dict):
            home_team = game["home_team"]
            if "team_attributes" in home_team:
                attrs = home_team["team_attributes"]
                update_ops = {}
                
                if "foul_modifier" in attrs:
                    update_ops["home_team.team_attributes.fight"] = attrs["foul_modifier"]
                    update_ops["home_team.team_attributes.$unset.foul_modifier"] = ""
                
                if "turnover_modifier" in attrs:
                    update_ops["home_team.team_attributes.discipline"] = attrs["turnover_modifier"]
                    if "home_team.team_attributes.$unset" not in update_ops:
                        update_ops["home_team.team_attributes.$unset"] = {}
                    update_ops["home_team.team_attributes.$unset.turnover_modifier"] = ""
                
                if update_ops:
                    set_ops = {k: v for k, v in update_ops.items() if not k.endswith(".$unset")}
                    unset_ops = {}
                    for k, v in update_ops.items():
                        if k.endswith(".$unset"):
                            unset_key = k.replace("home_team.team_attributes.$unset.", "")
                            unset_ops[f"home_team.team_attributes.{unset_key}"] = ""
                    
                    final_update = {}
                    if set_ops:
                        final_update["$set"] = set_ops
                    if unset_ops:
                        final_update["$unset"] = unset_ops
                    
                    games_collection.update_one({"_id": game["_id"]}, final_update)
                    updated = True
        
        # Check away_team
        if "away_team" in game and isinstance(game["away_team"], dict):
            away_team = game["away_team"]
            if "team_attributes" in away_team:
                attrs = away_team["team_attributes"]
                update_ops = {}
                
                if "foul_modifier" in attrs:
                    update_ops["away_team.team_attributes.fight"] = attrs["foul_modifier"]
                    update_ops["away_team.team_attributes.$unset.foul_modifier"] = ""
                
                if "turnover_modifier" in attrs:
                    update_ops["away_team.team_attributes.discipline"] = attrs["turnover_modifier"]
                    if "away_team.team_attributes.$unset" not in update_ops:
                        update_ops["away_team.team_attributes.$unset"] = {}
                    update_ops["away_team.team_attributes.$unset.turnover_modifier"] = ""
                
                if update_ops:
                    set_ops = {k: v for k, v in update_ops.items() if not k.endswith(".$unset")}
                    unset_ops = {}
                    for k, v in update_ops.items():
                        if k.endswith(".$unset"):
                            unset_key = k.replace("away_team.team_attributes.$unset.", "")
                            unset_ops[f"away_team.team_attributes.{unset_key}"] = ""
                    
                    final_update = {}
                    if set_ops:
                        final_update["$set"] = set_ops
                    if unset_ops:
                        final_update["$unset"] = unset_ops
                    
                    games_collection.update_one({"_id": game["_id"]}, final_update)
                    updated = True
        
        if updated:
            modified_count += 1
    
    print(f"   ✅ Updated {modified_count} game documents")
    return modified_count

def main():
    print("=" * 60)
    print("Migrating foul_modifier → fight")
    print("Migrating turnover_modifier → discipline")
    print("=" * 60)
    print()
    
    teams_count = update_teams_collection()
    print()
    
    tournaments_count = update_tournaments_collection()
    print()
    
    franchises_count = update_franchises_collection()
    print()
    
    games_count = update_games_collection()
    print()
    
    print("=" * 60)
    print("✅ Migration complete!")
    print(f"   Teams: {teams_count}")
    print(f"   Tournaments: {tournaments_count}")
    print(f"   Franchises: {franchises_count}")
    print(f"   Games: {games_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()


