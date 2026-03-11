# Franchise Expansion & DB Bloat Analysis

**Goal:** Add 8 more teams and 96 more players and sim more games per week without proportionally increasing DB load. Track findings and reduction options here.

---

## Current snapshot (gob DB)

| Collection | Documents | Storage | Avg doc size | Index size |
|------------|-----------|---------|--------------|------------|
| players | 96 | 110.59 kB | 2.35 kB | 45.06 kB |
| teams | 8 | 53.25 kB | 4.23 kB | 36.86 kB |
| games | 60 | 13.26 MB | 101.89 kB | 86.02 kB |
| franchise_players_data (FPD) | 1.8K | 962.56 kB | 1.70 kB | 245.76 kB |
| franchise_team_data (FTD) | 152 | 778.24 kB | 23.60 kB | 73.73 kB |
| franchises | 19 | 151.55 kB | 20.67 kB | 73.73 kB |
| plays | 23 | 221.18 kB | 32.59 kB | 36.86 kB |

---

## Doubling universal players & teams

**Q:** If we add 96 more players and 8 more teams, do we double those collections?

**A:** Yes. Document count doubles. Total storage scales with count × avg doc size (assuming new docs are similar). So roughly:
- **players:** 192 docs, ~221 kB storage (+ ~110 kB)
- **teams:** 16 docs, ~106 kB storage (+ ~53 kB)

Universal collections are small relative to **games** (13 MB for 60 games). The main growth from expansion will be more **games**, more **FPD** (per franchise × per player), and more **FTD** (per franchise × per team).

---

## Franchise collections: per-instance averages (19 active franchises)

**Assumption:** All game docs treated as franchise games (~95% of usage).

| Collection | Total storage | Per franchise (avg) | Docs per franchise (avg) |
|------------|---------------|---------------------|---------------------------|
| games | 13.26 MB | ~698 kB | ~3.2 |
| FPD | 962.56 kB | ~50.7 kB | ~95 |
| FTD | 778.24 kB | ~41.0 kB | 8 |

**Expansion assumption (8 more teams, 96 more players; 19 franchises unchanged):**
- **games:** Assume doubling → 120 docs, ~26.5 MB total, ~1.4 MB per franchise (avg).
- **FPD / FTD:** Roughly double (more teams → more FTD; more players/rosters → more FPD). **FRD will not expand for now.**

---

## Cascade delete when user starts new franchise / tournament

**Franchise:** When the user deletes their current franchise (e.g. "New Franchise" confirm), the code **does** delete linked games.

- **Where:** `BackEnd/api/franchise_routes.py` (and `admin_routes.py` for admin user delete).
- **Order:** FTD, FPD, FRD, **games** (`db.games.delete_many({"franchise_id": str(fid)})`), then franchise doc.

**Tournament:** When the user deletes their current tournament ("New Tournament"), the code **now** deletes linked games (fixed).

- **Where:** `BackEnd/api/tournament_routes.py` — `delete_current_tournament` finds user's tournament ids, runs `games_collection.delete_many({"tournament_id": {"$in": tournament_ids}})`, then deletes tournaments. Same cascade in `BackEnd/api/admin_routes.py` for admin reset-user-state.

---

## Bloat reduction (to fill in)

- Game docs: CPU sims already omit play-by-play (`turns` = [], no `text_log`). Possible trims: slimmer `teams`/`players` payload for sim-only games.
- FPD / FTD: Pending example docs to identify redundant or oversized fields.
- Next: Add sample game, FPD, FTD docs and note specific bloat candidates.
