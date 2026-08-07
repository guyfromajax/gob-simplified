# Team Builder — current-state inventory (source material)

**Date:** 2026-08-07  
**Purpose:** Flat, checkable inventory for writing the master document. Not the master.  
**Legend:** `verified` = claim confirmed by reading code in this pass. `unverified` = from docs/plan only. `finding` = code/doc disagreement or unexpected state. `artefact` = looks unintentional or leftover.

Format per claim:  
`- [status] claim — path::symbol`

---

## 1. Behavioural rules

### Identity resolution

- [verified] Overlay lives on franchise document field `team_builder` only (not FTD) — `BackEnd/utils/franchise_team_display.py::TEAM_BUILDER_FIELD`
- [verified] Overlay written only at Apply — `BackEnd/api/franchise_routes.py::team_builder_apply`
- [verified] Display resolve: if team ObjectId equals overlay `replaced_object_id`, return overlay identity/colours/court; else pass through core team — `franchise_team_display.py::resolve_team_display`
- [verified] Read overlay helper — `franchise_team_display.py::get_team_builder_overlay`
- [verified] Abbr uniqueness at Apply checked against `abbr_from_name` of all other core teams — `franchise_routes.py::team_builder_apply`
- [verified] After Apply, franchise `user_team_id` and FPD `meta.team` baked to custom name — `franchise_routes.py::team_builder_apply`
- [verified] Identity write helper for Mongo updates — `franchise_team_display.py::apply_overlay_to_identity_writes`
- [verified] Name→ObjectId resolution for FTD when display name is custom overlay name — `BackEnd/api/api.py` (name resolve block ~871)

### Chrome hydration gate

- [verified] Session visual state: `_activeTeamBuilderVisual` + `_tbVisualReady` — `FrontEnd/static/js/shared/common.js`
- [verified] Hydrate from franchise payload — `common.js::hydrateTeamBuilderVisualFromFranchisePayload`
- [verified] Lazy network hydrate via `GET /franchise/command-center/data?franchise_id=&profile=1` — `common.js::ensureTeamBuilderVisualReady`
- [verified] League chrome map: await visual ready, then `GET /teams?franchise_id=`, index 128 programs — `common.js::ensureTeamBuilderChromeSnapshot`
- [verified] Paint assert throws on localhost/capture if visual not ready — `common.js::_assertTeamBuilderVisualReadyForChrome`
- [verified] TB SPA boot awaits chrome snapshot — `FrontEnd/static/team-builder.js::boot`
- [verified] Claim (`franchise-select-team`) awaits chrome snapshot — `FrontEnd/static/franchise-select-team.js`
- [verified] Court HTML / Phaser boot / matchup chrome / game scene / completion popup also await or hydrate — `court.html`, `bootGame.js`, `common.js::applyTeamBuilderMatchupChrome`, `gameScene.js`, `gameCompletionPopup.js`
- [verified] FCC / mode-select / set-lineup hydrate from payload without always awaiting snapshot first — `franchise-command-center.js`, `mode-select.js`, `set-lineup.js`

### Editor-as-diff

- [verified] Roster chapter is a diff editor over inherited baseline (`base` per player, `playerChanged`) — `FrontEnd/static/js/team-builder/roster.js::normalizePlayerRow`, `playerChanged`
- [verified] Apply payload is edit-diff only: `roster_mode: 'edit'`, `imported_players: rows` — `FrontEnd/static/team-builder.js::buildApplyPayload`
- [verified] Server applies only fields the editor sends onto inherited clone — `BackEnd/utils/team_builder_roster.py::apply_row_diff_to_inherited`, `apply_diffs_to_inherited_roster`
- [verified] Blank optional field inherits (does not default) — `apply_row_diff_to_inherited` (blank → keep inherited)
- [verified] CH/EM/MO/NG never taken from edit row — `team_builder_roster.py::_PRESERVE_ATTR_KEYS`
- [verified] Flat `photo` stripped; kit is `meta.image_id` — `team_builder_roster.py::replace_slot_roster` stamp loop
- [verified] Weight derived from height + player_id at stamp; authored weight ignored — `team_builder_roster.py` (§10.2 comment + `weight_from_height`)

### Bind-by-identity

- [verified] Slot scholarship JSON identity-keyed — `franchise_routes.py::team_builder_slot_roster_json` → roster helpers bound by `source_player_id`
- [verified] Hydration clones FPD by FTD player_id order; enrich from core `players` by stable id — `team_builder_roster.py::_ordered_source_fpd`, `_build_inherited_roster_payloads`, `_enrich_payload_from_core`
- [verified] Draft overlay merge matches players by id — `roster.js::_applyDraftOverlay`
- [verified] Portrait merge into roster is **slot-indexed**, not id-keyed — `roster.js::_mergePortraitAssignments` — **artefact / caveat vs pure bind-by-identity**
- [verified] Budgets/edits must bind by identity not find() ordinal — tested in `BackEnd/tests/test_team_builder_45b_inherit.py` / phase attacks (criterion 25 intent)

### Budget enforcement

- [verified] Attribute clamps [5, 99] — `BackEnd/constants/team_builder_budget.py::ATTR_MIN`, `ATTR_MAX`, `clamp_attr`
- [verified] Capped mode: per-player core-12 total must equal inherited (after top-up floor) — `team_builder_budget.py::capped_budget_for_inherited`, `force_core12_to_budget`; enforced in `replace_slot_roster`
- [verified] Defensive top-up: if inherited core-12 < 60, budget becomes 60 — `TOPUP_FLOOR`, `apply_capped_topup` / `capped_budget_for_inherited`
- [verified] Uncapped mode: team core-12 sum ≤ runtime league `team_pool` — `replace_slot_roster` + `compute_league_attr_context`
- [verified] League pool/median computed at runtime, never hardcoded in budget module — `team_builder_budget.py` module docstring; `team_builder_league_context.py::compute_league_attr_context`
- [verified] Apply computes `team_pool` via `compute_league_attr_context` then passes into `replace_slot_roster` — `franchise_routes.py::team_builder_apply`
- [verified] Capped height: team height sum ≤ inherited total — `replace_slot_roster` `height_budget_exceeded`
- [verified] Capped class: team class-rank sum must match inherited exactly — `replace_slot_roster` `class_budget_mismatch`
- [verified] Height range 66–84 in; JH forbidden — `TB_HEIGHT_MIN_IN`/`MAX`; `class_year_jh_forbidden`
- [verified] Roster must be exactly 15 named players — `AUTHORED_ROSTER_SIZE` / `roster_size_invalid`
- [verified] FE capped pool UI per player — `roster.js::attrPoolDelta`, inspector pool
- [finding] FE never calls `GET /franchise/team-builder/league-context` — uncapped team-pool meter not driven by that endpoint (server still enforces at Apply) — grep FE TB modules empty for `league-context`

### Mode permanence

- [verified] Modes: `capped` | `uncapped` — `ATTRIBUTE_MODES`; `normalize_attribute_mode` (unknown → capped)
- [verified] `online_eligible` iff mode is capped — `online_eligible_for_mode`
- [verified] Gate UI: “This Choice Is Permanent”; Continue locks `build_mode` into draft — `FrontEnd/static/js/team-builder/gate.js`; `team-builder.js` Continue handler
- [verified] Review UI: “This Program Is Permanent” — `review.js::paint`
- [verified] Apply freezes `attribute_mode`, `online_eligible`, `hasEverExceededBudget`, `roster_shape_at_creation` on franchise — `team_builder_apply` `$set`
- [verified] `build_mode` accepted as alias, stored as `attribute_mode` — `TeamBuilderApplyRequest` / Apply normalize
- [verified] Spec field `online_eligible`; legacy `online_eligibility` read only if absent — `resolve_online_eligible`
- [unverified] `roster_shape_at_creation` still unread by eligibility rules (exists for future retroactive rules) — plan §4.7; no live consumer found in this pass beyond write

### Portrait assignment and locking

- [verified] Pool = `recruit_set_0001` ∪ `builder_set_0001`; expected size 450 — `team_builder_portraits.py` (warns if `len(entries) != 450`)
- [verified] Assign fitted portraits — `classify_team_builder_player`, `assign_fitted_image`, `assign_roster_portraits`
- [verified] Idempotent draft store; mint `player_id` on first assign — `get_or_create_wizard_portraits`
- [verified] Preserve prior assignment when target unchanged; picker `source=="picker"` sticks across reassign — `assign_roster_portraits`
- [verified] Height-edit reassign via `force_reassign_slots` drops image, keeps player_id — `get_or_create_wizard_portraits`
- [verified] Reroll skips current id — `reroll_slot_portrait`
- [verified] Pick stores `source: "picker"` — `pick_slot_portrait`
- [verified] Apply stamps `meta.image_id` + wizard player_ids; warms R2 masters — `franchise_routes.py` warm-paint helper / `_warm_team_builder_roster_masters`
- [verified] FE lock: cleared on randomize; set on picker pick; UI copy locked vs auto — `roster.js::randomizePortrait`, `pickPortrait`, paint
- [verified] Portrait image URLs via `API_CONFIG.getRecruitImageUrl` → R2 `assets.geekedoutgames.com` / `recruits/white/` — `FrontEnd/static/js/config/api-config.js`

### Shape floors at Apply

- [verified] After height/class/pool checks, each player: `resolve_training_position` then `floor_violations` — `team_builder_roster.py::replace_slot_roster` (~1356–1374)
- [verified] Policy: refuse, don’t fix — comment + `ValueError("shape_floor_violation:…")`
- [verified] Floor need from weight-scaled P6 base + rel high/low — `BackEnd/constants/training_shape.py::floor_need`, `FLOOR_REL_HIGH=0.50`, `FLOOR_REL_LOW=0.20`, `SHAPE_P6_FLOOR_BASE`
- [finding] Apply HTTP handler has **no** dedicated `shape_floor_violation:` branch — falls through to generic 400 `"Unable to apply roster changes"` — `franchise_routes.py::team_builder_apply` except ValueError (~4191–4269)
- [finding] No TB test asserts shape-floor refusal at Apply — grep `test_team*` empty for `shape_floor`

### Roster composition / walk-ons

- [verified] Authored roster size 15; scholarship 12; walk-ons 3 — `team_builder_roster.py::ROSTER_SIZE` / `SCHOLARSHIP_SIZE` / `WALK_ON_COUNT` (and FE `AUTHORED_ROSTER_SIZE`, `SCHOLARSHIP_SIZE`)
- [verified] Wizard walk-ons via `generate_walk_on_profile`, idempotent on draft key — `build_wizard_walk_on_players`, `get_or_create_wizard_walk_ons`
- [verified] Walk-ons 12–14 prefer wizard draft walk-ons at Apply — `_build_inherited_roster_payloads`
- [verified] Apply deletes init FPD for superseded ids; writes 15 new FPD; FTD `players`/`scholarship_players` rewritten — `replace_slot_roster`

### Apply / franchise create

- [verified] Apply creates franchise via season init then roster rewrite — `team_builder_apply` → `FranchiseManager.initialize_season` then `replace_slot_roster`
- [verified] `roster_mode` must be `"edit"`; else 400 retiring CSV/Keep/Generate — `team_builder_apply` + `replace_slot_roster`
- [verified] Fresh `player_id`s minted unless wizard row supplies id — `replace_slot_roster` stamp loop
- [verified] Program name max 23 at Apply — `PROGRAM_NAME_MAX_LEN`
- [verified] Inside-wood contrast gate at Apply — `inside_wood_contrast_ok` / FE `insideWoodContrastOk`
- [verified] Banner variant normalized; `chevron` → `baseline` — `normalize_banner_variant`
- [verified] Court params normalized into overlay (never image) — `normalize_court_params`

### Leak detector

- [verified] Observe-only middleware; header `X-TB-Leak-Suspect`; never fails request — `team_builder_leak_detector.py::TeamBuilderLeakMiddleware`
- [verified] Installed at app boot — `BackEnd/api/api.py` → `install_team_builder_leak_middleware`
- [verified] Scans replaced name/abbr/colours in display-bound JSON; allowlists identity keys — `scan_json_for_replaced_name*`, `LOOKUP_IDENTIFIER_LEAVES`
- [verified] Env: on by default except prod; `TB_LEAK_DETECTOR` override — `detector_enabled`
- [verified] FE companion exists — `FrontEnd/static/js/shared/teamBuilderLeakDetector.js`

---

## 2. Constants and derived values

### Hardcoded — `BackEnd/constants/team_builder_budget.py`

| Value | Symbol | Kind |
|---|---|---|
| 5 | `ATTR_MIN` | hardcoded |
| 99 | `ATTR_MAX` | hardcoded |
| 60 | `TOPUP_FLOOR` | hardcoded (defensive guard) |
| CORE_12 tuple | `CORE_12_ATTRS` | hardcoded |
| 23 | `PROGRAM_NAME_MAX_LEN` | hardcoded (comment: Plate field; design once said 26) |
| `{capped, uncapped}` | `ATTRIBUTE_MODES` | hardcoded |
| 66 / 84 | `TB_HEIGHT_MIN_IN` / `TB_HEIGHT_MAX_IN` | hardcoded |
| SR=4…FR=1 | `TB_CLASS_RANK` | hardcoded |

### Hardcoded — `BackEnd/utils/team_builder_roster.py`

| Value | Symbol | Kind |
|---|---|---|
| 15 | `ROSTER_SIZE` / `MAX_ROSTER_SIZE` / `AUTHORED_ROSTER_SIZE` | hardcoded |
| 12 | `SCHOLARSHIP_SIZE` | hardcoded |
| 3 | `WALK_ON_COUNT` | hardcoded |

### Hardcoded — `BackEnd/utils/franchise_team_display.py`

| Value | Symbol | Kind |
|---|---|---|
| `baseline,keel,plate,sash` | `BANNER_VARIANT_KEYS` | hardcoded |
| `baseline` | `DEFAULT_BANNER_VARIANT` | hardcoded |
| 1 / 2 | `JERSEY_PRESET_SOLID` / `_WITH_TRIM` | hardcoded |
| 9 hardwood keys | `HARDWOOD_STYLE_KEYS` | hardcoded |
| 6 court param keys | `COURT_PARAM_KEYS` | hardcoded |
| `#6e675f` | `COURT_LINE_COLOR` | hardcoded |
| 3.0 | `INSIDE_WOOD_LINE_CONTRAST_MIN` | hardcoded |
| `???` | `ABBR_EMPTY` | hardcoded |

### Hardcoded — drafts / portraits

| Value | Symbol | Kind |
|---|---|---|
| 2 | `team_builder_drafts.py::SCHEMA_VERSION` | hardcoded |
| `team_builder_wizard_drafts` | `DRAFT_COLLECTION` | hardcoded |
| 450 (expected) | `team_builder_portraits.py` pool length check | hardcoded expectation; pool **read from data** under `scripts/recruit_sets` |

### Runtime / data-derived

| Value | Where | Kind |
|---|---|---|
| `team_pool`, `team_median`, scholarship medians, walk-on pads | `team_builder_league_context.py::compute_league_attr_context` | computed at runtime from DB |
| Floor needs per player | `training_shape.py::floor_need` × player mean core-12 | computed at Apply |
| `SHAPE_P6_FLOOR_BASE` | `training_shape.py` | data table in code (t0 shape-P6 export) |
| Weight at stamp | `weight_from_height(height, player_id)` | computed |
| `online_eligible` | derived from mode at Apply | derived |
| Portrait catalog filters/counts | `catalog_for_picker` | computed from pool data |

### Floors — `training_shape.py` (Apply refusal inputs)

| Value | Symbol | Kind |
|---|---|---|
| 0.50 | `FLOOR_REL_HIGH` | hardcoded |
| 0.20 | `FLOOR_REL_LOW` | hardcoded |
| per-pos/attr shape fractions | `SHAPE_P6_FLOOR_BASE` | table in code |
| cost/floor weights | `TRAINING_COST_WEIGHTS` | table in code (shared with development framework) |

### Frontend mirrors — `FrontEnd/static/js/team-builder/constants.js`

| Value | Symbol | Kind |
|---|---|---|
| 23 / 20 / 3 | `PROGRAM_NAME_MAX_LEN` / `MASCOT_MAX_LEN` / `ABBR_LEN` | hardcoded (name mirrors BE) |
| 480 / 140 / 600 | `ABBR_CHECK_MS` / `COURT_RENDER_MS` / `DRAFT_SAVE_MS` | hardcoded |
| `#6e675f` / 3.0 | `COURT_LINE_COLOR` / `INSIDE_WOOD_LINE_CONTRAST_MIN` | hardcoded |
| 5 chapters | `CHAPTERS` | hardcoded |
| 4 banner variants | `BANNER_VARIANTS` | hardcoded |
| 8 palettes / 12 swatches | `PALETTES` / `SWATCHES` | hardcoded |
| CORE_12 / RT keys / ATTR_CATS / POSITIONS / CLASSES | various | hardcoded |
| 5 / 99 / 60 / 66 / 84 / 15 / 12 | attr/height/roster | hardcoded |
| portrait chip maps | `PORTRAIT_SKIN_CHIPS`, `FRAME`, `DEFINITION` | hardcoded |
| 8 surprise presets | `SURPRISE` | hardcoded |

### Frontend art modules

| Value | Where | Kind |
|---|---|---|
| Banner card 400×141; primary 1920×679 | `teamGeneratedArt.js` | hardcoded |
| Banner contrast floor 4.5 | `teamGeneratedArt.js::CONTRAST_FLOOR` | hardcoded |
| Court canvas 3333×2083 | `teamCourtGenerator.js` | hardcoded |
| Hardwood tone hexes | `teamCourtGenerator.js::HARDWOOD_TONES` | hardcoded |
| Overlay paths `/images/teams/general/court-overlays/` | `teamCourtGenerator.js` | local static paths |
| Portrait CDN base `https://assets.geekedoutgames.com` | `api-config.js` | hardcoded |
| Image sizes thumb/card/modal 128/256/512 | `PLAYER_IMAGE_SIZES` | hardcoded |

### Artefacts / comment mismatches

- [artefact] Comment in `team_builder_budget.py` says “Why 24 (not design's 26)” but constant is **23** — `PROGRAM_NAME_MAX_LEN = 23`
- [finding] Design handoff README still says school name max **26** — `_documentation_master/projects/design_handoff_team_builder/README.md` vs code 23
- [artefact] Claim banner copy “Step 1 of 3” — `franchise-select-team.html` (flow is Claim + 5 chapters)
- [artefact] `teamGeneratedArt.js` / `common.js` still mention “Colors step” / “Wizard Colors preview”

---

## 3. Data model

### Franchise document writes (Apply)

- [verified] `team_builder` overlay: name, abbreviation, mascot, colours, jersey_preset, court params, banner_variant, replaced_object_id, attribute_mode (and related identity fields) — `team_builder_apply` / `franchise_team_display`
- [verified] Root: `attribute_mode`, `online_eligible`, `hasEverExceededBudget`, `roster_shape_at_creation` — Apply `$set`
- [verified] Unsets legacy `online_eligibility` when writing spec field — Apply path (per inventory; confirm if still present in `$unset`)

### FTD (`franchise_team_data`)

- [verified] Rewritten: `players` (15 ids), `scholarship_players` (12), `training_squad_players` `[]`, `total_player_attrs` — `replace_slot_roster`
- [verified] Does **not** store custom identity (overlay on franchise) — `franchise_team_display.py` module docstring

### FPD (`franchise_players_data`)

- [verified] 15 new docs inserted; old init ids deleted — `replace_slot_roster`
- [verified] Minted `player_id`s (unless wizard-supplied) — stamp loop
- [verified] Core-12 + anchors written from diff/top-up — `_build_fpd_doc` / finalize path
- [verified] `entry_tier`: carry / derive (`entry_tier_at_year` fallback) — `_build_fpd_doc` / enrich
- [verified] `potential_factor`: carry / `resolve_potential_factor`; **row does not overwrite** in `apply_row_diff_to_inherited` — roster helpers
- [verified] `development`: carry if present; omitted if None — `_build_fpd_doc`
- [verified] `position_intent`: carry / derive from ratings max — written on FPD
- [verified] `training_position`: **not written to FPD** by TB Apply — only read for floor resolve — **finding / gap**
- [verified] `meta.image_id` stamped; flat `photo` null — stamp loop
- [verified] Season/career stats zeroed unless inherited payload carries — `_build_fpd_doc`
- [verified] Walk-on archetype `"Walk On"` — wizard payload / meta

### Draft collection `team_builder_wizard_drafts`

- [verified] One doc per `(user_id, replaced_object_id)` at `schema_version == 2` — `team_builder_drafts.py`
- [verified] Old-format drafts discarded on read — `discard_old_format_for_user`
- [verified] Upsert keys: chapter, build_mode, identity, roster, portraits, walk_ons, extra, draft_id — `upsert_draft` / FE `upsertDraft`
- [verified] Apply deletes **all** drafts for user (not slot-scoped) — `delete_draft_for_slot(db, user_id=…)` without slot filter — **artefact?** confirm intentional wipe-all

### Deliberately does not mutate

- [verified] Core `teams` / `players` collections — overlay model; never mutated by Apply
- [verified] Base-league portrait masters — Apply paints franchise masters; does not overwrite pool masters (plan criterion 27; warm path writes franchise masters)
- [verified] CH/EM/MO/NG from editor — preserved from inherited
- [verified] Authored weight — ignored
- [verified] Mid-franchise re-edit of overlay — no write path after Apply (Apply-only)

---

## 4. Endpoints and entry points

### HTTP — Team Builder owned (`franchise_routes.py`)

| Method | Path | Handler | verified |
|---|---|---|---|
| GET | `/franchise/team-builder` | `get_team_builder_page` → `team-builder.html` | yes |
| GET | `/franchise/team-builder/slot-roster` | `team_builder_slot_roster_json` | yes |
| GET | `/franchise/team-builder/league-context` | `team_builder_league_context` | yes |
| POST | `/franchise/team-builder/position-ratings` | `team_builder_position_ratings` | yes |
| GET | `/franchise/team-builder/drafts` | `team_builder_list_drafts` | yes |
| POST | `/franchise/team-builder/drafts` | `team_builder_upsert_draft` | yes |
| DELETE | `/franchise/team-builder/drafts/{replaced_object_id}` | `team_builder_discard_draft` | yes |
| POST | `/franchise/team-builder/wizard-walk-ons` | `team_builder_wizard_walk_ons` | yes |
| POST | `/franchise/team-builder/portraits/assign` | `team_builder_portraits_assign` | yes |
| POST | `/franchise/team-builder/portraits/reroll` | `team_builder_portraits_reroll` | yes |
| POST | `/franchise/team-builder/portraits/pick` | `team_builder_portraits_pick` | yes |
| GET | `/franchise/team-builder/portraits/catalog` | `team_builder_portraits_catalog` | yes |
| POST | `/franchise/team-builder/apply` | `team_builder_apply` | yes |

### HTTP — related, not under `/team-builder/*`

| Method | Path | Role | verified |
|---|---|---|---|
| GET | `/franchise/select-team` | Claim HTML | yes |
| GET | `/teams?franchise_id=` | Chrome snapshot / TeamPicker | yes |
| GET | `/franchise/command-center/data` | Visual hydrate | yes |
| POST | `/franchise/select-team` | Non-builder take-slot (Claim non-builder path) | yes |
| (paint) | player image routes | Lazy paint uses `resolve_kit_keys` | yes — `player_image_routes.py` |

### Screens / URLs

| Screen | URL | Hydration gate | verified |
|---|---|---|---|
| Claim / Step 0 | `/franchise-select-team.html?builder=1` (+ `home_slot`); also `GET /franchise/select-team` | awaits chrome snapshot | yes |
| TB SPA | `/team-builder.html?replaced_object_id=&chapter=&draft_id=&mode=&home_slot=`; also `GET /franchise/team-builder` | awaits chrome snapshot | yes |
| Chapters (in-SPA) | `chapter=identity\|gate\|roster\|review\|establish` via `history.replaceState` | same SPA boot | yes |
| Post-Establish | `/franchise-command-center.html?franchise_id=` | FCC hydrates visual | yes |
| Band QA fixture | `/tb-band-placement-qa.html` (static only) | n/a | yes |

### Chapter → FE module

| Chapter | Module |
|---|---|
| identity | `js/team-builder/identity.js::IdentityChapter` |
| gate | `js/team-builder/gate.js::GateChapter` |
| roster | `js/team-builder/roster.js::RosterChapter` |
| review | `js/team-builder/review.js::ReviewChapter` |
| establish | `js/team-builder/establish.js::EstablishChapter` |

### FE → API calls (exhaustive for TB modules)

| Call | Caller |
|---|---|
| GET drafts | `team-builder.js::loadExistingDraft`; `franchise-select-team.js` |
| POST drafts | `team-builder.js::upsertDraft` |
| DELETE drafts/{id} | `franchise-select-team.js::discardDraft` |
| GET slot-roster | `roster.js::load` |
| POST wizard-walk-ons | `roster.js::load`; `team-builder.js::loadShapeBudgets` |
| POST portraits/assign\|reroll\|pick | `roster.js` |
| GET portraits/catalog | `roster.js::openPicker` |
| POST position-ratings | `roster.js::_fetchRatings` |
| POST apply | `team-builder.js::applyFranchise` → Establish |
| **No FE caller** | `GET …/league-context` |

### Absent routes

- [verified] No `slot-roster.csv` route — grep `BackEnd/api/`
- [verified] No Keep/Generate Apply modes — rejected if `roster_mode != "edit"`

---

## 5. Boundaries

| Touchpoint | Direction | What | verified |
|---|---|---|---|
| Sim / gameplay | TB → sim | Overlay + FPD/FTD become the franchise team the sim plays | yes (Apply writes; resolver feeds chrome/sim) |
| Mid-game resume | sim → chrome | Command center attaches `active_game_resume`; same path hydrates TB chrome — no TB-specific resume API | yes — `franchise_routes.py` command-center |
| Leak detector | TB → responses | Middleware scans franchise/game JSON for replaced-name leaks | yes |
| Development framework floors | framework → TB Apply | `floor_violations` / `resolve_training_position` refuse illegal shapes | yes — `training_shape.py` ← `replace_slot_roster` |
| Development offseason | TB → development | Authored FPD enter normal rollover; attractor retired so authored shape not α-pulled | verified attractor `0.0` in framework; TB does not call develop |
| Walk-on generator | TB → generator | `generate_walk_on_profile()` same producer as season init | yes — `team_builder_roster.py` |
| Recruit/portrait sets | data → TB | Pool from `scripts/recruit_sets` (`recruit_set_0001` ∪ `builder_set_0001`) | yes — `team_builder_portraits.py` |
| R2 assets | TB → R2 | Portrait masters warmed at Apply; FE reads R2 for recruit/white images | yes |
| R2 banners/courts | — | **Not used** — client canvas generators only | yes |
| Core teams/players | TB ↛ core | Never mutates | yes |
| League context | DB → Apply | Week-1 15-player totals for uncapped pool | yes |
| Uniforms | TB → config | Jersey preset 1/2; plan: entry in `teams_uniforms.json` (recolor recipe) — **unverified** whether Apply writes uniforms file |

---

## 6. Retired and removed

| Item | Status today | Remains | verified |
|---|---|---|---|
| CSV import | Retired | No FE UI; no CSV route; `imported_players` is edit-row payload name only; helpers `parse_import_class_year` / `count_importable_players` still used by edit path | yes |
| Keep path | Retired | `roster_mode != "edit"` → 400 | yes |
| Generate path | Retired | Same; `generate_roster_at_band` **still implemented**, test-only, not routed — **artefact** | yes — `team_builder_roster.py::generate_roster_at_band`; `test_team_builder_phase1_attacks.py` |
| Five-step wizard (Slot→Identity→Colors→Roster→Review) | Replaced | Claim + 5 in-SPA chapters; stale “Step 1 of 3” / “Colors step” comments | yes |
| §4.3 top-up as user-facing concern | Retired 2026-08-05 (recalibration: no sub-60 subjects) | Server `TOPUP_FLOOR` / `apply_capped_topup` **kept** as defensive guard; FE `TOPUP_FLOOR` still used in `cappedBudget`; UI surface copy removed per plan | code yes; doc `team-builder-v2-plan.md` §4.3 |
| Offseason attractor on authored rosters | Retired framework-wide | `OFFSEASON_ATTRACTOR_ALPHA = 0.0`; level-only offseason — `player_development.py` / framework §11 | yes |
| Chevron banner | Retired | Normalizes to `baseline` | yes — `normalize_banner_variant` |
| Top-5 / four-condition soft budget | Retired | Module docstring in `team_builder_budget.py` | yes |

### Doc/code disagreements (findings)

- [finding] `Team_Builder_System.md` body still lists Keep/Generate/CSV / `slot-roster.csv` in places while header says retired — doc vs `team_builder_apply`
- [finding] Design README name max 26 vs code 23
- [finding] `Team_Builder_System.md` / older plans may still describe attractor-era behaviour — prefer framework §11 + this inventory

---

## 7. Known gaps

### Unimplemented / deferred

- [unverified] **3c uploads** (horizontal logo, player images) — committed fast follow; requires R2 upload storage — `team-builder-v2-plan.md` §6.4; no FE upload UI found
- [verified] **Cold Apply timing number** — design handoff `SERVER_MS=2600` placeholder; live Establish uses design beat timers and waits on Apply promise — **real Apply duration never instrumented in shipping FE** — `establish.js::_startSequence`; handoff README / `tb-implementation-prompt.md`
- [verified] FE **does not call** `league-context` — criterion 12 (no hardcoded league literals) holds on server Apply; FE has no uncapped team-pool meter wired to runtime context — **gap vs plan criterion 12/14 intent on editor surface**

### Unverified / needs re-check

- [unverified] **Acceptance criteria 12 & 13** (plan §4.8): (12) no hardcoded league constants — server OK, FE unused endpoint; (13) editor opens with 15 (12 + 3 wizard walk-ons) — code path exists (`wizard-walk-ons` + slot-roster) but **not re-verified in this pass against new floor refusal**
- [finding] Shape-floor refusal at Apply: implemented in roster replace, **HTTP detail not mapped**, **no TB test**, **criteria not re-run** after floors landed
- [unverified] Uniforms JSON write at Apply for custom programs
- [unverified] Whether `hasEverExceededBudget` / `roster_shape_at_creation` are read anywhere outside TB write

### Unowned (also framework §8a)

- [unverified] Recruit generation branch: init `recruit_set_0001` σ≈15.7 vs live `generate_recruits_list` σ≈11.6 (~26% variety loss after S1) — framework §8a / Player_Development_System; **not a TB Apply path**, affects league after custom franchise exists
- [verified] `training_position` has **no live write path**; TB Apply does not persist it; floors resolve via `position_intent` / ratings fallbacks — `replace_slot_roster` + `_build_fpd_doc` omission

### Expected but not found

- [finding] Dedicated Apply 400 detail for `shape_floor_violation:*`
- [finding] FE consumer for `/franchise/team-builder/league-context`
- [finding] Instrumented real Apply ms in Establish (placeholder retired in design; measurement not shipped)
- [finding] TB tests for shape-floor Apply refusal
- [finding] Upload UI (3c)
- [artefact] `generate_roster_at_band` still in production module (tests only)

### Things that look wrong (not fixed)

- [artefact] Comment “Why 24” vs constant 23 — `team_builder_budget.py`
- [artefact] Portrait merge by slot index while draft overlay binds by id — can desync if order/id diverge
- [artefact] Apply deletes all user drafts, not only the slot’s draft
- [finding] Generic Apply error for shape floors hides player/attr detail the `ValueError` already carries
- [artefact] Claim “Step 1 of 3” copy vs five-chapter SPA

---

## 8. Module map (absolute)

| Path | Role |
|---|---|
| `BackEnd/api/franchise_routes.py` | All TB HTTP + Apply |
| `BackEnd/constants/team_builder_budget.py` | Attr/mode/height/class budgets |
| `BackEnd/constants/training_shape.py` | Apply shape floors + cost weights |
| `BackEnd/utils/team_builder_roster.py` | Hydration, diffs, walk-ons, replace |
| `BackEnd/utils/team_builder_drafts.py` | Draft CRUD |
| `BackEnd/utils/team_builder_portraits.py` | Assign/reroll/pick/catalog |
| `BackEnd/utils/team_builder_league_context.py` | Week-1 league pool |
| `BackEnd/utils/team_builder_leak_detector.py` | Replaced-name scanner |
| `BackEnd/utils/franchise_team_display.py` | Overlay resolve, banner/court/jersey |
| `BackEnd/api/api.py` | Leak install + name→OID |
| `BackEnd/api/player_image_routes.py` | Lazy paint / kit keys |
| `FrontEnd/static/team-builder.html` + `team-builder.js` | SPA shell |
| `FrontEnd/static/js/team-builder/*` | Chapters |
| `FrontEnd/static/franchise-select-team.html` + `.js` | Claim |
| `FrontEnd/static/js/shared/common.js` | Chrome hydration gate |
| `FrontEnd/static/js/shared/teamGeneratedArt.js` | Banner canvas |
| `FrontEnd/static/js/shared/teamCourtGenerator.js` | Court canvas |
| `FrontEnd/static/js/config/api-config.js` | Portrait CDN |

### Tests present

`BackEnd/tests/test_team_builder_{roster,budget,drafts,league_context,portraits,wizard_walk_ons,court_persist,phase1_attacks,phase4_height_class,45b_inherit}.py`, `tests/test_tb_leak_detector.py`.

### Primary docs (not verified as truth)

- `_documentation_master/04_Franchise_Mode_Systems/Team_Builder_System.md` — mixed stale/current
- `_documentation_master/projects/team-builder-v2-plan.md` — plan + acceptance criteria
- `_documentation_master/projects/design_handoff_team_builder/*` — design handoff
- `_documentation_master/10_Players_Systems/player-development-framework.md` — floors / §11 closed

---

## 9. Apply request surface (verified fields)

`TeamBuilderApplyRequest` / court model — `franchise_routes.py` ~2633–2673:

- `replaced_object_id`, `home_slot`, `name`, `abbreviation`, `mascot`
- `primary_color`, `secondary_color`, `jersey_preset`
- `court` (`TeamBuilderCourtParams`)
- `roster_mode` (must be `"edit"`)
- `attribute_mode`, `build_mode` (alias)
- `imported_players`, `per_player_budgets`
- `draft_id`, `banner_variant`
