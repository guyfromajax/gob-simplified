# Team Images System

Team imagery lives under **`FrontEnd/static/images/teams/`**, one folder per team (and a shared **general** folder for fallbacks). Paths are built in code via **team_slug** and **asset key**; no hardcoded filenames.

---

## Folder structure

```
FrontEnd/static/images/teams/
  general/                    # Fallback when team unknown or asset missing
    general_banner_primary.jpg
    general_logo_square.png
    general_court.jpg
    general_background.png
  bentley_truman/
    bentley_truman_banner_primary.jpg
    bentley_truman_logo_square.png
    bentley_truman_court.jpg
    bentley_truman_background.png
  ocean_city/
    ...
  ...                         # One folder per team (slug)
```

- **Folder name** = team_slug (lowercase, spaces → underscores, no punctuation/hyphens).
- **Filename** = `{team_slug}_{asset_key}.{ext}` (e.g. `bentley_truman_court.jpg`).

---

## Naming and formats

| Asset key       | Format | Notes |
|-----------------|--------|--------|
| banner_primary  | JPG    | Wide/hero banner; used in brackets, scoreboard, team-select buttons. |
| logo_square     | PNG    | Square logo; transparent background. Used in FCC header, game plan, set-lineup, tournament top bar. |
| court           | JPG    | Court image for gameplay. **Do not resize or re-encode**—animation system depends on exact dimensions. |
| background      | PNG    | Headshot container background on roster, player-detail, set-lineup. |

**File specs** (dimensions, DPI, etc.) are not defined here; measure from reference assets or document separately for accuracy.

---

## How paths are built in code

- **Shared helper:** `FrontEnd/static/common.js`
  - **`nameToTeamSlug(teamName)`** — Derives slug from display name (e.g. `"Ocean City"` → `ocean_city`).
  - **`getTeamAssetPath(teamNameOrSlug, assetKey)`** — Returns path like `/images/teams/{slug}/{slug}_{asset}.{ext}`. If `teamNameOrSlug` is missing/invalid, uses **general** folder.
- **Asset keys:** `court`, `logo_square`, `background`, `banner_primary` (see `TEAM_ASSET_SPEC` in common.js).
- **Loading:** Pages that use team images load **common.js** so `getTeamAssetPath` is available; fallbacks point at **general** assets.

---

## Where each image type is used

| Asset            | Where used |
|------------------|------------|
| **banner_primary** | Mode-select team buttons; single-game / tournament / franchise team-select screens; bracket (FCC/TCC); court scoreboard (gameScene, bootGame). |
| **logo_square**     | FCC header; tournament top bar (user team); game plan; set-lineup header; player-detail team logo. |
| **court**           | Court/game page (Phaser background); play-details; play-builder(s); default in builders = general_court.jpg. |
| **background**      | Team roster view (headshot container); set-lineup (headshot container); player-detail (portrait background). |

---

## Source of truth

- **Canonical list of teams/slugs:** `teams/128_teams.txt` (and team JSON in `teams/`). Sync scripts and backend use these; frontend derives slug from team **name** when `team_slug` is not in the API response.
- **Fallback:** When a team has no folder or asset, paths resolve to **general** (e.g. `general_logo_square.png`). Ensure `images/teams/general/` contains all four asset types.
