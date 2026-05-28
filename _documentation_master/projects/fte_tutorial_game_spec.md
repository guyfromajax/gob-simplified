# New User Onboarding — Tutorial Game (FTE Overhaul)

**Purpose:** Replace the current four-modal FTE with a single playable first-game loop. A brand-new user picks a team, names themselves, and plays a real 4-minute game against a tuned opponent — then their debut publishes to the mode-select Live Feed. This is the implementation brief for C+C.

**Design lens:** Simple, Stable, Scalable. The first experience teaches by playing, not by reading. Every screen has one decision and only the words that decision needs.

**Status:** Directional brief. Open technical questions are flagged inline for C+C to resolve.

---

## Why this replaces the current FTE

The current FTE (`authBarInit.js` → 4 welcome modals → mode-select) *talks about* the game and teaches nothing actionable, then drops the user on a hub with no momentum. New-user retention past session 1–2 is the problem it fails to solve.

The fix is not more onboarding. It is one complete, legible loop: a real decision that visibly matters. Our incoming users are hand-raisers (organic search + YouTube algorithm) who arrived *wanting* depth — so we do not hide complexity or hand them an easy win. We get them to a real, winnable-but-not-guaranteed game fast, and publish the result to the world.

---

## The flow (end to end)

| # | Screen | The one decision / beat | Notes |
|---|--------|------------------------|-------|
| 1 | Team select | Pick 1 of 8 programs (pithy handles) | Identity-forming. Reuse existing team-select UI + handles. |
| 2 | Username | "You're now coaching [Program]. What's your name, Coach?" | Attaches to the team pick. Name must exist before step 7 publishes. |
| 3 | Situation card | Read the stakes | "Xavien. Tied 60–60. 4 minutes left in the 4th." → CTA to set lineup. |
| 4 | Set lineup (pre-filled) | Confirm or tweak the five | Bespoke pre-fill function. Stats laddered to 60–60 visible. Attribute hover tooltips live. One Sammy modal. |
| 5 | Play | Coach the 4 minutes | Real engine. Opponent quietly tuned (see Opponent Tuning). |
| 6 | Payoff | Win or loss message | Win: congrats. Loss: spine, not a participation trophy. |
| 7 | Publish | Debut hits the Live Feed | Standalone "arrival" entry. Headline the debut, not the scoreline. Soften losses. |
| 8 | Land | Mode-select, on the board | User sees their entry. World in front of them. |

**Throwaway exhibition:** This game touches NO franchise state. The user starts their real franchise fresh afterward, with a clean game 1. The Live Feed entry is a standalone debut record, not a franchise game result (see Live Feed Publish).

---

## Screen-by-screen

### 1. Team select
- Reuse the existing 8-program select screen and its handles (e.g. Bentley-Truman "Top-Shelf Talent," Lancaster "Muscle & Defense," South Lancaster "Us vs The World").
- **Source of truth for the full eight: `franchise-select-team.html`.** Reconcile all handles against the repo before build.
- No new copy needed here beyond what exists.

### 2. Username
- Single modal, immediately after team pick.
- Copy: **"You're now coaching the [Program]. What's your name, Coach?"**
- Input → `POST /api/auth/set-username` (existing endpoint — preserve).
- This is the one piece carried over from the old FTE. It moves from a cold pre-game gate to an identity beat riding the team-pick high.

### 3. Situation card
- One screen, stakes only.
- Copy: **"Xavien. Tied 60–60. 4 minutes left in the 4th. Set your lineup, Coach."**
- (Opponent is Xavien per the prototype default — weakest available. If the user somehow has Xavien as their own pick, fall back to South Lancaster, mirroring prototype logic.)
- CTA → set-lineup.

### 4. Set lineup (pre-filled)
- **Bespoke pre-fill function** sets a valid default lineup for the chosen team. (Confirmed buildable.)
- Display the fabricated team + player stats that ladder believably to a 60–60 score. Must survive a curious user clicking in and studying them — keep them internally consistent.
- **Attribute hover tooltips** live on the attribute header (e.g. hover "ID" → "Inside Defense"). This is where attribute teaching happens — in context, on demand. No standalone attribute lesson anywhere in the flow.
- **One Sammy modal** (assistant coach, `sammy_tutorial.png`), merged from the two we considered:
  > "I've set your lineup — tweak it if you like, and hover any attribute to see what it means."
- Keep it to this single modal. Modal-creep is exactly what made the old FTE dead weight.
- CTA → play.

### 5. Play
- Real game engine, real 4-minute 4th quarter. Music, SFX, visuals — the compelling core, unmodified.
- Phaser canvas dimensions must NOT be modified (standing constraint).

### 6. Payoff
- **Win:** congratulatory, earned.
- **Loss:** something with spine and forward motion — this audience wants stakes, not consolation. No "good try!" tone.
- Both lead to the publish + mode-select.

### 7. Live Feed publish
- Write a **standalone debut entry** to the mode-select Live Feed, under the user's new username.
- **Headline the arrival, not the scoreline.** Frame: a new coach has entered the league. This is what earns the throwaway exhibition — the user is socially on the board before committing to a franchise.
- **Soften loss language**; do not publish a bald "lost to Xavien."
- **Critical (throwaway integrity):** the entry must NOT imply a clickable franchise behind it. A debut announcement needs no franchise to click into; a "game result" implies one does. Build it as an arrival record so it never looks orphaned or broken later.

### 8. Land on mode-select
- User arrives on the hub with their debut visible in the Live Feed, ready to start their real franchise.

---

## Opponent tuning

- **Secretly nerf the opponent's attributes / thresholds** for the tutorial game only.
- **Goal is not "make them win" — it's "make the honest game winnable on a first try without setup knowledge."** They have not done training camp or learned tactics; the nerf compensates for that, nothing more.
- **Tune so a *competent* first decision wins and a *careless* one can still lose.** The loss must stay real. If it can't be lost, the published result is meaningless and the stakes evaporate.

---

## What's preserved vs. replaced

**Preserved:**
- Username creation (`POST /api/auth/set-username`) — relocated to step 2.
- `fte: true` flag + `POST /api/auth/fte-complete` to mark the experience done.
- Sammy assistant-coach character (`sammy_tutorial.png`).

**Replaced / removed:**
- The four welcome modals (Hey Coach / we assume you know hoops / tutorial button / YouTube). Gone. Their teaching intent is dissolved into the in-context hover tooltips at step 4.

---

## Open technical questions for C+C

1. **Where does the tutorial game live in the page graph?** It runs pre-franchise, after signup, before mode-select. Does it slot into the existing FTE trigger in `authBarInit.js`, or does it need its own entry route? It must run on a page where the game engine can load (note: `authBarInit.js` currently skips `court.html` and gameplay pages).

2. **Pre-fill function scope.** Confirm the bespoke lineup pre-fill produces a fully valid, playable lineup for any of the 8 teams with no further required input.

3. **Fabricated stat consistency.** Ensure the laddered-to-60–60 stats render coherently on set-lineup and any drill-down a user might open.

4. **Live Feed entry schema.** Define the standalone debut entry so it is visibly distinct from real franchise game results and is non-clickable-into-a-franchise.

5. **FTE-complete timing.** Call `fte-complete` after the publish (step 7) so an interrupted tutorial doesn't mark the user as onboarded prematurely. Decide the resume behavior if a user drops mid-tutorial.

6. **`fte: true` users who already exist.** Confirm migration/behavior for current alpha users carrying `fte: true` who would now hit the new flow.
