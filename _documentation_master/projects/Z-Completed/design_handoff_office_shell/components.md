# Component specs

- **Sizes** are given at 1280. Anything using `--fs-*`, `--dsp-*` or `--dsz-*` becomes about ×1.18 at 1920 automatically (see `layout.md`). `--space-*`, radii and line widths stay fixed.
- **Token shorthand:** `t100/t87/t60/t38` = `--text-100/87/60/38`; `w-N` = `--white-N`; `mix(X,N%)` = `color-mix(in srgb,var(--X) N%,transparent)`.
- **Defaults for every interactive element:**
  - **Focus:** `:focus-visible` → 2px `--white` outline, 2px offset (−2px inset on full-width rows, 3px on Advance).
  - **Hover transitions:** `--dur-hover` (120ms).
  - **Reduced motion:** under `prefers-reduced-motion` all animations and transitions are off and final states render immediately.
  - **No spinners, ever.**
- **Links:** player/team/game names are `.nm` (t100, semibold, underline appears on hover at t60). Text links are `.lnk` (Inter 600 fs-12, t60, trailing "→" that moves 2px on hover, colour → t100).

---

## 1. Top bar `.top`
**Size and surface**
- Height `--top-h` (56 / 64). Spans both grid columns.
- `--bg-chrome` background, 1px `--line` bottom border. Padding-right 16, gap `--dsp-24`.

**Contents, left to right**
- **`.top-id`:**
  - Logo 32px (38 at 1920): `.logo`, radius 24%, `--tc` fill, `--shadow-logo`.
  - Team name: Bebas 700 fs-22, `--tracking-4`, t100.
  - Left padding 16 (22 at 1920). The whole block links to the team page.
- **`.top-div`:** 1×26px, `--line-strong`.
- **`.top-stats`**, gap `--dsp-20`. Three `.ts` stacks: Record · National (`#14`, or `NR` if unranked) · Week N.
  - Value: Bebas 700 fs-20, tracking-3, t100.
  - Label: Inter 600 fs-10 UPPERCASE, tracking-8, t60.
  - Week label = phase: Training Camp · Regular Season · Conference Tourney · Region · Nationals · Signing Day · Offseason.
- **Flexible spacer**, then `.adv-wrap` (§4).

**Tier weeks `.top.is-tier`** (conference / region / national)
- Set inline `--tier-metal` / `--tier-metal-hi` from emblem.js TIER_TOKENS.
- Background adds `radial-gradient(420px 90px at 38% 50%, mix(tier-metal,13%), transparent 70%)`.
- `::after` is a 1px hairline along the bottom edge: gradient `transparent 5% → tier-metal 30% → tier-metal-hi 45% → tier-metal 60% → transparent 90%`, opacity .8.
- `.ts-tier` puts the colour emblem (20px, 24 at 1920) before the week stat. The phase label turns `--tier-metal-hi`.
- Nothing else in the bar changes.

## 2. Left rail `.rail`
**Container**
- Width `--rail-w` (64 / 200). `--bg-chrome` background, 1px `--line` right border.
- Padding 12×10 (14×12 at 1920). Flex column, gap 2.

**Section items `.rail-i`** — order: Office · Team · Prep · League · Recruiting · News
- **Default:** height 44, radius 10, colour t60. Icon 22px (stroke 1.8). Label Bebas 700 fs-16, tracking-6, gap 12.
- **Collapsed (1280):** icon centred, label hidden (`title` attribute gives the tooltip).
- **Expanded (1920):** padding 0×14, icon + label.
- **Hover:** background w-6, colour t100.
- **Active `.on`:** background `--navy`, colour t100, `inset 0 1px 0 w-14`. Only one item is ever active.
- **Focus:** 2px white outline, inset −2px.
- **Badge `em`:**
  - `--badge` fill, `--badge-ink` text, Inter 700 11px, min 18×18, radius 9, padding 0×5.
  - Collapsed: 16×16 / 10px, absolute top 4 right 4. Expanded: pushed right (`margin-left:auto`).
  - None: omit the element.
  - **Urgent `em.urgent`:** static 2px `mix(badge,35%)` ring, plus the `badgePulse` animation (§ Motion). Reduced motion: static 2px `mix(badge,50%)` ring only.

**Bottom group**
- After a flexible spacer, a 1px `--line` divider (margin 6×4).
- **Utility items `.rail-i.util`:** Tutorials (?) · Feedback (speech bubble — **online only**, omit offline) · Settings (gear). Height 40, icon 20, t60.
  - Open-panel state `.open`: background w-10, `inset 0 0 0 1px line-strong`. Neutral, never navy.
- Then a quieter divider (w-5, margin 8×4×6).
- **Exit `.rail-i.exit`:** height 36, icon 18, fs-14, t38. Hover: t87 on w-4.

## 3. Sub-tab row `.subtabs` (section pages)
- **Row:** flex, gap 6, directly under the page title in the sticky `.pg-head`.
- **Tab `.stab` (default):** height 40, min-width 118, padding 0×20. Bebas 700 fs-16, tracking-4.
  - Parallelogram: `clip-path: polygon(10px 0,100% 0,calc(100% - 10px) 100%,0 100%)`.
  - Background w-6, colour w-55.
- **Hover:** w-11 / w-90.
- **Active `.on`:** w-9 / white, plus a 2px w-70 top edge via `::before` (inset 10px on the left).
- **Focus:** background w-11 plus a 2px white inner bottom edge. `clip-path` would cut an outline, so none is used.
- Tabs are routes (the URL changes). ←/→ move between tabs while the row has focus.
- **Page title `.pg-title`:** Bebas 700 fs-32, tracking-4, t100, followed by a crumb in fs-12 t60.
- **`.pg-head`:** height `--dsz-118`, padding-top `--page-pad`, gap 12. Background `linear-gradient(180deg, --bg-page-solid 85%, --bg-page)`, sticky at top 0, `--z-sticky-head`.

## 4. Advance button `.advance` (+ `.adv-wrap`, `.adv-hint`)
There is exactly one per franchise screen, always in the top bar.

**Default**
- Height `--dsz-40` (40 / 47), min-width 138, padding 0×20, radius 10.
- `--green` fill, `--bg` ink, 1px w-28 border, `--shadow-advance`.
- Bebas 700 fs-18, `--tracking-btn` (1.6px), no wrap. It grows with the label and never truncates.
- Labels: RUN TRAINING · PLAY NEXT GAME · PLAY CONFERENCE SEMIFINAL · RUN SIGNING DAY · GO TO NEXT SEASON (existing copy wins where it exists).

**States**

| State | Treatment |
|---|---|
| Hover | `filter:brightness(1.06)`, `translateY(-1px)` |
| Pressed (`:active`) | `translateY(1px) scale(.985)`, `brightness(.94)`, `inset 0 2px 4px black-25`, `--dur-press` |
| Focus | 2px white outline, 3px offset |
| Loading | label → **"STARTING…"**, `filter:saturate(.55) brightness(.82)`, `cursor:progress`, no transform; repeat clicks ignored; **no spinner** |
| Disabled | background w-6, t38 text, w-12 border, no shadow, 15px lock icon before the label, `aria-disabled="true"`, `cursor:not-allowed`, no hover |

- **`.adv-hint`** is shown only when disabled, to the left of the button, gap 14. Inter 600 fs-12, t60, ending " →"; t100 on hover. It links to the blocking task.

## 5. Column header `.office-h`
- Height `--dsz-22` (20 at 1280), baseline-aligned, space-between.
- `h2`: Bebas 700 fs-20, tracking-7, t87. The zone number ("01", "02", "03") sits before it at fs-15, t38.
- Right meta: fs-11 t60 (e.g. "Week 22 · Regular Season").

## 6. Card `.card` (base surface)
- Background `linear-gradient(180deg, w-4, w-1p8)`, 1px `--line` border, radius 14, `--shadow-card`.
- Padding `--dsp-14` × `--dsp-16` (12×14 at 1280). Flex column, gap `--dsp-10` (8 at 1280).
- **`.card-h`:** `h3` Bebas 700 fs-16, tracking-8, t60; right side `.meta` (Inter 500 fs-11 t60) and/or `.lnk`.
- **`.sub-h`:** Inter 700 fs-10 UPPERCASE, tracking-10, t38, margin-top 4.
- **`.card-f`:** right-aligned links, gap 16, pushed to the card bottom.
- No card scrolls internally.

## 7. To-do row `.todo` (button) and note `.note`
**`.todo`**

*Default (required task)*
- Min-height `--dsz-50`, padding `--dsp-10`×`--dsp-12`, radius 10, gap `--dsp-12`.
- Background w-3p5, `inset 0 0 0 1px line`.
- Checkbox `.cbox`: `--dsz-18` square, radius 5, `inset 0 0 0 1.5px w-40`.
- Label `.td-l`: Inter 600 fs-14, t87.
- Meta `.td-m`: fs-11 t60.
- `.td-m2`: fs-11 t38, **1920 only**.
- Tags row `.td-tags`: margin-top 5, gap 6.
- Chevron `.td-c`: 16px, t38.

*States*

| State | Treatment |
|---|---|
| Hover | background w-7, inset w-20, `translateY(-1px)`, label t100, chevron t100 + `translateX(2px)` |
| Focus | outline, −2px inset |
| Done `.done` | transparent background, inset w-5; checkbox filled w-38 with a `--bg` check; label t38 + line-through w-25; meta t38; still clickable (opens report/result) |
| Gated `.gated` | inset mix(orange,30%); checkbox outline `--orange`; tag `.td-gate`: lock 11px + "BLOCKS ADVANCE", Bebas 700 fs-11, tracking-10, orange text, mix(orange,8%) fill, inset mix(orange,45%), radius 4, padding 4×7×3 |
| Advance-mirror | tag `.td-adv` "ADVANCE": Bebas 700 fs-11, tracking-12, t60, inset line-strong, radius 4, padding 4×6×3. The row routes to the same action as the top bar. |
| Locked `.locked` | label t60, checkbox inset w-20, Advance tag at 50% opacity |

**Note row `.note`** (optional item)
- Link. Padding `--dsp-8`×`--dsp-4`, 1px `--line` top border (except the first), fs-12, t60.
- 5px dot at t38, text flexes, trailing `.lnk` CTA. Meta goes after the text in t38 ("· Week 22").
- Hover: the CTA goes to t100.

**Overflow:** at 1280, 4 items maximum, then `.lnk.more` "See all · N more".

## 8. Result card `.office-res`
**Win (default)**
- Base card, gap `--dsp-12` (9 at 1280).
- Team wash: `linear-gradient(112deg, mix(team-primary,46%) 0%, mix(team-primary,16%) 42%, transparent 72%)` over the card fill.
- Border mix(team-primary,45%). A 3px top bar via `::before`: `linear-gradient(90deg, --team-primary, transparent 80%)`.

**Contents**
- **Kicker `.res-k`:** WIN badge + when-text (Inter 600 fs-11, UPPERCASE, tracking-6, t60) + "Box Score →".
  - `.wl.win`: height `--dsz-22`, padding 0×9 (top 2), radius 6, Bebas 700 fs-16, tracking-10. Colour `--delta-up`, background mix(green,12%), inset mix(green,40%).
- **Score `.res-score`:** `grid-template-columns: minmax(0,1fr) auto auto auto minmax(0,1fr)`, gap `--dsp-12`.
  - Team lockups: logo 34 (44 at 1920) + name (Bebas 700 fs-22, tracking-3). The opponent is right-aligned in t60, with its rank prefix (`#9`, 0.8em, t60).
  - Points `.rs-pts`: Bebas 700, fs-36 at 1280 / fs-48 at 1920, lh .9, t100. The loser uses `.them` (t60). The dash is Bebas 400 fs-28, t38.
- **Headline `.res-hl`:** Inter 600 fs-14, t87. Links to the article; underline on hover.
- **POTG `.potg`:**
  - 1px w-10 top rule, padding-top 8 (`--dsp-10` at 1920).
  - Portrait 46 (76 at 1920), radius 10, `object-position:50% 22%`.
  - Eyebrow "Player of the game" (Inter 700 fs-10, UPPERCASE, tracking-10, t60), name `.nm` fs-16, "POS · RT" with a tier digit.
  - Stat line: numbers Bebas 700 fs-32, labels fs-10 700 t60, gap `--dsp-16`.
  - **1920 only** `.pg-extra`: FG / 3PT / MIN in Bebas fs-18, t87.

**Loss `.is-loss`**
- No wash and no top bar, `--line` border.
- Badge `.wl.loss`: fs-14, text mix(red,90%), transparent fill, inset mix(red,35%).
- Names t87. Lawrence's score gets `.them` (t60), the winner's score t87.
- Eyebrow reads "Lawrence leader".
- **1920 only** `.res-next` row: "UP NEXT · [logo 18] vs York · Fri · Home · Scout them →". Padding `--dsp-8`×`--dsp-10`, radius 8, w-3p5, inset line.
- Calm arrival (see Motion).

**Season final** (Signing Day)
- Loss or win styling, plus `.res-season` above the kicker: Bebas 700 fs-14, tracking-8, t87, bottom rule `--line`. Example: "Season complete · 26–7 · Keystone Tournament champions".

## 9. Delta chip `.chip`
- Inline-flex, min-width `--dsz-34`, height `--dsz-20`, padding 0×6, radius 6. Inter 700 fs-11.
- Content is the glyph + value: "▲3" / "▼2" / "—" / "W4" / "L1" / "1st" / "2nd" / "T-1st".

| Variant | Text | Fill | Inset |
|---|---|---|---|
| `.up` | `--delta-up` | mix(green,11%) | mix(green,32%) |
| `.down` | `--delta-down` | mix(red,12%) | mix(red,36%) |
| `.flat` | t60 | w-5 | line-strong |

- In wire rows it becomes a square chip (min-width `--dsz-24`, padding 0) showing only ▲ / ▼ / —.
- Arrival: `ar-pop` (see Motion).

## 10. What moved `.office-mv`
- Base card. Header "What moved" + meta "Since Week N".
- **Strip `.mv-strip`:** 3 equal columns, gap `--dsp-8`. Each `.mv-cell` is a link:
  - Padding `--dsp-10`×`--dsp-12` (7×10 at 1280), radius 10, w-3, inset line; hover w-6p5.
  - Label Inter 700 fs-10, UPPERCASE, tracking-8, t60.
  - Value Bebas 700 fs-28 (24 at 1280), t100, plus its chip (gap 8). Cells: National rank (▲▼ chip) · Conference standing (▲▼ chip) · Record (streak chip).
- **Attribute rows `.mv-p`:**
  - Padding `--dsp-8`×2 (4×2 at 1280), 1px line top border (except the first).
  - Avatar 30 (**1920 only**), `.nm` name fs-13, "POS · Attribute" fs-12 t60.
  - Digits from → to in Bebas 700 fs-20, each coloured by its own tier; arrow t38 fs-12. Then the chip.
- Rank and record values count up on arrival.

## 11. Recruiting wire row `.wr` (in `.office-wire`)
- **Card header:** "Recruiting Wire" + status meta ("Invite Wk 3 of 7 · Board sent") + "Recruiting →".
- **Row:**
  - Grid `auto minmax(0,1fr) auto` (1920: `auto auto minmax(0,1fr) auto`), gap `--dsp-10`.
  - Padding `--dsp-8`×2 (4×2 at 1280), 1px line top border (except the first).
  - Direction chip (square) · avatar 32 (**1920 only**) · body · tag.
  - Line 1: `.nm` name fs-13 + meta fs-11 t60 ("PG · ★★★★☆ · Filmed B"). Filled stars t87, empty w-18.
  - Line 2: fs-12 t87 event text; a team name inside it is a `.nm` link.
  - Tag `.wr-tag`: Bebas 700 fs-16, tracking-4, t87 ("#1", "Top 3").
- **Gain / hold:** ▲ up chip / — flat chip.
- **Drop `.dn`:** ▼ down chip and the tag turns `--delta-down`. Layout, weight and size are identical to a gain; drops must be exactly as visible.
- **Hover:** the name underline appears; the whole row is the hit area.

## 12. Next-game card `.office-next`
**Regular**
- Base card.
- **Top meta:** "[label ·] Fri · 7:00 PM · Away". "Season opener" is bold t87.
- **Matchup `.nx-m`:**
  - Logo 44 (56 at 1920).
  - "at" / "vs" in Bebas 400 fs-14, tracking-12, t60.
  - Opponent `.nx-name`: Bebas 700 fs-32, lh .9, t100; 2px underline on hover.
  - Sub-line fs-12 t60: "#22 · 13–8 · Keystone Conference", or "Unranked · …".
- **RT compare `.nx-rt`:** padding `--dsp-8`×`--dsp-12`, radius 10, w-3, inset line. Label fs-10 UPPERCASE tracking-8 t60, then "LAW [A−]" / "MOR [B+]" with grades in Bebas 700 fs-18 coloured by tier (§ RT ramp).
- **1280 "Players to watch" `.ptw` ×2:** padding `--dsp-6`×2, `.nm` fs-13, role fs-11 t60, value Bebas 700 fs-22 t100, unit Inter 700 fs-10 t60 (width `--dsz-28`).
- **1920 "Projected starting five" `.f5` ×5:**
  - Grid `auto 1fr --dsz-30 --dsz-26 --dsz-64`, padding `--dsz-4`×2.
  - Avatar 28 · name + leader tag (`.f5-tag` fs-10 700 UPPERCASE tracking-6 t60, inset line-strong, radius 4) · position fs-11 t60 · RT digit Bebas fs-20 (tier colour) · stat right-aligned fs-13 600 + unit fs-10.
- **Footer:** "Scout them →".

**Tournament `.office-next.tier`**
- **Surface:**
  - Border mix(tier-metal,50%).
  - Background `radial-gradient(120% 70% at 50% 0%, mix(tier-metal,18%), transparent 60%), linear-gradient(180deg, --surface-tier-top, --surface-tier-bottom)`.
  - `--shadow-tier`.
  - `::before` hairlines: `repeating-linear-gradient(132deg, transparent 0 22px, mix(tier-metal-hi,3.5%) 22px 23px)`.
  - Gap 6 at 1280.
- **Band `.tn-band`:**
  - Lockup: emblem 28 (40 at 1920) + "CONFERENCE" (Bebas 700 fs-18) / "TOURNAMENT" (Bebas 400 fs-11, tracking-26, tier-metal-hi).
  - Round `.tn-round`: Bebas 700 fs-40 (32 at 1280), t100, `text-shadow 0 0 24px mix(tier-metal-hi,35%)`.
  - Bottom rule mix(tier-metal,35%), padding-bottom 6.
- **VS `.tn-vs`:** grid `1fr auto 1fr`.
  - Each side: logo 38 (52 at 1920) with a seed badge (`.tn-seed`: 22 circle, `--bg`, inset 1.5px tier-metal, Bebas 700 fs-13 tier-metal-hi, offset −8/−8), name Bebas 700 fs-28 (22 at 1280), record fs-11 t60.
  - At 1280 the record line also carries "· RT [grade]".
  - "VS": Bebas 700 fs-24, tier-metal-hi, tracking-8.
- **When `.tn-when`:** padding `--dsp-8`×`--dsp-12` (6×10 at 1280), radius 10, mix(tier-metal,9%) fill, inset mix(tier-metal,28%). fs-12 600 t87, stakes in t60.
- **Below:** 1920 shows the RT row + starting five; 1280 shows the two leader rows. Then "Scout them →".

## 13. Team snapshot `.office-snap`
- **Header:** "Team Snapshot" + "Team measures →".
- **Chemistry:** label fs-12 t60; value Bebas 700 fs-22 t100 with "/25" at 0.75em t38.
  - Meter `.meter`: height `--dsz-6`, radius 4, track w-7, fill w-62. Neutral, never the energy hue.
- **Player attitude:** label + "12 players" meta.
  - `.spread`: height `--dsz-6`, gap 2, one segment per bucket with `flex: count`. Luminance w-75 / w-45 / w-22, and `--red` for Unhappy only.
  - Key `.sp-key`: fs-11 t60, counts bold t87. The Unhappy entry is red when above 0.
- **"Moved most this week"** sub-head, then 2 `.msr` rows:
  - Padding `--dsp-6`×2, name t87 (underline on hover), value Bebas 700 fs-20 t87 (neutral), chip.
  - Preseason: sub-head "Set after camp", value "—", no chip.

## 14. Signing Day card `.office-sign`
Replaces column 3.
- **Header:** "Signing Day" + meta "Week 35 · Class of 2027".
- **Points `.sg-pts`** (link): padding `--dsp-10`×`--dsp-12`, radius 10, w-3, inset line.
  - Micro label "Points remaining".
  - Value Bebas 700 fs-40 + "/ 50" in Bebas fs-18 t38.
  - Neutral meter.
- **`.sg-2`:** 2 stat cells ("Promises made", "Roster spots open"), same style as What moved cells.
- **Sub-head** "Top targets · where you stand", then 3 `.wr.sg-t` rows:
  - Standing chip first (min-width `--dsz-40`): ▲1st = leading · ▼2nd = trailing · —T-1st = tied.
  - Then avatar (1920), name + position + stars, lean line, chevron.
- **Footer:** "Promises →", "Signing Board →".

## 15. Season preview card `.sp-card`
Replaces the result in week 1.
- **Tag `.sp-tag` "SEASON PREVIEW":** Bebas 700 fs-14, tracking-12, t100, padding 5×9×4, radius 6, fill mix(team-primary,55%), inset w-18. Meta "Week 1 · No games played".
- **Title `.sp-title`:** Bebas 700 fs-28, lh .95, t100. Links to the preview article.
- **Strip:** Preseason rank `#31` · Keystone outlook `Picked 4th` · Team RT (letter).
- **Rows:** Returning starters `3 of 5` · Top returner (name, position, RT digit) · Newcomers.
- **Footer:** Roster →, Season schedule →.
- **Plus a one-line Wire card:** "Recruiting Wire · Opens with the invite period · Week 14 · Build your watchlist →".

## 16. Final standings `.office-final` (Signing Day)
- **Strip:** Final national rank · Conference finish · Final record.
- **Table `.st-r`:**
  - Grid `--dsz-18 1fr --dsz-52 --dsz-60`, padding `--dsp-6`×`--dsp-8`, fs-12 t87, 1px line top border.
  - Rank column t38 bold. Header row is a micro label.
  - Your row `.me`: fill mix(navy,35%), radius 6, inset mix(navy-hi,35%).
  - Team cell: logo 18 + `.nm` + an optional tag (micro, t60). Rows are links; hover w-5.

## 17. Settings panel `.settings` + `.set-scrim`
**Panel and scrim**
- **Scrim:** absolute from `left: --rail-w; top: --top-h` to the far edges, `--scrim` fill, `--z-scrim`. Clicking it closes the panel.
- **Panel:**
  - Absolute at `left: --rail-w; top: --top-h; bottom: 0`, width 440, `--z-panel`.
  - `--surface-panel` fill, 1px line-strong right border, `--shadow-panel`.
  - Flex column. Enters with `setIn` (see Motion).
  - While open, the gear rail item takes `.open`.

**Header `.set-h`**
- Height 56, padding 0×20×0×24, bottom rule line.
- "Settings": Bebas 700 fs-28, tracking-4.
- Close `.set-x`: 32×32, radius 8, t60, fs-22 "×"; hover w-7 / t100. **Esc** also closes.

**Body `.set-b`**
- Padding 16×24, gap 18.
- Section `h3`: Bebas 700 fs-16, tracking-10, t60, with an optional right note (fs-11 t38) or link.

**Audio** — 4 rows (Master · Music · Sound Effects · Ambience), note "Changes apply instantly"
- Row `.aud`: grid `32px 96px 1fr 30px`, gap 12, height 36 → mute button · label (fs-13 600 t87) · slider · value (fs-12 600 t60, right-aligned).
- Muted row `.is-muted`: label and value t38, slider fill w-22, thumb `--slider-knob-muted`. The level is kept.
- Mute button `.mute`: 32×32, radius 8, inset line-strong, icon 18 t60.
  - Hover: w-7 / t100.
  - Muted `.on`: slashed-speaker icon, `--red` text, fill mix(red,8%), inset mix(red,40%).
- Slider `.slider` (`role="slider"`, `aria-valuenow`):
  - Hit area 18 tall. Track 4px, radius 2, w-10. Fill 4px w-72 (neutral).
  - Thumb 14 circle, white, `0 1px 4px black-50`.
  - Hover: +5px w-12 halo. Drag `.is-drag`: 7px mix(navy,55%) halo. Focus: 5px w-35 halo.
  - Keys: ←/→ ±5, Shift ±10, Home/End.

**Coach stats**
- Header link "Coach profile →".
- `.cs-grid`: 4 columns, gap 8.
- Tile `.cs` (link): padding 10×12, radius 10, w-3p5, inset line. Value Bebas 700 fs-24 t100; label fs-10 700 UPPERCASE tracking-6 t60.
- Tiles: Career record · Titles · All-Americans coached · Seasons coached.

**Account** (online only)
- `.acct` grid `84px 1fr`, gap 6×12, fs-13: label t60, value t87 600 (Username, Email).
- **Log Out `.btn-ghost`:**
  - Height 42, min-width 138, padding 0×18, radius 10.
  - w-5 fill, 1px w-18 border, t87 text, Bebas 700 fs-17, tracking-btn-sm, `inset 0 1px 0 w-9`.
  - Hover: w-10 fill, −1px lift. Not red.
- **Offline:** replace the whole section with `.set-note` (fs-12 t38): "Playing offline. Account settings return when you're back online."

**Footer `.set-f`**
- Height 44, padding 0×24, top rule line, fs-11 600 t38.
- Build label left ("Alpha 0.9 · build 1234").
- Connection right: a 6px dot, filled w-60 when Online and a hollow ring when Offline.

## 18. Toggle switch `.tgl`
- 36×20, radius 10, w-12 fill, inset line-strong. Knob 14px at 3/3, `--switch-knob-off`.
- **On `.on`:** `--navy` fill, inset mix(navy-hi,45%), knob `translateX(16px)` white. Transition `--dur-toggle`.
- `role="switch"`, `aria-checked`. Space/Enter toggles it.

## 19. Gameplay audio control (live game — no shell)
- **Strip `.sb`:** the existing scoreboard; the one in the frame is illustrative. It shows the shape: height 52, radius 12, `--surface-scoreboard`, `--shadow-scoreboard`.
- **Sound cap `.sb-snd`:** far right of the strip, padding 0×8, 1px line left border.
- **Button:** 30×30, radius 7, speaker icon 17, t38. Hover / open: t100 on `--line` fill. When muted, the slashed icon shows at t60.
- **Popover `.snd-pop`:**
  - Absolute, right −6, top 100% + 8, width 250, padding 12×14, radius 12.
  - `--surface-popover`, `--shadow-popover`, gap 10, `--z-popover`.
  - Arrow: a 10px rotated square at right 16, top −5.
- **Popover contents:**
  - Row "Mute all" + `.tgl` (fs-12 600 t87), bottom rule line, padding-bottom 8.
  - Rows `.snd-r`: grid `48px 1fr 26px`, gap 10 → label · `.slider` · value t60. Music and SFX only.
- Closes on outside click or Esc. The game never pauses.

---

## Motion
All motion uses tokens from `tokens.css`. Nothing ever blocks input.

**Office arrival** — only on the first open after a new result; a plain revisit gets none.
- Add `.arriving` to the root, then run the count-up.
- `.ar-card`: `arCard` (from `opacity:0; translateY(10px) scale(.985)`), `--dur-arrive-card` 380ms, `--ease-out`.
- `.ar-item`: `arItem` (from `opacity:0; translateY(6px)`), `--dur-arrive-item`. Delay `calc(--delay-arrive-items + var(--i)*--stagger)`, i.e. 320ms + 60ms × index.
- **Count-up:** elements with `data-cu-from` / `data-cu-to` / `data-cu-pre` / `data-cu-suf` tween over `--dur-count` (600ms), ease-out cubic, starting at 320ms.
  ```js
  function countUp(root){root.querySelectorAll('[data-cu-from]').forEach(el=>{const a=+el.dataset.cuFrom,b=+el.dataset.cuTo,pre=el.dataset.cuPre||'',suf=el.dataset.cuSuf||'';const t0=performance.now()+320;const step=t=>{const k=Math.min(1,Math.max(0,(t-t0)/600)),e=1-Math.pow(1-k,3);el.textContent=pre+Math.round(a+(b-a)*e)+suf;if(k<1)requestAnimationFrame(step)};requestAnimationFrame(step)})}
  ```
- `.ar-pop` (delta chips) pops last: `arPop` (from `opacity:0; scale(.55)`), `--dur-pop`, `--ease-pop`. Delay `--delay-chips` (920ms) + i × `--stagger-chip`.
- **After a loss** (root `.calm`): cards take 300ms with no scale, there is no count-up (render final values), and chips use `arItem` at `--delay-chips-calm` (560ms) with no overshoot.

**Rail**
- Hover: background and colour change over `--dur-hover`.
- **Hover-expand (collapsed rail only):** after `--delay-rail-expand` (400ms) of hover, the rail widens to 200px **as an overlay** (`position:absolute`, above `.main`, no reflow) over `--dur-rail` (180ms) `--ease-out`. It collapses 120ms after the pointer leaves. Keyboard focus inside the rail also expands it.

**Sub-tab switch**
- The active 2px top edge slides to the new tab over `--dur-tab` (160ms) `--ease-out`.
- Content crossfades over `--dur-hover` (120ms) with no vertical shift. Page scroll resets to the top.

**Advance press**
- Hover lift 1px, press 1px down + `scale(.985)` over `--dur-press` (80ms).
- On release it switches to the loading state immediately. The next screen replaces the page when ready.

**Badge pulse**
- Urgent only: `badgePulse` over `--dur-pulse` (1.6s), infinite. A `box-shadow` ring grows 0 → 7px while mix(badge) fades 55% → 0.
- It stops as soon as the gating task is done.
- Reduced motion: static 2px ring.

**Settings panel**
- `setIn` (from `translateX(-24px); opacity:0`), `--dur-panel` (220ms), `--ease-out`. Closing reverses it at 160ms.
- Reduced motion: instant.

**Toggle:** `--dur-toggle` (140ms). **Slider thumb halo:** `--dur-hover`.
