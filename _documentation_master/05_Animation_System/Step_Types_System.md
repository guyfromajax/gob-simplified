# Step Types System

Quick reference for the universal step types observed across migrated turn types. Each step type is a recurring pattern of player + ball movement that can be composed into any turn.

## Known step types (from CR + RR Fast Breaks)

- **Parallel Movement** — Multiple players move toward their own destinations in parallel; one player's natural traversal sets step T, others clamp to `rate × T`. "Drift" (settle-pace movement toward attacking-basket-relative targets) is just this step type with cruise archetype defaults.
- **Pass** — Ball travels passer → receiver; passer and receiver typically stationary; non-key players may continue prior movement in parallel.
- **Reset** — Ball handler delivers ball to PG and the 8 supporting players reposition to HCO setup spots; bridges a turn-end (FB / HCT / FCP / OREB) into the next HCO turn.
    -Note 1-- we must avoid an over & back violation in this logic -- if home offense and ball handler x spot >= 50, PG cannot move to an x spot < 50 to receive teh pass. if away offense and ball handler x spot <= 50, PG cannot move to an x spot > 50 to recieve the pass. If PG will be in violation per movmeent, clamp his x to 50.
    -Note 2: lane spots = random choice of basketSpot, lower lowPost, upper lowPost, lower midPost, upper midPost, midLane, upper highPost, lower highPost, topLane
    -Ball Handler holds his position
    -Offense PG
        -if not the ball handler, moves to a position within 10 euclidian spots of the ball handler, without causing an over & back violation. Sprint speed
        -if ball hander is PG, he holds his position for two game seconds
    -All other 8 or 9 players move toward a random spot inside the offense basket lane at cruise speed
    -Instances Used: following each fo the following steps:
        -CR FB: Defsenive Stop
        -RR FB: Hold Up
        -DREB before transition to HCO
        -Steal that does not lead to Fast Break
- **Shot Motion** — Shooter sprints to the shot spot with defender contesting; terminates the turn via `turn_stop: SHOT_ATTEMPT`.
- **Intercept** — Defender catches a pass mid-flight; ball bends from passer to contact point to defender; terminates via `turn_stop: STEAL`.
- **Batted Ball** — Defender deflects a pass mid-flight; ball bends from passer to contact point and drifts to the nearest OOB grid; terminates via `turn_stop: DEAD_BALL_TURNOVER`.
- **Stopper** — Anything other than a shot attempt that ends a turn -- dead ball turnover, steal, or foul.
