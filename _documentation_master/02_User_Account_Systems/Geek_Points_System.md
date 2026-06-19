# Geek Points System

Geek points are stored on each user document in the `users` collection and power the alpha leaderboard and other community-facing score displays.

## User document fields

- **`geek_points`** (integer): Total points; kept in sync with per-team awards by applying the **same** `$inc` delta to the total and to the team bucket in one update.
- **`geek_points_by_team`** (object, optional): Map of canonical team id (`teams.team_id`, e.g. `LANCASTER`) → integer points earned while playing as that franchise team. **Lazy:** the object and each key are created on first `$inc` for that team. Omitted until the user earns points at least once; new teams/conferences only add new keys when the user wins with that team.

If the team document cannot be resolved for a rare edge case, the code may increment only `geek_points` and log a warning (per-team bucket skipped).

## Franchise mode wins and losses

When the **user’s franchise team** wins or loses a game, the owning account receives a random geek-point award in the ranges below. Loss points only apply when the user's team participated in the game; simmed games between two other teams do not award loss points.

Gameplay-mode policy:

- Regular-season games use explicit bulk-sim vs non-bulk ranges.
- EOS tournament games use a base range, then apply the EOS gameplay-mode multiplier: bulk-sim games receive the base value; non-bulk games receive `2 * base`.
- The same final delta is applied to both `geek_points` and `geek_points_by_team.<team_id>`.

The durable source for this decision is `games.bulk_sim_used`.

Awards are applied server-side when results are committed (notably via `POST /franchise/complete-week`, and EOS helpers that record matchup results and `POST /franchise/sim-championship`).

Implementation: `BackEnd/utils/franchise_geek_points.py` (`maybe_award_franchise_win_geek_points`, `maybe_award_franchise_loss_geek_points`).

### Regular season (weeks 1–26)

| Event | Geek points |
|--------|-------------|
| Win, bulk-sim game | `random.randint(5, 12)` |
| Win, non-bulk game | `random.randint(13, 20)` |
| Loss, bulk-sim game | `random.randint(1, 2)` |
| Loss, non-bulk game | `random.randint(3, 4)` |

### End-of-season tournaments (weeks 27–34)

Tournament phase and round come from the franchise EOS bracket metadata (`BackEnd/tournament/franchise_tournament.py`).

| Event | Geek points |
|--------|-------------|
| Conference tournament, rounds 1–2 | Base: `random.randint(15, 20)` |
| Conference championship (round 3) | Base: `random.randint(25, 35)` |
| Region tournament (semifinal or final week) | Base: `random.randint(40, 50)` |
| National tournament, rounds 1–2 | Base: `random.randint(50, 75)` |
| National championship (round 3) | Base: `random.randint(125, 175)` |
| Loss (any week / phase, user played) | Base: `random.randint(1, 2)` |

For EOS games, apply the same gameplay-mode multiplier to the base value: bulk-sim games receive the base value; non-bulk games receive `2 * base`.

### Notes

- Only the **franchise owner** (`franchise_doc.user_id` → `users._id`) is credited; guest or unauthenticated flows without a stored owner do not receive points.
- Wins are detected by matching the game winner to the user’s team (`user_team_object_id` on the franchise document), including when team identifiers are stored as ObjectId strings or canonical `team_id` strings.
- Regular-season losses award `1–2` geek points for bulk-sim games and `3–4` geek points for non-bulk games when the user’s team was a participant and did not win. EOS losses use the EOS base-plus-multiplier policy above. Ties are handled by whichever team is recorded as the winner in the commit path.
- `games.bulk_sim_used` is set by `/api/simulate-quarter` when the user advances via Sim Full Game or Sim Rest of Game. It is sticky once true.

## API

- **`GET /api/auth/leaderboard`** — Overall alpha leaderboard (`geek_points`).
- **`GET /api/leaderboard/by-team`** (auth required) — Top 3 users per A1 team by `geek_points_by_team` canonical keys (`BENTLEY_TRUMAN`, `LANCASTER`, …). Response keys match mode select slugs (`bentley_truman`, `lancaster`, …). Also supports `?view=rank` (top users per team by active-franchise national rank instead of geek points).
