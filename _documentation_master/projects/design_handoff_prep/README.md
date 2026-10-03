# Prep pages — design handoff

Frames sit in the browse-template shell (`tokens.css`, `components.css`, `templates.css`). New rules are only in `prep.css`. Sample names and numbers are illustrative. Structure and the fields below are the spec.

Open any file in `frames/` in a browser.

| Frame | State |
|---|---|
| `frames/prep-training-1280.html` | Default week. 6-pip steppers (0–5). Points 18/24. One coaching focus. Twelve development rows. Submit is the top-bar Advance. |
| `frames/prep-training-fatigue-1280.html` | Breaks at 5 and Scrimmages at 4, with the copy those rows already have. |
| `frames/prep-training-report-1280.html` | After submit. Notes, player deltas, team deltas, playbook CMD delta. Advance has moved on. |
| `frames/prep-game-plan-1280.html` | Twelve settings as five stops. Shot diet grouped. Save is orange. |
| `frames/prep-playbooks-1280.html` | Offense weights, one play open, call sheet reorder, 8 cap. Save is orange. |
| `frames/prep-scouting-1280.html` | Opponent, projected five in the roster grid, eight measures, side cards, one usage table. |
| `frames/prep-scouting-1920.html` | The three usage tables side by side. Densest extra. |

## Decisions

1. **Underline row, not the parallelogram.** Prep uses the shipped `.tb` / `.ink` row: Training · Game Plan · Playbooks · Scouting Report. Ink is neutral white. The handoff `components.css` parallelogram is not used here.
2. **One Advance.** On an open training week the top bar reads Submit Training. There is no second green button in the body. Auto-Train stays a neutral chip. After submit, Advance is the next week action (Play Next Game in the sample).
3. **Orange is only Save** (Game Plan, Playbooks). Training does not have a save; submitting is the Advance.
4. **Navy is only “this is yours.”** A play in the call sheet gets the navy row. Opponent rows on Scouting do not. Coaching-focus and segment selection stay neutral white.
5. **Blue only on elite glyphs** (attribute 9+, RT A). Pip fills are white luminance, not a tier color.
6. **Steppers, not sliders, on Training.** Six pips, values 0–5, matching the approved phase-5 swap. The attribute code (SC, SH, …) sits on the row that trains it.
7. **Game Plan stays five stops.** The current control is a 0–4 slider with names only on the ends and the middle. The frame uses those names and leaves the two unnamed stops blank. The line under a control repeats the selected name. Shot diet keeps the one existing sentence: the three sliders share touches.
8. **No card inside a card.** Sections are open. Tables use the one `.tcard`. Content starts 8px under the tab hairline. Only `.main` scrolls.
9. **Scouting summary is the high and low axis**, not a written game plan. The page does not have a “how to beat them” field.
10. **Weekly deltas keep the existing up/down/flat colors.** They are not actions. Green on a delta is the data chip, and the only green *button* is Advance.

## Components (new)

| Piece | What | Size |
|---|---|---|
| `.pips` | Six 14×8 stops. Filled = points assigned. | 6 × 14px, gap 4 |
| `.stops` | Five equal buttons for a 0–4 game-plan value. Selected = white-10. | height 28 |
| `.play` | One play row: grip, name, weight, CMD. `.on` = in the call sheet (navy). | min-height 40 |
| `.detail` | The open play: one existing sentence, weight, CMD, target or motion focus, sheet slot. | under the row |
| `.mrow` | Measure name, signed value, luminance bar from the center for −20…+20. | height 22 |
| `.budget` | Points used / 24 and the focus name. Meter is luminance. | numeral 28 |

Nothing else. Portraits are the existing `.av` at 28px. Attribute digits and RT letters are the T2 `.ad` / `.rtl`.

## Data needed

Confirm each exists. Do not invent a missing one.

**Training setup**
- Point budget total (page uses 24) and points remaining.
- Each drill value 0–5: inside/outside offense, inside/outside defense, passing, ball handling, rebounding, offense/defense install, FB offense/defense install, P/T offense/defense install, strength, agility, conditioning, free throws, film study, breaks, scrimmages.
- Playbook training mode: current vs custom.
- Coaching focus value (the four families and their leaves, including the Player Maximizer modes Top 3, Attributes 4–6, Positional, Custom).
- Per varsity player: name, jersey, RT current letter, RT potential letter, roster position, training position (PG–C), training focus (standard, offensive, defensive, athletic, fundamentals, rebounding).
- Position tally and focus tally.
- Auto-Train result (the focus it locks).

**Training report**
- Week, upcoming opponent, training focus.
- Notes text.
- Per player: the twelve attribute digits and which ones changed.
- Team measure deltas (Fight, Discipline, and the rest the report already prints).
- Playbook summary: play name, side, weight, CMD, CMD change.
- Projected five, attributes view and stats view.

**Game Plan** (each is 0–4)
- offense, inside, attack, outside, tempo, alterations, defense, aggression, half-court trap, full-court press, fast breaks, offensive rebounding.
- The three named labels per slider (the page already has them).
- Shot-diet shared-touches note (already one string).

**Playbooks**
- Per play: id, name, side, section (motion, set, fast break, man, zone, HC trap), active, locked/coming later, weight percent, CMD / effectiveness, top scorer, motion focus or target shooter.
- Call-sheet order, cap 8 offense and 8 defense.
- Flexible-section total and whether it is 100 (the “0 of 2 balanced” indicator).
- Position shot weights for the live strip.
- The one-line play copy (`copy_1` on Pick & Roll — Entry Pass is the sample).

**Scouting**
- Opponent name, record, national rank, team-page link.
- Projected five: portrait or monogram, jersey, name, RT letters, position, year, twelve attribute digits. Stats toggle: the season line the current table already shows.
- Eight radar axes, each −20 to +20: offensive efficiency, fb efficiency, discipline, pt efficiency, defensive efficiency, fb opp modifier, fight, pt opp modifier.
- Shooting (`shot_threshold`), rebounding (`rebound_modifier`), chemistry (`team_chemistry` / 25).
- Three usage tables: play name, times run, success rate, usage percent. Half-court offense, fast breaks, half-court traps.

## Questions

- **Per-player energy / fatigue.** Not on the training page. Only the Breaks and Scrimmages tooltips mention fatigue. No meter was designed.
- **Rotation and matchups.** Not on Game Plan. They are Set Lineup. Not designed here.
- **“How to beat them.”** No such string in the scouting payload. The frame shows the high and low measure only.
- **Unnamed game-plan stops.** Values 1 and 3 between the named ends have no label in the product. Left blank.
- **Fast-break and trap play names** on the 1920 usage sample (“Rim Run”, “Wing Trap”) are not confirmed. Replace with the names the usage API returns.
- **Shooting and rebounding scales.** The side cards use `shot_threshold` and `rebound_modifier`. The frame shows them as 62 and 48. Confirm the scale before treating those as percents.
