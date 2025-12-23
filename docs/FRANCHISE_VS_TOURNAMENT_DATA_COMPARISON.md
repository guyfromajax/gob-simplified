# Franchise vs Tournament Mode: Data Persistence Comparison

**Date:** January 2025  
**Purpose:** Side-by-side comparison of persisted data in non-gameplay situations to identify inconsistencies and streamline structures

---

## Document-Level Fields

| Field | Franchise Mode | Tournament Mode | Notes |
|-------|---------------|-----------------|-------|
| `_id` | `ObjectId("franchise_id")` | `ObjectId("tournament_id")` | ✅ Same |
| `user_team_id` | ❌ Not stored | ✅ `string` (team name) | ⚠️ **INCONSISTENT** - Franchise uses state collection |
| `user_team_object_id` | ❌ Not stored | ✅ `string` (ObjectId) | ⚠️ **INCONSISTENT** - Should add to Franchise |
| `created_at` | ❌ Not stored | ✅ `datetime` | ⚠️ **INCONSISTENT** - Should add to Franchise |
| `week` / `current_round` | ✅ `week: number` (1-14) | ✅ `current_round: number` (1-3) | ✅ Same concept, different names |
| `schedule` | ✅ `[[team_A_id, team_B_id], ...]` (14 weeks) | ❌ Not stored (bracket only) | ⚠️ **DIFFERENT** - Tournament uses bracket structure |
| `bracket` | ❌ Not stored | ✅ `{round1: [...], round2: [...], final: [...]}` | ⚠️ **DIFFERENT** - Tournament-specific |
| `results` | ✅ `{week: [{away_id, home_id, scores}]}` | ❌ Not stored (in bracket) | ⚠️ **DIFFERENT** - Tournament stores in bracket |
| `training_status` | ✅ `{current_week, training_completed, session_type}` | ✅ `{training_completed, round, last_training_date}` | ⚠️ **INCONSISTENT** - Different field names |
| `latest_training` | ✅ `{player_logs, team_log, session_type, week}` | ✅ `{round, player_changes, team_changes, ...}` | ⚠️ **INCONSISTENT** - Different field names |
| `applied_games` | ✅ `["game_id_1", ...]` | ✅ `["game_id_1", ...]` | ✅ Same |
| `recruits` | ✅ `[{name, attributes, ...}]` | ❌ Not applicable | ✅ Tournament doesn't need recruits |
| `stats` / `leaderboards` | ❌ Not stored | ✅ `{top_10_points, top_10_rebounds, ...}` | ⚠️ **INCONSISTENT** - Should add to Franchise |
| `completed` | ❌ Not stored | ✅ `boolean` | ⚠️ **INCONSISTENT** - Should add to Franchise |

---

## Team Objects Structure

| Field | Franchise Mode | Tournament Mode | Notes |
|-------|---------------|-----------------|-------|
| **Storage Path** | `franchise_teams.{team_id}` | `teams.{team_id}` | ⚠️ **INCONSISTENT** - Different key names |
| **Initialization** | ✅ All 8 teams upfront | ❌ Lazy (only user team) | ⚠️ **INCONSISTENT** - Should align |
| **Team Attributes** | | | |
| `team_chemistry` | ✅ 7-13 (franchise range) | ✅ 7-25 (tournament range) | ✅ Same concept, different ranges |
| `offensive_efficiency` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `shot_threshold` | ✅ -100 to +100 | ✅ -100 to +100 | ✅ Same |
| `turnover_modifier` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `foul_modifier` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `rebound_modifier` | ✅ 0.8-1.2 | ✅ 0.8-1.2 | ✅ Same |
| `defensive_efficiency` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `fb_efficiency` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `pt_efficiency` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `fb_opp_modifier` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `pt_opp_modifier` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| **Strategy Settings** | | | |
| `strategy_settings` | ✅ `{offense, inside, attack, outside, tempo, defense, aggression, hc_trap, fc_press, rebounding}` | ✅ Same structure | ✅ Same |
| **Plays Data** | | | |
| `plays` | ✅ `{[playName]: {play_id, name, play_type, play_focus, effectiveness, momentum, cloaking, game_stats, season_stats}}` | ✅ Same structure | ✅ Same |
| `plays[].effectiveness` | ✅ 0-100 (franchise: from universal or 0) | ✅ 0-80 (tournament: randomized 0-80 on init) | ⚠️ **INCONSISTENT** - Different init ranges |
| `plays[].momentum` | ✅ 0-10 (franchise: from universal or 0) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **INCONSISTENT** - Different init values |
| `plays[].cloaking` | ✅ 0-10 (franchise: from universal or 0) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **INCONSISTENT** - Different init values |
| **Scouting Data** | | | |
| `scouting_data` | ✅ `{defense: {Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT}}` | ✅ Same structure | ✅ Same |
| `scouting_data.defense[].effectiveness` | ✅ 0-100 (franchise: 0 on init) | ✅ 0-80 (tournament: randomized 0-80 on init) | ⚠️ **INCONSISTENT** - Different init ranges |
| `scouting_data.defense[].momentum` | ✅ 0-10 (franchise: 0 on init) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **INCONSISTENT** - Different init values |
| `scouting_data.defense[].cloaking` | ✅ 0-10 (franchise: 0 on init) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **INCONSISTENT** - Different init values |
| **Playbook Settings** | | | |
| `playbook_settings` | ✅ `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns}` | ✅ Same structure | ✅ Same |
| **Legacy** | | | |
| `playcall_settings` | ✅ `{Base, Freelance, Inside, Attack, Outside, Set}` | ✅ Same structure | ✅ Same |
| **Training Reports** | | | |
| `training_reports` | ❌ Not stored per-team | ✅ `{round: {...}}` (per-round) | ⚠️ **INCONSISTENT** - Should add to Franchise |

---

## Player Objects Structure

| Field | Franchise Mode | Tournament Mode | Notes |
|-------|---------------|-----------------|-------|
| **Storage Path** | `players.{player_id}` | `player_stats.{player_id}` | ⚠️ **INCONSISTENT** - Different key names |
| **Player Metadata** | | | |
| `meta` | ✅ `{first_name, last_name, team, team_id}` | ❌ Not stored (fields at root level) | ⚠️ **INCONSISTENT** - Should align structure |
| `first_name` | ✅ In `meta` | ✅ At root level | ⚠️ **INCONSISTENT** |
| `last_name` | ✅ In `meta` | ✅ At root level | ⚠️ **INCONSISTENT** |
| `team` | ✅ In `meta` | ✅ At root level | ⚠️ **INCONSISTENT** |
| `team_id` | ✅ In `meta` | ❌ Not stored | ⚠️ **INCONSISTENT** |
| **Evolved Attributes** | | | |
| `attributes` | ✅ All 30+ attributes with `anchor_` prefixed versions | ✅ All 30+ attributes with `anchor_` prefixed versions | ✅ Same |
| **Position Ratings** | | | |
| `position_ratings` | ✅ `{PG, SG, SF, PF, C}` | ❌ Not stored | ⚠️ **INCONSISTENT** - Should add to Tournament |
| **Statistics** | | | |
| `season` | ✅ Season stats object | ✅ Season stats object | ✅ Same |
| `career` | ✅ Career stats object | ❌ Not applicable | ✅ Tournament doesn't need career stats |

---

## Summary of Inconsistencies

### 🔴 Critical Inconsistencies (Should Align)

1. **Team Objects Storage Key:**
   - Franchise: `franchise_teams.{team_id}`
   - Tournament: `teams.{team_id}`
   - **Recommendation:** Keep different (franchise has `franchise_teams` for clarity, tournament can use `teams`)

2. **Team Objects Initialization:**
   - Franchise: All 8 teams upfront
   - Tournament: Lazy (only user team)
   - **Status:** ✅ **ALIGNED** - Tournament mode now initializes all teams upfront (Phase 1.1)

3. **Player Objects Storage Key:**
   - Franchise: `players.{player_id}`
   - Tournament: `player_stats.{player_id}`
   - **Recommendation:** Keep different (tournament uses `player_stats` to emphasize stats focus)

4. **Player Metadata Structure:**
   - Franchise: `meta: {first_name, last_name, team, team_id}`
   - Tournament: `{first_name, last_name, team}` at root level
   - **Status:** ✅ **ALIGNED** - Tournament mode now uses `meta` wrapper (Phase 1.4)

5. **Position Ratings:**
   - Franchise: ✅ Stored
   - Tournament: ❌ Not stored
   - **Status:** ✅ **ALIGNED** - Tournament mode now stores `position_ratings` (Phase 1.3)

### 🟡 Minor Inconsistencies (Nice to Align)

6. **Document-Level Fields:**
   - `user_team_object_id`: Tournament has it, Franchise doesn't
   - `created_at`: Tournament has it, Franchise doesn't
   - `stats`/`leaderboards`: Tournament has it, Franchise doesn't
   - `completed`: Tournament has it, Franchise doesn't
   - **Status:** ✅ **ALIGNED** - Franchise mode now has `user_team_object_id`, `created_at`, `stats`/`leaderboards`, and `current_season` (Phase 1.2, 2.1)

7. **Training Status Field Names:**
   - Franchise: `{current_week, training_completed, session_type}`
   - Tournament: `{training_completed, round, last_training_date}`
   - **Status:** ✅ **ALIGNED** - Both modes now have `session_type` and `last_training_date` (Phase 2.2)

8. **Latest Training Field Names:**
   - Franchise: `{player_logs, team_log, session_type, week}`
   - Tournament: `{player_changes, team_changes, round, ...}`
   - **Status:** ✅ **ALIGNED** - Tournament mode now uses `player_logs` and `team_log` (Phase 2.3)

9. **Training Reports Storage:**
   - Franchise: Not stored per-team (only in `latest_training`)
   - Tournament: Stored in `teams.{team_id}.training_reports.{round}`
   - **Status:** ✅ **ALIGNED** - Franchise mode already stores per-week training reports (verified in Phase 2.4)

10. **Plays/Scouting Initialization:**
    - Franchise: Uses values from universal collection or defaults to 0
    - Tournament: Randomizes values on init (0-80 for effectiveness, 0-10 for momentum/cloaking)
    - **Recommendation:** Keep different (tournament randomization is intentional for variety)

---

## Recommended Alignment Strategy

### ✅ **Must Align (Critical):**

1. **Initialize all teams upfront in Tournament mode** (match Franchise pattern)
2. **Add `position_ratings` to Tournament player objects** (needed for training)
3. **Use `meta` wrapper for player metadata in Tournament** (consistency)

### ✅ **Should Align (Important):**

4. **Add missing document-level fields to Franchise:**
   - `user_team_object_id`
   - `created_at`
   - `stats`/`leaderboards`
   - `completed`

5. **Standardize training status field names:**
   - Use `current_week`/`current_round` consistently
   - Use `session_type` in both
   - Use `last_training_date` in both

6. **Standardize latest training field names:**
   - Use `player_logs` (not `player_changes`)
   - Use `team_log` (not `team_changes`)
   - Use `week`/`round` consistently

7. **Add per-week training reports to Franchise:**
   - Store in `franchise_teams.{team_id}.training_reports.{week}`

### ⚠️ **Keep Different (Intentional):**

- Team objects storage key (`franchise_teams` vs `teams`) - Different for clarity
- Player objects storage key (`players` vs `player_stats`) - Different for clarity
- Plays/scouting initialization ranges (tournament randomization is intentional)
- Team attribute ranges (different by design for mode balance)
- Schedule structure (bracket vs weekly schedule) - Different by design
- Career stats (franchise-only, tournament doesn't need)
- Recruits (franchise-only, tournament doesn't need)

---

## Implementation Priority

1. **Phase 1 (Critical):** Initialize all teams upfront in Tournament mode
2. **Phase 2 (Important):** Align player metadata structure and add position_ratings
3. **Phase 3 (Nice to Have):** Standardize document-level fields and training field names

