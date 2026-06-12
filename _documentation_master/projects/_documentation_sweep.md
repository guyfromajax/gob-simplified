# Documentation Sweep — Checklist & Work Plan

**Created:** 2026-06-12
**Goal:** Review every file in `_documentation_master/` to confirm it is current, flag files to delete or combine to avoid doc bloat, and identify docs needing significant updates.

## How to use

- Mark `[x]` when a file has been reviewed.
- After each file, record a verdict after the `→`:
  - **Keep** — current and accurate, no action needed
  - **Update** — needs significant updates (note what)
  - **Combine** — fold into another doc (note the target)
  - **Delete** — obsolete / superseded
- Add brief notes inline as needed.

**Sunset modes decision (2026-06-12):** Single Game mode and Tournament mode are sunset. Their docs get **deleted** as we reach them, replaced by a single one-page sunset note (tag + key learnings) to be drafted when we hit `01_Game_Mode_Systems`. Code removal is a separate future project (tag commit first, staged deletion). Live docs that merely mention these modes get a "(sunset)" tag, removed when the code goes.

**Progress:** 6 / 180 reviewed

---

## 00_Data_Systems (3)

- [x] `00_Data_Systems/Database_System.md` → **Updated 2026-06-12** — rewritten as top-level DB doc: full 21-collection inventory from `db.py`, identity conventions (incl. FTD ObjectId vs FPD/FRD string `franchise_id`), startup indexes, env/db selection. Play-storage detail now lives only in `O_&_D_Plays_Collections.md`.
- [x] `00_Data_Systems/Games_Collection.md` → **Updated 2026-06-12** — trimmed 218→~70 lines. Fixed stale structure claims (`home_team`/`away_team` dicts no longer exist; `text_log` not persisted); documented legacy `team1_id`/`team2_id` result fields (still written by save-result, contrary to old doc); dropped Jan-2025 changelog narratives, stale line numbers, and "Future Documentation" placeholder; cleanup section rewritten as implemented behavior (single-game delete endpoint, franchise/tournament cascade deletes).
- [x] `00_Data_Systems/O_&_D_Plays_Collections.md` → **Updated 2026-06-12** — content verified current against code + seed scripts (play copy shape, `defenses` schema, normalize contract, play_id-first persistence, set-play alias remap). Fixed stale Related Docs links; added `motion_focus` to play-copy example. Canonical play/defense storage doc; `Database_System.md` now points here.

## 00_General_Systems (34)

- [x] `00_General_Systems/Account_Modal_System.md` → **Moved 2026-06-12** to `projects/Account_Modal_Player_View_Brief.md` — it's a feature brief, not system docs. Sections 1–2 (Username, Scouting Ambience) verified live; Section 3 (Player View sprite toggle) is planned/unbuilt. Added status header.
- [x] `00_General_Systems/Active_Page_Analysis.md` → **Deleted 2026-06-12** — Spring-2026 point-in-time navigation audit, already stale (predates news/account pages; lists sunset tournament pages as active). Its orphaned-page hit list is recoverable from git history when the frontend purge project starts.
- [x] `00_General_Systems/Box_Score_System.md` → **Keep** — verified current (all named functions exist where stated; synced to code Apr 2026). Added sunset-mode note for tournament references.
- [ ] `00_General_Systems/COURT_REDESIGN_HANDOFF.md` →
- [ ] `00_General_Systems/Coaching_Archetype_System.md` →
- [ ] `00_General_Systems/Coordinate_Orientation_Audit.md` →
- [ ] `00_General_Systems/DESIGN_HANDOFF.md` →
- [ ] `00_General_Systems/Defense_Coords_System.md` →
- [ ] `00_General_Systems/Deploy_To_Live_System.md` →
- [ ] `00_General_Systems/Font_Color_System.md` →
- [ ] `00_General_Systems/Front_End_Architecture.md` →
- [ ] `00_General_Systems/GOB FCC Shell POC.html` →
- [ ] `00_General_Systems/GOB Mode Select POC.html` →
- [ ] `00_General_Systems/GOB Set Lineup POC.html` →
- [ ] `00_General_Systems/Geek_Points_System.md` →
- [ ] `00_General_Systems/Loading_Overlay_System.md` →
- [ ] `00_General_Systems/Manual_QA_Checklist.md` →
- [ ] `00_General_Systems/New_Team_Creation_System.md` →
- [ ] `00_General_Systems/Page_Load_System.md` →
- [ ] `00_General_Systems/Plays_Page_System.md` →
- [ ] `00_General_Systems/Position_Checkpoints_and_Snapshot_Schema.md` →
- [ ] `00_General_Systems/Resend_System.md` →
- [ ] `00_General_Systems/Sound_Design_System.md` →
- [ ] `00_General_Systems/Statistics_System.md` →
- [ ] `00_General_Systems/Step_By_Step_System.md` →
- [ ] `00_General_Systems/Styleguide_updated.md` →
- [ ] `00_General_Systems/Team_Images_System.md` →
- [ ] `00_General_Systems/UESS_Backlog.md` →
- [ ] `00_General_Systems/UESS_System.md` →
- [ ] `00_General_Systems/UX_Page_Load_System.md` →
- [ ] `00_General_Systems/Unified_Animation_System.md` →
- [ ] `00_General_Systems/User_Account_System.md` →
- [ ] `00_General_Systems/fte_system.md` →
- [ ] `00_General_Systems/original_thresholds.md` →

## 01_Game_Mode_Systems (5)

- [ ] `01_Game_Mode_Systems/FCC.md` →
- [ ] `01_Game_Mode_Systems/Franchise_Mode_Systems.md` →
- [ ] `01_Game_Mode_Systems/Single_Game_Systems.md` → planned **Delete** (sunset mode; fold learnings into sunset note)
- [ ] `01_Game_Mode_Systems/TCC.md` → planned **Delete** (sunset mode; fold learnings into sunset note)
- [ ] `01_Game_Mode_Systems/Tournament_Mode_Systems.md` → planned **Delete** (sunset mode; fold learnings into sunset note)

## 03_Data_Persistence (7)

- [ ] `03_Data_Persistence/Cache_Usage_Documentation.md` →
- [ ] `03_Data_Persistence/Data_Persistence_System.md` →
- [ ] `03_Data_Persistence/Player_Stats_Architecture_Update.md` →
- [ ] `03_Data_Persistence/Settings_Persistence_Guide.md` →
- [ ] `03_Data_Persistence/State_&_Persistence_Contract.md` →
- [ ] `03_Data_Persistence/Unified_State_Persistence_Work_Plan.md` →
- [ ] `03_Data_Persistence/timeout_data_&_state_persistence.md` →

## 05_Animation_System (8)

- [ ] `05_Animation_System/AG_Implementation.md` →
- [ ] `05_Animation_System/Advance_Triggers.md` →
- [ ] `05_Animation_System/Animation_Detection_Reference.md` →
- [ ] `05_Animation_System/Animation_Handler_Reference.md` →
- [ ] `05_Animation_System/Core_Animation_System.md` →
- [ ] `05_Animation_System/Player_Sprite_System.md` →
- [ ] `05_Animation_System/Step_Types_System.md` →
- [ ] `05_Animation_System/Transition_Systems.md` →

## 05_Features (6)

- [ ] `05_Features/Defense_Matchups_System.md` →
- [ ] `05_Features/Lineup_Selection_Screen.md` →
- [ ] `05_Features/Playcall_Center.md` →
- [ ] `05_Features/Player_Momentum_System.md` →
- [ ] `05_Features/SFX_System.md` →
- [ ] `05_Features/Sim_Quarter_System.md` →

## 05_GP_Supporting_Systems (30)

- [ ] `05_GP_Supporting_Systems/Announcement_System.md` →
- [ ] `05_GP_Supporting_Systems/BIP_System.md` →
- [ ] `05_GP_Supporting_Systems/Block_System.md` →
- [ ] `05_GP_Supporting_Systems/Computer_Team_Game_Init_System.md` →
- [ ] `05_GP_Supporting_Systems/Computer_Timeout_System.md` →
- [ ] `05_GP_Supporting_Systems/Constants_System.md` →
- [ ] `05_GP_Supporting_Systems/End_Of_Game_System.md` →
- [ ] `05_GP_Supporting_Systems/Energy_System.md` →
- [ ] `05_GP_Supporting_Systems/FB_Triangle_Play_Spec.md` →
- [ ] `05_GP_Supporting_Systems/FCP_HCT_System.md` →
- [ ] `05_GP_Supporting_Systems/Fast_Break_System.md` →
- [ ] `05_GP_Supporting_Systems/Free_Throw_System.md` →
- [ ] `05_GP_Supporting_Systems/Game_Init_System.md` →
- [ ] `05_GP_Supporting_Systems/Gameplay_Buttons_System.md` →
- [ ] `05_GP_Supporting_Systems/HCO_Turn_Resolution_System.md` →
- [ ] `05_GP_Supporting_Systems/Home_Crowd_System.md` →
- [ ] `05_GP_Supporting_Systems/Motion_Offense_Shot_System.md` →
- [ ] `05_GP_Supporting_Systems/Possession_Mgmt_System.md` →
- [ ] `05_GP_Supporting_Systems/Real_Time_Clock_System.md` →
- [ ] `05_GP_Supporting_Systems/Rebound_System.md` →
- [ ] `05_GP_Supporting_Systems/SIP_System.md` →
- [ ] `05_GP_Supporting_Systems/Shot_Clock_Audit_and_Work_Plan.md` →
- [ ] `05_GP_Supporting_Systems/Shot_System.md` →
- [ ] `05_GP_Supporting_Systems/Sim_Playcalling_System.md` →
- [ ] `05_GP_Supporting_Systems/Situational_Logic_System.md` →
- [ ] `05_GP_Supporting_Systems/Special_Tracking_System.md` →
- [ ] `05_GP_Supporting_Systems/Steal_System.md` →
- [ ] `05_GP_Supporting_Systems/Stopper_System.md` →
- [ ] `05_GP_Supporting_Systems/Timeout_System.md` →
- [ ] `05_GP_Supporting_Systems/Turn_by_Turn_System.md` →

## 06_Features (2)

- [ ] `06_Features/Coaching_Grid.md` →
- [ ] `06_Features/Statistics_System.md` → (note: name collision with `00_General_Systems/Statistics_System.md` — compare for combine)

## 06_GMO_Supporting_Systems (29)

- [ ] `06_GMO_Supporting_Systems/Attribute_Clamp_System.md` →
- [ ] `06_GMO_Supporting_Systems/Championship_Announce_Moments.md` →
- [ ] `06_GMO_Supporting_Systems/Coaching_Focus_Implementation_Map.md` →
- [ ] `06_GMO_Supporting_Systems/Community_Highlights_System.md` →
- [ ] `06_GMO_Supporting_Systems/Court_Template_Implementation_Spec.md` →
- [ ] `06_GMO_Supporting_Systems/Court_Template_Spec.md` →
- [ ] `06_GMO_Supporting_Systems/Distant_Game_Sim_Player_Stats.md` →
- [ ] `06_GMO_Supporting_Systems/Distant_Game_Sim_System.md` →
- [ ] `06_GMO_Supporting_Systems/Distant_Team_Training_System.md` →
- [ ] `06_GMO_Supporting_Systems/EOS_Write_Path_Inventory.md` →
- [ ] `06_GMO_Supporting_Systems/End_Of_Season_System.md` →
- [ ] `06_GMO_Supporting_Systems/Franchise_Tournament_System.md` →
- [ ] `06_GMO_Supporting_Systems/Mode_Init_System.md` →
- [ ] `06_GMO_Supporting_Systems/Offense_Plays_System.md` →
- [ ] `06_GMO_Supporting_Systems/Play_Builder_System.md` →
- [ ] `06_GMO_Supporting_Systems/Playbook_Weights_System.md` →
- [ ] `06_GMO_Supporting_Systems/Playbooks_Page.md` →
- [ ] `06_GMO_Supporting_Systems/Player_Attribute_System.md` →
- [ ] `06_GMO_Supporting_Systems/Position_Ratings_System.md` →
- [ ] `06_GMO_Supporting_Systems/Practice_Squad_System.md` → (note: currently 1 line — stub?)
- [ ] `06_GMO_Supporting_Systems/Press_Conference_System.md` →
- [ ] `06_GMO_Supporting_Systems/Rank_Prestige_System.md` →
- [ ] `06_GMO_Supporting_Systems/Recruiting_System.md` →
- [ ] `06_GMO_Supporting_Systems/Season_Init_System.md` →
- [ ] `06_GMO_Supporting_Systems/Team_Attribute_System.md` →
- [ ] `06_GMO_Supporting_Systems/Tournament_Execution_System.md` →
- [ ] `06_GMO_Supporting_Systems/Training_Notes_System.md` →
- [ ] `06_GMO_Supporting_Systems/Training_System.md` →
- [ ] `06_GMO_Supporting_Systems/Training_System_Live_Feed.md` →

## 07_Design_Systems (6)

- [ ] `07_Design_Systems/Attribute Tour Mechanic (standalone).html` →
- [ ] `07_Design_Systems/FTE Onboarding Redesign.html` →
- [ ] `07_Design_Systems/Resource_Page_Design_System.md` →
- [ ] `07_Design_Systems/Sonic_Identity.md` →
- [ ] `07_Design_Systems/Soundtrack_System.md` →
- [ ] `07_Design_Systems/Styleguide.md` → (note: compare with `00_General_Systems/Styleguide_updated.md` — likely combine/delete one)

## Root files (2)

- [ ] `ENV_VARIABLES.md` →
- [ ] `SECURITY_BASELINE.md` →

## tasks (1)

- [ ] `tasks/Defense_ID_Migration.md` →

## projects (26)

- [ ] `projects/Animation_Cleanup.md` →
- [ ] `projects/Animation_System_Updated.md` →
- [ ] `projects/Dynamic_HCT_Turns.md` →
- [ ] `projects/News_System.md` →
- [ ] `projects/Recruit_Generation_System.md` →
- [ ] `projects/Resend_Project_Brief.md` →
- [ ] `projects/Resend_Project_Work_Plan.md` →
- [ ] `projects/Social_Activation.md` →
- [ ] `projects/Tutorial_Alerts_System.md` →
- [ ] `projects/bugs.md` →
- [ ] `projects/cloudflare_migration.md` →
- [ ] `projects/offensive_state_hardening.md` →
- [ ] `projects/rebounding_logic.md` →
- [ ] `projects/secondary_announce/CURSOR_BRIEF_Secondary_Announce.md` →
- [ ] `projects/secondary_announce/Secondary Announce.html` →
- [ ] `projects/simulate_quarter_api_cleanup.md` →
- [ ] `projects/staging_otps.md` →
- [ ] `projects/universal_3point_helper.md` →
- [ ] `projects/used_otp_codes.md` →
- [ ] `projects/user_feedback_form.md` →
- [ ] `projects/Website_Copy/alpha-box-copy.md` →
- [ ] `projects/Website_Copy/alpha_mode_select_copy.md` →
- [ ] `projects/Website_Copy/carousel_copy.md` →
- [ ] `projects/Website_Copy/faqs.md` →
- [ ] `projects/Website_Copy/fte-copy.md` →
- [ ] `projects/Website_Copy/tutorials_copy.md` →

## projects/Z-Completed (14) — completed-project archive; candidates for quick confirm-and-keep or delete

- [ ] `projects/Z-Completed/Championship Announce.html` →
- [ ] `projects/Z-Completed/Fast_Break_Refactor.md` →
- [ ] `projects/Z-Completed/Movement_Rate_Refactor.md` →
- [ ] `projects/Z-Completed/Parallel_Franchise_CPU_Sims_and_Week_Finalization_Work_Plan.md` →
- [ ] `projects/Z-Completed/Playbooks_Tutorial_Brief.md` →
- [ ] `projects/Z-Completed/README.md` →
- [ ] `projects/Z-Completed/SFX_Brief.md` →
- [ ] `projects/Z-Completed/SFX_Manager_Implementation.md` →
- [ ] `projects/Z-Completed/Scouting Link Options.html` →
- [ ] `projects/Z-Completed/Scouting_Tutorial_Brief.md` →
- [ ] `projects/Z-Completed/Sound_Design_Update.md` →
- [ ] `projects/Z-Completed/Tutorial Alert Modal.html` →
- [ ] `projects/Z-Completed/eligible_players_bug.md` →
- [ ] `projects/Z-Completed/training-tutorial-brief.md` →

## projects/scouting-tutorial-reference-files (7) — reference assets for the scouting tutorial

- [ ] `projects/scouting-tutorial-reference-files/Scouting.html` →
- [ ] `projects/scouting-tutorial-reference-files/assets/gob-nav.js` →
- [ ] `projects/scouting-tutorial-reference-files/assets/gob-tutorial.css` →
- [ ] `projects/scouting-tutorial-reference-files/assets/scouting/play-usage.png` →
- [ ] `projects/scouting-tutorial-reference-files/assets/scouting/roster-attributes.png` →
- [ ] `projects/scouting-tutorial-reference-files/assets/scouting/season-stats.png` →
- [ ] `projects/scouting-tutorial-reference-files/assets/scouting/starting-five.png` →

---

*`projects/_documentation_sweep.md` (this file) is excluded from the review count.*
