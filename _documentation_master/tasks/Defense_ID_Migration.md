# Defense ID Migration (tasks doc)

**Goal:** Use **stable string IDs** for defensive playcalls throughout runtime, persistence, and APIs so defense **display names** in the universal `defenses` collection can change without breaking scouting keys, `game_state`, stats rollups, or UI bindings.

**Design decision (locked):** **Canonical defense identity = universal `defenses.defense_id`** (slug string, e.g. `2-3-zone`, `base-man`). This matches existing seed scripts and is **stable across reseeds** when documents are upserted by `defense_id`. **Offense** remains **`play_id` = `str(plays._id)`** — the two domains intentionally differ; do not force Mongo `_id` hex for defense as “parity.”

**Current split (important):**
- **`playbook_settings.man_defense` / `zone_defense`** already use **logical IDs** (`man_normal`, `man_pressure`, `zone_23`, …) in many paths; see `BackEnd/utils/playbook_settings_utils.py` (`MAN_DEFENSE_ID_TO_NAME`, `ZONE_DEFENSE_ID_TO_NAME`, `DEFENSE_NAME_TO_ID`).
- **`game_state["defense_playcall"]`**, **`strategy_calls.defense_call`**, **`scouting_data["defense"]` keys**, **`populate_scouting_data()`**, **`team_manager` templates**, and much of **sim / phase_resolution / turn_manager** still use **display names** (`"Man"`, `"2-3 Zone"`, …).
- **`pc_order.defense`** is **partially** id-oriented: `normalize_pc_order_settings` resolves `defenseId` / `id` where present (`playbook_settings_utils.py`).

This migration is about **closing the gap**: one canonical **`defense_id`** everywhere runtime/persistence care, plus **reserved synthetic ids** for non-catalog rows (`vs_Fast_Break`, `FCP`, `HCT`, etc.). Use **`str(_id)`** only when issuing Mongo queries by primary key, not as the app-wide defense playcall string.

---

## 1. Code sweep — places to inspect or change

Below: **primary** files (high confidence) and **secondary** (verify during implementation). Line numbers drift; search by symbol.

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

### Phase 1 — Central resolution module ✅ (initial drop)

1. **`BackEnd/utils/defense_identity.py`** (implemented):  
   `resolve_to_defense_id`, `get_defense_doc`, `defense_display_name`, `is_zone_defense_id`, `refresh_defense_identity_cache`, `clear_defense_identity_cache`; synthetics `SYNTHETIC_DEFENSE_IDS`; playbook key maps; legacy Man / `Zone` dual-read.  
   **Tests:** `BackEnd/tests/test_defense_identity.py`.
2. **Next:** Refactor `defense_utils.py` to delegate zone/man checks to **`defense_id`** via `is_zone_defense_id` where callers have migrated; keep legacy `is_zone_defense(name)` until sim uses ids.

### Phase 2 — Scouting & template

1. Change `populate_scouting_data`, `team_manager` template, and `normalize_scouting_data_for_gameplay` to use **id keys** (with migration helper reading legacy name keys).
2. Update `training_execution_v2`, `stat_updater`, `phase_resolution`, `turn_manager` increment paths to use **id** keys.
3. Data migration script: rewrite `franchise_team_data`, `games.teams.*.scouting`, tournament docs — **or** lazy migration on read (prefer explicit script for prod clarity).

### Phase 3 — Game state & sim

1. Replace `defense_playcall` string literals in selection with ids; keep **display** resolution at API/UI edge.
2. Update `shot_manager`, `phase_resolution`, `rim_runner_fast_break`, `animator` branches to key off **id** or `is_zone` from DB metadata.
3. Update `strategy_calls.defense_call` contract (frontend + backend) to store id.

### Phase 4 — APIs & frontend surfaces

1. **GET /api/playbooks** / gameplan: ensure `man_defense_rows` / `zone_defense_rows` and turn payloads expose **id** as authority; names for labels only.
2. Update **FCC / tournament / training-report** scouting sections to iterate **template order** or **rows from API**, not raw `Object.entries(scouting_data.defense)` name keys.
3. **box-score.js:** resolve defense sections via id map or server-provided labels in EOG snapshot.
4. **Phaser** playcall UI: map id → label using cached defense list or turn payload `defense_display_name` if provided.

### Phase 5 — Tests, rollout, cleanup

1. Extend `test_training_system` and add defense id round-trip tests (init → sim turn → summarize → scouting keys).
2. Staging: verify franchise + tournament + single; box score; training report; playbooks save/load.
3. Remove dual-read after TTL; drop legacy name-key writes.

---

## 3. Out of scope / explicit risks

- **Renaming defenses in Mongo** before migration completes will still break in-flight games unless dual-read is deployed.
- **Third-party or cached** frontend bundles may assume string labels — version or feature-flag API responses if needed.
- **Distant sim / batch paths** (if any duplicate playcall logic) must be included in the same sweep as GP sim.

---

**Document status:** Task plan / sweep only — no implementation in this file.  
**Created:** April 2026.  
**Updated:** April 2026 — **canonical = `defense_id`** (user decision).
