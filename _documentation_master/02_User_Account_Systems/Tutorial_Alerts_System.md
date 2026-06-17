
**The System**
- We'll cue the user with modals at key points during their early experience with the game.
- These will be one-time per user only. Once a user sees a modal, it will never show again.
- If a user chooses not to proceed with the tutorial, add a glow effect behind the Tutorials button in the top nav bar with the next tutorial noted in a callout coming from the button. Example, "Next: Player Attributes".
- Modal Buttons
    - Start lesson (primary design)
    - I'll Do This Later (ghost design)
- Modal timing and copy for each is noted below.
- Note: if a user has already viewed a tutorial, we will still present them with the modal per the logic below, but we will not show the glow effect with the callout next to the Tutorial button if they choose to skip it.

**Counter gates (locked franchise only)** — eligibility uses forward-only counters, not franchise week. Week labels in copy are the curriculum map; thresholds are:

| Alert | Trigger | Counter threshold |
|-------|---------|-------------------|
| Player Attributes | Run Training click | `training_returns === 0` (first training) |
| Training | Run Training click | `training_returns >= 1` |
| Team Attributes | FCC load after training | `training_returns >= 2` |
| Game Plan | Play Next Game click | `games >= 3` |
| Playbooks | FCC load after training | `training_returns >= 4` |
| Scouting | FCC load after a game | `games >= 6` |
| Recruiting | FCC load after a game | `games >= 7` (body copy uses live `{n} games in`) |

**Player Attributes**
- When: first Run Training click on the locked franchise (`training_returns === 0`)
- Modal Copy
    "Hey Coach, you're about to run training for the first time, and this will impact your players' attributes. We suggest you read the Player Attributes tutorial first — player attributes are the core of the game and will impact everything moving forward."

**Training**
- When: Run Training click when `training_returns >= 1`
- Modal Copy
    "You're about to run training. Take a minute with the Training tutorial first."

**Team Attributes**
- When: FCC load when `training_returns >= 2` (typically after 2nd training return)
- Modal Copy
    "You just evolved some of your team's attributes, Coach. The Team Attributes tutorial breaks down the impact of those changes."

**Game Plan**
- When: Play Next Game click when `games >= 3`
- Modal Copy
    "You're about to tip off for a big game, Coach. Run through the Game Plan tutorial before the game begins for a few extra pointers."

**Playbooks**
- When: FCC load when `training_returns >= 4`
- Modal Copy
    "Hey Coach, we think you're ready for the Playbooks tutorial. Playbooks add a deeper level of control and coaching customization."

**Scouting**
- When: FCC load when `games >= 6`
- Modal Copy
    "You've seen the Scouting Report tab by now, Coach. The Scouting tutorial covers how to read it and turn it into an edge."

**Recruiting**
- When: FCC load when `games >= 7`
- Modal Copy (dynamic)
    "{n} games in, Coach. Time to get smart on Recruiting — it's how you build your program for the long haul." (`n` = `tutorial_alerts_games`)


---

## Back To Game (alert-resume footer)

When a user taps **Start lesson** on a contextual alert modal (primary CTA only), the lesson sub-page swaps its normal exit chrome for a **Back To Game** flow so they can return to the exact game moment they were in.

**When it applies**
- User entered the lesson via the alert modal's **Start lesson** button.
- Does **not** apply when entering via Tutorial Home, nav glow re-entry, or any direct/hub link — those paths keep the normal **Back To Tutorial Home** button and **Next up** handoff.

**Lesson sub-page changes (alert entry only)**
- **Remove** the top **Back To Tutorial Home** button.
- **Replace** the bottom **Next up** handoff block with a sticky **Back To Game** footer.
- Footer sits fixed above the persistent tutorial bottom nav; single centered button.
- Button is **ghost** (`.gob-btn--ghost`) from load and **always clickable**.
- When the user scrolls to the bottom of the page, the button switches to **orange fill** (`.gob-btn--action`).
- Tapping **Back To Game** navigates to the stored return URL and **clears** the resume context.

**Return destinations (resume map)**

| Alert # | Lesson | Return destination |
|--------:|--------|-------------------|
| 1 | Player Attributes | `/training.html?…` (full query string captured at Run Training intercept) |
| 2 | Training | `/training.html?…` (same) |
| 3 | Team Attributes | Current FCC URL (`franchise_id`, `team_id`, etc.) |
| 4 | Game Plans | Set Lineup URL for the upcoming game (captured at Play Next Game intercept) |
| 5 | Playbooks | Current FCC URL |
| 6 | Scouting | Current FCC URL |
| 7 | Recruiting | Current FCC URL |

FCC return URLs are captured at modal show time; `tut_alert` is stripped from the stored URL.

**Context scoping**
- Resume context lives in `sessionStorage` (`gob_tut_alert_resume`) for the current browser tab.
- Footer only activates when the stored `lessonId` matches the current sub-page.
- If the user navigates to another lesson via Tutorial Home while context is still set, that other page shows normal **Next up** (no false swap).
- Context clears only when **Back To Game** is used (not on skip, not on leaving the page).


---

## Technical Execution

*(scaffold — expand as needed)*

**Files**

| Layer | File | Role |
|---|---|---|
| Orchestrator | `FrontEnd/static/js/shared/gobTutorialAlerts.js` | eligibility, queue, modal trigger, nav glow, resume URL capture, intercepts |
| Modal builder | `FrontEnd/static/js/shared/gobTutorialNav.js` | `GOB.showTip()` (alertMode), local lesson `seen` state, loads resume script on sub-pages |
| Alert-resume footer | `FrontEnd/static/js/shared/gobTutorialAlertResume.js` | sticky Back To Game bar, scroll-gated styling, context read/clear |
| Loader | `FrontEnd/static/js/shared/authBarInit.js` | loads nav+alerts scripts, fires `onAuthMeLoaded` |
| Triggers | `franchise-command-center.js` (Run Training + Play Next Game clicks), `training-report.js` (`tut_alert=training_return` on training return) |
| Game counter | `BackEnd/utils/user_game_commit.py` | server-side `$inc tutorial_alerts_games` per finalized game, scoped to the enrolled franchise |
| API | `BackEnd/api/auth_routes.py` | dismiss / enroll / increment endpoints |
| Schema | `BackEnd/utils/user_tracking.py` | `tutorial_alerts_*` fields + `TUTORIAL_ALERT_IDS` (7 ids incl. `game-plans`) |
| Styles | `FrontEnd/static/css/gob-tutorial.css` | `.gob-tut-alert-resume*`, `.gob-tut--alert-resume` body padding |

**Server-persisted state (per user, on `/api/auth/me`)**

| Field | Meaning |
|---|---|
| `tutorial_alerts_franchise_id` | first franchise instance; alerts lock to it (never changes) |
| `tutorial_alerts_dismissed[]` | alert ids whose modal has been shown (one-time per user) |
| `tutorial_alerts_games` | games completed on the locked franchise — **incremented server-side** at game commit (`user_game_commit.py`), not via a URL param |
| `tutorial_alerts_training_returns` | training returns on the locked franchise (incremented client-side via `tut_alert=training_return`) |

Lesson-completion (`seen`) stays **local** (`GOB.isSeen`); dismissal is **server-side** (cross-device).

**Flow**
- Player Attributes + Training: `interceptTraining()` wraps Run Training; stores `/training.html?…` as resume URL. Player Attributes when `training_returns === 0`; Training when `training_returns >= 1`.
- Game Plans: `interceptPlayNextGame()` when `games >= 3`; stores set-lineup URL as resume URL.
- Team Attributes / Playbooks (`training_returns >= 2` / `>= 4`) + Scouting / Recruiting (`games >= 6` / `>= 7`): evaluated by `onFccDomReady` on **every FCC load**. `training_returns` increments client-side from `tut_alert=training_return`; `games` is read from the server count. Resume URL = current FCC URL at modal show.
  - *Why param-independent:* the franchise game→FCC return navigates via `return_url`, which the box-score never tags with `tut_alert=game_complete`. The old param-gated path therefore never incremented `games` nor evaluated Scouting/Recruiting — so both are now server-counted and evaluated unconditionally. See bug history 2026-06-09 (counter).
- On **Start lesson**: `stashAlertResume(alertId, returnUrl)` → `sessionStorage` → lesson sub-page reads via `GOBTutorialAlertResume`.
- On skip ("I'll Do This Later") with the lesson still unseen → nav-bar glow + "Next: <Topic>" callout (`applyNavGlow`); no resume context is set.
- **"I'll do this later" advance** (when the modal blocked an underlying navigation): Training / Player Attributes → `/training.html`; Game Plans → set-lineup URL; Team Attributes / Playbooks / Scouting / Recruiting → no extra navigation (user is already on FCC). Close ✕ / backdrop dismiss without advancing.

**Alert-resume footer (implementation)**
- `gobTutorialAlertResume.js` maps pathname → lesson id; activates only when `sessionStorage.gob_tut_alert_resume.lessonId` matches.
- Hides `[data-gob-back]` and `.handoff`; appends `.gob-tut-alert-resume` fixed at `bottom: var(--nav-h)`.
- Scroll listener toggles `gob-btn--ghost` ↔ `gob-btn--action` when `scrollY + innerHeight >= scrollHeight - 32`.
- `gobTutorialNav.js` dynamically loads the resume script on all seven lesson sub-pages.
- If `GOBTutorialAlertResume` is not yet loaded when the modal fires (FCC / mode-select), `gobTutorialAlerts.js` writes `sessionStorage` directly as fallback.

**Modal — Coach Card (premium takeover)**
- One component for all 7 alerts: `GOB.showTip({alertMode:true, ...})` in `gobTutorialNav.js` (`showAlertCard`); styles `.gob-talert-*` in `css/gob-tutorial.css`. See Styleguide → *Tutorial Alert (Coach Card)*.
- Two-column card (256px branded rail + content), full-screen blurred scrim. Rail: whistle "TUTORIAL" mark, Coach Sammy portrait (2px orange ring), "Lesson N of 7" + 7-dot progress. Content: lesson title headline, body copy, "Start lesson" (→ lesson page) + "I'll do this later".
- **Lesson numbering** is the hub's 7-lesson curriculum order via `LESSON_INDEX` (gobTutorialAlerts.js): Player Attributes 1, Training 2, Team Attributes 3, Game Plans 4 (`games >= 3` on Play Next Game), Playbooks 5, Scouting 6, Recruiting 7. Dots: past = dim orange, current = pill, future = faint.
- **Coach art:** lesson 1 → generic white Sammy; lessons 2–7 → selected team uniform via `portraitFor()` (mirrors `teamCoachAsset.js`; team from `localStorage.franchise_user_team`; generic fallback).
- **Entrance:** `.is-entering` animates scrim fade + card rise, removed on `animationend` (800ms fallback); resting state never `opacity:0`; honors reduced-motion.

**Gotchas (load-bearing — see bug history below)**
- **A gate may only reference state reachable on the screen it fires on.** The yield to archetype-reveal / alpha-feedback (`shouldYieldToOtherModals`) is **scoped to FCC** (`isFcc()`), because those modals only mount on FCC. Player Attributes fires on Run Training (FCC) and does not yield to blockers that only exist on other pages.
- **Yield, don't drop.** Where yielding *is* legitimate (FCC alerts), the alert stays queued and retries — `drainQueue` gates on `canShowAlert()` *before* dequeuing, retries via `scheduleDrainRetry()`, and is re-driven by `gob:auth-me-loaded` (fires when the blocking modal closes).
- **Never swallow a click.** `interceptTraining` and `interceptPlayNextGame` only block navigation when an alert *actually shows*; if it can't (yield / scripts not loaded / none eligible) the underlying action proceeds — otherwise Run Training / Play Next Game looks like a dead button.
- **Resume context is modal-primary only.** Hub, glow, and direct links never call `stashAlertResume`; those entries keep **Next up** + **Back To Tutorial Home**.
- **FCC return params must survive `return_url`.** Training submit forwards `return_url` (FCC) onto `training-report.html`. `resolveFranchiseLockerRoomUrl` must **merge** `extraParams` (e.g. `tut_alert=training_return`) into that URL — not return it verbatim — or `processFccReturn` never runs and post-training / post-game alerts silently fail.
- **One show per page load — `presented` set, not just `dismissed`.** `onAuthMeLoaded` can run multiple times on a page (event listener + authBarInit's explicit call + script-load check), and each call overwrites `meCache` with the caller's `/me` object. A locally-patched dismissal lives only in the *replaced* cache, so a stale `/me` (fetched before the dismiss PATCH) silently reverts it and re-queues the alert. The page-local `presented` set in `gobTutorialAlerts.js` is the source of truth that survives cache overwrites — checked in `eligibleIds`, `enqueue`, and `drainQueue` (and set in `showAlert`). authBarInit's explicit call also reads the live `window.__gobAuthMeData` instead of its stale closure copy. **Never rely on `dismissed()` alone to prevent a same-session re-show.**

**Bug history**
- 2026-06-08: Run Training was a hard no-op when an alert yielded (`interceptTraining` returned "blocked" unconditionally); fixed by only blocking when a modal actually shows.
- 2026-06-09: Player Attributes never appeared on mode-select. Root cause: yield gate scoped incorrectly. Fixed by scoping yield to FCC; Player Attributes later moved to Run Training intercept (2026-06-14).
- 2026-06-09 (sweep): Same bug class hit **training / team-attributes / playbooks** on FCC. The reveal only renders when `lead_archetype` is set (≥1 real game), but the yield fired on `archetype_reveal_seen === false` alone — so the early-franchise alerts (which fire *before* the first game) yielded against a reveal that couldn't appear. Fixed: yield to the reveal only when `archetype_reveal_seen === false && lead_archetype` (mirrors `archetypeReveal.maybeShow`). Also bounded the drain-retry and made it re-pull `/api/auth/me` (blocker modals PATCH the server but don't refresh our cache), so legitimate yields resolve instead of spinning on stale state.
- 2026-06-09: Team Attributes (and post-game scouting/recruiting) alert missing after training/game. Root cause: `training.js` attaches `return_url` (FCC) to the training-report redirect; training-report's "Go To Locker Room" called `resolveFranchiseLockerRoomUrl({ extraParams: { tut_alert: … } })`, but that helper returned `return_url` **without** merging `extraParams` — so `tut_alert` never reached the FCC and `processFccReturn` never ran. Fixed: merge `extraParams` into a safe `return_url` when both are present (`common.js`).
- 2026-06-09 (counter): **Scouting and Recruiting never fired at old thresholds.** Fixed (server-authoritative): increment `tutorial_alerts_games` in `user_game_commit.py`; evaluate FCC-return alerts on every load. Thresholds updated 2026-06-14 to `games >= 6` / `>= 7`.
- 2026-06-14: Counter thresholds aligned to curriculum week map (training_returns 0/1/2/4; games 3/6/7). Player Attributes moved from mode-select to first Run Training intercept. Scouting/recruiting pushed to games ≥ 6 / ≥ 7 to avoid alpha-feedback overlap at games ≥ 4.
- 2026-06-09 (re-show on Later): **Player Attributes modal reappeared after "I'll Do This Later" on mode-select.** Root cause: `onAuthMeLoaded` runs more than once per page (the `gob:auth-me-loaded` event AND authBarInit's explicit `.then(() => onAuthMeLoaded(meData))` with the same `/me` response). `markDismissed` patches dismissal into a *new* `meCache` object (`patchMe` uses `Object.assign` copies), so the original `meData` captured in authBarInit's closure stayed stale; the second call overwrote `meCache` with it, `dismissed()` went false again, and `evaluateAndShow` re-enqueued the alert while the first modal was open (queue dedupe couldn't see it — the first instance was already dequeued; the `showing` gate just held the duplicate). Pressing Later ran `finish()` → `drainQueue()` → the duplicate popped instantly. Fixed: (1) page-local `presented` set in `gobTutorialAlerts.js`, checked in `eligibleIds`/`enqueue`/`drainQueue`, set in `showAlert` — an id can never re-show within a page session regardless of cache state; (2) authBarInit's explicit call now passes live `window.__gobAuthMeData` instead of the stale closure object. Bug class applied to any alert shown between duplicate `onAuthMeLoaded` calls.
