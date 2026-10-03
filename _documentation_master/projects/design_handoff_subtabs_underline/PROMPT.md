Implement the new section sub-tab row ("Underline") across all section pages: Team, Prep, League, Recruiting and News. The full spec is in `design_handoff_subtabs_underline/README.md`, and the live reference is `reference/Subtab Underline.html`. In `reference/subtabs.css`, use only the shared `.sx` rules and the `.dA` rules.

**Before writing any code, report back and wait for my go-ahead:**
1. Which files own the section page head, the current parallelogram sub-tabs, the rounded outer card and inner bordered card that wrap them, the page tools (`.seg` / `.search`), and the sticky table-header offset.
2. The production sub-tab list for each section, and how Tournament's locked state and unlock week are determined today.
3. Which data fields exist for everything under "Data needed" in the README.

**Rules:**
- Never invent, derive or approximate a missing field. If something isn't backed by data (e.g. the Tournament unlock week), stop and ask.
- Don't change what already works: the existing `.seg` / `.search` components and their copy/counts, the top bar, rail and tables, and every existing colour scaling (RT, energy, shot weight).
- All values in the reference are illustrative: tab lists, crumbs, counts, tooltip copy and names. Only structure, tokens and behaviour are the spec. The production tab lists win if they differ; tell me where they do.
- The tab row is neutral white only: no green, navy, blue or orange.
- Overflow is measured (ResizeObserver), not breakpoint-based. Search collapses first, then trailing tabs fold into "More". The selected tab never folds.
- Implement the keyboard model in the README: roving tabindex, ←/→ with automatic activation, Home/End, a focusable locked tab with its tooltip, the More menu keys, and "/" for search.

When you're done, check at 1280×720 and 1920×1080:
- League › Standings fits without collapsing anything.
- League › Team Stats collapses search to an icon.
- Shrinking the window below 1280 folds trailing tabs into More.
- Table headers stick directly under the new head, with no gap or overlap.
