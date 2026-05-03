# Parallel franchise CPU sims and week finalization — work plan

**Location:** `_documentation_master/projects/` (canonical project plan)  
**Status:** Planning  
**Goal:** Run CPU game sims in parallel (server-side) while the user plays their franchise game; separate **per-game persistence** from **week-level closure** (rankings, stat leaders, week advance, etc.) behind a single idempotent `try_finalize_week`-style gate.  
**Explicitly out of scope for this milestone:** Quarter checkpoints / resume abandoned user games (may follow as phase 2 once this spine exists).

---

## 1. Documentation baseline (read first)

| Doc | Why |
|-----|-----|
| `_documentation_master/05_GP_Supporting_Systems/End_Of_Game_System.md` | Canonical EOG flow, phase A / phase B split, monolith fallback, box-score `post_game_phase_b=1`. |
| `_documentation_master/06_GMO_Supporting_Systems/Press_Conference_System.md` | How PGPC overlaps phase B today; product decision if PGPC is removed or deferred. |
| `docs/To Do/Post_Game_Split.md` | Deeper design notes on the split (if still current). |

---

## 2. Current system — traced code path (inventory)

Use this as the checklist when refactoring so nothing is dropped.

### 2.1 Client: user game complete → phase A → EOG → phase B kickoff

1. **`FrontEnd/static/js/phaser/gameScene.js`** — Detects Q4 / OT end, drives completion UI.
2. **`FrontEnd/static/js/phaser/finalizeGame.js`** — Franchise: shows “Saving game…”, `POST /franchise/complete-week/phase-a` with `CompleteWeekRequest` body (`franchise_id`, `week`, `game_id`, `result`, optional `game_document`). On success sets `localStorage.franchise_complete_week_pending` = `{ franchise_id, week }` and passes `franchisePhaseBPending` into the EOG popup payload.
3. **`FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`** — When franchise completion modal is shown, calls **`getOrStartFranchisePhaseB(franchisePhaseBPending)`** so phase B starts in the background (not gated on PGPC button).
4. **`FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js`** — Single-flight `POST /franchise/complete-week/phase-b` per `franchise_id:week` key.
5. **`FrontEnd/static/js/phaser/utils/postGamePressConference.js`** — Attaches to the **same** phase-b Promise after PGPC flow; clears pending on success / handles errors.
6. **`FrontEnd/static/box-score.js`** — `setupLockerRoomButton()`: pending week + URL alignment can trigger phase-b / overlay (`pageLoadOverlay`); legacy path may POST monolithic `/franchise/complete-week`.

### 2.2 Server: phase A → phase B → single “finish week” function

| Step | Location | Role |
|------|----------|------|
| Phase A | `BackEnd/api/franchise_routes.py` — `complete_week_phase_a` | `_complete_week_process_user_game_block`: user game → `games` / inbox / `results[week]` user row, EOS user bracket saves, GP, etc. Persists `post_game_status.phase_a_user_week`, merges `results.{week}`, optional EOS tournament blobs. |
| Phase B | `complete_week_phase_b` | Reloads franchise; requires phase A + non-empty `results[week]`; builds `results` copy from DB; calls **`_complete_week_finish_cpu_and_persist`**. Idempotent if `franchise.week` already advanced past `req.week`. |
| Monolith | `complete_week` | User block + `_complete_week_finish_cpu_and_persist` (or skip user block if phase A already wrote the week). Escape hatch for old clients. |
| CPU + week | `_complete_week_finish_cpu_and_persist` | Loops non-user week games: distant vs full `run_simulation` path; `_save_game_result`, EOS `save_*_game_result`, `_award_gp_sim`; builds full `results` list; then **in the same function**: recruiting lean updates, `_apply_regular_season_rank_prestige_updates`, EOS advance/init, `update_fields` with **`week` → next week**, franchise `update_one`, clears `post_game_status`, etc. |

**Important observation for the plan:** Rank/prestige, recruiting aggregates, week bump, and EOS conference advancement currently run **after** the CPU loop has produced a **complete** `results` week list inside `_complete_week_finish_cpu_and_persist`. That is the blob to tease apart: **per-game writes** vs **`try_finalize_week` (week closure)**.

### 2.3 Related systems (flag for dependency analysis)

- **`BackEnd/tournament/franchise_tournament.py`** — EOS weeks, `get_eos_week_games`, `save_conference_game_result`, `advance_*` (must stay consistent with any new ordering).
- **Distant sim / training** — `training_status.cpu_distant_complete_week` and related paths (ensure parallel CPU jobs do not fight distant-complete semantics).
- **`docs/To Do/indempotency_analysis.md`** — Align with any existing idempotency notes.

---

## 2.4 Phase 0 inventory — `_complete_week_finish_cpu_and_persist` (completed)

**Source:** `BackEnd/api/franchise_routes.py`, function `_complete_week_finish_cpu_and_persist` (CPU `for` loop ends where `existing_results` is assigned from the built `results` list).

### A. Before the CPU loop (context only)

| Item | What happens |
|------|----------------|
| FTD batch load | `franchise_team_data_collection.find` — prestige, `total_player_attrs`, chemistry (for distant sim inputs). |
| Conference map | `db.teams.find` for `team_ids_for_conf` — used for regular-season distant vs full-sim routing. |

### B. Inside the CPU loop (per non-user matchup) — **per-game** side effects today

Each iteration may: read `db.games` for existing doc; `_sync_eos_bracket_from_existing_game_doc` (mutates `franchise_doc` in memory); `_persist_distant_franchise_game` / `_save_game_result` (writes `games` + franchise result rows per existing patterns); `run_simulation` + `db.games.update_one` + `stat_updater.finalize_game` + `_save_game_result` + `_finalize_team_attributes_for_game`; `ft.save_conference_game_result` / `save_region_game_result` / `save_national_game_result` (mutates `franchise_doc`); `_award_gp_sim` → `maybe_award_franchise_*` geek points (DB). Appends one row to in-memory `results`.

**Note:** Phase A has already merged the **user** row into `results`; this loop only appends **CPU** rows. Full `results` for the week exists only after the loop completes.

**Note:** Franchise **league stat leaders** (if updated for franchise mode) are not referenced after the loop in this function; they may be updated inside **`stat_updater.finalize_game`** on each full-sim CPU game. Confirm in `stat_updater` if any logic still assumes a “week closed” batch elsewhere.

### C. Immediately after the CPU loop (aggregate / week-level) — **candidates for `try_finalize_week`**

| Order | Call / step | Needs full week `results`? | Notes |
|-------|-------------|------------------------------|--------|
| 1 | `existing_results[str(week)] = results` | Yes — assigns **complete** week list into `franchise_doc`-backed dict | Today overwrites entire week key; parallel design may move to merge-by-slot. |
| 2 | `_apply_performance_based_recruiting_lean_updates(franchise_doc, week, results)` | **Yes for faithful behavior** | Iterates all `results` rows; uses FTD `natl_rank` and recruit pool; sets `recruiting_performance_lean_applied.{week}` on franchise when done. Could be refactored per-game with care (ordering / duplicate rolls). |
| 3 | `_apply_complete_week_recruiting_lean_updates(franchise_doc, week, results)` | **Yes** | Weeks 20–26 only; `_team_outcomes_by_week_results(results)`; updates `franchise_recruits_data`; clears `recruit_visit` on FTD; sets `recruiting_lean_updates_applied.{week}`. |
| 4 | `_apply_regular_season_rank_prestige_updates(franchise_id, franchise_doc, week, results)` | **Yes** | Regular season weeks only (v2 gate); loops every result for SOS/prestige deltas; `calculate_franchise_standings(results_snapshot, …)` with **full** `results` including this week; bulk `franchise_team_data_collection.update_one` per team; sets `RANK_PRESTIGE_LAST_APPLIED` (field constant) on franchise. |
| 5 | Build `next_week` and base `update_fields` | Yes (branching uses `week` + EOS state on `franchise_doc`) | `$set`: `results`, `week` → `next_week`, `season_inbox`, `training_status.training_completed`, `training_status.session_type`. |
| 6 | **If `week == REGULAR_SEASON_WEEKS`** | EOS init | Re-queries FTD for team ids; `ft.initialize_conference_tournaments`; `maybe_award_conference_rs_championship`; overrides `update_fields.week` to first EOS conference week; sets `conference_tournaments`, `eos_tournament_active`. |
| 7 | **`elif week in EOS_WEEKS`** | Bracket **advance** + next EOS week | **Conference weeks:** `advance_conference_bracket` for conferences 1–16 (mutates `franchise_doc`); may init **region** tournaments and jump week; **region weeks:** may init **national**; **national weeks:** `advance_national_bracket`; last week clears `eos_tournament_active`, sets week **35**. All copy tournament blobs from `franchise_doc` into `update_fields`. |
| 8 | `db.franchises.update_one(..., {"$set": update_fields})` | — | Single persist for franchise document fields above + `post_game_status.phase_a_user_week: None` + optional `community_highlight_pending`. |
| 9 | `flush_community_highlight_pending_after_week(franchise_id, week)` | Week completed | Separate try/except; may touch highlights / related collections. |
| 10 | If `update_fields.get("week") == 35` | Post-season capstone | Reload franchise; `_persist_week_35_awards_if_needed`. |
| 11 | Return payload | — | Builds `scoreboard` from `results` + `db.teams` names (read-only for response). |

### D. Classification summary

| Bucket | Members |
|--------|---------|
| **Per-game (already parallel-shaped or loop-local)** | Distant/full sim persistence, `games` collection, `stat_updater.finalize_game`, `_finalize_team_attributes_for_game`, EOS `save_*` on `franchise_doc`, `_award_gp_sim` / geek point writes, `results.append`. |
| **Week closure (needs all CPU rows + user row, or equivalent merge)** | Full `results` write, both recruiting lean passes, rank/prestige v2, `update_fields` week/training/inbox, EOS **advance/init** branches, single `franchises.update_one`, community highlight flush, week-35 awards. |

### E. Product / planning (still open)

- [ ] **Product sign-off:** Remove PGPC vs keep vs feature-flag; **when** to start background CPU jobs (tip-off vs other trigger).

---

## 3. Target architecture (conceptual)

1. **Per-game finalization (parallel-safe, idempotent)**  
   For each CPU matchup (keyed by franchise + week + stable game/slot id): persist game doc, franchise result row, EOS slot if applicable, per-game GP, etc. Safe to retry; no “full week” assumptions.

2. **Week finalization (`try_finalize_week` or equivalent)**  
   Single server entry that runs **only if** predicate is true, e.g.  
   `user_game_final_for_week_W` **and** `all_cpu_games_final_for_week_W`.  
   Contains: national/league rankings that need full slate, stat leaders, `week` advance, inbox/training flags, EOS **advance** steps that assume R1 complete, etc. **Must be safe to call multiple times** (conditional update / “already finalized” marker).

3. **Client**  
   - Optionally start CPU job batch when user **starts** week W game (or another agreed trigger).  
   - EOG: phase A unchanged in principle (user final).  
   - Navigation: poll or subscribe to **week closure status**; if PGPC removed, simplify CTAs per product spec.

---

## 4. Suggested implementation phases (execution order)

### Phase 0 — Work plan + spike (this doc + half day)

- [x] Walk `_complete_week_finish_cpu_and_persist` end-to-end and list **every** side effect after the CPU `for` loop — see **§2.4 Phase 0 inventory**.
- [x] Confirm **which** effects require “full `results` list” vs per-game — see **§2.4** tables **B** vs **C/D**.
- [ ] Product sign-off: remove PGPC vs keep; when to start background jobs.

### Phase 1 — Extract week closure (no behavior change)

- [x] Introduce a dedicated week-closure function containing post–CPU-loop logic — implemented as **`_finalize_franchise_week_after_cpu_games`** in `franchise_routes.py`, called only from **`_complete_week_finish_cpu_and_persist`** (same call site as before; behavior preserved).
- [ ] Add unit/integration tests: double-call → second call no-op; “user last” vs “CPU last” ordering simulated by calling finalize from two call sites in tests (deferred until Phase 2 idempotency work; optional smoke test can call Phase B twice with idempotent response today).

### Phase 2 — Per-game idempotent CPU persistence

- [x] Stable matchup id: **`_week_result_matchup_key`** (documented) plus **`_expected_franchise_week_matchup_key_set`**, **`_week_results_list_contains_matchup`**, **`_franchise_week_results_cover_schedule`** in `BackEnd/api/franchise_routes.py`.
- [x] Dedupe at CPU loop start (**`_dedupe_franchise_week_results_by_matchup`**); skip CPU iterations when that matchup already appears in `results`; gate closure with **`_try_finalize_franchise_week_if_complete`** → **`_finalize_franchise_week_after_cpu_games`** only when the schedule is fully covered (else **HTTP 500**, no week advance).
- [ ] Optional: external job pool invoking **`_try_finalize_franchise_week_if_complete`** after each per-game persist (not needed for current in-process `ThreadPoolExecutor` phase B).

### Phase 3 — Parallel execution

- [x] **In-process parallel (phase B unchanged from client):** full `run_simulation` CPU games are batched with **`ThreadPoolExecutor`** (`as_completed`); DB / EOS / GP persist **sequentially** in schedule index order. Env **`FRANCHISE_CPU_SIM_MAX_WORKERS`** (default **4**, minimum 1). Helpers: **`_run_franchise_cpu_full_simulation_core`**, **`_franchise_cpu_full_sim_max_workers`**, **`_order_franchise_week_results_like_schedule`** in `franchise_routes.py`. Log line **`[COMPLETE-WEEK-PHASE3]`**.
- [ ] Optional later: separate worker process / queue, start jobs earlier than EOG, or client polling (not required while phase B stays one HTTP request).

### Phase 4 — UX + cleanup

- [ ] EOG modal: “Go To Locker Room” vs “simming…” modal per spec; auto-navigate when closure completes if user already dismissed EOG to waiting UI.
- [ ] Remove or feature-flag PGPC if approved.
- [ ] Update `End_Of_Game_System.md` and `Press_Conference_System.md` to match shipped behavior.

---

## 5. Observability (add early)

- Log **predicate inputs** at `try_finalize_week`: counts finalized vs expected for week W.
- Log outcome: `waiting` | `ran_closure` | `already_finalized` | `error`.
- Optional: metric for time from phase A success to week closure.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Partial week in DB after abandon | No final user row until phase A; CPU rows may exist — document “week not closed”; idempotent CPU writes. |
| Duplicate phase B / duplicate jobs | Single-flight client + server idempotency keys; `try_finalize_week` conditional write. |
| EOS bracket half-updated | Per-game EOS saves already exist; closure step only advances when predicate true (align with `franchise_tournament` invariants). |
| Long request timeouts | Phase B already heavy; parallel + smaller requests or server-side job + polling reduces gateway timeouts. |

---

## 7. Next concrete step

Phase 0 **code inventory is done** (§2.4). **Phase 1:** `_finalize_franchise_week_after_cpu_games`. **Phase 2:** matchup keys, dedupe, skip-if-present, **`_try_finalize_franchise_week_if_complete`**. **Phase 3 (in-process):** parallel full CPU sims inside phase B; **`FRANCHISE_CPU_SIM_MAX_WORKERS`**. **Next:** optional separate job queue / earlier triggers; tests; product sign-off for PGPC if still open.

---

## 8. File index (quick reference)

| Area | Files |
|------|--------|
| EOG + phase A | `finalizeGame.js`, `End_Of_Game_System.md` |
| Phase B trigger | `gameCompletionPopup.js`, `franchisePhaseBClient.js`, `postGamePressConference.js` |
| Box score pending | `box-score.js`, `pageLoadOverlay.js` |
| API | `franchise_routes.py` — `complete_week_phase_a`, `complete_week_phase_b`, `complete_week`, `_complete_week_finish_cpu_and_persist`, **`_finalize_franchise_week_after_cpu_games`**, **`_try_finalize_franchise_week_if_complete`**, matchup-key helpers, `_complete_week_process_user_game_block` |
| EOS | `BackEnd/tournament/franchise_tournament.py` |
