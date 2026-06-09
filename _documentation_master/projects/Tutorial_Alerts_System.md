
**The System**
- We'll cue the user with modals at key points during their early experience with the game. 
- These will be one-time per user only. Once a user sees a modal, it will never show again.
- If a user chooses not to proceed to with the tutorial, add a glow effect behind teh Tutorials button in the top nav bar with the next tutorial noted in a call out coming from the button. Example, "Next: Player Attributes".
- Modal Buttons
    - Tutorials (primary design)
    - I'll Do This Later (ghost design)
-Modal timing and copy for each is noted below
-Note, if a user has already viewed a tutorial, we will still present them with the modal per the logic below, but we will not show the glow effect with teh callout next to the Tutorial button if they choose to skip it.


**Player Attributes**
-When: after the user completes their fte game and they land back on the mode-selet screen.
-Modal Copy
    "Nice work, Coach. Before you start your first franchise, get to know Player Attributes — they're the foundation for every decision ahead."

**Training**
-When: when teh user presses the Run Training button for the first time in their first frandchise instance
-Modal Copy
    "You're about to run training for the first time, Coach. Take a minute with the Training tutorial first."

**Team Attributes**
-When: when the user returns from their first training and lands back on the FCC
-Modal Copy
    "You just evolved some of your team's attributes, Coach. The Team Attributes tutorial breaks down the impact of those changes."

**Game Plan**
-When: when teh user presses the Play Next Game button for the first time in their first frandchise instance
-Modal Copy
    "Your first game is next, Coach. Run through the Game Plan tutorial before you tip off."

**Playbooks**
-When: when the user returns from their week 2 training in their first franchise instance and lands on the FCC.
-Modal Copy
    "Hey Coach, we think you're ready for the Playbooks tutorial."

**Scouting**
-When: when user returns to the FCC after completing their week 3 game of their first franchise instance.
-Modal Copy
    "You've seen the Scouting Report tab by now, Coach. The Scouting tutorial covers how to read it and turn it into an edge."

**Recruiting**
-When: when user returns to the FCC after completing their week 6 game of their first franchise instance.
-Modal Copy
    "Six games in, Coach. Time to get smart on Recruiting — it's how you build your program for the long haul."


---

## Technical Execution

*(scaffold — expand as needed)*

**Files**

| Layer | File | Role |
|---|---|---|
| Orchestrator | `FrontEnd/static/js/shared/gobTutorialAlerts.js` | eligibility, queue, modal trigger, nav glow |
| Modal builder | `FrontEnd/static/js/shared/gobTutorialNav.js` | `GOB.showTip()` (alertMode), local lesson `seen` state |
| Loader | `FrontEnd/static/js/shared/authBarInit.js` | loads nav+alerts scripts, fires `onAuthMeLoaded` |
| Triggers | `franchise-command-center.js` (training click), `box-score.js` / `training-report.js` (`tut_alert` URL param on FCC return) |
| API | `BackEnd/api/auth_routes.py` | dismiss / enroll / increment endpoints |
| Schema | `BackEnd/utils/user_tracking.py` | `tutorial_alerts_*` fields + `TUTORIAL_ALERT_IDS` |

**Server-persisted state (per user, on `/api/auth/me`)**

| Field | Meaning |
|---|---|
| `tutorial_alerts_franchise_id` | first franchise instance; alerts lock to it (never changes) |
| `tutorial_alerts_dismissed[]` | alert ids whose modal has been shown (one-time per user) |
| `tutorial_alerts_games` | games completed on the locked franchise |
| `tutorial_alerts_training_returns` | training returns on the locked franchise |

Lesson-completion (`seen`) stays **local** (`GOB.isSeen`); dismissal is **server-side** (cross-device).

**Flow**
- Player Attributes: `onAuthMeLoaded` on mode-select, gated on `fte_v2_complete`.
- Training: `interceptTraining()` wraps the Run Training click.
- Team Attributes / Playbooks / Scouting / Recruiting: FCC return via `?tut_alert=` param → `processFccReturn()` → counter increment → eligibility check.
- On skip ("I'll Do This Later") with the lesson still unseen → nav-bar glow + "Next: <Topic>" callout (`applyNavGlow`).

**Gotchas (load-bearing — see bug history below)**
- **A gate may only reference state reachable on the screen it fires on.** The yield to archetype-reveal / alpha-feedback (`shouldYieldToOtherModals`) is **scoped to FCC** (`isFcc()`), because those modals only mount on FCC. On mode-select (where Player Attributes fires) there is nothing to yield to, so the gate must not apply — otherwise the alert defers forever against a blocker that can never clear. This is the core design rule: **one alert, one screen, gates that only depend on state present on that screen.**
- **Yield, don't drop.** Where yielding *is* legitimate (FCC alerts), the alert stays queued and retries — `drainQueue` gates on `canShowAlert()` *before* dequeuing, retries via `scheduleDrainRetry()`, and is re-driven by `gob:auth-me-loaded` (fires when the blocking modal closes).
- **Never swallow a click.** `interceptTraining` only blocks navigation when an alert *actually shows*; if it can't (yield / scripts not loaded / none eligible) training proceeds — otherwise Run Training looks like a dead button.

**Bug history**
- 2026-06-08: Run Training was a hard no-op when an alert yielded (`interceptTraining` returned "blocked" unconditionally); fixed by only blocking when a modal actually shows.
- 2026-06-09: Player Attributes never appeared on mode-select. Root cause: `shouldYieldToOtherModals` yielded whenever `archetype_reveal_seen === false`, but the archetype-reveal modal only mounts on FCC — so on mode-select a new user (reveal not yet seen) yielded against a blocker that could never clear. Fixed by scoping the yield to FCC only.
