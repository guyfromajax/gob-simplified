# Names + recruiting colour — 2026-09-29

Branch: `fix/names-and-recruit-colour` (from `origin/develop` @ `932b8a250`).

## 1. Team names

**Source used:** the Team Builder–aware display resolver in `BackEnd/utils/franchise_team_display.py`.

`resolve_geek_points_teams(geek_points_by_team, user_id)` looks up each Geek Points key as `teams.team_id` (then ObjectId, then exact `teams.name`). The display string is `teams.name` as stored. If one of the user's franchises has a Team Builder overlay whose `replaced_object_id` matches that team, the overlay name replaces it. The key is shown unchanged when no team doc exists. Nothing is title-cased, hyphen-stripped, or exception-listed.

**Payload:** `GET /api/auth/me` now also returns additive `geek_points_teams: [{ team_id, display_name, points }]`. `geek_points_by_team` is unchanged. `display_name` is chrome (TB leak scanner treats it as chrome; wire `name` is not on this list). Leaderboard endpoints were not touched.

**Account page:** `account.html` renders `geek_points_teams[].display_name`. If that list is missing, it looks up `/teams` by `team_id` and otherwise shows the key as stored. `TEAM_NAMES` / `titleCaseName` are gone.

Verified in the Geek Points list: **IDA**, **Bentley-Truman** (hyphen kept), **Seattle AAA**.

### Other title / case display (listed, not rewritten)

These still reformat a team string for display. Same anti-pattern as the old Account title-case; left alone because they sit on other agents' surfaces or are shared globally.

| Place | What it does |
|---|---|
| `FrontEnd/static/common.js` `formatTeamName` | lowercases, then title-cases; hyphens kept per segment. Shared helper. |
| `franchise-command-center.js` ~518 | `formatTeamName(data.team)` |
| `playbook-report.js` | `formatTeamName` on home/away labels |
| `js/phaser/utils/pgpcSammyReminderModal.js` | `formatTeamName(userTeamName)` |
| `set-lineup.js` ~2343–2344 | `formatTeamName` then `.toUpperCase()` (Player Training / court surface — not edited) |
| `js/shared/usernameModal.js` ~91 | mascot `.toUpperCase()` in “YOU'RE COACHING THE …” |
| `js/shared/officeHome.js` ~257 `labelize` | title-cases **measure keys**, not team names — listed so it is not mistaken for the Account bug |

`recruiting-common.js` region alias title-case is region codes, not team names.

## 2. Recruiting colour law

Green only the top-bar Advance and positive data (board gains / up arrows). Orange only saves. Navy only “yours”. Choice controls and status labels neutral. RT ramp and attribute tiers unchanged.

### Week 21 (required)

| Control | Before | After |
|---|---|---|
| “Invite Season” label + phase dot | green + pulse | `--text-87` / muted status dot |
| “Submit Invites” (`.bbtn-save`) | green gradient | orange save (same as other saves) |
| Lean pill toward your team | green | navy |
| Lean pills toward other teams | (already muted) | still muted |
| “This week” visit tile | orange | outline emphasis |
| “1/7 invites sent” count | orange | `--text` |

### Rest of recruiting (same pass)

**Spine / pool / board**

- `--you` / `--you-soft` / `--you-line` remapped from green to navy (`#27408E`). Your-team lean tokens, region-mine chip, “mine” row edge, and standing chips follow.
- “On your lean list” gold (`--list`) remapped to quieter navy (still yours).
- Pool region chips: active = muted outline; your-region = navy. Not orange/green.
- Watch star: gold off → muted text (choice control).
- Sort arrow: orange → muted.
- “New” lean flag: green → muted status.
- Invite hero wash and visit pills: green → muted/outline.
- Phase timeline segments and key dots: green/blue/orange → muted; current week uses a stronger outline.
- Board movement wash (`.brow.gained`, `.bmv-ico.up`) **kept green** (positive data).

**Dock**

- Invite-week pips: sent green / now orange → muted / outline.
- “Leaning” chip and sent slots: green → navy.
- This-week slot: orange → outline.
- Save toast: green → orange (save confirmation).
- `.idock-save` was already orange.

**Signing Day hub**

- Pool / Orders tabs: green → muted (choice).
- Watch filter gold → muted (choice).
- Your-team stand / won rows / “mine” signing / user tally: green → navy.
- Submit Orders (`.rail-submit`) and leftover `.sd-btn.is-go`: green → orange save.
- Results “play” (`.rbtn.main`): green → muted (not Advance).
- Orders-submitted hub chip: green → orange (saved state).
- Budget remaining numeral: orange → `--text` (status count).
- Promise toggle **kept orange** (it commits a promise).
- Committed-order rail cards **kept orange wash** (saved commitments).
- Sign-odds meters (`o-lock` / likely / even / slim) **left as data viz**, same family as RT. Not remapped.

**Account**

- Scouting Ambience switch: orange on-state → scoped neutral switch (`#acct-ambience-switch` only; shared auth-bar switch untouched).

**Not loaded on the hub:** `recruiting.css` still has leftover `--gob-green` / gold budget chrome. The live hub uses spine + dock + signing only.

## 3. Tests

- `tests/test_geek_points_team_display.py` — stored names (hyphen, IDA, Seattle AAA), unknown key unchanged, TB overlay chrome, leak scanner clean on the `/me` shape.
- `tests/e2e/names-recruit-colour.spec.js` — Account names + neutral switch; week 21 computed colours; pool chips; signing day reachable.
- Polish Account assertion updated from “Bentley Truman” to **Bentley-Truman**.
- `invite-visit-calendar` and `recruits-pool` watch-star specs updated to the new (non-orange / non-gold) chrome.

## 4. Gate counts

**pytest** (`.venv/bin/python -m pytest --ignore=tests/e2e -q`): **4052 passed**, 16 skipped, 109 xfailed, 1 xpassed, **0 failed**.

**Playwright** (`env -u CI`, `PORT=8053`, `workers=1`, `PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright`): **640 passed**, 3 skipped. One flake on `recruiting-tabs` week-21 `page.goBack` (`net::ERR_ABORTED`) — not a colour assertion. Isolated re-run of that test on port 8054: **passed**. Colour-law specs (names-recruit-colour, invite-visit-calendar, recruits-pool watch star, polish account names): all passed.

TB leak detector suite: **15 passed**.

## 5. Screenshots (1280×720)

All opened and checked:

- `reports/names-recruit-colour/account-geek-points.png` — IDA, Bentley-Truman, Seattle AAA; ambience switch is white/neutral, not orange.
- `reports/names-recruit-colour/recruiting-week21.png` — Invite Season label + dot muted; 1/7 white; This week tile not orange; Submit Invites orange; LAN navy, FAI muted; top-bar Advance green.
- `reports/names-recruit-colour/recruiting-pool.png` — filters muted; your lean navy; other lean muted; Advance green.
- `reports/names-recruit-colour/signing-day.png` — reachable at week 35; your lean navy; points count white; Submit Orders present (disabled/empty board, so not the orange enabled fill).

## 6. Self-check

- Names show exactly as stored. No exceptions list.
- `/me` carries `geek_points_teams` (additive, TB-aware). Scanner green.
- Week 21: no green except Advance (+ board-gain data, not in that shot). Submit Invites orange. Your lean navy. Week tile and invite count not orange.
- RT / attribute tiles not restyled.
- Did not edit Home Base or Player Training files.
- Tracked `reports/` images regenerated by the full Playwright run were restored (`git checkout -- reports`). Only this folder’s shots are new.

STATUS: COMPLETE
