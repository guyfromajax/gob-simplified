# Chapter 7 Home Base — data prep + offline guard — 2026-09-28

Branch: `feat/home-base-data` (from origin/develop 479d7bf1d). Code commit bc554ace3. No redesign:
the layout and "Find Your Program" are unchanged (the quiet secondary button comes with the Claude Design pass).

Note: this worktree already had uncommitted edits to seven files when I started, from another
agent: `franchise_routes.py` (a `name_by_id` → `display_name_by_id` hunk in `_standings_rows_from_doc`),
`UX_System.md`, `check_env_safety.py` and four test files. I left them in place and unstaged. In
`franchise_routes.py` only my hunks were committed (the index was built from my copy with that hunk
reverted; the committed file compiles on its own).

## 1. last_played on GET /franchise/list

**No existing field fits.** The franchise doc has no "last played" timestamp:
- The `updated_at` writes in the franchise routes are on FTD/FPD/training docs, not on `franchises`.
- `browse_rev` is a counter bumped by every franchise write, including browse-only changes.

So I added `franchises.last_played_at` (a UTC datetime; it round-trips through the SQLite save as `{"$date": iso}`).

**Where it's written (route level only):** `@marks_last_played` (`BackEnd/utils/franchise_last_played.py`)
wraps these routes:
- `save-result`;
- `complete-week`, `complete-week/phase-a`, `complete-week/phase-b`;
- `sim-rest-of-tournament`, `sim-championship`;
- `finish-season`.

It stamps after the handler returns successfully. It skips when the payload has `idempotent: true`,
so retries and box-score reloads of a finalized week don't count as play, and it never stamps on an exception.
`start-cpu-sims` (the background CPU slate) is deliberately not stamped. Nothing is written inside the sim
engine, `cpu_week_pool`, `sim_rng`, `stat_updater`/finalize or `_complete_week_finish_cpu_and_persist`. A test
asserts that the sim modules never mention the field.

**Payload:**
- Each card has `last_played_at` as an ISO UTC string (`"2026-09-28T20:00:00Z"`), or `null` if the franchise has never been played since this ships.
- The list has a top-level `most_recent_franchise_id`: the latest `last_played_at`. A never-played franchise ranks by creation time (the ObjectId timestamp), below any played one.

The UI doesn't need to sort.

## 2. Coach career offline

**Where the numbers are incremented today (online):**
- `users.record` in `BackEnd/utils/user_game_commit.py::commit_user_game_record`. This is called once per
  game from `stat_updater.finalize_game` after the `applied_games` claim. It `$inc`s `record.wins/losses/total_games`,
  plus `discount_*`, `archetypes.*` and `alpha_feedback_games`, then `$set`s `record.win_rate`, `lead_archetype` and `updated_at`.
- `users.championships_total` in `BackEnd/utils/franchise_championships.py::_inc_championship`, via
  `maybe_award_conference_rs_championship` (conf_rs, when brackets are built after week 26) and
  `maybe_award_franchise_eos_title_championship` (conf_t, region, national on the final). Both are called from the complete-week, sim and EOS routes. It also `$inc`s `championships_by_team.<TEAM>.<kind>`.
- Both are read by `/api/auth/me`.

**Why nothing persisted offline:** the desktop principal is `user_id = "local-desktop-user"`, which isn't an ObjectId. On
the SQLite save, `users` is a `RemoteUnavailable` handle that refuses every call. So the record update raised
inside its try/except and logged, and the championship update failed at `ObjectId(...)` and logged a warning. The desktop coach always showed 0-0 and no titles.

**Fix (same points, same numbers):** the local coach is one doc in the save's local `save_meta` collection,
`{_id: "local_coach", record, archetypes, lead_archetype, championships_total, championships_by_team}`
(`BackEnd/utils/local_coach.py`). In the two helpers above, only when the owner is `local-desktop-user`:
- the same `$inc` and `$set` target that doc (created by upsert on the first commit);
- the `users`-only tutorial-alert counter is skipped.

Every other owner takes the unchanged `users` path; tests cover both, on mongomock and SQLite. `finalize_game` itself is untouched.

**Route:** loopback does **not** serve `/api/auth/me`, because `api.py` omits the auth, community and leaderboard routers under
`is_loopback()`, and the frontend classifies `/api/auth` as always-remote. So I added
`GET /franchise/coach-career` (routable), which returns the `/api/auth/me` career fields: `user_id`, `username`,
`record`, `archetypes`, `lead_archetype`, `championships_total`. A test asserts it is a subset of `UserResponse`.
- On loopback it reads the local coach doc.
- Online it reads the same `users` fields `/me` does (additive; `/me` is unchanged).

Home Base on desktop calls `API_CONFIG.buildUrl('/franchise/coach-career', { runtime: 'local' })`, which resolves to
the loopback base.

**Adapter bug found and fixed:** `SqliteCollection.find_one_and_update` tested `str(return_document).endswith("AFTER")`,
but pymongo's `ReturnDocument.AFTER` is the bool `True`, so on SQLite every `ReturnDocument.AFTER` caller got the
*before* document (`None` on upsert). It now honours `True`. The other callers are unaffected in practice:
- `alpha_otp_service` and `otp_validator` use remote collections, which are never on SQLite;
- `stat_updater.rollup_game_to_franchise` has no callers.

## 3. Offline guard (mode-select)

On the desktop profile (`API_CONFIG.getBuildProfile() === 'desktop'`, which also covers the loopback cookie),
`mode-select.js` hides `.around-the-league-section`, `.community-section` and `.community-highlights-section`
before any fetch. It skips the leaderboard, highlights and Around The League loads, the 20 s ATL poll and its
visibility refresh, and the leaders-by-team modal. Each loader also returns early on desktop. There is no error text and no
"Sign in to see…" copy: the panels aren't rendered. One CSS rule (`.mode-wrapper > section[hidden]{display:none}`)
is needed because `.community-section` sets `display:flex`. Web is unchanged.

## 4. Trophy-case data (report only)

What is stored today:

| Where | What | Lifetime |
|---|---|---|
| `users` (and now the local coach doc) | `championships_total.{conf_rs,conf_t,region,national}` counts; `championships_by_team.<TEAM>.<kind>` counts; `record`; `geek_points`, `geek_points_by_team` | career, **counts only** (no season, franchise or date) |
| `franchise_players_data.titles.<kind>` | per-player title counts for the user team's active roster at award time; carried for returning players in `finish_season`, reset for new players | player's time in the franchise |
| `franchise_players_data.career` / `.season` | stat totals | career / current season |
| `franchises.conference_tournaments`, `region_tournaments`, `national_tournament` | full brackets and winners | **current season only**; `finish_season` resets them to `{}` |
| `franchises.awards` (`AWARDS_FIELD`) | All-American 1st/2nd/3rd teams, computed and persisted at week 35 | **current season only**; reset in `finish_season` |
| `franchises.pending_championship_moments` | one-shot UI overlays (conference/region/national, trophy spotlight, banner raise) | consumed on display |
| `franchises.results`, `stats.top_10_*` | weekly results, season leaders | current season only |

Not stored anywhere:
- a per-season history of titles or All-Americans;
- final season records by season;
- a records book (single-game or season highs).

**Can a per-coach list be built server-side?**
- **Counts: yes, today.** Use `championships_total` / `championships_by_team`, and now the same fields for the desktop coach.
- **An itemised trophy list** (e.g. "Season 2 · National Champion · Lancaster"): **no.** Once `finish_season` wipes the
  brackets and awards there is nothing left to rebuild it from.

It would need a small append-only log, e.g. `trophies: [{season, kind, team_id, franchise_id, at}]`, written at the
same award points (`_inc_championship` already has the kind, team and franchise; the season comes from the franchise doc).
All-Americans on the user team could be appended from `_persist_week_35_awards_if_needed`. That would be a
route/helper-level change like item 2, with no sim or finalize changes.

## Tests

- `tests/test_home_base_data.py` (16 tests, each store-backed test run on mongomock and SQLite):
  - stamp and UTC-ISO round-trip;
  - the decorator stamps on success, skips when idempotent, and skips on error;
  - most-recent ordering, including naive vs aware datetimes;
  - route wiring (seven routes wrapped, `start-cpu-sims` not, sim modules clean);
  - `/franchise/list` returns `last_played_at` and `most_recent_franchise_id`;
  - the local owner's record (1-1, 50 %, archetypes, lead) lands in the save and not in `users`;
  - an online owner still goes to `users`;
  - local championships (totals and by-team) are stored, and online ones go to `users`;
  - `/franchise/coach-career` serves the local coach (zeros, then counts, in the `/me` shape) and online users.
- `tests/e2e/home-base-offline-guard.spec.js`:
  - **Desktop:** zero requests to the four community paths on any host, including after 65 s of fake clock (past the
    20 s poll) and a visibility change. The panels and the leaders-by-team trigger are hidden, and there's no "sign in"
    or "could not load" copy. With the old mode-select files this test fails: desktop made several community requests.
  - **Web:** the leaderboard, highlights and ATL requests fire, the ATL poll repeats after 21 s, and leaders-by-team fires on click.
- During work: the new tests plus `test_persistence_adapter`, `test_user_game_commit`, `test_loopback_profile`,
  `test_orphaned_team_display`, `test_browse_rev` (every decorated writer), `test_tb_leak_detector` and
  `test_franchise_championships`: all passing.

Full runs (after the code commit):
- **Playwright** (UX §8, workers=1, port 8157, CI unset): **544 passed, 3 skipped** (the known environment-gated skips).
  It started only after the audit agent's own full Playwright run had finished and `ps` was clear. Server stopped;
  regenerated report images restored.
- **pytest --ignore=tests/e2e** (`tests/` and `BackEnd/tests`): **3876 passed, 20 skipped, 109 xfailed, 1 xpassed,
  0 failed.** That working tree includes the audit agent's uncommitted edits to four test files. Running
  origin/develop's committed versions of those four files gives **6 pre-existing failures**, the ones the audit agent is fixing:
  - `test_fcc_team_measures_radar_scale::test_team_measures_and_scouting_share_plus_minus_twenty_radar_scale`
  - `test_resource_page_scoping::test_standings_region_filter`
  - `test_resource_page_scoping::test_team_stats_scope_filters_to_user_conference`
  - `test_training_page_phase5::test_the_before_you_submit_bar_became_a_pill`
  - `test_training_page_phase5::test_the_pill_sits_under_the_page_title`
  - `test_training_page_phase5::test_tally_recounts_after_a_save`

  None of them touch code on this branch. This branch adds no failures.

## SELF-CHECK (screenshots opened)

- `reports/home-base-data/mode-select-offline-1280x720.png` (desktop profile): the top bar (logo, Tutorials,
  YouTube, X, the Settings gear, Log Out), **My Franchises** with two "Start Your Coaching Journey" slots and orange
  **Find Your Program** buttons, and the **Find A Game / Coming Soon** card. There's no Around The League, Leaderboard or
  Community Highlights, and no error or sign-in text. Below the two cards the legacy white **"FAQs"** site-footer bar is
  visible mid-page. That footer is injected by `authBarInit.js` on non-shell pages and was already there; it only
  moved up because the page is now shorter. It belongs to the Home Base design pass.
- `reports/home-base-data/mode-select-online-1280x720.png` (web): the same two top cards, then **Around The League**
  ("Could not load Around The League." because the test server has no community data), **Community Highlights** and the
  **Leaderboard** with its Geek Points / Titles toggle. The community zone is unchanged online.

STATUS: COMPLETE
