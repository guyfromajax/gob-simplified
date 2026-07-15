# Balancing Team Attributes

This doc summarizes how each persisted franchise team attribute moves during normal season play. It is intentionally high level for balancing work; source-of-truth implementation is in `BackEnd/models/training_execution_v2.py`, `BackEnd/api/franchise_routes.py`, `BackEnd/distant_sim_engine.py`, and the shared clamps in `BackEnd/constants`.

## Current Persisted Attributes

| Attribute | Range | Better Direction | Main Use |
|---|---:|---|---|
| `shot_threshold` | 20 to 220 | Lower | Shot make difficulty |
| `discipline` | -10 to 10 | Higher | Fouls, turnovers, pressure/contest checks |
| `fight` | -10 to 10 | Higher | Physicality, blocks, fast break/contact moments |
| `rebound_modifier` | 0.0 to 0.4 | Higher | Team rebound tie/score modifier |
| `momentum_score` | -10 to 10 | Higher | Distant sim season momentum |
| `offensive_efficiency` | -10 to 10 | Higher | HCO/pass/read execution |
| `team_chemistry` | 7 to 25 | Higher | Team cohesion, distant sim, rebounding ties, foul/contest factors |
| `defensive_efficiency` | -10 to 10 | Higher | Defensive execution and contest/read checks |
| `fb_efficiency` | -10 to 10 | Higher | Fast break offensive execution |
| `pt_efficiency` | -10 to 10 | Higher | Press/trap defensive execution |
| `fb_opp_modifier` | -10 to 10 | Higher | Fast break prevention/defense |
| `pt_opp_modifier` | -10 to 10 | Higher | Press/trap offense resistance |

## Shared Training Tables

The following team attributes use the standard training table:

- `offensive_efficiency`
- `defensive_efficiency`
- `fb_efficiency`
- `pt_efficiency`
- `fb_opp_modifier`
- `pt_opp_modifier`

| Points | Change |
|---:|---:|
| 0 | `-2` to `-1` |
| 1 | `0` to `+1` |
| 2 | `+1` to `+3` |
| 3 | `+2` to `+3` |
| 4 | `+2` to `+4` |
| 5+ | `+2` to `+5` |

`fight` and `discipline` use a separate shared table:

| Effective Points | Change |
|---:|---:|
| 0 | `-4` to `-3` |
| 1 | `-1` to `+1` |
| 2 | `0` to `+2` |
| 3 | `+1` to `+3` |
| 4 | `+2` to `+4` |
| 5+ | `+3` to `+5` |

`team_chemistry` uses its own table (`chemistry_ranges` in `training_execution_v2.py`). Effective points are the half-up rounded sum of weighted drill contributions (see Team Chemistry section), then bucketed `0–5`:

| Effective Points | Change |
|---:|---:|
| 0 | `-3` to `-1` |
| 1 | `0` to `+1` |
| 2 | `+1` to `+2` |
| 3 | `+2` to `+3` |
| 4 | `+2` to `+4` |
| 5+ | `+2` to `+5` |

Positive gains can be amplified by coaching focus. The focus multiplier is randomly selected from `1.5x`, `1.6x`, `1.7x`, or `1.8x`.

## Shot Threshold

`shot_threshold` is a golf-score attribute: lower is better.

During user training, scrimmages are the direct source:

| Scrimmage Points | Change |
|---:|---:|
| 0 | `+5` to `+15` |
| 1 | `0` to `+5` |
| 2 | `-3` to `-8` |
| 3 | `-5` to `-11` |
| 4 | `-5` to `-15` |
| 5+ | `-5` to `-20` |

At end of game:

- FG% above 50%: `-10` to `-5`.
- FG% above 45% and win: `-5` to `0`.
- FG% above 45% and loss: `0` to `+5`.
- FG% at or below 45%: `+5` to `+10`.

CPU distant training can also move it through `distant_training.team_values` template deltas. All persisted writes clamp to 20-220.

## Discipline

During user training:

- Inside Defense and Outside Defense feed `discipline` at 0.25x.
- Passing and Ball Handling feed `discipline` at 0.25x.
- Summed effective points use the fight/discipline table.
- Authoritarian focus, except Teamwork, gives a flat `+1` to `+2`.
- Culture Builder focus, except Confidence, gives a flat `-2` to `-1`.
- Authoritarian Discipline can amplify positive discipline gains.
- Breaks can reduce discipline:
  - 3 Breaks: `-1` to `0`.
  - 4 Breaks: `-2` to `-1`.
  - 5+ Breaks: `-3` to `-1`.

At end of game:

- If team fouls + turnovers are below opponent fouls + turnovers + 8: `+1` to `+2`.
- If team fouls + turnovers are above that buffered opponent total: `-2` to `-1`.
- Otherwise: `-1` to `0`.

CPU distant training can also move it through template deltas.

## Fight

During user training:

- Strength Training feeds `fight` at 0.5x.
- Conditioning feeds `fight` at 0.5x.
- Summed effective points use the fight/discipline table.
- Culture Builder focus, except Team Building, gives a flat `+1` to `+2`.
- Authoritarian focus, except Rebounding, gives a flat `-2` to `-1`.
- Authoritarian Discipline can amplify positive fight gains.
- Breaks can reduce fight:
  - 3 Breaks: `-1` to `0`.
  - 4 Breaks: `-2` to `-1`.
  - 5+ Breaks: `-3` to `-1`.

At end of game:

- Win: `0` to `+2`.
- Loss: `-2` to `0`.

CPU distant training can also move it through template deltas.

## Rebound Modifier

During user training:

- Technical Drills / Rebounding gives effective team points at 0.5x, rounded half-up.
- Scrimmages also feed rebounding at 0.5x, rounded half-up.
- Both sources now use the same effective-point ranges:

| Effective Points | Change |
|---:|---:|
| < 1 | `-0.05` to `-0.03` |
| 1-2 | `+0.03` to `+0.05` |
| 3-4 | `+0.03` to `+0.07` |
| 5+ | `+0.03` to `+0.10` |

Authoritarian Rebounding can amplify positive gains. Breaks does not scale or reset `rebound_modifier`.

At end of game:

- Outrebound opponent by more than 8: `+0.00` to `+0.05`.
- Get outrebounded by more than 8: `-0.05` to `-0.10`.
- Otherwise: `-0.01` to `-0.05`.

CPU distant training can also move it through template deltas.

## Momentum Score

User training currently does not allocate direct momentum-score points. There is a code TODO for a future coaching-focus amplifier, but no normal user-training write today.

At end of game, normal live/full-sim finalization does not change `momentum_score` in `update_team_attributes_after_game`.

Distant simulated CPU games update `momentum_score` and distant win/loss streak fields through `compute_distant_momentum_score_updates()`. Team chemistry affects the size of these distant momentum updates.

CPU distant training templates may include `momentum_score` deltas if the template contains that key.

## Offensive Efficiency

During user training:

- Team Offense / Install feeds `offensive_efficiency`.
- Uses the standard training table.
- Systems Coach / Offense can amplify positive gains.

At end of game for non-distant games:

- More than 12 offensive play calls: `0` to `+1`.
- More than 10 offensive play calls: `-1` to `0`.
- 10 or fewer: `-2` to `-1`.

At end of game for distant sim games:

- Random `-2` to `+1`.

CPU distant training can also move it through template deltas.

## Team Chemistry

During user training:

- Free Throws feed `team_chemistry` at 0.25x.
- Film Study feeds `team_chemistry` at 0.25x.
- Scrimmages feed `team_chemistry` at 0.25x.
- Weighted contributions are summed, then half-up rounded to an effective-point bucket (`0–5`):

| Effective Points | Change |
|---:|---:|
| 0 | `-3` to `-1` |
| 1 | `0` to `+1` |
| 2 | `+1` to `+2` |
| 3 | `+2` to `+3` |
| 4 | `+2` to `+4` |
| 5+ | `+2` to `+5` |

- Culture Builder / Team Building gives a flat `+1` to `+3`.
- Authoritarian / Teamwork gives a flat `0` to `+1`.
- Culture Builder / Inspire can amplify positive chemistry gains.
- Breaks can directly move chemistry:
  - 3 Breaks: `-1` to `+1`.
  - 4 Breaks: `-2` to `+1`.
  - 5+ Breaks: `-3` to `+1`.

At end of game, chemistry is based on national rank. Lower integer rank is better: `#1` is highest, `#128` is lowest. Missing rank is treated as `999`.

- Beat a lower-ranked team: `0` to `+1`.
- Beat a higher-ranked team outside the top 10: `+1` to `+2`.
- Beat a higher-ranked top-10 team: `+2` to `+4`.
- Lose to a higher-ranked top-10 team: `-1` to `0`.
- Lose to a higher-ranked non-top-10 team: `-2` to `0`.
- Lose to a lower-ranked team ranked 100-128: `-5` to `-3`.
- Lose to another lower-ranked team: `-3` to `-2`.

CPU distant training can also move it through template deltas.

## Defensive Efficiency

During user training:

- Team Defense / Install feeds `defensive_efficiency`.
- Uses the standard training table.
- Systems Coach / Defense can amplify positive gains.

At end of game for non-distant games:

- Max defensive row share at or below 39%: `0` to `+1`.
- Max defensive row share at or below 49%: `-1` to `0`.
- Max defensive row share above 49%: `-2` to `-1`.

At end of game for distant sim games:

- Random `-2` to `+1`.

CPU distant training can also move it through template deltas.

## Fast Break Efficiency

During user training:

- Fast Breaks / Offense Install feeds `fb_efficiency`.
- Uses the standard training table.
- Systems Coach / Fast Breaks can amplify positive gains.

At end of game for non-distant games:

- If one fast-break type exceeds 60% of team fast-break usage: `-2` to `-1`.
- If one type exceeds 50%: `-1` to `0`.
- Otherwise: `0` to `+1`.

At end of game for distant sim games:

- Random `-2` to `+1`.

CPU distant training can also move it through template deltas.

## Press/Trap Efficiency

During user training:

- Presses/Traps / Defense Install feeds `pt_efficiency`.
- Uses the standard training table.
- Systems Coach / Press-Trap can amplify positive gains.

At end of game for non-distant games:

- More than 20 press/trap attempts: `-2` to `-1`.
- More than 16 attempts: `-1` to `0`.
- Otherwise: `0` to `+1`.

At end of game for distant sim games:

- Random `-2` to `+1`.

CPU distant training can also move it through template deltas.

## Fast Break Opponent Modifier

During user training:

- Fast Breaks / Defense Install feeds `fb_opp_modifier`.
- Uses the standard training table.
- Systems Coach / Fast Breaks can amplify positive gains.

At end of game for non-distant games:

- Opponent fast-break total above 15: `-2` to `-1`.
- Opponent fast-break total above 10: `-1` to `0`.
- Otherwise: `0` to `+1`.

At end of game for distant sim games:

- Random `-2` to `+1`.

CPU distant training can also move it through template deltas.

## Press/Trap Opponent Modifier

During user training:

- Presses/Traps / Offense Install feeds `pt_opp_modifier`.
- Uses the standard training table.
- Systems Coach / Press-Trap can amplify positive gains.

At end of game for non-distant games:

- Opponent press/trap attempts above 16: `-2` to `-1`.
- Opponent press/trap attempts above 12: `-1` to `0`.
- Otherwise: `0` to `+1`.

At end of game for distant sim games:

- Random `-2` to `+1`.

CPU distant training can also move it through template deltas.

## Other Code Paths That Affect Team Attributes

Confirmed normal persisted progression paths:

- **User team training:** `execute_training()` / `apply_training_points()` mutate the user's FTD `team_attributes` through the selected weekly training allocation.
- **CPU distant training:** `_apply_franchise_distant_cpu_training()` applies template deltas from the `distant_training` collection to all non-user FTDs.
- **End-of-game progression:** `update_team_attributes_after_game()` updates both teams after live, full-sim, and distant-sim games.
- **Distant sim momentum:** `_distant_sim_persist_momentum_score_updates()` updates `momentum_score` and distant streak fields after distant games.

Other code paths found in the scan:

- **Initialization/backfill/migration scripts** can seed, migrate, or repair `team_attributes`, but they are not normal runtime progression.
- **Tournament/practice-squad/game-init helpers** create team-attribute payloads for those modes or game snapshots.
- **Home crowd, score-balancing, tutorial, and other gameplay modifiers** can temporarily change effective shot thresholds or use team attributes during a game. Those are not persisted back to FTD `team_attributes` as progression.
- **Offensive play effectiveness and defensive scouting-row effectiveness** are separate persisted systems. They can decay at end of game and improve through training, but they are not fields inside `team_attributes`.

Bottom line: for franchise balancing, the persistent team-attribute movement to watch is training, CPU distant training, end-of-game progression, and distant-sim momentum. I did not find another normal runtime path that silently progresses the core `team_attributes`.

## 100-Season Simulation Snapshot

Read-only dry run via `scripts/team_attr_season_dry_run.py` after the latest training-range recalibration.

- **Runs:** 100 seasons × 26 weeks (no byes)
- **Seeds:** 1000–1099
- **Roster source:** `Lancaster Johnnies` (staging franchise `6a4f7d9d49987a7e01e21372`)
- **Start attrs:** random franchise init ranges each run
- **Training:** Auto-Train (week 1 = 30 pts, weeks 2–26 = 24 pts) + random coaching focus
- **EOG:** random W/L each week; uniform random outcome band per attribute, then roll inside band
- **Record:** mean wins `12.80 ± 2.59` out of 26 (approx 50% W/L by design)

Values below are **mean ± sample stdev** across the 100 runs.

| Attribute | Start | End | Net | Training sum | EOG sum |
|---|---:|---:|---:|---:|---:|
| `shot_threshold` | 105.01 ± 3.26 | 119.93 ± 35.76 | +14.92 ± 35.47 | +15.17 ± 17.39 | -0.25 ± 32.77 |
| `discipline` | 0.06 ± 0.84 | -5.45 ± 4.78 | -5.51 ± 4.83 | +3.69 ± 5.28 | -9.20 ± 6.03 |
| `fight` | -0.10 ± 0.80 | 5.09 ± 5.15 | +5.19 ± 5.25 | +5.42 ± 5.17 | -0.23 ± 2.93 |
| `team_chemistry` | 8.46 ± 1.11 | 18.33 ± 5.17 | +9.87 ± 5.28 | +11.99 ± 3.05 | -2.12 ± 5.79 |
| `offensive_efficiency` | 0.01 ± 0.75 | 6.34 ± 3.45 | +6.33 ± 3.46 | +20.57 ± 3.38 | -14.24 ± 4.12 |
| `defensive_efficiency` | -0.03 ± 0.80 | 6.95 ± 3.40 | +6.98 ± 3.43 | +20.37 ± 3.80 | -13.39 ± 4.41 |
| `fb_efficiency` | 0.01 ± 0.85 | 6.63 ± 3.17 | +6.62 ± 3.37 | +20.64 ± 3.41 | -14.02 ± 3.75 |
| `pt_efficiency` | -0.03 ± 0.81 | 6.94 ± 3.07 | +6.97 ± 3.28 | +20.43 ± 3.42 | -13.46 ± 4.25 |
| `fb_opp_modifier` | 0.07 ± 0.82 | 6.84 ± 3.22 | +6.77 ± 3.21 | +20.04 ± 3.43 | -13.27 ± 4.25 |
| `pt_opp_modifier` | -0.02 ± 0.78 | 6.90 ± 3.02 | +6.92 ± 3.08 | +20.80 ± 3.35 | -13.88 ± 4.01 |
| `rebound_modifier` | 0.200 ± 0.000 | 0.017 ± 0.027 | -0.183 ± 0.027 | +0.000 ± 0.000 | -0.183 ± 0.027 |

Notes:

- `shot_threshold` is golf-score (lower is better); positive net means worse shooting threshold.
- Training sum / EOG sum are post-clamp applied weekly deltas accumulated over the season.
- Chemistry often hits the 25 ceiling, so training mean can exceed observed net.

## 100-Season Simulation Snapshot (after Breaks/rebound fix)

Second 100-run batch after excluding `rebound_modifier` from Breaks scaling and keeping rebound on a float/0.01 grid.

- **Runs:** 100 seasons × 26 weeks (no byes)
- **Seeds:** 1000–1099 (same as first batch for comparison)
- **Roster source:** `Lancaster Johnnies` (staging franchise `6a4f7d9d49987a7e01e21372`)
- **Start attrs:** random franchise init ranges each run
- **Training:** Auto-Train (week 1 = 30 pts, weeks 2–26 = 24 pts) + random coaching focus
- **EOG:** random W/L each week; uniform random outcome band per attribute, then roll inside band
- **Record:** mean wins `12.80 ± 2.59` out of 26

Values below are **mean ± sample stdev** across the 100 runs.

| Attribute | Start | End | Net | Training sum | EOG sum |
|---|---:|---:|---:|---:|---:|
| `shot_threshold` | 105.01 ± 3.26 | 119.93 ± 35.76 | +14.92 ± 35.47 | +15.17 ± 17.39 | -0.25 ± 32.77 |
| `discipline` | 0.06 ± 0.84 | -5.45 ± 4.78 | -5.51 ± 4.83 | +3.69 ± 5.28 | -9.20 ± 6.03 |
| `fight` | -0.10 ± 0.80 | 5.09 ± 5.15 | +5.19 ± 5.25 | +5.42 ± 5.17 | -0.23 ± 2.93 |
| `team_chemistry` | 8.46 ± 1.11 | 18.33 ± 5.17 | +9.87 ± 5.28 | +11.99 ± 3.05 | -2.12 ± 5.79 |
| `offensive_efficiency` | 0.01 ± 0.75 | 6.34 ± 3.45 | +6.33 ± 3.46 | +20.57 ± 3.38 | -14.24 ± 4.12 |
| `defensive_efficiency` | -0.03 ± 0.80 | 6.95 ± 3.40 | +6.98 ± 3.43 | +20.37 ± 3.80 | -13.39 ± 4.41 |
| `fb_efficiency` | 0.01 ± 0.85 | 6.63 ± 3.17 | +6.62 ± 3.37 | +20.64 ± 3.41 | -14.02 ± 3.75 |
| `pt_efficiency` | -0.03 ± 0.81 | 6.94 ± 3.07 | +6.97 ± 3.28 | +20.43 ± 3.42 | -13.46 ± 4.25 |
| `fb_opp_modifier` | 0.07 ± 0.82 | 6.84 ± 3.22 | +6.77 ± 3.21 | +20.04 ± 3.43 | -13.27 ± 4.25 |
| `pt_opp_modifier` | -0.02 ± 0.78 | 6.90 ± 3.02 | +6.92 ± 3.08 | +20.80 ± 3.35 | -13.88 ± 4.01 |
| `rebound_modifier` | 0.200 ± 0.000 | 0.364 ± 0.037 | +0.164 ± 0.037 | +1.038 ± 0.150 | -0.874 ± 0.152 |

Notes:

- Same seed range as the first snapshot so training/EOG randomness is comparable aside from the Breaks/rebound code change.
- `rebound_modifier` training should now show non-zero contribution (Breaks no longer zeroes fractional gains).

## 100-Season Simulation Snapshot (seed block 5000–5099)

Third 100-run batch with a **different seed block** and current logic (including Breaks/rebound fix). No balancing formula changes vs the second snapshot — only the random sample differs.

- **Runs:** 100 seasons × 26 weeks (no byes)
- **Seeds:** 5000–5099
- **Roster source:** `Lancaster Johnnies` (staging franchise `6a4f7d9d49987a7e01e21372`)
- **Start attrs:** random franchise init ranges each run
- **Training:** Auto-Train (week 1 = 30 pts, weeks 2–26 = 24 pts) + random coaching focus
- **EOG:** random W/L each week; uniform random outcome band per attribute, then roll inside band
- **Record:** mean wins `12.64 ± 2.68` out of 26

Values below are **mean ± sample stdev** across the 100 runs.

| Attribute | Start | End | Net | Training sum | EOG sum |
|---|---:|---:|---:|---:|---:|
| `shot_threshold` | 105.06 ± 3.06 | 117.16 ± 39.46 | +12.10 ± 39.20 | +16.13 ± 17.02 | -4.03 ± 35.23 |
| `discipline` | 0.05 ± 0.81 | -5.38 ± 4.82 | -5.43 ± 4.97 | +3.20 ± 6.02 | -8.63 ± 6.04 |
| `fight` | 0.07 ± 0.81 | 4.70 ± 5.07 | +4.63 ± 4.91 | +5.18 ± 4.42 | -0.55 ± 3.11 |
| `team_chemistry` | 8.53 ± 1.11 | 17.54 ± 5.63 | +9.01 ± 5.72 | +11.89 ± 3.32 | -2.88 ± 6.15 |
| `offensive_efficiency` | -0.02 ± 0.78 | 6.18 ± 4.21 | +6.20 ± 4.30 | +19.85 ± 3.37 | -13.65 ± 4.65 |
| `defensive_efficiency` | -0.02 ± 0.80 | 6.21 ± 3.56 | +6.23 ± 3.70 | +20.40 ± 3.23 | -14.17 ± 4.23 |
| `fb_efficiency` | 0.20 ± 0.84 | 6.30 ± 3.97 | +6.10 ± 3.91 | +20.87 ± 3.55 | -14.77 ± 4.24 |
| `pt_efficiency` | -0.12 ± 0.84 | 6.80 ± 3.53 | +6.92 ± 3.65 | +20.32 ± 3.85 | -13.40 ± 4.15 |
| `fb_opp_modifier` | 0.13 ± 0.86 | 7.19 ± 3.06 | +7.06 ± 2.97 | +20.09 ± 3.70 | -13.03 ± 4.19 |
| `pt_opp_modifier` | -0.05 ± 0.83 | 6.94 ± 3.10 | +6.99 ± 3.16 | +20.56 ± 3.51 | -13.57 ± 4.71 |
| `rebound_modifier` | 0.200 ± 0.000 | 0.363 ± 0.034 | +0.163 ± 0.034 | +1.030 ± 0.175 | -0.866 ± 0.179 |

Notes:

- Compare to the second snapshot (seeds 1000–1099, post Breaks fix) to see sampling variance with identical rules.

## 100-Season Simulation Snapshot (seed block 7000–7099)

Fourth 100-run batch after latest range tweaks: standard training bucket `1 → 0…+1`, discipline EOG bad band `−2…−1`, fight EOG win `0…+2` / loss `−2…0`.

- **Runs:** 100 seasons × 26 weeks (no byes)
- **Seeds:** 7000–7099
- **Roster source:** `Lancaster Johnnies` (staging franchise `6a4f7d9d49987a7e01e21372`)
- **Start attrs:** random franchise init ranges each run
- **Training:** Auto-Train (week 1 = 30 pts, weeks 2–26 = 24 pts) + random coaching focus
- **EOG:** random W/L each week; uniform random outcome band per attribute, then roll inside band
- **Record:** mean wins `12.80 ± 2.88` out of 26

Values below are **mean ± sample stdev** across the 100 runs.

| Attribute | Start | End | Net | Training sum | EOG sum |
|---|---:|---:|---:|---:|---:|
| `shot_threshold` | 104.95 ± 3.21 | 120.80 ± 37.78 | +15.85 ± 37.10 | +15.87 ± 16.37 | -0.02 ± 35.12 |
| `discipline` | 0.04 ± 0.85 | -2.69 ± 6.25 | -2.73 ± 6.37 | +0.70 ± 5.55 | -3.43 ± 5.85 |
| `fight` | -0.03 ± 0.81 | 2.78 ± 6.12 | +2.81 ± 6.12 | +4.07 ± 5.93 | -1.26 ± 6.30 |
| `team_chemistry` | 8.48 ± 1.11 | 17.14 ± 5.81 | +8.66 ± 5.77 | +11.80 ± 3.98 | -3.14 ± 7.37 |
| `offensive_efficiency` | 0.03 ± 0.81 | 0.45 ± 5.10 | +0.42 ± 4.96 | +13.29 ± 2.86 | -12.87 ± 4.06 |
| `defensive_efficiency` | -0.06 ± 0.83 | 0.21 ± 5.11 | +0.27 ± 5.11 | +13.77 ± 3.00 | -13.50 ± 4.43 |
| `fb_efficiency` | 0.15 ± 0.78 | 0.88 ± 5.22 | +0.73 ± 5.11 | +13.17 ± 3.40 | -12.44 ± 4.72 |
| `pt_efficiency` | -0.12 ± 0.82 | 0.06 ± 4.97 | +0.18 ± 5.06 | +13.11 ± 2.60 | -12.93 ± 4.59 |
| `fb_opp_modifier` | 0.09 ± 0.82 | 0.63 ± 4.70 | +0.54 ± 4.60 | +13.57 ± 2.99 | -13.03 ± 4.15 |
| `pt_opp_modifier` | -0.30 ± 0.76 | -0.04 ± 5.28 | +0.26 ± 5.26 | +13.66 ± 3.20 | -13.40 ± 4.42 |
| `rebound_modifier` | 0.200 ± 0.000 | 0.361 ± 0.033 | +0.161 ± 0.033 | +1.021 ± 0.157 | -0.860 ± 0.158 |

Notes:

- Compare to seed blocks 1000–1099 (post Breaks/rebound fix) and 5000–5099 for sampling + latest range effects.

## 100-Season Simulation Snapshot (seed block 8000–8099)

Fifth 100-run batch after standard training bucket `2 → +1…+3` (was `+1…+2`). No EOG formula change.

- **Runs:** 100 seasons × 26 weeks (no byes)
- **Seeds:** 8000–8099
- **Roster source:** `Lancaster Johnnies` (staging franchise `6a4f7d9d49987a7e01e21372`)
- **Start attrs:** random franchise init ranges each run
- **Training:** Auto-Train (week 1 = 30 pts, weeks 2–26 = 24 pts) + random coaching focus
- **EOG:** random W/L each week; uniform random outcome band per attribute, then roll inside band
- **Record:** mean wins `12.97 ± 2.48` out of 26

Values below are **mean ± sample stdev** across the 100 runs.

| Attribute | Start | End | Net | Training sum | EOG sum |
|---|---:|---:|---:|---:|---:|
| `shot_threshold` | 104.65 ± 2.94 | 123.87 ± 37.14 | +19.22 ± 36.69 | +18.79 ± 17.41 | +0.43 ± 31.26 |
| `discipline` | 0.07 ± 0.84 | -1.31 ± 6.17 | -1.38 ± 6.26 | +1.92 ± 5.83 | -3.30 ± 5.53 |
| `fight` | 0.00 ± 0.89 | 3.13 ± 5.43 | +3.13 ± 5.43 | +4.05 ± 4.72 | -0.92 ± 4.97 |
| `team_chemistry` | 8.53 ± 1.08 | 17.86 ± 5.30 | +9.33 ± 5.51 | +11.86 ± 3.50 | -2.53 ± 6.57 |
| `offensive_efficiency` | -0.04 ± 0.82 | 2.82 ± 5.31 | +2.86 ± 5.18 | +16.04 ± 3.29 | -13.18 ± 4.82 |
| `defensive_efficiency` | -0.08 ± 0.77 | 3.72 ± 4.85 | +3.80 ± 4.83 | +16.29 ± 3.44 | -12.49 ± 4.01 |
| `fb_efficiency` | 0.00 ± 0.82 | 2.06 ± 4.87 | +2.06 ± 4.94 | +15.89 ± 3.35 | -13.83 ± 4.53 |
| `pt_efficiency` | 0.09 ± 0.81 | 2.58 ± 4.72 | +2.49 ± 4.57 | +15.94 ± 3.83 | -13.45 ± 4.85 |
| `fb_opp_modifier` | 0.03 ± 0.82 | 3.66 ± 4.41 | +3.63 ± 4.31 | +15.79 ± 3.44 | -12.16 ± 4.69 |
| `pt_opp_modifier` | 0.04 ± 0.85 | 3.39 ± 5.29 | +3.35 ± 5.32 | +17.09 ± 4.00 | -13.74 ± 4.44 |
| `rebound_modifier` | 0.200 ± 0.000 | 0.363 ± 0.033 | +0.163 ± 0.033 | +1.070 ± 0.171 | -0.907 ± 0.171 |

Notes:

- Compare to seed block 7000–7099 for the effect of widening standard training bucket 2.
