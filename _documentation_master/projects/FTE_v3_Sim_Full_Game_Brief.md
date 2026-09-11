# FTE v3: Sim Full Game Tutorial — Design Brief

> **Status:** Design locked. Ready for implementation.
> **Purpose:** Replace FTE v2's Play-a-Quarter tutorial with a Sim Full Game broadcast (~80–85s) that showcases the product mode users actually play, with pre-sim coaching decisions and ≤5 min wall-clock target.

---

## 1. Context / Goal

### What we're replacing

FTE v2 hooks new users with a Q4 Play-a-Quarter tutorial game (4-minute manual gameplay). This is **being scrapped**. The tutorial game was isolated from franchise state and gave users 4+ minutes of controlled gameplay that doesn't represent how most users experience GOB.

### What we're building

**New hook:** Sim Full Game with a ~80–85s broadcast presentation that shows users the actual mode they'll use — strategic coaching decisions followed by an animated result, not manual gameplay.

### Why

- **Cut post-FTE drop-off:** Show the mode users actually use (Sim + Game Plan + Lineup) rather than teaching manual play controls they won't need.
- **Surface causal coaching:** Let users make pre-game strategic decisions (opponent pick, full Game Plan, lineup) and see immediate results.
- **Maintain ≤5 min wall-clock target:** Setup + broadcast fits the same time budget as the old flow.

### Existing canon to reference

Implementers should read these first:

- **Current FTE v2 system:** `_documentation_master/02_User_Account_Systems/fte_system.md` — this is the baseline being replaced.
- **Sim Game Presentation:** `_documentation_master/06_Gameplay_Systems/Sim_Game_Presentation_System.md` — the broadcast experience we're routing users to.
- **Game Plan system:** `_documentation_master/04_Franchise_Mode_Systems/Game_Plan_System.md` — twelve strategic sliders.
- **Lineup Selection:** `_documentation_master/06_Gameplay_Systems/Lineup_Selection_Screen.md` — roster table and autoset behavior.

---

## 2. Locked Spine (Ordered Steps)

The new FTE v3 flow is **eight steps**, replacing the current seven-step FTE v2:

| # | Step | Screen | Notes |
|---|------|--------|-------|
| 1 | **Sammy Welcome** | `tutorial-persona-intro.html` | Persona intro (unchanged from v2) |
| 2 | **Pick Program** | `franchise-select-team.html?mode=tutorial` | Team select (unchanged from v2) |
| 3 | **Username** | Modal over team select | Keep — required (unchanged from v2) |
| 4 | **Pick Opponent** | NEW screen | Show 7 other conference teams ranked by talent |
| 5 | **Game Plan** | `game-plan.html?mode=tutorial` | All 12 sliders with "Shot Diet" nest |
| 6 | **Lineup** | `set-lineup.html?mode=tutorial` | Preset starting five + optional adjust |
| 7 | **Tip-off → Sim Full Game** | Tip-off modal → `court.html?mode=tutorial` | Broadcast presentation (~80–85s) |
| 8 | **End of Game → Handoff** | EOG modal → `mode-select.html` | Franchise/mode-select entry (unchanged from v2) |

**Progress thread:** Update to 8 dots. Step IDs: `persona | program | username | opponent | gameplan | lineup | tipoff | gameplay`. The `gameplay` dot is never active (same as v2 — it signals the final stop).

### Explicitly OUT of FTE v3

**Playbooks / Playbook % dials are NOT part of this tutorial.** Do not include any "session 2" playbook path, playbook percentage screen, or Playbook Report. Users set Game Plan sliders only; playbook percentages remain at system defaults for the tutorial game.

---

## 3. Step Details

### Step 1–3: Unchanged from FTE v2

**Sammy Welcome, Pick Program, Username** remain as-is. Refer to `fte_system.md` §2 for current implementation. No changes to these screens.

---

### Step 4: Pick Opponent (NEW)

**Placement:** After username is set, before Game Plan.

**What to show:**

- The other **7 conference teams** (exclude the user's chosen team).
- Vertical stack, ranked **most talented → least talented** (top = toughest).
- Make the ranking criterion **clear in the UI** (eyebrow or header).

**UI requirements:**

- **Eyebrow/header copy:** Something like:
  - `CONFERENCE / Pick your opponent / Ranked by talent — top is toughest`
  - Or: `YOUR CONFERENCE · PICK YOUR OPPONENT`
  - Subhead: `Top team is toughest`
- **Default highlight:** A mid-table opponent (rank ~3 or 4 out of 7).
- **Selection:** Tap/click a team card to select; orange-ring selected state (reuse existing team-card pattern from Pick Program).

**Sammy modal (exact copy):**

> Pick your opponent. Top is toughest.

(8 words — within guideline.)

**Ranking metric:**

- Use **best existing team strength signal** available in the codebase.
- Options: team RT aggregate, existing talent score from `teams` collection, or sum of position ratings.
- **Implementer should pick the most accurate existing metric** and document the choice in the PR.
- Do NOT invent a new metric; use what the engine already computes.

**Navigation:**

- `POST /api/auth/tutorial-advance` with `{ step: "gameplan", opponent_pick: <team_name> }` (or similar).
- Store opponent selection in `tutorial_state`.
- Advance to Game Plan screen.

**Fallback opponent (if user picks the same team the opponent would have been):**

- Default opponent logic can mirror FTE v2's `deriveOpponent` pattern: if user team is Xavien, opponent is South Lancaster. Otherwise, pick a sensible mid-table conference foe based on the ranking.

---

### Step 5: Game Plan (NEW — modified from existing Game Plan screen)

**What changes from the existing `game-plan.html`:**

1. **Show ALL 12 sliders** (no reduced "Coach's Card").
2. **Sammy modal on entry (exact copy):**

   > Set your strategy. Sliders have real tradeoffs.

   (7 words.)

3. **NO per-slider hover tooltips** for the general set of 12 sliders (revisit only if user feedback shows a gap).

4. **Nested UX for Inside / Attack / Outside Offense ONLY:**

   - Wrap the three `slider-group` elements (`inside`, `attack`, `outside`) in a **quiet nested family card** inside the existing left offense column.
   - **Do not break the existing two-column layout** (left = offense, right = defense/general).
   - **Section title:** `How you score` or `Shot diet` (implementer pick; either is acceptable).
   - **One shared ⓘ / title hover tip** (~12 words max):

     > These three share touches — raise one, the others compete.

   - **No ⓘ on each individual slider** (`inside`, `attack`, `outside`).

5. **Page mode:** `mode=tutorial`, read-only as in current FTE v2. Sliders should be **interactive** (not disabled), but the tutorial game's strategy settings are initialized to sensible defaults (e.g., all sliders at 2, matching `TUTORIAL_STRATEGY_SETTINGS` from `tutorial_game.py`).

6. **Save behavior:** On CTA click, persist the user's chosen slider values to the tutorial game document (same pattern as current `PUT /api/gameplan` with `mode=tutorial` aliasing to `single`).

7. **Navigation CTA:** Orange action button labeled **CONTINUE** or **SET LINEUP** → advances to Lineup screen.

**Implementation notes:**

- Implementers should reference `game-plan.html` and `game-plan.js`.
- The Shot Diet nest is a **visual grouping only** — it does not change the slider semantics or validation.
- Existing validation (offense-not-all-zero rule) still applies.
- The nested family card should use quiet, low-contrast styling (light border or background tint) to group the three sliders without overwhelming the layout.

---

### Step 6: Lineup (MODIFIED)

**What changes from current FTE v2 `set-lineup.html?mode=tutorial`:**

1. **Preset a smart starting five** (use `POST /api/autoset-lineup` under the hood on page load, or equivalent backend logic).
2. **Sammy modal on entry (exact copy, 9 words):**

   > I set your starting five. Adjust if you'd like.

3. **Primary path:** User clicks **CONTINUE** or **GOT IT** (orange action button) → proceeds to Tip-off.
4. **Secondary path:** User clicks **Adjust lineup** (or equivalent affordance) → enters the full Set Lineup table interaction.

**If user chooses to Adjust:**

- Land on the Set Lineup table with **Attributes tab already selected** (not Game tab).
- **Sammy coach-mark or modal:** CTA to hover attribute headers to learn what they mean.
- **Attribute headers:** Keep existing one/two-word labels only (`Scoring`, `Inside Defense`, `Ball Handling`, etc.) — **do NOT add an attribute textbook or detailed descriptions**.
- Existing attribute hover tooltips (from `attributeTooltips.js`) remain available; no new content needed.
- After user makes changes (or not), CTA: **RETURN TO GAME** (green gate button, same as current FTE v2 feedback modal) → advances to Tip-off.

**Existing tutorial lineup behavior to preserve:**

- Tutorial game should load with **empty lineup slots initially** (if that's the current FTE v2 pattern) or with the preset five (new pattern).
- Lineup intro modal and feedback modal patterns from `tutorialLineupModals.js` can be reused or adapted.
- The feedback algorithm (`pickLineupFeedbackMessage`) can still run if user adjusts lineup, but it's optional for v3 — focus on preset + optional adjust, not on teaching lineup composition.

**Implementation notes:**

- Implementers should reference `set-lineup.html`, `set-lineup.js`, and `js/shared/tutorialLineupModals.js`.
- The preset five should be generated via the existing autoset algorithm (team chemistry ~15, standard eligibility rules) or a simplified sensible default (e.g., top 5 by RT).
- If user does NOT adjust, skip the feedback modal — just advance to Tip-off.

---

### Step 7: Tip-off → Sim Full Game (MODIFIED)

**What changes from current FTE v2:**

1. **Use Sim Full Game path** (not Play Quarter / Q4 inject tutorial game).
2. **Tip-off modal:** Existing `tutorial-situation.html` Moment modal pattern can be reused, but update copy to reflect that the user will **watch** a full game, not play Q4.
   - **Suggested eyebrow:** `YOUR DEBUT`
   - **Suggested body:** Brief score/situation setup (or just "You're ready, Coach. Let's see how your decisions play out.")
   - **CTA:** Green **SIM GAME** or **TIP OFF** button → launches Sim Full Game.

3. **Sim Full Game broadcast:**
   - Boot `court.html?mode=tutorial` with `quarter=1`.
   - Immediately trigger Sim Full Game path: `handleSimFullGame()` in `bootGame.js`.
   - User sees Act 1 (starting-five reveal if Sim Full Game) → Act 2 (broadcast presentation, ~80–85s).
   - Refer to `Sim_Game_Presentation_System.md` for the existing implementation.

4. **Soft-nerf / favorable matchup OK:**
   - Under the hood, the tutorial game can use favorable shot thresholds or opponent settings to increase win probability (same as current FTE v2 tutorial game: `USER_SHOT_THRESHOLD = -10`, `COMPUTER_SHOT_THRESHOLD = 90`).
   - **Do NOT fake rules** — the sim engine runs as normal, just with tilted odds.

5. **Isolation guarantees:**
   - Tutorial game touches **NO** franchise/tournament state (same as FTE v2).
   - Game doc is deleted on locker-room click.
   - All existing tutorial isolation guarantees from `fte_system.md` §9 must be preserved.

**Implementation notes:**

- Implementers should reference `bootGame.js` → `handleSimFullGame()`, `preGameExperience.js`, `simGamePresentation.js`.
- The tutorial game should init with the user's chosen opponent, Game Plan settings, and lineup.
- Opponent derives from Step 4 selection; opponent settings can use default CPU strategy (all sliders 2) or a sensible challenge level.
- The broadcast should render cleanly with tutorial mode styling (team colors, names, etc.).

---

### Step 8: End of Game → Handoff (UNCHANGED)

**EOG behavior remains the same as FTE v2:**

- `gameCompletionPopup.js` renders tutorial variant: eyebrow `Your Debut`, win/loss message, score.
- **No Box Score button** (tutorial game is throwaway).
- **Go To Locker Room** CTA → `POST /api/community/debut` → `POST /api/auth/tutorial-complete` → delete game doc → navigate to `/mode-select.html`.
- Debut publishes to mode-select Live Feed with gold border (unchanged).

**Handoff goal:** User lands on mode-select or franchise-creation flow with **hunger to build their program**, not a pile of tutorials. FTE is complete.

---

## 4. Sammy / Copy Principles

### General guidelines

- **≤8 words for Sammy modals** (Plants vs Zombies / George Fan GDC principle). Exceptions only where locked copy above specifies longer strings.
- **Peer voice, not corporate tutorial tone.** Sammy is a friendly coach-mentor, not a help-desk bot.
- Avoid tutorial-ese like "Let's learn about…" or "Now we're going to…". Prefer direct, active language.

### Locked Sammy strings (exact copy required)

| Step | Locked Copy | Word Count |
|------|-------------|------------|
| Pick Opponent | `Pick your opponent. Top is toughest.` | 6 |
| Game Plan | `Set your strategy. Sliders have real tradeoffs.` | 7 |
| Lineup | `I set your starting five. Adjust if you'd like.` | 9 |

### Shot Diet tooltip (exact copy required)

**Nested family card shared hover tip:**

> These three share touches — raise one, the others compete.

(10 words.)

---

## 5. Implementation Notes for Builders

### Where to look

**Frontend files:**

- **FTE flow orchestration:** `js/shared/authBarInit.js` → `routeToTutorial()` (step-to-page routing).
- **Tutorial state machine:** `POST /api/auth/tutorial-advance` in `BackEnd/api/auth_routes.py`.
- **Game Plan page:** `game-plan.html`, `game-plan.js`, `game-plan.css` (add Shot Diet nest).
- **Lineup page:** `set-lineup.html`, `set-lineup.js` (preset + optional adjust).
- **Sim Full Game:** `bootGame.js` → `handleSimFullGame()`, `simGamePresentation.js`, `preGameExperience.js`.
- **Tutorial game init:** `BackEnd/utils/tutorial_game.py` → `apply_tutorial_initial_state()`.

**New screen (Pick Opponent):**

- Create `tutorial-pick-opponent.html`, `tutorial-pick-opponent.js`, `tutorial-pick-opponent.css` (or similar).
- Reuse team card pattern from `franchise-select-team.html`.
- Fetch conference teams from `/api/teams` or equivalent (filter to user's conference, exclude user team, rank by strength).

**State machine updates:**

- Insert `opponent_pick` step between `username` and `gameplan` (or similar step name).
- Update `TutorialStep` enum in `auth_routes.py`.
- Update `routeToTutorial()` in `authBarInit.js` to route `opponent_pick` step to new page.
- Update progress thread in `tutorialProgressThread.js` to 8 dots.

**Game Plan modifications:**

- Wrap `inside`, `attack`, `outside` slider groups in a nested card.
- Add section title (`How you score` or `Shot diet`) and shared hover tip.
- Ensure tutorial mode (`mode=tutorial`) persists user slider choices to tutorial game doc.

**Lineup modifications:**

- On page load, autoset lineup (via `POST /api/autoset-lineup` or backend preset logic).
- Sammy modal: "I set your starting five. Adjust if you'd like."
- Primary CTA: **CONTINUE** (orange) → Tip-off.
- Secondary path: **Adjust lineup** → open table with Attributes tab selected.

**Sim Full Game integration:**

- Tutorial game should boot with `quarter=1` and immediately trigger Sim Full Game path.
- Use existing `handleSimFullGame()` in `bootGame.js` (no Play Quarter branch).
- Preserve tutorial isolation guarantees (no franchise writes, game doc deleted on EOG).

**Opponent talent ranking:**

- Use **best existing team strength signal**: team RT aggregate, `teams.talent` field, or sum of `position_ratings`.
- Do NOT invent a new metric — use what's already computed.
- **Document the chosen metric in the PR** so future implementers understand the ranking.

**Tutorial game v2 isolation guarantees to preserve:**

- No `franchises_collection` writes (no `franchise_id` on game doc).
- No `tournaments_collection` writes (no `tournament_id`).
- `init-game` `mode=tutorial` branch uses `apply_tutorial_initial_state` and follows `single` finalize path.
- `game-plan` / `playbooks` endpoints alias `mode=tutorial → single` (no franchise lookup).
- Game doc deleted on locker-room click — no orphaned game state.

(Refer to `fte_system.md` §9 for full details.)

---

## 6. Done Criteria

### File deliverables

- [ ] This design brief exists at `_documentation_master/projects/FTE_v3_Sim_Full_Game_Brief.md` (or updated equivalent).
- [ ] PR opened with a short summary (title: "Add FTE v3 Sim Full Game design brief" or similar).
- [ ] PR description links to this file and notes that it's documentation-only (no application code changes).

### Content checklist

- [ ] Locked spine (8 steps) with exact order.
- [ ] Exact Sammy strings for Pick Opponent, Game Plan, Lineup.
- [ ] Shot Diet nest spec (nested card, shared hover tip, no per-slider ⓘ).
- [ ] Opponent pick spec (7 teams, ranked by talent, mid-table default).
- [ ] Playbooks explicitly excluded from FTE v3.
- [ ] Sim Full Game path specified (not Play Quarter / Q4 tutorial game).
- [ ] Implementation notes pointing at relevant files/systems without prescribing line-by-line edits.
- [ ] Opponent talent ranking needs a defined metric (implementer to choose best existing signal and document in PR).

### What this PR does NOT include

- **No application code changes.** This is a design brief only.
- **No implementation of FTE v3 screens or flows.** That work comes in future PRs based on this brief.
- **No changes to existing FTE v2 code.** This brief is the handoff doc for future implementers (Claude / in-IDE agents).

---

## 7. Next Steps (for future implementers)

When building FTE v3 from this brief:

1. **Read the canon:** `fte_system.md`, `Sim_Game_Presentation_System.md`, `Game_Plan_System.md`, `Lineup_Selection_Screen.md`.
2. **Branch and isolate:** Create feature branch, implement one step at a time, test in `mode=tutorial`.
3. **Preserve isolation guarantees:** No franchise writes, no tournament writes, game doc deleted on EOG.
4. **Test the happy path:** New user signup → 8-step flow → Sim Full Game broadcast → EOG → mode-select.
5. **Test edge cases:** Interrupted flow (should resume at correct step), opponent fallback, lineup preset, Game Plan validation.
6. **Measure time:** Target ≤5 min wall-clock from signup to mode-select handoff.

---

## 8. Design Rationale (for context)

### Why Sim Full Game over Play Quarter?

- **Authenticity:** Most users sim most games; teaching manual gameplay over-indexes on a minority path.
- **Speed:** ~85s broadcast + setup fits ≤5 min target; 4-minute manual gameplay leaves less time for coaching decisions.
- **Causal learning:** User makes strategic choices (opponent, Game Plan, lineup) and immediately sees results (win/loss, performance). Play Quarter obscures the causal link between strategy and outcome.

### Why all 12 Game Plan sliders (not a reduced set)?

- **Real tradeoffs:** Hiding sliders or using a "Coach's Card" subset teaches a product that doesn't exist. Users need to see the full strategic surface.
- **Shot Diet nest:** Groups the three offensive sliders that compete for touches (Inside/Attack/Outside) to make the tradeoff explicit without overwhelming the layout.

### Why preset lineup with optional adjust?

- **Reduce friction:** Most users will roll with a smart default; giving them a "no-touch" path respects their time.
- **Preserve agency:** Users who want to tweak can still adjust; landing on Attributes tab primes discovery without forcing it.

### Why Pick Opponent?

- **Stakes and choice:** Letting users choose difficulty (top = toughest) gives them agency and sets expectations.
- **Conference framing:** Reinforces that GOB is about conference play and rivalries, not generic matchups.

---

## 9. Open Questions (for future PRs)

- **Progress thread animation:** Should the thread pulse or glow on step completion, or stay static (like FTE v2)?
- **Opponent card visual:** Reuse team card pattern from Pick Program, or create a simpler ranked-list row style?
- **Game Plan Shot Diet nest:** Visual treatment (border, background tint, spacing) — implementer to choose, but should be quiet and low-contrast.
- **Lineup preset messaging:** Should Sammy modal also show a preview of the preset five (e.g., "I set your top 5 by talent"), or just the locked copy above?
- **Sim Full Game broadcast in tutorial mode:** Should callouts/ticker be suppressed or reduced frequency for tutorial games, or run as normal?

These are **not blockers** — implementers should use judgment and document choices in their PRs. If user feedback surfaces issues, we iterate.

---

**End of Brief.**
