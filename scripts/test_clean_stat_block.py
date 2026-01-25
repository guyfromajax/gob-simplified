#!/usr/bin/env python3
"""Test _clean_stat_block function"""

import sys
sys.path.insert(0, '.')

from BackEnd.utils.stat_updater import _clean_stat_block

# Test with sample player data from box_score
sample_player = {
    "playerId": "test-id",
    "name": "Test Player",
    "jersey": 1,
    "PTS": 14,
    "FGM": 6,
    "FGA": 12,
    "3PTM": 1,
    "3PTA": 3,
    "REB": 5,
    "AST": 2,
    "MIN": 480,  # seconds
    "x": 50,  # Should be filtered
    "y": 25,  # Should be filtered
    "team": "Test Team",  # Should be filtered
    "pos": "PG"  # Should be filtered
}

print("Testing _clean_stat_block...")
print(f"Input: {sample_player}")
print()

cleaned = _clean_stat_block(sample_player)

print(f"Cleaned stats: {cleaned}")
print()
print(f"Stats that should be kept: PTS, FGM, FGA, 3PTM, 3PTA, REB, AST, MIN")
print(f"Stats that should be filtered: playerId, name, jersey, x, y, team, pos")
print()

if "PTS" in cleaned and cleaned["PTS"] == 14:
    print("✅ PTS correctly kept")
else:
    print(f"❌ PTS issue: {cleaned.get('PTS', 'MISSING')}")

if "3PTM" in cleaned and cleaned["3PTM"] == 1:
    print("✅ 3PTM correctly kept")
else:
    print(f"❌ 3PTM issue: {cleaned.get('3PTM', 'MISSING')}")

if "playerId" not in cleaned:
    print("✅ playerId correctly filtered")
else:
    print("❌ playerId should be filtered but is present")

if "x" not in cleaned:
    print("✅ x correctly filtered")
else:
    print("❌ x should be filtered but is present")

print()
print(f"Total cleaned stats: {len(cleaned)}")

