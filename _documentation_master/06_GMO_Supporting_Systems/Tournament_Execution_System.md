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

**Reconcile:** `reconcile_region_tournaments_with_canonical` — replace or patch incomplete unplayed slots from canonical; runs on **FCC load** and **sim-rest** in region weeks. Prevents empty `get_eos_week_games` when Mongo had half-filled “TBD” rows.

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
| **`POST /franchise/sim-rest-of-tournament`** | Reconcile → meta list → sim → `_eos_calendar_advance_update_fields`. |
| **`POST /franchise/complete-week`** | Finalize → `_eos_calendar_advance_update_fields` when in EOS. |
| **`POST /franchise/sim-championship`** | National final only; do not double-advance national (see inventory). |

---

## 8. Operational logging

- **`[EOS-REGION-RECONCILE]`** — `context=fcc` \| `sim_rest`, `week`, `franchise_id`, `persisted`, `ftd_team_count`.
- **`[EOS-SIM-REST] empty_meta`** — right before sim-rest **400**.

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
| Tournament mode | `tests/test_tournament_*` |

---

## 13. Related / archive

- `docs/To Do/Archive/tournament_eos_bracket_merge_plan.md` — historical merge plan.
- `EOS_Write_Path_Inventory.md` — EOS writers.

---

## 14. Historical note

Franchise EOS was once documented as a **single** embedded `eos_tournament` over weeks **15–17**; production is **multi-phase 27–34** on `conference_tournaments` / `region_tournaments` / `national_tournament`. This file is the **canonical** tournament doc under the name **`Tournament_Execution_System.md`** (content was consolidated from a short-lived **`Current_Tournament_System.md`** and obsolete material from an older doc generation was removed).
