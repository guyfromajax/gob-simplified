# Week 14 → Week 15 / Postseason Transition Fix

## Problem

After playing through the regular season in franchise mode, completing week 14 did not progress to week 15 or set up the postseason tournament. The FCC stayed on week 14 with no playoff bracket.

## Root Cause

The End-of-Season (EOS) tournament initialization path assumed team list lived in **`franchise_doc.franchise_teams`**. After the FTD (Franchise Team Data) migration:

- The franchise document keeps **`franchise_teams = {}`** for backward compatibility.
- The authoritative team list for a franchise lives in the **`franchise_team_data`** collection (one doc per team, keyed by `franchise_id` + `team_id`).

So when `complete_week` ran with `req.week == 14`:

1. It called `initialize_eos_tournament(franchise_doc, db.teams)`.
2. `calculate_standings(franchise_doc, teams_collection)` read `franchise_teams` → **empty** → `team_ids = []`.
3. Standings and seeds were empty; `generate_bracket(seeds, …)` then did `sorted_teams[0][0]` etc. on an empty list → **IndexError**.
4. The exception prevented `db.franchises.update_one(...)` from running, so the franchise was never updated to week 15 and no EOS tournament was saved.

## Fix (Implemented)

### 1. Backend: EOS tournament uses FTD team list when `franchise_teams` is empty

- **`BackEnd/tournament/eos_tournament.py`**
  - **`calculate_standings(..., team_ids=None)`**  
    If `team_ids` is provided (e.g. from FTD), use it; otherwise fall back to `franchise_doc.franchise_teams.keys()`.
  - **`initialize_eos_tournament(..., team_ids=None)`**  
    Accepts optional `team_ids` and passes it through to `calculate_standings`.
  - **`generate_bracket(...)`**  
    Added a defensive check: if `len(seeds) < 8`, raise `ValueError` with a clear message instead of indexing an empty list.

- **`BackEnd/api/franchise_routes.py`** (in `complete_week`, when `req.week == 14`)
  - Query **`franchise_team_data_collection`** for this franchise:  
    `find({"franchise_id": franchise_id}, {"team_id": 1})` (use ObjectId for `franchise_id`).
  - Build `eos_team_ids` from the `team_id` field of each FTD doc.
  - Set **`franchise_doc["results"] = existing_results`** so EOS sees results **including week 14** (standings/seeding use full regular season).
  - Call **`initialize_eos_tournament(franchise_doc, db.teams, team_ids=eos_team_ids)`**.

Standings (and thus seeds) are computed from **`franchise.results`** (W/L, PF, PA via `calculate_franchise_standings`). The **list of team IDs** comes from FTD. EOS init must receive results through week 14; the caller assigns `existing_results` to `franchise_doc["results"]` before the call.

### 2. Behavior after fix

- Completing week 14 triggers `complete_week` as before.
- Team IDs for the franchise are loaded from FTD and passed into EOS init.
- `franchise_doc["results"]` is set to `existing_results` (weeks 1–14) so EOS seeds from full regular-season results.
- Standings are calculated from `franchise.results` (W/L, PF, PA via `calculate_franchise_standings`), seeds 1–8 are generated, and the bracket is built.
- Franchise doc is updated with `week: 15`, `eos_tournament`, and `eos_tournament_active: true`.
- User returns to FCC in week 15 with the postseason bracket available.

### 3. Edge cases

- If FTD returns fewer than 8 teams, a warning is logged and we still call `initialize_eos_tournament`. If seeds then have fewer than 8 teams, `generate_bracket` raises `ValueError` and the update is not applied (no partial/broken tournament saved).
- Existing franchises that still had `franchise_teams` populated would continue to work via the fallback in `calculate_standings` when `team_ids` is not passed (e.g. if any other caller omits it). For `complete_week` we always pass `team_ids` from FTD for week 14.

### 4. Weeks 15 → 16 → 17 transition

- **`complete_week`** allows weeks 15–17 when `eos_tournament_active` and `eos_tournament` exist. “Week games” come from the **bracket** (current round), not the schedule. Same flow as regular season: user’s game first, then **sim the other matchups** in that round, save each to the bracket via `save_tournament_game_result`, then advance. When the round advances, set `franchise.week = 14 + new_round`; otherwise keep `week` unchanged.
- **`/franchise/sim-rest-of-tournament`** sims incomplete matchups, saves to bracket, advances. When the round advances, it also sets `franchise.week = 14 + new_round` in the same `$set` as `eos_tournament`.

### 5. User eliminated (EOS)

When the user **loses** an EOS game, set `training_status.training_disabled_for_eos = true`. Training is disabled for all remaining EOS weeks; `run-training` returns 400 when that flag is set and `week >= 15`. The FCC shows **“Sim Rest Of Tournament”** when there are rounds remaining (same pattern as Tournament mode), or **“Finish Current Season”** when the tournament is complete. `command-center/data` returns `user_eliminated`, `offer_sim_rest`, and `training_disabled_for_eos`.

## Files Touched

| File | Change |
|------|--------|
| `BackEnd/tournament/eos_tournament.py` | `calculate_standings(..., team_ids=None)`; `initialize_eos_tournament(..., team_ids=None)`; `generate_bracket` guard for `len(seeds) < 8` |
| `BackEnd/api/franchise_routes.py` | Week 14: FTD team IDs, `franchise_doc["results"] = existing_results`, EOS init. Weeks 15–17: allow when EOS active, week_games from bracket; sim other matchups, save result → advance (no reload), set `week` on advance; on user loss set `training_disabled_for_eos`; `sim-rest-of-tournament` sets `week` when advancing. `command-center/data`: `user_eliminated`, `offer_sim_rest`, `training_disabled_for_eos`. `run-training`: 400 when `training_disabled_for_eos` and week ≥ 15. |

## Verification

1. Start a new franchise (or use one at week 13).
2. Complete week 14 (play/sim last game, then complete week so computer games run).
3. Confirm FCC shows week 15 and postseason bracket (e.g. Schedule tab or dedicated EOS view).
4. Confirm no 500s in Railway logs and no `IndexError` / `ValueError` for EOS during that flow.

## References

- EOS design: `docs/docs_1_systems/01_Game_Mode_Systems/Franchise_Mode_Systems.md` (EOS Tournament section).
- FTD migration: `docs/To Do/franchise_bloat_analysis.md` and franchise_team_data collection usage across `BackEnd/api/franchise_routes.py`, `BackEnd/models/franchise_manager.py`.
