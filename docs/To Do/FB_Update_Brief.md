We are going to add new plays to the Fast Breaks.

The current logic we use will be referred to as the "Covert Release" fast break play.

**Sustained spec:** `docs/docs_1_systems/05_GP_Supporting_Systems/Fast_Break_System.md` is the canonical “Bible” for Fast Break behavior; this file is short-term working notes for the project.

**Scope:** Play types (e.g. Covert Release) apply only to **DREB → outlet** fast breaks. Fast breaks off **steals** are unchanged and are not assigned a play type.

**Fast Break Plays**
There will be three fast break plays that run after a DREB FB Outlet:
1. Covert Release (currently implemented)
2. Rim Runner (will be implemented in the near future)
3. 32 (will be implemented in the near future)
And we will continue to track stats for FBs after a steal as "After Steal".

**Fast Break Stat Tracking**
- **Implemented (backend):** `scouting_data["offense"]["fast_break_plays"]` with per-play **`A`/`S`** (`covert_release`, `rim_runner`, `thirty_two`, `after_steal`); increments align with **`Fast_Break_Entries`** / **`Fast_Break_Success`**. Turn field **`fast_break_play`**. Player offense: **`FB_A`/`FB_S` only** (`FB_F`/`FB_N` retired). **Box Score scouting lines** = follow-up UI.
- We will continue to track all Fast Break stats for players and teams as we currently are
- **Play-level splits (attempts / successes per play) are offense-only, team / scouting only** — defensive FB scouting stays **team-level only** (no per-play defense splits)
- Field name **`thirty_two`** in code / data; label **"32"** in UI when we build that
- Structure will be to track play-level stats in the scouting notes for each team, and then aggregate those play-level stats up to the team's overall Fast Break stats
- In the Box Score, in the Scouting Notes section, add Fast Breaks after Defensive Plays and structure the data as follows
    "Fast Breaks: {FB_S}/{FB_A} {FB%}"
        "Covert Release: {S}/{A} {%}"
        "Rim Runner: {S}/{A} {%}"
        "32: {S}/{A} {%}"
        "After Steal: {S}/{A} {%}"

**Covert Release Details**

1. Whomever on the defense is **guarding the shooter** cannot be the outlet receiver / release player.
2. From among defenders who are **not** guarding the shooter (same exclusion as §1), identify the defensive player who is **farthest from the basket being shot at** in the x direction (home orientation). That player is the target release player.
    - If the **away** team is shooting (home basket attacked, **home** team on defense): choose the defender with the **highest** x coordinate at the time of the shot.
    - If the **home** team is shooting (away basket attacked, **away** team on defense): choose the defender with the **lowest** x coordinate at the time of the shot.
    - If two players are tied, choose one at random.
3. `the_read = random.randint(1,100)`
    - if `the_read <` release player's IQ, `good_release = True`, else `good_release = False`
4. `d_read = random.randint(1,100)`
    - for each get-back player, if `d_read <` that player's IQ, `good_d_release = True` for that player, else `good_d_release = False` for that player
5. Calculate get-back coords (note these are for home team as outlet receiver; flip for away team as outlet receiver)
    - for release player
        - if AG >= 80: x_min = 50
        - elif AG >= 60, x_min = 47
        - else, x_min = 45
    - for each get back player
        - if AG >= 80: def_x_min = 55
        - elif AG >= 60, def_x_min = 53
        - else, def_x_min = 50
    - if `good_release`, x range = x_min – 55, y range = 18–32, else x range = (x_min -5) – 50, y range = 22–30
    - if `good_d_release`, x range = def_x_min - 60, y range = 22–30, else x range = (def_x_min - 5) – 60, y range = 18–32

6. Check for possibility of a defensive stop
    - A defender can attempt a stop if his x coordinate is equal to the outlet receiver's or closer to the basket (i.e. if home team is on offense for the fast break, his x must be `>=` the ball handler's; if away team is on offense for the fast break, his x must be `<=` the ball handler's), **and** the defender is within **±8** y coordinates of the ball handler.
    - Use the current calculation of `break_score` vs `stop_score` to determine the outcome of the FB stop attempt.
7. Proceed with our current logic for both defensive stops and FB shot attempts.



