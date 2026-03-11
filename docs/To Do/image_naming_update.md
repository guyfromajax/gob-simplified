We are expanding Geeked-Out Basketball from 8 teams to 128 teams, so we need to standardize image naming conventions, formats, and folder structure to prevent future tech debt.

Please refactor the frontend image asset system accordingly.

1. Team Slug Definition

Each team must have a team_slug.

The team_slug is the normalized version of the school name and will be used for:

folder names

file names

asset path generation in code

team_slug rules
team_slug =
lowercase school name
spaces → underscores
remove punctuation
no hyphens
no abbreviations
Examples
Bentley-Truman → bentley_truman
Little York → little_york
Four Corners → four_corners
Queen's Guard → queens_guard
St. Anthony → st_anthony

The team_slug should be stored as a first-class field in the team data model, not dynamically derived in code.

Example:

{
  "team_name": "Bentley-Truman",
  "team_slug": "bentley_truman",
  "mascot": "Knights"
}
2. Naming Convention (New Standard)

All team assets must follow snake_case using the team_slug.

Rules:

lowercase only

underscores only

no punctuation

no hyphens

school name used (not mascot)

3. Standard Filename Pattern

All team assets must follow:

team_slug_asset.ext

Example:

bentley_truman_banner_primary.jpg
bentley_truman_banner_clean.svg
bentley_truman_mark.svg
bentley_truman_logo_square.png
bentley_truman_uniform_home.png
bentley_truman_court.jpg
bentley_truman_background.png
4. Standard File Formats

Use the optimal format for each asset type.

Asset	Format
banner_primary	JPG
banner_clean	SVG
mark	SVG
logo_square	PNG
uniform_home	PNG
court	JPG
background	PNG

Notes:

square logos must have transparent backgrounds

courts must remain JPG; do not convert or resize—pixel dimensions must stay unchanged (gameplay animation system depends on exact coordinates)

background: used as the player headshot container background on roster, player-detail, and set-lineup pages

5. New Folder Structure

We will move away from asset-type folders (courts/, square-logos/, teampage-logos/, etc.) and instead organize by team.

Current structure example
static/images/
    courts/
    square-logos/
    teampage-logos/
    team-backgrounds/
New structure
static/images/teams/

    bentley_truman/
        bentley_truman_banner_primary.jpg
        bentley_truman_banner_clean.svg
        bentley_truman_mark.svg
        bentley_truman_logo_square.png
bentley_truman_uniform_home.png
bentley_truman_court.jpg
bentley_truman_background.png

    general/
        general_banner_primary.jpg
        general_logo_square.png
        general_court.jpg
        general_background.png
        (other general_* assets as needed for fallback)

    little_york/
        little_york_banner_primary.jpg
        little_york_banner_clean.svg
        little_york_mark.svg
little_york_logo_square.png
little_york_uniform_home.png
little_york_court.jpg
little_york_background.png

This structure keeps all assets for a team in one location and scales cleanly to 128 teams.

The **general** folder holds generic/fallback assets (same naming pattern with slug "general"). Use these when a team has no assets yet or when team_slug is missing (e.g. default logo, default court). Duplicate an existing team’s assets into general and rename to general_* for initial setup.

6. Team slug source (backend)

Add **team_slug** as a first-class field on the team data model (e.g. in the teams collection). Populate it from the same rules (lowercase, spaces→underscores, remove punctuation, no hyphens). Ensure every API that returns team info used for asset paths (command center, standings, game, roster, tournament, etc.) includes team_slug so the frontend can build paths without deriving the slug.

7. Bracket and scoreboard logos

Bracket and scoreboard team logos should use the **banner_primary** asset (not logo_square). Update bracket (and any scoreboard) code to use the path for banner_primary (e.g. `teams/${team_slug}/${team_slug}_banner_primary.jpg`) when displaying team logos in the bracket.

8. Code Refactor Requirement

Update the frontend code to derive asset paths using the team_slug variable instead of hardcoded file names.

Example pattern:

team_slug = "bentley_truman"

banner_primary = `/images/teams/${team_slug}/${team_slug}_banner_primary.jpg`
banner_clean = `/images/teams/${team_slug}/${team_slug}_banner_clean.svg`
logo_square = `/images/teams/${team_slug}/${team_slug}_logo_square.png`
uniform_home = `/images/teams/${team_slug}/${team_slug}_uniform_home.png`
court = `/images/teams/${team_slug}/${team_slug}_court.jpg`
background = `/images/teams/${team_slug}/${team_slug}_background.png`

Use the **general** folder when team_slug is missing or the asset is not found (e.g. `/images/teams/general/general_logo_square.png`).

9. Migration

Please:

Create the new static/images/teams/ directory

Move existing team assets into team folders

Rename files to match the new naming convention

Update frontend references accordingly

Ensure no broken image references remain

10. Important Constraint

Court images must not be resized or altered during migration.

Their pixel dimensions must remain unchanged because the gameplay animation system depends on exact coordinates.