"""Create indexes for franchises and franchise_team_data collections.

- Franchises: wildcard indexes for player metadata and aggregated stats.
- FTD: unique compound (franchise_id, team_id) for franchise_team_data.

Run as part of DB migration or one-time setup after deploying.
"""

from BackEnd.db import franchises_collection, ensure_ftd_index

# Franchise collection indexes
INDEX_SPECS = [
    ("players.$**.meta.team_id", 1),
    ("players.$**.season.totals.$**", 1),
    ("players.$**.career.totals.$**", 1),
]

for field, order in INDEX_SPECS:
    try:
        name = franchises_collection.create_index([(field, order)])
        print(f"✅ Created index '{name}' for '{field}'")
    except Exception as exc:
        print(f"⚠️ Failed to create index for '{field}': {exc}")

# FTD unique compound index
try:
    ensure_ftd_index()
    print("✅ FTD index (franchise_team_unique) ensured")
except Exception as exc:
    print(f"⚠️ FTD index: {exc}")
