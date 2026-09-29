# Chapter 7 — career data (backend)

Branch `feat/career-data` off `origin/develop`. Backend only: no frontend file was
touched. The server now stores and returns everything Home Base "Your Career", the
Trophy Case and the end-of-season review read, so the client formats strings and
never computes a win %, a GP total, a ranking, a best-players list or a count.

Built on what already exists — `last_played_at`, `GET /franchise/coach-career`,
the trophy log and the local coach doc. Nothing was duplicated.

## Where the coach doc lives

One helper decides, once, which doc a career field belongs to:

`BackEnd/utils/local_coach.py::coach_target` → `(collection, doc_id, is_local)`
- online: `users` / `ObjectId(user_id)`
- desktop (`local-desktop-user`): the save's `save_meta` doc `_id="local_coach"`

`coach_fields(owner_user_id, *fields)` and `coach_field(owner_user_id, field)` are
the projected reads on top of it — never a whole-doc read. Every write point below
goes through `coach_target`, so online and offline carry the same field names and
the same shape.

## Write points

| what | file::function |
| --- | --- |
| GP career total, per-team bucket, per-season bucket (one `$inc`) | `BackEnd/utils/franchise_geek_points.py::apply_geek_points_delta` |
| win-game delta (computed once) | `BackEnd/utils/franchise_geek_points.py::maybe_award_franchise_win_geek_points` |
| loss-game delta (computed once) | `BackEnd/utils/franchise_geek_points.py::maybe_award_franchise_loss_geek_points` |
| franchise/season context when the caller cannot pass it | `BackEnd/utils/franchise_geek_points.py::_franchise_season_for_award` |
| season review snapshot merged into the `season_record` detail | `BackEnd/utils/trophy_log.py::season_record_detail` |
| `milestone_first_signing_class` | `BackEnd/utils/trophy_log.py::record_first_signing_class_milestone`, called from `BackEnd/api/franchise_routes.py::run_week_35_recruiting` (right after the `week_35_recruiting_results` update) |
| `milestone_first_bracket` | `BackEnd/utils/trophy_log.py::record_first_bracket_milestone`, called from `BackEnd/api/franchise_routes.py::_finalize_franchise_week_after_cpu_games` (after `maybe_award_conference_rs_championship`) |
| `milestone_first_archetype` | `BackEnd/utils/trophy_log.py::record_first_archetype_milestone`, called from `BackEnd/utils/community_highlights.py::record_archetype_change_if_any` (the `lead_before == ""` branch) |
| `archetype_evolution_pending` on the coach doc | `BackEnd/utils/community_highlights.py::record_archetype_change_if_any` (the `lead_before` non-empty branch) |

GP award call sites that now pass `franchise_id` / `season` explicitly:
- `BackEnd/api/franchise_routes.py::_complete_week_process_user_game_block` (7304, 7314)
- `BackEnd/api/franchise_routes.py::sim_rest_of_tournament` (18968, 18977)
- `BackEnd/api/franchise_routes.py::sim_championship` (19163, 19172)

The fourth call site, `_award_gp_sim` inside `_complete_week_finish_cpu_and_persist`
(8506, 8513), was **not** touched — it is on the do-not-change list. Both context
kwargs are therefore optional, and that path resolves the franchise and season with
one projected `franchises` read in `_franchise_season_for_award`, keyed on
`(user_id, user_team_object_id)` and disambiguated by `week` when a coach has two
saves with the same team. If it is still ambiguous the career total and team bucket
still increment and only the season bucket is skipped — an under-count, never a
wrong number. A guard test asserts `_complete_week_finish_cpu_and_persist` contains
no reference to `career_data`, `season_gp` or a milestone, and that the sim engine,
`cpu_week_pool`, `sim_rng` and the stat-updater/finalize modules mention none of them.

## Read points

| what | file::function |
| --- | --- |
| career totals, `top_seasons`, `win_pct_display` | `BackEnd/utils/career_data.py::coach_career_extras` |
| season review fields | `BackEnd/utils/career_data.py::season_review_snapshot` |
| route payload | `BackEnd/api/franchise_routes.py::get_coach_career` |
| desktop archetype signals on an Office load | `BackEnd/api/franchise_routes.py::_coach_archetype_signals`, merged into `command_center_data` |

## 1–2. Geek Points mirror and season buckets

The per-game award rule and its single `random.randint` call are unchanged: the
delta is computed once by `maybe_award_franchise_{win,loss}_geek_points` and written
once by `apply_geek_points_delta`, in one `$inc` on one doc:

```
geek_points                              +delta
geek_points_by_team.<TEAM_KEY>           +delta
season_gp.<franchise_id>:<season>        +delta
```

Online that doc is `users`; for the desktop principal it is the save's `local_coach`
doc (upserted, so it is created on the coach's first award). Online behaviour and
online values are unchanged.

`season_gp` is a dict path, like `trophy_keys` — the SQLite query engine does not
traverse arrays, and a Mongo field name cannot hold `.` or start with `$`, so
`season_gp_key` sanitises both.

## 3. Season review snapshot

`season_record` keeps its key, its `wins`/`losses` and its idempotency exactly as
they were. The detail now also carries, read off the franchise doc before the
season transition wipes it:

```json
{
  "wins": 25, "losses": 8,
  "national_rank": 4,
  "season_gp": 620,
  "best_players": [
    {"player_id": "p2", "name": "Bea Hall", "position": "SF", "class_year": "JR",
     "stats": {"ppg": 5, "rpg": 2, "apg": 1}, "all_american": "all_american_1"},
    {"player_id": "p3", "name": "Cy Hall", "position": "SF", "class_year": "JR",
     "stats": {"ppg": 3, "rpg": 2, "apg": 1}, "all_american": "all_american_3"},
    {"player_id": "p1", "name": "Ada Hall", "position": "SF", "class_year": "JR",
     "stats": {"ppg": 20, "rpg": 2, "apg": 1, "spg": 1.5}}
  ],
  "class_signed": [
    {"name": "Dee Prospect", "position": "PG", "home_region": "B",
     "rt_now": 71, "rt_potential": 84}
  ]
}
```

- `national_rank` is `franchise_team_data.natl_rank`, which the regular-season
  prestige pass writes for weeks 1–26 — so it is the rank the season ended on.
- conference place is the existing `conf_finish`, untouched.
- `best_players`: user-team All-Americans first in team order (1st, then 2nd, then
  3rd), then filled to three by season points. Python's stable sort keeps roster
  order on a tie, so two players on equal points always come back in the same
  order. Position comes from the roster (the All-American pick does not carry one).
- `stats` is `ppg`/`rpg`/`apg` plus `spg` **only** when `STL` is on that player's
  season line.
- `class_signed` is the user team's non-walk-on signings from
  `week_35_recruiting_results`.

## What is omitted because the source does not exist

Nothing here is derived or approximated; the field is simply absent.

- **`region_seed` — always omitted today.** `initialize_region_tournaments` /
  `_build_region_bracket` write `round1`, `final` and `current_round` and never a
  `seeds` map. The reader (`career_data.region_seed`) is in place and a test proves
  it reports the seed the moment a `seeds` map is written, so nothing needs to
  change here when region seeding lands. (Conference seeds *are* stored, and
  `milestone_first_bracket` uses one as its optional detail.)
- `national_rank`, `season_gp`, `best_players`, `class_signed` are each dropped
  from the snapshot when their source is missing — a brand-new franchise records
  `{"wins": 0, "losses": 0}` and nothing else.
- Per-player `spg` is dropped unless `STL` is already on the season line, and a
  signing's `position` / `home_region` / `rt_now` / `rt_potential` are dropped when
  the stored signing entry lacks them (including the `"--"` placeholder).
- `top_seasons[].finish` is `null` for a season with neither a title nor a
  `furthest_round`, and `week` is `null` for a completed season.
- `win_pct_display` is `null` before the coach's first game rather than `.000`.

## 4. Milestones

Three new kinds in the trophy log, same `append_trophy` guard, same entry shape,
detail optional:

| kind | recorded when | detail |
| --- | --- | --- |
| `milestone_first_signing_class` | week-35 recruiting results are written | `{"signed": n}` |
| `milestone_first_bracket` | the user team first appears in any conference bracket round | `{"seed": n}` when a seed is stored |
| `milestone_first_archetype` | the coach's lead archetype is first established | `{"archetype": key}` |

Keys are `coach:<kind>` — no franchise, no season — so each fires **once per coach**,
across every save and every program. No new sim hooks: each one is recorded at the
existing point where that fact is first written.

## 5. `GET /franchise/coach-career`

Same route, online and loopback, everything server-computed. Real response
(desktop coach, 73–22, one live season):

```json
{
  "user_id": "local-desktop-user",
  "username": "Coach",
  "record": {"wins": 73, "losses": 22, "total_games": 95, "win_rate": 77,
             "discount_wins": 0, "discount_losses": 0},
  "archetypes": {"pure_offense": 0, "...": 0, "total": 0},
  "lead_archetype": "",
  "championships_total": {"conf_rs": 1, "conf_t": 1, "region": 1, "national": 0},
  "win_pct_display": ".768",
  "geek_points": 4060,
  "seasons_completed": 2,
  "programs": 1,
  "top_seasons": [
    {"franchise_id": "6abb…cc37", "team_name": "Lancaster", "team_slug": "lancaster",
     "season": 2, "wins": 25, "losses": 8, "finish": "Region champions",
     "season_gp": 800, "in_progress": false, "week": null},
    {"franchise_id": "6abb…cc37", "team_name": "Lancaster", "team_slug": "lancaster",
     "season": 3, "wins": 0, "losses": 0, "finish": null,
     "season_gp": 620, "in_progress": true, "week": 9},
    {"franchise_id": "6abb…cc37", "team_name": "Lancaster", "team_slug": "lancaster",
     "season": 1, "wins": 18, "losses": 12, "finish": null,
     "season_gp": 400, "in_progress": false, "week": null}
  ],
  "trophies": [
    {"key": "6abb…cc37:2:season_record:t", "season": 2, "kind": "season_record",
     "team_id": "t", "team_name": "Lancaster", "franchise_id": "6abb…cc37",
     "at": null, "detail": {"wins": 25, "losses": 8, "season_gp": 800}},
    {"key": "coach:milestone_first_signing_class", "season": 1,
     "kind": "milestone_first_signing_class", "team_id": "t",
     "team_name": "Lancaster", "franchise_id": "6abb…cc37", "at": null,
     "detail": {"signed": 4}}
  ]
}
```

- `record.win_rate` is returned as before — the whole-percent integer
  (`round(100 × wins ÷ total)`) every existing caller reads. Unchanged.
- `win_pct_display` is the new three-decimal string the career strip prints
  (`.768`, `1.000`), formatted server-side, `null` before the first game. Added
  because the client does no arithmetic and `win_rate` cannot represent `.768`.
- `seasons_completed` counts `season_record` entries.
- `programs` counts distinct franchise ids across the trophies **and** the coach's
  current franchises.
- `top_seasons` is up to five rows by season GP descending, ties by win %
  descending, and **includes each in-progress season** from the live franchises
  (current record from the standings, current `week`, season GP so far,
  `in_progress: true`). A completed `season_record` wins over a live row for the
  same `(franchise_id, season)`.
- `team_slug` is the server-side equivalent of the client's team-art key, via
  `team_slug.path_slug_for_display_name`. Team Builder display names are honoured:
  the Team Builder leak scanner is clean on this payload in the tests.
- `trophies` now includes the three milestone kinds.

## 6. Archetype offline

**Where `archetype_evolution_pending` is written today:**
`BackEnd/utils/community_highlights.py::record_archetype_change_if_any`, called from
`BackEnd/api/franchise_routes.py::_complete_week_process_user_game_block` (7604) and
the legacy `save_result` (5909). Before this change it `$set` it on the `users` doc
only, and it reached the client solely through `UserResponse` on
`GET /api/auth/me` (`BackEnd/api/auth_routes.py`, cleared by
`POST /api/auth/archetype-evolution/clear`). Loopback serves no `/api/auth`, so on
desktop the field was written nowhere readable and the modal never fired.

Two fixes, both at that same write point:
1. The `$set` now goes through `coach_target`, so the desktop principal gets it on
   the save's `local_coach` doc (upserted) with the same field name. Online is
   unchanged.
2. First-time establishment (`lead_before == ""`) records
   `milestone_first_archetype`.

Also fixed on the read side: `lead_archetype_for_user` queried `users` directly, so
it returned `""` for the desktop principal and no archetype change could ever be
detected offline. It now reads through `local_coach.coach_field`.

Command-center exposure: `_coach_archetype_signals` returns
`archetype_evolution_pending`, `lead_archetype` and `archetype_reveal_seen` from the
principal online and from a **projected** `local_coach` read on desktop. Those three
keys are merged into the command-center payload and the pending value is passed to
`build_moment_queue`, which is how the moment queue already reads it. The read is
projected to three fields, so an Office load does not pull the coach's career back;
a trophy-log test asserts every coach read on an Office load is projected.

## Tests

`tests/test_career_data.py` — 66 tests, each parametrised over **mongomock and
SQLite** and, where a coach doc is involved, over **local and online** owners:

- GP mirror: the desktop delta equals the online delta for the same rule and the
  same randomness call; an award never writes the other coach's doc; a game the
  user did not play awards nothing.
- Season GP: buckets accumulate per franchise and per season; the context-free
  caller still buckets correctly; the career total still lands when two saves make
  the season unresolvable.
- Season review: every field present; every field omitted when its source is
  absent; `region_seed` reported as soon as a `seeds` map exists; best-players
  ordering (All-Americans first, then PPG, stable on ties); `class_signed` field
  omission.
- Milestones: each recorded once per coach across seasons and franchises; none
  recorded when the fact is not true; the offline archetype milestone fires at the
  real write point; `_coach_archetype_signals` resolves the desktop coach.
- coach-career: the computed counts; `top_seasons` ordering with in-progress rows;
  the same shape online; the empty-but-shaped new coach; `win_pct_display`; the
  Team Builder leak scanner clean on the payload.
- Guard: the sim engine, `cpu_week_pool`, `sim_rng`, the stat updater/finalize
  modules and `_complete_week_finish_cpu_and_persist` mention no career data, and
  the GP helpers' context kwargs default to `None`.

Two existing tests encode contracts this change deliberately extends and were
updated: `tests/test_home_base_data.py` (coach-career is now the `/api/auth/me`
shape *plus* the trophy log and the career numerals) and `tests/test_trophy_log.py`
(an Office load now makes one more coach read — asserted to be projected, with
still exactly one `trophy_keys` read per load).

## Merge gate (UX_System §8)

- `pytest --ignore=tests/e2e`: **3988 passed, 20 skipped, 109 xfailed, 1 xpassed,
  0 failed.** One test, `tests/test_loopback_profile.py::test_prove_pool_cli_exits_clean`,
  fails only under the tooling sandbox (SQLite `unable to open database file` for a
  subprocess outside the workspace); the whole file passes unsandboxed
  (`11 passed`) and is unrelated to this change.
- Playwright `tests/e2e`: **551 passed, 3 skipped, 0 failed** (8.1m). One full run,
  `--workers=1`, port 8157, `CI` unset, started only after `ps` showed no other
  Playwright run. Report images the run regenerated were restored.

STATUS: COMPLETE
