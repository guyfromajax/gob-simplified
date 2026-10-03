# Settings mute icons and close × — 2026-09-28

Branch: `fix/settings-mute-icons` (from origin/develop de2fef419). Fix commit 583910970.

## Outcome

The four mute buttons and the panel's close × now render flat on every page where Settings opens:
- a transparent background with the thin `--line-strong` frame;
- a speaker icon stroked in `--text-60` at rest and `--text-100` on hover;
- the existing red `.mute.on` state when muted.

The white squares came from the **browser's default button face**, not a legacy stylesheet rule.

## Root cause (computed styles, read via the DevTools protocol)

| Page | `.mute` / `.set-x` background | border | appearance | Winning source |
|---|---|---|---|---|
| mode-select (no shell) | `rgb(239,239,239)` | `2px outset` | auto | user-agent `button` style: no author rule set background/border |
| Office (shell) | transparent | 0 | auto | `gob-components.css:23` reset |
| standings (browse) | transparent | 0 | auto | same reset |
| recruiting (focus) | transparent | 0 | auto | same reset |

The component reset at `gob-components.css:23` was:

    .gob .top button, … ,.gob .gob-settings-host button{font:inherit;color:inherit;background:none;border:0;…}

Inside the shell the Settings host sits under `html.gob`, so `.gob .gob-settings-host button` matches.
On mode-select (and any other page outside the shell) `gobSettings.js` adds the host to `body` as
`<div class="gob gob-settings-host">` with no `.gob` ancestor, so the descendant selector never matched,
and Chromium's `ButtonFace` background and outset border showed through.

The SVG was never the problem. On all four pages it was 18×18, `display:block`, `fill:none`, with a 1.8px stroke
in `currentColor` = `--text-60` (rgba(255,255,255,.6)). That's a pale stroke on a light-grey face, so it
read as a blank white square. The legacy side has no `!important` on background, border or appearance,
so the fix needs none. The existing `color:…!important` on `.mute` and `.set-x` is unchanged.

## Fix (gob-components.css, tokens only, no new colours)

1. At the source: the reset also matches the host itself, `.gob.gob-settings-host button`, so
   outside the shell every Settings button gets the same reset as inside it.
2. Belt and braces, scoped to `.gob`: `.gob .mute` and `.gob .set-x` add
   `appearance:none; background:transparent; border:0; padding:0`. This also removes `appearance:auto`,
   which the shell reset left on.

The hover (`--white-7`) and `.mute.on` (red) backgrounds still apply: they are more specific.
Log Out (`.btn-ghost`) sets its own background and border with `!important`, so it is unaffected.

## Tests (tests/e2e/foundation-settings.spec.js)

"settings mute icons and close render flat on …" runs on mode-select, Office, standings (browse) and
recruiting (focus) at 1280×720. It checks that:
- The Music mute has a computed background `rgba(0,0,0,0)`, no background image, a 0px border and
  `appearance:none`.
- The colour is `--text-60`. Token values are resolved in the page, not hard-coded.
- The SVG has a non-zero box, `fill:none`, stroke = `--text-60`, a stroke width above 0, and the speaker-waves path.
- Hover turns the colour to `--text-100`.
- Click gives `.on`, `aria-pressed="true"`, the SPEAKER_OFF path (`M16 9.5l5 5`), and colour and stroke = `--red`.
  The other three mute buttons stay off and transparent.
- A second click gives `.on` removed, `aria-pressed="false"`, the SPEAKER icon back, and `--text-60`.
- The close × is transparent, has no border, uses `appearance:none` and `--text-60`, so it is not a white box.

Against the old CSS, mode-select fails on the background (`rgb(239,239,239)`), and the three shell pages
fail on `appearance:auto`.

Runs (UX §8, workers=1, port 8157, CI unset):
- foundation-settings + shell-1 + shell-1b + shell-2 + shell-site-footer: **49 passed**.
- Full suite (run when `ps` showed no other Playwright): **537 passed, 3 skipped** (the known
  environment-gated t3-detail, office-frontend and tournament-view skips).
- Server on 8157 stopped. Regenerated report images restored; the tree is clean.

## SELF-CHECK (screenshots opened)

`reports/settings-mute-icons/settings-mode-select-1280x720-music-muted.png`:
- **Master, Sound Effects, Ambience**: a grey outline speaker with sound waves, centred in a 32px rounded
  square with a thin light frame on the dark panel. No white fill.
- **Music (muted)**: a red speaker with an ×, in a faint red frame with a light red tint. The Music row
  label and slider are dimmed.
- **Close ×**: a small grey "×" at the top right of the header. No box or background.

`reports/settings-mute-icons/settings-office-1280x720-music-muted.png`:
- The same result in the shell. Master, Sound Effects and Ambience show grey speaker outlines in thin frames,
  Music shows the red speaker-with-× in the red frame, and the close × is a plain grey glyph with no box.

STATUS: COMPLETE
