# Player Momentum System

**Current state:** Player MO exists as an attribute but is **display-only** — nothing in live gameplay reads or changes it. "Team momentum" is a separate, small legacy in-game system. This doc maps everything that touches either value today, as the starting point for designing the real system.

> Two different things — don't conflate:
> - **Player MO** — per-player attribute, range **−10 to +10** (`player.attributes["MO"]`)
> - **Team momentum** — per-team in-game value, range **-50 to 50** (`team_attributes["momentum"]`)

---

## Player MO (−10 to +10)

| When | Effect | Where |
|---|---|---|
| Game init | Set to **0** for every player, all modes | `player.py:121` (`randomize_game_attributes`) |
| Load | Clamped to −10..+10 | `player.py:16` (`clamp_mo`) |
| **Training — Culture Builder "Inspire"** | **+1 or +2** per player (`randint(1,2)`), clamped; also updates `anchor_MO` | `training_execution_v2.py:624` |
| Gameplay | **Nothing** — never read or written during a game | (none) |
| Display | Red/green pill (−10..+10) | `set-lineup.js`, `training-report.js`, `player-detail.js` |
| Persistence | Saved on the player snapshot in game/franchise/tournament docs; restored on load | `shared.py` (serialize), `api.py` / `franchise_routes.py` (load/write) |

- MO is **excluded from trainable attributes** (no training-point allocation) — "Inspire" is the only thing that moves it.
- A per-archetype `momentum_score` training amplifier is a **TODO, not implemented** (`training_execution_v2.py` ~L724).

---

## Team momentum (0 to 10) — in-game only

In-memory during a game (`team_attributes["momentum"]`), **not persisted**, defaults to 0.

| When | Effect | Where |
|---|---|---|
| **Block** | Offense **−1** (floor 0), defense **+1** (cap 10) | `shot_manager.py:899-900` |
| **3-point shot** | `threshold += THREE_POINT_SHOT_THRESHOLD_INCREASE − randint(1,5) × momentum` → higher momentum = easier 3s | `shot_manager.py:606-608` |

That's the entire team-momentum system today: **blocks shift it, and it only affects 3-point shooting.** (Likely an early-build vestige — reconcile/remove when the real momentum system is designed.)

---

## Other "momentum"-named fields (NOT the above — don't confuse)

- **Play / Defense `momentum`** (0..10) — static field on each play/defense; random 0–10 in tournament/gameplan init; **display only** (FCC, training report, coaching grid). `add_momentum_field_to_plays_defenses.py`, `team_manager.py`, `gameplan_routes.py`.
- **Team `momentum_score`** (−10..+10) — separate team-level attribute; random 0–20 at dev init; clamp defined but **no live logic uses it**.

**Team Momentum**
- Only has a non-zero value during gameplay
- It is an aggregate value of the five active players' MO attribute scores in the lineup, so it's range is -50 to 50, since each player has a MO value range of -10 to 10.
- The court.html screen, MO bar display should treate 0 is teh middle, extend proportioally to -50 on the left with a red fill and proportionally to 50 on teh right with a green fill.

**Player Momentum Moments**
- Blocked shot (blocking player +1 MO, player who's shot is blocked -1 MO)
- Player consecutive shot attempts
    - Note a player's consectuive shots are relative to himself only, not the broader team. he does not need to take consecutive shots among the team to qualify, we simply track each players' shots throughout the entire game.
    - if a player makes his third consecutive shot, + 1 MO and +1 MO for each consecutive make after that.
    - if a player misses his third consecutive shot, -1 MO, and -1 MO for each consecutive miss after that.
    - Qualifying shot details
        - Blocks count as a miss (these are doubly negative for the shooter as he gets a -1 to MO for the block per the point above, and a False added to his consecutive shot list)
        - Shot attempts in HCO, HCT, FCP, OREB Putback, and Fast Break quality to track makes and misses. Shot attempts in Free Throws do not.
- Steal (stealing player +1 MO, player stole from -1 MO)
- And 1 Made Shots: if a player is fouled and he makes his shot, +1 MO. Note this can be doubly good for the shooter as he also gets the True added to his consecutive shots list.
- Dunk (these are not wired yet but will be soon), +1 MO (can be doubly good for the shooter, same as And 1 make). Note if he dunks AND gets fouled, he gets credit for both to his MO, so technically this is a +2 (+1 each for the dunk and the AND 1)
- Charge, -1 to the fouling player, +1 to the player who drew the charge (please verify that we identify a player as drawing the charge, if not I'll add this)
- Shot Clock violation: (40% chance - offense team momentum) for each offensive player that he'll recieve -1 MO (each player gets his own roll) and (40% chance + defense team momentum) for each defensive player that he'll get a +1 MO (each player gets his own roll)
- if a player gets his 5th OREB of the game, +1 MO. Each subsequent OREB after tha tis +1 MO.

**Player Momentum Impact**
- Shot Attempts
    - if a player has a MO > 0, he has a chance for the random calculation for his shot attempt to be random.randint(2,6) instead of random.randint(1.6). This scales by his MO value.
        - MO 1: 10% chance of the improved scale, MO 2: 20% of the improved scale...up to MO 10: 100% chance of improved scale.
    - if a player has a MO < 0, he has a chance for the random calculation for his shot attempt to be random.randint(1,5) instead of random.randint(1,6). This scales by his MO value.
        - MO -1: 10% chance of the reduced scale, MO -2: 20% of the reduced scale...up to MO -10: 100% chance of reduced scale.

**Players' MO Resets**
- All player's MO resets at all quarter breaks and timeouts. They do not reset in a player foul out situation.
- Reset logic
    - All bench players are set to 0
    - All active players with MO > 0 get their MO reduced by random.randint(4,7), with the lowest value that can be reset to being zero. I.e. if player has +1 MO and he rolls a 7 for his reduction, he's reset to 0, not -6.
    - All active plyaers with MO < 0 get their MO increased by random.randint(4,7), with the highest vlaue that can be rest to being zero. I.e. if a player has -3 MO and he rolls a 7 for his increase, he's reset to 0, not 4.
- During the halftime break, from Q2 to Q3, all players' MO resets to 0 with two exceptions:
    - MO 10 resets to random.randint(1,3)
    - MO -10 resets to random.randint(-3,-1)
- If a player makes a Final Shot at a quarter break, add +1 to his MO, based on whatever the above calculations result in for him, to start the next quarter.
- **End of game:** every player's MO resets to 0 (both teams, active + bench) so no in-game momentum persists past the game. Wired at the live game-final detection (`is_final`) before the final save — see `End_Of_Game_System.md`. Code: `reset_all_player_momentum()` in `BackEnd/utils/player_momentum.py`.
