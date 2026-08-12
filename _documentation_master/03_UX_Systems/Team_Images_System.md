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
| court           | JPG    | Court image for gameplay. **Exactly 3,333 × 2,083.** **Do not resize or re-encode**—animation system depends on exact dimensions and marking placement. |
| background      | PNG    | Headshot container background on roster, player-detail, set-lineup. |

**Court dimensions:** every team court (all 129, including `general`) is **3,333 × 2,083**.

**Court generator:** `scripts/generate_non_a1_courts.mjs` produced 120 of 129 courts from fixed geometry constants. The eight Conference 1 / A1 reference courts are excluded and hand-authored: `bentley_truman`, `lancaster`, `four_corners`, `morristown`, `ocean_city`, `little_york`, `xavien`, `south_lancaster`. Team Builder custom programs use the browser canvas port `FrontEnd/static/js/shared/teamCourtGenerator.js` (same geometry); Phaser loads the result as a **blob/object URL**, never a data URI.

---

## How paths are built in code

- **Shared helpers:**
  - **FE `nameToTeamSlug(teamName)`** (`FrontEnd/static/common.js`) — Derives path slug from display name (e.g. `"Queen's Guard"` → `queens_guard`).
  - **BE `slug_from_display_name`** (`BackEnd/utils/team_slug.py`) — Same rules; use at display→path / display→stored-slug boundaries. Not an identity normalizer.
  - **`getTeamAssetPath(teamNameOrSlug, assetKey)`** — Returns path like `/images/teams/{slug}/{slug}_{asset}.{ext}`. If `teamNameOrSlug` is missing/invalid, uses **general** folder.
- **Asset keys:** `court`, `logo_square`, `background`, `banner_primary` (see `TEAM_ASSET_SPEC` in common.js).
- **Loading:** Pages that use team images load **common.js** so `getTeamAssetPath` is available; fallbacks point at **general** assets.

---

## Where each image type is used

| Asset            | Where used |
|------------------|------------|
| **banner_primary** | Mode-select franchise card + team buttons; franchise team-select cards + loading banner; bracket (FCC); court scoreboard (gameScene, bootGame); EOG completion popup + in-game stats panel; box-score header; pulse loading overlay (`pageLoadOverlay.js`); FTE tutorial situation screen; *(sunset)* single-game/tournament team-select, TCC. |
| **logo_square**     | FCC header; game plan; set-lineup header; player-detail team logo; post-game press conference; *(sunset)* tournament top bar. |
| **court**           | Court/game page (Phaser background); play-details; play-builder(s); default in builders = general_court.jpg. |
| **background**      | Team roster view (headshot container); set-lineup (headshot container); player-detail for assigned players and signed recruits. Unsigned recruit detail uses neutral `#747474` because no team owns the player yet. |

---

## Source of truth

- **Canonical list of teams/slugs:** `teams/128_teams.txt` (and team JSON in `teams/`). Sync scripts and backend use these; frontend derives slug from team **name** when `team_slug` is not in the API response.
- **Fallback:** When a team has no folder or asset, paths resolve to **general** (e.g. `general_logo_square.png`). Ensure `images/teams/general/` contains all four asset types.
