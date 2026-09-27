# Detail and roster polish — 2026-09-27

The detail pages now use the roster's attribute tiles, and a command center opened without `team_id` still resolves the user's team. The page formats the payload. It does not derive a rate, rank, place, streak, or attribute bucket.

## User team when the URL omits it

`GOBViews` resolves the user's team in one place: the URL (`team_id` or `user_team_id`), then `FranchiseLS` for that franchise, then the id the command center publishes from its payload (`team_id`, `user_team_id`, `user_team_object_id`, or `office_digest.user_team_id`). A view waits for that id before it mounts, so a first paint of `?tab=roster-view` no longer freezes an empty id and requests `/roster/`.

Rankings was the view that still read `team_id` off the URL for its team links. It uses the resolved id. Standings, Leaders, Team Stats, and Team Attributes already took `ctx.teamId`; they now receive it after the command-center payload. Shared roster links do the same when the URL has no owner.

A cold desktop open of Lancaster (`6ab284847ab3853ae89a1184`) at `tab=roster-view` with no `team_id` paints Varsity 12. The settled URL stays without `team_id`.

## Player attributes

Player attribute digits use `tileHtml`, the same component as the roster grid, at the roster size (`--dsz-30` by `--dsz-26`, digit `--fs-20`). 9+ stays the readable tier blue (`#6BA4E0`). Contrast on a 12 is at least 4.5:1 at 1280 and 1920.

## Null percentages

A null percentage renders an em dash. A real 0% stays `0.0`. `oneDecimal` already dashed nulls on the player hero and the season/career table. Leaders `showValue` and Team Stats decimal cells were turning null into `0.0` through `Number(null)`; they now dash a null rate.

Roger Henrich on the Lancaster save is 0-for-2 from three (`3PTM` 0, `3PTA` 2), so his 3PT% is the sent rate `0.0`, on the hero and in the season and career rows. His assists are 0 in 1 game, so AST is `0.0` as well. A percentage with no attempts is null on the payload and shows as an em dash.

## Development focus

The native select is the segmented control. Labels are the focus names. The emphasises line sits under the control (`Emphasises SC · SH · ID`) and is omitted for Standard, which emphasises nothing. Save is the orange save button, disabled until the selection changes. Saving calls `GOBStore.mutate`, then the button reads Saved and stays disabled.

## Team page roster

The team page uses a compact roster: Player (portrait and name), RT, POS, YR, HT, then SC, SH, ID, OD, RB. Starters and Bench stay. The card does not scroll sideways at 1280 or 1920. Team › Roster keeps the full grid.

## Team Attributes

A tie is `61st of 128`. The `T-` prefix is gone.

## Tests

109 passed, workers=1: t3-detail, t2-roster, t1-tables, shell-1, shell-1b, shell-2, store-client, navigation-history, navigation-fixes-3, app-router, office-frontend, standalone-roster, attr-tiles.

New coverage: every registered view opens with no `team_id` in the URL; player-tile contrast and size; null rates versus a real `0.0`; the focus control, the emphasises line, and `GOBStore.mutate`; the compact roster columns; ties without `T-`.

## Screenshots

Offline Lancaster save, pointer parked in `.main`, 1280×720 and 1920×1080, in `reports/detail-polish/`.

| File | Page |
|---|---|
| `offline-player-user-*` | Roger Henrich |
| `offline-player-cpu-*` | Derrick Smith |
| `offline-team-opp-*` | Little York |
| `offline-team-attributes-*` | Team Attributes, `61st of 128` |
| `offline-roster-no-team-*` | Roster, URL has no `team_id`, Varsity 12 |

Cold offline player first open was 310ms. The cold roster open with no `team_id` was 926ms, which includes waiting for the command-center payload before the roster request.

## Follow-up

The compact roster header was `position: sticky` with the page-head offset, inside a card that clips overflow, so the header painted under the first starter. Compact headers stay in normal flow. The header row is first, then Starters, then the players. The compact table does not repeat a header in the body, so the every-16-rows repeat cannot land on row 1.

The RT column had no width, and `table-layout: fixed` collapsed it onto the names. The player column has a minimum width and ellipsizes a long name inside that cell. RT has its own 4.75rem column. A row's text boxes no longer overlap, and the RT letters sit inside the RT cell, at 1280 and 1920, including a long name.

Development focus is a 3×2 grid of equal segments. The six names stay visible in two rows of three at 1280 and 1920, which reads more clearly than a dropdown that would hide five of them. Save stays orange while it is enabled.

t3-detail, t2-roster, shell-1, shell-2, and app-router passed (41). `offline-team-opp` and `offline-player-user` were retaken at both sizes.
