"""Create wildcard indexes for the franchises collection.

This script ensures efficient queries on player metadata and aggregated
statistics within franchise documents. It can be run as part of a database
migration or one-time setup step after deploying the application.
"""

from BackEnd.db import franchises_collection

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
