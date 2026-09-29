# UX polish batch B — Game Plan, Playbooks, and "Changes May Not Be Saved"

Branch `ux/polish-prep-plan` from `origin/develop`. Front end only; no backend or sim change. Embed-bridge views stay embed-bridge.

## 0. Bug: "Changes May Not Be Saved"

**What it is.** It is the browser's own `beforeunload` dialog. The app has no copy with that wording, and Electron has no `will-prevent-unload` handler.

**Cause.** Each embed registered a leave check once per command-center document through `GOBNav.warnOnLeave`, and the check stayed armed after an in-app tab switch:

1. In-app switches (`CommandCenterTabs.show`) never asked the checks, so an edit stayed silently "dirty" after you left the view. The next *document* navigation (a link, Recruiting, a reload) then showed the browser prompt, even though the user was nowhere near the edited view.
2. The checks were plain "touched" booleans, not a comparison with saved values. Moving a slider and moving it back counted as an edit.
3. Playbooks had no dirty tracking at all.
4. A hosted Game Plan save ran the standalone page's navigate-after-save callback.

A no-edit probe on a real franchise (Training → Game Plan → Playbooks → Team › Schedule, dispatching a cancelable `beforeunload` at each step) reported no prompt. The prompt only came from state left armed by earlier edits, which fits causes 1 and 2.

**Fix.**
- `GOBNav.warnOnLeave(hasEdits, { view, confirm })`. `hasEdits` compares current values with the last saved ones.
- `CommandCenterTabs.show` calls `GOBNav.confirmLeave(proceed, view)` before leaving a view. With real edits, the owner's `confirm` opens the in-app `GOBLeaveConfirm` (Keep Editing / Discard / Save). The switch runs after Discard or after a save lands.
- `go`, `replace`, `back`, and same-origin link clicks ask the same checks, so leaving the document with edits also gets the in-app confirm.
- The browser prompt now fires only for a reload or window close with real edits.
- **Game Plan:** a snapshot comparison against `lastSavedSettings`, a revert on Discard, and a hosted save that stays on the view.
- **Playbooks:** the snapshot is the save payload with keys sorted, minus `_meta` and `even_distribution_all`. Also a revert on Discard and a hosted save that stays on the view.
- **Training:** edits are written to the existing session draft (`saveTrainingFormDraft`) as they happen, and the next open restores that draft. Nothing is lost, so there is no prompt.
- **Deviation from the brief's "make an edit, switch → in-app confirm" test, for Training only:** an edit there persists, so the test asserts no prompt instead.
- **Known limit:** a browser Back/Forward `popstate` is not guarded (documented in UX_System §6).

## 1. Game Plan layout

- Every track sits in one tokenised title column: `--gp-name-w: calc(--dsz-118 * 2 + --dsz-50)`. The shot-diet nest subtracts its own inset (`--dsp-14`). All tracks therefore share their start x, end x, and stop positions in each column. Measured within ±1px at 1280 and 1920.
- The `Offense` / `Defense` h2 headers are removed. The sections keep `aria-label="Offense"` / `"Defense"`.
- `Execution` (Offense Tempo, Play Alteration) is a new `.eb.grp-h`, the same element and class as `Transition`. Transition has a little extra space above it so the two headers sit on one baseline. The test checks the bottom edges and that the computed `font` is identical.
- Title-to-slider gap: `column-gap: var(--dsp-24)` on every row.

## 2. Game Plan copy

- Removed "Paint touches" / "Perimeter shots" and kept the rest of each line. Inside now reads "Your highest-percentage shots." and Outside reads "Lowest %, most impact."
- Tempo: "Work the offense or shoot fast."
- Defense: "Man uses talent. Zone uses IQ."
- Aggression: "Play it safe or take more risks."
- Play Alteration is unchanged: "Follow the script or read and react."

## 3. Shot diet (i)

- Wired to the existing tooltip component, `attributeTooltips.js`, through a new `addTextTooltip(element, text)`.
- The copy is the existing, exact-copy-required line from `FTE_v3_Sim_Full_Game_Brief.md`: "These three share touches — raise one, the others compete." It also sits in a hidden `#shot-diet-tip` that the button references with `aria-describedby`.
- `setupTooltipEvents` now shows the tooltip on `focus` and hides it on `blur`, as well as on hover. A mouseleave does not hide it while the trigger has focus. This also adds focus support to every other focusable tooltip trigger.

## 4. Playbooks

- **Divider:** a 1px `--line-strong` inset line plus `--dsp-24` of padding between the Playbooks and Playcall Center groups in the shot strip.
- **LIVE removed** from the HTML and from `paintShotWeights`.
- **Sliders:**
  - The track is wider: the weight column is `calc(--dsz-118 * 2)` and the track flexes to fill it. At 1280 it is about 3× the old 64px.
  - The value sits right next to the track.
  - `role="slider"`, `tabindex="0"`, `aria-valuenow` and `aria-valuetext` on both enforced and chip sliders.
  - Arrow keys move ±1 and Shift+Arrow ±5. The steps and the rebalancing are unchanged (`setEnforced`).
- **Offense/Defense toggle** has moved off the Prep tab row into `.playbooks-side-row` at the top of the playcall edit column, styled as the same neutral segment. The toolbar divider went with it.
- **Set play focus** shows on each row: "Inside · Target shooter SF".
- **Order:** Inside, then Attack, then Outside, with CMD high to low within each group, then name. This is applied at load and after a save. The shared `compareSetPlaysForDisplay` used by the FCC and Set Lineup is unchanged.
- **Lock:** it is now a top-level `.wl` button sitting next to its slider in a reserved slot, so tracks align across sections whether or not a row has a lock. It has `aria-pressed` and an `aria-label`. It was removed from the expanded detail, and clicking it doesn't expand the row.

## 5. Shared toast

- `GOBToast.show(text)` in `js/shared/gobToast.js` and `css/gob-toast.css`.
- One line of text in neutral chrome: `--surface-popover`, `--shadow-popover`, `--text-87`. No accent, no icon.
- `role="status"`, `aria-live="polite"`.
- Fixed over the centre of `.main`, so there is no layout shift (the test checks that the layout box's y is unchanged).
- Fades after 1500ms, and honours reduced motion.
- Used for the hosted saves: "Game plan saved" and "Playbooks saved". A failed hosted Playbooks save shows "Playbooks not saved. Try again."
- The class is `.gob-save-toast` because the tutorials' unscoped `.gob-toast` in `gob-tutorial.css` is also loaded in the command center. It paints an orange left border, and the first screenshot caught it.
- Documented in UX_System §14 "Save feedback", with the leave rules in §6.

### Existing save-feedback patterns (left as they are)

| Where | Pattern |
|---|---|
| `game-plan.js` `#toast` | Card with a green `#34EC27` check, then navigates on the standalone page. |
| `game-plan.js` `showUnsavedChangesWarning` | Inline-styled modal with an orange Save and "Leave Without Saving", plus the `gameplan_suppress_warning` flag. Now only the fallback. |
| `playbooks.js` `#toast` | Card, green on success and orange on failure, 3000ms. Also the load-failure toast in `initPlaybooks`. |
| Duplicate `#toast` ids | Both embeds import their own `#toast` into the command center. |
| `recruiting-hub.js` `showToast(title, sub, ok)` | Submit or run failures. |
| `set-lineup.js` `showToast(msg)` | Rule messages ("Free throw shooter must stay in the lineup"). |
| `playerView.js` | The button text swaps to "Saved" with `.is-saved`. |
| Tutorials `.gob-toast` (`gob-tutorial.css`) | Bottom-right card with an orange left border. |

The hosted Game Plan and Playbooks saves now use `GOBToast` instead of the first and third patterns. The standalone pages keep theirs.

## Screenshots (`reports/polish-prep-plan/`)

Taken by `POLISH_SHOTS=1` in `tests/e2e/polish-prep-plan.spec.js` from the captured fixture.

- **`game-plan-1280x720.png`, `game-plan-1920x1080.png`:**
  - Two columns with no Offense/Defense headers.
  - The Execution and Transition eyebrows sit on one line.
  - In each column every track starts and ends at the same x, and the stops line up down the page.
  - Orange appears only on Save Game Plan, green only on the top-bar Run Training Camp, and navy only on the active rail item.
- **`game-plan-tooltip-*.png`:**
  - Keyboard focus on the (i) shows the exact copy in the existing black tooltip bubble, centred over the icon.
  - At 1280 the bubble reaches near the rail edge but is not clipped.
- **`playbooks-*.png`:**
  - The shot strip has no LIVE and has a hairline between the Playbooks and Playcall Center groups.
  - The neutral Offense | Defense segment sits above Motion.
  - The locks are visible beside each track.
  - The tracks are wide, with the % right beside them.
  - Set Plays read Inside (CMD 82, 67, 60, 58, 34, 30), then Attack (86, 71…).
  - Orange appears only on Save Playbooks.
  - Navy marks only the rows in your Playcall Center, which are "yours".
- **`playbooks-toast-*.png`:** "Playbooks saved" in neutral chrome, centred low over `.main`, with no layout movement.

## Tests

`tests/e2e/polish-prep-plan.spec.js` is in the default suite and stubbed from `tests/e2e/fixtures/prep-plan.json`. It has 14 tests, all passing:

- **Leave prompt:**
  - For each of Training, Game Plan and Playbooks, with no edits, switching to Schedule gives no prompt and no dialog.
  - Moving a Game Plan slider and back gives no prompt.
  - A real Game Plan edit, followed by an in-app switch, opens the in-app confirm. Keep Editing stays on the view; Discard leaves it.
  - A real Playbooks edit, followed by a switch, opens the confirm, and Save posts once and leaves.
  - A Training edit gives no prompt, because it is kept as a draft.
- **Game Plan:**
  - At 1280 and 1920: track left and right x within ±1px per column, equal widths, and stops within ±1px.
  - No Offense/Defense headers; Execution and Transition present and matching.
  - The new copy is present, and the removed lines are gone.
- **Tooltip:** shows on hover, hides when the pointer leaves, and shows on focus.
- **Playbooks:**
  - No LIVE; the toggle sits beside the editor, not in `.pg-tools`; the divider is present.
  - Focus order and CMD order are correct, and the focus label shows.
  - The lock is visible without expanding, sits next to the track, and toggles.
  - The track is at least 118px wide.
  - Arrow ±1, Shift ±5.
- **Toast (Game Plan and Playbooks, both sizes):** it appears on save, is `aria-live="polite"`, has no border accent and causes no layout shift, and is gone at 2s. The view stays put, with nothing left unsaved.

## Gate (UX_System §8)

- **pytest** (`--ignore=tests/e2e`): **4047 passed, 0 failed** (16 skipped, 109 xfailed, 1 xpassed).
- **Playwright**, full suite: workers=1, port 8012, `CI` unset, and no other Playwright run was going. The result was **578 passed, 1 failed, 3 skipped** (582 in total).
  - The one failure is `app-router.spec.js` › "rankings opens in place, stays cached, and restores history". It fails at line 258, where Forward should reach `#rankings-view`.
  - It is **pre-existing:** it fails the same way with all of this branch's tracked changes stashed (plain `origin/develop`), 2 out of 2 runs. Not caused by this PR.
- `node tests/test_gob_nav.js`: 26 passed, 4 failed. The four are `exitFlow` cases, and they fail identically with develop's `gobNav.js`, so they are pre-existing too.

## Self-check

- **Colour law:**
  - Green is only the top-bar Advance.
  - Orange is only Save Game Plan, Save Playbooks and the Save button in the leave confirm.
  - Navy is only "yours" (the rail's active item, your Playcall Center rows).
  - The segment, locks, sliders and toast are neutral. There is no reward gold.
- **Tokens:** all new CSS uses tokens and is scoped:
  - `html.gob-shell .gpc …`
  - `#playbooks-view …`
  - `.gob .gob-save-toast`
- **Heading leak:** no new `h3` inside `#franchise-container .tab-content`. The leave confirm mounts on `body`.
- **Embed bridge:** kept. Two scripts load before `loadIsolated`, and one CSS link was added per view.
- **Files left alone:** `mode-select.*`, `rosterView`, `teamAttributesView`, `teamScheduleView` and the headshot CSS are untouched.
- **Cleanup:**
  - Regenerated report images were restored.
  - The report folders the suite created were removed.
  - The exploration server on 8241 was stopped and its SQLite file deleted.
  - The probe spec was deleted.

STATUS: COMPLETE
