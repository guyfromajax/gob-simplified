# Build: Tutorial — Advanced Topics (3 sub-pages + hub wiring)

## What this is
Three Advanced Topic tutorial sub-pages have been designed and approved as static mockups. Build them into the live frontend, wire them into the master tutorial hub, and set their back-button behavior.

## Source of truth
- **Design, page structure, and final on-page copy:** the three approved mockup files and their shared stylesheet:
  - `Advanced — Momentum.html`
  - `Advanced — Press & Trap.html`
  - `Advanced — Practice Squads.html`
  - `assets/gob-advanced.css` (loaded *after* `gob-tutorial.css`; contains all the reusable Advanced-Topic components)
  - Ensure you have these four files before starting. If they are not in your working tree, ask for them — do not reconstruct from memory.
- **Original copy (for reference/reconciliation only):**
  - `_documentation_master/projects/Tutoraial_Pages_Copy/momentum-subpage.md`
  - `_documentation_master/projects/Tutoraial_Pages_Copy/press-trap-subpage.md`
  - `_documentation_master/projects/Tutoraial_Pages_Copy/practice-squad-subpage.md`

The mockups were built on the existing tutorial design system (`gob-tutorial.css` + the shared tutorial nav script) and deliberately mirror the structure of the existing lesson page and the master hub at `FrontEnd/static/tutorial.html`.

**Treat the rendered text in the approved mockups as the final on-page copy.** Where it differs from the source markdown, it was intentionally copy-edited — do not silently revert to the markdown.

## Tasks
1. **Create the three sub-pages** in the frontend, following the codebase's existing conventions for tutorial lesson pages (file location, naming/routing, templating, head/script includes, auth-bar and footer injection, analytics, favicon, etc.). The mockups reference local asset paths (`assets/gob-tutorial.css`, `assets/gob-nav.js`); replace these with the production equivalents the rest of the tutorial system uses. Place/serve `gob-advanced.css` wherever the tutorial CSS lives and load it after the base tutorial stylesheet.

2. **Wire the master hub containers to the sub-pages.** In `FrontEnd/static/tutorial.html`, the Advanced Topics section renders into `#advanced-topics-list` via `gobTutorialHub.js`. Replace the current "coming soon" / disabled state for these three topics with live entries that link to the new sub-pages. Inspect how the core topics are defined and rendered in `gobTutorialHub.js` and follow that same data/rendering pattern.

3. **Back-button behavior.** On all three sub-pages, the back control (`[data-gob-back]`) must return the user to the **master tutorial page**. Adjust whatever drives this (the shared tutorial nav script) so these sub-pages route back to the hub, rather than the current smart-back / referrer-based behavior — implement it the way the codebase prefers to express this.

4. **Reconcile progress / "seen" tracking.** Each mockup calls `GOB.markSeen('adv-momentum' | 'adv-press-trap' | 'adv-practice-squads')`. Align these ids with the hub's actual Advanced Topics progress system so the Advanced Progress bar updates correctly when a topic is visited. Use the real ids/keys from the codebase, not the placeholder ids in the mockup.

## Do not guess
You have full purview over the codebase, database, and repo structure. For anything not explicitly pinned above — file locations, routing, build/templating, the hub's data schema, progress storage keys, asset pipeline — inspect the codebase and follow existing patterns. Do not invent paths, ids, or conventions. If something is genuinely ambiguous, or the source copy conflicts with the approved mockup (e.g. the Standard Trap line in the press/trap content that reads "two backcourt defenders," which may have been intended as frontcourt), surface it for a decision rather than guessing.

## Acceptance checks
- All three Advanced Topics hub containers link to and open their respective sub-pages (no remaining "coming soon" state for these three).
- Each sub-page renders with the standard tutorial shell, styles, bottom nav, and footer, consistent with existing lessons.
- The back button on each sub-page returns the user to the master tutorial page.
- The hub's Advanced Progress reflects visited topics.
