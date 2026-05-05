# Tournament Execution System

**Purpose:** Single handoff reference for (1) **franchise multi-phase EOS** (weeks **27–35**), (2) the **shared 8-team bracket engine** used by conference + national + **Tournament mode**, and (3) **bracket UI** (FCC / TCC). Pair with `EOS_Write_Path_Inventory.md` for “who writes what” during EOS.

**Primary code — franchise EOS:**  
`BackEnd/tournament/franchise_tournament.py`,  
`BackEnd/tournament/franchise_tournament_progression.py`,  
`BackEnd/api/franchise_routes.py`.

**Primary code — shared engine + Tournament mode:**  
`BackEnd/tournament/bracket_engine.py`,  
`BackEnd/tournament/tournament_manager.py`,  
`BackEnd/tournament/bracket_logic.py`,  
`eos_tournament.py` (legacy / standalone EOS helpers where still referenced).

**Companion:** `EOS_Write_Path_Inventory.md` — EOS write-path matrix; new paths should use **`record_tournament_game_result`** + **`_eos_calendar_advance_update_fields`** (except championship-only tails like `sim-championship`).

**Team identifiers:** Bracket cells use **ObjectId strings** (hex). Resolve names at API / UI boundaries.

---

## 1. Franchise EOS calendar (`week`)

| Franchise `week` | Phase | Bracket data on franchise doc |
|------------------|--------|--------------------------------|
| 1–26 | Regular season | (no EOS blobs) |
| **27–29** | Conference EOS | `conference_tournaments` (16 keys `"1"`…`"16"`), each with `bracket`, `current_round`, `seeds`, `champion` |
| **30–31** | Region EOS | `region_tournaments` (keys **`A`–`H`**; conferences 1–2 → `A`, … 15–16 → `H`) |
| **32–34** | National EOS | `national_tournament` (`bracket`, `current_round`, `champion`) |
| **35+** | Post-EOS / offseason | `eos_tournament_active` **false** after national champion |

**Flag:** `eos_tournament_active` — set **true** when conference brackets initialize (end of week **26** closure); set **false** when national champion is decided.

Constants: `EOS_CONFERENCE_WEEKS`, `EOS_REGION_WEEKS`, `EOS_NATIONAL_WEEKS`, `EOS_WEEKS` in `franchise_tournament.py`.

---

## 2. Franchise document fields (progression)

- **`week`** — Advanced only through finalize / sim-rest / sim-championship paths during EOS, not ad hoc.
- **`results[str(w)]`** — Result rows for that calendar week (EOS included).
- **`conference_tournaments`** — Per-conference **8-team** bracket (uses **`bracket_engine`**): `bracket` (`round1` / `round2` / `final`), `current_round`, `seeds`, `champion`.
- **`region_tournaments`** — Custom 4-team region shape per letter; `R1_0` / `R1_1` placeholders in `final` until R1 resolves.
- **`national_tournament`** — **8-team** bracket for region winners (`bracket_engine`).
- **`eos_tournament_active`**, **`games`** — As in inventory; bracket + `results` + `games` should stay aligned (repair/heal when not).

---

## 3. Single game write funnel + idempotency (franchise EOS)

**Entry:** `franchise_tournament_progression.record_tournament_game_result(...)`  
Does **not** set franchise `week` by itself; records one matchup and may advance conference/national helpers in memory.

**Idempotency (summary):** same winner+scores replay → no-op (may fill `game_id`); `cpu_full` / `distant` won’t clobber a settled cell with a different outcome; user / existing_* can repair. CPU full-sim enqueue deduped per slot. Details: `get_eos_bracket_slot_snapshot`, `tests/test_franchise_tournament_progression.py`.

### 3a. User game bracket write invariant

`_complete_week_process_user_game_block` (in `franchise_routes.py`) **must** end up with a valid `eos_g_meta` whenever `req.week ∈ EOS_WEEKS` and the franchise has an active EOS slate. If it does not, the endpoint raises **HTTP 409** instead of falling through to `_save_game_result` (which would persist the score / `franchise.results` row but leave the bracket cell empty — the silent state that produced the historical "calendar advanced, bracket cell missing winner+game_id" symptom).

Resolution order in `_resolve_user_eos_game_meta_or_raise`:

1. **`req.game_document.eos_meta`** — single source of truth, locked at game start by `play-next-game` (forward-compat path; immune to slate / week drift).
2. **`find_user_eos_game_meta`** — the calendar slate (`include_completed=True`) plus the playable fallback (per-tournament `current_round`, `include_completed=False`).
3. **`find_eos_game_meta_for_team_pair`** — same slate, matched by team-id pair instead of user id (handles `user_team_id_str` mismatches against bracket ids).

If all three miss, the helper logs `[EOS-BRACKET-DEBUG] eos_meta_unresolved_in_eos_week` with `req_week`, `franchise.week`, `game_doc.week`, `user_team_id`, `team1`, `team2`, and `slate_n`, then raises 409. This is intentional — losing the bracket write silently is worse than failing the request.

**`eos_meta` on the game document.** Whenever a user game's bracket slot resolves successfully, `_stamp_eos_meta_on_game_doc` writes a snapshot (`phase`, `round`, `matchup_index`, `away_id`, `home_id`, plus `conference` / `region`) onto `db.games.{_id}.eos_meta`. Future retries, phase-b syncs, and repair tooling can read the bracket slot directly off the game document — no slate matching, no week-drift sensitivity. `play-next-game`'s response also surfaces `eos_meta` for FE plumbing into `req.game_document` (see step 1 above).

### 3b. start-cpu-sims persist must merge fresh DB state

`_complete_week_finish_cpu_and_persist` is called from three entry points: monolithic `complete-week`, `complete-week/phase-b`, and `complete-week/start-cpu-sims` (the last one with `persist_cpu_results_only=True`). The first two finalize the week via `_eos_calendar_advance_update_fields`; the third only persists `results.{week}` plus the EOS bracket blobs.

**Invariant for the `persist_cpu_results_only=True` branch:** before writing `conference_tournaments` / `region_tournaments` / `national_tournament` to the DB, re-read those blobs from the DB and pass them through `merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise(fresh_eos, franchise_doc)`. Persist the merge result, not the raw `franchise_doc` blob.

**Why.** start-cpu-sims skips the user matchup by design (the `if {away,home} == {user_team1,user_team2}: continue` branch in the sim loop). If a phase-a user-bracket write lands in the DB *after* start-cpu-sims loaded `franchise_doc` but *before* it persists, the local `franchise_doc.conference_tournaments` blob — which never had the user's winner because this path skips the user — would clobber the user's slot back to `null` on the blanket overwrite. That race is the historical silent root cause of the "calendar advanced, user bracket cell stays null" symptom (§3a). The merge keeps fresh's winners and copies stale's winners only into slots fresh hadn't seen, so a concurrent user write survives intact while CPU writes that this request just produced are still added.

Phase-a's persist already uses this same merge helper for the same reason. start-cpu-sims now matches that pattern.

---

## 4. Calendar week advance (franchise EOS)

**Function:** `_eos_calendar_advance_update_fields` in `franchise_routes.py`.  
**Called from:** `_finalize_franchise_week_after_cpu_games`, **`POST /franchise/sim-rest-of-tournament`**.

Returns **`$set` fragments** (`week`, bracket blobs, `eos_tournament_active`); mutates `franchise_doc` in memory. Does not set `results` / training (caller merges).

**By `completed_week` (read `franchise_routes._eos_calendar_advance_update_fields` for truth):**

- **27, 28:** advance all 16 conference brackets; `week` → next conference week; persist `conference_tournaments`.
- **29:** same advances, then **`initialize_region_tournaments`**, set **`region_tournaments`**, `week` → **30**.
- **30:** `week` → **31**; persist `region_tournaments` from mutated doc.
- **31:** **`initialize_national_tournament`**, set **`national_tournament`**, `week` → **32**.
- **32, 33:** `advance_national_bracket`; bump `week` toward **34**.
- **34:** advance national; on **final** completion set **`eos_tournament_active`: false**, **`week`: 35**.

**Week 26 → 27:** `_finalize_franchise_week_after_cpu_games` initializes `conference_tournaments`, sets `eos_tournament_active`, `week` → **27** (not inside `_eos_calendar_advance_update_fields`).

**Training:** `_training_status_reset_after_advance_to_week` merged into finalize/sim-rest `$set` when leaving EOS weeks.

---

## 5. Region brackets: build, bye, reconcile

**Build:** `initialize_region_tournaments` → `_build_region_bracket` from conference **champion** + **RS #1** (#1 seed in `seeds`, or inferred from `bracket.round1[0].home_team` if `seeds` missing).

**Bye:** champion == RS #1 for a conference → that side can skip to **region final** (possibly **no R1** rows, **final** with two real teams).

**Reconcile:** `reconcile_region_tournaments_with_canonical` — replace or patch incomplete unplayed slots from canonical. Runs on **FCC load**, **sim-rest**, **`POST /franchise/play-next-game`** (region weeks), and **`_resolve_complete_week_week_games`** (region weeks). The play / complete-week entry-point reconciles were added so a user who clicks Play without first hitting `/franchise/command-center/data` cannot land on a half-built region bracket whose placeholder `R1_0`/`R1_1` slots would drop their pair out of `get_eos_week_games` and trip the bracket-write invariant. Helper: `_maybe_reconcile_region_for_eos(franchise_doc, franchise_id, week=, context_label=)` (idempotent: persists only when something actually changed; logs `[EOS-REGION-RECONCILE] context=<label>`).

---

## 6. `get_eos_week_games`

`franchise_tournament.get_eos_week_games(franchise_doc, week, include_completed=False)`.

- **Conference:** playable mode uses each conference’s **`current_round`** (not global week) so slow brackets still list R1 after calendar advances.
- **Region week 30:** real R1 matchups; if **no** playable R1 but **`final[0]`** has two real teams, emit that final as **round 2** (double-bye path).
- **Region week 31:** finals. **National:** same calendar vs `current_round` pattern as conference.

---

## 7. HTTP / UX (franchise EOS)

| Surface | Role |
|---------|------|
| **`GET /franchise/command-center/data`** | Reconcile regions when needed; `offer_sim_rest`, `user_eliminated`, derived `eos_tournament` for **user’s region** display. |
| **`offer_sim_rest`** | Requires non-empty **`get_eos_week_games(..., include_completed=False)`** for that `week` among other flags. |
| **`POST /franchise/play-next-game`** | Reconcile region (region weeks) → `get_eos_week_games(..., include_completed=False)` → resolve user matchup. Returns `{home, away, week, home_id, away_id, eos_meta}`. `eos_meta` carries `{phase, round, matchup_index, away_id, home_id, conference|region}` so FE can plumb it through to `complete-week`. |
| **`POST /franchise/sim-rest-of-tournament`** | Reconcile → meta list → sim → `_eos_calendar_advance_update_fields`. |
| **`POST /franchise/complete-week`** & **`/complete-week/phase-a`** | Harden `req.week` (future-week guard + symmetric `game_document.week` trust) → reconcile region (region weeks) → resolve user EOS slot via `_resolve_user_eos_game_meta_or_raise` (raises 409 if EOS week and slot is unresolvable) → record bracket + `_eos_calendar_advance_update_fields` when finalizing. |
| **`POST /franchise/complete-week/phase-b`** | `_eos_heal_all_eos_from_games` (conference + region + national) → resolve / sync → finalize → `_eos_calendar_advance_update_fields`. |
| **`POST /franchise/sim-championship`** | National final only; do not double-advance national (see inventory). |

---

## 8. Operational logging

- **`[EOS-REGION-RECONCILE]`** — `context=fcc` \| `sim_rest` \| `play_next_game` \| `complete_week`, `week`, `franchise_id`, `persisted`, `ftd_team_count`.
- **`[EOS-SIM-REST] empty_meta`** — right before sim-rest **400**.
- **`[COMPLETE-WEEK-WEEK-HARDEN]`** — `req.week=<n> > franchise.week=<m>` (future-week coalesce); `eos_trust_game_document week req=<rw> doc=<gw> franchise.week=<fr_w> direction=<doc_behind|doc_ahead>` (symmetric); `no_slate_match_either_week` (downstream raise expected).
- **`[EOS-BRACKET-DEBUG] eos_meta_from_game_document`** — bracket slot taken from `req.game_document.eos_meta` (slate matching skipped).
- **`[EOS-BRACKET-DEBUG] eos_meta_resolved_by_pair`** — slate primary missed, team-pair fallback hit.
- **`[EOS-BRACKET-DEBUG] eos_meta_unresolved_in_eos_week`** — emitted at `logger.error` immediately before the 409 raise; includes `req_week`, `franchise_week`, `game_doc_week`, `user_team_id`, `team1`, `team2`, `slate_n`. This is the first log to grep when a phase-a / complete-week request fails 409.
- **`[EOS-HEAL] phase=<conference|region|national>`** — emitted by each per-phase heal at the start of phase-b when work was done; carries `results_rows_added`, `bracket_slots_synced`, `advance_steps`.
- **`[START-CPU-SIMS] persisted partial week results`** — start-cpu-sims persist completed; followed by an internal merge that preserves any concurrent phase-a write to the user's bracket cell (§3b).

---

## 8a. EOS self-heal at phase-b (conference + region + national)

`complete_week_phase_b` runs `_eos_heal_all_eos_from_games` *before* it touches `franchise_doc`, so the user-game / CPU-game cells that landed in `db.games` and `franchise.results` but never made it to the bracket get backfilled before phase-b advances anything. Three per-phase variants share the same generic `_eos_heal_phase_from_games` helper and sync the same way:

| Phase | Helper | Bracket field | Advance step |
|-------|--------|---------------|--------------|
| Conference (27, 28, 29) | `_eos_heal_conference_eos_from_games` | `conference_tournaments` | `_eos_advance_all_conference_brackets_until_idle` |
| Region (30, 31) | `_eos_heal_region_eos_from_games` | `region_tournaments` | none — `save_region_game_result` fills `final` from R1 winners in-line |
| National (32, 33, 34) | `_eos_heal_national_eos_from_games` | `national_tournament` | `_eos_advance_national_bracket_until_idle` |

For each EOS week ≤ `franchise.week`:

1. `_eos_sync_missing_result_rows_from_games_for_week` — append a `franchise.results.{week}` row for any matchup with a `db.games` doc but no results row (fixes W/L display when the user game hit `games` + bracket but never landed in `franchise.results`).
2. `_eos_sync_bracket_slots_from_games_for_week` — for any unwon bracket cell whose meta row matches a `db.games` doc, write `winner` / `score` / `game_id` from that doc via `_sync_eos_bracket_from_existing_game_doc` → `record_tournament_game_result(source="existing_games")`.
3. Run the phase-specific advance until idle (conference / national); for region the bracket fills `final` slots automatically when the R1 cells are written.
4. Persist `results` and the relevant bracket field only when something changed. Idempotent.

The aggregate `_eos_heal_all_eos_from_games` runs all three in dependency order (conference → region → national) and returns `{did_work, conference, region, national}`. Phase-b uses `did_work` to decide whether to reload `franchise_doc` from Mongo before continuing.

**Why all three.** A user game whose bracket write was missed during phase-a (e.g. 409 followed by a manual override, or a legacy run before the invariant landed) used to self-heal only for conference. Region (30–31) and national (32–34) misses stayed broken until manual repair. The heal-coverage extension closes that gap.

---

## 9. Shared 8-team bracket engine (`bracket_engine.py`)

Used by: **Tournament mode**, franchise **conference** (×16), franchise **national** (×1). **Not** used for the custom **region** 4-team layout (`region_tournaments`).

| Function | Purpose |
|----------|---------|
| `get_round_name(round_num)` | 1 → `round1`, 2 → `round2`, 3 → `final`. |
| `generate_bracket(seed_order)` | 8 ObjectId strings, seeds 1–8. Matchups: **1v8, 4v5, 2v7, 3v6**. Returns `{round1, round2, final}`; `round2` / `final` start empty. |
| `save_game_result(...)` | Sets `game_id`, `winner`, `score` on one matchup; mutates bracket in place. |
| `advance_bracket(...)` | Completes current round from winners, fills next round; returns `(bracket, next_round, completed, champion)`. |

**Matchup shape:** `{home_team, away_team, game_id, winner, score}` — team fields as ObjectId strings.

**Rounds:** R1 (4 games) → R2 (2) → final (1) → champion.

---

## 10. Tournament mode (standalone)

| Topic | Detail |
|-------|--------|
| **Storage** | `tournaments` collection: `bracket`, `current_round`, seeds, etc. |
| **Seeding** | Random shuffle of 8 teams → `generate_bracket(seed_order)`. |
| **Flow** | Init bracket → `save_game_result` per finished game → `advance_bracket` when round complete → persist via routes / `TournamentManager`. |
| **Code** | `tournament_manager.py`, `bracket_logic.update_bracket_from_results`, tournament routes. |

---

## 11. Bracket UI (FCC + TCC)

- **Shared renderer:** `FrontEnd/static/bracket.js` — `renderBracketShared(container, bracketData, teamIdToNameMap, options)`. Same layout as `tournament.css` `.bracket` grid.
- **FCC Tournament tab:** id→name from `/franchise/team-stats`; container `#tournament-bracket-container`; seeds from `eos_tournament` / bracket payload.
- **TCC Bracket tab:** id→name from `/tournament/team-stats`; same `renderBracketShared` with TCC options.
- **IDs in API**, names on client; schedule / scouting resolve ObjectIds via the same maps.

---

## 12. Tests (non-exhaustive)

| Area | Files |
|------|--------|
| Bracket engine | `tests/test_bracket_engine.py` |
| EOS + engine integration | `tests/test_eos_bracket_engine_integration.py` |
| Franchise EOS recording | `tests/test_franchise_tournament_progression.py` |
| Region week 30 meta | `tests/test_eos_region_week30_meta.py` |
| Region reconcile | `tests/test_region_tournament_reconcile.py` |
| FCC / sim policy | `tests/test_franchise_eos_sim_policy.py` |
| User-game bracket-write invariant + symmetric harden + region/national heal + `eos_meta` on game doc | `tests/test_franchise_eos_bracket_invariant.py` |
| Tournament mode | `tests/test_tournament_*` |

---

## 13. Related / archive

- `docs/To Do/Archive/tournament_eos_bracket_merge_plan.md` — historical merge plan.
- `EOS_Write_Path_Inventory.md` — EOS writers.

---

## 14. Historical note

Franchise EOS was once documented as a **single** embedded `eos_tournament` over weeks **15–17**; production is **multi-phase 27–34** on `conference_tournaments` / `region_tournaments` / `national_tournament`. This file is the **canonical** tournament doc under the name **`Tournament_Execution_System.md`** (content was consolidated from a short-lived **`Current_Tournament_System.md`** and obsolete material from an older doc generation was removed).

Earlier iterations of `_complete_week_process_user_game_block` silently fell through to `_save_game_result` when the EOS slate did not contain the user pair, producing a calendar-advanced-but-bracket-empty state. That fall-through is now a hard 409 (§3a). A symmetric form of `_harden_complete_week_request_week` (§7 / §8) and three-phase `_eos_heal_all_eos_from_games` (§8a) close the same class of failure across all EOS phases. A snapshot `eos_meta` on the game document (§3a) is the forward-compat single source of truth for the bracket slot — `play-next-game` already returns it; the FE plumbing into `req.game_document.eos_meta` is the next step.

A separate strain of the same symptom turned out to be a race between concurrent endpoints: `start-cpu-sims` running with stale in-memory `conference_tournaments` could persist after a phase-a user-bracket write had landed in the DB, blanket-overwriting the user's slot back to `null`. The fix is to merge fresh DB blobs before persisting in that path — see §3b.
