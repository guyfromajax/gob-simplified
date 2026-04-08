# Training Notes System

Training Notes appear in the Training Report after each week’s training run.

## Relevance to Play Identity Migration

Most Training Notes rules did not change.

One important clarification:
- notes that reference offensive plays should still display the play `name`
- any underlying matching or ranking logic can use `play_id`, but the note text shown to the user should remain display-name based

## Current Rule

Training Notes remain a reporting/output layer, not a persistence identity layer.

So:
- `play_id` is appropriate for backend matching
- `name` remains the user-facing string in the note body

## No Additional System Change

The recent `play_id` and `target_shooter` migration did not otherwise change:
- section ordering
- section thresholds
- note generation categories
- empty-state behavior
