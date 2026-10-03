# Decisions to confirm — browse templates

Decided during design but not in the brief. Confirm each, or tell the implementer otherwise, before shipping. **[field]** = needs a data field that may not exist — the implementer must stop and ask, not invent it.

## Encodings and colour
1. **Player RT is letters everywhere — this supersedes Round 2.** The Office/Shell handoff showed player RT as a digit (POTG, projected five, roster). Per this brief, player RT (current → potential) is always a letter grade; digits are for attributes only. The Office frames need the same swap. `CLAUDE.md` still says "Player RT uses the ramp"; it does, as letters.
2. **Attribute digit = hue on the glyph + neutral luminance behind it.** 0–4 no fill, 5–6 w-3, 7–8 w-6, 9+ w-10 with a ring. Strengths read as bright blocks, weaknesses recede, and no hue is spent on a fill (fills belong to energy). This replaces the production tinted tiles (`attr-tiles.css` hue-tinted backgrounds). Confirm the swap — it changes a shipped component.
3. **Blue is used twice on T2 rows** (RT A and attribute 9+). The brief defines both as "elite rating", so they share blue by design. Nothing else on these pages is blue.
4. **Sort indicator is neutral** (white caret + 2px w-70 underline + column wash). The earlier attribute-tile handoff used an orange caret; orange is now reserved for saves / non-advancing actions.
5. **Scope/segment selection is neutral white, not navy.** Navy stays reserved for "your team / your player" rows and the switch-on state.
6. **Streak is plain text** (W t87 / L t60), not the green/red chip. In a 32-row Standings view, coloured chips on every row would spend the alarm channel on the default.
7. **DIFF gets a diverging bar** (neutral, from a centre tick) plus a signed numeral. Direction/position is the channel for diverging values; no green/red.
8. **Weekly deltas on Team Attributes use the Round 2 chip** (green ▲ / red ▼ / neutral —). Only movers are coloured.
9. **Watch star is orange when on** — it's a save.
10. **Recruit hero uses a neutral surface** (no team-colour wash): the recruit isn't on your team yet.

## Page structure
11. **Page tools live at the right end of the sub-tab row**, inside the sticky head, so scope and search stay reachable without adding a second sticky row. At 1280 this slot fits ≈430–520px. If a page ever needs more controls, they go in the table card header.
12. **Standings order: your conference first**, then the rest. Group name lives in the first header cell ("A2 CONFERENCE · Yours"), so the stuck header always says which group you're reading.
13. **Standings at 1920 is a 2 × 2 grid** so a whole region (32 teams) is visible at once; 1280 stacks the four conferences.
14. **Starters / Bench divider rows** appear only in lineup order; any sort removes them.
15. **Varsity / Practice Squad is a scope toggle** on Roster (as approved in the tile handoff). The old "Practice Squad" sub-tab is removed; Team sub-tabs become Roster · Player Stats · Team Attributes · Schedule · Development. **Confirm the tab list** — the mock's order and names are illustrative.
16. **Recruiting sub-tabs** in the mock (Pool · Watchlist · Visits · Signing Board) are placeholders. Use the production list.
17. **The last text column absorbs spare width** on T2 (Dev focus / Lean) so identity, RT and the attribute block stay tight as the window widens.
18. **Full attribute names:** `title` + `aria-label` on every abbreviation, a styled tooltip (name + one-line description + sort hint) on hover/focus, full names on the player page, plus descriptions at 1920. Descriptions are condensed from the tutorial copy (`gob-attributes.js`) — use that source.
19. **Leaders is a board, not a table:** 8 category cards (leader + 2–5 + "Full list →"). The full list is a T1 table. **[field]** qualification rules for FG% / DEF% (e.g. minimum attempts).
20. **Team Stats: GP and PPG lead, ungrouped;** then six groups. The column set is a proposal — if production already has a Team Stats column set, keep it (rule 3).
21. **Team Attributes layout:** two family cards (Character · On the floor) of measure rows with a neutral meter and weekly chip. Family names and descriptions are illustrative. **[field]** scale for each measure (mock: Chemistry /25, the rest /100), descriptions, and which family each belongs to.

## Wide tables
22. **Wide mode is triggered by measured overflow**, not by breakpoint. At 1280, Team Stats (natural 1,300px vs 1,168) scrolls; at 1920 it fits and gets the normal sticky header.
23. **No sticky header in wide mode — the column-header row repeats every 16 rows** instead. The team column is pinned.
24. **Card header controls:** group jump buttons, a position map and ◂ ▸ paging (80% of the visible width). The page's vertical wheel is never captured.

## Detail pages
25. **Sticky detail bar** with "up one level" (labelled with the parent list's name: "← Roster", "← Standings"), breadcrumb and **prev/next within the parent list** ("4 of 12"). Back restores the list's scroll, sort and scope. **[field/route]** the ordered source list.
26. **Sections, not tabs,** on detail pages (keeps the two-level cap; a detail page is the third level).
27. **Player page sections:** Attributes · Development · Recent changes · Stats (career table that includes the current season, with Per game / Totals). Season line appears in the hero. **[field]** attribute change history (week, attribute, from, to); **[field]** which attribute a dev focus trains ("Trains ST").
28. **Attribute change chips were removed from the attribute panel** to avoid duplicating Recent changes.
29. **Team page shows last 6 results + next 4** with "Full schedule →", not the whole season. Games against your team get the navy row.
30. **Team hero actions:** "Scout them" (ghost). Label illustrative.
31. **Recruit page (spec'd, not framed):** neutral hero, RT letters, lean ladder in the key-numbers slot, status tags (Invited · Visit · Wk 5), orange primary action + watch star; body = Attributes (same panel) · Lean detail · Visits/invites. **[field]** action labels and statuses.

## Loading and empty
32. **Skeletons keep the real header** and use final shapes; pulse is opacity-only.
33. **New token `--dur-skeleton: 1.4s`.** The only new token. No existing duration fits a slow ambient pulse (`--dur-pulse` 1.6s is the urgent-badge alarm and shouldn't be shared with a neutral state).
34. **Empty-state copy explains why and when it fills** (e.g. "Standings fill in after Week 1"). Copy is illustrative.

## Carried over, unchanged
35. `components.css` and all Round 2 decisions stand. `.rtab` is superseded by `.tbl` (same values).
