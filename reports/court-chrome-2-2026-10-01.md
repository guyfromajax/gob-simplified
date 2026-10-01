# Court chrome part 2 — remaining pieces (safe pass) — 2026-10-01

Branch `ux/court-chrome-2`, built on **part 1** (`cbb3ebdac`, merged into `origin/develop`
mid-task and merged in here as the base). Visual-only; no animation timing, court geometry,
or sim/UESS/finalize/sim_rng changes. One source file: `FrontEnd/static/court.html`.

## Scope decision (confirmed with Jamie: "safe pass + flag")

Surveying the *remaining* court chrome showed it is **not** the clean neutral chrome that
the scoreboard was. It is dominated by three things that are **not** a token swap:

1. **Game-state colour-coding** — the Playcall Center cockpit (strategy dials, armed
   offense/defense, the "COLOR-CODED ACTIVE BUTTON STATES" block), the playcall reveal HUD,
   the lower-third / secondary-announcement ribbons, and the active-player HUD. These encode
   game state (and team) via colour; recolouring is a data/ramp ruling, and some are asserted
   by the equivalence specs.
2. **Opaque-grey legacy surfaces** (`#1a1a1a`, `#333`, `#444`, `#555`, `#aaa`) with **no 1:1
   gob token** (gob uses navy surfaces + translucent whites). Migrating grey → navy is a
   visual redesign, not "paints identically".
3. **On-canvas Phaser text** in the scene JS — equivalence-locked + ramp-governed.

Per the agreed **safe pass**: tokenise the genuinely-neutral chrome, fix clearly-**decorative**
off-law colours, keep data / team / grey (annotated), and flag the three categories above.

## Changes (safe pass)

| Element | Was | Now | Why |
|---|---|---|---|
| sim-quarter popup divider (`.sim-quarter-header`) | orange `#ff6200` | neutral `#6b7280` | Decorative; orange is saves only. Legacy **light** popup → neutral grey, not gob dark tokens |
| sim-quarter scrollbar thumb | orange `#ff6200` | neutral `#6b7280` | same |
| `#player-tooltip` / `#play-tooltip` border | orange `#ff6200` | `--white-28` | Decorative tooltip border |
| `#main-container` bg | `#000` | `--black` | Value-identical tokenisation |
| `.momentum-bar-wrap` divider | `rgba(255,255,255,.06)` | `--white-6` | Value-identical |
| box-score `h3`, `.momentum-bar-value` | `#fff` | `--text-100` | Value-identical |

## Kept (data / team-identity — not recoloured)

- Side-panel stat-view toggles (`.toggle-btn.active`, S1/S2/S3) use the panel's **team colour**
  for the selected state — flagged (choice-control-vs-team-identity ruling for Jamie).
- Both momentum bars (`.momentum-fill-*`, `.momentum-bar-left|center|right`) use red / green /
  yellow / white for **momentum direction** (data). `#34EC27` positive == `--green` by value.
- Scoreboard **quarter + shot clock** read gold; timeout **pips** read orange — game data.

## Deliberately NOT done (flagged for a dedicated review)

- **Game-state colour-coding**: Playcall Center cockpit (strategy dials, armed offense/defense,
  color-coded active-button states), playcall reveal HUD, lower-third + secondary-announcement
  ribbons, active-player HUD (gold has-ball / defender, `#4caf50` "AUDIBLE!"). Ramp/spec-adjacent.
- **Opaque-grey → navy surface migration** of the side panels (a visual redesign).
- **On-canvas Phaser text** (fonts/colours in the scene JS) — equivalence-locked.

(These are documented in UX_System's "Live-game screen chrome (court.html)" section.)

## Verification

- **Screenshots** (`reports/court-chrome-2/`, `page.screenshot`, scroll 0, 1280 + 1920): the
  court view with the pre-game modal hidden (so the DOM chrome paints; the Phaser canvas is
  black in headless). `before/after-court-{1280,1920}` are **identical** — the tokenisations are
  value-identical and the orange→neutral fixes live in the sim-quarter popup / tooltips, which
  mount only during play / on hover, so they don't appear in this view (verified by guard instead).
- **Computed-style guards** — `tests/e2e/court-chrome-2-tokens.spec.js` (3 tests, committed):
  sim-quarter divider is `rgb(107,114,128)` not orange; player/play tooltip borders are
  `rgba(255,255,255,.28)` not orange; `.momentum-bar-wrap` divider is `--white-6`. Probe-injected
  so they exercise the rules regardless of play state. Fails on develop.

## Gates (`.venv/bin/python`)

- **pytest** `--ignore=tests/e2e -q`: **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (243s). 2 XPASS backend/pre-existing; `known_failures.py` not edited.
- **`check_ui_tokens.py --strict --no-write`**: **exit 0** (real code, no pipe). New-surface hits 0/0/0 — develop's prior `box-score.css:494` red is now fixed/merged. court.html is legacy; its law hits dropped **79 → 75** with this pass.
- **`check_migration_gates.py`**: **passed** — Gate A 0/0; Gate B 134 lines/43 files.
- **Equivalence specs** (`game-winner`, `sim-broadcast-fit`, `court-layout`, `game-start-sequence`, `sim-team-callouts` = 55): **55/55**.
- **Full Playwright** (workers=1, port 8000, under `/tmp/gob-full-playwright.lock`): **806 passed, 7 skipped, 1 failed** (12.6m; 813 incl. the 3 new part-2 guards). The one failure, `fcc-fresh-after-game.spec.js:259` (FCC warm-paint cache), is **not a regression**: this branch touches only `court.html` + `UX_System.md` (zero FCC files) and it passed **5/5** isolated (`--repeat-each=5`) — the same pre-existing load flake seen in part 1.

STATUS: COMPLETE (safe pass). All gates green; the one full-suite failure is a pre-existing FCC flake (5/5 isolated). Game-state colour-coding, the grey→navy surface migration, and on-canvas Phaser text are flagged for a dedicated review (see UX_System).
