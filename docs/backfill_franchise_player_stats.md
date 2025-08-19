# Backfill Franchise Player Stats

Use the helper script to migrate existing franchise documents to the new
`player_stats` schema. The script copies legacy `players` data, computes per-game
averages and shooting percentages, and stores processed game ids.

```bash
python scripts/backfill_franchise_player_stats.py
```

The command processes every franchise in the database. To migrate a single
franchise, provide its identifier:

```bash
python scripts/backfill_franchise_player_stats.py --franchise-id <FRANCHISE_ID>
```

Ensure the `MONGO_URI` environment variable points at your database before
running the backfill.
