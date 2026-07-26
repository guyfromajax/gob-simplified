# Mode Select overhaul — handoff

## Drop into the repo (replace in place)
- FrontEnd/static/mode-select.html
- FrontEnd/static/mode-select.css

## Read, don't copy
- CC Mode Select Overhaul Prompt.md — implementation prompt for Claude Code
- Mode Select JS Patch Notes.md — the three mode-select.js diffs (chips, game line, delete label)

## Preview
"Mode Select Redesign (preview).html" runs the real stylesheet against mock franchise /
leaderboard / ATL / highlights markup, so you can see every card state without the backend.
It expects the two team banner JPGs at FrontEnd/static/images/teams/<team>/<team>_banner_primary.jpg
(already in the repo) and FrontEnd/static/images/buttons/whiteball.svg. Open it from the repo
root, or from this folder after copying those assets in.

Preview-only chrome (the top bar, the layout A/B/C switcher, the franchise-state switcher and
the mock <script>) is NOT part of the production files.
