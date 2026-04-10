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

- `docs/docs_1_systems/06_GMO_Supporting_Systems/Play_Builder_System.md`
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Playbooks_Page.md`
