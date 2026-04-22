# Team Attributes: End of Game vs Training Comparison

Quick current-code comparison of how franchise-mode team attributes move in:

- **End of Game (EOG)**: [End_Of_Game_System.md](/Users/jamesdavies/gob-simplified/docs/docs_1_systems/05_GP_Supporting_Systems/End_Of_Game_System.md:1)
- **Training**: [Training_System.md](/Users/jamesdavies/gob-simplified/docs/docs_1_systems/06_GMO_Supporting_Systems/Training_System.md:1)

`momentum_score` is omitted because current franchise training and EOG do not update it.

## Current Summary

| Attribute | End of Game (EOG) | Training |
|-----------|-------------------|----------|
| `shot_threshold` | FG%-driven. Lower is better. Winners: `-10 to -5`, `-5 to +5`, or `+5 to +15`. Losers: `0 to +5`, `+5 to +10`, or `+10 to +25`. | Scrimmages only: `0 -> +10 to +20`, `1 -> -5 to +5`, `2 -> -5 to -15`, `3 -> -5 to -25`, `4 -> -10 to -25`, `5 -> -10 to -30`. |
| `rebound_modifier` | TREB vs opponent TREB: `> opp + 8 -> +0.00 to +0.05`; `< opp - 8 -> -0.20 to -0.10`; otherwise `-0.10 to -0.05`. | Rebounding drill: `1-2 -> +0.00 to +0.03`, `3-4 -> +0.03 to +0.07`, `5 -> +0.04 to +0.10`. Scrimmages: `1-2 -> -0.03 to +0.03`, `3-4 -> +0.02 to +0.05`, `5 -> +0.03 to +0.07`. |
| `offensive_efficiency` | Usage-based sink from completed-game offensive play count: `>12 -> -2 to -1`, `8-12 -> -3 to -2`, `<8 -> -4 to -3`. | Offense Install: `0 -> -2 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`. |
| `defensive_efficiency` | Usage-based sink from completed-game defensive play concentration: `>49% one play -> -4 to -3`, `>39% -> -3 to -2`, else `-2 to -1`. | Defense Install uses the same standard install range as offense. |
| `fb_efficiency` | Usage-based sink from completed-game fast-break play concentration: `>60% one play -> -4 to -3`, `>50% -> -3 to -2`, else `-2 to -1`. Distant sim override: `-2 to +1`. | Fast Break Offense Install uses the standard install range. |
| `pt_efficiency` | Usage-based sink from completed-game HCT+FCP volume: `>20 -> -4 to -3`, `>15 -> -3 to -2`, else `-2 to -1`. Distant sim override: `-2 to +1`. | P/T Defense Install uses the standard install range. |
| `fight` | Win/loss only: win `0 to +1`, loss `-3 to -1`. | Strength + Conditioning contributions use `0 -> -3 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +2 to +5`, `4 -> +2 to +6`, `5 -> +2 to +7`. Breaks can subtract at `4-5`. Any Culture Builder archetype also adds flat `0 to +1`. |
| `discipline` | Compare team `(F + TO)` to opponent `(F + TO) + 8`: lower `0 to +1`, equal `-1 to 0`, higher `-3 to -2`. | Inside Defense + Outside Defense + Passing + Ball Handling contributions use the same `fight/discipline` training range. Breaks can subtract at `4-5`. Any Authoritarian archetype also adds flat `0 to +1`. |
| `team_chemistry` | Score delta and win/loss: wins `+1 to +2`, `+1 to +3`, `+2 to +4`; losses `-2 to -1`, `-4 to -2`, `-6 to -4`. | Free Throws + Film Study + Scrimmages contributions use `0 -> -3 to -1`, `1 -> +1 to +2`, `2 -> +2 to +3`, `3 -> +3 to +4`, `4 -> +3 to +6`, `5 -> +3 to +7`. Breaks add direct variance at `3-5`. Team Building adds flat `+1 to +3`. Inspire amplifies positive chemistry gains. |
| `fb_opp_modifier` | Opponent fast-break volume: `>20 -> -4 to -3`, `>10 -> -3 to -2`, else `-2 to -1`. Distant sim override: `-2 to +1`. | Fast Break Defense Install uses the standard install range. |
| `pt_opp_modifier` | Opponent press/trap volume: `>20 -> -4 to -3`, `>10 -> -3 to -2`, else `-2 to -1`. Distant sim override: `-2 to +1`. | P/T Offense Install uses the standard install range. |

## Notes

- EOG now leans heavily on the same finished-game snapshot the box score uses: team totals, play usage, special situations, and scouting usage counts.
- Training now has three team-attribute range families:
  - standard install attrs
  - `fight` / `discipline`
  - `team_chemistry`
- `breaks` directly changes `team_chemistry` at `3-5`, and `discipline` / `fight` at `4-5`.
