# Championship Announce Moments

Four overlay templates that fire at specific franchise milestones. All four
extend the existing Moment Modal pattern; behavioral foundation is shared with
[Styleguide_updated.md](../00_General_Systems/Styleguide_updated.md) (`Moment Modals`).

Visual source of truth:
[Championship Announce.html](../projects/Championship%20Announce.html).

| # | Template          | Trigger                                                                         | Theming           | Buttons                              |
|---|-------------------|----------------------------------------------------------------------------------|-------------------|--------------------------------------|
| A | Classic Modal     | Conference championship complete (week 29) **and** Region championship (week 31) | Winning team      | Back to Locker Room · Box Score      |
| B | Cinematic         | National championship complete (week 34)                                         | Winning team      | Back to Locker Room · Box Score      |
| C | Trophy Spotlight  | First FCC mount of week 27 (Regular-Season Champion of user's conference, 1-seed)| Winning team      | Back to Locker Room                  |
| D | Banner Raise      | First FCC mount of new season after the user team won the National Championship  | User team         | Back to Locker Room                  |

A, B, and C show **regardless of who won**, in the winning team's colors.
D is reserved to the user team only.

## Detection rules

- `phase == "conference" and round == 3` → Classic (conference championship)
- `phase == "region" and round == 2` → Classic (region championship)
- `phase == "national" and round == 3` → Cinematic (national championship)

For A and B, the moment is filtered to the user's own conference / region; the
user only sees their bracket's championship. National applies to all users.

## Backend architecture

### Persistence

Pending moments live on the franchise document at
`pending_championship_moments` (list of moment dicts).

Each entry carries everything the frontend needs to render with no follow-up
fetches: `id`, `type`, `season`, `conference`/`region`, `winner_team_*`,
`winner_natl_rank`, `winner_record`, `winner_seed` (Trophy only), score block,
`game_id`, `user_is_winner`.

Module: [BackEnd/utils/franchise_championship_moments.py](../../BackEnd/utils/franchise_championship_moments.py).
Idempotent enqueue keyed on `(type, conf|region, season, game_id)`.

### Enqueue hooks

| Hook                                        | Where                                                                                             | Triggered when |
|---------------------------------------------|---------------------------------------------------------------------------------------------------|----------------|
| `maybe_enqueue_championship_game_moment`    | `record_tournament_game_result` ([franchise_tournament_progression.py:449](../../BackEnd/tournament/franchise_tournament_progression.py#L449)) | Sim paths only (`source in {"cpu_full", "distant"}`). User live-game source is intentionally skipped — the live-game branch of `showGameCompletionPopup` renders directly from the game doc, so a queued moment would double-show on the next FCC mount. |
| `enqueue_trophy_spotlight_for_user_conference` | After `initialize_conference_tournaments` runs in `_finalize_franchise_week_after_cpu_games` (week 26 → 27) ([franchise_routes.py:3873](../../BackEnd/api/franchise_routes.py#L3873)) | Always, once per season. |
| `enqueue_banner_raise_if_user_won_national` | At the top of `finish_season`, before the franchise rollover wipes `national_tournament` ([franchise_routes.py:10897](../../BackEnd/api/franchise_routes.py#L10897)) | Only when user's team is the national champion. |

### Endpoints

- `GET /franchise/command-center/data` — response now includes `pending_championship_moments` (list).
- `GET /franchise/championship-moments/context?franchise_id&game_id` — returns `{ is_championship: bool, moment? }` for the live-game branch of the EOG popup. Computes the moment from the game doc + bracket state at request time, so it works before `eos_meta` has been stamped on the game document.
- `POST /franchise/championship-moments/dismiss` — `{ franchise_id, moment_id }`; pops the matching entry from the queue.

## Frontend architecture

Module: [FrontEnd/static/js/shared/championshipMoments.js](../../FrontEnd/static/js/shared/championshipMoments.js).
Public API (`window.ChampionshipMoments`):

- `showMoment(moment, options) -> Promise<void>` — renders one moment overlay; resolves on user dismissal.
- `processPendingMoments(franchiseId, moments, options) -> Promise<void>` — sequential render of a queue, server-clears each one after the user dismisses.
- `dismissOnServer(franchiseId, momentId)` — POSTs to the dismiss endpoint.

`options.lockerRoomUrl` and `options.boxScoreUrl` (or `boxScoreUrlBuilder(moment)`) drive the action buttons.

### Integration points

- **FCC mount** — [franchise-command-center.js:2772](../../FrontEnd/static/franchise-command-center.js#L2772). After `topData` loads, the queue is consumed via `processPendingMoments`. When the queue is non-empty, the legacy `maybeShowChampionshipCompleteModal` is skipped to avoid double-show.
- **Live game** — [gameCompletionPopup.js:51](../../FrontEnd/static/js/phaser/utils/gameCompletionPopup.js#L51). On franchise mode the popup first calls `/franchise/championship-moments/context`. If the just-completed game is a championship, the championship overlay replaces the standard EOG modal and the EOG flow short-circuits. The shared module is lazy-loaded on the gameplay page (FCC pre-loads it).

### Behavioral rules (all four)

- Backdrop click does **not** dismiss.
- ESC does **not** dismiss.
- Only one moment visible at a time.
- Once dismissed, the moment is removed server-side; refresh does not bring it back.
- Active team color flows through `--cm-team` and `--cm-team-deep` (deep is derived as a 55%-darkened shade of the primary).

### Eyebrow / pedestal data sources

- Season → `franchise.current_season`
- Conference label → `team_doc.conference` (integer)
- Region label → `team_doc.region` (letter)
- Conference seed (Trophy Spotlight) → `conference_tournaments[conf]['seeds'][team_id]`
- National rank → `franchise_team_data.natl_rank`
- Record → `calculate_franchise_standings(franchise.results)`
