# Database System

Top-level map of the MongoDB layer: every collection, what owns it, and the identity conventions used across the app. For the offensive/defensive play storage model, see `O_&_D_Plays_Collections.md` (canonical).

## Environment & Connection

- `BackEnd/db.py` defines nearly all collection handles; point-of-use exceptions are documented beside their callers.
- `BackEnd/env_config.py` resolves the application environment before `db.py` opens a client.
- Real Mongo requires both `MONGO_URI` and `MONGO_DB_NAME`; the explicit name must match the URI path and the `ENVIRONMENT` target.
- Ordinary local startup requires repository-root `.env.local` and permits `gob-staging` only. There is no `.env` fallback and no implicit production default.
- Railway uses injected process variables and does not load a repository env file.
- Tests select in-memory Mongo explicitly with `GOB_DB_MODE=mongomock`, `ENVIRONMENT=test`, and a non-live database name such as `gob-test`.
- Missing, malformed, or failed real Mongo configuration does not fall back to mongomock.
- Maintenance scripts use `BackEnd/script_db.py`, require an explicit target and access
  intent, and enforce read-only mode at the operation boundary. See
  [Environment_Operations.md](../00_Operations/Environment_Operations.md).

## Collection Inventory

### Universal / seeded (baseline definitions; read-mostly at runtime)

| Collection | Purpose |
|---|---|
| `teams` | 128 base teams: name (school), mascot, colors, `conference`, `region`, prestige baselines |
| `players` | Baseline player pool keyed to base teams |
| `plays` | Canonical offensive play docs (skeletons, baselines) — see `O_&_D_Plays_Collections.md` |
| `defenses` | Canonical defenses (`defense_id`, `defense_type`, `zone_definitions`, `shift_triggers`) — maintained and published by `scripts/publish_defenses.py` |
| `fcp_skeletons` | Fast Court Press setup/animation skeletons |
| `hct_skeletons` | Half-court transition skeletons |

### Mode state (created and written at runtime)

| Collection | Purpose |
|---|---|
| `games` | Live + completed game documents (per-game team/play/defense state) |
| `tournaments` | Tournament-mode master docs |
| `franchises` | Franchise master doc: week, schedule `results`, `season_news`, `season_inbox`, recruiting flags, user team fields; **`applied_games`** (finalized game `_id` strings) and **`applied_matchups`** (franchise-week matchup keys for stat rollup idempotency — see `Box_Score_System.md` §5) |
| `franchise_team_data` (FTD) | Per-franchise, per-team state: plays copies, playbook settings, scouting, `natl_rank`, recruiting orders |
| `franchise_players_data` (FPD) | Per-franchise player docs: meta, attributes, position ratings, season/career stats, and the top-level identity/development carry — `entry_tier`, `position_intent`, `potential_factor`, plus the `development` subdoc (`peak_count`, `peak_rungs`, `family_timing`, `ch_seed`, `ht_total`) and `training_position`/`coaching_quality` (see `PLAYER_DEV_CARRY_FIELDS`) |
| `franchise_recruits_data` (FRD) | Per-franchise recruit pool: attributes, `entry_tier`, `position_intent`, `potential_factor`, `development`, `year`, `Home Region`, `Lean`. `archetype` is a **derived display label** (from position_intent+tier), not a generation input |
| `franchise_state` | **Deprecated** single-state doc; only read as a backward-compat fallback for user-team resolution |
| `training_sessions` | Training run log |

### Accounts & platform

| Collection | Purpose |
|---|---|
| `users` | Auth + profile; career `record`, coaching `archetypes`, `lead_archetype` (see `00_General_Systems/Coaching_Archetype_System.md`) |
| `password_reset_tokens` | Password reset flow |
| `alpha_otps` | OTP codes for gated alpha signup |
| `access_code_requests` | "Request Access Code" submissions (admin fulfills manually) |
| `alpha_feedback` | Alpha feedback survey responses (lazily created on first insert) |
| `press_conference_sessions` | Press conference session state |
| `community_highlights` | Community highlights feed entries |
| `feedback_submissions` | User feedback form submissions (`BackEnd/api/feedback_routes.py`) |

Note: Mongo creates collections lazily on first write. As of 2026-06, `training_sessions`, `franchise_state` (deprecated), and `alpha_feedback` are defined in code but have never been written on prod `gob`, so they don't appear there.

## Identity Conventions

- Mongo `_id` stays `ObjectId` inside a collection; app/runtime logic uses the **stringified** `_id` (team ids, player ids, `play_id`).
- `name` is display text, never canonical identity.
- Franchise child collections are keyed by `franchise_id` + entity id, with unique compound indexes (see below). **Type caution:** FTD stores `franchise_id` as `ObjectId`; FPD/FRD store it as a **string**. Queries must match the stored type, and `db.teams` lookups must convert string ids back to `ObjectId`.
- Defense identity is migrating from name-based to `defense_id` (see `tasks/Defense_ID_Migration.md`); most persisted settings are still defense-name keyed.

## Adding New Teams & Players (manual seeding)

**New team** — provide: `name`, `team_id`, `primary_color`, `secondary_color` (see `teams` fields above; `player_ids` and optional `mascot` round out the doc).

**New player** — provide:

- `first_name`, `last_name`, `team`
- attributes (`SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT`); anchor values set equal to these. `EM`, `MO`, `CH` initialized at 0 (game/mode init overwrites `CH` and `EM` 1–100, `MO` stays 0)
- `jersey`, `year`, `height`, `weight`
- the identity/development carry — `entry_tier`, `position_intent`, `potential_factor`, and a `development` profile (the generator logs loudly when `potential_factor`/`entry_tier` are missing, and `develop_rollover` lazy-backfills a missing `development` once). Prefer generating via `generate_player` so these are populated correctly rather than hand-seeding.
- headshot: until specified otherwise, all new players use `/static/images/players/generic_headshot.png` (set `photo` to that path)

## Indexes (ensured at startup, idempotent)

- `franchise_team_data`: unique `(franchise_id, team_id)`
- `franchise_players_data`: unique `(franchise_id, player_id)`
- `franchise_recruits_data`: unique `(franchise_id, recruit_id)`
- `games`: `franchise_id`
- `franchises`: `user_id`
- `users`: unique sparse `username_lower`

## Related Docs

- `_documentation_master/00_Data_Systems/O_&_D_Plays_Collections.md` — play/defense storage model (canonical)
- `_documentation_master/00_Data_Systems/Games_Collection.md`
- `_documentation_master/03_Data_Persistence/Data_Persistence_System.md`
- `_documentation_master/06_GMO_Supporting_Systems/Mode_Init_System.md`
