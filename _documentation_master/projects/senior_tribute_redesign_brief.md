# Senior Tribute — Redesign Brief (for Claude Design)

**Status:** design exploration. Delete once the chosen design is built and folded into
`04_Franchise_Mode_Systems/End_Of_Season_System.md` § Senior Tribute.

## The ask

Redesign the **Senior Tribute**: the full-screen moment that plays when the user presses
**Go To Next Season**. It honours the user's graduating seniors before the next season starts.

Today it is correct but flat — a plain header, a lone portrait in a lot of empty space, a
generic stat box, and a resolution list with wide rows and no hierarchy. Make it feel like a
**send-off**: emotional, celebratory, a little bittersweet — premium, not busy.

Please give **2–3 distinct directions** first (slide + resolution for each), then take the
chosen one to hi-fi.

## How it plays (fixed — design within this)

| | |
|---|---|
| Trigger | FCC → Go To Next Season → confirm |
| Sequence | one **slide per senior**, auto-advancing every **6s**, **no skip / no pause** → **resolution screen** listing all seniors → green **Advance To Next Season** button |
| Who | user team's active-roster seniors only, ordered by RT (best first). **1 to 12 players** |
| No seniors | tribute is skipped entirely (not your problem) |
| Layer | full-screen takeover **over** the top nav bar — no site chrome is visible |
| Audio | a music track plays for the whole sequence |

## Data per senior

**Available now** (`GET /franchise/senior-tribute`):

| Field | Notes |
|---|---|
| name | first + last. Design for long names |
| headshot | painted portrait: head + shoulders in team uniform (jersey number and mascot visible). Transparent PNG. Served at 512px (slide) / 256px (rows) |
| ppg · rpg · apg | career per-game, one decimal |
| def_pct | career DEF%, whole number |
| titles | counts of `conf_rs` (Conf. Regular Season), `conf_t` (Conf. Tourney), `region` (Region Tourney), `national` (National Tourney). **Usually all zero** — the design must look complete with no titles, and still handle 3–4 |
| rt | overall rating (drives order; not currently shown) |
| season | the season number ("Class of Season N") |

**Cheap to add if a direction needs it** (already on the player record — say so if you use them):
position, class year, height, weight, jersey number, games played, career totals. The user's
**team primary colour** is also available on this page.

Anything beyond that (hometown, awards, highlight plays, college commitments) does not exist.

## Constraints

- **Brand:** follow `_documentation_master/11_Design_Systems/Styleguide.md`. Display type Bebas
  Neue Pro, supporting type Inter. Brand navy `#27408E` and orange `#F79420` for atmosphere/accent.
- **Green `#34EC27` is reserved for the gating action.** On this screen that is only the Advance
  To Next Season button — never decorative.
- **Dark, full-bleed.** Must work from ~1280px desktop down to a ~400px phone.
- **Motion:** slide transitions are welcome (today cards slide in from the left, matching the
  Signing Day reveal). Provide a `prefers-reduced-motion` fallback.
- **Nothing interactive on the slides** — they auto-advance. The resolution screen has exactly one action.
- Vanilla HTML/CSS/JS — no framework. Deliver as an HTML/CSS prototype; it will be ported into
  the existing module.

## States to show

1. Slide — no titles, typical name
2. Slide — 3+ titles, very long name
3. Resolution — 1 senior, 5 seniors, 12 seniors (must not scroll awkwardly at 12)
4. Phone width for a slide and the resolution
5. Motion notes: slide-to-slide, and slides → resolution

## Current screenshots

Attached: slide 1 of 5, slide 4 of 5, resolution with 5 seniors (desktop).

## Repo files to review

| File | Why |
|---|---|
| `FrontEnd/static/js/shared/seniorTribute.js` | current markup, sequence, timing, title labels |
| `FrontEnd/static/css/senior-tribute.css` | current styles |
| `_documentation_master/04_Franchise_Mode_Systems/End_Of_Season_System.md` § Senior Tribute | behaviour spec |
| `BackEnd/utils/senior_tribute.py` | exact data returned |
| `_documentation_master/11_Design_Systems/Styleguide.md` | colours, type, buttons, surfaces |
| `FrontEnd/static/recruiting-signing.css` (`.rvhost`, `.sd-*`) + `recruiting-hub.js` `renderReveal()` | Signing Day reveal — the sibling full-screen moment; keep the family resemblance |
| `FrontEnd/static/js/shared/championshipMoments.js`, `css/big-news-modals.css` | existing celebration moments, for tone |

## Out of scope

Backend/data changes beyond the "cheap to add" list · skip/pause controls · the 6s hold ·
the season-transition load screen · the FCC confirm modal.
