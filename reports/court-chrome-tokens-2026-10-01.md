# Court chrome → gob tokens + colour law — 2026-10-01

Branch `ux/court-chrome-tokens` off `origin/develop`. Put the live-game **screen chrome**
in `court.html` on gob tokens + the colour law. Visual-only: no animation, timing, court
layout geometry, or sim/UESS logic touched. One source file changed: `FrontEnd/static/court.html`.

## Scope decision

`court.html` is ~7,800 lines with a single ~4,300-line inline `<style>` (513 colour/type
literals) — full tokenisation is well over a day. Per the brief, I did the **highest-traffic
chrome** and listed the rest:

- **Pre-game start prompt** (`.pre-game-*`, `.play-button`, `.sim-full-game-button`) — the most
  visible pre-game chrome, and the clearest law fix.
- **Scoreboard top bar** (`#scoreboard` and children) — always on during a game.
- **Game controls** (pause / skip / game-speed across the base, `.pcc-*` cockpit, and
  `#game-controls-strip` layers).

Enabling change: `court.html` `<body>` now carries `class="gob"` so gob-tokens.css custom
properties resolve for the court DOM. gob-tokens.css is **custom-properties-only** (3 `.gob`
rules, zero element declarations — verified), so the court paints identically except where
chrome now references tokens.

## Colour-law fixes

| Element | Was | Now | Why |
|---|---|---|---|
| `.play-button` ("Play Quarter" / "Resume Game") | orange `#F79420` | **green** `--green`/`--bg` | It starts the game = the one Advance action |
| `.pre-game-modal-accent` | orange `#F79420` | neutral `--white-28` | Decorative; orange is saves only |
| `.sim-full-game-button` | raw white rgbas | `--white-6`/`--white-12`/`--text-87` | Neutral secondary (not the Advance) |
| `#pause-btn` (strip + `.pcc-pause` + base) | orange `#F79420`/`#ff6200` | neutral `--white-10`/`--white-28`/`--text-100` | Pause/Resume is a playback control, not a save |
| `.pcc-speed-btn.on`, `#game-speed-btn` | orange `var(--orange)` / purple `#9c27b0` | neutral white tokens | Choice controls are neutral |
| `#skip-btn` | blue `#007bff` | neutral `--white-10` | Choice control; blue is RT-only |
| `#scoreboard` bar / scores / TOL-F / rank / record / strategy gauges | `#000` / `#fff` / raw white rgbas | `--black` / `--text-100` / `--text-60` / `--text-38` / `--white-12` / `--white-20` | Neutral chrome on tokens |

## Kept as team-identity (annotated `/* colour-law: team-identity */`)

- Away/home **score underlines** (`text-decoration-color: var(--away/home-vibrant-color)`).
- Scoreboard **divider gradient** endpoints (away→home) — the white centre was tokenised to `--white-10`.
- **Logo-container framing tint** (`rgba(var(--…-vibrant-rgb), .25)`) — frames the team's own logo (identity zone), not a content wash.
- Strategy-gauge marker `--mk-color` (neutral `#8A94A6` fallback) — read-only data gauge.

## Wanted to change but did NOT (flagged for Jamie)

- **Timeout button** (`#game-controls-strip #timeout-btn`, `.pcc-timeout`) is **green**
  (`#34EC27`). Possibly "timeouts available" positive-data; left as-is (data/ramp call).
- **Active-player HUD on the scoreboard** (`.active-player-*`): gold "has ball" / defender
  ring, `#4caf50` "AUDIBLE!" text, and a circular headshot (HUD is exempt from the square rule
  per the overlays section). Game-presentation data — left as-is.
- **Not yet tokenised (remaining):** the Playcall Center cockpit (strategy dials, armed
  offense/defense + color-coded active-button states), the player-stats side panels,
  announcements / reveal HUD / lower-third / secondary ribbon, the sim-quarter popup,
  play-by-play, the momentum bar, and on-canvas Phaser text/labels. (court.html still has
  ~79 legacy colour-law literals after this pass, down from ~91.)

## Verification

- **Screenshots** (`reports/court-chrome-tokens/`, `page.screenshot`, scroll 0, 1280 + 1920):
  `before/after-pregame-{1280,1920}` show the start prompt — Play Quarter **orange → green**,
  accent neutral, Sim Full Game neutral, layout identical. The **live scoreboard/controls do
  not paint in headless** (Phaser canvas + the scoreboard render black without full game data),
  so the scoreboard + controls are verified by the computed-style guard below rather than by a
  screenshot (black live/scoreboard captures were discarded).
- **Computed-style guards** — `tests/e2e/court-chrome-tokens.spec.js` (4 tests, committed):
  body has `.gob`; Play Quarter computes to `rgb(52,236,39)` ink `rgb(11,13,20)` (proves
  `--green`/`--bg` resolve) and is not orange; scoreboard is `rgb(0,0,0)` with white scores;
  pause/skip/game-speed are neutral white tokens, never orange/blue/purple. Fails on develop.

## Gates (`.venv/bin/python`)

- **pytest** `--ignore=tests/e2e -q`: **4297 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (238s). 2 XPASS are backend/pre-existing (this change is court.html only); `known_failures.py` not edited.
- **`check_ui_tokens.py --strict --no-write`**: **exit 1** (real code, no pipe). The single new-surface hit is **`box-score.css:494`** (green) — **pre-existing on develop** (stats is fixing it per the brief; not touched here). court.html is legacy; its law hits **dropped ~91 → ~79** with this pass, and no new-surface hit was added.
- **`check_migration_gates.py`**: **passed** — Gate A 0 imports/0 files; Gate B 134 lines/43 files. (Two informational NOTEs about `training.html` / `training-report.html` are pre-existing allow-list staleness.)
- **Equivalence specs** (`game-winner`, `sim-broadcast-fit`, `court-layout`, `game-start-sequence`, `sim-team-callouts` = 55): **55/55** after the edits (incl. `.gob` on body).
- **Full Playwright** (workers=1, port 8000, under `/tmp/gob-full-playwright.lock`): **796 passed, 7 skipped, 1 failed** (13.7m; 804 incl. the 4 new court-chrome guards). The one failure, `fcc-fresh-after-game.spec.js:259` (FCC warm-paint cache), is **not a regression**: this branch touches **zero** FCC files (only `court.html` + `UX_System.md`), and the test passed **5/5** re-run in isolation (`--repeat-each=5`) — a pre-existing load flake.

STATUS: COMPLETE. Scoreboard + start prompt + controls on gob tokens; `check_ui_tokens` exit 1 is the pre-existing `box-score.css:494` (not this change); the one full-suite failure is a pre-existing FCC flake (5/5 isolated).
