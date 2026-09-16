# CC Prompt — Senior Tribute redesign ("Last Page")

Implement the approved Senior Tribute redesign. The design prototype is
`Senior Tribute - Last Page.html` (+ `senior-tribute-hifi.css`, `senior-tribute-hifi.js`)
in the design project. Brief: `_documentation_master/projects/senior_tribute_redesign_brief.md`.

This replaces the visual design of the existing module. **The sequence, timing, trigger,
music and rollover handoff are unchanged and out of scope.**

---

## 0 · Discovery — report before writing any code

Do not start editing. First report back:

1. **Which files own this UI today**, and confirm the list is complete:
   - `FrontEnd/static/js/shared/seniorTribute.js` — markup, sequence, 6000ms hold, title labels
   - `FrontEnd/static/css/senior-tribute.css` — all `.st-*` styles
   - `FrontEnd/static/franchise-command-center.js` — `SeniorTribute.start/teardown` call site and the `/franchise/senior-tribute` fetch
   - `FrontEnd/static/franchise-command-center.html` — stylesheet + script includes
   - `BackEnd/utils/senior_tribute.py` — payload builder
2. **Which data fields actually exist** on the `GET /franchise/senior-tribute` payload today, quoting the builder. Then, for each field the design adds, say whether it is already on the source document the builder reads (`franchise_players_data` → `meta` / `career` / `position_ratings`) or not:
   - jersey number
   - position
   - games played
   - career points
   - seasons with the program / class year
3. **Portrait behaviour**: what `API_CONFIG.getPlayerImageUrl(id, {size})` returns for `modal` and `card`, whether the served PNG is transparent, and what renders today when the image 404s.

**Never invent, derive, or approximate a missing field. If any of the above is not
available, stop and ask** — do not substitute a computed stand-in, and do not fall back to
a field that means something else.

---

## 1 · What changes

Two screens, both inside the existing `.st-host` full-screen takeover.

### Slide (one per senior, unchanged 6s auto-advance)

Editorial layout, bottom-anchored, two zones:

- **Left column** — eyebrow (`Class of Season N · #NN · POS`), then the name set large with
  the **given name in a muted tone on its own line** and the **surname in full white
  beneath it**; a hairline rule; a four-cell career stat row (PPG / RPG / APG / DEF%);
  a one-line career sentence; then title marks if any.
- **Right column** — the portrait as a transparent cutout, bottom-aligned and bleeding off
  the bottom edge with a soft mask, the **jersey number ghosted behind it** at ~5% white.

### Resolution (all seniors, one green CTA)

Replaces the wide-row list. Header (`Class of Season N` + `N seniors · thank you`), then a
**centred grid of portrait cards**, then the CTA. Each card: portrait standing on a hairline
baseline with the jersey number ghosted behind, name, `POS · NN games`, and a four-cell
career stat strip.

Grid buckets (columns × card width × portrait height):

| Class size | Columns | Card width | Portrait height |
|---|---|---|---|
| 1 | 1 | 300px | `min(372px, 44vh)` |
| 2–6 | one per senior | 188px | `min(240px, 29vh)` |
| 7–12 | 6 (wraps to 2 rows) | 154px | `clamp(92px, 16vh, 154px)` |

Use `grid-template-columns: repeat(var(--cols), minmax(0, var(--cw)))` with
`justify-content: center` so columns shrink rather than wrap at narrow widths. **The
resolution must never scroll** — at 12 seniors and 1280×800 the CTA sits clear of the
bottom row.

---

## 2 · Data

Everything the slide and cards show comes from the tribute payload. Fields the design needs
**beyond** what the payload returns today:

- `jersey_number` — the ghosted numeral on both screens and in the eyebrow
- `position` — eyebrow and card meta line
- `games_played` — card meta line and the career sentence
- `career_points` — the career sentence

Add them to `build_senior_tribute_payload` **only if step 0 confirms they already exist on
the documents it reads**. The career sentence reads
`{games} games · {points} career points · four seasons in a {mascot} uniform` — if the
"four seasons" part cannot be derived from an existing field, **drop that clause**; do not
compute it from class year or roster history.

`titles` keeps its current shape and label set (`conf_rs` / `conf_t` / `region` /
`national`, labels unchanged from `TITLE_LABELS`). Usually all zero — both screens must
look finished with none, and hold four.

`rt` continues to drive order and stays unshown.

---

## 3 · Brand rules that are not negotiable

- **Green `#34EC27` appears only on the Advance To Next Season button.** The current
  `.st-chip` is green-tinted — that is the change with the most reach. Titles now render as
  small **orange `#F79420`** squares (a 5–6px block) beside uppercase Inter labels on the
  slide, and as a row of orange marks under the card. No green, no pill chips.
- Display type `Bebas Neue Pro`, supporting type `Inter`, per `Styleguide.md`.
- Team primary colour is **atmosphere only** — one soft radial at the bottom-right of the
  host. Never behind a numeral, never under body copy.
- Small supporting text: `rgba(255,255,255,.6)` for stat labels and card meta,
  `rgba(255,255,255,.46)` for eyebrows. Do not go lighter — the values in the prototype are
  the floor that keeps 4.5:1 on the `#080a10` ground.

---

## 4 · Motion

- **Slide → slide**: outgoing slide fades and drifts 46px left over 300ms; incoming slide is
  inserted at the same time (they overlap, the stage is never empty). Incoming elements
  stagger on `cubic-bezier(.2,.8,.25,1)`: portrait 0ms/620ms, eyebrow 60ms, name 90ms,
  rule wipe 200ms, stats 240ms, career line 300ms, titles 360ms.
- **Hold**: a 2px bar across the top of the host fills over the 6000ms hold. It is the only
  moving thing once the slide has settled, and the only indication of how long the wait is.
- **Slides → resolution**: the last slide's portrait **travels into its own card** — measure
  its rect, clone it to a fixed-position element, animate to the target card's image rect
  over 520ms, then reveal the real image and drop the clone. The other cards arrive on a
  55ms stagger; the CTA fades in 300ms after the last card.
- **`prefers-reduced-motion: reduce`**: every entrance becomes a 150ms opacity fade, the
  progress bar steps to `scaleX(i/total)` per slide instead of animating, the portrait FLIP
  is skipped, and the resolution renders fully formed. The 6s cadence does not change.

See `senior-tribute-hifi.js` (`renderSlide`, `renderRes`, `flip`) for the working version of
all of the above — lift it rather than re-deriving it.

---

## 5 · Responsive

One breakpoint at **820px**. Below it the slide stacks — portrait on top (`max-height:44vh`,
mask fading into the copy), copy block beneath — and the resolution drops the per-cell stat
labels, keeps the values as 12px Inter, and goes to 3 columns (2–6 seniors) or 4 columns
(7–12). Must work down to 400px wide. No horizontal scroll at any width.

---

## 6 · Accessibility / behaviour (keep as-is)

Host keeps `role="dialog"`, `aria-modal="true"`, `aria-label="Senior Tribute"`, and the
z-index that puts it above the auth bar and below modals/toasts. Ghost numerals and title
mark rows are decorative — `aria-hidden="true"`. `#st-advance` keeps its id, its
click-to-`onAdvance` contract, and its disabled "Advancing…" state.

---

## 7 · Do not change

The 6s hold · no skip/pause · the trigger and confirm modal · the music track and
`tributeMusic` wiring · `teardown()` · the FCC background `finish-season` handoff ·
`onAdvance` · RT ordering · the CTA copy ("Advance To Next Season") · the title label
strings · the payload's existing field names.

---

## 8 · The mock's values are illustrative

Player names, jersey numbers, PPG/RPG/APG/DEF%, games and career points in the prototype are
**fixture data invented for the mock**. The portraits in `art/tribute/` are cut out of
screenshots and are stand-ins for the served transparent PNGs. The copy "four seasons in a
Knights uniform" is a sample of the sentence shape, not final per-team copy. Use the real
payload for everything.

---

## 9 · Acceptance

1. 1, 5 and 12 seniors: resolution fits 1280×800 with no scroll and no overlap of the CTA.
2. Zero titles: no empty containers, no reserved gap on either screen.
3. Four titles + a 30-character name: slide holds without clipping or reflowing the portrait.
4. Missing portrait: slide and card fall back to the ghost numeral / initials rather than a
   broken image box.
5. 400px wide: both screens readable, nothing below the fold on the resolution.
6. Reduced motion: no transforms, cadence unchanged.
7. `rg -n "34EC27|#9dff5a|st-chip"` over the tribute CSS returns the CTA only.
