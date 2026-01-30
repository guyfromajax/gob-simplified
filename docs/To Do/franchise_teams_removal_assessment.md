# Assessment: Removing `franchise_teams` from Franchise Documents

**Status:** Code removal complete. Application code no longer reads or writes `franchise_teams`; FTD is the source of truth. Optional: one-off DB `$unset` to remove the field from existing franchise docs.

**Goal:** Remove the `franchise_teams` field from franchise docs and all code references, now that FTD (franchise_team_data) is the source of truth.

**Scope:** Backend, tests, and docs. Frontend does not reference `franchise_teams`.

---

## 1. Current Usage Summary

| Category | What uses it | Writes? | Reads? |
|----------|--------------|---------|--------|
| **DB** | Franchise doc field | Yes (see below) | Yes, many places |
| **FTD** | Team data (attributes, plays, scouting, playbooks) | FTD only | FTD only |
| **EOS** | Standings team list | No | Legacy fallback only |
| **Team-stats / Team-traits** | Team list for aggregation | No | No (use FTD) |
| **Stat updater** | Team name→ObjectId maps for play/defense/finalize | No | Yes |
| **Gameplan** | Paths, team_obj, persist playbook/plays | Yes | Yes |
| **Turn manager** | In-game playbook fallback from doc | No | Yes |
| **Team settings manager** | `extract_team_settings` (franchise `saved_doc`) | No | Yes |
| **Franchise manager** | New franchise init | Yes (`franchise_teams: {}`) | No |
| **Migration script** | One-time migrate to FTD | No | Yes |
| **Standings util** | `calculate_franchise_standings` | No | Caller passes dict; EOS builds from FTD |

---

## 2. Writes to `franchise_teams` (Must Stop)

**User-initiated Game Plan / Playbooks save:** Uses `save_team_settings()`. In franchise mode we **never** write to `franchise_teams`:
- **Pre-game (FCC):** Save goes to **FTD** (`franchise_team_data_collection`).
- **In-game:** Save goes to **game** doc `teams.{team_id}.*`.

So **game plan settings are not saved to `franchise_teams`**; they are saved to FTD or game doc.

**Actual writes to `franchise_teams` on the franchise document:**

1. **`franchise_manager`**  
   - **Where:** `BackEnd/models/franchise_manager.py`  
   - **What:** New franchises get `"franchise_teams": {}` on create.  
   - **Change:** Stop adding `franchise_teams` to new franchise docs.

2. **`gameplan_routes` (get_playbooks internal persist)**  
   - **Where:** `BackEnd/api/gameplan_routes.py`  
   - **What:** When we persist position_filters or populate plays, we use either (a) **FTD** for “franchise + not load_from_game_doc”, or (b) the **else** branch, which uses `team_key = franchise_teams.{id}` and `collection.update_one`. In that else branch we update the **game** doc (when we loaded from game) or **tournament** doc (when tournament). We do **not** update the franchise doc there—for franchise master we use FTD. So we do **not** write to the franchise document’s `franchise_teams` in this flow.  
   - **Note:** For franchise + load_from_game_doc we update the **game** doc; using `franchise_teams` as the key there would be wrong (game uses `teams`). That’s a separate bug.  
   - **Change:** For franchise, ensure we never use `franchise_teams`-style paths; use FTD or game `teams` as appropriate. Clean up any dead or buggy branches.

**No other code** writes to `franchise_teams` on the franchise document (training, update_team_attributes, stat updater, etc. all use FTD or other collections).

---

## 3. Reads from `franchise_teams` (Must Replace or Remove)

### 3.1 **Stat updater** (`BackEnd/utils/stat_updater.py`) — ✅ DONE

- **What:** Builds `team_name → ObjectId` and `team_id → ObjectId` maps for franchise mode. Used in:
  - `_update_offensive_play_season_stats` (play stats → FTD)
  - `_update_defensive_play_season_stats` (defense stats → FTD)
  - `finalize_game` (player season/career stats, `meta.team_id` on franchise doc)
- **Change implemented:** Added `_build_franchise_team_maps_from_ftd(franchise_id)` that queries `franchise_team_data` by `franchise_id`, gets `team_id` (ObjectId) per FTD doc, resolves `name` and `team_id` (canonical) from `teams` collection, and returns `(team_name_to_id, team_id_to_object_id)`. Replaced all franchise_teams-based map building in the three call sites with this helper. Removed `franchise_teams` reads from stat_updater.

### 3.2 **Gameplan routes** (`BackEnd/api/gameplan_routes.py`)

- **Projections:** `{"franchise_teams": 1}` when loading franchise doc (e.g. around 811, 1220, 1577).  
  **Change:** Drop `franchise_teams` from projections; never load it.

- **Path helper:** `get_team_settings_path("franchise", ...)` returns `franchise_teams.{team_id}`.  
  **Change:** For franchise, we no longer update franchise doc; this path is only relevant for persist targets. When persisting to franchise **master**, use FTD only. Remove or refactor `get_team_settings_path` so it is not used for franchise→franchise doc updates.

- **Loading team_obj from franchise doc:** Several spots use `doc.get("franchise_teams", {}).get(actual_team_id, {})` or equivalent (e.g. 1859, 1897–1898, 1969–1970), including when “reloading” after persist.  
  **Change:** For franchise mode, always obtain `team_obj` from **FTD** (or game doc `teams` when loading from game). Remove any reload-from-franchise-doc logic that uses `franchise_teams`.

- **Ensure team objects:** `ensure_team_objects_exist` already uses FTD for franchise. It still loads franchise doc with `franchise_teams` projection and uses it in some branches.  
  **Change:** Stop loading or using `franchise_teams` there; use FTD only.

### 3.3 **Turn manager** (`BackEnd/models/turn_manager.py`)

- **What:** Fallback load of `playbook_settings` from `doc.get("franchise_teams", {}).get(resolved_team_id, {})` when `mode == "franchise"` (offense and defense).  
- **Impact:** Today, with `franchise_teams` empty post-FTD, this fallback already returns nothing. Removing the field doesn’t change behavior, but the fallback is dead.  
- **Change:** Switch this fallback to load from **FTD** by `(franchise_id, team_id)` if we want a DB fallback when `GameManager` doesn’t have settings. Otherwise, remove the franchise_teams-based fallback and document that FTD (or game doc) is the source.

### 3.4 **Team settings manager** (`BackEnd/utils/team_settings_manager.py`)

- **What:** `extract_team_settings` uses `saved_doc.get("franchise_teams", {})` when `mode == "franchise"`.  
- **Callers:** `extract_team_settings` is called with `saved_doc` = game doc (mode `"single"`), tournament doc, or franchise doc. For **franchise master** load, `load_team_settings_from_doc` in `api.py` already uses **FTD** only and does not call `extract_team_settings` with the franchise doc. The franchise-doc + `extract_team_settings` path exists when loading from **game** doc (e.g. gameplan flow) and then extracting from franchise doc.  
- **Change:** Whenever we would pass the franchise doc into `extract_team_settings` for franchise mode, stop doing that. Use FTD (or game doc `teams`) instead. Remove franchise-specific `franchise_teams` handling from `extract_team_settings`.

### 3.5 **Franchise routes** (`BackEnd/api/franchise_routes.py`)

- **Team-stats / team-traits:** Use `_ftd_team_list_for_franchise` and FTD. They do **not** read `franchise_teams`. No change.

- **Training player_ids fallback:** If `team_doc` (from FTD) has no `player_ids`, we fall back to `franchise_teams.get(team_id, {}).get("player_ids", [])`.  
  **Change:** Remove this fallback. Ensure `player_ids` (or equivalent) always come from FTD / franchise_players / team doc. If we never persist `player_ids` to `franchise_teams` anymore, the fallback is obsolete.

- **EOS:** `complete_week` uses FTD for team list. Legacy `calculate_standings` fallback uses `franchise_doc["franchise_teams"]` when `team_ids` is not provided.  
  **Change:** Ensure all callers always pass `team_ids` from FTD. Remove the legacy fallback that reads `franchise_teams` from the franchise doc.

### 3.6 **EOS tournament** (`BackEnd/tournament/eos_tournament.py`)

- **What:** Legacy path: `franchise_teams = franchise_doc.get("franchise_teams", {})`, then `team_ids = [ObjectId(tid) for tid in franchise_teams.keys()]` when `team_ids` is not provided.  
- **Change:** Same as above: always pass `team_ids` from FTD; remove the legacy `franchise_teams` fallback.

### 3.7 **Franchise standings** (`BackEnd/utils/franchise_standings.py`)

- **What:** `calculate_franchise_standings(franchise_results, franchise_teams)` takes a `franchise_teams` dict; it only iterates `franchise_teams.keys()` to initialize standings.  
- **Change:** No change to the function signature. Callers already pass a dict built from FTD (e.g. `{str(tid): {} for tid in team_ids}`). Ensure no caller builds this from `franchise_doc["franchise_teams"]` anymore.

### 3.8 **Team stats aggregator** (`BackEnd/utils/team_stats_aggregator.py`)

- **What:** Receives `team_ids` from callers. Franchise callers use `_ftd_team_list_for_franchise`. No direct read of `franchise_teams`.  
- **Change:** None. Docstring reference to `franchise_teams` can be updated to say “FTD” or “team list from FTD.”

### 3.9 **Team ID resolver** (`BackEnd/utils/team_id_resolver.py`)

- **What:** Comment only: “franchise.franchise_teams[ObjectId]”.  
- **Change:** Update or remove the comment.

---

## 4. Tests

- **`tests/test_phase5_6_comprehensive_settings.py`**
  - Creates franchise with `franchise_teams: {}`, asserts `"franchise_teams" in franchise_doc` after save, and tests `get_team_settings_path("franchise", "MORRISTOWN") == "franchise_teams.MORRISTOWN"`.
- **Change:**  
  - Stop asserting on `franchise_teams` in franchise doc.  
  - For franchise, assert that settings are stored in **FTD** (and optionally still in game doc `teams` when saving to game).  
  - Adjust or remove `get_team_settings_path` tests for franchise if that helper no longer returns a franchise-doc path.

---

## 5. Migration Script (`scripts/migrate_to_ftd.py`)

- **What:** Reads `franchise_teams` from franchise docs and migrates to FTD.  
- **Change:** Keep the script for **legacy** franchises that still have `franchise_teams` and have not been migrated. Once we remove the field, the script only applies to pre-migration franchises. Add a brief note that `franchise_teams` is deprecated and will be removed from new code.

---

## 6. Documentation

- **Change:** Update all docs that mention `franchise_teams` (data model, training, gameplan, standings, FTD, etc.) to state that team data lives in **FTD** (and game `teams` where relevant). Remove or qualify references to “`franchise_teams`” as legacy/deprecated.

---

## 7. DB Migration (Optional)

- **Option A:** Only change code. Leave existing `franchise_teams` data in DB (either unused or for migrate script only). No DB migration.
- **Option B:** Run a one-off update to `$unset` `franchise_teams` from all franchise documents (after FTD migration is complete and we’ve validated no code reads it). Reduces doc size and avoids confusion.

---

## 8. Summary: What Breaks If We Remove It Without Code Changes

| Area | Breaks? | Notes |
|------|--------|--------|
| **New franchise creation** | No | We’d just stop adding the field. |
| **Stat updater** | **No** | ✅ Now uses FTD via `_build_franchise_team_maps_from_ftd`. |
| **Gameplan persist** | **No** | User-initiated saves already go to FTD (pre-game) or game doc (in-game). Internal get_playbooks persist uses FTD for franchise master. |
| **Gameplan load** | **Yes** | Any path that reloads `team_obj` from `franchise_teams` would get nothing; we’d need FTD. |
| **Turn manager fallback** | No | Already effectively dead (empty `franchise_teams`). |
| **Team-stats / team-traits** | No | Use FTD only. |
| **EOS** | Only legacy | Only if something skipped passing `team_ids` and used fallback. |
| **Training** | **Maybe** | Only if we relied on `player_ids` from `franchise_teams` fallback; FTD/team_doc should cover it. |
| **Extract team settings** | **Maybe** | Only for call paths that pass franchise doc for franchise mode; those should use FTD. |
| **Tests** | **Yes** | Assertions on `franchise_teams` and `get_team_settings_path` for franchise would fail. |

---

## 9. Effort Estimate

| Task | Effort | Risk |
|------|--------|------|
| Stop writing `franchise_teams` (franchise_manager only; game plan already uses FTD) | Small | Low |
| ~~Stat updater: build maps from FTD~~ | ~~Medium~~ | ✅ **Done** |
| Gameplan: drop franchise_teams load/reload paths; use FTD only | Medium | Medium – many branches, load vs save, game vs master |
| Turn manager: FTD fallback or remove | Small | Low |
| Team settings manager: remove franchise_teams extract path | Small | Low |
| Franchise routes: remove fallbacks (training, EOS) | Small | Low |
| EOS: remove legacy franchise_teams fallback | Small | Low |
| Tests + docs | Small | Low |
| **Total** | **Medium** | **Medium** |

**Conclusion:** Removing `franchise_teams` is **doable** with a focused refactor. The main work is switching **stat updater** and **gameplan** from `franchise_teams` to FTD (and game `teams` where relevant), and cleaning up fallbacks and tests. Careful testing of franchise game flow (play stats, defense stats, finalize, gameplan load/save) is recommended.
