# Post-game flow: Phase A / Phase B split

This document inventories today’s `POST /franchise/complete-week` behavior and outlines the work plan to split **Phase A** (user game fully persisted, EOG/box score safe) from **Phase B** (CPU games, full week `results`, week advance, recruiting/rank/prestige, EOS transitions).

## Status (implementation)

- **2026-04-23:** `POST /franchise/complete-week/phase-a` added.
- **2026-04-23 (frontend):** `finalizeGame.js` calls **phase-a** with “Saving game…”, then EOG **Sim Computer Games** and box-score pending path call **`POST /franchise/complete-week/phase-b`** with `{ franchise_id, week }`. `localStorage.franchise_complete_week_pending` stores that minimal object (legacy `{ body }` still POSTs monolithic `complete-week`). Monolithic **`POST /franchise/complete-week`** remains (user block + CPU + advance); shared **`_complete_week_finish_cpu_and_persist`** clears **`post_game_status.phase_a_user_week`** after a full persist.
- **2026-04-23 (backend):** **`POST /franchise/complete-week/phase-b`** — requires franchise `week ==` request week, phase-a flag, and non-empty `results[week]`; idempotent if franchise `week` already advanced past request. **`CompleteWeekPhaseBRequest`:** `franchise_id`, `week` only. It runs the same user-game pipeline as monolithic `complete-week` (via `_complete_week_process_user_game_block`), merges the user matchup into `franchise.results[str(week)]`, `$set`s `season_inbox`, and sets `post_game_status.phase_a_user_week` for idempotency. Monolithic `complete-week` skips re-processing the user game when that flag matches the request week **and** `results[week]` is a non-empty list (so Phase A → `complete-week` does not double-finalize or double-award user GP). **Phase B** is still the existing CPU loop + week advance inside `complete-week`; a dedicated Phase B route and frontend wiring are not done yet.

## API routing (short-term vs long-term)

| Horizon | Endpoint(s) | Role |
|--------|---------------|------|
| **Long-term (target)** | `POST /franchise/complete-week/phase-a` then `POST /franchise/complete-week/phase-b` | Canonical split: Phase A saves the user game before EOG/box score; Phase B runs CPU games, full-week `results`, recruiting/rank/prestige, EOS transitions, and `week` advance. Explicit intent, easier idempotency and monitoring. |
| **Short-term (fallback)** | `POST /franchise/complete-week` | Keep the **monolithic** handler until the new flow is fully wired and stable. Means “user + CPU + advance” in one call when Phase A was never used; when Phase A already ran, the server can skip the user block (see Status above). Legacy clients and escape hatch during rollout. |
| **Deprecation** | Eventually | Once all paths use phase-a + phase-b, narrow or remove monolithic `complete-week` (e.g. require an explicit `phase: full` body flag, or return 410 and document migration). |

## References (current code)

| Area | Location |
|------|----------|
| Phase A endpoint | `BackEnd/api/franchise_routes.py` — `complete_week_phase_a()` |
| User-game block (shared) | `BackEnd/api/franchise_routes.py` — `_complete_week_process_user_game_block()` |
| Week schedule resolution (shared) | `BackEnd/api/franchise_routes.py` — `_resolve_complete_week_week_games()` |
| Phase B endpoint | `BackEnd/api/franchise_routes.py` — `complete_week_phase_b()` → `_complete_week_finish_cpu_and_persist()` |
| Main handler — monolith / fallback | `BackEnd/api/franchise_routes.py` — `complete_week()` |
| Game row upsert (scores on `games` collection) | `BackEnd/api/franchise_routes.py` — `_save_game_result()` (~L1613+) |
| Franchise finalize + phase A / EOG sim button | `FrontEnd/static/js/phaser/finalizeGame.js`; EOG UI `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`; box-score fallback `FrontEnd/static/box-score.js` (`franchise_complete_week_pending`) |
| Training distant idempotency pattern (prior art) | `training_status.cpu_distant_complete_week` in `franchise_routes.py` + `BackEnd/utils/franchise_training_state.py` |

---

## Inventory: `complete_week` in execution order

Steps are listed in the order they run today. Tags:

- **A** — belongs in Phase A (user game durable before EOG UI).
- **B** — belongs in Phase B (depends on full week or CPU work).
- **A + B** — user slice in A; CPU slice in B (same loop structure, split boundary).
- **End** — week-close persistence (currently one `$set`; may move entirely to B or split carefully).

| # | Step (summary) | Tag | Notes |
|---|----------------|-----|--------|
| 1 | Load franchise, resolve schedule / EOS `week_games` / `week_games_meta`, user team | **A/B shared** | Same setup for both phases. |
| 2 | `_save_game_result(...)` for **user** matchup → `games` collection | **A** | Updates scores on the user’s game doc (with `game_id`). |
| 3 | Append user row to in-memory `results` | **A** | Today this is only written to DB at step 24–25. **Phase A must persist the user’s row** into `franchise.results[str(week)]` (merge or replace-with-partial) so W/L and PF/PA views that read `results` stay consistent. |
| 4 | EOS: `save_*_game_result` for **user** bracket slot | **A** | When `week_games_meta` + `user_game_id` and user found in week. |
| 5 | `maybe_award_franchise_win_geek_points` / loss / EOS title (user game) | **A** | User matchup only. |
| 6 | Persist `game_document` snapshot → `games` (`$set`, upsert) if provided | **A** | Removes race with Q4 save. |
| 7 | `stat_updater.finalize_game(user_game_id, franchise, …)` | **A** | Player/team stat finalization for user game. |
| 8 | `_finalize_team_attributes_for_game` (user game) | **A** | Post-game team attributes on game doc / FTD paths used by EOG. |
| 9 | `season_inbox` entry for user game (in-memory on `franchise_doc`) | **A** | Today committed only in final `update_fields` (**End**). Phase A should `$set` inbox (and any other user-only franchise fields) when A completes. |
| 10 | Legacy branch: lookup game by week + teams if no `game_id` | **A** | Same finalize + attrs + inbox pattern. |
| 11 | Batch-load FTD prestige / `total_player_attrs`, team conferences | **B** | Feeds distant sim and partition logic for **non-user** games. |
| 12 | **For each non-user week game:** load existing `games` doc or sim (distant / `run_simulation`) | **B** | Includes `_persist_distant_franchise_game`, `finalize_game` for CPU games, `_finalize_team_attributes_for_game` for CPU games, EOS bracket saves, `_award_gp_sim` for CPU games. |
| 13 | `existing_results[str(req.week)] = results` (full list) | **B** | **Critical:** Today the franchise’s authoritative week results array is only updated here. Phase A should write **at least** the user row; Phase B should **merge** CPU rows without dropping the user row (idempotent retries). |
| 14 | `_apply_complete_week_recruiting_lean_updates(franchise_doc, week, results)` | **B** | Uses **full** `results` for the week. |
| 15 | `_apply_regular_season_rank_prestige_updates(...)` | **B** | Weekly rank/prestige after full week (see `Rank_Prestige_System.md`). |
| 16 | Build `update_fields`: `results`, `week` → `next_week`, `season_inbox`, training reset, EOS bracket fields | **B** (mostly) | `season_inbox` user line ideally already applied in A; final pass can still include full inbox if single source of truth is one `$set`. |
| 17 | EOS: init conference tournaments (week 14), advance brackets, region/national init | **B** | Depends on complete week / bracket state. |
| 18 | `db.franchises.update_one(..., {"$set": update_fields})` | **End** | Today one write; split implies **Phase A** `$set` (user game + partial `results` + inbox + flags) and **Phase B** `$set` (merge results, advance week, recruiting, rank/prestige, EOS). |
| 19 | Week 35 awards: `_persist_week_35_awards_if_needed` | **B** | When `update_fields.week == 35`. |
| 20 | Return `{ week, results: scoreboard }` | **A / B** | Phase A response should confirm user persistence; Phase B returns full scoreboard + new `week`. |

### `games` vs `franchise.results`

- **`_save_game_result`** only updates the **`games`** collection. It does **not** update `franchise.results` by itself.
- **Team records / W–L / PF–PA** for franchise mode are derived from **`franchise.results`** (see comment on `_save_game_result` and franchise docs). Therefore Phase A **must** update `franchise.results[week]` to include the user outcome (or an equivalent canonical field), not rely on the in-memory `results` list that is only flushed at the end today.

---

## Work plan

### 1. API shape

- [x] **Chosen:** `POST /franchise/complete-week/phase-a` (done) + **`POST /franchise/complete-week/phase-b`** (target). **Short-term:** keep `POST /franchise/complete-week` as fallback monolith until frontend and Phase B route are solid.
- [x] Phase A request body matches current `CompleteWeekRequest` (`franchise_id`, `week`, `result`, `game_id`, `game_document`).
- [ ] Phase B: define body (likely minimal: `franchise_id`, `week`; optionally scores/game id for validation) and JSON responses (full scoreboard + new `week` + EOS fields as needed).

### 2. Phase A implementation (server)

- [x] Extract steps tagged **A** into a callable used by the new endpoint (`_complete_week_process_user_game_block`).
- [x] **Persist `franchise.results[str(week)]`** with user game row (`_merge_phase_a_user_row_into_week_results`).
- [x] **`$set` `season_inbox`** on phase-a completion.
- [x] **Week-scoped flag** `post_game_status.phase_a_user_week` set when A succeeds; `complete-week` skips user block when flag + non-empty `results[week]`.
- [x] Double Phase A: second call returns `{ idempotent: true }` without re-running user pipeline.

### 3. Phase B implementation (server)

- [x] Extract CPU + recruiting + rank/prestige + EOS + `week` advance into **`_complete_week_finish_cpu_and_persist`**; **`complete_week`** and **`complete_week_phase_b`** both call it.
- [x] **`phase-b`** requires Phase A flag + non-empty `results[week]`; franchise `week` must equal request week (409 / 400 otherwise).
- [x] **Merge** into `results[week]`: starts from DB `results[week]` list; CPU loop appends/skips user matchup.
- [x] Idempotent **phase-b** if `franchise_doc.week > req.week` (week already advanced).
- [x] Clear **`post_game_status.phase_a_user_week`** on successful persist inside finish helper.

### 4. Frontend (`finalizeGame.js` and EOG / box score UI)

- [x] After user game ends: call **Phase A** first; status **“Saving game…”** (not CPU sim).
- [x] On success: EOG popup; **Sim Computer Games** runs **`complete-week`** then navigates to FCC; double-submit: button disabled while in flight.
- [x] Box-score path: **localStorage** `franchise_complete_week_pending` so **Back to Locker Room** can run **`complete-week`** after box score (final games only).
- [ ] On load / command center: if week not advanced but phase-a done, **resume Phase B** (auto or banner) without relying on localStorage alone.
- [ ] Phase B: training-style **pulse + rotating copy** until complete (currently static “Simulating Computer Games…”).

### 5. CPU sim highlight copy (Phase B UX)

- [ ] Spec structured inputs (matchups, scores, upsets, user conference) and implement a small builder (parallel to `training_loading_highlights.py`, separate module).

### 6. Tests

- [ ] Phase A twice: same week → no duplicate GP / finalize side effects.
- [ ] Phase B twice: no duplicate week increment / recruiting / rank-prestige.
- [ ] Phase B after Phase A: full `results[week]` matches expected length; user row preserved.
- [ ] Simulated refresh: Phase A committed, Phase B not run → resume completes week.
- [ ] Optional: regression extend `tests/test_franchise_complete_week.py` for split endpoints.

### 7. Documentation updates (after implementation)

- [x] `docs/docs_1_systems/05_GP_Supporting_Systems/End_Of_Game_System.md` — two-step flow (phase-a / phase-b, monolith fallback, box-score flag, key files).
- [ ] `docs/Franchise_Mode/Franchise_Weekly_Database_Saves.md` — Phase A vs B writes.

---

## Open design choices (to decide during implementation)

1. **Partial `results[week]`:** Array with only user game until B runs vs. placeholder objects for unplayed CPU slots. Prefer whatever standings code tolerates without showing false 0–0 games.
2. **Single vs. multiple franchise `$set`:** Phase A write + Phase B write vs. transactional script; favor clarity and idempotency over a single write if retries matter.
3. **Legacy clients:** **Short-term:** yes — monolithic `complete-week` remains the fallback. **Long-term:** deprecate or restrict once phase-a + phase-b are the only supported paths.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-04-20 | Initial inventory and work plan from `complete_week` trace. |
| 2026-04-23 | Phase A route + shared helpers; `complete-week` respects `phase_a_user_week`. API routing: target `phase-b` long-term; `complete-week` short-term fallback (see section above). |
| 2026-04-23 | **`phase-b`** endpoint + **`_complete_week_finish_cpu_and_persist`**; frontend EOG/box-score call `phase-b` with `{ franchise_id, week }`. |
