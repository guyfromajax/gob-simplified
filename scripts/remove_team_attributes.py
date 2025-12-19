#!/usr/bin/env python3
"""
Script to update team attributes in all MongoDB collections.

REMOVES the following attributes:
- d_tendency_reads
- o_tendency_reads
- momentum_delta
- offensive_adjust
- ft_shot_threshold

ADDS the following attributes (with default value 0):
- defensive_efficiency
- fb_efficiency
- pt_efficiency
- fb_opp_modifier
- pt_opp_modifier

From:
- teams collection (8 team documents)
- tournaments collection (all tournament docs → nested teams objects)
- franchises collection (all franchise docs → nested franchise_teams objects)
- games collection (all game docs → nested team objects)
"""

import sys
import os
import random

# Add parent directory to path to import BackEnd modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import teams_collection, tournaments_collection, franchises_collection, games_collection
from bson import ObjectId

# Attributes to remove
ATTRIBUTES_TO_REMOVE = [
    "d_tendency_reads",
    "o_tendency_reads",
    "momentum_delta",
    "offensive_adjust",
    "ft_shot_threshold",
    "foul_threshold",
    "turnover_threshold"
]

# Attributes to add (with default value 0)
ATTRIBUTES_TO_ADD = {
    "defensive_efficiency": 0,
    "fb_efficiency": 0,
    "pt_efficiency": 0,
    "fb_opp_modifier": 0,
    "pt_opp_modifier": 0,
    "foul_modifier": 0,
    "turnover_modifier": 0
}

def update_teams_collection():
    """Remove old attributes and add new attributes to teams collection."""
    print("📋 Processing teams collection...")
    
    # Remove old attributes
    unset_ops = {attr: "" for attr in ATTRIBUTES_TO_REMOVE}
    
    # For universal teams collection, we need to update each team individually
    # to set random values in the new ranges (not just 0)
    teams = teams_collection.find({})
    updated_count = 0
    
    for team in teams:
        set_ops = {}
        
        # Add new attributes with random values in new ranges (for universal teams)
        # For foul_modifier and turnover_modifier: random.randint(-10, 10)
        # For others: default to 0
        set_ops["foul_modifier"] = random.randint(-10, 10)
        set_ops["turnover_modifier"] = random.randint(-10, 10)
        set_ops["defensive_efficiency"] = random.randint(-10, 10)
        set_ops["fb_efficiency"] = random.randint(-10, 10)
        set_ops["pt_efficiency"] = random.randint(-10, 10)
        set_ops["fb_opp_modifier"] = random.randint(-10, 10)
        set_ops["pt_opp_modifier"] = random.randint(-10, 10)
        
        # Combine operations
        update_ops = {}
        if unset_ops:
            update_ops["$unset"] = unset_ops
        if set_ops:
            update_ops["$set"] = set_ops
        
        teams_collection.update_one({"_id": team["_id"]}, update_ops)
        updated_count += 1
    
    print(f"   ✅ Updated {updated_count} team documents")
    return updated_count

def update_tournaments_collection():
    """Remove old attributes and add new attributes to tournaments collection (nested in teams objects)."""
    print("📋 Processing tournaments collection...")
    modified_count = 0
    
    # Get all tournament documents
    tournaments = tournaments_collection.find({})
    
    for tournament in tournaments:
        updated = False
        unset_ops = {}
        set_ops = {}
        
        # Check if tournament has teams object
        if "teams" in tournament and isinstance(tournament["teams"], dict):
            for team_id, team_obj in tournament["teams"].items():
                if isinstance(team_obj, dict):
                    # Remove old attributes
                    for attr in ATTRIBUTES_TO_REMOVE:
                        if attr in team_obj:
                            unset_ops[f"teams.{team_id}.{attr}"] = ""
                            updated = True
                    
                    # Add new attributes (only if they don't exist)
                    for attr, default_value in ATTRIBUTES_TO_ADD.items():
                        if attr not in team_obj:
                            set_ops[f"teams.{team_id}.{attr}"] = default_value
                            updated = True
        
        if updated:
            update_ops = {}
            if unset_ops:
                update_ops["$unset"] = unset_ops
            if set_ops:
                update_ops["$set"] = set_ops
            
            tournaments_collection.update_one(
                {"_id": tournament["_id"]},
                update_ops
            )
            modified_count += 1
    
    print(f"   ✅ Updated {modified_count} tournament documents")
    return modified_count

def update_franchises_collection():
    """Remove old attributes and add new attributes to franchises collection (nested in franchise_teams objects)."""
    print("📋 Processing franchises collection...")
    modified_count = 0
    
    # Get all franchise documents
    franchises = franchises_collection.find({})
    
    for franchise in franchises:
        updated = False
        unset_ops = {}
        set_ops = {}
        
        # Check if franchise has franchise_teams object
        if "franchise_teams" in franchise and isinstance(franchise["franchise_teams"], dict):
            for team_id, team_obj in franchise["franchise_teams"].items():
                if isinstance(team_obj, dict):
                    # Remove old attributes
                    for attr in ATTRIBUTES_TO_REMOVE:
                        if attr in team_obj:
                            unset_ops[f"franchise_teams.{team_id}.{attr}"] = ""
                            updated = True
                    
                    # Add new attributes (only if they don't exist)
                    for attr, default_value in ATTRIBUTES_TO_ADD.items():
                        if attr not in team_obj:
                            set_ops[f"franchise_teams.{team_id}.{attr}"] = default_value
                            updated = True
        
        if updated:
            update_ops = {}
            if unset_ops:
                update_ops["$unset"] = unset_ops
            if set_ops:
                update_ops["$set"] = set_ops
            
            franchises_collection.update_one(
                {"_id": franchise["_id"]},
                update_ops
            )
            modified_count += 1
    
    print(f"   ✅ Updated {modified_count} franchise documents")
    return modified_count

def update_games_collection():
    """Remove old attributes and add new attributes to games collection (nested in team objects)."""
    print("📋 Processing games collection...")
    modified_count = 0
    
    # Get all game documents
    games = games_collection.find({})
    
    for game in games:
        updated = False
        unset_ops = {}
        set_ops = {}
        
        # Check for home_team and away_team objects
        for team_key in ["home_team", "away_team"]:
            if team_key in game and isinstance(game[team_key], dict):
                team_obj = game[team_key]
                # Remove old attributes
                for attr in ATTRIBUTES_TO_REMOVE:
                    if attr in team_obj:
                        unset_ops[f"{team_key}.{attr}"] = ""
                        updated = True
                
                # Add new attributes (only if they don't exist)
                for attr, default_value in ATTRIBUTES_TO_ADD.items():
                    if attr not in team_obj:
                        set_ops[f"{team_key}.{attr}"] = default_value
                        updated = True
        
        # Also check for teams object (if it exists)
        if "teams" in game and isinstance(game["teams"], dict):
            for team_id, team_obj in game["teams"].items():
                if isinstance(team_obj, dict):
                    # Remove old attributes
                    for attr in ATTRIBUTES_TO_REMOVE:
                        if attr in team_obj:
                            unset_ops[f"teams.{team_id}.{attr}"] = ""
                            updated = True
                    
                    # Add new attributes (only if they don't exist)
                    for attr, default_value in ATTRIBUTES_TO_ADD.items():
                        if attr not in team_obj:
                            set_ops[f"teams.{team_id}.{attr}"] = default_value
                            updated = True
        
        if updated:
            update_ops = {}
            if unset_ops:
                update_ops["$unset"] = unset_ops
            if set_ops:
                update_ops["$set"] = set_ops
            
            games_collection.update_one(
                {"_id": game["_id"]},
                update_ops
            )
            modified_count += 1
    
    print(f"   ✅ Updated {modified_count} game documents")
    return modified_count

def main():
    """Main execution function."""
    print("🔄 Updating team attributes in MongoDB...")
    print(f"   Attributes to remove: {', '.join(ATTRIBUTES_TO_REMOVE)}")
    print(f"   Attributes to add: {', '.join(ATTRIBUTES_TO_ADD.keys())} (default: 0)")
    print()
    
    teams_count = update_teams_collection()
    tournaments_count = update_tournaments_collection()
    franchises_count = update_franchises_collection()
    games_count = update_games_collection()
    
    print()
    print("✅ Update complete!")
    print(f"   Teams collection: {teams_count} documents updated")
    print(f"   Tournaments collection: {tournaments_count} documents updated")
    print(f"   Franchises collection: {franchises_count} documents updated")
    print(f"   Games collection: {games_count} documents updated")

if __name__ == "__main__":
    main()

