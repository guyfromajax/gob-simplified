# Chapter 7 PR 2 — Home Base, OFFLINE ("Your Career") + 3 server follow-ups

Branch `app/home-base-offline`, from `origin/develop` (PR 1 already merged).
Builds the desktop right zone "Your Career" and lands the three server follow-ups
PR 1 flagged. Online is unchanged except the titles numeral now reads a server total.

---

## Files changed

| File | Change |
| --- | --- |
| `BackEnd/utils/local_coach.py` | `coach_career_payload` adds `titles_total` (sum of `championships_total`) |
| `BackEnd/api/auth_routes.py` | leaderboard `top` cap 10 → **15**; pin threshold 10 → 15; `titles_top` stays 5 |
| `BackEnd/utils/around_the_league.py` | `_hydrate_slot` adds `team_slug` + `asset_strategy` |
| `BackEnd/utils/career_data.py` | top-season rows add `finish_is_title` (title-finish → reward gold) |
| `FrontEnd/static/css/home-base.css` | ported the offline `.cr/.tcase/.shelf/.tro/.med/.tsn-*` block (scoped `.gob`), `--med/--med-lg/--tsn-h` tokens |
| `FrontEnd/static/js/shared/homeBase.js` | offline `rightOfflineHtml` renders the "Your Career" zone from a view model; left-zone strip suppressed when `!online` |
| `FrontEnd/static/mode-select.js` | `hbCareerZoneModel` + `hbResolveBanner`; `loadCoachCareer` runs offline (loopback) and gates the loader; `hbAroundCard` uses `team_slug`/`asset_strategy`; titles read `titles_total` |
| `tests/test_home_base_data.py` | asserts `titles_total`; extends the key-set check |
| `tests/test_home_base_server_followups.py` | **new** — leaderboard cap 15, `_hydrate_slot` two new fields |
| `tests/e2e/home-base-offline.spec.js` | **new** — the whole offline zone |
| `tests/e2e/home-base-online.spec.js` | fixture gains `titles_total`; desktop test reflects the now-present zone |

## Server follow-ups (a/b/c + one)

- **(a) `titles_total`** — pre-summed on the server; both the online strip and the
  offline numeral read it, so the client does no arithmetic. `hbCareerModel` no
  longer sums `championships_total`.
- **(b) leaderboard cap 15** — `top=ranked_entries[:15]`, pin threshold raised to
  match so a rank 11–15 viewer is not both in the list and pinned. `titles_top` = 5.
  1280 still renders its own `--lb-rows` (7) from the same payload.
- **(c) `_hydrate_slot`** — `team_slug` (`path_slug_for_display_name`) +
  `asset_strategy` (`resolve_team_display`). `homeBase`/`mode-select` resolve Around
  GOB art through `hbResolveBanner` (the doors' TB-art path) instead of the name.
- **(one extra, needed) `finish_is_title`** on each top-season row. The gold law
  reserves reward gold for a title finish; the client must not classify the finish
  string, so the server flags it. Additive, defaulted `False`, in-progress rows `False`.

## The offline zone

- **Numerals** (`.cr-n`): record + `win_pct_display`, `titles_total`, `seasons_completed`,
  `geek_points`. Per-numeral hollow at 0. Caption "Every game you coach, in any
  program, adds to these." shows only in the all-zero state.
- **Trophy Case**: titles → gold medallions (N/R/C), the three milestones → neutral
  (S/B/A). All-Americans and season records are filtered out of the shelf. Empty →
  four labelled dashed slots (Conference/Region/National/First signing class).
  "View all →" is behind `HB_TROPHY_CASE_HREF` (still `''`), same as the online link.
- **Top Seasons** (`.tsn`): the server's order verbatim, up to 5. Row = rank, banner
  art (`team_slug`, TB via the generated producer), team + season, W–L, finish
  (gold only when `finish_is_title`), season GP. In-progress → "In progress · Week N",
  no finish. Unfilled ranks are dashed; the first carries the next/first-game copy.
- No remote calls: fed only by `GET /franchise/coach-career` over loopback. Left zone
  and green rule are the online build, unchanged.

## Omissions / deviations

- **TB art on Top Seasons rows** degrades to core/general when the program is custom:
  the top-season row carries `team_slug` but not colours or `asset_strategy`, so
  `hbResolveBanner` can't regenerate custom art there (only Around GOB, which now
  carries both, gets full TB art). Following the "omit, don't invent" rule.
- **First coach archetype** milestone shows a generic "First coach archetype" label —
  the archetype name needs the manifest (`/api/auth/me`), which is online-only.
- `finish_is_title` is a fourth server change beyond the three named follow-ups;
  called out above because the gold law requires a server-owned title flag.

## Gates

- **pytest** `--ignore=tests/e2e -q`: **4054 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed** (195s).
- **Playwright** full suite, `workers=1`, port 8000 free, `CI` unset, no other run active:
  **650 passed, 3 skipped, 0 failed** of 653. The PR 1 app-router flake did not fire.
- New coverage: `home-base-offline.spec.js` (15 tests) — offline guard (zero
  community/auth requests), zero state (4 hollow numerals, 4 dashed medallion slots,
  5 dashed ranks + first-row copy), populated state (solid numerals; **computed**
  reward-gold asserted on title medallions and title finishes only, milestones and a
  non-title finish neutral; Top Seasons in server order incl. an in-progress row),
  fit at 1280×720 and 1920×1080 in both states, plus the five screenshots.

## Self-check — `reports/home-base-offline/`

Every zone's own rect measured against the viewport (overflow:hidden hides run-off).

| Shot | Green buttons | Below fold | Differences from the frame |
| --- | --- | --- | --- |
| `first-1280` (zero) | **0** — both slots vacant, ghost CTAs | none | — |
| `two-1280` / `populated-1280` (2 programs) | **1** — Lawrence "Enter" (last played); Chapel Hill ghost | none | — |
| `two-1920` | **1** | none | numerals 80px, medallions/rows scale; same layout |
| `online-strip-1280` | **1** | none | titles reads `titles_total` (3); online look unchanged |

Notes from opening each:

- **Zero** reads as potential: `0–0 / 0 / 0 / 0` hollow, caption present, four dashed
  medallion slots (C·Conference, R·Region, N·National, S·First signing class), five
  dashed ranks, rank 1 "Coach your first game and your season ranks here".
- **Populated**: `73–22 · .770`, `3` Titles, `4` Seasons, `4,060` GP — all solid.
  Trophy Case "3 titles · 2 milestones": N/R/C gold, S/B neutral. Top Seasons in GP
  order 1,860 / 1,120 / 980 / 140 — the two title finishes gold, "National semifinal"
  neutral, Chapel Hill "In progress · Week 6", rank 5 dashed "Your next season can land here".
- Reward gold appears only on the N/R/C medallions and the two title finishes; the
  test asserts the computed colour `rgb(240, 197, 96)` and that milestones/the
  semifinal finish are not that colour. No gold on chrome, buttons or numerals.
- Desktop makes no community/auth request; the zone is fed by the loopback
  `coach-career` alone, and the left zone carries no career strip.

`git log -1` confirms the commit sits on `app/home-base-offline`.

STATUS: COMPLETE
