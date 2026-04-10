

##Objective##
Change the format and structure of the plays docs for play type "set_play" in the db to enable more dynamic coaching decisions and play choices by the user.

**Changes To Make**
Instead of using defined positions in teh db objects like "PG", "SG", "SF", "PF", and "C" with using these five variables:
"shooter", "pos1", "pos2", "pos3", "pos4"

"shooter" position will be equal to the "target_shooter" field value in that play doc. Note in the future, users will have the ability to change the "target shooter" via teh game's UI.

pos 1, 2, 3, and 4 will be assigned values via the following process
-use the standard order as follows: PG, SG, SF, PF, C
-remove the target_shooter value -- i.e. if SF is target shooter, you're left with PG, SG, PF, C
-assign pos1, pos2,, pos3, and pos4 in the exact order of the remaining list.
    - in this example: pos1 = PG, pos2 = SG, pos3 = PF, pos4 = C

**Next Steps**
1. Write and run a script to update the positions in the plays documents in the skeletons for the gob-staging databases from PG, SG, SF, PF, C to shooter, pos1, pos2, pos3, pos4. 
2. Rework the game engine to assing position values to teh skeletons for each playcall animation during HCO turns
**Note, this will not apply to HCT and FCP skeletons, only HCO skeletons.

## Play Name Change Migration Plan
Goal: allow play names to change in the database without breaking playbooks, team data, game data, training, scouting, or stat persistence.

### Target Model
- `play_id` becomes the stable identifier for all persisted references.
- `name` becomes display-only data.
- Team/game/franchise copies may still store `name` as denormalized convenience data, but code should never rely on it as the join key.

### Step-by-Step Plan
1. Inventory all current name-keyed usage.
- Identify every persisted structure that uses play names as dictionary keys, lookup keys, or stat paths.
- Confirm coverage across:
  - universal plays
  - franchise_team_data play objects
  - tournament team play objects
  - single-game team play objects
  - playbook_settings
  - slot assignments
  - scouting/play usage data
  - season/game play stats

2. Define the new persistence contract.
- Standardize team play objects to include:
  - `play_id`
  - `name`
  - `play_type`
  - `play_focus`
  - `target_shooter`
  - existing effectiveness / momentum / cloaking / stats fields
- Decide which persisted maps remain keyed by position/slot and which become keyed by `play_id`.

3. Update backend read paths to prefer `play_id`.
- Everywhere code currently looks up or joins by play name, switch to `play_id` first.
- Keep temporary fallback support for legacy name-keyed data during migration.
- Do this before running destructive data migrations so both old and new data shapes are readable.

4. Update frontend payload contracts to carry `play_id` as the primary reference.
- Ensure playbooks, Playcall Center, Play Details, Training Report, FCC Team tab, and Scouting Report all receive/display `name` but identify the play by `play_id`.
- Preserve `name` in payloads for display only.

5. Migrate playbook settings away from play-name keys.
- Convert:
  - `motion`
  - `set_play_inside`
  - `set_play_attack`
  - `set_play_outside`
- from `{play_name: percentage}` to `{play_id: percentage}` or equivalent ID-based structure.
- Migrate `slot_assignments` so `playId` remains the source of truth and `playName` is optional display-only cached text.

6. Migrate team play maps away from play-name dictionary keys.
- Replace name-keyed `plays` dictionaries with an ID-safe structure.
- Recommended options:
  - dictionary keyed by `play_id`
  - or array of play objects plus helper indexes built at runtime
- Update all backend code that reads `team.plays[current_playcall]` or loops `for play_name, play_data in plays.items()`.

7. Migrate historical and season stat persistence.
- Replace stat update paths that currently write to `plays.{play_name}...` with ID-based paths.
- Ensure franchise/tournament season rollups and scouting summaries aggregate by `play_id`.
- Preserve current stats by migrating old name-keyed season/game play stat entries into the new ID-based structure.

8. Remove hardcoded play-name assumptions from initialization logic.
- Replace hardcoded name lists in playbook default seeding and position-filter initialization with either:
  - `play_id` lists
  - or metadata-driven selection rules
- Update static/fallback UI content that still hardcodes specific play names.

9. Write migration scripts.
- Create scripts to migrate, in staging first:
  - universal references
  - FTD docs
  - tournament docs
  - game docs
  - playbook_settings
  - season/game play stats
- Scripts should be idempotent and print before/after counts.

10. Validate in staging.
- Smoke test:
  - Playbooks screen
  - Playcall Center
  - FCC Team tab
  - Training Report
  - Scouting Report
  - any play usage/stat views
- Rename one or more plays in staging and verify UI, gameplay, and stats still work without additional migrations.

11. Remove legacy fallback logic.
- After staging is stable, remove name-based fallback lookups from backend and frontend code.
- At that point, play-name changes should be safe, routine content edits.

### Recommended Order of Execution
1. Backend read-path compatibility
2. Frontend contract updates
3. Playbook settings migration
4. Team/game/FTD play object migration
5. Stats/scouting migration
6. Hardcoded-name cleanup
7. Staging rename test
8. Production rollout

### Execution Checklist

#### Phase 1: Backend Compatibility Layer
- Goal: make backend code able to read both legacy name-based data and new `play_id`-based data.
- Update these backend areas first:
  - `BackEnd/models/turn_manager.py`
  - `BackEnd/engine/phase_resolution.py`
  - `BackEnd/api/gameplan_routes.py`
  - `BackEnd/models/team_manager.py`
  - `BackEnd/utils/stat_updater.py`
  - `BackEnd/utils/scouting_utils.py`
- Required behavior:
  - if `play_id` exists, use it as the primary reference
  - if only `name` exists, fall back temporarily
  - keep current gameplay stable while mixed-shape data exists
- Deliverable:
  - no user-facing changes yet
  - codebase can safely read old and new data shapes

#### Phase 2: Frontend Contract Alignment
- Goal: ensure frontend screens treat `play_id` as identity and `name` as display text.
- Review and update these frontend areas:
  - `FrontEnd/static/playbooks.js`
  - `FrontEnd/static/court.html`
  - `FrontEnd/static/franchise-command-center.js`
  - `FrontEnd/static/training-report.js`
  - `FrontEnd/static/js/shared/scoutingReport.js`
  - `FrontEnd/static/play-details.html`
- Required behavior:
  - cards, rows, and links display `name`
  - selection, matching, and persistence prefer `play_id`
  - no screen should require the play name to be stable
- Deliverable:
  - all major play-related screens consume `play_id` cleanly

#### Phase 3: Playbook Settings Migration
- Goal: remove play-name keys from saved playbook settings.
- Migrate these structures:
  - `motion`
  - `set_play_inside`
  - `set_play_attack`
  - `set_play_outside`
  - `slot_assignments`
- Suggested target shape:
  - percentages keyed by `play_id`
  - slot assignments keyed by slot number with `playId` as source of truth
  - optional `playName` kept only as cached display text
- Primary code touchpoints:
  - `BackEnd/api/gameplan_routes.py`
  - `FrontEnd/static/playbooks.js`
  - any game-start/playbook-loading code in `court.html` and Phaser boot flow
- Deliverable:
  - renaming a play no longer invalidates saved playbook percentages or slot assignments

#### Phase 4: Team / FTD / Tournament / Game Play Object Migration
- Goal: stop keying team play collections by play name.
- Data stores to migrate:
  - `franchise_team_data.plays`
  - `tournaments.teams.{team_id}.plays`
  - `games.teams.{team_id}.plays`
- Decide and implement one target structure:
  - `plays_by_id: {play_id: play_data}`
  - or `plays: [play_data...]` with runtime indexes
- Primary code touchpoints:
  - `BackEnd/models/team_manager.py`
  - `BackEnd/api/gameplan_routes.py`
  - `BackEnd/engine/phase_resolution.py`
  - any code that currently does `plays[current_playcall]` or loops `for play_name, play_data in plays.items()`
- Deliverable:
  - team/game/franchise data remains valid after universal play renames

#### Phase 5: Stats and Scouting Migration
- Goal: ensure historical and future stats remain attached to the play across renames.
- Migrate these systems:
  - offensive play `game_stats`
  - offensive play `season_stats`
  - scouting play usage tables
  - FCC team play summaries
  - training report play summaries
- Primary code touchpoints:
  - `BackEnd/utils/stat_updater.py`
  - `BackEnd/utils/scouting_utils.py`
  - `FrontEnd/static/franchise-command-center.js`
  - `FrontEnd/static/training-report.js`
  - `FrontEnd/static/js/shared/scoutingReport.js`
- Deliverable:
  - old stats survive renames
  - future stat accumulation is ID-based

#### Phase 6: Hardcoded Name Cleanup
- Goal: eliminate code paths that still assume specific play names.
- Known areas to clean:
  - playbook default seeding in `BackEnd/api/gameplan_routes.py`
  - position filter initialization in `BackEnd/api/gameplan_routes.py`
  - static Playcall Center fallback content in `FrontEnd/static/court.html`
  - any docs/config seeds or test fixtures that require exact names
- Deliverable:
  - changing a play name does not silently break defaults or fallback UI

#### Phase 7: Migration Scripts
- Goal: convert persisted data in staging safely and repeatably.
- Create scripts for:
  - universal play rename update
  - playbook_settings key migration
  - FTD play object migration
  - tournament play object migration
  - game play object migration
  - season/game stat migration
- Script requirements:
  - staging-first
  - idempotent
  - clear before/after counts
  - log skipped/unknown records
- Deliverable:
  - full staging data can be converted without manual cleanup

#### Phase 8: Staging Validation
- Goal: prove a renamed play still works everywhere.
- Validation checklist:
  - rename one motion play and one set play in staging
  - Playbooks screen still shows and saves them
  - Playcall Center still loads and sends overrides
  - FCC Team tab still renders play summaries
  - Training Report still renders play rows
  - Scouting Report still renders play usage
  - in-game stat accumulation still updates the renamed play
  - historical stats remain attached
- Deliverable:
  - staging signoff that play renames are operationally safe

#### Phase 9: Production Rollout
- Goal: move the same model safely into `gob`.
- Production rollout sequence:
  1. deploy compatibility code
  2. run production migrations
  3. verify read/write behavior
  4. rename a low-risk play as a live proof
  5. remove legacy fallback logic later
- Deliverable:
  - play names become editable content rather than schema identifiers

### Suggested Script List
- `scripts/migrate_playbook_settings_to_play_ids.py`
- `scripts/migrate_team_play_maps_to_play_ids.py`
- `scripts/migrate_play_stats_to_play_ids.py`
- `scripts/rename_play_across_staging.py`
- `scripts/verify_play_id_migration.py`

### Definition of Done
- A play can be renamed in the universal plays collection.
- No saved playbook settings need manual repair.
- No team/game/franchise play objects break.
- Playcall Center, Playbooks, FCC Team tab, Training Report, and Scouting Report still display the renamed play.
- Historical and future stats remain attached to the same play.
- Backend no longer depends on play name as a persisted identifier.

### Phase 1 Detailed Task List
Goal: make backend read paths support both legacy name-based persistence and new `play_id`-based persistence before any broad data migration runs.

#### Task 1: Define canonical backend lookup helpers
- Add shared helper utilities for:
  - resolving a team play by `play_id` first, then by `name`
  - resolving a universal play doc by `play_id` first, then by `name`
  - extracting a stable display name from a play object
- Best candidate locations:
  - `BackEnd/utils/` helper module
  - or targeted helper functions inside existing play/team settings modules
- Output:
  - a single backend contract for “find play from mixed legacy/new data”

#### Task 2: Update universal-to-team play hydration
- File:
  - `BackEnd/models/team_manager.py`
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - ensure every hydrated team play object always includes `play_id`
  - continue including `name` as display data
  - avoid introducing any new name-key dependence
- Why first:
  - all downstream game/team docs inherit this shape

#### Task 3: Update HCO runtime play resolution
- Files:
  - `BackEnd/engine/phase_resolution.py`
  - `BackEnd/models/turn_manager.py`
- Work:
  - when looking up the current play, prefer `play_id`
  - only fall back to name if old data is encountered
  - isolate current-play resolution behind helper functions where possible
- Special attention:
  - current playcall selection
  - team-specific play overrides
  - skeleton fetch path
  - any place where `plays[current_playcall]` is assumed

#### Task 4: Update playbook loading and read logic
- File:
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - load playbook data in a way that can interpret:
    - old name-keyed percentages
    - future `play_id`-keyed percentages
  - normalize response payloads so frontend can continue functioning during transition
- Do not migrate persisted data yet.
- Only make read paths tolerant.

#### Task 5: Update stat aggregation read paths
- Files:
  - `BackEnd/utils/stat_updater.py`
  - `BackEnd/utils/scouting_utils.py`
  - any helper used to build FCC/scouting play summaries
- Work:
  - make stat readers robust to both:
    - legacy name-keyed play records
    - future ID-keyed play records
  - centralize any “play key” logic so it is not scattered
- Important:
  - avoid changing write paths yet unless needed for compatibility
  - Phase 1 is about safe reading, not full persistence conversion

#### Task 6: Update API payload builders that enumerate plays
- Files:
  - `BackEnd/api/gameplan_routes.py`
  - any report/scouting endpoints that serialize play rows
- Work:
  - ensure payloads include:
    - `play_id`
    - `name`
    - existing display metadata
  - if source data is legacy, derive output without breaking clients
- Output:
  - frontend gets stable IDs before persistence migration lands

#### Task 7: Add temporary compatibility logging
- Files:
  - same files above, where mixed-shape reads occur
- Work:
  - add low-noise debug/warning logging when backend falls back from `play_id` to `name`
  - log enough to confirm where legacy data still exists
- Purpose:
  - helps validate staging migration readiness
  - gives visibility into remaining legacy paths

#### Task 8: Add focused regression tests
- Test targets:
  - play resolution by `play_id`
  - fallback resolution by `name`
  - HCO skeleton fetch from mixed team play shapes
  - playbook payload generation with mixed name/ID persistence
  - scouting/stat summary generation from mixed shapes
- Suggested files:
  - `BackEnd/tests/`
  - add targeted unit tests instead of broad end-to-end tests for this phase

### Phase 1 Dependency Order
1. shared lookup helpers
2. team play hydration updates
3. HCO runtime resolution updates
4. playbook API read compatibility
5. stats/scouting read compatibility
6. response payload normalization
7. compatibility logging
8. regression tests

### Phase 1 Exit Criteria
- Backend can read and run with:
  - old name-keyed persisted play data
  - new `play_id`-based persisted play data
  - mixed environments during migration
- No gameplay regressions in HCO play resolution.
- No API regressions for Playbooks, Playcall Center, FCC summaries, Training Report, or Scouting Report.
- Frontend-facing payloads consistently include both `play_id` and `name`.

### Phase 2 Detailed Task List
Goal: make the frontend treat `play_id` as the primary identifier and `name` as display-only data, while remaining compatible with legacy payloads during migration.

#### Task 1: Define frontend identity contract
- Standardize the client-side contract for every play row/card/object:
  - `play_id` = primary stable ID
  - `name` = display label
  - `play_type`
  - `play_focus`
  - `target_shooter` where relevant
- Ensure every screen that consumes plays can tolerate:
  - modern payloads with `play_id`
  - legacy payloads where only `name` is usable

#### Task 2: Update Playbooks screen identity handling
- File:
  - `FrontEnd/static/playbooks.js`
- Work:
  - make `play_id` the primary value for:
    - percentages
    - slot assignments
    - visibility/filter checks
    - card matching
    - navigation state
  - keep `name` for visible labels only
  - preserve backward compatibility with older `assignment.playId` values that may still contain names
- Why high priority:
  - this screen currently mixes `play_id`, `id`, and `name` during matching and save flows

#### Task 3: Update Playcall Center data flow
- Files:
  - `FrontEnd/static/court.html`
  - `FrontEnd/static/js/phaser/ui/playcallCenter.js`
- Work:
  - make play option construction and headshot logic use `play_id` as the stable reference
  - allow display text to come from `name`
  - keep support for older slot assignment payloads until migration is complete
- Special attention:
  - offense card browsing
  - play override submission
  - page-load headshot population
  - any DOM attributes that currently store play names as identity

#### Task 4: Update Play Details navigation
- File:
  - `FrontEnd/static/play-details.html`
- Work:
  - determine whether details should be routed by `play_id` instead of `play_name`
  - if the page still accepts `play_name`, add compatibility for `play_id`
  - avoid assuming the display name is unique or stable

#### Task 5: Update FCC Team tab rendering assumptions
- File:
  - `FrontEnd/static/franchise-command-center.js`
- Work:
  - ensure row identity and sort/render logic can operate on play objects with `play_id`
  - keep `name` as label only
  - verify any local caching or diff logic does not use play name as the durable key

#### Task 6: Update Training Report rendering assumptions
- File:
  - `FrontEnd/static/training-report.js`
- Work:
  - ensure report rows can be keyed by `play_id`
  - keep visible text from `name`
  - tolerate mixed-shape API payloads while backend/data migration is still in progress

#### Task 7: Update Scouting Report rendering assumptions
- File:
  - `FrontEnd/static/js/shared/scoutingReport.js`
- Work:
  - ensure play usage tables can render and sort using play objects where `play_id` is the stable identifier
  - keep `name` for labels
  - avoid any future joins or selections by play name

#### Task 8: Normalize any in-browser caching/state
- Files:
  - `FrontEnd/static/js/state/gameStore.js`
  - any page-level local state in `playbooks.js`, `court.html`, and FCC/report scripts
- Work:
  - check whether cached playbook/play data stores name-keyed maps
  - normalize caches so identity survives display-name changes
- Important:
  - transient UI state can still display names, but persisted or cache-rehydrated references should prefer IDs

#### Task 9: Review query params and URL contracts
- Files:
  - `FrontEnd/static/playbooks.js`
  - `FrontEnd/static/play-details.html`
  - `FrontEnd/static/set-lineup.js`
  - any navigation helper that passes play references
- Work:
  - identify any URLs that still pass play names as identifiers
  - move to `play_id` where feasible
  - keep compatibility handling if old inbound links still use `play_name`

#### Task 10: Add frontend compatibility guards
- Files:
  - screens above as needed
- Work:
  - when a play object lacks `play_id`, gracefully fall back to name
  - log or surface low-noise debug warnings where legacy data is still in use
- Purpose:
  - allows staged backend/data migration without a brittle frontend cutover

#### Task 11: Add focused frontend regression coverage
- Priority checks:
  - Playbooks screen renders and saves with `play_id`
  - Playcall Center renders correct play labels and headshots
  - FCC Team tab still renders play summaries
  - Training Report still renders play rows
  - Scouting Report still renders play usage
  - renamed plays still appear correctly without broken matching
- Use existing test coverage where possible; otherwise add targeted smoke/manual test notes.

### Phase 2 Dependency Order
1. define frontend identity contract
2. Playbooks screen identity updates
3. Playcall Center identity updates
4. Play Details route compatibility
5. FCC Team tab updates
6. Training Report updates
7. Scouting Report updates
8. cache/state normalization
9. query-param / navigation cleanup
10. compatibility guards
11. regression checks

### Phase 2 Exit Criteria
- Frontend uses `play_id` as the primary identity across all major play-related screens.
- Display text always comes from `name`, but screen behavior does not depend on `name` stability.
- Playbooks, Playcall Center, FCC Team tab, Training Report, and Scouting Report all work against mixed legacy/new payloads.
- Renaming a play no longer breaks frontend matching, selection, rendering, or saved UI state.

### Phase 3 Detailed Task List
Goal: migrate `playbook_settings` from play-name-keyed persistence to `play_id`-keyed persistence without breaking existing saved user data.

#### Phase 3 Scope
- This phase is specifically about saved playbook configuration, not team play maps or stat history.
- Target structures:
  - `motion`
  - `set_play_inside`
  - `set_play_attack`
  - `set_play_outside`
  - `slot_assignments`
  - any related helper metadata that still stores play names as identity

#### Task 1: Define the new `playbook_settings` persistence shape
- Decide the exact target contract.
- Recommended shape:
  - `motion: { play_id: percentage }`
  - `set_play_inside: { play_id: percentage }`
  - `set_play_attack: { play_id: percentage }`
  - `set_play_outside: { play_id: percentage }`
  - `slot_assignments: { slotNumber: { playId, playName?, section, dropdown? } }`
- Keep `playName` optional and display-only inside slot assignments during transition.
- Document the final shape in the brief and relevant system docs.

#### Task 2: Update backend playbook read compatibility
- File:
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - detect whether stored playbook percentages are keyed by name or `play_id`
  - normalize both shapes into a single response contract for the frontend
  - preserve old data reads during staging migration
- Important:
  - do not break users with legacy saved playbooks

#### Task 3: Update backend playbook write handling
- File:
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - accept frontend payloads that save percentages by `play_id`
  - keep transitional support for old name-keyed payloads if needed
  - ensure returned/stored shape is consistent after save
- Goal:
  - once this lands, all newly saved playbook settings should be ID-based

#### Task 4: Update frontend save flow
- File:
  - `FrontEnd/static/playbooks.js`
- Work:
  - save `motion` and `set_play_*` percentages keyed by `play_id`
  - stop using play names as the source-of-truth persistence key
  - continue sending `playName` only where needed for display/debug
- Important:
  - preserve correct behavior for hidden plays, filtered plays, and zero-percent plays

#### Task 5: Update frontend load/render flow
- File:
  - `FrontEnd/static/playbooks.js`
- Work:
  - when rendering sections, resolve percentages by `play_id`
  - support fallback to old name-keyed saved settings during transition
  - ensure reordering, filtering, and slot highlighting still work after the ID switch

#### Task 6: Convert slot assignments to strict ID identity
- Files:
  - `FrontEnd/static/playbooks.js`
  - `BackEnd/api/gameplan_routes.py`
  - `FrontEnd/static/court.html`
- Work:
  - make `slot_assignments[*].playId` the only source of truth
  - keep `playName` only as optional cached text
  - update any load/build code in court/playcall-center logic that still assumes slot assignment identity by name
- Goal:
  - a renamed play stays attached to the same slot automatically

#### Task 7: Review related secondary settings
- Files:
  - `FrontEnd/static/playbooks.js`
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - verify `motion_dropdowns` are keyed safely relative to the new identity model
  - verify `position_filters` continue to operate correctly while still name-seeded in current UI
  - do not redesign filters yet, just ensure Phase 3 doesn’t break them

#### Task 8: Create playbook-settings migration script
- Suggested script:
  - `scripts/migrate_playbook_settings_to_play_ids.py`
- Responsibilities:
  - load universal plays and build `name -> play_id` map
  - migrate name-keyed `motion` / `set_play_*` maps to ID-keyed maps
  - normalize slot assignments so `playId` always stores DB `play_id`
  - preserve `playName` as display-only text if desired
  - run against staging first
- Script requirements:
  - idempotent
  - logs count of migrated docs
  - logs unknown play names that could not be mapped

#### Task 9: Apply migration to all playbook-setting owners
- Data stores to cover:
  - `franchise_team_data.playbook_settings`
  - `tournaments.teams.{team_id}.playbook_settings`
  - `games.teams.{team_id}.playbook_settings`
  - any cached/seeded playbook settings copied into game docs or runtime summaries
- Goal:
  - no surviving name-keyed playbook settings in staging after migration

#### Task 10: Add backend/frontend compatibility logging
- Files:
  - `BackEnd/api/gameplan_routes.py`
  - `FrontEnd/static/playbooks.js`
  - `FrontEnd/static/court.html`
- Work:
  - log when legacy name-keyed playbook settings are detected
  - log when frontend has to fall back from `play_id` to name matching
- Purpose:
  - helps identify remaining unmigrated records or stale payload paths

#### Task 11: Validate with staging saves and reloads
- Manual / smoke validation:
  - load Playbooks page for franchise, tournament, and single-game contexts
  - confirm percentages render correctly from migrated settings
  - save changes and reload
  - confirm Playcall Center slot order still matches selected plays
  - rename a play in staging and confirm playbook settings still map correctly
- Specific checks:
  - 0% entries remain stable
  - slot assignments survive rename
  - no duplicate/unresolved cards appear

#### Task 12: Update documentation
- Files/docs to refresh after implementation:
  - `pc_rework_brief.md`
  - Playbooks Page system docs
  - any data persistence docs that still describe play-name-keyed percentages
- Goal:
  - docs match the new contract before broader rollout

### Phase 3 Dependency Order
1. define new `playbook_settings` shape
2. backend read compatibility
3. backend write updates
4. frontend save flow
5. frontend load/render flow
6. strict slot-assignment identity
7. review secondary settings
8. migration script
9. apply migration to all owners
10. compatibility logging
11. staging validation
12. documentation updates

### Phase 3 Exit Criteria
- All newly saved playbook settings use `play_id` as the persistence key.
- Legacy name-keyed playbook settings still load during transition.
- Staging migration converts old playbook settings without data loss.
- Playbooks page and Playcall Center still behave correctly after save/reload.
- Renaming a play no longer breaks percentages or slot assignments.

### Phase 4 Detailed Task List
Goal: migrate team/franchise/tournament/game play collections away from name-keyed maps so play identity is stable even when display names change.

#### Phase 4 Scope
- Data stores in scope:
  - `franchise_team_data.plays`
  - `tournaments.teams.{team_id}.plays`
  - `games.teams.{team_id}.plays`
- This phase is about the play-object container shape itself, not just playbook settings.

#### Task 1: Choose the target play collection structure
- Decide the canonical persisted shape for team-owned play collections.
- Recommended options:
  - `plays_by_id: { play_id: play_data }`
  - or `plays: [play_data...]` plus runtime indexes
- Strong preference:
  - use an ID-keyed dictionary for simpler migration from current maps and for easier stat path updates later
- Ensure `play_data` still includes:
  - `play_id`
  - `name`
  - `play_type`
  - `play_focus`
  - `target_shooter`
  - effectiveness / momentum / cloaking
  - game/season stats

#### Task 2: Define runtime access helpers for team plays
- Add helpers that can:
  - fetch a play by `play_id`
  - fetch a play by `name` as temporary fallback
  - build `name -> play_id` and `play_id -> play_data` indexes when needed
- These helpers should become the only supported access path for team play collections.
- Best areas:
  - `BackEnd/models/team_manager.py`
  - shared utility module if reuse is broad

#### Task 3: Update team initialization paths
- Files:
  - `BackEnd/models/team_manager.py`
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - when team play collections are first populated from universal plays, persist them in the new structure
  - preserve compatibility for old name-keyed records during the transition
- Goal:
  - all newly created franchise/tournament/game team records use the new structure

#### Task 4: Update gameplay read paths
- Files:
  - `BackEnd/models/turn_manager.py`
  - `BackEnd/engine/phase_resolution.py`
  - any helper that reads `team.plays[...]`
- Work:
  - replace assumptions like `plays[current_playcall]`
  - use helper-based resolution through `play_id` / runtime indexes
  - maintain temporary fallback for old structures until staging migration is complete
- Goal:
  - gameplay does not care whether the stored collection is name-keyed or ID-keyed

#### Task 5: Update API serialization paths
- File:
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - when returning play collections to frontend, serialize from the new structure
  - preserve response shape the frontend expects during transition
  - avoid leaking internal storage shape unnecessarily
- Goal:
  - frontend screens continue working while backend storage evolves underneath

#### Task 6: Update any direct iteration over `plays.items()`
- Files to review carefully:
  - `BackEnd/api/gameplan_routes.py`
  - `BackEnd/utils/stat_updater.py`
  - `BackEnd/utils/scouting_utils.py`
  - `FrontEnd/static/franchise-command-center.js`
  - `FrontEnd/static/training-report.js`
- Work:
  - replace loops that assume `play_name` is the dictionary key
  - move to iterating over play objects and reading `play.name` as display text
- Goal:
  - display/report logic is independent of storage key choice

#### Task 7: Design backward compatibility strategy
- During transition, support these possibilities:
  - old name-keyed maps
  - new ID-keyed maps
  - mixed docs in staging
- Required behavior:
  - reads must succeed regardless of shape
  - writes should prefer the new structure once the compatibility layer is in place
- Optional:
  - stamp migrated docs with metadata/version marker for easier observability

#### Task 8: Create team play map migration script
- Suggested script:
  - `scripts/migrate_team_play_maps_to_play_ids.py`
- Responsibilities:
  - build `name -> play_id` map from universal plays
  - convert old `plays.{play_name}` maps into new ID-keyed structure
  - preserve all nested play data and stats
  - keep `name` in each play object for display
  - log unmapped or duplicate cases
- Script requirements:
  - idempotent
  - staging-first
  - before/after counts for each collection

#### Task 9: Migrate FTD docs
- Collection:
  - `franchise_team_data`
- Work:
  - convert each team’s play collection to the new structure
  - ensure franchise-mode read/write logic still works after migration
- Validate:
  - FCC Team tab
  - playbooks load/save
  - franchise sim/stat updates

#### Task 10: Migrate tournament docs
- Collection:
  - `tournaments`
- Work:
  - convert `teams.{team_id}.plays`
  - verify tournament pregame/playbooks/scouting paths still work
- Validate:
  - tournament Playbooks
  - scouting modal
  - simulated tournament games

#### Task 11: Migrate single-game docs
- Collection:
  - `games`
- Work:
  - convert `teams.{team_id}.plays`
  - verify in-progress and newly created games can both be read
- Validate:
  - court load
  - Playcall Center
  - HCO gameplay resolution
  - box score / game summary generation

#### Task 12: Add observability and verification tooling
- Add temporary verification/logging for:
  - number of legacy vs migrated docs read
  - fallback-from-name events
  - unmapped plays during migration
- Suggested script:
  - `scripts/verify_team_play_map_migration.py`
- Goal:
  - make staging rollout measurable before Phase 5 stat migration

#### Task 13: Stage rename proof test
- After migration, rename one play in staging and verify:
  - FCC Team tab still renders it
  - Training Report still renders it
  - Scouting Report still renders it
  - Playcall Center still resolves the selected play
  - gameplay and postgame stat accumulation still work
- This is the first real proof that team-owned play data is no longer name-anchored.

### Phase 4 Dependency Order
1. choose target play collection structure
2. add runtime access helpers
3. update team initialization
4. update gameplay read paths
5. update API serialization
6. replace direct `plays.items()` assumptions
7. finalize backward compatibility strategy
8. build migration script
9. migrate FTD docs
10. migrate tournament docs
11. migrate game docs
12. add verification tooling
13. run rename proof test

### Phase 4 Exit Criteria
- New team/franchise/tournament/game play collections persist in the new ID-safe structure.
- Backend gameplay logic can read both legacy and migrated team play collections during transition.
- FCC, Training Report, Scouting Report, Playbooks, and court/gameplay flows all work after migration.
- Renaming a play no longer requires rewriting team/game/franchise play containers.

### Phase 5 Detailed Task List
Goal: migrate play-related stats, summaries, and scouting/reporting logic so historical and future data attach to `play_id` instead of mutable play names.

#### Phase 5 Scope
- Systems in scope:
  - offensive play `game_stats`
  - offensive play `season_stats`
  - end-of-game stat rollups
  - scouting play usage summaries
  - FCC Team tab play summaries
  - Training Report play summaries
  - Scouting Report play usage tables
- This phase is about stat identity and reporting continuity after renames.

#### Task 1: Define the canonical stat identity model
- Decide where `play_id` becomes the stat anchor.
- Recommended model:
  - all persisted play stat buckets are keyed by `play_id`
  - each stat payload still stores `name` for display convenience
- Required properties:
  - historical data remains attached across renames
  - reports can still display current name cleanly

#### Task 2: Update game-time stat accumulation logic
- Files:
  - `BackEnd/engine/phase_resolution.py`
  - any runtime code that increments `game_stats` on team play objects
- Work:
  - ensure stat updates target the correct play via `play_id`
  - remove any assumption that current play name is the stat key
- Goal:
  - live game stat accumulation survives display-name changes

#### Task 3: Update end-of-game season rollup logic
- File:
  - `BackEnd/utils/stat_updater.py`
- Work:
  - replace season stat update paths currently anchored on play names
  - write season totals to ID-based paths
  - maintain temporary support for reading old name-based season stat paths during transition
- Critical area:
  - franchise/tournament season accumulation
  - any game-summary promotion from `game_stats` to `season_stats`

#### Task 4: Update scouting data extraction
- File:
  - `BackEnd/utils/scouting_utils.py`
- Work:
  - generate scouting play usage rows from play objects keyed by `play_id`
  - keep emitted rows shaped like:
    - `play_id`
    - `name`
    - `times_run`
    - `successes`
    - total/cumulative metrics as needed
- Goal:
  - scouting reports become immune to name changes

#### Task 5: Update FCC Team tab summary generation
- Files:
  - `FrontEnd/static/franchise-command-center.js`
  - any backend payload code feeding team play summaries
- Work:
  - ensure FCC rows use `play_id` as row identity
  - display `name` only as label text
  - verify sorting/top-scorer/success-rate calculations do not depend on name-keyed maps

#### Task 6: Update Training Report play summary generation
- Files:
  - `FrontEnd/static/training-report.js`
  - any backend report builder that emits play effectiveness changes
- Work:
  - carry `play_id` through report rows
  - render labels from `name`
  - avoid joining report changes back to plays by display name where possible

#### Task 7: Update Scouting Report rendering
- File:
  - `FrontEnd/static/js/shared/scoutingReport.js`
- Work:
  - make report rows keyed/rendered by `play_id`
  - keep displayed text from `name`
  - verify usage %, success rate, and sorting continue to work after renames

#### Task 8: Design legacy stat compatibility strategy
- Support these states during transition:
  - historical stats stored under old name-keyed paths
  - new stats stored under ID-keyed paths
  - mixed docs in staging
- Strategy options:
  - normalize reads from both old and new buckets
  - or migrate old stat structures first, then simplify reads
- Recommendation:
  - implement tolerant reads first, then run migration scripts

#### Task 9: Create stat migration script
- Suggested script:
  - `scripts/migrate_play_stats_to_play_ids.py`
- Responsibilities:
  - build `name -> play_id` map from universal plays
  - convert play-related stat structures from name-keyed to ID-keyed
  - preserve totals, successes, player_points, effectiveness, and any existing derived values
  - log unmapped names or collisions
- Script requirements:
  - idempotent
  - staging-first
  - before/after counts

#### Task 10: Create scouting/report verification script
- Suggested script:
  - `scripts/verify_play_stats_and_scouting_migration.py`
- Responsibilities:
  - verify every migrated stat bucket resolves to a valid `play_id`
  - verify no orphaned old-name stat entries remain unintentionally
  - compare pre/post aggregate totals for consistency

#### Task 11: Validate rename continuity in staging
- After stat migration, rename one or more plays in staging and verify:
  - FCC Team tab still shows historical usage for the renamed play
  - Training Report still shows the renamed play correctly
  - Scouting Report still shows the renamed play’s usage/success history
  - ongoing games continue adding stats to the same play record
  - season totals do not split across old/new names
- This is the key proof that stat identity is no longer name-based.

#### Task 12: Clean up old stat-path assumptions
- Files to review after migration:
  - `BackEnd/utils/stat_updater.py`
  - `BackEnd/utils/scouting_utils.py`
  - `FrontEnd/static/franchise-command-center.js`
  - `FrontEnd/static/training-report.js`
  - `FrontEnd/static/js/shared/scoutingReport.js`
- Work:
  - remove legacy read fallbacks once staging and production are stable
  - simplify code paths around ID-keyed stats

### Phase 5 Dependency Order
1. define canonical stat identity model
2. update game-time stat accumulation
3. update season rollup logic
4. update scouting data extraction
5. update FCC summaries
6. update Training Report summaries
7. update Scouting Report rendering
8. add legacy stat compatibility
9. build stat migration script
10. build verification script
11. run rename continuity validation
12. remove old stat-path assumptions later

### Phase 5 Exit Criteria
- Game and season play stats are anchored to `play_id`.
- FCC Team tab, Training Report, and Scouting Report all display renamed plays without losing historical continuity.
- Renaming a play no longer splits stat history across old and new names.
- Legacy name-keyed stat structures are either migrated or safely handled during transition.

### Phase 6 Detailed Task List
Goal: remove remaining hardcoded play-name assumptions so renames are routine content changes, not code changes.

#### Phase 6 Scope
- Hardcoded/default play-name lists
- Static fallback UI content
- Seed/default playbook logic
- Test fixtures and docs that still encode production play names as assumptions

#### Task 1: Inventory all remaining hardcoded play names
- Search the codebase and docs for explicit play-name literals.
- Categorize each hit as:
  - runtime-critical
  - seed/default-only
  - static UI fallback
  - test fixture
  - documentation only
- Goal:
  - produce a finite cleanup list before deleting or refactoring anything

#### Task 2: Refactor playbook default seeding
- File:
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - remove hardcoded seeded play-name lists where possible
  - replace with:
    - `play_id` lists
    - or metadata-driven rules
    - or explicit config tied to stable IDs
- Priority:
  - `standard_seed_plays`
  - `sf_seed_plays`
  - any future default playbook bootstrapping logic

#### Task 3: Refactor position filter initialization
- File:
  - `BackEnd/api/gameplan_routes.py`
- Work:
  - remove hardcoded per-position play-name arrays
  - replace with either:
    - metadata-driven derivation
    - or stable `play_id` configuration
- Note:
  - UI overhaul may supersede this later, but Phase 6 should at least remove name fragility from current logic

#### Task 4: Remove static Playcall Center play-name assumptions
- File:
  - `FrontEnd/static/court.html`
- Work:
  - replace hardcoded fallback/offense card play names with dynamic slot/playbook content
  - if placeholders are needed, make them generic rather than tied to real play names
- Goal:
  - changing a play name in DB should not require editing court markup

#### Task 5: Review Play Details and builder assumptions
- Files:
  - `FrontEnd/static/play-details.html`
  - `FrontEnd/static/plays-builder.html`
  - `FrontEnd/static/play-builder-v2.html`
- Work:
  - remove any assumption that a play name is a stable routing or loading identifier
  - prefer `play_id` or API-backed lookup flows

#### Task 6: Review docs/config seeds used by development or QA
- Files/areas:
  - docs describing seeded/default playbooks
  - any archived reference payloads
  - any local JSON/demo content
- Work:
  - update docs so they no longer imply play names are schema identifiers
  - keep examples illustrative, not normative

#### Task 7: Review tests for name-coupled assumptions
- Areas:
  - backend tests
  - frontend tests
  - any fixture payloads with exact play-name matching
- Work:
  - convert tests to assert on stable IDs and metadata where appropriate
  - keep only intentional display-label assertions tied to visible text
- Goal:
  - renaming a play should not cascade into brittle test failures unless the UI text itself is the thing being tested

#### Task 8: Add verification pass for hardcoded-name drift
- Suggested script:
  - `scripts/find_hardcoded_play_name_dependencies.py`
- Responsibilities:
  - scan for known production play names in runtime code
  - separate allowed docs/examples from runtime dependencies
  - make future regressions easy to detect

#### Task 9: Run staging rename proof after cleanup
- Rename one or more plays in staging and verify:
  - no code/default/fallback path still references the old name
  - default playbook initialization still works
  - Playcall Center fallback content still works
  - no screen shows stale old labels because of static markup

### Phase 6 Dependency Order
1. inventory hardcoded names
2. refactor playbook default seeding
3. refactor position filter initialization
4. remove static Playcall Center assumptions
5. review Play Details/builders
6. update docs/config seeds
7. update tests
8. add drift-detection tooling
9. run staging rename proof

### Phase 6 Exit Criteria
- No runtime-critical code depends on specific production play names.
- Default/seed behavior is stable under play renames.
- Static court/playcall markup no longer embeds real play names as assumptions.
- Renaming a play does not require code edits outside optional content/docs examples.

## Suggested Implementation Roadmap

### Sprint 1: Playbook Identity Foundation
Primary phases:
- Phase 3
- Phase 1

Goals:
- move playbook settings toward `play_id` persistence
- add backend compatibility so old and new data shapes can coexist
- avoid breaking existing saved playbooks while introducing the new model

Success criteria:
- Playbooks can save/load with `play_id` as the primary identity
- backend gameplay and API reads tolerate mixed name/ID persistence
- no visible regressions in Playbooks or Playcall Center

### Sprint 2: Frontend Identity Alignment
Primary phase:
- Phase 2

Goals:
- make frontend screens consistently use `play_id` for identity
- keep `name` as display-only text
- remove frontend matching logic that depends on name stability

Success criteria:
- Playbooks, Playcall Center, FCC Team tab, Training Report, and Scouting Report all function correctly against mixed-shape payloads
- a renamed play still renders and matches correctly in the UI

### Sprint 3: Team Data + Stats Migration
Primary phases:
- Phase 4
- Phase 5

Goals:
- move team/game/franchise/tournament play containers to an ID-safe structure
- migrate stat/scouting identity to `play_id`
- preserve historical continuity under renamed plays

Success criteria:
- gameplay resolves team plays correctly after migration
- FCC / Training Report / Scouting Report preserve historical play continuity
- renaming a play no longer splits team data or stats across old/new names

### Sprint 4: Hardening and Cleanup
Primary phase:
- Phase 6

Goals:
- remove remaining hardcoded-name assumptions
- clean up fallback paths, static markup, docs, and tests
- add verification tooling to prevent regression

Success criteria:
- no runtime-critical code depends on specific play names
- renaming a play is treated as a normal content change
- remaining name references are documentation/example-only
