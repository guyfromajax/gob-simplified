# RT Letter-Grade Display Experiment — Surface Audit and Implementation Brief

**Status:** Implemented; verification complete  
**Created:** August 3, 2026  
**Scope:** User-facing display of best/overall RT and PG/SG/SF/PF/C ratings

## 1. Objective

Experiment with displaying overall player/recruit RT as a letter grade while
preserving the raw numeric RT for calculations, sorting, filters, simulation,
and persistence. The experiment must be reversible through one shared display
setting rather than a page-by-page rollback.

This is a presentation change only. It must not alter:

- `position_ratings` values or their calculation;
- best-position selection;
- lineup, recruiting, roster, or CPU decision logic;
- numeric sort order;
- API payloads or persisted documents.

## 2. Proposed grade scale

The requested scale is:

| Numeric RT | Grade | Color |
|---:|:---:|---|
| 100+ | A++ | Light blue `#4A90D9` |
| 90–99 | A+ | Light blue `#4A90D9` |
| 80–89 | A | Light blue `#4A90D9` |
| 70–79 | B+ | Green `#34EC27` |
| 60–69 | B | Green `#34EC27` |
| 50–59 | C+ | Yellow `#FFD700` |
| 40–49 | C | Yellow `#FFD700` |
| Below 40 | F | Red `#ff6d6d` |

The same scale will apply to players and recruits of every year. The current
JH-specific recruit color thresholds will be retired for RT display if this
experiment ships.

## 3. Reversible implementation contract

Use the shared frontend display formatter anywhere RT is rendered:

```js
RT_DISPLAY_MODE = "letter" // in common.js; one-line frontend rollback: "number"

formatRtDisplay(rawRt)      // "B+" in letter mode; "84" in number mode
getRtDisplayClass(rawRt)    // class/color always derived from raw numeric RT
```

If backend-authored prose is included, add the equivalent backend formatter
using the same shared band definition. Do not send letter grades in place of
numeric API fields.

Rules:

1. Store and transport RT numerically.
2. Sort, compare, gate, and filter using raw numeric RT.
3. Convert only at the final rendering/copy boundary.
4. Unknown/null RT remains `--` or the surface's current empty state.
5. Keep column labels as `RT` unless product copy is intentionally changed.
6. Do not convert individual attributes.
7. Convert all five per-position rating displays through the same formatter.

This avoids a database migration and makes rollback a single configuration
change followed by ordinary asset deployment.

## 4. Confirmed primary player surfaces

| Surface | Display site | Current renderer |
|---|---|---|
| Standalone Team Roster — active roster | RT table column | `team-roster-view.js` |
| Standalone Team Roster — training/practice squad | RT table column | `team-roster-view.js` |
| FCC Roster tab | RT table column | `franchise-command-center.js` |
| FCC roster-adjacent tables | training squad and practice squad RT columns | `franchise-command-center.js` |
| FCC Scouting Report | projected-five RT badge/table cell | `js/shared/scoutingReport.js` |
| Player Detail | computed best RT/overall display, where present | `player-detail.js` |
| Set Lineup — player list | inline RT next to player name | `set-lineup.js` |
| Set Lineup — assigned-slot card | `RT: <value>` display | `set-lineup.js` |
| Set Lineup — player-card rating circle | highest position rating | `set-lineup.js` |
| Cut Players | RT column | `cut-players.js` |
| Training Report | player RT column and projected lineup | `training-report.js` |
| Pre-game Experience | starting-player edge RT values | `matchupsUiShared.js` via `preGameExperience.js` |
| In-game defense matchups popup | starting-player edge RT values | `matchupsUiShared.js` via `defenseMatchupsPopup.js` |
| Sim Game presentation | player RT badge | `simGamePresentation.js` |

The pre-game and defense-matchup overlays share one player-tile renderer, so
they should be migrated once in `matchupsUiShared.js`.

## 5. Confirmed recruiting surfaces

All recruit years must use the same new grade bands.

| Surface | RT presentations | Current renderer |
|---|---|---|
| FCC Coach's Office | recruiting card rows, current-week invite card | `franchise-command-center.js` |
| FCC Recruits tab | lean/signed recruit tables and invite banner | `franchise-command-center.js`, `recruiting-common.js` |
| Recruiting Hub / Recruits page | pool table, invite slots, priority rows, commitments/signings, visit summary | `recruiting-hub.js`, `recruiting-spine.js` |
| Recruiting main page | recruit and player tables | `recruiting.js`, `recruiting-common.js` |
| Recruiting Orders | pool rows, selected slots, focused rows | `recruiting-orders.js` |
| Recruiting Invites | pool rows, selected slots, focused rows | `recruiting-invites.js` |
| Recruiting Results | signed/visit result tables | `recruiting-results.js` |
| Training Report recruiting callout | structured recruit RT and legacy `RT: <number>` fallback text | `training-report.js` |
| Big recruiting/news modals | recruit RT number and label | `js/shared/bigNewsModals.js` |

The prior recruit display was fragmented across
`getRecruitRtBucketClass`, `getRecruitRtBucketClassForYear`, local fallbacks in
`recruiting-spine.js`, and direct string interpolation. Those should all route
through the new shared formatter/class helper.

### Recruiting controls that expose numeric RT

Recruiting Orders and Invites contain minimum-RT sliders and confirmation copy
such as `This recruit is rated 62`. Filtering remains numeric; visible slider
values show the exact threshold and grade together, and confirmation sentences
use the grade (§8).

## 6. Backend-authored and secondary displays

These are easy to miss because the numeric RT is composed before frontend
rendering:

| Surface/copy | Current source |
|---|---|
| FCC recruiting visit/news metadata such as `RT: 52` | `BackEnd/api/franchise_routes.py` |
| Season news: newly developed player is “now a 72 rated PG” | `BackEnd/api/franchise_routes.py` |
| Recruiting news: “a 54 rated…” and conference lists `Name (54)` | `BackEnd/api/franchise_routes.py` |
| Practice-squad roster announcements containing `Name (RT)` | practice-squad/franchise news builders |
| Offseason development report before/after RT or RT gain | franchise finish-season response and report UI |
| Recruit removal confirmation: “This recruit is rated 62” | `recruiting-orders.js`, `recruiting-invites.js` |

If “all surfaces” includes narrative prose, these must use a backend/shared-copy
formatter. Numeric deltas such as `+6 RT` may need to remain numeric because a
letter-grade change does not faithfully represent the magnitude of development.

## 7. Legacy, tutorial, and non-primary surfaces

These should be deliberately included or excluded rather than missed:

| Surface | Finding |
|---|---|
| Tournament roster views | `tournament.js` displays numeric RT; mode is sunset/legacy but still reachable in code. |
| Static A1 roster HTML files | Eight `team-roster/team-roster-*.html` files directly render RT and attribute bars. |
| Box score | Uses highest RT for ordering; no confirmed primary RT column in the current box-score table. Sorting must remain numeric. |
| Tutorials | Tutorial lineup logic uses RT for qualification/ranking; no conversion should touch that logic. Static tutorial screenshots/copy may continue to show whatever is baked into the image unless assets are intentionally regenerated. |
| Prototype/gallery HTML | Recruiting and design galleries contain mock RT values but are not production surfaces; do not migrate unless they are used for review baselines. |

## 8. Approved decisions

1. The corrected B+ band is **70–79**.
2. Convert both overall/best RT and all five PG/SG/SF/PF/C rating displays.
3. Recruiting threshold controls retain the exact numeric value and show its
   grade alongside it.
4. Backend-authored and frontend-authored prose uses grades.
5. Development deltas remain numeric (`+6 RT`).
6. Reachable legacy Tournament surfaces are included.
7. Use one shared global `letter`/`number` switch; simultaneous cohorts are not
   required for the initial experiment.

## 9. Canonical documentation updates when implemented

The best canonical owner is
[`11_Design_Systems/Styleguide.md`](../11_Design_Systems/Styleguide.md). It already
owns the Attribute Bar Scale, player RT color policy, and recruit RT exception.

When implementation ships:

- replace the current player/recruit RT display sections with the experiment
  mode, grade bands, colors, and rollback rule;
- keep the numeric Attribute Bar Scale for actual attributes and individual
  rating bar lengths while displaying their values as grades;
- update
  [`10_Players_Systems/Position_Ratings_System.md`](../10_Players_Systems/Position_Ratings_System.md)
  with a short cross-reference clarifying that RT remains numeric internally and
  is formatted only at the UI boundary;
- remove the JH/non-JH display-band distinction from canonical recruiting docs;
- keep this project file as the implementation checklist, not the long-term
  source of truth.

## 10. Verification checklist

- Boundary tests for 39/40, 49/50, 59/60, 69/70, 79/80, 89/90, 99/100,
  null, negative, decimal, and 100+ values.
- Same raw RT produces the same grade and color on player and recruit surfaces.
- Numeric sorting remains correct within the same grade (for example 89 before
  80 even though both display `A`).
- RT filters and game/recruiting logic remain numeric.
- No page-local grade or color thresholds remain.
- Number mode restores the existing numeric display without changing API data.
- Responsive layouts accommodate `A+` and labels such as `RT A+`.
- Screen-reader labels expose useful text rather than hiding the grade as
  decorative content.
