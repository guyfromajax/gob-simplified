
# New Team & Player Creation

**Creating New Teams**  
- Jamie provides the following:
    - name, team_id, primary_color, secondary_color
(See `docs/docs_1_systems/00_Data_Systems/Database_System.md` for team doc fields: name, team_id, primary_color, secondary_color, player_ids, optional mascot.)

**Creating New Players**
- Jamie provides the following:
    - first_name, last_name, team
    - attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT); anchor values set equal to these. EM, MO, CH initialized at 0 (game/mode init overwrites CH and EM 1–100, MO stays 0).
    - jersey, year, height, weight
    - headshot: until specified otherwise, all new players use **`/static/images/players/generic_headshot.png`** (set `photo` to that path).