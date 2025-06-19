import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()  # ✅ Load variables from .env into os.environ


MONGO_URI = os.environ["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["gob"]
players_collection = db["players"]
teams_collection = db["teams"]
games_collection = db["games"]
