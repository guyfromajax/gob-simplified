import os
from pymongo import MongoClient
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

# ✅ LOCAL DEV: Load .env.local if it exists (dev), otherwise use .env (Railway)
# This allows local dev to use different MongoDB (local or Atlas) without affecting Railway
if os.path.exists(".env.local"):
    load_dotenv(".env.local")
    print("🔧 [LOCAL DEV] Loaded .env.local")
else:
    load_dotenv()  # Load .env or use Railway env vars
    print("☁️ [RAILWAY/PROD] Loaded .env or system environment")

MONGO_URI = os.environ.get("MONGO_URI")

def _get_database_name(uri: str | None) -> str:
    """
    Extract database name from MONGO_URI or use environment variable.
    
    Priority:
    1. MONGO_DB_NAME environment variable (explicit)
    2. Database name from MONGO_URI path (e.g., mongodb+srv://.../gob-staging?...)
    3. Default to 'gob' (backward compatibility)
    """
    # Check for explicit database name environment variable
    db_name_env = os.environ.get("MONGO_DB_NAME")
    if db_name_env:
        return db_name_env
    
    # Try to extract from MONGO_URI if it contains database name in path
    if uri:
        # Format: mongodb+srv://user:pass@cluster.mongodb.net/database?options
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(uri)
            if parsed.path and parsed.path != '/':
                # Path will be like '/gob-staging' - remove leading slash
                db_name = parsed.path.lstrip('/')
                if db_name:
                    return db_name
        except Exception:
            # If parsing fails, fall through to default
            pass
    
    # Default to 'gob' for backward compatibility
    return "gob"

def _init_client(uri: str | None):
    if not uri:
        return None
    try:
        return MongoClient(uri, serverSelectionTimeoutMS=5000)
    except PyMongoError as e:
        print(f"⚠️ Failed to connect to MongoDB at {uri}: {e}")
        return None

# Get database name (configurable for staging/production separation)
DB_NAME = _get_database_name(MONGO_URI)
print(f"📊 [DB CONFIG] Using database: {DB_NAME}")

client = _init_client(MONGO_URI)

if client:
    db = client[DB_NAME]
    players_collection = db["players"]
    teams_collection = db["teams"]
    games_collection = db["games"]
    tournaments_collection = db["tournaments"]
    training_log_collection = db["training_sessions"]
    franchise_state_collection = db["franchise_state"]
    franchises_collection = db["franchises"]
    plays_collection = db["plays"]
    defenses_collection = db["defenses"]
    fcp_skeletons_collection = db["fcp_skeletons"]
    hct_skeletons_collection = db["hct_skeletons"]
else:
    import mongomock
    client = mongomock.MongoClient()
    db = client[DB_NAME]  # DB_NAME is defined at module level above
    players_collection = db["players"]
    teams_collection = db["teams"]
    games_collection = db["games"]
    tournaments_collection = db["tournaments"]
    training_log_collection = db["training_sessions"]
    franchise_state_collection = db["franchise_state"]
    franchises_collection = db["franchises"]
    plays_collection = db["plays"]
    defenses_collection = db["defenses"]
    fcp_skeletons_collection = db["fcp_skeletons"]
    hct_skeletons_collection = db["hct_skeletons"]


