

**Post Game Press Conference**
Occurs after the user's game completes (complete week / phase A) and before/during simulating of computer games (complete week / phase B)

##After user's game completes##
EOG modal appears with current data and design. **Franchise, phase B pending:** Box Score is hidden; the primary CTA is **Post-Game Press Conference** (replaces the old “Sim Computer Games” control on this popup only). Other modes keep Box Score + Go To Locker Room.

When the user presses **Post-Game Press Conference**, a dedicated modal opens on `court.html`, **`POST /franchise/complete-week/phase-b` starts only after** a press-conference session is created successfully (so the week is not advanced if PGPC cannot start). The user works through questions while phase B runs in parallel.

If the user closes the browser before PGPC, `localStorage.franchise_eog_pgpc_snapshot` (plus `franchise_complete_week_pending`) is written after phase A for a future **resume** hook (not fully wired in v1).

##Post-Game PC Experience##
Modal over `court.html` with dummy copy for plumbing:

- **10 questions:** “Question 1” … “Question 10”
- **5 options each:** “Answer A” … “Answer E”, rows labeled **A–E**, `click-tiny.wav` on choice
- **While user finishes before phase B:** team banner, **“Simming Computer Games”**, green horizontal pulse (in-modal, not `PageLoadOverlay`)
- **After phase B and all questions:** “Week {week} complete.”, small summary line **`A: n, B: n, …`**, **Go To Locker Room** → FCC; `POST .../complete` marks the session; pending localStorage cleared on successful phase B

If phase B finishes first, after the last answer the same completion view appears immediately.

##Data Storage##
Collection **`press_conference_sessions`**: per-session doc with `user_id`, `franchise_id`, `week`, optional `game_id`, `question_set_id` (e.g. `dummy_v1`), `answers[]`, `choice_counts`, `status`, timestamps. **FTD / gameplay effects from answers are not applied yet.**

##Code references##
- UI: `FrontEnd/static/js/phaser/utils/postGamePressConference.js`
- EOG wiring: `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`
- Snapshot after phase A: `FrontEnd/static/js/phaser/finalizeGame.js` (`franchise_eog_pgpc_snapshot`)
- API: `BackEnd/api/press_conference_routes.py`, DB handle `press_conference_sessions_collection` in `BackEnd/db.py`
