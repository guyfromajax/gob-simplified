"""
Update primary_color and secondary_color for the core 8 teams (Conference 1) in both
gob and gob-staging teams collections so they match 128_teams.txt / team JSON files.

Run from repo root:
  python3 scripts/align_core8_team_colors.py

Uses MONGO_URI from .env or .env.local. Updates both databases on the same cluster:
  - gob
  - gob-staging

If your staging DB is on a different cluster, run twice with different MONGO_URI.
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)


def _load_env(filepath):
    out = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for path in [".env.local", ".env"]:
    for k, v in _load_env(path).items():
        os.environ.setdefault(k, v)

# Canonical core 8 (Conference 1): name -> (primary_color, secondary_color)
CORE_8_COLORS = {
    "Bentley-Truman": ("#4066b2", "#ffffff"),
    "Ocean City": ("#2a2168", "#00a89d"),
    "Lancaster": ("#d24a1b", "#000000"),
    "Four Corners": ("#c0976a", "#00954b"),
    "Morristown": ("#ec1d28", "#cccccc"),
    "Xavien": ("#016837", "#999999"),
    "Little York": ("#65308e", "#f6af38"),
    "South Lancaster": ("#7c2b24", "#e39649"),
}


def main():
    try:
        from pymongo import MongoClient
    except ImportError:
        print("❌ pymongo not installed. Run: pip install pymongo", file=sys.stderr)
        sys.exit(1)

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("❌ MONGO_URI not set. Set it in .env or .env.local.", file=sys.stderr)
        sys.exit(1)

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    # Determine database names: default both gob and gob-staging on same cluster
    db_names = ["gob", "gob-staging"]

    for db_name in db_names:
        try:
            db = client[db_name]
            coll = db.teams
            for name, (primary, secondary) in CORE_8_COLORS.items():
                result = coll.update_many(
                    {"name": name},
                    {"$set": {"primary_color": primary, "secondary_color": secondary}},
                )
                if result.modified_count or result.matched_count:
                    print(f"  [{db_name}] {name}: primary={primary} secondary={secondary} (matched={result.matched_count}, modified={result.modified_count})")
                else:
                    print(f"  [{db_name}] {name}: no document found (skipped)")
        except Exception as e:
            print(f"❌ [{db_name}] Error: {e}", file=sys.stderr)

    print("✅ Done. Core 8 team colors aligned in both databases.")


if __name__ == "__main__":
    main()
