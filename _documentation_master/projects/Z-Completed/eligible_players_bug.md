# Eligible Players / Lineup Exhaustion Bug

## Status

Addressed for CPU-only full simulations and computer-controlled teams in
interactive user games. Interactive user-team handling remains open and
requires a separate UI/UX decision.

## Sentry Event

- Issue ID: `7468124957`
- Date: June 9, 2026
- Environment: Production
- Transaction: `/franchise/complete-week/start-cpu-sims`
- Affected team: Appalachia
- Game state: Fourth quarter, 46 seconds remaining
- Score when the simulation failed: Lancaster 117, Appalachia 67

## Error

```text
ValueError: Team 'Appalachia' lineup missing positions ['SF']:
Only 0 eligible players available (need 1, 8 fouled out)
even after relaxing NG and foul limits
```

## What Happened

Appalachia had only four eligible players remaining after another player received
his fifth foul. Eight players had already fouled out, and the newly disqualified
player left the `SF` lineup position empty.

The lineup repair process correctly:

1. Removed the newly fouled-out player.
2. Excluded the four players already assigned to other lineup positions.
3. Relaxed energy and non-disqualifying foul restrictions.
4. Continued to exclude every player with five or more fouls.

No eligible fifth player remained, so `_ensure_complete_lineup()` raised a
`ValueError`.

## Code Path

```text
complete-week CPU simulation
  -> _run_franchise_cpu_full_simulation_core()
  -> run_simulation()
  -> simulate_quarter()
  -> GameManager.simulate_macro_turn()
  -> TurnManager.run_micro_turn()
  -> resolve_half_court_offense_logic()
  -> ShotManager.resolve_shot()
  -> check_and_handle_foul_out()
  -> _ensure_complete_lineup()
```

Relevant files:

- `BackEnd/main.py`: `_ensure_complete_lineup()`
- `BackEnd/engine/phase_resolution.py`: `check_and_handle_foul_out()`
- `BackEnd/utils/db_utils.py`: lineup eligibility and waterfall rules
- `BackEnd/api/franchise_routes.py`: CPU full-simulation error fallback

## Previous Recovery Behavior

The exception does not stop Week completion. The parallel CPU simulation
pipeline catches it and generates random scores between 50 and 90 for both
teams. It then records that fallback result and synchronizes any tournament
bracket state.

For this event, that means the in-progress 117-67 game was discarded and
replaced by a random result.

## Impact

- The user can continue the franchise.
- The affected CPU game receives an artificial final score and potentially a
  different winner.
- Full box-score statistics from the failed simulation are lost.
- Standings or tournament advancement can be changed by the random fallback.
- The same lineup-exhaustion condition may also be possible during a user game,
  where there is no defined gameplay rule for continuing with fewer than five
  eligible players.

## Why This Is Not Just Sentry Noise

The exception is handled operationally, but it exposes a missing basketball
rule in the simulation engine. Suppressing the error would hide corrupted game
results rather than resolve the underlying condition.

## Implemented Computer-Team Rule

Emergency re-entry is enabled for:

- CPU-only full games run through `run_simulation()`
- the computer-controlled opponent during an interactive user game

When normal lineup repair cannot produce five players:

1. The engine completes the full NG and non-disqualifying foul-limit waterfall.
2. It preserves all remaining normally eligible players.
3. It calculates the exact number of additional players required.
4. It randomly selects that number from the team's fouled-out players.
5. Those selected players re-enter only to complete the five-player lineup.

This prevents CPU-only games from being discarded and replaced with random
fallback scores solely because fewer than five non-fouled-out players remain.
It also allows an interactive user game to continue when the computer opponent
exhausts its eligible roster.

## Implemented User-Team Experience

When the user's team reaches eight or more fouled-out players and therefore has
four or fewer players below five fouls:

1. The foul-out transition is allowed to reach the set-lineup screen even
   though the user's lineup is temporarily incomplete.
2. Every player with fewer than five fouls is included in the active lineup.
3. The remaining slots are filled by randomly selected fouled-out players.
4. The five selected players are assigned to the five positions and the lineup
   is locked.
5. The set-lineup screen displays:
   `You have 8 or more players fouled out. A legal lineup will be randomly set for you.`
6. The modal CTA is `Got It`.
7. Roster selection, dragging, removing players, autoset, roster view toggles,
   and other lineup-changing activity are disabled.
8. `Game Plan`, `Playbooks`, and `Return to Game` remain active.
9. The backend validates that the lineup has five distinct roster players and
   includes every player with fewer than five fouls.
10. A reinstated fouled-out player remains in the locked lineup after any
    additional foul and does not trigger another foul-out substitution.

The locked state is preserved through Game Plan navigation and is sent to the
gameplay backend when the user returns to the court.

## Implementation Warning

Do not fix this by silently treating a player with five fouls as normally
eligible. Foul-out eligibility is enforced consistently through
`is_player_eligible_for_lineup()`, `_get_eligible_players()`, and
`_ensure_complete_lineup()`. Any exception to that rule needs to be explicit
and supported throughout the simulation and presentation layers.
