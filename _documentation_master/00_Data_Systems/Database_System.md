# Database System

Top-level map of the MongoDB layer: every collection, what owns it, and the identity conventions used across the app. For the offensive/defensive play storage model, see `O_&_D_Plays_Collections.md` (canonical).

## Environment & Connection

- `BackEnd/db.py` defines nearly all collection handles; all code imports them from there. Two exceptions are created at point of use: `feedback_submissions` (`BackEnd/api/feedback_routes.py`) and `distant_training` (read via `db["distant_training"]` in `BackEnd/api/franchise_routes.py`).
- `MONGO_URI` selects the cluster; the database name comes from `MONGO_DB_NAME`, else the URI path (e.g. `/gob-staging`), else defaults to `gob` (prod).
- `.env.local` (if present) overrides `.env` for local dev.
- If `MONGO_URI` is unset or the client fails to init, `db.py` falls back to **mongomock** (used by tests).

## Collection Inventory

### Universal / seeded (baseline definitions; read-mostly at runtime)

| Collection | Purpose |
|---|---|
| `teams` | 128 base teams: name (school), mascot, colors, `conference`, `region`, prestige baselines |
| `players` | Baseline player pool keyed to base teams |
| `plays` | Canonical offensive play docs (skeletons, baselines) — see `O_&_D_Plays_Collections.md` |
| `defenses` | Canonical defenses (`defense_id`, `defense_type`, `zone_definitions`, `shift_triggers`) — seeded by `scripts/init_defenses_collection.py` and siblings |
| `fcp_skeletons` | Fast Court Press setup/animation skeletons |
| `hct_skeletons` | Half-court transition skeletons |
| `distant_training` | CPU-team training templates (`training_type`: tc/regular), seeded by `scripts/generate_distant_training_templates.py` |

### Mode state (created and written at runtime)

| Collection | Purpose |
|---|---|
| `games` | Live + completed game documents (per-game team/play/defense state) |
| `tournaments` | Tournament-mode master docs |
| `franchises` | Franchise master doc: week, schedule `results`, `season_news`, `season_inbox`, recruiting flags, user team fields |
| `franchise_team_data` (FTD) | Per-franchise, per-team state: plays copies, playbook settings, scouting, `natl_rank`, recruiting orders |
| `franchise_players_data` (FPD) | Per-franchise player docs: meta, attributes, position ratings, season/career stats |
| `franchise_recruits_data` (FRD) | Per-franchise recruit pool: attributes, archetype, `year`, `Home Region`, `Lean` |
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
