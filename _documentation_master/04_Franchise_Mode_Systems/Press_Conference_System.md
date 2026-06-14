
# Post-Game Press Conference (PGPC) (**verified 2026-06-13**)

> Verified vs code — **fully accurate, no corrections.** `FRANCHISE_PGPC_AT_EOG_ENABLED = false` default (`gameCompletionPopup.js` L12); `PGPC_MIN_WEEK_FOR_PROGRAM_NARRATIVE_QUESTIONS = 5` gating `max_chemistry`/`above_500` (`pgpc_qualification.py`); selection `r.randint(6, 8)` weighted, ≤3 `always` in first vanilla fill then pad (`select_pgpc_questions_for_session`); `shuffle_answers_for_display` shuffles all rows then returns first four A–D; API routes `/franchise/press-conference/session[/{id}/answer|/complete]` (`press_conference_routes.py`); all referenced modules (`pgpc_context/qualification/selection/template_substitution/player_slot/snapshot_storage`, `models/pgpc_snapshot.py`, `utils/press_conference_questions.py`) + `docs/To Do/PGPC_Snapshot_Schema.md` exist. Doc references symbols by name (no line numbers) → drift-resistant.

Franchise-only flow that runs **after the user’s game is saved** (`POST /franchise/complete-week/phase-a`) and **overlaps** simulation of CPU games (`POST /franchise/complete-week/phase-b`). The user answers press questions in a modal on `court.html` while phase B may still be running.

**Franchise EOG gate (May 2026):** PGPC is **not shown** on the franchise game-complete modal while **`FRANCHISE_PGPC_AT_EOG_ENABLED`** is **`false`** in `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` (default). PGPC modules and API remain in the codebase; set the flag to **`true`** to restore the old EOG CTA and press-conference overlay.

---

## When it runs

1. **End of game:** `finalizeGame` runs (tournament save, franchise **phase A**, etc.). For franchise mode, phase A persists the user result and sets pending state (`localStorage`: `franchise_complete_week_pending`, `franchise_eog_pgpc_snapshot`) for optional resume—not fully productized, but written after successful phase A.
2. **EOG modal:** `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` shows **Game Complete** with real score / POTG.
   - **Franchise with phase B pending and `FRANCHISE_PGPC_AT_EOG_ENABLED`:** **Box Score** is hidden on this popup; primary CTA is **Post-Game Press Conference** (replaces the usual Box Score + locker row on this surface only).
   - **Franchise with phase B pending and flag `false`:** **Box Score** + **Go To Locker Room** (same as other modes); **Go To Locker Room** waits for phase B then navigates to the FCC.
   - **Other modes:** Box Score + Go To Locker Room unchanged.
   - **Background scoreboard:** When the EOG popup opens, the court scoreboard DOM is synced to **final** home/away scores and a **FINAL / 0:00** clock readout so the dimmed court behind the modal is not stuck at Q1 / 0–0.
3. **PGPC CTA:** Optional **Sammy reminder** modal (`pgpcSammyReminderModal.js`) unless suppressed; then `launchPostGamePressConference` opens the PGPC overlay.
4. **Phase B timing:** `POST /franchise/complete-week/phase-b` starts **as soon as the franchise EOG popup appears** (`getOrStartFranchisePhaseB` in `FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js`, invoked from `gameCompletionPopup.js`). It is **not** gated on Sammy or the PGPC button. When PGPC is enabled and the user opens it, `launchPostGamePressConference` **reuses the same in-flight Promise** (single-flight per `franchise_id` + `week` in a tab) so phase B is not requested twice. When PGPC is disabled at EOG, **Go To Locker Room** awaits that same Promise and clears `franchise_complete_week_pending` on success. If PGPC is enabled and the user finishes all press answers before phase B returns, the existing **“Simming Computer Games”** waiting UI (team logo + pulse) still applies.

---

## Question content (live sessions)

When the session request includes **`game_id`** and the game exists in Mongo:

1. **Context:** `BackEnd/pgpc_context.py` — `build_franchise_context_for_pgpc(game_doc, franchise_doc, …)` merges box score / game doc with franchise `results` (streaks, season series vs opponent, first/last week flags, **above .500 / below .500** flags, etc.). Optional DB fields: national ranks and player RT from franchise collections.
2. **Qualification:** `BackEnd/pgpc_qualification.py` — `get_qualifying_pgpc_questions(game_doc, ctx)` filters `PRESS_CONFERENCE_QUESTIONS` from `BackEnd/utils/press_conference_questions.py` by `trigger.condition` + filters. Question bank is loaded via importlib from that file (avoids heavy `BackEnd.utils` import).
3. **Selection:** `BackEnd/pgpc_selection.py` — `select_pgpc_questions_for_session`: **`random.randint(6, 8)`** distinct questions (capped by pool size), **weighted** by `weight`, preferring non-`always` triggers; up to **3** `always` questions in the first vanilla fill, then more vanilla if needed to hit the target.
4. **Per-question display:** `shuffle_answers_for_display` **shuffles** all answer rows from the bank, then returns only the **first four** with letters **A–D**. The bank may still define **five** answers; the fifth is omitted at random by shuffle order (not a fixed “drop E”).
5. **Templates & slots:** `BackEnd/pgpc_template_substitution.py` resolves placeholders (`{player_name}`, `{opponent_name}`, stat tokens, Tier-C tokens from `game_doc["pgpc_tier_c"]`). `BackEnd/pgpc_player_slot.py` resolves `player_slot` (e.g. high scorer) from the game doc.
6. **Week 5+ narrative gates:** Until **`ctx["week"] >= 5`** (`PGPC_MIN_WEEK_FOR_PROGRAM_NARRATIVE_QUESTIONS`), these do **not** qualify: **`team_chemistry`** with **`max_chemistry`** (chemistry_low), and **`above_500_first_time_season`**. High-chemistry (`min_chemistry`) rows are not gated by week.

**Caveats**

- The same **condition** can match **multiple** bank rows (e.g. several “first time above .500” variants). Selection does **not** dedupe by subcategory; several similar questions can appear in one session.
- Season flags that use `franchise_doc["results"]` depend on correct **`week`** and complete prior-week rows; misaligned week or gaps in `results` can skew flags (see `[PGPC_CONTEXT]` logs in `BackEnd/pgpc_context.py`).

---

## API

Base path: **`/franchise/press-conference`** (FastAPI router in `BackEnd/api/press_conference_routes.py`). Auth: current user; franchise ownership verified on create.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/franchise/press-conference/session` | Create session. Body: `franchise_id`, `week` (≥ 1), optional `game_id`, `question_set_id` (default **`bank_v1`**). Returns `session_id`, `questions`, `question_count`. |
| `POST` | `/franchise/press-conference/session/{id}/answer` | Body: `question_index`, `choice` **`A`–`E`**. Updates `answers[]`, `choice_counts`. UI currently sends **A–D** only. |
| `POST` | `/franchise/press-conference/session/{id}/complete` | Marks session `completed`. |

If **`game_id`** is missing or the game is not found, the server builds **dummy** questions (10 × placeholder A–E) for plumbing—**not** the normal franchise UX. The live client always sends `game_id` when starting PGPC from EOG.

**Session document** (`press_conference_sessions` collection, `BackEnd/db.py`): `user_id`, `franchise_id`, `week`, `game_id`, `question_set_id`, **`questions`** (resolved list shown to the user), **`answers`**, **`choice_counts`**, `status`, timestamps, optional **`pgpc_context`**, **`qualified_question_count`**, **`pgpc_snapshot`** (`BackEnd/pgpc_snapshot_storage.py`: pruned game + context for audit/debug).

**Gameplay / franchise effects** from answer `effect_tags` are **not** applied yet (storage and analytics only).

---

## Frontend

| File | Role |
|------|------|
| `FrontEnd/static/js/phaser/utils/postGamePressConference.js` | Modal UI: waiting state (logo, “Simming Computer Games”, pulse), question loop (**A–D** from API), completion (“Week *n* complete.”, **Go To Locker Room** → FCC), `POST` answer + complete; attaches phase-b handlers to shared Promise. |
| `FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js` | Single-flight `POST …/complete-week/phase-b` per franchise week; EOG starts it, PGPC reuses it. |
| `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` | EOG popup, franchise PGPC button, Sammy reminder, scoreboard sync, **background phase-b** when pending. |
| `FrontEnd/static/js/phaser/finalizeGame.js` | Phase A, `finalScore` / localStorage snapshot for PGPC. |
| `FrontEnd/static/js/phaser/gameScene.js` | Calls `showGameCompletionPopup` with `finalScore` after `finalizeGame`. |

Placeholder **`PGPC_DUMMY_QUESTIONS`** in `postGamePressConference.js` uses **10** questions × **4** letters only for the brief period before the API returns; the server-driven list is **6–8** questions with **four** shuffled answers each.

---

## Related specs / types

- Question bank shape and effect tags: header docstring in `BackEnd/utils/press_conference_questions.py`.
- Context / snapshot typing: `BackEnd/models/pgpc_snapshot.py`, `docs/To Do/PGPC_Snapshot_Schema.md`.

---

## Observability

`build_franchise_context_for_pgpc` emits **`INFO`** lines prefixed with **`[PGPC_CONTEXT]`** (week, record before/after, flags, `results` week keys, weeks missing a user row). Use to debug wrong eligibility (e.g. “first time above .500”) when `week` or `results` do not match the command center.
