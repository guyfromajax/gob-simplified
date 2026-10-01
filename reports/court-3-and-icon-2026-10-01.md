# Court panels (Jamie #3/#4/#5) + desktop app icon (#11) — 2026-10-01

Branch `ux/court-3-and-icon` off `origin/develop`. Records three settled rulings from
`reports/jamie-decisions-2026-10-01.md` and ships the desktop app icon. Visual-only on the
court; no animation timing, court geometry, or sim/UESS/finalize/sim_rng changes. The five
equivalence specs stay 55/55.

## #3 — Court live game-state colours: KEEP as data (recorded, no recolour)
Settled in `UX_System.md` as a documented **game-state** category (alongside the RT ramp and
the Sim-broadcast palette), exempt from the everyday colour law. New game-state colour is
annotated `/* colour-law: game-state */`. **No court colour was changed for this ruling.**
Covers the Playcall Center state colours, reveal HUD, lower-third / secondary ribbons, the
active-player HUD (gold has-ball/defender, `#4caf50` AUDIBLE), momentum bars, and the
scoreboard quarter/shot-clock + timeout pips.

## #4 — Court side panels: opaque grey → gob navy surfaces + translucent whites
`FrontEnd/static/court.html` (`<body class="gob">` already present). Migrated the player-stats
and team-stats panels off ad-hoc greys to gob tokens:

| Was (grey) | Now (token) | Where |
|---|---|---|
| `#1a1a1a` | `--surface-2` (#141824 navy) | `.player-stats-panel` |
| `#151515` | `--surface-1` | `.team-box-score` |
| `#222` | `--surface-1` | `.player-box-score th` |
| `#333` / `#444` | `--line` / `--line-strong` | panel/box/header/table borders |
| `#2b2b2b` / `#222` (td) | `--line` | table row borders |
| `#252525` | `--white-6` | row hover |
| `#aaa` / `#888` / `#bbb` | `--text-60` / `--text-87` | header + label text |
| `#fff` | `--text-100` | hover text |

**Kept as team identity (annotated `/* colour-law: team-identity */`):** the team-colour
**edge borders** (`.player-stats-panel.away/.home`) and the subtle side tints — they mark which
team the panel is. Momentum-bar fills (red/green direction) are game-state data (#3), untouched.

## #5 — Side-panel stat toggles: selected state NEUTRAL (not team colour)
`.toggle-btn.active` and `.team-toggle-btn.active` were the panel's team colour
(`--home/away-vibrant`). Now **neutral**: `--white-20` fill, `--text-100`, `--white-28` border;
the per-team `.away` override was removed. Choice controls are neutral.

**Before/after** (`reports/court-3-and-icon/`, scroll 0, 1280 + 1920, pre-game modal hidden so the
DOM panels paint — the Phaser canvas is black in headless): `before/after-court-{1280,1920}` and
`before/after-panel-away-{1280,1920}`. Before = grey panel + **orange** S1/S2/S3; after = navy
panel + **neutral** S1/S2/S3, team edge border retained.

**Guards:** `tests/e2e/court-panel-tokens.spec.js` — #4 panel bg is `rgb(20,24,36)` (`--surface-2`),
not the old `rgb(26,26,26)`; #5 selected toggle is `rgba(255,255,255,.2)` (`--white-20`), never the
team orange `rgb(255,98,0)`. Fails on develop.

## #11 — Desktop app icon
Source: `desktop/build/icon-source-1024.png` (1024×1024 full-bleed square, committed). Generated
with Pillow + `iconutil`:
- **`desktop/build/icon.png`** — 1024 full-bleed (electron-builder / general).
- **`desktop/build/icon.icns`** — macOS, the standard rounded-rect mask + ~10% transparent margin
  (content inset to 80%, corner radius ≈ 22.37%), full iconset 16→1024 via `iconutil -c icns`.
- **`desktop/build/icon.ico`** — Windows, 16/32/48/64/128/256 full-bleed.

`desktop/pack.js` **already** conditionally appends `--icon=build/icon` when the platform icon
(`icon.icns` on mac / `icon.ico` on win) exists — so generating the icons activates it with **no
pack.js change**. (Verified: the file's `hasIcon` guard now resolves true.) The `icon.iconset/`
intermediate is not committed. Regeneration command (if the source changes):
`./.venv/bin/python <scratch>/make_icons.py` (Pillow) then `iconutil -c icns build/icon.iconset`.

## Gates (`.venv/bin/python`)

- **pytest** `--ignore=tests/e2e -q`: **4298 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (234s). One test — `test_desktop_shell_local.py::test_pack_icon_flag_is_conditional` — asserted the icons did **not** exist; updated to assert they now do (keeping the conditional-logic assertions). 2 XPASS backend/pre-existing.
- **`check_ui_tokens.py --strict --no-write`**: **exit 0** (real code; new-surface 0/0/0; court.html legacy colour literals 407 → 380).
- **`check_migration_gates.py`**: **passed** (Gate A 0/0; Gate B 134/43).
- **Equivalence specs** (`game-winner`, `sim-broadcast-fit`, `court-layout`, `game-start-sequence`, `sim-team-callouts` = 55): **55/55**. Plus `court-panel-tokens.spec.js` guard **2/2**.
- **Full Playwright** (workers=1, port 8000, under `/tmp/gob-full-playwright.lock`): **826 passed, 7 skipped, 1 failed** (16.6m). The one failure, `signing-orders-panel.spec.js:251` (deliverable signing frame), is **not a regression**: no signing/recruiting files changed, and it passed **5/5** isolated (`--repeat-each=5`) — a pre-existing load flake.

STATUS: COMPLETE. #3 recorded (game-state kept as data), #4 panels → navy surfaces, #5 toggles neutral, #11 icons generated; all gates green (the one full-suite failure is a pre-existing flake).
