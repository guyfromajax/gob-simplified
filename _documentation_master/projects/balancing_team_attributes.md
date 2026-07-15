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
| 1 | `0` to `+2` |
| 2 | `+1` to `+2` |
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
- If team fouls + turnovers are above that buffered opponent total: `-3` to `-2`.
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

- Win: `0` to `+1`.
- Loss: `-1` to `0`.

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

Authoritarian Rebounding can amplify positive gains.

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
