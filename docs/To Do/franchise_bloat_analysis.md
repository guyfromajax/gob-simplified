# Franchise Document Bloat — Analysis & Strategy

**Date:** 2026-01-28  
**Context:** Franchise docs are 350–550KB each. `franchise_teams` (~350KB) and `players` (~154KB) dominate. Queries take 1.5–3s. Goal: long-term fix via normalization + projections.

---

## 1. What’s Stored (Source of Truth: Codebase)

### 1.1 `players` (≈154KB, ~28% of doc)

- **Written:** `FranchiseManager.initialize_season()` — `db.players.find({})` (all players, all teams).
- **Structure per player:** `meta` (first_name, last_name, team, team_id), `season` (zero_stats), `career`, `attributes` (12+ attrs, often `anchor_` dupes), `position_ratings`.
- **Updated:** Training (`execute_training`), game stat finalization (`stat_updater`), roster usage.
- **Read by:** Roster loader, team-stats, team-traits, training (run + report), gameplay init, state endpoint. Many of these use projections `{"players": 1}` only.

### 1.2 `franchise_teams` (≈350KB, ~64% of doc)

**Per team (8 teams):**

| Field | Source | Notes |
|-------|--------|--------|
| 11 team attributes | `TeamManager.init_team_attributes("franchise")` | Small |
| `strategy_settings` | Defaults / user | Small |
| `playbook_settings` | `initialize_playbook_settings()` | Small |
| **`plays`** | **`populate_team_plays("franchise")`** | **Same template copied 8×.** One entry per universal play. Each has `game_stats`, `season_stats` (incl. `player_points` per player). Grows as games are played. |
| **`scouting_data`** | **`populate_scouting_data("franchise")`** | **Same template copied 8×.** Defense (Man, 2-3, 3-2, 1-3-1) + `game_stats` / `season_stats`. Grows with usage. |
| **`training_reports.{week}`** | **`run_franchise_training`** | **Per team, per week.** Each report stores full `plays_data` and `scouting_data` snapshots. Massive duplication over 14 weeks × 8 teams. |

**Written:** `FranchiseManager.initialize_season()` (init); `ensure_team_objects_exist` / gameplan routes (plays, scouting, settings); `run_franchise_training` (training reports + updated plays/scouting); `stat_updater` (play season_stats, defensive season_stats); `update_team_attributes_after_game`.

**Read by:** Team-data, playbooks, gameplan, standings, training, stat_updater, scouting-report, various game init paths. Several already use `{"franchise_teams": 1}` projections, but that still pulls the whole 350KB.

---

## 2. Root Causes of Bloat

1. **Plays and scouting duplicated 8×**  
   Same `populate_team_plays` / `populate_scouting_data` result stored per team. No sharing.

2. **Training reports store full plays + scouting**  
   `training_reports.{week}` and `latest_training` each hold full `plays_data` and `scouting_data`. So we keep 14+ full snapshots per team (and 8 teams).

3. **Plays/scouting grow over time**  
   `season_stats` (including `player_points` per player) and defensive `game_stats` / `season_stats` accumulate. Same structure, more data.

4. **Players = all teams in one blob**  
   One big `players` map for the whole franchise. Often we only need one team’s roster; we still fetch all.

5. **Full-doc reads**  
   Many `find_one` calls still pull the whole doc (or only drop `players`/`franchise_teams` via projection). No field-level or sub-doc-level narrowing.

---

## 3. How Each Field Is Used (Reads)

### 3.1 `players`

- **Roster:** By team (via `team_id` / `player_ids`). Need attributes, `position_ratings`, meta.
- **Team-stats / team-traits:** Aggregate over `players` + `franchise_teams` (e.g. team_ids).
- **Training:** User’s team only; merge franchise attrs + core `players` (year, height, etc.).
- **State:** Frontend fetches `players` (often with `{"players": 1}`).
- **Game init:** Roster loader uses `franchise.players` for trained attributes.

### 3.2 `franchise_teams`

- **Team-data:** One team’s attributes, plays, scouting. Often by `team_id`.
- **Playbooks / gameplan:** One team’s `plays`, `playbook_settings`, `strategy_settings`.
- **Standings:** Team list + results; modest subset of team data.
- **Training:** User’s team’s plays, scouting, settings. Computer teams: same structure, different team_ids.
- **Scouting-report:** One team’s `scouting_data` (+ last game).
- **Stat updater:** Maps game → franchise team_ids, then updates `franchise_teams.{id}.plays` and `scouting_data` (season_stats, etc.).
- **Training report:** Reads `training_reports.{week}` (and `latest_training`).

---

## 4. Strategic Options

### A. Projections only (quick win)

- Add strict projections to every franchise `find_one` so we only pull required fields (e.g. `players`, or `franchise_teams`, or `franchise_teams.{team_id}`-centric).
- **Pros:** Fast to implement, no migration, immediate latency improvement.  
- **Cons:** Doc size unchanged; we still store 8× plays/scouting and heavy training reports. Bloat and write amplification remain.

### B. Normalize big pieces (like games)

**Move to separate collections, keyed by `franchise_id` (+ `team_id` where relevant):**

1. **`franchise_team_data`**  
   One doc per `(franchise_id, team_id)`: attributes, `strategy_settings`, `playbook_settings`, **`plays`**, **`scouting_data`**.  
   - Stops 8× duplication of plays/scouting inside the franchise doc.  
   - Matches “one team’s stuff” access pattern (team-data, playbooks, gameplan, training, scouting-report).

2. **`franchise_training_reports`**  
   One doc per `(franchise_id, team_id, week)`: `player_logs`, `team_log`, `coaching_focus`, etc.  
   - Store **references or deltas only** (e.g. play effectiveness changes, defense changes), not full `plays_data` / `scouting_data`.  
   - Keeps “training report” behavior without duplicating full plays/scouting per week.

3. **`franchise_players`**  
   One doc per `(franchise_id, player_id)` OR embed small “franchise overlay” (attrs, `position_ratings`) and keep core bio in `players` collection.  
   - Allows “fetch only this team’s players” or “fetch only overlays for this team’s roster” instead of the whole franchise `players` blob.

**Pros:** Shrinks franchise doc dramatically; clearer model; scales better.  
**Cons:** Migration, more read paths, need to keep `franchise_id` / `team_id` resolution consistent.

### C. Hybrid (recommended)

1. **Short term:**  
   - Apply projections everywhere we read franchises (see §5).  
   - Add a shared “plays + scouting template” if we keep them in-doc (optional micro-optimization while we still store them there).

2. **Medium term:**  
   - Introduce `franchise_team_data` and migrate `plays` + `scouting_data` (and possibly attributes/settings) out of `franchise_teams`.  
   - Move training reports to `franchise_training_reports` and stop storing full `plays_data` / `scouting_data` in them.

3. **Later:**  
   - Consider `franchise_players` (or overlay docs) if we want to avoid ever loading the full franchise `players` blob.

---

## 5. Immediate Projection Fixes (No Schema Change)

All franchise `find_one` usages should use a projection. Below, “full doc” means no projection or projection that still pulls `players` + `franchise_teams` in full.

| Location | Current | Prefer |
|----------|---------|--------|
| `roster_loader` | `{"players": 1}` | Keep (already minimal). |
| `get_franchise_team_data` | `{"franchise_teams": 1, …}` | Restrict to `franchise_teams.{actual_team_id}` if we add dotted projection support, or keep `franchise_teams` but ensure we never pull `training_reports` when not needed. |
| `get_training_points` | Full doc | `{"week": 1, "results": 1, "_id": 1}` only. |
| `run_franchise_training` | Full doc | Load in stages: e.g. `{"franchise_teams": 1, "user_team_id": 1, "user_team_object_id": 1}`, then fetch only user’s team data (or `franchise_team_data` once normalized). |
| `stat_updater` | `{"franchise_teams": 1}` | Keep, but goal is to shrink `franchise_teams` via normalization. |
| `get_franchise_state` | `{"players": 1, "_id": 1}` | Keep. |
| `get_franchise_roster` | `{"players": 1, "_id": 1}` + batch `players` | Keep. |
| `team-stats` | `{"players": 1, "franchise_teams": 1, "results": 1}` | Keep for now; later replace with `franchise_team_data` + `franchise_players` (or overlay). |
| `team-traits` | `{"players": 1, "franchise_teams": 1}` | Same as above. |
| `scouting-report` | Full doc | `{"franchise_teams.{team_id}": 1, …}` or similar; avoid full `franchise_teams`. |
| Gameplan / playbooks | Often `{"franchise_teams": 1}` | Same; eventually `franchise_team_data` only. |
| Training report | Full doc in some paths | `{"franchise_teams.{team_id}.training_reports": 1, "latest_training": 1, …}` or use `franchise_training_reports` when migrated. |
| `update_team_attributes_after_game` | Full doc | `{"franchise_teams": 1}` (or `franchise_team_data` later). |
| `load_team_settings_from_doc` (api) | `{"franchise_teams": 1}` | Same. |
| EOS tournament / advance | Full doc | Minimize to required fields (e.g. `eos_tournament`, `week`, `schedule`, `results`). |

Audit all `db.franchises.find_one` / `franchises_collection.find_one` and ensure they use a projection that matches the actual fields used.

---

## 6. Data to Capture Before Refactors

- **Plays collection size:** `db.plays.countDocuments()` and optionally `db.plays.stats()`.  
- **Rough size of `populate_team_plays` vs `populate_scouting_data`** (e.g. via a small script that builds both and measures `len(bson.BSON.encode({...}))`).  
- **Per-team, per-week size of `training_reports`** (and of `plays_data` / `scouting_data` inside them).  
- **Confirm `franchise_teams` projection** in production still returns ~350KB ( Samblon sizes) to validate our assumptions.

---

## 7. Suggested Order of Work

1. **Projections audit**  
   - List every franchise `find_one`, add minimal projections, deploy, and measure latency with existing timing logs.

2. **Stop storing full plays/scouting in training reports**  
   - Change `training_report` to store only deltas / references (e.g. play and defense effectiveness changes).  
   - Reconstruct “full” view when needed from current `franchise_team_data` (or current `franchise_teams` before that’s migrated) plus report.

3. **Introduce `franchise_team_data`**  
   - Schema: `(franchise_id, team_id)` → attributes, settings, `plays`, `scouting_data`.  
   - Migrate from `franchise_teams`; update all read/write paths (team-data, playbooks, gameplan, training, scouting, stat updater).  
   - Optionally keep a slim `franchise_teams` (e.g. team list + refs) for standings and similar, or drop it and derive from `franchise_team_data`.

4. **Introduce `franchise_training_reports`**  
   - Migrate from `franchise_teams.{id}.training_reports.{week}` and `latest_training`.  
   - Use deltas only; avoid full plays/scouting in reports.

5. **Revisit `players`**  
   - If we still see large franchise `players` blobs and many “single team” reads, consider `franchise_players` or overlay docs.

---

## 8. Summary

| Lever | Impact | Effort |
|-------|--------|--------|
| Projections everywhere | High (latency), no size reduction | Low |
| No full plays/scouting in training reports | High (size + writes) | Medium |
| `franchise_team_data` collection | Very high (size + latency) | High |
| `franchise_training_reports` collection | High (size) | Medium |
| `franchise_players` (or overlay) | Medium (size + latency) | High |

Recommended path: **projections now** → **training report slim-down** → **`franchise_team_data`** → **`franchise_training_reports`** → **`franchise_players` if needed**.  
Use the existing `[DB TIMING]` logs and MongoDB metrics to validate each step.



**Jamie's Notes**
## Franchise Team Data (FTD) Collection ##
   - Assumption, FTD colleciton will be stand alone,a dn we'll still have team objects in franchise game docs that will have bespoke values and data contained to the game instance
   - Offense and Defense Plays Objects Process
      - At the start of the game, read each team's effectiveness, cloaking, and momentum scores for each play and save them to the team object in the franchise game document
      - During gameplay, these values will iterate, all iterations will be contained to the game instance
      - All Game Stats start at 0, these do no not need to be part of the Franchise Teams Doc
      - All Seasons stats are contained to the FTD, and will not be accessed during the game instance
      - At tend of the game, add Game Stats values to the Season Stats values for each play
      - At the end of the game, any changes to the Effectiveness, Cloaking, and Momentum values for the FTD will be calcuated in the team_attribute_changes() function
   - The same process above applies to the following Team Attributes:
      - shot threshold, rebound modifier, team chemistry, momentum score, offensive efficiency, defensive efficiency, discipline, fight, pt opp modifier, fb opp modifier, fb efficiency, pt efficiency
   - Game Plan and Playbooks settings will be applied from the FTD to the team objects in the Franchise game doc at teh start of the game. Any fluctuations during the game will be contained to that game and the values on the FTD at the start of the game will persist after the game completes. The only changes to these two items that are saved to the FTD are changes made from the FCC.
   - training data will be contained to the FTD
   - Let's discuss how scouting-report and stat updater should be managed.

---

## Clarifications & Open Questions

### ✅ **What's Clear:**
1. **FTD is standalone** - separate collection, game docs still have team objects for game-specific data
2. **Plays process** - effectiveness/cloaking/momentum copied at game start, game_stats accumulate in game doc, season_stats stay in FTD
3. **Team attributes** - same flow as plays (copy at start, changes in game doc, merge back at end)
4. **Settings** - strategy_settings and playbook_settings copied at start, only FCC changes persist to FTD

### ❓ **What Needs Clarification:**

#### 1. **Scouting Data Structure**
Your notes mention "Offense and Defense Plays Objects" but scouting_data has two parts:
- **`scouting_data.defense`** - Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone (each with effectiveness, momentum, cloaking, game_stats, season_stats)
- **`scouting_data.offense`** - Fast_Break_Entries, Playcalls (Motion/Set buckets), Cumulative stats

**Question:** Does the same process apply to `scouting_data.defense`? (Copy effectiveness/momentum/cloaking at game start, accumulate game_stats in game doc, merge to season_stats at end?)

**Question:** What about `scouting_data.offense`? Currently it tracks playcall usage (Motion vs Set, inside/attack/outside). Does this follow the same pattern, or is it only tracked during games (no season_stats)?

#### 2. **Game Start - What Gets Read from FTD?**
At `init-game` or `simulate-quarter`:
- **Plays:** effectiveness, cloaking, momentum (per play) ✅
- **Team attributes:** shot_threshold, rebound_modifier, etc. ✅
- **Settings:** strategy_settings, playbook_settings ✅
- **Scouting defense:** effectiveness, momentum, cloaking (per defense type)? ❓
- **Scouting offense:** Does this get copied, or initialized fresh? ❓

**Proposal:** Read only what's needed via projection:
```python
# Read FTD for both teams at game start
ftd_home = franchise_team_data.find_one(
    {"franchise_id": fid, "team_id": home_team_object_id},
    {"plays.effectiveness": 1, "plays.cloaking": 1, "plays.momentum": 1,
     "scouting_data.defense": 1,  # effectiveness/momentum/cloaking only?
     "team_attributes": 1, "strategy_settings": 1, "playbook_settings": 1}
)
```

#### 3. **End of Game - What Gets Written to FTD?**
Currently `stat_updater.finalize_game()` does:
- `_update_offensive_play_season_stats()` - increments `plays.{play_name}.season_stats` (times_run, successes, player_points)
- `_update_defensive_playcall_season_stats()` - increments `scouting_data.defense.{defense_name}.season_stats` (used, success, vs_* stats)
- `update_team_attributes_after_game()` - calculates changes to team attributes

**Proposal:** All three should update **FTD**, not franchise doc:
- `franchise_team_data.update_one({franchise_id, team_id}, {"$inc": {"plays.{play_name}.season_stats.times_run": ...}})`
- `franchise_team_data.update_one({franchise_id, team_id}, {"$inc": {"scouting_data.defense.{defense_name}.season_stats.used": ...}})`
- `franchise_team_data.update_one({franchise_id, team_id}, {"$set": {"team_attributes.shot_threshold": new_value}})`

**Question:** Should `team_attribute_changes()` calculate effectiveness/cloaking/momentum changes for plays AND defenses, or just plays?

#### 4. **Scouting Report Endpoint**
Currently `/franchise/scouting-report`:
- Gets `team_attributes` from `franchise_teams.{team_id}.attributes`
- Gets `plays` from **last game document** (extracts `game_stats` from game doc)

**Proposal:**
- `team_attributes` → Read from **FTD** ✅
- `plays` → Still read from **game document** (last completed game) ✅
  - This is correct - scouting report shows "last game's play usage" which is `game_stats`, not `season_stats`
  - Game doc already has the plays with `game_stats` populated

**No changes needed** - scouting-report already reads from the right places, just needs to read team_attributes from FTD instead of franchise doc.

#### 5. **Stat Updater - Current Behavior**
Looking at `_update_defensive_playcall_season_stats()`:
- Currently updates `teams_collection` (universal teams collection) ❌
- Should update `franchise_teams.{team_id}.scouting_data` (franchise doc) or **FTD** ✅

**Proposal:** Change `_update_defensive_playcall_season_stats()` to:
- For franchise mode: Update `franchise_team_data` collection
- For tournament mode: Update tournament document (current behavior)
- Remove the `teams_collection` update (that's wrong for franchise mode)

#### 6. **Training Reports**
You said "training data will be contained to the FTD" - does this mean:
- `training_reports.{week}` should be stored in **FTD** (not franchise doc)?
- Or `training_reports` stays in franchise doc but references FTD data?

**Proposal:** Store `training_reports` in **separate `franchise_training_reports` collection** (as discussed in analysis doc). This avoids bloating FTD with historical snapshots.

---

## Proposed FTD Schema

```javascript
{
  "_id": ObjectId("ftd_id"),
  "franchise_id": ObjectId("franchise_id"),
  "team_id": ObjectId("team_object_id"),  // ObjectId string
  
  // Team Attributes (updated by games + training)
  "team_attributes": {
    "shot_threshold": 90,
    "rebound_modifier": 1.0,
    "team_chemistry": 8,
    "momentum_score": 0,
    "offensive_efficiency": 0,
    "defensive_efficiency": 0,
    "discipline": 0,
    "fight": 0,
    "pt_opp_modifier": 0,
    "fb_opp_modifier": 0,
    "fb_efficiency": 0,
    "pt_efficiency": 0
  },
  
  // Settings (updated by FCC only)
  "strategy_settings": {...},
  "playbook_settings": {...},
  
  // Plays (effectiveness/cloaking/momentum + season_stats)
  "plays": {
    "Motion Inside": {
      "effectiveness": 45,  // Updated by team_attribute_changes()
      "cloaking": 5,        // Updated by team_attribute_changes()
      "momentum": 3,        // Updated by team_attribute_changes()
      "season_stats": {     // Updated by stat_updater
        "times_run": 120,
        "successes": 65,
        "player_points": {"player_id_1": 45, "player_id_2": 32},
        "effectiveness": 0.54
      }
      // NO game_stats - that's in game doc only
    }
  },
  
  // Scouting Data (defense effectiveness/momentum/cloaking + season_stats)
  "scouting_data": {
    "defense": {
      "Man": {
        "effectiveness": 50,  // Updated by team_attribute_changes()?
        "momentum": 4,        // Updated by team_attribute_changes()?
        "cloaking": 6,        // Updated by team_attribute_changes()?
        "season_stats": {     // Updated by stat_updater
          "used": 450,
          "success": 280,
          "vs_motion": {"attempts": 200, "success": 120},
          "vs_set": {"attempts": 250, "success": 160},
          // ... etc
        }
        // NO game_stats - that's in game doc only
      },
      "2-3 Zone": {...},
      "3-2 Zone": {...},
      "1-3-1 Zone": {...}
    },
    "offense": {
      // ❓ Does this get stored in FTD or only tracked during games?
      // Currently tracks: Fast_Break_Entries, Playcalls (Motion/Set buckets)
      // Proposal: Only track during games, no season_stats needed
    }
  },
  
  // Metadata
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

**Index:** `{franchise_id: 1, team_id: 1}` (unique compound index)

---

## Implementation Flow Summary

### **Game Start (`init-game` or `simulate-quarter`):**
1. Read FTD for home team (projection: plays effectiveness/cloaking/momentum, scouting_data.defense, team_attributes, settings)
2. Read FTD for away team (same projection)
3. Copy to game doc `teams.{team_id}`:
   - `plays.{play_name}.effectiveness/cloaking/momentum` (from FTD)
   - `plays.{play_name}.game_stats` = `{times_run: 0, successes: 0, player_points: {}}`
   - `scouting_data.defense.{defense_name}.effectiveness/momentum/cloaking` (from FTD)
   - `scouting_data.defense.{defense_name}.game_stats` = `{used: 0, success: 0, ...}`
   - `team_attributes` (from FTD)
   - `strategy_settings`, `playbook_settings` (from FTD)

### **During Gameplay:**
- All changes happen in game doc `teams.{team_id}`
- effectiveness/cloaking/momentum can change (via game logic)
- game_stats accumulate

### **End of Game (`finalize_game`):**
1. **Extract game_stats from game doc** (for both teams)
2. **Update FTD season_stats:**
   - `franchise_team_data.update_one({franchise_id, team_id}, {"$inc": {"plays.{play_name}.season_stats.times_run": game_stats.times_run}})`
   - Same for successes, player_points
   - Same for `scouting_data.defense.{defense_name}.season_stats`
3. **Calculate attribute changes:**
   - `team_attribute_changes()` calculates effectiveness/cloaking/momentum changes for plays (and defenses?)
   - `update_team_attributes_after_game()` calculates team attribute changes
4. **Update FTD:**
   - `franchise_team_data.update_one({franchise_id, team_id}, {"$set": {"plays.{play_name}.effectiveness": new_value, ...}})`
   - `franchise_team_data.update_one({franchise_id, team_id}, {"$set": {"team_attributes.shot_threshold": new_value, ...}})`

### **Scouting Report:**
- Read `team_attributes` from **FTD** ✅
- Read `plays` with `game_stats` from **last game document** ✅ (no change needed)

### **Stat Updater:**
- `_update_offensive_play_season_stats()` → Update **FTD** (not franchise doc)
- `_update_defensive_playcall_season_stats()` → Update **FTD** (not teams_collection)
- `update_team_attributes_after_game()` → Update **FTD** (not franchise doc)

---

## Answers & Final Recommendations

### ✅ **1. Scouting Defense** 
**Answer:** Yes, follows same pattern as plays (effectiveness/momentum/cloaking copied at start, can change during game, merged back at end via `team_attribute_changes()`).

### ✅ **2. Scouting Offense (Fast Breaks & Playcalls)**
**Answer:** Tracked during games (game_stats start at 0), then merged to season_stats in FTD. Same method as offense/defense playcall stats.

**Recommendation:** Store `scouting_data.offense` in FTD with `season_stats`:
```javascript
"scouting_data": {
  "offense": {
    "Fast_Break_Entries": { "game_stats": {...}, "season_stats": {...} },
    "Playcalls": {
      "Motion": { "game_stats": {...}, "season_stats": {...} },
      "Set": { "game_stats": {...}, "season_stats": {...} }
    }
  }
}
```

### ✅ **3. Training Reports**
**Answer:** User prefers FTD, asking if FCC schedule tab access is easier from FTD or franchise doc.

**Recommendation:** Store in **FTD** (not separate collection). Here's why:
- **FCC Schedule Tab** needs to show "has training been completed this week?" - that's `training_status` (franchise doc level) ✅
- **Training Report details** are accessed per-team, per-week - matches FTD access pattern ✅
- **Training reports are team-specific** - fits FTD model perfectly ✅
- **One query** to get FTD = get team data + training reports together ✅

**Structure in FTD:**
```javascript
"training_reports": {
  "1": { /* week 1 report */ },
  "2": { /* week 2 report */ },
  ...
}
"latest_training": { /* most recent report */ }
```

### ✅ **4. Game Start Projection**
**Answer:** User asking if we need full play structures, mentions zone definitions, shift triggers, skeletons for offense/HCT/FCP.

**Analysis:**
- **Zone definitions** (2-3, 3-2, 1-3-1) are **hardcoded constants** in `shared_defense.py` - NOT stored in scouting_data ✅
- **Shift triggers** are logic in code (ball position → zone shift) - NOT stored in scouting_data ✅
- **FCP/HCT skeletons** are fetched from **universal collections** (`fcp_skeletons_collection`, `hct_skeletons_collection`) during gameplay - NOT in team data ✅
- **Offensive play skeletons** are fetched from **universal `plays_collection`** via `play_id` reference - NOT stored in team's plays dict ✅

**What's Actually in Team Plays Dict:**
Looking at `populate_team_plays()`, team's `plays` dict contains:
- `play_id` (reference to universal play)
- `name`, `play_type`, `play_focus`
- `effectiveness`, `momentum`, `cloaking` (per-team values)
- `game_stats`, `season_stats` (stats only, no skeletons)

**Recommendation:** **Minimal projection is correct** - we only need:
- `plays.{play_name}.effectiveness/cloaking/momentum` (from FTD)
- `scouting_data.defense.{defense_name}.effectiveness/momentum/cloaking` (from FTD)
- `scouting_data.offense` structure (for game_stats initialization)
- `team_attributes` (from FTD)
- `strategy_settings`, `playbook_settings` (from FTD)

**We DON'T need:**
- Full play skeletons (fetched from universal `plays_collection` via `play_id`)
- Zone definitions (hardcoded constants)
- FCP/HCT skeletons (fetched from universal collections)
- `season_stats` (not accessed during gameplay)

**Game Start Projection:**
```python
# Read FTD for both teams
projection = {
    "plays.effectiveness": 1,
    "plays.cloaking": 1,
    "plays.momentum": 1,
    "plays.play_id": 1,  # Reference to fetch skeletons
    "plays.name": 1,
    "plays.play_type": 1,
    "plays.play_focus": 1,
    "scouting_data.defense.effectiveness": 1,
    "scouting_data.defense.momentum": 1,
    "scouting_data.defense.cloaking": 1,
    "scouting_data.offense": 1,  # Full structure for game_stats init
    "team_attributes": 1,
    "strategy_settings": 1,
    "playbook_settings": 1
}
```

**Note:** MongoDB projections don't support nested field selection like `"plays.effectiveness": 1` - you'd need to either:
- Project entire `plays` object (but exclude `season_stats` via aggregation)
- Or read full `plays` but it's much smaller without skeletons (just metadata + stats)

**Better approach:** Use aggregation to reshape:
```python
ftd_agg = franchise_team_data.aggregate([
    {"$match": {"franchise_id": fid, "team_id": team_object_id}},
    {"$project": {
        "plays": {
            "$arrayToObject": {
                "$map": {
                    "input": {"$objectToArray": "$plays"},
                    "as": "play",
                    "in": {
                        "k": "$$play.k",
                        "v": {
                            "play_id": "$$play.v.play_id",
                            "name": "$$play.v.name",
                            "play_type": "$$play.v.play_type",
                            "play_focus": "$$play.v.play_focus",
                            "effectiveness": "$$play.v.effectiveness",
                            "cloaking": "$$play.v.cloaking",
                            "momentum": "$$play.v.momentum",
                            "game_stats": {"times_run": 0, "successes": 0, "player_points": {}}
                        }
                    }
                }
            }
        },
        "scouting_data": 1,  # Full structure (defense + offense)
        "team_attributes": 1,
        "strategy_settings": 1,
        "playbook_settings": 1
    }}
])
```

**Simpler approach:** Just read the full FTD document - it's per-team, so much smaller than franchise doc. The projection optimization can come later if needed.

---

## Final FTD Schema (Complete)

```javascript
{
  "_id": ObjectId("ftd_id"),
  "franchise_id": ObjectId("franchise_id"),
  "team_id": ObjectId("team_object_id"),  // ObjectId string
  
  // Team Attributes (updated by games + training)
  "team_attributes": {
    "shot_threshold": 90,
    "rebound_modifier": 1.0,
    "team_chemistry": 8,
    "momentum_score": 0,
    "offensive_efficiency": 0,
    "defensive_efficiency": 0,
    "discipline": 0,
    "fight": 0,
    "pt_opp_modifier": 0,
    "fb_opp_modifier": 0,
    "fb_efficiency": 0,
    "pt_efficiency": 0
  },
  
  // Settings (updated by FCC only)
  "strategy_settings": {...},
  "playbook_settings": {...},
  
  // Plays (effectiveness/cloaking/momentum + season_stats, NO skeletons)
  "plays": {
    "Motion Inside": {
      "play_id": "uuid_ref_to_universal_play",  // Reference for skeleton lookup
      "name": "Motion Inside",
      "play_type": "motion",
      "play_focus": "inside",
      "effectiveness": 45,  // Updated by team_attribute_changes()
      "cloaking": 5,        // Updated by team_attribute_changes()
      "momentum": 3,        // Updated by team_attribute_changes()
      "season_stats": {     // Updated by stat_updater
        "times_run": 120,
        "successes": 65,
        "player_points": {"player_id_1": 45, "player_id_2": 32},
        "effectiveness": 0.54
      }
      // NO game_stats - that's in game doc only
      // NO skeletons - fetched from universal plays_collection via play_id
    }
  },
  
  // Scouting Data (defense + offense effectiveness/momentum/cloaking + season_stats)
  "scouting_data": {
    "defense": {
      "Man": {
        "effectiveness": 50,  // Updated by team_attribute_changes()
        "momentum": 4,         // Updated by team_attribute_changes()
        "cloaking": 6,         // Updated by team_attribute_changes()
        "season_stats": {     // Updated by stat_updater
          "used": 450,
          "success": 280,
          "vs_motion": {"attempts": 200, "success": 120},
          "vs_set": {"attempts": 250, "success": 160},
          // ... etc (all vs_* stats)
        }
        // NO game_stats - that's in game doc only
        // NO zone definitions - those are hardcoded constants
      },
      "2-3 Zone": {...},
      "3-2 Zone": {...},
      "1-3-1 Zone": {...}
    },
    "offense": {
      "Fast_Break_Entries": {
        "game_stats": {...},  // Initialized at game start, tracked during game
        "season_stats": {...} // Updated by stat_updater at end of game
      },
      "Playcalls": {
        "Motion": {
          "game_stats": {...},
          "season_stats": {...}
        },
        "Set": {
          "game_stats": {...},
          "season_stats": {...}
        }
      }
    }
  },
  
  // Training Reports (per week)
  "training_reports": {
    "1": {
      "week": 1,
      "player_logs": {...},
      "team_log": {...},
      "coaching_focus": {...},
      "training_notes": [...],
      "plays_effectiveness_changes": {...},  // Deltas only, not full plays_data
      "defenses_effectiveness_changes": {...}, // Deltas only, not full scouting_data
      "session_type": "preseason",
      "date": "2026-01-28"
    },
    "2": {...}
  },
  "latest_training": { /* most recent report */ },
  
  // Metadata
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

**Index:** `{franchise_id: 1, team_id: 1}` (unique compound index)

---

## Implementation Status (2026-01)

**FTD implementation complete.** All read/write paths use `franchise_team_data` for franchise mode. Franchise doc keeps `franchise_teams: {}` (empty) for backward compatibility. Index `franchise_team_unique` on `(franchise_id, team_id)` is ensured on new-franchise creation and via `scripts/setup_franchise_indexes.py` / `scripts/migrate_to_ftd.py`.

---

## Implementation Checklist

### Phase 1: Create FTD Collection & Migration Script
- [x] Create `franchise_team_data` collection (`BackEnd/db.py`)
- [x] Write migration script (`scripts/migrate_to_ftd.py`) to extract `franchise_teams.{team_id}` → FTD
- [x] Migrate existing franchises when needed (run script; staging was cleared, so optional)
- [x] Verify migration (spot check)

### Phase 2: Update Game Start Flow
- [x] Modify `init-game` / `simulate-quarter` to read from FTD (`BackEnd/api/api.py`, `load_ftd_data_for_team`, `load_team_attributes_from_doc`)
- [x] Copy effectiveness/cloaking/momentum + team_attributes + settings to game doc
- [x] Initialize `game_stats` = 0 for plays and scouting_data

### Phase 3: Update Stat Updater
- [x] `_update_offensive_play_season_stats()` → FTD (`BackEnd/utils/stat_updater.py`)
- [x] `_update_defensive_playcall_season_stats()` → FTD
- [x] `update_team_attributes_after_game()` → FTD (`BackEnd/api/franchise_routes.py`)

### Phase 4: Update All Read Paths
- [x] `/franchise/team-data` → FTD
- [x] `/api/playbooks` → FTD (franchise mode; game doc when in-game)
- [x] `/api/gameplan` → FTD (franchise mode; game doc when in-game)
- [x] `/franchise/scouting-report` → team_attributes from FTD (plays from game doc)
- [x] Training routes → FTD (`/franchise/run-training`, `/franchise/training-report`)
- [x] Standings / team-stats / team-traits still use franchise doc (team list, results, players); no FTD change needed

### Phase 5: Update Write Paths
- [x] Game Plan save → FTD (`save_team_settings` in `team_settings_manager.py`)
- [x] Playbooks save → FTD (same)
- [x] Training execution → FTD (user + computer teams)
- [x] Team attributes after game → FTD
- [x] `ensure_team_objects_exist` (franchise) → creates/updates FTD

### Phase 6: Cleanup & Verify
- [x] Ensure FTD index on `(franchise_id, team_id)` via `ensure_ftd_index()` in `db.py`; called from `FranchiseManager.initialize_season` and `setup_franchise_indexes.py`
- [x] Keep `franchise_teams: {}` in franchise doc for backward compatibility
- [x] Update `franchise_bloat_analysis.md` (this doc)
- [ ] Monitor performance (latency, doc sizes) after deploy

---

## Key Code Changes Summary

### Game Start (`init-game` or `simulate-quarter`):
```python
# OLD: Read from franchise doc
franchise_doc = franchises_collection.find_one({"_id": fid})
team_obj = franchise_doc["franchise_teams"][team_id]

# NEW: Read from FTD
ftd_home = franchise_team_data.find_one({"franchise_id": fid, "team_id": home_team_object_id})
ftd_away = franchise_team_data.find_one({"franchise_id": fid, "team_id": away_team_object_id})

# Copy to game doc (same as before, just source changed)
game_doc["teams"][home_team_id] = {
    "plays": {name: {
        "effectiveness": ftd_home["plays"][name]["effectiveness"],
        "cloaking": ftd_home["plays"][name]["cloaking"],
        "momentum": ftd_home["plays"][name]["momentum"],
        "game_stats": {"times_run": 0, "successes": 0, "player_points": {}}
    } for name in ftd_home["plays"]},
    # ... same for scouting_data, team_attributes, settings
}
```

### End of Game (`stat_updater.finalize_game`):
```python
# OLD: Update franchise doc
franchises_collection.update_one(
    {"_id": fid},
    {"$inc": {f"franchise_teams.{team_id}.plays.{play_name}.season_stats.times_run": game_stats.times_run}}
)

# NEW: Update FTD
franchise_team_data.update_one(
    {"franchise_id": fid, "team_id": team_object_id},
    {"$inc": {f"plays.{play_name}.season_stats.times_run": game_stats.times_run}}
)
```

### Scouting Report:
```python
# OLD: Read from franchise doc
franchise_doc = franchises_collection.find_one({"_id": fid})
team_attributes = franchise_doc["franchise_teams"][team_id]["attributes"]

# NEW: Read from FTD
ftd = franchise_team_data.find_one({"franchise_id": fid, "team_id": team_object_id})
team_attributes = ftd["team_attributes"]
# Plays still read from last game document (no change)
```

---

## Expected Performance Impact

**Before:**
- Franchise doc: 550 KB
- Query time: 1.5-3 seconds
- Every query pulls all 8 teams' data

**After:**
- Franchise doc: ~50-100 KB (just metadata, schedule, results, players)
- FTD per team: ~40-50 KB (one team's data)
- Query time: 10-50ms per FTD read
- Only fetch the team(s) you need

**Total reduction:** ~90% smaller documents, ~95% faster queries 🚀