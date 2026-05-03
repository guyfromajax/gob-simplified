# Parallel franchise CPU sims and week finalization — work plan

**Location:** `_documentation_master/projects/` (canonical project plan)  
**Status:** Implemented (v1 — in-process phase B, week gated by **`_try_finalize_franchise_week_if_complete`**). **Next product milestone (v2):** CPU week sims start at **first franchise Play Quarter** — see **§9**.  
**Goal:** Run CPU game sims in parallel (server-side) while the user plays their franchise game; separate **per-game persistence** from **week-level closure** (rankings, stat leaders, week advance, etc.) behind a single idempotent `try_finalize_week`-style gate.  
**Explicitly out of scope for this milestone:** Quarter checkpoints / resume abandoned user games (may follow as phase 2 once this spine exists). **v1 deferred items** (partial): separate worker/queue, client polling — folded into **§9** as decisions for v2.

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

### E. Product / planning (v1 decisions — May 2026)

- [x] **PGPC at franchise EOG:** Kept behind **`FRANCHISE_PGPC_AT_EOG_ENABLED`** in `gameCompletionPopup.js` (default **`false`**). Set to **`true`** to restore Post-Game Press Conference on the EOG modal; code paths remain in repo.
- [x] **When CPU / phase B runs (v1):** After the user’s game is finalized for the week — **`POST /franchise/complete-week/phase-a`** persists the user row; the client starts **`POST /franchise/complete-week/phase-b`** when the franchise completion UI is shown (single-flight per `franchise_id:week`). CPU sims are **not** started at tip-off or week open in v1.
- [ ] **Future product (optional):** Start background CPU jobs earlier than EOG; requires async job design + client polling or push (see §4 Phase 3–4 deferred items).

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
- [x] Product decisions for v1: PGPC flag (§2.E); phase B start after phase A + EOG client (not tip-off).

### Phase 1 — Extract week closure (no behavior change)

- [x] Introduce a dedicated week-closure function containing post–CPU-loop logic — implemented as **`_finalize_franchise_week_after_cpu_games`** in `franchise_routes.py`, called only from **`_complete_week_finish_cpu_and_persist`** (same call site as before; behavior preserved).
- [x] Tests: **`tests/test_franchise_complete_week.py`** — `_try_finalize_franchise_week_if_complete` logging (`waiting` / `ran_closure`); **`POST .../phase-b`** **`idempotent: true`** when `franchise.week` already advanced; **phase A → phase B → second phase B** idempotent chain; monolithic **`/franchise/complete-week`** + canonical team id tests assert **`franchise.results[week]`** (not universal `teams.record`); CPU full-sim path stubbed via **`_run_franchise_cpu_full_simulation_core`** where a second matchup would otherwise require rosters.

### Phase 2 — Per-game idempotent CPU persistence

- [x] Stable matchup id: **`_week_result_matchup_key`** (documented) plus **`_expected_franchise_week_matchup_key_set`**, **`_week_results_list_contains_matchup`**, **`_franchise_week_results_cover_schedule`** in `BackEnd/api/franchise_routes.py`.
- [x] Dedupe at CPU loop start (**`_dedupe_franchise_week_results_by_matchup`**); skip CPU iterations when that matchup already appears in `results`; gate closure with **`_try_finalize_franchise_week_if_complete`** → **`_finalize_franchise_week_after_cpu_games`** only when the schedule is fully covered (else **HTTP 500**, no week advance).
- [ ] Optional: external job pool invoking **`_try_finalize_franchise_week_if_complete`** after each per-game persist (not needed for current in-process `ThreadPoolExecutor` phase B).

### Phase 3 — Parallel execution

- [x] **In-process parallel (phase B unchanged from client):** full `run_simulation` CPU games are batched with **`ThreadPoolExecutor`** (`as_completed`); DB / EOS / GP persist **sequentially** in schedule index order. Env **`FRANCHISE_CPU_SIM_MAX_WORKERS`** (default **4**, minimum 1). Helpers: **`_run_franchise_cpu_full_simulation_core`**, **`_franchise_cpu_full_sim_max_workers`**, **`_order_franchise_week_results_like_schedule`** in `franchise_routes.py`. Log line **`[COMPLETE-WEEK-PHASE3]`**.
- [ ] Optional later: separate worker process / queue, start jobs earlier than EOG, or client polling (not required while phase B stays one HTTP request).

### Phase 4 — UX + cleanup

- [x] Franchise EOG: **`FRANCHISE_PGPC_AT_EOG_ENABLED`** (`gameCompletionPopup.js`, default **`false`**) — PGPC code kept; Box Score + **Go To Locker Room** shows **`PageLoadOverlay`** (“Simulating Computer Games”), awaits phase B, then clears pending + navigates to FCC (same pulse as box-score path).
- [x] Optional pre-navigation overlay: satisfied by **Go To Locker Room** + box-score **`PageLoadOverlay`** until phase B completes (no separate idle overlay on the EOG modal itself).
- [x] Update **`End_Of_Game_System.md`** and **`Press_Conference_System.md`** for the above + phase B parallel sim note.

---

## 5. Observability (add early)

- [x] **`_try_finalize_franchise_week_if_complete`** logs **`[TRY-FINALIZE-WEEK]`** with **`outcome=waiting`** (`expected_matchups`, `deduped_rows`, `missing_matchups`, `extra_matchups`) when the week slate is incomplete; **`outcome=ran_closure`** when week closure runs.
- [x] **`complete_week_phase_b`** logs **`[COMPLETE-WEEK-PHASE-B] outcome=already_finalized`** when `franchise.week` is already past `req.week` (idempotent retry after week advance).
- [ ] Optional: metric for time from phase A success to week closure.

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

**v1 is closed** (see §4, §5, **`tests/test_franchise_complete_week.py`**). **Active work:** **§9 Milestone 2** — Play Quarter triggers CPU sims for the week, then existing week-closure + week advance when **user + all CPUs** are complete.

---

## 8. File index (quick reference)

| Area | Files |
|------|--------|
| EOG + phase A | `finalizeGame.js`, `End_Of_Game_System.md` |
| Phase B trigger (v1) | `gameCompletionPopup.js`, `franchisePhaseBClient.js`, `postGamePressConference.js` |
| v2 CPU start hook | `bootGame.js` + **`franchiseStartCpuSimsClient.js`** → **`POST /franchise/complete-week/start-cpu-sims`** |
| start-cpu-sims API | `franchise_routes.py` — `complete_week_start_cpu_sims`, **`persist_cpu_results_only`** |
| Box score pending | `box-score.js`, `pageLoadOverlay.js` |
| API | `franchise_routes.py` — `complete_week_phase_a`, `complete_week_phase_b`, `complete_week`, `_complete_week_finish_cpu_and_persist`, **`_finalize_franchise_week_after_cpu_games`**, **`_try_finalize_franchise_week_if_complete`** (`[TRY-FINALIZE-WEEK]` logs), matchup-key helpers, `_complete_week_process_user_game_block` |
| Tests | `tests/test_franchise_complete_week.py` — try-finalize + phase-B idempotent |
| EOS | `BackEnd/tournament/franchise_tournament.py` |

---

## 9. Milestone 2 — “Play Quarter starts CPU week sims” (v2)

**Product intent (four steps):**

1. User presses **Play Quarter** to begin **Q1** of their franchise game → that action **also starts** simming **all other scheduled games for that week** in parallel (**distant** + **full turn-by-turn** CPU paths, same rules as today’s CPU loop).
2. User’s game finishes; **all** computer games for that week are already finished (or finish alongside).
3. Run **week-level** logic that **requires the full week slate** (recruiting lean / natl-rank–related passes, regular-season rank & prestige, aggregates over every result, EOS advance/init when applicable, inbox/training/community-highlight steps, week-35 capstone, etc.) — i.e. what **`_finalize_franchise_week_after_cpu_games`** does today, **only after** **`_try_finalize_franchise_week_if_complete`** sees a **complete** set of matchups (user row + every CPU row).
4. **Advance** franchise **`week`** (and EOS week jumps) as part of that same gated closure.

**Today (v1) vs target (v2):** v1 starts the CPU batch **after** the user’s result is saved (**phase A**) and runs heavy work in **phase B** from the **EOG** client. v2 moves the **CPU batch start** to **first Play Quarter** for that week’s user game; **phase A** stays “persist user game”; a **finalize** step after phase A should **merge** user row + any CPU rows already written, run **only missing** CPU sims if any, then **`_try_finalize`** → closure + week advance.

### 9.1 New / changed API (conceptual)

| Piece | Role |
|-------|------|
| **`POST /franchise/complete-week/start-cpu-sims`** | Body: `franchise_id`, `week` (`CompleteWeekStartCpuSimsRequest`). **409** if phase A already ran for that week. Runs **non-user** matchups via **`_complete_week_finish_cpu_and_persist(..., persist_cpu_results_only=True)`** — persists **`results.{week}`** (+ EOS tournament blobs on EOS weeks). **Does not** advance `franchise.week`; no week-closure until phase B when user row exists. |
| **`complete_week_phase_a`** | Unchanged in principle: user game → user row + `post_game_status.phase_a_user_week`. |
| **`complete_week_phase_b`** (or slim follow-up) | After reload: ensure **all** CPUs present (no-op for already-simmed matchups), merge user row, call **`_try_finalize_franchise_week_if_complete`** → **`_finalize_franchise_week_after_cpu_games`** when complete. |

### 9.2 Client hook

- **Franchise mode**, **first transition into live Q1** (pre-game → Q1): fire **`start-cpu-sims`** once per `franchise_id:week` (**single-flight**, same spirit as `franchisePhaseBClient.js`). Prefer **non-blocking** relative to simulate-quarter if feasible (fire-and-forget or short timeout + retry-safe idempotency on server).

**Likely file:** `FrontEnd/static/js/phaser/bootGame.js` (Play Quarter / `handleButtonClick` / `handleSimQuarter` when `quarter === 0` and `mode === 'franchise'` — exact hook TBD in implementation).

### 9.3 Open decisions (record before build)

| Decision | Options |
|----------|---------|
| **Where CPU work runs** | **A)** In-process threads on API server (reuse `ThreadPoolExecutor` pattern; simpler, may contend with **Play Quarter** CPU). **B)** Queue + worker (better isolation; more infra). |
| **Request shape** | One long **`start-cpu-sims`** HTTP vs chunked / job id + poll (only needed if timeouts bite). |
| **EOS weeks** | Short design pass: confirm early CPU sims cannot violate bracket ordering vs user game (regular season is lower risk). |

### 9.4 Implementation checklist (suggested order)

- [x] **Spike + parameterize:** **`persist_cpu_results_only`** on **`_complete_week_finish_cpu_and_persist`** — partial `$set` of **`results.{week}`** (+ EOS blobs); no **`_try_finalize`** / no week advance.
- [x] **`POST /franchise/complete-week/start-cpu-sims`** — guards: `franchise.week == req.week`, rejects if phase A done (**409**), logs **`[START-CPU-SIMS]`**. Tests in **`tests/test_franchise_complete_week.py`**.
- [ ] **Auth / ownership** — same pattern as **`complete_week_phase_a`** today (no `Depends` on these routes); tighten if product requires it.
- [ ] **Adjust phase B** (or post–phase-A finalize entry) for “CPUs may already exist.”
- [x] **Client:** `bootGame.js` — **`maybeFireFranchiseStartCpuSimsAtQ1Entry()`** on franchise **quarter === 0** for **Play Quarter**, **Sim Quarter**, and **Sim Full Game**; **`franchiseStartCpuSimsClient.js`** single-flight + non-fatal `.catch` (must not brick Q1).
- [ ] **Tests:** idempotent `start-cpu-sims`; phase A + B with CPUs pre-filled; week does not advance until user row present.
- [ ] **Docs:** `End_Of_Game_System.md` + this §9 when behavior ships.

### 9.5 Backend anchor (existing)

Reuse **`_try_finalize_franchise_week_if_complete`** and **`_finalize_franchise_week_after_cpu_games`** in `BackEnd/api/franchise_routes.py` — v2 is mostly **when** CPUs start and **splitting** the HTTP surface, not replacing week-closure semantics.
