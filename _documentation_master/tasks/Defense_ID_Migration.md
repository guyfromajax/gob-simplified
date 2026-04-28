# Defense ID Migration (tasks doc)

**Goal:** Use **stable string IDs** for defensive playcalls throughout runtime, persistence, and APIs so defense **display names** in the universal `defenses` collection can change without breaking scouting keys, `game_state`, stats rollups, or UI bindings.

**Design decision (locked):** **Canonical defense identity = universal `defenses.defense_id`** (slug string, e.g. `2-3-zone`, `base-man`). This matches existing seed scripts and is **stable across reseeds** when documents are upserted by `defense_id`. **Offense** remains **`play_id` = `str(plays._id)`** — the two domains intentionally differ; do not force Mongo `_id` hex for defense as “parity.”

### Implementation status (snapshot)

| Phase | Status | Notes |
|-------|--------|--------|
| **0** | Done | Locks as documented below. |
| **1** | Done | `defense_identity.py` + `test_defense_identity.py`. `defense_utils.is_zone_defense` delegates to `resolve_to_defense_id` / `is_zone_defense_id` (legacy string fallback remains for tests / empty DB). Optional cleanup: refresh docstrings on `map_defense_playcall_to_tracking_name`. |
| **2** | Done (backend) | Canonical **slug keys** in `populate_scouting_data`, `team_manager` template, and `normalize_scouting_data_for_gameplay` (`canonical_scouting_defense_key` / `_remap_defense_scouting_keys_for_merge`). Training, `stat_updater`, `phase_resolution`, and `turn_manager` scouting increments use **canonical row keys** via `defense_scouting_row_key` / id-shaped `game_state`. **No standalone DB backfill script** in repo yet — **lazy migration on read** is the current approach; add an explicit script if prod needs a one-shot rewrite. |
| **3** | In progress | **`shot_manager`:** HCO rebound zone penalty and zone-vs-3pt multiplier now use `defense_playcall` + `is_zone_defense` (no bogus `game_state["defense_call"]` / `"Zone"` string). **`shared`:** OREB putback uses `defense_playcall` with legacy `defense_call` fallback. **`rim_runner_fast_break`:** only touches synthetic `vs_Fast_Break` — already id-shaped. **Tests:** `BackEnd/tests/test_defense_phase3_contracts.py` (row keys + zone detection). **Remaining:** optional API persist of canonical slug for `strategy_calls["defense_call"]` (must not collapse **Zone sentinel**); GP client contract; fuller override → turn → scouting test. |
| **4** | In progress | **`defense-display.js`** (global) + **`js/phaser/utils/defenseUi.js`** (ES module): canonical slug → label, `getDefenseBlock`, ordered playbook rows. Wired: **FCC / tournament / training-report** playbook summary, **box-score** defense sections, **Phaser** `playcallDisplay` / `playcallCenter`. HTML loads `/defense-display.js` before page scripts on those four pages. **Remaining:** other static surfaces if any; prefer backend `defensive_playcall_display` on turns where useful; playbooks API audit. |
| **5** | Partial | Extend round-trip / E2E tests; staging checklist; eventual removal of dual-read / legacy writes. |

**Repo / git:** Latest defense work is on **`develop`** (commit message references phases 1–2); branch **tracks `origin/develop`** when clean — confirm after each local session with `git status` / `git push`.

**Current split (post–Phase 2 backend):**
- **`playbook_settings`** + **`defense_identity`** maps still bridge **playbook percentage keys** ↔ **`defense_id`** / scouting row keys.
- **Runtime / sim (backend):** `game_state["defense_playcall"]`, scouting defense rows, and major sim increment paths use **canonical ids** with **dual-read** at normalize / resolve boundaries.
- **Still open:** **Frontend** surfaces and some **contracts** (turn payloads, box score, scouting report copy) may still treat defense map keys as display names; **Phase 4** closes that gap.

This migration is about **closing the gap**: one canonical **`defense_id`** everywhere runtime/persistence care, plus **reserved synthetic ids** for non-catalog rows (`vs_Fast_Break`, `FCP`, `HCT`, etc.). Use **`str(_id)`** only when issuing Mongo queries by primary key, not as the app-wide defense playcall string.

---

## 1. Code sweep — places to inspect or change

Below: **primary** files (high confidence) and **secondary** (verify during implementation). Line numbers drift; search by symbol. **Many backend rows are already migrated** — use **§ Implementation status** for phase truth; use these tables for **residual verification** (especially **frontend** in §1.5–1.6).

### 1.1 Backend — simulation & game state

| Area | File(s) | What uses name today |
|------|---------|----------------------|
| Half-court playcall selection & tracking | `BackEnd/models/turn_manager.py` | `game_state["defense_playcall"]`, `tracking_name = defense_playcall`, `strategy_calls["defense_call"]`, random zone picks as `"2-3 Zone"` strings, comparisons to `"Man"` / zone names |
| Shot / pressure / zone deltas | `BackEnd/models/shot_manager.py` | `defense_playcall` / `defense_call` from `game_state`; string compares (`"2-3 Zone"`, `"Zone"`) |
| HCO / execution / EV storage | `BackEnd/engine/phase_resolution.py` | `defense_playcall in defense_team.scouting_data["defense"]`, `is_zone_defense(defense_call)`, success increments keyed by `tracking_name`, FCP/HCT/vs_Fast_Break literals |
| Fast break defense success | `BackEnd/engine/rim_runner_fast_break.py`, `BackEnd/engine/phase_resolution.py` | `def_scouting["defense"]["vs_Fast_Break"]` (synthetic key — decide id policy) |
| Animation / presentation hooks | `BackEnd/models/animator.py` | `defense_playcall` string branching (`"3-2 Zone"`, `"1-3-1 Zone"`) |
| Playbook manager defaults | `BackEnd/models/playbook_manager.py` | Default `"Man"` |
| Defense helpers | `BackEnd/utils/defense_utils.py` | `map_defense_playcall_to_tracking_name`, `is_zone_defense` — become id-aware or wrap a central resolver |
| Man matchup resolution | `BackEnd/utils/man_defense_matchups.py` | Uses `defense_playcall` from game state when selecting defenders — must resolve id → man vs zone behavior |

### 1.2 Backend — scouting shape & init

| Area | File(s) | What uses name today |
|------|---------|----------------------|
| Scouting template & normalize | `BackEnd/models/team_manager.py` | `_create_scouting_data_template_base()` keys: `"Man"`, `"2-3 Zone"`, …; `normalize_scouting_data_for_gameplay` merges on those keys |
| FTD → game seed | `BackEnd/utils/franchise_ftd_game_seed.py` | Pass-through of `scouting_data` after normalize; keys follow template |
| Lazy scouting init | `BackEnd/api/gameplan_routes.py` — `populate_scouting_data()` | Builds `defense_structure` with **name keys** |
| Training defense updates | `BackEnd/models/training_execution_v2.py` | Iterates `scouting_data["defense"].items()` by name; zone list `["2-3 Zone", …]`; bridges `ZONE_DEFENSE_ID_TO_NAME` for playbook percentages |
| Tests | `BackEnd/tests/test_training_system.py` | Fixture defense keys by name |

### 1.3 Backend — persistence, stats, EOG

| Area | File(s) | What uses name today |
|------|---------|----------------------|
| Season stat increments for defense | `BackEnd/utils/stat_updater.py` | `_update_defensive_playcall_season_stats`: iterates `defense_data.items()`; Mongo paths `scouting_data.defense.{playcall_name}...` |
| Franchise EOG / attribute heuristics | `BackEnd/api/franchise_routes.py` | `_defensive_play_max_share`: explicit tuple `("Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone")` |
| Team settings / playbook save | `BackEnd/utils/team_settings_manager.py` | Already mixes transformed playbook with `man_defense` / `zone_defense` / `pc_order` — align with id-based defense playcall fields |
| Game plan / playbooks API | `BackEnd/api/gameplan_routes.py` | `initialize_playbook_settings`, `get_playbooks` / row builders: `man_defense_rows` / `zone_defense_rows` with `id` + `name`; **response may already expose id** — confirm all clients send/receive ids for **playcalls** not only percentages |
| Playbook normalization | `BackEnd/utils/playbook_settings_utils.py` | **Offense-like** id maps for percentages + `normalize_pc_order_settings` for defense list — extend to be **single source** for resolving id ↔ name |

### 1.4 Backend — database & admin

| Area | File(s) | Notes |
|------|---------|--------|
| Universal defenses | `BackEnd/db.py` — `defenses_collection` | Canonical `_id` / any `defense_id` field — **define** app-wide `defense_id` string |
| Seeds / migrations | Any scripts seeding `defenses` | Renames affect display only after migration |

### 1.5 Frontend — gameplay (GP)

| Area | File(s) | What uses name today |
|------|---------|----------------------|
| Playcall center UI | `FrontEnd/static/js/phaser/ui/playcallCenter.js` | Displays `defensive_playcall` / `defense_playcall` from turn payload (expects human-readable strings today) |
| Playcall display helpers | `FrontEnd/static/js/phaser/utils/playcallDisplay.js` | Same |
| Court playbook payload | `FrontEnd/static/court.html` | Builds save payload with `man_defense` / `zone_defense` maps (likely **id-keyed** already — verify against backend) |

### 1.6 Frontend — FCC, lineup, playbooks, reports

| Area | File(s) | What uses name today |
|------|---------|----------------------|
| Playbooks page | `FrontEnd/static/playbooks.js` | Rows from API with `row.id`; percentages keyed by id — **playcall override / PC order** may still assume names in places |
| Playbook report | `FrontEnd/static/playbook-report.js` | `defenseNameMap` from `row.id` → `name`; good pattern for display |
| Set lineup modal | `FrontEnd/static/set-lineup.js` | Man/zone sections use `row.id` for percentages (aligned with offense-style ids) |
| Franchise command center | `FrontEnd/static/franchise-command-center.js` | Playbooks tab: id-based percentages; **scouting report sections** iterate `Object.entries(scouting_data.defense)` using **object keys as display names** (`defense_name`) — **high-impact** for migration |
| Tournament command center | `FrontEnd/static/tournament.js` | Same scouting pattern as FCC |
| Training report | `FrontEnd/static/training-report.js` | Same `scouting_data.defense` key-as-name iteration |
| Game plan page | `FrontEnd/static/game-plan.js` | Mostly strategy sliders; confirm any defense playcall override wiring |
| Box score | `FrontEnd/static/box-score.js` | **Hard-coded defense keys**: `defense.Man`, `defense['2-3 Zone']`, `defense['3-2 Zone']`, `defense['1-3-1 Zone']`, `defense.HCT`, `defense.FCP` — must map id → section or resolve from snapshot metadata |

### 1.7 Docs & contracts (update after implementation)

| Area | File(s) |
|------|---------|
| Master data | `_documentation_master/00_Data_Systems/O_&_D_Plays_Collections.md` — defense name-keyed note |
| Persistence | `Data_Persistence_System.md`, `Settings_Persistence_Guide.md`, `Statistics_System.md`, `Game_Init_System.md` |
| Features | `Playcall_Center.md`, `Defense_Matchups_System.md`, `Fast_Break_System.md`, `FCP_HCT_System.md` |

### 1.8 Mirror: offensive `play_id` patterns (reference only)

Use these as **templates** for dual-read / normalization:
- `BackEnd/utils/playbook_settings_utils.py` — percentage key normalization, `play_id` in `pc_order.offense`
- `BackEnd/utils/team_play_utils.py` — `iter_team_plays` (name vs id tolerance)
- `FrontEnd/static/playbooks.js` / `playbookTeamId.js` — row `id` usage

---

## 2. Work plan

### Phase 0 — Design locks (short)

1. **Canonical id (done):** **`defenses.defense_id`**. Resolver loads row via `defenses_collection.find_one({"defense_id": ...})` (and may accept legacy name / `str(_id)` during dual-read only).
2. **Synthetic keys:** Define fixed string constants for `vs_Fast_Break`, `FCP`, `HCT` (or store as real docs — product call).
3. **Runtime vs persistence:** **`game_state` authority = `defense_id` only**; optional **display-only** name on turn payloads for UI (not used for sim).
4. **Dual-read period:** All readers accept **legacy display name OR `defense_id`** (and optionally `str(_id)` if ever stored), normalizing to **`defense_id`** at the `TeamManager` / `GameManager` boundary.
5. **Playbook percentage keys** (`zone_23`, `man_normal`, …): keep mapping to / from **`defense_id`** explicit in one module (extends today’s `MAN_DEFENSE_ID_TO_NAME` / `ZONE_DEFENSE_ID_TO_NAME` pattern).

### Phase 1 — Central resolution module ✅

1. **`BackEnd/utils/defense_identity.py`:**  
   `resolve_to_defense_id`, `get_defense_doc`, `defense_display_name`, `is_zone_defense_id`, `refresh_defense_identity_cache`, `clear_defense_identity_cache`; synthetics `SYNTHETIC_DEFENSE_IDS`; playbook key maps; legacy Man / `Zone` dual-read.  
   **Tests:** `BackEnd/tests/test_defense_identity.py`.
2. **`defense_utils.py`:** `is_zone_defense` delegates through `defense_identity` (legacy display-string fallback retained). Optional: align `map_defense_playcall_to_tracking_name` docs with id-first behavior.

### Phase 2 — Scouting & template ✅ (backend)

1. ✅ `populate_scouting_data`, `team_manager` template, and `normalize_scouting_data_for_gameplay` use **canonical slug keys** (`man`, `2-3-zone`, …) with **legacy key remap** before template merge.
2. ✅ `training_execution_v2`, `stat_updater`, `phase_resolution`, and `turn_manager` paths that read/write scouting defense rows operate on **canonical keys** (variable names like `defense_name` may still appear — they are often **ids** now).
3. **Persistence backfill:** **Lazy on read** via `normalize_scouting_data_for_gameplay` / remap — **done**. **Explicit bulk migration script** for existing Mongo docs — **not added**; schedule if ops wants documents rewritten at rest.

### Phase 3 — Game state & sim (in progress)

1. ✅ HCO selection / `game_state["defense_playcall"]` largely uses canonical ids; display remains a separate concern for Phase 4 APIs/UI.
2. ✅ **`shot_manager`:** rebound D-weight zone penalty reads **`defense_playcall`**; **`calculate_shot_score`** zone 3pt multiplier uses **`is_zone_defense(defense_call)`** instead of `== "Zone"`. **`rim_runner_fast_break`:** no change needed (synthetic **`vs_Fast_Break`** key only).
3. 🔄 **`strategy_calls.defense_call`**: still stores client payload as-is; **`turn_manager._coerce_hco_defense_id`** normalizes at sim time. Optional: normalize on **API write** for slugs/display names **without** breaking **Zone sentinel** → weighted zone (`_select_zone_defense_with_playbook_weights`). **Contract tests:** `BackEnd/tests/test_defense_phase3_contracts.py` (slug + legacy + playbook keys → `defense_scouting_row_key` / `is_zone_defense`). **Still to add:** override → possession → scouting row (integration).

### Phase 4 — APIs & frontend surfaces (in progress)

1. 🔄 **GET /api/playbooks** / gameplan: confirm `man_defense_rows` / `zone_defense_rows` and turn payloads expose **id** as authority; names for labels only (spot-check clients).
2. ✅ **FCC / tournament / training-report** playbook summary: **`GOBDefenseDisplay.buildPlaybookStyleDefenseRows`** — canonical order (`man`, then zone slugs), dual-read keys via **`getDefenseBlock`**; legacy `Object.entries` fallback if script missing.
3. ✅ **box-score.js:** defense blocks resolved via **`getDefenseBlock`** + legacy key fallback for EOG stats.
4. ✅ **Phaser** `playcallDisplay.js` / `playcallCenter.js`: import **`defenseUi.js`** — scoreboard Man/Zone bucket + status line labels for slug / legacy display strings.

### Phase 5 — Tests, rollout, cleanup (partial)

1. Extend `test_training_system` and add defense id round-trip tests (init → sim turn → summarize → scouting keys).
2. Staging: verify franchise + tournament + single; box score; training report; playbooks save/load.
3. Remove dual-read after TTL; drop legacy name-key writes.

---

## 3. Out of scope / explicit risks

- **Renaming defenses in Mongo** before migration completes will still break in-flight games unless dual-read is deployed.
- **Third-party or cached** frontend bundles may assume string labels — version or feature-flag API responses if needed.
- **Distant sim / batch paths** (if any duplicate playcall logic) must be included in the same sweep as GP sim.

---

**Document status:** Task plan + **implementation progress** (updated as migration proceeds; no code in this file).  
**Created:** April 2026.  
**Updated:** April 2026 — **canonical = `defense_id`** (user decision); status table reflects **post–Phase 2 backend**, **Phase 3** (`shot_manager` / putback fixes landed), **Phase 4 outstanding**.
