# Implementation brief: Prep pages v2

Paste this whole file into the agent. It is written for Claude Code or a Cursor agent working in `guyfromajax/gob-simplified` on branch `develop`.

---

You are implementing the redesigned Prep section: **Training · Game Plan · Playbooks · Scouting Report**.

The spec is `_documentation_master/projects/design_handoff_prep_v2/`:
- `README.md` has the frames, decisions, new components and data needed. Read all of it first.
- `prep-v2.css` has the new component CSS, built on the existing tokens only.
- `frames/*.html` are static references. Open them in a browser, or open `index.html` to see every frame with its full scroll length.
- `shell.js` is preview scaffolding only. **Do not port it.** The shipped top bar and rail stay exactly as they are.

The frames sit on the browse-template system in `_documentation_master/projects/design_handoff_browse_templates/` (`tokens.css`, `components.css`, `templates.css`). The tab row follows `_documentation_master/projects/design_handoff_subtabs_underline/`. If that row has already shipped, reuse it. Don't rebuild it.

## Step 0 — report before writing any code

Stop after this step and wait for my reply.

1. **Owning files.** For each of the four pages, list the HTML, JS and CSS files that own it today:
   - `training.html/.js/.css`, `training-report.*`, `game-plan.*`, `playbooks.*`
   - the scouting report surface, including `js/shared/scoutingReport.js`
   - the shared modules each page uses: `developmentFocus.js`, `attrTiles.js`, `rtBucket.js`, the playbook tiles and call-sheet code, and the shot-weights strip
2. **Shell.** Say whether the Prep pages already render inside the franchise shell (top bar + rail + Underline sub-tab row). If they don't, describe what hosting them there involves.
3. **Data.** For every item under **Data needed** in the README, say whether the field exists. Give its name and where it comes from (API route, payload key). Mark each one **exists / exists under another name / missing**.
4. **Open questions.** Answer each of these, or say you can't find it:
   - What enables Submit Training today (`updateRequirementsBar()`): all points spent, focus chosen, or both?
   - Is there a threshold at which the Breaks and Scrimmages copy is meant to show, or is it tooltip-only?
   - What enables Save Playbooks?
   - How is a play added to or removed from the call sheet today?
   - Do the scouting usage tables have a locked state? See `test_scouting_usage_unlocks`.
   - What scale do `shot_threshold` and `rebound_modifier` use?
   - Which play names do the fast-break and half-court-trap usage tables actually return?
   - Is strongest/weakest measure a field, or should it be computed as max/min of the eight axes?

## Hard rules

- **Never invent, derive or approximate a missing field.** If something in a frame has no backing data, stop and ask. This includes effect copy for Tempo and Play Alteration. They have none, so render no line.
- **Mock values are illustrative.** That covers player names, initials standing in for headshots, ratings, weights, CMD, percentages, notes text, play names, sample CTA labels and counts. Only structure, tokens and behaviour are the spec.
- **Don't micromanage what already works.**
  - Keep existing CTA copy, validation and modals: the offense-not-all-Never modal, Auto-Train lock-in, the Player Maximizer modal, Back To Lineup / Cancel.
  - Keep existing column sets (report and scouting stats views) and the shared Development Focus selects.
  - Keep existing colour scalings: the **RT ramp**, the **energy ramp**, and the **shot-weight strip's own colour scaling and thresholds**. The frame's neutral shot-weight numerals are a stand-in. Keep production's.
- **Colour law:**
  - Green only on the top-bar Advance. On an open training week it reads Submit Training, and there is no second Submit in the body.
  - Orange only on Save Game Plan and Save Playbooks.
  - Navy only for "yours": call-sheet rows, and plays in the list that are on the call sheet.
  - Blue only on elite glyphs (attribute 9+, RT A).
  - Choice controls (chips, segments, selects) stay neutral white.
- **Layout:**
  - One vertical scroller per page (`.main`). No card inside a card, and only tables get the single `.tcard`.
  - Content starts 8px under the tab hairline.
  - **Game Plan must fit 1280×720 with nothing below the fold and Save visible.** It is reachable from timeouts.
- **No new design tokens.** Use `prep-v2.css` classes as the reference. Port them into the codebase's own structure rather than linking the file wholesale.

## Build order (after I approve Step 0)

One PR per page, in this order:

1. **Game Plan.**
   - The `.gt` 5-stop track replaces the range inputs. Keep the same ids, 0–4 values and save payload.
   - It is `role="slider"`: arrow keys step, Home/End jump.
   - Save goes in the tab-row tools.
2. **Training.**
   - `.ps` six-stop stepper replacing the drill sliders (same inputs, 0–5, stops above the remaining budget disabled).
   - `.bud` budget and focus check in the tab-row tools.
   - Coaching focus 2×2.
   - Player Development table with 28px portraits (monogram fallback).
   - `.dnote` for Breaks and Scrimmages per the Step 0 answer.
   - Then the **training report**: order, the `.ad.cu` / `.ad.cd` changed-tile marks, neutral ▲/▼ deltas.
3. **Playbooks.**
   - `.play` rows with the in-place `.pdet` detail.
   - Sticky `.csr` call sheet, keeping the existing drag/reorder logic and the 8+8 cap.
   - Offense/Defense segment, balance check and Save in the tools.
4. **Scouting.**
   - Opponent header with the `.xt` strongest/weakest block.
   - Projected five in the T2 Roster grid (`.agrid`).
   - `.ms` measures (−20…+20).
   - Three usage tables. At 1920 the page must fit one screen, as in `prep-scouting-1920.html`.

## Acceptance checks per PR

- Compare side by side with the matching frame at 1280×720, and at 1920×1080 for Scouting.
- No console errors. Save, submit and validation behave exactly as before.
- Keyboard: tabs, sliders, pips, chips and selects are reachable, with visible `:focus-visible` rings.
- The colour law holds. A grep for green, orange, navy and blue in the new CSS finds only the allowed uses.
- Worst-case data renders without overflow: 12 players, 8/8 call-sheet slots, the longest play name, every Game Plan setting at an unnamed stop.
