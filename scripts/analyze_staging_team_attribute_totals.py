#!/usr/bin/env python3
"""
Analyze team attribute totals from staging JSON files.

This script:
1. Loads players from staging JSON files in the teams folder
2. Groups players by team
3. Verifies each team has exactly 12 players
4. Calculates team-level totals for all player attributes
5. Ranks teams for each attribute
6. Generates a report document in the same format as team_attribute_analysis.txt
"""

import os
import sys
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


def load_staging_team_files(teams_dir: Path) -> Dict[str, List[Dict]]:
    """
    Load all staging JSON files and extract players.
    
    Returns:
        dict: {
            "team_name": [player1, player2, ...]
        }
    """
    teams_data = defaultdict(list)
    staging_files = [
        "bentley_truman_staging.json",
        "lancaster_staging.json",
        "four_corners_staging.json",
        "morristown_staging.json",
        "ocean_city_staging.json",
        "south_lancaster_staging.json",
        "little_york_staging.json",
        "xavien_staging.json",  # Include Xavien team
    ]
    
    for filename in staging_files:
        file_path = teams_dir / filename
        if not file_path.exists():
            print(f"⚠️ Warning: File not found: {filename}")
            continue
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        team_name = data.get("name")
        if not team_name:
            print(f"⚠️ Warning: No team name in {filename}")
            continue
        
        players = data.get("players", [])
        teams_data[team_name] = players
        print(f"✅ Loaded {len(players)} players from {team_name}")
    
    return teams_data


def analyze_team_attributes(teams_data: Dict[str, List[Dict]]) -> Dict:
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
    # Note: In JSON files, attributes are stored directly on the player object, not in an "attributes" dict
    team_totals = {}
    for team_name, players in teams_data.items():
        totals = {attr: 0 for attr in attributes}
        
        for player in players:
            for attr in attributes:
                # Attributes are stored directly on player object in JSON files
                totals[attr] += player.get(attr, 0)
        
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
    
    Format matches team_attribute_analysis.txt exactly:
    Team Name (total):
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
        
        report_lines.append(f"{team_name} ({overall_total}):")
        
        attr_strings = []
        
        for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH"]:
            total = team_attrs[attr]
            rank = rank_lookup[attr][team_name]
            attr_strings.append(f"{attr}: {total} ({rank})")
        
        report_lines.append(", ".join(attr_strings))
        report_lines.append("")
    
    # Add stack rankings for each attribute
    report_lines.append("")
    attributes_list = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]
    
    for attr in attributes_list:
        report_lines.append(attr)
        report_lines.append("")
        for rank, (team_name, total) in enumerate(rankings[attr], start=1):
            report_lines.append(f"{rank}. {team_name}: {total}")
        report_lines.append("")
    
    # Generate Top 20 Overall list
    report_lines.append("Overall")
    report_lines.append("")
    
    # Create list of all (team_name, attribute, value) tuples
    all_values = []
    for attr in attributes_list:
        for team_name, total in rankings[attr]:
            all_values.append((team_name, attr, total))
    
    # Sort by value descending
    all_values.sort(key=lambda x: x[2], reverse=True)
    
    # Top 20
    for rank, (team_name, attr, value) in enumerate(all_values[:20], start=1):
        report_lines.append(f"{rank}. {team_name} {attr}: {value}")
    
    report_lines.append("")
    
    # Generate Top 20 (excluding FT) list
    report_lines.append("Overall (excluding FT)")
    report_lines.append("")
    
    # Filter out FT values
    all_values_no_ft = [(team, attr, val) for team, attr, val in all_values if attr != "FT"]
    
    # Top 20 (or however many there are)
    for rank, (team_name, attr, value) in enumerate(all_values_no_ft[:20], start=1):
        report_lines.append(f"{rank}. {team_name} {attr}: {value}")
    
    return "\n".join(report_lines)


def save_report(report: str, output_file: str = "staging_team_attribute_analysis.txt"):
    """Save report to teams folder."""
    # Get the teams directory (parent of scripts directory)
    teams_dir = Path(__file__).resolve().parent.parent / "teams"
    teams_dir.mkdir(exist_ok=True)
    
    output_path = teams_dir / output_file
    
    with open(output_path, "w") as f:
        f.write(report)
    
    print(f"✅ Report saved to: {output_path}")


def main():
    """Main execution function."""
    try:
        # Get teams directory
        teams_dir = Path(__file__).resolve().parent.parent / "teams"
        
        if not teams_dir.exists():
            raise FileNotFoundError(f"Teams directory not found: {teams_dir}")
        
        print("📂 Loading staging JSON files...")
        teams_data = load_staging_team_files(teams_dir)
        
        if not teams_data:
            print("❌ No team data loaded")
            sys.exit(1)
        
        print("\n📊 Analyzing team attributes...")
        analysis = analyze_team_attributes(teams_data)
        
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

