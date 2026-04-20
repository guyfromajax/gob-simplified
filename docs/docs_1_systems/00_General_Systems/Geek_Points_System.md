# Geek Points System

Geek points (`geek_points`) are stored on each user document in the `users` collection. They power the alpha leaderboard and other community-facing score displays.

## Franchise mode wins

When the **user’s franchise team** wins a game, the owning account receives a random geek-point award. Awards are applied server-side when results are committed (notably via `POST /franchise/complete-week`, and EOS helpers `POST /franchise/sim-rest-of-tournament` and `POST /franchise/sim-championship` when those paths produce a win for the user’s team).

Implementation: `BackEnd/utils/franchise_geek_points.py` (increment with MongoDB `$inc` on `geek_points`).

### Regular season (weeks 1–26)

| Event | Geek points |
|--------|-------------|
| Win | `random.randint(5, 15)` |

### End-of-season tournaments (weeks 27–34)

Tournament phase and round come from the franchise EOS bracket metadata (`BackEnd/tournament/franchise_tournament.py`).

| Event | Geek points |
|--------|-------------|
| Conference tournament, rounds 1–2 | `random.randint(15, 20)` |
| Conference championship (round 3) | `random.randint(25, 35)` |
| Region tournament (semifinal or final week) | `random.randint(40, 50)` |
| National tournament, rounds 1–2 | `random.randint(50, 75)` |
| National championship (round 3) | `random.randint(125, 175)` |

### Notes

- Only the **franchise owner** (`franchise_doc.user_id` → `users._id`) is credited; guest or unauthenticated flows without a stored owner do not receive points.
- Wins are detected by matching the game winner to the user’s team (`user_team_object_id` on the franchise document), including when team identifiers are stored as ObjectId strings or canonical `team_id` strings.
- Losses and ties do not change geek points.
