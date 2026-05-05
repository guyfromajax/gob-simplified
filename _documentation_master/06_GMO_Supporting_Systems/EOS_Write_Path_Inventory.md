# EOS write path inventory

Living reference for **who mutates** franchise postseason state (`week` 27–35, `conference_tournaments`, `region_tournaments`, `national_tournament`, `eos_tournament_active`, `results`, `games`) and how that lines up with the **single calendar funnel** and **`record_tournament_game_result`** write funnel.

## Region week 30 (calendar) vs meta

`get_eos_week_games(..., week=30)` lists **region R1** matchups from each region’s `round1`. When **both** feeder conferences are double-bye, `round1` is **empty** but `final[0]` already has two real teams — that final is **included** in week 30 meta as **round 2** (same shape as week 31) so `sim-rest` / `play-next` / status code never see an empty round.

## Core primitives (intended single doors)

| Primitive | Role |
|-----------|------|
| `franchise_tournament_progression.record_tournament_game_result` | Persist one EOS matchup outcome (games + bracket slot + idempotency rules). Does **not** bump franchise `week` by itself. |
| `_eos_calendar_advance_update_fields` (`franchise_routes.py`) | After a **completed EOS calendar week**’s results are committed in memory, advance bracket phase / `week` / `eos_tournament_active` in one place. Used by **complete-week finalize** and **`sim-rest-of-tournament`**. |
| `_training_status_reset_after_advance_to_week` | When leaving EOS-unfriendly training policy (not weeks 27–34), set `training_status` for the **destination** week. |

## HTTP / mainline franchise routes (`BackEnd/api/franchise_routes.py`)

| Entry / function | EOS mutations | Funnel |
|------------------|---------------|--------|
| `_finalize_franchise_week_after_cpu_games` | `results`, `week`, week 26 → init conferences + `eos_tournament_active`; EOS weeks via `_eos_calendar_advance_update_fields`; training reset helper | **Calendar funnel** + progression on user/CPU paths before finalize |
| `POST /franchise/sim-rest-of-tournament` | CPU/distant sims → `ftp.record_tournament_game_result`; `results`; `_eos_calendar_advance_update_fields`; training helper | **Yes** |
| `POST /franchise/complete-week` (+ phase A / start-cpu-sims / phase B) | User block + `_complete_week_finish_cpu_and_persist` → `_finalize_franchise_week_after_cpu_games` | **Yes** (via finalize) |
| `POST /franchise/sim-championship` | National final: `ftp.record_tournament_game_result` + `ftp.advance_national_bracket` + `$set` national / `eos_tournament_active` / `week` 35 + training reset for 35 | **Record funnel** for the game; **calendar tail** is championship-specific (must **not** call `_eos_calendar_advance_update_fields(34)` again — that would **double** `advance_national_bracket`) |
| `_eos_heal_conference_eos_from_games` (phase B preflight) | Sync `results` / bracket from `games`; `_eos_advance_all_conference_brackets_until_idle`; `$set` `results` / `conference_tournaments` only | **Repair / heal**, not calendar week advance |
| `_eos_advance_all_conference_brackets_until_idle` | In-memory + persisted via heal patch | Helper for heal only |

## Progression module (`BackEnd/tournament/franchise_tournament_progression.py`)

- **`record_tournament_game_result`**: delegates bracket writes to `franchise_tournament.save_*` internally; main **game outcome** funnel.
- **`advance_conference_bracket` / `advance_national_bracket`**: wrappers used by `_eos_calendar_advance_update_fields` and heal loops — not HTTP entry points.

## Repair / admin (`BackEnd/utils/repair_franchise_eos_bracket.py`, `scripts/repair_franchise_eos_bracket_from_results.py`)

- **`repair_franchise_eos_bracket_from_results`**: backfills bracket from `results` / `games` via `_sync_eos_bracket_from_existing_game_doc` → **`record_tournament_game_result`**. Optional Mongo persist of tournament keys only — **no franchise `week` bump**.

## Out of scope for this table

- **Command-center reads** (`GET /franchise/command-center/data`): no writes.
- **`flask_app.py`**: legacy franchise routes checked — **no** duplicate EOS week writers found for the paths above.

## Maintenance rule

When adding a new code path that **bumps `franchise.week` during 27–34** or **initializes/advances** EOS bracket blobs:

1. Prefer **`ftp.record_tournament_game_result`** for any new “game finished” write.
2. Prefer **`_eos_calendar_advance_update_fields`** for the same **calendar** transitions already handled after a full EOS week’s sims (unless the case is **championship-only**, like `sim-championship`).

Last reviewed: codebase inventory pass (automated grep + manual read of `sim_championship`, heal, repair).
