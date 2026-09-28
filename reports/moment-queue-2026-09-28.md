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
- The 8s cut safety net can still open the cut modal while a queue overlay is up if the queue hangs.
- `recruiting_results_modal` is still on the CC payload. A future caller that opens it from that flag would bring the duplicate signing pop-up back.
- Sammy `maybeShow` still has the old 300-retry loop for isolated tests; only the Office path is off that loop.
- Archetype “1 of 2” is available to the modal but the evolution chrome has no eyebrow to show it.

## Gates

Related tests during work: `tests/test_moment_queue.py` + sibling modal tests, 25 passed; `tests/e2e/moment-queue.spec.js` passed.

Full Playwright (`env -u CI`, port 8088, workers=1): **543 passed, 3 skipped** (7.9m). One new spec vs the prior 542 on develop.

`pytest --ignore=tests/e2e` on this branch: **3865 passed**, 9 failed, 14 skipped, 109 xfailed, 1 xpassed. Failures (same names as origin/develop / the audit-agent set):

- `test_env_static_safety`
- `test_fcc_team_measures_radar_scale`
- `test_resource_page_scoping` ×2
- `test_tb_leak_detector`
- `test_training_page_phase5` ×3
- `test_player_stats` (flake)

No new Python failure from the queue. Servers stopped; regenerated `reports/` images restored.

STATUS: COMPLETE
