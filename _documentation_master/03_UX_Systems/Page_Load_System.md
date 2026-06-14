# Page Load System

## Purpose

Define the standardized page-load pattern for franchise-mode resource pages so initial downloads stay light and repeated page visits feel fast.

## Applies to

- `standings.html`
- `stats.html`
- `team-traits.html`
- `rankings.html`
- `leaders.html` / `leaders.js` (cache page key `leaders-v2`)
- `team-stats.html` / `team-stats.js` (cache page key `fcc-team-stats`)
- `schedule.html` (loads CC data first + loading message, but now fetches one national payload — see below)
- stateful gameplay transitions such as `set-lineup.html` -> `court.html`

Shared cache module: `FrontEnd/static/js/shared/resourceCache.js` (`ResourceCache.createResourceCache(page, franchiseId, season, week)` — memory Map + `sessionStorage`, key pattern below).

## Standardized process

1. Each standalone resource page first loads `/franchise/command-center/data`.
2. The page reads the current:
   - `franchise_id`
   - `current_season`
   - `week`
   - default user scope data such as `user_conference` or `user_region`
3. The page fetches only the default visible slice of data on first render.
   - While that initial scoped fetch is in flight, the page should show a lightweight loading message for the primary content area.
4. Additional slices are fetched only when the user clicks a toggle.
5. Each fetched payload is cached:
   - in memory for the current page life
   - in `sessionStorage` for the current browser session
6. Cache keys include:
   - page name
   - `franchise_id`
   - `current_season`
   - `week`
   - scope / region / conference selector
7. When week or season changes, the cache key changes automatically, so stale data is not reused.

## Cache key pattern

`resource:{page}:{franchise_id}:{season}:{week}:{scope_key}`

Examples:

- `resource:schedule:abc123:2:18:5`
- `resource:standings:abc123:2:18:A`
- `resource:stats:abc123:2:18:conference`

## Page behavior

### Schedule

- **Diverged from the scoped pattern (current behavior):** `schedule.html` fetches `/franchise/command-center/data` + `/franchise/schedule/national` in parallel and renders the full season (weeks 1–26 + tournament weeks 27–34) from the single national payload. No per-conference scoped fetching and no `ResourceCache` usage.
- While loading, the page shows `Loading schedule...`.
- The national endpoint returns the full schedule, `tournament_schedule`, `team_name_map`, and `team_display_name_map`.

### Standings

- First load fetches only the user's region.
- Clicking another region toggle fetches only that region.

### Stats

- First load fetches only `conference` scope.
- `region` and `national` are fetched only when selected.
- Each scope caches both:
  - `/franchise/team-stats`
  - `/franchise/leaders`

### Team Traits

- First load fetches only `conference` scope.
- `region` and `national` are fetched only when selected.

### Rankings

- Rankings remain a single national payload.
- `Top 25` and `All 128` are still client-side toggles.
- The page uses session caching for reload speed, but does not split rankings into multiple backend calls.

## SS&S rules

- Always prefer loading only the visible slice of data first.
- Do not fetch broad national/all-team payloads if the page initially shows a narrower scope.
- Keep caching browser-session scoped only.
- Do not use server-side global caches unless profiling later proves they are needed.
- Keep rendering separate from fetching and separate from caching.
- For stateful pages, do not hide the page-load overlay until all visible header/UI state has been hydrated from current data.

## Rationale

This pattern reduces initial page download cost, avoids repeated requests when users click back and forth between toggles, and keeps invalidation simple by tying cache keys to franchise, season, and week.
