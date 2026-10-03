# Championship moments re-show every visit

Date: 2026-09-30
Branch: `fix/champ-moment-repeat` from `origin/develop` @ `34ba2137a`

## Symptom

During the Conference Tournament, the "Conference Regular-Season Champions" takeover (`trophy_spotlight`) showed after every tournament game / Office remount, not just once after week 26.

## Repro log

Enqueue is one-shot. `enqueue_trophy_spotlight_for_user_conference` is called only at week 26→27 (`BackEnd/api/franchise_routes.py:8146-8150`) after conference tournaments are initialized. `enqueue_moment` de-dups on `(type, conference|region, season, game_id)` (`BackEnd/utils/franchise_championship_moments.py:200-228`). A second tournament game does not re-queue the same spotlight. The pending row that Jamie kept seeing was the original one, never consumed.

Client leak (pre-fix `championshipMoments.js:794-819`):

```
await SeasonPeak.showTitle(...)   // Promise resolves only via close()
for moment in moments:
    await dismissOnServer(...)    // POST /franchise/championship-moments/dismiss
```

`SeasonPeak.showTitle` (`seasonPeak.js:334-393`) resolves only from Continue / Enter / Escape (`bindContinue` at `310-321`). Box score is a plain `<a class="lnk" href="...">` (`seasonPeak.js:378`) with no click handler. Navigation does not call `close()`. `dismissOnServer` was a normal `await fetch` with no `keepalive`.

Production `trophy_spotlight` has no `game_id` (`franchise_championship_moments.py:502-516`), so the Box score link is hidden on that type. Jamie's live exits after week 26 were Office remounts (next tournament game, Advance, rail, reload). Those abort the unresolved `showTitle` promise the same way Box score does.

| Exit | Dismiss fired (old) | Re-shows next Office |
|---|---|---|
| Continue / Enter / Escape | yes (promise resolves) | no |
| Box score (`<a>` navigate, when `game_id` is present) | no | yes |
| Advance / rail / next tournament game | no | yes |
| Reload / tab close | no | yes |

Stateful e2e on the old `processPendingMoments` (temporarily reverted): takeover visible, `POST /franchise/championship-moments/dismiss` count stayed `0` until Continue. Box score path timed out waiting for that POST. After restore, the same test dismisses on mount (`count === 1`) and the second Office load has no `.pk`.

`pending_championship_moments` before/after (code + e2e state):

1. After week 26→27 enqueue: `[{id, type: trophy_spotlight, ...}]`
2. After takeover mounts (old): still that row — dismiss not sent
3. After Box score / rail / next game (old): still that row
4. Next Office load (old): `list_moments` still returns it → queue v2 still includes `championship`
5. After takeover mounts (new): `POST dismiss` with `keepalive: true` → `$pull` by id → empty
6. Next Office load (new): no championship item

## Root cause

`FrontEnd/static/js/shared/championshipMoments.js:794-819` (pre-fix) consumed only after `showTitle` resolved. Any non-Continue exit left the row in `pending_championship_moments`. Next Office visit replayed it. Enqueue was not wrong.

Same after-resolve mark on:

- `season_review` — `momentQueue.js` `openSeasonReview` PATCHed `/franchise/season-review-seen` only in the `.then` after `showReview` resolved
- every MILESTONE kind — `openMilestone` PATCHed the seen key only after `MilestoneModal.show` resolved. Esc/× do resolve, so they already marked the current item. Rail / reload / tab close while open leaked the same way

Desktop extra: SQLite `$pull` compared the whole array element to `{"id": moment_id}` (`BackEnd/persistence/sqlite_query.py:302-307` old). Mongo treats that spec as a query. Desktop `consume_moment` therefore never removed the row even when dismiss did fire. Hosted Mongo `$pull` was already correct.

## Fix

Consume when shown, not when Continue is clicked.

- `championshipMoments.js`: `dismissOnServer` is `fetch(..., { keepalive: true })` as soon as `processPendingMoments` starts, before `showTitle` / `showMoment`. Same path for every championship type (`conference_championship`, `region_championship`, `national_championship`, `trophy_spotlight`, `banner_raise`).
- `momentQueue.js`: `markMilestoneSeen` for `season_review` and MILESTONE kinds fires when the overlay is opened. `patchJson` uses `keepalive: true`.
- `sqlite_query.py`: `$pull` with a dict spec is a query on the element (`_pull_matches` + `match_query`), matching Mongo. Desktop dismiss now actually removes the row.
- `UX_System.md` §10: seen PATCHes and championship consume fire when the overlay mounts.

Did not change sim, finalize, or enqueue.

Queue v2 unchanged: tiers, max two per visit, championship + season_review still pair as 1 of 2 / 2 of 2. If the player Box-scores off the title, the title is consumed and the review (never shown) stays eligible for the next visit.

## Other moment types with the same leak

| Type | Path | Leak |
|---|---|---|
| `trophy_spotlight` | `processPendingMoments` | yes |
| `conference_championship` | same | yes |
| `region_championship` | same | yes |
| `national_championship` | same | yes |
| `banner_raise` | same | yes |
| `season_review` | `openSeasonReview` after-resolve PATCH | yes (rail/reload/tab close; no Box score link) |
| MILESTONE (`signed_class`, `walk_on_welcome`, `bracket_reveal`, `region_bye`, `conference_rs_region`, `first_archetype`, `elimination`) | `openMilestone` after-resolve PATCH | yes on rail/reload/tab close; Esc/× already marked the shown item |

## Tests

- `tests/e2e/champ-moment-repeat.spec.js`: trophy_spotlight Box score then Office again (not shown); same for Continue; conference title Box score; desktop `GOB_BUILD_PROFILE`. New e2e failed on the old consume-after-close path, then passed.
- `tests/test_championship_moment_consume.py`: `consume_moment` removes the row on mongomock and SQLite; a second Office queue build has no `championship` kind. Also locks query-style `$pull`.

Screenshots (1280, `page.screenshot`, scroll 0):

- `reports/champ-moment-repeat/takeover-1280.png` — takeover once
- `reports/champ-moment-repeat/office-next-visit-1280.png` — Office on the next visit, no takeover

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4236 passed**, 16 skipped, 109 xfailed, **1 xpassed**, 0 failed (228s). XPASS is `test_leaders_view_scope_filters_to_user_conference` (pre-existing). |
| Playwright `tests/e2e --workers=1`, PORT=58639, CI unset | **765 passed**, 5 skipped, **0 failed** (12.4m) |
| `.venv/bin/python scripts/check_ui_tokens.py --strict --no-write` | exit 0. Colour-law new-design 0. FCC freeze unchanged. |
| `.venv/bin/python scripts/ci/check_migration_gates.py` | passed. Gate A: 0 imports in 0 files. Gate B: 138 lines in 46 files. |

## Unsure

Production `trophy_spotlight` has no `game_id`, so the Box score link is not on that takeover. The e2e fixture adds a `game_id` so the requested Box score exit can be clicked. The live leak Jamie hit is the same consume-after-close path on Office remount after the next tournament game.

`consume_moment` still returns `True` on a second call because `fold_browse_rev` always `$inc`s `browse_rev`. The row is gone; the boolean is not a reliable "was it present" flag. Left as-is.
