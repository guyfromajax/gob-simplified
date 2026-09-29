# Office weekly card + moment queue v2 (backend)

Branch `feat/weekly-and-queue-v2` off `origin/develop`. Backend only — no frontend
file changed, and item 1c turned out not to need one (see below). The UI PRs read
what is below; the client never ranks, caps, picks, styles or sounds a moment, and
never recomputes a gain threshold.

## A1. The exceptional-gain rule

**`change-gold` has no rule in `training-report.js`.** The class exists only in
`training-report.css` (and is overridden to `--text-100` in the Ch7 block), and no
JavaScript ever applies it. What the client *does* carry is an explicit, named,
documented threshold that nothing calls:

```614:616:FrontEnd/static/training-report.js
function getExceptionalGainThreshold() {
  return getReportWeekNumber() === 1 ? 10 : 5;
}
```

That is the rule, and it is what I ported — not `describeTrainingChange`'s arrow
bands, whose top band (`change-elite`, `n >= 3`) is a different scale and a
different meaning (blue triple-up, not gold).

Ported to `BackEnd/utils/attribute_gain.py::is_exceptional_gain`:

| Source | Python |
|---|---|
| `getReportWeekNumber()` → `reportData.week` | the stored report's own `week` — a camp report read in week 2 keeps the camp threshold |
| `=== 1 ? 10 : 5` | `exceptional_gain_threshold(week)` → `10` at week 1, `5` otherwise |
| the compared delta | the **raw** per-attribute delta from the report's `player_logs` (legacy name `player_changes`), written by `training_execution_v2` as `(anchor + banked fraction)` after minus before |
| gains only | `delta >= threshold`; a drop is never exceptional, and the marker shows on a loss week too |

Two scales matter here. `player_logs` holds raw attribute points (0–99 scale);
`player_attribute_display_movements` holds the first-digit display bucket
(`raw // 10`) that the Office lists. The threshold is raw, so the digest joins its
display rows back to the raw delta by player name rather than comparing buckets.
A test asserts parity against the transcribed JS expression over a table of twelve
cases plus every week in `{0, 1, 2, 5, 26, 35, 36}`.

**1b.** `what_moved.attribute_changes[]` now carries `exceptional: true` on
qualifying rows only; the key is absent otherwise.

**1c.** The same pairs are on the training-report route as `exceptional_gains`
(`[{name, attribute}]`), and on both post-training responses, so the two surfaces
share one rule. **`training-report.js` cannot "switch to the flag", because it does
not render a gold marker today** — `getExceptionalGainThreshold` is dead code and
`.change-gold` is unused CSS. There is nothing to swap, trivially or otherwise, so
no frontend file was touched. The Ch7 training UI can read `exceptional_gains`
when it renders the marker.

## A2. `result_key`

`office_digest.result.result_key` is the game id — the same id already on
`result.box_score.params.game_id`, lifted to the top of `result` so the client can
play the weekly entrance once per result. It is `null` when the stored game has no
id. No server "seen" state exists or is needed: the client stores that locally. A
store-parametrised test confirms it on mongomock and SQLite.

## A3. Confirmed weekly-card fields

| Element | What the server returns |
|---|---|
| `result.leader` | `{player_id, name, stats}` with `stats.pts / reb / ast` always present, plus `fgm, fga, fg3m, fg3a, min` **only when the box score stored them**. `leader_role` is `potg` on a win, `team_leader` on a loss. |
| `what_moved.national_rank` | `{now, prev, delta}`; delta is `prev - now`, so positive means the team climbed. `prev` comes from the week-advance snapshot, and delta is `null` until one exists. |
| `what_moved.conference_standing` | Same shape, place in Standings order (wins, then point differential). |
| `what_moved.record` | `{wins, losses}`. |
| `what_moved.streak` | `"W4"` / `"L1"`, or `null` with no decided game. **No thresholds.** There is no W5/W10 field and none was added, per the design. |
| `result.opponent_rank` | The opponent's `natl_rank` from the rankings already on the response; `null` when the opponent is not ranked. |
| `result.round_name` | `ROUND_NAME_BY_WEEK` for weeks 27–34 only; `null` in the regular season. |

## B1. Every kind and its source

| Kind | Tier | Source flag / payload (file::function) |
|---|---|---|
| `championship` | SEASON PEAK | `pending_championship_moments` — `franchise_championship_moments.py::list_moments` (enqueued by `maybe_enqueue_championship_game_moment`, `enqueue_trophy_spotlight_for_user_conference`, `enqueue_banner_raise_if_user_won_national`) |
| `season_review` | SEASON PEAK | **NEW** `season_moments.py::season_review_payload` → `career_data.py::season_review_snapshot` (the same reader `finish_season` stores on the `season_record` trophy) |
| `elimination` | MILESTONE | **NEW** `season_moments.py::elimination_payload`, from the brackets `franchise_routes.py::_user_eos_bracket_and_seeds` returns |
| `bracket_reveal` | MILESTONE / WEEKLY | `franchise_routes.py::_build_bracket_reveal_modal_payload`; tier decided by `season_moments.py::user_in_bracket` |
| `signed_class` | MILESTONE | **NEW** `season_moments.py::signed_class_payload` — eligibility from `franchise_routes.py::_build_recruiting_results_modal_payload`, rows from `career_data.py::class_signed` |
| `walk_on_welcome` | MILESTONE | `franchise_routes.py::_build_walk_on_welcome_modal_payload` |
| `region_bye` | MILESTONE | `franchise_routes.py::_should_show_region_bye_modal` |
| `conference_rs_region` | MILESTONE | `franchise_routes.py::_build_conference_rs_region_modal_payload` |
| `first_archetype` | MILESTONE | **NEW** `season_moments.py::first_archetype_payload`, from `franchise_routes.py::_coach_archetype_signals` (`lead_archetype` + `archetype_reveal_seen`) |
| `bracket_update` | WEEKLY | `franchise_routes.py::_build_bracket_update_modal_payload` |
| `recruit_visit` | WEEKLY | `franchise_routes.py::_build_recruit_visit_modal_payload` |
| `archetype_evolution` | WEEKLY | `archetype_evolution_pending`, written by `community_highlights.py::record_archetype_change_if_any` |

All three new payloads are derived in `franchise_routes.py::_build_moment_queue_for_command_center`
and placed on the response under their `payload_ref` keys (`elimination`,
`season_review`, `signed_class`, `first_archetype`). No detector was added inside
the sim; a guard test asserts the sim modules and
`_complete_week_finish_cpu_and_persist` mention neither `moment_queue` nor
`exceptional`.

### How elimination is detected

From the stored brackets only. The team is eliminated when it lost its latest
decided tournament matchup (a `winner` that is set and is not the user) and no
later tournament still awaits it: a **conference** loss only ends the season for a
team that did not qualify for its region, while a **region** or **national** loss
always does. The round is named by mapping the bracket slot to its calendar week
(`season_moments.ROUND_WEEK`: conference round1/round2/final → 27/28/29, region →
30/31, national → 32/33/34) and then through the existing
`office_digest.ROUND_NAME_BY_WEEK`. Once per season, stamped by
`PATCH /franchise/elimination-seen`.

### When the review becomes eligible

Once the season's games are all played and before `finish_season` runs: a national
champion is decided (`national_tournament.champion`) or the calendar has left the
tournament weeks (`week >= 35`). Both are existing signals. The franchise still
holds everything the review reads, so the review a coach sees is the review that
gets written to the Trophy Case. Once per season, via
`PATCH /franchise/season-review-seen`.

### Why the signing class needs its own gate

The hub reveal's seen state is **not** on command-center data — `week_35_reveal_seen`
is computed on `GET /franchise/recruiting-data`. So the queue reads the stored
`week_35_reveal_seen_season` off the franchise doc and requires it to equal the
current season. Until the hub has played, `signed_class` is not eligible, so the
Office can never pre-empt Signing Day (decision 24). It reuses the existing
`recruiting_results_modal_seen_season` stamp and its PATCH — one beat, one stamp.
The recruit rows come from `career_data.class_signed`, not the modal payload,
because the modal projects `pos` / `potential_rt_ratcheted` and **drops
`home_region`** while the stored signing entry has it.

## B2–B4. Priority, cap and durations

Priority, tier, duration, style and sting are in the module docstring of
`BackEnd/utils/moment_queue.py` and in UX_System §10, which this change updates.
Weekly items follow the pop-up tiers in the order bracket_update (80),
recruit_visit (90), archetype_evolution (100), bracket_reveal-not-in (110).

Cap: a season peak takes the whole visit. A championship and a review together are
exactly `[championship, season_review]`; a peak on its own shows on its own. With
no peak, the old rule stands — one pop-up, or two when the first is `short` and the
second is a pop-up tier.

One consequence worth knowing before the UI PR: in weeks 35–36 the review is
eligible, so it claims the visit and the signing class defers to the next Office
open. That is the cap working as specified, not a bug.

## B5. Style and sting

Set on the server, per item: `style` is `"gold"` on every season-peak and milestone
row and `"quiet"` on elimination; weekly rows carry `null`. `sting` is
`"STING_SEASON_PEAK"` on the season peak, `"STING_MILESTONE"` on gold milestones,
and `null` on elimination and every weekly row. The files do not exist yet, so the
slot is silent — the server only says which cue a moment carries.

## B6. The "Also" row

`office_digest.also` is the highest-priority weekly item as
`{kind, title, line, href}`, or `null`. `weekly_card_items` stays the full ordered
list, and every weekly kind now has an `href`:

| Kind | href |
|---|---|
| `bracket_update` | `/franchise-command-center.html?tab=tournament-view` |
| `bracket_reveal` (not in it) | `/franchise-command-center.html?tab=tournament-view` |
| `recruit_visit` | `/recruiting.html` |
| `archetype_evolution` | `/coaching-archetypes.html` online; **omitted on desktop** |

## B7. Deferral

Unchanged. Items that do not show stay in `moments` and stay eligible; dismissing
one leaves the rest for the next visit; seen is only written for items actually
shown. A test walks a two-visit sequence.

## New queue item shapes

**A championship + review visit** (the one pair that shows together):

```json
{
  "moments_for_this_visit": [
    {"id": "championship", "kind": "championship", "tier": "SEASON_PEAK",
     "priority": 10, "payload_ref": "pending_championship_moments",
     "seen_key": "pending_championship_moments", "title": "Championship moment",
     "line": "A title moment is waiting.", "style": "gold",
     "sting": "STING_SEASON_PEAK", "duration": "long"},
    {"id": "season_review", "kind": "season_review", "tier": "SEASON_PEAK",
     "priority": 15, "payload_ref": "season_review",
     "seen_key": "season_review_seen_season", "title": "Season review",
     "line": "Your season, start to finish.", "style": "gold",
     "sting": "STING_SEASON_PEAK", "duration": "long"}
  ],
  "weekly_card_items": [
    {"id": "bracket_update", "kind": "bracket_update", "tier": "WEEKLY",
     "priority": 80, "payload_ref": "bracket_update_modal",
     "seen_key": "update:national:3:35", "title": "Tournament update",
     "line": "The tournament bracket moved this week.", "style": null,
     "sting": null, "href": "/franchise-command-center.html?tab=tournament-view"}
  ],
  "also": {"kind": "bracket_update", "title": "Tournament update",
           "line": "The tournament bracket moved this week.",
           "href": "/franchise-command-center.html?tab=tournament-view"}
}
```

**An elimination visit** (region final loss):

```json
{
  "moments_for_this_visit": [
    {"id": "elimination", "kind": "elimination", "tier": "MILESTONE",
     "priority": 20, "payload_ref": "elimination",
     "seen_key": "elimination_seen_season", "title": "Season over",
     "line": "Your season ended in the Region Tourney Championship.",
     "style": "quiet", "sting": null, "duration": "short"}
  ],
  "elimination": {
    "eligible": true, "season": 3, "tier": "region", "round_key": "final",
    "round_name": "Region Tourney Championship",
    "opponent_team_id": "bbbb…bbbb", "opponent_team_name": "Kingsport",
    "score": {"user": 58, "opponent": 66}, "game_id": "g-region",
    "record": {"wins": 24, "losses": 9},
    "conference_place": 2, "national_rank": 11
  }
}
```

**A signed-class visit:**

```json
{
  "moments_for_this_visit": [
    {"id": "signed_class", "kind": "signed_class", "tier": "MILESTONE",
     "priority": 40, "payload_ref": "signed_class",
     "seen_key": "recruiting_results_modal_seen_season", "title": "Signing class",
     "line": "2 recruits signed with your program.", "style": "gold",
     "sting": "STING_MILESTONE", "duration": "long"}
  ],
  "also": null,
  "signed_class": {
    "eligible": true, "count": 2,
    "recruits": [
      {"name": "Dee Prospect", "position": "PG", "home_region": "B",
       "rt_now": 71, "rt_potential": 84},
      {"name": "Marcus Vane", "position": "C", "rt_now": 64}
    ]
  }
}
```

## What was omitted, and why

Nothing here is invented or derived from a missing source.

- **Both elimination seeds on a region loss.** `region_tournaments` stores
  `round1` / `final` / `current_round` and no `seeds` map, so a region elimination
  carries neither `user_seed` nor `opponent_seed`. A conference elimination does
  carry both (a test proves it), because conference blobs store seeds.
- **`opponent_team_name`** is omitted when the request's `team_name_map` does not
  hold that id; `score` is omitted when the matchup has no recorded score;
  `game_id`, `record`, `conference_place` and `national_rank` are each omitted when
  absent. `national_rank` is dropped when it is 0 or less.
- **`round_name`** is omitted for a bracket slot outside weeks 27–34.
- **A recruit's `home_region`, `rt_now` or `rt_potential`** is omitted when the
  stored signing entry lacks it (including the `"--"` placeholder), so
  `Marcus Vane` above has no region and no potential.
- **Streak thresholds** (W5, W10 …) were not added. No field exists and the design
  says skip them.
- **`region_seed`** inside the review snapshot stays omitted for the same reason as
  the career-data PR: region brackets store no seeds.
- **Weekly `duration`** is absent rather than null: weekly items never pop.
- **An exceptional gain that does not cross a display digit** never appears in the
  Office training list at all, because `attribute_changes` rows exist only where
  `player_attribute_display_movements` recorded a bucket change. The gold marker
  therefore shows on the rows the Office lists, not on every exceptional gain. The
  training-report route's `exceptional_gains` is not filtered that way. This is
  existing digest behaviour, not something this change introduced.
- **`player_logs` is keyed by display name**, so two players with the same name
  share one raw-gain entry. That is the shape the map has always had; the join
  inherits the limitation rather than guessing at player ids.

## Beyond the brief, and why it was needed

**The two archetype "seen" PATCHes now work on desktop.**
`PATCH /api/auth/archetype-reveal-seen` and `/archetype-evolution-seen` both did
`ObjectId(user["user_id"])`, which raises for the desktop principal
(`local-desktop-user`), so on desktop the call failed. With `first_archetype` and
`archetype_evolution` in the queue, a moment could be shown and never marked seen,
and would return on every Office load — a straight violation of "same behaviour
online and on desktop". Both now route through the `local_coach.coach_target`
helper from the career-data PR (`auth_routes.py::_set_on_coach`), so the keys land
on the same doc `command_center_data` reads them back from. Online is unchanged.

**Two new stored fields**, `elimination_seen_season` and
`season_review_seen_season`, with `PATCH /franchise/elimination-seen` and
`PATCH /franchise/season-review-seen`, in the same season-stamped style as every
existing modal flag. The two new milestones had no seen route to reuse, and without
one they could not obey "seen is only written for items actually shown".

**The queue is now built after `office_digest`** in `command_center_data`, so the
elimination payload reports the season record, conference place and national rank
the digest already computed instead of reading them a second time. The digest never
read any queue key, so nothing else moved.

## Not changed

The sim engine, `cpu_week_pool`, `sim_rng`, the stat updater/finalize internals and
`_complete_week_finish_cpu_and_persist` are untouched. No frontend file changed.

`tests/e2e/moment-queue.spec.js` mocks the command-center response with hardcoded
tiers and priorities, so it exercises client behaviour and stays green; its fixture
numbers are now stale relative to the server and should be refreshed by the UI PR
that touches that spec.

One note on the handoff: the "Data needed" table maps Elimination to
`conference_rs_region_modal`. Those are different moments — that modal is the
consolation notice for a regular-season conference champion who lost the conference
tournament, and it stays its own kind at priority 65. Elimination is the new one.

## Merge gate (UX_System §8)

- `pytest --ignore=tests/e2e`: **4043 passed, 20 skipped, 109 xfailed, 1 xpassed,
  0 failed.**
- Playwright `tests/e2e`: **551 passed, 3 skipped, 0 failed** (8.3m). One full run, `--workers=1`, port 8157,
  `CI` unset, started only after `ps` showed no other Playwright run.

New tests: `tests/test_attribute_gain.py` (25) covers the threshold parity table,
the raw-gain join and the digest flag; `tests/test_moment_queue.py` (33, rewritten
for v2) covers every kind's tier and priority, the durations, style and sting, the
season-peak pair, short+short and long caps, bracket reveal in vs not in,
`signed_class` blocked until the hub reveal, first establish vs evolution,
elimination once per season with omitted seeds, the `also` row, the desktop href
omission, deferral, and the sim guard — with the route-level detectors exercised on
mongomock and SQLite. `tests/test_office_digest.py` gains `result_key`, the folded
slots and a both-stores round-trip of the exceptional flag.

STATUS: COMPLETE
