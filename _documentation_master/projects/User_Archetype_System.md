## Implementation status (2026-06)

Tracking plumbing **built & verified end-to-end on gob-staging** (Sim Full Game; archetypes + W/L land on the user record). Franchise-only (tournament sunset).

| Piece | Where | Status |
|---|---|---|
| Schema (single source) | `BackEnd/utils/user_tracking.py` | ✅ |
| Backfill | `scripts/add_user_tracking_fields.py` | ✅ staging · ⏳ prod deferred |
| Signup defaults | `BackEnd/api/auth_routes.py` | ✅ |
| Classifier | `BackEnd/utils/coaching_archetype.py` | ✅ + tests |
| Per-period stash | `archetype_tracking.py` → `/api/simulate-quarter` | ✅ + tests |
| Commit (W/L + archetypes) | `user_game_commit.py` → `finalize_game` | ✅ + tests |
| Surface on `/api/auth/me` | `BackEnd/api/auth_routes.py` | ✅ |
| `lead_archetype` + `archetype_reveal_seen` (schema/commit/me/PATCH/leaderboard APIs/backfill) | `user_tracking.compute_lead_archetype`, `user_game_commit.py`, `auth_routes.py`, `leaderboard_routes.py` | ✅ + tests |
| Shared badge component | `js/shared/archetypeBadge.js` (`createBadge`/`badgeHtml`/`leadFrom`) | ✅ |
| Badge beside username | account modal (`authBarInit.js`) + leaderboards (`mode-select.js`: geek/rank/by-team) | ✅ |
| Explainer page | `coaching-archetypes.html` (manifest-driven; 4 sections by `group`) | ✅ |
| First-archetype reveal (Moment modal) | `js/shared/archetypeReveal.js` on FCC | ✅ |
| Manifest fields added | `archetypes.json`: `sections`, `group`, `description:"TBD"`, `reveal_name` | ✅ |

**UI decisions:** account page deferred (none exists) → explainer link lives in the Account Settings modal; reveal fires on Franchise Command Center; existing coaches backfilled `archetype_reveal_seen=true` (no retroactive popup). Badge reads `lead_archetype` with client fallback to highest archetype count.

Rules locked in: every period counts (Q1–Q4 + OT, simmed or played); deduped on `(game_id, quarter)` so refreshes/timeouts/foul-outs don't recount; committed once at game completion (abandoned games count 0); `win_rate = round(100*wins/total_games)`.

**Persistence note (load-bearing — don't remove without reading [`simulate_quarter_api_cleanup.md`](simulate_quarter_api_cleanup.md) §5):** the stash's own `$set` of `archetype_periods` does NOT survive to `finalize` in the franchise save flow. So persistence relies on (1) the **api.py call-site** writing `archetype_periods` from the returned `dbg.result`, and (2) a `finalize` **fallback** reading results from the durable `game.archetype_hook.<q>.dbg.result`. Root cause unexplained — open investigation.

**Deferred (not bugs):** (1) **prod backfill** — run `--apply --db production --confirm-production-write` after code ships; (2) **`discount_wins`/`discount_losses`** — fields exist, tracking unwired (future hook reads `game.bulk_sim_used`). Still TODO: manual franchise playthrough on staging to confirm the live stash.

##Modal Display
- username
- Scouting Ambience toggle
- button / link to full account page

##Full Account Page
- username
- Scouting Ambience toggle
- Position / Jersey toggle
- Geek Points
    - Total
    - By Team (8 potential)
- Records (Wins - Losses   Win%)
-Coaching Archetype Percentages


 ##Coaching Archetype System
 - Each time the user enters the court.html screen from the set-lineup screen during gameplay, anlyze their five active players and choose one Coaching Archetype that qualifies.
 - If more than one archetypes qualify, choose one of the qualifying archetypes at random. If one archetype qualifies, choose that one. If zero archetypes qualify, choose the Unconventional archetype.

 **Calculating Qualifying Archetypes**
 - total all player attriburtes for each attribute. total SC = all five players' SC, SH = all five players' SH, etc
 - Only calculate teh following attributes: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ
 - determine the top 3 total attribute values among those 11
 - determine all Coaching Archetypes that qualify based on the list below

 **Coaching Archetypes**
 - Pure Offense: SC & SH
 - Pure Defense: ID & OD
 - O/D Balance: (SC or SH) and (ID or OD)
 - Rebounding King: RB & ST
 - The Intimidator: (ID or OD) and ST 
 - Mr Fundamentals: 2+ of (PS, BH, RB) | At least two of those three in top-3 
 - Outrun The Competition: ND & AG
 - Cerebral Offense: (SC or SH) and IQ 
 - Cerebral Defense: (ID or OD) and IQ 
 - Pure Athleticism: 2+ of (ST, AG, ND) | At least two of those three in top-3 
 - Pure Discipline: (PS or BH) and IQ 
 - Offensive Athleticism: (SC or SH) and (ST/AG/ND)
 - Defensive Athleticism: (ID or OD) and (AG or ND)
 - Offensive Fundamentals: (SC or SH) and (BH or PS)
 - Defensive Fundamentals: (ID or OD) and (BH or PS)
 - Offensive Rebounding: (SC or SH) and RB
 - Defensive Rebounding: (ID or OD) and RB
 - Mr Unconventional: if none of the above qualify



**Task 1 - Update user collections in the database**
- update each user account in the gob and gob-staging dbs to have the following fields and nested data structures
- "record"
    - "wins": integer
    - "losses": integer
    - "total_games": integer (wins + losses)
    - "win_rate": integer (round(100 * wins / total_games) when total_games > 0, else 0)
    - "discount_wins": integer — subset of wins from games that used **Sim Full Game** or **Sim Rest of Game** at any point (see Bulk sim tracking below)
    - "discount_losses": integer — subset of losses from those same games
    - Invariant: `discount_wins + discount_losses` ≤ `total_games`; each completed user game increments either discount win/loss or neither (never both win and loss)
- "archetypes", which will have the followign nested data structure:
    - "pure_offense": integer
    - "pure_defense": integer
    - "od_balance": integer
    - "rebounding_king": integer
    - "the_intimidator": integer
    - "mr_fundamentals": integer
    - "outrun_the_competition": integer
    - "cerebral_offense": integer
    - "cerebral_defense": integer
    - "pure_athleticism": integer
    - "pure_discipline": integer
    - "offensive_athleticism": integer
    - "defensive_athleticism": integer
    - "offensive_fundamentals": integer
    - "defensive_fundamentals": integer
    - "offensive_rebounding": integer
    - "defensive_rebounding": integer
    - "mr_unconventional": integer
    - "total": integer (sum of all of the above 18 archetypes)

- Every time a user completes a game, we add a win or loss to their user total based on the result of the game
- Every time a user enters are re-enters the court.html screen from the set-linup screen, we add 1 to the chosen archetype
- Note for UI/UX dispaly, we'll always dispaly archetypes as percentages. I assume this can be done simply via the following calculation: archetype/total

---

## Bulk sim tracking (Sim Full Game / Sim Rest of Game)

**Goal:** Geek Points discounting + `record.discount_wins` / `record.discount_losses`. **Not** triggered by Sim Quarter alone or Play Quarter only.

### Game document (`games` collection)

Persist on the game for the whole session (sticky once true):

- `bulk_sim_used`: boolean — `true` if the user ever started a quarter via **Sim Full Game** or **Sim Rest of Game** for this `game_id`.

**How to set:** Frontend sends `advance_method` on every `POST /api/simulate-quarter`:

| Button | `advance_method` |
|--------|------------------|
| Play Quarter | `play_quarter` |
| Sim Quarter | `sim_quarter` |
| Sim Full Game | `sim_full_game` |
| Sim Rest of Game | `sim_rest_of_game` |

Backend on each successful save:

```python
if body.advance_method in ("sim_full_game", "sim_rest_of_game"):
    games_collection.update_one(
        {"_id": game_id_oid},
        {"$set": {"bulk_sim_used": True}},
    )
```

Optional audit array: `quarter_log: [{ "quarter": 1, "advance_method": "play_quarter" }, ...]` (append-only).

**Examples:**

| Session | `bulk_sim_used` |
|---------|-----------------|
| Play all four quarters | `false` |
| Sim Full from pre-game | `true` |
| Play Q1, Sim Rest Q2–Q4 | `true` |
| Sim Quarter each break (no Full/Rest) | `false` |

### At game complete (same hook as `record.wins` / `record.losses`)

After resolving user win/loss for the game (single / tournament / franchise user-played paths):

1. Load game doc (or pass `bulk_sim_used` from summary).
2. `$inc` `record.wins` or `record.losses` and `record.total_games` (recompute `win_rate` in app or via aggregation).
3. If `bulk_sim_used`:
   - `$inc` `record.discount_wins` or `record.discount_losses` (same outcome as step 2).
4. Franchise geek points: in `maybe_award_franchise_win_geek_points` / `maybe_award_franchise_loss_geek_points`, accept `bulk_sim_used: bool` and apply discount (e.g. `delta = max(1, int(delta * 0.5))` or separate reduced ranges — product decision).

**Leaderboard / display:** Primary record = all games; optional UI line “Bulk-sim record: {discount_wins}-{discount_losses}” or exclude discount games from a future “competitive” leaderboard.

**Reference:** [`Gameplay_Buttons_System.md`](../05_GP_Supporting_Systems/Gameplay_Buttons_System.md), [`Geek_Points_System.md`](../00_General_Systems/Geek_Points_System.md), `bootGame.js` (`handleSimFullGame` / `handleButtonClick`).

