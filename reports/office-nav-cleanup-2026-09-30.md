# Chapter 8 — Office + nav cleanup (4 items)

Branch `ux/office-nav-cleanup` off `origin/develop` (6f0bbcf18; includes the Ch7
weekly card f63998d11).

---

## 1. Office standings back to ≥4 rows at 1280×720

**Cause.** The middle-column grid row at 1280 is fixed at **570px** (the office is a
no-scroll fit screen: `main` = 664px = strip 76 + grid + 18px top + 18px bottom pad).
Column 2 is `office-h(20) + This Week(152) + Team snapshot(255) + standings`, with
12px inter-card gaps. Four standings rows need **579px** of column-2 content, which
overflows the 570px column box by 9px — `fitStandings`' overflow check
(`col.scrollHeight − col.clientHeight > 1`) then windows it down to 3. Measured: at
4 rows `col.scrollHeight=579, col.clientHeight=570, colOv=true`; at 3 rows `570=570,
false`. (Confirmed the Ch7 weekly card is what tipped it: column 1 used to be two
shorter cards.)

**Fix.** Tighten only the **Team snapshot** card's padding at 1280
(`html.gob-shell.gob-office.gob-1280 .office-snap { padding-top: var(--dsp-4);
padding-bottom: var(--dsp-2) }`) — it has the most slack. That drops column-2's
four-row content to ~559px, so it fits inside the existing 570px grid row **without
growing the grid** (growing it would make column 2 the tallest and stretch/distribute
the other columns' gaps) and **without shrinking any type or the standings row
height**. Column 1's weekly card is untouched and uncropped.
File: `FrontEnd/static/css/office-home.css`.

Assertion restored to `>= 4` at 1280×720 in `office-frontend.spec.js` (still all 8 at
≥1440). See §2 for the proof run.

**Proof.** Measured 8× at 1280×720 → 4 rows every time, `mainScroll=0`; 1920×1080 → 8
rows (`mode: all`). Screenshots below.

## 2. The flaky Office standings test

**Cause — measurement before the layout was at rest.** `openOffice()` waited a fixed
`waitForTimeout(900)`. The display font (Bebas Neue Pro) loads async; its metrics are
taller than the fallback, so `fitStandings` (which runs during first paint) measures
the wrong card heights and can window one row short, and the card edges/gaps keep
shifting a frame or two after the font swap. Whether the 900ms sleep landed before or
after that reflow was luck — hence the flake.

**Fix (cause, not retries).**
- **Product:** the office now re-runs its standings fit on `document.fonts.ready`
  (`officeHome.js`) — the real signal that the font metrics are final, not a timeout.
- **Test:** `openOffice()` now waits on `document.fonts.ready` and then until a **layout
  signature** (standings row count + every column card's top/bottom edges) is stable
  across 5 consecutive frames — i.e. the office is genuinely at rest — replacing the
  900ms sleep.

**Proof:** `office-frontend.spec.js -g "standings show every conference team"
--repeat-each=10 --workers=1` → **10 passed**. `six states fit` (also uses `openOffice`
+ the heading-gap invariant that the flake tripped) → **5/5** and green in the full spec.

## 3. Duplicate id `#alpha-badge`

**Cause.** `franchise-command-center.html` (the franchise shell) loads BOTH
`alphaBanner.js` (inserts a badge at body-top, guarded by an existing-badge check) and,
via `authGuard.js`, `authBarInit.js` (bakes a `#alpha-badge` into the injected auth
bar, unguarded). alphaBanner usually won the async race and inserted first, then
authBarInit added a second — a duplicate id. Grep showed one static badge per page and
two injectors; a DOM count on FCC gave **1,2,2,2,2** across 5 runs. Both are
`display:none` on the shell (`gob-shell.css` hides `#auth-bar`/`#alpha-badge`), so it's
purely an invalid-id / `getElementById` hazard, not a visible double. (Public auth
pages — login/signup/reset-password — early-return in authGuard, so they keep their
single static badge.)

**Fix.** `authBarInit.js` `injectAuthBar()` removes any stray pre-existing badge before
inserting its bar, so the bar's badge is the only one. alphaBanner's guard already
covers the reverse order.

**Assertion added.** `tests/e2e/alpha-badge-single.spec.js` asserts
`querySelectorAll('#alpha-badge').length <= 1` on FCC (the fixed page) and on
login/signup/reset-password. `--repeat-each=5` → **20 passed** (FCC race gone).

## 4. `test_gob_nav.js` exitFlow failures

**Cause — a deliberate product change the test wasn't updated for.** 4 exitFlow tests
expected a synchronous `history.go(-1)`; the current product defers the jump unless
`document.readyState === 'complete'`. That deferral was added in **commit `c20fcbd13`**
("Open Training and the report inside the franchise shell…") — `goWhenSettled` was
changed from "defer only while loading/interactive, else run" to "run synchronously
only when complete, else defer to the `load` event" (Chrome drops `history.go` while a
document is still loading; the training-report button is in the first HTML chunk). The
author added the `'exitFlow waits out an in-progress load'` test (which sets
`readyState='loading'` and drives `load`) but left the other four on a fake document
with **no** `readyState` (→ treated as not-complete → deferred → no navigation).

**Fix (test, to the intended behaviour).** A real page is fully loaded when the user
clicks an exit, so `exitFlow`'s `history.go` runs synchronously. The fake window's
`document` now defaults to `readyState: 'complete'`; the one test that wants the
deferred path still overrides it to `'loading'`. `node tests/test_gob_nav.js` → **30
pass, 0 fail**.

---

## Gates

- **pytest** `--ignore=tests/e2e -q`: **4135 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed** (198s).
- **check_migration_gates.py**: **passed** (Gate A 0/0; Gate B 138 lines/46 files — unchanged; I added no franchise-identity URLSearchParams reads).
- **check_ui_tokens.py --strict**: exits 1 on **11 reward-gold hits, all in `css/office-home.css`** (the Ch7 weekly card, already on develop), 0 new green/orange. My Ch8 diff adds no colour tokens (office-home.css `--reward-gold` count 6 = develop). This is the reward-gold false-positive the checker fix targets — noted and moved on per the brief.
- **test_gob_nav.js**: 30 pass, 0 fail.
- **Full Playwright** (workers=1, port 8000, CI unset, no other run): **745 passed, 3 skipped, 0 failed** (10.6m).

## Screenshots (`reports/office-nav-cleanup/`)

- `office-1280-before.png` — develop: standings windows to **3** rows.
- `office-1280-after.png` — after: standings shows **4** rows (Gamma/Amariabi/Delta/Echo); Team snapshot marginally tighter; nothing clipped, weekly card intact, nothing below the fold.
- `office-1920-after.png` — after: all **8** standings rows (full table).

## Files changed

| File | Item |
| --- | --- |
| `FrontEnd/static/css/office-home.css` | 1 — snapshot padding trim (1280) |
| `FrontEnd/static/js/shared/officeHome.js` | 1/2 — re-fit standings on `document.fonts.ready` |
| `tests/e2e/office-frontend.spec.js` | 1/2 — assertion `>=4`; layout-signature "at rest" wait |
| `FrontEnd/static/js/shared/authBarInit.js` | 3 — remove stray badge before injecting the bar |
| `tests/e2e/alpha-badge-single.spec.js` | 3 — new single-badge assertion |
| `tests/test_gob_nav.js` | 4 — fake document defaults to `readyState: 'complete'` |

STATUS: COMPLETE
