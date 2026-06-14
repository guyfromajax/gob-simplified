# Post-Game Press Conference (PGPC) — Implementation Work Plan

This document is the execution plan for wiring **real questions**, **qualification**, **selection**, and **session/UI** for the post-game press conference. It assumes alignment with `PGPC_Trigger_Condition_Assessment.md` and the question bank in `BackEnd/utils/press_conference_questions.py`.

**Scope note:** “PCPG” in the filename matches repo naming; elsewhere we use **PGPC** (post-game press conference).

**Phase 0 detail:** Typed snapshot contract and per-trigger source table live in **`PGPC_Snapshot_Schema.md`** (same folder).

---

## Goals

1. Persist on the **finalized game document** every measure that **cannot** be derived from the box score alone (plus any Tier C / narrative triggers the product requires).
2. On **game complete**, compute **all qualifying questions** for that game (game snapshot + franchise context where needed).
3. **Select** `random.randint(10, 15)` questions per session; **cap vanilla at 3** unless the qualified pool is too small, then pad with vanilla to reach the chosen count.
4. **Wire** the PGPC modal/API to the **selected** questions (text + shuffled answers; `{player_name}` resolution when `player_slot` is set).
5. **Defer:** apply **effect tags** from answers to franchise/coach/player state (`effect_tag_resolver` path) — final step when design is ready.

---

## Implementation order (strict dependency chain)

| Phase | What | Why first / next |
|-------|------|------------------|
| **0** | Snapshot contract + frozen PGPC payload | Single source of truth for qualification; avoids rework when engine fields land piecemeal. |
| **1** | Engine / `summarize_game_state` writes non-box measures | Qualification cannot be correct without persisted data (e.g. opening five, any Tier C flags). |
| **2** | `get_qualifying_questions(...)` | Pure evaluation + unit tests; can use fixtures before engine is 100% complete once the contract exists. |
| **3** | `select_pgpc_questions(...)` | Depends only on qualified list + RNG + vanilla cap / padding rules. |
| **4** | API + frontend: build session from (2)+(3) | Game complete flow must call backend; UI renders returned payload. |
| **5** | Answer impact resolver | Last; depends on stable `effect_tags` and franchise write rules. |

---

## Phase 0 — Snapshot contract and frozen session input

**Deliverables** (see **`PGPC_Snapshot_Schema.md`** for the full TypedDict + 43-condition map)

- Short **schema** (Python `TypedDict` or docstring constants) listing every field the **qualifier** reads from:
  - **Game doc:** scores, margins, OT, `points_by_quarter`, per-player box rows, `players[]` (incl. `attributes.EM`), team totals, **`opening_lineup` / `opening_lineup_player_ids`** (or equivalent), any future Tier C blobs.
  - **Context passed at session build:** `user_team_id`, `opponent_id`, `week`, paths to **streaks**, **standings**, **FTD ranks**, **series vs opponent**, etc. (per assessment Section B).
- Rule: **freeze** a copy of the inputs used to build the question list on the `press_conference_sessions` document (or hash + embedded snapshot) so late writes to the game record do not change an in-progress session.

**References:** `PGPC_Trigger_Condition_Assessment.md` Sections A–D; `BackEnd/utils/shared.py` (`summarize_game_state`).

**Acceptance:** Reviewer can trace each `trigger.condition` in the question bank to either a snapshot field or an explicit “franchise query at build time” row.

**Started:** Types in `BackEnd/models/pgpc_snapshot.py`; context stub in `BackEnd/pgpc_context.py` (also imported from `BackEnd.utils.shared`); tests in `tests/test_pgpc_context.py`. **Opening lineup:** `BackEnd/opening_lineup_snapshot.py` + DB/summarize restore (see `_documentation_master/03_Data_Persistence/Data_Persistence_System.md`, "Special Gameplay-Tracking Fields").

---

## Phase 1 — Engine / summary persistence (non-box-score)

**Deliverables**

- Implement persistence for **opening-lineup snapshot** (and any other Section B/C gaps not already on the game doc) at the **correct lifecycle hook** (game start or first possession vs finalize — per product; assessment recommends summarize/game-state alongside finalize).
- Incrementally add **Tier C** or tracking fields only where the assessment marks them as required (avoid speculative columns).
- Migration / default: define behavior for **legacy games** missing new fields (skip triggers that need them, or safe defaults — document the choice).

**Acceptance:** A finalized franchise user game in DB contains the fields Phase 0 promised; spot-check with one simmed game.

---

## Phase 2 — Qualification service

**Deliverables**

- Module e.g. `BackEnd/utils/pgpc_qualification.py` (name as you prefer) exposing:
  - `qualify_questions(game_doc: dict, franchise_context: dict) -> list[dict]`  
    or `-> list[str]` of question ids, loading from `PRESS_CONFERENCE_QUESTIONS`.
- Map every **`trigger.condition`** and **`filters`** to evaluation logic; respect **`requires_tracking`** / tier gating if the snapshot lacks Tier 2 data.
- **`condition: 'always'`** (vanilla) included in the qualified pool for selection phase.
- **Unit tests:** fixture games for win/loss, blowout, close, OT, come-from-behind (using `points_by_quarter`), and at least one franchise-dependent stub (mock context).

**Acceptance:** Tests green; no qualification logic duplicated in the frontend.

---

## Phase 3 — Selection algorithm

**Deliverables**

- `select_pgpc_questions(qualified: list, *, rng: random.Random) -> list` implementing:
  - `n = random.randint(10, 15)` (use a single RNG instance per session for reproducibility if you store seed).
  - **Weighted** choice among non-vanilla where `weight` is set; document tie-breaking.
  - **Vanilla cap:** at most **3** vanilla unless `len(non_vanilla_qualified) < n` after exhausting non-vanilla, then fill with vanilla to reach `n`.
  - If `len(qualified) < n` even after vanilla: define explicit behavior (repeat vanilla with replacement, or lower `n` — **pick one** and document).

**Optional later:** max questions per `subcategory` to reduce repetition.

**Acceptance:** Deterministic tests with fixed `rng.seed()` for counts and vanilla cap.

---

## Phase 4 — API and UI wiring

**Deliverables**

- **Endpoint** (or extension of existing flow): on game complete / “start PGPC”, accept `franchise_id`, `game_id`, `week`, `user_id`, load game + franchise slice, run Phase 2 + 3, **create** `press_conference_sessions` doc with:
  - ordered list of questions (ids + display text + answers),
  - **shuffled** answer rows per question (letters A–E reassigned per `Press_Conference_System.md` / question bank rules),
  - resolved `{player_name}` where applicable,
  - `status`, timestamps, **`question_set_id`** or version stamp (real bank version, not `dummy_v1`).
- **Frontend:** `postGamePressConference.js` + `gameCompletionPopup.js` consume the payload; remove placeholder “Question 1…” when API returns real data.
- **Phase B gate:** keep existing guarantee: week does not advance until session is created successfully (`Press_Conference_System.md`).

**Acceptance:** Full happy path: complete user game → PGPC shows 10–15 real questions → answers appended → session complete clears pending state.

---

## Phase 5 — Answer effects (deferred)

**Deliverables (when ready)**

- Resolve `effect_tags` through a single resolver; apply to FTD / franchise / coach / targeted player per tag semantics.
- Idempotency: completing a session twice should not double-apply (or sessions are immutable after complete).

**Acceptance:** Integration test: chosen answer produces expected delta on a test franchise doc.

---

## Cross-cutting checklist

| Topic | Action |
|-------|--------|
| **One session per game** | Enforce or document “replace vs reject” if user restarts PGPC. |
| **Auth / ownership** | Session `user_id` + `franchise_id` match on all routes. |
| **Performance** | Qualify + select should be O(n) in bank size; cache question list in memory. |
| **Docs** | Update `Press_Conference_System.md` when dummy copy and `dummy_v1` are retired. |

---

## Suggested milestones (for tracking)

1. **M1:** Phase 0 doc + opening lineup (and any critical Tier A gaps) on game document.  
2. **M2:** Phase 2 + tests (fixtures); vanilla + win/loss smoke.  
3. **M3:** Phase 3 + tests; wire counts and vanilla cap.  
4. **M4:** Phase 4 end-to-end (API + UI); retire dummy question set.  
5. **M5:** Phase 5 effect resolver when product is ready.

---

## What this plan intentionally omits

- **Content authoring** for new questions (ongoing in `press_conference_questions.py`).
- **Localization** (if ever needed, hook after selection returns stable question ids).
- **Analytics** (which triggers fire most often) — add if product wants it.

---

## Next immediate step

**Phase 0:** Draft the **PGPC snapshot + franchise context** schema (bullet list or TypedDict) and add **`opening_lineup`** (or agreed field name) to the finalize path as the first **engine** change. Then implement **Phase 2** against that contract with fixtures so qualification and engine work can proceed in parallel without blocking each other.
