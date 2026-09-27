# News and Awards views — 2026-09-27

Branch `app/news-awards-views`, fast-forwarded onto `origin/develop` (`881201e01`) before the suite. News › News and News › Awards are in-page module views on the browse templates.

## Inventory

The old press tab and `news.html` were one feed of stored `season_news` headlines plus browser-built "your team" rows (`fccTeamDispatches` in `franchise-command-center.js`). A headline opened a story body of `rich_lines` or `lines`: gap, heading, link, `player_table`, `ranking_table`, `team_roster`, `game_result` (with a Box Score link). Story types on the feed are walk-ons, upset reports, Practice Squad, and recruiting. There is no press-conference type and no community-highlights feed here. `/franchise/league-news` is the training-load wire, not this tab.

`awards.html` rendered three All-American tables (1st, 2nd, 3rd) from `GET /franchise/awards`. Before week 35 that route is HTTP 400. The snapshot rows are `player_id`, `name`, `team_id`, `team_name`, `year`, `score`, and `stats` (PTS, REB, AST, STL, BLK, DEF%). No past winners, no season list, no coach or all-conference or all-region awards.

## Mapping (decision A)

1. Feed. `GET /franchise/news` still returns stored `season_news`, newest first, grouped by week. Each row has a type label. The navy left edge (`inset 3px #1c2a52`) is only where the payload says `yours`. No category filter on this view. The route still accepts `category` for other callers; it filters `news` only.

2. Story bodies stay. A headline is a detail drill-in: `GOBNav` push, then the story id is written onto that history entry. Back is `data-gob-up`, so it returns to the feed at the same scroll position. The body reuses the existing rich-line renderer (`js/shared/newsStory.js`). Tables use the browse tokens: luminance tiles for attributes, `rtBucket` letters for RT. Headlines are plain text.

   `news.html?story=<id>` redirects to `franchise-command-center.html?tab=news-view` and keeps the query, including `story`. That is the smaller choice (same shape as `rankings.html`). The old page is not left rendering. `awards.html` redirects to `tab=awards-view` the same way.

3. Dispatches stay, built on the server. `_news_dispatch_items` reads the same stored fields the browser used (`latest_training.week`, `season_inbox`). Wording is unchanged:

   - `Week {n} training report` when `latest_training.week >= 1` and the franchise and team ids exist. Target is the franchise training report. `link_label` is `view`.
   - `Week {n} Practice Squad development report` for `season_inbox` items of type `training_squad_report`. Target is the squad report. `link_label` is `view`.
   - Game results: `{user} defeated|lost to {opponent} {user_score}-{opponent_score}` when both names are present (`defeated` only when `result == "win"`). Otherwise the stored `copy`. Target is the stored `box_score_url`. `link_label` is `box score`.

   Every dispatch is `{week, type, headline, target, link_label, yours: true}`. `link_label` is extra so the view does not choose "view" versus "box score". The view paints dispatches at the top of their week group. `fccTeamDispatches` and `renderNewsTab` are gone.

   The home News card is unchanged: five headlines from `news_headlines` on the command-center payload, upset reports excluded. The card's links now open the in-app view (`buildStandaloneNewsUrl`).

   Cache. Dispatches are computed inside the existing `@browse_cached` handler. `season_inbox` is written on the week-advance `$set` that already folds `browse_rev`. `latest_training` is written on the training `$set` that already folds it. No new cache key. The ETag stays `franchise_id:season:week:browse_rev:build:signature`.

4. Name links: no. Headlines stay plain text. The browser does not parse names. Entity-tagged headlines would be a future backend change.

5. Awards. Three All-American tables with the stat line on the row. DEF% is the stored integer plus `%`. A row is `tr.me` when `team_id` matches the user's team (the snapshot has `player_id`, and the marker uses `team_id`). Before week 35, and on a 200 body with no `all_american_teams`, the view says "Awards are not available yet." No season selector, no portraits, nothing that is not in the snapshot. A team cell pushes `team-view`. Player names are plain text.

6. Inbound links. Rail section map: News and Awards are in-page tabs (`news-view`, `awards-view`), with no `link`. `?tab=press-tab` aliases to `news-view`. Training-report back target is `tab: 'news-view'`. The practice-squad box-score return is `tab=news-view&story=`. The home card uses the in-app URL. `authGuard` still allowlists `/news.html` and `/awards.html` so the redirect documents load. shell-1 and shell-1b assert the in-page panels. shell-2 still opens `news.html` and `awards.html`; those documents redirect into the shell, so the spec did not need a new URL. `?tab=awards-tab` is still the old League › Leaders panel and was left alone.

`news.js` and `awards.js` are unused. The renderer lives in `newsStory.js`.

## Fields

No new stored fields. `GET /franchise/news` adds `dispatches`, each `{week, type, headline, target, link_label, yours}`.

## Tests

- Baseline, before the feature, on `ffeaf7e0a`: 495 passed, 2 skipped, 7.1m, exit 0, port 8010, workers=1.
- After the feature, on this tree: 501 passed, 2 skipped, 7.4m, exit 0, port 8010, workers=1. The six new tests are `tests/e2e/news-awards.spec.js` (tabs stay in-page, week order with the yours dispatch on top, story push and scroll restore, `news.html?story=` and `awards.html` redirects, week-35 empty copy, skeleton and retry, no sideways scroll at 1280 and 1920).
- `tests/test_news_dispatches.py` covers the wording (win, loss, copy fallback) and the route on mongomock and sqlite.
- `tests/test_player_development_grid.py` now asserts the view interleaves dispatches above stories and that the training-report back target is `news-view`.

## Screenshots

`reports/news-awards/`, pointer parked in `.main`, 1280×720 and 1920×1080.

- `save-news-*` and `save-awards-*`: offline copy of the schedule-time save (Lancaster, week 3). The feed shows week groups, type labels, and the navy edge on the training report and the game result. Awards is the week-35 empty state.
- `fixture-news-*` and `fixture-awards-*`: week 12 feed (game-result dispatch on top, upset, recruiting) and a 1st-team row marked `tr.me` with DEF% 61.

STATUS: COMPLETE
