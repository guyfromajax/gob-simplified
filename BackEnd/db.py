import os
from pymongo import MongoClient
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

# ✅ LOCAL DEV: Load .env.local if it exists (dev), otherwise use .env (Railway)
# This allows local dev to use different MongoDB (local or Atlas) without affecting Railway
import sys
print("🔵 [DEBUG] db.py: Starting module", file=sys.stderr, flush=True)
if os.path.exists(".env.local"):
    load_dotenv(".env.local")
    print("🔧 [LOCAL DEV] Loaded .env.local", file=sys.stderr, flush=True)
else:
    load_dotenv()  # Load .env or use Railway env vars
    print("☁️ [RAILWAY/PROD] Loaded .env or system environment", file=sys.stderr, flush=True)

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
    """Initialize MongoDB client. Returns None on any error to allow graceful fallback to mongomock."""
    if not uri:
        print("⚠️ [DB] MONGO_URI not set - will use mongomock", file=sys.stderr, flush=True)
        return None
    try:
        print(f"🔵 [DB] Attempting to connect to MongoDB...", file=sys.stderr, flush=True)
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        print(f"✅ [DB] MongoDB client created successfully", file=sys.stderr, flush=True)
        return client
    except Exception as e:  # Catch ALL exceptions, not just PyMongoError
        print(f"⚠️ [DB] Failed to initialize MongoDB client: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        print(f"⚠️ [DB] Will fallback to mongomock for development", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None

# Get database name (configurable for staging/production separation)
print("🔵 [DEBUG] db.py: About to get database name", file=sys.stderr, flush=True)
DB_NAME = _get_database_name(MONGO_URI)
print(f"📊 [DB CONFIG] Using database: {DB_NAME}", file=sys.stderr, flush=True)

print("🔵 [DEBUG] db.py: About to initialize MongoDB client", file=sys.stderr, flush=True)
client = _init_client(MONGO_URI)
print(f"🔵 [DEBUG] db.py: MongoDB client initialized: {client is not None}", file=sys.stderr, flush=True)

if client:
    print(f"🔵 [DEBUG] db.py: Using real MongoDB client, database: {DB_NAME}", file=sys.stderr, flush=True)
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
    print("🔵 [DEBUG] db.py: Collections initialized", file=sys.stderr, flush=True)
else:
    print("🔵 [DEBUG] db.py: Using mongomock (no MongoDB connection)", file=sys.stderr, flush=True)
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
    print("🔵 [DEBUG] db.py: Mongomock collections initialized", file=sys.stderr, flush=True)

print("🔵 [DEBUG] db.py: Module initialization complete", file=sys.stderr, flush=True)


