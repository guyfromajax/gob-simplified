# Token hygiene (2026-10-01)

**Status: ready for review.** Branch `chore/token-hygiene`, pushed. Not merged. Closes Styleguide open questions 6–11. **No visual change.**

## What closed

| # | Open question | Done | Where |
|---|---|---|---|
| 6 | Navy aliases local to one sheet | `--you`, `--you-soft`, `--you-line`, `--you-ink` are tokens, same values. `recruiting-spine.css` no longer declares them and reads the tokens (its uses, and those in `recruiting-dock.css` and `recruiting-signing.css`, are untouched). | `css/gob-tokens.css`, `recruiting-spine.css` |
| 7 | RT colours carried their own values | `rtBucket.js` now writes `--rt-*-color` as `var(token, same value)`: `--tier-red`, `--tier-yellow`, `--tier-green`, and `--blue` for A. `.rt-unknown` reads `--white-40`. | `js/shared/rtBucket.js`, `css/rt-buckets.css` |
| 8 | `css/gob-buttons.css` hard-coded | Colours, display face, weight, tracking, radius and padding read tokens, each with the same value as a fallback. Header comment now states the law (orange = save or commit only; it said "advances UI"). | `css/gob-buttons.css` |
| 9 | Position colours had no tokens | `--pos-pg`, `--pos-sg`, `--pos-sf`, `--pos-pf`, `--pos-c`, same values. The one consumer (the sim broadcast position label) reads them. | `css/gob-tokens.css`, `js/phaser/utils/simGamePresentation.js` |
| 10 | Tier digit ceiling | **The code was right:** `Math.floor(n / 10)`, no cap, and `attributeDisplay.js` already said so. Only the token comment was wrong ("Player digit 0–16"). Comment fixed; no logic touched. | `css/gob-tokens.css` |
| 11 | Repo `CLAUDE.md` pointer | Frontend section points the colour law at `Styleguide.md#colour-law`. | `CLAUDE.md` |

Styleguide "Open questions" is now 1–5 plus one new, narrower question (below). A "Closed mechanically" table records the six.

## One thing that could not be purely mechanical: RT A and `--tier-blue`

| Fact | Value |
|---|---|
| RT A / A+ / A++ has always painted | `#4A90D9`, which is `--blue` |
| `--tier-blue` (attribute tiles) | `#6BA4E0`, a brighter step; its comment says "Do not point it back at `--blue`" |

Pointing RT A at `--tier-blue` would change every A grade on screen. That is a design call, so RT A reads **`--blue`** (same pixels) and red / yellow / green read the tier tokens (same values). The Styleguide RT table and Blue row said `--tier-blue` for RT; they now say `--blue`, which is what renders. The leftover question is listed as open question 6: one blue or two.

## Values that still exist outside the token file, on purpose

| Where | What | Why | Guard |
|---|---|---|---|
| `rtBucket.js` `color` | the four RT hexes | `getRtColor()` feeds scripts that need a concrete colour (inline bars, court overlays), and pages with no gob tokens | `tests/test_token_mirrors.py` |
| `matchupsUiShared.js` `POSITION_COLORS` | the five position hexes | exported for colour maths; currently has no caller | same test |
| `var(--token, value)` fallbacks in `gob-buttons.css`, `rt-buckets.css`, `simGamePresentation.js` | same value as the token | modules inject these into pages that are not `.gob` | same test: every fallback must equal its token |
| `gob-buttons.css` literals | `#15181f` (ink on orange / green), `#ffa84a` and `#4dff3f` (hovers), `rgba(255,255,255,.85)` (ghost text), heights, min-widths, font sizes | No token has that value. `--fs-*` tokens scale at 1920, so swapping a font size would change the button there. | test pins the list |
| `recruiting-spine.css` | `--you-edge`, `--list`, `--list-soft`, `--list-line` | Not in the brief's four. Left local. | none |

## Proof of no visual change

Shots in `reports/token-hygiene/`, 1280, `page.screenshot` at scroll 0. `before-*` from develop's copies of the seven changed front-end files, `after-*` from this branch.

| Shot | Changed pixels | Where |
|---|---|---|
| `set-lineup-1280` | 0 | |
| `hub-pool-1280`, `hub-leans-1280` | 7 each (max channel delta 5) | one recruit avatar corner; the same spot differs by 4 between two shots of identical code |
| `roster-1280` | 75 in the top bar and rail; **0 in the page content** | logo edge, rail icons |
| `buttons-token-page-1280`, `buttons-hover-ghost-1280` | 75 in the top bar and rail; **0 in the button panel** | logo edge, rail icons |
| `buttons-no-tokens-1280` (fallbacks only) | 0 | |

The FCC top-bar logo edge and rail icons flicker between identical runs (up to 80 pixels, max channel delta 15; measured by shooting the same code twice). Inside the page content and inside the button panel the difference is 0.

**A capture artefact I chased down.** My first BEFORE set showed 14 corner pixels different on the hub (delta ≤ 3), repeatably. I restored each changed file in turn, then all of them: with every old file back, the hub rendered pixel-identical to the new code, twice. The first capture was the outlier, not the code. The committed BEFORE set is a fresh single run from the old files.

## Guards

| Test | Asserts |
|---|---|
| `tests/e2e/token-hygiene.spec.js`, Set Lineup | `.rt-low/mid/high/elite/unknown` compute to the same five colours; `--rt-*-color` names a token; `getRtColor()` still returns the hexes |
| …, Recruiting hub | the four aliases are declared in `gob-tokens.css` only; your ladder slot, chip and rank ink compute to the same values |
| …, Roster | `--pos-*` equal `POSITION_COLORS`; RT letters keep their colours |
| …, Buttons on a token page | every variant: fill, border, ink, highlight, face, weight, radius, padding, heights; hover fills |
| …, Buttons with no tokens | the same values through the fallbacks, on a page with no tokens at all |
| `tests/test_token_mirrors.py` (8 tests) | RT hexes = tokens; RT A is `--blue` and `--tier-blue` differs from it; position hexes = tokens; every `var()` fallback in the two injected sheets = its token; the button sheet has no literal a token covers; aliases declared once; tier comment; `CLAUDE.md` pointer |

**On the old code:** the three token-specific e2e tests fail; the two button tests pass, as they should (they assert the paint did not change). On the branch: 15/15 at `--repeat-each=3`.

## Gates (on `2466170bc`: this work + develop `874e9a175` merged in)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4312 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (221s). +8 are the new mirror tests; +2 came with develop. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe). New-surface hits 0 / 0 / 0. Legacy 402, unchanged. |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| `grep -cE '#[0-9A-Fa-f]{3,8}\b' Styleguide.md` | 0 |
| Full Playwright, one run under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017 | exit 0. **836 passed, 7 skipped, 0 failed** of 843 (14.6m). Lock taken 16:20:28, released 16:35:03. Run on `74966b32b`, before the merge below. |
| Failure re-runs at `--repeat-each=5` | none needed |

The Playwright run was one tracked job that took and released the lock itself while I blocked on it (the foreground limit is 10 minutes; the suite takes about 14).

Merge: develop moved by 14 commits during the Playwright run (audit's logo fallback and Save-until-dirty, a signing-orders test fix, QA docs). One conflict, in `Styleguide.md`: three adjacent colour-law rows. **Kept both sides:** audit's Orange row (Save only while there is an unsaved edit) and this branch's Navy and Blue rows. `UX_System.md` merged cleanly. Audit's branch had already removed the "Pending audit" notes.

After the merge I re-ran pytest, the token gate, the migration gates and four specs (`token-hygiene`, `prep-modules-gameplan`, `prep-modules-playbooks`, `jamie-rulings-batch`: 28 passed, 1 skipped). **The full Playwright suite was not run a second time**; its result above is from before the merge. None of the merged files is one this branch changes, apart from the two docs. The before/after shots are also from before the merge.

## Docs

| File | Change |
|---|---|
| `Styleguide.md` | Navy row lists the aliases; Blue row and the RT table say `--blue` for RT; position colours added to "Data palettes outside the table"; Buttons notes both sheets read tokens and adds the neutral-primary role; "Closed mechanically" table; open questions 6–11 replaced by one. Still 0 hex. |
| `UX_System.md` | §2: the fallback rule for injected sheets, the literal-plus-test rule for scripts, the warning that `--fs-*` / `--dsp-*` / `--dsz-*` scale with density, and that the aliases and `--pos-*` are tokens. |
| `CLAUDE.md` | Colour law → Styleguide. |

## Unsure

| # | Item |
|---|---|
| 1 | **`simGamePresentation.js` is court presentation code.** I changed one constant (the position label's inline colour now reads `var(--pos-*, same hex)`). No sim, finalize or RNG code. The sim equivalence specs ran in the full suite. Say if you would rather that file stay untouched; the tokens would then have no consumer. |
| 2 | **`getRtColor()` still returns hex.** Making it return `var()` would break any caller that does colour maths or draws on canvas. The test holds the hexes to the tokens instead. |
| 3 | **Styleguide RT table changed from `--tier-blue` to `--blue`.** That is a correction to match what renders, not a ruling. Open question 6 asks which you want. |
| 4 | **`POSITION_COLORS` has no caller** (dead export). Left, with a comment. |
| 5 | `tests/e2e/zz-tb-debug.spec.js` is still on disk (untracked, comment-only); `rm` is denied to me. |
