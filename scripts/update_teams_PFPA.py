from pathlib import Path
import sys

# Setup for relative imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from BackEnd.db import db

def add_pf_pa_to_teams():
    teams = db.teams.find()
    updates = 0

    for team in teams:
        update_fields = {}
        if "PF" not in team:
            update_fields["PF"] = 0
        if "PA" not in team:
            update_fields["PA"] = 0

        if update_fields:
            db.teams.update_one({"_id": team["_id"]}, {"$set": update_fields})
            updates += 1
            print(f"✅ Updated {team['name']} with: {update_fields}")

    if updates == 0:
        print("✅ All teams already have PF and PA fields.")
    else:
        print(f"✅ Updated {updates} team(s) in total.")

if __name__ == "__main__":
    add_pf_pa_to_teams()
