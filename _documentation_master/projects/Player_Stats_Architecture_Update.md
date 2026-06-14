# Player Stats Architecture Update

> **Status (2026-06-12):** Unimplemented proposal — moved from `03_Data_Persistence/` to `projects/`. Verified against code: no shared franchise player resolver exists, and the inconsistent season-stat reads this doc flags (`season_stats`, `stats.season`, etc.) are still present across ~10 frontend files (`box-score.js`, `rosterStatsRenderer.js`, `franchise-command-center.js`, …). The plan below remains valid future work.

## Problem

Player season stats in franchise mode are currently accessed through inconsistent read paths and inconsistent response shapes.

Examples of the current inconsistency:

- FCC Player Stats effectively relies on franchise-scoped player season data
- Player Detail was recently patched to read franchise-scoped `season` overlay data from the player endpoint
- Other pages may still rely on:
  - raw player doc fields
  - `/roster/...` payloads
  - page-local assumptions about `stats`, `stats.season`, `season`, or `season_stats`

This is not ideal SS&S. The core issue is not that franchise pages read franchise-scoped stats. That part is correct. The issue is that the access path and resolved data shape are not standardized.

## Correct SS&S Model

The clean source-of-truth split should be:

- Global player document:
  - identity
  - baseline bio
  - universal/default metadata
  - universal/default attributes

- Franchise player data document:
  - franchise-specific meta overrides
  - trained attributes
  - franchise position ratings
  - franchise season stats
  - franchise career progression

In other words:

- franchise season stats should remain franchise-scoped
- they should not be moved onto the universal player doc just to simplify page wiring

## What Needs To Change

### 1. Define a canonical franchise player view shape

Create one resolved player payload contract for franchise mode, used everywhere.

That resolved shape should include, at minimum:

- `_id`
- `first_name`
- `last_name`
- `name`
- `team`
- `year`
- `height`
- `weight`
- `jersey`
- `attributes`
- `position_ratings`
- `season`
- `career`
- derived helpers if desired:
  - `rt`
  - `best_position`

The key point is that all franchise pages should consume the same field names.

Avoid mixed patterns like:

- `player.stats.season`
- `player.stats`
- `player.season`
- `player.season_stats`

### 2. Centralize the merge logic

We should have one backend resolver for:

- base player doc
- franchise player overlay doc
- final merged franchise-mode player view

That resolver should be reused by:

- `/player/{player_id}` in franchise mode
- `/roster/{team_identifier}` in franchise mode
- FCC-supporting endpoints that expose player rows
- any future franchise player detail / scouting / stats endpoints

This prevents every route from manually deciding how to merge:

- attributes
- meta
- position ratings
- season stats
- career stats

### 3. Standardize season-stat field naming

Pick one canonical field name for resolved franchise player season stats.

Recommended:

- `season`

And one canonical field name for career history:

- `career`

Then stop exposing alternate equivalents unless there is a migration requirement.

### 4. Decide where derived values belong

Values like:

- `rt`
- best position
- formatted display name
- rebound totals
- percentages

should not be recomputed differently on every page.

We should decide whether these belong:

- in the backend resolved player payload
- or in shared frontend helper utilities

Either is acceptable, but it must be consistent.

### 5. Audit frontend consumers

We need an audit of FCC and other key pages for similar inconsistent player-data access.

This audit should explicitly check:

- FCC
- Player Detail
- Team Roster View
- Set Lineup
- Box Score
- Training Report
- Tournament pages
- Scouting-related pages
- any modal or card that displays player season stats, RT, or position

Specifically look for inconsistent reads of:

- `stats`
- `stats.season`
- `season`
- `season_stats`
- `rt`
- `position_ratings`
- `attributes`
- `MO` / momentum

## Recommended Implementation Order

1. Define the canonical resolved franchise player response shape
2. Build or extract a shared backend resolver utility for franchise player merge logic
3. Update `/player/{player_id}` franchise mode to use that resolver
4. Update `/roster/{team_identifier}` franchise mode to use that resolver
5. Audit FCC and other major pages and align them to the canonical shape
6. Remove redundant fallback logic once the standardized payload is live everywhere

## Important Note

This is not primarily a storage problem. It is a read-model consistency problem.

The fix is not:

- “move franchise season stats onto the global player doc”

The fix is:

- “standardize the franchise-mode resolved player view and make all major pages consume it”

## Follow-Up Audit Required

We need to audit FCC and other key pages for any similar data-access instances where:

- franchise-scoped player data is read through inconsistent field names
- derived values are recomputed differently by page
- pages rely on raw player docs when they should be using franchise-resolved player data

This audit should be treated as required follow-up work, not optional cleanup.
