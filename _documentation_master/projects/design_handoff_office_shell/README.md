# Handoff: GOB — The Office, franchise shell, Settings, gameplay audio

## Overview
This package covers everything approved in design rounds 1–2 for *Geeked-Out Basketball*:

- **The Office** — the franchise home screen. It has three columns: This week, Since last week, and Next game. It comes in five states: after a win, after a loss, first week, tournament week, and Signing Day.
- **The franchise shell** — the top bar and left rail used on every franchise page, plus section pages with sub-tabs.
- **Settings** — a panel that opens from the gear in the rail.
- **Gameplay audio control** — a speaker icon and popover in the live-game scoreboard strip.

## About these files
The target codebase is **plain HTML/CSS/JS**, and so are these files. `frames/*.html` are static, high-fidelity references. Their markup and `components.css` are written to be copied. They are still **reference implementations, not drop-in production files**:
- Wire them to real data and routes.
- Merge them into the codebase's existing page structure.
- Keep existing behaviour that already works (see the rules below).

## Fidelity
**High fidelity.** Colours, type, spacing, radii, states and motion are final. Every value is a token in `tokens.css`. Any literal px value left in `components.css` is a component dimension, and those are listed in `components.md`.

## Rules for the implementing agent (read first)
1. **Before writing any code, report back:**
   - which existing files own each affected piece of UI (the Office / Coach's Office tab, the franchise top bar, the nav, the Team page, settings, the scoreboard strip);
   - which data fields actually exist for every value in `README › Data needed`.
2. **Never invent, derive or approximate a missing field.** If a value in the mocks has no backing field, stop and ask.
3. **Don't micromanage what already works.** Keep existing CTA copy where it exists, existing colour scalings (shot weight has its own programmed scaling — do not substitute), and existing table column sets.
4. **All sample values are illustrative.** This includes names, scores, percentages, coach stats, the build label, initials standing in for headshots, the portrait image, letter monograms standing in for team logos, and sample CTA labels. Only the structure, tokens and behaviour are specified.
5. **Canonical encodings are fixed game-wide.** Player RT digit: 0–4 red · 5–6 yellow · 7–8 green · 9+ blue. Team RT letter: A blue · B green · C yellow · D/F red. Energy uses the green/yellow/red ramp. Each variable gets its own visual channel:
   - hue on a bar or fill = energy;
   - hue on a glyph = RT;
   - luminance only = supporting numbers;
   - direction or position = diverging values.
   **Blue belongs to RT.**
6. **Green `#34EC27` is the one Advance action per screen.** Orange is for saves and non-advancing actions. Navy is for structure and selection only. There are no spinners anywhere.
7. **Live-gameplay screens never show the franchise shell.**

## Files
```
tokens.css            all design tokens (:root + .gob-1280 / .gob-1920 density sets)
components.css        every component, tokens only
components.md         per-component spec: dimensions, tokens, states, motion
layout.md             grid, breakpoints, rail/top bar sizes, what changes 1280 ↔ 1920
decisions.md          everything decided that wasn't in the brief — confirm before shipping
frames/
  office-win-1280.html          office-win-1920.html
  office-loss-1280.html         office-first-week-1280.html
  office-tournament-1280.html   office-tournament-1920.html
  office-signing-day-1280.html
  team-roster-1280.html         (section page + sub-tabs, page-only scroll)
  settings-online-1280.html     settings-offline-1280.html
  gameplay-audio-1280.html
  component-sheet.html          every component and state on one page
assets/portrait-placeholder.png illustrative headshot (wrong jersey; replace with real portraits)
fonts/BebasNeuePro-*.otf        display face (Inter loads from Google Fonts)
reference/emblem.js             existing tournament-tier emblem source of truth (renderEmblem / renderLockup)
```
Open any frame directly in a browser. The frames load `../tokens.css` and `../components.css`.

## How the CSS is organised
- The root element is `.gob` plus a density class: `.gob-1280` (default) or `.gob-1920`. See `layout.md` for when to apply each.
- The shell is `.app`, a grid containing `.top` (top bar), `.rail` and `.main`. The Office content is `.office`, a grid of three `.office-col` columns.
- Two inline custom properties are **data** and are set per element: `--tc` (a team's primary colour, used on `.logo`) and `--i` (stagger index for the arrival motion). In tier weeks, `.top.is-tier` also receives `--tier-metal` and `--tier-metal-hi` inline, taken from `emblem.js` TIER_TOKENS.
- Hover-state classes `.is-hover`, `.is-press`, `.is-drag` exist only so the component sheet can show those states statically. In the product, `:hover`, `:active` and dragging produce them.
- Tournament emblems in the frames are inline SVG produced by the `emblem.js` geometry. In code, call `renderEmblem` / `renderLockup` from `reference/emblem.js` (it's already in the repo), not the pasted SVG.

## Data needed (confirm each exists — do not invent)
- **Top bar:** team name and logo, record, national rank, week number, phase label, tournament tier (conference / region / national) or none, and the Advance action (label, enabled flag, blocking task).
- **Rail:** count of pending recruiting actions, an urgent flag (a recruiting task gates Advance), and online/offline state.
- **This week:** to-do list, where each item has label, meta, required/optional, done, gates-advance, is-the-advance-action, and target route.
- **Result:** last game (both scores, opponent and opponent rank, home/away/neutral, round name if any), a headline, and a player-of-the-game or team leader with their stat line and the route to the box score.
- **What moved:** change in national rank, change in conference standing, record and streak, per-player attribute changes (name, attribute, from, to).
- **Recruiting wire:** a status line; events with recruit, position, stars, filmed grade, event text, list position and direction.
- **Next game:** opponent, rank, record, conference, date/time, site, team RTs, top scorer and rebounder, and the projected starting five with player RT and key stat. Tournament weeks add round, seeds and stakes.
- **Team snapshot:** chemistry (x/25), attitude distribution across the 12 players, and the two team measures that moved most, with deltas.
- **Signing Day:** points remaining / total, promises made, open roster spots, and the top 3 targets with lean standing.
- **Season preview:** preseason rank, conference projection, team RT, returning starters, top returner, newcomers, and the season opener.
- **Settings:** audio levels and mute per channel (master, music, SFX, ambience); coach career record, titles, All-Americans coached, seasons coached; username, email; build label; online flag.

## Assets
- Portrait: `assets/portrait-placeholder.png`, illustrative only (its jersey reads "Patriots").
- Team logos: letter monograms drawn by `.logo` with `--tc`. Replace them with real logos at the same sizes.
- Icons: inline 24×24 stroke SVGs, stroke-width 1.8, round caps and joins, `currentColor`. The paths are in the frames. If the codebase has an icon set, use it at the same size and weight.
