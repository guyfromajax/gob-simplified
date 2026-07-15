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

## Week 32 Franchise Snapshot: Lancaster vs CPU Average

Source:

- DB: `gob-staging`
- Franchise: `6a4f7d9d49987a7e01e21372`
- Week: `32`
- User team: `Lancaster Johnnies`
- CPU teams counted: `127`
- Read-only pull; no Mongo writes.

### Key Read

Lancaster's `shot_threshold` is `0.00` while the CPU average is `71.02`.

Because `shot_threshold` is a golf-score attribute where **lower is better**, this is a very large live gameplay advantage and is likely central to the current user-team blowout pattern. Lancaster is also above the CPU average in several roster and team-control attributes, but the shot-threshold gap is the clearest outlier.

### Team Attribute Snapshot

| Attribute | Lancaster | CPU Avg | Diff (Lancaster - CPU) |
|---|---:|---:|---:|
| `shot_threshold` | 0.00 | 71.02 | -71.02 |
| `discipline` | 10.00 | 9.67 | +0.33 |
| `fight` | 10.00 | 4.80 | +5.20 |
| `team_chemistry` | 25.00 | 18.45 | +6.55 |
| `offensive_efficiency` | 10.00 | 8.93 | +1.07 |
| `defensive_efficiency` | -3.00 | 7.35 | -10.35 |
| `fb_efficiency` | 10.00 | 7.31 | +2.69 |
| `pt_efficiency` | 10.00 | 8.61 | +1.39 |
| `fb_opp_modifier` | 8.00 | 6.98 | +1.02 |
| `pt_opp_modifier` | 10.00 | 8.64 | +1.36 |
| `rebound_modifier` | 0.08 | 0.01 | +0.07 |

### Player Attribute Snapshot

| Attribute | Lancaster Avg | CPU Team Avg | Diff (Lancaster - CPU) |
|---|---:|---:|---:|
| `SC` | 52.92 | 50.46 | +2.46 |
| `SH` | 45.33 | 52.12 | -6.79 |
| `ID` | 64.75 | 55.04 | +9.71 |
| `OD` | 52.58 | 48.02 | +4.57 |
| `PS` | 46.50 | 45.69 | +0.81 |
| `BH` | 44.08 | 42.89 | +1.19 |
| `RB` | 50.92 | 47.14 | +3.78 |
| `ST` | 52.75 | 60.92 | -8.17 |
| `AG` | 49.58 | 46.81 | +2.78 |
| `FT` | 56.92 | 42.83 | +14.09 |
| `ND` | 54.75 | 42.37 | +12.38 |
| `IQ` | 51.17 | 42.40 | +8.76 |
| `CH` | 53.67 | 64.42 | -10.76 |

### Position Rating Snapshot

| Rating | Lancaster Avg | CPU Team Avg | Diff (Lancaster - CPU) |
|---|---:|---:|---:|
| `PG` | 48.42 | 44.56 | +3.86 |
| `SG` | 49.33 | 49.13 | +0.21 |
| `SF` | 52.42 | 51.75 | +0.66 |
| `PF` | 52.00 | 49.72 | +2.28 |
| `C` | 40.00 | 38.86 | +1.14 |

### Aggregate Snapshot

| Bucket | Lancaster | CPU Avg | Diff |
|---|---:|---:|---:|
| Player attr avg sum | 675.92 | 641.10 | +34.82 |
| Team attr reported sum | 90.08 | 151.76 | -61.68 |
| Position rating avg sum | 242.17 | 234.03 | +8.14 |
