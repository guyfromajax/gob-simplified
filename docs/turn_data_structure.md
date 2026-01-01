# Turn Data Structure

This document summarises the payload our backend returns for each **micro-turn**
(the smallest unit of game simulation) and how the frontend consumes it.

The data is produced inside `BackEnd/models/turn_manager.py::run_micro_turn`.
Additional helpers (animator, fast break logic, free-throw resolution) augment
the result before it is serialised to JSON and sent to the client.

## High-Level Shape

```json5
{
  "turn_count": 42,
  "result_type": "MAKE" | "DREB" | "OREB" | "TURNOVER" | "FOUL" | "FREE_THROW" | "HCO" | "FAST_BREAK",
  "time_elapsed": 1280,
  "offense_team_id": "TEAM_UUID",
  "current_turn": "HCO" | "FCP" | "HCT" | "FAST_BREAK" | "FREE_THROW" | "OREB" | "BASELINE_INBOUND" | "SIDE_INBOUND" | "OPENING_TIP" | "TIMEOUT",
  "next_turn": "HCO" | "FCP" | "HCT" | "FAST_BREAK" | "FREE_THROW" | "BASELINE_INBOUND" | "SIDE_INBOUND",
  "possession_flips": true,
  "score": { "Home": 44, "Away": 40 },

  // Participant metadata (strings; player objects are normalised away)
  "shooter_id": "PLAYER_UUID",
  "shooter": "Player Name",
  "ball_handler": "Player Name",
  "passer": "Player Name",
  "stealer_id": "PLAYER_UUID",
  "victim_id": "PLAYER_UUID",

  // Animation + role context
  "animations": [...],
  "events": [...],
  "roles": {...},
  "next_play_type": "HCO" | "FAST_BREAK" | "FREE_THROW" | null,

  // Free throw details (optional)
  "attempts": ["MAKE", "MISS"],
  "ftContext": { "ftIndex": 1, "ftTotal": 2, "bonusType": "REGULAR" },

  // Rebound information (optional)
  "rebound_type": "DREB" | "OREB" | null,
  "rebounder_id": "PLAYER_UUID" | null,

  // Scoreboard snapshots
  "home_lineup": { "PG": {...}, ... },
  "away_lineup": { "PG": {...}, ... },
  "deltas": {
    "PLAYER_UUID": {
      "team": "Home",
      "stats": { "PTS": 2, "REB": 1 }
    }
  },
  "homeFouls": 4,
  "awayFouls": 3,
  "clock": "3:12",
  "quarter": 2,
  "period_label": "Q2",

  // Narrative & flags
  "text": "Player drills the mid-range jumper.",
  "fast_break": false,
  "hold_up": false,
  "stopper_id": "PLAYER_UUID",
  "is_three_pointer": false,
  "is_and_one": false,
  "putback_attempt": false
}
```

All player references are serialised to ids/names via `convert_players` before
the turn leaves the backend. The frontend should not expect live class
instances.

## Core Fields

| Field | Type | Notes |
| ----- | ---- | ----- |
| `turn_count` | int | Sequential counter for micro-turns. |
| `result_type` | string | Primary routing key (MAKE/DREB/OREB/TURNOVER/FOUL/FREE_THROW/HCO/FAST_BREAK). |
| `time_elapsed` | int | Milliseconds deducted from the game clock. |
| `offense_team_id` | string | **SS&S Standard:** Team on offense during this turn (authoritative). Replaces deprecated `possession_team_id`. **Note:** `possession_team_id` may still be present in some turn types for backward compatibility, but `offense_team_id` should always be used as the authoritative source. |
| `current_turn` | string | Explicit turn type identifier (HCO/FCP/HCT/FAST_BREAK/FREE_THROW/OREB/BASELINE_INBOUND/SIDE_INBOUND/OPENING_TIP/TIMEOUT). Used for routing and debugging. |
| `next_turn` | string | Explicit next turn type (set by `game_manager.determine_next_turn()`). Used for transition logic. |
| `possession_flips` | bool | If true, backend flips possession immediately after the turn. |
| `score` | object | Authoritative team scores after the turn. Always use this rather than re-adding `points`. |
| `text` | string | Guaranteed non-empty narrative for the play-by-play ticker. |

## Participant Metadata (optional)

Depending on the play type, one or more of the following string fields may be
present: `shooter_id`, `shooter`, `ball_handler`, `passer`, `screener`,
`defender`, `stealer_id`, `victim_id`, `stopper_id`. These are already coerced
into simple strings.

## Animation & Roles

- **`animations`** – Array of per-player movement tracks (positions, actions,
  `hasBallAtStep`) used by both the legacy animator and the new
  `PossessionRunner`.
- **`events`** – Optional array of high-level events (`PUTBACK_ATTEMPT`,
  `KICKOUT_RESET`, `STEAL`, etc.) the frontend uses to trigger specialised
  flows.
- **`roles`** – Optional map describing offensive/defensive roles for the turn
  (ball handler, rebounder, outlet receiver, etc.).
- **`next_play_type`** – Hint about what the backend expects next (`HCO`,
  `FAST_BREAK`, `FREE_THROW`), useful when staging transitions. (Note: `next_turn` is the authoritative value set by `game_manager.determine_next_turn()`)

## Free Throw Metadata

- **`attempts`** – Ordered results of each free throw (`MAKE` or `MISS`).
- **`free_throws_remaining`** – Number of free throws remaining after this turn (turn-by-turn mode). If undefined, fall back to `ftContext`.
- **`ftContext`** – Added by `animateGameTurns.annotateFreeThrowTurns` to expose
  attempt index/total and bonus type for UI copy (batch mode fallback).

## Rebounds

- **`rebound_type`** – `DREB` or `OREB` for missed shots/free throws.
- **`rebounder_id`** – Player securing the rebound.

When an offensive rebound occurs, the backend now emits *two* turns:

1. `result_type = "OREB"` describing the rebound itself.
2. A follow-up turn (putback attempt, kick-out reset, etc.) where normal shot or
   HCO logic applies.

## Scoreboard Snapshots & Deltas

- **`home_lineup` / `away_lineup`** – Serialised lineup info (position → player
  metadata) used by overlays and debugging.
- **`deltas`** – Per-player stat increments accumulated during the turn (scoring,
  rebounds, steals, etc.).
- **`homeFouls` / `awayFouls`** – Team foul totals this quarter.
- **`clock`**, **`quarter`**, **`period_label`** – Human-readable game-clock
  state after the turn.

## Team Data

- **`team_stats`** – Current team stats from scouting_data (offense/defense effectiveness).
  Structure: `{"Team Name": {"offense": {...}, "defense": {...}}}`
- **`team_totals`** – Cumulative team game stats (aggregated from all players).
  Structure: `{"Team Name": {/* team game stats */}}`
- **`team_plays`** – Play data for tooltips (effectiveness and tracking).
  Structure: `{"Team Name": [/* array of play objects */]}`

## Player State

- **`player_energy`** – Energy levels (NG attribute) for all active players (fatigue display).
  Structure: `{"PLAYER_UUID": {"NG": 1.0, "team": "Team Name"}}`

## Strategy Calls

- **`offense_tempo_call`** – Actual tempo call made by offense team (for strategy bars).
- **`offense_aggression_call`** – Actual aggression call made by offense team (for strategy bars).
- **`defense_tempo_call`** – Actual tempo call made by defense team (for strategy bars).
- **`defense_aggression_call`** – Actual aggression call made by defense team (for strategy bars).

## Flags & Routing Helpers

- **`fast_break`** – Set when the backend is resolving a transition play. Paired
  with `hold_up` and `stopper_id` for defensive stops.
- **`is_three_pointer`**, **`is_and_one`**, **`putback_attempt`** – Shot context
  used for commentary and animation choices.

## Sample Payloads

### Made Shot
```python
{
    "turn_count": 47,
    "result_type": "MAKE",
    "shooter_id": "player-123",
    "shooter": "John Smith",
    "time_elapsed": 1820,
    "offense_team_id": "TEAM_HOME",
    "current_turn": "HCO",
    "next_turn": "BASELINE_INBOUND",
    "possession_flips": true,
    "score": {"Home": 44, "Away": 40},
    "is_three_pointer": false,
    "fast_break": false,
    "animations": [...],
    "events": [],
    "deltas": {"player-123": {"team": "Home", "stats": {"PTS": 2}}},
    "homeFouls": 4,
    "awayFouls": 3,
    "clock": "3:12",
    "quarter": 2,
    "text": "John Smith sinks the jumper from mid-range."
}
```

### Defensive Rebound Launching a Fast Break
```python
{
    "turn_count": 48,
    "result_type": "DREB",
    "shooter_id": "player-321",
    "time_elapsed": 860,
    "offense_team_id": "TEAM_AWAY",
    "current_turn": "HCO",
    "next_turn": "FAST_BREAK",
    "possession_flips": true,
    "score": {"Home": 44, "Away": 40},
    "rebound_type": "DREB",
    "rebounder_id": "player-456",
    "fast_break": true,
    "next_play_type": "FAST_BREAK",
    "animations": [...],
    "events": [
        {"event_type": "FAST_BREAK_START", "rebounderId": "player-456"}
    ],
    "text": "Doe pulls down the board and immediately looks to run."
}
```

### Free Throw (Missed – Defensive Rebound)
```python
{
    "turn_count": 52,
    "result_type": "FREE_THROW",
    "shooter_id": "player-123",
    "time_elapsed": 0,
    "offense_team_id": "TEAM_HOME",
    "current_turn": "FREE_THROW",
    "next_turn": "HCO",
    "possession_flips": true,
    "score": {"Home": 45, "Away": 40},
    "attempts": ["MISS"],
    "free_throws_remaining": 0,  # Turn-by-turn mode: 0 means this was the final FT
    "ftContext": {"ftIndex": 1, "ftTotal": 2, "bonusType": "REGULAR"},  # Batch mode fallback
    "rebound_type": "DREB",
    "rebounder_id": "player-789",
    "next_play_type": "HCO",
    "animations": [...],
    "events": [],
    "text": "Smith misses the first, but the defense controls the glass."
}
```

## Design Notes

- **Authoritative scoring** – `turn.score` always reflects the official game
  score. Even if a turn includes a `points` field (legacy helpers occasionally
  add it), treat it as informational only.
- **No generic "MISS"** – Missed shots resolve to either `DREB` or `OREB`. Use
  `rebound_type` to differentiate defensive/offensive rebounds.
- **SS&S Possession System** – Use `offense_team_id` (not deprecated `possession_team_id`) as the authoritative team on offense. Backend flips possession based on `possession_flips` flag. **Note:** `possession_team_id` may still be included in some turn types for backward compatibility (e.g., inbound passes), but `offense_team_id` is always the authoritative source and should be used by all new code.
- **Turn Type Identification** – Use `current_turn` to identify turn type and `next_turn` for transition logic (both set by backend).
- **Free Throw Modes** – Backend supports both turn-by-turn mode (`free_throws_remaining`) and batch mode (`ftContext`). Frontend should prefer `free_throws_remaining` if available.
- **Frontend annotations** – The frontend may append helper context (currently
  `ftContext`). Do not mutate core fields that the backend controls.
- **Telemetry** – With `window.DEBUG_ANIM = true` the Possession Runner emits
  `possessionRunner:*` events to help reason about timeline stalls and FSM
  transitions.
- **Debug Fields** – `debug_turn_start` and `debug_turn_result` are optional debug-only fields (only present if backend DEBUG flag is enabled).

Keep this document in sync whenever backend fields change so frontend and
instrumentation work remain aligned.
