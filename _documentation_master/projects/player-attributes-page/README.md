# Handoff: Tutorial Experience — "Mastering GOB" Hub + Player Attributes

## Prompt for Claude Code

> Implement the **Mastering GOB tutorial hub** as the new `tutorial.html` in the
> `gob-simplified` repo (`FrontEnd/static/`). The design files in
> `design_files/` are a working **vanilla HTML/CSS/JS prototype built on the GOB
> styleguide** — adapt them into the repo using existing conventions, tokens, and
> assets (do **not** introduce a framework). All links that would lead to a
> per-topic sub-page (Player Attributes, Team Attributes, Game Plans, etc.) are
> **dead buttons for now** — those pages don't exist yet. Wire everything else
> (persistent nav, smart back, progress meter, dynamic "next up" cue, toasts).

---

## Overview
This redesigns the GOB tutorial system. The current `tutorial.html` is a dense,
text-only accordion-inside-tabs page. This replacement is a **visual hub** —
"Mastering GOB" — that frames tutorials as an **in-game resource a coach returns
to** (not first-time onboarding; the FTE already covers the absolute basics).
It organizes everything into four categories, spotlights **Player Attributes** as
the must-master fundamental, tracks per-topic progress, and dynamically points the
coach at the next lesson in line.

Each remaining topic will get its own sub-page over time. This handoff now covers
**two screens: the hub (`tutorial.html`) and the first sub-page, Player Attributes
(`player-attributes.html`).**

---

## Screen 2: Player Attributes (`player-attributes.html`)
The first tutorial sub-page and the template for the rest. Same chrome as the hub
(global `#auth-bar` + `#site-footer`, `.gob-shell`, `.gob-head` Back link, fixed
`.gob-bottomnav`, `.gob-toast`). `body[data-gob-nav="players"]`. Reuses
`/css/gob-tutorial.css`, `/css/gob-buttons.css`, `/js/shared/gobTutorialNav.js`,
plus a new `/js/shared/gobPlayerAttributes.js` (data + rendering). **On load it
calls `GOB.markSeen('player-attributes')`** — that single call lights up the hub's
progress meter, the explored ✓, and the next-up cue.

> Build from `design_files/Player Attributes.html` + `design_files/assets/gob-attributes.js`.
> **Do NOT carry over the dead `.court-*` / `.puck` / `.umbrella` / `.bracket` /
> `.filter-*` / `.scale-egs` CSS still in the prototype's `<style>` — an earlier
> court-diagram concept was dropped; those rules are unused.**

**Layout (top → bottom):**
1. **Back** ghost link in `.gob-head`.
2. **Hero:** breadcrumb `Tutorials › Players › Player Attributes`;
   `<h1>PLAYER ATTRIBUTES</h1>` (Bebas `clamp(48px,7vw,86px)`); subhead
   *"Every player has 14 attributes that determine his unique skill set."* (No
   eyebrow, no "Foundational" badge.)
3. **Attribute rows** (`#attr-reference`, JS-rendered) — five category groups, each
   a header (color dot + Bebas label + count) over a 2-col card grid:
   - **Offense:** SC, SH · **Defense:** ID, OD · **Technical:** PS, BH, RB ·
     **Physical:** ST, AG, ND · **Intangibles:** IQ, FT, Emotion, Momentum.
   - **Each card:** rounded-square code badge filled with the category color · the
     attribute name · a `◎ Matters most: <zone>` line in the category color · the
     **definition**. 3px category-colored left border.
   - **Emotion & Momentum** are full-width cards (`grid-column: 1/-1`) with an inline
     meter under the text: Emotion = the 😎/😊/😐/😕/😡 mood scale
     (Happiest→Disruptive); Momentum = a Cold↔Hot gauge, needle centered on "0".
     Emotion has **no prose definition** — the mood scale is its content.
4. **The Attribute Scale** ("How To Read A Rating"): one horizontal bar segmented
   **red 40% / yellow 20% / green 20% / light-blue 20%**; ticks show only **0**
   (left) and **100+** (right); four tier labels — **Below Average / Average /
   Solid / Elite** — each positioned to begin exactly where its color starts
   (flex widths 40/20/20/20, left-aligned) with its range sub-label.
5. **Handoff** panel: "NEXT UP / Training" + orange `Start lesson` (**dead** — toasts)
   + ghost `All topics` → `Tutorial Home.html#topics`.

**Category wayfinding colors** (tints only, NOT data colors): Offense `#f79420`,
Defense `#4a90d9`, Technical `#7b5ea7`, Physical `#aeb8cc`, Intangibles `#d4a017`.
The **Attribute Scale** uses the canonical product value scale
(`#ff6d6d / #ffd700 / #34ec27 / #4a90d9`) — keep those exact.

**Copy:** every attribute **definition is verbatim from the legacy `tutorial.html`**
(the old accordion page on `main`) — do not paraphrase. The `◎ Matters most: <zone>`
line is a new one-liner per attribute; exact strings live in the data file.

## Page chrome (decided)
Use the **global top `#auth-bar` + the design's fixed bottom nav**:
- **Keep** the standard global `#auth-bar` (logo, alpha badge, nav links) so the page matches every other product page.
- **Drop** the in-shell header's logo + alpha badge to avoid a double logo. *(The prototype still shows an in-shell logo as a stand-in for page chrome — ignore it; the auth-bar replaces it.)*
- **Keep** the in-shell `Back` ghost link — per the styleguide the back/return link is a low-weight text link left-justified above the primary content container, so it lives inside the shell, not in the auth-bar.
- **Keep** the fixed bottom nav — it's *intra-tutorial* navigation (Home/Players/Team/Strategy/Training), distinct from the product-level auth-bar.
- **Keep** the injected global `#site-footer`, but give the content container `padding-bottom ≥ 62px` (bottom-nav height) so the fixed nav never covers the footer or last row.

## About the Design Files
The files in `design_files/` are **design references** — a functional prototype
showing the intended look and behavior. They are written in the same vanilla
HTML/CSS/JS stack the repo already uses and deliberately reuse GOB styleguide
tokens and the canonical `.gob-btn` component, so they can be adapted directly
rather than re-derived. Recreate them in `FrontEnd/static/` following existing
repo patterns (shared CSS, `/images/` asset paths, `Bebas Neue`/`Inter` already
loaded globally, auth-bar/footer includes, sound hooks, etc.).

## Fidelity
**High-fidelity.** Final colors, typography, spacing, components, and interactions
are all specified and pulled from `Styleguide.md` + `franchise-command-center.css`.
Recreate pixel-faithfully, preferring the repo's existing canonical CSS where it
already exists (notably `css/gob-buttons.css`).

---

## IMPORTANT: Dead buttons (this pass)
Per product direction, every control that would navigate to a per-topic **sub-page**
is **inert** for now. Specifically these are dead / no-op:
- Each **topic tile** in the category grid (Player Attributes, Team Attributes,
  Recruiting, Game Plans, Playbooks, Scouting, Training)
- The hero **action button** ("Start lesson" — the dynamic next lesson)
- **"See All Reminders"** (reminders manager not built yet)

For dead buttons, the prototype shows a small toast ("Lesson coming soon" /
"In development"). In production you may either keep that toast OR make them truly
inert — but **do not navigate**. Leave the progress hook in place (see State) so
that when sub-pages ship, each one only needs to call `GOB.markSeen('<topic-id>')`
on load and the whole progress/next-up system lights up automatically.

Controls that **do** work this pass:
- **Back** link (smart back — returns to the page the coach came from)
- **Persistent bottom nav** Home/Players/Team/Strategy/Training (Home → top of hub;
  the others scroll to their category section on the hub via `#cat-<id>`)
- **Browse all topics** (scrolls to the topics section)
- **Reset** progress link
- Progress meter, dynamic next-up cue, toasts

---

## Information Architecture
Four categories (matching the bottom nav). Recruiting lives under **Team**.

| Category | Topics |
|---|---|
| **Players** | Player Attributes *(priority — "Master first")* |
| **Team** | Team Attributes · Recruiting |
| **Strategy** | Game Plans · Playbooks · Scouting |
| **Training** | Training |

Topic metadata (id · depth badge · exact sub-copy):

- `player-attributes` — Player Attributes — **Foundational**, **priority** —
  "The 14 attributes that determine the unique skill set of every player."
- `team-attributes` — Team Attributes — **Foundational** —
  "Your program's identity — compounding mindset traits vs. trained, decaying systems."
- `recruiting` — Recruiting — **Advanced** —
  "Manage your recruiting pipeline by mastering invites, visits, and commitments."
- `game-plans` — Game Plans — **Foundational** —
  "The foundation of your strategy."
- `playbooks` — Playbooks — **Advanced** —
  "Learn how to build playbooks that match your coaching style."
- `scouting` — Scouting — **Advanced** —
  "Learn how to study your upcoming opponents."
- `training` — Training — **Foundational** —
  "Player & team drills, playbook installs, scrimmages, and the coaching style that defines your team's focus."

> Note: Recruiting & Scouting content is still **TBD** (to be authored later) but
> they are presented as normal **Advanced** lessons in the UI, not flagged as TBD.

---

## Screens / Views

### Screen: Tutorial Home ("Mastering GOB")
Single scrolling page inside the brand **shell container**, with a fixed bottom nav.

**Page background** (styleguide "core brand background"): deep blue-black atmosphere.
```
background:
  radial-gradient(120% 80% at 50% -10%, rgba(39,64,142,0.55) 0%, rgba(20,31,74,0.25) 38%, transparent 70%),
  linear-gradient(180deg, #11183a 0%, #0c1024 46%, #0b0d14 100%);
background-attachment: fixed;
```

**Shell container** (`.gob-shell`) — mirrors `#franchise-container`:
- `width: min(1180px, calc(100vw - 28px))`, centered, `margin: 14px auto`
- `border-radius: 24px`; `border: 1px solid rgba(255,255,255,0.09)`
- background: `linear-gradient(160deg, rgba(255,255,255,0.028) 0%, rgba(255,255,255,0.014) 18%, transparent 40%), rgba(14,16,24,0.96)`
- `box-shadow: 0 24px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.07)`
- `::after` diagonal banding: `repeating-linear-gradient(132deg, transparent 0 102px, rgba(255,255,255,0.012) 102px 103px, transparent 103px 208px)`
- `padding-bottom` leaves room for the fixed bottom nav (`var(--nav-h)` = 62px + ~34px)

**Layout, top → bottom:**
1. **Header row** (`.gob-head`): GEEKED-OUT logo (`/images/geekedout_logo.png`, h30) +
   alpha badge (`/images/gob-alpha-badge.png`, h22) + flex spacer + **Back** ghost
   text link, right-aligned. (Styleguide back-link: low-weight ghost text, small
   left arrow `‹`, subdued white, brightens on hover.) Bottom hairline border.
2. **Hero** (`.hero.panel` — single horizontal band: avatar + main, vertically
   centered; stacks under 760px). This is the page's focal point and is built
   around the **dynamic next lesson** — there is no "Mastering GOB" wordmark
   (brand identity comes from the auth-bar logo). Contents:
   - **Coach Sammy avatar** (`/images/sammy_tutorial.png`, 92px, 3px orange ring) as the guide anchor.
   - **Kicker** (`#kicker-label`): orange tick + "NEXT UP" (uppercase, tracked).
   - **`<h1>` (`#hero-topic`)**: the dynamic next-lesson name, Bebas Neue
     `clamp(46px,6.4vw,80px)`, `line-height: .96`. Default "Player Attributes";
     advances as lessons are explored; reads "You're all caught up" when done.
   - **Guide line** (Inter 14.5px muted): *"Pick up right where you left off — or
     browse any topic, any time. Learn GOB on your terms." — Coach Sammy*.
   - **CTA row (single source of truth):** action button `#cta-next` (orange,
     `--lg`) reading **"Start lesson"** (→ the next lesson; becomes "Browse all
     topics" when caught up) + ghost **"Browse all topics"** (`#jump-cats`,
     scrolls to the topics section). No duplicate "next up" pill — the headline
     itself is the cue.
3. **Progress strip** (`.panel`, flex row): big Bebas % (40px) · label "Your Coaching
   Knowledge" + "N of 7 lessons explored" · orange progress bar · "Reset" link.
4. **Topics** section (the single organizing section — there is **no** separate
   "Start Here" / Core Loop section; the recommended path lives on the tiles).
   Eyebrow "ALL TOPICS", h2 "MASTER THE COMPLETE COACHING SYSTEM", right hint
   "The numbers mark the recommended order — but every lesson stands alone, so dip
   in anywhere." Then a 2-col grid of four **category panels** (`.cat.panel`),
   each: header (category icon chip + Bebas name — **no count**) and a list of
   **topic tiles**. Tiles are dead this pass.
5. **Smart Reminders** band (`.panel`, 3px orange left accent): eyebrow "SMART
   REMINDERS", h3 "WE'LL FIND YOU WHEN IT MATTERS", copy *"As your season unfolds,
   Coach Sammy will surface the next lesson when it becomes relevant. Already a pro?
   Mute any topic and it won't bug you again."*, and a ghost **"See All Reminders"**
   button (dead — toasts a placeholder).

**Fixed bottom nav** (`.gob-bottomnav`): 5 items (Home, Players, Team, Strategy,
Training), each an icon + Bebas label; active item label white on faint fill with
the **icon tinted orange**. `rgba(10,12,20,0.86)` + `backdrop-filter: blur(14px)`.

#### Component specs
**Topic tile** (`.tile`): flex row — **numbered order badge** (`.t-num`, 38px
circle, Bebas, neutral) · name (Inter 700, 15px) + badge · sub-copy (12.5px muted)
· trailing `→` (or green ✓ when explored). The number is the topic's position in
the recommended order (`ORDER.indexOf(id)+1`), so it reads 1–7 across the four
categories (e.g. Team shows 3 and 7 — intentional; it's a path step, not a
category index).
- **Priority** variant (`player-attributes`, order #1): orange-tinted bg
  `rgba(247,148,32,0.06)`, border `rgba(247,148,32,0.28)`, **orange number badge**
  (`background:#f79420; color:#15181f`), and a `★ Master first` orange tag instead
  of a depth badge.
- **Depth badge** (`.depth`): "Foundational" = orange
  (`color:#f79420; bg:rgba(247,148,32,.12); border:rgba(247,148,32,.3)`);
  "Advanced" = light blue (`#4a90d9` equivalents).
- **Explored state** (`.is-seen`): show a small **green** `#34ec27` ✓ (the styleguide
  permits green for positive semantic states), hide the `→`.

**Buttons** — use the repo's canonical `.gob-btn` (`css/gob-buttons.css`):
- Hero primary = `.gob-btn--action` (orange, non-gating) at `--lg` size.
- Ghosts = `.gob-btn--ghost`. No green buttons here (no gating action on this page).

---

## Interactions & Behavior
- **Smart back** (`[data-gob-back]`): on first arrival from a non-tutorial page,
  store `document.referrer` in `sessionStorage['gob_tut_origin']`. Back navigates to
  that origin; falls back to history, then to the hub. (Goal: return the coach to
  wherever they opened tutorials from, across multiple in-tutorial navigations.)
- **Persistent bottom nav**: active item derived from `body[data-gob-nav]`. Home =
  this hub; Players/Team/Strategy/Training scroll to `#cat-<id>` on the hub for now.
- **Progress meter**: % and bar reflect explored learnable lessons ÷ 7. Updates live
  on a `gob:progress` event.
- **Dynamic "Next up"**: the hero headline (`#hero-topic`), kicker (`#kicker-label`),
  and action button (`#cta-next`) all reflect the first **un-explored** lesson in
  recommended order:
  `['player-attributes','training','team-attributes','game-plans','playbooks','scouting','recruiting']`.
  As lessons get marked explored the headline advances; when all are explored it
  reads "You're all caught up" / "Nice work, coach" and the button falls back to
  "Browse all topics". (Dead navigation this pass — but the labels are live.)
- **Toasts** (styleguide spec): bottom-right, `rgba(28,33,43,0.97)`, 3px left accent
  (orange), Bebas title + Inter subline, slide-in from right, auto-dismiss ~3s,
  single toast reused (reset timer, never stack).
- **Hover/active**: tiles & steps lift/brighten subtly; buttons follow `.gob-btn`
  (-1px lift on hover, compress on press).
- **Reduced motion / responsive**: hero and grids collapse to 1-col under 920px;
  bottom nav stays fixed.

## State Management
Plain `localStorage` / `sessionStorage` (no framework):
- `localStorage['gob_tut_seen']` — JSON array of explored topic ids. API exposed on
  `window.GOB`: `seen()`, `isSeen(id)`, `markSeen(id)` (fires `gob:progress`),
  `unseenAll()`.
- `localStorage['gob_tut_muted']` — JSON array of muted topic ids (for the future
  reminder system): `isMuted(id)`, `mute(id)`.
- `sessionStorage['gob_tut_origin']` — smart-back origin URL.
- **Hook for sub-pages (future):** each topic page should call
  `GOB.markSeen('<topic-id>')` on load. That single call drives the hub's progress
  meter, the explored ✓, and the next-up cue — no other wiring needed.

## Design Tokens
From `Styleguide.md` (authoritative) — already encoded in `design_files/assets/gob-tutorial.css`:
- **Brand:** blue `#27408e` (anchor/atmosphere only — never a data/stat color),
  light blue `#4a90d9`, orange `#f79420` (non-gating action + key accent),
  yellow `#ffd700`, green `#34ec27` (**scarce** — gating actions & positive data only),
  red `#ff6d6d`.
- **Surfaces:** base `#0b0d14`; shell `rgba(14,16,24,0.96)` border `rgba(255,255,255,0.09)`;
  panels `linear-gradient(180deg, rgba(255,255,255,0.05), transparent 18%), linear-gradient(180deg, rgba(42,48,58,0.92), rgba(30,35,44,0.95))`, border `rgba(255,255,255,0.12)`, radius 14px.
- **Text:** `#f7f9ff`; muted `rgba(255,255,255,0.72)` / `0.5` / `0.34`.
- **Type:** `Bebas Neue` (display, tabs, headers, all buttons) + `Inter` (body).
- **Radii:** 10px buttons, 14px panels/tiles, 24px shell. **Nav height:** 62px.

## Assets (already in the repo — reuse, don't re-import)
- `/images/geekedout_logo.png`
- `/images/gob-alpha-badge.png`
- `/images/sammy_tutorial.png` (Coach Sammy)
- Category/topic/nav icons are inline SVG strings in `design_files/assets/gob-nav.js`
  (`GOB.icons`) — reuse or swap for the repo's icon set.

## Files in this bundle
- `design_files/Tutorial Home.html` — the hub markup + hub-specific CSS.
- `design_files/Player Attributes.html` — the Player Attributes sub-page markup + CSS
  (ignore the leftover dead `.court-*`/`.puck`/`.umbrella` rules, see above).
- `design_files/assets/gob-tutorial.css` — design-system CSS (shell, panels, buttons,
  nav, toast, depth badges). Prefer the repo's existing `css/gob-buttons.css` for the
  `.gob-btn` component and treat the copy here as reference.
- `design_files/assets/gob-nav.js` — shared behavior: smart back, bottom-nav render,
  icon library, progress API (`window.GOB`).
- `design_files/assets/gob-hub.js` — hub data model (IA + copy), category/tile render,
  progress meter, dynamic next-up cue, toasts.
- `design_files/assets/gob-attributes.js` — Player Attributes data (the 14 attributes,
  their category, `zone` for "Matters most", and verbatim definitions) + the row /
  meter rendering.

## Reference (repo files this design is built against)
- `_documentation_master/07_Design_Systems/Styleguide.md`
- `FrontEnd/static/franchise-command-center.css` (shell + panel patterns)
- `FrontEnd/static/css/gob-buttons.css` (canonical `.gob-btn`)
