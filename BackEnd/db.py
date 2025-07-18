import os
from pymongo import MongoClient
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")

def _init_client(uri: str | None):
    if not uri:
        return None
    try:
        return MongoClient(uri, serverSelectionTimeoutMS=5000)
    except PyMongoError as e:
        print(f"⚠️ Failed to connect to MongoDB at {uri}: {e}")
        return None

client = _init_client(MONGO_URI)

if client:
    db = client["gob"]
    players_collection = db["players"]
    teams_collection = db["teams"]
    games_collection = db["games"]
    tournaments_collection = db["tournaments"]
    training_log_collection = db["training_sessions"]
else:
    import mongomock
    client = mongomock.MongoClient()
    db = client["gob"]
    players_collection = db["players"]
    teams_collection = db["teams"]
    games_collection = db["games"]
    tournaments_collection = db["tournaments"]
    training_log_collection = db["training_sessions"]


