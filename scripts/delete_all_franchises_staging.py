#!/usr/bin/env python3
"""
Delete All Franchises from gob-staging

⚠️  WARNING: This will delete ALL franchise documents from the gob-staging database!
This is a destructive operation and cannot be undone.

Use this to start with a fresh slate before implementing FTD collection.
"""

import os
import sys
import subprocess

# Try to use mongosh (MongoDB Shell) if available
def delete_with_mongosh():
    """Use mongosh to delete all franchises."""
    # Get MONGO_URI from environment
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("❌ MONGO_URI not found in environment variables")
        return False
    
    # Extract connection details from URI
    # Format: mongodb+srv://user:pass@cluster.mongodb.net/gob-staging?options
    try:
        from urllib.parse import urlparse
        parsed = urlparse(mongo_uri)
        cluster = parsed.netloc  # cluster.mongodb.net
        db_name = "gob-staging"
        
        # Build mongosh connection string
        # Remove credentials for security (mongosh will prompt if needed)
        connection_string = f"mongodb+srv://{cluster}/{db_name}"
        
        # MongoDB shell command to delete all franchises
        js_command = f"""
        use('{db_name}');
        const count = db.franchises.countDocuments({{}});
        print('📈 Current franchises count: ' + count + ' documents');
        if (count > 0) {{
            print('🗑️  Deleting all franchise documents...');
            const result = db.franchises.deleteMany({{}});
            print('✅ Deleted ' + result.deletedCount + ' franchise documents');
            const remaining = db.franchises.countDocuments({{}});
            print('📊 Final franchises count: ' + remaining + ' documents');
            if (remaining === 0) {{
                print('✅ Success! All franchise documents deleted from gob-staging');
            }}
        }} else {{
            print('✅ Franchises collection is already empty.');
        }}
        """
        
        # Try to run mongosh
        try:
            result = subprocess.run(
                ["mongosh", connection_string, "--eval", js_command],
                capture_output=True,
                text=True,
                timeout=30
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return result.returncode == 0
        except FileNotFoundError:
            print("⚠️  mongosh not found. Trying alternative methods...")
            return False
    except Exception as e:
        print(f"❌ Error parsing MONGO_URI: {e}")
        return False

# Try Python approach first
def delete_with_python():
    """Use pymongo to delete all franchises."""
    try:
        # Add BackEnd to path so we can import db module
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        
        # Use existing database connection from BackEnd.db
        from BackEnd.db import client
        
        if not client:
            return False
        
        # Connect to gob-staging database specifically
        db = client["gob-staging"]
        
        print("🔗 Connected to MongoDB")
        print(f"📊 Database: {db.name}")
        print()
        
        franchises_collection = db["franchises"]
        
        # Count current documents
        count = franchises_collection.count_documents({})
        print(f"📈 Current franchises count: {count} documents")
        print()
        
        if count == 0:
            print("✅ Franchises collection is already empty. Nothing to delete.")
            return True
        
        print(f"⚠️  WARNING: This will delete ALL {count} franchise documents from gob-staging!")
        print("   This operation cannot be undone.")
        print()
        print("🗑️  Deleting all franchise documents...")
        
        # Delete all documents
        result = franchises_collection.delete_many({})
        deleted_count = result.deleted_count
        
        print(f"   ✅ Deleted {deleted_count} franchise documents")
        print()
        
        # Verify deletion
        remaining_count = franchises_collection.count_documents({})
        print(f"📊 Final franchises count: {remaining_count} documents")
        
        if remaining_count == 0:
            print()
            print("✅ Success! All franchise documents deleted from gob-staging")
            print("   Collection is now empty and ready for fresh data")
            return True
        else:
            print()
            print(f"⚠️  Warning: {remaining_count} documents still remain (unexpected)")
            return False
        
    except ImportError:
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Load .env file manually
def load_env_file(filepath):
    """Load environment variables from .env file manually."""
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars

# Main execution
if __name__ == "__main__":
    # Load environment variables manually
    env_vars = {}
    if os.path.exists(".env.local"):
        env_vars.update(load_env_file(".env.local"))
    if os.path.exists(".env"):
        env_vars.update(load_env_file(".env"))
    
    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
    
    # Try Python first, then mongosh
    success = delete_with_python()
    
    if not success:
        print("\n⚠️  Python method failed. Trying mongosh...")
        success = delete_with_mongosh()
    
    if not success:
        mongo_uri = os.getenv("MONGO_URI", "your-mongo-uri")
        print("\n❌ Both methods failed.")
        print("\nAlternative: Run this MongoDB shell command manually:")
        print(f"  mongosh '{mongo_uri}' --eval \"use('gob-staging'); db.franchises.deleteMany({{}});\"")
        sys.exit(1)
