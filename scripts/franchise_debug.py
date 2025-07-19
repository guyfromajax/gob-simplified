"""Debugging utilities for the franchise manager.

This script can be executed directly via ``python scripts/franchise_debug.py``.
To ensure imports work correctly when run this way we add the project root to
``sys.path``.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from BackEnd.db import db
from BackEnd.models.franchise_manager import FranchiseManager
import pprint

def debug_franchise_init():
    manager = FranchiseManager(db)
    
    print("✅ Initializing season...")
    manager.initialize_season()

    print("✅ Generating recruits...")
    manager.generate_recruits()

    print("📅 Schedule Preview (14 weeks):")
    for week_num, games in enumerate(manager.schedule, start=1):
        print(f"Week {week_num}:")
        for game in games:
            print(f"  {game[0]} vs {game[1]}")

    print("\n🎓 Recruit Sample:")
    recruits = list(db.recruits.find().limit(5))
    pprint.pprint(recruits)

if __name__ == "__main__":
    debug_franchise_init()
