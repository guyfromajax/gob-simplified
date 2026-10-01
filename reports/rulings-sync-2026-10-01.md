# Rulings sync: Styleguide + UX_System (2026-10-01)

**Status: ready for review.** Branch `docs/rulings-sync`, pushed. Not merged. Docs only: no CSS, no script, no token promoted.

Sources: `reports/jamie-decisions-2026-10-01.md`, `jamie-rulings-batch-2026-10-01.md`, `court-3-and-icon-2026-10-01.md`, `gallery-fixes-2026-10-01.md`.

## Split kept

| Doc | Holds | After this change |
|---|---|---|
| `Styleguide.md` | The look and the colour law | Every ruling is stated once, in the section it belongs to. New "Settled 2026-10-01" table links each ruling to that section. |
| `UX_System.md` | How to build | "Settled rulings" is now a build index only: files, selectors, guards. It links to the Styleguide for the rule and no longer restates it. |

## Closed (now in the law, out of "Open questions")

| Ruling | Where it lives in the Styleguide | UX_System |
|---|---|---|
| Navy = "yours" and what you picked; not a generic selected colour | Colour law, Navy row | index row 1 |
| Shot-share ramp kept as a data ramp | Data scales, Other ramps; Blue row names it as the one exception | index row 2; Play-flow section no longer calls it an open question |
| Court game-state colours are data | Colour law, new "Data palettes outside the table" | index row 3; the rule now has one home ("Live-game screen chrome"), the overlays section points to it |
| Court side panels blue-black, not grey | Elevation; Never do | index row 4 |
| Court stat toggles neutral | Team colour row (banned: a control's selected state); Choice controls | index row 5 |
| Tribute title marks gold | Reward gold row (sixth surface) | index row 6 |
| Presence dot neutral | Chips, pills and badges; Neutral by rule | index row 7, with the note that the dot is not visible under the shell today |
| No gold on buttons | Reward gold row; Modals (Moment); Never do | index row 8 |
| Submit Training green | Green row; Buttons (Gate) | index row 9; its sound stays `SFX_COMMIT` |
| Empty-state card | New "Empty states" component | "Empty states" keeps where to use it and links to the look |
| Franchise Set Lineup starts empty by design | Not a look rule: listed in the settled table only | New bullet in "Set Lineup" |
| Twin pages, desktop icon | Not a look rule: listed in the settled table only | index rows 10, 11 |

Styleguide "Open questions" went from 12 to 11: the navy question is gone, and the position-colours question now covers position colours only (the broadcast and game-state half is settled).

## Pending audit (not added)

Checked `git log origin/develop` right before pushing: audit's branch had **not** merged. Both are listed as "pending audit" in each doc and nowhere else:

| Ruling | Will change, once merged |
|---|---|
| Save buttons neutral until something has changed | Styleguide Orange row and the Action button role; UX_System "Save feedback" |
| Team art `logo_square` → `logo_primary` fallback | Styleguide "Headshots and logos"; UX_System team-art notes |

## Still open (Styleguide "Open questions")

1. Delta chips: which surfaces must be neutral.
2. W/L plates: neutral everywhere, or data in tables.
3. Orange beyond saves: the rail count badge, `.gated` / `.td-gate` / `.is-on`, the Office blocking outline, attitude bars, the modal accent, the tutorial alert, the leave-confirm "Stay".
4. Team-colour wash on the weekly / result card.
5. Destructive actions: neutral or a sanctioned red.
6. Navy aliases (`--you*`) stay local to `recruiting-spine.css`.
7. RT colours do not use the tier tokens.
8. `css/gob-buttons.css` still hard-codes old values.
9. Position colours have no tokens.
10. Tier digit ceiling: token comment and `attributeDisplay.js` disagree.
11. Repo `CLAUDE.md` still says the colour law lives in UX_System.

Also still open, in UX_System only: on-canvas Phaser text.

## Other corrections in the same two files

Statements that today's merged work had made false:

| Line | Was | Now |
|---|---|---|
| UX_System §7, League › Standings | "`?tab=standings-tab` still opens the old panel" | it remaps to `standings-view`; the panel is gone |
| UX_System, FCC freeze notes | `#standings-tab` listed as a panel still in the markup | removed from the list; its unused rules noted for the next peel |
| UX_System, Colour law | the checker / annotation sentence had ended up below the settled table | back under the law summary |

## Unsure

| # | Item |
|---|---|
| 1 | **"Do not add a franchise preset"** on Set Lineup is my wording of "starts empty by design". Soften it if a preset is still on the table. |
| 2 | **Submit Training is described as the training page's Advance (gate).** UX_System §3 says its sound is `SFX_COMMIT`, "not Advance". I left the sound rule alone and said so in the index. If green means it should also sound like Advance, that is a separate call. |
| 3 | **`game-state` and `team-identity` annotations.** The court pass writes them in `court.html`. The checker only reads `positive-data`, `committed`, `saved`, `reward`. The Styleguide now says those two are for readers only. |
| 4 | I did not touch repo `CLAUDE.md` (open question 11) or `00_Agent_Docs/CLAUDE.md`. |

## Checks

| Check | Result |
|---|---|
| `grep -cE '#[0-9A-Fa-f]{3,8}\b' Styleguide.md` | **0** |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe) |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| Playwright, pytest | not run (docs only, as briefed) |

Merge: `origin/develop` had not moved since the branch was cut (`fe28bb4d0`), so there was nothing to merge and no doc conflict.

## Files

| File | Change |
|---|---|
| `_documentation_master/11_Design_Systems/Styleguide.md` | +60 / −25 |
| `_documentation_master/11_Design_Systems/UX_System.md` | +27 / −18: settled index, court / play-flow / Set Lineup / empty-state passages, three corrections |
