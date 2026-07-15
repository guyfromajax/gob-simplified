# Training Comparison

## Purpose

This project doc tracks the read-only comparison between **user Auto-Train** and **computer distant training** over a 26-week training window.

The immediate reason for this audit is to understand whether user teams can outpace computer teams through the season because the two paths train different systems.

## Audit Tool

Script:

```bash
scripts/training_delta_dry_run.py
```

Example:

```bash
./.venv/bin/python scripts/training_delta_dry_run.py --db gob-staging --seed 42
```

Target specific teams:

```bash
./.venv/bin/python scripts/training_delta_dry_run.py --db gob-staging --user-team "Lancaster" --cpu-team "Providence" --seed 42
```

The script is **read-only**. It loads franchise data from Mongo, clones the selected teams in memory, runs simulated training, prints deltas, and performs no Mongo writes.

## Side-by-Side Season Totals

The script now prints a compact side-by-side table before the detailed per-bucket tables.

Verified staging sample:

```text
Full-Season Side-by-Side Totals
-------------------------------
bucket                                      user_auto_train  cpu_distant_training  note
------------------------------------------  ---------------  --------------------  -------------------------------------------------
roster_player_attr_total_gain               704.0            1548.0                sum of all trainable attr deltas across roster
roster_player_attr_avg_gain_per_player      58.67            129.0                 total attr gain divided by loaded roster size
team_attr_total_gain                        34.0             75.1                  sum of reported numeric team attr deltas
position_rating_avg_delta_sum               20.08            45.93                 sum of average PG/SG/SF/PF/C rating deltas
offensive_play_effectiveness_total_gain     1942.0           n/a                   CPU distant training does not train plays
defensive_row_effectiveness_total_gain      2757.0           n/a                   CPU distant training does not train scouting rows
combined_play_def_effectiveness_total_gain  4699.0           n/a                   user-only trainable surface
```

Bucket definitions:

- `roster_player_attr_total_gain`: sum of all trainable player attribute deltas across every loaded roster player.
- `roster_player_attr_avg_gain_per_player`: total trainable attribute gain divided by loaded roster size.
- `team_attr_total_gain`: sum of the reported numeric team attribute deltas.
- `position_rating_avg_delta_sum`: sum of average PG, SG, SF, PF, and C rating deltas.
- `offensive_play_effectiveness_total_gain`: total effectiveness gain across user offensive plays.
- `defensive_row_effectiveness_total_gain`: total effectiveness gain across user defensive scouting rows.
- `combined_play_def_effectiveness_total_gain`: user play + defensive-row effectiveness gain.

Important: CPU distant training intentionally reports `n/a` for playbook/scouting effectiveness because distant training currently does not train those surfaces.

## Modeled Training Behavior

### User Team

The user team is modeled as pressing **Auto-Train** every week.

- Week 1 / training camp uses 30 points.
- Weeks 2-26 use 24 points.
- All 20 sliders start at 1.
- Random sliders are bumped to 2 until the week’s point budget is spent.
- Coaching focus is randomly selected from the same leaf focus options used by the frontend Auto-Train button.

### Computer Team

The computer team uses distant training templates.

- All non-user franchise teams use distant training.
- This includes computer teams in the user’s conference.
- The “same conference vs distant conference” distinction applies to game simulation depth, not training behavior.
- CPU distant training applies team attribute deltas and roster player deltas from `distant_training` templates.
- CPU distant training does not train offensive play effectiveness, defensive scouting effectiveness, playbook settings, or scouting reports.

## Initial Finding

In the first staging dry-run, both paths improved teams and players, but they improved different surfaces:

- CPU distant training produced strong player attribute growth.
- User Auto-Train produced player/team growth and also heavily increased offensive play effectiveness and defensive scouting-row effectiveness.
- CPU distant training reported `does_not_train_plays_or_scouting` for that bucket.

This is a real asymmetry. If user teams are overperforming across full seasons, this should be investigated as a likely contributor because the user path can compound play/defense effectiveness while CPU distant training cannot.

## Validation

Completed:

- `./.venv/bin/python -m py_compile scripts/training_delta_dry_run.py`
- `./.venv/bin/python scripts/training_delta_dry_run.py --help`
- Read-only staging run with `--db gob-staging --seed 42`

The staging run completed successfully and printed team attribute, player attribute, position rating, and play/defense effectiveness deltas.
