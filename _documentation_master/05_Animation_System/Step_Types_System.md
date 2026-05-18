# Step Types System

Quick reference for the universal step types observed across migrated turn types. Each step type is a recurring pattern of player + ball movement that can be composed into any turn.

## Known step types (from CR + RR Fast Breaks)

- **Parallel Movement** — Multiple players move toward their own destinations in parallel; one player's natural traversal sets step T, others clamp to `rate × T`. "Drift" (settle-pace movement toward attacking-basket-relative targets) is just this step type with cruise archetype defaults.
- **Pass** — Ball travels passer → receiver; passer and receiver typically stationary; non-key players may continue prior movement in parallel.
- **Reset** — Ball handler delivers ball to PG and the 8 supporting players reposition to HCO setup spots; bridges a turn-end (FB / HCT / FCP / OREB) into the next HCO turn.
- **Shot Motion** — Shooter sprints to the shot spot with defender contesting; terminates the turn via `turn_stop: SHOT_ATTEMPT`.
- **Intercept** — Defender catches a pass mid-flight; ball bends from passer to contact point to defender; terminates via `turn_stop: STEAL`.
- **Batted Ball** — Defender deflects a pass mid-flight; ball bends from passer to contact point and drifts to the nearest OOB grid; terminates via `turn_stop: DEAD_BALL_TURNOVER`.
- **Stopper** — Anything other than a shot attempt that ends a turn -- dead ball turnover, steal, or foul.
