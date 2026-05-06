# CURSOR BRIEF — Championship Announce Moments

## Goal
Implement a new "Championship Announce" moment system for Geeked-Out Basketball. These are peak-gameplay celebration moments that sit on top of the existing modal system but are visually distinct from the standard End-of-Game Moment Modal. There are **four distinct moment templates**, each tied to a specific in-game trigger.

The reference design lives in `Championship Announce.html` (4 variations switchable via the Tweaks panel: A, B, C, D). Match the visual treatment in that file exactly — typography, color tokens, layout, spacing, animations, button shapes, and team-color theming. The file is the source of truth for visual implementation.

## Foundation
These moments extend the existing Moment Modal system documented in `Styleguide_updated.md` ("Moment Modals" section). All four share these foundational rules from that spec:
- Surface base: `rgba(13, 17, 36, 0.97)` (where applicable)
- Backdrop: `rgba(0, 0, 0, 0.72)`
- Border: `1px solid rgba(255,255,255,0.12)`
- Border radius: `16px` (where applicable)
- Entrance: subtle scale from `0.96` → `1.0` over `200ms ease` (Variations A and C)
- Button row: `flex-direction: row`, primary `flex: 2`, secondary `flex: 1` (where two buttons are present)
- Button height: `44px`
- Backdrop click does **not** dismiss — explicit button action required
- ESC does **not** dismiss
- All button copy uses `Bebas Neue Pro`
- Toggle visibility via `.is-visible` class (not inline `display`)
- Only one modal visible at a time

Where a variation departs from these (e.g. full-bleed treatments), follow the reference file.

## Four Moment Templates

### 1. Classic Moment (Variation A)
**Visual:** Banner-anchored Moment Modal extension. 560px max-width. Team-color banner top section with trophy chip, gold "CHAMPIONS" headline, green badge, neutral body with team name + score + meta line, two-action button row.

**Triggers:**
- After every **Conference Tournament Championship game** completes (replaces the regular EOG Modal for that game only).
- After every **Region Tournament Championship game** completes (replaces the regular EOG Modal for that game only).
- If the user's team has been eliminated earlier in the bracket and the user pressed **Sim Round**: the Classic Moment should still appear, layered on top of the FCC page when the round simulation completes.
- This moment appears in **all instances** of a Conference or Region Tournament Championship game completing — whether the user's team won, lost, or was eliminated earlier.

**Buttons:** `Back to Locker Room` (primary) and `Box Score` (secondary). Behavior is identical to the current EOG Modal buttons — wire them to the same handlers.

**Eyebrow copy:** `SEASON {N} · CONFERENCE {X}` for conference championship; `SEASON {N} · REGION {X}` for region championship. Pull conference/region label from the existing tournament data model.

---

### 2. Cinematic Full-Bleed (Variation B)
**Visual:** Edge-to-edge full-viewport flood. Team-color floodlight from below, white-on-team-color stadium backdrop, massive "NATIONAL CHAMPIONS" headline, scoreboard-style two-team score row.

**Triggers:**
- After the **National Championship game** completes (the final game of the postseason bracket).
- Same behavior pattern as the Classic Moment for Conference/Region: replaces the regular EOG Modal for that game; if the user pressed Sim Round and the National Championship round resolves, layer this over the FCC.
- Appears in **all instances** of the National Championship game completing — winner and loser both see it (the score row reflects outcome).

**Buttons:** `Back to Locker Room` (primary) and `Box Score` (secondary, dark ghost). Same wiring as current EOG Modal.

---

### 3. Trophy Spotlight (Variation C)
**Visual:** 600px ceremonial modal with gold light-shaft from top, SVG trophy hero, gold-bordered surface, team crest pedestal panel with team name + record + final score.

**Triggers:**
- Appears after **Week 26 has completed** and the user has entered **Week 27**.
- Trigger point: when the user returns to the FCC after pressing **Back to Locker Room** from either the standard EOG Modal *or* from the Box Score view, on the game that closes out Week 26.
- Appears in **all instances** of the Week 26 → Week 27 transition (every team in the league sees it for their own regular-season conference standing).
- This is **not** the National Championship — it celebrates the **Regular Season Champions** for the user's conference.

**Buttons:** **Single button — `Back to Locker Room` only.** No Box Score button. Use a single full-width button OR retain the two-action shape with the secondary slot omitted — match what's in the reference (currently two buttons; **remove the Box Score button** when implementing this template).

**Copy:**
- Eyebrow: `SEASON {N}`
- Headline: `REGULAR SEASON CHAMPIONS`
- Sub: `CONFERENCE {X} · SEASON {N}`
- Pedestal: team name, team record, final regular-season game line (or omit the score row if no game just completed — confirm with PM)

---

### 4. Banner Raise (Variation D)
**Visual:** Full-viewport. Animated championship banner descends from the top rafters with overshoot easing (`cubic-bezier(.22,1,.36,1)`, ~1100ms with 200ms delay), confetti falls in team color + brand palette colors, summary line + action buttons fade up below the banner with staggered delays. Banner uses team color with gold trim and bottom fringe.

**Triggers:**
- Appears **only** for the user's team after they have **won the National Championship** the previous season.
- Trigger point: at the **start of the new season**, after the user has confirmed progressing through the End-of-Season → Next Season flow.
- Appears on the user's **first entrance to the FCC** at the start of the new season, layered over the FCC.
- One-shot: only on first FCC entrance of that new season — not on subsequent FCC visits within the same session/season.
- Appears in **all instances** of a user team winning the National Championship the previous season.

**Buttons:** `Back to Locker Room` (primary) and `Box Score` (secondary, dark ghost). Confirm with PM whether Box Score makes sense here — there is no recent game to score; we may want to **remove Box Score from this template** and ship single-button. **Cursor: ask before implementing.**

**Animation note:** the entrance must run reliably every time. The reference file uses a class-toggle + CSS `transition` pattern (not `animation` keyframes) for the banner, summary, and action fades — replicate that approach so the entrance plays correctly on every mount, including when D activates after being hidden.

---

## Theming
- All four moments must respect the **active team color** for the user's franchise. The reference uses two CSS custom properties: `--team` (primary team color) and `--team-deep` (a darker shade for gradients). Wire these from the active franchise context.
- Default fallback if no team context: `--team: #C0392B`, `--team-deep: #6f1f17` (the Morristown red shown in the reference).
- Gold accents (`#FFD700`) and the `--yellow` brand token are fixed across all team colors — they signal championship semantics.

## Typography
- Display: `Bebas Neue Pro` (existing font files in `/fonts/`)
- Body: `Inter`
- All copy follows the typographic scale in the reference file. Do not introduce new sizes.

## Behavioral Rules (all four)
- Backdrop click does **not** dismiss.
- ESC does **not** dismiss.
- Only one championship moment visible at a time.
- Use the `.is-visible` class on the overlay to toggle visibility (consistent with existing modal system).
- Existing EOG Modal logic should be **bypassed** when one of these championship moments is the appropriate response to a game-completion event — these replace the EOG Modal, they do not stack on top of it.
- Box Score and Back to Locker Room button handlers should reuse the existing EOG Modal handlers (where those buttons are present).

## Out of Scope
- The standard EOG Modal for non-championship games is **unchanged**. Do not modify it.
- The Functional Modal, Strategic Modal, Action-Only Modal patterns are unchanged.
- Toast notifications are unchanged.

## Reference Files
- `Championship Announce.html` — visual reference, all four variations switchable via the Tweaks panel. Source of truth for layout, color, type, spacing, animation timing.
- `Styleguide_updated.md` — modal system foundation. The "Moment Modals" subsection is the spec these extend.

## Cursor: Ask Before Building
**Do not assume or guess.** Before implementing, surface every question you have about:
- Where the existing EOG Modal is wired (component name, file path, the event that opens it). Confirm exactly which call sites need to branch into the new championship moments.
- The data model for tournaments (how to detect "this game was the Conference Championship" vs "Region Championship" vs "National Championship"). Specifically: what flag/field on the game or round object identifies championship-tier games?
- How "Sim Round" completion currently routes to the EOG Modal, and how to layer the championship moment on top of the FCC instead in that path.
- The exact event/state transition for "Week 26 → Week 27" (where in the codebase that boundary is detected) and how to gate Trophy Spotlight to fire exactly once on the first FCC entrance after that transition.
- Where the End-of-Season → Next Season confirmation flow lives, and the right hook to set a "show Banner Raise on next FCC mount" flag for the user's team after a National Championship win.
- The active-franchise team color: where it's stored, how to read `--team` / `--team-deep` from it (and whether `--team-deep` already exists or needs to be derived).
- Whether Trophy Spotlight should show a final-game score line (the regular-season game that closed Week 26) or omit the pedestal score block entirely.
- Whether Banner Raise should keep the Box Score button (there is no recent game) — confirm one-button vs two-button shape with PM.
- How to handle a user who plays multiple franchises: are these moments per-franchise (yes, expected) and how is "first FCC entrance of new season" tracked per franchise?
- Any persistence required — e.g. if a user dismisses Banner Raise and reloads the page mid-session, should it reappear? (Default expectation: no — once dismissed, it does not reappear.)
- How to localize / pluralize the eyebrow copy (`SEASON 1 · CONFERENCE 1`, etc.) using existing string utilities.
- Sound/audio: should any of these moments play a stinger? If so, which one?

**Do not start writing code until each of these is answered.** When in doubt, ask.

## Acceptance Criteria
- All four moments visually match `Championship Announce.html` at default team color and at every team-color swatch in the Tweaks panel.
- Each moment fires only at its specified trigger.
- Each moment correctly replaces (not stacks on) the standard EOG Modal where applicable.
- Buttons are wired to existing handlers; no new navigation logic is introduced unless explicitly approved.
- Animation entrance for Banner Raise plays reliably on every mount (including after navigating away and returning, if the moment is re-shown for any reason).
- Backdrop click and ESC do not dismiss.
- Active team color flows through `--team` / `--team-deep` to all four moments.
