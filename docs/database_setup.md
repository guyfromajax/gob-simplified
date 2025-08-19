# Database Setup

Use the helper script to create database indexes for franchise documents.

```bash
python scripts/setup_franchise_indexes.py
```

This script adds wildcard indexes for:

- `players.<pid>.meta.team_id`
- `players.<pid>.season.totals.*`
- `players.<pid>.career.totals.*`

Running the script once during migrations or environment setup ensures
queries targeting player metadata or aggregated statistics are
optimized.
