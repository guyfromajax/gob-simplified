# Game overlays → gob tokens (coverage gap #1) — 2026-09-30

Branch `ux/game-overlays-tokens` off `origin/develop`. Put the live-game **DOM**
overlays (built with `createElement` in `js/phaser/utils/`) on the gob design system,
sim-safe. **Not** touched: the Phaser **canvas** HUD / announcements / status /
strategy / playcall text, `gameScene.js`, or `court.html` inline chrome.

## What shipped (per-overlay commits, pushed as each landed)

| # | Overlay | Commit | Colour literals |
|---|---|---|---|
| 1 | `gameCompletionPopup.js` | `ff344c528` | 47 → 16 |
| 2 | `foulOutPopup.js` | `405fa5ae5` | 15 → 3 |
| 3 | `defenseMatchupsPopup.js` (`matchupsUiShared.js`: no change) | `390e641a6` | 35 → 14 |
| 4 | `postGamePressConference.js` (+ `pgpcSammyReminderModal.js`) | `9cfcbae35` | 20 → 5 (+ 2 sammy) |
| 5 | `preGameExperience.js` | `c16fd6104` | 43 → 19 |
| 6 | `simGamePresentation.js` | `f503ef08d` | −1 (orange glow only) |
| — | report + UX_System | this commit | — |

Plus `court.html`: one line — `gob-tokens.css` `<link>` after `app-fonts` (the only
allowed court change; adds only `.gob`-scoped custom props → court paints identically).

## Colour-law decisions

**Green = the ONE forward/Advance action per overlay** (kept green, tokenised to
`--green`/`--bg`):
- `gameCompletionPopup` locker-room button (starts phase-b)
- `defenseMatchupsPopup` "Submit Defense Matchups" (saves + resolves → quarter starts)
- `postGamePressConference` primary button (always "Go To Locker Room" / exit)
- `preGameExperience` "Submit & Tip Off" / "Tip Off" (saves + tips off)

**Neutralised law hits:**
- W/L outcome badges → white fill / outline (never win-green / loss-red).
- `foulOutPopup` "Sub Players" button → neutral: it **navigates** to set-lineup to fix
  the lineup; it is not the game/week Advance, so not green (and not orange).
- Orange accents, hovers, header bars → neutral (orange is saves only): foul-out accent
  bar; PGPC choice hover + A/B/C/D letters; pregame + sim decorative orange ambient glows.
- "Don't show again" checkboxes (defense-matchups, pregame) → neutral: the pref persists
  only on Submit, so at toggle time it is pending, not a committed save.
- PGPC "simming" pulse bar → neutral: a passive loader, not the Advance action or data.

**Kept as data (identification / ramps — not chrome):**
- Team-colour name bars / head underlines / tile borders / favor arrows + borders.
- Team `primary_color` fallbacks (`#1F8A5B` / `#9E1B32`).
- `matchupsUiShared.js` RT-ramp fallbacks, contrast-math constants, neutral inline SVG —
  **no change** to that file.
- The Sim broadcast's 5-colour data palette (GREEN/BLUE/ORANGE/RED/GOLD) and its bespoke
  neutral token layer (see below).

**Navy:** left on HOLD. Existing navy ambient glows (pregame, sim) were **not** added or
removed; no navy added to any selection.

## Wanted to change but did NOT (flagged for Jamie)

- **Sim broadcast data-adjacent reserved colours** — spotlight row + "TOP"/"SPOT" mark in
  **orange**, "FOUL TROUBLE" tag/ring in **gold**, "POSS" worm caption in **orange**,
  highlights toggle-on in **green**. These are state/data indicators that are BOTH
  asserted by the equivalence specs (exact computed colours) AND governed by the frontend
  colour ramps (CLAUDE.md: don't re-map). Re-colouring is a ramp/design call, not mine.
- **Sim broadcast neutral token layer** — `--w90/.90 … --w25/.25 / --hair/.08`. These
  alphas do not map 1:1 onto the gob white/text scale; forcing them onto gob tokens would
  shift values (breaks "visual-only / identical" and risks the specs). Left intact.
- **preGameExperience tip-off veil** — green radial glow + green "TIP OFF" text glow were
  neutralised (dark veil / white glow) because green is reserved for the Advance action +
  positive data, not a decorative transition. If the green "GO" flourish is meant to be the
  advance-into-game beat, revert the two lines marked `FLAGGED` in `.pgxp-tipoff`.
- **`pgpcSammyReminderModal.js`** — legacy **FTE light shell**; it loads `/css/fte.css`,
  which **does not exist anywhere in the repo** (pre-existing bug, surfaced here). Not
  re-themed to gob (tokens wouldn't resolve on a non-`.gob` light surface); only the two
  reserved-orange law hits were neutralised to `#6b7280`.
- Canvas HUD / announcements / `court.html` inline chrome — out of scope (not DOM overlays).

## Sim-safety proof

Visual-only. No change to logic, timing, event order, callbacks, data reads, when popups
open/close, or anything sim / finalize / `gameScene.js`. Equivalence specs
(`game-winner`, `sim-broadcast-fit`, `court-layout`, `game-start-sequence`,
`sim-team-callouts` = **55**) re-run after **every** overlay → **55/55**, including
`sim-team-callouts` "callout accent is the exact color selected for that worm line" and
`sim-broadcast-fit` fouls-pill colour asserts.

## Screenshots (`reports/game-overlays-tokens/`, before + after, 1280 + 1920, scroll 0)

`completion-win`, `completion-loss`, `foulout`, `matchups`, `pgpc`, `pregame`, `sim`.
Before/after are identical where the change was a value-preserving tokenisation or an
imperceptible decorative-glow neutralisation (sim, pregame-ambient); visibly different
where a reserved colour was neutralised (completion W/L badges, foul-out button + accent,
PGPC choice letters).

## Gates

- **pytest** `--ignore=tests/e2e -q`: **4297 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (240s). The 2 XPASS are backend and pre-existing (this change is frontend-only); not editing `known_failures.py`.
- **`check_ui_tokens.py --strict --no-write`**: **exit 0** (new-surface law hits 0/0/0; the overlay files are legacy JS, so their remaining literals report as legacy and do not fail the gate).
- **`check_migration_gates.py`**: **passed** — Gate A 0 imports/0 files; Gate B 136 lines/44 files (unchanged; no franchise-identity `URLSearchParams` added). (Two informational NOTEs about `training.html` / `training-report.html` are pre-existing allow-list staleness, not from this task.)
- **Full Playwright** (workers=1, port 8000, under `/tmp/gob-full-playwright.lock`): **785 passed, 6 skipped, 2 failed** (11.9m). Both failures are in **`recruiting-tabs.spec.js`** (`:415` week-21 focus flow, `:479` browse-hub Leans sync) — **not a regression**:
  - This branch touches **zero** recruiting files (`git diff --name-only origin/develop...HEAD` → only `js/phaser/utils/*`, `court.html`, `UX_System.md`, `reports/`).
  - Isolated re-runs (`--repeat-each=5`): `:479` → **5/5 pass** (clean flake); `:415` → **3–4/5 pass** (flaky ~20–40% under load). The captured failure is a load-timeout (the recruiting page rendered only its "← Back to Locker Room" link; async pool/Leans content hadn't painted before the assertion) — box contention, not a structural break.
  - The task's five **equivalence** specs were **55/55** on every overlay.

STATUS: COMPLETE. The only full-suite failures are a pre-existing recruiting-tabs load flake, unrelated to this frontend game-overlay change (no recruiting files touched; flaky in isolation).
