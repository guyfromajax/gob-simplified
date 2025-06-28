
# print_teams.py

from BackEnd.db import teams_collection

def list_all_teams():
    teams = teams_collection.find()
    print("📋 All teams in the database:")
    for team in teams:
        print("-", team.get("name"))

if __name__ == "__main__":
    list_all_teams()
