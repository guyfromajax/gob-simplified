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

### Court design variation (the 120 generated courts)

*(Merged from `projects/court_redesign_brief.md`, 2026-09-14.)* The 120 non-Conference-1 courts
vary hardwood and branding, using the eight Conference 1 courts as the reference for what is
possible (hardwood texture, center / deep-wing logo marks, overhead-light reflections).

**Never change:** court colour schemes; court spec, dimensions and naming convention.

**Roll per team, independently:** center-court treatment, non-center treatment, hardwood. Repeats
are allowed; apply compatibility rules after rolling. Percentages are **per-team random weights,
not portfolio quotas** — do not rebalance later courts to hit them (parquet need not land on 5%).

| Center court | Weight | | Non-center team logo | Weight | | Hardwood | Weight |
|---|---|---|---|---|---|---|---|
| None | 10% | | None | 50% | | Classic | 15% |
| Team logo | 60% | | Deep wing ×2 | 10% | | Gloss | 40% |
| Team wordmark | 30% | | Deep wing ×4 | 5% | | Fine plank | 25% |
| | | | Inside 3-pt arc ×2 | 25% | | Alternating board | 15% |
| | | | Inside 3-pt arc ×4 | 10% | | Parquet | 5% |

**Branding rules**

- A team logo normally appears **once**. The non-center ×2 / ×4 options explicitly override this and
  repeat it in symmetric locations; other decorative spots may stay unbranded.
- A wordmark (school/team name **or** mascot name) may appear **only at center court** — alone, or
  paired with one non-repeated logo elsewhere.
- **Exceptions:** 20 new courts plus Ocean City (**21 total**) carry one wordmark in a single deep-wing
  position; vary school-name vs mascot-name and placement (upper/lower × left/right) at random.
  **IDA** keeps its five shield placements as an intentional organic outlier.
- **Deep wing** = the open midcourt channel outside a 3-pt arc, between the arc and the center line
  (reference: Ocean City's lower-right school-name placement). **Not** the corner/short-wing area
  between an arc and the baseline.
- No full logo/mascot wordmarks rotated into the baseline border bands. **Baseline branding is
  tabled** for this rollout; the earlier 10% max / Bentley-Truman direction remains a future option.
- Abilene is included in the 120.
- Overhead-light reflections keep the slightly imperfect, human placement of the Conference 1
  courts: only very subtle variation in spacing, vertical alignment, size, intensity and softness —
  never mechanically exact, never exaggerated enough to look accidental.


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
