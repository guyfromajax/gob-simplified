# Open design rulings for Jamie, part 2: 2026-10-01

The Styleguide's remaining colour-law open questions (Styleguide.md › Open questions 1–5). Each has a current shot (1280, scroll 0), 2–3 options, and a one-line recommendation. **No product code changed.** Mocks are test-only CSS injected by a scratch Playwright spec (`page.addStyleTag`). Computed colours below were read from the live page in the same run. Answer the summary table at the bottom in one reply.

Shots: `reports/jamie-decisions-2/*-1280.png`. Fixtures are stubbed (hosted e2e server, route stubs): Lawrence, Week 15, a win, 3 recruiting events pending, one to-do that blocks Advance.

---

## 1. Delta chips: which surfaces must be neutral?

The law says ▲/▼ are neutral. Today:

| Surface | Today | Where |
|---|---|---|
| Office › Team snapshot › "Moved most" `.chip.up/.down` | **green ▲ / red ▼** (`rgb(52,236,39)` / `rgb(255,109,109)`) | `gob-components.css:83-84`, `officeHome.js chip()` |
| Office › weekly card (rank/conference ▲, training ▲1/▼1) | neutral (your earlier override) | `office-home.css` `.wkc` |
| Box score › player attribute chips `.attr-chip.up/.down`, `.attr-chip-val` | green / red, annotated `positive-data` | `box-score.css:491-522` |
| Player view › attribute changes `.gob-chg .is-up i` | green ▲ | `gob-tables.css:815` |
| `.attr-chip .arr.up/.down` | green / red, **no live emitter found** (dead CSS) | `office-home.css:309-310` |

Current: `office-current-1280.png` (Moved most: green ▲2, red ▼3; weekly card neutral).

- **A.** Neutral everywhere: every ▲/▼ is white text on a neutral chip (`office-mock-chips-neutral-1280.png`).
- **B.** Status quo: data surfaces (Moved most, box score, player view) keep green/red. Only the weekly card is neutral.
- **C.** Up = green (positive data), down = neutral; red gets no role (`office-mock-chips-up-only-1280.png`).

**Rec:** **C.** It is the law applied exactly (green = positive data, red has no role), and it keeps the good-news signal. Delete the dead `.attr-chip .arr` rules either way.

## 2. W/L plates: neutral everywhere, or data colour in tables?

| Surface | Today |
|---|---|
| Home Base `.wl.w/.l`, Office weekly card, box score | white **W** plate / outline **L** (already neutral) |
| League › Rankings "Last Week", Team › Schedule `.gob-wl.up/.dn` | **green W / red L** letters (`rgb(52,236,39)` / `rgb(255,109,109)`), `gob-tables.css:921-922` |
| `gob-components.css` `.wl.win/.loss` (green/red) | **no live emitter found**: only `.office-res`, itself dead (§4), references it |

Current: `rankings-current-1280.png`.

- **A.** Neutral everywhere, using the Home Base plate (white W / outlined L) in tables too (`rankings-mock-wl-plates-1280.png`).
- **B.** Neutral text only: W/L letters in body colour, no plate (`rankings-mock-wl-text-neutral-1280.png`).
- **C.** Keep green/red in tables as data.

**Rec:** **A.** One W/L treatment app-wide, and the plate scans well down a column. Delete the dead `.wl.win/.loss` rules.

## 3. Orange beyond saves: which stay?

The law says orange = saved/committed ("there is something to save"). The presence dot (neutral) and Save-at-rest (neutral until dirty, shipped on `ux/logo-fallback-save-state`) are already settled. One row each:

### 3a. Rail count badge
`--badge: var(--orange)` (`gob-tokens.css:39`). The Recruiting rail badge is `rgb(247,148,32)`, and `.urgent` pulses it.
Current: `office-current-1280.png` (orange "3" on the Recruiting rail icon).
- **A.** Keep orange.
- **B.** Neutral: white plate, dark digit; the urgent pulse stays (`office-mock-badge-neutral-1280.png`).

**Rec:** **B.** A count is attention, not a save; a white badge still pops on the dark rail.

### 3b. `.td-gate` tag and `.is-on` (checker allow-list)
- `.td-gate` is the "BLOCKS ADVANCE" tag: orange text and ring, `gob-components.css:330`.
- `.is-on` has two orange users:
  - Recruiting › Signing "My Orders" tab when selected (`recruiting-signing.css:288`, annotated `committed`);
  - advanced-tutorial picks `.fg-pick.is-on` (`gob-advanced.css:203`, a file the checker excludes).
- `.gob-save-toast.is-on` is already neutral.

Current: `office-current-1280.png` (tag), `reports/signing-orders-panel/after-orders-2-1280.png` (orders panel).
- **A.** Keep orange and leave them on the allow-list.
- **B.** Neutral tag (white text, white ring); `.is-on` selections neutral (selected = neutral emphasis). Remove `.gated`, `.td-gate` and `.is-on` from the allow-list (`office-mock-gated-neutral-1280.png` shows the tag).

**Rec:** **B.** A tag and a selected tab are not saves. The words "BLOCKS ADVANCE" carry the meaning.

### 3c. Office blocking-step outline
`.wk-step.gated` uses a 1.5px orange ring and an 8% orange fill (`office-home.css:213-216`); `.todo.gated` is the same (`gob-components.css:332-333`).
Current: `office-current-1280.png` ("Assign practice squad").
- **A.** Keep the orange outline.
- **B.** Neutral strong outline (`--white-62`) and a light fill (`office-mock-gated-neutral-1280.png`, shown together with 3b).

**Rec:** **B.** The step is still the loudest thing in the strip without borrowing the save colour.

### 3d. Attitude bars
Buckets 0–19 / 20–39 / 40–59 / 60–79 / 80+ are **red / orange / white-45 / green-mix / green** (`office-home.css:356-363`).
Current: `office-current-1280.png` (Team snapshot › Attitude).
- **A.** Keep the 4-colour ramp.
- **B.** Monochrome ramp, white-18 to white-90; the emoji carry the mood (`office-mock-attitude-mono-1280.png`).
- **C.** Drop only the orange stop: 20–39 becomes a muted red. Red / neutral / green stays as a data ramp (`office-mock-attitude-no-orange-1280.png`).

**Rec:** **C.** Orange is the only law clash; the rest reads as a data ramp, like the RT ramps.

### 3e. Functional-modal accent default
- `resource-pages.css:404-408` defaults `.gob-modal-accent` to `#F79420`. It beats `auth-bar.css`'s zero-specificity neutral default on the 12 pages that load `resource-pages.css`.
- Live on: "Trim Your Roster to Size" (FCC), Training "Lock In", the username modal, the tutorial lineup modals, and training-shell. Measured accent: `rgb(247,148,32)` over a green CTA.

Current: `modal-accent-current-1280.png`.
- **A.** Keep the orange default.
- **B.** Neutral default (white-14 hairline, the same as the auth-bar default); modals opt in to a colour (`modal-accent-mock-neutral-1280.png`).

**Rec:** **B.** An accent is decoration; the Trim modal shows orange next to green Advance for no reason.

### 3f. Tutorial alert
**Already neutral on develop** (`tutorials-fte-tokens`). `gob-tutorial.css` `.gob-talert*` has no orange, and the primary is a white "Start lesson". The Styleguide question is stale here.
Current: `reports/tutorials-fte-tokens/after-alert-1280.png`.
- **A.** Confirm neutral (no work) and drop it from the question.
- **B.** Reinstate an orange primary.

**Rec:** **A.**

### 3g. Leave-confirm "Stay" (Assign Practice Squad)
`cut-players.js attemptLeave()`: when players are selected, Back opens "Leave Without Assigning?". **Stay** is the orange primary (`rgb(247,148,32)`) on a red accent (`rgb(255,109,109)`), and Leave is the neutral secondary. (The shared `GOBLeaveConfirm` used elsewhere is Keep Editing / Discard / **Save**, where orange is lawful.)
Current: `stay-current-1280.png`.
- **A.** Keep the orange Stay.
- **B.** Neutral primary (white Stay, as in the tutorial alert) and a neutral accent (`stay-mock-neutral-1280.png`).

**Rec:** **B.** Stay saves nothing; orange should mean a save.

## 4. Team-colour wash on the weekly / result card

- The weekly card `.wkc` is **neutral**. Measured: `linear-gradient(white-4 → white-2)` with a `white-8` border.
- `.office-res` (`gob-components.css:157-158, 289, 338-343`) still paints a `--team-primary` gradient and a top bar, but **no code creates `.office-res`** (0 elements on the Office). It is dead CSS from the earlier result card.

Current: `office-current-1280.png`.
- **A.** No wash anywhere: record it and delete the dead `.office-res` rules.
- **B.** Team-colour wash on the result card (example colour `#c8102e`: `office-mock-wkc-wash-1280.png`).
- **C.** A 3px team-colour top bar only (`office-mock-wkc-bar-1280.png`).

**Rec:** **A.** It is your existing weekly-card override. The WIN plate carries the result, and the wash fights the green Advance.

## 5. Destructive actions: neutral, or a sanctioned red?

| Where | Today |
|---|---|
| Home Base › Delete program confirm `.btn-del` | red outline button (`rgb(255,109,109)` text, 55% red ring); Cancel takes focus. This is **Ch7 decision 7** ("delete is a red-outline confirm, never a red button in the slot"), `home-base.css:124` |
| Home Base slot menu "Delete program…" `.pop-i.danger` | red text, `home-base.css:115` |
| Assign Practice Squad confirm / leave / error modals | red accent (`cut-players.js:78, 278, 296, 405`). The default for any unspecified accent is `is-red`. |

Current: `destructive-current-1280.png` (delete confirm), `stay-current-1280.png` (red accent).
- **A.** Neutral everywhere: white-outline Delete button, neutral accents (`destructive-mock-neutral-1280.png`).
- **B.** Sanctioned red for **irreversible deletes only** (the Ch7 decision 7 red outline + menu item). Everything else, including the practice-squad modals, uses a neutral accent.
- **C.** Red for every destructive or warning modal (status quo, including the practice-squad modals).

**Rec:** **B.** It keeps your Ch7 delete ruling and stops red leaking onto reversible, everyday confirms.

## Known open item (no options needed)

- **On-canvas Phaser text** (court scene: canvas HUD, announcements and labels drawn in Phaser JS) is still off the colour law. UX_System lists it as still open: it is equivalence-locked (`sim-broadcast-fit`, `sim-team-callouts`) and ramp-governed, so it needs its own sim-safe pass, not CSS.

---

## Summary: answer in one reply

| # | Ruling | Options | Rec |
|---|---|---|---|
| 1 | Delta chips ▲/▼ | A neutral everywhere · B status quo (data green/red) · C up green, down neutral | **C** |
| 2 | W/L in tables (Rankings, Schedule) | A white plate / outline everywhere · B neutral letters · C keep green/red | **A** |
| 3a | Rail count badge | A orange · B neutral white | **B** |
| 3b | `.td-gate` tag + `.is-on` selections | A orange (allow-list) · B neutral, drop from allow-list | **B** |
| 3c | Office blocking-step outline | A orange · B neutral strong outline | **B** |
| 3d | Attitude bars | A 4-colour · B monochrome · C drop orange stop | **C** |
| 3e | Functional-modal accent default | A orange · B neutral default | **B** |
| 3f | Tutorial alert | A confirm neutral (already is) · B orange | **A** |
| 3g | Leave-confirm "Stay" | A orange primary · B neutral primary + accent | **B** |
| 4 | Team-colour wash on weekly / result card | A none, delete dead `.office-res` · B wash · C 3px bar | **A** |
| 5 | Destructive actions | A neutral · B red outline for irreversible deletes only · C red everywhere | **B** |
| — | On-canvas Phaser text | known open item, own pass | — |

## How the shots were made

- A scratch spec and config in the session scratchpad (not committed), run against the hosted e2e server (`playwright.config.js`, mongomock) with route stubs for `/franchise/command-center/data`, `/roster/…`, `/franchise/list` and the like.
- **First run** under `/tmp/gob-full-playwright.lock` (16:35:04–16:35:20): **5 passed**.
- Two Office mocks used `--white-60`, which is not a token (the outline and one bar rendered blank). I fixed them to `--white-62` and **re-ran only the Office test** under the lock (16:35:45–16:35:58): **1 passed**. That was a second, single-test Playwright run.
- No full suite (docs only).
