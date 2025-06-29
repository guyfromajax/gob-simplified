
from BackEnd.db import teams_collection, players_collection

teams_collection.delete_many({})
players_collection.delete_many({})
print("✅ Cleared all teams and players")
