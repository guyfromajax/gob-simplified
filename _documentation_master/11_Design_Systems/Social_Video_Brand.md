# GOB Brand Book: Social & Video Chapter

**Status:** v2.4.1. **Section 1 (Thumbnails) LOCKED, v2.3 + v2.4/v2.4.1 clarifications.** **Section 2: Draft v2.4.1, ready for template build.** **Section 3: draft outline**, for Jamie's review via Lobot · **Owner:** Princess Leia (Marketing) · **Executes:** Chewbacca (social/video) · **Date:** Oct 1, 2026
**Inputs:** `gob-brand/thumbnail-best-practices.md` (approved brief: 10 principles, 3 formulas, rubric, Test & Compare plan) · `styleguide.md` (in-game style guide) · `gob-brand/UX_System.md` (colour law, token names) · `gob-brand/originals/*.png` (3 old thumbnails that scored 16–19/30) · `gob-brand/gob_icon_square.png` (official square mark) · `gob-brand/gob_logo_wordmark.png` (full wordmark)
**Builds on:** the in-game style guide and UX_System colour law. Colors are given as `token` + hex so the brand stays in sync with the game. **Token note:** `gob-tokens.css` is not on the box (I searched all of `/workspace` and the filesystem). Token names come from `UX_System.md`, and hex values for tokens that UX_System doesn't spell out come from `styleguide.md`. Verify both against `FrontEnd/static/css/gob-tokens.css` when it's available.

> **Positioning:** The deep basketball management sim for hardcore sports sim gamers left behind by mainstream sports games. **Tagline:** Build Your Basketball Dynasty.
> **Voice (binding):** a smart scout. Authentic, specific and challenging. Uses scout-report phrasing. No hype, no drama, no exclamation marks. **The game leads.** Jamie is founder access, not the headline.

### Changelog: v2.4 → v2.4.1 (Oct 1, 2026): clarifications from the remaining template conflicts
1. **Glance test (#1):** **168×94 is the publish gate.** 160×90 and 320×180 are exported as references only (§1.4, §1.7).
2. **Scout's Report text (#6):** auto-fit from 140px down to 112px is approved, and the hero text box may extend down to **y≤672**, staying out of the timestamp no-go (F2).
3. **Milestone Jamie (#9):** **no Jamie by default.** If he's used: (936,152)–(1232,424), clear of the headline and the date bar (F3).
4. **Full-bleed game screen (#10):** new layer **`53_BG_gamescreen`** directly under `50_BG_ramp`. The ramp runs **down** on Dev Diary and Milestone, and **right** on Scout's Report (§1.4, §1.9).
5. **Layers (#13):** `GOB_LT_System` reuses `10_TXT_name` (no role line). `GOB_TC_Open_Milestone` has no chip, so `10_TXT_chip` is removed from its list (§2.1, §2.2).
6. **End screens (#14):** the Shorts end is the wordmark plus the CTA only (no tagline or subline). New layer **`43_BG_freeze-blur`** in all end-screen templates (§2.5).
7. **Arrows (#15):** ▲ ▼ → are set in **Inter Bold 64px**, because Bebas Neue Pro has no arrow glyphs (§2.4).
8. **Callouts (#16):** `GOB_CO_Bracket`, `GOB_CO_Stat`, `GOB_CO_Grade` and `GOB_FX_ZoomDim` take a **`series` parameter, default Scout's Report**, which sets the accent (§2.4).
9. **Shared keyword:** the Milestone **date bar is exempt** from the §1.6 no-shared-keyword rule, though video titles should preferably leave the date out (§1.6, F3).
10. **Sources and files (#17–#19):** this chapter supersedes the older thumbnail docs (`yt-thumb-system/GOB_YT_Thumbnail_System.md`, brief §(c) layouts). The **SVG is the master file**; PSDs are previews (§1.9).

### Changelog: v2.3 → v2.4 (Oct 1, 2026): v2.4 clarifications
*These come from Chewbacca's template build (`templates/SPEC_NOTES.md`). Decided under Jamie's delegated authority. Section 1 stays locked; these are clarifications, not changes to the system.*
1. **Corner mark vs logo:** the rule is *no corner mark*, not *no logo*. The full wordmark may be the hero image on Milestone thumbnails (§1.2a, F3).
2. **Wordmark:** always used unaltered, orange ball included, on every format. Never recolor or edit it, and it doesn't count as a format accent (§1.2a, §1.3, §2.0).
3. **Scout's Report hero panel:** wireframe corrected to **(48,120)–(656,672) = 36.4%** of the frame, which meets the ≥36% rule and matches `TPL_SR`. The old drawn box was 33.9%.
4. **Layer order:** stacking now keeps content visible, matching Chewbacca's SVGs. `41_ART_callout` sits above `40_ART_ui-crop`, and `21_TXT_cta` sits above `20_CTA_plate_green`. Layer numbers are names, not stack positions (§1.9, §2.5).
5. **Scout's Report Jamie test variant:** ≤20% of the frame, pushed to the right edge. The text column keeps its full width (688–1232). Shoulders may enter the timestamp box; the face may not (F2).
6. **Milestone copy:** the gold bar holds **the date only, ≤12 characters** (e.g. `FEB 2027`), and doesn't count toward the 4-word limit. The headline is the benefit (e.g. `PLAY IT FIRST`) and never repeats the video title. The F3 wireframe, examples and the §1.6 pairing row are updated.
7. **Gold top rule:** optional, full width at the very top of the frame, **(0,0)–(1280,2)**, in `--reward-gold` (F3).
8. **Section 2 type scale:** added **Display XS 48px** (chapter tag) and **Display L 96px** (Milestone label bar). The 144px stat/grade role is renamed **Display Stat** to keep the names unique (§2.0, §2.4).
9. **MOGRT:** none for now. SVG/PSD plus the spec are the deliverable, to be revisited once Section 3 picks the editing tool (§2.0).
10. **`GOB_TC_Chapter` layers:** `00_GUIDES_noexport` · `10_GFX_plate` · `11_GFX_accent-bar` · `12_TXT_chapter` (§2.1).
11. **X end card (`GOB_ES_X_16x9`):** centered both horizontally and vertically (§2.5).
12. **Dev Diary:** no secondary line (F1). The §1.4 secondary-line row now applies to Scout's Report and Milestone only.

### Changelog: v2.2 → v2.3 (Oct 1, 2026)
- **Corner mark: NONE (locked by Jamie).** Thumbnails have no corner mark. The series chip sits at (48,48)–(~300,88) on every thumbnail. The "pending" language, the mark slot in the wireframes, checklist and layer names, and the separate logo-is-hero rule (now covered by the general rule) are all removed.
  - Concepts A/B/C moved to `marks/_parked/`. They're parked and not for use.
- **Grades:** the UX_System RT scale is the source of truth: A `--lblue`, **B `--green`**, C #FFD700, D/F `--red`. The orange B came from a pre-overhaul screenshot.
  - New hard rule H8 (+ §1.4, §2.4): never use pre-overhaul captures that show off-scale grade colors. Recapture from the current build.
  - The §2.4 stat-callout mockup is flagged for recapture because its source frame is that pre-overhaul capture.
- **End-screen CTA:** default `WISHLIST ON STEAM`. During Next Fest and other demo events it becomes `PLAY THE DEMO`, with the same spec and the same `--green`.
- Open questions are resolved and removed. Only the Section 3 items remain.
- **Section 1 locked again at v2.3. Section 2 marked Draft v2.3, ready for template build.**

### Changelog: v2.1 → v2.2 (Oct 1, 2026)
- **Corner mark (Section 1, pending Jamie):** the square app icon is **out of the thumbnail corner** because Jamie finds it distracting there. It stays the social avatar, favicon and desktop app icon.
  - The corner now gets either a square "GOB" mark (concepts A/B/C in `marks/`, recomposed from wordmark glyphs) or nothing. **Recommended default: no mark**, since none of the concepts reads at 168×94 (`tests/gob-mark/`).
  - With no mark, the series chip sits at (48,48). With a mark, it stays at x=144 next to the mark.
  - Wireframes, 1.2a, 1.7, 1.9 and the Milestone formula are updated. This is the only change to locked Section 1.
- **Logo-is-hero rule (Jamie):** when the full wordmark is the thumbnail hero (most Milestones), the corner stays **empty** and the chip moves to x=48. Added to §1.2a and the Milestone formula.
- **Section 2 written in full** (draft): global system, title and chapter cards, lower thirds, captions (16:9 + Shorts safe zones), zoom/ring and stat callouts, end screens, and a checklist. Mockups are in `tests/section2/`. Four of the six outline questions are resolved in the spec (cold open + card, Jamie's title, Shorts emphasis, no count-up, ring color, no Steam capsule).
- Section 3 Shorts safe box aligned to §2.3. Section 3 is otherwise unchanged (outline).

### Changelog: v2 → v2.1 (Oct 1, 2026)
- **Milestone gold APPROVED:** `--reward-gold` #F0C560 is final. The warning flag and its open question are removed. Added a one-off Test & Compare on the first Milestone video, gold vs #FFD700 (§1.7, step 7).
- **App icon:** use the full square icon at every size, 16 and 32px included (Jamie already uses it as the favicon). Removed all wording about a simplified small-size version, and removed that open question.
- **Section 1 LOCKED at v2.1.** Sections 2 and 3 stay draft outlines.

### Changelog: v1 → v2 (Oct 1, 2026)
- **Grades:** the in-game RT scale is now the rule everywhere (A `--lblue` #4A90D9, B `--green` #34EC27, C #FFD700, D/F `--red` #ff6d6d). The brief's "green = elite" wording is removed. Added a rule for when an A-grade hero shares the Scout's Report accent color (§1.3).
- **Series accents LOCKED** (Jamie): Dev Diary orange, Scout's Report light blue, Milestone gold. Green is for the CTA and real game data only.
- **Milestone accent changed from #FFD700 to `--reward-gold` #F0C560.** This is the color the game uses for milestones and rewards, so thumbnails now match the in-game milestone modal. Contrast is 11.9:1 on `--bg` (passes 7:1). The label bar is now solid gold and the orange→yellow gradient is gone. #FFD700 is kept only for native C grades. (Approved by Jamie in v2.1.)
- **Colour law alignment:** added token names next to every hex, plus a "never contradict the game" rule for navy, green and orange (§1.3).
- **Brand marks:** the official square mark (`gob_icon_square.png`) is now the thumbnail corner mark at 80×80 px, (48,40)–(128,120), with a 2px white outline. It's also the social avatar and the desktop app icon. The full wordmark is for wide placements only. I tested both at 168×94 (§1.2a), and the wordmark doesn't read at that size. Added an app-icon export note. The v1 "56px orange GOB tile" is gone, and the wireframes are updated.
- **Screen rules made generic** ("any data table / player card"). Stats, Standings and Leaders pages are cleared for marketing as they are.
- **LOCKED:** game footage is ≥60% of Dev Diary runtime, and Jamie never appears in Scout's Report except as a test variant.
- Open questions: 5 resolved and removed, 2 new (both resolved in v2.1).

---

## Section 1: Thumbnails (full spec)

> **LOCKED, v2.3 (Oct 1, 2026), with v2.4 and v2.4.1 clarifications** (see changelog). **Sources:** this chapter supersedes the older thumbnail docs (`yt-thumb-system/GOB_YT_Thumbnail_System.md` and the brief's §(c) layouts). The brief's principles, rubric and Test & Compare plan still apply. Changes need Jamie's sign-off via Lobot. The one exception is the scheduled Milestone color test in §1.7, step 7.

### 1.1 Hard rules (fail any one and the thumbnail doesn't ship)

| # | Rule |
|---|---|
| H1 | 1280×720, 16:9, sRGB, PNG/JPG under 2 MB. Never 3:2. |
| H2 | No AI-generated people, crowds, arenas or props. Use only real game screens, real Jamie, fictional-universe game assets (Coach Sammy, team banners, crests), and official GOB brand marks. |
| H3 | No NBA marks, real players or teams, real brand or apparel logos, and no licensed-looking player renders. |
| H4 | Never use `!`. Use `?` at most once. No ALL-CAPS hype words (HUGE, INSANE, BROKEN!!, NEW!). |
| H5 | 0–4 words of thumbnail text, with **3 as the target** (brief, principle 4). The text must not repeat the video title (§1.6). |
| H6 | Nothing important goes inside the no-go boxes in §1.2. |
| H7 | Every grade, number or screen shown must appear in the video, ideally in the first 60 seconds (brief, principle 2). |
| H8 | **No pre-overhaul captures that show off-scale grade colors** (e.g. an orange B). Grades must match the UX_System RT scale. Recapture from the current build. |
| H9 | **No corner mark.** Brand recognition comes from the series chip, `--bg`, Bebas and the layout. |

### 1.2 Canvas, grid, safe zones

All coordinates are in px on the 1280×720 canvas, written as (x1,y1)–(x2,y2), with the origin at top-left.

```
(0,0)                                                              (1280,0)
 ┌──────────────────────────────────────────────────────┬───────────┐
 │ [SERIES CHIP] (48,48)-(~300,88)   no corner mark     │ HOVER     │
 │                                                      │ (1120,0)– │
 │                                                      │ (1280,140)│
 │       ┊ thirds x=427       ┊ thirds x=853            │           │
 │ ┄┄┄┄┄┄┼┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┼┄┄┄┄┄┄┄┄┄┄┄┄ y=240         └───────────┤
 │       ┊   LIVE AREA        ┊                                      │
 │       ┊ (48,40)–(1232,672) ┊                                      │
 │ ┄┄┄┄┄┄┼┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┼┄┄┄┄┄┄┄┄┄┄┄┄ y=480                      │
 │       ┊                    ┊                    ┌─────────────────┤
 │                                                 │ TIMESTAMP NO-GO │
 │                                                 │(1040,600)–      │
 ├─────────────────────────────────────────────────┤ (1280,720)      │
 │ PROGRESS-BAR STRIP (0,688)–(1280,720): no text  │                 │
 └─────────────────────────────────────────────────┴─────────────────┘
```

| Zone | Box | Rule |
|---|---|---|
| Live area | (48,40)–(1232,672) | All text, the series chip and focal points go inside this. Margins are 48 left/right, 40 top, 48 bottom. |
| **Timestamp no-go** | **(1040,600)–(1280,720)** | YouTube's duration badge sits here. Only background, or Jamie's shoulders and torso, can enter this box. Never text, faces, grades or hands. |
| Progress-bar strip | (0,688)–(1280,720) | The red watched-progress bar covers this. No text. |
| Hover-icon zone | (1120,0)–(1280,140) | Desktop hover icons (Watch later / Queue) cover this. Nothing critical. |
| Grid | 12 columns, 84px each, 16px gutters, inside the live area | Snap panels and text blocks to columns. Place focal points on the thirds lines (x=427/853, y=240/480). |

### 1.2a Brand marks

| Asset | File | Use |
|---|---|---|
| **Official square icon** (illustrated player peering over a basketball, on a blue gradient) | `gob_icon_square.png` (1024²) | Social avatars (already live on X, Facebook, YouTube and TikTok), the favicon, and the **desktop app icon** (replacing the default Electron icon). **Never in thumbnails** |
| **Full wordmark** (GEEKED-OUT BASKETBALL) | `gob_logo_wordmark.png` (1261×449) | Wide placements only: end cards, title cards, banners, channel art, and the hero of a Milestone thumbnail. Minimum width 480px on a 1920 frame. **Always unaltered, orange ball included, on every format** (v2.4). Never recolor, crop or edit it. It doesn't count as a format accent |

*Parked: square "GOB" concepts A/B/C are in `marks/_parked/`. Not for use.*

**Corner rule (LOCKED, v2.3): thumbnails have no corner mark.** The top-left holds only the series chip at **(48,48)–(~300,88)**: 40px tall, 12px radius, 16px horizontal padding, Inter Bold 26px uppercase, +1px tracking. That applies to every formula, including thumbnails where the wordmark is the hero. **No corner mark ≠ no logo** (v2.4): the full wordmark may be the hero image of a Milestone thumbnail. It's just never a corner mark. Brand recognition comes from the locked system: the chip color, `--bg`, Bebas and the layout, which is exactly what rubric criterion 5 ("would someone know it's GOB with the logo covered?") asks for.

**Legibility tests (history; why there's no corner mark)** (renders in `gob-brand/tests/` and `tests/gob-mark/`):

| Test | Result |
|---|---|
| Wordmark at 200px wide → 168×94 | **Doesn't read.** It shrinks to 26×9 px, a grey band with an orange dot. |
| Square icon at 80px → 168×94 (v2) | Read as a blue-and-orange avatar square. Retired from the corner in v2.2. |
| **GOB concepts A/B/C (parked) vs no mark** on the three test thumbnails → 168×94 and 320×180 (`gob_mark_comparison_full.png`, `gob_mark_comparison_168.png`, `gob_mark_corner_zoom_168.png`) | **None of the three reads as "GOB" at 168×94.** The letters are about 3px wide. **A** is a white smudge in a dark box. **B** is the most distinctive (an orange dot between white blobs) but still not legible. **C** reads as a blue tile, which is too close to the old icon. **No mark** is the cleanest, and the colored series chip carries recognition by itself. At 320×180 all three are legible, with B best. |

**App icon note:**
- Export from the 1024 master to 512/256/128/64/32/16 px.
- macOS gets `.icns` (with @2x pairs), Windows gets `.ico` (16/32/48/256 layers), and Linux gets `.png` (512 and 256). Place them in `desktop/build/icon.icns` / `icon.ico` per UX_System so the build stops falling back to the default Electron icon.
- **Use the full square icon at every size, 16 and 32px included.** There's no simplified small-size version. Jamie already uses the full icon as the favicon and it works. (In the test render `icon_appsizes_64-32-16.png`, the expression fades below 64px but the blue-over-orange icon stays recognizable.)

### 1.3 Color roles (marketing)

Jamie's decision is that marketing is **free of the game's color meanings**, apart from the guardrail below. Marketing uses **one fixed accent per series (LOCKED) plus shared neutrals.** At most 2 *added* accent colors per thumbnail (brief). The unaltered wordmark doesn't count toward that either (v2.4). Colors native to a cropped game screen don't count, but crop tightly so the screen doesn't bring in a rainbow.

**Guardrail (colour law):** marketing never uses navy, green or orange in a way that contradicts what players see on game screens.
- Navy (`--you`) never marks something that isn't the player's.
- Green (`--green`) never sits on a negative stat, a loss, or a fake button.
- Orange (`--orange`) never fakes a "saved" or "committed" state inside a UI crop.
- Never recolor pixels inside a real screen. Callouts sit on top of the screen as separate graphics.

| Role | Token · hex | Contrast on `--bg` | Use |
|---|---|---|---|
| Base | `--bg` · #0b0d14 | n/a | Every background starts here |
| Panel surface | `--surface-2` (styleguide value `rgba(14,16,24,0.96)`), border `--line`, radius 24px | n/a | Frame around a UI crop |
| Primary text | `--text-100` · #FFFFFF | 19.4:1 | Default hero text |
| Secondary text | `--text-60` (60% white) | ≈7:1 | Small sub-labels only |
| **Dev Diary accent (LOCKED)** | `--orange` · #F79420 | 8.5:1 | Series chip, underline, hand-drawn circle, rim light |
| **Scout's Report accent (LOCKED)** | `--lblue` · #4A90D9 | 5.8:1 | Series chip (with `--bg` text), callout rings and brackets. **Never hero text** (below 7:1). In the game, blue means RT, which fits a ratings series |
| **Milestone accent (LOCKED)** | `--reward-gold` · #F0C560 | **11.9:1** | Solid label bar, dates and numbers. Matches the in-game milestone modal |
| Atmosphere | `--you` / `--navy` · #27408E | 2.0:1 | Background glow or court-line texture at ≤20% opacity. Never text, never a fill behind text, never a highlight on a specific row or player |
| **Green** | `--green` · #34EC27 | 12.2:1 | **CTA plus real game data only.** In video it's the Wishlist / Play Demo CTA (§2). In thumbnails it only appears as native data (e.g. a B grade). Never an accent, background or decoration. Max 1 per frame |
| Red | `--red` · #ff6d6d | 7.1:1 | Native data only (D/F grades, red tiles). Never decorative |
| C-grade yellow | #FFD700 (no token named in UX_System) | 13.8:1 | **Only** for a native or rebuilt C/C+ grade |

**Grades always use the in-game RT scale:** A++/A+/A `--lblue` #4A90D9 · B+/B `--green` #34EC27 · C+/C #FFD700 · D/F `--red` #ff6d6d.

**A-grade hero in a Scout's Report** (same blue as the accent):
- Put the grade on its own `--bg` near-black panel, with at least 24px clear of the blue chip.
- Switch that thumbnail's callout rings to `--text-100` white, so the only blue on the canvas is the chip and the grade.
- No outline on the grade.

**Contrast rules:**
- Hero text needs ≥7:1 against its immediate background. `--text-100`, `--reward-gold` and `--orange` on `--bg` all pass.
- `--bg` text on an orange or gold fill is allowed (8.5:1 and 11.9:1).
- White on orange (2.3:1), white on light blue (3.3:1) and white on gold (1.6:1) are banned.

### 1.4 Type, stroke, background, UI crops

| Element | Font | Size @1280w | Notes |
|---|---|---|---|
| Hero text | Bebas Neue Pro Bold | **140px** (min 112, max 180) | Tracking +1px. 1–2 lines, line-height 0.9. Upright, never italic or skewed |
| Hero number or grade | Bebas Neue Pro Bold | **320–420px** | Scout's Report and Milestone. Rebuild the grade as live type in its exact RT color, matching a value on the real screen |
| Secondary line | Bebas Neue Pro Bold | 64–80px | Optional, **Scout's Report and Milestone only** (Dev Diary has none, v2.4). Counts toward the 4-word limit. The Milestone date bar doesn't |
| Series chip | Inter Bold | 26px | Uppercase, +1px tracking. This is the only place Inter appears |
| Absolute minimum | n/a | 64px for anything the viewer needs to read | At 168px wide, 140px type shows at about 18px and 64px at about 8px |

- **Stroke/shadow:** by default there's no stroke. Use one soft shadow: `0 6px 24px rgba(11,13,20,0.80)`. If text sits on a busy screen, either add a 6px outside stroke in `--bg` or put it on a `--bg` bar at 85% opacity. No bevels, chrome, gradient-filled text, glows, flames, sparks or brush strokes. All of those appear in the originals.
- **Background:** `--bg` base. An optional full-bleed game screen (layer `53_BG_gamescreen`) sits directly under a darkening ramp, `linear-gradient(to <direction>, rgba(11,13,20,0.15) 0%, rgba(11,13,20,0.95) 80%)`. The ramp runs **down** on Dev Diary and Milestone, and **right** (toward the text) on Scout's Report (v2.4.1). An optional diagonal band texture (132°, 1px line every 104px, 3% white) echoes the in-game shell. No stadium lights, lens flares or bokeh.
- **Cropping game UI so it reads small** (applies to any screen, including stats, standings and leaders pages as they ship today):
  1. Capture at 2560×1440 or 4K, then crop **one element**: any player card, any grade, any attribute row, or a 3–5 row section of any data table. Never the full screen.
  2. Scale so in-game body text ends up at **≥28px**, and the number that carries the hook at **≥96px**.
  3. Show it flat and front-on. No monitor or desk mockups and no perspective tilt (`new_features.png` put real UI on a fake angled monitor, so it turned to mush at 168px).
  4. Frame it in the panel surface (24px radius, 1px border). At most 1 callout per crop: a series-accent (or white) ring or bracket, 8px stroke.
  5. Use fictional teams and [Player Name]-style data only. Blur or swap anything that's debug or unfinished.
  6. Capture only from the current build. Never use pre-overhaul captures that show off-scale grade colors (H8).
  - *Screen rules will be revisited after the UX overhaul.*
- **Mobile legibility test (mandatory):** **168×94 is the publish gate** (v2.4.1). At 168, the subject and the hook must read in about 1 second, which is rubric criterion 1. **160×90** (the brief's size) and **320×180** are exported as references only; at 320, every word should read.

### 1.5 The three formulas

#### Formula 1: DEV DIARY (founder + the game)
**Purpose:** show the build honestly and earn trust through founder access. **Use for:** design decisions, cuts, before/after, "why we built it this way." **Chip:** `DEV DIARY #07` on `--orange`.

```
(0,0)                                                    (1280,0)
 ┌─────────────────────────────────────────────────────────┐
 │[DEV DIARY #07] chip (48,48)-(~300,88)                   │
 │ ┌───────────────────────────────────┐                   │
 │ │ GAME ARTIFACT (one UI element or  │      JAMIE        │
 │ │ before/after split)               │   (880,180)-      │
 │ │ (48,136)-(800,536)  752x400       │   (1280,720)      │
 │ │                     ◯ orange ring │   head ≤216px tall│
 │ └───────────────────────────────────┘   face y<560      │
 │ HERO TEXT 140px  (48,552)-(800,672)       looks/points ◄│
 │                                          ┌──────────────┤
 │                                          │ no-go        │
 └──────────────────────────────────────────┴──────────────┘
```
- **Text:** 1–3 words that name the *stake or problem*, not the topic. White, with an optional single orange word. **One hero line only: Dev Diary has no secondary line** (v2.4).
  - Good: `WE CUT IT` · `TOO EASY?` · `V1 VS V2` · `WRONG CALL` · `STILL NOT RIGHT`
  - Bad → fixed: `NEW FEATURES!` → `WHAT CHANGED` (and the title names the feature)
- **Image:** one real artifact from the build. A before/after split is fine as long as each half stays at least 368px wide.
- **Face rule:** real Jamie only, in the right third, chest-up.
  - **His figure takes ≤25% of frame area (hard cap 30%) and his head is ≤30% of frame height.**
  - The game artifact must be **≥1.5× Jamie's area** and is the highest-contrast element.
  - Natural mid-explanation expression: mouth slightly open, pointing, skeptical brow. No shock face, no open-mouth gasp, no pointing at the camera.
  - His eyeline or hand points *at the artifact*.
  - Use an orange rim light or plain background, and cut him out cleanly (no glow outline).
- **Runtime (LOCKED):** game footage is ≥60% of every Dev Diary.
- **Do:** pull frames from the actual recording.
- **Don't:** let the face be the biggest element · use a cutout without a game screen · use an exclamation, emoji or red arrow.

#### Formula 2: SCOUT'S REPORT (systems, players, ratings, stat callout)
**Purpose:** prove depth by giving the viewer a call they can check against their own judgment. **Use for:** system breakdowns, player and ratings deep dives, recruiting reads, stat callouts. **Chip:** `SCOUT'S REPORT` in `--lblue` with `--bg` text (episode number optional).

```
 ┌─────────────────────────────────────────────────────────┐
 │[SCOUT'S REPORT] chip (48,48)-(~330,88)                  │
 │ ┌──────────────────────────┐   ┌──────────────────────┐ │
 │ │ HERO GRADE / CARD        │   │ CONTEXT STRIP: real  │ │
 │ │ on --bg panel            │   │ UI (attribute row,   │ │
 │ │ (48,120)-(656,672)       │   │ stat line, banner)   │ │
 │ │ 608x552 = 36.4% of frame │   │ (688,152)-(1232,400) │ │
 │ │ grade type 320-420px     │   └──────────────────────┘ │
 │ │                          │   HERO TEXT 140→112px fit  │
 │ │                          │   (688,424)-(1232,≤672)    │
 │ └──────────────────────────┘             ┌──────────────┤
 │                                          │ no-go        │
 └──────────────────────────────────────────┴──────────────┘
```
- **Text:** 0–3 words, phrased as a scouting verdict or challenge. The grade often *is* the text. **Auto-fit (v2.4.1):** 140px on one line, shrinking to 112px. If it still doesn't fit, break to 2 lines; the box may extend to y≤672 but never into the timestamp no-go.
  - Good: `OVERRATED` · `TRUST THE C+` · `A++ AS A JH?` · `READ THE TILES` · `SELL HIGH`
  - Bad → fixed: `RECRUITING!` → `IGNORE THE A` (the title explains which recruit signals matter)
- **Image:** one hero object that reads at 168px: a letter grade, any player card, or any row of attribute tiles. Add a fictional team banner or crest as the niche signal (it does the job that licensed faces do for 2K channels). `--you` court-line texture at ≤20% is allowed behind it. If the grade is an A, follow the A-grade rule in §1.3.
- **Face rule (LOCKED):** **Jamie never appears in Scout's Report, except as a Test & Compare variant** (brief, test 1 face vs no face). The variant replaces the context strip with a Jamie cutout of **≤20% of frame area** (measured on the cutout's pixels), **pushed to the right edge** and bleeding off it, within (960,152)–(1280,720). **The text column keeps its full width (688–1232)** and sits above him. His head stays in the top part, above the hero text and never behind it. **Shoulders may enter the timestamp box (1040,600)–(1280,720); his face may not** (v2.4). Coach Sammy can stand in (brief, test 4). Video runtime follows the same rule (§3).
- **Do:** state a verdict the video defends.
- **Don't:** recolor grades for drama · show a grade the video never shows · stack more than one grade.

#### Formula 3: MILESTONE (launch, Next Fest Feb 2027, alpha, wishlists, patch)
**Purpose:** state a fact and make it look different in the subscription feed. **Use for:** release date, Steam Next Fest (Feb 2027), alpha access, wishlist milestones, patch drops. **Chip:** `MILESTONE` on `--reward-gold` with `--bg` text. This is the one formula that intentionally breaks the template.

```
 ════════ optional gold top rule (0,0)-(1280,2) ═════════════
 ┌─────────────────────────────────────────────────────────┐
 │[MILESTONE] chip (48,48)-(~250,88)                       │
 │            ┌──────────────────────────────┐             │
 │            │ HERO: wordmark / key art /   │             │
 │            │ Coach Sammy / real screen    │             │
 │            │ (400,112)-(880,424) centered │             │
 │            └──────────────────────────────┘             │
 │      HEADLINE (benefit) 140px --text-100, centered      │
 │      (160,440)-(1120,576), ≤4 words                     │
 │              ┌──────────────────────┐                   │
 │              │ DATE BAR (440,592)-  │ --reward-gold,    │
 │              │ (840,664), ≤12 chars │ 60px --bg text    │
 │              └──────────────────────┘                   │
 │                                          ┌──────────────┤
 │                                          │ no-go        │
 └──────────────────────────────────────────┴──────────────┘
```
- **Text (v2.4):**
  - **Headline = the benefit**, 1–4 words, Bebas 140px `--text-100`, centered. It **never repeats the video title**.
  - **Gold bar = the date only**, ≤12 characters, Bebas 60px in `--bg` on solid `--reward-gold`. The bar is auto width, centered, max 400px, and **doesn't count toward the 4-word limit**.
  - Good: `PLAY IT FIRST` + `FEB 2027` · `TRY IT EARLY` + `[MON YYYY]` · `WHAT'S FIXED` + `[MON YYYY]` · `YOUR DYNASTY STARTS` + `MARCH 2027`
  - Bad → fixed: `HUGE NEWS!!!` / `STEAM NEXT FEST · FEB 2027` → headline `PLAY IT FIRST`, bar `FEB 2027`
- **Image:** the full wordmark, official key art, Coach Sammy (generic white uniform or a fictional team's uniform), or one real hero screen. A radial `--you` glow at ≤20% is allowed behind it. An optional **gold top rule, full width at the very top of the frame, (0,0)–(1280,2), in `--reward-gold`**, echoes the in-game milestone modal (v2.4).
- **Face rule:** **no Jamie by default** (v2.4.1). If he's used: a candid still ≤20% of the frame at **(936,152)–(1232,424)**, clear of the headline and the date bar, never centered and never the hero.
- **Do:** lead with the benefit · put the date in the gold bar.
- **Don't:** use countdown hype, confetti, or "FINALLY". Don't use this formula for anything other than a real milestone.

**Cadence (brief):** 70% of uploads use the fixed template. Every milestone, plus about 1 in 4 videos, is a deliberate experiment.

### 1.6 Title/thumbnail pairing

The thumbnail **shows** and the title **tells**. They must not share a keyword. The Milestone date bar is exempt (v2.4.1), but titles should preferably leave the date out. Together they should pose one honest question that the first minute answers. Titles front-load keywords, and the series and episode go at the end.

| Video title | Thumbnail text | Why it works |
|---|---|---|
| Why we rebuilt [System] from scratch · Dev Diary #07 | `WE CUT IT` | The title gives the topic and the thumbnail gives the stake |
| How to read a JH recruit's attribute tiles · Scout's Report | `IGNORE THE A` | A challenge the viewer can test |
| [Player Name]: the [Position] every save overrates · Scout's Report | `OVERRATED` + grade | A verdict, with evidence inside |
| GOB is in Steam Next Fest | `PLAY IT FIRST` + bar `FEB 2027` | The headline adds the benefit, and the date sits only in the bar |
| ✗ Practice Squads Explained | ✗ `PRACTICE SQUADS!` | Repeats the title and uses `!` |

### 1.7 Production checklist (Chewbacca, every upload)

1. Pick the formula and write **3 thumbnail concepts and 10 titles** (brief, principle 10).
2. Pull real frames: game captures at 2560×1440 or higher, and Jamie stills from the shoot.
3. Build from the template (§1.9). Check H1–H9, the no-go boxes, the chip position (48,48) with no corner mark (H9), current-build captures only (H8), the accent count, the colour-law guardrail and contrast.
4. Export at 1280×720, then run the **168×94 publish gate** on a dark and a light YouTube mock. Also export 160×90 and 320×180 as references.
5. **Score with the brief's rubric** (§d: glance, focal point, text economy, honest curiosity gap, brand recognition, niche signal; 1–5 each, /30).

| Gate | Requirement |
|---|---|
| **Publish (Variant A)** | **≥24/30**, with no criterion below 3 and Glance ≥4 |
| Test variants B/C | ≥21/30 and they pass every hard rule. A is the default when a test is inconclusive, so A must be the safest on-brand option |
| <24 on A | Rework it. Don't publish a 18–23 as A |

6. **Test & Compare** (brief §e): load 2–3 *clearly different* variants on long-form uploads, one hypothesis per video, in this order: face vs no face → 0 vs 3 words → grade vs UI hero → Sammy vs Jamie → orange vs gold. Don't edit the title or thumbnail mid-test. Log each test in one row (hypothesis, variants, result, watch-time split, days). After 3 inconclusive results on the same variable, stop testing it. Check against Steam wishlist adds through the tracked link that goes first in the description. Refresh back-catalog videos that score below 18.
7. **Milestone color test (one-off, first Milestone video):** run a Test & Compare of Variant A, `--reward-gold` #F0C560 (the default), against Variant B, #FFD700. Everything else stays pixel-identical: art, text, layout and title. Only the label bar, the chip and the gold dates change. If #FFD700 **clearly wins** on watch-time share (result type "Winner"), switch the Milestone accent to #FFD700 for all future Milestones and log the result in the test log and in this doc's changelog. If the result is "Performed Same" or "Inconclusive", keep reward gold. A single-variable test may come back inconclusive because YouTube favors clearly different variants; if it does, that settles it in favor of reward gold.

### 1.8 Before → after (the originals)

All three break hard rules H1–H4, and each uses a different palette (electric blue, red/black, warm gold), so the channel grid reads as three different brands.

| Original | What's wrong (observed) | Redo |
|---|---|---|
| `new_features.png` (1536×1024, 3:2) | `NEW FEATURES!` in slanted chrome-white with an orange `!`. Real-looking match UI (box score, court, "REBOUND!" popup) set on an AI-rendered angled monitor, with a stadium-light glow, a basketball, a mug and a keyboard. At 168px the UI is noise. Electric-blue palette. Topic, no promise. | **Milestone (patch)** if it's a patch: one flat, cropped element showing the biggest change, with the gold label bar `PATCH [X.Y]` and the title listing the changes. Or **Dev Diary**: Jamie on the right pointing at the one feature, with `WHAT CHANGED`. |
| `practice_squads.png` (1672×941) | An AI stock "coach" in a red cap with a pirate-skull crest, smiling at nothing, holding a clipboard. AI-generated players in "DEVILS" jerseys, and a "HOME OF THE DEVILS" scoreboard. Italic brush type `Practice Squads!` on a red brush stroke. Red-dominant palette. No game UI. | **Dev Diary:** real Jamie at ≤25% on the right, mid-explanation. On the left, a real roster data table showing the practice squad, cropped to 3–4 rows with attribute tiles at ≥28px. Text: `WHY IT EXISTS`. Orange chip `DEV DIARY #[NN]`. |
| `recruiting.png` (1536×1024, 3:2) | Two AI stock men shaking hands at a signing table, with a **Nike swoosh** on the coach's polo (implies real-brand or licensing ties), a "STERLING KNIGHTS" hoodie, Knights and "BULLDOGS" caps, an AI crowd and lens flares. `RECRUITING!` in beveled yellow-orange with sparks. Reads as a sports-drama poster, not a sim. | **Scout's Report:** a huge recruit grade (e.g. `A` in `--lblue`, 380px, on a `--bg` panel, with white callout rings per the A-grade rule) on the left, a context strip on the right with that recruit's attribute tiles plus a fictional team crest, and the text `IGNORE THE A`. Light-blue chip. Title: "How to read a recruit beyond the grade · Scout's Report". |

### 1.9 File naming & template handoff

- **File:** `GOB_YT_{DD|SR|MS}_{ep##}_{slug}_v{A|B|C}_{YYYYMMDD}.png`, e.g. `GOB_YT_SR_03_ignore-the-a_vA_20261015.png`. Finals go in `/workspace/gob-brand/thumbs-final/`, and Test & Compare variants plus the log go in `/workspace/gob-brand/thumb-tests/`.
- **Templates:** one Figma frame or PSD per formula (`TPL_DD`, `TPL_SR`, `TPL_MS`). Stacking order from top to bottom (v2.4, matches `templates/thumbnails/*.svg`): `00_GUIDES_noexport` (grid, thirds, no-go boxes in 50% magenta) · `10_BRAND_chip` (locked at (48,48)) · `20_TEXT_hero` · `21_TEXT_sub` (SR/MS only) · `30_FACE_jamie` · **`41_ART_callout` · `40_ART_ui-crop`** (callout above the screenshot) · `50_BG_ramp` · **`53_BG_gamescreen`** (optional full-bleed screen, directly under the ramp, v2.4.1) · `51_BG_texture` · `52_BG_base_bg` (locked). Only text, face, art and game-screen layers get edited. Keep the fonts as live text. Layer numbers are names, not stack positions. Name swatches by token (`--orange`, `--lblue`, `--reward-gold`…). **Files (v2.4.1):** the SVG is the master (live text, lock state); PSDs are previews.

---

## Section 2: In-video titles & graphics (Draft v2.4, ready for template build)

> **Status:** Draft v2.4, ready for template build. **Deliverable format (v2.4):** no MOGRT for now. SVG/PSD templates plus this spec are the deliverable, to be revisited once the editing tool is chosen in Section 3. Builds on the locked Section 1 system: Bebas Neue Pro / Inter, series accents, the RT grade scale, the colour-law guardrail (§1.3) and the generic screen rules (§1.4). Mockups are in `tests/section2/` (real Bebas Neue Pro and Inter; game frames are real captures, blurred or dimmed only).

### 2.0 Global system (applies to every element)

**Frames and safe areas** (master is 1920×1080; the 1280×720 equivalent is ×⅔):

| Zone | 1920×1080 | 1280×720 | Rule |
|---|---|---|---|
| Action-safe (3.5%) | (67,38)–(1853,1042) | (45,25)–(1235,695) | Rings, plates and anything that matters |
| **Title-safe (5%)** | **(96,54)–(1824,1026)** | (64,36)–(1216,684) | All text |
| Player-chrome band | y ≥ 960 | y ≥ 640 | YouTube controls and CC cover this. No plate edge below y=948 (632) |

**Type scale at 1920** (no other sizes):

| Role | Font | Size | Tracking | Case |
|---|---|---|---|---|
| Display Stat (stat value, grade) | Bebas Neue Pro Bold | 144px (grade up to 200px) | 0 | UPPER |
| Display XL (title) | Bebas Neue Pro Bold | 120px | +1px | UPPER |
| Display L (Milestone label bar) | Bebas Neue Pro Bold | 96px | +1px | UPPER |
| Display M (name, CTA) | Bebas Neue Pro Bold | 56–64px | +1 to +1.5px | UPPER |
| Display XS (chapter tag) | Bebas Neue Pro Bold | 48px | +1px | UPPER |
| Label | Inter Bold | 24–26px (chip 36px) | +1.5px | UPPER |
| Body/role/context | Inter Medium | 26–28px | 0 | Sentence |
| Caption 16:9 / 9:16 | Inter SemiBold / Bold | 44px / 60px | 0 | Sentence |

**Color by format** (tokens from §1.3):

| | Dev Diary | Scout's Report | Milestone |
|---|---|---|---|
| Accent (chips, bars, rules, rings) | `--orange` #F79420 | `--lblue` #4A90D9 | `--reward-gold` #F0C560 |
| Text on accent fill | `--bg` | `--bg` | `--bg` |

- Text is `--text-100` on plates. Secondary text is `--text-60`, and context is `--text-87`. Light blue is never text.
- **Green `--green`** appears only as the CTA plate (§2.5) or as native or rebuilt game data (a B grade).
- **Navy `--you`** is background atmosphere only, at ≤20%.
- **Red `--red`** is data only.
- Never tint, desaturate or recolor a real game screen. Blur and a `--bg` dim are the only allowed treatments.

**Plate:** `--surface-2` at 92% (`rgba(14,16,24,0.92)`), 1px `--line` border (`rgba(255,255,255,0.12)`), radius **12px** (8px at 1280), shadow `0 12px 32px rgba(0,0,0,0.45)`. Accent bars are 6px (4px at 1280).

**Motion tokens:**

| Token | Duration | Easing |
|---|---|---|
| `IN` | 240ms | `cubic-bezier(0.2,0,0,1)` (ease-out) |
| `OUT` | 200ms | `cubic-bezier(0.4,0,1,1)` (ease-in) |
| `MOVE` | 480ms | `cubic-bezier(0.4,0,0.2,1)` (zooms) |

- Allowed: fades, clip-wipes and slides of ≤24px.
- Not allowed: overshoot, bounce, elastic, scale-pop, blur-in, rotation, per-letter animation or shake.
- At 30fps, 240ms ≈ 7 frames.

**Brand in video:** there's no small or corner mark in any template. The **wordmark** (≥480px wide, always unaltered with its orange ball, and never counted as a format accent) is the brand in wide placements (§2.1, §2.5). The square icon appears only automatically, as the channel avatar in YouTube's subscribe element.

### 2.1 Title cards

**Decision (resolves "title card vs cold-open title"):** **both, in this order.** Open with a cold open of ≤10s of real footage that lands the hook, then a 2.0s opening card (2.5s for Milestone), then content. No opening card on Shorts or X cutdowns.

**Opening card, Dev Diary and Scout's Report** (mock: `s2_titlecard_devdiary_1920.png`):

| Element | 1920 placement | Spec |
|---|---|---|
| Background | full frame | `--bg`, plus 132° banding (1px every 156px, 3% white), plus an optional freeze of the next shot blurred 32px under a `--bg` dim at 85% |
| Format chip | (192,372)–(auto,428) | 56px tall, radius 14, 22px padding, Inter Bold 36px +1.5px, accent fill, `--bg` text. `DEV DIARY #07` / `SCOUT'S REPORT #03` |
| Title | x=192, first baseline y=560, second y=670 | Display XL 120px, `--text-100`, ≤2 lines, **≤24 characters per line**, ≤7 words, left-aligned |
| Accent rule | (192, last baseline+32), 160×6 | Accent color |
| Wordmark | (1248,801)–(1728,972), 480 wide | Full wordmark, unaltered |

1280 equivalents: chip at (128,248), 37px tall · title 80px at x=128 · wordmark (832,534)–(1152,648).

**Milestone opening card:** wordmark centered at 800 wide, (560,250)–(1360,535). Solid `--reward-gold` label bar at (360,640)–(1560,760), Display L 96px `--bg`. Date line in Display M 64px `--reward-gold`, centered at baseline y=840.

**Motion:** hard cut in from the cold open. Chip `IN` (fade + 16px rise) at 0ms → title `IN` at +80ms → rule clip-wipe left→right over 320ms at +200ms → wordmark fade `IN` at +200ms. Hold until 2.0s, then hard cut out (or `OUT` fade).

**Chapter tag** (in-frame, keeps the game on screen):
- Plate at title-safe top-left, (96,54)–(auto,126), 72px tall.
- Contents: number `01` in Display XS 48px in the accent, a 1px `--line` divider, then the chapter name in Display XS 48px `--text-100`. ≤26 characters.
- Motion: clip-wipe `IN` over 280ms, hold 3.0s, `OUT`.
- Use it only in videos ≥6 min. Max 1 per 2 min and ≤8 per video. Names match the YouTube description chapters.
- **Collision:** it may cover game nav or chrome, but never data or the element being discussed. If it would, mirror it to top-right (right edge at 1824). If both corners are busy, use a full-frame chapter card for 1.2s instead (the opening-card layout, title at 96px, no wordmark).
- Never on screen at the same time as a system label (§2.2).

| | Copy |
|---|---|
| Good: opening titles | `WHY WE REBUILT [SYSTEM]` · `HOW TO READ A RECRUIT` · `[PLAYER NAME]: OVERRATED?` |
| Good: chapters | `01 · THE PROBLEM` · `02 · WHAT WE TRIED` · `03 · THE VERDICT` (Scout's: `THE CARD` / `THE NUMBERS` / `THE CALL`) |
| Bad → fixed | `YOU WON'T BELIEVE THIS UPDATE!` → `WHAT CHANGED IN PATCH [X.Y]` · `PART 2 LET'S GO` → `02 · THE NUMBERS` |

**Don't:** use a card longer than 2.5s, stingers with whooshes, logo animations, or a title that's longer than the YouTube title.
**Templates:** `GOB_TC_Open_DevDiary` · `GOB_TC_Open_ScoutsReport` · `GOB_TC_Open_Milestone` · `GOB_TC_Chapter`. Layers: `00_GUIDES_noexport` · `10_TXT_chip` (DD/SR only; the Milestone card has no chip, v2.4.1) · `11_TXT_title` · `12_TXT_date` (MS) · `20_GFX_accent-rule` · `21_GFX_labelbar` (MS) · `30_BRAND_wordmark` · `40_BG_freeze-blur` · `41_BG_banding` · `42_BG_base_bg`. Accent is one swatch parameter named by token.
**`GOB_TC_Chapter` layers (v2.4):** `00_GUIDES_noexport` · `10_GFX_plate` · `11_GFX_accent-bar` · `12_TXT_chapter`.

### 2.2 Lower thirds

**Person lower third: Jamie and guests** (mock: `s2_lowerthird_jamie_1920.png`):

| Item | 1920 | 1280 |
|---|---|---|
| Plate | (96,844)–(96+w,948), 104px tall, w = 6 + 28 + text + 36, **max 760px** | (64,563)–(…,632) |
| Accent bar | 6px, full height, left edge, format accent | 4px |
| Name | Display M **56px**, +1px, `--text-100`, UPPER, baseline y=898, **≤24 characters** | 37px |
| Role | Inter Medium **28px**, `--text-60`, sentence case, baseline y=932, **≤40 characters** | 19px |

- **Jamie (resolves the "lower-third title" question):** `JAMIE DAVIES` / `Founder, Geeked-Out Basketball`. It uses the one fact we have and nothing invented.
- **Guests:** `[GUEST NAME]` / `[Role], [Studio or community]`. Handles go in the description, not on screen.
- **Motion:** plate clip-wipe left→right over 280ms with `IN` easing, text fade at +120ms, **hold 4.0s**, then `OUT`.
- **Frequency:** once per person per video, ≥1s after they start speaking.
- **Collision:**
  - Default is bottom-left. If the speaker is framed on the left third, mirror it to bottom-right (right edge at 1824, bar on the right).
  - Keep ≥48px clear of the face box (hairline to chin) and of hands pointing at UI.
  - It may cover game panels nobody is discussing for its 4s hold. It must never cover the discussed element (if it would, delay it until the next shot).
  - A Jamie picture-in-picture always pushes the lower third to the opposite side.

**System label ("what you're looking at"):**
- Plate at (96,54)–(auto,110), 56px tall, radius 10. Inter Bold 24px UPPER +1.5px, `--text-100`, ≤32 characters. No accent bar, because it's neutral like the game's information codes.
- Pattern: `[SCREEN] · [CONTEXT]`, e.g. `PLAYER CARD · [PLAYER NAME]` · `ANY DATA TABLE · [TEAM]` · `SEASON [N] · WEEK [N]`.
- Motion: fade `IN`, hold 4s or the length of the shot if shorter, then `OUT`. Show it again only when the screen changes.
- Uses the same corner and mirroring rules as the chapter tag. When both are queued, the chapter tag goes first and the system label follows 0.5s after it leaves.

**Don't:** use titles like "CEO / Visionary", emoji, @handles, or per-letter type-on, or leave a label on screen permanently.
**Templates:** `GOB_LT_DevDiary` · `GOB_LT_ScoutsReport` · `GOB_LT_Milestone` (person; mirror toggle) · `GOB_LT_System`. Layers: `00_GUIDES_noexport` · `10_TXT_name` · `11_TXT_role` · `20_GFX_accentbar` · `30_PLATE` · `31_PLATE_shadow`. `GOB_LT_System` reuses `10_TXT_name` for its label and has no role line or accent bar (v2.4.1).

### 2.3 Captions and subtitles

**Where:** YouTube long-form gets an uploaded **SRT** (not burned in). Shorts, X and any platform without reliable captions get **burned-in** captions.

| Spec | 16:9 burned-in (1920) | 9:16 Shorts (1080×1920) |
|---|---|---|
| Font | Inter SemiBold **44px** (29px at 1280), line-height 1.25 | Inter Bold **60px**, line-height 1.2 |
| Lines / characters | ≤2 lines, **≤42 characters per line (target 32–38)** | ≤2 lines, **≤22 characters per line** (60px across an 840px safe width) |
| Plate | `--bg` at 75%, radius 8, padding 10×18, one box per caption block | `--bg` at 80%, radius 12, padding 14×22 |
| Position | centered x=960, block bottom at **y=948** | centered x=**480**, block bottom at **y=1440** |
| Alt position | lower third on screen → bottom at y=820 · discussed UI at bottom-center → block top at y=108 | discussed UI low in frame → block top at y=260 |

**Shorts 9:16 safe zones (1080×1920):**

| Zone | Box | Rule |
|---|---|---|
| Top UI no-go | (0,0)–(1080,220) | Status bar, search, header |
| Right action rail no-go | (900,820)–(1080,1720) | Like, comment, share and remix buttons |
| Bottom no-go | (0,1500)–(1080,1920) | Channel name, subscribe, description, sound, progress |
| **Content-safe** | **(60,220)–(900,1500)** | All captions, numbers, grades and the discussed UI. Visual center is x=480 |

**Timing:** each block shows for 1.0–6.0s. Reading speed ≤17 characters/sec, ≥2 frames between blocks, and sync to speech within ±100ms. Captions cut on and off with no animation, and lines break at phrase boundaries (never split a name or a grade from its number).

**Copy rules:** sentence case · digits for numbers · grades exactly as shown (`B+`) · no emoji · **no exclamation marks, even when the delivery is emphatic** · drop filler words without changing meaning.
- Good: "This recruit is a B+ on paper." · "Watch what happens to his grade by Week [N]." · "We cut it. Here's why."
- Bad → fixed: "OMG this guy is INSANE!!" → "His numbers don't match his grade."

**Keyword emphasis (resolves "colored keywords in Shorts"):**
- **16:9:** none.
- **Shorts:** at most **one emphasized word per block**, shown as a **6px underline in the format accent**. The text stays `--text-100`, so contrast holds at ≥7:1 even with light blue.
- The one color exception: a grade written in a caption may render in its RT-scale color, because that's real data.
- Never green, red or navy for emphasis. No word-by-word "karaoke" highlighting; captions appear as phrase blocks.

**Templates:** `GOB_CAP_16x9` (burn-in preset + matching SRT style notes) · `GOB_CAP_9x16`. Layers: `00_GUIDES_noexport` (Shorts no-go boxes in 50% magenta) · `10_TXT_caption` · `11_GFX_underline` · `20_PLATE`.

### 2.4 Stat callouts and UI zoom/ring callouts

(mock: `s2_statcallout_scoutsreport_1920.png`). ⚠️ **Needs a recapture:** its source frame (`thumb-tests/src/ref_player_profile.png`) is the pre-overhaul player card that shows an orange B. The B is outside the zoomed crop, but the frame breaks H8, so rebuild this mock from a current-build capture before using it as a template reference.

**UI zoom:**
- Push smoothly from 100% to **150–200%** with `MOVE` (480ms). Go up to 250% only with a 4K source. No snap zooms or punch-ins.
- Hold **≥3.0s, plus 1s per 10 words visible** in the zoomed area. Zoom out over 400ms.
- If the recording has Jamie's webcam baked in, crop it out before zooming and re-add it as a separate, unzoomed picture-in-picture on the side away from the ring.

**Ring:**
- Rounded rectangle, radius 12, **6px stroke** (4px at 1280), 12px padding around the element.
- **Spotlight dim** outside the ring: `--bg` at 55%, fading in with the ring.
- Draw-on: a clockwise stroke trim over 320ms (`IN`), starting 80ms after the zoom lands. Out: ring fades `OUT` (160ms), then the zoom-out starts.
- One ring on screen at a time. For rows or ranges wider than 900px, use **corner brackets** instead (48px arms, 6px stroke).
- **Ring color (resolves the open question):**
  - The default is the **format accent**.
  - Use `--text-100` white when the ringed element is already that hue: an A grade in Scout's Report (mirrors §1.3), or orange UI in a Dev Diary.
  - Never green, red or navy, since those carry data or "yours" meanings in the game.

**Stat callout card:**

| Item | 1920 | 1280 |
|---|---|---|
| Plate | min **460×240**, plate spec + **6px accent top rule** (inset 12px) | 307×160 |
| Label | Inter Bold 26px UPPER +1.5px, `--text-60`, ≤18 characters | 17px |
| Value | Display Stat **144px**, `--text-100` (grades use RT colors) | 96px |
| Context | Inter Medium 26px, `--text-87`, 1 line, **≤32 characters** | 17px |
| Placement | ≥32px from the ringed element, on the side with more empty space, inside title-safe. Never covers the element or a face. No arrows or leader lines | — |

- **Motion:** card fade + 12px slide in from the element side (`IN`), after the ring finishes. **Hold ≥2.5s** and at least through the voiceover sentence that states the number. `OUT` together with the ring. At most **1 card on screen and 3 per minute**.
- **Count-up animation: no** (resolves the open question). Values appear at their final number. A before → after shows as two static values with a neutral `→`, revealed 400ms apart.
- **Grades (source of truth: UX_System RT scale):** rebuild them in Bebas at 144–200px in the exact RT color: A/A+/A++ `--lblue` · B/B+ `--green` · C/C+ #FFD700 · D/F `--red`. The rebuilt grade must match the grade on screen at that moment. In Scout's Report with an A grade, the card's top rule turns white. **Never use pre-overhaul captures that show off-scale grade colors** (H8). Recapture from the current build.
- **Deltas stay neutral, as they are in the game:** ▲ in `--text-100` and ▼ in `--text-60`, numeric (e.g. `+6 RT ▲`). Never green-up or red-down. **Arrow glyphs ▲ ▼ → are set in Inter Bold 64px** inside the value line, because Bebas Neue Pro has no arrows (v2.4.1).

| | Context-line copy |
|---|---|
| Good | `Rank [N] of [N] on the roster` · `Up from [N] in Week [N]` · `Same grade, different player` |
| Bad → fixed | `INSANE STAT!!!` → `Rank [N] of [N] on the roster` |

**Templates:** `GOB_CO_Ring_DevDiary` · `GOB_CO_Ring_ScoutsReport` · `GOB_CO_Ring_Milestone` · `GOB_CO_Bracket` · `GOB_CO_Stat` · `GOB_CO_Grade` · `GOB_FX_ZoomDim`. Layers: `00_GUIDES_noexport` · `10_TXT_label` · `11_TXT_value` · `12_TXT_context` · `20_GFX_toprule` · `21_GFX_ring` · `30_PLATE` · `40_FX_dim`. **`GOB_CO_Bracket`, `GOB_CO_Stat`, `GOB_CO_Grade` and `GOB_FX_ZoomDim` take a `series` parameter (default: Scout's Report)** that sets the accent (v2.4.1).

### 2.5 End screens (where the wordmark lives)

**Long-form, last 20s** (YouTube allows 5–20s; use 15s only if the outro is short):

| Element | 1920 placement | Spec |
|---|---|---|
| Wordmark | (96,96)–(736,324), 640 wide | Full wordmark, unaltered |
| Tagline | x=96, baseline y=420 | `BUILD YOUR BASKETBALL DYNASTY`, Display M 56px +2px, `--text-100` |
| **CTA plate** | (96,476)–(736,588), radius 12 | **`--green` fill**, `WISHLIST ON STEAM` (default) in Display M 64px +1.5px, `--bg` (12.2:1). **During Next Fest and other demo events: `PLAY THE DEMO`**, with the same spec and the same green. This is the only non-data green in any video |
| CTA sub-line | x=96, baseline y=636 | Inter Medium 26px, `--text-60`: `Link first in the description` |
| Subscribe element | circle (96,700)–(316,920) | YouTube element (shows the square icon avatar). Nothing drawn underneath it |
| Video slot A | (1056,108)–(1824,540), 768×432 | YouTube element. Draw nothing inside it |
| Video slot B | (1056,580)–(1824,1012) | Same |
| Background | full frame | `--bg`, banding, optional `--you` radial glow ≤20% behind the wordmark, or the last game shot blurred 32px under an 85% dim |

- **Motion:** dissolve from content over 400ms. Then wordmark `IN`, tagline at +80ms, CTA at +160ms. Static after that: no loops or pulses. Music fades out over the last 2s.
- **Steam capsule: no** (resolves the open question). The wordmark already identifies the game, a capsule would duplicate it and crowd the CTA, and the real Steam link lives first in the description.
- **Voiceover:** Jamie says one sentence or nothing.
  - Good: "If this is the depth you've been missing, wishlist it on Steam." · "Next one breaks down [topic]."
  - Bad: "Smash that like button!!"
- **Milestone variant:** same layout and CTA rule (`WISHLIST ON STEAM`, or `PLAY THE DEMO` during demo events), with the tagline swapped for the date in `--reward-gold`.

**Shorts and X end (last 1.5–2s, no YouTube end screen):**
- **9:16:** **wordmark plus CTA only, no tagline or subline** (v2.4.1). Wordmark 640 wide, centered at x=480, at (160,560)–(800,788). Green CTA plate at (120,1180)–(840,1300), Display M 64px (same copy rule). Everything sits inside the content-safe box.
- **16:9 X cut (`GOB_ES_X_16x9`):** the long-form left column, **centered both horizontally and vertically** in the frame (v2.4).

**Templates:** `GOB_ES_Long` · `GOB_ES_Long_Milestone` · `GOB_ES_Short_9x16` · `GOB_ES_X_16x9`. Stacking order from top to bottom (v2.4, matches `templates/video/GOB_ES_*.svg`): `00_GUIDES_noexport` (YouTube element boxes) · `10_BRAND_wordmark` · `11_TXT_tagline` · **`21_TXT_cta` (`WISHLIST ON STEAM` / `PLAY THE DEMO`) · `20_CTA_plate_green`** (text above the plate) · `22_TXT_subline` (not in the Shorts end) · `40_BG_glow` · `41_BG_banding` · **`43_BG_freeze-blur`** (blurred last game shot, all end-screen templates, v2.4.1) · `42_BG_base_bg`.

### 2.6 Graphics checklist (Chewbacca, per video)
1. Templates come from the `GOB_*` set, with the format accent swatch set correctly.
2. All text is inside title-safe. Shorts text is inside (60,220)–(900,1500).
3. No graphic covers the discussed element or a face. Chapter tags and system labels never overlap.
4. Every number and grade on screen matches the game frame showing at that moment, in RT colors with neutral deltas. Every capture comes from the current build (no pre-overhaul frames).
5. Green appears only as the CTA or as data. Navy appears only as atmosphere. No game screen is recolored.
6. No `!`, no emoji, no count-ups, no bounce.

## Section 3: Editing rules (outline)

- **Pacing:** deliberate. Let a screen sit long enough to be read (≥3s for any UI the viewer is meant to parse). Prove the thumbnail's promise in the first 60s. Cut dead air and loading screens. *Open:* target length per series.
- **Cuts & transitions:** hard cuts by default. A 6–8 frame cross-dissolve is allowed only for time skips. **No meme cuts:** no zoom-punches, whip pans, reaction inserts, record scratches, glitch or shake effects, or stock meme clips.
- **Music/SFX:** a subtle instrumental bed ducked to about −20 dB under voice. Master voice-led mixes to about −14 LUFS integrated. SFX are limited to real in-game UI sounds. No whooshes, booms or airhorns. *Open:* music library or license source, and whether GOB gets a signature sting (≤2s).
- **Screen capture:** 2560×1440 or 4K, 60 fps, clean fictional save data, OS notifications off, no debug overlays. Any screen can be captured as it ships (screen rules will be revisited after the UX overhaul). Hide the cursor unless you're demonstrating something; when demonstrating, use a cursor at ≥150% size with a soft highlight. Zoom in post (see §2), not by capturing at low resolution.
- **Founder on camera (LOCKED):**
  - **Game footage ≥60% of Dev Diary runtime.**
  - **Jamie never appears in Scout's Report videos**, except in a thumbnail test variant.
  - Use a real setup with the game visible on screen behind or beside Jamie. Frame him on a third, and keep the game the larger element when you split-screen.
- **Captions:** always on. SRT for long-form, burned in for Shorts and X (specs in §2.3).
- **Intro/outro:** cold open ≤10s (the hook, straight into the game), a brand sting ≤2s or none, and an outro equal to the end screen at 15–20s. No "like and subscribe" monologue.
- **Platform cutdowns:**
  - Shorts/Reels: 1080×1920, 15–45s target. Keep critical content inside the §2.3 content-safe box, (60,220)–(900,1500). Reframe UI crops for vertical rather than letterboxing.
  - X: 16:9 1920×1080 or 1:1 1080×1080, ≤60s, burned-in captions. The first frame should be a readable game screen because it acts as the thumbnail.
  - Every cutdown ends on the Steam wishlist CTA (`--green`, §2.5). The square icon is the avatar everywhere.
  - *Open:* whether the X posts come from Jamie's account or a GOB account.

---

## Open questions for Jamie

**Section 1 (Thumbnails):** none. Locked at v2.3.
**Section 2 (In-video graphics):** none. Draft v2.3, ready for template build.
**Section 3 (Editing, outline):** these are still open and flagged inline:
1. Target video length per series.
2. Music library/license, and whether GOB gets a ≤2s sting.
3. Whether X posts come from your account or a GOB account.
