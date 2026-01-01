# Franchise vs Tournament Mode: Data Persistence Comparison

**Date:** January 2025  
**Purpose:** Side-by-side comparison of persisted data in non-gameplay situations to identify inconsistencies and streamline structures

---

## Document-Level Fields

| Field | Franchise Mode | Tournament Mode | Notes |
|-------|---------------|-----------------|-------|
| `_id` | `ObjectId("franchise_id")` | `ObjectId("tournament_id")` | ✅ Same |
| `user_team_id` | ✅ `string` (team name) | ✅ `string` (team name) | ✅ Same |
| `user_team_object_id` | ✅ `string` (ObjectId) | ✅ `string` (ObjectId) | ✅ Same |
| `created_at` | ✅ `datetime` | ✅ `datetime` | ✅ Same |
| `week` / `current_round` | ✅ `week: number` (1-14) | ✅ `current_round: number` (1-3) | ✅ Same concept, different names |
| `schedule` | ✅ `[[team_A_id, team_B_id], ...]` (14 weeks) | ❌ Not stored (bracket only) | ⚠️ **DIFFERENT** - Tournament uses bracket structure |
| `bracket` | ❌ Not stored | ✅ `{round1: [...], round2: [...], final: [...]}` | ⚠️ **DIFFERENT** - Tournament-specific |
| `results` | ✅ `{week: [{away_id, home_id, scores}]}` | ❌ Not stored (in bracket) | ⚠️ **DIFFERENT** - Tournament stores in bracket |
| `training_status` | ✅ `{current_week, training_completed, session_type, last_training_date}` | ✅ `{round, training_completed, session_type, last_training_date}` | ✅ Same concept, mode-specific names |
| `latest_training` | ✅ `{player_logs, team_log, session_type, week}` | ✅ `{round, player_logs, team_log, session_type}` | ✅ Same concept, mode-specific week/round |
| `applied_games` | ✅ `["game_id_1", ...]` | ✅ `["game_id_1", ...]` | ✅ Same |
| `recruits` | ✅ `[{name, attributes, ...}]` | ❌ Not applicable | ✅ Tournament doesn't need recruits |
| `stats` / `leaderboards` | ✅ `{top_10_points, top_10_rebounds, ...}` | ✅ `{top_10_points, top_10_rebounds, ...}` | ✅ Same |
| `current_season` / `completed` | ✅ `current_season: number` | ✅ `completed: boolean` | ⚠️ **DIFFERENT** - Franchise is multi-season, tournament ends after final |

---

## Team Objects Structure

| Field | Franchise Mode | Tournament Mode | Notes |
|-------|---------------|-----------------|-------|
| **Storage Path** | `franchise_teams.{team_id}` | `teams.{team_id}` | ⚠️ **DIFFERENT** - Intentional naming difference |
| **Initialization** | ✅ All 8 teams upfront | ✅ All 8 teams upfront | ✅ Same |
| **Team Attributes** | | | |
| `team_chemistry` | ✅ 7-13 (franchise range) | ✅ 7-25 (tournament range) | ✅ Same concept, different ranges |
| `offensive_efficiency` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges |
| `shot_threshold` | ✅ -10 to 190 | ✅ -10 to 190 | ✅ Same (center at 90 for pill display) |
| `discipline` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges (formerly turnover_modifier) |
| `fight` | ✅ -3 to +3 | ✅ -10 to +10 | ✅ Same concept, different ranges (formerly foul_modifier) |
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
| `plays[].effectiveness` | ✅ 0-100 (franchise: from universal or 0) | ✅ 0-80 (tournament: randomized 0-80 on init) | ⚠️ **DIFFERENT** - Intentional init ranges |
| `plays[].momentum` | ✅ 0-10 (franchise: from universal or 0) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **DIFFERENT** - Intentional init values |
| `plays[].cloaking` | ✅ 0-10 (franchise: from universal or 0) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **DIFFERENT** - Intentional init values |
| **Scouting Data** | | | |
| `scouting_data` | ✅ `{defense: {Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT}}` | ✅ Same structure | ✅ Same |
| `scouting_data.defense[].effectiveness` | ✅ 0-100 (franchise: 0 on init) | ✅ 0-80 (tournament: randomized 0-80 on init) | ⚠️ **DIFFERENT** - Intentional init ranges |
| `scouting_data.defense[].momentum` | ✅ 0-10 (franchise: 0 on init) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **DIFFERENT** - Intentional init values |
| `scouting_data.defense[].cloaking` | ✅ 0-10 (franchise: 0 on init) | ✅ 0-10 (tournament: randomized 0-10 on init) | ⚠️ **DIFFERENT** - Intentional init values |
| **Playbook Settings** | | | |
| `playbook_settings` | ✅ `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns}` | ✅ Same structure | ✅ Same |
| **Legacy** | | | |
| `playcall_settings` | ✅ `{Base, Freelance, Inside, Attack, Outside, Set}` | ✅ Same structure | ✅ Same |
| **Training Reports** | | | |
| `training_reports` | ✅ `{week: {...}}` (per-week) | ✅ `{round: {...}}` (per-round) | ✅ Same concept, mode-specific period |

---

## Player Objects Structure

| Field | Franchise Mode | Tournament Mode | Notes |
|-------|---------------|-----------------|-------|
| **Storage Path** | `players.{player_id}` | `player_stats.{player_id}` | ⚠️ **INCONSISTENT** - Different key names |
| **Player Metadata** | | | |
| `meta` | ✅ `{first_name, last_name, team, team_id}` | ✅ `{first_name, last_name, team, team_id}` | ✅ Same |
| `first_name` | ✅ In `meta` | ✅ In `meta` | ✅ Same |
| `last_name` | ✅ In `meta` | ✅ In `meta` | ✅ Same |
| `team` | ✅ In `meta` | ✅ In `meta` | ✅ Same |
| `team_id` | ✅ In `meta` | ✅ In `meta` | ✅ Same |
| **Evolved Attributes** | | | |
| `attributes` | ✅ All 30+ attributes with `anchor_` prefixed versions | ✅ All 30+ attributes with `anchor_` prefixed versions | ✅ Same |
| **Position Ratings** | | | |
| `position_ratings` | ✅ `{PG, SG, SF, PF, C}` | ✅ `{PG, SG, SF, PF, C}` | ✅ Same |
| **Statistics** | | | |
| `season` | ✅ Season stats object | ✅ Season stats object | ✅ Same |
| `career` | ✅ Career stats object | ❌ Not applicable | ✅ Tournament doesn't need career stats |

---

## Summary of Differences (Remaining by design)

- Team objects storage key: `franchise_teams.{team_id}` vs `teams.{team_id}` (intentional naming difference)
- Schedule vs bracket: Franchise uses weekly schedule; Tournament uses bracket (different by design)
- Current season vs completed flag: Franchise tracks `current_season`; Tournament uses `completed` (mode-specific)
- Plays/scouting initialization ranges: Franchise uses universal/default values; Tournament randomizes on init (intentional variety)

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

