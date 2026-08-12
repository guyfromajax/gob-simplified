repo: guyfromajax/gob-simplified
branch: develop
path: FrontEnd/static

## Last sync
date: 2026-08-05T12:29:40Z

### Updated in this project
- **Adopted the shipped art generators.** Copied `js/shared/teamGeneratedArt.js` and `js/shared/teamCourtGenerator.js` verbatim; `tb-art.jsx` is now a thin React wrapper that calls them. Every banner, court and jersey preview in the prototype is now pixel-identical to production.
- Rebuilt the Found studio's controls to the generators' real input set and deleted the invented ones.
- Reconciled the Review screen onto the same generators (`defaultsFromTeamColors` for the court, real chevron banner for the hero).
- Rebuilt `tb-league-data.js` on the REAL league: the canonical 128 slugs from `images/teams/`, conference-level `CONFERENCE_GEOGRAPHY`, region letters A–H, rank bands 26/25/26/25/26.
- Copied the 128 `<slug>_banner_card.webp` files + `general_banner_card.webp` — the Claim cards show real program artwork.

### Where my earlier design was wrong (now corrected)
- **Banner composition.** I drew a left-aligned mark + rule + name at 4:1. Production is a **chevron**: flat primary, angled `shadeHex(primary,-0.16)` split, two secondary chevron strips at .9/.35 alpha, 150px ghost initials at 12% bottom-left, **centred** shrink-to-fit wordmark (50px → 20px floor, max 300px in card space), centred Oswald-300 mascot at 10px with 4.5px tracking. Card is **400×141**, primary **1920×679**.
- **Ink.** I tinted the wordmark in the secondary color with a 2.4:1 threshold. Production uses **pure #000 or #fff, best-of-two by WCAG contrast**, tie floor ~4.58:1 — so legibility is guaranteed, not negotiated. Secondary never appears as text.
- **Jersey.** I invented four styles (Solid/Piped/Panel/Shadow) that changed the banner. There are **two presets** (1 SOLID, 2 SOLID WITH TRIM) and they affect **only the jersey SVG**, never the banner.
- **Court.** Mine was hand-drawn SVG with 5 invented regions including a centre-circle fill. Production is a 3333×2083 canvas port of `generate_non_a1_courts.mjs` with **9 hardwood keys** (`{inside}_{outside}` over light/medium/dark) and five color params: `oobColor`, `laneColor`, `outsideWoodColor`, `halfArcFillColor`, `lineColor`. There is **no centre-circle color** — I removed that control. `outsideWoodColor` paints midcourt, not the centre.
- **Missing controls I had omitted:** midcourt floor override and markings/line color. Both added.
- **"EST. 2026"** in my banner does not exist in production. Removed.

### Requested production changes
Three design asks that the shipped generators cannot express today. None are
blocking the prototype; each needs a small addition to the real code.

1. **`insideWoodColor` on `teamCourtGenerator.js`.** `resolveWoodColors` only
   honours `outsideWoodColor`; the inside-the-arcs tone comes from the style key
   alone, so a custom color inside the 3PT lobes is not renderable. The studio
   therefore offers light/medium/dark inside and light/medium/dark/custom for
   midcourt — an asymmetry the design would rather not have.
2. **A second line parameter — WITHDRAWN.** The Markings control was removed
   from the design, so `lineColor` stays at the generator's own `COLORS.line`
   (#6e675f) for every custom program and no second parameter is needed. The
   original problem stands recorded: `lineColor` paints every marking
   (`drawPaintLinework` + `drawCourtLinework`), so had it stayed user-editable it
   could erase the 3-point line against the wood.
3. **Banner composition variants — DECIDED.** Four compositions ship and the
   chevron is retired: **Keel**, **Baseline** (default), **Plate**, **Sash**.
   Each is a draw function in `tb-banner-variants.jsx` written to
   `drawChevronBanner`'s exact contract (400×141 card space, shrink-to-fit
   wordmark 50→20px, WCAG best-of-two ink), so they port over as-is. Needs:
   - four new draw functions beside (or replacing) `drawChevronBanner`
   - a stored `banner_variant` on the team, defaulting to `baseline`
   - `bannerCardDataUrl` / `bannerPrimaryDataUrl` to dispatch on it
   Two fixes worth carrying over: shrink-to-fit must measure against each
   composition's own field width (Plate's is 264 card units, not 300), and the
   mascot's opacity/contrast must be computed against the surface actually
   beneath it, not the primary by assumption.

## Known gaps
- Court preview uses `useOverlays:false` (the real preview path). The Phaser path loads basket/rimnet overlay PNGs from `images/teams/general/court-overlays/` — not copied, so the prototype shows the fallback rim strokes, exactly as the wizard preview does.
- Claim's conference assignment is derived from program place-names, not the real `team.conference`; the Review standings still name eight invented Conference-14 programs.
- The gate, roster and Review still name "Northlake State" / "Cascade Valley" — not yet driven by a shared fixture with Claim.

## Screen map
| Screen | Built from |
| --- | --- |
| Team Builder - Claim.html | FrontEnd/static/franchise-select-team.html + js/shared/teamPicker.js + css/team-picker.css @develop |
| tb-league-data.js | images/teams/ folder names (canonical 128) + CONFERENCE_GEOGRAPHY / BAND_CUTOFFS from js/shared/teamPicker.js + nameToTeamSlug from common.js @develop |
| FrontEnd/static/images/teams/**/*_banner_card.webp | copied verbatim @develop |
| Team Builder - Banner Options.html | five candidate compositions on the shipped contract; A = drawChevronBanner @develop |
| tb-banner-variants.jsx | draw functions in drawChevronBanner's contract — the shipping set (B/C/D/E) |
| Team Builder - Found Studio.html | js/shared/teamGeneratedArt.js + js/shared/teamCourtGenerator.js @develop (generators used verbatim) |
| tb-art.jsx | React wrapper over TeamGeneratedArt / TeamCourtGenerator @develop |
| FrontEnd/static/js/shared/teamGeneratedArt.js | copied verbatim @develop |
| FrontEnd/static/js/shared/teamCourtGenerator.js | copied verbatim @develop |
| Team Builder - Build Mode Gate.html | new — brief §3.3 (no shipped source read) |
| Team Builder - Roster Screen.html | new — brief §3.2/§3.3/§4.5 (no shipped source read) |
| Team Builder - Review.html | brief §4.6 + teamGeneratedArt/teamCourtGenerator @develop |
| FrontEnd/static/mode-select.html | FrontEnd/static/mode-select.html @develop |
| FrontEnd/static/mode-select.css | FrontEnd/static/mode-select.css @develop |
| Mode Select Redesign.html (preview) | markup mirrored from FrontEnd/static/mode-select.js injection |

## Sync history
### 2026-07-26T15:13:42Z
- Redesigned mode-select ("Coach's Home Base"): My Franchises + Find A Game as co-equal heroes.
- Franchise slots stacked vertically; cards compacted (Rank + Prestige chips suppressed).
- Leaderboard / Around The League / Community Highlights restyled as supporting tiers.
- Added `Mode Select Redesign.html`; copied two team banner JPGs + `images/buttons/whiteball.svg`.
