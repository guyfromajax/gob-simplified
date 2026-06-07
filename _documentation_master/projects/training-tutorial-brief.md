# Handoff: Tutorial Experience — Training sub-page

## Prompt for Claude Code

> Implement the **Training** tutorial lesson as a new page in the `gob-simplified`
> repo (`FrontEnd/static/`). It is the next **Mastering GOB** sub-page after Player
> Attributes and follows the **exact same chrome and conventions** as
> `player-attributes.html` (global `#auth-bar` + `#site-footer`, `.gob-shell`,
> `.gob-head` Back link, fixed `.gob-bottomnav`, `.gob-toast`). Build from
> `design_files/Training.html` — a working vanilla **HTML/CSS/JS prototype on the GOB
> styleguide**; adapt it into the repo using existing tokens, shared CSS, and assets
> (do **not** introduce a framework). **Name the file `tutorial-training.html`**, NOT
> `training.html` — that filename is already taken by the in-game Team Training UI.
> `body[data-gob-nav="training"]`. **On load it calls `GOB.markSeen('training')`** —
> that single call lights up the hub's progress meter, the explored ✓, and the
> next-up cue. Reuse `/css/gob-tutorial.css`, `/css/gob-buttons.css`, and
> `/js/shared/gobTutorialNav.js`. The page is **mostly static markup** (no data file
> like `gob-attributes.js` is needed) plus a tiny inline script for `markSeen` and the
> "coming soon" toast.

---

## ⚠️ Copy status — READ FIRST
Some copy on this page is **final/verbatim**; some is **placeholder Lorem awaiting
authoring**. Do not ship the placeholders as-is — wire the layout, leave a `TODO`.

| Block | Status |
|---|---|
| Hero subhead | **Final** |
| Player Drills → drill-to-attribute map (12 rows) | **Final** (mapping is canonical) |
| Breaks card | **Final** |
| Scrimmages card | **Final** |
| Coaching Style — the two intro paragraphs | **Final** |
| **Team Drills — the 6 Install descriptions** | **PLACEHOLDER (Lorem)** — real copy pending |
| **Team Drills — "Training Playbooks" paragraph** | **PLACEHOLDER (Lorem)** — pending |
| **Coaching Style — the 16 focus sentences** | **PLACEHOLDER (Lorem)** — pending |

---

## Overview
The Training lesson teaches how practice between games develops a roster. It reuses
the Player Attributes page template — same hero, same section rhythm, same "Next up"
handoff — but its centerpiece is **lever cards** (the weekly practice choices) rather
than an attribute reference grid, because that's the shape of this content.

Hero subhead (final): *"Practice is where your program develops into your vision."*

---

## Layout (top → bottom)

1. **Back** ghost link in `.gob-head`.
2. **Hero:** breadcrumb `Tutorials › Training › Training`; `<h1>TRAINING</h1>`
   (Bebas `clamp(48px,7vw,86px)`); the subhead above.
3. **Section: "Your Training Week"** — eyebrow only (orange tick + `YOUR TRAINING
   WEEK`), no H2/helper line. Then a single column of **lever cards** (`.levers`
   grid; all cards are `.lever--wide` / full-width and stack):

   **a. Player Drills & General** — accent orange `#f79420`.
   Intro line, then the **drill → attribute map** (`.dmap-grid`, 4 cols × 3 rows):
   each cell is a drill name + a mono **code badge filled with the attribute's
   *category* color**. This is canonical — keep exact:
   | Drill | Code | Category color |
   |---|---|---|
   | Inside Offense | SC | offense `#f79420` |
   | Outside Offense | SH | offense `#f79420` |
   | Inside Defense | ID | defense `#4a90d9` |
   | Outside Defense | OD | defense `#4a90d9` |
   | Passing | PS | technical `#7b5ea7` |
   | Ball Handling | BH | technical `#7b5ea7` |
   | Rebounding | RB | technical `#7b5ea7` |
   | Strength | ST | physical `#aeb8cc` |
   | Agility | AG | physical `#aeb8cc` |
   | Conditioning | ND | physical `#aeb8cc` |
   | Free Throws | FT | intangibles `#d4a017` |
   | Film Study | IQ | intangibles `#d4a017` |
   Below the map: **"See the 14 player attributes →"** cross-link → **live** to
   `player-attributes.html`.

   **b. Breaks** — accent slate `#aeb8cc`, moon icon. Single paragraph (final).
   Sits directly **above** Team Drills.

   **c. Team Drills** — accent blue `#4a90d9`.
   Intro line, then **install cards** (`.ins-grid`, 2 cols): six cards —
   **Offense Install, Defense Install, Fast Break Install, Fast Break Defense
   Install, Press/Trap Install, Press/Trap Break Install** — each a dot + name +
   one **(placeholder)** description, with a left accent + dot **color-coded by
   side**: offense-nature = orange `#f79420` (Offense, Fast Break, Press/Trap
   Break), defense-nature = blue `#4a90d9` (Defense, Fast Break Defense,
   Press/Trap). A **7th full-width card "Training Playbooks"** (`.ins-card--full`,
   gold `#d4a017`, faint gold tint) spans both columns beneath the six, with a
   **(placeholder)** 3-sentence paragraph. Then **"See team attributes →"**
   cross-link — **dead** this pass (toasts; → `team-attributes.html` once it ships).

   **d. Scrimmages** — accent purple `#7b5ea7`, full-width. Single paragraph (final).

   **e. Coaching Style** — accent gold `#d4a017`, `.lever--feature`.
   Two intro paragraphs (final, left-justified). Then the **16-focus overview**
   (`.focuses`): small caption **"16 Focuses · 4 Coaching Archetypes"** (middle `·`),
   then four **archetype groups** stacked (`.arch-group`, 3px colored left border +
   colored dot + Bebas name). Each group lists its **four focuses in a 2×2**
   (`.arch-focuses`), each focus = name (in the archetype color) over one
   **(placeholder)** sentence, left-aligned. Archetype colors are the **production
   values from `training.css`** — keep exact:
   | Archetype | Color | Focuses |
   |---|---|---|
   | Authoritarian | `#C0392B` | Discipline · Rebounding · Execution · Teamwork |
   | Systems Coach | `#D4A017` | Offense · Defense · Fast Breaks · Press / Trap |
   | Player Maximizer | `#3A8C4A` | Top 3 · Attributes 4–6 · Positional Focus · Custom |
   | Culture Builder | `#7B5EA7` | Inspire · Confidence · Community Engagement · Team Building |
   > Note: **Player Maximizer**'s four are a tier deeper than the others — in the game
   > they're chosen through the single "Choose Attributes" pick (its modal). Listed
   > flat here for the overview.

4. **Handoff** panel: "NEXT UP / Team Attributes" + orange **"Start lesson"**
   (**dead** — toasts) + ghost **"All topics"** → `Tutorial Home.html#topics`
   (repo: `tutorial.html#topics`).

---

## Page chrome (same decisions as Player Attributes)
- **Keep** the global `#auth-bar`; **drop** the in-shell logo/alpha badge to avoid a
  double logo (the prototype's in-shell `.gob-head` only carries the Back link here).
- **Keep** the in-shell `Back` ghost link, the fixed bottom nav (intra-tutorial), and
  the injected `#site-footer`. Give the content container `padding-bottom ≥ 62px` so
  the fixed nav never covers the footer or last row.

## Dead vs. live controls (this pass)
- **Live:** Back (smart back), bottom nav, the **"See the 14 player attributes →"**
  cross-link (→ `player-attributes.html`).
- **Dead (toast "coming soon", do not navigate):** the **"See team attributes →"**
  cross-link, and the handoff **"Start lesson"** (Team Attributes lesson not built).
  Use the same single-reused toast pattern as the hub.

## Fidelity
**High-fidelity.** Colors, type, spacing, and components are all specified in
`design_files/Training.html` (page CSS is inline in its `<style>` — port it to a
page stylesheet or scope it, your call) and pull from the GOB styleguide. Prefer the
repo's canonical `css/gob-buttons.css` for `.gob-btn`. Recreate pixel-faithfully.

## Files in this bundle
- `design_files/Training.html` — full page markup + page-specific CSS (inline) +
  the inline `markSeen('training')` / toast script.
- `design_files/assets/gob-tutorial.css` — shared design-system CSS (reference; prefer
  the repo's existing copy + `css/gob-buttons.css`).
- `design_files/assets/gob-nav.js` — shared behavior (smart back, bottom-nav render,
  `window.GOB` progress API). Reuse the repo's `gobTutorialNav.js`.

## Reference (repo files this design is built against)
- `_documentation_master/07_Design_Systems/Styleguide.md`
- `FrontEnd/static/training.html` + `training.css` — source of the archetype colors,
  the 16 focuses, and the 6 installs (the live Team Training UI).
- `FrontEnd/static/css/gob-buttons.css` (canonical `.gob-btn`)
- `player-attributes.html` (this page's sibling template)
