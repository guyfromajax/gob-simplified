# GOB Resource Page Design System
**Geeked-Out Basketball — Internal Design Reference**
*Scope: Resource Pages only. Does not govern the broader game experience.*

---

## What Is a Resource Page?

Pages that are accessed via the Resources tab in the FCC.

The Stats page is the reference implementation of this system.

---

## Design Philosophy

**Dark. Dense. Legible.**
Resource Pages live in a professional, utilitarian space — think front office, not arena jumbotron. The aesthetic is disciplined and data-forward. Every visual decision should make information easier to parse, not harder.

**Consistency over creativity.**
These pages share a design language. A user who has seen one Resource Page should feel immediately at home on any other. Don't introduce new patterns when an existing one works.

**Hierarchy through restraint.**
Color and weight are used sparingly so they carry meaning when they appear. A value that's always orange means nothing. A value that's orange only when it leads the league means everything.

---

## Color

```
--bg:       #0d0f14   /* page background */
--surface:  #141720   /* cards, table container, topbar */
--surface2: #1c2030   /* table header rows, card headers, hover states */
--border:   #252a3a   /* all dividers, grid lines, borders */
--accent:   #e8903a   /* orange — CTAs, active states, #1 rank, section labels */
--accent2:  #4a9eff   /* blue — column group labels only */
--text:     #e8eaf0   /* primary text */
--muted:    #6b7280   /* secondary text, inactive labels */
--good:     #34d399   /* wins, positive deltas */
--warn:     #f5c542   /* losses, caution states */
```

Color is used with intent:
- **Orange** (`--accent`) is reserved for navigation actions, active UI states, #1 ranked values, and section labels. Do not use it for general data emphasis.
- **Green / Yellow** (`--good` / `--warn`) are reserved for win/loss records and explicit positive/negative indicators.
- **Blue** (`--accent2`) is reserved for column group headers in data tables.
- All data values default to `--text`. A value is only colored if it carries specific semantic meaning per the rules above.

---

## Typography

```
Display / Headers:  Barlow Condensed (weights 700, 800)
Body / Data:        Barlow (weights 400, 500, 600)
Source:             Google Fonts
```

**Usage rules:**
- Page titles, section labels, card category headers, topbar text, tab labels, column headers, stat values → `Barlow Condensed`
- Table cell content, player names, body copy → `Barlow`
- Section labels: `Barlow Condensed 700`, 11px, `letter-spacing: 0.2em`, uppercase, `--accent` color
- Card category headers: `Barlow Condensed 800`, 13px, uppercase, `--accent` color
- Column headers: `Barlow Condensed 700`, 11px, uppercase, `--muted` color

---

## Layout

Pages are constrained to `max-width: 1400px`, centered, with `32px` horizontal padding.

**Vertical rhythm:** Sections are separated by `40px` of space. Within a section, elements use `12–16px` gaps. Don't compress; the density comes from the data, not from cramming the chrome.

**Responsive:** Tables scroll horizontally on smaller viewports (`overflow-x: auto`) — never collapse or reflow table columns. Cards use `repeat(auto-fill, minmax(280px, 1fr))`.

---

## Components

### Topbar
Present on every Resource Page. `background: --surface`, `border-bottom: 1px solid --border`.

Contains:
- A back-navigation button on the left. Orange fill (`--accent`), `Barlow Condensed 700`, uppercase, angled shape via `clip-path: polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%)`.
- A breadcrumb or page identifier to the right: `Barlow Condensed 800`, with `--accent` used on the separator character only.

### Section Labels
A full-width ruled divider with an inline label. The label is left-aligned; the rule extends to the right edge using a flex `::after` pseudo-element (`height: 1px`, `background: --border`). Always `--accent` color. Always uppercase. Always `letter-spacing: 0.2em`.

### Scope Tabs (Conference / Region / National)
A pill-style tab group. The outer container has a dark background (`--surface`), a `--border` border, 4px padding, and a 6px border radius. Tabs are borderless buttons inside this container. The active tab has `background: --accent`, white text. Inactive tabs are muted, with a subtle hover darkening to `--surface2`. Font: `Barlow Condensed 700`, 13px, uppercase.

### Data Tables
- Container: `background: --surface`, `border: 1px solid --border`, `border-radius: 8px`, `overflow-x: auto`
- Two-row header: first row for column group labels (blue), second row for individual column names (muted)
- Column group separators: `border-left: 1px solid --border` on the first column of each group — these subtle vertical grid lines must always be present
- Row dividers: `border-bottom: 1px solid --border`
- Row hover: `background: --surface2`
- Totals / summary rows: `background: rgba(232,144,58,0.07)`, `border-top: 2px solid --border`, bold weight, always pinned to bottom regardless of sort
- Column headers are clickable to sort: descending on first click (↓), ascending on second (↑), reset on third. Active sort column header color: `--accent`
- Font size: 13px. Padding: `10px 14px` per cell

### Stat / Leader Cards
Used for ranked individual or team leaders within a category.

- Container: `background: --surface`, `border: 1px solid --border`, `border-radius: 8px`
- Header bar: `background: --surface2`, `border-bottom: 1px solid --border`, category name in `Barlow Condensed 800`, `--accent`
- Each row: 4-column grid — rank | name + sub-label (stacked) | value. `border-bottom: 1px solid --border`. Hover: `background: --surface2`
- **#1 row only** receives color treatment: `background: rgba(232,144,58,0.06)`, rank in `--accent`, value in `--accent` at larger size (`Barlow Condensed 800`, 18px). All other rows are unstyled.
- Row count by scope: Conference → 10, Region → 10, National → 20. Rows beyond the limit are hidden, not removed from the DOM, so tab switching is instant.

---

## What This System Does Not Cover

- Game screens (play, simulation, animation views)
- Modals and overlays
- Onboarding or tutorial flows
- Any screen where the primary interaction is action-based rather than information-based

Those will be designed separately. Do not extend these patterns speculatively into non-Resource Page contexts.