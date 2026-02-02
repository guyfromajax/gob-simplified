#!/usr/bin/env python3
"""
Delete All Franchises and Related Data from gob-staging

⚠️  WARNING: This will delete ALL documents from:
  - franchises
  - franchise_team_data (FTD)
  - franchise_players_data (FPD)
  - franchise_recruits_data (FRD)
in the gob-staging database. This is a destructive operation and cannot be undone.

Use this to start with a fresh slate (e.g. before re-running FTD migration).
"""

import os
import sys
import subprocess

# Try to use mongosh (MongoDB Shell) if available
def delete_with_mongosh():
    """Use mongosh to delete all franchises."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("❌ MONGO_URI not found in environment variables")
        return False
    
    db_name = "gob-staging"
    try:
        # Use full URI (with credentials) so mongosh can authenticate
        # MongoDB shell command to delete franchises, FTD, FPD, FRD
        js_command = f"""
        use('{db_name}');
        let count = db.franchises.countDocuments({{}});
        print('📈 Current franchises count: ' + count + ' documents');
        if (count > 0) {{
            const result = db.franchises.deleteMany({{}});
            print('✅ Deleted ' + result.deletedCount + ' franchise documents');
        }} else {{ print('✅ Franchises already empty.'); }}
        count = db.franchise_team_data.countDocuments({{}});
        print('📈 Current franchise_team_data (FTD) count: ' + count);
        if (count > 0) {{
            const result = db.franchise_team_data.deleteMany({{}});
            print('✅ Deleted ' + result.deletedCount + ' franchise_team_data documents');
        }} else {{ print('✅ FTD already empty.'); }}
        count = db.franchise_players_data.countDocuments({{}});
        print('📈 Current franchise_players_data (FPD) count: ' + count);
        if (count > 0) {{
            const result = db.franchise_players_data.deleteMany({{}});
            print('✅ Deleted ' + result.deletedCount + ' franchise_players_data documents');
        }} else {{ print('✅ FPD already empty.'); }}
        count = db.franchise_recruits_data.countDocuments({{}});
        print('📈 Current franchise_recruits_data (FRD) count: ' + count);
        if (count > 0) {{
            const result = db.franchise_recruits_data.deleteMany({{}});
            print('✅ Deleted ' + result.deletedCount + ' franchise_recruits_data documents');
        }} else {{ print('✅ FRD already empty.'); }}
        const fRem = db.franchises.countDocuments({{}});
        const ftdRem = db.franchise_team_data.countDocuments({{}});
        const fpdRem = db.franchise_players_data.countDocuments({{}});
        const frdRem = db.franchise_recruits_data.countDocuments({{}});
        print('📊 Final: franchises=' + fRem + ', FTD=' + ftdRem + ', FPD=' + fpdRem + ', FRD=' + frdRem);
        if (fRem === 0 && ftdRem === 0 && fpdRem === 0 && frdRem === 0) {{
            print('✅ Success! All franchise-related collections empty in gob-staging');
        }}
        """
        
        # Run mongosh with full URI (includes credentials)
        try:
            result = subprocess.run(
                ["mongosh", mongo_uri, "--eval", js_command],
                capture_output=True,
                text=True,
                timeout=30
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return result.returncode == 0
        except FileNotFoundError:
            print("⚠️  mongosh not found. Install MongoDB Shell or use Python method.")
            return False
    except Exception as e:
        print(f"❌ Error running mongosh: {e}")
        return False

# Try Python approach first
def delete_with_python():
    """Use pymongo to delete all franchises, FTD, FPD, and FRD."""
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
        ftd_collection = db["franchise_team_data"]
        fpd_collection = db["franchise_players_data"]
        frd_collection = db["franchise_recruits_data"]
        
        # Count current documents
        franchises_count = franchises_collection.count_documents({})
        ftd_count = ftd_collection.count_documents({})
        fpd_count = fpd_collection.count_documents({})
        frd_count = frd_collection.count_documents({})
        print(f"📈 Current franchises count: {franchises_count} documents")
        print(f"📈 Current franchise_team_data (FTD) count: {ftd_count} documents")
        print(f"📈 Current franchise_players_data (FPD) count: {fpd_count} documents")
        print(f"📈 Current franchise_recruits_data (FRD) count: {frd_count} documents")
        print()
        
        if franchises_count == 0 and ftd_count == 0 and fpd_count == 0 and frd_count == 0:
            print("✅ All franchise-related collections already empty. Nothing to delete.")
            return True
        
        print("⚠️  WARNING: This will delete ALL documents from franchises, FTD, FPD, FRD in gob-staging!")
        print("   This operation cannot be undone.")
        print()
        
        # Delete franchises
        print("🗑️  Deleting all franchise documents...")
        result_f = franchises_collection.delete_many({})
        print(f"   ✅ Deleted {result_f.deleted_count} franchise documents")
        
        # Delete franchise_team_data (FTD)
        print("🗑️  Deleting all franchise_team_data (FTD) documents...")
        result_ftd = ftd_collection.delete_many({})
        print(f"   ✅ Deleted {result_ftd.deleted_count} franchise_team_data documents")
        
        # Delete franchise_players_data (FPD)
        print("🗑️  Deleting all franchise_players_data (FPD) documents...")
        result_fpd = fpd_collection.delete_many({})
        print(f"   ✅ Deleted {result_fpd.deleted_count} franchise_players_data documents")
        
        # Delete franchise_recruits_data (FRD)
        print("🗑️  Deleting all franchise_recruits_data (FRD) documents...")
        result_frd = frd_collection.delete_many({})
        print(f"   ✅ Deleted {result_frd.deleted_count} franchise_recruits_data documents")
        print()
        
        # Verify
        remaining_f = franchises_collection.count_documents({})
        remaining_ftd = ftd_collection.count_documents({})
        remaining_fpd = fpd_collection.count_documents({})
        remaining_frd = frd_collection.count_documents({})
        print(f"📊 Final: franchises={remaining_f}, FTD={remaining_ftd}, FPD={remaining_fpd}, FRD={remaining_frd}")
        
        if remaining_f == 0 and remaining_ftd == 0 and remaining_fpd == 0 and remaining_frd == 0:
            print()
            print("✅ Success! All franchise-related collections empty in gob-staging")
            print("   Ready for fresh data")
            return True
        else:
            print()
            print(f"⚠️  Warning: some documents still remain (unexpected)")
            return False
        
    except ImportError as e:
        print(f"❌ Import error (is pymongo installed? run from repo root?): {e}")
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
    # Load .env from repo root (parent of scripts/) so it works regardless of cwd
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_vars = {}
    for name in (".env.local", ".env"):
        path = os.path.join(repo_root, name)
        if os.path.exists(path):
            env_vars.update(load_env_file(path))
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
        print(f"  mongosh '{mongo_uri}' --eval \"use('gob-staging'); db.franchises.deleteMany({{}}); db.franchise_team_data.deleteMany({{}}); db.franchise_players_data.deleteMany({{}}); db.franchise_recruits_data.deleteMany({{}});\"")
        sys.exit(1)
