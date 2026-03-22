We are going to add new plays to the Fast Breaks.

The current logic we use will be referred to as the "Covert Release" fast break play.

**Scope:** Play types (e.g. Covert Release) apply only to **DREB → outlet** fast breaks. Fast breaks off **steals** are unchanged and are not assigned a play type.

I'd like to execute with the following logic, but you tell me if this is feasible given our current codebase.

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
    - if `good_release`, x range = 45–55, y range = 18–32, else x range = 40–50, y range = 22–30
    - if `good_d_release`, x range = 53–60, y range = 22–30, else x range = 45–60, y range = 18–32

6. Check for possibility of a defensive stop
    - A defender can attempt a stop if his x coordinate is equal to the outlet receiver's or closer to the basket (i.e. if home team is on offense for the fast break, his x must be `>=` the ball handler's; if away team is on offense for the fast break, his x must be `<=` the ball handler's), **and** the defender is within **±8** y coordinates of the ball handler.
    - Use the current calculation of `break_score` vs `stop_score` to determine the outcome of the FB stop attempt.
7. Proceed with our current logic for both defensive stops and FB shot attempts.
