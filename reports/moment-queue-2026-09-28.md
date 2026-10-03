# Chapter 7 — Server-side moment queue

Branch: `feat/moment-queue` (from `origin/develop`). Ordering and the 1–2 cap are computed in `BackEnd/utils/moment_queue.py` and attached to `GET /franchise/command-center/data`. The browser only opens the existing modal for each `moments_for_this_visit` kind. No sim engine, `cpu_week_pool`, `sim_rng`, or finalize changes.

## Priority table

Lower number first. Built from the existing eligibility flags; `recruiting_results_modal` is omitted.

| Priority | Kind | Tier | Duration | Surface |
|---|---|---|---|---|
| 10 | championship | SEASON PEAK | long | Pop-up |
| 20 | bracket_reveal | MILESTONE | long | Pop-up |
| 30 | walk_on_welcome | MILESTONE | long | Pop-up |
| 40 | conference_rs_region | MILESTONE | short | Pop-up |
| 50 | region_bye | MILESTONE | short | Pop-up |
| 60 | archetype_evolution | MILESTONE | short | Pop-up |
| 70 | bracket_update | WEEKLY | — | Office card |
| 80 | recruit_visit | WEEKLY | — | Office card |

Each item: `{id, kind, tier, priority, payload_ref, seen_key, title, line}` plus `duration` on pop-up tiers. Payloads stay on the existing CC keys (`pending_championship_moments`, `conference_rs_region_modal`, …). Archetype reads `user.archetype_evolution_pending` and is also copied onto the CC response as `archetype_evolution_pending`.

Same table is in UX_System §10.

## Cap rule

`moments_for_this_visit` is the first pop-up-tier item (MILESTONE or SEASON PEAK).

A second item is included only when:

1. the first item’s `duration` is `short`, and
2. the second item’s tier is MILESTONE or SEASON PEAK.

Championship, bracket reveal, and walk-on are `long`, so they take the whole visit. Conference / region-bye / archetype are `short`, so two of those can share a visit.

Remaining pop-up-tier items stay in `moments`. Their seen keys are not marked until a visit actually shows them, so they are eligible next time.

WEEKLY items (`bracket_update`, `recruit_visit`) go to `weekly_card_items` (also copied onto `office_digest`). They never take a pop-up slot. `officeHome.js` paints them with the existing card helper in the This Week column.

## What was removed

Office no longer chains `ChampionshipMoments.processPendingMoments` → Sammy `maybeShow` ×4 → `BigNewsModals.maybeShow`, and it no longer runs `ArchetypeEvolutionModal.run(competing)` (which consumed the pending flag even when skipped).

`franchise-command-center.js` starts `MomentQueue.play` after tutorial return alerts settle. The 300-retry wait loop is gone from the Office Big News path (`maybeShow` is a no-op; `showBracketReveal` / `showBracketUpdate` return Promises). Sammy modules still expose `maybeShow` for isolated component tests; FCC does not call them.

`recruiting_results_modal` is not opened from the Office. The signing celebration is the week-35 hub reveal in `recruiting-hub.js` (`/franchise/week-35-reveal-seen`).

### What still references `recruiting_results_modal`

| Place | Role |
|---|---|
| `franchise_routes._build_recruiting_results_modal_payload` | Still builds the payload on CC data (builder tests keep working) |
| `PATCH /franchise/recruiting-results-modal-seen` | Seen endpoint unchanged |
| `bigNewsModals.js` `showRecruitingModal` / `markRecruitingSeen` | Still in the file; Office does not call them |
| `tests/test_big_news_modals.py` | Payload eligibility / seen |
| `tests/test_walk_on_reveal_window.py` | Mentions the builder |
| `tests/test_browse_rev.py` | Browse-rev writer for the seen PATCH |
| `tests/e2e/tournament-view.spec.js` | Stub field `eligible: false` |
| `Season_Init_System.md`, Ch7 inventory, Recruiting Hub ux-build-plan | Docs |

Marking seen for queued kinds uses the existing endpoints and keys, unchanged.

## Cut-players and tutorial (outside the queue)

Tutorial return alerts (`GOBTutorialAlerts.whenReturnAlertsSettled`) still go first. They are not queue items.

`MomentQueue.play` starts only after those alerts settle (or immediately if the module is absent).

Cut-players stay blocking roster work, outside the queue. After tutorial settle, the cut modal waits for the queue promise so it does not stack on a queue overlay. The pre-existing 8s safety net remains.

`?tab=tournament-view` still skips the Office moment queue (same browse-tab gate as before).

Archetype: if the queue defers it, `run()` no longer consumes the pending flag. `showFromQueue` presents and then PATCHes `/api/auth/archetype-evolution-seen`.

## Frontend wiring

`js/shared/momentQueue.js` reads `moments_for_this_visit` and opens, in order:

- championship → `ChampionshipMoments.processPendingMoments`
- bracket reveal/update → `BigNewsModals.showBracketReveal` / `showBracketUpdate`
- conference / bye / walk-on / visit → `showFromQueue` on the existing Sammy modules
- archetype → `ArchetypeEvolutionModal.showFromQueue`

`MomentQueue.queueLabel` supplies `"1 of 2"` to the modal eyebrow when two pop-ups share the visit.

## Tests

- `tests/test_moment_queue.py` — order, cap (long=1, short+popup=2), weekly fold, recruiting omitted, deferral; mongomock + sqlite seen-endpoint deferral.
- `tests/e2e/moment-queue.spec.js` — three eligible moments, this visit opens two pop-ups, the rest on the next visit.

## Risks

- A `long` first moment (championship / bracket reveal / walk-on) blocks a second pop-up even if the second is SEASON PEAK.
- Several championship moments still count as one visit slot (one kind).
- WEEKLY moments never pop up, even on a quiet visit. They only appear on the Office card.
- The 8s cut safety net no longer opens while a queue overlay is visible; it waits for the queue promise. A hang still delays cut until the promise settles.
- `recruiting_results_modal` is still on the CC payload. A future caller that opens it from that flag would bring the duplicate signing pop-up back.
- Sammy `maybeShow` still has the old 300-retry loop for isolated tests; only the Office path is off that loop.
- Archetype “1 of 2” is available to the modal but the evolution chrome has no eyebrow to show it.

## Fix pass

Merged `origin/develop` (pytest-green + feat/home-base-data). No conflicts.

### Weekly card actually renders

`weeklyCard` was unshifted onto `second` *after* `second.forEach` had already appended into column 2, so the card never left the array. It is built and unshifted before the columns fill. It sits at the top of This Week using the existing `card` / `card-h` / `sn-row` chrome. No new colours.

Playwright now asserts the card is visible with a recruit_visit item and a bracket_update item.

### Cut modal once-only

`showTs` ran from the queue promise *and* from `setTimeout(8000)` with no guard. Restored `let shown = false`. The 8s net does not open the cut modal while a queue overlay is visible (same selectors as `fccHasCompetingModal`: championship, archetype reveal, alpha feedback, tutorial alert, Sammy, Big News). If an overlay is up at 8s, it waits for the queue promise instead.

Playwright: one pop-up + `cut_required` → cut modal count is 0 while the pop-up is up, then exactly 1 after dismiss, still 1 after 8.5s.

### Weekly hrefs

Server sets `href` on each WEEKLY item:

- `bracket_update` → `/franchise-command-center.html?tab=tournament-view`
- `recruit_visit` → `/recruiting.html`

The Office row is an `<a class="ow-row">` with that href (franchise/team ids appended from the current URL). Existing Office link style (`color: inherit`). Label is a small uppercase line above the sentence; a → sits on the right.

### Weekly-card lifetime (eligibility window; no browser seen-mark)

WEEKLY items no longer go through a modal, so they do not PATCH seen. The card lasts as long as the **existing server flag** stays eligible:

| Kind | Stays while | Ends when |
|---|---|---|
| **recruit_visit** | Weeks 20–26 and `_build_recruit_visit_modal_payload` finds a visit for **this week** | The week advances (that week’s assignment is no longer current) or week leaves 20–26. Does not outlive its week. |
| **bracket_update** | Current week is in `BRACKET_UPDATE_WEEKS` (28, 29, 31, 33, 34, 35) and `_build_bracket_update_modal_payload` is eligible (EOS/national checks, that week’s `update:{tier}:{season}:{week}` key unseen) | The week leaves that map, or that week’s update_key is no longer eligible. Does not outlive its update week. |

No extra server-flag change: both builders are already week-keyed. The old modal seen-stamp only hid the card mid-week after a pop-up; the week window already ended it.

### Cut modal on top

The earlier shot caught `fcc-modal-enter` (box opacity 0→1 over 200ms), so Office cards showed through the text. The spec now waits until the box’s computed opacity is 1, then `elementFromPoint` at the title centre and the button centre must land inside `.fcc-cut-required-modal`. That passed without a stacking-CSS change. Screenshot is taken after the opacity wait.

### Weekly card copy/layout

Dropped the inner “This week” header. Each row is label over line, left-aligned, full width (`.ow-row`, not `.sn-row`). Label is small uppercase, no wrap. Whole row is the link; hover uses the existing Office row wash (`--white-5`). A muted → sits on the right, same idea as Box Score →. CSS scoped to `.office-weekly`.

### Self-check (1280)

- `reports/moment-queue/office-weekly-card.png` — Column 02 is titled This Week only (no second header on the card). Top card has two stacked rows: **TOURNAMENT UPDATE** over “The tournament bracket moved this week.” with → on the right; **RECRUIT VISIT** over “Ellis Clemons is visiting this week.” with → on the right. Next game (AT 21. Morristown) and Team snapshot sit **below** that card, not over it. No overlapping text. Neutral chrome, no gold. Green only on Advance (Play Next Game).
- `reports/moment-queue/popup-1-of-2.png` — One Sammy modal over the Office. Eyebrow reads “1 OF 2 · REGION TOURNAMENT QUALIFIED”. Nothing else stacked.
- `reports/moment-queue/cut-after-popup.png` — The cut modal is **on top** and fully opaque. Title “Trim Your Roster to Size”, body about assigning 2 players, and the green “Assign Practice Squad” button are all readable. Office cards (result, What moved, next game) sit **behind** the dimmed page; none of their text is drawn over the modal title or button. No Sammy overlay. Advance label is Assign Practice Squad.

### Gates (small fix pass)

`tests/test_moment_queue.py`: 8 passed. `tests/e2e/moment-queue.spec.js` + `tests/e2e/office-frontend.spec.js`: 13 passed, 1 skipped. Did not re-run the full suites (no cut-modal stacking CSS; changes stayed in officeHome, `.office-weekly` CSS, the spec, and the report).

STATUS: COMPLETE
