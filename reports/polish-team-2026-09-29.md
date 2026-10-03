# UX polish batch A — Team (design review items 3, 4, 5, 6)

Branch `ux/polish-team` off `origin/develop`.

## Read this first — three calls that need your sign-off

1. **The server now sends twelve measure rows instead of six.** Item 5 said "find why they're dropped and fix at the source; if the server doesn't send them, stop and tell me." The *values* were always on the response (`team_attributes` carries all twelve). What was missing was the **display list** and the **ranks**: `office_digest.py` hard-coded six rows and `team_measure_ranks.py` ranked six keys. I extended both rather than stopping, because the fix was additive and no existing field changed meaning. If you'd rather I had stopped, this is the commit to revert.
2. **Momentum is the twelfth row, and that was my inference.** You named six missing measures (Offense, Defense, P/T Offense, P/T Defense, Fast Break, Fast Break Defense), which takes six to twelve only if `momentum_score` also joins. Twelve fills a 4×3 grid exactly, so I included it. Say the word and it comes out, leaving eleven and one empty cell.
3. **The ± pill went on exactly the eight you specified**, and I had to name them from `Team_Attribute_System.md` rather than from you: Offense, Defense, P/T Offense, P/T Defense, Fast Break, Fast Break Defense, Fight, Discipline — the eight trained, compounding measures documented at −20…+20. Chemistry (7…25), Momentum (−10…+10), Shooting (~85…95) and Rebounding (~0.5) have no meaningful zero, so they stay on the league percentile bar they already had.

Two smaller flags are in **Judgement calls** at the bottom.

---

## Item 3 — Square headshots

### The brand rule

Added to `UX_System.md` §2 as **"Player headshots are square"**: a square with a small corner, never a circle, everywhere a player's face appears — photo, monogram or placeholder. Team logos and team initials badges are explicitly excluded and keep `--radius-logo`.

The corner scales with the box so every headshot reads the same *weight*: `--radius-6` on the 28–46px table and list badges, `--radius-10` on the large portrait. A radius past a quarter of the side is closer to a circle than to a square, so that's the documented ceiling.

**Why not simply `--radius-10` everywhere.** You said to use the token the portrait/tile components use, which is `--radius-10`. On the 120px portrait that's a small corner. On a 28px table badge it's 36% of the side and reads as a squircle — close enough to a circle to defeat the point of the change. I rendered 4/6/8/10px and 50% side by side at 28px to check rather than guess. `--radius-6` is also what `recruiting-results-hub.css` already used for its square signing headshots, so it was the established corner here, not a new one.

### Every place changed

| File | Selector | Was | Now | Surfaces it reaches |
|---|---|---|---|---|
| `css/gob-components.css` | `.gob .av` | `--radius-10`¹ | `--radius-6` | Roster, Leaders, Player Stats, Scouting, Recruiting results hub — the one shared atom |
| `css/prep-v2-scouting.css` | `#scouting-view .av` | `--radius-round` | *(rule reduced to size only)* | Prep › Scouting |
| `recruiting-spine.css` | `.pool .pc-av` | `--radius-round` | `--radius-6` | Recruiting pool |
| `css/player-development-grid.css` | `.pdg-av`, `.pdg-av img` | `50%` | `--radius-6` | Player development grid |
| `css/training-newswire.css` | `.wr-hs` | `50%` | `8px` (46px box) | Training newswire |
| `training-report.css` | `.training-notes-hero-portrait-img`, `-fallback` | `999px` | `6px` (40px box) | Training Report notes hero |
| `player-detail.css` | `.pd-portrait-wrap`, `.pd-portrait-placeholder` | `50%` | `10px` (120px box) | Player detail hero |

¹ `.gob .av` was `50%` at the start of this branch; I had already moved it to `--radius-10` earlier in the batch, then to `--radius-6` after looking at it rendered.

Prep › Scouting's rule was re-declaring the whole atom — display, fill, ring, corner — so it silently overrode the shared change. I deleted the duplicated properties and left only the size, which removes the divergence rather than patching it twice.

`training-report.css` used `border-radius: 999px`, which a `50%` sweep misses entirely. I widened the search to `999px`/`9999px` and re-swept; that's how the Training Report hero was caught.

### Deliberately not changed

- **Team logos and team initials badges** (`.gob .logo`, `--radius-logo`) — not headshots, per your instruction.
- **The live game (`court.html`) and the sim's Phaser marker.** Four circular headshots, all styled by `court.html`'s own inline `<style>` rather than any shared sheet: the playcall reveal HUD (`.hud-headshot-container`, 70×70), the sim quarter event log (`.sim-quarter-player-image`, 40×40), and two that are dormant — the scoreboard's `.active-player-headshot` (its updater returns immediately) and the audible popup's `.audible-headshot-container` (styles and handler both commented out). Plus `createHeadshotMarkerV2.js`, which draws circles on the Phaser canvas with a height-linked radius, not in the DOM at all. Squaring these is a game-presentation change rather than a UI one, so I left them. **Tell me if you want them in scope** — the two live ones are a two-line change.
- **Account/user avatars** (`auth-bar.css .account-avatar`, `account.html`) — the signed-in person, not a player.
- Roughly 130 other `50%` rules across the app are dots, toggle knobs, spinners, notification pips and slider thumbs.

Recruiting had no files in the nav agent's list, so nothing was skipped on that account. Adding headshots where Recruiting has none remains a later batch.

**Why seven files and not one.** `gob-components.css` — and therefore `.gob .av` — is loaded by `franchise-command-center.html` alone. The Recruiting pool, the development grid, the training newswire, the Training Report and Player detail each run on pages that never see it, so each needed its own rule changed. A parallel sweep of the whole frontend confirms these seven cover every live circular player headshot in the DOM outside `court.html`. Already square before this batch, for the record: the Office Player of the Game (`--radius-10`), the shell's Player detail tab (`8px`), the signing results table (`--radius-6`), Set lineup (`5px`), both POTG cards (`8px`), the foul-out and matchup popups (`10–12px`) and Team builder (`5–10px`).

## Item 4 — Roster

All four changes are scoped `html.gob-shell #roster-view`, in `gob-views.css`, with the alignment carried on classes emitted by `rosterView.js`.

- **Current → Pot left-justified.** `th.rt`/`td.rt` are `text-align: left`, so the two grades start at the column edge and read as one lockup.
- **Highlight squares removed.** These were the luminance background fills on `.attr-tile.is-mid/.is-hi/.is-elite` plus the inset ring on elite. `#roster-view .attr-tile` now has `background: transparent; box-shadow: none`. The tier still lives in the digit's colour, so nothing is lost — the grid just stops reading as a heat map. The tiers themselves (`floor(raw/10)`), the RT ramp, the energy ramp and the tier metals are all untouched.
- **Attribute values centred** under their headers, header and body both.
- **Column rhythm.** Three blocks with their own padding scale: identity columns (`.code` centred, `.num` right-aligned with tabular figures), then six attribute pairs, then Dev focus. A pair is tight (`--space-2` between its two cells) and pairs are spaced (`--dsp-10` at each pair boundary). **WT no longer crowds SC**: `td.wt` closes the identity block with `--dsp-16` on its right, the widest gutter in the table, and Dev focus opens with the same. Dev focus keeps its right justification.

Scoped to `#roster-view` only. The compact five-attribute roster inside `#team-view` is a different table and is unchanged.

## Item 5 — Team Attributes

### Why six measures were missing

Two independent six-row lists on the server, both hard-coded, neither one a data problem:

1. **`BackEnd/utils/office_digest.py`** built the display rows from a literal tuple of six `(key, label, scale_max)` entries: Chemistry, Fight, Discipline, Shooting, Rebounding, Defensive efficiency. Offense, both P/T measures, both Fast Break measures and Momentum simply had no row to appear in. Now twelve entries, and each carries a fourth field, `signed_scale`.
2. **`BackEnd/utils/team_measure_ranks.py`** `MEASURE_SPECS` ranked the same six keys, so even once a row existed it would have had no place and no movement. Now all twelve, `higher_better` except `shot_threshold`. `_DELTA_KEYS` derives from `TEAM_MEASURE_KEYS`, so `rank_delta` picked the new keys up with no further change.

The stored values were never dropped: `GET /franchise/team-data` has always returned all twelve keys on `team_attributes`. The radar has always drawn eight of them. Only the row list and the rank table were short.

The one semantic call: `Team_Attribute_System.md` defines `pt_efficiency` as your own press/trap execution and `pt_opp_modifier` as working through the opponent's press. So `pt_efficiency` is **P/T Defense** and `pt_opp_modifier` is **P/T Offense**. I also relabelled `defensive_efficiency` from "Defensive efficiency" to **"Defense"** so it pairs with Offense.

### The radar

`buildTeamMeasuresRadarMarkup` is called, not reimplemented — `teamAttributesView.js` reaches it as `window.buildTeamMeasuresRadarMarkup` because `franchise-command-center.js` is a classic script, and its `tm-radar-*` CSS is already on the page. Same ±20 scale, same eight axes, same zero ring.

Two things had to be fixed around it:

- **It was rendering at a fraction of its size.** My card was `display: flex`, which made `.tm-radar-wrap` a shrink-to-fit flex item; the svg's own `width: 100%` then resolved against that collapsed width, so the chart drew at roughly 220px with 7px axis labels. The card is now a plain block and lets `.tm-radar-wrap` do the centring it already does.
- **Its axis labels disagreed with the cells below it.** The chart said "Fast Breaks" and "Press/Traps" where the grid said "Fast Break" and "P/T Defense" — two names for one measure on one screen. I changed the two labels in `TEAM_MEASURES_RADAR_AXES`, and the matching two in `TEAM_ATTR_NAMES` so the legacy FCC tab doesn't contradict its own chart. No test pinned either string.

The chart is sized `min(448px, 44vh)`. It's square, so its width is its height; bounding it by the viewport keeps all twelve cells on screen at 720px tall and still lets it grow at 1080. The shell only ever sets `.gob-1280` and `.gob-1920`, so a mid-size density class would have been dead code.

### The grid

Four columns by three rows at both sizes. Each column holds a pair, exactly as specified:

| | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| **Row 1** | Offense | P/T Offense | Fast Break | Shooting |
| **Row 2** | Defense | P/T Defense | Fast Break Defense | Rebounding |
| **Row 3** | Chemistry | Fight | Discipline | Momentum |

Each cell is the name and the place on one line, then the gauge, the value and the movement on the next — so no row ends in a long empty run. The bottom row drops its rule, which would otherwise float just above the card's own edge.

The **± pill is the shared `.gob .dv` atom**, not a second implementation. Prep v2 had already built exactly this control — neutral, centre-zero, `--v` as the magnitude 0–1, `.neg` flipping the fill left — for the same eight measures. I promoted it from `prep-v2-scouting.css` into `gob-components.css` and left a pointer comment behind. Prep › Scouting now reads the same atom; its spec still passes.

A stored `0` is a real reading and draws the centre tick (Fast Break Defense in the screenshots). No stored value draws an empty track. These differ because `Number(null)` is `0` — the first version of `gauge()` got this wrong and the spec caught it.

**Movement is neutral**, matching the Prep v2 decision: ▲ at `--text-100`, ▼ at `--text-60`. No green, no red, no chips.

Raw values show for Chemistry (`19/25`) and for the eight signed measures (`+11`, `−7`). Shooting, Rebounding and Momentum show place and bar only — the same as before this change, since `88` and `0.6` are engine numbers that mean nothing to a player. Your cell spec was name/rank/pill/movement, so nothing is missing; say so if you want a figure there.

## Item 6 — Team Schedule

`teamScheduleView.js`: the `#N` prefix renders only when `opponent_natl_rank` is 1–25, otherwise the opponent's name stands alone. Nothing else changed.

The fixture proves the boundary in both directions — 25th is prefixed, 26th is not — and the screenshots show 118th, 88th, 64th, 51st, 41st, 26th and an unranked 999 all clean.

## Tests

New: **`tests/e2e/polish-team.spec.js`**, 11 tests, both viewports.

- **Roster** — computed `text-align` per column class; every attribute tile has a transparent background and no ring while at least one still carries a high tier; the pair rhythm measured between *ink* rather than between cell boxes (adjacent table cells always touch, so the geometry lives in the padding), plus the declared padding scale; no sideways overflow.
- **Team Attributes** — twelve `.mcell`; the radar present and drawn larger than 300px rather than collapsed; every axis label also appearing as a cell name; a 4×3 grid; each pair sharing a column centre to within 1px; `.dv` on exactly the eight signed keys and `.gob-meter` on the other four; every pill's fill starting or ending at the track's centre line; every colour in the grid neutral (red, green and blue channels within 12 of each other); radar and all twelve cells inside one screen.
- **Schedule** — every prefix is 1–25 and the four above-25 opponents appear bare.
- **Headshots** — computed radius is not 50% *and* not more than a quarter of the side, sides equal, on Leaders, the Roster and the Training Report's three headshot components. Plus a stylesheet crawl asserting no rule matching a headshot selector resolves to a circle.

The Training Report needs a whole week's payload to render, so its test mounts the two real headshot components against the real `training-report.css` and `training-newswire.css`, served from the origin so the page's own script — which redirects when no franchise is loaded — never runs. The shape is what's under test.

Updated: `t2-roster.spec.js` (twelve measures, the grid, the pills, no tile fills), `team-schedule-columns.spec.js` (the 25/26 boundary), `test_team_attribute_measures.py` (twelve rows, the four paired labels, and that only the eight carry `signed_scale`), `test_team_measure_ranks.py` (all twelve directions), `recruits-pool.spec.js` (it pinned `--radius-round` in source and asserted the monogram *was* round — now asserts square).

## Gate

Both green, one run each, on this branch.

- `pytest --ignore=tests/e2e` — **4045 passed, 20 skipped, 109 xfailed, 1 xpassed, 0 failed** (3m 17s).
- Full Playwright — **562 passed, 3 skipped, 0 failed** (8.5m). `--workers=1`, port 8157, `CI` unset, `ps` showed no other Playwright run first.

`test_prove_pool_cli_exits_clean` passes; its SQLite failure is a tool-sandbox artifact only and this run was unsandboxed.

The suite regenerated 91 report images belonging to other briefs. All 91 are restored to `HEAD`; nothing under `reports/` is staged except this report and `reports/polish-team/`.

## Screenshots and self-check

`reports/polish-team/` at 1280×720 and 1920×1080. I opened each.

**`roster-1280` / `roster-1920`.** Six identity columns then six shaded/unshaded attribute pairs under Offense, Defense, Skills, Grit, Body, Mind, then Dev focus. Current → Pot reads from the left edge of its column ("C+ → B+"). Attribute digits sit centred under their headers with no square behind any of them, including the 10s and 11s that used to carry the brightest fill. WT's numbers are right-aligned with a clear gutter before SC. Dev focus is hard right. Headshot monograms are square with a small corner. Eleven of twelve players are visible at 720px and the twelfth is a short scroll; no clipping, no sideways scroll.

**`team-attributes-1280` / `team-attributes-1920`.** The radar sits above a 4×3 grid and everything fits one screen at both sizes. Eight axes labelled Offense, Fast Break, Discipline, P/T Defense, Defense, Fast Break Defense, Fight, P/T Offense — the same words as the cells. Offense `+11` fills right of the centre line, Defense `−7` fills left, Fast Break Defense `0` is a bare tick on the centre, Discipline `−4` fills left. Chemistry, Shooting, Rebounding and Momentum are left-filling percentile bars, all four on the same track width as the pills. Movement reads ▲4 ▼6 ▲1 ▲2 ▲3 ▼2 ▼1 in white and grey.

**`team-schedule-1280` / `team-schedule-1920`.** Four week columns, the whole season on one screen. Prefixes on #1 Fairview, #3 York, #7 Millbrook, #12 Ashford, #19 Oak Ridge, #25 Four-Corners. Bare names for Bentley-Truman (26), Harbor City (41), Northgate (51), Morristown (64), Crestwood Prep (88), Kingsport Valley (118) and St. Brendan (999).

**`leaders-1280` / `leaders-1920`.** Eight leaderboards, each hero a 36px square headshot with a small corner. Navy marks the rows for Lancaster and nothing else.

**`training-report-1280` / `training-report-1920`.** The three Training Report headshot components: the 40px monogram fallback, the 40px photo, and the 46px newswire badge. All square. The generic silhouette now shows shoulders rather than being cropped to a disc, which is the visible argument for the whole item.

**Colour law.** Green appears only on the top-bar Advance across all six screens. No orange anywhere (no saves on these views). Navy only on the active rail item and the user's own rows. Blue only on the elite end of the RT and attribute ramps, plus the radar's own fill. No reward gold. Choice controls (Varsity / Practice Squad, Conference / National) are neutral.

## Judgement calls

- **The radar's polygon fill is blue.** Blue is reserved for RT A / attribute 9+ and elite glyphs, so a blue chart body is arguably outside the law. It's the pre-existing shared component you asked me to reuse rather than rewrite, so I left its internals alone. Worth a separate look.
- **Prep v2 and Team Attributes use different words for three measures.** Prep › Scouting says "Press/Trap Defense", "Press Break" and "Fast Break Offense" where Team Attributes now says "P/T Defense", "P/T Offense" and "Fast Break". I used your words on the view you asked about and did not touch Prep's, since that wasn't in scope. Two surfaces, one data set, two vocabularies — probably worth reconciling in a later batch.
- **Win/loss colour on the schedule.** "W" is green and "L" is red. Green for positive data is within the law; red isn't named in it at all. Item 6 said change nothing else, so I didn't.

## Files

Server: `BackEnd/utils/office_digest.py`, `BackEnd/utils/team_measure_ranks.py`.

Views: `FrontEnd/static/js/shared/views/teamAttributesView.js` (rewritten), `rosterView.js`, `teamScheduleView.js`, `FrontEnd/static/franchise-command-center.js` (two label pairs).

CSS: `css/gob-views.css`, `css/gob-components.css`, `css/prep-v2-scouting.css`, `css/player-development-grid.css`, `css/training-newswire.css`, `training-report.css`, `player-detail.css`, `recruiting-spine.css`.

Docs: `_documentation_master/11_Design_Systems/UX_System.md` (§2 headshot rule, §15 twelve rows and `signed_scale`).

Tests: `tests/e2e/polish-team.spec.js` (new), `tests/e2e/t2-roster.spec.js`, `tests/e2e/team-schedule-columns.spec.js`, `tests/e2e/recruits-pool.spec.js`, `tests/test_team_attribute_measures.py`, `tests/test_team_measure_ranks.py`.

No file in the other agents' list was touched: `mode-select.*`, `gobShell.js`, `officeHome.js`, `gobTables.js`, `rankingsView.js`, `training.js`, `gobAdvance.js`.

STATUS: COMPLETE
