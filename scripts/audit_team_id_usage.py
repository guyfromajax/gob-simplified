#!/usr/bin/env python3
"""
Team ID Format Audit Script

Scans the codebase to identify all team ID usage patterns and format inconsistencies.
This is a READ-ONLY audit - no code or data is modified.

Usage:
    python scripts/audit_team_id_usage.py
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

# Try to import ObjectId for database checks (optional)
try:
    from bson import ObjectId
    HAS_BSON = True
except ImportError:
    HAS_BSON = False
    ObjectId = None

# Patterns to search for
TEAM_ID_PATTERNS = [
    r'team_id\s*[=:]',  # team_id = or team_id:
    r'teamId\s*[=:]',   # teamId = or teamId:
    r'team_identifier', # team_identifier
    r'user_team_id',    # user_team_id
    r'userTeamId',      # userTeamId (camelCase)
    r'userTeamId',      # userTeamId
    r'home_team_id',    # home_team_id
    r'away_team_id',    # away_team_id
    r'franchise_teams\[',  # franchise_teams[team_id]
    r'tournament\.teams\[',  # tournament.teams[team_id]
    r'teams\[.*team_id',    # teams[team_id]
    r'meta\.team_id',       # meta.team_id
    r'\.team_id',           # .team_id (any attribute)
    r'team_id_str',         # team_id_str
    r'team_id_key',         # team_id_key
    r'team_id_to_object_id', # team_id_to_object_id
    r'team_name_to_id',     # team_name_to_id
    r'teamId',              # teamId (camelCase)
]

# Files to scan
BACKEND_PATHS = [
    'BackEnd/api',
    'BackEnd/models',
    'BackEnd/utils',
    'BackEnd/tournament',
    'BackEnd/season',
]

FRONTEND_PATHS = [
    'FrontEnd/static',
]

# Files to exclude
EXCLUDE_PATTERNS = [
    '__pycache__',
    '.pyc',
    'node_modules',
    '.git',
    'venv',
    'tests/',  # We'll scan tests separately
]

def is_excluded(file_path: str) -> bool:
    """Check if file should be excluded from scanning."""
    return any(pattern in file_path for pattern in EXCLUDE_PATTERNS)

def find_files(directories: List[str], extensions: List[str]) -> List[str]:
    """Find all files with given extensions in directories."""
    files = []
    for directory in directories:
        if not os.path.exists(directory):
            continue
        for root, dirs, filenames in os.walk(directory):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not is_excluded(os.path.join(root, d))]
            
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, filename)
                    if not is_excluded(file_path):
                        files.append(file_path)
    return files

def scan_file_for_team_id_usage(file_path: str) -> List[Dict]:
    """Scan a file for team ID usage patterns."""
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [{"error": f"Could not read file: {e}"}]
    
    for line_num, line in enumerate(lines, 1):
        for pattern in TEAM_ID_PATTERNS:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                # Get context (20 chars before and after)
                start = max(0, match.start() - 20)
                end = min(len(line), match.end() + 20)
                context = line[start:end].strip()
                
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "pattern": pattern,
                    "context": context,
                    "full_line": line.strip()
                })
    
    return findings

def analyze_team_id_format_usage(findings: List[Dict]) -> Dict:
    """Analyze findings to categorize team ID format usage."""
    analysis = {
        "by_file": defaultdict(list),
        "by_pattern": defaultdict(list),
        "format_indicators": {
            "objectid_string": [],  # str(ObjectId) or ObjectId string
            "team_id_string": [],   # "MORRISTOWN" style
            "team_name": [],        # "Morristown" style
            "ambiguous": []         # Could be either
        },
        "high_risk_locations": [],  # Places that do lookups/assignments
    }
    
    # Keywords that indicate format
    objectid_indicators = ['ObjectId', 'str(', 'team_obj_id', 'team_object_id', 'resolved_team_id']
    team_id_string_indicators = ['team_id_key', 'team_id_str', 'home_team_id', 'away_team_id', 'game.get("home_team_id")']
    team_name_indicators = ['team_name', 'team.get("name")', 'team_doc.get("name")']
    
    for finding in findings:
        file_path = finding["file"]
        line = finding["full_line"]
        context = finding["context"].lower()
        
        analysis["by_file"][file_path].append(finding)
        analysis["by_pattern"][finding["pattern"]].append(finding)
        
        # Categorize format usage
        is_objectid = any(indicator.lower() in context for indicator in objectid_indicators)
        is_team_id_string = any(indicator.lower() in context for indicator in team_id_string_indicators)
        is_team_name = any(indicator.lower() in context for indicator in team_name_indicators)
        
        # High-risk locations (lookups, assignments, dictionary keys)
        is_high_risk = any(keyword in line for keyword in [
            '.get(', '=', 'meta.team_id', 'teams[', 'franchise_teams[', 'tournament.teams[',
            'box_score[', 'team_stats_map[', 'set_doc[', 'inc_doc['
        ])
        
        if is_high_risk:
            analysis["high_risk_locations"].append(finding)
        
        if is_objectid:
            analysis["format_indicators"]["objectid_string"].append(finding)
        elif is_team_id_string:
            analysis["format_indicators"]["team_id_string"].append(finding)
        elif is_team_name:
            analysis["format_indicators"]["team_name"].append(finding)
        else:
            analysis["format_indicators"]["ambiguous"].append(finding)
    
    return analysis

def check_database_format_consistency():
    """Check database documents for team ID format consistency."""
    if not HAS_BSON:
        print("⚠️  bson module not available. Skipping database format checks.")
        return None
    
    try:
        from BackEnd.db import teams_collection, tournaments_collection, franchises_collection, games_collection
        
        issues = {
            "tournament_players": [],
            "franchise_players": [],
            "game_documents": [],
        }
        
        # Check tournament.players[].meta.team_id
        print("🔍 Checking tournament.players[].meta.team_id formats...")
        tournaments = tournaments_collection.find({}, {"players": 1})
        for tournament in tournaments:
            players = tournament.get("players", {})
            for pid, pdata in players.items():
                meta = pdata.get("meta", {})
                team_id = meta.get("team_id")
                if team_id:
                    # Check if it's ObjectId string format
                    is_objectid = False
                    try:
                        if ObjectId:
                            ObjectId(team_id)
                            is_objectid = True
                    except:
                        pass
                    
                    if not is_objectid:
                        issues["tournament_players"].append({
                            "tournament_id": str(tournament.get("_id")),
                            "player_id": pid,
                            "team_id_value": team_id,
                            "format": "team_id_string" if len(team_id) < 20 else "unknown"
                        })
        
        # Check franchise.players[].meta.team_id
        print("🔍 Checking franchise.players[].meta.team_id formats...")
        franchises = franchises_collection.find({}, {"players": 1})
        for franchise in franchises:
            players = franchise.get("players", {})
            for pid, pdata in players.items():
                meta = pdata.get("meta", {})
                team_id = meta.get("team_id")
                if team_id:
                    is_objectid = False
                    try:
                        if ObjectId:
                            ObjectId(team_id)
                            is_objectid = True
                    except:
                        pass
                    
                    if not is_objectid:
                        issues["franchise_players"].append({
                            "franchise_id": str(franchise.get("_id")),
                            "player_id": pid,
                            "team_id_value": team_id,
                            "format": "team_id_string" if len(team_id) < 20 else "unknown"
                        })
        
        # Check game documents for box_score keys
        print("🔍 Checking game documents for box_score key formats...")
        games = games_collection.find({}, {"box_score": 1, "home_team_id": 1, "away_team_id": 1})
        for game in games:
            box_score = game.get("box_score", {})
            if box_score:
                for key in box_score.keys():
                    # Check if key is ObjectId string
                    is_objectid = False
                    try:
                        if ObjectId:
                            ObjectId(key)
                            is_objectid = True
                    except:
                        pass
                    
                    if not is_objectid:
                        issues["game_documents"].append({
                            "game_id": str(game.get("_id")),
                            "box_score_key": key,
                            "format": "team_id_string" if len(key) < 20 else "team_name"
                        })
        
        return issues
        
    except ImportError:
        print("⚠️  Could not import database modules. Skipping database checks.")
        return None
    except Exception as e:
        print(f"⚠️  Error checking database: {e}")
        return None

def generate_report(analysis: Dict, db_issues: Dict = None) -> str:
    """Generate a human-readable report."""
    report = []
    report.append("=" * 80)
    report.append("TEAM ID FORMAT AUDIT REPORT")
    report.append("=" * 80)
    report.append("")
    
    # Summary
    total_findings = sum(len(findings) for findings in analysis["by_file"].values())
    report.append(f"📊 SUMMARY")
    report.append(f"   Total team ID references found: {total_findings}")
    report.append(f"   Files with team ID usage: {len(analysis['by_file'])}")
    report.append(f"   High-risk locations: {len(analysis['high_risk_locations'])}")
    report.append("")
    
    # Format breakdown
    report.append(f"📋 FORMAT BREAKDOWN")
    for format_type, findings in analysis["format_indicators"].items():
        report.append(f"   {format_type}: {len(findings)} references")
    report.append("")
    
    # High-risk locations
    report.append(f"🔴 HIGH-RISK LOCATIONS (Lookups/Assignments)")
    report.append(f"   These locations do lookups or assignments and are most likely to cause bugs:")
    report.append("")
    
    high_risk_by_file = defaultdict(list)
    for finding in analysis["high_risk_locations"]:
        high_risk_by_file[finding["file"]].append(finding)
    
    for file_path, findings in sorted(high_risk_by_file.items())[:20]:  # Top 20 files
        report.append(f"   {file_path}: {len(findings)} high-risk locations")
        for finding in findings[:3]:  # Show first 3 examples
            report.append(f"      Line {finding['line']}: {finding['context']}")
        if len(findings) > 3:
            report.append(f"      ... and {len(findings) - 3} more")
        report.append("")
    
    # Files by pattern
    report.append(f"📁 FILES WITH MOST TEAM ID USAGE")
    file_counts = [(file, len(findings)) for file, findings in analysis["by_file"].items()]
    file_counts.sort(key=lambda x: x[1], reverse=True)
    
    for file_path, count in file_counts[:15]:  # Top 15 files
        report.append(f"   {file_path}: {count} references")
    report.append("")
    
    # Database issues
    if db_issues:
        report.append(f"🗄️  DATABASE FORMAT INCONSISTENCIES")
        
        tournament_issues = len(db_issues.get("tournament_players", []))
        franchise_issues = len(db_issues.get("franchise_players", []))
        game_issues = len(db_issues.get("game_documents", []))
        
        report.append(f"   Tournament players with non-ObjectId team_id: {tournament_issues}")
        report.append(f"   Franchise players with non-ObjectId team_id: {franchise_issues}")
        report.append(f"   Game documents with non-ObjectId box_score keys: {game_issues}")
        report.append("")
        
        if tournament_issues > 0:
            report.append(f"   Sample tournament issues (first 5):")
            for issue in db_issues["tournament_players"][:5]:
                report.append(f"      Tournament {issue['tournament_id']}, Player {issue['player_id']}: team_id='{issue['team_id_value']}' (format: {issue['format']})")
            report.append("")
        
        if franchise_issues > 0:
            report.append(f"   Sample franchise issues (first 5):")
            for issue in db_issues["franchise_players"][:5]:
                report.append(f"      Franchise {issue['franchise_id']}, Player {issue['player_id']}: team_id='{issue['team_id_value']}' (format: {issue['format']})")
            report.append("")
        
        if game_issues > 0:
            report.append(f"   Sample game document issues (first 5):")
            for issue in db_issues["game_documents"][:5]:
                report.append(f"      Game {issue['game_id']}: box_score key='{issue['box_score_key']}' (format: {issue['format']})")
            report.append("")
    
    # Recommendations
    report.append(f"💡 RECOMMENDATIONS")
    report.append("   1. Start with high-risk locations (lookups/assignments)")
    report.append("   2. Create unified resolve_team_id() helper function")
    report.append("   3. Add validation at API boundaries")
    report.append("   4. Migrate database documents with format mismatches")
    report.append("   5. Replace usage incrementally, file by file")
    report.append("")
    
    report.append("=" * 80)
    
    return "\n".join(report)

def main():
    """Main audit function."""
    print("🔍 Starting Team ID Format Audit...")
    print("")
    
    # Find all files to scan
    print("📁 Scanning codebase for team ID usage...")
    backend_files = find_files(BACKEND_PATHS, ['.py'])
    frontend_files = find_files(FRONTEND_PATHS, ['.js'])
    
    print(f"   Found {len(backend_files)} Python files")
    print(f"   Found {len(frontend_files)} JavaScript files")
    print("")
    
    # Scan files
    print("🔍 Scanning files for team ID patterns...")
    all_findings = []
    
    for file_path in backend_files + frontend_files:
        findings = scan_file_for_team_id_usage(file_path)
        all_findings.extend(findings)
        if findings:
            print(f"   Found {len(findings)} references in {file_path}")
    
    print(f"\n✅ Scanned {len(backend_files) + len(frontend_files)} files")
    print(f"   Found {len(all_findings)} total team ID references")
    print("")
    
    # Analyze findings
    print("📊 Analyzing findings...")
    analysis = analyze_team_id_format_usage(all_findings)
    print("")
    
    # Check database
    print("🗄️  Checking database for format consistency...")
    db_issues = check_database_format_consistency()
    print("")
    
    # Generate report
    report = generate_report(analysis, db_issues)
    
    # Print report
    print(report)
    
    # Save to file
    output_file = "team_id_audit_report.txt"
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"\n💾 Full report saved to: {output_file}")
    
    # Also save JSON for programmatic access
    json_output = {
        "summary": {
            "total_references": len(all_findings),
            "files_scanned": len(backend_files) + len(frontend_files),
            "files_with_usage": len(analysis["by_file"]),
            "high_risk_locations": len(analysis["high_risk_locations"])
        },
        "format_breakdown": {
            format_type: len(findings) 
            for format_type, findings in analysis["format_indicators"].items()
        },
        "top_files": [
            {"file": file, "count": len(findings)}
            for file, findings in sorted(analysis["by_file"].items(), key=lambda x: len(x[1]), reverse=True)[:20]
        ],
        "high_risk_locations": [
            {
                "file": f["file"],
                "line": f["line"],
                "pattern": f["pattern"],
                "context": f["context"]
            }
            for f in analysis["high_risk_locations"][:50]  # Top 50
        ],
        "database_issues": db_issues
    }
    
    json_file = "team_id_audit_report.json"
    with open(json_file, 'w') as f:
        json.dump(json_output, f, indent=2)
    
    print(f"💾 JSON data saved to: {json_file}")

if __name__ == "__main__":
    main()

