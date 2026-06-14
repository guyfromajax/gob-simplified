## Plays Page System

## Overview

The Play Details page renders a single offensive play and its animation/copy.

Primary frontend:
- `FrontEnd/static/play-details.html`

Primary backend:
- `BackEnd/api/play_routes.py`

## Current Fetch Rules

Preferred fetch path:
- `GET /api/plays/{play_id}`

Compatibility fetch path:
- `GET /api/play/{play_name_or_id}`

**Data source note:** both routes read from the **`gob-staging` database's `plays` collection** (`get_staging_plays_collection()` in `play_routes.py`) — the play-builder workflow saves to staging first, and the Details page renders that staging copy, not the runtime `plays` collection of the active DB.

Navigation from Playbooks now prefers `play_id` and still includes `play_name` as fallback.

## URL Parameters

Current details-page identity parameters:
- `play_id`
- `play_name` fallback

The page loads by `play_id` when present.
It only falls back to `play_name` if `play_id` is missing.

## Skeleton Loading

Motion plays:
- use `skeletons.base_loop`

Set plays:
- use `skeletons.successful`
- tolerate both direct `steps` and `versions`

## Rename Safety

The Details page is now mostly rename-safe because:
- navigation prefers `play_id`
- fetch prefers `play_id`

Remaining compatibility behavior:
- the page still accepts `play_name`
- the compatibility route still resolves names

## Related Docs

- `_documentation_master/06_GMO_Supporting_Systems/Offense_Plays_System.md` (includes the Play Builder section)
- `_documentation_master/06_GMO_Supporting_Systems/Playbooks_Page.md`
