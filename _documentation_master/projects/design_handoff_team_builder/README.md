# Handoff: Team Builder (Geeked-Out Basketball)

## Overview

Team Builder lets a player put **their own program into the 128-team GOB league** by taking over the slot of an existing program. The league size never changes, no schedules break, and the new program inherits its predecessor's conference, region, standing and fifteen players.

This handoff covers a **restructured flow** and **seven screens**. The original feature was a five-step wizard (Slot → Identity → Colors → Roster → Review). It is now **three chapters of unequal weight, one hard gate, and a curtain**:

```
Program Select ──▶ Ⅰ CLAIM ──▶ Ⅱ IDENTITY ──▶ [BUILD MODE GATE] ──▶ Ⅲ ROSTER ──▶ REVIEW ──▶ ESTABLISH
   (browse)      (whose place)   (name/color)    (capped/uncapped)    (workspace)  (curtain)  (sequence)
```

**Why the shape changed.** The five steps were drawn the same size, which is the visual grammar of a form — a sequence of equal blanks. But the steps are not equal: Identity and Colors are one act, the roster is unbounded work that is never "complete," and build mode is the only irreversible decision in the product yet was buried as a toggle inside the densest screen. The three chapters each have their own spatial identity so the user always knows what kind of work they are doing.

Three principles hold across every screen:

1. **The league is always in the room.** Every decision is shown against what it displaces or joins.
2. **You inherit, then you author.** No blank field where an inherited value could sit. Every edit is visibly a *departure*.
3. **Show it wearing the uniform.** Preview artwork in real product furniture, not on swatch cards.

The register is **takeover, not setup**: institutional-sporting, no confetti, no "Congratulations!". The payoff for this audience is specificity — a plausible program appearing in a real standings table.

---

## About the Design Files

The files in `design/` are **design references created in HTML/CSS/React-via-Babel** — prototypes that show intended look and behavior. **They are not production code to copy directly.**

The task is to **recreate these designs inside `gob-simplified`'s existing environment**: vanilla JS + per-page CSS under `FrontEnd/static/`, following the patterns already used by `franchise-select-team.html`, `teamPicker.js` and `mode-select.js`. React and Babel are prototype-only scaffolding; drop them.

**Three exceptions — these are real production code and should be used as-is:**

| File | Status |
| --- | --- |
| `FrontEnd/static/js/shared/teamGeneratedArt.js` | Copied verbatim from `develop`. Every banner/jersey/mark in the prototype calls it. |
| `FrontEnd/static/js/shared/teamCourtGenerator.js` | Copied verbatim from `develop`. Every court render calls it. |
| `tb-banner-variants.jsx` | **New** draw functions written to `drawChevronBanner`'s exact contract. Port the four functions into `teamGeneratedArt.js`. |

An earlier revision of this prototype contained a hand-written banner and court generator. It disagreed with production in ~six ways and was **deleted**. Do not reintroduce independent art code — `tb-art.jsx` is a thin wrapper with no drawing logic in it.

## Fidelity

**High-fidelity.** Final colors, typography, spacing, copy and interaction states. Recreate pixel-accurately using GOB's existing CSS custom properties and Bebas Neue Pro / Inter stack. All measurements below are as-authored at zoom 1.

The `Prototype view` bar at the top of every screen (with Fit/100%/125%… buttons) is **scaffolding for review only — do not ship it.** See *Sticky offsets* under Interactions for why this matters more than it looks.

---

## Screens / Views

### 0. Program Select — browse mode (`Team Builder - Claim.html`, default state)

**Purpose:** choose one of 128 programs to coach as it stands, or enter Team Builder.

**Layout:** max-width 1420px, padding 22px 24px 24px.
- **Header:** h1 Bebas 46px/.96, letter-spacing .02em, `#fff`. Subhead 14px `--tx2`, margin-top 9px.
  - h1: *"Who are you coaching?"* Subhead: *"Take over one of the 128 programs below."*
- **Team Builder entry band** (`.tbe`): margin-top 16px, `linear-gradient(120deg, rgba(247,148,32,.11), rgba(247,148,32,.03) 46%, rgba(255,255,255,.02))`, 1px `rgba(247,148,32,.3)`, radius 14px, padding 16px 20px, flex with 24px gap.
  - Headline Bebas 28px `#fff`: *"Or put your own program in the league"*
  - Body 13px `--tx2`: *"Your school **takes an existing program's place** — its conference, its region, its schedule."*
  - Button (right, min-width 214px): **Open Team Builder**
- **Filter bar** (`.fbar`): sticky, `rgba(16,19,30,.97)` + blur(8px), 1px `--bdr`, radius 12px, padding 11px 14px, flex wrap, gap 10px.
  - Search input 214px × 34px, placeholder *"Search program, conference or state"*
  - Five selects, 28px tall, min-width 104px, labels 8.5px/.13em uppercase `--tx3`: Talent, Prestige, Size, Experience (options *"Any tier"* + five band labels), Geography (*"Anywhere"* + 56 values)
  - Right: match count — Bebas 19px number + 12px `--tx2` *"of 128 match"*; `Clear N` link in `--org` when filters are active
- **Conference sections** ×16: header row with Bebas 19px/.08em uppercase `#fff` *"Conference N"*, then 9.5px/.11em uppercase `rgba(255,255,255,.56)` *"Region X"*, then 10px `--tx3` geography list (`Idaho · Washington · Oregon · West Canada`), a 1px flex-filling rule, then `N of 8` count.
- **Card grid:** `repeat(8, minmax(0,1fr))`, gap 8px.

**Program card** (`.pg`): `--panel` bg, 1px `--bdr`, radius 11px, `box-shadow 0 10px 22px rgba(0,0,0,.28)`.
- **Art region:** `aspect-ratio: 400/141`, `object-fit: contain` — the real `_banner_card.webp` asset. **Contain, not cover:** these are logo lockups and cropping eats the wordmark. (The styleguide's "cropped, never letterboxed" rule is about photographic banners.)
  - Path: `/images/teams/<slug>/<slug>_banner_card.webp`, `onerror` → `/images/teams/general/general_banner_card.webp`
  - Slug from `nameToTeamSlug` in `common.js`. **One folder-casing exception: `ida` lives in `images/teams/IDA/` while the file stem stays lowercase.**
- **Body:** padding 7px 9px 8px. Name Bebas 15px, 2-line clamp. Then four tier rows, grid `31px 1fr`, gap 6px, line-height 1.3:

  | Label | Value color |
  | --- | --- |
  | TLNT | `--org` if band 1, else `--tx2` |
  | PRSTG | `--ylw` if band 1, else `--tx2` |
  | SIZE | always `--tx2` |
  | EXP | always `--tx2` |

  **Only Talent and Prestige get a top-tier accent.** Loaded and Blue Blood are *better*; Tallest is not better than Quickest and Most Experienced is not better than Youngest — they are trade-offs. Accenting all four would imply a ranking that does not exist.
- **Hover:** `translateY(-3px)`, border `rgba(247,148,32,.42)`, shadow `0 18px 34px rgba(0,0,0,.44)`, and a detail panel drops below (`rgba(22,26,36,.99)`, radius 9px) with Talent pts, Prestige score, Mascot, Size, Experience, Conference · Region, and last season's records.
- **Filtered out:** `opacity .34; filter: grayscale(.4); pointer-events: none`. **Dim, never remove** — the grid never reflows and never empties, so spatial memory survives and the user can see what they excluded. There is no empty state to design.
- **Selected:** border `--org`, `box-shadow 0 0 0 2px rgba(247,148,32,.5)`, plus a 22px `--org` circular ✓ at top-right.

**Selection bar** (`.abar`): fixed bottom, `rgba(11,13,20,.95)` + blur(10px), 1px top `--bdr`. Slides up via `transform: translateY(100%) → 0`, `.2s cubic-bezier(.2,.8,.2,1)`. **Never a modal** — comparison must stay possible while a selection is held.
- 152px art thumbnail (400/141, contain) · name Bebas 24px with mascot in `--tx3` · meta line 12.5px · four tier readouts (hidden below 1180px) · `Clear` ghost button · primary CTA.
- Browse mode CTA: **Enter Franchise**, `--grn` background.

### 1. Chapter Ⅰ · Claim — Team Builder mode (`Team Builder - Claim.html`, `builder` state)

**Purpose:** choose whose place your program takes.

**This is the same grid with a changed verb** — confirmed as the intended production shape. It is a separate screen server-side; render it from the same template/component with a mode flag.

Clicking **Open Team Builder** changes **five things at once**. A click that changes only a button label reads as a broken button, so entering a mode must be visible in more than one place:

1. **Mode banner appears** (`.mbar`) — sticky, `linear-gradient(180deg, rgba(247,148,32,.20), rgba(247,148,32,.10))`, 1px bottom `rgba(247,148,32,.42)`, blur(8px), padding 9px 24px. Animates in with `mbdrop .22s cubic-bezier(.2,.8,.2,1)` from `translateY(-100%)`.
   - `TEAM BUILDER` Bebas 17px/.13em uppercase `#ffc781`
   - `Step 1 of 3` badge, 9.5px/.13em uppercase `rgba(255,255,255,.78)`, 1px `rgba(255,255,255,.28)`, radius 4px
   - Body 12.5px `--tx2`: *"Choose whose place your program takes. **Nothing is committed yet.**"*
   - **Cancel** button at the right end
2. **h1 changes** to *"Whose place are you taking?"*, tinted `#ffd9a8`
3. **Subhead changes** to *"Your program replaces one of these. You inherit **its conference, its region and its schedule**."*
4. **The entry band disappears** — you are in the thing it offered
5. **The selection bar reframes:** headline becomes *"You are taking ⟨Name⟩'s place"* (name in `--org`), CTA becomes **Take This Place** in `--org` (not the green Enter Franchise)

**Cancel** restores all five and clears the selection.

**State must survive the switch** — scroll position, active filters, match count. A mode change that resets browsing punishes curiosity.

### 2. Chapter Ⅱ · Identity (`Team Builder - Found Studio.html`)

**Purpose:** name the program, color it, design its court, pick its jersey.

**This merges the old Identity and Colors steps.** They were never two acts — naming a program and choosing its colors is a single imaginative gesture, and every sports fan performs it that way.

**The organising principle is a preview with controls attached, not a form with a preview.** Grid `388px minmax(0,1fr)`, gap 12px, align-items start.

**Left rail** (`.rail`, `--panelD`, radius 14px) — four groups separated by 1px `--bdr2`:
- **Header:** *Identity* Bebas 19px + **Surprise me** ghost button (rolls name, mascot, abbreviation, palette, jersey preset, banner composition, both hardwood tones in one click — a *starting point*, not a skip, and the best demo of what the screen does)
- **Fields:** School name (max 26) full width; then Mascot (max 20) + Abbreviation (max 3, `[A-Z0-9]`, center-aligned, letter-spacing .16em) in a `1fr 108px` grid. Inputs 38px tall, Bebas 20px, `rgba(255,255,255,.05)`, 1px `--bdr`, radius 8px; focus border `rgba(247,148,32,.6)`.
  - Abbreviation auto-derives from the school name via `TGA.initialsFromName` **until the user touches it**, then stops.
  - Uniqueness line below, 10px mono: *"three characters, exactly"* / *"checking the league…"* / green *"✓ CVU is free"* / red *"✕ CVU is already in the league"*
- **Palette:** 8 preset pairs in a `repeat(4,1fr)` grid, 34px tall split swatches. Then two color rows, each: 12 preset 22px swatches + a **Custom** swatch — same 22px square, dashed 1px border, inset well showing the live color, white ring when active. One shape per row.
  - Presets are **archetypal collegiate pairings with invented names**, not real school colors: navy/gold, forest/gold, crimson/cream, purple/gold, teal/orange, rust/navy, blue/pale-blue, charcoal/amber.
- **Court:** six controls. Hardwood inside the arcs (light/medium/dark); Hardwood midcourt (light/medium/dark/**custom**); then four token pickers — Out of bounds, Free-throw lane, Half-circle arcs, and their Custom chips.
- **Footer:** `← Back to Claim` ghost button.

**Right column** — the content:
- **Top row,** grid `minmax(0,1fr) 246px`, align-items **stretch** (both columns share a height):
  - **Banner frame:** the generator at width 780. Below it a **style switch** strip: `Style · Keel · Baseline · Plate · Sash`, buttons Bebas 13.5px, radius 7px; active is `rgba(247,148,32,.16)` / `#ffc781` / `rgba(247,148,32,.5)`.
  - **Jersey panel:** the real jersey SVG centered, with `Solid` / `Solid with trim` buttons **below** it, split evenly. Both control strips sit on the same baseline as the banner's.
- **Court:** the real 3333×2083 render, downscaled to 980px wide, max-width 880px centered, `#0e1118` well. No header row. Legend beneath: six swatch chips naming each colored surface.

**Every control that previews something visual sits with its preview.** The rail holds only what has no picture of its own — which is why Court is the one exception (six color fields will not fit under a court image).

### 3. Build mode gate (`Team Builder - Build Mode Gate.html`)

**Purpose:** capped or uncapped. The only irreversible decision in the flow.

**This is a full screen, not a control.** The brief had it as a persistent toggle above the roster editor, but a control that lives among 180 other controls is read as a preference however large it is drawn — persistence is not prominence. It costs the user ten seconds and it is the only ten seconds that cannot be undone by editing.

**Layout:** centered, max-width ~1120px.
- Context line at top: `Cascade Valley · CVU · replacing Rainier Central · Conference 14`, with 4px dot separators
- **h1** Bebas 62px/.94, centered, margin-top 30px: *"This Choice Is Permanent"* — the headline carries the one fact the screen exists to convey, so no lede paragraph is needed
- **Two cards**, nothing preselected, equal weight:

| | Capped | Uncapped |
| --- | --- | --- |
| Eyebrow | `CAPPED` Bebas 15px/.18em `--tx3` | `UNCAPPED` |
| Consequence | **Eligible for online play** Bebas 34px `--grn` | **Not eligible for online play** Bebas 34px `--red` |
| Sub line 1 | *Multiplayer or Single-Player* | *Single Player only* |
| Sub line 2 | *Eligible for leaderboards, multiplayer leagues, and head-to-head games.* | *Total anarchy.* |
| Lead | *Three budgets, inherited from Rainier Central.* | *No budgets at all.* |
| Attributes | Every player keeps his own total. Points never move between players. | Any value from 5 to 99. No total to land on. |
| Height | 1,164″ across the fifteen. Under the cap is allowed. | Any height from 5′6″ to 7′0″. No team cap. |
| Year | 38 exactly. Not more, not less. | Any mix of years. No team total. |

  - **The consequence is the largest text on each card, above any explanation of budgets** — stated in the plainest available language.
  - Card footer: `Click to choose` 11.5px `--tx3`, warming to `--org` **on hover only**. At rest it would be the loudest thing on each card and would beat the eligibility line; it is a hint, not a CTA — the whole card is the button.
- **No bottom primary CTA.** Choosing a mode card lights the **state band** Continue (orange). When nothing is chosen, the band shows a disabled Continue with adjacent copy *"Nothing is chosen yet."* When a mode is chosen, the band reason updates to the eligibility sentence and Continue enables. Never a live-looking dead control.
- `← Back to Identity` (content-area secondary only)

**Dynamic vs static values.** Height budget, Year budget, replaced program, program name, abbreviation and conference come from the chosen slot — all 128 differ. The attribute range 5–99, the height range 5′6″–7′0″, fifteen players and FR/SO/JR/SR are product constants and are correctly hardcoded.

### 4. Chapter Ⅲ · Roster (`Team Builder - Roster Screen.html`)

**Purpose:** decide which of the fifteen inherited players you want to be different.

**This is the hardest screen and the most important reframe. The roster is not a step.**

The fact the original flow hid: **the roster is already a real, legal, playable team before the user touches it.** Fifteen players with names, portraits, attributes and ratings, inherited from the program being replaced, and in capped mode already satisfying all three budgets by definition. The user's job is not to fill in 180 fields.

Framing it as a wizard step actively destroys that — a step says "complete this to continue," so 180 controls read as 180 obligations and the screen becomes data entry by implication. **The same screen framed as a workspace becomes management.** So: **no `Next`.** It has a readiness state and a primary action that is live from the moment the user arrives.

**Layout, top to bottom:**

**a. State strip** (`.statebar`) — `--panel`, 1px `--bdr`, radius 12px, `box-shadow 0 14px 34px rgba(0,0,0,.4)`, flex-wrap.
- Five info cells, each `flex: 1 1 auto; min-width: 0; overflow: hidden` so they share the row evenly and **truncate with ellipsis before anything else gives way**. Label 9px/.13em uppercase `--tx3`; value Bebas 19px `#fff`; sub-line 10.5px `--tx2`.

| Cell | Value | Sub |
| --- | --- | --- |
| Chapter | `Ⅲ · Roster` | Claim · Identity · **Roster** |
| Replacing | Rainier Central | Conference 14 · Region G |
| Program | Cascade Valley | CVU · Timberwolves |
| Build mode | ● Capped | eligible for online play |
| Roster | ● Ready / Not legal | *n* of 15 changed |

- **Action cell**, `flex: 0 0 auto`, pinned right: adjacent **reason** + primary band button. When legal: reason *"Editable until you establish the program"* and the action enabled. When illegal: action **disabled** and the reason is the legality verdict (same substance as the page verdict — unplaced points / year / height), not a silent dead control.
- **Disabled button state must read as present-but-unavailable, not absent:** reduced opacity, `cursor: not-allowed`. Never a primary that looks live and isn't.
- **Roster band CTA:** **Continue to Review** (orange). It navigates only — Apply lives on Review. Naming the destination matters: Roster is the last authoring step, so a bare Continue could be read as commit.

**b. Budget band** (`.budgetbar`) — `--panelL`, radius 12px, padding 14px 18px, flex-wrap, gap 16px 22px.
- **h1** Bebas 27px: *"Edit Your Roster"*
- **Two meters**, `flex: 1 1 240px; max-width: 400px`: Height — team (`used / 1164″`) and Year — team (`used / 38`). Track 100% wide; fill color **red if over, green if exact, neutral `rgba(255,255,255,.42)` if under.**
  - **Under-cap is neutral, not amber.** Red is the only color that means *resolve this*; amber is reserved for *departed from inherited*. An under-cap height budget is legal and needs no action, so coloring it amber invents a problem.
- **Third cell — the verdict** (`.verdict`), sized and styled like a meter, immediately right of the Year meter:
  - Legal: green tint, `Legal` Bebas 17px `--grn`, *"All three budgets satisfied."*
  - Illegal: red tint, `Not legal` + the specific reason + a **Take me there** jump that selects the offending player
- In **uncapped**, the meters become **reference readouts** rather than vanishing — `1164 / 1164 inherited · unchanged — no cap`. "You inherit, then you author" survives the loss of budgets. The verdict slot instead carries **Not eligible · written permanently when the program is established**.

**c. The board** — all fifteen players visible at once, `--panelD` card.
- Header: `Roster` Bebas 19px + a `Signature / Full grid` segmented control
- **Signature view:** one row per player, grid `28px 150px 34px 40px 34px 1fr 30px`. Number, name, position badge (color-coded, Bebas 10px on `--pos` background), Year, Height, then a **12-bar sparkline** of attributes (SC→FT) with bars colored by value band (red ≤40, yellow 41–60, green 61–80, blue 81+), then `RT`.
  - **`RT` is the position rating at the listed slot. There is no overall rating anywhere in the product** — do not add one, and do not let the column read as one.
  - Amber marker on any row changed from inherited. Footer legend carries only `Changed from inherited`; the color band scale is ordinal and self-evident across fifteen adjacent rows.
- **Full grid view:** a table of all 12 attributes × 15 players. **Rows are clickable and jump straight into editing that player** — a caption explaining what a click does is worse than the click doing something.

**d. Inspector** (`.insp`) — opens beside the board, so the team stays in view while a player is edited. The management feeling comes from seeing the roster *as a roster* — who's tall, who can shoot, where the holes are.
- **Header:** portrait (72px, tone-tinted, monogram fallback) with caption *"auto-assigned · click to override"*; then Jersey #, First name, Last name fields; then `Randomize` / `Revert to inherited`.
  - **First and last are views onto a single canonical `name` field**, recombined on every keystroke — the board row, grid and monogram need no data-model change.
  - **There is no Slot field.** Position is fixed at generation and was read-only; it is already shown by the board badge, the RT column and the five position cards. A read-only text restatement of a value shown three other ways is noise.
- **Two columns.** Left: **Year** (FR/SO/JR/SR segmented, inherited value ticked) with a compact team tally `TEAM · 38 / 38 · exact`; **Height** stepper (66–84, displayed 5′6″–7′0″) with the team bar and tally, plus *"Weight will be re-calibrated at franchise initialization based on the player's height and attributes."*
  - **A stepper, not a slider.** Height has nineteen legal values displayed in feet and inches and a slider is poor at hitting an exact one. More importantly, under a pure-renderer architecture a slider's continuous feedback is largely a lie — position ratings do not move until release. A discrete control where each click is a committed change matches what the system actually does.
  - Budget feedback at the point of edit is a **compact readout, not a sentence**. §3.3 requires budget state to be visible where the user is editing; it does not require a paragraph.
- Right: **Attribute points — this player** pool (`used / budget`, green when 0 remaining, red when over), then 12 sliders grouped by category with **tick marks at inherited values**, then five position-rating cards.
- **Full-width legend band** across the bottom of both columns: `repeat(4, minmax(0,1fr))`, 3 rows — all 12 codes with names, colored to their category.

**e. Portrait picker** — three filter axes (**Tone**, **Frame**, **Build**) **reorder** the 450-image pool and dim non-matches rather than filtering them. Best matches first, grid never reflows, never empties, no empty state to design. Same rule as the program grid, used a second time.

**Tone (skin):** unlabelled swatches in a light-to-dark ramp — **no race vocabulary in the interface** (no labels, tooltips, `title`, `alt`, `aria-label` taxonomy, CSS class names, or `data-*` values carrying classifier skin keys). Accessible names are positional/tonal only (e.g. *"Skin tone 1 of 5, lightest"*). Chip fills are **measured** mean colours from the pool; selection is a **ring**, not a fill change; chips 1 and 5 carry a stronger border so they read on `#0e1118`. Classifier keys stay unchanged underneath — a chip may map to multiple keys (display-layer merge). Match counts aggregate across every key a selected chip maps to. **Do not normalise chroma** to smooth the ramp — ends are duller than the mid by measurement. Full method, Lab table, ΔE00 basis and chip→key map: `team-builder-v2-plan.md` §6.5b.

**Frame / Definition:** labelled sets (orthogonal classifier axes — skeleton vs muscle/fat). Help: *"Frame is how big and broad he's built. Definition is how muscular or soft that frame looks."* Frame value **Doughy** is shown as **Heavy** (display-layer only; classifier key unchanged) so the size ramp reads Slight → Lean → Normal → Broad → Heavy. Match-count: no filters → *N portraits*; filters active → *N matches, shown first. The rest stay selectable.* (No-filter order is catalog order — do not claim player-fit.)

### 5. Review (`Team Builder - Review.html`)

**Purpose:** nothing. This is the only screen in the flow with no work on it.

**It is a curtain, not a checkpoint.** In the original flow it sat as step five with Back/Next, which framed it as something to verify and clear — and that is why it read as a state printout. Its layout was telling the truth about its role. Bigger artwork does not fix a checkpoint; changing its role does.

**The core move is context, not size.** A banner shown larger is still a banner on a page. A banner shown in a standings row, among real programs, is a thing that already exists in a league that was running before the user arrived.

**Layout:** max-width 1400px.
- Top line: `Review` eyebrow 10px/.2em `--org` + *"Everything below is still editable until you establish the program."*
- **Hero banner**, max-width 820px centered, radius 16px, `box-shadow 0 22px 54px rgba(0,0,0,.5)`
- **Roster** — all fifteen in a `repeat(5,1fr)` grid, 1px gaps: portrait, number, name, position badge, Year, height, WO badge, RT
- **Two-column grid**, `minmax(0,1.32fr) minmax(0,1fr)`, gap 14px, **align-items: stretch**
  - **Left:** eligibility block, then the Conference 14 standings. `.col:first-child > .card { flex: 1 }` and the table `flex: 1` so it absorbs the slack and both columns end on the same line — the rows breathe from 21px to 25px, which makes the table read more like a real standings page.
    - **Eligibility block:** green tint (`rgba(52,236,39,.10)` → `.03`, 1px `rgba(52,236,39,.34)`), radius 14px, padding 20px 22px. Headline Bebas 33px `--grn`: **Eligible for online play**. Body: *"Built **capped**. **This cannot be changed later.**"*
    - **Standings:** 8 rows, columns Program / Conf / Overall / Preseason. The user's row is tinted in their own primary via `linear-gradient(125deg, var(--me) 0, transparent 78%)` with a 3px inset left bar, name in Bebas 17px.
  - **Right:** Team Measures (Height budget, Year budget, Attribute points, Changed from inherited, **Average Height**, Year shape) and Program Details (Conference, Region, Replacing, National Programs 128)
- **Home Court** — the real court render, 700px wide, max-width 700px centered
- **No bottom primary CTA.** The commit lives in the **state band** only (`Establish ⟨Program⟩`). Page gravity: full-width *"This Program Is Permanent"* plus a one-line consequence; the band performs the click. `← Back to the Roster` is a content-area secondary control, not a footbar.
- **Action-bar rule (all chapter screens):** the primary action always lives in the top state band. Advance (Continue / Continue to Review) is orange. Irreversible **Establish** is also orange fill — distinguished by **heavier type and more horizontal padding**, not by green (green means valid/legal throughout the product) and not by red (creates, doesn't destroy). The screen headline carries permanence; the chip's job is to be unmistakably primary. Establish curtain / Enter Franchise stays off-band. When the band action is unavailable it is visibly disabled **and** the adjacent reason states why. Never render a primary that looks live and isn't. Band height is measured into `--tb-statebar-h` / `--chrome-h` — never hardcode content insets from assumed chrome size.

**There is no schedule card.** Confirmed: **the schedule does not exist at this point in the flow.** An earlier revision showed six dated fixtures; it was removed rather than showing data that isn't real. The standings already put the seven programs the user will face on screen.

**Standings and conference membership are derived from the league, never hardcoded** — sorted by conference wins then overall, with the user's program standing in the slot of the program it replaced. A hardcoded list desynced from the real league once already.

### 6. Establish sequence (`Team Builder - Establish.html`)

**Purpose:** the wait after Apply. Replaces the shipped `team-select-loading` overlay and its *"Building Your Franchise, Coach"* message.

**Designed as three beats rather than a spinner**, because this is the only moment in the flow where the user has nothing to do and everything is already decided.

Full-bleed, centered, `min-height: calc(100vh - var(--chrome-h, 0px))`, radial vignette at 50% 38%. Stage max-width 940px.

1. **0–0.7s — the banner arrives.** `opacity 0 → 1`, `translateY(10px) scale(.985) → none`, `.7s` opacity / `cubic-bezier(.2,.8,.2,1)` transform. Max-width 600px.
   - Implementation note: the pre-roll must be its **own class state**. A phase initialised to −1 and clamped with `Math.max(0, phase)` renders the released state on first paint and the transition never fires.
2. **0.7–2.1s — the charter writes itself.** Two columns under the banner, gap 22px. Left: six rows, 210ms apart, each `opacity/translateY(6px)` over `.42s`. Grid `126px 1fr`. Label 9.5px/.15em uppercase `rgba(255,255,255,.7)`; value Bebas 17px `#fff`; note 10.5px `--tx2` on its own line.

   | Label | Value | Note |
   | --- | --- | --- |
   | Program registered | Cascade Valley | CVU |
   | Conference seat | Conference 14 | Region G |
   | Taking the place of | Rainier Central | |
   | Roster assigned | 15 players | 12 scholarship · 3 walk-ons |
   | Court and uniforms | Medium hardwood | Solid with trim |
   | Build mode | Capped | eligible for online play *(green)* |

3. **2.1–3.0s — the takeover, literally.** Right column: the Conference 14 standings appear, the replaced program's row struck through in red (`rgba(255,109,109,.09)` bg, line-through in `rgba(255,109,109,.7)`), then after 700ms it becomes the user's program in green (`rgba(52,236,39,.10)`, name promoted to Bebas 16px `#fff`). `.45s` background and color transitions.

4. **Close.** *"Cascade Valley Timberwolves"* Bebas 27px + *"Established 2026 · Conference 14"* 11.5px mono uppercase, and **Enter Franchise** (`--grn`).

**The progress rule reports real elapsed time against Apply, not a scripted curve** — and its label changes from *"Writing the charter"* to *"Waiting on the league office"* if the server is slower than the animation. **The close is gated on both the last beat and the server finishing**, so a fast Apply still gets the beat and a slow one does not get a premature button. A fake bar that completes before the server does is the specific thing that makes loading screens feel dishonest.

**`SERVER_MS` at the top of `tb-establish-app.jsx` is a placeholder (2600) and needs the real Apply timing.**

**On this screen the `--tx3`-weight text *is* the payoff** — the charter labels, the W–L records, the closing line. All are raised to `rgba(255,255,255,.66–.74)`. Do not drop them back to `--tx3`.

---

## Interactions & Behavior

### Progress and commitment

**There is no progress bar and no step counter.** A step counter promises a known amount of work remaining, but the roster's work is unbounded by design — "4 of 5" is a lie in both directions, and the user who spends twenty minutes gets no acknowledgment while the user who spends none gets the same 80%. Worse, a progress bar frames the flow as *a task being completed*, which is the framing the redesign is trying to escape.

**The state strip replaces it.** It reports what *exists* rather than what remains, it becomes the navigation once the first pass is done, and it is the only chrome shared across chapters. The primary action is live from the moment the roster is reachable: **the user can always see that they are allowed to finish.**

- **Nothing is skippable, because nothing is empty.** Slot must be chosen (it is the premise). Mode must be chosen. Identity has *Surprise Me*. The roster is inherited and already legal. **The minimum viable path is four decisions**, and the flow is infinitely deepenable.
- **Linear on the way in, navigable after.** Each chapter needs the one before it. From the roster onward the strip cells are links; edits preserve; no re-confirmation. Build mode is the one deliberate speed bump on the way back.
- **One commitment, at the end, named as an act:** *Establish ⟨Program⟩*.

### Sticky offsets — the one implementation trap

Three separate bugs in this prototype had the same cause: **an offset that crosses a scaled/unscaled or measured/unmeasured boundary was authored as a number.**

**Rule: any offset that depends on chrome height must be derived from a measurement, never hardcoded.**

- Filter bar: `top: var(--fbar-top)`, computed from the review bar's measured height ÷ current scale
- Mode banner: `top: var(--mbar-top)`, set on `:root` (not on the page wrapper — the banner renders outside it)
- Establish curtain: `min-height: calc(100vh - var(--chrome-h, 0px))`
- Action-bar clearance: measured from the bar itself via `ResizeObserver`

In production all of these resolve to `0` because the prototype review bar does not exist. **Hardcoding them will not fail visibly during development and will be wrong in production.**

(Also tried and rejected: moving the zoom to `body` so everything scales together. Chrome resolves `position: fixed` against the *scaled* containing block, which throws fixed bars off-screen.)

### Server checks

**Abbreviation uniqueness is the only debounced server check in the flow** (480ms). States: too short / checking / free / taken. **Colors have no server validation** — no reserved colors, no distinctness check. The client is the whole story for color.

### Budget arithmetic

**Running totals over server-supplied values are allowed and already shipped.** Height and Year budgets are sums over values the client already holds; showing "126 of 129 inches used" while a control moves is addition over known data, not a reimplemented game rule. If client and server disagree, the server's number overwrites.

**Position ratings are different** — those are genuine formulas and arrive from the server on release. The UI shows a `recomputing…` state while pending and never guesses.

### Court field storage

**The five court fields store tokens (`oob: "Primary"`), not resolved hex.** If they stored hex, changing the palette after coloring the court would leave a court in the old colors with no indication why. Resolve at render; resolve once more at Apply if the server wants final hex. `Custom` is the one case that stores a literal hex, which is why each field carries its own custom value alongside its token.

### Animation inventory

| Element | Property | Duration / easing |
| --- | --- | --- |
| Mode banner | `translateY(-100%) → 0` | `.22s cubic-bezier(.2,.8,.2,1)` |
| Selection bar | `translateY(100%) → 0` | `.2s cubic-bezier(.2,.8,.2,1)` |
| Card hover | `translateY(-3px)` + shadow | `.14s` |
| Filtered-out card | `opacity`, `filter` | `.18s` |
| Establish banner | `opacity` / `transform` | `.7s` / `cubic-bezier(.2,.8,.2,1)` |
| Charter row | `opacity` / `translateY(6px)` | `.42s`, staggered 210ms |
| Standings row swap | `background`, `color` | `.45s` |
| Court re-render | debounce | 140ms (each render builds two full-size grain canvases) |

`@media (prefers-reduced-motion: reduce)` disables the establish transitions.

---

## State Management

**Claim**
`builder: boolean` · `q: string` · `f: {talent, prestige, size, experience: 0–5, geo: string}` · `sel: program | null`
Derived: `matches` map over all 128, `count`, `active` filter count. Selection clears if it falls outside the active filter.

**Identity**
`name` · `mascot` · `abbr` · `abbrTouched` · `primary` · `secondary` · `jerseyPreset: 1|2` · `bannerVariant: 'B'|'C'|'D'|'E'` · `inside`/`outside: 'light'|'medium'|'dark'|'custom'` · four court tokens + their custom hexes · `uniq: {state, code}`

**Gate**
`mode: 'capped' | 'uncapped' | null`

**Roster**
`players[15]` (each with `attrs{12}`, `ht`, `cls`, `name`, `n`, `pos`, `tone`, `build`, `wo`, plus `base*` inherited values) · `sel: index` · `view: 'sig' | 'grid'` · `pending` per player for server ratings
Derived: `pools[playerId]`, `heightUsed`, `classUsed`, `legal`, `reason`, `jump`

**Establish**
`phase: -1…3` · `lines: 0–6` · `swapped` · `ready` (server) · `pct`

---

## Design Tokens

```css
--bg:      #0b0d14   /* page */
--panel:   rgba(22,26,36,0.97)
--panelL:  rgba(16,19,30,0.98)
--panelD:  rgba(13,16,24,0.97)
--bdr:     rgba(255,255,255,0.10)
--bdr2:    rgba(255,255,255,0.06)
--tx:      rgba(255,255,255,0.88)
--tx2:     rgba(255,255,255,0.56)
--tx3:     rgba(255,255,255,0.36)   /* chrome only — never body text or data */
--org:     #F79420   /* primary action, "changed from inherited" */
--grn:     #34EC27   /* legal, eligible, gating actions */
--blu:     #4A90D9   /* attribute band 81+ */
--red:     #ff6d6d   /* over cap, illegal, not eligible */
--ylw:     #FFD700   /* Blue Blood tier, attribute band 41–60 */
```

**Typography** — display `'Bebas Neue Pro', 'Bebas Neue', sans-serif`; body `'Inter', system-ui, sans-serif`; mono `ui-monospace, SFMono-Regular, Menlo, monospace`. The court generator additionally uses `Oswald` 300 for mascot text.

**Type scale:** h1 62px (gate) / 46px (Claim) / 27px (roster band); card titles 19px; values 15–19px; body 12.5–15px; labels 8.5–10px at .13–.15em uppercase.

**Spacing:** 1 / 2 / 4 / 6 / 8 / 10 / 12 / 14 / 18 / 22 / 26 px. **Radius:** 4 / 5 / 6 / 7 / 8 / 9 / 10 / 11 / 12 / 14 / 16 px.

**Shadows:** `0 10px 22px rgba(0,0,0,.28)` cards · `0 14px 34px rgba(0,0,0,.4)` state strip · `0 18px 34px rgba(0,0,0,.44)` card hover · `0 22px 54px rgba(0,0,0,.5)` hero · `0 26px 60px rgba(0,0,0,.6)` establish banner.

**Contrast floor: 4.5:1 for anything that is content.** `--tx3` (3.29:1) is for chrome only. This was caught five times across the review passes; treat it as a lint rule.

---

## Assets

| Asset | Source | Notes |
| --- | --- | --- |
| 128 × `<slug>_banner_card.webp` | `FrontEnd/static/images/teams/<slug>/` @develop | Real, unmodified. `contain` at 400/141. |
| `general_banner_card.webp` | `images/teams/general/` | `onerror` fallback |
| Bebas Neue Pro (Bold/Regular/Book) | `fonts/` | OTF |
| Inter | Google Fonts | 400–700 |
| Oswald 300 | Google Fonts | required by the court generator |
| Court overlay PNGs | `images/teams/general/court-overlays/` | **Not copied.** Prototype uses `useOverlays: false` (the real preview path) and shows fallback rim strokes, exactly as the shipped wizard preview does. |
| Player portraits | 450-image pool | Not in prototype — monogram placeholders stand in |

---

## Production changes required

Two items in the real codebase, both in `js/shared/`. Neither blocks the prototype.

**1. Four banner draw functions + `banner_variant` — `teamGeneratedArt.js`**

The chevron composition that ships today runs its diagonal from the baseline up through the centre of the card, which is exactly where the wordmark sits. On a light secondary the strip cuts through the letterforms. **Decision: four compositions ship and the chevron is retired.**

| Key | Name | Description |
| --- | --- | --- |
| B | Keel | Same two-tone split and secondary strips, relocated to the right edge as a vertical keel with the initials in it |
| **C** | **Baseline** ← **default** | One full-width secondary rule along the bottom, soft top light, ghost initials. **Nothing sits over the wordmark at any palette or name length.** |
| D | Plate | Solid secondary plate carrying the initials, wordmark left-aligned on the field beside it. The only variant where the secondary carries type. |
| E | Sash | Diagonal kept but dropped clear of both lines of type, so it reads as a raked foot rather than a stripe across the name |

All four are in `design/tb-banner-variants.jsx`, written to `drawChevronBanner(ctx, w, h, opts)`'s exact contract — 400×141 card space, shrink-to-fit wordmark 50→20px, WCAG best-of-two ink — so they port over as-is. Needed:
- the four draw functions beside (or replacing) `drawChevronBanner`
- a stored `banner_variant` on the team, defaulting to `baseline`
- `bannerCardDataUrl` / `bannerPrimaryDataUrl` dispatching on it

**Two invariants worth carrying over, both found by building these:**
- **Shrink-to-fit must measure against each composition's own field width.** Plate's is 264 card units, not the shared 300 — measuring against the constant clipped long names instead of shrinking them.
- **The mascot's opacity and contrast must be computed against the surface actually beneath it**, not the primary by assumption. Sash reported 4.55:1 for pixels that were actually ~2:1 while its band sat behind the glyphs.

**2. `insideWoodColor` — `teamCourtGenerator.js`**

`resolveWoodColors` only honours `outsideWoodColor`; the inside-the-arcs tone comes from the `{inside}_{outside}` style key alone, so a custom color inside the 3PT lobes is not renderable. The studio therefore offers light/medium/dark inside but light/medium/dark/**custom** for midcourt — an asymmetry the design would rather not have.

**Withdrawn:** a second line parameter (`accentLineColor`). The Markings control was removed from the design, so `lineColor` stays at the generator's own `COLORS.line` (`#6e675f`) for every custom program. Recorded because the underlying problem is real: `lineColor` paints *every* marking, so had it stayed user-editable a user could erase the 3-point line against the wood.

---

## Open questions

1. **Apply timing** — `SERVER_MS` in the establish sequence is a 2600ms placeholder. The design works at either extreme but the real number should replace it.
2. **Conference membership** — the prototype's `tb-league-data.js` assigns conferences from each program's own place name onto the real `CONFERENCE_GEOGRAPHY`. Production must use `team.conference` from `/teams`.
3. **Display names** — the prototype title-cases them from slugs with an exceptions map (`Archbishop McClellan`, `Couer d'Alene`, `Queen's Guard`, `Mt. Simmons`…). `nameToTeamSlug` is lossy for internal capitals, periods and apostrophes, so **names must come from `/teams` and never be derived from slugs.**
4. **Draft persistence** — an unfinished program currently evaporates. Someone who leaves at the roster has already named a school and picked its colors; that is the most valuable half-built thing in the product. Resumable drafts (a *"Cascade Valley · unfinished · continue"* card on Program Select) need server support and were scoped out. Without it, the abandonment answer degrades to warning-on-exit.
5. **Year vs potential** — the copy guard *"A younger roster has more seasons ahead, not better players"* was removed from both the roster and Review during the copy passes. The brief named this a domain risk: a player reading Year as potential rather than experience. It is now unstated anywhere in the flow. Consider covering it once, on the gate, where budgets are explained.

---

## Screenshots

`screenshots/` holds reference captures of all seven screens, with a README noting which states are only visible live (Claim's Team Builder mode, the illegal roster state, and the establish sequence in motion).

## Files

Everything is in `design/`. Open the HTML files directly in a browser — no build step.

| Screen | HTML | CSS | JS |
| --- | --- | --- | --- |
| Program Select + Claim | `Team Builder - Claim.html` | `tb-claim.css` | `tb-claim-app.jsx`, `tb-league-data.js` |
| Identity studio | `Team Builder - Found Studio.html` | `tb-studio.css`, `tb-art.css` | `tb-studio-app.jsx`, `tb-art.jsx`, `tb-banner-variants.jsx` |
| Build mode gate | `Team Builder - Build Mode Gate.html` | `tb-gate.css` | inline |
| Roster | `Team Builder - Roster Screen.html` | `tb-roster.css` | `tb-roster-app.jsx`, `tb-roster-data.js` |
| Review | `Team Builder - Review.html` | `tb-review.css` | `tb-review-app.jsx` |
| Establish | `Team Builder - Establish.html` | `tb-establish.css` | `tb-establish-app.jsx` |
| Banner options (reference) | `Team Builder - Banner Options.html` | `tb-banners.css` | `tb-banners-app.jsx`, `tb-banner-variants.jsx` |
| Structural rationale (reference) | `Team Builder - Structural Read.html` | inline | `doc-page.js` |

**Production code, use as-is:** `FrontEnd/static/js/shared/teamGeneratedArt.js`, `FrontEnd/static/js/shared/teamCourtGenerator.js`

`Team Builder - Banner Options.html` shows all five compositions side by side over five test palettes — switch to **Pale** to see why the chevron is being retired. `Team Builder - Structural Read.html` is the round-one argument for the flow restructure, if the reasoning behind the shape is useful.
