# Set Lineup redesign — locked decisions

Carry-over brief. Current file: **`Set Lineup - v3 Fits.html`**. Predecessors kept for reference: `Set Lineup - Timeout Read.html` (v1, two-panel), `Set Lineup - Timeout Read v2 Consolidated.html` (v2, single table, 15-player error).

## Context

The Set Lineup screen is what the user lands on during **timeouts and quarter breaks** in live gameplay. The read has to happen in seconds. Priority order, per the user: **energy → RT → headshot/name → momentum**. Roster is **12 players**. Worst case is an empty lineup = 5 slot placeholders + 12 bench = **17 rows**.

## The encoding grammar (the core of the whole redesign)

Energy and RT clashed in the original because they were rendered *identically* — two colored text values, same size, adjacent. The fix was never placement; it was giving each variable its own visual channel. Every channel is now used exactly once per row:

| Variable | Channel | Treatment |
| --- | --- | --- |
| ENG | hue in a **bar** | brand green ≥70 / yellow 40–69 / red <40 |
| ENG number | **luminance**, no hue | ~55% white ≥70 / ~90% white 40–69 / 100% white <40 |
| RT | hue on a **letter** | the game's canonical blue/green/yellow/red ramp, untouched |
| F | neutral, speaks only at 4–5 | quiet at 0–3, amber 4, red 5 |
| MO | **direction**, one-sided hue | −5…+5 pip ladder, red left / white right, no blue |
| Shot weights | existing programmed ramp | do not re-map |

Rules that fall out of it and must hold:
- **Energy's hue lives in the fill, never in the number.** That's what prevents two colored glyphs sitting adjacent.
- **Blue belongs to RT.** MO and +/− were both reverted off blue for this reason.
- **Row edge flags problems only** — 3px leading edge, amber 40–69, red <40, *absent* ≥70. Coloring the healthy state was the original "loud at rest" trap: 12 green cells saying nothing is wrong.
- **Only color the exception, not the default.** Same principle behind the row edge.

## Structural decisions

1. **One table, not two panels.** Once the on-court five were un-dimmed and grouped at the top, the right-hand Starting Five cards were a second copy of the same five players with the same values. Deleting them made substitution one gesture in one list instead of a cross-panel drag.
2. **On-court group at full contrast, bench slightly dimmer.** The original dimmed the assigned five — inverted hierarchy, since their energy is the most important data on screen.
3. **Empty slots are real dashed rows** holding their position label. ON COURT is always exactly 5 rows; header reads `2/5 · 3 SLOTS OPEN`.
4. **Derived reads live in the title bar** — AVG ENG / UNDER 50% / FOUL RISK, centered between the label and the view toggle. They were tried on the group header first; the title bar removed a dead band.
5. **Third view tab `Game`, default.** Attributes and Stats keep their existing columns verbatim — they only inherit the ENG/RT relocation and row grouping. Twelve static attribute columns answer a roster-building question, not a timeout question.
6. **The rail earns its place** — two shot-weight charts (Playbook, Play Call Center), same format, plus a bottom-anchored action zone (Autoset / Game Plan / Playbooks). The rail's content is short and the table's is long, so bottom-anchoring absorbs slack instead of displaying it as a dead pocket.
7. **Nothing below the fold, ever** — unless the user shrank the window. Rows 28px, headshots 24px. ENG is the single flexible column so surplus width lengthens the energy bar (cap ~150px) rather than pooling as a gutter; no trailing spacer column; every other column content-sized. Attributes is the widest view and sets the floor.

## Rejected, and why

- **RT on a prestige/achromatic ramp** — elegant, and it made hue collision impossible, but RT's canonical ramp is used game-wide. Consistency of a core encoding beats local elegance.
- **Green energy numbers** — telegraphic but spends the loudest signal on the default state.
- **Blue for positive MO / positive +/−** — steals RT's elite marker.
- **MO as a continuous bar** — the data is a −5…+5 integer, so the encoding should be discrete.
- **+/− column** — the sim doesn't track it. Removed.
- **MO on the lineup cards** — went away with the cards themselves; it lives in the table only.

## Open / unverified

- The **70/40 energy thresholds** are a proposal — needs checking against how the sim actually depletes energy.
- Whether **28px rows** hold up at real size; there's ~84px of headroom now that the roster is 12, so 32px is affordable.
- **Pre-game state**: every bar is 100% green and energy contributes nothing to the read. If that's the most-seen state, energy may not deserve full width there.
- Whether the on-court group stays distinct enough as rows rather than cards for a 30-second glance.
- Headshots in all mocks are **initials placeholders** — the real component/images exist in the build.

## Handoff

`CC Prompt - Set Lineup Timeout Read.md` is the Claude Code prompt but is **stale** — written against v2, before the 12-player correction, the empty-slot rows, and the rail action zone. Regenerate it from v3 before handing it over. Its standing instructions are worth keeping: make C+C report which files own the table and rail before writing anything; never invent or derive a missing field; don't touch Attributes/Stats columns, RT's mapping, the shot-weight scaling, or the primary CTA copy.
