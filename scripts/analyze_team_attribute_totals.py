#!/usr/bin/env python3
"""
Analyze team attribute totals from universal players collection.

This script:
1. Pulls all players from the universal players collection
2. Groups players by team
3. Verifies each team has exactly 12 players
4. Calculates team-level totals for all player attributes
5. Ranks teams for each attribute
6. Generates a report document
"""

import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection


def load_mongo_uri() -> str:
    """Load MongoDB URI from environment."""
    # Try .env.local first (local dev), then .env (Railway/prod)
    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
    else:
        load_dotenv()
    
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    return mongo_uri


def get_players_collection() -> Collection:
    """Get MongoDB players collection."""
    mongo_uri = load_mongo_uri()
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client["gob"]
    return db["players"]


def analyze_team_attributes(players_collection: Collection) -> Dict:
    """
    Analyze team attribute totals and rankings.
    
    Returns:
        dict: {
            "teams": {
                "team_name": {
                    "player_count": int,
                    "attributes": {
                        "SC": total,
                        "SH": total,
                        ...
                    }
                }
            },
            "rankings": {
                "SC": [("team_name", total), ...],  # Sorted descending
                "SH": [("team_name", total), ...],
                ...
            }
        }
    """
    # Pull all players
    all_players = list(players_collection.find({}))
    
    print(f"📊 Total players in collection: {len(all_players)}")
    
    # Group players by team
    teams_data = defaultdict(list)
    for player in all_players:
        team_name = player.get("team")
        if not team_name:
            print(f"⚠️ Warning: Player {player.get('_id')} has no team name")
            continue
        teams_data[team_name].append(player)
    
    print(f"📊 Teams found: {len(teams_data)}")
    
    # Verify each team has exactly 12 players
    teams_with_wrong_count = []
    for team_name, players in teams_data.items():
        if len(players) != 12:
            teams_with_wrong_count.append((team_name, len(players)))
            print(f"⚠️ Warning: {team_name} has {len(players)} players (expected 12)")
    
    if teams_with_wrong_count:
        print(f"\n❌ ERROR: {len(teams_with_wrong_count)} teams do not have exactly 12 players!")
        return None
    
    print("✅ All teams have exactly 12 players\n")
    
    # Attribute list to analyze
    attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH"]
    
    # Calculate team totals
    team_totals = {}
    for team_name, players in teams_data.items():
        totals = {attr: 0 for attr in attributes}
        
        for player in players:
            player_attrs = player.get("attributes", {})
            for attr in attributes:
                totals[attr] += player_attrs.get(attr, 0)
        
        team_totals[team_name] = {
            "player_count": len(players),
            "attributes": totals
        }
    
    # Calculate rankings for each attribute
    rankings = {}
    for attr in attributes:
        # Create list of (team_name, total) tuples
        team_scores = [(team_name, team_totals[team_name]["attributes"][attr]) 
                       for team_name in team_totals.keys()]
        # Sort descending (higher is better)
        team_scores.sort(key=lambda x: x[1], reverse=True)
        rankings[attr] = team_scores
    
    return {
        "teams": team_totals,
        "rankings": rankings
    }


def generate_report(analysis: Dict) -> str:
    """
    Generate formatted report string.
    
    Format:
    Team Name:
    SC: total (rank), SH: total (rank), ID: total (rank), ...
    """
    if not analysis:
        return "❌ Analysis failed - cannot generate report"
    
    teams = analysis["teams"]
    rankings = analysis["rankings"]
    
    # Get sorted team names (alphabetically)
    team_names = sorted(teams.keys())
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("TEAM ATTRIBUTE TOTALS AND RANKINGS")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Create rank lookup dict for each attribute
    rank_lookup = {}
    for attr, ranked_teams in rankings.items():
        rank_lookup[attr] = {}
        for rank, (team_name, _) in enumerate(ranked_teams, start=1):
            rank_lookup[attr][team_name] = rank
    
    # Generate report for each team
    for team_name in team_names:
        team_attrs = teams[team_name]["attributes"]
        
        # Calculate overall attribute total
        overall_total = sum(team_attrs.values())
        
        report_lines.append(f"{team_name} ({overall_total:,}):")
        
        attr_strings = []
        
        for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH"]:
            total = team_attrs[attr]
            rank = rank_lookup[attr][team_name]
            attr_strings.append(f"{attr}: {total} ({rank})")
        
        report_lines.append(", ".join(attr_strings))
        report_lines.append("")
    
    return "\n".join(report_lines)


def save_report(report: str, output_file: str = "team_attribute_analysis.txt"):
    """Save report to file."""
    output_path = os.path.join("docs", output_file)
    os.makedirs("docs", exist_ok=True)
    
    with open(output_path, "w") as f:
        f.write(report)
    
    print(f"✅ Report saved to: {output_path}")


def main():
    """Main execution function."""
    try:
        print("🔍 Connecting to MongoDB...")
        players_collection = get_players_collection()
        
        print("📊 Analyzing team attributes...")
        analysis = analyze_team_attributes(players_collection)
        
        if not analysis:
            print("❌ Analysis failed")
            sys.exit(1)
        
        print("📝 Generating report...")
        report = generate_report(analysis)
        
        print("\n" + report)
        
        print("\n💾 Saving report to file...")
        save_report(report)
        
        print("\n✅ Analysis complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

