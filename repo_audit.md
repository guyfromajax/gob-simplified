# Repository audit: standalone desktop migration

Audit date: 2026-07-30  
Scope: runtime application source in `BackEnd/` and `FrontEnd/`. Tests, generated
team-roster pages, documentation, binary/media assets, `node_modules`, caches, and
build/performance artifacts are excluded from the source tree. Backend route/query
parameters are mapped in Section 4; Section 3 focuses on browser-location coupling.
No application code was changed for this audit.

## 1. Stack & entry points

### Stack

| Layer | Finding | Evidence |
|---|---|---|
| Frontend | Vanilla HTML, CSS, and JavaScript; no React/Vue/Svelte framework | `package.json` has no runtime frontend dependencies |
| Game renderer | Phaser **3.60.0**, loaded as a browser script | `FrontEnd/static/court.html` |
| Routing | Static multi-page navigation through `.html` URLs; no routing library | `netlify.toml`, page scripts using `window.location.href` |
| Frontend build | No compilation/bundling; Netlify publishes `FrontEnd/static` directly | `netlify.toml`: `publish = "FrontEnd/static"` |
| JavaScript modules | Mix of classic scripts/IIFEs and native ES modules | `FrontEnd/static/js/phaser/bootGame.js` and shared scripts |
| Backend | FastAPI served by Uvicorn; FastAPI/Uvicorn versions are unpinned | `requirements.txt`, `Procfile`, `start.sh` |
| Database | MongoDB through PyMongo | `BackEnd/db.py`, `requirements.txt` |
| Communication | JSON REST over `fetch`; no GraphQL, WebSocket, or SSE runtime found | Frontend `fetch`/`fetchJSON` call sites and FastAPI decorators |
| Hosting | Netlify frontend plus Railway backend | `netlify.toml`, `railway.json` |

The only Node dependency is Playwright (`@playwright/test ^1.40.0`), used for
browser tests rather than application runtime. No package lock establishes a
frontend framework runtime.

### Entry points

- Frontend public entry: `FrontEnd/static/homepage.html`, with `/` rewritten to it
  by `netlify.toml`.
- Authenticated hub: `FrontEnd/static/mode-select.html` +
  `FrontEnd/static/mode-select.js`.
- Franchise hub: `FrontEnd/static/franchise-command-center.html` +
  `FrontEnd/static/franchise-command-center.js`.
- Game flow: `set-lineup.html` → `game-plan.html` → `court.html`; the court imports
  `FrontEnd/static/js/phaser/bootGame.js`, which creates
  `FrontEnd/static/js/phaser/gameScene.js`.
- Backend process: `start.sh`/`Procfile` run
  `uvicorn BackEnd.api.api:app`.
- FastAPI bootstrap: `BackEnd/api/_bootstrap.py` creates `app`; route and middleware
  registration occurs in `BackEnd/api/api.py`.
- Backend routing: decorators in `BackEnd/api/api.py` plus routers imported from
  `BackEnd/api/*_routes.py` and registered with `app.include_router(...)`.

There is no central frontend route table. The effective route configuration is
distributed across static page filenames, `window.location` assignments, and the
Netlify redirects:

```toml
[build]
  publish = "FrontEnd/static"
[[redirects]]
  from = "/"
  to = "/homepage.html"
  status = 200
```

Local development differs from production: `BackEnd/api/api.py` mounts
`FrontEnd/static` under `/static` and redirects root-relative asset/page requests
to that prefix; production expects Netlify to serve them.

## 2. Full file tree (source only)

Descriptions are ten words or fewer. Generated `FrontEnd/static/team-roster/*`,
test files/directories, and media/vendor binaries are intentionally excluded.

### `BackEnd/`

- `BackEnd/__init__.py` — Implements init backend support.
- `BackEnd/api/_bootstrap.py` — Defines bootstrap HTTP routes.
- `BackEnd/api/admin_routes.py` — Defines admin routes HTTP routes.
- `BackEnd/api/alpha_feedback_routes.py` — Defines alpha feedback routes HTTP routes.
- `BackEnd/api/api.py` — FastAPI application, middleware, simulation, and game endpoints.
- `BackEnd/api/auth_routes.py` — Defines auth routes HTTP routes.
- `BackEnd/api/community_highlights_routes.py` — Defines community highlights routes HTTP routes.
- `BackEnd/api/email_routes.py` — Defines email routes HTTP routes.
- `BackEnd/api/feedback_routes.py` — Defines feedback routes HTTP routes.
- `BackEnd/api/franchise_routes.py` — Defines franchise routes HTTP routes.
- `BackEnd/api/gameplan_routes.py` — Defines gameplan routes HTTP routes.
- `BackEnd/api/leaderboard_routes.py` — Defines leaderboard routes HTTP routes.
- `BackEnd/api/play_routes.py` — Defines play routes HTTP routes.
- `BackEnd/api/player_image_routes.py` — Defines player image routes HTTP routes.
- `BackEnd/api/pointer_validation_routes.py` — Defines pointer validation routes HTTP routes.
- `BackEnd/api/press_conference_routes.py` — Defines press conference routes HTTP routes.
- `BackEnd/api/skeleton_routes.py` — Defines skeleton routes HTTP routes.
- `BackEnd/api/tournament_routes.py` — Defines tournament routes HTTP routes.
- `BackEnd/api/training_routes.py` — Defines training routes HTTP routes.
- `BackEnd/constants/__init__.py` — Defines init values.
- `BackEnd/constants/announcement_constants.py` — Defines announcement constants values.
- `BackEnd/constants/computer_game_constants.py` — Defines computer game constants values.
- `BackEnd/constants/dead_ball_fumble_constants.py` — Defines dead ball fumble constants values.
- `BackEnd/constants/eog_attr_bands.py` — Defines eog attr bands values.
- `BackEnd/constants/fast_break_constants.py` — Defines fast break constants values.
- `BackEnd/constants/fast_break_play_types.py` — Defines fast break play types values.
- `BackEnd/constants/fcp_press_play_types.py` — Defines fcp press play types values.
- `BackEnd/constants/flss_sfx.py` — Defines flss sfx values.
- `BackEnd/constants/hct_trap_play_types.py` — Defines hct trap play types values.
- `BackEnd/constants/momentum.py` — Defines momentum values.
- `BackEnd/constants/multi_franchise.py` — Defines multi franchise values.
- `BackEnd/constants/shot_micro_movements_constants.py` — Defines shot micro movements constants values.
- `BackEnd/constants/shot_threshold_scale.py` — Defines shot threshold scale values.
- `BackEnd/constants/shot_variants.py` — Defines shot variants values.
- `BackEnd/constants/team_builder_budget.py` — Defines team builder budget values.
- `BackEnd/data/__init__.py` — Implements init backend support.
- `BackEnd/data/names/__init__.py` — Implements init backend support.
- `BackEnd/data/tutorial_rosters.py` — Implements tutorial rosters backend support.
- `BackEnd/db.py` — MongoDB connection, collections, indexes, and database helpers.
- `BackEnd/engine/__init__.py` — Implements init simulation logic.
- `BackEnd/engine/after_steal_drive_integration.py` — Implements after steal drive integration simulation logic.
- `BackEnd/engine/after_steal_fast_break.py` — Implements after steal fast break simulation logic.
- `BackEnd/engine/after_steal_fast_break_step_emitter.py` — Implements after steal fast break step emitter simulation logic.
- `BackEnd/engine/after_steal_transition_positioning.py` — Implements after steal transition positioning simulation logic.
- `BackEnd/engine/attack_drive_clearance.py` — Implements attack drive clearance simulation logic.
- `BackEnd/engine/covert_release.py` — Implements covert release simulation logic.
- `BackEnd/engine/covert_release_drive_integration.py` — Implements covert release drive integration simulation logic.
- `BackEnd/engine/covert_release_step_emitter.py` — Implements covert release step emitter simulation logic.
- `BackEnd/engine/cutoff_resolution.py` — Implements cutoff resolution simulation logic.
- `BackEnd/engine/dead_ball_fumble.py` — Implements dead ball fumble simulation logic.
- `BackEnd/engine/dreb_fast_break_arming.py` — Implements dreb fast break arming simulation logic.
- `BackEnd/engine/dreb_step_emitter.py` — Implements dreb step emitter simulation logic.
- `BackEnd/engine/dynamic_fcp.py` — Implements dynamic fcp simulation logic.
- `BackEnd/engine/dynamic_fcp_step_emitter.py` — Implements dynamic fcp step emitter simulation logic.
- `BackEnd/engine/dynamic_hct.py` — Implements dynamic hct simulation logic.
- `BackEnd/engine/dynamic_hct_shot.py` — Implements dynamic hct shot simulation logic.
- `BackEnd/engine/dynamic_hct_step_emitter.py` — Implements dynamic hct step emitter simulation logic.
- `BackEnd/engine/eoq_debug_log.py` — Implements eoq debug log simulation logic.
- `BackEnd/engine/eoq_perfection.py` — Implements eoq perfection simulation logic.
- `BackEnd/engine/fast_break_trigger.py` — Implements fast break trigger simulation logic.
- `BackEnd/engine/fb_drive_resolution.py` — Implements fb drive resolution simulation logic.
- `BackEnd/engine/fb_drive_step_emitter.py` — Implements fb drive step emitter simulation logic.
- `BackEnd/engine/fb_outlet_pass_step_emitter.py` — Implements fb outlet pass step emitter simulation logic.
- `BackEnd/engine/fb_step_state.py` — Implements fb step state simulation logic.
- `BackEnd/engine/fb_stop_decision.py` — Implements fb stop decision simulation logic.
- `BackEnd/engine/fb_terminal_announce.py` — Implements fb terminal announce simulation logic.
- `BackEnd/engine/fb_uess_debug.py` — Implements fb uess debug simulation logic.
- `BackEnd/engine/fcp_inbound_release.py` — Implements fcp inbound release simulation logic.
- `BackEnd/engine/fcp_offball_attack.py` — Implements fcp offball attack simulation logic.
- `BackEnd/engine/fcp_pf_c_zone.py` — Implements fcp pf c zone simulation logic.
- `BackEnd/engine/fcp_press_plays.py` — Implements fcp press plays simulation logic.
- `BackEnd/engine/fcp_step_trace.py` — Implements fcp step trace simulation logic.
- `BackEnd/engine/final_turn_pacing.py` — Implements final turn pacing simulation logic.
- `BackEnd/engine/ft_step_emitter.py` — Implements ft step emitter simulation logic.
- `BackEnd/engine/hct_step_emitter.py` — Implements hct step emitter simulation logic.
- `BackEnd/engine/hct_trap_plays.py` — Implements hct trap plays simulation logic.
- `BackEnd/engine/motion_freelance.py` — Implements motion freelance simulation logic.
- `BackEnd/engine/motion_read_map.py` — Implements motion read map simulation logic.
- `BackEnd/engine/motion_step_decision.py` — Implements motion step decision simulation logic.
- `BackEnd/engine/motion_subtle.py` — Implements motion subtle simulation logic.
- `BackEnd/engine/oreb_step_emitter.py` — Implements oreb step emitter simulation logic.
- `BackEnd/engine/over_and_back.py` — Implements over and back simulation logic.
- `BackEnd/engine/pass_contest.py` — Implements pass contest simulation logic.
- `BackEnd/engine/phase_resolution.py` — Implements phase resolution simulation logic.
- `BackEnd/engine/pressure_step_state.py` — Implements pressure step state simulation logic.
- `BackEnd/engine/rendered_contest.py` — Implements rendered contest simulation logic.
- `BackEnd/engine/rim_runner_drive_integration.py` — Implements rim runner drive integration simulation logic.
- `BackEnd/engine/rim_runner_fast_break.py` — Implements rim runner fast break simulation logic.
- `BackEnd/engine/rim_runner_step_emitter.py` — Implements rim runner step emitter simulation logic.
- `BackEnd/engine/shot_micro_movements.py` — Implements shot micro movements simulation logic.
- `BackEnd/engine/skeleton_step_emitter.py` — Implements skeleton step emitter simulation logic.
- `BackEnd/engine/steal_fast_break_routing.py` — Implements steal fast break routing simulation logic.
- `BackEnd/engine/step_state.py` — Implements step state simulation logic.
- `BackEnd/engine/triangle_step_emitter.py` — Implements triangle step emitter simulation logic.
- `BackEnd/eog_attr_rules.py` — Implements eog attr rules backend support.
- `BackEnd/flask_app.py` — Implements flask app backend support.
- `BackEnd/main.py` — Core simulation initialization and quarter execution.
- `BackEnd/models/__init__.py` — Implements init domain model.
- `BackEnd/models/animator.py` — Implements animator domain model.
- `BackEnd/models/franchise_manager.py` — Implements franchise manager domain model.
- `BackEnd/models/game_manager.py` — Implements game manager domain model.
- `BackEnd/models/logger.py` — Implements logger domain model.
- `BackEnd/models/pgpc_snapshot.py` — Implements pgpc snapshot domain model.
- `BackEnd/models/play_manager.py` — Implements play manager domain model.
- `BackEnd/models/playbook_manager.py` — Implements playbook manager domain model.
- `BackEnd/models/player.py` — Implements player domain model.
- `BackEnd/models/recruit_sets.py` — Implements recruit sets domain model.
- `BackEnd/models/shot_manager.py` — Implements shot manager domain model.
- `BackEnd/models/team_manager.py` — Implements team manager domain model.
- `BackEnd/models/training_execution_v2.py` — Implements training execution v2 domain model.
- `BackEnd/models/training_manager.py` — Implements training manager domain model.
- `BackEnd/models/training_notes.py` — Implements training notes domain model.
- `BackEnd/models/turn_manager.py` — Implements turn manager domain model.
- `BackEnd/opening_lineup_snapshot.py` — Implements opening lineup snapshot backend support.
- `BackEnd/pgpc_context.py` — Implements pgpc context backend support.
- `BackEnd/pgpc_player_slot.py` — Implements pgpc player slot backend support.
- `BackEnd/pgpc_qualification.py` — Implements pgpc qualification backend support.
- `BackEnd/pgpc_selection.py` — Implements pgpc selection backend support.
- `BackEnd/pgpc_snapshot_storage.py` — Implements pgpc snapshot storage backend support.
- `BackEnd/pgpc_template_substitution.py` — Implements pgpc template substitution backend support.
- `BackEnd/playcall_skeletons/attack_skeletons.py` — Implements attack skeletons backend support.
- `BackEnd/playcall_skeletons/base_skeletons.py` — Implements base skeletons backend support.
- `BackEnd/playcall_skeletons/fcp_skeletons.py` — Implements fcp skeletons backend support.
- `BackEnd/playcall_skeletons/freelance_skeletons.py` — Implements freelance skeletons backend support.
- `BackEnd/playcall_skeletons/hct_skeletons.py` — Implements hct skeletons backend support.
- `BackEnd/playcall_skeletons/inside_skeletons.py` — Implements inside skeletons backend support.
- `BackEnd/playcall_skeletons/outside_skeletons copy.py` — Implements outside skeletons copy backend support.
- `BackEnd/playcall_skeletons/outside_skeletons.py` — Implements outside skeletons backend support.
- `BackEnd/playcall_skeletons/set_play_skeletons.py` — Implements set play skeletons backend support.
- `BackEnd/practice_squad/__init__.py` — Implements init backend support.
- `BackEnd/practice_squad/constants.py` — Implements constants backend support.
- `BackEnd/practice_squad/manager.py` — Implements manager backend support.
- `BackEnd/practice_squad/roster.py` — Implements roster backend support.
- `BackEnd/practice_squad/schedule.py` — Implements schedule backend support.
- `BackEnd/practice_squad/sim.py` — Implements sim backend support.
- `BackEnd/practice_squad/stats.py` — Implements stats backend support.
- `BackEnd/run.py` — Implements run backend support.
- `BackEnd/season/schedule_generator.py` — Implements schedule generator backend support.
- `BackEnd/season/season_manager.py` — Implements season manager backend support.
- `BackEnd/season/standings_tracker.py` — Implements standings tracker backend support.
- `BackEnd/services/__init__.py` — Implements init backend support.
- `BackEnd/services/r2_images.py` — Implements r2 images backend support.
- `BackEnd/services/recruit_image.py` — Implements recruit image backend support.
- `BackEnd/tournament/bracket_engine.py` — Implements bracket engine backend support.
- `BackEnd/tournament/bracket_logic.py` — Implements bracket logic backend support.
- `BackEnd/tournament/eos_tournament.py` — Implements eos tournament backend support.
- `BackEnd/tournament/franchise_tournament.py` — Implements franchise tournament backend support.
- `BackEnd/tournament/franchise_tournament_progression.py` — Implements franchise tournament progression backend support.
- `BackEnd/tournament/match_scheduler.py` — Implements match scheduler backend support.
- `BackEnd/tournament/tournament_manager.py` — Implements tournament manager backend support.
- `BackEnd/utils/__init__.py` — Provides init backend helpers.
- `BackEnd/utils/alpha_access_email.py` — Provides alpha access email backend helpers.
- `BackEnd/utils/alpha_otp_service.py` — Provides alpha otp service backend helpers.
- `BackEnd/utils/animation_step_helpers.py` — Provides animation step helpers backend helpers.
- `BackEnd/utils/animation_step_schema.py` — Provides animation step schema backend helpers.
- `BackEnd/utils/archetype_tracking.py` — Provides archetype tracking backend helpers.
- `BackEnd/utils/around_the_league.py` — Provides around the league backend helpers.
- `BackEnd/utils/auth.py` — Provides auth backend helpers.
- `BackEnd/utils/coaching_archetype.py` — Provides coaching archetype backend helpers.
- `BackEnd/utils/command_center_data.py` — Provides command center data backend helpers.
- `BackEnd/utils/community_highlights.py` — Provides community highlights backend helpers.
- `BackEnd/utils/cpu_playbook_customization.py` — Provides cpu playbook customization backend helpers.
- `BackEnd/utils/cpu_week_pool.py` — Provides cpu week pool backend helpers.
- `BackEnd/utils/db_utils.py` — Provides db utils backend helpers.
- `BackEnd/utils/debug_flags.py` — Provides debug flags backend helpers.
- `BackEnd/utils/defense_identity.py` — Provides defense identity backend helpers.
- `BackEnd/utils/defense_utils.py` — Provides defense utils backend helpers.
- `BackEnd/utils/email_sender.py` — Provides email sender backend helpers.
- `BackEnd/utils/email_suppression.py` — Provides email suppression backend helpers.
- `BackEnd/utils/energy_system.py` — Provides energy system backend helpers.
- `BackEnd/utils/eoq_clock_progression.py` — Provides eoq clock progression backend helpers.
- `BackEnd/utils/fast_break_shot_geometry.py` — Provides fast break shot geometry backend helpers.
- `BackEnd/utils/fb_geo_helpers.py` — Provides fb geo helpers backend helpers.
- `BackEnd/utils/fb_shot_logical_coords.py` — Provides fb shot logical coords backend helpers.
- `BackEnd/utils/franchise_championship_moments.py` — Provides franchise championship moments backend helpers.
- `BackEnd/utils/franchise_championships.py` — Provides franchise championships backend helpers.
- `BackEnd/utils/franchise_coaching_focus_counts.py` — Provides franchise coaching focus counts backend helpers.
- `BackEnd/utils/franchise_ftd_game_seed.py` — Provides franchise ftd game seed backend helpers.
- `BackEnd/utils/franchise_geek_points.py` — Provides franchise geek points backend helpers.
- `BackEnd/utils/franchise_rank_prestige.py` — Provides franchise rank prestige backend helpers.
- `BackEnd/utils/franchise_standings.py` — Provides franchise standings backend helpers.
- `BackEnd/utils/franchise_team_display.py` — Provides franchise team display backend helpers.
- `BackEnd/utils/franchise_training_state.py` — Provides franchise training state backend helpers.
- `BackEnd/utils/game_id_utils.py` — Provides game id utils backend helpers.
- `BackEnd/utils/game_summary_builder.py` — Provides game summary builder backend helpers.
- `BackEnd/utils/game_team_scoreboard_enrichment.py` — Provides game team scoreboard enrichment backend helpers.
- `BackEnd/utils/getback_selection.py` — Provides getback selection backend helpers.
- `BackEnd/utils/headless_simulation.py` — Provides headless simulation backend helpers.
- `BackEnd/utils/home_crowd.py` — Provides home crowd backend helpers.
- `BackEnd/utils/log_redact.py` — Provides log redact backend helpers.
- `BackEnd/utils/man_defense_matchups.py` — Provides man defense matchups backend helpers.
- `BackEnd/utils/opening_tip.py` — Provides opening tip backend helpers.
- `BackEnd/utils/otp_validator.py` — Provides otp validator backend helpers.
- `BackEnd/utils/ownership.py` — Provides ownership backend helpers.
- `BackEnd/utils/payload_builder.py` — Provides payload builder backend helpers.
- `BackEnd/utils/playbook_settings_utils.py` — Provides playbook settings utils backend helpers.
- `BackEnd/utils/playbook_weights_utils.py` — Provides playbook weights utils backend helpers.
- `BackEnd/utils/player_development.py` — Provides player development backend helpers.
- `BackEnd/utils/player_entry.py` — Provides player entry backend helpers.
- `BackEnd/utils/player_generation.py` — Provides player generation backend helpers.
- `BackEnd/utils/player_momentum.py` — Provides player momentum backend helpers.
- `BackEnd/utils/player_year.py` — Provides player year backend helpers.
- `BackEnd/utils/pointer_validation.py` — Provides pointer validation backend helpers.
- `BackEnd/utils/position_ratings.py` — Provides position ratings backend helpers.
- `BackEnd/utils/position_snapshot_ledger.py` — Provides position snapshot ledger backend helpers.
- `BackEnd/utils/press_conference_questions.py` — Provides press conference questions backend helpers.
- `BackEnd/utils/profiling.py` — Provides profiling backend helpers.
- `BackEnd/utils/quarter_start.py` — Provides quarter start backend helpers.
- `BackEnd/utils/quick_foul.py` — Provides quick foul backend helpers.
- `BackEnd/utils/rate_limiter.py` — Provides rate limiter backend helpers.
- `BackEnd/utils/reengagement_email.py` — Provides reengagement email backend helpers.
- `BackEnd/utils/repair_franchise_eos_bracket.py` — Provides repair franchise eos bracket backend helpers.
- `BackEnd/utils/resend_sender.py` — Provides resend sender backend helpers.
- `BackEnd/utils/reset_step_helper.py` — Provides reset step helper backend helpers.
- `BackEnd/utils/resolve_game_teams_slot_keys.py` — Provides resolve game teams slot keys backend helpers.
- `BackEnd/utils/roster_builder.py` — Provides roster builder backend helpers.
- `BackEnd/utils/roster_loader.py` — Provides roster loader backend helpers.
- `BackEnd/utils/scouting_utils.py` — Provides scouting utils backend helpers.
- `BackEnd/utils/season_momentum.py` — Provides season momentum backend helpers.
- `BackEnd/utils/shared.py` — Provides shared backend helpers.
- `BackEnd/utils/shared_defense.py` — Provides shared defense backend helpers.
- `BackEnd/utils/shot_attempt_geometry.py` — Provides shot attempt geometry backend helpers.
- `BackEnd/utils/shot_ball_arc.py` — Provides shot ball arc backend helpers.
- `BackEnd/utils/shot_clock_policy.py` — Provides shot clock policy backend helpers.
- `BackEnd/utils/shot_geometry.py` — Provides shot geometry backend helpers.
- `BackEnd/utils/shot_split_tracker.py` — Provides shot split tracker backend helpers.
- `BackEnd/utils/sim_profiler.py` — Provides sim profiler backend helpers.
- `BackEnd/utils/sim_random.py` — Provides sim random backend helpers.
- `BackEnd/utils/simulation_diagnostics.py` — Provides simulation diagnostics backend helpers.
- `BackEnd/utils/situational_logic.py` — Provides situational logic backend helpers.
- `BackEnd/utils/stat_updater.py` — Provides stat updater backend helpers.
- `BackEnd/utils/team_attr_scale.py` — Provides team attr scale backend helpers.
- `BackEnd/utils/team_builder_roster.py` — Provides team builder roster backend helpers.
- `BackEnd/utils/team_id_resolver.py` — Provides team id resolver backend helpers.
- `BackEnd/utils/team_play_utils.py` — Provides team play utils backend helpers.
- `BackEnd/utils/team_settings_manager.py` — Provides team settings manager backend helpers.
- `BackEnd/utils/team_slug.py` — Provides team slug backend helpers.
- `BackEnd/utils/team_stats_aggregator.py` — Provides team stats aggregator backend helpers.
- `BackEnd/utils/training_feed_lines.py` — Provides training feed lines backend helpers.
- `BackEnd/utils/training_loading_highlights.py` — Provides training loading highlights backend helpers.
- `BackEnd/utils/transition_analyzer.py` — Provides transition analyzer backend helpers.
- `BackEnd/utils/transition_bridge.py` — Provides transition bridge backend helpers.
- `BackEnd/utils/transition_event_detector.py` — Provides transition event detector backend helpers.
- `BackEnd/utils/transition_registry.py` — Provides transition registry backend helpers.
- `BackEnd/utils/transition_shot_board_crash.py` — Provides transition shot board crash backend helpers.
- `BackEnd/utils/transition_validator.py` — Provides transition validator backend helpers.
- `BackEnd/utils/tutorial_game.py` — Provides tutorial game backend helpers.
- `BackEnd/utils/uncontested_shot.py` — Provides uncontested shot backend helpers.
- `BackEnd/utils/used_otp_codes_markdown.py` — Provides used otp codes markdown backend helpers.
- `BackEnd/utils/user_game_commit.py` — Provides user game commit backend helpers.
- `BackEnd/utils/user_tracking.py` — Provides user tracking backend helpers.

### `FrontEnd/`

- `FrontEnd/app.js` — Controls app client behavior.
- `FrontEnd/games.html` — Renders games page.
- `FrontEnd/index_legacy.html` — Renders index legacy page.
- `FrontEnd/player.html` — Renders player page.
- `FrontEnd/roster.html` — Renders roster page.
- `FrontEnd/roster.js` — Controls roster client behavior.
- `FrontEnd/static/Playcall Center POC.html` — Renders Playcall Center POC page.
- `FrontEnd/static/Recruiting Orders v2.html` — Renders Recruiting Orders v2 page.
- `FrontEnd/static/Tournament Tab.html` — Renders Tournament Tab page.
- `FrontEnd/static/account.html` — Renders account page.
- `FrontEnd/static/alpha-feedback.html` — Renders alpha feedback page.
- `FrontEnd/static/auth.css` — Styles auth interface.
- `FrontEnd/static/awards.html` — Renders awards page.
- `FrontEnd/static/awards.js` — Controls awards client behavior.
- `FrontEnd/static/box-score.css` — Styles box score interface.
- `FrontEnd/static/box-score.html` — Renders box score page.
- `FrontEnd/static/box-score.js` — Controls box score client behavior.
- `FrontEnd/static/bracket.js` — Controls bracket client behavior.
- `FrontEnd/static/brackets-page.js` — Controls brackets page client behavior.
- `FrontEnd/static/brackets.html` — Renders brackets page.
- `FrontEnd/static/coaching-archetypes-leaderboard.html` — Renders coaching archetypes leaderboard page.
- `FrontEnd/static/coaching-archetypes.html` — Renders coaching archetypes page.
- `FrontEnd/static/coaching-grid.css` — Styles coaching grid interface.
- `FrontEnd/static/coaching-grid.html` — Renders coaching grid page.
- `FrontEnd/static/coaching-grid.js` — Controls coaching grid client behavior.
- `FrontEnd/static/command-center-team-styles.css` — Styles command center team styles interface.
- `FrontEnd/static/common.js` — Provides shared formatting, navigation, and return-URL helpers.
- `FrontEnd/static/court (1).html` — Renders court (1) page.
- `FrontEnd/static/court.html` — Renders court page.
- `FrontEnd/static/css/attribute-tour.css` — Styles attribute tour interface.
- `FrontEnd/static/css/auth-bar.css` — Styles auth bar interface.
- `FrontEnd/static/css/big-news-modals.css` — Styles big news modals interface.
- `FrontEnd/static/css/button-font.css` — Styles button font interface.
- `FrontEnd/static/css/coach-mark.css` — Styles coach mark interface.
- `FrontEnd/static/css/fonts.css` — Styles fonts interface.
- `FrontEnd/static/css/gob-advanced.css` — Styles gob advanced interface.
- `FrontEnd/static/css/gob-buttons.css` — Styles gob buttons interface.
- `FrontEnd/static/css/gob-tutorial.css` — Styles gob tutorial interface.
- `FrontEnd/static/css/playbook-cmd.css` — Styles playbook cmd interface.
- `FrontEnd/static/css/playbook-tiles.css` — Styles playbook tiles interface.
- `FrontEnd/static/css/rt-buckets.css` — Styles rt buckets interface.
- `FrontEnd/static/css/sammy-modal.css` — Styles sammy modal interface.
- `FrontEnd/static/css/team-picker.css` — Styles team picker interface.
- `FrontEnd/static/css/tutorial-lineup-modal.css` — Styles tutorial lineup modal interface.
- `FrontEnd/static/css/tutorial-persona-intro.css` — Styles tutorial persona intro interface.
- `FrontEnd/static/css/tutorial-progress.css` — Styles tutorial progress interface.
- `FrontEnd/static/css/tutorial-tipoff.css` — Styles tutorial tipoff interface.
- `FrontEnd/static/css/username-modal.css` — Styles username modal interface.
- `FrontEnd/static/cut-players.css` — Styles cut players interface.
- `FrontEnd/static/cut-players.html` — Renders cut players page.
- `FrontEnd/static/cut-players.js` — Controls cut players client behavior.
- `FrontEnd/static/defense-display.js` — Controls defense display client behavior.
- `FrontEnd/static/faqs.html` — Renders faqs page.
- `FrontEnd/static/fcc-tournament-style-a.js` — Controls fcc tournament style a client behavior.
- `FrontEnd/static/fcp-skeletons.html` — Renders fcp skeletons page.
- `FrontEnd/static/franchise-command-center.css` — Styles franchise command center interface.
- `FrontEnd/static/franchise-command-center.html` — Renders franchise command center page.
- `FrontEnd/static/franchise-command-center.js` — Controls franchise command center client behavior.
- `FrontEnd/static/franchise-select-team.css` — Styles franchise select team interface.
- `FrontEnd/static/franchise-select-team.html` — Renders franchise select team page.
- `FrontEnd/static/franchise-select-team.js` — Controls franchise select team client behavior.
- `FrontEnd/static/franchise-tournament-brackets-render.js` — Controls franchise tournament brackets render client behavior.
- `FrontEnd/static/game-plan.css` — Styles game plan interface.
- `FrontEnd/static/game-plan.html` — Renders game plan page.
- `FrontEnd/static/game-plan.js` — Controls game plan client behavior.
- `FrontEnd/static/game-plans.html` — Renders game plans page.
- `FrontEnd/static/hct-skeletons.html` — Renders hct skeletons page.
- `FrontEnd/static/homepage-backup.html` — Renders homepage backup page.
- `FrontEnd/static/homepage-v2.css` — Styles homepage v2 interface.
- `FrontEnd/static/homepage-v2.js` — Controls homepage v2 client behavior.
- `FrontEnd/static/homepage-v3-source.html` — Renders homepage v3 source page.
- `FrontEnd/static/homepage-v3.css` — Styles homepage v3 interface.
- `FrontEnd/static/homepage-v3.html` — Renders homepage v3 page.
- `FrontEnd/static/homepage-v3.js` — Controls homepage v3 client behavior.
- `FrontEnd/static/homepage.css` — Styles homepage interface.
- `FrontEnd/static/homepage.html` — Renders homepage page.
- `FrontEnd/static/homepage.js` — Controls homepage client behavior.
- `FrontEnd/static/index.html` — Renders index page.
- `FrontEnd/static/js/config/api-config.js` — Resolves environment API URL and authentication headers.
- `FrontEnd/static/js/musicController.js` — Controls musicController client behavior.
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` — Implements AnimationEngine court animation.
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js` — Implements AnimationRouter court animation.
- `FrontEnd/static/js/phaser/animation/BallController.js` — Implements BallController court animation.
- `FrontEnd/static/js/phaser/animation/BallControllerAdapter.js` — Implements BallControllerAdapter court animation.
- `FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js` — Implements FreeThrowAnimationSystem court animation.
- `FrontEnd/static/js/phaser/animation/HCOAnimationSystem.js` — Implements HCOAnimationSystem court animation.
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js` — Implements PassAnimationSystem court animation.
- `FrontEnd/static/js/phaser/animation/ReboundAnimationSystem.js` — Implements ReboundAnimationSystem court animation.
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` — Implements ShotAnimationSystem court animation.
- `FrontEnd/static/js/phaser/animation/SimplifiedStateMachine.js` — Implements SimplifiedStateMachine court animation.
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` — Implements animateGameTurns court animation.
- `FrontEnd/static/js/phaser/animation/animateStep.js` — Implements animateStep court animation.
- `FrontEnd/static/js/phaser/animation/animationPlayback.js` — Implements animationPlayback court animation.
- `FrontEnd/static/js/phaser/animation/animationStepSchema.js` — Implements animationStepSchema court animation.
- `FrontEnd/static/js/phaser/animation/animationTimeline.js` — Implements animationTimeline court animation.
- `FrontEnd/static/js/phaser/animation/animationTimeline.stub.js` — Implements animationTimeline stub court animation.
- `FrontEnd/static/js/phaser/animation/animation_config.js` — Implements animation config court animation.
- `FrontEnd/static/js/phaser/animation/arrivalHeartbeat.js` — Implements arrivalHeartbeat court animation.
- `FrontEnd/static/js/phaser/animation/ballAnimationSimple.js` — Implements ballAnimationSimple court animation.
- `FrontEnd/static/js/phaser/animation/ballManager.js` — Implements ballManager court animation.
- `FrontEnd/static/js/phaser/animation/ballManager.stub.js` — Implements ballManager stub court animation.
- `FrontEnd/static/js/phaser/animation/ballTween.js` — Implements ballTween court animation.
- `FrontEnd/static/js/phaser/animation/batOobAnimation.js` — Implements batOobAnimation court animation.
- `FrontEnd/static/js/phaser/animation/benchEntry.js` — Implements benchEntry court animation.
- `FrontEnd/static/js/phaser/animation/countdownAnimation.js` — Implements countdownAnimation court animation.
- `FrontEnd/static/js/phaser/animation/courtClamp.js` — Implements courtClamp court animation.
- `FrontEnd/static/js/phaser/animation/courtConstants.js` — Implements courtConstants court animation.
- `FrontEnd/static/js/phaser/animation/createBallTrail.js` — Implements createBallTrail court animation.
- `FrontEnd/static/js/phaser/animation/debugStepLogger.js` — Implements debugStepLogger court animation.
- `FrontEnd/static/js/phaser/animation/drebOutletTargetResolver.js` — Implements drebOutletTargetResolver court animation.
- `FrontEnd/static/js/phaser/animation/dunkPlayback.js` — Implements dunkPlayback court animation.
- `FrontEnd/static/js/phaser/animation/fastBreak.js` — Implements fastBreak court animation.
- `FrontEnd/static/js/phaser/animation/fastBreakStateHelpers.js` — Implements fastBreakStateHelpers court animation.
- `FrontEnd/static/js/phaser/animation/flourishes.js` — Implements flourishes court animation.
- `FrontEnd/static/js/phaser/animation/freeThrow.js` — Implements freeThrow court animation.
- `FrontEnd/static/js/phaser/animation/generateBallTween.js` — Implements generateBallTween court animation.
- `FrontEnd/static/js/phaser/animation/onAction.js` — Implements onAction court animation.
- `FrontEnd/static/js/phaser/animation/openingTip.js` — Implements openingTip court animation.
- `FrontEnd/static/js/phaser/animation/outletUtils.js` — Implements outletUtils court animation.
- `FrontEnd/static/js/phaser/animation/passDetection.js` — Implements passDetection court animation.
- `FrontEnd/static/js/phaser/animation/pathKnotPlayback.js` — Implements pathKnotPlayback court animation.
- `FrontEnd/static/js/phaser/animation/playbackPause.js` — Implements playbackPause court animation.
- `FrontEnd/static/js/phaser/animation/possession/PossessionRunner.js` — Implements PossessionRunner court animation.
- `FrontEnd/static/js/phaser/animation/possession/normalizeTurn.js` — Implements normalizeTurn court animation.
- `FrontEnd/static/js/phaser/animation/runOutClock.js` — Implements runOutClock court animation.
- `FrontEnd/static/js/phaser/animation/timelinePolyfill.js` — Implements timelinePolyfill court animation.
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — Implements turnAnimation court animation.
- `FrontEnd/static/js/phaser/animation/turnPreparation.js` — Implements turnPreparation court animation.
- `FrontEnd/static/js/phaser/animation/turnoverAdapter.js` — Implements turnoverAdapter court animation.
- `FrontEnd/static/js/phaser/animation/unitCompletionContract.js` — Implements unitCompletionContract court animation.
- `FrontEnd/static/js/phaser/animation/validateStructure.js` — Implements validateStructure court animation.
- `FrontEnd/static/js/phaser/bootGame.js` — Bootstraps URL-driven game and server simulation lifecycle.
- `FrontEnd/static/js/phaser/constants/fastBreakConstants.js` — Defines fastBreakConstants values.
- `FrontEnd/static/js/phaser/constants/flssSfx.js` — Defines flssSfx values.
- `FrontEnd/static/js/phaser/finalizeGame.js` — Implements finalizeGame Phaser gameplay support.
- `FrontEnd/static/js/phaser/gameScene.js` — Runs Phaser court scene and turn-by-turn client flow.
- `FrontEnd/static/js/phaser/setup/createHeadshotMarkerV2.js` — Implements createHeadshotMarkerV2 Phaser gameplay support.
- `FrontEnd/static/js/phaser/setup/createPhaserPlayer.js` — Implements createPhaserPlayer Phaser gameplay support.
- `FrontEnd/static/js/phaser/setup/loadPhaserPlayers.js` — Implements loadPhaserPlayers Phaser gameplay support.
- `FrontEnd/static/js/phaser/setup/markerConfig.js` — Implements markerConfig Phaser gameplay support.
- `FrontEnd/static/js/phaser/setup/preloadPlayerHeadshots.js` — Implements preloadPlayerHeadshots Phaser gameplay support.
- `FrontEnd/static/js/phaser/setup/staminaRing.js` — Implements staminaRing Phaser gameplay support.
- `FrontEnd/static/js/phaser/state/gameStateMachine.js` — Implements gameStateMachine Phaser gameplay support.
- `FrontEnd/static/js/phaser/testScene.js` — Implements testScene Phaser gameplay support.
- `FrontEnd/static/js/phaser/ui/playcallCenter.js` — Implements playcallCenter Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/activePlayerDisplay.js` — Implements activePlayerDisplay Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/animationEndFromTurn.js` — Implements animationEndFromTurn Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/announcements.js` — Implements announcements Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/autosetLineupApi.js` — Implements autosetLineupApi Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/courtEntryResolver.js` — Implements courtEntryResolver Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/debug.js` — Implements debug Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/debugFlags.js` — Implements debugFlags Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/defenseMatchupsPopup.js` — Implements defenseMatchupsPopup Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/defenseUi.js` — Implements defenseUi Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/eoqDebugLog.js` — Implements eoqDebugLog Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/eventBus.js` — Implements eventBus Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/fbTelemetryDebug.js` — Implements fbTelemetryDebug Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/foulAnnouncementClassifier.js` — Implements foulAnnouncementClassifier Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/foulAnnouncementLanguage.js` — Implements foulAnnouncementLanguage Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/foulOutPopup.js` — Implements foulOutPopup Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js` — Implements franchisePhaseBClient Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/franchiseStartCpuSimsClient.js` — Implements franchiseStartCpuSimsClient Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/gameAnnouncements.js` — Implements gameAnnouncements Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/gameClock.js` — Implements gameClock Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` — Implements gameCompletionPopup Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/gameSfx.js` — Implements gameSfx Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/gameSpeedManager.js` — Implements gameSpeedManager Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/gridToPixels.js` — Implements gridToPixels Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/loadGameStats.js` — Implements loadGameStats Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/matchupsUiShared.js` — Implements matchupsUiShared Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/offenseTeamIdResolver.js` — Implements offenseTeamIdResolver Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/oobFcpHctCapture.js` — Implements oobFcpHctCapture Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/pgpcSammyReminderModal.js` — Implements pgpcSammyReminderModal Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/playcallDisplay.js` — Implements playcallDisplay Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/playerMovementDuration.js` — Implements playerMovementDuration Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/playerMovementSpeed.js` — Implements playerMovementSpeed Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/playerSpriteTweenPause.js` — Implements playerSpriteTweenPause Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/playerUtils.js` — Implements playerUtils Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/possessionManager.js` — Implements possessionManager Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/postGamePressConference.js` — Implements postGamePressConference Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/preGameExperience.js` — Implements preGameExperience Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/quarterEndAirhorn.js` — Implements quarterEndAirhorn Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/simGamePresentation.js` — Implements simGamePresentation Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/simTimelineAssembler.js` — Implements simTimelineAssembler Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/statusDisplay.js` — Implements statusDisplay Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/strategyBars.js` — Implements strategyBars Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/syncPlayerSpriteAttributes.js` — Implements syncPlayerSpriteAttributes Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/textScroll.js` — Implements textScroll Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` — Implements timeoutButtonManager Phaser gameplay support.
- `FrontEnd/static/js/phaser/utils/vibrantColors.js` — Implements vibrantColors Phaser gameplay support.
- `FrontEnd/static/js/shared/accessDenied.js` — Provides shared accessDenied browser helper.
- `FrontEnd/static/js/shared/adminGuard.js` — Provides shared adminGuard browser helper.
- `FrontEnd/static/js/shared/alphaBanner.js` — Provides shared alphaBanner browser helper.
- `FrontEnd/static/js/shared/alphaFeedbackModal.js` — Provides shared alphaFeedbackModal browser helper.
- `FrontEnd/static/js/shared/analytics.js` — Provides shared analytics browser helper.
- `FrontEnd/static/js/shared/archetypeBadge.js` — Provides shared archetypeBadge browser helper.
- `FrontEnd/static/js/shared/archetypeEvolutionModal.js` — Provides shared archetypeEvolutionModal browser helper.
- `FrontEnd/static/js/shared/archetypeReveal.js` — Provides shared archetypeReveal browser helper.
- `FrontEnd/static/js/shared/attributeTooltips.js` — Provides shared attributeTooltips browser helper.
- `FrontEnd/static/js/shared/attributeTour.js` — Provides shared attributeTour browser helper.
- `FrontEnd/static/js/shared/authBarInit.js` — Provides shared authBarInit browser helper.
- `FrontEnd/static/js/shared/authGuard.js` — Provides shared authGuard browser helper.
- `FrontEnd/static/js/shared/bigNewsModals.js` — Provides shared bigNewsModals browser helper.
- `FrontEnd/static/js/shared/captureBootstrap.js` — Provides shared captureBootstrap browser helper.
- `FrontEnd/static/js/shared/captureControls.js` — Provides shared captureControls browser helper.
- `FrontEnd/static/js/shared/captureCourt.js` — Provides shared captureCourt browser helper.
- `FrontEnd/static/js/shared/captureDom.js` — Provides shared captureDom browser helper.
- `FrontEnd/static/js/shared/captureUtils.js` — Provides shared captureUtils browser helper.
- `FrontEnd/static/js/shared/championshipMoments.js` — Provides shared championshipMoments browser helper.
- `FrontEnd/static/js/shared/coachMark.js` — Provides shared coachMark browser helper.
- `FrontEnd/static/js/shared/commandCenterTabs.js` — Provides shared commandCenterTabs browser helper.
- `FrontEnd/static/js/shared/errorHandler.js` — Provides shared errorHandler browser helper.
- `FrontEnd/static/js/shared/franchiseLocalStorage.js` — Provides shared franchiseLocalStorage browser helper.
- `FrontEnd/static/js/shared/getGameMode.js` — Provides shared getGameMode browser helper.
- `FrontEnd/static/js/shared/gobPlayerAttributes.js` — Provides shared gobPlayerAttributes browser helper.
- `FrontEnd/static/js/shared/gobTutorialAlertResume.js` — Provides shared gobTutorialAlertResume browser helper.
- `FrontEnd/static/js/shared/gobTutorialAlerts.js` — Provides shared gobTutorialAlerts browser helper.
- `FrontEnd/static/js/shared/gobTutorialHub.js` — Provides shared gobTutorialHub browser helper.
- `FrontEnd/static/js/shared/gobTutorialNav.js` — Provides shared gobTutorialNav browser helper.
- `FrontEnd/static/js/shared/gtm-loader.js` — Provides shared gtm loader browser helper.
- `FrontEnd/static/js/shared/maintenanceBanner.js` — Provides shared maintenanceBanner browser helper.
- `FrontEnd/static/js/shared/pageLoadOverlay.js` — Provides shared pageLoadOverlay browser helper.
- `FrontEnd/static/js/shared/playbookTeamId.js` — Provides shared playbookTeamId browser helper.
- `FrontEnd/static/js/shared/playerYear.js` — Provides shared playerYear browser helper.
- `FrontEnd/static/js/shared/pointerValidation.js` — Provides shared pointerValidation browser helper.
- `FrontEnd/static/js/shared/potg.js` — Provides shared potg browser helper.
- `FrontEnd/static/js/shared/regionByeModal.js` — Provides shared regionByeModal browser helper.
- `FrontEnd/static/js/shared/resourceCache.js` — Provides shared resourceCache browser helper.
- `FrontEnd/static/js/shared/rosterLoader.js` — Provides shared rosterLoader browser helper.
- `FrontEnd/static/js/shared/rosterStatsRenderer.js` — Provides shared rosterStatsRenderer browser helper.
- `FrontEnd/static/js/shared/rtBucket.js` — Provides shared rtBucket browser helper.
- `FrontEnd/static/js/shared/sammyModal.js` — Provides shared sammyModal browser helper.
- `FrontEnd/static/js/shared/scoutingReport.js` — Provides shared scoutingReport browser helper.
- `FrontEnd/static/js/shared/sentryInit.js` — Provides shared sentryInit browser helper.
- `FrontEnd/static/js/shared/stateTelemetry.js` — Provides shared stateTelemetry browser helper.
- `FrontEnd/static/js/shared/teamCoachAsset.js` — Provides shared teamCoachAsset browser helper.
- `FrontEnd/static/js/shared/teamGeneratedArt.js` — Provides shared teamGeneratedArt browser helper.
- `FrontEnd/static/js/shared/teamPicker.js` — Provides shared teamPicker browser helper.
- `FrontEnd/static/js/shared/teamShotThresholdScale.js` — Provides shared teamShotThresholdScale browser helper.
- `FrontEnd/static/js/shared/teamStatsTable.js` — Provides shared teamStatsTable browser helper.
- `FrontEnd/static/js/shared/tierEmblem.js` — Provides shared tierEmblem browser helper.
- `FrontEnd/static/js/shared/timeoutNavigationHelper.js` — Provides shared timeoutNavigationHelper browser helper.
- `FrontEnd/static/js/shared/tutorialLineupModals.js` — Provides shared tutorialLineupModals browser helper.
- `FrontEnd/static/js/shared/tutorialProgressThread.js` — Provides shared tutorialProgressThread browser helper.
- `FrontEnd/static/js/shared/usernameModal.js` — Provides shared usernameModal browser helper.
- `FrontEnd/static/js/state/gameStore.js` — Controls gameStore client behavior.
- `FrontEnd/static/js/utils/attributeDisplay.js` — Controls attributeDisplay client behavior.
- `FrontEnd/static/js/utils/courtPositions.js` — Controls courtPositions client behavior.
- `FrontEnd/static/js/vendor/html2canvas.min.js` — Controls html2canvas min client behavior.
- `FrontEnd/static/leaders.html` — Renders leaders page.
- `FrontEnd/static/leaders.js` — Controls leaders client behavior.
- `FrontEnd/static/login.html` — Renders login page.
- `FrontEnd/static/maintenance.html` — Renders maintenance page.
- `FrontEnd/static/mode-select.css` — Styles mode select interface.
- `FrontEnd/static/mode-select.html` — Renders mode select page.
- `FrontEnd/static/mode-select.js` — Controls mode select client behavior.
- `FrontEnd/static/news.html` — Renders news page.
- `FrontEnd/static/news.js` — Controls news client behavior.
- `FrontEnd/static/play-builder-v2.html` — Renders play builder v2 page.
- `FrontEnd/static/play-builder.html` — Renders play builder page.
- `FrontEnd/static/play-details.html` — Renders play details page.
- `FrontEnd/static/playbook-report.css` — Styles playbook report interface.
- `FrontEnd/static/playbook-report.html` — Renders playbook report page.
- `FrontEnd/static/playbook-report.js` — Controls playbook report client behavior.
- `FrontEnd/static/playbooks.css` — Styles playbooks interface.
- `FrontEnd/static/playbooks.html` — Renders playbooks page.
- `FrontEnd/static/playbooks.js` — Controls playbooks client behavior.
- `FrontEnd/static/player-attributes.html` — Renders player attributes page.
- `FrontEnd/static/player-detail.css` — Styles player detail interface.
- `FrontEnd/static/player-detail.html` — Renders player detail page.
- `FrontEnd/static/player-detail.js` — Controls player detail client behavior.
- `FrontEnd/static/plays-builder.html` — Renders plays builder page.
- `FrontEnd/static/practice-squad-bracket.html` — Renders practice squad bracket page.
- `FrontEnd/static/practice-squad-bracket.js` — Controls practice squad bracket client behavior.
- `FrontEnd/static/practice-squad-standings.html` — Renders practice squad standings page.
- `FrontEnd/static/practice-squad-standings.js` — Controls practice squad standings client behavior.
- `FrontEnd/static/rankings.html` — Renders rankings page.
- `FrontEnd/static/recruiting-common.js` — Controls recruiting common client behavior.
- `FrontEnd/static/recruiting-dock.css` — Styles recruiting dock interface.
- `FrontEnd/static/recruiting-hub.js` — Controls recruiting hub client behavior.
- `FrontEnd/static/recruiting-invites.html` — Renders recruiting invites page.
- `FrontEnd/static/recruiting-invites.js` — Controls recruiting invites client behavior.
- `FrontEnd/static/recruiting-lean-ladder.css` — Styles recruiting lean ladder interface.
- `FrontEnd/static/recruiting-orders.html` — Renders recruiting orders page.
- `FrontEnd/static/recruiting-orders.js` — Controls recruiting orders client behavior.
- `FrontEnd/static/recruiting-results-hub.css` — Styles recruiting results hub interface.
- `FrontEnd/static/recruiting-results.html` — Renders recruiting results page.
- `FrontEnd/static/recruiting-results.js` — Controls recruiting results client behavior.
- `FrontEnd/static/recruiting-signing.css` — Styles recruiting signing interface.
- `FrontEnd/static/recruiting-spine-data.js` — Controls recruiting spine data client behavior.
- `FrontEnd/static/recruiting-spine-gallery.html` — Renders recruiting spine gallery page.
- `FrontEnd/static/recruiting-spine.css` — Styles recruiting spine interface.
- `FrontEnd/static/recruiting-spine.js` — Controls recruiting spine client behavior.
- `FrontEnd/static/recruiting.css` — Styles recruiting interface.
- `FrontEnd/static/recruiting.html` — Renders recruiting page.
- `FrontEnd/static/recruiting.js` — Controls recruiting client behavior.
- `FrontEnd/static/reset-password.html` — Renders reset password page.
- `FrontEnd/static/resource-pages.css` — Styles resource pages interface.
- `FrontEnd/static/schedule.html` — Renders schedule page.
- `FrontEnd/static/scouting-report.css` — Styles scouting report interface.
- `FrontEnd/static/scouting.html` — Renders scouting page.
- `FrontEnd/static/scrimmage-select.html` — Renders scrimmage select page.
- `FrontEnd/static/set-lineup.css` — Styles set lineup interface.
- `FrontEnd/static/set-lineup.html` — Renders set lineup page.
- `FrontEnd/static/set-lineup.js` — Controls set lineup client behavior.
- `FrontEnd/static/signup.html` — Renders signup page.
- `FrontEnd/static/standings.html` — Renders standings page.
- `FrontEnd/static/stats.css` — Styles stats interface.
- `FrontEnd/static/stats.html` — Renders stats page.
- `FrontEnd/static/team-attributes.html` — Renders team attributes page.
- `FrontEnd/static/team-builder.css` — Styles team builder interface.
- `FrontEnd/static/team-builder.html` — Renders team builder page.
- `FrontEnd/static/team-builder.js` — Controls team builder client behavior.
- `FrontEnd/static/team-roster-view.html` — Renders team roster view page.
- `FrontEnd/static/team-roster-view.js` — Controls team roster view client behavior.
- `FrontEnd/static/team-select.js` — Controls team select client behavior.
- `FrontEnd/static/team-stats.html` — Renders team stats page.
- `FrontEnd/static/team-stats.js` — Controls team stats client behavior.
- `FrontEnd/static/team-traits.html` — Renders team traits page.
- `FrontEnd/static/tournament-select.css` — Styles tournament select interface.
- `FrontEnd/static/tournament-select.html` — Renders tournament select page.
- `FrontEnd/static/tournament-select.js` — Controls tournament select client behavior.
- `FrontEnd/static/tournament.css` — Styles tournament interface.
- `FrontEnd/static/tournament.html` — Renders tournament page.
- `FrontEnd/static/tournament.js` — Controls tournament client behavior.
- `FrontEnd/static/training-playbooks.css` — Styles training playbooks interface.
- `FrontEnd/static/training-playbooks.html` — Renders training playbooks page.
- `FrontEnd/static/training-playbooks.js` — Controls training playbooks client behavior.
- `FrontEnd/static/training-report.css` — Styles training report interface.
- `FrontEnd/static/training-report.html` — Renders training report page.
- `FrontEnd/static/training-report.js` — Controls training report client behavior.
- `FrontEnd/static/training-squad-report.html` — Renders training squad report page.
- `FrontEnd/static/training-squad-report.js` — Controls training squad report client behavior.
- `FrontEnd/static/training.css` — Styles training interface.
- `FrontEnd/static/training.html` — Renders training page.
- `FrontEnd/static/training.js` — Controls training client behavior.
- `FrontEnd/static/tutorial-advanced-momentum.html` — Renders tutorial advanced momentum page.
- `FrontEnd/static/tutorial-advanced-practice-squads.html` — Renders tutorial advanced practice squads page.
- `FrontEnd/static/tutorial-advanced-press-trap.html` — Renders tutorial advanced press trap page.
- `FrontEnd/static/tutorial-game-plans.html` — Renders tutorial game plans page.
- `FrontEnd/static/tutorial-persona-intro.html` — Renders tutorial persona intro page.
- `FrontEnd/static/tutorial-persona-intro.js` — Controls tutorial persona intro client behavior.
- `FrontEnd/static/tutorial-playbooks.html` — Renders tutorial playbooks page.
- `FrontEnd/static/tutorial-player-attributes.html` — Renders tutorial player attributes page.
- `FrontEnd/static/tutorial-recruiting.html` — Renders tutorial recruiting page.
- `FrontEnd/static/tutorial-scouting.html` — Renders tutorial scouting page.
- `FrontEnd/static/tutorial-situation.html` — Renders tutorial situation page.
- `FrontEnd/static/tutorial-situation.js` — Controls tutorial situation client behavior.
- `FrontEnd/static/tutorial-team-attributes.html` — Renders tutorial team attributes page.
- `FrontEnd/static/tutorial-training.html` — Renders tutorial training page.
- `FrontEnd/static/tutorial.html` — Renders tutorial page.
- `FrontEnd/style.css` — Styles style interface.

## 3. URL-coupling audit — priority

### Scope and conclusion

This is not merely URL-based navigation. The browser query string is a
cross-page state container and, in the live-game flow, a partial persistence and
resume protocol. It carries:

- database pointers: `game_id`, `franchise_id`, `team_id`, `home_id`, `away_id`;
- mode/context: `mode`, `my_team`, `user_team_id`, `week`;
- game state: `quarter`, `period`, `clock`, scores, possession/inbound flags;
- lineups: side-prefixed `*_pg`, `*_sg`, `*_sf`, `*_pf`, `*_c`;
- resume state: `active_resume`, `resume_from_anchor`, `consume_resume_anchor`,
  `anchor_type`, `resume_from_timeout`, `timeout_trace_id`,
  `quarter_break_from`, `lineup_checkpoint`;
- cross-page continuation: `return_url`, `return_tab`, `next_url`, `from`;
- auth/session actions: `redirect`, password-reset `token`;
- tutorial/debug controls: `tut_alert`, `debug_pc`, `debug_scoreboard`,
  `debug_music`, `debug_sfx`, and related flags.

Ordinary links that only navigate to a fixed page are excluded. Backend API
path/query inputs are covered by the endpoint map in Section 4.

### Persistence

#### `FrontEnd/static/js/phaser/bootGame.js`

Resume state is written back into the URL and later re-read after reload/hops.

```js
const params = new URLSearchParams(window.location.search);
params.set('quarter', String(resumeQuarter));
params.set('period', periodLabel);
params.set('resume_from_timeout', resumeState.resume_from_timeout ? 'true' : 'false');
params.set('resume_from_anchor', 'true');
if (resumeState.clock) params.set('clock', resumeState.clock);
history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`);
```

#### `FrontEnd/static/js/shared/timeoutNavigationHelper.js`

This serializes the current game checkpoint across lineup, game-plan, and court
pages, including lineup, score, clock, IDs, and resume flags.

```js
if (gameId) {
  if (window.StateTelemetry) {
    window.StateTelemetry.logStateWrite('game_id', window.StateTelemetry.SOURCE_TYPES.URL, gameId, 'timeoutNavigationHelper.js');
  }
  params.set('game_id', gameId);
}
```

#### `FrontEnd/static/set-lineup.js`

The URL is mutated after server initialization and when one-shot resume markers
are consumed.

```js
const currentParams = new URLSearchParams(window.location.search);
currentParams.set('locked_exhausted_user_lineup', 'true');
['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
  currentParams.set(`${myTeamSide}_${pos.toLowerCase()}`, lineup[pos]);
});
history.replaceState(null, '',
  `${window.location.pathname}?${currentParams.toString()}`);
```

#### `FrontEnd/static/js/phaser/gameScene.js`

Quit/resume and quarter transitions preserve a URL assembled from current live
game state; single-game resume also stores the resulting pointer locally.

```js
if (resumeFromTimeout && urlParams.get('resume_from_anchor') !== 'true') {
  const futureParams = new URLSearchParams(window.location.search);
  futureParams.set('resume_from_timeout', 'false');
  if (typeof history !== 'undefined' && history.replaceState) {
    history.replaceState(null, '',
      `${window.location.pathname}?${futureParams.toString()}`);
  }
}
```

#### `FrontEnd/static/common.js`

`return_url` preserves a complete path/query/hash continuation between pages.

```js
function getCurrentRelativeUrl() {
  return `${window.location.pathname}${window.location.search}${window.location.hash || ''}`;
}
```

#### `FrontEnd/static/js/shared/gobTutorialAlerts.js`

Tutorial alert state is carried in `tut_alert` and consumed with
`history.replaceState`, making the URL a one-shot persistence channel.

```js
var params = new URLSearchParams(window.location.search);
var franchiseId = params.get('franchise_id');
var evt = params.get('tut_alert');
if (evt) {
  params.delete('tut_alert');
  var qs = params.toString();
  var next = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
  try { history.replaceState(null, '', next); } catch (e) {}
}
```

Other persistence participants:

- `FrontEnd/static/js/phaser/utils/loadGameStats.js` — reads resume markers and
  `game_id` to restore the authoritative server snapshot.
- `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` — serializes timeout
  game state into the lineup URL.
- `FrontEnd/static/js/shared/errorHandler.js` — rebuilds recovery URLs from the
  failing page's complete game context.
- `FrontEnd/static/box-score.js` — carries `post_game_phase_b`, game/week IDs, and
  return context through post-game completion.
- `FrontEnd/static/mode-select.js` — reconstructs active game resume URLs from
  server data.

### Navigation/routing

#### `FrontEnd/static/js/shared/authGuard.js`

The pathname decides whether the current screen is public and captures a return
route for login.

```js
var token = typeof localStorage !== "undefined" ? localStorage.getItem("auth_token") : null;
if (!token) {
  var redirectParam = encodeURIComponent(logicalPath + (window.location.search || ""));
  window.location.replace("/login.html?redirect=" + redirectParam);
}
```

#### `FrontEnd/static/js/shared/commandCenterTabs.js`

The `tab` query parameter selects a command-center view rather than merely
changing the address.

```js
var urlParams = new URLSearchParams(window.location.search);
var activeTab = urlParams.get('tab') || defaultTab;
function updateUrl(tabName) {
  var newUrl = new URL(window.location);
  newUrl.searchParams.set('tab', tabName);
  window.history.pushState({}, '', newUrl);
}
```

#### `FrontEnd/static/js/phaser/utils/courtEntryResolver.js`

Resume flags determine which court boot path executes.

```js
if (get('active_resume') === 'true') return COLD_RESUME_ENTRY;
if (get('resume_from_anchor') === 'true') {
  return ANCHOR_RESTORE_ENTRY;
}
if (get('resume_from_timeout') === 'true') {
  return TIMEOUT_DIRECT_ENTRY;
}
```

#### Redirect/compatibility pages

- `FrontEnd/static/recruiting-orders.html` and
  `FrontEnd/static/recruiting-invites.html` forward selected query state to
  `recruiting.html`.
- `FrontEnd/static/tournament.html` redirects to `mode-select.html`; its associated
  legacy `tournament.js` still contains URL-driven behavior.
- `FrontEnd/static/js/shared/gobTutorialNav.js` uses pathname/hash to classify
  tutorial pages and activate sections.
- `FrontEnd/static/coaching-archetypes-leaderboard.html` uses `document.referrer`
  as an internal return route.
- `FrontEnd/static/team-roster-view.js` uses `return_url`, `return_tab`, mode, and
  IDs to decide its data source and back destination.

### Caching

#### `FrontEnd/static/js/shared/resourceCache.js`

The cache itself uses page/franchise/season/week keys. Pages commonly source the
franchise/week components from the URL, indirectly making URL context part of the
cache identity.

```js
function createResourceCache(page, franchiseId, season, week) {
  function key(scopeKey) {
    return ['resource', page, franchiseId || '', season || '',
      week || '', scopeKey || 'default'].join(':');
  }
}
```

#### `FrontEnd/static/js/shared/maintenanceBanner.js`

A query parameter forces every poll to bypass HTTP caches.

```js
function fetchConfig() {
  var url = CONFIG_URL + "?t=" + nowMs();
  return fetch(url, { cache: "no-store" });
}
```

#### `FrontEnd/static/game-plan.html`

Hostname selects local/remote static behavior; a query suffix cache-busts the
dynamically injected game-plan script.

```js
const isLocalhost = window.location.hostname === 'localhost'
  || window.location.hostname === '127.0.0.1';
script.src = `${API_CONFIG.getStaticPath()}/game-plan.js?v=${cacheBuster}`;
```

### State container

#### `FrontEnd/static/js/phaser/bootGame.js`

This module explicitly treats URL values as required pointers and source of
truth.

```js
const queryFranchiseId = urlParams.get('franchise_id');
const urlMode = urlParams.get('mode');
const franchiseId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('franchise_id', queryFranchiseId || null) : (queryFranchiseId || null);
```

#### `FrontEnd/static/game-plan.js`

The selected lineup is read directly from URL parameters and forwarded into
gameplay.

```js
const currentUrlParams = new URLSearchParams(window.location.search);
const currentQuarter = parseInt(currentUrlParams.get('quarter'), 10) || 1;
const currentGameId = helper.getGameId(currentUrlParams);
const resumeFromTimeout = helper.getResumeFromTimeout(currentUrlParams);
const currentMyTeamSide = currentUrlParams.get('my_team');
const currentMode = currentUrlParams.get('mode') || 'single';
```

#### `FrontEnd/static/set-lineup.js`

Team identity, mode, quarter, game pointer, scores, clock, and checkpoint flags
all originate in the query string.

```js
const weekParam = urlParams.get('week');
const tournamentId = window.StateTelemetry ? window.StateTelemetry.logUrlRead('tournament_id', urlParams.get('tournament_id')) : urlParams.get('tournament_id');
const modeParam = urlParams.get('mode');
const DEBUG = urlParams.has('debug');
const quarter = parseInt(urlParams.get('quarter'), 10) || 1;
```

#### `FrontEnd/static/js/shared/franchiseLocalStorage.js`

The URL franchise pointer namespaces persistent local cache entries.

```js
function resolveFranchiseIdFromUrl(search) {
  var q = new URLSearchParams(search || window.location.search);
  return q.get('franchise_id') || null;
}
function key(franchiseId, field) {
  return `franchise:${franchiseId}:${field}`;
}
```

#### Feature pages using URL as primary context

| File | Load-bearing values and effect |
|---|---|
| `FrontEnd/static/franchise-command-center.js` | `franchise_id`, `team_id`, `mode`, `next_url`, `from`, `story` select franchise state and modal/view flow |
| `FrontEnd/static/box-score.js` | `game_id`, mode, team/franchise/week IDs, post-game flags select data and completion behavior |
| `FrontEnd/static/playbook-report.js` | game/team/franchise context selects playbook and next-game behavior |
| `FrontEnd/static/playbooks.js` | mode, team/game/franchise, `play_id`, `from`, `backTo` select editable playbook |
| `FrontEnd/static/player-detail.js` | `id`/`recruit_id`, mode, franchise/game select endpoint and portrait context |
| `FrontEnd/static/team-roster-view.js` | mode plus team/franchise/PS identifiers select roster provider |
| `FrontEnd/static/training.js` | franchise/team/week/session type select training workflow |
| `FrontEnd/static/training-report.js` | mode, franchise/team/week select report and return flow |
| `FrontEnd/static/training-playbooks.js` | mode/team/franchise/session select training playbook state |
| `FrontEnd/static/recruiting-common.js` | franchise/team/recruit IDs and return URL provide hub-wide context |
| `FrontEnd/static/recruiting-orders.js` | franchise/team/session select orders and submissions |
| `FrontEnd/static/recruiting-invites.js` | franchise/team/session select invite workflow |
| `FrontEnd/static/recruiting-results.js` | `week` selects displayed signing results |
| `FrontEnd/static/leaders.js` | franchise/team select leaderboard scope |
| `FrontEnd/static/news.js` | franchise/team/story select news dataset and story |
| `FrontEnd/static/schedule.html` | franchise/team select schedule |
| `FrontEnd/static/standings.html` | franchise/team select standings and roster links |
| `FrontEnd/static/stats.html` | franchise/team and view scope select statistics |
| `FrontEnd/static/team-stats.js` | franchise/team select statistics |
| `FrontEnd/static/team-traits.html` | franchise/team and scope select trait data |
| `FrontEnd/static/rankings.html` | franchise/team/national select ranking mode |
| `FrontEnd/static/practice-squad-standings.js` | franchise/team select PS schedule and standings |
| `FrontEnd/static/practice-squad-bracket.js` | franchise/team select PS bracket |
| `FrontEnd/static/brackets-page.js` | franchise/team/return URL select bracket and back route |
| `FrontEnd/static/cut-players.js` | franchise/team/mode/next URL select roster mutation flow |
| `FrontEnd/static/team-builder.js` | `home_slot` selects which franchise slot receives imported team |
| `FrontEnd/static/franchise-select-team.js` | tutorial mode and `home_slot` select creation path |
| `FrontEnd/static/team-select.js` | `my_team`/`user_team_id` determine controlled side |
| `FrontEnd/static/play-details.html` | play identity plus game/team context select play and back flow |
| `FrontEnd/static/scouting.html` | inherited URL context selects opponent scouting report |
| `FrontEnd/static/tournament.js` | legacy tournament/team/game values select tournament state |

### Auth/session context

#### `FrontEnd/static/login.html`

The `redirect` query value determines the post-login destination.

```js
localStorage.setItem('auth_token', data.token);
const urlParams = new URLSearchParams(window.location.search);
const redirectUrl = urlParams.get('redirect') || '/mode-select.html';
window.location.href = redirectUrl;
```

Unlike `getSafeReturnUrl`, this excerpt does not validate same-origin or require a
relative path before assignment. That is both desktop-migration and open-redirect
risk.

#### `FrontEnd/static/reset-password.html`

The password-reset bearer credential is transported in the URL.

```js
const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');
if (token) {
  document.getElementById('set-section').style.display = 'block';
}
```

#### `FrontEnd/static/js/config/api-config.js`

Authentication itself is in `localStorage`, but hostname chooses the backend
security boundary and query `franchise_id` supplies multi-slot identity.

```js
const hostname = window.location.hostname;
const baseUrl = this._resolveBaseUrl(hostname);
```

The token is separately sourced for every authenticated request:

```js
getAuthHeaders() {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null;
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}
```

Also involved: `FrontEnd/static/js/shared/adminGuard.js`,
`accessDenied.js`, `authBarInit.js`, and `authGuard.js` combine pathname,
stored token/user data, and login redirect URLs.

### Other load-bearing URL use

#### Environment/backend selection

`FrontEnd/static/js/config/api-config.js` maps browser hostname to hardcoded
production/staging Railway APIs. A `file://` or desktop custom protocol has no
defined mapping and falls into the local/default branch.

```js
if (hostname.includes('.railway.app') || hostname.includes('.netlify.app')) {
  if (hostname.includes('staging') || hostname.includes('test')) {
    return 'https://gob-simplified-staging.up.railway.app';
  }
}
```

#### Debug and feature switches

The following URL flags change runtime behavior, logging, animation, or server
payloads rather than simple navigation:

- `debug_pc`/`debug_playcall`: `court.html`, `bootGame.js`, `gameScene.js`,
  `playbookTeamId.js`.
- `debug_scoreboard`: `gameScene.js`.
- `debug_music`: `js/musicController.js`.
- `debug_sfx`: `js/phaser/utils/gameSfx.js`.
- `debug_shot_variant`: `ShotAnimationSystem.js`.
- `debug_oob`: `animationPlayback.js`.
- `profile`: `bootGame.js`, `franchise-select-team.js`,
  `tournament-select.js`.

#### Hash/path-driven UI

- `FrontEnd/static/js/shared/gobTutorialNav.js` uses `location.pathname` to
  classify tutorial pages and `location.hash`/`history.replaceState` to select
  tutorial sections.
- `FrontEnd/static/js/shared/archetypeEvolutionModal.js` and
  `gobTutorialAlerts.js` only activate on the command-center pathname.
- `FrontEnd/static/js/shared/gtm-loader.js` suppresses analytics on selected
  hostnames.
- `FrontEnd/static/js/shared/maintenanceBanner.js` changes polling/display based
  on pathname and a remote configuration file.

### Complete URL-coupled file index

This index covers files that read browser path/query/hash/referrer or rewrite
history. It omits files that only assign a fixed `window.location.href`.

| Area | Files |
|---|---|
| Core game state | `set-lineup.js`, `game-plan.js`, `box-score.js`, `court.html`, `court (1).html`, `js/phaser/bootGame.js`, `js/phaser/gameScene.js`, `js/phaser/finalizeGame.js`, `js/phaser/utils/loadGameStats.js`, `timeoutButtonManager.js`, `foulOutPopup.js`, `gameCompletionPopup.js`, `defenseMatchupsPopup.js`, `playcallCenter.js` |
| Shared URL/state infrastructure | `common.js`, `js/shared/timeoutNavigationHelper.js`, `courtEntryResolver.js`, `getGameMode.js`, `playbookTeamId.js`, `pointerValidation.js`, `errorHandler.js`, `franchiseLocalStorage.js`, `stateTelemetry.js` |
| Franchise/resource pages | `franchise-command-center.js`, `franchise-select-team.js`, `cut-players.js`, `leaders.js`, `news.js`, `playbook-report.js`, `playbooks.js`, `player-detail.js`, `team-roster-view.js`, `team-stats.js`, `training.js`, `training-report.js`, `training-playbooks.js`, `training-squad-report.js` |
| Inline page controllers | `rankings.html`, `schedule.html`, `standings.html`, `stats.html`, `team-traits.html`, `player-attributes.html`, `team-attributes.html`, `scouting.html`, `game-plans.html`, `play-details.html` |
| Recruiting/PS/brackets | `recruiting-common.js`, `recruiting-orders.js`, `recruiting-invites.js`, `recruiting-results.js`, redirect HTML counterparts, `practice-squad-standings.js`, `practice-squad-bracket.js`, `brackets-page.js` |
| Auth/account | `login.html`, `reset-password.html`, `js/shared/authGuard.js`, `adminGuard.js`, `accessDenied.js`, `authBarInit.js` |
| Tutorial/modals | `gobTutorialAlerts.js`, `gobTutorialAlertResume.js`, `gobTutorialNav.js`, `commandCenterTabs.js`, `bigNewsModals.js`, `regionByeModal.js`, `archetypeReveal.js`, `archetypeEvolutionModal.js` |
| Environment/debug | `js/config/api-config.js`, `js/musicController.js`, `maintenanceBanner.js`, `gtm-loader.js`, `ShotAnimationSystem.js`, `animationPlayback.js`, `gameSfx.js`, `captureCourt.js` |
| Legacy/prototype | `FrontEnd/app.js`, `FrontEnd/player.html`, `tournament.js`, `tournament-select.js`, `coaching-archetypes*.html` |

### High-risk multi-category hotspots

Files appearing in three or more categories:

1. `FrontEnd/static/js/phaser/bootGame.js` — persistence, routing, state
   container, caching/environment, debug.
2. `FrontEnd/static/js/phaser/gameScene.js` — persistence, routing, state
   container, debug, server orchestration.
3. `FrontEnd/static/set-lineup.js` — persistence, routing, state container,
   caching, server initialization.
4. `FrontEnd/static/game-plan.js` — persistence, routing, state container,
   caching/debug.
5. `FrontEnd/static/box-score.js` — persistence, routing, state container,
   post-game server workflow.
6. `FrontEnd/static/common.js` — persistence, routing, state container, safe
   return handling.
7. `FrontEnd/static/js/config/api-config.js` — auth/session, environment routing,
   configuration caching.
8. `FrontEnd/static/franchise-command-center.js` — routing, state container,
   persistence bridge, server orchestration.

## 4. Server-dependency map

### Runtime API organization

The frontend talks to FastAPI exclusively through REST/JSON `fetch` calls.
`API_CONFIG.buildUrl()` supplies a remote origin based on browser hostname.
There are no WebSocket, GraphQL, or EventSource runtime channels.

“Incidental online” means the current implementation requires HTTP/MongoDB, but
the feature is fundamentally local/single-player and could be bundled with a
local process/database. “Inherent online” means its purpose depends on a remote
service or shared users.

| Feature/module | Frontend files | Required endpoints | Dependency |
|---|---|---|---|
| Authentication/account | `login.html`, `signup.html`, `account.html`, auth shared scripts | `/api/auth/config`, `/request-access-code`, `/signup`, `/login`, `/me`, `/account-settings`, `/logout`, `/reset-request`, `/reset-password` | Inherent online under current accounts/email model |
| Community/leaderboards | `mode-select.js`, coaching leaderboard | `/api/community/highlights`, `/api/community/around-the-league`, `/api/community/debut`, `/api/leaderboard/by-team`, `/api/leaderboard/by-archetype`, `/api/auth/leaderboard` | Inherent online |
| Feedback/analytics | shared auth bar, feedback pages | `/api/feedback`, `/api/alpha-feedback`, auth prompt-seen endpoints; Sentry/GTM external calls | Inherent online |
| Email/unsubscribe/OTP | auth pages | `/unsubscribe`, auth access-code/reset endpoints | Inherent online |
| Remote portraits | API config/shared image helpers | `/player-image/ensure`, `/recruit-image/ensure`; backend R2/S3 service | Online unless assets are bundled/generated locally |
| App/maintenance configuration | global scripts | `/app-config`, static `maintenance.json` polling | Incidental except live maintenance control |
| Team/roster catalog | selection and roster pages | `/teams`, `/roster/{team}`, `/player/{id}`, `/teams/{id}/players` | Incidental online |
| Single-game creation | `set-lineup.js`, tutorial | `/api/autoset-lineup`, `/api/init-game` | Incidental online; **single-player blocking round-trip** |
| Live single-player simulation | `bootGame.js`, `gameScene.js` | `/api/simulate`, `/api/simulate-quarter`, `/api/simulate-turn` | Incidental online; **single-player blocking round-trip every turn/quarter** |
| Game hydration/resume | court, lineup, box score | `/api/game/{game_id}`, `/resume-state`, `/ft-lock`, `/playbook-settings`, `/lineup-for-matchups`, `/api/validate-pointer` | Incidental online; **single-player blocking round-trip** |
| In-game coaching | court utilities | `/api/set-playcall-override`, `/api/call-timeout`, `/api/save-man-defense-matchups` | Incidental online; **single-player blocking round-trip** |
| Game-plan/playbooks | game-plan/playbooks pages | `/api/gameplan` GET/PUT, `/api/playbooks` GET/POST, `/preview-shot-weights` | Incidental online |
| User-created plays | play builder/details | `/api/plays` GET/POST, `/api/plays/{id}` GET/DELETE, `/api/play/{name}` | Incidental online |
| Franchise creation/listing | mode/select pages | `/franchise/list`, `/current`, `/select-team`, `/team-builder/*`, `/franchise/{id}` | Incidental online |
| Franchise command center | `franchise-command-center.js` | `/franchise/command-center/data`, `/state`, `/standings`, `/roster`, `/teams` | Incidental online |
| Franchise game/week | command center, court, box score | `/play-next-game`, `/save-result`, `/complete-week`, `/phase-a`, `/start-cpu-sims`, `/phase-b` | Incidental online; **single-player progression blocking** |
| Franchise schedule/stats | standings/schedule/stats/leaders pages | `/standings`, `/schedule`, `/schedule/national`, `/leaders`, `/team-stats`, `/team-traits`, `/team-player-stats` | Incidental online |
| Recruiting | recruiting hub scripts | `/recruiting-data`, `/recruiting-orders`, `/recruiting-results`, `/run-week-35-recruiting`, `/recruits`, `/recruit/{id}` | Incidental online |
| Training | `training.js`, reports/playbooks | `/training-points`, `/run-training/user`, `/run-training/cpu-train`, `/training-report`, `/training-squad-reports`, `/api/run_training` | Incidental online |
| Roster cuts | `cut-players.js` | `/cut-players`, `/cut-players-final` | Incidental online |
| Practice squad | PS pages | `/practice-squad/standings`, `/schedule`, `/brackets`, `/team` | Incidental online |
| Franchise tournaments/EOS | command center/brackets | `/sim-rest-of-tournament`, `/sim-championship`, `/finish-season`, championship moments endpoints | Incidental online |
| Post-game press conference | court utilities | `/franchise/press-conference/session`, `/{session_id}/answer`, `/complete` | Incidental online unless responses become community-visible |
| Legacy tournament mode | `tournament.js`, team roster fallback | `/tournament/start`, `/state`, `/command-center/data`, `/team-stats`, `/save-result`, `/simulate-round`, `/sim-remaining`, `/run-training` | Incidental but apparently sunset/legacy |
| Admin/diagnostics | admin/debug/test pages | `/api/admin/reset-user-state`, `/api/diagnostics/*`, skeleton endpoints | Development/operations only |

### Single-player server-round-trip blockers

The standalone migration cannot be solved only by replacing auth and cloud
persistence. The basketball engine executes in Python on the backend:

1. `set-lineup.js` calls `/api/init-game` before entering the court.
2. `bootGame.js` fetches game state, rosters, playbooks, and game plans.
3. `gameScene.js` calls `/api/simulate-turn` during interactive play and
   `/api/simulate-quarter` for quarter simulation.
4. Timeout, matchup, substitution, and resume actions write/read the server game
   document.
5. Finalization and franchise week advancement require multiple backend
   persistence phases.

The most direct desktop architecture is therefore not a JavaScript-only port:
bundle the Python engine and expose it through an in-process bridge or loopback
service, then replace MongoDB/cloud services with a local persistence adapter.
Reimplementing the engine in JavaScript would be a separate, much larger effort.

### External services beyond the API

- MongoDB Atlas: all persistent game/franchise/auth data (`BackEnd/db.py`).
- Cloudflare R2/S3 API: generated player/recruit portraits
  (`BackEnd/services/r2_images.py`, `recruit_image.py`).
- Resend/email HTTP services: access, reset, and re-engagement email helpers.
- Google Fonts: linked by most HTML pages.
- Google Tag Manager: `js/shared/gtm-loader.js` and `<noscript>` tags.
- Sentry: frontend and FastAPI error reporting.
- Netlify/Railway domain routing and CORS allowlists.

## 5. Local-persistence readiness

### Current persistence layers

| Layer | Current use | Desktop readiness |
|---|---|---|
| MongoDB | Users, teams, players, games, franchise state, FTD/FPD/FRD, plays, playbooks, training, recruiting | Primary save system; requires local adapter/embedded DB |
| URL query string | Identity pointers, lineups, quarter/clock/scores, resume flags, return routes, tutorial/debug state | High migration risk; should become explicit application/navigation state |
| `localStorage` | JWT/user, namespaced franchise context, last game/box score, audio/settings, tutorial/UI dismissals, legacy tournament state | Available in Electron/Tauri webview, but not a robust save-file system |
| `sessionStorage` | resource cache, training playbook selection, matchup/pregame suppression, one-shot animation flags | Ephemeral; lost across desktop process/session boundaries |
| In-memory JS | Phaser scene, page controllers, `Map` caches | Lost on reload/process exit |
| Backend memory | `ongoing_games` and simulation objects | Not durable; backed/reconstructed from Mongo game documents |
| Browser downloads | Team Builder CSV template/error/roster export through `Blob` + synthetic anchor | Export only, not general save/load |

Representative local persistence:

```js
const token = localStorage.getItem('auth_token');
sessionStorage.setItem(cacheKey, JSON.stringify(value));
localStorage.setItem(`franchise:${id}:week`, String(week));
```

### Save/load readiness verdict

- There is **no general file-based game save/load system**.
- There is no IndexedDB, SQLite, Electron store, Tauri filesystem plugin, File
  System Access API, or native save-dialog integration.
- Team Builder supports CSV download/upload-like workflows, but that is content
  import/export rather than application persistence.
- Persistence is not literally 100% server/URL-driven because browser storage
  holds auth, preferences, caches, and resume conveniences. Authoritative game,
  franchise, roster, training, and recruiting state is server/MongoDB-driven.
- Existing serialization is useful: game/franchise state already crosses a JSON
  REST boundary. That provides schemas to target for a local repository layer.
- A desktop save system needs atomic local writes, schema versioning/migrations,
  slot enumeration, backup/recovery, and removal of JWT/URL pointers as the
  primary identity mechanism.

## 6. Packaging signals

### Existing desktop packaging

None found. There is no Electron, Tauri, Neutralino, NW.js, electron-builder,
Electron Forge, or desktop manifest/configuration. `package.json` only defines
Playwright tests. Current packaging is Netlify static hosting plus Railway
Uvicorn deployment.

### Browser/hosting assumptions

- Heavy reliance on `window`, `document`, `location`, `history`,
  `localStorage`, `sessionStorage`, `alert`, `confirm`, and synthetic anchors.
- Native ES-module imports use root-relative `/js/...` and `/images/...` URLs;
  these do not naturally work under `file://`.
- `API_CONFIG` selects API origin from `window.location.hostname` and contains
  hardcoded Railway/custom-domain URLs.
- Local development checks only `localhost`/`127.0.0.1`.
- FastAPI production CORS explicitly allows Netlify/custom web origins and
  localhost ports; a desktop custom scheme or packaged origin is absent.
- FastAPI static mounting is conditional on `ENVIRONMENT == development`;
  production assumes Netlify.
- Most pages load Google Fonts and GTM remotely; offline presentation will differ
  unless fonts/scripts are bundled or disabled.
- Sentry initialization and maintenance polling assume network access.
- Auth assumes a bearer JWT in `localStorage` attached to HTTP calls.
- Portraits may be lazily generated/fetched through R2.
- Phaser 3.60.0 is loaded from browser-facing scripts and expects DOM/WebGL/Web
  Audio. Electron supports those; Tauri/webview support must be verified across
  target OS/GPU/audio stacks.
- Browser security functions matter in a desktop shell: unrestricted
  `window.location.href` from login `redirect` and links to remote origins must
  not gain native-shell privileges.

## Top 10 riskiest coupling points

1. **`FrontEnd/static/js/phaser/bootGame.js`** — URL parameters bootstrap nearly
   all identity, checkpoint, and resume behavior.
2. **`FrontEnd/static/js/phaser/gameScene.js`** — interactive single-player play
   requires repeated server simulation and persistence calls.
3. **`FrontEnd/static/js/shared/timeoutNavigationHelper.js`** — serializes a
   large implicit game-state schema into navigation URLs.
4. **`FrontEnd/static/set-lineup.js`** — bridges URL state, server-created game
   IDs, lineups, resume anchors, and court entry.
5. **`FrontEnd/static/game-plan.js`** — treats the mutable URL as the canonical
   lineup/game pointer between screens.
6. **`BackEnd/api/api.py`** — combines application bootstrap, HTTP API, live game
   orchestration, Mongo persistence, and simulation endpoints.
7. **`BackEnd/api/franchise_routes.py`** — enormous server-side aggregate for
   franchise saves, weeks, training, recruiting, games, and EOS.
8. **`FrontEnd/static/box-score.js`** — couples final display to multi-phase
   franchise completion and server persistence.
9. **`FrontEnd/static/js/config/api-config.js`** — hostname-driven hardcoded
   cloud routing and JWT HTTP assumptions lack a desktop origin.
10. **`BackEnd/db.py` plus direct collection imports** — broad MongoDB coupling
    prevents swapping in a local save repository at one boundary.
