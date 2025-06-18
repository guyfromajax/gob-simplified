import os
from pymongo import MongoClient

MONGO_URI = os.environ["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["gob"]
players_collection = db["players"]
teams_collection = db["teams"]
games_collection = db["games"]
