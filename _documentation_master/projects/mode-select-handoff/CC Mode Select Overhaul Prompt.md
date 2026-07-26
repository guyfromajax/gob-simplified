# CC Prompt — Mode Select ("Coach's Home Base") Overhaul

## Context

`FrontEnd/static/mode-select.html` is the screen players land on after login. It currently
renders four stacked full-width sections inside `.mode-wrapper`: franchise slots, Leaderboard,
Around The League, Community Highlights. The redesign gives the page two clear heroes —
**My Franchises** and **Find A Game** — side by side, with the community sections demoted to a
supporting tier below.

The design work is done. Three files in the design project are the source of truth:

- `FrontEnd/static/mode-select.html` — the new markup (drop-in replacement)
- `FrontEnd/static/mode-select.css` — the new stylesheet (drop-in replacement)
- `Mode Select JS Patch Notes.md` — the only `mode-select.js` changes needed, as diffs

Your job is to land those two files in the repo and apply the three small JS changes.
**Do not redesign anything.** If something looks wrong, flag it rather than reinterpreting it.

## Hard constraints

Everything `mode-select.js` reaches for must survive verbatim:

- IDs: `#franchise-home-slots`, `#community-leaderboard`, `#around-the-league-grid`,
  `#leaderboard-view-geek-points`, `#leaderboard-view-titles`, `#leaders-by-team-btn`,
  `#leaders-by-team-modal`, `#leaders-by-team-grid`, `#leaders-by-team-close`,
  `#leaders-by-team-backdrop`, `#alpha-disclaimer`, `#alpha-disclaimer-dismiss`,
  `#mode-select-loading`, `#delete-franchise-modal` (+ its cancel/confirm/text ids),
  `#slots-full-modal`, `#slots-full-modal-ok`
- Class hooks queried by JS: `.community-highlights-body`, `.ms-leaderboard-subtitle`,
  `.leaders-by-team-title`, `.mode-select-loading` on `<body>`
- All `<script>` tags, in the same order, including `authGuard.js`, `gtm-loader.js`,
  `sentryInit.js` and the GTM `<noscript>` iframe
- The `franchise-*`, `atl-*`, `community-*`, `lbt-*` class names that JS emits into those
  containers — the CSS styles them; JS keeps producing them

New in the markup, and required:

- `#franchise-home-slots` carries a layout class: `class="franchise-home-slots fv-a"`.
  The CSS ships three franchise-card layouts (`fv-a` stacked band — shipping,
  `fv-b` status band, `fv-c` editorial ledger). `fv-a` is the approved one. Leave the other
  two rulesets in place for now; they are inert without the class. If you'd rather not carry
  dead CSS, deleting the `fv-b` and `fv-c` blocks is safe — do not delete `fv-a`.

## What the new layout does

**Page head** — new `.ms-page-head` row: eyebrow "Geeked-Out Basketball" + `<h1>` "Coach's
Home Base" with a hairline rule.

**Hero row** (`grid-template-areas: "franchise findgame"`, 1.3fr / 0.7fr):

- **My Franchises** — titled container (`.ms-hero.ms-hero--franchise`) wrapping
  `#franchise-home-slots`. Slots are stacked **vertically** (one column), vertically centred
  in the panel. Each occupied card is a compact ~120–140px band over the team banner art:
  row 1 team name + season line, row 2 Record + Next Opponent chips, row 3 the live-game line,
  with Resume/Enter and Delete Franchise stacked on a right rail.
- **Find A Game** — new `.ms-hero--pvp` panel: eyebrow, big "Find A Game", one hook line,
  a sweeping matchmaking bar and a pulsing "Coming Soon" chip. It is a teaser, not a disabled
  control: no button, nothing clickable, and it must not read as greyed out. All motion is
  wrapped in `prefers-reduced-motion: reduce`.

**Supporting tier** — Around The League full width, then Community Highlights (left, wide) and
Leaderboard (right, narrow). Same markup as before apart from: an `.ms-panel-note` in the ATL
header, and the two "leaders by team" links wrapped in a single `.leaders-by-team-triggers` row.

## Responsive behaviour (don't "simplify" this)

- `@media (max-width: 960px)` stacks the wrapper to one column in the order
  head → franchise → findgame → aroundleague → highlights → community.
- `.franchise-home-slot-cell` is a **size container** (`container-type: inline-size`), and
  `@container franchiseslot (...)` rules retune the card below ~620–660px. That is what keeps
  the chips row, the live-game line and the action rail from colliding in the two-column hero
  at 960–1200px viewports. Keep the container queries; a plain media query cannot express this
  (the card's width depends on the hero split, not the viewport).

## The three JS changes

Apply exactly the diffs in `Mode Select JS Patch Notes.md`, all inside
`buildOccupiedSlotHtml()`:

1. Delete the **Rank** and **Prestige** chips. The card keeps Record + Next Opponent.
   Then delete this now-redundant safety net from the CSS:
   `.franchise-card-grid .franchise-chip:nth-child(n+2):nth-last-child(n+2){display:none}`
2. Game-in-progress line shows the opponent only: `@ Morristown` when the user's team is the
   away side, `vs Xavien` when it's home. Derive from
   `activeGameResume.user_team_side` (same field `buildActiveGameCourtUrl` passes as `my_team`).
3. Delete button label: `Delete` → `Delete Franchise`. No handler change —
   `data-action="delete-franchise"` still drives the confirm modal.

Leave the CPU-sim resume branch's copy as-is; it inherits the same styling.

## Acceptance criteria

- Franchise slots load and render for: zero franchises, one franchise + empty slot, two
  franchises, and two franchises with games in progress. No card is clipped by its container
  and nothing spills past a card edge in any of those states.
- Enter Franchise, Resume Game, Finish Week, Delete Franchise (confirm + cancel), the
  slots-full modal, Start Franchise from an empty slot, the Geek Points/Titles toggle,
  Leaders By Team modal, Coaching Archetypes link, Around The League polling + its FLIP
  animation, and the alpha banner dismiss all behave exactly as before.
- No console errors on load; the loading panel still hides once `revealModeSelect()` runs.
- Check at 1440, 1200, 1100, 1000 and 768px wide. The 1000–1200px band is the one that
  previously broke — verify the live-game line and the chips never overlap the green CTA.
- Find A Game shows no interactive affordance and reads as upcoming, not disabled.

## Out of scope

Franchise data flow, the `/franchise/list` and command-center fetches, Around The League and
Highlights payloads, the modals' internals, and anything on other pages. This is a layout,
styling and copy change only.
