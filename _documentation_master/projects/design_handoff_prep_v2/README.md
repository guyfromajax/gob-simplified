# Prep v2 — design handoff

The four Prep pages (Training · Game Plan · Playbooks · Scouting Report) in the browse-template system. The rules come from `../design_handoff_browse_templates/` (tokens, components, templates) and the Underline tab row from `../design_handoff_subtabs_underline/`. `prep-v2.css` holds the new pieces only. `shell.js` injects the shipped top bar and rail into the preview frames. It is not product code.

Open `index.html` to see every frame at its real size next to its full scroll length. Each frame also opens on its own from `frames/`.

**Sample values are illustrative.** That covers names, initials standing in for headshots, ratings, percentages, notes text, play names, weights and CMD values. Only structure, tokens and behaviour are the spec.

| Frame | State |
|---|---|
| `frames/prep-training-1280.html` | Default week. 18/24 points, focus set. Submit Training (top-bar Advance) is disabled because the budget is not spent. |
| `frames/prep-training-high-load-1280.html` | Breaks 5, Scrimmages 4, 24/24. Their existing copy opens under each row. Pips above the remaining budget are hollow. Advance is enabled. |
| `frames/prep-training-report-1280.html` | After submit. Notes, team deltas, player report (changed tiles), projected five, playbook summary. Advance reads Play Next Game. |
| `frames/prep-game-plan-1280.html` | Twelve settings, 5-stop tracks, one effect line each. Fits 1280×720. Save is in view. |
| `frames/prep-playbooks-1280.html` | Offense view, one play open, sticky call sheet (5/8 offense, 3/8 defense). |
| `frames/prep-scouting-1280.html` | Opponent + strongest/weakest, projected five, eight measures, three usage tables. |
| `frames/prep-scouting-1920.html` | The same page on one screen (1016px of 1016 used). |

## Decisions

1. **Shell and tab row.** These use the shipped top bar and rail, plus the Underline row (Training · Game Plan · Playbooks · Scouting Report). The row has white ink, one hairline, and the head is 114px at 1280. Content starts 8px under the hairline. Only `.main` scrolls, and there are no cards inside cards. The one `.tcard` is only around tables.
2. **The page's action and status live on the tab row's right end** (`.pg-tools`), so they stay sticky and always fit on screen:
   - Training: points budget, focus check, Auto-Train.
   - Game Plan: Save.
   - Playbooks: Offense/Defense segment, balance check, Save.
3. **Colour law.**
   - Green is only the top-bar Advance. On an open week it reads Submit Training, and it is disabled until points and focus are both done.
   - Orange is only Save Game Plan and Save Playbooks.
   - Navy is only "yours": the rail item, call-sheet rows, and plays in the list that are on the call sheet.
   - Blue is only on elite glyphs (attribute 9+, RT A).
   - Choice controls (focus chips, segments, selects) stay neutral white.
4. **Deltas go neutral.** Training-report and playbook changes use ▲/▼ and luminance, not the green and red delta chips. The tier hue is already on the digit, and green is reserved. *To confirm:* say so if you'd rather keep the existing delta-chip colours.
5. **Changed attributes** (report) keep their tier glyph and luminance tile, plus a 1px ring and a direction mark. No second hue in the row.
6. **Training stepper.** Six stops for 0–5, matching the production `pipstep`: stop 0 is a dot, stops 1–5 are bars. It fills up to the current value and the current stop is brightest. Stops above the remaining budget are hollow (production disables them). A luminance numeral repeats the value.
7. **Breaks/Scrimmages copy** opens inline under the row, neutral with no hue. It uses the product's existing sentences. The trigger threshold must come from the product (see Data needed). If there isn't one, the copy stays a hover tip.
8. **Coaching focus.** Four families in a 2×2 grid, one row each. Player Maximizer keeps a single Choose Attributes chip. Its modes stay in the existing modal.
9. **Game Plan track.** The 0–4 value sits on five stops. The three product names are tick labels under 0, 2 and 4. Stops 1 and 3 are small unlabeled dots. The selected name turns white, and at 1 or 3 both neighbours turn t60, so the position reads without invented names.
10. **Game Plan effect lines** are cut down from the Game Plans tutorial copy, one line each. Tempo and Play Alteration have no source copy, so they show no line.
11. **Game Plan grouping.**
    - Shot diet keeps its nest and its existing tip. The nest also carries the existing validation: at least one of the three stays above Never.
    - Fast Break and Offensive Rebounding sit under a "Transition" eyebrow in the right column, which is the production column order.
12. **Playbooks.**
    - The open play expands in place: the `copy_1` sentence plus weight, CMD, target shooter, top scorer and call-sheet slot.
    - The call sheet sits beside the list and is sticky, with numbered slots, drag grip and "N open".
    - The live shot-weight strip stays on top.
13. **Scouting summary** is the strongest and weakest team measure, shown as display numerals. There is no written game plan. The two rows are also brightest in the measures list.
14. **Portraits** are 28px circles. Where there is no headshot, the fallback is initials on `--surface-3`.

## New components (all in `prep-v2.css`)

| Class | What |
|---|---|
| `.bud` | Points used / total, a luminance meter, points left, and a requirement check `.ck`. Sits in the tab-row tools. |
| `.ps` | Six-stop 0–5 stepper: states filled `.f`, current `.c`, over budget `.x`. Hit target is the 30px row. |
| `.dnote` | Inline copy under a drill row (Breaks/Scrimmages). |
| `.gt` + `.gpr` | Game Plan row: name and one line on the left, a five-stop track with three tick labels on the right. `role="slider"`, 0–4, arrow keys step. |
| `.play` + `.pdet` | Play row: name/meta, weight bar + %, CMD, call-sheet slot or add. `.on` means in the call sheet (navy). `.open` shows detail below. `.lk` means coming later. |
| `.csr` | Call-sheet row: slot numeral, grip, name, weight, CMD, all navy. `.csr.open` is the dashed "N open" filler. |
| `.ms` + `.xt` | Measure row using the existing `.dv` diverging bar at full width, −20…+20. `.xt` is the strongest/weakest block. |
| `.sel` | Quiet select (training position, training focus). Wraps the existing Development Focus selects. |
| `.btn-q` | Quiet display-face button (Auto-Train, Normalize → 100). |

Everything else is existing: `.tbl` / `.agrid` / `.ad` / `.rtl` / `.pos` / `.seg` / `.tg` / `.lnk` / `.btn-o` / `.advance` / `.dv` / `.av`.

## Data needed

Confirm each exists. **Do not invent, derive or approximate a missing one. Stop and ask.**

**Shell**
- Advance label and state per week phase (Submit Training / Play Next Game). Also its enabled condition on Training: the frame assumes points = total **and** focus chosen. Confirm against `updateRequirementsBar()`.

**Training (setup)**
- Point budget total (24 in sample), points used, points remaining.
- Twenty drill values, 0–5:
  - Player Drills: inside offense, outside offense, inside defense, outside defense, passing, ball handling, rebounding.
  - Scheme Installs: offense install, defense install, FB offense install, FB defense install, P/T offense install, P/T defense install.
  - Full Team Sessions: strength, agility, conditioning, free throws, film study, breaks, scrimmages.
- Attribute code each drill trains (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, FT, IQ). Confirm the mapping.
- Playbook training mode: Current Playbooks / Custom Playbook.
- Coaching focus value. The families are Authoritarian, Systems Coach, Player Maximizer and Culture Builder. The Player Maximizer modes are Top 3, Attributes 4–6, Positional, Custom.
- Coaching focus subtitle string (existing).
- Breaks and Scrimmages copy (existing strings), and **the value at which they show inline**. If there is no threshold field, keep them as hover tips.
- Per varsity player (12):
  - portrait URL or none (monogram fallback), jersey, name
  - RT current letter, RT potential letter, roster position
  - training position (PG–C), training focus (Standard, Offensive, Defensive, Athletic, Fundamentals, Rebounding)
- Position tally and focus tally.
- Auto-Train result (the focus it locks).

**Training report**
- Week, upcoming opponent, training focus. Brief line ("Week N Training Brief · For Coaching Staff Only").
- Notes (list of strings). The sample text is illustrative.
- Team measure deltas: Fight and Discipline, plus any others the report already prints. The frame shows two.
- Per player: twelve attribute digits, which ones changed, and the direction (up / down).
- Projected five: attributes view and stats view (existing columns).
- Playbook summary: play name, side, section, weight %, CMD, CMD change.

**Game Plan** (each 0–4)
- offense, inside, attack, outside, tempo, alterations, defense, aggression, hc_trap, fc_press, fast_breaks, rebounding.
- The three existing labels per setting (in `game-plan.html`).
- One-line effect copy. The frame uses shortened tutorial copy for ten settings. **Tempo and Play Alteration have no source copy. Write it or leave it blank.**
- Shot-diet tip string and the offense-not-all-Never validation (both existing).
- Existing hidden actions for the timeout entry (Back To Lineup, Cancel). They go beside Save in the tools slot.

**Playbooks**
- Per play: id, name, side, section (motion, set plays, fast breaks, man, zone, HC traps), active, locked / coming later, weight %, CMD, top scorer, motion focus or target shooter, `copy_1`.
- Section totals. Also which sections are flexible (fast breaks, HC traps must total 100) and the "N of 2 balanced" state. The frame shows 2 of 2.
- Save enabled condition (the production button starts disabled).
- Call-sheet order and membership, cap 8 offense + 8 defense. **How a play enters the sheet:** keep the existing assign control. The frame's "+" / slot badge marks where it sits.
- Position shot weights for the live strip. **Keep the strip's existing colour scaling and thresholds.** The frame shows neutral numerals as a stand-in.

**Scouting**
- Opponent name, logo/colour, record, national rank, team-page link.
- Projected five:
  - portrait or monogram, jersey, name
  - RT current and potential letters, position, year
  - twelve attribute digits
  - stats-view columns (the existing season line)
- Eight axes, −20…+20: offensive efficiency, fb efficiency, discipline, pt efficiency, defensive efficiency, fb opp modifier, fight, pt opp modifier. Confirm the display labels map to these (Offense, Fast Breaks, Discipline, Press/Traps, Defense, Fast Break Defense, Fight, P/T Offense).
- Strongest / weakest: computed as max / min of the eight. Confirm this is acceptable, or that a field exists.
- Shooting (`shot_threshold`) and rebounding (`rebound_modifier`), shown as bare numerals because their **scale is unconfirmed**. Chemistry (`team_chemistry` / 25).
- Usage tables: half-court offense, fast breaks, half-court traps. Each has play name, times run, success %, usage %. Also any locked/unlock state (see `test_scouting_usage_unlocks`). **Fast-break and trap play names in the frames are stand-ins.**

## Not designed (per the source handoff)
- No per-player energy/fatigue number on Training.
- No rotation or matchups on Game Plan. They belong to Set Lineup.
- No "how to beat them" text on Scouting.
