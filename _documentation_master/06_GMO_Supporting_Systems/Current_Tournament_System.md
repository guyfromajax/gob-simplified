# Current Tournament System

## Purpose

This document captures the current franchise end-of-season tournament architecture and the proposed consolidation plan for tournament progression.

The existing system works, but tournament progression is fragile because completed game state is spread across multiple objects and written by multiple flows. The goal of the next refactor is to make tournament game recording deterministic and centralized.

## Current Franchise EOS Structure

Franchise postseason runs after the 26-week regular season.

- Weeks 27-29: Conference tournaments
- Weeks 30-31: Region tournaments
- Weeks 32-34: National tournament
- Week 35: postseason complete / offseason transition

Tournament state is embedded on the franchise document:

- `conference_tournaments`: 16 conference brackets, 8 teams each
- `region_tournaments`: 8 region brackets, 4 qualifiers each, with possible `R1_0` / `R1_1` placeholders
- `national_tournament`: 1 bracket with 8 region champions

Game/result state also exists outside those bracket blobs:

- `games` collection
- `franchise.results.<week>`
- bracket matchup fields: `game_id`, `winner`, `score`

## Current Risk

The current system has several tournament writers:

- user game completion
- CPU full sim
- distant sim
- phase A
- phase B
- retry/idempotency paths
- heal/sync paths
- sim-rest-of-tournament
- bracket advance paths

This creates multiple possible sources of truth. A tournament game can appear complete in `results.<week>` while the bracket slot remains incomplete, or a bracket slot can update in memory and then be overwritten by a stale merge.

The core invariant should be:

> A tournament game is not complete until `games`, `franchise.results.<week>`, and the tournament bracket slot all agree on the matchup, score, winner, and game id.

## Proposed Architecture

Create one backend module responsible for franchise tournament progression.

Suggested module:

`BackEnd/tournament/franchise_tournament_progression.py`

One public operation should be the main mutation entry point:

```python
record_tournament_game_result(franchise_doc, game_meta, result)
```

All franchise EOS game completion paths should call this operation.

## Public Operation Contract

### `record_tournament_game_result(franchise_doc, game_meta, result)`

Responsibilities:

1. Normalize all team ids to canonical ObjectId strings.
2. Validate that `result` belongs to the bracket slot described by `game_meta`.
3. Save or update the matching `games` document.
4. Save or update the matching `franchise.results.<week>` row.
5. Write `game_id`, `winner`, and `score` to the bracket slot.
6. Resolve dependent bracket structure:
   - conference round advance
   - region `R1_0` / `R1_1` final placeholders
   - national round advance
7. Persist the mutated tournament state in one update boundary.
8. Return derived tournament status for the caller.

The operation should be idempotent. Calling it again with the same matchup/result should not duplicate results, change the winner, or create a different bracket state.

## Inputs

### `game_meta`

The bracket locator. This should come from the current EOS schedule/meta builder.

Expected shape:

```python
{
    "phase": "conference" | "region" | "national",
    "week": int,
    "round": int,
    "matchup_index": int,
    "conference": int | None,
    "region": str | None,
    "away_id": str,
    "home_id": str,
}
```

### `result`

The completed game result.

Expected shape:

```python
{
    "game_id": str | None,
    "away_id": str,
    "home_id": str,
    "away_score": int,
    "home_score": int,
    "source": "user" | "cpu_full" | "distant" | "existing_games" | "existing_results",
}
```

## Output

The function should return a structured status object:

```python
{
    "phase": "conference" | "region" | "national",
    "week": int,
    "game_id": str,
    "winner_id": str,
    "loser_id": str,
    "bracket_slot_recorded": True,
    "results_row_recorded": True,
    "game_doc_recorded": True,
    "round_advanced": bool,
    "phase_completed": bool,
    "champion_id": str | None,
    "user_eliminated": bool | None,
    "user_has_next_game": bool | None,
}
```

## Invariants

After recording a tournament result:

- The bracket slot has a non-empty `winner`.
- The bracket slot has a `score`.
- The bracket slot has a `game_id` when a game document exists or is created.
- The matching `franchise.results.<week>` row exists exactly once.
- The matching `games` document exists when the result needs a box score link or replay reference.
- No region final contains `R1_0` or `R1_1` after the corresponding R1 winner is known.
- A round only advances when all required games in that round have winners.
- Week progression only happens after the current tournament phase reaches a valid boundary.

## Phase-Specific Rules

### Conference Tournaments

Conference tournaments use the shared 8-team bracket engine.

- Round 1: week 27
- Round 2: week 28
- Final: week 29

When all games in a conference round have winners, advance that conference bracket.

When all conference champions are known after week 29, initialize region tournaments.

### Region Tournaments

Region tournaments are custom 4-qualifier brackets.

Qualifiers per region:

- conference champion from the first conference
- regular-season #1 from the first conference
- conference champion from the second conference
- regular-season #1 from the second conference

If a conference champion is also that conference's regular-season #1, that team receives a bye into the region final.

Region finals may initially contain placeholders:

- `R1_0`: winner of `round1[0]`
- `R1_1`: winner of `round1[1]`

The progression module must resolve those placeholders whenever source winners exist.

When all region champions are known after week 31, initialize the national tournament.

### National Tournament

National tournament uses the shared 8-team bracket engine.

- Round 1: week 32
- Round 2: week 33
- Final: week 34

When the national final has a winner:

- set `national_tournament.champion`
- set `eos_tournament_active = False`
- advance franchise to week 35

## Migration Plan

### Step 1: Tests First

Add regression tests for tournament recording invariants.

Minimum cases:

- Conference R1 user win
- Conference R1 user loss
- Conference R2 user win
- Conference R2 user loss
- Conference final user win/loss
- Region R1 user win/loss in `round1[0]`
- Region R1 user win/loss in `round1[1]`
- Region final user win/loss
- National R1/R2/final user win/loss
- CPU result already exists in `results.<week>` but no `games` doc
- CPU result already exists in `games` but bracket slot is empty
- Region final placeholder merge with user and CPU results arriving in separate writes

### Step 2: Introduce the Module

Create `franchise_tournament_progression.py` with the public operation and small private helpers.

Initial helpers:

- `normalize_tournament_team_id`
- `locate_bracket_slot`
- `derive_winner_and_loser`
- `upsert_game_doc`
- `upsert_results_row`
- `write_bracket_slot`
- `resolve_region_placeholders`
- `advance_phase_if_ready`
- `validate_tournament_invariants`

### Step 3: Route User Game Completion First

Update user EOS game completion to call `record_tournament_game_result`.

This replaces direct calls to:

- `save_conference_game_result`
- `save_region_game_result`
- `save_national_game_result`

for user-completed EOS games.

### Step 4: Route CPU/Distant Sim Results

Update CPU full sim and distant sim paths to call the same operation.

The caller should not directly mutate tournament brackets.

### Step 5: Route Existing Result/Game Sync

Replace ad hoc healing paths with calls to the same operation using:

- `source = "existing_games"`
- `source = "existing_results"`

This keeps retries deterministic and prevents bracket/results drift.

### Step 6: Reduce Direct Bracket Mutation

Once all tournament completion paths use the progression module, direct bracket mutation functions should become internal helpers only.

Allowed internal helpers:

- `save_conference_game_result`
- `save_region_game_result`
- `save_national_game_result`
- `advance_conference_bracket`
- `advance_national_bracket`

External franchise routes should not call them directly.

## Testing Philosophy

Tests should focus on invariants, not only win/loss outcomes.

Important assertions:

- user win and user loss both persist the result
- completed games appear in all three places: `games`, `results.<week>`, bracket slot
- no duplicate result rows
- completed rounds advance exactly once
- region placeholders resolve as soon as their source winners exist
- retrying the same result is idempotent
- no tournament phase initializes until the previous phase has all required champions

## Open Design Questions

- Should all tournament game docs require full box score summaries, or is a minimal game doc acceptable for repaired existing-results paths?
- Should `results.<week>` or bracket slots be considered authoritative when they disagree?
- Should week advancement happen inside `record_tournament_game_result` or in a separate `finalize_tournament_week` operation?
- Should CPU same-conference postseason games use full TBT sim or distant sim unless the user is involved?

## Recommended Direction

Use bracket slots as the authoritative tournament progression state.

`results.<week>` and `games` are supporting records, but a postseason round should never advance unless bracket slots are complete and internally valid.

