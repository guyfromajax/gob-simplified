# FPD & FRD Implementation Plan

Franchise Players Data (FPD) and Franchise Recruits Data (FRD) move `players` and `recruits` off the franchise document into standalone collections. Player UUID remains the connector; recruit UUID is assigned per franchise at creation. No backfill for existing franchises.

---

## 1. Collection Schemas

### 1.1 `franchise_players_data` (FPD)

- **One document per (franchise, player).**
- **Keys:** `franchise_id` (string, franchise `_id`), `player_id` (string, player UUID).
- **Fields** (mirror current `franchise.players[uuid]`):
  - `meta`: `{ first_name, last_name, team, team_id }`
  - `season`: stats dict (PTS, REB, etc., same keys as today)
  - `career`: stats dict
  - `attributes`: franchise-specific attributes (SH, EM, CH, etc.)
  - `position_ratings`: franchise-specific position ratings
- **Index:** Compound unique `(franchise_id, player_id)` for lookups and “all players for franchise” queries.

### 1.2 `franchise_recruits_data` (FRD)

- **One document per (franchise, recruit).**
- **Keys:** `franchise_id` (string), `recruit_id` (string, UUID generated at creation).
- **Fields** (mirror current recruit object in `franchise.recruits[i]`):
  - `name`, `attributes`, `position_ratings`, `height`, `weight`, `archetype`, `year`, `created_at`
- **Index:** Compound unique `(franchise_id, recruit_id)`.

**Connector:** Player UUID unchanged everywhere (FTD.players, games, box scores). Recruit UUID is new: generated when creating recruits for a franchise; used only within that franchise.

---

## 2. DB Setup

- **File:** `BackEnd/db.py`
- Add:
  - `franchise_players_data_collection = db["franchise_players_data"]`
  - `franchise_recruits_data_collection = db["franchise_recruits_data"]`
- Add `ensure_fpd_index()` and `ensure_frd_index()` (mirror `ensure_ftd_index()`): compound unique on `(franchise_id, player_id)` and `(franchise_id, recruit_id)`.
- Call both in franchise init (and optionally on app startup).

---

## 3. Franchise Init (`BackEnd/models/franchise_manager.py`)

**Current behavior:** Builds `players_map` (keyed by player UUID), writes `extra_state["players"] = players_map` and `extra_state["recruits"] = recruits` to the franchise doc; then creates FTD docs.

**New behavior:**

1. **Players:** After building `players_map`, do **not** set `extra_state["players"]`. Instead, for each `(pid, data)` in `players_map`, insert (or upsert) one FPD doc:
   - `franchise_id`: `self.franchise_id` (string)
   - `player_id`: `pid`
   - `meta`, `season`, `career`, `attributes`, `position_ratings`: from `data`
2. **Recruits:** When generating recruits (e.g. `recruit_manager.generate_recruits_list()`), assign a new UUID per recruit (e.g. `uuid.uuid4().hex` or standard UUID string). Do **not** set `extra_state["recruits"]`. Instead, for each recruit, insert one FRD doc:
   - `franchise_id`: `self.franchise_id`
   - `recruit_id`: new UUID for that recruit
   - Remaining fields: same as current recruit object (`name`, `attributes`, etc.)
3. **Franchise doc:** Omit `players` and `recruits` (or set to empty `{}` / `[]` so any legacy code doesn’t assume presence). Keep `applied_games`, `training_status`, etc. as today.
4. **FTD:** No change. FTD.`players` remains the list of 12 player UUIDs per team; init already sets that from `team.get("player_ids", [])`.

---

## 4. Read Paths (franchise.players → FPD, franchise.recruits → FRD)

### 4.1 Roster loader (`BackEnd/utils/roster_loader.py`)

- **Current:** `franchise_doc = franchises_collection.find_one(..., {"players": 1})`, then for each `team_player_id` in FTD/team, `franchise_players.get(pid_str)` and merge with universal player.
- **New:** Do **not** request `players` from franchise. For franchise mode, after resolving `team_player_ids` (from FTD or team), for each `pid_str` load FPD doc: `franchise_players_data_collection.find_one({"franchise_id": franchise_id, "player_id": pid_str})`. Merge that doc’s `attributes` (and any other needed fields) with universal player as today. If no FPD doc, treat as missing (log and skip or fallback as you do now).

### 4.2 Franchise routes – team-stats (`BackEnd/api/franchise_routes.py`)

- **Current:** `franchise_doc = db.franchises.find_one(..., {"players": 1, "results": 1})`, `players = franchise_doc.get("players", {})`, then aggregate via FTD.players roster.
- **New:** Load franchise with projection that excludes `players` (e.g. `results`, `_id`). Build `franchise_team_rosters` from FTD as today. For each player_id in those rosters, load FPD doc by `(franchise_id, player_id)` and read `season` (and `career` if needed) for aggregation. If FPD is used, no need to pass `franchise_doc["players"]` into the aggregator; pass a list of FPD docs or a dict keyed by player_id built from FPD.

### 4.3 Franchise routes – team-traits

- **Current:** `franchise_doc = db.franchises.find_one(..., {"players": 1})`, iterate `players`, use attributes.
- **New:** Get team list and FTD rosters as today. For each player_id in roster, load FPD by `(franchise_id, player_id)` and use `attributes` (and `position_ratings` if needed).

### 4.4 Franchise routes – get_team_player_stats (and any similar “player list + stats” endpoint)

- **Current:** Loads franchise `players`, uses FTD.players to resolve roster, then reads from `franchise_players.get(pid_str)`.
- **New:** Resolve roster from FTD. For each player_id, load FPD doc; use FPD for attributes and stats.

### 4.5 Franchise routes – roster endpoint (by team name/ID)

- **Current:** `franchise_doc = db.franchises.find_one(..., {"players": 1})`, `franchise_players = franchise_doc.get("players", {})`, then for each team player ID get `franchise_players.get(pid_str)` and merge with universal.
- **New:** Same as roster_loader: get team player IDs (from FTD or team), then for each `pid_str` load FPD by `(franchise_id, pid_str)` and merge with universal player.

### 4.6 Franchise routes – state (`/franchise/state` or command-center data)

- **Current:** Sometimes loads `{"players": 1}` and returns count or full players for frontend.
- **New:** If frontend only needs count, query FPD: `franchise_players_data_collection.count_documents({"franchise_id": fid})`. If frontend needs full player list/structure, query FPD by `franchise_id` and build the same shape in memory (or change frontend to accept list from API). Do not load `players` from franchise doc.

### 4.7 Franchise routes – recruits (`GET /franchise/recruits`)

- **Current:** `franchise = db.franchises.find_one(..., {"recruits": 1})`, `recs = franchise.get("recruits", [])`.
- **New:** `recs = list(franchise_recruits_data_collection.find({"franchise_id": franchise_id}))`. Optionally strip `franchise_id` from each doc for response. Return same array shape (include `recruit_id` so frontend can reference recruits by UUID).

### 4.8 Training and training report

- **Current:** Load `franchise_doc.get("players", {})`, iterate by FTD roster or all players, update `franchise_update["players.{pid}.attributes.*"]` etc., then `franchises.update_one(...)`.
- **New:** Load players for training from FPD (by franchise_id and, for roster, filter by FTD.players or meta.team_id). Compute attribute/position updates as today. Instead of one big `franchises.update_one` with `$set` on `players.<pid>.*`, run `franchise_players_data_collection.update_one({"franchise_id": fid, "player_id": pid}, {"$set": { "attributes.*": ..., "position_ratings": ... }})` per player (or batch if you add a bulk API). Training report: load FPD docs for the relevant player IDs and build the same response shape.

### 4.9 Training report – “player not in franchise.players”

- **Current:** Looks up `franchise_players.get(pid_str)`.
- **New:** Look up FPD by `(franchise_id, pid_str)`. If not found, same “player not found” handling.

### 4.10 Any other readers of `franchise.players` or `franchise.recruits`

- Grep for `franchise_doc.get("players")`, `franchise.get("recruits")`, `franchise_players`, and similar. Replace with FPD/FRD queries by `franchise_id` (and `player_id` / `recruit_id` where needed).

---

## 5. Write Paths (franchise.players / franchise.recruits → FPD / FRD)

### 5.1 Stat updater – finalize_game (franchise mode)

- **Current:** Builds `inc_doc` with keys `players.{pid}.season.{stat}`, `players.{pid}.career.{stat}`, `set_doc` with `players.{pid}.meta.team_id`, and `set_on_insert_doc` with full `players.{pid}` for new players. Single `db.franchises.update_one({"_id": fid, "applied_games": {"$ne": game_id}}, { "$addToSet": { "applied_games": game_id }, "$inc": inc_doc, "$set": set_doc, "$setOnInsert": set_on_insert_doc })`.
- **New:**
  1. **Franchise doc:** Only update `applied_games`: `db.franchises.update_one({"_id": fid, "applied_games": {"$ne": game_id}}, { "$addToSet": { "applied_games": game_id } })`.
  2. **Per player:** For each `pid_str` in the box_score player set:
     - **If FPD doc exists:** `franchise_players_data_collection.update_one( { "franchise_id": str(fid), "player_id": pid_str }, { "$inc": { "season.<stat>": val, "career.<stat>": val for each stat }, "$set": { "meta.team_id": team_object_id } } )`.
     - **If FPD doc does not exist:** Insert one FPD doc (same structure as current “set_on_insert” player: meta, season, career, attributes, position_ratings from players_collection + game context), then apply the same $inc/$set.
  - Build per-player updates from current `inc_doc` / `set_doc` / `set_on_insert_doc` logic; execute against FPD instead of franchise doc.

### 5.2 Training – attribute / position_ratings updates

- **Current:** `franchise_update["players.{pid}.attributes.*"]`, `franchise_update["players.{pid}.position_ratings"]`, then `franchises.update_one(...)` or FTD update.
- **New:** For each trained player, `franchise_players_data_collection.update_one( {"franchise_id": franchise_id, "player_id": pid}, { "$set": { "attributes": ... , "position_ratings": ... } } )`. FTD training_reports and other FTD-only fields stay as today.

### 5.3 Recruits – create/update

- **Current:** `generate_recruits_list()` returns list of recruit objects; franchise init or `generate_recruits()` does `$set: { "recruits": recruits }` on franchise.
- **New:** No franchise.recruits write. When generating recruits, assign `recruit_id` (UUID) to each, insert FRD docs. Any “replace all recruits” flow should delete FRD docs for that franchise and re-insert (or upsert by recruit_id if you ever update in place).

### 5.4 Recruit signing (if applicable)

- If signing a recruit adds them as a player: create FPD doc for the new player (new player_id = new UUID or existing recruit_id as decided by product) and update FTD.players for the signing team. Remove or update FRD doc for that recruit as needed. Detail in implementation when that flow exists.

---

## 6. Franchise Doc After Migration

- **No** `players` or `recruits` on new franchise docs (or explicitly set to `{}` / `[]` for safety).
- **Keep:** `applied_games`, `training_status`, `schedule`, `week`, `results`, `eos_tournament`, `eos_tournament_active`, `user_team_id`, `user_team_object_id`, `stats`, `created_at`, `current_season`, etc.
- **FTD:** Unchanged; `FTD.players` remains list of 12 player UUIDs per team.

---

## 7. Key Files Summary

| Area | File | Change |
|------|------|--------|
| DB | `BackEnd/db.py` | Add FPD/FRD collections and index helpers |
| Init | `BackEnd/models/franchise_manager.py` | Write players to FPD, recruits to FRD (with recruit_id UUID); stop writing players/recruits to franchise |
| Roster | `BackEnd/utils/roster_loader.py` | Load player data from FPD by (franchise_id, player_id) instead of franchise.players |
| Stats | `BackEnd/utils/stat_updater.py` | Franchise finalize_game: update applied_games on franchise; apply stat/meta updates per player to FPD (insert if missing) |
| Routes | `BackEnd/api/franchise_routes.py` | team-stats, team-traits, get_team_player_stats, roster, state, recruits, training, training report: read/write FPD and FRD instead of franchise.players/recruits |

---

## 8. Order of Implementation

1. **DB:** Add collections and indexes; ensure_fpd_index / ensure_frd_index.
2. **Init:** Create FPD and FRD docs in franchise_manager; stop populating franchise.players and franchise.recruits for new franchises.
3. **Reads:** Roster loader → FPD. Then franchise_routes: recruits → FRD; state, team-stats, team-traits, get_team_player_stats, roster → FPD.
4. **Writes:** Stat updater franchise finalize_game → FPD (and franchise only for applied_games). Training → FPD updates.
5. **Recruits:** Ensure generate_recruits_list (or caller) assigns recruit_id; all recruit reads/writes go through FRD.
6. **Smoke test:** New franchise, play games, run training, open roster/recruits/team-stats; confirm no reads of franchise.players/recruits and correct FPD/FRD content.

---

## 9. References

- FTD design: `docs/To Do/franchise_bloat_analysis.md`, `docs/docs_1_systems/03_Data_Persistence/Data_Persistence_System.md`
- Current franchise init: `BackEnd/models/franchise_manager.py` (`initialize_season`, `RecruitManager.generate_recruits_list`)
- Current stat application: `BackEnd/utils/stat_updater.py` (franchise branch of `finalize_game`)
- Current roster load: `BackEnd/utils/roster_loader.py` (franchise path)
- Week 14→15 / EOS: `docs/To Do/week_14_to_15_postseason_transition_fix.md` (FTD team list; no change to FPD/FRD)
