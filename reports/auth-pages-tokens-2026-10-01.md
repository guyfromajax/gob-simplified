# Auth pages on gob tokens: 2026-10-01

Branch `ux/auth-pages-tokens` from `origin/develop` (`dd931bab4`), in `~/gob-audit`. Upstream unset after `checkout -b`. Merged develop `cbb3ebdac` (court-chrome part 1) before push; clean, `NEW_DESIGN_CSS` keeps every entry. A laptop crash interrupted the first gate run; everything below was re-run on the merged tree.

## Scope

| Page | Surfaces |
|---|---|
| `login.html` | form, error, links |
| `signup.html` | alpha access code step (OTP), code error, code accepted + account step, Request Access modal |
| `reset-password.html` | request form, sent (success), set new password (`?token=`) |

One sheet: `auth.css` (only these three pages load it). Logout lands on `/mode-select.html`, not an auth page; out of scope.

**Visual only.** HTML changes: `class="gob"` on `<html>`, a `gob-tokens.css` link, and `auth-button--advance` added to the LOG IN and SIGN UP buttons. No ids, names, endpoints, headers, token/session or rate-limit code touched; all page `<script>` blocks are unchanged.

## Colour law applied

| Element | Before | After |
|---|---|---|
| LOG IN, SIGN UP (enter the game) | orange | **green** `.auth-button.auth-button--advance` |
| Continue (code), Request Access, Got it, Send Reset Link, Update Password | orange | neutral white plate (`.gob-btn--neutral` recipe) |
| Error message | pink `#ff9b9b`, literals | `--red` text, 10% fill, 45% border |
| Success message, "Code accepted" | green | neutral (`--text-87` / `--text-100`) |
| Links (Sign up / Log in, Request access, change, forgot hover) | orange | underlined `--text-100` / `--text-87` |
| Input focus, password-toggle focus | orange | `--white-45` border, `--white-12` ring / `--white-70` outline |
| Request Access modal top bar, alpha disclaimer | orange | neutral |
| Page atmosphere | navy + blue radial glow | neutral `--white-4` lift + diagonal banding |
| Type | literal families | `--font-display` (Bebas Neue Pro) headings/buttons, `--font-body` (Inter) |

`auth.css` has no colour literals left; it is in `NEW_DESIGN_CSS` (strict). One layout fix: the signup account step had no gap and SIGN UP was content-width. `#signup-step-account` now uses the form's 18px column gap (visible in `before`/`after-signup-account`).

## Shots

`reports/auth-pages-tokens/{before,after}-<surface>-{1280,1920}.png` via `page.screenshot` at scroll 0; BEFORE on develop CSS (`AUTH_PAGES_BEFORE=1`) before any edit. Surfaces: `login`, `login-error`, `signup-code`, `signup-code-error`, `signup-account`, `signup-request-access`, `reset-request`, `reset-sent`, `reset-set`. All API calls stubbed (`/app-config` alpha on, login 401, access-code check, reset request).

## Tests

- `tests/e2e/auth-pages-tokens.spec.js`: shots + computed-style guards:
  - html.gob and tokens resolve; Inter body, Bebas titles and buttons;
  - no blue atmosphere;
  - LOG IN and SIGN UP green with dark ink; other buttons neither orange nor green;
  - error text and border red;
  - focus, links, "Code accepted" and success not orange or green;
  - modal bar neutral.
- **Helper fix:** the colour helper parses `color(srgb …)`, which is what computed `color-mix()` returns. Without it the guards could not see those colours.
- **Fails on old code:** ran the guards (soft) with develop's four files served via `page.route` from a scratchpad config (swapping files in the worktree was denied). They fail on every page. Examples: `LOG IN green rgb(247,148,32)`, `code accepted rgb(138,240,127)`, `success border rgba(52,236,39,0.4)`, `no blue atmosphere … rgba(39,64,142,0.55)`, `html.gob`, `modal bar`, `reset submit`. Two did not fire on develop: error red (develop's pink already reads as red) and input focus.

## Gates (merged tree)

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4298 passed**, 14 skipped, 108 xfailed, 2 xpassed, **0 failed** (241.27s). Same two XPASS as the previous branches (`known_failures.py` not edited). The pre-crash run under heavy load showed 20 skipped / 4292 passed; the clean re-run is back to 14. |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (run without a pipe) |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files. No `--write-allowlist`. |
| Playwright full `tests/e2e --workers=1` under `/tmp/gob-full-playwright.lock` (PORT=8244) | **806 passed, 7 skipped, 0 failed** (13.2m), on the merged tree. No failures, so no `--repeat-each=5` reruns. All 3 `auth-pages-tokens` tests passed. Skips: 5 existing `test.skip`s plus 2 "handoff frames" tests that skip without `FRAMES_BASE`. |
| Targeted `auth-pages-tokens.spec.js` | 3 passed |

## Files

`FrontEnd/static/auth.css`, `login.html`, `signup.html`, `reset-password.html`, `scripts/check_ui_tokens.py` (`NEW_DESIGN_CSS` + docstring), `_documentation_master/11_Design_Systems/UX_System.md` (new "Auth pages" section), `tests/e2e/auth-pages-tokens.spec.js`, this report + shots.

## Unsure

- **Brief vs law on the auth submit:** the brief says "primary submit that enters the game = green". UX_System says green is the one Advance per screen; LOG IN / SIGN UP are treated as that Advance. Reset submits do not enter the game, so they are neutral.
- **Alpha badge:** `alpha_badge_gold.png` is an image, not CSS; untouched.
- **Earlier temp worktree:** the one from the tutorials task may still be at `<scratchpad>/old`. The scratchpad dir may not survive the reboot.
